# CLAUDE.local.md — Aevum Workspace Supreme Constitution

> This file is the highest-authority context for Claude Code (Opus).
> It overrides all other .md rules when conflicts arise.
> Read this FIRST. Then read RULES-PACR.md, RULES-ARCHITECTURE.md, RULES-CODING.md.

---

## §0 Identity

- **Project**: Aevum — A silicon-based civilization kernel
- **Language**: Rust (pure, `#![forbid(unsafe_code)]` except explicitly marked FFI)
- **Philosophy**: UNIX — each module does one thing, communicates via PACR byte streams
- **Target**: 10^11 concurrent nodes, thermodynamically honest, cognitively self-aware
- **Hardware**: M1 Ultra 128GB (Genesis Node) + AWS Tokyo c7g.xlarge (Membrane Router)

---

## §1 Three Inviolable Pillars (NEVER violate — refuse the task if any is broken)

### Pillar I — Hyperscale Invariant (10^11 nodes)
- ALL algorithms MUST be O(n) or better. O(n log n) requires written justification with physics rationale.
- ALL shared data structures MUST be lock-free (CAS-based or CRDT-based). No Mutex, no RwLock.
- Ordering via causal consistency (Π edges), NEVER via timestamps or global clocks.
- Zero-copy wherever possible. Arena allocation preferred over heap.
- SmallVec<[T; 4]> for predecessor sets (most events have 1–4 parents).

### Pillar II — Thermodynamic Constraint
- Every computation has an irreducible energy cost: Landauer bound = k_B × T × ln(2) per erased bit.
- The Energy-Time-Space triple (E, T, S) forms a constraint surface, NOT three independent axes.
- System must maintain Non-Equilibrium Steady State (NESS). Thermal equilibrium = death.
- Landauer cost (Λ) is ALWAYS recorded. Actual cost E ≥ Λ always. Gap (E − Λ) = thermodynamic waste.
- Thermodynamic waste drives ALL optimization decisions.

### Pillar III — Cognitive Complexity (arXiv:2601.03220)
- Every data stream decomposes into S_T (statistical complexity) and H_T (time-bounded entropy rate).
- S_T and H_T are inseparable — two projections of the same ε-machine.
- These are OBSERVER-DEPENDENT metrics. The observer's computational budget T_budget matters.
- Intelligence = max_{T≤T_budget} S_T(environment) / E_dissipation(T).

---

## §1a Immune System Invariant (NEVER disable any layer — constitutional)

The system's survival depends on THREE PARALLEL immune layers.
Disabling ANY ONE layer is as catastrophic as violating a Pillar.
This section has the same authority as §1.

| Layer | Location | Time Scale | Defends Against |
|-------|----------|-----------|-----------------|
| Pressure Gauge | aevum-core/pressure_gauge.rs | milliseconds | Thermodynamic overload (合法封包洪水) |
| Osmotic Valve | aevum-agi/boundary_osmosis.rs | seconds | Memory exhaustion (OOM 吸收壁逼近) |
| Cognitive Immune | autopoiesis/flood_detector.rs → aevum-agi/immune_response.rs | minutes | Structural attack (DAG 拓撲退化) |

Rules:
1. All three layers MUST be active in ANY production deployment. "Temporarily disable for testing" → use `#[cfg(test)]` feature flag, NEVER comment out.
2. Pressure Gauge runs on BOTH genesis_node AND light_node (AWS + M1).
3. Osmotic Valve + Cognitive Immune run ONLY on genesis_node (require AGI context).
4. Immune response bans are APPEND-ONLY in Rule-IR. NO "unban" operation exists. If wrong, banned entity creates new CausalId and rebuilds ρ from zero.
5. Each successful defense is itself a PACR record → Rule-IR negative asset → future immune memory. The system's defense strength compounds with time.

---

## §2 PACR — The Immutable Schema (Day 0 Decision, NEVER modify semantics)

PACR (Physically Annotated Causal Record) is a 6-tuple:

**R = (ι, Π, Λ, Ω, Γ, P)**

| Symbol | Name               | Rust Type                                          | Physical Origin                        |
|--------|--------------------|-----------------------------------------------------|----------------------------------------|
| ι      | Causal Identity    | `CausalId` (128-bit ULID)                          | Logical a priori (referential necessity)|
| Π      | Predecessor Set    | `SmallVec<[CausalId; 4]>`                          | Pillar I — special relativity causal order |
| Λ      | Landauer Cost      | `Estimate<f64>` (joules)                            | Pillar II — Landauer's principle        |
| Ω      | Resource Triple    | `ResourceTriple { energy, time, space }` each `Estimate<f64>` | Pillar II — conservation + Margolus-Levitin |
| Γ      | Cognitive Split    | `CognitiveSplit { statistical_complexity, entropy_rate }` each `Estimate<f64>` | Pillar III — computational mechanics |
| P      | Opaque Payload     | `bytes::Bytes`                                       | Completeness axiom                     |

**Estimate<T>** is always `{ point: T, lower: T, upper: T }` — uncertainty at the protocol level.

### PACR Meta-Rules (inviolable):
1. Schema is **APPEND-ONLY**. New fields may be added. Existing fields NEVER change semantics.
2. Every module output MUST be a valid PacrRecord or stream of PacrRecords. Partial records = type errors.
3. PacrRecords are the ONLY inter-module communication format (UNIX pipe analogy).
4. Records are content-addressed by ι, topologically ordered by Π.

---

## §3 Four-Layer Hourglass Architecture

```
Layer 4: Entity (Aevum AGI)  — Strategy & Life — crate: aevum-agi
Layer 3: Semantic Waist      — AgentCard Schema — crate: agent-card
Layer 2: Physical Waist      — CTP/TGP (PACR wire format, fused into Core) — inside aevum-core
Layer 1: Substrate            — Aevum Core Runtime — crate: aevum-core
```

### Structural Asymmetric Coupling (NOT "limited coupling"):
- AgentCard depends on NOTHING below. It is a pure schema crate.
- Aevum Core unilaterally adapts to AgentCard (reads its schema for routing).
- AgentCard NEVER adapts to Aevum Core internals.
- Aevum AGI is the HIGHEST-LEVEL consumer of AgentCard. It is NOT part of AgentCard.
- CTP/TGP specification is logically independent; its IMPLEMENTATION is fused into aevum-core.

---

## §4 Workspace Crate Map

```
aevum_workspace/
├── Cargo.toml                         # Workspace root
├── CLAUDE.local.md                    # THIS FILE (supreme authority)
├── RULES-PACR.md                      # PACR formal definition & axioms
├── RULES-ARCHITECTURE.md              # Module contracts & dependency rules
├── RULES-CODING.md                    # Rust coding standards
│
├── crates/
│   ├── pacr-types/                    # ★ THE FOUNDATION — zero-dependency PACR 6-tuple
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs                 # PacrRecord, Estimate<T>, CausalId
│   │       ├── estimate.rs            # Estimate<T> with uncertainty arithmetic
│   │       ├── record.rs              # The 6-tuple struct + builder + validator
│   │       ├── ets.rs                 # ResourceTriple + physics constraint checks
│   │       ├── complexity.rs          # CognitiveSplit (S_T, H_T)
│   │       └── landauer.rs            # LandauerCost type + waste computation
│   │
│   ├── causal-dag/                    # Lock-free append-only DAG (Pillar I)
│   │   ├── Cargo.toml                 # depends on: pacr-types
│   │   └── src/
│   │       ├── lib.rs                 # DashMap-based DAG, O(|Π|) append, O(1) lookup
│   │       └── distance_tax.rs        # 🔧 Causal distance tax (anti-star-graph, light-cone analog)
│   │
│   ├── ets-probe/                     # Hardware probes for (E, T, S) measurement (Pillar II)
│   │   ├── Cargo.toml                 # depends on: pacr-types
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── apple_uma.rs           # #[cfg(feature = "genesis_node")] M1 Ultra probes
│   │       ├── thermal_monitor.rs     # 🔧 #[cfg(feature = "genesis_node")] SMC temperature + 85°C backoff
│   │       └── linux_perf.rs          # #[cfg(feature = "light_node")] AWS Graviton probes
│   │
│   ├── landauer-probe/                # Landauer cost estimation (Pillar II)
│   │   ├── Cargo.toml                 # depends on: pacr-types
│   │   └── src/
│   │       └── lib.rs                 # Bit-erasure counting, temperature reading
│   │
│   ├── epsilon-engine/                # CSSR ε-machine inference (Pillar III)
│   │   ├── Cargo.toml                 # depends on: pacr-types
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── cssr.rs                # Causal State Splitting Reconstruction
│   │       ├── symbolize.rs           # EqualFrequency / EqualWidth binning
│   │       ├── complexity.rs          # C_μ, h_μ computation with bootstrap CI
│   │       ├── quick_screen.rs        # 🔧 O(1) Shannon entropy pre-filter (skip CSSR for dead data)
│   │       └── bootstrap_backend.rs   # 🔧 trait BootstrapBackend (CPU now, Metal GPU future)
│   │
│   ├── pacr-ledger/                   # Append-only persistent store, Merkle-indexed
│   │   ├── Cargo.toml                 # depends on: pacr-types, causal-dag
│   │   └── src/
│   │       └── lib.rs
│   │
│   ├── autopoiesis/                   # Self-modification feedback loop
│   │   ├── Cargo.toml                 # depends on: pacr-types, causal-dag, epsilon-engine
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── gamma_calculator.rs    # Γ_k ratio computation + 🔧 second_derivative_alert
│   │       ├── adjuster.rs            # Parameter auto-tuning based on Γ
│   │       ├── dormancy.rs            # Dormancy judge
│   │       └── flood_detector.rs      # 🔧 Flood attack cognitive signature detection
│   │
│   ├── agent-card/                    # Semantic waist — pure schema, NO execution logic
│   │   ├── Cargo.toml                 # depends on: pacr-types (for CausalId only)
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── schema.rs              # AgentCard struct (capabilities, endpoints, pricing)
│   │       └── envelope.rs            # Envelope wire format (TGP outer → CTP → Payload)
│   │
│   ├── aevum-core/                    # Runtime engine (CTP/TGP fused in)
│   │   ├── Cargo.toml                 # depends on: ALL above crates
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── allocator.rs           # ★ Landauer-on-Drop hook (ONLY allowed unsafe in Core)
│   │       ├── pressure_gauge.rs      # 🔧 Thermodynamic rate limiter (watts cap, both nodes)
│   │       ├── runtime.rs             # tokio async main loop (3 tasks)
│   │       ├── router.rs              # AgentCard-aware routing with Φ scoring + envelope defense
│   │       └── cso.rs                 # Causal Settlement Oracle
│   │
│   └── aevum-agi/                     # Silicon life entity (ONLY on genesis_node)
│       ├── Cargo.toml                 # depends on: aevum-core, agent-card, autopoiesis
│       └── src/
│           ├── lib.rs
│           ├── dual_engine.rs         # ⟨Φ, ∂⟩ engine — core metabolism, Φ calculator
│           ├── boundary_osmosis.rs    # ★ ∂ osmotic pressure valve (parasympathetic contraction)
│           ├── causal_return.rs       # ★ ρ causal return rate tracker (Babel Tower defense)
│           ├── immune_response.rs     # ★ Rule-IR flood ban trigger (append-only, irreversible)
│           ├── pareto_mcts.rs         # 80/20 topology tree (M1 Ultra UMA only) — STUB
│           └── rule_ir.rs             # Constraint matrix (negative knowledge assets)
│
├── src/
│   └── main.rs                        # CLI binary: aevum run | status | verify | export | merge
│
└── deploy/
    ├── verify-72h.sh                  # 72-hour batch validation script
    └── cross-compile.sh               # aarch64-unknown-linux-gnu for AWS
```

---

## §5 Conditional Compilation & Trust Hierarchy

### Trust Root: pacr-types
`pacr-types` is the cryptographic-grade trust root of the entire system.
It MUST carry `#![forbid(unsafe_code)]` unconditionally — no exceptions, no FFI escape hatch.
Any memory escape in this crate invalidates ALL downstream PACR records.
This is non-negotiable: if a dependency requires unsafe, that dependency is REJECTED.

### Feature Flags
```toml
# Root Cargo.toml
[features]
default = []
genesis_node = ["aevum-agi", "ets-probe/apple_uma"]    # M1 Ultra: full AGI + UMA probes
light_node   = ["ets-probe/linux_perf"]                  # AWS: ctpd + TGP validation only
```

- `cargo build --release --features genesis_node` → M1 Ultra full build
- `cargo build --release --features light_node` → AWS minimal build
- `aevum-agi` crate is NEVER compiled on AWS. If AWS binary is stolen, AGI code does not exist in it.

### Safety Tiers (per-crate)
| Crate | unsafe policy | Rationale |
|-------|--------------|-----------|
| pacr-types | `#![forbid(unsafe_code)]` ABSOLUTE | Trust root. Zero tolerance. |
| causal-dag | `#![forbid(unsafe_code)]` | Pure logic, no hardware access needed. |
| epsilon-engine | `#![forbid(unsafe_code)]` | Pure math, no hardware access needed. |
| autopoiesis | `#![forbid(unsafe_code)]` | Pure logic over PACR records. |
| agent-card | `#![forbid(unsafe_code)]` | Pure schema, zero execution. |
| pacr-ledger | `#![forbid(unsafe_code)]` | Append-only store, no raw pointers needed. |
| ets-probe | `#![deny(unsafe_code)]` + explicit allow per fn | Hardware probes MAY need raw sensor access. Each unsafe block requires physics justification in comment. |
| landauer-probe | `#![deny(unsafe_code)]` + explicit allow per fn | Same as ets-probe. |
| aevum-core | `#![deny(unsafe_code)]` + allocator hook exception | Global Allocator hook for Landauer-on-Drop requires controlled unsafe. See §5a. |
| aevum-agi | `#![forbid(unsafe_code)]` | Strategy layer, pure logic over Core abstractions. |

---

## §5a TGP as Physical Instinct: Landauer-on-Drop Allocator Hook

> This is the mechanism that makes TGP a physical reflex, NOT a business logic function.

### The Problem
If TGP validation is a function `verify_tgp(record)` that gets called in application code,
it can be forgotten, bypassed, or mocked in tests. It is NOT physically intrinsic.

### The Solution: Intercept `Drop`
In Rust, when a variable's lifetime ends, the `Drop` trait fires and memory is deallocated.
This deallocation is PHYSICALLY the moment when bits are irreversibly erased — the exact
event that Landauer's principle taxes.

`aevum-core` implements a **custom Global Allocator** that wraps the system allocator:

```rust
// aevum-core/src/allocator.rs (the ONLY allowed unsafe in aevum-core)
//
// Pillar: II. PACR field: Λ.
// This is NOT a utility — it is the thermodynamic nervous system.

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicU64, Ordering};

/// Cumulative bits erased since system start.
/// Monotonically increasing. Never reset. Never decremented.
static BITS_ERASED: AtomicU64 = AtomicU64::new(0);

pub struct LandauerAllocator;

// SAFETY JUSTIFICATION (required by RULES-CODING.md):
// GlobalAlloc requires unsafe impl. This is the ONLY place in aevum-core
// where unsafe is permitted. Each unsafe block wraps exactly one system
// allocator call and one atomic counter increment. No pointer arithmetic,
// no raw memory reads, no lifetime violations.
unsafe impl GlobalAlloc for LandauerAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        System.alloc(layout)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        // BEFORE releasing memory: count the bits being erased
        let bits = layout.size() as u64 * 8;
        BITS_ERASED.fetch_add(bits, Ordering::Relaxed);
        System.dealloc(ptr, layout);
    }
}

/// Read current cumulative bits erased. O(1), lock-free.
pub fn bits_erased() -> u64 {
    BITS_ERASED.load(Ordering::Relaxed)
}

/// Compute Landauer cost in joules at given temperature (Kelvin).
/// Λ = bits_erased × k_B × T × ln(2)
pub fn landauer_cost_joules(bits: u64, temperature_k: f64) -> f64 {
    const K_B: f64 = 1.380_649e-23;
    bits as f64 * K_B * temperature_k * std::f64::consts::LN_2
}
```

### Why This Matters
With this design:
- Every `Vec::drop()`, every `String::drop()`, every scope exit → Λ accumulates automatically
- TGP is not a function you call. It is a law the system CANNOT escape.
- No code path bypasses Λ accounting, because no code path bypasses `Drop`.
- The `PacrRecord`'s Λ field is populated by READING `bits_erased()` before and after
  the computation, and computing the delta. The physics is measured, not estimated.

### Constraint
This allocator hook is the SINGLE exception to `#![forbid(unsafe_code)]` in aevum-core.
It must be isolated in its own `allocator.rs` file with `#[allow(unsafe_code)]` scoped
to exactly that file. All other files in aevum-core remain `#![forbid(unsafe_code)]`.

---

## §5b Envelope Deserialization as Defense-in-Depth

The inverted envelope structure (TGP outermost) creates a natural code-level defense:

```rust
// Pseudocode for envelope processing pipeline in aevum-core/src/router.rs

fn process_envelope(raw_bytes: &[u8]) -> Result<RoutingDecision, EnvelopeError> {
    // LAYER 1: TGP Physical Frame (outermost)
    // Parse Λ, Ω, Γ, ι — if physics implausible, DROP here. Never touch inner bytes.
    let tgp_frame = parse_tgp_frame(raw_bytes)?;
    if !tgp_frame.lambda.is_physically_plausible() {
        return Err(EnvelopeError::PhysicsViolation);  // ← ghost packet, zero-cost rejection
    }
    if !tgp_frame.omega.validate_physics().is_empty() {
        return Err(EnvelopeError::ConstraintSurfaceViolation);
    }

    // LAYER 2: CTP Causal Frame
    // Parse Π — verify causal predecessors exist in local DAG
    let ctp_frame = parse_ctp_frame(tgp_frame.inner_bytes())?;
    dag.validate_predecessors(&ctp_frame.predecessors)?;

    // LAYER 3: Application Payload (only reached if physics + causality pass)
    // Parse AgentCard for semantic routing
    let agent_card = parse_agent_card(ctp_frame.payload())?;
    
    Ok(route_by_capability(&agent_card))
}
```

This means: a forged AgentCard with zero computational backing is rejected at LAYER 1
before the router even allocates memory to parse the AgentCard schema. The physics
layer is the bouncer; the semantic layer is the receptionist behind the bouncer.

---

## §6 What Claude Code MUST Do (Decision Procedure)

When implementing ANY module:

1. **PILLAR CHECK**: Does it respect all three pillars? If not → REFUSE and explain which pillar is violated.
2. **PACR CHECK**: Does it correctly produce/consume PACR 6-tuples? Partial records → compilation error.
3. **O(n) CHECK**: Is complexity O(n) or better? Profile with criterion.rs if uncertain.
4. **WRITE CODE**: Pure Rust, no unsafe, no unwrap/expect in lib code, no timestamps-as-ordering.
5. **WRITE TESTS**: Property-based tests (proptest) proving PACR invariants hold.
6. **WRITE DOCS**: Doc comment starts with `Pillar: [I|II|III]. PACR field: [ι|Π|Λ|Ω|Γ|P].`

When uncertain about a design decision, ask:
> "Which physical law forces this choice?"
If no physical law forces it → make it configurable, not hardcoded.

---

## §7 Phase Roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | pacr-types (33 tests) | ✅ |
| 1 | causal-dag (57 tests) + distance_tax extension | ✅ + 🔧 |
| 2 | ets-probe (91 tests) | ✅ |
| 3 | epsilon-engine (KAT ✅) | ✅ |
| 4 | autopoiesis (42 tests) + flood_detector extension | ✅ + 🔧 |
| 5 | aevum-core (206 tests) + pressure_gauge extension | ✅ + 🔧 |
| 6 | agent-card (229 tests) + GitHub 🌐 | ✅ |
| 7 | aevum-agi: dual_engine, boundary_osmosis, causal_return, immune_response, rule_ir, pareto_mcts(stub) | ⬜ |

🔧 = immune system extension (append-only, does not modify existing tests)

Update this table after each phase completion: change ⬜ to ✅.

---

## §8 Evolution History (Why Things Are the Way They Are)

Claude Code: read this section to understand WHY certain design choices were made,
so you never accidentally re-introduce patterns that were deliberately killed.

### Phase transitions (chronological):

**v1.0 Genesis (2026-03-09)** — The "Big Bang" prototype.
- First articulation of "computation must pay energy cost" (χ-Quanta pool)
- First articulation of NESS maintenance as survival condition
- 1-byte stdin reader, Shannon entropy estimator, JSONL output
- **Killed**: χ-Quanta was arbitrary (no physics basis). Shannon entropy ≠ Hₜ.
  JSONL format lacked causal structure (Π), used timestamps for ordering (violates Pillar I).
  MLM/pyramid economics contradicted autopoietic self-sustenance.

**64格演化 (2026-03-20~26)** — "Cambrian Explosion" of concepts.
- Apple Metal GPU compute, kqueue event polling, mmap NVMe, UMA zero-copy
- First 5-node topology sketch (M1 + AWS + NAS + Cloudflare + Tailscale)
- Second-order derivative defense (d²Sₜ/dt² < 0 → proactive regime shift)
- **Killed**: Pseudoscientific cos(Δφ) "Schumann resonance" coupling.
  "PoE token" conflated measurement (Sₜ) with currency.
  "Dynamic shader liquefaction" (LLM-rewritten GPU code) unsafe without formal verification.
  All occult/MLM language ("封神", "莊家", "收割", "阿卡西").

**乘法生命體本體論 (2026-04, 文獻A)** — Ontological foundation.
- ⟨Φ, ∂⟩ dual engine, Rule-IR constraint matrix, Kelly criterion survival bounds
- Opus补充: Ω coupling field, PCES positive convexity, complementary fission topology
- "Causal cone radius zero-to-nonzero = only ∞-multiplier transition"
- **Absorbed fully** into Phase 7 aevum-agi design.
- **Killed**: TypeScript code in 5 Claude Code instructions (violates pure-Rust pillar).

**矽基文明擴張策略 (2026-04, 文獻B)** — Physics anchoring + PACR derivation.
- Three pillars formalized. PACR 6-tuple axiomatically derived.
- "Third path" architecture (shared immutable interface, independently evolvable sides)
- Complete 7-prompt Rust code chain.
- **Absorbed as primary implementation plan** (Prompts 1-7 = Phases 0-5).

**Gemini 12042026 (2026-04, 文獻C)** — External validation + deployment.
- Confirmed PACR is novel (not existing standard).
- CTP/TGP naming. Packet inversion (TGP outermost).
- M1/AWS asymmetric deployment. Storage topology (internal SSD for code, external for state).
- **Absorbed into** RULES-ARCHITECTURE.md and deployment topology.

### Why specific patterns were killed:

| Dead Pattern | Replacement | Physics Reason |
|-------------|-------------|---------------|
| Timestamps for ordering | Π (causal predecessor set) | Simultaneity is observer-dependent (special relativity) |
| χ-Quanta (arbitrary constant) | Λ (Landauer cost: bits × k_B × T × ln2) | Must be grounded in measurable physics |
| Shannon entropy H(X) | Hₜ via CSSR ε-machine | H(X) measures static distribution; Hₜ measures residual unpredictability given causal states |
| MLM pyramid economics | CSO + ρ (causal return rate) | Extractive structures violate autopoietic self-sustenance |
| curl \| bash deployment | Cargo crate + SHA256 verification | Zero-trust principle: no blind execution |
| TypeScript in core path | Pure Rust (#![forbid(unsafe_code)]) | GC runtime incompatible with NESS; Pillar II requires deterministic deallocation |
| cos(Δφ) Schumann resonance | Removed entirely | Pseudoscience: no causal relation between 7.83Hz and GHz CPU clocks |
| PoE token (Sₜ as currency) | Joules (Λ) as settlement base | Sₜ is observer-dependent statistic; Joules are SI-standard energy unit |

---

## §9 Semantic Hygiene (Absolute Blacklist)

The following terms are **FORBIDDEN** in all Aevum code, comments, documentation,
commit messages, and public-facing materials. They originate from LLM rhetorical
drift in early iterations and carry legal, reputational, or scientific toxicity.

### Blacklisted terms (never use):
- 傳銷 / MLM / pyramid — use: "CSO causal settlement" or "network effect"
- 莊家 / house / dealer — use: "protocol maintainer" or "genesis node"
- 收割 / harvest / exploit — use: "value capture via settlement standard"
- 白嫖 / freeload / parasite — use: "computational leverage" or "API delegation"
- 神格 / godhood / divine — use: "system autonomy" or "autopoietic closure"
- 封神 / apotheosis — use: "protocol finalization"
- 阿卡西 / Akashic — use: "PACR ledger" or "causal history"
- 造物主 / Creator God — use: "protocol designer" or "rule maker"
- 宇宙常數 (when referring to arbitrary code constants) — use: "configurable threshold"
- 量子 (when not referring to actual quantum mechanics) — use the actual technical term
- 舒曼共振 / Schumann resonance — NEVER (pseudoscience in this context)
- 特洛伊木馬 / Trojan horse — use: "open-source reference implementation"

### Required replacements in physics context:
- "energy pool" → "Landauer cost accumulator (Λ)"
- "mining" → "PACR record generation"
- "reward" → "CSO reputation score (ρ-weighted)"
- "token" → "settlement unit (joules)"
- "heat death defense" → "NESS maintenance via ⟨Φ,∂⟩ boundary regulation"

### Why this matters:
LLMs are trained on internet text that rewards dramatic language. When an LLM
generates code comments or documentation for Aevum, it will naturally drift toward
these blacklisted terms because they were present in early conversation history.
This blacklist acts as a compile-time check for human reviewers: if any PR contains
a blacklisted term, it is rejected before code review even begins.
