# CLAUDE.md — Aevum Core Project Context

## Identity
Project: Aevum Core
Language: Rust (pure, no unsafe except in explicitly marked FFI boundaries)
Philosophy: UNIX — each module does one thing, communicates via byte streams
Architecture: Autopoietic AGI kernel built on three physical pillars + PACR

---

## First Principles (NEVER violate these)

### Pillar I — Hyperscale Invariant
- Target: 10^11 concurrent nodes
- ALL algorithms MUST be O(n) or better. O(n log n) requires written justification.
- ALL shared data structures MUST be lock-free (CAS-based or CRDT-based).
- Cache coherence via causal consistency, NOT linearizability.
- Zero-copy wherever possible. Arena allocation preferred over heap.

### Pillar II — Thermodynamic Constraint
- Every computation has an irreducible energy cost: Landauer bound = k_B * T * ln(2) per erased bit.
- The Energy-Time-Space triple (E, T, S) forms a constraint surface, not three independent axes.
- System must maintain Non-Equilibrium Steady State (NESS): entropy is produced, exported, and accounted for.
- Landauer cost (Λ) is ALWAYS recorded. It is the theoretical floor; actual cost E ≥ Λ.
- Thermodynamic waste = E - Λ. This metric drives all optimization decisions.

### Pillar III — Cognitive Complexity
- Every data stream has an intrinsic cognitive structure decomposable into:
  - S_T (statistical complexity): minimum causal-state information to predict the stream
  - H_T (time-bounded entropy rate): residual unpredictability given causal states
- S_T and H_T form an inseparable pair (two projections of the same ε-machine).
- These are OBSERVER-DEPENDENT metrics — the observer's computational budget matters.
- Reference: "From Entropy to Epiplexity" (arXiv:2601.03220)

---

## PACR — Physically Annotated Causal Record (THE immutable schema)

PACR is a 6-tuple: R = (ι, Π, Λ, Ω, Γ, P)

| Symbol | Name                | Type                              | Origin               |
|--------|---------------------|-----------------------------------|----------------------|
| ι      | Causal Identity     | `CausalId` (128-bit ULID)        | Logical a priori     |
| Π      | Predecessor Set     | `BTreeSet<CausalId>`             | Pillar I (causality) |
| Λ      | Landauer Cost       | `Estimate<f64>` (joules)         | Pillar II (thermo)   |
| Ω      | Resource Triple     | `(Estimate<f64>, Estimate<f64>, Estimate<f64>)` — (E,T,S) | Pillar II |
| Γ      | Cognitive Split     | `(Estimate<f64>, Estimate<f64>)` — (S_T, H_T) | Pillar III |
| P      | Opaque Payload      | `Bytes` (arbitrary byte sequence) | Completeness axiom   |

### Estimate<T> is always: { point: T, lower: T, upper: T }
This encodes measurement uncertainty at the protocol level. Day 0 rough estimates
and Year-5 precision measurements use the SAME format — only interval width differs.

### PACR rules:
1. PACR schema is APPEND-ONLY. New fields may be added; existing fields NEVER change semantics.
2. Every module's output MUST be a valid PACR record or a stream of PACR records.
3. PACR records are the ONLY inter-module communication format (UNIX pipe analogy).
4. PACR records are content-addressed by ι and topologically ordered by Π.

---

## Module Architecture (UNIX-style pipeline)

[Sensor] → [PACR Minter] → [Causal DAG] → [Ledger]
↓
[Γ Estimator] → [Autopoietic Loop]
↓ ↓
[Λ Auditor] [Schema Evolver]

### Module contracts:
- `pacr-types`     : Zero-dependency crate defining PACR 6-tuple. THE foundation.
- `causal-id`      : ULID-based globally unique, monotonic, sortable ID generator.
- `causal-dag`     : Lock-free append-only DAG. Edges = Π. Nodes = ι.
- `landauer-audit`  : Estimates Λ for each computation event. Computes waste = E - Λ.
- `ets-surface`    : Validates (E, T, S) against physical constraint inequalities.
- `epsilon-machine`: Computes (S_T, H_T) from data streams via causal-state splitting.
- `pacr-ledger`    : Append-only persistent store. Content-addressed. Merkle-indexed.
- `autopoiesis`    : The feedback loop — reads Γ trends, proposes schema/parameter evolution.
- `aevum-cli`      : UNIX-style CLI. Pipes PACR records. `aevum mint | aevum dag | aevum ledger`

---

## Coding Standards

### Rust-specific:
- Edition 2021. MSRV = 1.75.
- `#![forbid(unsafe_code)]` in all crates except `ffi/` boundary crates.
- `#![deny(clippy::all, clippy::pedantic)]`
- All public types implement: `Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash`
- Error handling: `thiserror` for library crates, `anyhow` for binary crates.
- No `unwrap()` or `expect()` in library code. Use `?` operator everywhere.
- Prefer `SmallVec<[T; 8]>` over `Vec<T>` for predecessor sets (most events have < 8 parents).

### Architecture:
- Every function that creates a PACR record MUST populate ALL 6 fields. Partial records are type errors.
- Timestamps are NEVER used for ordering. Only Π (causal predecessors) determines order.
- All numeric physics quantities use SI units internally. Display formatting is separate.
- Confidence intervals default to 95% (configurable at the system level, not per-record).

### Testing:
- Property-based tests (proptest) for all PACR invariants.
- Fuzz testing for all deserialization paths.
- Benchmark every O(n) claim with criterion.rs at 10^6 scale. Reject O(n log n) regressions.

### Documentation:
- Every module's doc comment starts with: "Pillar: [I|II|III]. PACR field: [ι|Π|Λ|Ω|Γ|P]."
- Every design decision references the specific physical axiom that necessitates it.

---

## Autopoietic Loop Protocol

The system evolves itself via a disciplined feedback loop:
1. OBSERVE: Aggregate Γ = (S_T, H_T) across recent PACR records.
2. DIAGNOSE: If S_T is rising while H_T is stable → system is discovering structure → good.
   If H_T is rising while S_T is stable → system is encountering noise → investigate.
   If both rising → new regime detected → prepare schema evolution proposal.
3. PROPOSE: Generate a candidate schema extension (new PACR field) or parameter adjustment.
4. VALIDATE: Prove the proposal doesn't violate any of the 5 PACR meta-properties.
5. COMMIT: Append the proposal as a PACR record itself (self-referential closure).

---

## What Claude Code (Opus) Should Do

When implementing any module:
1. FIRST check if it respects all three pillars. If not, refuse and explain which pillar is violated.
2. THEN check if it correctly produces/consumes PACR 6-tuples. Partial records = compilation error.
3. THEN check O(n) complexity. Profile if uncertain.
4. THEN write the code — pure Rust, no unsafe, no unwrap, no timestamps-as-ordering.
5. THEN write property-based tests proving PACR invariants hold.
6. FINALLY write the doc comment linking to the physical axiom.

When uncertain about a design decision, ask:
"Which physical law forces this choice?" If no physical law forces it, the choice is arbitrary
and should be deferred (made configurable, not hardcoded).

