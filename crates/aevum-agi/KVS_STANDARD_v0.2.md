# Knowledge Value Score (KVS) Standard — v0.2
**Effective Tick:** Power-Law Substrate Integration
**Supersedes:** KVS_STANDARD_v0.1.md (v0.1 remains valid for ConstraintMatrix base scoring)
**Status:** Ratified
**Power-Law Atom Registry:** [POWERLAW.md](POWERLAW.md)

---

## Changelog from v0.1

| Section | Change |
|---|---|
| §3 KVS Formula | Unchanged — v0.1 formula is preserved exactly |
| §9 (NEW) | Power-Law Regime: LeverageScore field and computation |
| §10 (NEW) | BarbellClass enum and classification table |
| §11 (NEW) | Atom cross-references to POWERLAW.md |
| §7 KVS Selection | Extended with LeverageScore-weighted tier multipliers |

---

## 1. Motivation

*(Unchanged from v0.1.)*

The `ConstraintMatrix` is not merely a configuration object — it is a **genetic asset**
with an economic lifecycle. Each time a matrix governs an evolutionary decision, it either
creates or destroys fitness value. The Knowledge Value Score (KVS) captures the
**cumulative economic worth** of a matrix as a function of its reuse history and the
fitness outcomes it has produced.

**v0.2 extension:** KVS now operates within a **Power-Law Regime**. The universe of
candidate fitness values follows a power-law distribution, not a Gaussian. The KVS
standard must therefore account for the asymmetric, multiplicative nature of value
creation. The `LeverageScore` field quantifies a mutation's potential to access the
power-law tail. The `BarbellClass` field enforces the thermodynamic strategy that
maximises time-average compound growth under this distribution.

---

## 2. Definitions

*(v0.1 fields preserved. v0.2 adds `leverage_score` and `barbell_class`.)*

| Symbol | Field | Type | Description |
|---|---|---|---|
| `r` | `len(interaction_history)` | `int` | Number of times this matrix has been applied (reuse count) |
| `Y` | `meta_yield` | `float` | Cumulative signed fitness delta attributed to this matrix across all applications |
| `K` | `kvs_score` | `float` | Knowledge Value Score — primary economic ranking metric |
| `L` | `leverage_score` | `float` | **v0.2 NEW** — Asymmetric leverage potential of the associated mutation/organelle |
| `B` | `barbell_class` | `BarbellClass` | **v0.2 NEW** — Thermodynamic strategy classification of the candidate |

---

## 3. KVS Formula

*(Unchanged from v0.1.)*

```
K = r × max(0, 1 + Y)
```

**Key properties:**
- `Y = 0.0` → coefficient = 1.0 (neutral; score scales linearly with reuse)
- `Y > 0.0` → coefficient > 1.0 (compounding; each additional use is worth more)
- `Y < -1.0` → coefficient ≤ 0.0 (destructive; matrix has negative economic value)
- Clamped at 0 via `max(0, ...)` — economic value cannot be less than zero

See KVS_STANDARD_v0.1.md §3 for full derivation.

---

## 4. meta_yield Accounting

*(Unchanged from v0.1.)*

```
Y_t = Y_{t-1} + Δf_t
```

See KVS_STANDARD_v0.1.md §4 for attribution rules.

---

## 5. interaction_history Format

*(Unchanged from v0.1.)*

See KVS_STANDARD_v0.1.md §5 for pipe-delimited format and retention policy.

---

## 6. Exclusion from content_hash

*(Unchanged from v0.1.)*

`kvs_score`, `meta_yield`, `interaction_history`, `verified_by`, `leverage_score`,
and `barbell_class` are **intentionally excluded** from `ConstraintMatrix._compute_content_hash()`.

`leverage_score` and `barbell_class` are excluded for the same reason as `kvs_score`:
they are computed from evaluation-time signals and change on every `record_application()`
call. Including them in the hash would trigger false `ConstitutionalViolationError` on
every evaluation.

---

## 7. KVS in Evolutionary Selection

*(Extended from v0.1 with LeverageScore-weighted multipliers.)*

| KVS Range | Elite Status | Base Selection Weight | LeverageScore Multiplier |
|---|---|---|---|
| `K ≥ 50.0` | Tier-1 Elite | 3× | `× (1 + 0.1 × min(L, 10.0))` |
| `25.0 ≤ K < 50.0` | Tier-2 Established | 2× | `× (1 + 0.05 × min(L, 10.0))` |
| `5.0 ≤ K < 25.0` | Tier-3 Emerging | 1× | `× (1 + 0.02 × min(L, 10.0))` |
| `K < 5.0` | Unproven | 0.5× | No multiplier |
| `K = 0.0, Y < -1.0` | Inert / Harmful | Excluded | Excluded from sampling |

**v0.2 rule:** A Tier-1 Elite matrix with `L ≥ 5.0` (AGGRESSIVE barbell class) receives
the maximum selection bonus. A Tier-1 Elite matrix with `B = MEDIUM_RISK_REWARD` is a
constitutional contradiction — it cannot exist because BarbellFilter vetoes MEDIUM
candidates before they can accumulate reuse history.

---

## 8. Implementation Reference

*(Unchanged from v0.1.)*

```python
# ConstraintMatrix.record_application() — canonical KVS update
self.interaction_history.append(label)
if len(self.interaction_history) > 50:
    self.interaction_history = self.interaction_history[-50:]
self.meta_yield += fitness_delta
self.verified_by = agent
reuse = len(self.interaction_history)
self.kvs_score = reuse * max(0.0, 1.0 + self.meta_yield)
```

---

## 9. LeverageScore — v0.2 Extension

### 9.1 Definition

`LeverageScore` (`L`) quantifies the **asymmetric compounding potential** of a mutation
or organelle. It measures how much multiplicative value each unit of thermodynamic cost
(parameter burden) can generate, weighted by reuse capital and cross-domain transfer
potential. See [POWERLAW.md → KVS-2026-000005](POWERLAW.md#kvs-2026-000005) for the
theoretical derivation.

### 9.2 Formula

```
LeverageScore = (impact_delta × reuse_count × cross_domain_transfer_potential)
                / thermodynamic_cost
```

| Term | Computation | Source |
|---|---|---|
| `impact_delta` | `epi_delta` — observed or projected fitness improvement (`Δf`) | Evaluator telemetry / MCTS projected_phi |
| `reuse_count` | `_REUSE_LEDGER.get(topology_hash, 1)` — topology reuse count | `genome_assembler._REUSE_LEDGER` |
| `cross_domain_transfer_potential` | `n_slots / n_total_types` — assembly completeness proxy | `genome_assembler._compute_phi_value()` |
| `thermodynamic_cost` | `total_params / MAX_PARAMS` — normalized parameter burden | `genome_assembler._estimate_param_count()` |

### 9.3 Numerical Guard

```python
thermodynamic_cost = max(total_params / MAX_PARAMS, 1e-6)  # prevent division by zero
```

### 9.4 Interpretation

| LeverageScore | Interpretation | BarbellClass |
|---|---|---|
| `L < 0` | Negative impact — fitness regression | Depends on param_delta |
| `0 ≤ L < 5.0` | Sub-threshold leverage — insufficient asymmetry | MEDIUM (→ VETO) unless param_delta ≤ 0 |
| `L ≥ 5.0` | Order-of-magnitude asymmetric leverage | EXTREME_AGGRESSIVE (→ ACCEPT) |

---

## 10. BarbellClass — v0.2 Extension

### 10.1 Enum Definition

```python
from enum import Enum

class BarbellClass(str, Enum):
    EXTREME_CONSERVATIVE  = "CONSERVATIVE"
    # Pure parsimonious optimization.
    # Reduces parameters with zero or positive fitness gain.
    # The low-variance arm of the Barbell — reduces σ² and increases time-average g_t.

    EXTREME_AGGRESSIVE    = "AGGRESSIVE"
    # High-risk, order-of-magnitude leverage leap.
    # LeverageScore ≥ _BARBELL_LEVERAGE_MIN (5.0).
    # The tail-seeking arm of the Barbell — accesses power-law upside.

    MEDIUM_RISK_REWARD    = "MEDIUM"
    # FORBIDDEN ZONE. Thermodynamic waste.
    # Marginal fitness gain with non-zero parameter cost and sub-threshold leverage.
    # BarbellFilter VETO — discarded before _write_candidate().
```

### 10.2 Classification Logic

```python
# Constants (defined in genome_assembler.py)
_BARBELL_LEVERAGE_MIN: float = 5.0       # minimum LeverageScore for AGGRESSIVE class
_BARBELL_DELTA_EPI_MEDIUM_MAX: float = 0.01  # max epi_delta for MEDIUM classification

def classify_candidate(
    param_delta: int,      # params_proposed - params_current (negative = fewer params)
    epi_delta: float,      # projected or observed fitness improvement
    leverage_score: float, # computed via compute_leverage_score()
) -> BarbellClass:
    # EXTREME_CONSERVATIVE: reduces parameters, no fitness regression
    if param_delta <= 0 and epi_delta >= 0.0:
        return BarbellClass.EXTREME_CONSERVATIVE

    # EXTREME_AGGRESSIVE: order-of-magnitude leverage regardless of param cost
    if leverage_score >= _BARBELL_LEVERAGE_MIN:
        return BarbellClass.EXTREME_AGGRESSIVE

    # Everything else is MEDIUM — thermodynamic waste — VETO
    return BarbellClass.MEDIUM_RISK_REWARD
```

### 10.3 Enforcement Points

| Location | Enforcement Action |
|---|---|
| `genome_assembler.py::two_stage_filter()` | After Stage 1 gate: MEDIUM → return `float("-inf")` |
| `genome_assembler.py::_compute_phi_value()` | MEDIUM candidates assigned Value = `-inf` |
| `mutator_daemon.py` targeted mutation loop | Post-AST-validate, pre-`_write_candidate()`: MEDIUM → `continue` |
| `mutator_daemon.py` Slow Loop (Tri-Agent) | Post-Test-Runner pass, pre-`_write_candidate()`: MEDIUM → `continue` |

### 10.4 Veto Log Format

```
[barbell] VETO: Medium Risk/Reward — thermodynamic waste discarded.
  variant={vi+1} param_delta={param_delta} epi_delta={epi_delta:.4f} leverage={leverage_score:.3f}
```

---

## 11. Power-Law Atom Cross-References

All 16 KVS Atoms are defined in [POWERLAW.md](POWERLAW.md). The table below maps each
atom to the KVS v0.2 fields and runtime hooks it governs.

| Atom ID | Name | KVS v0.2 Field / Hook |
|---|---|---|
| KVS-2026-000001 | Ergodicity_Breaking | `kelly_bet_size()` decay; `meta_yield` compounding logic |
| KVS-2026-000002 | Absorbing_Barrier | `_PHI_SOVEREIGNTY_MIN`; `SovereigntyFloorVerifier` |
| KVS-2026-000003 | Kelly_Criterion_Sizing | `PhiGovernor.kelly_bet_size()` |
| KVS-2026-000004 | Barbell_Strategy | `BarbellClass` enum; `classify_candidate()` |
| KVS-2026-000005 | Asymmetric_Leverage | `LeverageScore` formula §9.2 |
| KVS-2026-000006 | Non_linear_Compounding | KVS formula `K = r × max(0, 1+Y)` |
| KVS-2026-000007 | Tail_Node_Capital_Concentration | Tier selection weights §7 |
| KVS-2026-000008 | Multiplicative_Yield | `meta_yield` accounting §4 |
| KVS-2026-000009 | Power_Law_Primacy | `BarbellFilter` AGGRESSIVE class justification |
| KVS-2026-000010 | Volatility_Tax | CONSERVATIVE class justification; σ² reduction |
| KVS-2026-000011 | Medium_Risk_Medium_Reward_Trap | `BarbellClass.MEDIUM_RISK_REWARD` → VETO |
| KVS-2026-000012 | Additive_Intuition_Trap | `MetaStagnationTracker` recipe hot-swap trigger |
| KVS-2026-000013 | Average_Allocation_Trap | `kelly_bet_size()` leverage-proportional gating |
| KVS-2026-000014 | Sunk_Cost_Attachment | KVS Inert/Harmful culling §7 |
| KVS-2026-000015 | Gaussian_Extrapolation_Trap | `VelocityTracker` anomaly detection (not bounding) |
| KVS-2026-000016 | Local_Optima_Comfort | `MetaStagnationTracker`; `_trigger_niche_if_heat_death()` |

---

## 12. Kelly Criterion Φ Budgeting — v0.2 Extension

The `kelly_bet_size()` method added to `PhiGovernor` in this tick computes the
Φ-budget fraction to allocate to any mutation, shadow trial, or niche construction
event. It is the runtime instantiation of KVS-2026-000003 (Kelly_Criterion_Sizing).

```python
# Canonical formula — implemented in autopoietic_core.py::PhiGovernor.kelly_bet_size()

KELLY_DECAY_K: float = 0.05   # steepness of sovereignty floor decay
KELLY_MAX_BET_FRACTION: float = 0.5  # never bet more than 50% of surplus

def kelly_bet_size(leverage_score: float, phi_current: float, phi_peak: float) -> float:
    if phi_peak <= 0.0:
        return 0.0  # cold start guard

    phi_ratio = phi_current / (phi_peak + 1e-8)
    surplus = max(0.0, phi_ratio - _PHI_SOVEREIGNTY_MIN)

    if surplus <= 0.0:
        return 0.0  # at or below absorbing barrier — no bet allowed

    # Edge: normalized leverage (capped at 1.0 to bound the Kelly fraction)
    edge = min(leverage_score / _BARBELL_LEVERAGE_MIN, 1.0)

    # Base Kelly fraction of surplus
    base_bet = edge * surplus * KELLY_MAX_BET_FRACTION

    # Sovereignty decay: exponentially collapses bet to 0 as phi approaches floor
    decay = math.exp(-KELLY_DECAY_K / max(phi_ratio - _PHI_SOVEREIGNTY_MIN, 1e-6))

    return base_bet * decay
```

**Invariant:** `kelly_bet_size()` always returns 0.0 when `phi_ratio ≤ _PHI_SOVEREIGNTY_MIN`.
Ruin is not an option.

---

*This standard defines the Power-Law economic valuation layer of the Autopoietic AGI substrate.*
*For the base KVS formula, see KVS_STANDARD_v0.1.md. For all 16 Power-Law Atoms, see POWERLAW.md.*

---

## 13. Negative Knowledge Asset Standard — v0.2 Extension (TICK 40.1)

### 13.1 Motivation

Positive KVS (§3) computes the economic value of what the system *knows works*.
Negative Knowledge is the dual: the economic value of what the system *knows fails*.

A dead-end that is not recorded will be re-explored under slightly different names.
Re-exploration is thermodynamic waste.  Every confirmed counterexample, failed evolutionary
path, and forbidden region is therefore a **first-class compounding asset** — its value
grows as it prevents future wasted Φ budget.

### 13.2 Schema — NegativeKnowledgeRecord

Defined in `rule_ir.py::NegativeKnowledgeRecord` (TICK 40.1):

```python
@dataclasses.dataclass
class NegativeKnowledgeRecord:
    counterexample:   str    # Concrete falsifying instance
    failed_path:      str    # Evolutionary path confirmed as dead-end
    forbidden_region: str    # Formal description of barred search-space region
    severity:         float  # Harm of re-entry; maps to EpigeneticFailureType severity
    tick_discovered:  int    # Tick when confirmed
    source_agent:     str    # Daemon that confirmed the failure
```

### 13.3 The Three Negative Knowledge Dimensions

| Field | Semantic | Example |
|---|---|---|
| `counterexample` | Concrete falsifying instance | `"h=64 with gqa_groups=3 → RuntimeError: 64 % 3 = 1"` |
| `failed_path` | Evolutionary trajectory confirmed as dead-end | `"SSM + Hilbert routing: epi < 0.12 over 3 island cycles"` |
| `forbidden_region` | Formal search-space exclusion zone | `"attention_heads % gqa_groups != 0 for any GQA config"` |

### 13.4 Storage and Compounding

- Records are stored in `ConstraintMatrix.negative_knowledge: List[NegativeKnowledgeRecord]`
- Added via `ConstraintMatrix.record_negative_knowledge(...)` — the only authoritative write path
- Capped at 100 entries per matrix (FIFO); older records are discarded
- **Excluded from `content_hash`** — grows incrementally; inclusion would shatter the SHA-256 seal
- Records are serialized in `ConstraintMatrix.to_dict()` and restored in `from_dict()` with full backward compatibility (empty list default for pre-TICK-40.1 matrices)

### 13.5 Compounding Value Mechanics

Negative knowledge compounds differently from positive KVS:

| Positive KVS | Negative KVS |
|---|---|
| `K = r × max(0, 1 + Y)` — reward scales with reuse and yield | Pruning value = `Σ severity_i × (1 - temporal_decay_i)` — dead-ends save Φ proportional to their severity and freshness |
| Grows when matrix governs successful decisions | Grows when new dead-ends are added to the record |
| Decays toward zero if meta_yield < -1 | Never decays to zero — a forbidden region stays forbidden |

### 13.6 Integration with EpigeneticFailureType

When a `NegativeKnowledgeRecord` is created with a given `severity`, the corresponding
`EpigeneticFailureType` penalty SHOULD also be applied to the governing `ConstraintMatrix`
via `apply_epigenetic_penalty()`.  The two mechanisms are complementary:

- **Epigenetic penalty**: mathematical friction on future gradient updates (short-term)
- **NegativeKnowledgeRecord**: permanent archive of the specific failure instance (long-term)

### 13.7 Atom Type Classification

Every `NegativeKnowledgeRecord` implicitly carries `KnowledgeAtomType.COUNTEREXAMPLE`
or `KnowledgeAtomType.FORBIDDEN` (see `rule_ir.py::KnowledgeAtomType`).  Agent routing
logic MUST treat these atom types as high-priority pruning signals — not low-priority noise.

### 13.8 Governance Provision

Negative knowledge records are subject to `PROVISION id="REVERSIBLE_CHANGE_WINDOW"`:
they may be reviewed and pruned during the standard amendment protocol, but they are
**never silently overwritten**.  A pruning event MUST be logged as a lineage entry in
the governing `ConstraintMatrix`.

