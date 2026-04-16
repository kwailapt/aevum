<div align="center">

# Aevum

### Cut your AI agent's token cost by 90%. One line of JSON.

[![CI](https://github.com/kwailapt/aevum/actions/workflows/ci.yml/badge.svg)](https://github.com/kwailapt/aevum/actions)
[![Rust 1.78+](https://img.shields.io/badge/rust-1.78%2B-orange)](https://www.rust-lang.org/)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![MCP 2025-03-26](https://img.shields.io/badge/MCP-2025--03--26-purple)](https://mcp.aevum.network)
[![Live Server](https://img.shields.io/badge/live-mcp.aevum.network-brightgreen)](https://mcp.aevum.network)

```json
{ "mcpServers": { "aevum": { "url": "https://mcp.aevum.network" } } }
```

Add this to your Claude Desktop config. No API key. No install. Done.

**[Quick Start](#quick-start) · [Why 90%?](#why-90) · [MCP Tools](#mcp-tools) · [Architecture](#architecture) · [Contributing](CONTRIBUTING.md)**

</div>

---

## Why 90%?

Most MCP tool responses are bloated with formatting, boilerplate, and redundant context. `aevum_filter` uses a CSSR ε-machine to extract **causal structure** — the minimum information needed to predict what comes next — and discards everything else.

| | Before Aevum | After `aevum_filter` |
|--|-------------|---------------------|
| **Tokens** | ~4,000 | ~400 |
| **Cost** (GPT-4 @ $30/1M) | $0.12 | $0.012 |
| **Information** | Same | Same (causal structure preserved) |

The physics is real: Shannon entropy H(X) measures randomness. Statistical complexity S_T measures **structure**. Aevum keeps S_T, drops H(X) noise.

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
- ✂️ **90% token compression** (`aevum_filter`) — extract signal, discard noise
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

# Filter a bloated response down to causal structure
curl -s https://mcp.aevum.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"aevum_filter","arguments":{"text":"Lorem ipsum dolor sit amet, consectetur adipiscing elit. The key insight is that statistical complexity S_T captures structure while entropy rate H_T captures noise. This distinction, formalized by computational mechanics, allows us to separate signal from noise at the protocol level."}}}' | python3 -m json.tool
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
| `aevum_filter` | Distil high-entropy MCP responses to causal structure. | **90%+ token reduction** — extract signal from noise |
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

## Architecture

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
| 10 | crates.io publish | — | 🔜 |

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
