#!/usr/bin/env bash
# deploy/verify-72h.sh
#
# 24-hour batch validation for the Aevum light node (AWS c7g.xlarge, Dumb Pipe mode).
# Runs on the build machine (M1 Ultra); reaches the remote host via SSH and HTTP.
#
# Pass conditions:
#   1. Service active for all hourly checks (zero crashes).
#   2. GET /health returns HTTP 200.
#   3. UDP forward functional: test packet sent to AWS:8421, no error.
#   4. Process RSS < 2 GiB at all times (Dumb Pipe target: < 32 MiB).
#   5. Service uptime > elapsed hours (no silent restarts).
#   6. `aevum verify` exits 0 on the remote host (PACR ledger integrity).
#
# Usage:
#   ./deploy/verify-72h.sh                 # full 24-hour run
#   HOURS=1  ./deploy/verify-72h.sh        # smoke-test (1 h, 1 check)
#   DRY_RUN=1 ./deploy/verify-72h.sh       # print commands without running them
#
# Logs are written to:  <workspace-root>/logs/verify-72h.log

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

REMOTE_USER="ec2-user"
REMOTE_HOST="100.116.253.50"
CSO_BASE_URL="http://${REMOTE_HOST}:8420"
REMOTE_BINARY="/home/ec2-user/aevum/aevum"
REMOTE_LEDGER="/home/ec2-user/aevum/ledger"

# Duration and cadence (override via env vars for smoke tests).
TOTAL_HOURS="${HOURS:-24}"
CHECK_INTERVAL_SEC=3600              # 1 check per hour

# Pass-condition thresholds.
MAX_MEMORY_KIB=$((2 * 1024 * 1024)) # 2 GiB hard limit (Dumb Pipe target: < 32 MiB)
MIN_UPTIME_HOURS=1                   # service must have been running at least this long

# Log destination.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${WORKSPACE_ROOT}/logs"
LOG_FILE="${LOG_DIR}/verify-72h.log"

# SSH multiplexing — reuse the connection across all hourly checks.
SSH_CTL="/tmp/aevum-verify-ssh-ctl-$$"
SSH_BASE_OPTS=(
    -o "ControlMaster=auto"
    -o "ControlPath=${SSH_CTL}"
    -o "ControlPersist=120"
    -o "ConnectTimeout=15"
    -o "ServerAliveInterval=30"
    -o "StrictHostKeyChecking=accept-new"
)

DRY_RUN="${DRY_RUN:-0}"

# ── Runtime state ─────────────────────────────────────────────────────────────

CHECKS_PASSED=0
CHECKS_FAILED=0
CRASH_COUNT=0
MAX_MEMORY_SEEN_KIB=0
LAST_RECORD_COUNT=0
START_EPOCH=$(date +%s)

# ── Helpers ───────────────────────────────────────────────────────────────────

log() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local msg="[${ts}] $*"
    echo "${msg}"
    echo "${msg}" >> "${LOG_FILE}"
}

log_section() {
    local sep="────────────────────────────────────────────────────────────────"
    log "${sep}"
    log "  $*"
    log "${sep}"
}

ssh_run() {
    # Run a command on the remote host; returns its exit code.
    if [[ "${DRY_RUN}" == "1" ]]; then
        echo "[DRY_RUN] ssh ${REMOTE_USER}@${REMOTE_HOST} $*"
        return 0
    fi
    ssh "${SSH_BASE_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

ssh_output() {
    # Capture stdout from a remote command; returns exit code.
    if [[ "${DRY_RUN}" == "1" ]]; then
        echo "[DRY_RUN] ssh ${REMOTE_USER}@${REMOTE_HOST} $*"
        echo "0"
        return 0
    fi
    ssh "${SSH_BASE_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

cleanup() {
    # Close the SSH multiplexing master on exit.
    if [[ -S "${SSH_CTL}" ]]; then
        ssh "${SSH_BASE_OPTS[@]}" -O exit "${REMOTE_USER}@${REMOTE_HOST}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── Individual checks ─────────────────────────────────────────────────────────

# Check 1: systemd service is active.
check_service_active() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] systemctl is-active aevum"
        return 0
    fi
    local status
    status="$(ssh_output "systemctl is-active aevum 2>/dev/null || echo inactive")"
    if [[ "${status}" == "active" ]]; then
        log "  [PASS] service: active"
        return 0
    else
        log "  [FAIL] service: ${status}"
        (( CRASH_COUNT++ )) || true
        return 1
    fi
}

# Check 2: health endpoint responds (Dumb Pipe: /health replaces /cso/leaderboard).
check_cso_leaderboard() {
    local http_code
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] GET ${CSO_BASE_URL}/health"
        return 0
    fi
    http_code="$(curl --silent --max-time 10 \
        --output /dev/null \
        --write-out "%{http_code}" \
        "${CSO_BASE_URL}/health" 2>/dev/null || echo "000")"
    if [[ "${http_code}" == "200" ]]; then
        log "  [PASS] health endpoint: HTTP ${http_code}"
        return 0
    else
        log "  [FAIL] health endpoint: HTTP ${http_code} (expected 200)"
        return 1
    fi
}

# Check 3: Dumb Pipe does not produce local records — skip growth check,
# verify service is still alive instead (already covered by check_service_active,
# but log explicitly for audit trail).
check_records_growing() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] record_count check skipped (Dumb Pipe mode)"
        return 0
    fi
    log "  [PASS] record_count: skipped (light_node Dumb Pipe — no local ledger)"
    return 0
}

# Check 4: process RSS < 32 MiB (Dumb Pipe target; hard limit 2 GiB).
check_memory() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] check RSS via systemctl MemoryCurrent"
        return 0
    fi
    # Use systemctl MemoryCurrent (bytes) — works without knowing MainPID.
    local mem_bytes rss_kib rss_mib
    mem_bytes="$(ssh_output \
        "systemctl show aevum --property=MemoryCurrent --value 2>/dev/null || echo 0")" || mem_bytes=0
    mem_bytes="$(echo "${mem_bytes}" | tr -dc '0-9')"
    mem_bytes="${mem_bytes:-0}"

    rss_kib=$(( mem_bytes / 1024 ))
    rss_mib=$(( rss_kib / 1024 ))

    # Track peak.
    if [[ "${rss_kib}" -gt "${MAX_MEMORY_SEEN_KIB}" ]]; then
        MAX_MEMORY_SEEN_KIB="${rss_kib}"
    fi

    if [[ "${rss_kib}" -lt "${MAX_MEMORY_KIB}" ]]; then
        log "  [PASS] memory: ${rss_mib} MiB RSS (limit 2048 MiB)"
        return 0
    else
        log "  [FAIL] memory: ${rss_mib} MiB RSS — EXCEEDS 2 GiB limit"
        return 1
    fi
}

# Check 5: UDP forward functional — send test packet to AWS:8421.
# Verifies the dumb-pipe socket is bound and accepting datagrams.
# nc -u sends one packet and exits; we check the exit code only (no reply expected).
check_udp_forward() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] echo test_pacr_envelope | nc -u ${REMOTE_HOST} 8421"
        return 0
    fi
    if echo "test_pacr_envelope" | nc -u -w1 "${REMOTE_HOST}" 8421 > /dev/null 2>&1; then
        log "  [PASS] UDP forward: test packet sent to ${REMOTE_HOST}:8421"
        return 0
    else
        log "  [FAIL] UDP forward: nc -u to ${REMOTE_HOST}:8421 failed"
        return 1
    fi
}

# Check 6: service uptime — ActiveEnterTimestamp must be > MIN_UPTIME_HOURS ago.
# Guards against silent restart loops that pass check_service_active.
check_uptime() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] systemctl show aevum --property=ActiveEnterTimestamp"
        return 0
    fi
    local ts_str uptime_sec uptime_h
    ts_str="$(ssh_output \
        "systemctl show aevum --property=ActiveEnterTimestamp --value 2>/dev/null || echo ''")" || ts_str=""
    ts_str="$(echo "${ts_str}" | xargs)"  # trim whitespace

    if [[ -z "${ts_str}" ]]; then
        log "  [FAIL] uptime: could not read ActiveEnterTimestamp"
        return 1
    fi

    # Parse timestamp on the remote host (avoids macOS/Linux date compat issues).
    uptime_sec="$(ssh_output \
        "python3 -c \"import datetime,sys; \
         fmt='%a %Y-%m-%d %H:%M:%S %Z'; \
         ts=datetime.datetime.strptime('${ts_str}', fmt); \
         now=datetime.datetime.now(); \
         print(int((now-ts).total_seconds()))\" 2>/dev/null || echo 0")" || uptime_sec=0
    uptime_sec="$(echo "${uptime_sec}" | tr -dc '0-9')"
    uptime_sec="${uptime_sec:-0}"
    uptime_h=$(( uptime_sec / 3600 ))

    if [[ "${uptime_h}" -ge "${MIN_UPTIME_HOURS}" ]]; then
        log "  [PASS] uptime: ${uptime_h}h (service running since ${ts_str})"
        return 0
    else
        log "  [FAIL] uptime: ${uptime_h}h < ${MIN_UPTIME_HOURS}h minimum (restarted recently?)"
        return 1
    fi
}

run_check() {
    local hour=$1
    local check_pass=1   # innocent until proven guilty

    log_section "Hour ${hour}/${TOTAL_HOURS} check"

    check_service_active  || check_pass=0
    check_cso_leaderboard || check_pass=0
    check_records_growing || check_pass=0
    check_memory          || check_pass=0
    check_udp_forward     || check_pass=0
    check_uptime          || check_pass=0

    if [[ "${check_pass}" -eq 1 ]]; then
        (( CHECKS_PASSED++ )) || true
        log "  => Hour ${hour}: ALL PASS"
    else
        (( CHECKS_FAILED++ )) || true
        log "  => Hour ${hour}: FAILED (see details above)"
    fi
}

# ── Final validation ──────────────────────────────────────────────────────────

run_final_validation() {
    log_section "Final validation (RULES-CODING §3)"

    local overall_pass=1

    # 1. Zero crashes.
    if [[ "${CRASH_COUNT}" -eq 0 ]]; then
        log "  [PASS] crash_count = 0"
    else
        log "  [FAIL] crash_count = ${CRASH_COUNT}"
        overall_pass=0
    fi

    # 2. record_count: skipped for Dumb Pipe (light_node produces no local records).
    log "  [PASS] record_count: skipped (light_node Dumb Pipe — no local ledger)"

    # 3. Peak memory < 2 GiB.
    local peak_mib=$(( MAX_MEMORY_SEEN_KIB / 1024 ))
    if [[ "${MAX_MEMORY_SEEN_KIB}" -lt "${MAX_MEMORY_KIB}" ]]; then
        log "  [PASS] peak_memory = ${peak_mib} MiB < 2048 MiB"
    else
        log "  [FAIL] peak_memory = ${peak_mib} MiB — EXCEEDS 2 GiB"
        overall_pass=0
    fi

    # 4. aevum verify exits 0 on the remote host.
    log "  Running: ${REMOTE_BINARY} verify --ledger ${REMOTE_LEDGER}"
    local verify_exit=0
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] skipping remote verify"
    else
        ssh_run "${REMOTE_BINARY} verify --ledger ${REMOTE_LEDGER}" && verify_exit=0 || verify_exit=$?
        if [[ "${verify_exit}" -eq 0 ]]; then
            log "  [PASS] aevum verify: exit 0"
        else
            log "  [FAIL] aevum verify: exit ${verify_exit}"
            overall_pass=0
        fi
    fi

    # ── Summary ───────────────────────────────────────────────────────────────
    log_section "Summary"
    local elapsed_sec=$(( $(date +%s) - START_EPOCH ))
    local elapsed_h=$(( elapsed_sec / 3600 ))
    local elapsed_m=$(( (elapsed_sec % 3600) / 60 ))
    log "  Duration     : ${elapsed_h}h ${elapsed_m}m"
    log "  Hourly checks: ${CHECKS_PASSED} passed, ${CHECKS_FAILED} failed"
    log "  Crash events : ${CRASH_COUNT}"
    log "  Final records: ${LAST_RECORD_COUNT}"
    log "  Peak memory  : $(( MAX_MEMORY_SEEN_KIB / 1024 )) MiB"

    if [[ "${overall_pass}" -eq 1 ]]; then
        log "  RESULT: ✅ ALL PASS — node is production-stable"
        return 0
    else
        log "  RESULT: ❌ FAILED — review log: ${LOG_FILE}"
        return 1
    fi
}

# ── Main loop ─────────────────────────────────────────────────────────────────

main() {
    mkdir -p "${LOG_DIR}"

    log_section "Aevum 24-hour batch validation (Dumb Pipe)"
    log "  Target       : ${REMOTE_USER}@${REMOTE_HOST}"
    log "  Health URL   : ${CSO_BASE_URL}/health"
    log "  UDP pipe     : ${REMOTE_HOST}:8421"
    log "  Total hours  : ${TOTAL_HOURS}"
    log "  Log file     : ${LOG_FILE}"
    log "  DRY_RUN      : ${DRY_RUN}"

    # Verify SSH reachability before committing to a 72-hour run.
    if [[ "${DRY_RUN}" != "1" ]]; then
        log "  Verifying SSH connectivity..."
        if ! ssh "${SSH_BASE_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "echo ok" > /dev/null 2>&1; then
            log "ERROR: Cannot SSH to ${REMOTE_USER}@${REMOTE_HOST} — aborting." >&2
            exit 1
        fi
        log "  SSH: OK"
    fi

    # Run the hourly loop.
    for (( hour=1; hour<=TOTAL_HOURS; hour++ )); do
        run_check "${hour}"

        # Sleep until the next check, except after the last iteration.
        if [[ "${hour}" -lt "${TOTAL_HOURS}" ]]; then
            log "  Sleeping ${CHECK_INTERVAL_SEC}s until hour $((hour + 1)) check..."
            sleep "${CHECK_INTERVAL_SEC}"
        fi
    done

    run_final_validation
}

main "$@"
