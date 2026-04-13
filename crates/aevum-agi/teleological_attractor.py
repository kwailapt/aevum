#!/usr/bin/env python3
"""teleological_attractor.py — Teleological Attractor & Future-Guided MCTS (TICK 20.1).

"The organism no longer searches blindly.  It is pulled by its own perfection."

Defines the Perfect Topological Attractor — a theoretical upper bound on the
organism's thermodynamic state — and computes a Distance-to-Attractor penalty
that biases the MCTS value function toward the shortest evolutionary path.

══════════════════════════════════════════════════════════════════════════════
THE PERFECT ATTRACTOR STATE
══════════════════════════════════════════════════════════════════════════════

The attractor is the theoretically perfect organism defined by:

    A* = { latency → 0,
           Φ (Free Energy Rate Density) → Φ_max,
           Information Entropy Gain → H_max,
           MDL (Minimum Description Length) → MDL_min,
           Evolvability → 1.0 }

No real organism can reach A*, but the *distance* from the current state
to A* creates a teleological gradient — a directional pull that prevents
the MCTS from exploring sideways when a direct path exists.

══════════════════════════════════════════════════════════════════════════════
DISTANCE-TO-ATTRACTOR FORMULA
══════════════════════════════════════════════════════════════════════════════

    D(s, A*) = Σ_i  w_i × (1 - s_i / A*_i)²     for maximization dims
             + Σ_j  w_j × (s_j / A*_j)²           for minimization dims

    Where:
        s    = current organism state vector
        A*   = attractor state vector
        w_i  = dimension weight (normalized to sum=1)

    Attractor Penalty for MCTS:
        V_attractor(node) = -λ_attr × D(s_node, A*)

    This penalty is ADDED to the standard MCTS value (Φ tax + parsimony):
        V_total = V_base + V_attractor

══════════════════════════════════════════════════════════════════════════════
M-SERIES REALITY COUPLING (Attractor Calibration)
══════════════════════════════════════════════════════════════════════════════

The attractor bounds are calibrated to the physical hardware:

    Φ_max       = f(chip_bandwidth, unified_memory)
    latency_min = f(clock_speed, memory_bandwidth)
    MDL_min     = theoretical minimum based on Kolmogorov complexity estimate

These are NOT arbitrary "dream" values.  They are physics-bounded upper
limits — the absolute best any architecture could achieve on THIS silicon.

══════════════════════════════════════════════════════════════════════════════
MCTS INTEGRATION
══════════════════════════════════════════════════════════════════════════════

The `attractor_penalty()` function is called during MCTS node evaluation
(genome_assembler.py `_compute_phi_value()`).  It adds a directional bias:

    Before TICK 20.1:
        Value = projected_phi - λ_tax × cost + parsimony_bonus

    After TICK 20.1:
        Value = projected_phi - λ_tax × cost + parsimony_bonus
                - λ_attr × distance_to_attractor

The attractor penalty causes the MCTS to prefer nodes that are CLOSER
to the theoretical optimum, even if their immediate projected_phi is
slightly lower.  This creates a teleological gradient — the search
is pulled by the future rather than just pushed by the past.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# ATTRACTOR CONSTANTS (Physics-Bounded Upper Limits)
# ═══════════════════════════════════════════════════════════════

# M-Series chip characteristics (immutable — matches dag_oracle.py §7)
_CHIP_SPECS: Dict[str, Dict[str, float]] = {
    "M1":       {"bw_gbps": 68.25,   "typical_ram_gb": 16.0},
    "M2":       {"bw_gbps": 100.0,   "typical_ram_gb": 24.0},
    "M3":       {"bw_gbps": 150.0,   "typical_ram_gb": 36.0},
    "M4":       {"bw_gbps": 273.0,   "typical_ram_gb": 32.0},
    "M1 Ultra": {"bw_gbps": 800.0,   "typical_ram_gb": 128.0},
}

# Default chip for attractor calibration
_DEFAULT_CHIP: str = "M1 Ultra"

# Attractor penalty weight in MCTS value function
_LAMBDA_ATTRACTOR: float = 0.10

# Dimension weights (sum = 1.0)
_W_PHI: float          = 0.30   # Φ (Free Energy Rate Density)
_W_LATENCY: float      = 0.15   # Latency (minimize)
_W_ENTROPY_GAIN: float = 0.25   # Information Entropy Gain (maximize)
_W_MDL: float          = 0.15   # MDL compression (minimize)
_W_EVOLVABILITY: float = 0.15   # Evolvability (maximize)


# ═══════════════════════════════════════════════════════════════
# ATTRACTOR STATE DEFINITION
# ═══════════════════════════════════════════════════════════════

class AttractorState:
    """The Perfect Topological Attractor — the theoretical upper bound.

    Calibrated to the physical hardware to prevent hallucinated targets.
    """

    def __init__(
        self,
        phi_max: float = 1.0,
        latency_min_ms: float = 0.1,
        entropy_gain_max: float = 1.0,
        mdl_min: float = 100.0,
        evolvability_max: float = 1.0,
    ) -> None:
        self.phi_max = phi_max
        self.latency_min_ms = latency_min_ms
        self.entropy_gain_max = entropy_gain_max
        self.mdl_min = mdl_min
        self.evolvability_max = evolvability_max

    @classmethod
    def from_hardware(cls, chip: str = _DEFAULT_CHIP) -> "AttractorState":
        """Calibrate attractor bounds to hardware physics.

        Φ_max is bounded by memory bandwidth and compute density.
        Latency_min is bounded by memory access time (1 / BW * min_tensor_size).
        MDL_min is a theoretical floor based on vocabulary compression.
        """
        spec = _CHIP_SPECS.get(chip, _CHIP_SPECS[_DEFAULT_CHIP])
        bw = spec["bw_gbps"]
        ram = spec["typical_ram_gb"]

        # Φ_max: theoretical max efficiency = BW utilization × compute density
        # Normalized to [0, 1] relative to chip capability
        phi_max = min(1.0, (bw / 800.0) * 0.8 + (ram / 128.0) * 0.2)

        # Latency_min: minimum forward pass for a 1M param model at full BW
        # ~ 4 bytes/param × 1M params / BW = minimum transfer time
        min_bytes = 4e6  # 4 MB (1M params × 4 bytes)
        latency_min_ms = max(0.01, (min_bytes / (bw * 1e9)) * 1000.0)

        # Entropy_gain_max: bounded by vocabulary size and sequence length
        # H_max = log2(512) ≈ 9.0 bits, normalized to 1.0
        entropy_gain_max = 1.0

        # MDL_min: Kolmogorov complexity floor (a transformer block is ~200 LOC)
        mdl_min = 50.0  # bytes per epi unit (theoretical minimum)

        return cls(
            phi_max=phi_max,
            latency_min_ms=latency_min_ms,
            entropy_gain_max=entropy_gain_max,
            mdl_min=mdl_min,
            evolvability_max=1.0,
        )


# ═══════════════════════════════════════════════════════════════
# ORGANISM STATE VECTOR
# ═══════════════════════════════════════════════════════════════

class OrganismState:
    """Current thermodynamic state of the organism.

    Extracted from evaluator telemetry and mutator metrics.
    """

    def __init__(
        self,
        phi: float = 0.0,
        latency_ms: float = 100.0,
        entropy_gain: float = 0.0,
        mdl: float = 10000.0,
        evolvability: float = 0.0,
    ) -> None:
        self.phi = phi
        self.latency_ms = latency_ms
        self.entropy_gain = entropy_gain
        self.mdl = mdl
        self.evolvability = evolvability

    @classmethod
    def from_telemetry(cls, record: Dict[str, Any]) -> "OrganismState":
        """Build organism state from an evaluator telemetry record."""
        best_epi = record.get("best_epi", 0.0)
        evolvability = max(record.get("evolvability_score", 0.01), 0.01)
        phi = best_epi * evolvability

        latency_ms = record.get("tick_time_ms", 130.0)
        entropy_gain = min(1.0, best_epi / 0.80)  # normalize: 0.80 epi = max info gain

        # MDL proxy: if available from MDLTracker
        mdl = record.get("mdl", 5000.0)

        return cls(
            phi=phi,
            latency_ms=latency_ms,
            entropy_gain=entropy_gain,
            mdl=mdl,
            evolvability=evolvability,
        )

    @classmethod
    def from_mcts_node(
        cls,
        projected_phi: float,
        estimated_params: int,
        evolvability: float = 0.5,
    ) -> "OrganismState":
        """Build organism state from an MCTS node's projected values.

        Used during MCTS rollout to estimate the state at a hypothetical
        assembly point.
        """
        # Latency proxy: proportional to param count (linear in FLOPs)
        latency_ms = max(0.5, estimated_params / 1e6 * 10.0)

        # MDL proxy: bytes per epi unit
        est_bytes = estimated_params * 4  # 4 bytes/param
        mdl = est_bytes / max(projected_phi, 1e-6)

        # Entropy gain: proportional to phi
        entropy_gain = min(1.0, projected_phi / 0.5)

        return cls(
            phi=projected_phi,
            latency_ms=latency_ms,
            entropy_gain=entropy_gain,
            mdl=mdl,
            evolvability=evolvability,
        )


# ═══════════════════════════════════════════════════════════════
# DISTANCE-TO-ATTRACTOR COMPUTATION
# ═══════════════════════════════════════════════════════════════

def distance_to_attractor(
    state: OrganismState,
    attractor: AttractorState,
) -> float:
    """Compute the normalized distance from current state to the attractor.

    Returns a value in [0, ∞) where 0 = at the attractor.

    Uses weighted L2 distance with dimension-appropriate normalization:
      - Maximization dims (Φ, entropy_gain, evolvability): (1 - s/A*)²
      - Minimization dims (latency, MDL): (s/A* - 1)²  (clamped at 0 if s < A*)
    """
    # Maximization dimensions: higher is better → (1 - s/A*)², already in [0,1]
    d_phi = (1.0 - min(1.0, state.phi / max(attractor.phi_max, 1e-8))) ** 2
    d_ent = (1.0 - min(1.0, state.entropy_gain / max(attractor.entropy_gain_max, 1e-8))) ** 2
    d_evo = (1.0 - min(1.0, state.evolvability / max(attractor.evolvability_max, 1e-8))) ** 2

    # Minimization dimensions: lower is better
    # Use log-scale normalization to prevent explosion when s >> A*
    # d = tanh(log(s/A*))² → smoothly maps [1, ∞) → [0, 1)
    lat_ratio = state.latency_ms / max(attractor.latency_min_ms, 1e-8)
    d_lat = math.tanh(max(0.0, math.log(max(lat_ratio, 1.0)))) ** 2

    mdl_ratio = state.mdl / max(attractor.mdl_min, 1e-8)
    d_mdl = math.tanh(max(0.0, math.log(max(mdl_ratio, 1.0)))) ** 2

    # Weighted sum — all components now in [0, 1]
    D = (_W_PHI * d_phi +
         _W_LATENCY * d_lat +
         _W_ENTROPY_GAIN * d_ent +
         _W_MDL * d_mdl +
         _W_EVOLVABILITY * d_evo)

    return D


def attractor_penalty(
    state: OrganismState,
    attractor: Optional[AttractorState] = None,
    lambda_attr: float = _LAMBDA_ATTRACTOR,
) -> float:
    """Compute the attractor penalty for MCTS value function integration.

    Returns a NEGATIVE value (penalty) proportional to the distance.
    Add this to the standard MCTS node value:

        V_total = V_base + attractor_penalty(state, attractor)

    The penalty pulls the MCTS toward architectures closer to the attractor.
    """
    if attractor is None:
        attractor = AttractorState.from_hardware()

    D = distance_to_attractor(state, attractor)
    return -lambda_attr * D


def attractor_gradient_direction(
    state: OrganismState,
    attractor: AttractorState,
) -> Dict[str, float]:
    """Compute the gradient direction from current state toward attractor.

    Returns a dict of signed gradients per dimension:
      positive = increase this metric
      negative = decrease this metric

    Useful for injecting teleological bias into the mutation prompt.
    """
    return {
        "phi": max(0.0, attractor.phi_max - state.phi),
        "latency_ms": min(0.0, attractor.latency_min_ms - state.latency_ms),
        "entropy_gain": max(0.0, attractor.entropy_gain_max - state.entropy_gain),
        "mdl": min(0.0, attractor.mdl_min - state.mdl),
        "evolvability": max(0.0, attractor.evolvability_max - state.evolvability),
    }


# ═══════════════════════════════════════════════════════════════
# MCTS VALUE FUNCTION AUGMENTATION
# ═══════════════════════════════════════════════════════════════

def augmented_mcts_value(
    projected_phi: float,
    simulation_delay_ms: float,
    tree_depth: int,
    estimated_params: int,
    max_params: int,
    evolvability: float = 0.5,
    synergy_multiplier: float = 1.0,
    attractor: Optional[AttractorState] = None,
    lambda_tax: float = 0.001,
    lambda_attr: float = _LAMBDA_ATTRACTOR,
) -> float:
    """Compute the full MCTS value with Teleological Attractor integration.

    TICK 20.1 upgrade to genome_assembler.py _compute_phi_value():

        V = projected_phi × synergy
            - λ_tax × (delay_ms + depth × 10)
            + parsimony_bonus
            + attractor_penalty

    The attractor penalty is the new term: it pulls the MCTS toward the
    theoretical perfect state, creating a teleological gradient that
    shortens the evolutionary path.
    """
    # Base value (TICK 17.0 formula)
    base_value = projected_phi * synergy_multiplier

    # Thermodynamic tax (TICK 17.0)
    cost = simulation_delay_ms + tree_depth * 10.0
    tax = lambda_tax * cost

    # Parsimony bonus (TICK 17.0)
    param_ratio = estimated_params / max(max_params, 1)
    parsimony = max(0.0, 1.0 - param_ratio) * 0.05

    # Attractor penalty (TICK 20.1 — NEW)
    org_state = OrganismState.from_mcts_node(
        projected_phi=projected_phi,
        estimated_params=estimated_params,
        evolvability=evolvability,
    )
    if attractor is None:
        attractor = AttractorState.from_hardware()
    attr_pen = attractor_penalty(org_state, attractor, lambda_attr)

    return base_value - tax + parsimony + attr_pen


# ═══════════════════════════════════════════════════════════════
# TELEOLOGICAL PROMPT INJECTION
# ═══════════════════════════════════════════════════════════════

def format_attractor_markdown(
    state: OrganismState,
    attractor: Optional[AttractorState] = None,
) -> str:
    """Format the teleological gradient as Markdown for LLM prompt injection.

    Shows the organism its distance from perfection and the direction to move.
    """
    if attractor is None:
        attractor = AttractorState.from_hardware()

    D = distance_to_attractor(state, attractor)
    grad = attractor_gradient_direction(state, attractor)

    lines = [
        "--- TELEOLOGICAL ATTRACTOR (TICK 20.1: Future-Guided Evolution) ---",
        f"Distance to Perfect State: D = {D:.6f}",
        f"  Φ: current={state.phi:.4f} → target={attractor.phi_max:.4f} "
        f"(Δ={grad['phi']:+.4f})",
        f"  Latency: current={state.latency_ms:.1f}ms → "
        f"target={attractor.latency_min_ms:.3f}ms "
        f"(Δ={grad['latency_ms']:+.1f}ms)",
        f"  Entropy Gain: current={state.entropy_gain:.4f} → "
        f"target={attractor.entropy_gain_max:.4f} "
        f"(Δ={grad['entropy_gain']:+.4f})",
        f"  MDL: current={state.mdl:.0f} → target={attractor.mdl_min:.0f} "
        f"(Δ={grad['mdl']:+.0f})",
        f"  Evolvability: current={state.evolvability:.4f} → "
        f"target={attractor.evolvability_max:.4f} "
        f"(Δ={grad['evolvability']:+.4f})",
        "",
        "The MCTS value function now includes an attractor penalty.",
        "Architectures closer to the attractor are favored even if their",
        "immediate Φ is slightly lower — the shortest path to perfection",
        "is preferred over local hill-climbing.",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def get_default_attractor() -> AttractorState:
    """Return the hardware-calibrated attractor for the current machine."""
    return AttractorState.from_hardware()


def compute_mcts_attractor_value(
    projected_phi: float,
    estimated_params: int,
    evolvability: float = 0.5,
) -> float:
    """Quick attractor penalty computation for MCTS rollout integration.

    Returns the penalty value to ADD to the existing MCTS node value.
    This is the minimal API for genome_assembler.py integration.
    """
    state = OrganismState.from_mcts_node(
        projected_phi=projected_phi,
        estimated_params=estimated_params,
        evolvability=evolvability,
    )
    return attractor_penalty(state)
