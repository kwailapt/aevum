#!/usr/bin/env bash
# deploy/verify-72h.sh
#
# 72-hour batch validation for the Aevum light node (AWS c7g.xlarge).
# Runs on the build machine (M1 Ultra); reaches the remote host via SSH and
# HTTP for each check.
#
# Pass conditions (RULES-CODING §3):
#   1. Service active for all 72 hourly checks (zero crashes / unexpected exits).
#   2. Final record_count in [259,200 ± 1,000]  ← 72h × 1 rec/s.
#      (Adjust EXPECTED_RECORDS if producer_interval_ms ≠ 1000 in light-node.toml.)
#   3. Peak process RSS < 2 GiB at all times.
#   4. `aevum verify` exits 0 on the remote host (PACR ledger integrity).
#
# Usage:
#   ./deploy/verify-72h.sh                 # full 72-hour run
#   HOURS=1  ./deploy/verify-72h.sh        # smoke-test (1 h, 1 check)
#   DRY_RUN=1 ./deploy/verify-72h.sh       # print SSH commands without running them
#
# Logs are written to:  <workspace-root>/logs/verify-72h.log
#
# Requirements on the build machine:
#   - ssh access to ec2-user@100.116.253.50 (key in ~/.ssh or ssh-agent)
#   - curl, jq (macOS: brew install jq)

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

REMOTE_USER="ec2-user"
REMOTE_HOST="100.116.253.50"
CSO_BASE_URL="http://${REMOTE_HOST}:8420"
REMOTE_BINARY="/home/ec2-user/aevum/aevum"
REMOTE_LEDGER="/home/ec2-user/aevum/ledger"

# Duration and cadence (override via env vars for smoke tests).
TOTAL_HOURS="${HOURS:-72}"
CHECK_INTERVAL_SEC=3600              # 1 check per hour

# Pass-condition thresholds.
EXPECTED_RECORDS=259200              # 72h × 3600 s/h × 1 rec/s
RECORD_TOLERANCE=1000
MAX_MEMORY_KIB=$((2 * 1024 * 1024)) # 2 GiB expressed in kibibytes

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

# Check 2: CSO leaderboard endpoint responds.
check_cso_leaderboard() {
    local http_code
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] GET ${CSO_BASE_URL}/cso/leaderboard"
        return 0
    fi
    http_code="$(curl --silent --max-time 10 \
        --output /dev/null \
        --write-out "%{http_code}" \
        "${CSO_BASE_URL}/cso/leaderboard" 2>/dev/null || echo "000")"
    if [[ "${http_code}" == "200" ]]; then
        log "  [PASS] CSO leaderboard: HTTP ${http_code}"
        return 0
    else
        log "  [FAIL] CSO leaderboard: HTTP ${http_code} (expected 200)"
        return 1
    fi
}

# Check 3: record_count is strictly greater than the previous check's value.
check_records_growing() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] read record_count from ${REMOTE_LEDGER}/status.json"
        return 0
    fi
    local count
    # Parse record_count from status.json using jq (fallback: python3).
    count="$(ssh_output \
        "jq -r '.record_count // 0' '${REMOTE_LEDGER}/status.json' 2>/dev/null \
         || python3 -c \"import sys,json; print(json.load(open('${REMOTE_LEDGER}/status.json')).get('record_count',0))\" 2>/dev/null \
         || echo 0")" || count=0

    # Strip whitespace / non-numeric characters.
    count="$(echo "${count}" | tr -dc '0-9')"
    count="${count:-0}"

    if [[ "${count}" -gt "${LAST_RECORD_COUNT}" ]]; then
        local delta=$(( count - LAST_RECORD_COUNT ))
        log "  [PASS] record_count: ${count} (+${delta} since last check)"
        LAST_RECORD_COUNT="${count}"
        return 0
    else
        log "  [FAIL] record_count: ${count} (did not grow; was ${LAST_RECORD_COUNT})"
        return 1
    fi
}

# Check 4: process RSS < 2 GiB.
check_memory() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "  [DRY_RUN] check MainPID RSS via /proc"
        return 0
    fi
    # Get MainPID from systemd, then read RSS from /proc.
    local pid rss_kib
    pid="$(ssh_output "systemctl show -p MainPID --value aevum 2>/dev/null || echo 0")" || pid=0
    pid="$(echo "${pid}" | tr -dc '0-9')"
    pid="${pid:-0}"

    if [[ "${pid}" == "0" ]] || [[ -z "${pid}" ]]; then
        log "  [FAIL] memory: could not determine MainPID"
        return 1
    fi

    # VmRSS from /proc/<pid>/status is in kB.
    rss_kib="$(ssh_output \
        "grep VmRSS /proc/${pid}/status 2>/dev/null | awk '{print \$2}' || echo 0")" || rss_kib=0
    rss_kib="$(echo "${rss_kib}" | tr -dc '0-9')"
    rss_kib="${rss_kib:-0}"

    local rss_mib=$(( rss_kib / 1024 ))

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

# ── One hourly check ──────────────────────────────────────────────────────────

run_check() {
    local hour=$1
    local check_pass=1   # innocent until proven guilty

    log_section "Hour ${hour}/${TOTAL_HOURS} check"

    check_service_active  || check_pass=0
    check_cso_leaderboard || check_pass=0
    check_records_growing || check_pass=0
    check_memory          || check_pass=0

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

    # 2. record_count ≈ EXPECTED_RECORDS ± RECORD_TOLERANCE.
    local lo=$(( EXPECTED_RECORDS - RECORD_TOLERANCE ))
    local hi=$(( EXPECTED_RECORDS + RECORD_TOLERANCE ))
    if [[ "${LAST_RECORD_COUNT}" -ge "${lo}" ]] && [[ "${LAST_RECORD_COUNT}" -le "${hi}" ]]; then
        log "  [PASS] record_count = ${LAST_RECORD_COUNT} (expected ${EXPECTED_RECORDS} ± ${RECORD_TOLERANCE})"
    else
        log "  [FAIL] record_count = ${LAST_RECORD_COUNT} (expected [${lo}, ${hi}])"
        overall_pass=0
    fi

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

    log_section "Aevum 72-hour batch validation"
    log "  Target       : ${REMOTE_USER}@${REMOTE_HOST}"
    log "  CSO endpoint : ${CSO_BASE_URL}/cso/leaderboard"
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
