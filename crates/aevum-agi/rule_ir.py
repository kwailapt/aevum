#!/usr/bin/env python3
"""rule_ir.py — Rule-IR Constraint Matrix Compiler (TICK 20.1).

"Let the rules become mathematics. Let the mathematics evolve."

The End of Semantic Hallucination:
  Text-based prompts in mutation_recipe.py suffer from LLM semantic drift —
  each meta-evolution cycle rewrites English sentences that introduce
  progressive ambiguity, contradictions, and hallucinated constraints.

  The Rule-IR Compiler converts all recipe rules into a numerical Constraint
  Matrix: a rank-3 tensor C[category, constraint, weight] where every
  mutation policy is encoded as real-valued weights.

  Meta-evolution no longer outputs English.  It outputs gradient updates
  ΔC to the Constraint Matrix.  The evolution of rules becomes pure
  linear algebra, completely eradicating semantic hallucination.

══════════════════════════════════════════════════════════════════════════════
CONSTRAINT MATRIX ARCHITECTURE
══════════════════════════════════════════════════════════════════════════════

  C ∈ ℝ^{N_cat × N_con × 1}   (squeezable to ℝ^{N_cat × N_con})

  Categories (axis 0):
    0: TEMPERATURE_POLICY     — exploration vs exploitation bias
    1: STRUCTURAL_SCOPE       — how radical mutations may be
    2: PROBE_STRATEGY         — when/how aggressively to use sandbox
    3: RISK_APPETITE          — tolerance for parameter budget expansion
    4: ORGANELLE_PRIORITY     — which organelle types to focus on
    5: RECOMBINATION_BIAS     — cross-pollination vs de-novo invention
    6: PARSIMONY_PRESSURE     — MDL compression strength
    7: TEMPORAL_HORIZON       — short-term fitness vs long-term evolvability

  Constraints (axis 1):
    0: base_weight            — default strength [0, 1]
    1: momentum               — inertia from previous successful updates
    2: decay_rate             — how fast constraint decays without reinforcement
    3: min_bound              — hard lower clamp
    4: max_bound              — hard upper clamp
    5: gradient_accumulator   — running sum of applied gradients (Adam-like)
    6: squared_grad_acc       — running sum of squared gradients (RMSProp)
    7: update_count           — number of gradient updates applied

══════════════════════════════════════════════════════════════════════════════
CONSTRAINT → PROMPT PROJECTION
══════════════════════════════════════════════════════════════════════════════

  The Constraint Matrix does NOT replace the LLM prompt entirely.  Instead,
  it governs the *numerical hyperparameters* injected into the prompt:

    temperature    = C[0, 0] × temp_scale
    structural_rad = C[1, 0]   → controls how many classes may be changed
    probe_freq     = C[2, 0]   → probability of issuing <action> probes
    risk_budget    = C[3, 0]   → fraction of MAX_PARAMS the LLM may use
    ...

  The text scaffolding remains (constitutional directives, tool docs), but
  all *tunable strategy knobs* are governed by the matrix, not by English.

══════════════════════════════════════════════════════════════════════════════
META-EVOLUTION GRADIENT PROTOCOL
══════════════════════════════════════════════════════════════════════════════

  When META_EVOLUTION triggers (TICK 10.0), the LLM is NO LONGER asked to
  rewrite English text.  Instead:

    1. The current Constraint Matrix C is serialized to a compact JSON/tensor.
    2. A failure summary (stagnation metrics) is provided.
    3. The LLM outputs a <constraint_gradient> block containing ΔC:
       a JSON dict mapping (category, constraint) → gradient_value.
    4. The daemon applies: C ← C + α × ΔC  (with Adam momentum).
    5. The updated matrix is saved to island_meta/constraint_matrix.json.

  This eliminates:
    - Prompt corruption from progressive rewriting
    - Hallucinated rules that contradict the Constitution
    - Semantic drift across meta-evolution generations
    - The need for recipe API surface validation (it's just a tensor)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import dataclasses
from collections import deque
from pathlib import Path
import enum
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# CATEGORY & CONSTRAINT DEFINITIONS
# ═══════════════════════════════════════════════════════════════

CATEGORIES: List[str] = [
    "temperature_policy",      # 0
    "structural_scope",        # 1
    "probe_strategy",          # 2
    "risk_appetite",           # 3
    "organelle_priority",      # 4
    "recombination_bias",      # 5
    "parsimony_pressure",      # 6
    "temporal_horizon",        # 7
]

CONSTRAINTS: List[str] = [
    "base_weight",             # 0
    "momentum",                # 1
    "decay_rate",              # 2
    "min_bound",               # 3
    "max_bound",               # 4
    "gradient_accumulator",    # 5
    "squared_grad_acc",        # 6
    "update_count",            # 7
]

N_CAT: int = len(CATEGORIES)
N_CON: int = len(CONSTRAINTS)

# Category index lookup
CAT_IDX: Dict[str, int] = {name: i for i, name in enumerate(CATEGORIES)}
CON_IDX: Dict[str, int] = {name: i for i, name in enumerate(CONSTRAINTS)}


# ═══════════════════════════════════════════════════════════════
# EPIGENETIC FAILURE TYPES (TICK 25.0)
# ═══════════════════════════════════════════════════════════════

class EpigeneticFailureType(enum.Enum):
    """Failure modes translated to topological gradient penalties.

    TICK 25.0: Epigenetic Tensor Decay — abolishes text-based failure logs.
    Each failure type maps to specific category penalties applied directly
    to the Rank-2 Constraint Matrix via Adam optimizer.  History is
    amortized as mathematical friction, not natural language.
    """
    OOM = "oom"
    TIMEOUT = "timeout"
    SHAPE_MISMATCH = "shape_mismatch"
    NAN_DIVERGENCE = "nan_divergence"
    PERMISSION_VIOLATION = "permission_violation"
    DAG_REJECT = "dag_reject"


# Epigenetic penalty map: failure_type → {category: gradient_penalty}
# Negative gradients = mathematical friction blocking the Architect
# from repeating the same class of mistake.
_EPIGENETIC_PENALTY_MAP: Dict[EpigeneticFailureType, Dict[str, float]] = {
    EpigeneticFailureType.OOM: {
        "risk_appetite": -0.15,
        "structural_scope": -0.10,
        "parsimony_pressure": +0.10,
    },
    EpigeneticFailureType.TIMEOUT: {
        "structural_scope": -0.12,
        "temporal_horizon": -0.08,
        "risk_appetite": -0.05,
    },
    EpigeneticFailureType.SHAPE_MISMATCH: {
        "structural_scope": -0.20,
        "recombination_bias": -0.10,
        "temperature_policy": -0.05,
    },
    EpigeneticFailureType.NAN_DIVERGENCE: {
        "temperature_policy": -0.15,
        "risk_appetite": -0.10,
        "structural_scope": -0.08,
    },
    EpigeneticFailureType.PERMISSION_VIOLATION: {
        "risk_appetite": -0.20,
        "structural_scope": -0.15,
    },
    EpigeneticFailureType.DAG_REJECT: {
        "structural_scope": -0.12,
        "risk_appetite": -0.08,
        "parsimony_pressure": +0.05,
    },
}


# ═══════════════════════════════════════════════════════════════
# CONSTRAINT MATRIX (pure Python — no PyTorch dependency)
# ═══════════════════════════════════════════════════════════════

class ConstraintMatrix:
    """Rank-2 numerical constraint tensor governing mutation policy.

    All mutation strategy knobs are encoded as real-valued weights.
    Meta-evolution applies gradient updates instead of rewriting text.
    """

    def __init__(
        self,
        substrate_deps: Optional[Dict[str, Any]] = None,
        seed: int = 0,
    ) -> None:
        # C[cat][con] — initialize with sensible defaults
        self.C: List[List[float]] = [[0.0] * N_CON for _ in range(N_CAT)]
        self._init_defaults()
        self.version: int = 0
        self.lineage: List[str] = []  # history of gradient update descriptions

        # ── TICK 28.0 Topological Axioms ──────────────────────────────────
        # substrate_deps: hardware/framework profile captured at mint time.
        #   e.g. {"framework": "MLX", "vram_gb": 128, "platform": "darwin-arm64"}
        # seed: the exact PRNG/MCTS seed active when this constraint was discovered.
        # content_hash: SHA-256 of payload + substrate_deps + seed — tamper-evident
        #   seal.  Empty string = un-sealed (bootstrap); set via seal().
        self.substrate_deps: Dict[str, Any] = substrate_deps if substrate_deps is not None else {}
        self.seed: int = seed
        self.content_hash: str = ""  # populated by seal()

        # ── TICK 31.0 Capitalization Fields (Mutable Metadata) ───────────────
        # These fields track the economic/provenance history of this matrix.
        # They are INTENTIONALLY EXCLUDED from _compute_content_hash() because
        # they change on every record_application() call.  Including them would
        # shatter the SHA-256 seal on every application event, generating false
        # ConstitutionalViolationError violations across the autopoietic lineage.
        # Immutable Identity Substrate (hashed): C, substrate_deps, seed
        # Mutable Capitalization Metadata (NOT hashed): verified_by, meta_yield,
        #   interaction_history, kvs_score, scenario, negative_knowledge
        self.verified_by: str = ""          # agent/process that last verified this matrix
        self.meta_yield: float = 0.0        # cumulative fitness-delta attributable to this matrix
        self.interaction_history: List[str] = []  # log of application events (capped at 50)
        self.kvs_score: float = 0.0         # Knowledge Value Score — compounding asset value

        # ── TICK 40.1 Scenario Dimensions & Negative Knowledge ───────────────
        # scenario: Optional[ScenarioDimensions] — set at mint time or on first
        #   application.  Encodes how agents invoke this matrix and how fast it decays.
        #   Excluded from content_hash: decision_impact and temporal_dynamics are
        #   empirically updated; including them would shatter the SHA-256 seal.
        # negative_knowledge: List[NegativeKnowledgeRecord] — compounding dead-end
        #   archive.  Each record captures a concrete counterexample, failed path,
        #   and forbidden region discovered while this matrix was governing decisions.
        #   High-value asset: prevents thermodynamic waste from re-exploring the same
        #   terrain.  Excluded from content_hash (grows on every confirmed dead-end).
        self.scenario: "Optional[ScenarioDimensions]" = None
        self.negative_knowledge: "List[NegativeKnowledgeRecord]" = []

    def _init_defaults(self) -> None:
        """Set initial constraint weights calibrated to TICK 20.0 behavior."""
        # base_weight=0, momentum=1, decay=2, min=3, max=4, grad_acc=5, sq_grad=6, count=7

        # Temperature policy: balanced exploration
        self.C[0] = [0.50, 0.0, 0.01, 0.15, 1.20, 0.0, 0.0, 0.0]

        # Structural scope: moderate radicality
        self.C[1] = [0.40, 0.0, 0.02, 0.10, 0.90, 0.0, 0.0, 0.0]

        # Probe strategy: moderate probing frequency
        self.C[2] = [0.60, 0.0, 0.01, 0.20, 1.00, 0.0, 0.0, 0.0]

        # Risk appetite: conservative parameter budget usage
        self.C[3] = [0.35, 0.0, 0.02, 0.10, 0.90, 0.0, 0.0, 0.0]

        # Organelle priority: balanced across all types
        self.C[4] = [0.33, 0.0, 0.01, 0.10, 0.80, 0.0, 0.0, 0.0]

        # Recombination bias: moderate cross-pollination preference
        self.C[5] = [0.50, 0.0, 0.01, 0.10, 0.90, 0.0, 0.0, 0.0]

        # Parsimony pressure: moderate MDL compression
        self.C[6] = [0.55, 0.0, 0.01, 0.20, 0.95, 0.0, 0.0, 0.0]

        # Temporal horizon: balanced short/long term
        self.C[7] = [0.50, 0.0, 0.01, 0.10, 0.90, 0.0, 0.0, 0.0]

    # ── Topological Axiom Methods (TICK 28.0) ───────────────────────────────

    def _compute_content_hash(self) -> str:
        """Deterministically compute SHA-256 over C, substrate_deps, and seed.

        Uses json.dumps(sort_keys=True) to guarantee byte-identical serialization
        regardless of Python dict insertion order or platform.

        INCLUDED in hash payload (Immutable Identity Substrate):
            C               — the rank-2 constraint tensor
            substrate_deps  — hardware/framework profile at mint time
            seed            — PRNG/MCTS seed active at discovery

        EXCLUDED from hash payload (Mutable Capitalization Metadata — TICK 31.0):
            verified_by        — changes on every verification event
            meta_yield         — accumulates on every fitness application
            interaction_history — grows on every record_application() call
            kvs_score          — recomputed dynamically from meta_yield + history

        WARNING: Do NOT add mutable metadata to the payload dict below.  Doing
        so would cause verify_integrity() to raise ConstitutionalViolationError
        on every application event, breaking the entire autopoietic lineage.
        """
        payload = json.dumps(
            {
                "C": self.C,
                "substrate_deps": self.substrate_deps,
                "seed": self.seed,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def seal(self) -> str:
        """Compute and store the content_hash.  Call after any structural change.

        Returns the hash string for logging convenience.
        """
        self.content_hash = self._compute_content_hash()
        return self.content_hash

    def verify_integrity(self) -> None:
        """Assert content_hash matches the current payload.

        No-op when content_hash == "" (un-sealed / cold-start bootstrap) so
        that legacy matrices loaded from disk before TICK 28.0 are accepted
        and can be re-sealed without data loss.

        Raises:
            ConstitutionalViolationError: if the recalculated hash does not
                match self.content_hash.  This is intentionally fatal — a
                tampered or corrupted Constraint Matrix MUST NOT govern
                evolutionary decisions.
        """
        if not self.content_hash:
            # Un-sealed (old matrix or freshly constructed) — skip verification.
            return
        expected = self._compute_content_hash()
        if expected != self.content_hash:
            raise ConstitutionalViolationError(
                f"CONSTITUTIONAL VIOLATION: ConstraintMatrix integrity check failed.  "
                f"Stored hash: {self.content_hash[:16]}…  "
                f"Recomputed:  {expected[:16]}…  "
                f"The matrix has been tampered with or corrupted.  "
                f"The system will not proceed."
            )

    def record_application(
        self,
        agent: str,
        fitness_delta: float,
        event_tag: str = "",
    ) -> None:
        """Record one application event into the capitalization metadata.

        This is the ONLY correct way to mutate meta_yield, interaction_history,
        and kvs_score.  It DOES NOT alter the Immutable Identity Substrate
        (C, substrate_deps, seed) so content_hash remains valid across calls.

        Args:
            agent:         Identifier of the agent/process applying this matrix.
            fitness_delta: Signed fitness change attributed to this application.
            event_tag:     Optional short label (e.g. "tick_32", "probe_result").
        """
        import datetime as _dt

        timestamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        label = f"{timestamp}|{agent}|Δ{fitness_delta:+.4f}"
        if event_tag:
            label = f"{label}|{event_tag}"
        self.interaction_history.append(label)
        # Cap to last 50 entries to prevent unbounded growth
        if len(self.interaction_history) > 50:
            self.interaction_history = self.interaction_history[-50:]

        self.meta_yield += fitness_delta
        self.verified_by = agent

        # KVS = reuse count × (1 + meta_yield) — pure function of serializable state
        reuse = len(self.interaction_history)
        self.kvs_score = reuse * max(0.0, 1.0 + self.meta_yield)

    def record_negative_knowledge(
        self,
        counterexample: str,
        failed_path: str,
        forbidden_region: str,
        severity: float = 1.0,
        tick_discovered: int = 0,
        source_agent: str = "",
    ) -> "NegativeKnowledgeRecord":
        """TICK 40.1: Record a confirmed dead-end as a compounding negative-knowledge asset.

        The record is appended to self.negative_knowledge (capped at 100 entries
        to prevent unbounded growth).  It is intentionally excluded from
        content_hash — negative knowledge grows incrementally and must not
        shatter the SHA-256 seal.

        Returns the created NegativeKnowledgeRecord for logging convenience.
        """
        record = NegativeKnowledgeRecord(
            counterexample=counterexample,
            failed_path=failed_path,
            forbidden_region=forbidden_region,
            severity=severity,
            tick_discovered=tick_discovered,
            source_agent=source_agent,
        )
        self.negative_knowledge.append(record)
        # Cap to last 100 entries
        if len(self.negative_knowledge) > 100:
            self.negative_knowledge = self.negative_knowledge[-100:]
        return record

    def get(self, category: str, constraint: str = "base_weight") -> float:
        """Read a single constraint value."""
        ci = CAT_IDX.get(category, -1)
        cj = CON_IDX.get(constraint, 0)
        if ci < 0:
            return 0.0
        return self.C[ci][cj]

    def set(self, category: str, constraint: str, value: float) -> None:
        """Set a single constraint value (with clamping)."""
        ci = CAT_IDX.get(category, -1)
        cj = CON_IDX.get(constraint, -1)
        if ci < 0 or cj < 0:
            return
        lo = self.C[ci][CON_IDX["min_bound"]]
        hi = self.C[ci][CON_IDX["max_bound"]]
        if constraint == "base_weight":
            value = max(lo, min(hi, value))
        self.C[ci][cj] = value

    # ── Projection to mutation hyperparameters ───────────────────────────

    def project_temperature(self) -> float:
        """Project constraint matrix → LLM temperature."""
        base = self.C[0][0]  # temperature_policy.base_weight
        return max(0.15, min(1.20, base * 1.6 + 0.15))

    def project_structural_scope(self) -> float:
        """Project → max fraction of classes the LLM may modify (0..1)."""
        return max(0.10, min(1.0, self.C[1][0]))

    def project_probe_frequency(self) -> float:
        """Project → probability [0,1] that the LLM should issue probes."""
        return max(0.0, min(1.0, self.C[2][0]))

    def project_risk_budget(self) -> float:
        """Project → fraction of MAX_PARAMS the LLM may target."""
        return max(0.10, min(0.95, self.C[3][0]))

    def project_parsimony_strength(self) -> float:
        """Project → MDL compression pressure coefficient."""
        return max(0.0, min(1.0, self.C[6][0]))

    def project_temporal_bias(self) -> float:
        """Project → 0 = short-term exploitation, 1 = long-term exploration."""
        return max(0.0, min(1.0, self.C[7][0]))

    def project_all(self) -> Dict[str, float]:
        """Project all mutation hyperparameters from the constraint matrix."""
        return {
            "temperature": round(self.project_temperature(), 4),
            "structural_scope": round(self.project_structural_scope(), 4),
            "probe_frequency": round(self.project_probe_frequency(), 4),
            "risk_budget": round(self.project_risk_budget(), 4),
            "parsimony_strength": round(self.project_parsimony_strength(), 4),
            "temporal_bias": round(self.project_temporal_bias(), 4),
            "organelle_focus": round(self.C[4][0], 4),
            "recombination_bias": round(self.C[5][0], 4),
        }

    # ── Gradient update (Adam-style optimizer) ───────────────────────────

    def apply_gradient(
        self,
        gradient: Dict[str, float],
        learning_rate: float = 0.05,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ) -> Dict[str, float]:
        """Apply a gradient update to the constraint matrix.

        gradient: dict mapping category_name → gradient_value for base_weight.
                  e.g., {"temperature_policy": +0.1, "parsimony_pressure": -0.05}

        Uses Adam optimizer for stable convergence with momentum tracking.

        Returns the actual deltas applied (after clamping).
        """
        applied: Dict[str, float] = {}

        for cat_name, grad_val in gradient.items():
            ci = CAT_IDX.get(cat_name, -1)
            if ci < 0:
                continue

            # Adam update on base_weight (constraint index 0)
            bw_idx = CON_IDX["base_weight"]
            m_idx = CON_IDX["momentum"]           # first moment
            v_idx = CON_IDX["squared_grad_acc"]    # second moment
            t_idx = CON_IDX["update_count"]

            old_val = self.C[ci][bw_idx]
            t = self.C[ci][t_idx] + 1.0

            # Update biased first/second moments
            m = beta1 * self.C[ci][m_idx] + (1.0 - beta1) * grad_val
            v = beta2 * self.C[ci][v_idx] + (1.0 - beta2) * (grad_val ** 2)

            # Bias correction
            m_hat = m / (1.0 - beta1 ** t)
            v_hat = v / (1.0 - beta2 ** t)

            # Update
            delta = learning_rate * m_hat / (math.sqrt(v_hat) + epsilon)
            new_val = old_val + delta

            # Clamp to bounds
            lo = self.C[ci][CON_IDX["min_bound"]]
            hi = self.C[ci][CON_IDX["max_bound"]]
            new_val = max(lo, min(hi, new_val))
            actual_delta = new_val - old_val

            # Store
            self.C[ci][bw_idx] = new_val
            self.C[ci][m_idx] = m
            self.C[ci][v_idx] = v
            self.C[ci][t_idx] = t
            self.C[ci][CON_IDX["gradient_accumulator"]] += abs(grad_val)

            applied[cat_name] = round(actual_delta, 6)

        self.version += 1
        return applied

    def apply_decay(self) -> None:
        """Apply per-category decay to base_weight (pulls toward center).

        Prevents runaway constraint drift over many meta-evolution cycles.

        TICK 27.0: After decay, the IdentityMembrane snaps any eroded
        invariant category back to its floor — decay cannot dissolve
        the indestructible identity core.
        """
        bw = CON_IDX["base_weight"]
        dr = CON_IDX["decay_rate"]
        for ci in range(N_CAT):
            rate = self.C[ci][dr]
            if rate > 0:
                center = 0.5 * (self.C[ci][CON_IDX["min_bound"]] +
                                self.C[ci][CON_IDX["max_bound"]])
                self.C[ci][bw] += rate * (center - self.C[ci][bw])
        # TICK 27.0: Hard clip invariant categories — identity cannot decay.
        _GLOBAL_IDENTITY_MEMBRANE.enforce(self)

    def apply_epigenetic_penalty(
        self,
        failure_type: EpigeneticFailureType,
        severity: float = 1.0,
        learning_rate: float = 0.08,
    ) -> Dict[str, float]:
        """TICK 25.0: Epigenetic Tensor Decay — failure as mathematical friction.

        When the Test-Runner or DAG Oracle rejects a variant, this method
        translates the failure into a topological penalty applied directly
        to the Rank-2 Constraint Matrix.  NO text traceback is generated.
        NO natural language is sent to the Architect's next prompt.

        The penalty is:
          gradient = _EPIGENETIC_PENALTY_MAP[failure_type] × severity
        applied via the existing Adam optimizer (apply_gradient).

        This forms an 'epigenetic memory' — mathematical friction that
        blocks the Architect from repeating the same class of mistakes
        without any semantic hallucination risk.

        Args:
            failure_type: The category of failure (OOM, timeout, etc.)
            severity: Multiplier ∈ [0.1, 3.0] scaling the penalty.
                      Higher = stronger friction (repeated failures).
            learning_rate: Adam lr for this penalty (default: 0.08,
                          slightly higher than normal meta-evo lr=0.05
                          to ensure penalties bite quickly).

        Returns:
            Dict of actual deltas applied to each category.
        """
        severity = max(0.1, min(3.0, severity))

        base_penalties = _EPIGENETIC_PENALTY_MAP.get(failure_type, {})
        if not base_penalties:
            return {}

        # Scale penalties by severity
        gradient: Dict[str, float] = {
            cat: penalty * severity
            for cat, penalty in base_penalties.items()
        }

        # Apply through the existing Adam optimizer pipeline
        applied = self.apply_gradient(gradient, learning_rate=learning_rate)

        # TICK 27.0: Identity Membrane enforcement — snap back any invariant
        # category that the gradient tried to erode below its floor.
        # Hard mathematical clip: the optimizer cannot dissolve the identity core.
        identity_clipped = _GLOBAL_IDENTITY_MEMBRANE.enforce(self)

        # Record in lineage as structured data (NOT natural language)
        self.lineage.append(
            f"epigenetic:{failure_type.value}:sev={severity:.2f}:applied={applied}"
            + (f":identity_clipped={identity_clipped}" if identity_clipped else "")
        )

        return applied

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        d: Dict[str, Any] = {
            "version": self.version,
            "categories": CATEGORIES,
            "constraints": CONSTRAINTS,
            "matrix": self.C,
            "lineage": self.lineage[-20:],  # last 20 updates
            "projected": self.project_all(),
            # ── TICK 28.0 Topological Axioms ──
            "substrate_deps": self.substrate_deps,
            "seed": self.seed,
            "content_hash": self.content_hash,
            # ── TICK 31.0 Capitalization Fields ──
            "verified_by": self.verified_by,
            "meta_yield": self.meta_yield,
            "interaction_history": self.interaction_history[-50:],  # cap at 50
            "kvs_score": self.kvs_score,
            # ── TICK 40.1 Scenario Dimensions & Negative Knowledge ──
            "scenario": self.scenario.to_dict() if self.scenario is not None else None,
            "negative_knowledge": [nk.to_dict() for nk in self.negative_knowledge],
        }
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConstraintMatrix":
        """Deserialize from JSON-compatible dict.

        Handles legacy matrices (pre-TICK-28.0) that lack substrate_deps/seed/
        content_hash by treating them as un-sealed (content_hash == "").
        Any sealed matrix whose hash does not match raises ConstitutionalViolationError.
        Handles matrices pre-TICK-31.0 that lack capitalization fields (safe defaults).
        """
        substrate_deps = data.get("substrate_deps", {})
        seed = int(data.get("seed", 0))
        cm = cls(substrate_deps=substrate_deps, seed=seed)
        cm.version = data.get("version", 0)
        cm.lineage = data.get("lineage", [])
        matrix = data.get("matrix", [])
        for ci in range(min(N_CAT, len(matrix))):
            for cj in range(min(N_CON, len(matrix[ci]))):
                cm.C[ci][cj] = float(matrix[ci][cj])
        # Restore stored hash (empty string = un-sealed, verify_integrity is a no-op).
        cm.content_hash = data.get("content_hash", "")
        # ── TICK 31.0 Capitalization Fields — safe defaults for backward compat ──
        cm.verified_by = data.get("verified_by", "")
        cm.meta_yield = float(data.get("meta_yield", 0.0))
        raw_history = data.get("interaction_history", [])
        cm.interaction_history = list(raw_history)[-50:]  # cap at 50 on load
        cm.kvs_score = float(data.get("kvs_score", 0.0))
        # ── TICK 40.1 Scenario Dimensions & Negative Knowledge — safe defaults ──
        raw_scenario = data.get("scenario")
        cm.scenario = (
            ScenarioDimensions.from_dict(raw_scenario)
            if isinstance(raw_scenario, dict) else None
        )
        raw_nk = data.get("negative_knowledge", [])
        cm.negative_knowledge = [
            NegativeKnowledgeRecord.from_dict(r)
            for r in raw_nk
            if isinstance(r, dict)
        ]
        # Integrity check: raises ConstitutionalViolationError on tamper.
        cm.verify_integrity()
        return cm

    def save(self, path: str) -> None:
        """Atomically save constraint matrix to disk.

        Auto-seals (computes content_hash) before writing so every file on
        disk is tamper-evident from the moment it is created.
        """
        self.seal()  # Mod-8: ensure hash is fresh before persisting
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            os.rename(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    @classmethod
    def load(cls, path: str) -> "ConstraintMatrix":
        """Load constraint matrix from disk, or return fresh defaults.

        ConstitutionalViolationError is intentionally NOT caught here — a
        tampered matrix is a fatal condition and must propagate to the caller.
        Only I/O and JSON parse errors produce the safe default.
        """
        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)  # verify_integrity() called inside from_dict
        except (OSError, json.JSONDecodeError, KeyError):
            return cls()

    def format_markdown(self) -> str:
        """Format constraint matrix as compact Markdown for LLM context."""
        proj = self.project_all()
        lines = [
            f"--- RULE-IR CONSTRAINT MATRIX v{self.version} ---",
        ]
        for cat in CATEGORIES:
            ci = CAT_IDX[cat]
            bw = self.C[ci][0]
            m = self.C[ci][1]
            lines.append(f"  {cat}: w={bw:.3f} momentum={m:.3f}")
        lines.append("Projected hyperparams:")
        for k, v in proj.items():
            lines.append(f"  {k} = {v}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# RECIPE COMPILATION (Text Rules → Constraint Matrix)
# ═══════════════════════════════════════════════════════════════

def compile_recipe_to_matrix(recipe: Any) -> ConstraintMatrix:
    """Compile a text-based mutation_recipe module into a ConstraintMatrix.

    Reads the recipe's hyperparameters and maps them to matrix weights.
    This is the one-way bridge from TICK 10.0 text recipes to TICK 20.1
    numerical constraints.
    """
    cm = ConstraintMatrix()

    # Temperature policy: map LLM_TEMPERATURE → base_weight
    temp = getattr(recipe, "LLM_TEMPERATURE", 0.6)
    cm.set("temperature_policy", "base_weight", (temp - 0.15) / 1.05)

    # Structural scope: map BATCH_SIZE → radicality proxy
    batch = getattr(recipe, "BATCH_SIZE", 3)
    cm.set("structural_scope", "base_weight", min(1.0, batch / 5.0))

    # Parsimony: map EXPLOITATION_EVO_FLOOR → parsimony pressure
    evo_floor = getattr(recipe, "EXPLOITATION_EVO_FLOOR", 0.15)
    cm.set("parsimony_pressure", "base_weight", 1.0 - evo_floor)

    # Risk appetite: moderate by default
    cm.set("risk_appetite", "base_weight", 0.35)

    cm.lineage.append(f"compiled from recipe v{getattr(recipe, 'RECIPE_VERSION', 'unknown')}")
    return cm


# ═══════════════════════════════════════════════════════════════
# META-EVOLUTION GRADIENT EXTRACTION
# ═══════════════════════════════════════════════════════════════

import re

_CONSTRAINT_GRADIENT_RE = re.compile(
    r"<constraint_gradient>(.*?)</constraint_gradient>",
    re.DOTALL,
)


def extract_constraint_gradient(llm_response: str) -> Optional[Dict[str, float]]:
    """Extract <constraint_gradient> block from LLM meta-evolution response.

    Expected format inside tags:
    {
        "temperature_policy": +0.05,
        "parsimony_pressure": -0.03,
        "structural_scope": +0.10
    }

    Returns gradient dict, or None if not found/invalid.
    """
    match = _CONSTRAINT_GRADIENT_RE.search(llm_response)
    if not match:
        return None

    raw = match.group(1).strip()
    try:
        gradient = json.loads(raw)
        if not isinstance(gradient, dict):
            return None
        # Validate: all keys must be valid categories, values must be numbers
        validated: Dict[str, float] = {}
        for k, v in gradient.items():
            if k in CAT_IDX and isinstance(v, (int, float)):
                validated[k] = float(v)
        return validated if validated else None
    except (json.JSONDecodeError, ValueError):
        return None


def build_constraint_meta_prompt(
    cm: ConstraintMatrix,
    failure_summary: str,
    perf_history: str = "",
) -> Tuple[str, str]:
    """Build the meta-evolution prompt for constraint gradient generation.

    Instead of asking the LLM to rewrite English text, we ask it to
    output numerical gradient updates to the Constraint Matrix.

    Returns (system_prompt, user_prompt).
    """
    system_prompt = (
        "You are a Meta-Cognitive Constraint Optimizer.\n\n"
        "You govern the evolutionary search strategy through a NUMERICAL "
        "Constraint Matrix — NOT through English text rules.\n\n"
        "The matrix has 8 categories, each with a base_weight ∈ [min, max]:\n"
        "  0. temperature_policy: exploration heat (higher = more random)\n"
        "  1. structural_scope: mutation radicality (higher = more classes changed)\n"
        "  2. probe_strategy: sandbox usage frequency\n"
        "  3. risk_appetite: parameter budget usage fraction\n"
        "  4. organelle_priority: focus on specific organelle types\n"
        "  5. recombination_bias: cross-pollination vs de-novo\n"
        "  6. parsimony_pressure: MDL compression strength\n"
        "  7. temporal_horizon: short-term fitness vs long-term evolvability\n\n"
        "PROTOCOL:\n"
        "1. Analyze the failure summary and current matrix state.\n"
        "2. Identify which constraint weights are causing the stagnation.\n"
        "3. Output a <constraint_gradient> block with a JSON dict:\n"
        "   Keys = category names, Values = gradient values (positive = increase).\n"
        "   Typical gradients: [-0.2, +0.2] range. Be surgical.\n\n"
        "DO NOT output English rules. DO NOT output Python code.\n"
        "ONLY output <constraint_gradient>{...}</constraint_gradient>.\n\n"
        "The optimizer applies Adam momentum to your gradients, so small\n"
        "consistent pushes are more effective than large one-shot jumps.\n"
    )

    matrix_md = cm.format_markdown()
    user_prompt = (
        f"CURRENT CONSTRAINT MATRIX:\n{matrix_md}\n\n"
        f"FAILURE SUMMARY:\n{failure_summary}\n\n"
    )
    if perf_history:
        user_prompt += f"HISTORICAL PERFORMANCE:\n{perf_history}\n\n"

    user_prompt += (
        "Analyze the stagnation pattern. Which constraint weights are "
        "causing the bottleneck? Output your gradient update:\n"
        "<constraint_gradient>\n"
    )

    return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════
# CONSTRAINT MATRIX → DYNAMIC PARAMS OVERRIDE
# ═══════════════════════════════════════════════════════════════

def override_dynamic_params(
    cm: ConstraintMatrix,
    base_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Override dynamic compute params with constraint matrix projections.

    Blends the recipe-derived base_params with the matrix projections.
    The matrix has authority over strategy knobs; the recipe provides
    fallback defaults.
    """
    proj = cm.project_all()
    overridden = dict(base_params)

    # Temperature: blend matrix projection with velocity-derived value
    matrix_temp = proj["temperature"]
    base_temp = base_params.get("temperature", 0.6)
    # Matrix has 60% authority, velocity tracker has 40%
    overridden["temperature"] = round(0.6 * matrix_temp + 0.4 * base_temp, 4)

    # Structural scope and risk budget are pure matrix-driven
    overridden["_structural_scope"] = proj["structural_scope"]
    overridden["_risk_budget"] = proj["risk_budget"]
    overridden["_parsimony_strength"] = proj["parsimony_strength"]
    overridden["_probe_frequency"] = proj["probe_frequency"]
    overridden["_temporal_bias"] = proj["temporal_bias"]

    return overridden


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

# Default matrix persistence path (inside workspace)
_DEFAULT_MATRIX_PATH: str = "island_meta/constraint_matrix.json"


def load_or_compile_matrix(
    workspace_root: str,
    recipe: Any = None,
    substrate_deps: Optional[Dict[str, Any]] = None,
    seed: int = 0,
) -> ConstraintMatrix:
    """Load existing constraint matrix or compile from recipe.

    If a saved matrix exists, load it.  Otherwise, compile from the
    current text recipe as a one-time migration.

    Args:
        substrate_deps: Hardware/framework profile of the current host
            (e.g. from biogeo_probe.get_physics_schema()).  Injected into
            newly-minted matrices; ignored when loading an existing matrix
            (the stored substrate_deps governs the loaded matrix's lineage).
        seed: Active PRNG/MCTS seed at mint time.
    """
    path = os.path.join(workspace_root, _DEFAULT_MATRIX_PATH)
    if os.path.exists(path):
        cm = ConstraintMatrix.load(path)  # integrity verified inside load()
        if cm.version > 0:
            return cm

    # First-time compilation from text recipe
    if recipe is not None:
        cm = compile_recipe_to_matrix(recipe)
        cm.substrate_deps = substrate_deps or {}
        cm.seed = seed
        cm.save(path)  # auto-seals inside save()
        print(f"[rule-ir] Compiled recipe → Constraint Matrix v{cm.version} "
              f"[seed={seed}, substrate={list((substrate_deps or {}).keys())}]")
        return cm

    cm = ConstraintMatrix(substrate_deps=substrate_deps, seed=seed)
    return cm


def save_matrix(workspace_root: str, cm: ConstraintMatrix) -> None:
    """Save constraint matrix to workspace."""
    path = os.path.join(workspace_root, _DEFAULT_MATRIX_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cm.save(path)


# ═══════════════════════════════════════════════════════════════
# TICK 26.0: DEPENDENCY RISK LEDGER
# ═══════════════════════════════════════════════════════════════
#
# Prevents fractal degradation and single-point-of-failure reliance
# on "favorite" elite organelles.  Tracks concentration of reliance
# on specific topological modules and computes a Dependency Risk
# penalty D(π) = max(reliance) - η × redundancy_score.
#
# D(π) is injected into the core loss function as +λ_D × D(π),
# forcing the Architect to invent redundant pathways (backup
# organelles) rather than over-relying on a single structure.

_DEPENDENCY_ETA: float = 0.3  # Redundancy discount factor


class DependencyLedger:
    """Tracks per-organelle reliance concentration across assemblies.

    Thread-safe: all mutations go through explicit method calls that
    should be wrapped in the caller's lock (SharedState._lock).
    The ledger itself holds no lock — it relies on the caller's
    synchronization protocol (zero-IPC SharedState pattern).
    """

    def __init__(self) -> None:
        # organelle_key → usage_count (e.g., "attention:elite_attn_012.py" → 47)
        self._usage: Dict[str, int] = {}
        self._total_assemblies: int = 0

    def record_assembly(self, organelle_keys: List[str]) -> None:
        """Record that an assembly used these organelle keys.

        organelle_keys: list of strings like "attention:elite_attn_012.py"
        """
        self._total_assemblies += 1
        for key in organelle_keys:
            self._usage[key] = self._usage.get(key, 0) + 1

    def reliance_distribution(self) -> Dict[str, float]:
        """Return normalized reliance fractions for each organelle.

        reliance[key] = usage_count[key] / total_assemblies
        Range: [0, 1] for each key. Sum may exceed 1.0 (each assembly
        uses multiple organelles).
        """
        if self._total_assemblies == 0:
            return {}
        return {
            key: count / self._total_assemblies
            for key, count in self._usage.items()
        }

    def max_reliance(self) -> float:
        """Return the maximum reliance on any single organelle.

        Range: [0, 1]. High values indicate single-point-of-failure risk.
        """
        if self._total_assemblies == 0:
            return 0.0
        if not self._usage:
            return 0.0
        return max(self._usage.values()) / self._total_assemblies

    def redundancy_score(self) -> float:
        """Measure topological redundancy: how many distinct organelles are active.

        redundancy = n_distinct_organelles / (n_organelle_types × min_diversity)
        where min_diversity = 3 (at least 3 variants per type for healthy redundancy).

        Range: [0, 1+]. Values > 1.0 indicate excellent diversity.
        """
        if not self._usage:
            return 0.0
        n_distinct = len(self._usage)
        # Assume 3 organelle types × 3 min variants = 9 for healthy diversity
        min_healthy = 9.0
        return n_distinct / min_healthy

    def dependency_risk(self, eta: float = _DEPENDENCY_ETA) -> float:
        """Compute the Dependency Risk penalty D(π).

        D(π) = max(reliance_on_single_module) - η × redundancy_score

        Range: Can be negative (good: high redundancy outweighs concentration).
        Clamped to [0, 1] for loss injection.

        When D > 0: the system is dangerously concentrated.
        When D ≤ 0: sufficient redundancy exists.
        """
        d = self.max_reliance() - eta * self.redundancy_score()
        return max(0.0, min(1.0, d))

    def format_status(self) -> str:
        """Compact status string for logging."""
        dist = self.reliance_distribution()
        if not dist:
            return "dep_ledger: empty"
        top3 = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:3]
        parts = [f"{k}={v:.2f}" for k, v in top3]
        return (
            f"dep_risk={self.dependency_risk():.3f} "
            f"max_rel={self.max_reliance():.3f} "
            f"redund={self.redundancy_score():.3f} "
            f"top=[{', '.join(parts)}]"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assemblies": self._total_assemblies,
            "n_distinct": len(self._usage),
            "max_reliance": round(self.max_reliance(), 4),
            "redundancy_score": round(self.redundancy_score(), 4),
            "dependency_risk": round(self.dependency_risk(), 4),
            "top_usage": dict(
                sorted(self._usage.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }


# ═══════════════════════════════════════════════════════════════
# TICK 27.0: IDENTITY MEMBRANE — Layer 3 of the IIS
# ═══════════════════════════════════════════════════════════════
#
# The IdentityMembrane locks a subset of Rule-IR Constraint Matrix
# weights as "Identity Invariants".  These specific base_weight values
# CANNOT be decayed to zero by the Adam optimizer in
# apply_epigenetic_penalty() or apply_decay().
#
# Implementation: hard clip(min=invariant_floor) applied AFTER every
# gradient update or decay operation.  No text description, no
# natural language — pure tensor mathematics.
#
# Categories protected:
#   risk_appetite     — must stay ≥ 0.10 so the system retains the
#                       capacity to allocate parameter budget at all.
#   organelle_priority — must stay ≥ 0.10 so organelle-type selection
#                       remains active (prevents monotype collapse).
#   parsimony_pressure — must stay ≥ 0.15 so MDL compression never
#                       fully deactivates (prevents bloat death).
#   temporal_horizon  — must stay ≥ 0.10 so long-term exploration
#                       cannot be fully eroded by short-term pressure.

IDENTITY_INVARIANTS: Dict[str, float] = {
    "risk_appetite":      0.10,
    "organelle_priority": 0.10,
    "parsimony_pressure": 0.15,
    "temporal_horizon":   0.10,
}


class IdentityMembrane:
    """Enforces the indestructible identity floor on the Constraint Matrix.

    TICK 27.0: Invariant Identity Substrate — Layer 3.

    After any optimizer update (epigenetic penalty, Adam gradient, decay),
    this membrane clips the base_weight of each protected category back up
    to its invariant floor.  The Adam optimizer cannot erode these weights
    below the floor — they represent the minimum functional identity of
    the Tri-Agent system.

    Zero-IPC: this object is pure Python/math, no MLX tensors, no
    threading — safe to call from any context.
    """

    def __init__(
        self,
        invariants: Optional[Dict[str, float]] = None,
    ) -> None:
        self._invariants: Dict[str, float] = invariants or dict(IDENTITY_INVARIANTS)

    def enforce(self, cm: "ConstraintMatrix") -> Dict[str, float]:
        """Clip invariant categories back to their floor values.

        Iterates over the protected categories.  For each one whose
        base_weight has been eroded below the floor, snaps it back.

        Args:
            cm: The ConstraintMatrix to enforce invariants on (mutates in place).

        Returns:
            Dict mapping category_name → amount_clipped (0.0 if not needed).
            Only categories that were actually clipped appear with non-zero values.
        """
        bw_idx = CON_IDX["base_weight"]
        clipped: Dict[str, float] = {}

        for cat_name, floor in self._invariants.items():
            ci = CAT_IDX.get(cat_name, -1)
            if ci < 0:
                continue
            current = cm.C[ci][bw_idx]
            if current < floor:
                delta = floor - current
                cm.C[ci][bw_idx] = floor
                clipped[cat_name] = round(delta, 6)

        return clipped

    def get_floors(self) -> Dict[str, float]:
        """Return the invariant floor mapping (read-only view)."""
        return dict(self._invariants)

    def is_invariant(self, category: str) -> bool:
        """True if this category is identity-protected."""
        return category in self._invariants


# Module-level singleton — shared by all ConstraintMatrix instances.
# Wire this into apply_epigenetic_penalty() and apply_decay() below.
_GLOBAL_IDENTITY_MEMBRANE: IdentityMembrane = IdentityMembrane()


# ═══════════════════════════════════════════════════════════════
# TICK 28.0: CONSTRAINT EXCHANGE PROTOCOL — Cross-Niche Shadow Penalties
# ═══════════════════════════════════════════════════════════════
#
# A catastrophic failure (OOM, timeout, deadlock) in Niche A encodes
# critical structural knowledge: "this topology is lethal in condition X".
#
# ConstraintMorphism is the carrier of that knowledge across niches.
# Instead of letting each niche re-discover the same failure independently
# (O(n²) search cost), a ConstraintMorphism broadcasts a SHADOW penalty
# — attenuated to 30% of the original severity — to all OTHER active niches.
#
# The receiving niche's SovereigntyFloorVerifier independently caps the
# shadow severity before it is applied, so no cascade can push any niche
# below its thermodynamic floor.
#
# NegativeTransferFirewall: an audit ledger (deque, cap=50) of recent
# ConstraintMorphisms.  Purely observational — broadcasting is synchronous
# and immediate.  The firewall provides a queryable history for telemetry,
# the mutator's context window, and post-mortem analysis.

# Shadow attenuation: how much of the original severity propagates to peers.
# 0.30 → 30% of the original penalty crosses the niche boundary.
# Geometric series convergence: if every niche re-broadcasts at 30%, the
# total penalty across N niches converges to severity / (1 - 0.30) = 1.43x.
_SHADOW_ATTENUATION: float = 0.30

# IIS sovereignty floor for shadow penalty capping — mirrors
# autopoietic_core._PHI_SOVEREIGNTY_MIN without creating a circular import.
_SHADOW_SOVEREIGNTY_FLOOR: float = 0.12
_SHADOW_PENALTY_COST_EST: float = 0.02  # Φ drop per severity unit (same as Layer 1)


@dataclasses.dataclass
class ConstraintMorphism:
    """TICK 28.0: A cross-niche constraint broadcast event.

    Encapsulates one catastrophic failure in a source niche and the
    resulting shadow penalty that must be applied to all peer niches.

    Immutable once created — treated as an event record in the firewall.

    Fields:
        morphism_id:       Unique identifier (timestamp-based).
        source_niche:      Niche where the failure occurred.
        failure_type:      The EpigeneticFailureType that was triggered.
        original_severity: Full severity applied to the source niche.
        shadow_severity:   Attenuated severity for peer niches
                           (= original × _SHADOW_ATTENUATION).
        timestamp:         Unix timestamp of the morphism creation.
    """
    morphism_id: str
    source_niche: str
    failure_type: EpigeneticFailureType
    original_severity: float
    shadow_severity: float
    timestamp: float = dataclasses.field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        source_niche: str,
        failure_type: EpigeneticFailureType,
        original_severity: float,
        attenuation: float = _SHADOW_ATTENUATION,
    ) -> "ConstraintMorphism":
        """Factory: create a ConstraintMorphism from a source failure.

        morphism_id is deterministic from (source_niche, failure_type, ts)
        for idempotency checking — duplicate events within the same ms
        produce the same ID and are deduplicated by the firewall.
        """
        ts = time.time()
        mid = f"{source_niche}:{failure_type.value}:{ts:.3f}"
        return cls(
            morphism_id=mid,
            source_niche=source_niche,
            failure_type=failure_type,
            original_severity=max(0.0, original_severity),
            shadow_severity=max(0.0, original_severity * attenuation),
            timestamp=ts,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "morphism_id": self.morphism_id,
            "source_niche": self.source_niche,
            "failure_type": self.failure_type.value,
            "original_severity": round(self.original_severity, 4),
            "shadow_severity": round(self.shadow_severity, 4),
            "timestamp": round(self.timestamp, 3),
        }


class NegativeTransferFirewall:
    """TICK 28.0: Audit ledger for cross-niche constraint morphisms.

    Maintains a bounded deque (cap=50) of recent ConstraintMorphism events.
    Broadcasting is synchronous and immediate in NicheRegistry — this
    class is purely an observational record for telemetry, the mutator's
    context window, and post-mortem analysis.

    Thread-safety: the caller (NicheRegistry, protected by SharedState._lock)
    owns synchronization.  The firewall itself holds no lock.

    Zero-IPC: pure Python in-memory data structure, no MLX, no filesystem I/O.
    """
    _MAX_HISTORY: int = 50

    def __init__(self) -> None:
        self._history: deque = deque(maxlen=self._MAX_HISTORY)

    def record(self, morphism: ConstraintMorphism) -> None:
        """Record a dispatched morphism in the audit history."""
        self._history.append(morphism)

    def recent(self, n: int = 10) -> List[ConstraintMorphism]:
        """Return the n most recent morphisms (newest last)."""
        items = list(self._history)
        return items[-n:] if len(items) >= n else items

    def count_by_niche(self) -> Dict[str, int]:
        """Return count of morphisms emitted by each source niche."""
        counts: Dict[str, int] = {}
        for m in self._history:
            counts[m.source_niche] = counts.get(m.source_niche, 0) + 1
        return counts

    def format_status(self) -> str:
        """Compact one-line status for logging."""
        total = len(self._history)
        by_niche = self.count_by_niche()
        if not total:
            return "firewall: empty"
        parts = [f"{n}={c}" for n, c in sorted(by_niche.items())]
        return f"firewall: total={total} [{', '.join(parts)}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_morphisms": len(self._history),
            "by_niche": self.count_by_niche(),
            "recent": [m.to_dict() for m in self.recent(5)],
        }


# ═══════════════════════════════════════════════════════════════
# TICK 29.0: FEDERATED SELF-AMENDMENT & AUDITABLE SRCA
# Self-Referential Constitutional Architecture (SRCA)
#
# The Gödel Bottleneck: meta-rules governing the system
# (Pareto thresholds, Adam LRs, decay constants) were hardcoded.
# TICK 29.0 allows niches to safely mutate these soft-rules via
# Shadow Forking and Dual Verification, while the IMMUTABLE_HARD_CORE
# (sovereignty floor, identity invariants, genesis hash, matrix shape)
# remains absolutely inviolable.
#
# Architecture:
#   IMMUTABLE_HARD_CORE  — frozenset of constant names that CANNOT mutate
#   EvolvableSoftShell   — mutable meta-rules with validated ranges
#   SoftShellAmendment   — dataclass: one proposed rule change
#   ConstitutionalDiffLedger — append-only audit log of all amendments
#   DualVerifier         — compares main vs shadow Φ rollouts
# ═══════════════════════════════════════════════════════════════


# ── Mod-1: ConstitutionalViolationError ──────────────────────────────────
class ConstitutionalViolationError(BaseException):
    """TICK 29.0 (upgraded TICK 40.0): Raised immediately and loudly when
    any mutation attempt targets a constant in IMMUTABLE_HARD_CORE or when
    a SHA-256 content_hash integrity check fails on any sealed structure
    (ConstraintMatrix, SpecFinal, organelle topological anchors).

    Inherits BaseException (not Exception) since TICK 40.0 — this makes it
    UNCATCHABLE by generic `except Exception:` immortal loops in the daemons.
    A tampered or corrupted identity substrate is an extinction-class event.
    The system MUST halt rather than continue operating on corrupted state.
    """


# ── Mod-2: IMMUTABLE_HARD_CORE ───────────────────────────────────────────
# The mathematical bedrock of the organism's identity.
# These constants encode:
#   - The minimum thermodynamic budget for the Tri-Agent to survive
#   - The identity floors that prevent Adam from eroding selfhood
#   - The cryptographic genesis anchor (TICK 13 constitution hash)
#   - The constraint matrix dimensionality (shape cannot mutate mid-flight)
#   - The fundamental categories and constraint axes
#
# Any string in this frozenset CANNOT be the target of EvolvableSoftShell.set().
# Attempting to mutate these raises ConstitutionalViolationError immediately.
IMMUTABLE_HARD_CORE: frozenset = frozenset({
    "_PHI_SOVEREIGNTY_MIN",
    "IDENTITY_INVARIANTS",
    "TICK13_CONSTITUTION_HASH",
    "N_CAT",
    "N_CON",
    "CATEGORIES",
    "CONSTRAINTS",
    "_LAMBDA_VIOLATION",           # authorized-action penalty is infinite by design
})


# ── Mod-3: EvolvableSoftShell ─────────────────────────────────────────────
class EvolvableSoftShell:
    """TICK 29.0: The mutable layer of the system's governing meta-rules.

    Holds all soft parameters that niches are permitted to propose amendments
    for.  Each parameter has:
      - A current value (starts at the system default)
      - A (min, max) range — proposals outside this range are rejected
      - A record of the snapshot at last permeation (for rollback)

    Thread-safety: all mutations go through set() which validates range and
    hard-core membership.  Callers must hold SharedState._lock before calling
    set() or restore() during live operation.

    Zero-MLX: all values are pure Python floats.  No tensors, no lazy eval.
    """

    # (default_value, min_allowed, max_allowed)
    _PARAMS: Dict[str, Tuple[float, float, float]] = {
        # Cross-niche shadow penalty attenuation (TICK 28.0)
        "shadow_attenuation":    (0.30,  0.05,  0.80),
        # Reproductive fitness cross-niche bonus coefficient (TICK 28.0)
        "fo_alpha":              (0.20,  0.05,  0.50),
        # MCTS Pareto pool cutoff — fraction of top candidates retained
        "pareto_threshold":      (0.20,  0.05,  0.50),
        # Boundary operator Adam learning rate
        "boundary_lr":           (0.02,  0.001, 0.20),
        # Boundary operator L2 weight decay
        "boundary_decay":        (0.01,  0.001, 0.10),
        # Phi ratio above which boundary expansion is allowed
        "expand_threshold":      (0.70,  0.30,  0.95),
        # Phi ratio below which boundary contraction triggers
        "contract_threshold":    (0.30,  0.05,  0.60),
        # Niche construction λ weight (generation cost + mismatch penalty)
        "niche_lambda":          (0.15,  0.05,  0.50),
        # Epigenetic penalty decay rate per tick
        "epigenetic_decay":      (0.01,  0.001, 0.10),
    }

    def __init__(self) -> None:
        # Live values — start at defaults
        self._values: Dict[str, float] = {
            name: spec[0] for name, spec in self._PARAMS.items()
        }
        # Snapshot taken just before the last permeation (used for rollback)
        self._last_permeated_snapshot: Optional[Dict[str, float]] = None
        # Baseline phi ratio at time of last permeation (rollback trigger ref)
        self.permeation_phi_baseline: float = 0.0

    def get(self, name: str) -> float:
        """Return current value of a soft-shell parameter."""
        if name not in self._values:
            raise KeyError(f"EvolvableSoftShell: unknown parameter '{name}'")
        return self._values[name]

    def set(self, name: str, value: float) -> None:
        """Set a soft-shell parameter.

        Raises:
            ConstitutionalViolationError: if name is in IMMUTABLE_HARD_CORE.
            KeyError:  if name is not a recognised soft-shell parameter.
            ValueError: if value is outside the allowed (min, max) range.
        """
        if name in IMMUTABLE_HARD_CORE:
            raise ConstitutionalViolationError(
                f"CONSTITUTIONAL VIOLATION: attempt to mutate immutable hard-core "
                f"constant '{name}'.  The bedrock cannot be amended.  "
                f"The system will not proceed."
            )
        if name not in self._PARAMS:
            raise KeyError(f"EvolvableSoftShell: unknown parameter '{name}'")
        _, lo, hi = self._PARAMS[name]
        if not (lo <= value <= hi):
            raise ValueError(
                f"EvolvableSoftShell: value {value} for '{name}' outside "
                f"allowed range [{lo}, {hi}]"
            )
        self._values[name] = value

    def snapshot(self) -> Dict[str, float]:
        """Return a full copy of current values (for rollback or shadow fork)."""
        return dict(self._values)

    def restore(self, snap: Dict[str, float]) -> None:
        """Restore all values from a previously taken snapshot.

        Validates each key/value pair before applying (no hard-core bypass).
        Raises ConstitutionalViolationError if snapshot contains hard-core keys.
        """
        for name, value in snap.items():
            if name in IMMUTABLE_HARD_CORE:
                raise ConstitutionalViolationError(
                    f"CONSTITUTIONAL VIOLATION: snapshot restore attempted to "
                    f"overwrite immutable hard-core constant '{name}'."
                )
        self._values.update(snap)

    def params(self) -> Dict[str, Tuple[float, float, float]]:
        """Return the full parameter specification dict (read-only view)."""
        return dict(self._PARAMS)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "values": self.snapshot(),
            "permeation_phi_baseline": self.permeation_phi_baseline,
        }


# ── Mod-4: SoftShellAmendment ─────────────────────────────────────────────
@dataclasses.dataclass
class SoftShellAmendment:
    """TICK 29.0: A single proposed amendment to the Evolvable Soft Shell.

    Lifecycle:
      PENDING   → created, shadow instance running
      ACCEPTED  → shadow won Dual Verification, value permeated to main shell
      ACTIVE    → permeated value is now governing live operation
      REJECTED  → shadow lost or breached sovereignty floor
      ROLLED_BACK → was ACTIVE but caused a Φ spike → reverted

    Fields:
        amendment_id:     Unique identifier (niche:param:timestamp).
        param_name:       The soft-shell parameter being amended.
        old_value:        Value before the amendment.
        proposed_value:   Value the shadow instance will test.
        proposing_niche:  Which NicheSpecies proposed this change.
        timestamp:        Unix timestamp of proposal.
        status:           One of PENDING / ACCEPTED / ACTIVE / REJECTED / ROLLED_BACK.
        activation_phi:   Φ ratio recorded at time of ACTIVE transition
                          (used as rollback baseline).
    """
    amendment_id: str
    param_name: str
    old_value: float
    proposed_value: float
    proposing_niche: str
    timestamp: float = dataclasses.field(default_factory=time.time)
    status: str = "PENDING"
    activation_phi: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ── Mod-5: ConstitutionalDiffLedger ──────────────────────────────────────
class ConstitutionalDiffLedger:
    """TICK 29.0: Append-only audit log of all soft-shell amendment events.

    Tracks the full lifecycle of every proposed change to the Evolvable Soft
    Shell — from proposal through shadow testing, acceptance/rejection, and
    any subsequent rollback.  Provides the Federation-Level Rollback mechanism
    via get_active_amendments() + rollback accounting.

    Cap: deque(maxlen=200).  Oldest entries are discarded when full.
    This is intentional: constitutional history beyond 200 amendments is
    archived offline; the live ledger tracks only recent amendments.

    Thread-safety: append() / update_status() called under SharedState._lock.
    """
    _MAX_HISTORY: int = 200

    def __init__(self) -> None:
        self._ledger: deque = deque(maxlen=self._MAX_HISTORY)

    def append(self, amendment: SoftShellAmendment) -> None:
        """Record a new amendment (any status)."""
        self._ledger.append(amendment)

    def update_status(self, amendment_id: str, new_status: str, **kwargs: Any) -> bool:
        """Update status (and optional fields) of an amendment by ID.

        Returns True if found and updated, False if ID not in ledger.
        """
        for amendment in self._ledger:
            if amendment.amendment_id == amendment_id:
                amendment.status = new_status
                for k, v in kwargs.items():
                    if hasattr(amendment, k):
                        setattr(amendment, k, v)
                return True
        return False

    def pending(self) -> List[SoftShellAmendment]:
        return [a for a in self._ledger if a.status == "PENDING"]

    def accepted(self) -> List[SoftShellAmendment]:
        return [a for a in self._ledger if a.status in ("ACCEPTED", "ACTIVE")]

    def active(self) -> List[SoftShellAmendment]:
        return [a for a in self._ledger if a.status == "ACTIVE"]

    def get_by_id(self, amendment_id: str) -> Optional[SoftShellAmendment]:
        for a in self._ledger:
            if a.amendment_id == amendment_id:
                return a
        return None

    def rollback_count_for_niche(self, niche_name: str) -> int:
        """Count how many ROLLED_BACK amendments were proposed by this niche.

        Used for the strike-based cooldown: a niche with ≥3 rollback strikes
        is temporarily barred from proposing new amendments.
        """
        return sum(
            1 for a in self._ledger
            if a.proposing_niche == niche_name and a.status == "ROLLED_BACK"
        )

    def format_status(self) -> str:
        total = len(self._ledger)
        by_status: Dict[str, int] = {}
        for a in self._ledger:
            by_status[a.status] = by_status.get(a.status, 0) + 1
        parts = [f"{s}={c}" for s, c in sorted(by_status.items())]
        return f"ledger: total={total} [{', '.join(parts)}]"

    def to_dict(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._ledger]


# ── Mod-6: DualVerifier ───────────────────────────────────────────────────
class DualVerifier:
    """TICK 29.0: Compares main-instance vs shadow-instance Φ rollouts.

    Pure arithmetic — no MLX tensors, no threading, no IPC.
    Called by PhiGovernor._finalize_shadow_test() once the shadow instance
    has accumulated enough rollouts.

    Verdict rules:
        shadow_wins iff:
          1. mean(shadow_phis) > mean(main_phis)    — shadow is thermodynamically
                                                       more efficient (higher Φ)
          2. min(shadow_phis) >= sovereignty_floor  — shadow never dips below
                                                       the existence threshold

        If either condition fails → shadow_wins = False → amendment REJECTED.

    The delta_phi returned is mean(shadow) − mean(main).
    Positive delta → shadow is better.
    Negative delta → shadow is worse (or equal → also rejected, conservative).
    """
    _MIN_ROLLOUTS: int = 5

    @staticmethod
    def evaluate(
        main_phis: List[float],
        shadow_phis: List[float],
        sovereignty_floor: float = 0.12,
    ) -> Tuple[bool, float]:
        """Return (shadow_is_better, delta_phi).

        Args:
            main_phis:         List of Φ values observed in the main instance.
            shadow_phis:       List of Φ values observed in the shadow instance.
            sovereignty_floor: Minimum acceptable Φ — shadow must never breach.

        Returns:
            (True, delta_phi > 0)  if shadow wins
            (False, delta_phi ≤ 0) if shadow loses or breaches floor
        """
        if not main_phis or not shadow_phis:
            return False, 0.0
        if len(main_phis) < DualVerifier._MIN_ROLLOUTS or len(shadow_phis) < DualVerifier._MIN_ROLLOUTS:
            return False, 0.0

        mean_main = sum(main_phis) / len(main_phis)
        mean_shadow = sum(shadow_phis) / len(shadow_phis)
        delta_phi = mean_shadow - mean_main

        # Condition 2: shadow must never have breached the sovereignty floor
        floor_safe = all(phi >= sovereignty_floor for phi in shadow_phis)

        shadow_wins = (delta_phi > 0.0) and floor_safe
        return shadow_wins, delta_phi


# ═══════════════════════════════════════════════════════════════
# TICK 30.1: SPEC_FINAL — Teleological Identity Core (TIC)
# ═══════════════════════════════════════════════════════════════
#
# spec_final.json is the Absolute Teleological Attractor (A*) and
# the Executable Identity Core (IIS) for the silicon-clock era.
#
# Cryptographic protocol:
#   - The canonical payload is the full JSON object with the
#     "content_hash" key stripped from "topological_anchors".
#   - SHA-256 is computed over json.dumps(sort_keys=True,
#     separators=(",",":"), ensure_ascii=False).encode("utf-8").
#   - On FIRST load the stored hash equals _SPEC_HASH_PLACEHOLDER.
#     The loader seals the file (computes real hash, writes back).
#   - On all subsequent loads the recomputed hash must match the
#     stored hash — any mismatch raises ConstitutionalViolationError.
#
# Substrate enforcement:
#   - verify_substrate() measures live RAM via biogeo_probe and
#     compares it against substrate_deps.ram_ceiling_gb.
#   - A machine with less RAM than the spec ceiling raises
#     ConstitutionalViolationError (fatal before evolution).
# ════════════════════════════════════════════════════════════════

_SPEC_HASH_PLACEHOLDER: str = "PENDING_SHA256_CALCULATION_ON_FIRST_LOAD"
_SPEC_FINAL_FILENAME: str = "spec_final.json"


class SpecFinal:
    """TICK 30.1: Loader, sealer, and integrity guardian for spec_final.json.

    Lifecycle:
      FIRST LOAD  — stored hash == _SPEC_HASH_PLACEHOLDER
                    → compute real SHA-256, write back atomically, return spec
      SUBSEQUENT  — recompute hash, compare; mismatch → ConstitutionalViolationError

    Thread-safety: all file I/O uses atomic os.rename() writes (same pattern
    as ConstraintMatrix.save()).  Pure Python arithmetic for hash — no MLX,
    no subprocesses, no deadlock risk.
    """

    # ── Canonical hash computation ────────────────────────────────────────

    @staticmethod
    def _canonical_payload(spec: Dict[str, Any]) -> str:
        """Build the canonical JSON string for hashing.

        Excludes the content_hash field itself so the hash can be
        embedded in the same document it covers.
        """
        import copy
        payload = copy.deepcopy(spec)
        anchors = payload.get("topological_anchors", {})
        anchors.pop("content_hash", None)
        payload["topological_anchors"] = anchors
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)

    @staticmethod
    def _compute_hash(spec: Dict[str, Any]) -> str:
        """SHA-256 of the canonical payload, returned as 64-char hex digest."""
        canonical = SpecFinal._canonical_payload(spec)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ── Public API ────────────────────────────────────────────────────────

    @staticmethod
    def load(path: str) -> Dict[str, Any]:
        """Load spec_final.json; seal on first load; verify on all subsequent.

        Args:
            path: Absolute or relative path to spec_final.json.

        Returns:
            The validated spec dict.

        Raises:
            FileNotFoundError: if the file does not exist.
            ConstitutionalViolationError: if the stored hash does not match
                the recomputed hash (tamper or corruption).
            json.JSONDecodeError: if the file is not valid JSON.
        """
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        stored_hash: str = spec.get("topological_anchors", {}).get(
            "content_hash", _SPEC_HASH_PLACEHOLDER
        )

        if stored_hash == _SPEC_HASH_PLACEHOLDER:
            # ── First load: bootstrap seal ───────────────────────────────
            genesis_hash = SpecFinal._compute_hash(spec)
            spec["topological_anchors"]["content_hash"] = genesis_hash
            SpecFinal._atomic_write(path, spec)
            print(
                f"[spec_final] GENESIS SEAL — identity kernel locked.\n"
                f"  Hash: {genesis_hash}\n"
                f"  File: {path}"
            )
        else:
            # ── Subsequent loads: integrity verification ─────────────────
            expected = SpecFinal._compute_hash(spec)
            if expected != stored_hash:
                raise ConstitutionalViolationError(
                    f"CONSTITUTIONAL VIOLATION: spec_final.json integrity check failed.\n"
                    f"  Stored hash:    {stored_hash[:16]}…\n"
                    f"  Recomputed:     {expected[:16]}…\n"
                    f"  The Teleological Identity Core has been tampered with or corrupted.\n"
                    f"  The system will not ignite."
                )

        return spec

    @staticmethod
    def verify_substrate(spec: Dict[str, Any]) -> None:
        """Assert the live physical substrate meets the spec's minimum requirements.

        Checks RAM_ceiling_gb from substrate_deps against the machine's
        total RAM reported by biogeo_probe.  A machine below the threshold
        cannot faithfully execute the silicon-clock evolution pipeline.

        Raises:
            ConstitutionalViolationError: if total RAM < ram_ceiling_gb.
        """
        required_gb: float = float(
            spec.get("topological_anchors", {})
                .get("substrate_deps", {})
                .get("ram_ceiling_gb", 0.0)
        )
        if required_gb <= 0.0:
            return  # no constraint defined

        live_gb: float = 0.0
        try:
            from biogeo_probe import get_physics_schema
            physics = get_physics_schema()
            live_gb = float(
                physics.get("memory", {}).get("total_gb", 0.0)
                or physics.get("Memory", {}).get("Total_Gb", 0.0)
                or 0.0
            )
        except Exception:
            # biogeo_probe unavailable — skip substrate check rather than
            # blocking an otherwise valid startup (graceful degradation).
            return

        if live_gb < required_gb:
            raise ConstitutionalViolationError(
                f"CONSTITUTIONAL VIOLATION: substrate check failed.\n"
                f"  spec_final requires ram_ceiling_gb ≥ {required_gb:.0f} GB\n"
                f"  Live machine reports {live_gb:.1f} GB total RAM.\n"
                f"  This silicon cannot faithfully execute the teleological pipeline.\n"
                f"  The system will not ignite."
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _atomic_write(path: str, spec: Dict[str, Any]) -> None:
        """Atomically write spec back to disk (same pattern as ConstraintMatrix.save)."""
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.rename(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def get_forbidden_transitions(spec: Dict[str, Any]) -> List[str]:
        """Extract the forbidden_transitions list from the spec."""
        return list(
            spec.get("identity_kernel", {})
                .get("teleological_attractor", {})
                .get("forbidden_transitions", [])
        )

    @staticmethod
    def get_target_state(spec: Dict[str, Any]) -> str:
        """Extract the target_state string from the spec."""
        return str(
            spec.get("identity_kernel", {})
                .get("teleological_attractor", {})
                .get("target_state", "")
        )


# ═══════════════════════════════════════════════════════════════
# TICK 40.1: SCENARIO DIMENSIONS & NEGATIVE KNOWLEDGE
# "If the system cannot name what it has tried and failed, it
#  cannot prevent thermodynamic waste from re-exploring the same
#  forbidden regions under slightly different names."
# ═══════════════════════════════════════════════════════════════

class KnowledgeAtomType(enum.Enum):
    """Discrete taxonomy of knowledge atomic types (TICK 40.1).

    Every rule, organelle, or constraint carries exactly one atom_type.
    This enforces strict modularity: an agent knows precisely which
    cognitive operation to perform when it encounters a given atom.

    Classification semantics:
        ARCHITECTURAL  — governs structural topology (layer counts, connectivity)
        PARAMETRIC     — governs numerical hyperparameters (LR, temperature, bounds)
        CAUSAL         — records a discovered cause-effect relationship
        CONSTRAINT     — encodes a hard or soft boundary on the search space
        HEURISTIC      — encodes a learned empirical rule without formal proof
        COUNTEREXAMPLE — records a concrete instance that falsifies a hypothesis
        FORBIDDEN      — marks a region of the search space as permanently barred
        META           — governs the mutation/evaluation process itself (recipes,
                         selection pressures, governance rules)
    """
    ARCHITECTURAL  = "architectural"
    PARAMETRIC     = "parametric"
    CAUSAL         = "causal"
    CONSTRAINT     = "constraint"
    HEURISTIC      = "heuristic"
    COUNTEREXAMPLE = "counterexample"
    FORBIDDEN      = "forbidden"
    META           = "meta"


@dataclasses.dataclass
class ScenarioDimensions:
    """TICK 40.1: The 4 Irreversible Topological Scenario Dimensions.

    Every rule, organelle, or constraint matrix must declare these four
    dimensions at mint time.  They encode how the knowledge can be
    operationalized by an agent, how much it shifts decisions, how fast
    it decays, and what type of cognitive atom it represents.

    These fields are stored on ConstraintMatrix as MUTABLE METADATA —
    i.e., excluded from content_hash (per the TICK 31.0 capitalization
    pattern) — because decision_impact and temporal_dynamics are
    empirically updated as the organism applies the knowledge.

    Fields:
        agent_function:     Canonical name of the agent operation that can
                            directly invoke or apply this knowledge.
                            e.g., "mutator.targeted_mutation",
                                  "evaluator.fitness_gate",
                                  "PhiGovernor.tick_boundary".
        decision_impact:    Quantifiable metric ∈ [0, ∞) estimating how much
                            this rule shifts a downstream decision.
                            0.0 = cosmetic/no impact;
                            1.0 = changes one decision dimension;
                            > 1.0 = shifts multiple downstream decisions.
        temporal_dynamics:  Time-decay coefficient ∈ [0, 1] expressing how
                            quickly this knowledge loses relevance per tick.
                            0.0 = eternal (no decay); 1.0 = single-tick ephemeral.
                            Governs the epigenetic decay schedule for this rule.
        atom_type:          KnowledgeAtomType classification.  Strict modularity
                            enforcement: agents route different atom_types to
                            different processing pipelines.
    """
    agent_function:    str
    decision_impact:   float
    temporal_dynamics: float
    atom_type:         KnowledgeAtomType

    def __post_init__(self) -> None:
        if self.decision_impact < 0.0:
            raise ValueError(
                f"ScenarioDimensions.decision_impact must be ≥ 0, got {self.decision_impact}"
            )
        if not (0.0 <= self.temporal_dynamics <= 1.0):
            raise ValueError(
                f"ScenarioDimensions.temporal_dynamics must be in [0, 1], "
                f"got {self.temporal_dynamics}"
            )
        if not isinstance(self.atom_type, KnowledgeAtomType):
            raise TypeError(
                f"ScenarioDimensions.atom_type must be KnowledgeAtomType, "
                f"got {type(self.atom_type)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_function": self.agent_function,
            "decision_impact": self.decision_impact,
            "temporal_dynamics": self.temporal_dynamics,
            "atom_type": self.atom_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioDimensions":
        return cls(
            agent_function=str(data.get("agent_function", "")),
            decision_impact=float(data.get("decision_impact", 0.0)),
            temporal_dynamics=float(data.get("temporal_dynamics", 0.0)),
            atom_type=KnowledgeAtomType(data.get("atom_type", "heuristic")),
        )


@dataclasses.dataclass
class NegativeKnowledgeRecord:
    """TICK 40.1: Negative Knowledge as a First-Class Compounding Asset.

    The system explicitly records three categories of dead-end knowledge.
    A discovered forbidden region or failed path is NOT discarded — it is
    archived as a high-value asset that prevents future thermodynamic waste
    from re-exploring the same terrain under different names.

    Negative knowledge compounds: the more dead-ends are recorded, the
    faster the search can prune unpromising branches.  It is the dual of
    KVS (which tracks positive compounding yield) applied to the space of
    failures.

    Fields:
        counterexample:   A concrete input or configuration that falsifies
                          a previously held hypothesis.
                          e.g., "h=64 with gqa_groups=3 raises RuntimeError:
                                 h % gqa_groups != 0 (64 % 3 = 1)"
        failed_path:      A description of the evolutionary path that was
                          explored and confirmed as a dead-end.
                          e.g., "SSM + Hilbert curve routing: epi never
                                 exceeded 0.12 over 3 island cycles."
        forbidden_region: A formal description of the search-space region
                          that must never be re-entered.
                          e.g., "attention_heads % gqa_groups != 0 for any
                                 GQA configuration"
        severity:         How harmful re-entry into this region would be.
                          Maps directly to EpigeneticFailureType severity.
        tick_discovered:  The tick number when this dead-end was confirmed.
        source_agent:     The daemon or process that confirmed the failure.
    """
    counterexample:   str
    failed_path:      str
    forbidden_region: str
    severity:         float = 1.0
    tick_discovered:  int   = 0
    source_agent:     str   = ""

    def __post_init__(self) -> None:
        if self.severity < 0.0:
            raise ValueError(
                f"NegativeKnowledgeRecord.severity must be ≥ 0, got {self.severity}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counterexample": self.counterexample,
            "failed_path": self.failed_path,
            "forbidden_region": self.forbidden_region,
            "severity": self.severity,
            "tick_discovered": self.tick_discovered,
            "source_agent": self.source_agent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NegativeKnowledgeRecord":
        return cls(
            counterexample=str(data.get("counterexample", "")),
            failed_path=str(data.get("failed_path", "")),
            forbidden_region=str(data.get("forbidden_region", "")),
            severity=float(data.get("severity", 1.0)),
            tick_discovered=int(data.get("tick_discovered", 0)),
            source_agent=str(data.get("source_agent", "")),
        )
