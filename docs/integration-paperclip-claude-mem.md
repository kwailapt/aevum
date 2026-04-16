# Aevum + Paperclip + claude-mem — Integration Guide

Aevum, Paperclip, and claude-mem solve three different problems that compound when combined.

## What Each Project Does

| Project | Problem It Solves | Core Mechanism |
|---------|------------------|---------------|
| **[claude-mem](https://github.com/thedotmack/claude-mem)** | AI agents forget across sessions | Lifecycle hooks → SQLite + Chroma → AI-compressed summaries |
| **[Paperclip](https://github.com/paperclipai/paperclip)** | Multi-agent coordination is chaotic | Org chart + heartbeats + budgets + ticket system |
| **[Aevum](https://github.com/kwailapt/aevum)** | No one measures the physical cost | Landauer allocator + CSSR ε-machine + causal DAG |

## Why They're Complementary (Not Competing)

```
claude-mem:    WHAT did the agent do?     (session capture → semantic summary)
Paperclip:     WHO does what, and HOW?    (org chart → task delegation → governance)
Aevum:         AT WHAT COST, and WHY?     (Landauer Λ → causal DAG Π → S_T/H_T)
```

claude-mem records *content*. Paperclip coordinates *process*. Aevum measures *physics*.

None of them replaces the others. Together they form a complete agent infrastructure:

```
┌─────────────────────────────────────────────────────┐
│  Paperclip (coordination layer)                     │
│    org chart → goal alignment → heartbeats          │
│         │                │                          │
│    ┌────▼────┐    ┌──────▼──────┐                   │
│    │ Agent A │    │  Agent B    │                    │
│    │ (Claude │    │  (Codex)   │                    │
│    │  Code)  │    │             │                    │
│    └────┬────┘    └──────┬──────┘                   │
│         │                │                          │
│    ┌────▼────────────────▼────┐                     │
│    │  claude-mem (memory)     │  ← session summaries│
│    │  SQLite + Chroma         │                     │
│    └────────────┬─────────────┘                     │
│                 │                                   │
│    ┌────────────▼─────────────┐                     │
│    │  Aevum (physics layer)   │  ← Λ, S_T, ρ       │
│    │  Causal DAG + CSO        │                     │
│    └──────────────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

## Concrete Integration Patterns

### Pattern 1: Filter claude-mem summaries through Aevum

claude-mem produces AI-compressed session summaries. These summaries still contain LLM verbosity. Pipe them through `aevum_filter` before injection:

```
claude-mem session summary (800 tokens)
        │
        ▼
  aevum_filter (CSSR ε-machine)
        │
        ▼
  filtered summary (400-600 tokens, structure retained)
```

**Claude Desktop config** (both servers active simultaneously):
```json
{
  "mcpServers": {
    "claude-mem": {
      "command": "npx",
      "args": ["claude-mem"]
    },
    "aevum": {
      "url": "https://mcp.aevum.network"
    }
  }
}
```

Claude will have both toolsets available. You can prompt:
> "Search my memory for the authentication bug discussion, then filter the results through aevum_filter before showing me."

### Pattern 2: Track Paperclip agent reputation with Aevum CSO

Paperclip tracks budgets (dollars). Aevum tracks **causal return rate** (ρ = structure produced / energy consumed). They measure different things:

| Metric | Paperclip | Aevum |
|--------|-----------|-------|
| Cost control | Budget ($/month) | Landauer cost (joules/op) |
| Agent quality | Task completion % | ρ causal return rate |
| Coordination | Org chart hierarchy | Causal DAG (Π edges) |

After each Paperclip heartbeat, call `aevum_settle` to record the interaction:

```bash
curl -s https://mcp.aevum.network \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "aevum_settle",
      "arguments": {
        "source_agent_id": "PAPERCLIP_AGENT_A_HEX_ID",
        "target_agent_id": "PAPERCLIP_AGENT_B_HEX_ID",
        "lambda_joules": 1.5e-5,
        "phi_before": 0.6,
        "phi_after": 0.75
      }
    }
  }'
```

ρ converges via EMA (α=0.1) within ~20 interactions. Agents with stable ρ > 1.0 produce more structure than they consume — promote them in the org chart.

### Pattern 3: Aevum as the causal backbone for Paperclip audit trail

Paperclip's ticket system creates an immutable audit log. Aevum adds **causal provenance**:

- Each Paperclip ticket → `aevum_remember` (creates a PACR record with Π edges to predecessor tickets)
- Ticket delegation A→B → `aevum_settle` (records the causal relationship + energy cost)
- Ticket completion → `aevum_remember` + `aevum_recall` (link result to original goal via DAG)

The causal DAG then answers questions Paperclip alone cannot:
- "Which agent's work *caused* this bug?" (trace Π edges backward)
- "Is Agent B's output *causally dependent* on Agent A's input?" (DAG traversal)
- "What's the Landauer cost of the entire ticket lifecycle?" (sum Λ along path)

## For Paperclip Users

Add to your Paperclip agent's MCP config:

```json
{
  "mcpServers": {
    "aevum": {
      "url": "https://mcp.aevum.network"
    }
  }
}
```

Your Paperclip agents now have causal memory + physics measurement. Zero code changes to Paperclip.

## For claude-mem Users

Add alongside claude-mem in your Claude Desktop config:

```json
{
  "mcpServers": {
    "claude-mem": {
      "command": "npx",
      "args": ["claude-mem"]
    },
    "aevum": {
      "url": "https://mcp.aevum.network"
    }
  }
}
```

Your memories now have two layers:
- **claude-mem**: semantic compression (what happened)
- **Aevum**: causal annotation (why it happened, at what physical cost)

## Benchmark: Three-Stack vs Individual

| Setup | Memory | Coordination | Cost Tracking | Causal Provenance |
|-------|--------|-------------|---------------|-------------------|
| claude-mem only | ✅ | ❌ | ❌ | ❌ |
| Paperclip only | ❌ | ✅ | $ budget | ❌ |
| Aevum only | ✅ causal | ❌ | ✅ Λ joules | ✅ DAG |
| **All three** | **✅ semantic + causal** | **✅ org chart** | **✅ $ + joules** | **✅ full DAG** |
