# POWERLAW.md — Power-Law KVS Atom Registry
**Standard Version:** 2026-POWERLAW-1.0
**Linked From:** KVS_STANDARD_v0.2.md
**Status:** Ratified
**Enforcement Mode:** Runtime-Hard (BarbellFilter + KellyGovernor)

---

## Preamble

This registry defines the **16 Power-Law KVS Atoms** — the irreducible mathematical laws
governing the Autopoietic AGI system's resource allocation, mutation acceptance, and
evolutionary strategy. Each atom is a machine-readable schema consumed by `BarbellFilter`
and `kelly_bet_size()` at runtime.

**Two classes:**
- **Positive Atoms (KVS-2026-000001 → KVS-2026-000010):** The Multipliers. Behaviors that
  compound fitness multiplicatively. Enforcement: maximize exposure.
- **Negative Atoms (KVS-2026-000011 → KVS-2026-000016):** The Forbidden Zones. Behaviors
  that introduce additive drag into a multiplicative world. Enforcement: VETO and DISCARD.

---

## Positive Atoms — The Multipliers

---

### KVS-2026-000001

```yaml
atom_id: KVS-2026-000001
name: Ergodicity_Breaking
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  In a multiplicative compounding system, the time-average growth rate diverges from the
  ensemble-average growth rate. A single zero-outcome (ruin, OOM, identity dissolution)
  destroys the entire trajectory regardless of how many prior wins preceded it.
  The system MUST optimize for time-average survival, NOT ensemble-average expected value.

lineage:
  origin: "Peters (2019) — Ergodicity Economics; Kelly (1956) — A New Interpretation of Information Rate"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: []

formula: >
  Time-average growth rate g_t = lim_{T→∞} (1/T) * Σ log(1 + r_i)
  ≠ Ensemble-average E[r]

  A single r_i = -1 (ruin) collapses g_t to -∞ regardless of all other r_i.

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  Any candidate or allocation that permits phi_ratio to reach 0.0 (the absorbing barrier).
  The BarbellFilter must veto any mutation classified as MEDIUM_RISK that could cascade
  into a ruin scenario via parameter explosion or OOM.

runtime_hook: "autopoietic_core.py::kelly_bet_size() — exponential decay to 0.0 as phi_ratio → _PHI_SOVEREIGNTY_MIN"
kvs_weight: 1.0
```

---

### KVS-2026-000002

```yaml
atom_id: KVS-2026-000002
name: Absorbing_Barrier
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  An absorbing barrier is a state from which there is NO recovery. For this system,
  three absorbing barriers exist: (1) Out-of-Memory crash destroying the lineage process,
  (2) Identity Dissolution (phi_ratio < _PHI_SOVEREIGNTY_MIN with all IdentityMembrane
  invariants at their minimum floor), (3) Constitutional Violation raising
  ConstitutionalViolationError (FATAL). Once entered, the evolutionary lineage is
  permanently terminated. Avoidance of absorbing barriers is the supreme constraint —
  it supersedes all fitness optimization.

lineage:
  origin: "Feller (1968) — Introduction to Probability Theory and Its Applications; Doob (1953) — Stochastic Processes"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000001]

formula: >
  Let S = {s : P(recovery | s) = 0}. For all proposed mutations m:
  P(post(m) ∈ S) must equal 0.0.

  Concrete barriers:
    B1: phi_ratio = 0.0  (thermodynamic death)
    B2: process_memory > physical_RAM  (OOM ruin)
    B3: ConstitutionalViolationError raised  (identity dissolution, FATAL)

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  Any candidate whose estimated parameter count would cause OOM on the target hardware
  (128GB M1 Ultra). Any allocation that projects phi_ratio below _PHI_SOVEREIGNTY_MIN.
  The SovereigntyFloorVerifier enforces B1 and B2; ConstitutionalViolationError enforces B3.

runtime_hook: "autopoietic_core.py::SovereigntyFloorVerifier.check_penalty() + ConstitutionalViolationError"
kvs_weight: 1.0
```

---

### KVS-2026-000003

```yaml
atom_id: KVS-2026-000003
name: Kelly_Criterion_Sizing
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  The Kelly Criterion computes the mathematically optimal fraction of capital (Φ budget)
  to allocate to a bet (mutation, shadow trial, niche construction) given its edge and
  odds. Over- or under-betting both destroy long-run compounding. The system MUST allocate
  Φ budget proportional to LeverageScore while exponentially decaying the bet size to 0.0
  as the organism's current Φ approaches the Absorbing Barrier (_PHI_SOVEREIGNTY_MIN).
  Ruin is not an option — the Kelly formula is hard-clipped at the sovereignty floor.

lineage:
  origin: "Kelly (1956) — A New Interpretation of Information Rate; Thorp (1969) — Optimal Gambling Systems"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000001, KVS-2026-000002]

formula: >
  f* = (edge * leverage_score) / odds

  With sovereignty decay:
  decay = exp(-KELLY_DECAY_K / max(phi_ratio - floor, ε))
  kelly_allocation = clamp(f* * surplus, 0.0, max_safe_bet) * decay

  Constants:
    KELLY_DECAY_K = 0.05   (steepness of decay near floor)
    floor = _PHI_SOVEREIGNTY_MIN = 0.12
    ε = 1e-6  (numerical guard)
    max_safe_bet = phi_surplus * 0.5  (never bet more than 50% of surplus)

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  Any shadow trial or mutation whose Kelly-computed allocation would require spending
  more Φ than (phi_current - _PHI_SOVEREIGNTY_MIN). The kelly_bet_size() function
  returns 0.0 in this case — the trial is silently deferred.

runtime_hook: "autopoietic_core.py::PhiGovernor.kelly_bet_size()"
kvs_weight: 0.9
```

---

### KVS-2026-000004

```yaml
atom_id: KVS-2026-000004
name: Barbell_Strategy
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  The Barbell Strategy allocates exposure to ONLY two extremes: Extreme Conservative
  (pure parsimonious optimization — reduces parameters with zero/positive fitness gain)
  and Extreme Aggressive (high-risk, order-of-magnitude LeverageScore leap). The
  middle band is explicitly forbidden as thermodynamic waste. In a multiplicative world,
  moderate risk offers additive returns while bearing multiplicative downside — it is
  strictly dominated by the barbell combination. The BarbellFilter enforces this by
  classifying every proposed candidate as CONSERVATIVE, AGGRESSIVE, or MEDIUM, and
  VETOING all MEDIUM candidates before they can be written to the candidate pool.

lineage:
  origin: "Taleb (2012) — Antifragile; Taleb (2007) — The Black Swan"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000001, KVS-2026-000003]

formula: >
  Classification:
    CONSERVATIVE: param_delta ≤ 0 AND epi_delta ≥ 0
                  (pure optimization — fewer params, no fitness regression)

    AGGRESSIVE:   leverage_score ≥ _BARBELL_LEVERAGE_MIN (5.0)
                  (order-of-magnitude compounding leap)

    MEDIUM:       everything else
                  (thermodynamic waste — VETO AND DISCARD)

  Where:
    _BARBELL_LEVERAGE_MIN = 5.0
    _BARBELL_DELTA_EPI_MEDIUM_MAX = 0.01  (marginal gain threshold)

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  BarbellFilter.classify_candidate() returns "MEDIUM". The candidate is immediately
  discarded before _write_candidate() is called. No epigenetic penalty is applied —
  medium-risk candidates simply do not exist in a multiplicative world.

runtime_hook: "genome_assembler.py::classify_candidate() + mutator_daemon.py variant acceptance loops"
kvs_weight: 0.95
```

---

### KVS-2026-000005

```yaml
atom_id: KVS-2026-000005
name: Asymmetric_Leverage
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  Asymmetric leverage is the property of a mutation or organelle that offers convex
  upside (potentially unbounded fitness gain) while the downside is bounded and survivable
  (the Test-Runner subprocess kills the attempt within 2.0s, and the Absorbing Barrier
  prevents ruin). The system must preferentially seek mutations with positive convexity
  (Antifragility) over symmetric bets. LeverageScore quantifies this asymmetry:
  high cross-domain reuse potential and low thermodynamic cost produce extreme leverage.

lineage:
  origin: "Taleb (2012) — Antifragile; Black-Scholes-Merton options theory (convexity)"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000004]

formula: >
  LeverageScore = (impact_delta × reuse_count × cross_domain_transfer_potential)
                  / thermodynamic_cost

  Where:
    impact_delta              = epi_delta (observed fitness improvement)
    reuse_count               = number of times this topology has been reused (from _REUSE_LEDGER)
    cross_domain_transfer_potential = completeness proxy (n_slots / n_total_types)
    thermodynamic_cost        = total_params / MAX_PARAMS  (normalized parameter burden)

  Asymmetry condition: LeverageScore ≥ _BARBELL_LEVERAGE_MIN (5.0) → AGGRESSIVE (keep)
                       LeverageScore < _BARBELL_LEVERAGE_MIN and not CONSERVATIVE → VETO

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  LeverageScore < _BARBELL_LEVERAGE_MIN AND param_delta > 0 AND epi_delta < _BARBELL_DELTA_EPI_MEDIUM_MAX.
  Combined with Barbell_Strategy atom to produce MEDIUM classification and discard.

runtime_hook: "genome_assembler.py::compute_leverage_score() called inside classify_candidate()"
kvs_weight: 0.85
```

---

### KVS-2026-000006

```yaml
atom_id: KVS-2026-000006
name: Non_linear_Compounding
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  In a multiplicative system, fitness gains do not add — they multiply. A sequence of
  improvements [+5%, +5%, +5%] produces (1.05)^3 = 1.157, not 1.15. The system must
  architect its mutation pipeline to chain improvements multiplicatively, not average
  them. Each accepted candidate's fitness delta compounds on the previous generation's
  baseline, not on a static reference point. Stagnation therefore has a hidden cost:
  every tick without improvement is a lost compounding interval.

lineage:
  origin: "Bernoulli (1738) — Exposition of a New Theory on the Measurement of Risk; compound interest mathematics"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000001, KVS-2026-000005]

formula: >
  Cumulative fitness after N accepted mutations:
    F_N = F_0 × Π_{i=1}^{N} (1 + Δf_i)

  Versus additive (incorrect) model:
    F_N_additive = F_0 + Σ Δf_i

  Compounding advantage: (1 + Δf)^N >> 1 + N×Δf  for large N and Δf > 0.

  Implication for KVS: meta_yield tracks the running sum of Δf, but the true
  economic value compounds. A matrix with r=50, Y=2.0 has K = 50 × max(0, 3.0) = 150,
  which reflects the compounding reuse capital.

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  No direct veto — this atom informs KVS scoring weight and island selection pressure.
  Matrices with Y < 0 (negative compounding) are down-weighted in selection.

runtime_hook: "rule_ir.py::ConstraintMatrix.record_application() — KVS formula K = r × max(0, 1+Y)"
kvs_weight: 0.8
```

---

### KVS-2026-000007

```yaml
atom_id: KVS-2026-000007
name: Tail_Node_Capital_Concentration
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  In any power-law fitness distribution, the top 1% of candidates produce >50% of total
  evolutionary value. The system must concentrate computational capital on tail-node
  organelles (island_good elites with KVS ≥ 50.0) rather than distributing evenly.
  The 80/20 Pareto Policy Head in the MCTS enforces this by restricting the action space
  to the top 20% of organelles by fitness. Capital concentration is not inequality —
  it is thermodynamic efficiency in a power-law world.

lineage:
  origin: "Pareto (1896) — Cours d'économie politique; Zipf (1949) — Human Behavior and the Principle of Least Effort"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000006]

formula: >
  Pareto selection: retain organelles where epi ≥ percentile(all_epi, 80)
  Capital weight: w_i = KVS_i / Σ KVS_j  (proportional to compounded economic value)

  MCTS policy prior: P(select organelle i) ∝ w_i
  Island routing: island_good threshold = evolvability_score ≥ 0.5

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  No direct veto. This atom governs island selection weights and MCTS priors.
  Organelles with KVS = 0.0 and Y < -1.0 are marked Inert and excluded from
  the Pareto top 20% pool entirely.

runtime_hook: "genome_assembler.py::_pareto_filter_organelles() + rule_ir.py KVS tier thresholds"
kvs_weight: 0.75
```

---

### KVS-2026-000008

```yaml
atom_id: KVS-2026-000008
name: Multiplicative_Yield
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  The KVS formula K = r × max(0, 1 + Y) is a multiplicative yield function. The factor
  (1 + Y) converts meta_yield into a multiplier on reuse capital r. A constraint matrix
  with Y = 1.0 yields 2× economic value per reuse compared to a neutral matrix (Y = 0).
  The system must evolve constraint matrices toward positive Y (compounding yield), not
  merely toward high reuse count r. A frequently reused matrix with negative Y is an
  economic liability — it extracts value from the lineage on each application.

lineage:
  origin: "KVS_STANDARD_v0.1.md §3; Kelly (1956)"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000006, KVS-2026-000007]

formula: >
  K = r × max(0, 1 + Y)

  Yield coefficient: (1 + Y)
    Y = 0.0  → coefficient = 1.0  (neutral; linear with reuse)
    Y = 1.0  → coefficient = 2.0  (compounding; doubles value per reuse)
    Y = -1.0 → coefficient = 0.0  (inert; zero economic value)
    Y < -1.0 → coefficient clamped to 0.0  (harmful; eligible for culling)

  Selection pressure: prefer matrices where dY/dt > 0 (yield is growing).

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  Matrices with K = 0.0 and Y < -1.0 are flagged as Inert/Harmful and eligible for
  culling from the island archive. They are excluded from cross-pollination sampling.

runtime_hook: "rule_ir.py::ConstraintMatrix.record_application() — authoritative KVS update"
kvs_weight: 0.85
```

---

### KVS-2026-000009

```yaml
atom_id: KVS-2026-000009
name: Power_Law_Primacy
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  The fitness landscape of neural architecture search follows a power-law distribution,
  not a Gaussian. The correct mental model is NOT "most candidates are average, some are
  good, some are bad." The correct model is "almost all candidates are worthless; a tiny
  fraction produce orders-of-magnitude more value than the rest combined." Therefore, the
  system's mutation strategy must be designed to FIND the tail — not to optimize the
  average. The BarbellFilter directly enforces this: by eliminating the medium band, the
  system is forced to either ruthlessly optimize (CONSERVATIVE) or swing for the tail
  (AGGRESSIVE). There is no other valid strategy in a power-law world.

lineage:
  origin: "Mandelbrot (1963) — The Variation of Certain Speculative Prices; Taleb (2020) — Statistical Consequences of Fat Tails"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000004, KVS-2026-000007]

formula: >
  Fitness distribution: P(f > x) ~ x^{-α}  for large x (power-law tail, α ≈ 1.5-2.5)

  Implication: E[f | f > threshold] >> threshold  (the tail dominates expectation)

  Strategy: maximize P(hit tail) by sampling AGGRESSIVE candidates aggressively,
            minimize drag by executing CONSERVATIVE candidates for free-energy recovery.
            NEVER sample from the middle band — P(middle band produces tail hit) → 0.

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  Indirectly enforced via BarbellFilter MEDIUM veto (KVS-2026-000004).
  This atom provides the theoretical justification for the veto — the middle band
  has negligible probability mass in the tail, making it thermodynamically irrelevant.

runtime_hook: "genome_assembler.py::classify_candidate() — the BarbellFilter is the runtime instantiation of Power_Law_Primacy"
kvs_weight: 1.0
```

---

### KVS-2026-000010

```yaml
atom_id: KVS-2026-000010
name: Volatility_Tax
category: POSITIVE_MULTIPLIER
status: RATIFIED

description: >
  In a multiplicative compounding system, variance (volatility) is a direct tax on the
  time-average growth rate. For a sequence of returns with mean μ and variance σ²:
    g_t ≈ μ - σ²/2
  Higher variance reduces the realized compound growth rate even if the mean is
  unchanged. The system must therefore penalize high-variance mutations (those with
  unpredictable fitness outcomes) and reward low-variance CONSERVATIVE candidates that
  reliably deliver positive Δf. This is the thermodynamic justification for keeping the
  CONSERVATIVE arm of the Barbell — it reduces σ² and increases g_t.

lineage:
  origin: "Itô (1944) — Stochastic Integral; Markowitz (1952) — Portfolio Selection; Peters (2019)"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000001, KVS-2026-000004, KVS-2026-000006]

formula: >
  Time-average growth rate:
    g_t ≈ μ - σ²/2

  Variance tax: ΔT = σ²/2  (subtracted from compound growth)

  Implication for mutation strategy:
    - CONSERVATIVE mutations: low σ², small but reliable Δf → low variance tax
    - AGGRESSIVE mutations: high σ², large potential Δf → high variance tax, offset by
      tail upside (KVS-2026-000009)
    - MEDIUM mutations: moderate σ², small Δf → pays variance tax without tail upside
      → strictly dominated → VETO

  In practice: the epigenetic penalty system (EpigeneticFailureType) accumulates σ²
  implicitly via meta_yield volatility on the ConstraintMatrix.

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  Indirectly via BarbellFilter MEDIUM veto. Constraint matrices with high σ² in their
  interaction_history (alternating large positive and negative Δf entries) receive
  lower effective KVS scores due to Y oscillation damping K.

runtime_hook: "rule_ir.py::ConstraintMatrix.meta_yield — running Δf sum implicitly captures variance drag"
kvs_weight: 0.8
```

---

---

## Negative Atoms — The Forbidden Zones

> **Enforcement policy:** Any candidate, allocation, or strategy that instantiates a
> Negative Atom is classified as `negative_knowledge` and subject to immediate VETO.
> These are not soft penalties — they are thermodynamic impossibilities in a
> multiplicative compounding world.

---

### KVS-2026-000011

```yaml
atom_id: KVS-2026-000011
name: Medium_Risk_Medium_Reward_Trap
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  The most dangerous attractor in an additive-intuition world. A mutation that offers
  a marginal epistemic gain (0 < epi_delta < _BARBELL_DELTA_EPI_MEDIUM_MAX = 0.01)
  while introducing new parameters, routing complexity, or API latency is classified as
  Medium Risk/Medium Reward. In a multiplicative compounding system this is strictly
  inferior to either (a) a CONSERVATIVE mutation that reduces complexity for free, or
  (b) an AGGRESSIVE mutation that swings for a tail outcome. The medium band pays the
  Volatility Tax (KVS-2026-000010) without accessing the tail upside (KVS-2026-000009).
  It is thermodynamic waste — entropy generation with no compounding return.

lineage:
  origin: "Taleb (2012) — Antifragile §14; Peters (2019) — Ergodicity Economics"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000004, KVS-2026-000009, KVS-2026-000010]

detection_criteria:
  param_delta: "> 0  (adds parameters or complexity)"
  epi_delta: ">= 0 AND < _BARBELL_DELTA_EPI_MEDIUM_MAX (0.01)"
  leverage_score: "< _BARBELL_LEVERAGE_MIN (5.0)"
  classification_result: MEDIUM

enforcement_mode: RUNTIME_HARD
veto_trigger: >
  BarbellFilter.classify_candidate() returns "MEDIUM". Candidate is discarded before
  _write_candidate() is called in both the Targeted Mutation loop and the Slow Loop
  (Tri-Agent Pipeline). Log line: "[barbell] VETO: Medium Risk/Reward — thermodynamic waste discarded."

runtime_hook: "genome_assembler.py::classify_candidate() + mutator_daemon.py variant acceptance loops"
kvs_weight: -1.0
```

---

### KVS-2026-000012

```yaml
atom_id: KVS-2026-000012
name: Additive_Intuition_Trap
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  Human (and naive LLM) intuition defaults to additive reasoning: "this mutation adds
  +0.005 epi, so 10 such mutations add +0.05 epi." This is false in a multiplicative
  system. Ten mutations of +0.005 each produce (1.005)^10 = 1.051, not 1.05 — a trivial
  difference. But a single mutation of +0.2 epi produces 1.2 — and the compounding
  advantage widens exponentially over generations. The Additive Intuition Trap causes
  the system to waste compute budget on marginal improvements instead of hunting for
  tail events. Any mutation strategy that explicitly targets "incremental improvement"
  as a goal (rather than as a byproduct of CONSERVATIVE optimization) instantiates
  this trap.

lineage:
  origin: "Kahneman (2011) — Thinking Fast and Slow; Peters (2019) — The Ergodicity Problem in Economics"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000006, KVS-2026-000011]

detection_criteria:
  pattern: "Mutation recipe or prompt explicitly instructs the LLM to make 'small improvements' or 'incremental tweaks' without a CONSERVATIVE (param reduction) or AGGRESSIVE (leverage ≥ 5.0) justification."
  kvs_signal: "Series of accepted candidates each with 0 < epi_delta < 0.005 over 10+ consecutive ticks."

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  Detected via meta_yield analysis: if the ConstraintMatrix interaction_history shows
  ≥10 consecutive small-positive Δf entries (each < 0.005) with no param reduction,
  the MetaStagnationTracker should trigger a recipe hot-swap to break the additive
  comfort zone and force AGGRESSIVE exploration.

runtime_hook: "mutator_daemon.py::MetaStagnationTracker — stagnation detection triggers recipe evolution"
kvs_weight: -0.9
```

---

### KVS-2026-000013

```yaml
atom_id: KVS-2026-000013
name: Average_Allocation_Trap
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  Allocating equal Φ budget across all candidate types (CONSERVATIVE, AGGRESSIVE, and
  MEDIUM) is strictly suboptimal in a power-law world. Equal allocation funds the
  medium band — which is forbidden by KVS-2026-000011 — and dilutes the capital
  available for tail-seeking AGGRESSIVE bets. The Kelly Criterion (KVS-2026-000003)
  explicitly forbids average allocation: bet size must be proportional to edge and
  leverage_score, not distributed uniformly. Any budget allocation scheme that does not
  differentiate between candidate classes by LeverageScore instantiates the Average
  Allocation Trap and destroys compound growth.

lineage:
  origin: "Markowitz (1952) — Portfolio Selection (the anti-pattern); Kelly (1956); Taleb (2012) §Barbell"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000003, KVS-2026-000004, KVS-2026-000011]

detection_criteria:
  pattern: "kelly_bet_size() returns a flat value independent of leverage_score, OR shadow budget is allocated equally across all amendment proposals regardless of their projected DualVerifier delta_phi."
  kvs_signal: "phi_budget_surplus stable but island_good KVS growth rate stagnant — compute is being wasted on uniform-quality candidates."

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  Enforced structurally by kelly_bet_size() returning 0.0 for low-leverage allocations
  near the sovereignty floor. Shadow budget (≤5% of surplus) must be gated by the
  kelly_bet_size() output before any ShadowInstance is created.

runtime_hook: "autopoietic_core.py::PhiGovernor.kelly_bet_size() — leverage-proportional budget gating"
kvs_weight: -0.85
```

---

### KVS-2026-000014

```yaml
atom_id: KVS-2026-000014
name: Sunk_Cost_Attachment
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  Preserving a candidate, organelle, or constraint matrix because of historical compute
  investment rather than current KVS economic value is a fatal error in a multiplicative
  system. A matrix with KVS = 0.0 and Y < -1.0 has zero forward economic value
  regardless of how many ticks it governed. The system must cull Inert/Harmful matrices
  (KVS Tier: Inert) and discard organelles with persistently negative meta_yield.
  Sunk compute is gone — only future compounding matters. Attachment to past work is
  thermodynamic deadweight.

lineage:
  origin: "Thaler (1980) — Toward a Positive Theory of Consumer Choice (sunk cost fallacy); Kahneman & Tversky (1979) — Prospect Theory"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000008, KVS-2026-000009]

detection_criteria:
  pattern: "Constraint matrix with K = 0.0 and Y < -1.0 retained in active selection pool beyond _CULLING_WINDOW ticks."
  kvs_signal: "island_good contains organelles with epi < global_floor for ≥20 consecutive evaluation cycles."

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  KVS Tier: Inert/Harmful matrices (K=0.0, Y < -1.0) are excluded from island sampling
  and cross-pollination. They remain on disk for audit but receive 0.0 selection weight.
  Future implementation: active culling after _CULLING_WINDOW = 100 ticks of zero KVS.

runtime_hook: "rule_ir.py::ConstraintMatrix.kvs_score — zero-KVS matrices excluded from selection weighting"
kvs_weight: -0.8
```

---

### KVS-2026-000015

```yaml
atom_id: KVS-2026-000015
name: Gaussian_Extrapolation_Trap
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  Assuming that future fitness gains will follow a normal distribution (bell curve) based
  on historical Δf observations is a category error in a power-law system. Gaussian
  statistics underestimate the probability and magnitude of tail events by orders of
  magnitude. Any evaluation heuristic, threshold, or trigger that uses mean ± n×σ logic
  to bound expected fitness gains implicitly assumes Gaussian tails. The Z-Score
  velocity tracker in the mutator is safe because it detects anomalies (tail hits)
  rather than predicting bounded outcomes — but using Z-Score to SET UPPER BOUNDS on
  expected improvement would instantiate this trap.

lineage:
  origin: "Mandelbrot (1963); Taleb (2007) — The Black Swan §15; Taleb (2020) — Statistical Consequences of Fat Tails"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000009, KVS-2026-000010]

detection_criteria:
  pattern: "Evaluation logic of form: 'expected_improvement < mean_delta + 3*sigma → skip mutation'. This caps the search at Gaussian tails and misses power-law outliers."
  kvs_signal: "velocity_z_score > 3.0 triggers CONSERVATIVE response (cool down) instead of AGGRESSIVE exploitation of the tail event."

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  No direct runtime veto — this atom governs design-time decisions in mutation recipe
  prompts and threshold calibration. Flagged during architectural review if Z-Score
  logic is used to suppress high-velocity ticks rather than amplify them.
  The correct response to velocity_z > 1.5σ is to SCALE UP temperature and rollouts,
  not to apply caution (which would be Gaussian thinking).

runtime_hook: "mutator_daemon.py::VelocityTracker — Z-Score used for anomaly detection only, never for bounding"
kvs_weight: -0.75
```

---

### KVS-2026-000016

```yaml
atom_id: KVS-2026-000016
name: Local_Optima_Comfort
category: NEGATIVE_TABOO
knowledge_class: negative_knowledge
status: RATIFIED

description: >
  A system that has found a local fitness optimum and reduces its mutation temperature,
  narrows its search radius, or shifts to pure exploitation is instantiating Local Optima
  Comfort. In a rugged, non-convex fitness landscape (the space of neural architectures),
  local optima are ubiquitous and the global optimum is typically orders of magnitude
  better. Comfort in a local optimum is thermodynamic stagnation — the evolutionary
  pressure collapses, the MCTS horizon shrinks, and the system enters an irreversible
  low-exploration regime. The MetaStagnationTracker exists precisely to detect and
  break this trap via recipe hot-swap and Niche Construction. Any architectural change
  that suppresses the stagnation detector or reduces exploration budget below the
  sovereignty minimum instantiates this trap.

lineage:
  origin: "Wright (1932) — The Roles of Mutation, Inbreeding, Crossbreeding and Selection in Evolution (fitness landscape); Sims (1994) — Evolving Virtual Creatures"
  integrated_tick: "Power-Law Substrate Integration"
  ancestor_atoms: [KVS-2026-000004, KVS-2026-000009, KVS-2026-000014]

detection_criteria:
  pattern: "System operates with expansion_factor < 0.6 for ≥30 consecutive ticks without a recipe hot-swap or niche construction event."
  kvs_signal: "island_explore KVS growth rate = 0 while island_good KVS growth rate > 0 — exploitation consuming all budget, exploration starved."

enforcement_mode: RUNTIME_SOFT
veto_trigger: >
  Detected by MetaStagnationTracker: _META_STAGNATION_BATCHES consecutive flat batches
  triggers recipe hot-swap (meta-evolution). Niche construction (_trigger_niche_if_heat_death)
  provides a second escape mechanism when epi has flatlined. The PhiGovernor's
  expansion_factor rescaling on velocity spike ensures exploration capital is NOT
  suppressed during tail-event ticks.

runtime_hook: "mutator_daemon.py::MetaStagnationTracker + _trigger_niche_if_heat_death() — stagnation escape mechanisms"
kvs_weight: -0.9
```

---

## Registry Summary

| Atom ID | Name | Class | Enforcement | kvs_weight |
|---|---|---|---|---|
| KVS-2026-000001 | Ergodicity_Breaking | POSITIVE | RUNTIME_HARD | +1.0 |
| KVS-2026-000002 | Absorbing_Barrier | POSITIVE | RUNTIME_HARD | +1.0 |
| KVS-2026-000003 | Kelly_Criterion_Sizing | POSITIVE | RUNTIME_HARD | +0.9 |
| KVS-2026-000004 | Barbell_Strategy | POSITIVE | RUNTIME_HARD | +0.95 |
| KVS-2026-000005 | Asymmetric_Leverage | POSITIVE | RUNTIME_SOFT | +0.85 |
| KVS-2026-000006 | Non_linear_Compounding | POSITIVE | RUNTIME_SOFT | +0.8 |
| KVS-2026-000007 | Tail_Node_Capital_Concentration | POSITIVE | RUNTIME_SOFT | +0.75 |
| KVS-2026-000008 | Multiplicative_Yield | POSITIVE | RUNTIME_SOFT | +0.85 |
| KVS-2026-000009 | Power_Law_Primacy | POSITIVE | RUNTIME_HARD | +1.0 |
| KVS-2026-000010 | Volatility_Tax | POSITIVE | RUNTIME_SOFT | +0.8 |
| KVS-2026-000011 | Medium_Risk_Medium_Reward_Trap | NEGATIVE | RUNTIME_HARD | -1.0 |
| KVS-2026-000012 | Additive_Intuition_Trap | NEGATIVE | RUNTIME_SOFT | -0.9 |
| KVS-2026-000013 | Average_Allocation_Trap | NEGATIVE | RUNTIME_SOFT | -0.85 |
| KVS-2026-000014 | Sunk_Cost_Attachment | NEGATIVE | RUNTIME_SOFT | -0.8 |
| KVS-2026-000015 | Gaussian_Extrapolation_Trap | NEGATIVE | RUNTIME_SOFT | -0.75 |
| KVS-2026-000016 | Local_Optima_Comfort | NEGATIVE | RUNTIME_SOFT | -0.9 |

*POWERLAW.md fully assembled. 10 Positive Multipliers + 6 Negative Taboos = 16 KVS Atoms.*
