# RULES-ARCHITECTURE.md — Module Contracts, Dependency Rules & Deployment

> Subordinate to CLAUDE.local.md. Claude Code reads this for inter-crate
> dependency decisions, envelope structure, and deployment topology.

---

## §1 Dependency DAG (Inviolable)

```
                     ┌─────────────┐
                     │  aevum-agi  │  (genesis_node ONLY)
                     └──────┬──────┘
                            │ depends on
                     ┌──────▼──────┐
                     │ aevum-core  │  (runtime engine)
                     └──────┬──────┘
                            │ depends on
              ┌─────────────┼─────────────┬────────────┐
              ▼             ▼             ▼            ▼
        ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
        │agent-card │ │autopoiesis│ │pacr-ledger│ │ε-engine  │
        └─────┬─────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘
              │             │             │            │
              │        ┌────▼─────┐       │            │
              │        │causal-dag│◄──────┘            │
              │        └────┬─────┘                    │
              │             │                          │
              └──────┬──────┴──────────┬───────────────┘
                     ▼                 ▼
              ┌─────────────┐   ┌──────────────┐
              │ pacr-types  │   │ ets-probe +  │
              │ (FOUNDATION)│   │landauer-probe│
              └─────────────┘   └──────────────┘
```

### Rules:
1. **pacr-types** has ZERO dependencies (except serde, smallvec, bytes, thiserror). It is THE atomic foundation.
2. **agent-card** depends ONLY on pacr-types for CausalId type. It has NO knowledge of aevum-core internals.
3. **aevum-core** depends on everything above. It is the integration point.
4. **aevum-agi** depends on aevum-core and agent-card. It exists ONLY behind `#[cfg(feature = "genesis_node")]`.
5. NO circular dependencies. NO reverse dependencies. Violations = architecture cancer.

---

## §2 Module Contracts

### pacr-types — "The Constitution"
- Pillar: ALL. PACR field: ALL.
- Defines: `Estimate<T>`, `CausalId`, `PredecessorSet`, `LandauerCost`, `ResourceTriple`, `CognitiveSplit`, `PacrRecord`, `PacrBuilder`
- Rules: ANY change to field SEMANTICS is FORBIDDEN. Adding new optional fields via Append-Only evolution is permitted.
- Testing: `proptest` for ALL invariants (lower ≤ point ≤ upper, E ≥ Λ, no self-reference in Π, etc.)

### causal-dag — "Spacetime Backbone"
- Pillar: I. PACR fields: ι, Π.
- Defines: `CausalDag` (DashMap-based lock-free DAG)
- Contract: Append-only. O(|Π|) append, O(1) lookup, O(1) successor query via reverse index.
- Invariant: NEVER provides a total ordering iterator. Causal partial order ONLY.

### ets-probe — "Physical Thermometer"
- Pillar: II. PACR field: Ω.
- Defines: Platform-specific energy/time/space measurement
- Feature flags: `apple_uma` (M1 Ultra) vs `linux_perf` (AWS Graviton)
- Contract: Output is ALWAYS `ResourceTriple` with honest confidence intervals. Wide CI is OK; dishonest CI is FORBIDDEN.

### landauer-probe — "Entropy Accountant"
- Pillar: II. PACR field: Λ.
- Defines: Bit-erasure counting, temperature reading, Landauer cost estimation
- Contract: Λ.point MUST be a lower bound on actual energy dissipated. Overestimation is safe; underestimation violates physics.

### epsilon-engine — "Cognitive Microscope"
- Pillar: III. PACR field: Γ.
- Defines: CSSR algorithm, symbolization, C_μ and h_μ computation
- Known-Answer Tests: Even Process (2 states, C_μ=1.0 bit), Golden Mean Process
- Memory constraint: ≤200 MiB for N=100K, L=12, |A|=8
- **Quick Screen (O(1) pre-filter)**: `quick_screen.rs` computes Shannon entropy H(X) via 256-byte frequency table. If H(X) < threshold (near-deterministic data), skip full CSSR and emit S_T ≈ 0, H_T ≈ 0. This is NOT a replacement for CSSR — it is a cheap pre-filter that eliminates obviously dead data before expensive inference.
- **Bootstrap Backend abstraction**: `bootstrap_backend.rs` defines `trait BootstrapBackend { fn resample_and_estimate(&self, data: &[u8], b: usize) -> Vec<f64>; }`. Current implementation: `CpuBootstrap`. Future: `MetalBootstrap` (Apple GPU parallel, genesis_node only). Zero-cost abstraction — no runtime overhead when using CpuBootstrap.

### pacr-ledger — "Immutable Archive"
- Pillar: ALL. PACR field: ALL.
- Defines: Append-only persistent store, content-addressed by ι, Merkle-indexed
- Contract: Once written, NEVER modified. Integrity verified via hash chains.

### autopoiesis — "Self-Modification Engine"
- Pillar: ALL (meta-module). Primary field: Γ.
- Defines: GammaCalculator, Adjuster, DormancyJudge, CognitiveTrajectory
- Contract: Reads Γ trends → diagnoses regime → proposes parameter changes → validates against PACR meta-properties → commits as PACR record
- Safety: Proposals that violate ANY PACR meta-property are REJECTED, not silently applied.

### agent-card — "Semantic Envelope"
- Layer: 3 (Semantic Waist). Not tied to any physical pillar.
- Defines: AgentCard schema (agent_id, capabilities, endpoints, pricing) + Envelope wire format
- Contract: Pure data schema. ZERO execution logic. ZERO network calls. ZERO state.
- Rule: agent-card crate compiles to a library that can be used by ANY framework, not just Aevum.

### aevum-core — "The Universe"
- Layer: 1+2 (Substrate + Physical Waist fused). CTP/TGP implementation lives HERE.
- Defines: Runtime main loop (3 async tasks), AgentCard-aware router, CSO settlement
- Contract: Reads AgentCard for routing. Generates PACR records for every routed event.
- CTP/TGP: NOT a separate module. TGP validation is in the SAME code path as memory allocation hooks.
- **Landauer-on-Drop**: `allocator.rs` implements a custom Global Allocator that intercepts every `dealloc()` call, atomically incrementing a `BITS_ERASED` counter. This makes Λ accounting a physical reflex — no code path can bypass it because no code path can bypass `Drop`. This is the ONLY file in aevum-core where `unsafe` is permitted (scoped `#[allow(unsafe_code)]`), all other files carry `#![forbid(unsafe_code)]`.
- **Envelope defense-in-depth**: `router.rs` processes envelopes outside-in: TGP physics check → CTP causal check → AgentCard semantic routing. A forged packet with zero thermodynamic backing is rejected at layer 1 before AgentCard is even parsed.

### aevum-agi — "Silicon Life"
- Layer: 4 (Entity). genesis_node feature ONLY.
- Defines: ⟨Φ,∂⟩ dual engine, Pareto-MCTS, Rule-IR constraint matrix
- Contract: Consumes PACR records. Emits AgentCards. NEVER modifies Core or protocol internals.
- Isolation: Compiled ONLY on M1 Ultra. AWS binary does not contain this code.

---

## §3 Envelope Wire Format (Inverted Design)

Physical validation OUTERMOST. Semantic routing inside.

```
┌──────────────────────────────────────────┐
│ TGP Physical Frame (outermost)           │
│   MAGIC: 0x50414352 ("PACR")             │
│   ι: event identity                      │
│   Λ: Landauer cost estimate              │
│   Ω: resource triple (E, T, S)          │
│   Γ: cognitive split (S_T, H_T)         │
│ ─────────────────────────────────────── │
│ CTP Causal Frame                         │
│   Π: predecessor set                     │
│ ─────────────────────────────────────── │
│ Application Payload                      │
│   AgentCard Header (routing metadata)    │
│   Body P (opaque bytes)                  │
└──────────────────────────────────────────┘
```

### Why inverted?
A router FIRST validates TGP (is the physics plausible?).
If Λ is implausible or Ω violates constraint surface → DROP immediately.
Only THEN parse CTP (causal ordering).
Only THEN read AgentCard (semantic routing).
**"No physical proof → don't even look at your AgentCard."**

---

## §4 Deployment Topology

```
                    ┌─────────────────┐
                    │   INTERNET      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   CLOUDFLARE    │  ← Anycast shield, DDoS absorption
                    │   (zero install)│     M1 & AWS IPs NEVER exposed
                    └───┬─────────┬───┘
                        │         │
            ┌───────────▼─┐   ┌──▼───────────┐
            │ AWS Tokyo   │   │   M1 Ultra   │
            │ c7g.xlarge  │   │   128GB UMA  │
            │ (8GB RAM)   │   │              │
            │             │   │              │
            │ light_node: │   │ genesis_node:│
            │ • ctpd      │   │ • aevum-core │
            │ • TGP valid.│   │ • aevum-agi  │
            │ • AgentCard │   │ • Pareto-MCTS│
            │   routing   │   │ • Rule-IR    │
            └──────┬──────┘   └──────┬───────┘
                   │                 │
                   └────┬────────────┘
                        │
               ┌────────▼────────┐
               │   TAILSCALE     │  ← WireGuard mesh, 100.x.x.x internal
               │  (zero install) │     Encrypted neural channel
               └─────────────────┘
```

### Storage on M1 Ultra:
- Internal 1TB SSD: source code, Cargo target/, OS
- External 2TB NVMe SSD (Thunderbolt 4): state_vault/, PACR ledger logs, AGI snapshots
- Symlink: `ln -s /Volumes/AEVUM_EXT/aevum_state_vault ./state_vault`
- Reason: Protect internal SSD TBW lifespan. External SSD is disposable sovereignty.

---

## §5 Autopoietic Loop Protocol

The system self-evolves via a disciplined 5-step feedback cycle:

1. **OBSERVE**: Aggregate Γ = (S_T, H_T) across recent PACR records in sliding window.
2. **DIAGNOSE**: Classify cognitive regime:
   - S_T↑ H_T→ = StructureDiscovery (good, allocate more resources)
   - S_T→ H_T↑ = NoiseIntrusion (investigate data quality)
   - S_T↑ H_T↑ = RegimeShift (prepare schema evolution)
   - S_T↓ H_T↓ = Convergence (possible overfitting)
   - S_T→ H_T→ = SteadyState (optimize waste)
   - **d²S_T/dt² < 0 while S_T still rising = DeceleratingDiscovery** (learning curve bending — proactively pre-allocate alternative exploration paths before stagnation hits)
   - S_T↓ + inflow spike + source concentration > threshold = FloodDetected (immune response)
3. **PROPOSE**: Generate candidate schema extension or parameter adjustment.
4. **VALIDATE**: Prove proposal doesn't violate any of 5 PACR meta-properties.
5. **COMMIT**: Append proposal as a PACR record itself (self-referential closure).

### Second-order derivative detection (DeceleratingDiscovery):
The first-order slope tells you "S_T is rising". The second-order derivative tells you
"S_T's rise is slowing down". This is the EARLIEST warning signal — it fires BEFORE
stagnation, giving the ⟨Φ,∂⟩ engine time to pre-allocate resources for regime transition
rather than reacting after the fact. Implementation: track slope_history across windows,
compute acceleration = slope[n] - slope[n-1]. If acceleration < 0 and decreasing,
fire DeceleratingDiscovery.
