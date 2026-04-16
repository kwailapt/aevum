#!/usr/bin/env bash
# benchmarks/filter-benchmark.sh
#
# Reproducible benchmark for aevum_filter compression rates.
# Tests 6 input types against the live server and prints a results table.
#
# Usage:
#   bash benchmarks/filter-benchmark.sh [mcp_url]
# Default:
#   mcp_url = https://mcp.aevum.network

set -euo pipefail

MCP_URL="${1:-https://mcp.aevum.network}"

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  AEVUM FILTER — REPRODUCIBLE BENCHMARK"
echo "  Endpoint: $MCP_URL"
echo "  Date:     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Health check
health=$(curl -sf --max-time 5 "$MCP_URL/health" 2>/dev/null) || {
    echo "ERROR: Server unreachable at $MCP_URL"
    exit 1
}
echo "  Server: $health"
echo ""

run_test() {
    local name="$1"
    local content="$2"
    local input_len=${#content}

    local payload
    payload=$(python3 -c "
import json, sys
print(json.dumps({
    'jsonrpc': '2.0', 'id': 1,
    'method': 'tools/call',
    'params': {'name': 'aevum_filter', 'arguments': {'content': sys.argv[1]}}
}))
" "$content")

    local result
    result=$(curl -sf --max-time 10 \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$MCP_URL" 2>/dev/null) || {
        printf "  %-45s  ERROR\n" "$name"
        return
    }

    local output_len kept total
    output_len=$(echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d.get('result', {})
print(len(r.get('content', '')))
" 2>/dev/null || echo "?")

    kept=$(echo "$result" | python3 -c "
import sys, json; d=json.load(sys.stdin); print(d.get('result',{}).get('kept_chunks','?'))
" 2>/dev/null || echo "?")

    total=$(echo "$result" | python3 -c "
import sys, json; d=json.load(sys.stdin); print(d.get('result',{}).get('total_chunks','?'))
" 2>/dev/null || echo "?")

    local compression
    if [ "$output_len" != "?" ] && [ "$input_len" -gt 0 ]; then
        compression=$(python3 -c "print(round((1 - $output_len / $input_len) * 100))")
    else
        compression="?"
    fi

    printf "  %-45s %6s → %6s  %4s%%  (%s/%s chunks)\n" \
        "$name" "$input_len" "$output_len" "$compression" "$kept" "$total"
}

echo "  Input Type                                   Input    Output  Comp   Chunks"
echo "  ─────────────────────────────────────────────────────────────────────────────"

# Test 1: Pure repetition
REPEAT=""
for i in $(seq 1 50); do REPEAT="${REPEAT}As I mentioned before, "; done
REPEAT="${REPEAT}The answer is 42."
run_test "Pure repetition (50× phrase + 1 answer)" "$REPEAT"

# Test 2: Navigation HTML boilerplate
run_test "Navigation-only HTML" \
    "Navigation Home About Blog Contact Login Sign Up Terms of Service Privacy Policy Cookie Policy Accessibility Statement Footer Links Sitemap RSS Feed Copyright 2024 All Rights Reserved. More Navigation Home About Blog Contact Login Sign Up Social Media Facebook Twitter LinkedIn Instagram YouTube TikTok Related Articles You Might Also Like: Ten Tips for Better Prompting, How to Fine-Tune Your Model, Understanding Tokenization, A Guide to Vector Databases, Introduction to RAG Pipelines. Footer Navigation Home About Blog Contact Login Sign Up"

# Test 3: Repeated MCP filler + insight
FILLER=""
for i in $(seq 1 20); do FILLER="${FILLER}Based on my analysis of the codebase, here are the key findings. "; done
FILLER="${FILLER}The critical insight is that the authentication module has a race condition in the token refresh logic. When two concurrent requests hit the refresh endpoint, both may invalidate the current token, causing the second request to fail with a 401. The fix is to use an atomic compare-and-swap on the token store."
run_test "MCP response (20× filler + 1 insight)" "$FILLER"

# Test 4: Verbose LLM
run_test "Verbose LLM (typical Claude response)" \
    "Sure! I'd be happy to help you with that. Let me break this down step by step for you. First, let me explain what's happening here. The Model Context Protocol is a standardized protocol developed by Anthropic in 2024. It provides a way for AI assistants to interact with external tools in a structured manner. The protocol is based on JSON-RPC 2.0 and supports multiple transport mechanisms. Now, regarding your specific question, there are several considerations. The key insight is that statistical complexity captures the minimal causal structure needed to predict a process, while entropy rate measures residual unpredictability. In summary, MCP provides a standardized interface, and the difference between S_T and H_T is fundamental. I hope this helps! Let me know if you have any other questions."

# Test 5: Structured JSON (should retain)
run_test "GitHub API JSON (template URLs)" \
    '{"id":123456789,"name":"aevum","full_name":"kwailapt/aevum","private":false,"owner":{"login":"kwailapt","id":12345,"avatar_url":"https://avatars.githubusercontent.com/u/12345?v=4","url":"https://api.github.com/users/kwailapt","html_url":"https://github.com/kwailapt","followers_url":"https://api.github.com/users/kwailapt/followers","repos_url":"https://api.github.com/users/kwailapt/repos"},"description":"Thermodynamically honest AI infrastructure","fork":false,"stargazers_count":0,"license":{"key":"apache-2.0","name":"Apache License 2.0"}}'

# Test 6: Dense technical (should retain 100%)
run_test "Dense technical (CSSR description)" \
    "CSSR infers epsilon-machines from data. Given a stationary ergodic process, CSSR builds a minimal sufficient statistic by collecting suffix statistics for histories of length 1 to L, testing distributional homogeneity via Kolmogorov-Smirnov at significance alpha, and merging indistinguishable states. The resulting machine has statistical complexity C_mu equal to negative sum of pi_i log pi_i over causal states and entropy rate h_mu. The gap C_mu minus h_mu measures crypticity."

echo "  ─────────────────────────────────────────────────────────────────────────────"
echo ""
echo "  Interpretation:"
echo "    100% = correctly identified zero causal structure (pure noise/repetition)"
echo "      0% = correctly retained all content (high S_T, every sentence matters)"
echo "    The ε-machine measures CAUSAL STRUCTURE, not semantic importance."
echo "    Dense text with high S_T SHOULD compress 0% — that is correct behavior."
echo ""
echo "  Reproduce: bash benchmarks/filter-benchmark.sh $MCP_URL"
