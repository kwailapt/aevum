#!/usr/bin/env bash
# deploy/monitor-72h.sh
#
# Pillar: II/III. PACR field: Λ/Γ.
# 72-hour steady-state monitor for aevum-mcp-server.
#
# Samples every 60 seconds:
#   - RSS (resident set size, MB)    — Pillar I: O(n) memory growth
#   - Ledger size (bytes)            — Pillar II: thermodynamic accumulation
#   - DAG record count               — Pillar III: causal density
#   - MCP /health reachability       — liveness
#
# Output: TSV to stdout + ~/aevum_monitor_72h.tsv
# Stop:   Ctrl-C or after 72 hours (4320 samples)

set -euo pipefail

LEDGER="${LEDGER_PATH:-$HOME/.aevum/mcp.ledger}"
MCP_HTTP="${MCP_HTTP:-http://localhost:8889}"
OUT="$HOME/aevum_monitor_72h.tsv"
MAX_SAMPLES=4320        # 72h × 60 samples/h
INTERVAL=60             # seconds

# Find the aevum-mcp-server PID (HTTP transport instance).
find_pid() {
    pgrep -f "aevum-mcp-server.*transport.*http" 2>/dev/null | head -1 || echo ""
}

# RSS in MB for a given PID.
rss_mb() {
    local pid="$1"
    if [[ -z "$pid" ]]; then echo "N/A"; return; fi
    # macOS ps reports RSS in KB.
    ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.1f", $1/1024}' || echo "N/A"
}

# Ledger file size in bytes.
ledger_bytes() {
    stat -f "%z" "$LEDGER" 2>/dev/null || echo "0"
}

# DAG record count — query /health-extended or derive from ledger size.
# Ledger header = 8 bytes; each record ≈ 256 bytes (conservative estimate).
dag_records() {
    local sz
    sz=$(ledger_bytes)
    if [[ "$sz" -le 8 ]]; then echo "0"; return; fi
    echo $(( (sz - 8) / 256 ))
}

# HTTP health check.
health_check() {
    curl -sf --max-time 2 "$MCP_HTTP/health" 2>/dev/null | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(d.get('status','err'))" 2>/dev/null || echo "down"
}

# Header.
printf "%-24s\t%-6s\t%-12s\t%-10s\t%-8s\n" \
    "timestamp" "rss_mb" "ledger_bytes" "dag_est" "health" | tee -a "$OUT"
printf "%-24s\t%-6s\t%-12s\t%-10s\t%-8s\n" \
    "------------------------" "------" "------------" "----------" "--------" | tee -a "$OUT"

echo "▶ Monitor started. Output → $OUT"
echo "  Sampling every ${INTERVAL}s for up to ${MAX_SAMPLES} samples (72h)."
echo "  Press Ctrl-C to stop."
echo ""

count=0
while [[ $count -lt $MAX_SAMPLES ]]; do
    ts=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
    pid=$(find_pid)
    rss=$(rss_mb "$pid")
    lb=$(ledger_bytes)
    dag=$(dag_records)
    health=$(health_check)

    row=$(printf "%-24s\t%-6s\t%-12s\t%-10s\t%-8s" "$ts" "$rss" "$lb" "$dag" "$health")
    echo "$row" | tee -a "$OUT"

    (( count++ )) || true
    sleep "$INTERVAL"
done

echo ""
echo "✅ 72h monitor complete. $(wc -l < "$OUT") rows in $OUT"
