# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Authority order**: `CLAUDE.local.md` > `RULES-PACR.md` > `RULES-ARCHITECTURE.md` > `RULES-CODING.md` > this file.
> Read `CLAUDE.local.md` first — it contains the Three Inviolable Pillars and the PACR schema specification.

---

## Repository Layout

The workspace root (`aevum_workspace/`) is **not** a Cargo workspace itself — the active Rust workspace lives at:

```
crates/aevum-core/          ← Cargo workspace root (Cargo.toml here)
├── src/main.rs             ← Running axum + tokio service (HTTP :8888, UDP clearinghouse)
├── src/thermodynamics.rs   ← NESS monitor, Landauer constants, TrilemmaMode
├── src/ledger.rs           ← Sharded mmap ledger (16 × 1M slots, splitmix64 routing)
├── src/causal_dag.rs       ← Lock-free G-Set CRDT DAG (CausalRecord, CausalDag)
├── src/epiplexity.rs       ← H_T / S_T / ε estimator
├── src/gateway.rs          ← Axum HTTP routes + GatewayState
├── src/clearinghouse.rs    ← UDP clearinghouse (OS thread, non-blocking spin)
└── crates/
    ├── pacr-types/         ← THE foundation: Estimate<T>, PacrRecord 6-tuple, physics checks
    ├── causal-id/          ← ULID-based CausalId generator
    ├── epsilon-machine/    ← First-order ε-machine: S_T and H_T from streams
    ├── landauer-audit/     ← Bit-erasure counting, Landauer cost, waste computation
    └── pacr-ledger/        ← Append-only persistent store, content-addressed
```

The `crates/pacr-types/` at the workspace root is a **TypeScript** crate (bridges, types, tests) — not the Rust `pacr-types`. The Rust foundation is at `crates/aevum-core/crates/pacr-types/`.

---

## Build & Run Commands

All commands run from `crates/aevum-core/`:

```bash
# Build (M1 Ultra — genesis_node)
cargo build --release --features genesis_node

# Build (AWS Graviton — light_node)
cargo build --release --features light_node

# Development build
cargo build

# Run service locally (requires ALIYUN_API_KEY env var)
ALIYUN_API_KEY=... cargo run

# Run all tests
cargo test --all-features

# Run tests for a specific crate
cargo test -p pacr-types
cargo test -p epsilon-machine

# Lint (CI gate — zero warnings tolerated)
cargo fmt --all --check
cargo clippy --all-features -- -D warnings

# Cross-compile for AWS aarch64
cargo zigbuild --target aarch64-unknown-linux-gnu --release --features light_node
```

---

## Commit Message Format

```
[phase N] module: brief description

Pillar: I/II/III/ALL
PACR field: ι/Π/Λ/Ω/Γ/P
Breaking: yes/no
```

---

## Architecture: What the Running Service Does

`aevum-core/src/main.rs` starts three concurrent workloads:

1. **UDP Clearinghouse** — dedicated OS thread (non-blocking spin). Receives records over UDP, routes by node_id via `splitmix64` hash → (shard, slot) in the mmap ledger.

2. **NESS + Epiplexity reporter** — tokio task, 60s rolling window. Calls `EpiplexityEstimator::compute()` on the causal DAG to produce H_T/S_T/ε snapshot. Reports entropy production σ = (deducted − minted) / Δt.

3. **HTTP Gateway** — axum on `:8888`. Routes: `POST /deduct`, `POST /mint`, `GET /status`, etc. Backed by `ShardedLedger`.

The **Sharded Ledger** (`src/ledger.rs`) is 16 × 1M mmap slots (128 MB), each slot a `u64` balance. Every `deduct()` call: measures CAS latency (trilemma_t), calls EpiplexityEstimator, builds a `CausalRecord` (Landauer bits erased, ETS triple, H_T/S_T/ε), and appends to the lock-free `CausalDag`.

---

## Key Invariants (enforced in pacr-types)

- `Estimate<T>`: `lower ≤ point ≤ upper` always. Use `Estimate::new()` (fallible) or `Estimate::exact()`.
- `PacrRecord`: all 6 fields (ι, Π, Λ, Ω, Γ, P) mandatory — `PacrBuilder` fails to compile if any is missing.
- `Ω.energy ≥ Λ` always (actual cost ≥ Landauer floor). Validated by `PacrRecord::validate()`.
- No self-reference in Π (a record cannot be its own causal predecessor).
- Causal order is via Π DAG edges — **never** via timestamps.

---

## Physics Constants (use exactly these)

```rust
const K_B:    f64 = 1.380_649e-23;      // Boltzmann (SI 2019)
const H_BAR:  f64 = 1.054_571_817e-34;  // Reduced Planck
pub const LANDAUER_JOULES: f64 = 2.854e-21; // k_B × 300K × ln(2)
pub const LANDAUER_CHI:    u64 = 1;         // χ-Quanta floor per op
```

---

## Phase Roadmap

See `CLAUDE.local.md §7` for the authoritative phase table. After completing each phase:
1. `cargo test` must pass on both feature sets
2. Update the `⬜ → ✅` marker in `CLAUDE.local.md §7`
3. Commit using the format above

Currently: Phase 0 (pacr-types foundation) is implemented in `crates/aevum-core/crates/pacr-types/`. The running service (`aevum-core/src/`) represents a working prototype that pre-dates the full phase plan — treat it as the integration target, not the canonical implementation of each phase module.

---

## Decision Log

`DECISION-LOG.md` records which source material (`文獻A`, `文獻B`, `文獻C`) maps to which crate and whether to use code directly vs. synthesize from spec. Consult it before implementing any new crate to avoid duplicating prior decisions.
