#!/usr/bin/env bash
# deploy/paperclip-poc.sh
#
# Pillar: III. PACR field: Γ/P.
# Paperclip PoC — heartbeat → aevum_settle → observe ρ convergence.
#
# Simulates a Paperclip agent pair exchanging computational work.
# Each heartbeat sends an aevum_settle call with randomised lambda_joules
# and phi_before/phi_after values. The ρ (causal return rate) should
# converge toward a stable EMA within ~20 interactions (α=0.1).
#
# Usage:
#   ./paperclip-poc.sh [mcp_url] [interactions] [interval_sec]
# Defaults:
#   mcp_url      = http://localhost:8889
#   interactions = 30
#   interval_sec = 2
#
# Output: TSV showing rho convergence per heartbeat.

set -euo pipefail

MCP_URL="${1:-http://localhost:8889}"
N="${2:-30}"
INTERVAL="${3:-2}"

# Agent IDs must be pure hex strings (settle tool parses as u128 hex).
# Generate 32-char hex IDs (128-bit) using Python for portability.
SOURCE_ID=$(python3 -c "import random; print(f'{random.randrange(16**32):032x}')")
TARGET_ID=$(python3 -c "import random; print(f'{random.randrange(16**32):032x}')")

echo "Paperclip PoC — ρ convergence test"
echo "  MCP endpoint : $MCP_URL"
echo "  Source agent : $SOURCE_ID"
echo "  Target agent : $TARGET_ID"
echo "  Interactions : $N  (interval: ${INTERVAL}s)"
echo ""
printf "%-5s\t%-10s\t%-10s\t%-10s\t%-12s\n" "i" "lambda_J" "phi_ratio" "rho" "reputation"
printf "%-5s\t%-10s\t%-10s\t%-10s\t%-12s\n" "-----" "----------" "----------" "----------" "------------"

# Landauer floor at 300K ≈ 2.854e-21 J.  We simulate realistic micro-watt compute:
# lambda ranges 1e-6 to 1e-4 J (millijoule ops), phi 0.3..0.9 range.
LANDAUER_FLOOR="2.854e-21"

rho_prev=0.0

for i in $(seq 1 "$N"); do
    # Randomise lambda: 1e-6..1e-4 J (representative µ-Joule compute)
    lambda=$(python3 -c "import random,math; print(f'{random.uniform(1e-6,1e-4):.6e}')")

    # phi_before: random 0.3..0.8; phi_after: phi_before + random improvement
    phi_before=$(python3 -c "import random; print(f'{random.uniform(0.3,0.8):.4f}')")
    phi_after=$(python3 -c "
import random
pb=$phi_before
delta=random.uniform(-0.05, 0.15)
pa=max(0.0, min(1.0, pb+delta))
print(f'{pa:.4f}')
")
    phi_ratio=$(python3 -c "print(f'{float(\"$phi_after\")/float(\"$phi_before\"):.4f}')" 2>/dev/null || echo "1.0")

    # Call aevum_settle via MCP HTTP JSON-RPC.
    response=$(curl -sf --max-time 5 \
        -H "Content-Type: application/json" \
        -d "{
            \"jsonrpc\": \"2.0\",
            \"id\": $i,
            \"method\": \"tools/call\",
            \"params\": {
                \"name\": \"aevum_settle\",
                \"arguments\": {
                    \"source_agent_id\": \"$SOURCE_ID\",
                    \"target_agent_id\": \"$TARGET_ID\",
                    \"lambda_joules\": $lambda,
                    \"phi_before\": $phi_before,
                    \"phi_after\": $phi_after
                }
            }
        }" \
        "$MCP_URL" 2>/dev/null) || { echo "  ERROR: MCP server unreachable at $MCP_URL"; exit 1; }

    # Extract ρ and reputation_score from the MCP tool result.
    # HTTP transport returns result as a flat object (not stdio content[].text).
    rho=$(echo "$response" | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d.get('result',{})
# HTTP flat result
if 'rho' in r:
    print(f\"{r['rho']:.6f}\")
# stdio content[].text wrapper
elif isinstance(r.get('content'), list) and r['content']:
    text=r['content'][0].get('text','{}')
    inner=json.loads(text)
    print(f\"{inner.get('rho',0.0):.6f}\")
else:
    print('0.000000')
" 2>/dev/null || echo "0.000000")

    reputation=$(echo "$response" | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d.get('result',{})
if 'reputation_score' in r:
    print(f\"{r['reputation_score']:.4f}\")
elif isinstance(r.get('content'), list) and r['content']:
    text=r['content'][0].get('text','{}')
    inner=json.loads(text)
    print(f\"{inner.get('reputation_score',0.0):.4f}\")
else:
    print('0.0000')
" 2>/dev/null || echo "0.0000")

    printf "%-5s\t%-10s\t%-10s\t%-10s\t%-12s\n" \
        "$i" "$lambda" "$phi_ratio" "$rho" "$reputation"

    rho_prev=$rho
    sleep "$INTERVAL"
done

echo ""
echo "✅ PoC complete. Final ρ = $rho_prev"
echo ""
echo "ρ convergence analysis:"
echo "  EMA α=0.1 → converges within ~20 interactions (τ ≈ 1/α = 10 steps)."
echo "  ρ → phi_after/phi_before EMA reflects sustained causal return rate."
echo "  Stable ρ > 1.0: agent produces more causal structure than it consumes."
echo "  Stable ρ < 1.0: agent is a net consumer — investigate or throttle."
