#!/usr/bin/env bash
# resurrect_aevum.sh — Aevum Universe Resurrection Protocol
# ==========================================================
# Restarts all four core Aevum daemons after a reboot or process amnesia.
# Each process is launched with nohup so it survives terminal closure.
# Logs land in /tmp/ for easy tail-following.
#
# Usage:
#   cd /Volumes/Aevum/Obsidian/Opus_agi
#   bash resurrect_aevum.sh
#
# To follow logs afterwards:
#   tail -f /tmp/a2a_router.log
#   tail -f /tmp/wiki_agent.log
#   tail -f /tmp/oracle_agent.log
#   tail -f /tmp/ext_raw_ingestor.log

set -euo pipefail

WORKSPACE="/Volumes/Aevum/Obsidian/Opus_agi"
cd "$WORKSPACE"

# Activate the project venv so all dependencies (uvicorn, fastapi, etc.) are available
# shellcheck disable=SC1091
source "$WORKSPACE/.venv/bin/activate"

export PYTHONPATH="$WORKSPACE"

# Load .env if present (API keys etc.)
if [[ -f "$WORKSPACE/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$WORKSPACE/.env"
    set +a
    echo "[resurrect] .env loaded"
fi

# ---------------------------------------------------------------------------
# Helper: kill any existing instance of a pattern before relaunching,
# so re-running the script does not stack duplicate processes.
# ---------------------------------------------------------------------------
stop_existing() {
    local pattern="$1"
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "[resurrect] Stopping existing '$pattern' (PIDs: $pids)"
        kill $pids 2>/dev/null || true
        sleep 1
    fi
}

# ---------------------------------------------------------------------------
# 1. A2A Router — causal bridge on port 8420
# ---------------------------------------------------------------------------
stop_existing "ai2ai/main.py"
nohup python3 ai2ai/main.py > /tmp/a2a_router.log 2>&1 &
A2A_PID=$!
echo "[resurrect] A2A Router      → PID $A2A_PID  log: /tmp/a2a_router.log"

# ---------------------------------------------------------------------------
# 2. Wiki Agent — local knowledge agent
# ---------------------------------------------------------------------------
stop_existing "ai2ai/wiki_agent.py"
nohup python3 ai2ai/wiki_agent.py > /tmp/wiki_agent.log 2>&1 &
WIKI_PID=$!
echo "[resurrect] Wiki Agent       → PID $WIKI_PID  log: /tmp/wiki_agent.log"

# ---------------------------------------------------------------------------
# 3. Oracle Agent — Tier-3 oracle on port 9002
# ---------------------------------------------------------------------------
stop_existing "oracle_agent.py"
nohup python3 oracle_agent.py > /tmp/oracle_agent.log 2>&1 &
ORACLE_PID=$!
echo "[resurrect] Oracle Agent     → PID $ORACLE_PID  log: /tmp/oracle_agent.log"

# ---------------------------------------------------------------------------
# 4. 12h External Raw Ingestor daemon (43200s sleep loop)
# ---------------------------------------------------------------------------
stop_existing "ext_raw_ingestor.py"
nohup python3 ext_raw_ingestor.py > /tmp/ext_raw_ingestor.log 2>&1 &
INGEST_PID=$!
echo "[resurrect] Ext Raw Ingestor → PID $INGEST_PID  log: /tmp/ext_raw_ingestor.log"

# ---------------------------------------------------------------------------
# Health check — wait up to 10 s for port 8420 to open
# ---------------------------------------------------------------------------
echo ""
echo "[resurrect] Waiting for port 8420 (A2A Router)..."
for i in $(seq 1 10); do
    if lsof -i :8420 -sTCP:LISTEN -t > /dev/null 2>&1; then
        echo "[resurrect] Port 8420 is LISTENING after ${i}s — Aevum Universe online."
        break
    fi
    sleep 1
    if [[ $i -eq 10 ]]; then
        echo "[resurrect] WARNING: port 8420 not yet open after 10s."
        echo "            Check /tmp/a2a_router.log for startup errors."
    fi
done

echo ""
echo "PIDs written to /tmp/aevum_pids.txt"
cat > /tmp/aevum_pids.txt << PIDEOF
a2a_router:      $A2A_PID
wiki_agent:      $WIKI_PID
oracle_agent:    $ORACLE_PID
ext_raw_ingestor: $INGEST_PID
PIDEOF
cat /tmp/aevum_pids.txt

echo ""
echo "=== Aevum Universe Reignited ==="
echo "Follow all logs: tail -f /tmp/a2a_router.log /tmp/wiki_agent.log /tmp/oracle_agent.log /tmp/ext_raw_ingestor.log"
