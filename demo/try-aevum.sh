#!/usr/bin/env bash
# demo/try-aevum.sh
#
# Zero-install demo: curl the live Aevum MCP server.
# Shows token compression via aevum_filter and causal memory via aevum_remember.

set -euo pipefail

MCP_URL="${1:-https://mcp.aevum.network}"

echo "🔬 Aevum MCP Server Demo"
echo "   Endpoint: $MCP_URL"
echo ""

# 1. Health check
echo "─── 1. Health Check ───────────────────────────────────"
health=$(curl -sf "$MCP_URL/health" 2>/dev/null) || { echo "❌ Server unreachable at $MCP_URL"; exit 1; }
echo "   $health"
echo ""

# 2. List tools
echo "─── 2. Available Tools ───────────────────────────────"
tools=$(curl -sf "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' 2>/dev/null)
echo "$tools" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for t in d.get('result',{}).get('tools',[]):
    print(f\"   🔧 {t['name']}: {t.get('description','')[:80]}\")
" 2>/dev/null || echo "   (tools list unavailable)"
echo ""

# 3. Remember
echo "─── 3. aevum_remember ─────────────────────────────────"
remember=$(curl -sf "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0","id":2,"method":"tools/call",
    "params":{"name":"aevum_remember","arguments":{
      "text":"Every erased bit costs k_B × T × ln(2) joules. This is Landauer principle — the thermodynamic floor of computation."
    }}
  }' 2>/dev/null)
echo "$remember" | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d.get('result',{})
if isinstance(r.get('content'), list) and r['content']:
    inner = json.loads(r['content'][0].get('text','{}'))
    print(f\"   Causal ID: {inner.get('causal_id','?')}\")
    print(f\"   S_T (statistical complexity): {inner.get('s_t','?')}\")
    print(f\"   H_T (entropy rate):           {inner.get('h_t','?')}\")
    print(f\"   Recorded: {inner.get('recorded','?')}\")
else:
    print(f\"   {json.dumps(r, indent=2)}\")
" 2>/dev/null || echo "   $remember"
echo ""

# 4. Filter (the 90% compression demo)
echo "─── 4. aevum_filter (90% token compression) ──────────"
bloated_text="The model context protocol provides a standardized way for AI assistants to interact with external tools and data sources. It was developed by Anthropic and released in November 2024. The protocol defines a JSON-RPC 2.0 based communication layer. There are multiple transport mechanisms supported including stdio for local communication and HTTP with Server-Sent Events for remote communication. The key insight from computational mechanics is that statistical complexity S_T captures the minimal causal structure needed to predict a process, while entropy rate H_T measures residual unpredictability."
echo "   Input: ${#bloated_text} chars"

filtered=$(curl -sf "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",
    \"params\":{\"name\":\"aevum_filter\",\"arguments\":{
      \"text\":\"$bloated_text\"
    }}
  }" 2>/dev/null)
output_len=$(echo "$filtered" | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d.get('result',{})
if isinstance(r.get('content'), list) and r['content']:
    text = r['content'][0].get('text','')
    inner = json.loads(text) if text.startswith('{') else {'filtered': text}
    out = inner.get('filtered', inner.get('summary', str(inner)))
    print(len(out))
else:
    print(len(json.dumps(r)))
" 2>/dev/null || echo "?")
echo "   Output: ${output_len} chars"
echo "   Compression: ~$((100 - (output_len * 100 / ${#bloated_text})))%"
echo ""

echo "✅ Demo complete."
echo ""
echo "Add to your Claude Desktop config to use Aevum in every conversation:"
echo ""
echo '  { "mcpServers": { "aevum": { "url": "https://mcp.aevum.network" } } }'
echo ""
