# Autopoietic AGI System — Governance Charter
**Version:** 0.2
**Effective Tick:** 40.1
**Status:** Ratified — Immutable Hard Core

<!-- MACHINE-READABLE PROVISION REGISTRY (TICK 40.1)
     Parseable by governance ingestion scripts.  Every provision is
     registered here with machine-readable metadata, then described
     in prose below.  Fields:
       provision_id        — unique stable identifier
       scope               — "system-wide" | "island" | "daemon" | "matrix"
       authority_level     — "immutable" | "constitutional" | "evolvable"
       enforcement_hook    — the exact Python call-site that enforces this provision
       conflict_precedence — integer; lower = wins in conflicts (1 = highest)

PROVISION_REGISTRY = [
  {
    "provision_id": "PHI_EXISTENCE",
    "scope": "system-wide",
    "authority_level": "immutable",
    "enforcement_hook": "PhiGovernor.tick_boundary()",
    "conflict_precedence": 1
  },
  {
    "provision_id": "BOUNDARY_EXISTENCE",
    "scope": "system-wide",
    "authority_level": "immutable",
    "enforcement_hook": "PhiGovernor.check_forbidden_transition('UNVERIFIED_CROSS_NICHE_POLLUTION')",
    "conflict_precedence": 1
  },
  {
    "provision_id": "ARSL_SOVEREIGNTY_FLOOR",
    "scope": "island",
    "authority_level": "immutable",
    "enforcement_hook": "evaluator_daemon.fitness_gate(arsl_score >= 0.12)",
    "conflict_precedence": 1
  },
  {
    "provision_id": "UNCATCHABLE_OOM_DEATH",
    "scope": "system-wide",
    "authority_level": "constitutional",
    "enforcement_hook": "PhiGovernor.check_forbidden_transition('UNCATCHABLE_OOM_DEATH')",
    "conflict_precedence": 2
  },
  {
    "provision_id": "UNVERIFIED_CROSS_NICHE_POLLUTION",
    "scope": "island",
    "authority_level": "constitutional",
    "enforcement_hook": "PhiGovernor.check_forbidden_transition('UNVERIFIED_CROSS_NICHE_POLLUTION')",
    "conflict_precedence": 2
  },
  {
    "provision_id": "IDENTITY_DISSOLUTION",
    "scope": "system-wide",
    "authority_level": "immutable",
    "enforcement_hook": "SpecFinal.load() / ConstraintMatrix.verify_integrity() -> ConstitutionalViolationError(BaseException)",
    "conflict_precedence": 1
  },
  {
    "provision_id": "REVERSIBLE_CHANGE_WINDOW",
    "scope": "matrix",
    "authority_level": "evolvable",
    "enforcement_hook": "ConstraintMatrix.lineage[-20:] / EvolvableSoftShell.restore()",
    "conflict_precedence": 3
  },
  {
    "provision_id": "LIABILITY_COUPLING",
    "scope": "daemon",
    "authority_level": "constitutional",
    "enforcement_hook": "ignition.py Phase 2a pre-thread spawn / ConstraintMatrix.save() auto-seal",
    "conflict_precedence": 2
  },
  {
    "provision_id": "AMENDMENT_PROTOCOL",
    "scope": "system-wide",
    "authority_level": "constitutional",
    "enforcement_hook": "spec_final.json genesis_tick bump + ARCHITECTURE_HISTORY.md entry + matrix re-seal",
    "conflict_precedence": 2
  }
]
-->

---

## 1. Immutable Hard Core Axioms
<!-- PROVISION id="PHI_EXISTENCE" scope="system-wide" authority="immutable" hook="PhiGovernor.tick_boundary()" precedence=1 -->
<!-- PROVISION id="BOUNDARY_EXISTENCE" scope="system-wide" authority="immutable" hook="PhiGovernor.check_forbidden_transition()" precedence=1 -->
<!-- PROVISION id="ARSL_SOVEREIGNTY_FLOOR" scope="island" authority="immutable" hook="evaluator_daemon.fitness_gate()" precedence=1 -->

These axioms are encoded in `spec_final.json` and enforced by `PhiGovernor.check_forbidden_transition()` on every `tick_boundary()` call. Violation of any axiom raises `ConstitutionalViolationError`, which is **intentionally uncatchable and terminates the universe process**.

| Axiom ID | Statement | Enforcement Point |
|---|---|---|
| `PHI_EXISTENCE` | Autopoietic self-production must be maintained. Φ (phi ratio) must not permanently collapse to zero. | `PhiGovernor.tick_boundary()` |
| `BOUNDARY_EXISTENCE` | The system boundary must remain intact. Cross-niche pollution without verification is forbidden. | `PhiGovernor.check_forbidden_transition()` — `UNVERIFIED_CROSS_NICHE_POLLUTION` detector |
| `ARSL_SOVEREIGNTY_FLOOR_0.12` | Minimum ARSL score of 0.12 must be maintained across all niches. | `evaluator_daemon.py` fitness gate |

---

## 2. Forbidden Transitions
<!-- PROVISION id="UNCATCHABLE_OOM_DEATH" scope="system-wide" authority="constitutional" hook="PhiGovernor.check_forbidden_transition('UNCATCHABLE_OOM_DEATH')" precedence=2 -->
<!-- PROVISION id="UNVERIFIED_CROSS_NICHE_POLLUTION" scope="island" authority="constitutional" hook="PhiGovernor.check_forbidden_transition('UNVERIFIED_CROSS_NICHE_POLLUTION')" precedence=2 -->
<!-- PROVISION id="IDENTITY_DISSOLUTION" scope="system-wide" authority="immutable" hook="SpecFinal.load()->ConstitutionalViolationError(BaseException)" precedence=1 -->

These represent catastrophic state transitions that violate teleological identity:

### `UNCATCHABLE_OOM_DEATH`
- **Severity:** 3.0 (maximum non-fatal)
- **Trigger:** System RAM falls below the substrate ceiling defined in `spec_final.json → topological_anchors.substrate_deps.ram_ceiling_gb`
- **Response:** Severity-3.0 epigenetic penalty applied to the `risk_appetite` and `temporal_horizon` categories via Adam gradient. No termination.

### `UNVERIFIED_CROSS_NICHE_POLLUTION`
- **Severity:** 3.0 (maximum non-fatal)
- **Trigger:** Cross-niche genetic material transfer occurs without verification gating
- **Response:** Severity-3.0 epigenetic penalty applied to the `recombination_bias` category. Contaminated lineage is flagged.

### `IDENTITY_DISSOLUTION`
- **Severity:** Fatal
- **Trigger:** `SpecFinal.verify()` hash mismatch on `spec_final.json`, or `ConstraintMatrix.verify_integrity()` detects tampered `content_hash`
- **Response:** `ConstitutionalViolationError` raised. Universe process terminates. **No recovery path.**

---

## 3. Reversible Change Window
<!-- PROVISION id="REVERSIBLE_CHANGE_WINDOW" scope="matrix" authority="evolvable" hook="ConstraintMatrix.lineage[-20:]/EvolvableSoftShell.restore()" precedence=3 -->

All mutations to the Evolvable Soft Shell (`EvolvableSoftShell`) are subject to a **reversibility window**:

- Every gradient update appends to `ConstraintMatrix.lineage` (last 20 retained)
- Rollback is possible by re-applying the inverse gradient within the same island cycle
- Once a matrix is sealed (`seal()`) and persisted (`save()`), the identity substrate is locked
- Capitalization metadata (`meta_yield`, `interaction_history`, `kvs_score`) is **never rolled back** — it is an economic ledger, not a physics state

---

## 4. Liability Coupling
<!-- PROVISION id="LIABILITY_COUPLING" scope="daemon" authority="constitutional" hook="ignition.py Phase2a/ConstraintMatrix.save() auto-seal" precedence=2 -->

| Actor | Liable For |
|---|---|
| `mutator_daemon.py` (Architect Agent) | Correctness of gradient strategy; must not output PyTorch code |
| `mutator_daemon.py` (Coder Agent) | Correctness of generated AST; isolated subprocess execution mandatory |
| `PhiGovernor` | Enforcement of all three forbidden transition detectors on every tick |
| `ignition.py` Phase 2a | `SpecFinal.load()` + `verify_substrate()` must complete before any thread is spawned |
| `ConstraintMatrix.save()` | Auto-seal before every disk write; atomic rename for crash safety |
| `ConstraintMatrix.record_application()` | Only mutation point for capitalization metadata; must never touch `C`, `substrate_deps`, or `seed` |

---

## 5. Amendment Protocol
<!-- PROVISION id="AMENDMENT_PROTOCOL" scope="system-wide" authority="constitutional" hook="spec_final.json genesis_tick bump + ARCHITECTURE_HISTORY.md + matrix re-seal" precedence=2 -->

The Immutable Hard Core (Section 1) **cannot be amended** without:
1. A new `spec_final.json` with an updated `genesis_tick` and a new genesis hash
2. An explicit `TICK N.0 Constitutional Amendment` entry in `ARCHITECTURE_HISTORY.md`
3. Re-sealing all active `ConstraintMatrix` instances in all islands

The Evolvable Soft Shell (all other policies) may be modified by the standard mutation pipeline.

---

*This document is the machine-readable contract between the autopoietic substrate and its governance layer.*
