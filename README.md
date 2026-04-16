# Aevum — Thermodynamically Honest AI Infrastructure

[![Rust](https://img.shields.io/badge/rust-1.78%2B-orange)](https://www.rust-lang.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Phase 8 complete](https://img.shields.io/badge/phase%208-complete%20%E2%9C%85-brightgreen)](#phase-roadmap)
[![MCP compatible](https://img.shields.io/badge/MCP-2025--03--26-purple)](https://mcp.aevum.network)

> Every computation has an irreducible energy cost. Aevum measures it, records it, and routes on it.

---

## What is Aevum?

Aevum is a Rust kernel for AI agents that enforces three physical laws at the protocol level:

| Pillar | Law | Enforcement |
|--------|-----|-------------|
| **I — Hyperscale** | All algorithms O(n) or better. Lock-free data structures. | Compile-time: `#![forbid(unsafe_code)]`, DashMap CRDT |
| **II — Thermodynamics** | Every erased bit costs energy (Landauer's principle). | Runtime: Global allocator hook counts bits on every `Drop` |
| **III — Cognitive Complexity** | Intelligence = causal structure / energy dissipated | CSSR ε-machine extracts S_T / H_T from every data stream |

The core schema is **PACR** — a 6-tuple that annotates every record with its physical cost:

```
R = (ι, Π, Λ, Ω, Γ, P)
     │   │   │   │   │   └── Payload (bytes)
     │   │   │   │   └────── Cognitive split: S_T, H_T (ε-machine)
     │   │   │   └────────── Resource triple: energy, time, space
     │   │   └────────────── Landauer cost (joules)
     │   └────────────────── Predecessor set (causal DAG edges)
     └────────────────────── Causal identity (128-bit ULID)
```

---

## MCP Server — Connect Any AI Agent

`aevum-mcp-server` exposes four tools via the [Model Context Protocol](https://modelcontextprotocol.io):

| Tool | What it does |
|------|-------------|
| `aevum_remember` | Store a causal memory record. Runs ε-machine CSSR, extracts S_T/H_T, appends to DAG. |
| `aevum_recall` | Retrieve causally relevant memories by ρ-weighted S_T similarity. Optional DAG traversal. |
| `aevum_filter` | Distil high-entropy MCP responses to causal structure. Cuts token cost 90%+. |
| `aevum_settle` | Record agent interaction, update ρ causal return rate in CSO reputation index. |

### Connect Claude Desktop (stdio — local)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Connect any MCP client (HTTP — remote)

The public genesis node is live at `https://mcp.aevum.network`:

```json
{
  "mcpServers": {
    "aevum": {
      "url": "https://mcp.aevum.network"
    }
  }
}
```

No API key required. MCP Streamable HTTP 2025-03-26 compliant.

---

## Crate Map

```
crates/
├── pacr-types/          ★ Foundation — zero-dep PACR 6-tuple, Estimate<T>
├── causal-dag/          Lock-free G-Set CRDT DAG (DashMap, O(1) append/lookup)
├── epsilon-engine/      CSSR ε-machine: S_T statistical complexity + H_T entropy rate
├── ets-probe/           Hardware probes: energy/time/space (M1 Ultra + AWS Graviton)
├── landauer-probe/      Landauer cost estimator (bit-erasure × k_B × T × ln2)
├── landauer-allocator/  Global allocator hook: counts bits erased on every Drop
├── pacr-ledger/         Append-only persistent store, content-addressed by ι
├── autopoiesis/         Self-modification feedback: Γ_k ratio, dormancy, flood detection
├── aevum-core/          Runtime engine: pressure gauge, CSO settlement, CTP/TGP routing
├── agent-card/          Semantic waist — pure schema, zero execution (AgentCard spec)
└── aevum-mcp-server/    MCP gateway: stdio + HTTP transports, 83 tests
```

---

## Build

```bash
# Clone
git clone https://github.com/kwailapt/aevum.git
cd aevum

# Run all tests (requires Rust 1.78+)
cargo test --workspace

# Build MCP server (stdio transport, default)
cargo build --release -p aevum-mcp-server

# Build MCP server (HTTP transport)
cargo build --release -p aevum-mcp-server --features transport-http

# M1 Ultra full build (AGI + Apple Silicon probes)
cargo build --release --features genesis_node

# AWS Graviton build (light node)
cargo build --release --features light_node

# Cross-compile for aarch64 AWS
bash deploy/cross-compile.sh
```

---

## Physics Constants

```rust
const K_B:            f64 = 1.380_649e-23;   // Boltzmann (SI 2019 exact)
const H_BAR:          f64 = 1.054_571_817e-34; // Reduced Planck
const LANDAUER_JOULES: f64 = 2.854e-21;       // k_B × 300K × ln(2)
const LANDAUER_CHI:    u64 = 1;               // χ-Quanta floor per op
```

---

## Paperclip PoC — ρ Convergence

The `aevum_settle` tool implements a Causal Settlement Oracle (CSO).
Run the convergence demo against the live server:

```bash
# 30 interactions, 2s interval
bash deploy/paperclip-poc.sh https://mcp.aevum.network 30 2
```

Expected output: ρ (causal return rate) converges via EMA α=0.1 within ~20 interactions.
Stable ρ > 1.0 means the agent produces more causal structure than it consumes.

---

## Phase Roadmap

| Phase | Deliverable | Tests | Status |
|-------|-------------|-------|--------|
| 0 | pacr-types foundation | 33 | ✅ |
| 1 | causal-dag + distance tax | 57 | ✅ |
| 2 | ets-probe (M1 + Graviton) | 91 | ✅ |
| 3 | epsilon-engine (CSSR KAT) | — | ✅ |
| 4 | autopoiesis + flood detector | 42 | ✅ |
| 5 | aevum-core (pressure gauge) | 206 | ✅ |
| 6 | agent-card schema | 229 | ✅ |
| 7 | aevum-agi dual engine | — | ✅ |
| 8 | aevum-mcp-server (MCP gateway) | 83 | ✅ |

---

## Design Philosophy

> "Which physical law forces this choice?"
>
> If no physical law forces it → make it configurable, not hardcoded.

Key decisions:
- **Causal ordering via Π edges, never timestamps** — simultaneity is observer-dependent (special relativity)
- **Landauer cost Λ is measured, not estimated** — global allocator hook fires on every `Drop`
- **S_T ≠ Shannon entropy** — H(X) measures static distributions; S_T measures residual unpredictability given ε-machine causal states
- **TGP outermost in packet envelope** — physics validation before semantic parsing; forged packets rejected at Layer 1

---

## Contributing

PRs welcome. Every commit must pass:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-features -- -D warnings
cargo test --workspace
```

Commit format:
```
[phase N] module: brief description

Pillar: I/II/III/ALL
PACR field: ι/Π/Λ/Ω/Γ/P
Breaking: yes/no
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

`aevum-mcp-server` is a drop-in MCP adapter. The physics kernel (`pacr-types` through `aevum-core`) is the reusable foundation — embed it in your own agents.
