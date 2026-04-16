# RULES-CODING.md — Rust Coding Standards & Testing Requirements

> Subordinate to CLAUDE.local.md. Claude Code reads this for ALL code generation.

---

## §1 Rust Standards

### Edition & Toolchain
- Edition: 2021
- MSRV: 1.75
- Target platforms: `aarch64-apple-darwin` (M1), `aarch64-unknown-linux-gnu` (AWS c7g)
- Cross-compile via `cross` or `cargo-zigbuild`

### Safety
- `#![forbid(unsafe_code)]` in ALL crates except explicitly marked FFI boundaries
- `#![deny(clippy::all, clippy::pedantic)]` in ALL crates
- No `unwrap()` or `expect()` in library code. Use `?` operator everywhere.
- `anyhow` for binary crates (main.rs). `thiserror` for library crates.

### Type System
- All public types implement: `Debug, Clone, Serialize, Deserialize`
- Additionally where applicable: `PartialEq, Eq, Hash, PartialOrd, Ord`
- `Eq` is intentionally NOT derived for `f64`-based `Estimate`. Use `is_consistent_with()`.
- `#[must_use]` on ALL pure functions that return values.
- `#[non_exhaustive]` on ALL public enums (future-proofing).

### Memory
- Prefer `SmallVec<[T; 4]>` over `Vec<T>` for predecessor sets
- Prefer arena allocation (bumpalo) over heap for hot paths
- `#[repr(align(64))]` for cache-line-critical structs (CausalDag nodes)
- Zero-copy: use `bytes::Bytes` for Payload, never `Vec<u8>`

### Concurrency
- No `Mutex`, no `RwLock` in any hot path
- `DashMap` for concurrent map access (sharded locks, acceptable for DAG)
- `crossbeam` channels for producer-consumer patterns
- `tokio` runtime: max_threads = 2 on c7g.large (match vCPU count)

### Numeric
- ALL physics quantities in SI units internally (joules, seconds, bytes)
- Display formatting is SEPARATE from internal representation
- Boltzmann constant: `const K_B: f64 = 1.380_649e-23;` (exact, 2019 SI redefinition)
- Reduced Planck: `const H_BAR: f64 = 1.054_571_817e-34;`
- Confidence intervals default to 95% (configurable at system level, NOT per-record)

---

## §2 Documentation Standards

Every module's doc comment MUST start with:
```rust
/// Pillar: [I|II|III|ALL]. PACR field: [ι|Π|Λ|Ω|Γ|P].
///
/// [Brief description of what this module does]
///
/// Physical axiom: [Which axiom necessitates this module's existence]
```

Every design decision that is NOT forced by physics MUST include:
```rust
// DESIGN CHOICE (configurable): [explanation]
// Not physics-mandated. Can be changed without violating PACR invariants.
```

---

## §3 Testing Requirements

### Property-Based Testing (proptest)
Required for ALL PACR invariants:
- `Estimate<f64>`: lower ≤ point ≤ upper
- `PacrRecord`: no self-reference in Π, Λ ≥ 0, Ω.E ≥ Λ, S_T ≥ 0, H_T ≥ 0
- `CausalDag`: append-only (no overwrites), no orphan predecessors, no cycles
- `ResourceTriple`: Margolus-Levitin constraint check

### Known-Answer Tests (KAT)
Required for epsilon-engine:
- Even Process: 2 states, C_μ = 1.0 bit (exact), h_μ ≈ 0.9183 bits/sym
- Golden Mean Process: 2 states, C_μ ≈ 0.9183 bits, h_μ ≈ 0.6792 bits/sym
- At N=10,000 samples: correct state count = 2, C_μ and h_μ within bootstrap CI

### Fuzz Testing
Required for ALL deserialization paths:
- `PacrRecord` from bytes
- Envelope wire format parsing
- AgentCard JSON parsing

### Benchmarks (criterion.rs)
Required for ALL O(n) claims:
- CausalDag::append at 10^6 scale
- CausalDag::get at 10^6 scale
- epsilon-engine CSSR at N=100K, L=12, |A|=8
- Reject any regression to O(n log n)

### Integration Test: 72-Hour Batch
After Phase 5 deployment:
- 72h × 1 record/s = ~259,200 records
- Memory < 2 GiB (each record ~4KB → ~1 GiB)
- CSSR triggered every 1,000 records → ~259 inferences
- Γ indicator stable after ~20 cycles (stddev of last 10 < 0.5)
- `aevum verify` → exit code 0
- `aevum status` → record_count ≈ 259,200 ± 1,000

---

## §4 Git & CI Conventions

### Branch Strategy
- `main`: always compiles on both `genesis_node` and `light_node` features
- `phase/N-description`: feature branches for each phase
- Merge to main requires: all tests pass on BOTH feature sets

### Commit Messages
```
[phase N] module: brief description

Pillar: I/II/III/ALL
PACR field: ι/Π/Λ/Ω/Γ/P
Breaking: yes/no
```

### Pre-commit Checks
```bash
cargo fmt --all --check
cargo clippy --all-features -- -D warnings
cargo test --all-features
```
