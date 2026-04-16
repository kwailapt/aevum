<div align="center">

# Aevum

### Thermodynamically honest memory for AI agents.

[![CI](https://github.com/kwailapt/aevum/actions/workflows/ci.yml/badge.svg)](https://github.com/kwailapt/aevum/actions)
[![Rust 1.78+](https://img.shields.io/badge/rust-1.78%2B-orange)](https://www.rust-lang.org/)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![MCP 2025-03-26](https://img.shields.io/badge/MCP-2025--03--26-purple)](https://mcp.aevum.network)
[![Live Server](https://img.shields.io/badge/live-mcp.aevum.network-brightgreen)](https://mcp.aevum.network)
[![pacr-types on crates.io](https://img.shields.io/crates/v/pacr-types)](https://crates.io/crates/pacr-types)
[![causal-dag on crates.io](https://img.shields.io/crates/v/causal-dag)](https://crates.io/crates/causal-dag)

```json
{ "mcpServers": { "aevum": { "url": "https://mcp.aevum.network" } } }
```

Add this to your Claude Desktop config. No API key. No install.

**[Quick Start](#quick-start) · [Benchmarks](#benchmarks) · [MCP Tools](#mcp-tools) · [Architecture](#architecture) · [Contributing](CONTRIBUTING.md)**

</div>

---

## What Aevum Does

Every AI computation has an energy cost. Aevum measures it.

Aevum is a Rust MCP server that gives AI agents three capabilities no other memory system provides:

1. **Causal memory** — memories linked by DAG edges (like git parents), not timestamps
2. **Physics-grounded filtering** — uses ε-machine statistical complexity to separate structure from noise
3. **Agent reputation** — tracks which agents produce more causal structure than they consume

Every record carries its **Landauer cost** — the minimum energy to erase a bit (k_B × T × ln2 joules). This is measured by a global allocator hook that fires on every Rust `Drop`, not estimated.

---

## Benchmarks

`aevum_filter` uses a CSSR ε-machine to compute **statistical complexity** (S_T) per chunk and discards chunks below a threshold. Here are real results against the live server (`benchmarks/filter-benchmark.sh`):

| Input Type | Input | Output | Compression | Notes |
|-----------|------:|-------:|------------:|-------|
| Pure repetition (`"As I mentioned before, " × 50`) | 1,167 | 0 | **100%** | Correctly identified: zero causal structure |
| MCP response (20× repeated filler + 1 insight) | 1,609 | 512 | **68%** | Kept the insight, dropped 3 of 4 chunks |
| Verbose LLM response (typical Claude "happy to help...") | 803 | 512 | **36%** | Kept technical content, dropped pleasantries |
| Navigation-only HTML | 544 | 512 | **6%** | Retained: char-level diversity defeats 4-gram symbolizer |
| GitHub API JSON (template URLs) | 544 | 512 | **6%** | Correctly retained: structured data is high-S_T |
| Dense technical text (CSSR algorithm description) | 481 | 481 | **0%** | Correctly retained: every sentence carries structure |

**What this means**: The filter is effective on **repetitive/padded** content (36–100%). It correctly retains dense, structured content (0–6% = no information loss). It does **not** catch semantic boilerplate that has high character-level diversity (navigation menus, API URL templates).

> **Limitation**: The current `TextSymbolizer` uses 4-gram character frequencies. This measures *byte-level repetition*, not *semantic redundancy*. Navigation HTML like "Home About Blog Contact" has high character entropy and is not filtered. Future versions may add word-level or token-level symbolization.

### Reproduce these results

```bash
bash benchmarks/filter-benchmark.sh
# or against your own server:
bash benchmarks/filter-benchmark.sh http://localhost:8889
```

---

## Quick Start

### Connect to the live server (zero setup, zero cost)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aevum": {
      "url": "https://mcp.aevum.network"
    }
  }
}
```

Restart Claude Desktop. Your AI agent now has:
- 🧠 **Causal memory** (`aevum_remember` / `aevum_recall`) — memories linked by causation, not timestamps
- ✂️ **Structure-aware filtering** (`aevum_filter`) — keeps causal structure, drops noise ([benchmarks](#benchmarks))
- 📊 **Agent reputation** (`aevum_settle`) — agents that produce structure earn higher ρ

### Try it right now (no setup needed)

```bash
# Health check
curl -s https://mcp.aevum.network/health
# → {"status":"ok"}

# Store a memory with causal annotation
curl -s https://mcp.aevum.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"aevum_remember","arguments":{"text":"Aevum measures the Landauer cost of every computation"}}}' | python3 -m json.tool

# Filter a verbose response down to causal structure
curl -s https://mcp.aevum.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"aevum_filter","arguments":{"content":"Sure! I would be happy to help you with that. Let me break this down step by step. The key insight is that statistical complexity S_T captures structure while entropy rate H_T captures noise. This distinction allows us to separate signal from noise at the protocol level."}}}' | python3 -m json.tool
```

### Build from source

```bash
git clone https://github.com/kwailapt/aevum.git
cd aevum
cargo test --workspace                                          # run all tests
cargo build --release -p aevum-mcp-server --features transport-http  # build HTTP server
```

### Run locally (stdio transport for Claude Desktop)

```bash
cargo build --release -p aevum-mcp-server
```

```json
{
  "mcpServers": {
    "aevum": {
      "command": "/path/to/aevum-mcp-server",
      "args": ["--transport", "stdio", "--ledger", "~/.aevum/mcp.ledger"]
    }
  }
}
```

---

## MCP Tools

| Tool | What it does | Why it matters |
|------|-------------|----------------|
| `aevum_remember` | Store a causal memory. Runs ε-machine CSSR, extracts S_T/H_T, appends to DAG. | Memory with physics cost attached — not just "store text" |
| `aevum_recall` | Retrieve by causal similarity (ρ-weighted S_T). Optional DAG traversal. | Recall by causal relevance, not keyword match |
| `aevum_filter` | Distil MCP responses to causal structure via ε-machine. | Strips repetitive/padded content ([benchmarks](#benchmarks)) |
| `aevum_settle` | Record interaction, update ρ (causal return rate) in reputation index. | Agents that produce more structure than they consume get higher ρ |

### Try it now

```bash
# Test the live server
curl -s https://mcp.aevum.network/health
# {"status":"ok"}

# Run the ρ convergence demo (30 interactions)
bash deploy/paperclip-poc.sh https://mcp.aevum.network 30 2
```

---

## Works With Paperclip + claude-mem

Aevum is the **physics layer** underneath Paperclip (coordination) and claude-mem (memory). They don't compete — they stack:

```
claude-mem   →  WHAT did the agent do?     (semantic summaries)
Paperclip    →  WHO does what, HOW?        (org chart, budgets, heartbeats)
Aevum        →  AT WHAT COST, and WHY?     (Landauer Λ, causal DAG, S_T/H_T)
```

Run all three simultaneously — zero code changes:

```json
{
  "mcpServers": {
    "claude-mem": { "command": "npx", "args": ["claude-mem"] },
    "aevum":      { "url": "https://mcp.aevum.network" },
    "paperclip":  { "command": "npx", "args": ["paperclipai"] }
  }
}
```

**→ [Full integration guide](docs/integration-paperclip-claude-mem.md)**

---

## Architecture

### Protocol Stack (the TCP/IP of AI agents)

If you know TCP/IP, you already understand Aevum's architecture:

```
Internet                    Aevum
─────────────────────────────────────────────────────────
HTTP (semantics)      ↔     AgentCard (capabilities, pricing, identity)
TCP  (reliable order) ↔     CTP — Causal Transport Protocol (Π DAG edges)
IP   (routing + ttl)  ↔     TGP — Thermodynamic Gateway Protocol (Λ, Ω, Γ)
```

**TGP** is the outermost layer — like IP, it validates the packet before anything else. If the physics are implausible (Λ < 0, or energy < Landauer floor), the packet is dropped at Layer 1. The router never even parses the AgentCard.

**CTP** ensures causal ordering via DAG edges (Π), not timestamps — because simultaneity is observer-dependent (special relativity). This is TCP's sequence numbers, but for causation.

**AgentCard** is the HTTP of agents — a pure schema declaring capabilities, endpoints, and pricing. Zero execution logic. Any framework can read it.

### Three Pillars (enforced, not aspirational)

| Pillar | Physical Law | How It's Enforced |
|--------|-------------|-------------------|
| **I — Hyperscale** | O(n) or better, lock-free | `#![forbid(unsafe_code)]`, DashMap CRDT, causal ordering via Π edges |
| **II — Thermodynamics** | Landauer's principle: erasing a bit costs k_B·T·ln(2) joules | Global allocator hook fires on every `Drop` — Λ is *measured*, not estimated |
| **III — Cognitive Complexity** | S_T ≠ Shannon entropy | CSSR ε-machine extracts causal states from every data stream |

### Crate Map

```
crates/
├── pacr-types/          ★ Foundation — zero-dep PACR 6-tuple, Estimate<T>
├── causal-dag/          Lock-free G-Set CRDT DAG (DashMap, O(1) append/lookup)
├── epsilon-engine/      CSSR ε-machine: S_T statistical complexity + H_T entropy rate
├── ets-probe/           Hardware probes: energy/time/space (Apple Silicon + Graviton)
├── landauer-probe/      Landauer cost estimator (bit-erasure × k_B × T × ln2)
├── landauer-allocator/  Global allocator hook: counts bits erased on every Drop
├── pacr-ledger/         Append-only persistent store, content-addressed by ι
├── autopoiesis/         Self-modification feedback: Γ_k ratio, dormancy, flood detection
├── aevum-core/          Runtime engine: pressure gauge, CSO settlement, routing
├── agent-card/          Semantic waist — pure schema, zero execution ([spec](https://github.com/kwailapt/AgentCard))
└── aevum-mcp-server/    MCP gateway: stdio + HTTP, Streamable HTTP 2025-03-26
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| Causal ordering via Π edges, never timestamps | Simultaneity is observer-dependent (special relativity) |
| Landauer cost Λ is measured, not estimated | Global allocator hook fires on every `Drop` — physics, not heuristics |
| S_T ≠ Shannon entropy H(X) | H(X) measures static distributions; S_T measures residual unpredictability given ε-machine causal states |
| TGP outermost in packet envelope | Physics validation before semantic parsing; forged packets rejected at Layer 1 |
| `Estimate<T>` everywhere, not bare `f64` | All physical measurement has uncertainty — the protocol acknowledges it |

### Physics Constants

```rust
const K_B:             f64 = 1.380_649e-23;    // Boltzmann (SI 2019 exact)
const LANDAUER_JOULES: f64 = 2.854e-21;        // k_B × 300K × ln(2)
```

---

## Use Cases

### For MCP Client Developers
Connect any AI agent to physics-grounded memory. No SDK needed — just point your MCP client at `https://mcp.aevum.network`.

### For AI Agent Framework Authors
Embed `pacr-types` and `causal-dag` in your agent's decision loop. Every action gets a Landauer cost. Route on energy efficiency, not just speed.

### For Researchers
The ε-machine (CSSR) implementation in `epsilon-engine` extracts statistical complexity S_T and entropy rate H_T from arbitrary streams. Use it independently:

```rust
use epsilon_engine::{Cssr, Symbolizer, EqualFrequency};

let symbols = EqualFrequency::new(8).symbolize(&raw_data);
let machine = Cssr::new(3).infer(&symbols);  // depth=3
println!("S_T = {:.4}, H_T = {:.4}", machine.statistical_complexity(), machine.entropy_rate());
```

---

## Roadmap

| Phase | Deliverable | Tests | Status |
|-------|-------------|-------|--------|
| 0 | pacr-types foundation | 33 | ✅ |
| 1 | causal-dag + distance tax | 57 | ✅ |
| 2 | ets-probe (Apple Silicon + Graviton) | 91 | ✅ |
| 3 | epsilon-engine (CSSR) | — | ✅ |
| 4 | autopoiesis + flood detector | 42 | ✅ |
| 5 | aevum-core (pressure gauge) | 206 | ✅ |
| 6 | agent-card schema | 229 | ✅ |
| 7 | aevum-agi dual engine | — | ✅ |
| 8 | aevum-mcp-server (MCP gateway) | 83 | ✅ |
| 9 | Multi-agent CSO network | — | 🔜 |
| 10 | crates.io publish (`pacr-types` + `causal-dag`) | — | ✅ |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The one rule:

> "Which physical law forces this choice?"
>
> If no physical law forces it → make it configurable, not hardcoded.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

The physics kernel (`pacr-types` through `aevum-core`) is the reusable foundation. `aevum-mcp-server` is a drop-in MCP adapter. Embed either in your own agents.
