# DECISION-LOG.md — Source Material Usage Decisions

> This file records WHICH content from 文獻A (乘法生命體本體論) and 文獻B (矽基文明擴張策略)
> should be used directly vs. adapted vs. discarded for Claude Code execution.

---

## Decision 1: pacr-types Crate — USE 文獻B CODE DIRECTLY

**Verdict: Direct use with minor fixes.**

文獻B (Opus) produced complete, compilable Rust code for `pacr-types/src/lib.rs` including:
- `Estimate<T>` with uncertainty arithmetic
- `CausalId` (128-bit ULID)
- `PredecessorSet` (SmallVec<[CausalId; 4]>)
- `LandauerCost`, `ResourceTriple`, `CognitiveSplit`
- `PacrRecord` (the 6-tuple)
- `PacrBuilder` (enforces all-6-fields-mandatory)
- `PacrValidationIssue` enum
- Physics constraint checks (Margolus-Levitin, E ≥ Λ, non-negative quantities)

**Action**: Copy 文獻B's `pacr-types` code as Phase 0 starting point. Split into separate files:
- `estimate.rs` ← Estimate<T>
- `record.rs` ← PacrRecord + PacrBuilder  
- `ets.rs` ← ResourceTriple + PhysicsViolation
- `complexity.rs` ← CognitiveSplit
- `landauer.rs` ← LandauerCost type alias + waste computation

**Required fixes**:
- Add `#[non_exhaustive]` to all public enums
- Fix `PredecessorSet` type: 文獻B uses `SmallVec<[CausalId; 4]>` in struct but `SmallVec<[CausalId; 8]>` in module comment — standardize to 4
- Add `Eq, Hash` derives where appropriate (NOT on f64-based Estimates)
- Ensure `bytes` crate version is pinned

---

## Decision 2: causal-dag Crate — USE 文獻B CODE DIRECTLY

**Verdict: Direct use.**

文獻B produced complete `causal-dag/src/lib.rs` with:
- `CausalDag` struct (DashMap-based)
- `append()` with O(|Π|) validation
- `get()`, `predecessors()`, `successors()` — all O(1)
- `ancestry()` with depth-limited BFS
- Reverse index for forward traversal

**Action**: Use directly. Add proptest invariant tests per RULES-CODING.md.

---

## Decision 3: autopoiesis Crate — USE 文獻B CODE AS SKELETON, EXTEND

**Verdict: Use skeleton, needs extension.**

文獻B produced `CognitiveTrajectory` + `CognitiveRegime` enum + `diagnose()` with linear regression.
This is the OBSERVATION + DIAGNOSIS part of the autopoietic loop.

**Missing (must be added)**:
- `GammaCalculator`: Γ_k = (ΔC_μ,k / C̄_μ,k) / (ΔΛ_k / Λ̄_k) — from 文獻B Prompt 6
- `Adjuster`: parameter auto-tuning based on Γ thresholds
- `DormancyJudge`: k consecutive periods without Γ → enter dormancy
- PROPOSE and VALIDATE steps (not yet coded in 文獻B)

**Action**: Start with 文獻B skeleton. Implement missing components per Prompt 6 specification.

---

## Decision 4: epsilon-engine Crate — USE 文獻B PROMPT SPEC, CODE FROM SCRATCH

**Verdict: Spec from 文獻B, code fresh.**

文獻B Prompt 5 provides detailed CSSR algorithm specification:
- Suffix tree construction for ℓ = 1..L
- KS test for homogeneity checking
- Recursive splitting
- C_μ and h_μ computation
- Bootstrap error estimation (B=200)
- Known-Answer Tests (Even Process, Golden Mean)
- Memory constraints (≤200 MiB for N=100K, L=12, |A|=8)
- Symbolization module (EqualFrequency, EqualWidth)

**But**: No actual code was produced in the conversation — only spec.

**Action**: Feed Prompt 5 specification directly to Claude Code. It will generate the code.

---

## Decision 5: ets-probe + landauer-probe — USE 文獻B PROMPT SPEC, CODE FROM SCRATCH

**Verdict: Spec from 文獻B Prompt 4, code fresh.**

Prompt 4 specifies:
- ets-probe: CPU time measurement, memory allocation tracking, temperature reading
- landauer-probe: bits_erased counting, Landauer cost = bits × k_B × T × ln(2)
- Platform target: aarch64-unknown-linux-gnu (AWS first, M1 later)
- Test: allocate 1 MiB → free → verify bits_erased == 8,388,608

**Action**: Feed Prompt 4 to Claude Code. Add M1 Ultra apple_uma feature flag for genesis_node.

---

## Decision 6: agent-card Crate — SYNTHESIZE FROM 文獻A + 文獻C, DO NOT USE 文獻A TS CODE

**Verdict: Synthesize new Rust code. Discard TypeScript.**

文獻A produced five TypeScript-based Claude Code instructions (Envelope, Reputation, π Projection, Graph API, Wire Format).
These are conceptually correct but violate the "pure Rust core" principle.

文獻C (Gemini) provided the critical insight: INVERT envelope structure (TGP outermost).

**Action**:
- Schema definition: new Rust code following SPEC-AGENTCARD.md
- Envelope wire format: new Rust code per RULES-ARCHITECTURE.md §3 (inverted design)
- Reputation/π/Graph: implement as Rust modules inside aevum-core (NOT agent-card crate)
- The five TypeScript instructions from 文獻A should be treated as conceptual blueprints,
  NOT as executable specifications

---

## Decision 7: aevum-core Runtime — USE 文獻B PROMPT 7 SPEC

**Verdict: Spec from 文獻B, code fresh.**

Prompt 7 specifies:
- CLI: `aevum run | status | verify | export | merge`
- Runtime: tokio with max_threads=2
- Three async tasks: Record Producer, Epsilon Worker, Autopoiesis
- Deploy: cross-compile → scp → systemd
- 72h verification plan

**Action**: Feed Prompt 7 to Claude Code after Phases 0–4 are complete.

---

## Decision 8: aevum-agi — DO NOT IMPLEMENT YET

**Verdict: Phase 7, after everything else works.**

文獻A's ⟨Φ,∂⟩ engine, Pareto-MCTS, Rule-IR are conceptual frameworks.
They require a working PACR infrastructure (Phases 0–5) before they can be meaningfully implemented.

**Action**: Defer to Phase 7. For now, the `aevum-agi` crate should contain only stub modules
with doc comments describing the intended behavior. The actual implementation requires:
1. A running 72h-validated PACR ledger (Phase 5 ✅)
2. A working CSO with real agent interactions (Phase 6 ✅)
3. Real Γ trajectory data to train the autopoietic loop

---

## Decision 9: 文獻B's 7-Prompt Chain — USE AS PRIMARY EXECUTION PLAN

**Verdict: The 7-prompt chain IS the implementation plan.**

文獻B Prompts 1–7 are designed to be fed sequentially to Claude Code:

| Prompt | Phase | Deliverable |
|--------|-------|-------------|
| 1 | 0 | estimate.rs (Estimate<T> type) |
| 2 | 0 | ets.rs (ResourceTriple + ETS constraint validation) |
| 3 | 1 | causal-dag crate (lock-free DAG) |
| 4 | 2 | ets-probe + landauer-probe (hardware measurement) |
| 5 | 3 | epsilon-engine (CSSR ε-machine) |
| 6 | 4 | pacr-bridge + autopoiesis (feedback loop) |
| 7 | 5 | runtime integration + 72h validation |

**Action**: Execute Prompts 1–7 in sequence. After each prompt:
1. `cargo test` must pass
2. Update CLAUDE.local.md Phase Roadmap table (⬜ → ✅)
3. Commit to git with message format from RULES-CODING.md

**Additional phases NOT in 文獻B** (must be added):
| Phase | Deliverable | Source |
|-------|-------------|--------|
| 6 | agent-card schema + envelope wire format | Synthesized from 文獻A+C |
| 7 | aevum-agi stubs (⟨Φ,∂⟩, Pareto-MCTS, Rule-IR) | 文獻A conceptual spec |

---

## Summary: Source Material Routing Table

| Component | 文獻A (乘法本體論) | 文獻B (擴張策略) | 文獻C (Gemini) | Action |
|-----------|-------------------|-----------------|----------------|--------|
| pacr-types | — | ★ Full Rust code | Validation | Use B directly |
| causal-dag | — | ★ Full Rust code | — | Use B directly |
| autopoiesis | Conceptual (⟨Φ,∂⟩) | ★ Skeleton code + Prompt 6 | — | B skeleton + extend |
| epsilon-engine | — | ★ Prompt 5 spec | — | B spec → fresh code |
| ets-probe | — | ★ Prompt 4 spec | — | B spec → fresh code |
| landauer-probe | — | ★ Prompt 4 spec | — | B spec → fresh code |
| agent-card | TS code (discard) | — | Schema insight | Synthesize new Rust |
| envelope | TS code (discard) | — | ★ Inverted design | C design → new Rust |
| aevum-core | — | ★ Prompt 7 spec | Deploy topology | B spec → fresh code |
| aevum-agi | ★ Conceptual spec | — | 4-layer separation | A concepts → Phase 7 stubs |
| CLAUDE.md | — | ★ Full draft | Full draft | Merge B+C → CLAUDE.local.md (done) |
| 9 broadcast strategies | — | ★ Complete | — | Reference only (not code) |
| Deployment topology | — | — | ★ M1/AWS/CF/TS | Use C directly |
