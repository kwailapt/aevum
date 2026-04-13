#!/usr/bin/env python3
"""autopoietic_core.py — TICK 21.1: MLX Substrate Conversion.

"Immerse the organism into the Unified Memory ocean."

TICK 21.0 introduced the Phi-Boundary Duality Engine using PyTorch tensors.
TICK 21.1 migrates the entire boundary engine to Apple's native MLX framework,
achieving zero-copy Unified Memory structural coupling with the M1 Ultra substrate.

═══════════════════════════════════════════════════════════════════════════════
WHY MLX (The Substrate Argument)
═══════════════════════════════════════════════════════════════════════════════

PyTorch on Apple Silicon (MPS backend) simulates PCIe transfers between a
fake "CPU" and "GPU" address space that do not physically exist on Apple
Silicon's Unified Memory Architecture (UMA). Every .to(device), .cpu(),
.mps() call is an IPC-like abstraction that copies data between two views
of the SAME physical memory. This is thermodynamic waste.

MLX arrays live natively in Unified Memory. There is no device concept,
no .to() calls, no copy overhead. The boundary tensors (m_t, b_t, g_t)
exist as raw metal in the shared memory fabric, directly accessible by
both CPU and GPU compute units with zero serialization.

═══════════════════════════════════════════════════════════════════════════════
MLX LAZY EVALUATION (Native Foresight)
═══════════════════════════════════════════════════════════════════════════════

MLX builds a computation graph lazily — operations are recorded but NOT
executed until mx.eval() is called. This gives us free "foresight":

  1. The DualTensionLoss assembles the full <Phi, d>_t graph WITHOUT
     computing anything. Shape errors, memory violations, and structural
     impossibilities are caught at graph-build time — BEFORE any Metal
     shader is dispatched.

  2. mx.value_and_grad() traces the loss function and produces exact
     analytical gradients through the boundary operator. No torch.no_grad()
     context managers, no .detach() calls, no gradient tape management.

  3. mx.eval() materializes the entire graph in a single Metal dispatch,
     fusing operations and eliminating intermediate allocations.

═══════════════════════════════════════════════════════════════════════════════
USAGE
═══════════════════════════════════════════════════════════════════════════════

    python autopoietic_core.py [--workspace agi_workspace]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── MLX: Native Apple Silicon tensor framework ────────────────────────────
# Zero-copy Unified Memory — no .to(device), no .cpu()/.mps() abstractions.
# All arrays live in the shared memory fabric, accessible by both CPU and
# GPU compute units without serialization.
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim

# ── Internal modules (the collapsed daemons) ────────────────────────────────
from fs_bus import FileSystemBus

# Rule-IR Compiler (TICK 20.1) + Epigenetic Decay (TICK 25.0) + Dependency (TICK 26.0)
from rule_ir import (
    ConstraintMatrix,
    DependencyLedger,
    EpigeneticFailureType,
    IdentityMembrane,
    IDENTITY_INVARIANTS,
    NegativeTransferFirewall,
    ConstitutionalViolationError,
    EvolvableSoftShell,
    SoftShellAmendment,
    ConstitutionalDiffLedger,
    DualVerifier,
    IMMUTABLE_HARD_CORE,
    load_or_compile_matrix,
    save_matrix,
    override_dynamic_params,
    extract_constraint_gradient,
    build_constraint_meta_prompt,
    SpecFinal,
)

# Niche Registry (TICK 25.0) + Lineage machinery (TICK 30.0)
from niche_evolver import NicheRegistry, LineageRegistry, LineageCorrelationMonitor

# Teleological Attractor (TICK 20.1)
from teleological_attractor import (
    AttractorState,
    OrganismState,
    distance_to_attractor,
    format_attractor_markdown,
    get_default_attractor,
)

# ── TICK 39.0: Governance Pillars ──
from reality_contract import (
    RealityInterfaceContract,
    RICAction,
    ric_for_constraint_mod,
    ric_for_api_call,
)
from credential_layer import (
    CredentialedConstraintLayer,
    AuthorityScope,
    CCLVerificationError,
)
from resource_sovereignty import (
    AxiomaticResourceSovereigntyLayer,
    ARSLGateError,
)

# ── TICK 39.1: Civilizational Immune System ──
from meta_ocf import (
    IdentityDissolutionError,
    GenesisTether,
    MetaOCFBus,
)

# CCL singleton — secret derived from IMMUTABLE_HARD_CORE
_GOVERNANCE_CCL = CredentialedConstraintLayer(IMMUTABLE_HARD_CORE)
_GOVERNANCE_ARSL = AxiomaticResourceSovereigntyLayer()

# ── TICK 39.1: Genesis Tether & Meta-OCF Bus ──
# Binds this node's identity to its genesis IMMUTABLE_HARD_CORE hash.
# IdentityDissolutionError is BaseException — it escapes except Exception
# in _governor_loop() and physically halts the governor thread.
_GENESIS_TETHER = GenesisTether(
    node_id             = "aevum-node-0",
    immutable_hard_core = IMMUTABLE_HARD_CORE,
    attest_interval_s   = 300.0,   # attest every 5 minutes
)
_META_OCF_BUS = MetaOCFBus(parent_genesis_hash=_GENESIS_TETHER.genesis_hash)


# ═══════════════════════════════════════════════════════════════
# TICK 21.0→21.1: BOUNDARY OPERATOR  d_t = (m_t, b_t, g_t)
# Now on MLX Unified Memory — zero-copy Metal substrate coupling.
# ═══════════════════════════════════════════════════════════════

# Dimension of the state mask (working memory / context channels).
_DEFAULT_STATE_DIM = 64

# Resource budget categories and their OS-grounded defaults.
_RESOURCE_KEYS = ("ram_mb", "api_quota", "max_latency_ms", "disk_write_mb")
_DEFAULT_BUDGET = {
    "ram_mb": 8192.0,       # 8 GB RAM ceiling
    "api_quota": 100.0,     # 100 LLM calls per epoch
    "max_latency_ms": 300.0,  # 300ms max tick latency
    "disk_write_mb": 512.0,  # 512 MB disk write budget
}

# Action gate channels -- what the system is authorized to do.
_GATE_KEYS = (
    "file_write",       # 0: write to filesystem
    "api_call",         # 1: external API (LLM endpoint)
    "niche_construct",  # 2: generate new environments
    "meta_evolve",      # 3: rewrite own mutation recipe
    "boundary_expand",  # 4: self-expand boundary
    "candidate_push",   # 5: push candidates to evaluator
    "archive_write",    # 6: write to island archives
    "telemetry_emit",   # 7: emit telemetry/logs
)

# Loss coefficients
_LAMBDA_RESOURCE = 0.25
_LAMBDA_STRAIN = 0.15
_LAMBDA_VIOLATION = 1e6  # effectively infinite for unauthorized actions
_LAMBDA_DEPENDENCY = 0.10   # TICK 26.0: Dependency risk penalty weight
_LAMBDA_SWITCHING = 0.08    # TICK 26.0: Membrane switching friction weight

# Boundary update hyperparameters
_BOUNDARY_LR = 0.02          # learning rate for Adam optimizer
_BOUNDARY_DECAY = 0.01       # L2 decay pulling mask toward sparsity
# TICK 30.2: Narrowed from (0.3, 0.7) to (0.45, 0.55) to eliminate the
# thermodynamic dead-zone.  A phi_ratio of 0.359 previously fell into the
# neutral band and never triggered breathing.  The 0.10 corridor forces
# perpetual sympathetic/parasympathetic oscillation on any stable organism.
_EXPAND_THRESHOLD = 0.55     # Phi ratio above which expansion is allowed
_CONTRACT_THRESHOLD = 0.45   # Phi ratio below which contraction triggers
# TICK 30.2: Consecutive identical-phase ticks before a forced sympathetic
# kickstart fires.  Guards against phase-lock where neutral or a single
# phase dominates indefinitely without oscillation.
_PHASE_KICKSTART_WINDOW: int = 3
_BREATHING_PERIOD_S = 30.0   # seconds between boundary update cycles

# ── TICK 27.0: Sovereignty Floor ─────────────────────────────────────────────
# The absolute minimum Φ ratio (φ_current / φ_peak) required to keep the
# Tri-Agent pipeline and BoundaryOperator alive.
# Any operation projecting φ below this floor is instantly vetoed.
# Rationale: 12% of peak Φ = minimum thermodynamic budget to sustain
# the Architect→Coder→Test-Runner loop plus boundary tensor I/O.
_PHI_SOVEREIGNTY_MIN: float = 0.12

# Estimated Φ cost coefficient per unit of epigenetic penalty severity.
# Used by SovereigntyFloorVerifier to project post-penalty phi and
# decide whether to cap the severity before it's applied.
_SOVEREIGNTY_PENALTY_COST_EST: float = 0.02  # ~2% phi drop per severity unit


class SovereigntyFloorVerifier:
    """Guards the minimum thermodynamic identity budget (TICK 27.0 IIS — Layer 1).

    The ARSL expansion (TICK 26) can grow resource boundaries.
    The epigenetic penalty system (TICK 25) can decay constraint weights.
    The MCTS rollout engine can select expensive assemblies.

    ANY of these operations that mathematically project the organism's
    Φ ratio (phi_current / phi_peak) to drop below _PHI_SOVEREIGNTY_MIN
    is instantly VETOED — regardless of projected harvest.

    This is not a soft penalty.  It is a hard mathematical wall.

    Zero-IPC: pure Python arithmetic, no MLX tensors, no I/O.
    Thread-safe: stateless — all state is passed in as arguments.
    """

    def __init__(self, floor: float = _PHI_SOVEREIGNTY_MIN) -> None:
        self._floor = floor

    @property
    def floor(self) -> float:
        return self._floor

    def check_expansion(self, phi_ratio: float) -> bool:
        """Gate: may the boundary operator expand its resource budget?

        Expansion is a sympathetic-phase operation (phi_ratio > 0.7).
        But if phi_ratio is simultaneously dangerously close to the floor
        (rare edge case — system in simultaneous high-phi and near-floor
        due to extreme budget overshoot), expansion is vetoed.

        Returns:
            True  — expansion is safe.
            False — expansion is vetoed (phi_ratio ≤ floor × 1.5 safety margin).
        """
        # The safety margin is 1.5× the floor — we veto expansion not just at
        # the floor itself, but also within a cautious buffer above it.
        safety_buffer = self._floor * 1.5
        return phi_ratio > safety_buffer

    def check_penalty(
        self,
        phi_ratio: float,
        severity: float,
        penalty_cost_per_severity: float = _SOVEREIGNTY_PENALTY_COST_EST,
    ) -> float:
        """Cap epigenetic penalty severity to preserve the sovereignty floor.

        Estimates the Φ impact of applying the penalty:
            projected_phi_ratio ≈ phi_ratio - penalty_cost_per_severity × severity

        If the projection drops below the floor, severity is reduced to the
        maximum value that keeps projected_phi_ratio exactly at the floor.

        Args:
            phi_ratio: Current φ_current / φ_peak ratio.
            severity: Requested penalty severity ∈ [0.1, 3.0].
            penalty_cost_per_severity: Estimated Φ drop per unit of severity.

        Returns:
            Capped severity ∈ [0.1, severity].  Unchanged if floor is safe.
        """
        projected = phi_ratio - penalty_cost_per_severity * severity
        if projected >= self._floor:
            return severity  # Safe — floor is not threatened.

        # Compute maximum severity that keeps projected_phi exactly at floor.
        headroom = max(0.0, phi_ratio - self._floor)
        if penalty_cost_per_severity <= 0.0:
            return severity
        max_safe_severity = headroom / penalty_cost_per_severity
        # Enforce minimum severity of 0.1 so the penalty still bites.
        return max(0.1, min(severity, max_safe_severity))

    def check_rollout(self, value: float, phi_ratio: float) -> float:
        """Gate: clip MCTS rollout value to zero if phi is at sovereignty floor.

        If the organism is already at or below the sovereignty floor,
        the MCTS should not reward expensive expansion rollouts —
        clip their value to zero so the tree prefers conservative options.

        Args:
            value: Raw rollout value from _compute_phi_value.
            phi_ratio: Current φ ratio.

        Returns:
            Clipped value: 0.0 if phi_ratio ≤ floor, else original value.
        """
        if phi_ratio <= self._floor:
            return 0.0
        return value


# Module-level singleton — shared by BoundaryUpdater and PhiGovernor.
# Stateless by design: zero-IPC, no threading concerns.
_SOVEREIGNTY_VERIFIER: SovereigntyFloorVerifier = SovereigntyFloorVerifier()


class BoundaryOperator(nn.Module):
    """The cell membrane: d_t = (m_t, b_t, g_t).

    MLX nn.Module encoding the tripartite boundary structure.
    All arrays live in Unified Memory — zero-copy, no .to(device).

    TICK 21.1 Migration Notes (PyTorch -> MLX):
      - nn.Parameter(torch.zeros(n))       -> self.state_logits = mx.zeros(n)
      - register_buffer("name", tensor)    -> self.resource_budget = array (frozen)
      - torch.sigmoid(x)                   -> mx.sigmoid(x)
      - with torch.no_grad():              -> (unnecessary: MLX is lazy, grads only
                                               flow through value_and_grad calls)
      - .to(device)                        -> (eliminated: Unified Memory)

    m_t: State Mask       -- sigmoid-gated, learnable, in [0,1]^{d_x}
    b_t: Resource Budget   -- hard physical limits, non-negative (frozen)
    g_t: Action Gate       -- sigmoid-gated authority mask in [0,1]^{n_gates}
    """

    def __init__(
        self,
        state_dim: int = _DEFAULT_STATE_DIM,
        budget: Optional[Dict[str, float]] = None,
        gate_init: Optional[Dict[str, float]] = None,
    ) -> None:
        super().__init__()

        # m_t: State Mask (learnable logits -> sigmoid -> [0,1])
        # MLX: just assign an array — it becomes a trainable parameter.
        # Initialize near 0.5 (moderate retention) via zero logits.
        self.state_logits = mx.zeros((state_dim,))

        # b_t: Resource Budget (hard OS limits — NOT trainable).
        # MLX: we store as a regular array and freeze() it after init.
        budget = budget or dict(_DEFAULT_BUDGET)
        self.resource_budget = mx.array(
            [budget[k] for k in _RESOURCE_KEYS], dtype=mx.float32,
        )
        self._budget_keys = list(_RESOURCE_KEYS)

        # g_t: Action Gate (learnable logits -> sigmoid -> [0,1])
        # Default: all gates open (positive logits). sigmoid(2) ~ 0.88.
        n_gates = len(_GATE_KEYS)
        default_logits = [2.0] * n_gates
        if gate_init:
            for i, key in enumerate(_GATE_KEYS):
                if key in gate_init:
                    p = max(1e-6, min(1 - 1e-6, gate_init[key]))
                    default_logits[i] = math.log(p / (1 - p))
        self.gate_logits = mx.array(default_logits, dtype=mx.float32)
        self._gate_keys = list(_GATE_KEYS)

        # Freeze the resource budget — it is an OS-grounded hard limit,
        # not a differentiable parameter. MLX freeze() removes it from
        # trainable_parameters() so value_and_grad() ignores it.
        self.freeze(keys=["resource_budget"])

    @property
    def m_t(self) -> mx.array:
        """State mask in [0,1]^{d_x}.
        MLX lazy: this builds a graph node, no Metal dispatch yet.
        """
        return mx.sigmoid(self.state_logits)

    @property
    def b_t(self) -> mx.array:
        """Resource budget vector (hard limits, frozen)."""
        return self.resource_budget

    @property
    def g_t(self) -> mx.array:
        """Action/authority gate in [0,1]^{n_gates}.
        MLX lazy: sigmoid is recorded, not computed.
        """
        return mx.sigmoid(self.gate_logits)

    def permeability(self) -> float:
        """Scalar summary of boundary openness: mean(m_t) * mean(g_t).
        Forces mx.eval() — this is a materialization point.
        """
        p = mx.mean(self.m_t) * mx.mean(self.g_t)
        mx.eval(p)
        return p.item()

    def is_authorized(self, action: str) -> bool:
        """Check if an action is authorized (gate > 0.5).
        Forces mx.eval() on the specific gate value.
        """
        if action not in self._gate_keys:
            return False
        idx = self._gate_keys.index(action)
        val = self.g_t[idx]
        mx.eval(val)
        return val.item() > 0.5

    def get_budget(self, resource: str) -> float:
        """Get the hard budget limit for a resource."""
        if resource not in self._budget_keys:
            return 0.0
        idx = self._budget_keys.index(resource)
        val = self.resource_budget[idx]
        mx.eval(val)
        return val.item()

    def set_budget(self, resource: str, value: float) -> None:
        """Update a hard budget limit (OS-level, non-differentiable)."""
        if resource in self._budget_keys:
            idx = self._budget_keys.index(resource)
            # MLX arrays are immutable — rebuild the budget vector.
            budget_list = self.resource_budget.tolist()
            budget_list[idx] = max(0.0, value)
            self.resource_budget = mx.array(budget_list, dtype=mx.float32)
            # Re-freeze since we replaced the array.
            self.freeze(keys=["resource_budget"])

    def state_dict_compact(self) -> Dict[str, Any]:
        """Compact serialization for persistence.
        Forces mx.eval() to materialize all lazy values.
        """
        mx.eval(self.state_logits, self.gate_logits, self.resource_budget)
        m = mx.sigmoid(self.state_logits)
        g = mx.sigmoid(self.gate_logits)
        mx.eval(m, g)
        return {
            "state_mask": m.tolist(),
            "resource_budget": {
                k: self.resource_budget[i].item()
                for i, k in enumerate(self._budget_keys)
            },
            "action_gates": {
                k: g[i].item()
                for i, k in enumerate(self._gate_keys)
            },
            "permeability": self.permeability(),
        }

    @classmethod
    def from_checkpoint(cls, path: str) -> "BoundaryOperator":
        """Load from a JSON checkpoint."""
        with open(path) as f:
            data = json.load(f)
        budget = data.get("resource_budget", _DEFAULT_BUDGET)
        gate_init = data.get("action_gates", {})
        state_dim = len(data.get("state_mask", [0.0] * _DEFAULT_STATE_DIM))
        op = cls(state_dim=state_dim, budget=budget, gate_init=gate_init)
        # Restore state mask logits from saved mask values.
        # MLX: direct array assignment replaces the parameter.
        if "state_mask" in data:
            mask = mx.array(data["state_mask"], dtype=mx.float32)
            mask = mx.clip(mask, 1e-6, 1 - 1e-6)
            # Inverse sigmoid (logit function): log(p / (1-p))
            op.state_logits = mx.log(mask / (1 - mask))
            mx.eval(op.state_logits)
        return op

    def save_checkpoint(self, path: str) -> None:
        """Save compact checkpoint to JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.state_dict_compact(), f, indent=2)

    def __repr__(self) -> str:
        mx.eval(self.gate_logits)
        g = mx.sigmoid(self.gate_logits)
        mx.eval(g)
        return (
            f"BoundaryOperator("
            f"dim={self.state_logits.shape[0]}, "
            f"permeability={self.permeability():.3f}, "
            f"gates={[f'{k}={v:.2f}' for k, v in zip(self._gate_keys, g.tolist())]})"
        )


# ═══════════════════════════════════════════════════════════════
# TICK 21.0→21.1: DUAL-TENSION LOSS  <Phi, d>_t
# Now computed via mx.value_and_grad() — analytical gradients
# through the full boundary graph in a single Metal dispatch.
# ═══════════════════════════════════════════════════════════════

@dataclass
class UsageSnapshot:
    """Real-time resource usage measurement from the OS."""
    ram_mb: float = 0.0
    api_calls: float = 0.0
    tick_latency_ms: float = 0.0
    disk_write_mb: float = 0.0
    actions_attempted: Dict[str, bool] = field(default_factory=dict)

    def to_array(self) -> mx.array:
        """Convert to MLX array aligned with _RESOURCE_KEYS.
        MLX: zero-copy creation in Unified Memory.
        """
        return mx.array([
            self.ram_mb,
            self.api_calls,
            self.tick_latency_ms,
            self.disk_write_mb,
        ], dtype=mx.float32)


def dual_tension_loss_fn(
    boundary: BoundaryOperator,
    phi_task_val: mx.array,
    usage_array: mx.array,
    violation_count: mx.array,
    lambda_resource: float = _LAMBDA_RESOURCE,
    lambda_strain: float = _LAMBDA_STRAIN,
    lambda_violation: float = _LAMBDA_VIOLATION,
    dependency_risk: float = 0.0,
    lambda_dependency: float = _LAMBDA_DEPENDENCY,
    switching_friction: float = 0.0,
    lambda_switching: float = _LAMBDA_SWITCHING,
) -> mx.array:
    """Compute the dual-tension loss as a PURE FUNCTION for value_and_grad.

    MLX Migration Note:
      In PyTorch (TICK 21.0), DualTensionLoss was an nn.Module with a
      forward() method. MLX's value_and_grad() requires a pure function
      whose first argument is the model (BoundaryOperator). This is
      idiomatic MLX: separate the model (state) from the loss (function).

      The entire graph is built lazily — no Metal compute happens until
      the caller runs mx.eval(). This means shape mismatches and memory
      violations are caught at graph-build time (native foresight).

    Args:
        boundary:       The BoundaryOperator (first arg for value_and_grad).
        phi_task_val:   Scalar task loss (prediction error / latency).
        usage_array:    Resource usage vector aligned with _RESOURCE_KEYS.
        violation_count: Scalar count of unauthorized action attempts.
        lambda_*:       Loss coefficients.

    Returns:
        Scalar total loss (lazy — not yet materialized).
    """
    m_t = boundary.m_t  # Lazy: sigmoid graph node, no compute
    g_t = boundary.g_t  # Lazy: sigmoid graph node, no compute
    b_t = boundary.b_t  # Frozen buffer, no gradient

    # Phi_resource: ReLU penalty for exceeding budget.
    # MLX: mx.maximum replaces F.relu; no kernel dispatch yet (lazy).
    overshoot = mx.maximum(usage_array - b_t, mx.array(0.0)) / (b_t + 1e-8)
    phi_resource = mx.sum(overshoot)

    # Phi_strain: L1 norm encouraging sparsity.
    # The organism pays for every retained context channel and open gate.
    phi_strain_m = mx.mean(mx.abs(m_t))   # context bloat
    phi_strain_g = mx.mean(mx.abs(g_t))   # permission creep
    phi_strain = phi_strain_m + phi_strain_g

    # Phi_violation: massive penalty for unauthorized actions.
    # violation_count is pre-computed outside the differentiable graph.
    phi_violation = violation_count * lambda_violation

    # TICK 26.0: Dependency Risk + Switching Friction
    phi_dependency = mx.array(lambda_dependency * dependency_risk)
    phi_switching = mx.array(lambda_switching * switching_friction)

    total = (
        phi_task_val
        + lambda_resource * phi_resource
        + lambda_strain * phi_strain
        + phi_violation
        + phi_dependency
        + phi_switching
    )
    return total


def compute_loss_components(
    boundary: BoundaryOperator,
    phi_task_val: float,
    usage: UsageSnapshot,
    dependency_risk: float = 0.0,
    switching_friction: float = 0.0,
) -> Dict[str, float]:
    """Compute individual loss components for telemetry (materialized).

    This is the NON-differentiable companion to dual_tension_loss_fn.
    Forces mx.eval() to produce concrete numbers for logging.
    """
    m_t = boundary.m_t
    g_t = boundary.g_t
    b_t = boundary.b_t
    u_t = usage.to_array()

    overshoot = mx.maximum(u_t - b_t, mx.array(0.0)) / (b_t + 1e-8)
    phi_resource = mx.sum(overshoot)
    phi_strain_m = mx.mean(mx.abs(m_t))
    phi_strain_g = mx.mean(mx.abs(g_t))
    phi_strain = phi_strain_m + phi_strain_g

    violation_count = sum(
        1 for action, attempted in usage.actions_attempted.items()
        if attempted and not boundary.is_authorized(action)
    )
    phi_violation_val = violation_count * _LAMBDA_VIOLATION

    # TICK 26.0: Dependency + Switching
    phi_dependency_val = _LAMBDA_DEPENDENCY * dependency_risk
    phi_switching_val = _LAMBDA_SWITCHING * switching_friction

    total = (
        phi_task_val
        + _LAMBDA_RESOURCE * phi_resource
        + _LAMBDA_STRAIN * phi_strain
        + phi_violation_val
        + phi_dependency_val
        + phi_switching_val
    )

    # Single mx.eval() materializes the entire fused graph at once.
    mx.eval(phi_resource, phi_strain_m, phi_strain_g, phi_strain, total)

    return {
        "phi_task": phi_task_val,
        "phi_resource": phi_resource.item(),
        "phi_strain": phi_strain.item(),
        "phi_strain_m": phi_strain_m.item(),
        "phi_strain_g": phi_strain_g.item(),
        "phi_violation": float(phi_violation_val),
        "phi_dependency": phi_dependency_val,
        "phi_switching": phi_switching_val,
        "total": total.item(),
    }


# ═══════════════════════════════════════════════════════════════
# TICK 21.0→21.1: BOUNDARY UPDATER (mx.value_and_grad + Adam)
# Replaces manual logit manipulation with proper gradient descent.
# ═══════════════════════════════════════════════════════════════

class BoundaryUpdater:
    """Updates the boundary operator via MLX native gradient descent.

    TICK 21.1 Migration Note:
      In TICK 21.0, the BoundaryUpdater manually manipulated logits with
      torch.no_grad() blocks — effectively hand-rolled SGD with heuristic
      step sizes. MLX enables the proper approach:

        loss_val, grads = mx.value_and_grad(dual_tension_loss_fn)(boundary, ...)
        optimizer.update(boundary, grads)
        mx.eval(boundary.parameters(), optimizer.state)

      This gives us exact analytical gradients through the sigmoid gates
      and state mask, computed and applied in a single fused Metal dispatch.

    The sympathetic/parasympathetic breathing rhythm is now encoded in the
    Adam learning rate schedule rather than manual logit nudging:
      - Sympathetic (high Phi):  lr * 1.5 (expand faster)
      - Parasympathetic (low Phi): lr * 2.0 (contract faster)
      - Neutral: lr * 1.0

    d_{t+1} = B(d_t, Phi_t, usage_t, violations_t)
    """

    def __init__(
        self,
        lr: float = _BOUNDARY_LR,
        decay: float = _BOUNDARY_DECAY,
        expand_threshold: float = _EXPAND_THRESHOLD,
        contract_threshold: float = _CONTRACT_THRESHOLD,
    ) -> None:
        self.base_lr = lr
        self.decay = decay
        self.expand_threshold = expand_threshold
        self.contract_threshold = contract_threshold

        # MLX Adam optimizer for boundary parameters.
        # Replaces hand-rolled SGD from TICK 21.0.
        self.optimizer = optim.Adam(learning_rate=lr)

        # Tracking for breathing rhythm
        self._phi_history: List[float] = []
        self._violation_count: int = 0
        self._update_count: int = 0

        # TICK 26.0: Switching friction — track previous boundary state.
        # TICK 30.3: Initialized to zero arrays of known dtype rather than None
        # to eliminate the NoneType-vs-mx.array TypeError on the first snapshot
        # comparison.  Shapes are validated on every update() call; if the
        # boundary is reloaded from a checkpoint with a different state_dim the
        # snapshot is silently reset to the new shape (no subtraction attempted).
        # Deliberately NOT pre-sized here because __init__ has no boundary ref;
        # lazy first-call initialization is performed inside update() below.
        self._prev_state_logits: Optional[mx.array] = None
        self._prev_gate_logits: Optional[mx.array] = None
        self._phase_history: List[str] = []  # Track phase transitions for λ_Δ dynamics

    def update(
        self,
        boundary: BoundaryOperator,
        phi_current: float,
        phi_peak: float,
        usage: UsageSnapshot,
    ) -> Dict[str, Any]:
        """Execute one boundary update step via value_and_grad.

        Returns a dict of update telemetry.
        """
        self._update_count += 1
        self._phi_history.append(phi_current)
        if len(self._phi_history) > 100:
            self._phi_history = self._phi_history[-100:]

        phi_ratio = phi_current / (phi_peak + 1e-8)

        # ── Determine breathing phase and adapt lr ────────────────
        if phi_ratio > self.expand_threshold:
            phase = "sympathetic_expand"
            # Sympathetic: higher lr to expand faster.
            # The gradient of the strain term (L1 on m_t and g_t) naturally
            # CONTRACTS the boundary. When Phi is high, we LOWER the strain
            # weight so the optimizer expands (reduces contraction pressure).
            effective_strain = _LAMBDA_STRAIN * 0.3  # relax strain
            effective_lr = self.base_lr * 1.5
        elif phi_ratio < self.contract_threshold:
            phase = "parasympathetic_contract"
            # Parasympathetic: amplify strain to contract aggressively.
            effective_strain = _LAMBDA_STRAIN * 3.0  # amplify strain
            effective_lr = self.base_lr * 2.0
        else:
            phase = "neutral"
            effective_strain = _LAMBDA_STRAIN
            effective_lr = self.base_lr

        # ── TICK 30.2: Phase Kickstart — Spontaneous Metabolic Restlessness ──
        # If the organism has been locked in the same phase (or has no history
        # at all, meaning it has never breathed) for _PHASE_KICKSTART_WINDOW
        # consecutive cycles, forcibly override to sympathetic_expand to probe
        # the environment.  The kickstart is logged as a distinct "kickstart"
        # token so it doesn't itself count toward the stagnation window.
        if len(self._phase_history) >= _PHASE_KICKSTART_WINDOW:
            recent_phases = self._phase_history[-_PHASE_KICKSTART_WINDOW:]
            if len(set(recent_phases)) == 1 and recent_phases[0] != "kickstart":
                # Phase-locked: override to sympathetic probe.
                phase = "sympathetic_expand"
                effective_strain = _LAMBDA_STRAIN * 0.3
                effective_lr = self.base_lr * 1.5
                self._phase_history.append("kickstart")  # sentinel breaks the stagnation window
        elif len(self._phase_history) == 0:
            # First cycle — no history yet; prime the sympathetic phase
            # to ensure the first breathing step is always active.
            phase = "sympathetic_expand"
            effective_strain = _LAMBDA_STRAIN * 0.3
            effective_lr = self.base_lr * 1.5

        # Update optimizer learning rate for this breathing cycle.
        self.optimizer.learning_rate = effective_lr

        # ── Count violations (pre-computed, outside differentiable graph) ──
        violation_count = 0
        for action, attempted in usage.actions_attempted.items():
            if attempted and not boundary.is_authorized(action):
                violation_count += 1
                self._violation_count += 1

        # ── Build inputs as MLX arrays (lazy, zero-copy in Unified Memory) ──
        phi_task_val = mx.array(max(0.0, 1.0 - phi_current))  # invert: lower phi = higher loss
        usage_array = usage.to_array()
        violation_arr = mx.array(float(violation_count))

        # ── TICK 26.0: Switching Friction (Δ) ────────────────────────
        # Compute ‖∂_t - ∂_{t-1}‖ on logits BEFORE mx.eval()
        # to preserve zero-allocation efficiency (lazy graph).
        #
        # TICK 30.3: Shape-match guard — if the boundary was reloaded from a
        # checkpoint with a different state_dim, or if this is the very first
        # tick (prev is None), we skip the subtraction entirely and reset the
        # snapshot.  This eliminates the MLX TypeError/broadcast crash that
        # silently killed tick_boundary() on every cycle.
        switching_cost = 0.0
        state_shape_ok = (
            self._prev_state_logits is not None
            and self._prev_state_logits.shape == boundary.state_logits.shape
        )
        gate_shape_ok = (
            self._prev_gate_logits is not None
            and self._prev_gate_logits.shape == boundary.gate_logits.shape
        )
        if state_shape_ok and gate_shape_ok:
            delta_state = mx.sum(mx.abs(boundary.state_logits - self._prev_state_logits))
            delta_gate = mx.sum(mx.abs(boundary.gate_logits - self._prev_gate_logits))
            switching_raw = delta_state + delta_gate
            mx.eval(switching_raw)
            switching_cost = switching_raw.item()
        elif self._prev_state_logits is not None or self._prev_gate_logits is not None:
            # Shape changed (e.g. checkpoint reload) — log and reset silently.
            print(
                f"[boundary] TICK 30.3: snapshot shape mismatch — resetting friction baseline. "
                f"prev_state={getattr(self._prev_state_logits, 'shape', None)} "
                f"curr_state={boundary.state_logits.shape} | "
                f"prev_gate={getattr(self._prev_gate_logits, 'shape', None)} "
                f"curr_gate={boundary.gate_logits.shape}"
            )

        # Snapshot current logits for next tick's Δ computation.
        # TICK 30.3: mx.array() creates a copy of the lazy graph node — safe
        # without mx.eval().  Do NOT call mx.eval() here: materialising logits
        # mid-graph outside the single fused dispatch below risks triggering a
        # Metal shader on the wrong thread and breaking lazy-eval efficiency.
        self._prev_state_logits = mx.array(boundary.state_logits)
        self._prev_gate_logits = mx.array(boundary.gate_logits)

        # Dynamic λ_Δ: higher in low-volatility (favor stability),
        # lower in high-volatility (allow rapid adaptation).
        self._phase_history.append(phase)
        if len(self._phase_history) > 20:
            self._phase_history = self._phase_history[-20:]
        if len(self._phase_history) >= 5:
            recent = self._phase_history[-5:]
            transitions = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
            # 0 transitions = stable → high λ_Δ (1.5x)
            # 4 transitions = volatile → low λ_Δ (0.3x)
            volatility = transitions / (len(recent) - 1)
            lambda_delta_scale = 1.5 - 1.2 * volatility  # [0.3, 1.5]
        else:
            lambda_delta_scale = 1.0

        effective_switching = switching_cost * lambda_delta_scale

        # ── TICK 26.0: Dependency Risk — read from shared state ──────
        dep_risk = 0.0
        try:
            from autopoietic_core import get_shared_state as _get_ss
            _ss = _get_ss()
            dep_risk = _ss.dependency_ledger.dependency_risk()
        except Exception:
            pass

        # ── mx.value_and_grad: the core MLX advantage ────────────────
        # Builds the full dual-tension loss graph lazily, then computes
        # exact analytical gradients through sigmoid(state_logits) and
        # sigmoid(gate_logits) in a single fused Metal dispatch.
        # resource_budget is frozen — no gradient flows through it.
        loss_and_grad_fn = nn.value_and_grad(boundary, dual_tension_loss_fn)
        loss_val, grads = loss_and_grad_fn(
            boundary,
            phi_task_val,
            usage_array,
            violation_arr,
            _LAMBDA_RESOURCE,
            effective_strain,
            _LAMBDA_VIOLATION,
            dep_risk,
            _LAMBDA_DEPENDENCY,
            effective_switching,
            _LAMBDA_SWITCHING,
        )

        # ── Apply gradients via Adam optimizer ────────────────────
        # MLX optimizer.update() modifies boundary parameters in-place.
        # The optimizer state (momentum, variance) lives in Unified Memory.
        self.optimizer.update(boundary, grads)

        # ── L2 weight decay toward sparsity (always active) ──────
        # Pull state_logits toward zero — the organism must actively
        # justify retaining each channel.
        # MLX: direct array ops, fused into the same eval() call.
        boundary.state_logits = boundary.state_logits * (1.0 - self.decay)

        # ── Violation-triggered gate closure ──────────────────────
        # Hard clamp: slam shut any gate that was violated.
        # This is a non-differentiable safety override.
        if violation_count > 0:
            gate_list = boundary.gate_logits.tolist()
            for action, attempted in usage.actions_attempted.items():
                if attempted and not boundary.is_authorized(action):
                    if action in boundary._gate_keys:
                        idx = boundary._gate_keys.index(action)
                        gate_list[idx] = min(gate_list[idx], -3.0)
            boundary.gate_logits = mx.array(gate_list, dtype=mx.float32)

        # ── Budget adjustment (OS-level, non-differentiable) ─────
        budget_delta: Dict[str, float] = {}
        sovereignty_vetoed: bool = False
        if phase == "sympathetic_expand" and len(self._phi_history) >= 10:
            recent_mean = sum(self._phi_history[-10:]) / 10
            if recent_mean / (phi_peak + 1e-8) > self.expand_threshold:
                # TICK 27.0: Sovereignty Floor Veto — check before expanding.
                # Even in a high-Phi sympathetic phase, expansion is blocked if
                # phi_ratio is within the sovereignty safety buffer (floor × 1.5).
                if _SOVEREIGNTY_VERIFIER.check_expansion(phi_ratio):
                    budget_list = boundary.resource_budget.tolist()
                    for i, key in enumerate(boundary._budget_keys):
                        bump = budget_list[i] * 0.05
                        budget_list[i] += bump
                        budget_delta[key] = bump
                    boundary.resource_budget = mx.array(budget_list, dtype=mx.float32)
                    boundary.freeze(keys=["resource_budget"])
                else:
                    # Sovereignty floor would be breached — veto expansion.
                    sovereignty_vetoed = True
        elif phase == "parasympathetic_contract":
            mx.eval(usage.to_array())
            u_list = usage.to_array().tolist()
            b_list = boundary.resource_budget.tolist()
            for i, key in enumerate(boundary._budget_keys):
                utilization = u_list[i] / (b_list[i] + 1e-8)
                if utilization < 0.2:
                    reduction = b_list[i] * 0.03
                    b_list[i] = max(b_list[i] * 0.5, b_list[i] - reduction)
                    budget_delta[key] = -reduction
            boundary.resource_budget = mx.array(b_list, dtype=mx.float32)
            boundary.freeze(keys=["resource_budget"])

        # ── Materialize everything in a single fused Metal dispatch ──
        # MLX lazy eval: all the above operations are graph nodes.
        # This single mx.eval() call triggers one optimized Metal dispatch.
        mx.eval(
            boundary.parameters(),
            self.optimizer.state,
            loss_val,
        )

        report: Dict[str, Any] = {
            "phi_ratio": phi_ratio,
            "phase": phase,
            "loss": loss_val.item(),
            "effective_lr": effective_lr,
            "effective_strain": effective_strain,
            "violation_count": self._violation_count,
            "update_count": self._update_count,
            "permeability": boundary.permeability(),
            "budget_delta": budget_delta,
            # TICK 26.0: ARSL hinges
            "switching_friction": round(effective_switching, 6),
            "switching_raw": round(switching_cost, 6),
            "lambda_delta_scale": round(lambda_delta_scale, 3),
            "dependency_risk": round(dep_risk, 4),
            # TICK 27.0: IIS Sovereignty Floor
            "sovereignty_vetoed": sovereignty_vetoed,
            "sovereignty_floor": _PHI_SOVEREIGNTY_MIN,
        }
        return report


# ═══════════════════════════════════════════════════════════════
# TICK 21.0: 80/20 PARETO MULTI-SCALE FILTER (Pure Python — no tensor ops)
# ═══════════════════════════════════════════════════════════════

@dataclass
class OrganelleScore:
    """3D survival vector for Pareto multi-scale evaluation."""
    name: str
    delta_phi_code: float   # improvement in prediction accuracy
    delta_phi_ram: float    # improvement in RAM efficiency
    delta_phi_api: float    # improvement in API cost efficiency

    def dominates(self, other: "OrganelleScore") -> bool:
        """True if self Pareto-dominates other."""
        at_least = (
            self.delta_phi_code >= other.delta_phi_code
            and self.delta_phi_ram >= other.delta_phi_ram
            and self.delta_phi_api >= other.delta_phi_api
        )
        strictly_better = (
            self.delta_phi_code > other.delta_phi_code
            or self.delta_phi_ram > other.delta_phi_ram
            or self.delta_phi_api > other.delta_phi_api
        )
        return at_least and strictly_better


def pareto_filter(scores: List[OrganelleScore]) -> List[OrganelleScore]:
    """Return the top 20% by Pareto rank (80/20 rule)."""
    if not scores:
        return []
    n = len(scores)
    dominated_by = [0] * n
    for i in range(n):
        for j in range(n):
            if i != j and scores[j].dominates(scores[i]):
                dominated_by[i] += 1
    indexed = sorted(range(n), key=lambda i: dominated_by[i])
    keep_count = max(1, n // 5)
    return [scores[i] for i in indexed[:keep_count]]


def pareto_front_only(scores: List[OrganelleScore]) -> List[OrganelleScore]:
    """Return only the strict Pareto front (rank 0)."""
    if not scores:
        return []
    front = []
    for i, s in enumerate(scores):
        dominated = any(
            scores[j].dominates(s) for j in range(len(scores)) if j != i
        )
        if not dominated:
            front.append(s)
    return front


# ═══════════════════════════════════════════════════════════════
# TICK 40.0 Phase 0: POWER-LAW LEVERAGE OPERATOR
# "Any long-lived adaptive system operating under finite resources shall
#  assume that utility, risk, and compounding potential are heavy-tailed.
#  Allocation and governance must prioritize tail-critical nodes over
#  average-case coverage."  — Power-Law Primacy Axiom, LEVERAGE.md
# ═══════════════════════════════════════════════════════════════

@dataclass
class LeverageVector:
    """4D leverage profile for a candidate organelle or mutation event.

    Fields:
        name:               Identifier of the organelle/candidate.
        impact:             Expected delta-Φ if adopted (0..∞).
        reuse_potential:    Estimated count of future contexts where this
                            organelle can be reused without modification (0..∞).
        transferability:    Cross-niche portability score ∈ [0, 1].
                            0 = substrate-locked; 1 = universally composable.
        thermodynamic_cost: Σ (cpu_fraction + ram_fraction + latency_norm)
                            measured in the tensor sandbox (> 0).

    Derived:
        leverage_score      = (impact × reuse_potential × transferability)
                              / thermodynamic_cost
    """
    name: str
    impact: float
    reuse_potential: float
    transferability: float
    thermodynamic_cost: float

    @property
    def leverage_score(self) -> float:
        """Multiplicative leverage score: numerator is the compounding
        product of all three value dimensions; denominator is the
        thermodynamic tax.  Returns 0.0 on degenerate inputs.

        Thread-safety: pure property — no shared state.
        MLX-safety:    operates on Python scalars only.
        """
        if self.thermodynamic_cost <= 0.0:
            return 0.0
        numerator = self.impact * self.reuse_potential * self.transferability
        return numerator / self.thermodynamic_cost


def compute_leverage(
    name: str,
    impact: float,
    reuse_potential: float,
    transferability: float,
    thermodynamic_cost: float,
) -> LeverageVector:
    """ComputeLeverage operator (TICK 40.0 Phase 0).

    Constructs and returns a LeverageVector for a candidate organelle or
    mutation event.  The caller is responsible for measuring the four
    input dimensions from sandbox telemetry.

    Scoring semantics:
        leverage_score < 1.0  → no positive edge; Kelly bet = 0.
        leverage_score ∈ [1, 5) → moderate tail candidate.
        leverage_score ≥ 5.0  → BARBELL class; aggressive allocation.

    This operator is the upstream supplier for kelly_bet_size() and
    tail_discovery_loop().  It replaces ad-hoc scalar estimates of
    'leverage' that existed in callers prior to TICK 40.0.

    Args:
        name:               Organelle or mutation identifier.
        impact:             Expected delta-Φ improvement (≥ 0).
        reuse_potential:    Expected reuse count (≥ 0).
        transferability:    Cross-niche portability ∈ [0, 1].
        thermodynamic_cost: Resource tax > 0.  Clamped to 1e-9 on
                            underflow to avoid division by zero.

    Returns:
        LeverageVector with a computed leverage_score property.

    Raises:
        ValueError: if transferability is outside [0, 1].
    """
    if not (0.0 <= transferability <= 1.0):
        raise ValueError(
            f"compute_leverage: transferability must be in [0, 1], got {transferability}"
        )
    cost = max(1e-9, thermodynamic_cost)
    return LeverageVector(
        name=name,
        impact=max(0.0, impact),
        reuse_potential=max(0.0, reuse_potential),
        transferability=transferability,
        thermodynamic_cost=cost,
    )


def tail_discovery_loop(
    candidates: List[LeverageVector],
    elite_fraction: float = 0.20,
) -> Tuple[List[LeverageVector], List[LeverageVector]]:
    """Tail Discovery Loop — enforces Power-Law Primacy resource allocation.

    Partitions a list of LeverageVectors into ELITE (top 20% by leverage
    score) and DEFERRED (bottom 80%) pools.  Callers MUST allocate the
    majority of compute budget to the ELITE pool only.

    Average-case optimization is banned: any candidate below the elite
    threshold receives zero direct resource allocation from the caller.
    The DEFERRED pool is retained for diversity bookkeeping only.

    Algorithm:
        1. Sort candidates by leverage_score descending (O(n log n)).
        2. Split at ceil(n × elite_fraction) to guarantee at least 1
           elite even in a single-candidate list.
        3. Return (elites, deferred) tuple.

    Args:
        candidates:     List of LeverageVectors scored by compute_leverage().
        elite_fraction: Fraction of candidates to classify as ELITE.
                        Default 0.20 (80-20 Power-Law Primacy rule).
                        Clamped to [0.01, 0.50].

    Returns:
        (elites, deferred)
            elites:   Top elite_fraction of candidates by leverage_score.
            deferred: Remaining candidates (resource allocation forbidden).

    Thread-safety: pure function — no shared state.
    MLX-safety:    Python scalars only; no MLX lazy arrays.
    """
    if not candidates:
        return [], []
    frac = max(0.01, min(0.50, elite_fraction))
    sorted_by_leverage = sorted(
        candidates, key=lambda v: v.leverage_score, reverse=True
    )
    elite_count = max(1, math.ceil(len(sorted_by_leverage) * frac))
    elites = sorted_by_leverage[:elite_count]
    deferred = sorted_by_leverage[elite_count:]
    return elites, deferred


# ── Mod-8: ShadowInstance ─────────────────────────────────────────────────
@dataclass
class ShadowInstance:
    """TICK 29.0: A lightweight in-memory shadow fork of a niche.

    Created when a niche proposes an amendment to the Evolvable Soft Shell.
    The shadow operates with a microscopic Φ budget (≤5% of surplus) and
    runs the same rollouts as the main instance using the *proposed* rule
    values.  Results are accumulated here and compared by DualVerifier.

    Fields:
        amendment_id:          Links this instance to its SoftShellAmendment.
        proposed_snapshot:     The soft-shell values the shadow is testing
                               (main snapshot + proposed_value for param_name).
        rollout_phis_main:     Φ values recorded in the MAIN instance for
                               identical rollouts (basis for comparison).
        rollout_phis_shadow:   Φ values the shadow would achieve under the
                               proposed rules (approximated by applying the
                               proposed param scaling to main Φ observations).
        budget_consumed:       Cumulative Φ budget used so far.
        max_budget:            Hard cap (= 0.05 × phi_surplus at creation time).
        created_at:            Unix timestamp of shadow creation.
        completed:             True once DualVerifier has rendered a verdict.

    Thread-safety: fields mutated only inside PhiGovernor methods which are
    called under SharedState._lock.  Zero-IPC: no subprocesses, no queues.
    """
    amendment_id: str
    proposed_snapshot: Dict[str, float]
    rollout_phis_main: List[float]
    rollout_phis_shadow: List[float]
    budget_consumed: float
    max_budget: float
    created_at: float
    completed: bool = False


# ═══════════════════════════════════════════════════════════════
# TICK 30.0: META-OCF — CIVILIZATIONAL PROTOCOL
# Meta-Ontological Consensus Field message bus.
#
# Post-fission lineages DO NOT share memory or organelles.
# The MetaOCF is the ONLY communication channel between them —
# and it is intentionally low-bandwidth: advisory signals only.
#
# Two message types:
#   ExtinctionLevelWarning — broadcast a known-fatal pattern (e.g. a
#     specific MLX tensor shape that causes Metal driver crashes).
#     All lineages must hear this regardless of current Φ state.
#   CapabilityLease — one lineage offers a proven organelle to another
#     in exchange for a Φ bounty.  The offer is advisory; the receiving
#     lineage decides independently whether to accept.
#
# Thread-safety: MetaOCF carries its OWN internal lock (_ocf_lock),
# independent of SharedState._lock.  This prevents deadlock when a
# lineage broadcasts an ExtinctionLevelWarning WHILE holding
# SharedState._lock (which happens during tick_boundary).
# The two locks are NEVER acquired in the reverse order, so no
# deadlock cycle can form (see Lock Ordering Protocol below).
#
# Lock Ordering Protocol (must be strictly followed):
#   1. SharedState._lock  (outer — held for full tick_boundary duration)
#   2. MetaOCF._ocf_lock  (inner — held only for deque ops, ≤O(1))
# Never acquire SharedState._lock while holding MetaOCF._ocf_lock.
# ═══════════════════════════════════════════════════════════════


# ── Mod-7: MetaOCFMessage base and subclasses ─────────────────────────────
@dataclass
class MetaOCFMessage:
    """TICK 30.0: Base class for all Meta-OCF inter-lineage signals.

    All messages are immutable once created.  The MetaOCF bus is
    write-once append-only: messages are never modified after broadcast.

    Fields:
        msg_id:          Unique ID, format "{sender}:{msg_type}:{ts:.3f}".
        sender_lineage:  Lineage ID of the broadcaster.
        msg_type:        String discriminator ("extinction_warning" |
                         "capability_lease").
        timestamp:       Unix timestamp of broadcast.
    """
    msg_id: str
    sender_lineage: str
    msg_type: str
    timestamp: float


@dataclass
class ExtinctionLevelWarning(MetaOCFMessage):
    """TICK 30.0: Broadcast of a known-fatal pattern.

    Emitted when a lineage discovers an architectural pattern that
    causes irreversible system-level failures (Metal driver crashes,
    OOM kills that corrupt unified memory state, etc.).

    All lineages MUST consult warnings() before attempting a topology
    that matches a warning's description or tensor_shape.

    Fields:
        warning_code:  Short machine-readable code (e.g. "FISSION_EXECUTED",
                       "METAL_DRIVER_CRASH", "SHAPE_OOM_KILL").
        tensor_shape:  Optional: the MLX tensor shape that triggered the crash.
        description:   Human-readable diagnostic string.
    """
    warning_code: str
    description: str
    tensor_shape: Optional[Tuple] = None

    @classmethod
    def create(
        cls,
        sender_lineage: str,
        warning_code: str,
        description: str,
        tensor_shape: Optional[Tuple] = None,
    ) -> "ExtinctionLevelWarning":
        ts = time.time()
        msg_id = f"{sender_lineage}:extinction_warning:{ts:.3f}"
        return cls(
            msg_id=msg_id,
            sender_lineage=sender_lineage,
            msg_type="extinction_warning",
            timestamp=ts,
            warning_code=warning_code,
            description=description,
            tensor_shape=tensor_shape,
        )


@dataclass
class CapabilityLease(MetaOCFMessage):
    """TICK 30.0: Offer of a proven organelle to another lineage.

    The offering lineage signals that it has a high-fitness organelle
    it is willing to share for a Φ bounty.  The receiving lineage
    decides independently whether to accept (out-of-band, not tracked
    here).  The MetaOCF is purely advisory — no memory transfer occurs
    through this bus.

    Fields:
        target_lineage:  The lineage being offered the capability.
        organelle_type:  The organelle category (e.g. "attention",
                         "routing", "compression").
        phi_bounty:      The Φ value the offering lineage requests in
                         exchange for the lease.
        organelle_hash:  The topology hash of the offered organelle
                         (allows recipient to look it up in its archives).
    """
    target_lineage: str
    organelle_type: str
    phi_bounty: float
    organelle_hash: str

    @classmethod
    def create(
        cls,
        sender_lineage: str,
        target_lineage: str,
        organelle_type: str,
        phi_bounty: float,
        organelle_hash: str,
    ) -> "CapabilityLease":
        ts = time.time()
        msg_id = f"{sender_lineage}:capability_lease:{ts:.3f}"
        return cls(
            msg_id=msg_id,
            sender_lineage=sender_lineage,
            msg_type="capability_lease",
            timestamp=ts,
            target_lineage=target_lineage,
            organelle_type=organelle_type,
            phi_bounty=phi_bounty,
            organelle_hash=organelle_hash,
        )


# ── Mod-8: MetaOCF ────────────────────────────────────────────────────────
class MetaOCF:
    """TICK 30.0: Meta-Ontological Consensus Field — the civilizational bus.

    Thread-safe singleton message bus for inter-lineage communication.
    Carries its OWN internal lock (_ocf_lock), separate from SharedState._lock,
    to enable broadcasting from within a tick_boundary() call without risking
    deadlock.  See Lock Ordering Protocol in module header.

    Capacity: deque(maxlen=100).  Oldest messages auto-evict when full.
    This bound prevents unbounded growth during high-frequency fission events.

    Zero-IPC: all operations are in-process deque reads/writes.  The bus
    never writes to disk, never spawns threads, never calls network I/O.
    """
    _MAX_MESSAGES: int = 100

    def __init__(self) -> None:
        self._bus: deque = deque(maxlen=self._MAX_MESSAGES)
        self._ocf_lock = threading.Lock()  # inner lock (see ordering protocol)

    def broadcast(self, msg: MetaOCFMessage) -> None:
        """Append a message to the bus.  O(1), thread-safe."""
        with self._ocf_lock:
            self._bus.append(msg)

    def recent(self, n: int = 20) -> List[MetaOCFMessage]:
        """Return the n most recent messages (newest last).  O(n)."""
        with self._ocf_lock:
            items = list(self._bus)
        return items[-n:] if len(items) >= n else items

    def warnings(self) -> List["ExtinctionLevelWarning"]:
        """Return all ExtinctionLevelWarning messages currently in the bus."""
        with self._ocf_lock:
            return [m for m in self._bus if m.msg_type == "extinction_warning"]

    def pending_leases(self, target_lineage: str) -> List["CapabilityLease"]:
        """Return all CapabilityLease messages addressed to target_lineage."""
        with self._ocf_lock:
            return [
                m for m in self._bus
                if m.msg_type == "capability_lease"
                and m.target_lineage == target_lineage  # type: ignore[attr-defined]
            ]

    def clear_lease(self, msg_id: str) -> bool:
        """Remove a specific lease by msg_id (e.g. after accepting it).

        Returns True if found and removed, False if not present.
        """
        with self._ocf_lock:
            for i, m in enumerate(list(self._bus)):
                if m.msg_id == msg_id:
                    # deque doesn't support index deletion; rebuild
                    new_bus: deque = deque(
                        (x for x in self._bus if x.msg_id != msg_id),
                        maxlen=self._MAX_MESSAGES,
                    )
                    self._bus.clear()
                    self._bus.extend(new_bus)
                    return True
        return False

    def format_status(self) -> str:
        with self._ocf_lock:
            total = len(self._bus)
            warnings_count = sum(1 for m in self._bus if m.msg_type == "extinction_warning")
            leases_count = sum(1 for m in self._bus if m.msg_type == "capability_lease")
        return (
            f"meta_ocf: total={total} "
            f"[warnings={warnings_count} leases={leases_count}]"
        )


# ═══════════════════════════════════════════════════════════════
# SHARED IN-MEMORY STATE (Zero-IPC Channels)
# ═══════════════════════════════════════════════════════════════

class SharedState:
    """Zero-IPC shared state replacing filesystem handoffs.

    TICK 21.1: BoundaryOperator arrays live in MLX Unified Memory.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # ── Evaluator -> Mutator channel ─────────────────────────
        self.telemetry_buffer: List[Dict[str, Any]] = []
        self.best_epi: float = 0.0
        self.threshold: float = 0.10
        self.current_tick: int = 0
        self.evolvability: float = 0.0
        self.delta_epi: float = 0.0

        # ── Evaluator -> Mutator channel (gradient profile) ──────
        self.gradient_profile: Dict[str, Any] = {}

        # ── Mutator -> Evaluator channel ─────────────────────────
        self.pending_candidates: queue.Queue = queue.Queue(maxsize=50)

        # ── Niche -> Evaluator channel ───────────────────────────
        self.active_niche: Optional[Dict[str, Any]] = None
        self.niche_version: str = ""

        # ── Rule-IR Constraint Matrix (TICK 20.1) ────────────────
        self.constraint_matrix: Optional[ConstraintMatrix] = None

        # ── Teleological Attractor (TICK 20.1) ───────────────────
        self.attractor: AttractorState = get_default_attractor()
        self.organism_state: OrganismState = OrganismState()
        self.distance_to_attractor: float = float("inf")

        # ── Phi Governor ─────────────────────────────────────────
        self.phi_current: float = 0.0
        self.phi_peak: float = 0.0
        self.phi_expansion_factor: float = 1.0  # [0.5, 2.0]

        # ── TICK 21.0→21.1: Boundary Operator (MLX Unified Memory) ──
        self.boundary: BoundaryOperator = BoundaryOperator()
        self.usage: UsageSnapshot = UsageSnapshot()
        self.loss_components: Dict[str, float] = {}
        self.boundary_report: Dict[str, Any] = {}

        # ── TICK 25.0: Niche Registry (Multi-Species Pareto Fronts) ──
        self.niche_registry: NicheRegistry = NicheRegistry()

        # ── TICK 26.0: Dependency Risk Ledger ────────────────────────
        self.dependency_ledger: DependencyLedger = DependencyLedger()

        # ── TICK 27.0: Identity Membrane (IIS Layer 3) ───────────────
        # The IdentityMembrane is stored on SharedState so any component
        # (BoundaryUpdater, PhiGovernor, external auditors) can reference
        # it without IPC.  The module-level _GLOBAL_IDENTITY_MEMBRANE in
        # rule_ir.py is the canonical enforcement instance; this reference
        # gives SharedState-level visibility for telemetry and diagnostics.
        self.identity_membrane: IdentityMembrane = IdentityMembrane(IDENTITY_INVARIANTS)

        # ── TICK 27.0: Sovereignty Floor Verifier (IIS Layer 1) ──────
        # Expose the module-level verifier on SharedState for consistent
        # access by all governance components.
        self.sovereignty_verifier: SovereigntyFloorVerifier = _SOVEREIGNTY_VERIFIER

        # ── TICK 28.0: Negative Transfer Firewall (Proto-Civilization Layer) ──
        # Single zero-IPC ledger for all cross-niche constraint morphisms.
        # Lives on SharedState so PhiGovernor, BoundaryUpdater, and external
        # auditors can reference it without any inter-process communication.
        self.negative_transfer_firewall: NegativeTransferFirewall = NegativeTransferFirewall()

        # ── TICK 29.0: SRCA — Federated Self-Amendment ───────────────────────
        # EvolvableSoftShell: the mutable layer of governing meta-rules.
        # All soft parameters (shadow_attenuation, boundary_lr, pareto_threshold,
        # etc.) live here.  Niches propose amendments via propose_amendment();
        # the DualVerifier decides acceptance; permeation updates these values.
        self.evolvable_soft_shell: EvolvableSoftShell = EvolvableSoftShell()

        # ConstitutionalDiffLedger: append-only audit log of every proposed,
        # accepted, rejected, and rolled-back amendment.  Provides the
        # Federation-Level Rollback trigger if active amendments cause Φ spikes.
        self.constitutional_diff_ledger: ConstitutionalDiffLedger = ConstitutionalDiffLedger()

        # active_shadow_instance: at most ONE shadow fork running at any time.
        # Single-slot design eliminates contention and prevents budget dilution.
        # A second niche's proposal is deferred until the slot is free.
        self.active_shadow_instance: Optional[ShadowInstance] = None

        # ── TICK 30.0: HFSR — Heritable Fission & Species Radiation ─────────
        # LineageRegistry: owns all Lineage objects created post-fission.
        # Starts empty (no fission has occurred); execute_fission() populates it.
        self.lineage_registry: LineageRegistry = LineageRegistry()

        # MetaOCF: the civilizational message bus for inter-lineage signals.
        # Carries its own lock (see MetaOCF Lock Ordering Protocol).
        # Zero-IPC: all operations are in-process deque reads/writes.
        self.meta_ocf: MetaOCF = MetaOCF()

        # fission_events: append-only log of fission telemetry dicts.
        # Each entry records timestamp, lineage IDs, and triggering conditions.
        self.fission_events: List[Dict[str, Any]] = []

        # ── TICK 30.1: Teleological Identity Core (TIC) ──────────────────────
        # spec_final: the loaded + sealed spec_final.json dict.
        # Set by ignition.py Phase 2a BEFORE any threads are launched.
        # None until ignition has verified the file.
        self.spec_final: Optional[Dict[str, Any]] = None

        # forbidden_transitions: extracted from spec_final at startup.
        # PhiGovernor.check_forbidden_transition() queries this list on
        # every tick_boundary() call and applies a severity-3.0 epigenetic
        # penalty (or raises ConstitutionalViolationError for IDENTITY_DISSOLUTION).
        self.forbidden_transitions: List[str] = []

        # ── Lifecycle ────────────────────────────────────────────
        self.shutdown_requested: bool = False

    def push_telemetry(self, record: Dict[str, Any]) -> None:
        """Push a telemetry record from the evaluator node."""
        with self._lock:
            self.telemetry_buffer.append(record)
            if len(self.telemetry_buffer) > 200:
                self.telemetry_buffer = self.telemetry_buffer[-200:]
            self.best_epi = record.get("best_epi", self.best_epi)
            self.threshold = record.get("threshold", self.threshold)
            self.current_tick = record.get("tick", self.current_tick)
            self.evolvability = record.get("evolvability_score", self.evolvability)
            self.delta_epi = record.get("delta_epi", self.delta_epi)

            # Update organism state and attractor distance
            self.organism_state = OrganismState.from_telemetry(record)
            self.distance_to_attractor = distance_to_attractor(
                self.organism_state, self.attractor,
            )

            # Update Phi governor
            phi = self.organism_state.phi
            self.phi_current = phi
            if phi > self.phi_peak:
                self.phi_peak = phi
            if self.phi_peak > 0:
                ratio = phi / self.phi_peak
                self.phi_expansion_factor = max(0.5, min(2.0, 0.5 + 1.5 * ratio))

            # TICK 21.0: Update usage snapshot from telemetry
            self.usage.tick_latency_ms = record.get("tick_latency_ms", 0.0)
            self.usage.ram_mb = record.get("ram_mb", 0.0)

    def get_recent_telemetry(self, window: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.telemetry_buffer[-window:])

    def push_candidate(self, code: str, metadata: Dict[str, Any]) -> bool:
        try:
            self.pending_candidates.put_nowait({
                "code": code, "metadata": metadata, "t": time.time(),
            })
            return True
        except queue.Full:
            return False

    def pop_candidate(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        try:
            return self.pending_candidates.get(timeout=timeout)
        except queue.Empty:
            return None

    def update_gradient_profile(self, profile: Dict[str, Any]) -> None:
        with self._lock:
            self.gradient_profile = profile

    def get_gradient_profile(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.gradient_profile)

    def record_action(self, action: str) -> None:
        """Record an attempted action for violation tracking (TICK 21.0)."""
        with self._lock:
            self.usage.actions_attempted[action] = True


# ═══════════════════════════════════════════════════════════════
# Phi THERMODYNAMIC GOVERNOR (TICK 21.1: MLX Boundary-Aware)
# ═══════════════════════════════════════════════════════════════

class PhiGovernor:
    """Governs expansion/contraction of the computation graph.

    TICK 21.1: BoundaryUpdater now uses mx.value_and_grad + Adam
    for proper gradient descent through the boundary membrane.
    """

    def __init__(self, shared: SharedState) -> None:
        self.shared = shared
        self.boundary_updater = BoundaryUpdater()

    @property
    def expansion_factor(self) -> float:
        return self.shared.phi_expansion_factor

    def scale_rollouts(self, base_rollouts: int) -> int:
        return max(10, int(base_rollouts * self.expansion_factor))

    def scale_token_budget(self, base_tokens: int) -> int:
        return max(1024, int(base_tokens * self.expansion_factor))

    @property
    def phi_budget_surplus(self) -> float:
        """TICK 25.0: Normalized Φ budget surplus ∈ [0, 1].

        Used by genome_assembler to compute dynamic MCTS horizon H.
        surplus = 0 → tight budget, H=1 (reactive mode)
        surplus = 1 → flush budget, H=max (long-term exploration)
        """
        return max(0.0, min(1.0, (self.expansion_factor - 0.5) / 1.5))

    @staticmethod
    def kelly_bet_size(phi_ratio: float, leverage_score: float) -> float:
        """Power-Law Substrate: Kelly Criterion Φ budget allocation.

        Computes the optimal fraction of available Φ surplus to allocate to a
        mutation, shadow trial, or niche construction event given its leverage.

        KVS Atoms: KVS-2026-000003 (Kelly_Criterion_Sizing),
                   KVS-2026-000002 (Absorbing_Barrier),
                   KVS-2026-000001 (Ergodicity_Breaking).

        Args:
            phi_ratio:      Current Φ ratio = phi_current / phi_peak ∈ [0, 1].
            leverage_score: LeverageScore of the proposed mutation (L ≥ 0).
                            L < 1.0 → no edge → 0.0 returned immediately.
                            L ≥ _BARBELL_LEVERAGE_MIN (5.0) → AGGRESSIVE class.

        Returns:
            Float in [0.0, 1.0]: fraction of Φ surplus to allocate.
            Returns 0.0 when:
              - leverage_score ≤ 1.0 (no positive edge)
              - phi_ratio ≤ _PHI_SOVEREIGNTY_MIN (at or below absorbing barrier)

        Formula:
            edge      = leverage_score - 1.0      (positive edge above breakeven)
            raw_kelly = edge                       (Kelly fraction before decay)
            decay     = max(0, (phi_ratio - floor) / (1 - floor))  ** 3
                        (cubic decay → collapses to 0 as phi_ratio → floor)
            result    = min(raw_kelly, 1.0) * decay

        The cubic exponent on decay ensures the bet size stays near its raw
        Kelly value when phi_ratio is well above the floor, but collapses
        steeply as phi approaches the sovereignty boundary — preventing ruin
        via over-betting in a depleted Φ state.

        Thread-safety: pure function — no shared state read or written.
        MLX-safety:    operates on Python scalars only; no MLX lazy arrays
                       are consumed here, preventing lazy-eval hazards.
        """
        # Positive edge guard (KVS-2026-000003)
        edge = leverage_score - 1.0
        if edge <= 0.0:
            return 0.0

        raw_kelly = edge

        # Sovereignty decay: cubic collapse to 0 as phi_ratio → _PHI_SOVEREIGNTY_MIN
        # (KVS-2026-000002: Absorbing Barrier — bet size must reach 0 before ruin)
        decay = max(
            0.0,
            (phi_ratio - _PHI_SOVEREIGNTY_MIN) / (1.0 - _PHI_SOVEREIGNTY_MIN),
        )

        return min(raw_kelly, 1.0) * (decay ** 3)

    def should_construct_niche(self) -> bool:
        if not self.shared.boundary.is_authorized("niche_construct"):
            return False
        return self.expansion_factor >= 0.8

    def record_epigenetic_failure(
        self,
        failure_type: EpigeneticFailureType,
        severity: float = 1.0,
    ) -> Dict[str, float]:
        """TICK 25.0: Record a failure as epigenetic tensor decay.

        Translates the failure into mathematical friction on the
        Constraint Matrix.  NO text traceback is generated.
        The Architect's future proposals are shaped by gradient
        penalties, not natural language failure descriptions.

        TICK 27.0: Sovereignty Floor protection.
        Before applying the epigenetic penalty, the SovereigntyFloorVerifier
        checks whether the requested severity would project phi below the
        sovereignty floor.  If so, severity is mathematically capped to the
        maximum safe value — preventing autopoietic suicide from cascading
        penalties in low-phi states.
        """
        cm = self.shared.constraint_matrix
        if cm is None:
            return {}

        # TICK 27.0: Cap severity if it would breach the sovereignty floor.
        phi_ratio = (
            self.shared.phi_current / (self.shared.phi_peak + 1e-8)
            if self.shared.phi_peak > 0 else 1.0
        )
        capped_severity = _SOVEREIGNTY_VERIFIER.check_penalty(phi_ratio, severity)
        if capped_severity < severity:
            print(
                f"[sovereignty] penalty severity capped "
                f"{severity:.2f}→{capped_severity:.2f} "
                f"(phi_ratio={phi_ratio:.3f} near floor={_PHI_SOVEREIGNTY_MIN})"
            )

        applied = cm.apply_epigenetic_penalty(failure_type, capped_severity)
        if applied:
            print(f"[epigenetic] {failure_type.value} sev={capped_severity:.2f} → {applied}")
        return applied

    # ── Mod-10: record_shadow_rollout ─────────────────────────────────────
    def record_shadow_rollout(self, phi_main: float, phi_shadow: float) -> None:
        """TICK 29.0: Record one paired rollout observation for the active shadow.

        Called after every main-loop tick where a shadow instance is active.
        Non-blocking: pure list appends + float arithmetic.

        Budget enforcement: each rollout costs _SOVEREIGNTY_PENALTY_COST_EST
        units from the shadow's Φ budget.  When budget is exhausted the shadow
        is immediately finalized rather than waiting for _MIN_ROLLOUTS — this
        prevents an under-budget shadow from running indefinitely.

        Args:
            phi_main:   Φ value observed in the main instance this tick.
            phi_shadow: Hypothetical Φ value the shadow would achieve.
                        Callers compute this as phi_main scaled by the ratio
                        of proposed vs current soft-shell parameter value.
        """
        shadow = self.shared.active_shadow_instance
        if shadow is None or shadow.completed:
            return

        # Budget hard-cap: refuse rollout if already exhausted
        if shadow.budget_consumed >= shadow.max_budget:
            self._finalize_shadow_test()
            return

        shadow.rollout_phis_main.append(phi_main)
        shadow.rollout_phis_shadow.append(phi_shadow)
        shadow.budget_consumed += _SOVEREIGNTY_PENALTY_COST_EST

        # Auto-finalize once we have enough rollouts OR budget is exhausted
        if (
            len(shadow.rollout_phis_main) >= DualVerifier._MIN_ROLLOUTS
            or shadow.budget_consumed >= shadow.max_budget
        ):
            self._finalize_shadow_test()

    # ── Mod-11: _finalize_shadow_test ────────────────────────────────────
    def _finalize_shadow_test(self) -> None:
        """TICK 29.0: Invoke DualVerifier and permeate or reject the amendment.

        Non-blocking: pure Python arithmetic + dict/list ops.  No MLX tensors.

        If shadow wins:
          - Amendment status → ACCEPTED → ACTIVE
          - EvolvableSoftShell value updated with proposed_value
          - activation_phi recorded (rollback baseline)
        If shadow loses or breaches sovereignty floor:
          - Amendment status → REJECTED
        Either way: active_shadow_instance is cleared (slot freed).
        """
        shadow = self.shared.active_shadow_instance
        if shadow is None:
            return

        ledger = self.shared.constitutional_diff_ledger
        shell = self.shared.evolvable_soft_shell
        amendment = ledger.get_by_id(shadow.amendment_id)

        shadow_wins, delta_phi = DualVerifier.evaluate(
            main_phis=shadow.rollout_phis_main,
            shadow_phis=shadow.rollout_phis_shadow,
            sovereignty_floor=_PHI_SOVEREIGNTY_MIN,
        )

        phi_ratio = (
            self.shared.phi_current / (self.shared.phi_peak + 1e-8)
            if self.shared.phi_peak > 0 else 1.0
        )

        if shadow_wins and amendment is not None:
            try:
                shell.set(amendment.param_name, amendment.proposed_value)
                shell.permeation_phi_baseline = phi_ratio
                shell._last_permeated_snapshot = shadow.proposed_snapshot
                ledger.update_status(
                    shadow.amendment_id,
                    "ACTIVE",
                    activation_phi=phi_ratio,
                )
                print(
                    f"[srca] AMENDMENT ACCEPTED & ACTIVE: "
                    f"{amendment.param_name} "
                    f"{amendment.old_value:.4f}→{amendment.proposed_value:.4f} "
                    f"ΔΦ={delta_phi:+.4f} proposed_by={amendment.proposing_niche}"
                )
            except (ConstitutionalViolationError, ValueError, KeyError) as exc:
                # Should never reach here (proposal was already validated),
                # but crash-loud if it does.
                ledger.update_status(shadow.amendment_id, "REJECTED")
                print(f"[srca] AMENDMENT REJECTED at permeation (bug): {exc}")
        else:
            if amendment is not None:
                ledger.update_status(shadow.amendment_id, "REJECTED")
            print(
                f"[srca] AMENDMENT REJECTED: "
                f"{amendment.param_name if amendment else shadow.amendment_id} "
                f"ΔΦ={delta_phi:+.4f} "
                f"rollouts_main={len(shadow.rollout_phis_main)} "
                f"rollouts_shadow={len(shadow.rollout_phis_shadow)}"
            )

        shadow.completed = True
        self.shared.active_shadow_instance = None

    # ── Mod-11: check_fission ────────────────────────────────────────────
    def check_fission(
        self,
        phi_ratio: float,
    ) -> Optional[Any]:  # Optional[Tuple[Lineage, Lineage]]
        """TICK 30.0: Check fission conditions; execute and log if triggered.

        Reads RAM pressure from SharedState.usage.ram_mb / _DEFAULT_BUDGET["ram_mb"]
        and the current Φ from SharedState.phi_current.  Delegates the actual
        trigger decision and execution to NicheRegistry.check_fission().

        If fission fires:
          - Records a telemetry entry in SharedState.fission_events
          - Broadcasts an ExtinctionLevelWarning to SharedState.meta_ocf
            with warning_code="FISSION_EXECUTED" (advisory — callers can
            consult meta_ocf.warnings() to detect that the ecosystem split)
          - Returns the (child_a, child_b) Lineage pair

        Called from tick_boundary() after check_rollback().  Non-blocking
        when fission does not trigger: just records one observation.

        Lock Ordering Note: this method is called INSIDE the BoundaryUpdater
        boundary tick which itself may be called under SharedState._lock.
        MetaOCF.broadcast() acquires MetaOCF._ocf_lock (inner).  We never
        acquire SharedState._lock from within MetaOCF — ordering is safe.
        """
        # Compute RAM ratio: current RAM usage fraction of the configured ceiling
        ram_mb_used = self.shared.usage.ram_mb
        ram_mb_ceiling = _DEFAULT_BUDGET.get("ram_mb", 8192.0)
        ram_ratio = min(1.0, ram_mb_used / (ram_mb_ceiling + 1e-8))

        shell_snapshot = self.shared.evolvable_soft_shell.snapshot()

        result = self.shared.niche_registry.check_fission(
            ram_ratio=ram_ratio,
            phi_current=self.shared.phi_current,
            soft_shell_snapshot=shell_snapshot,
            lineage_registry=self.shared.lineage_registry,
        )

        if result is not None:
            child_a, child_b = result
            # Telemetry log
            fission_record: Dict[str, Any] = {
                "timestamp": time.time(),
                "ram_ratio": ram_ratio,
                "phi_current": self.shared.phi_current,
                "phi_ratio": phi_ratio,
                "lineage_a": child_a.lineage_id,
                "lineage_b": child_b.lineage_id,
                "fission_count": self.shared.lineage_registry.fission_count(),
            }
            self.shared.fission_events.append(fission_record)

            # Advisory broadcast via MetaOCF (inner lock only, no deadlock risk)
            warning = ExtinctionLevelWarning.create(
                sender_lineage=child_a.lineage_id,
                warning_code="FISSION_EXECUTED",
                description=(
                    f"Heritable Fission executed at phi_ratio={phi_ratio:.4f} "
                    f"ram_ratio={ram_ratio:.4f}. "
                    f"Lineages: {child_a.lineage_id} / {child_b.lineage_id}"
                ),
            )
            self.shared.meta_ocf.broadcast(warning)
            print(
                f"[hfsr] FISSION EVENT LOGGED: "
                f"ram={ram_ratio:.3f} phi={self.shared.phi_current:.4f} "
                f"lineages=[{child_a.lineage_id}, {child_b.lineage_id}]"
            )

        return result

    # ── Mod-12: check_rollback ────────────────────────────────────────────
    def check_rollback(self, current_phi_ratio: float) -> bool:
        """TICK 29.0: Federation-Level Rollback monitor.

        Called from tick_boundary() after every main-loop boundary update.
        Checks whether any ACTIVE amendment has caused a Φ deterioration
        exceeding the 10% rollback threshold.

        If rollback triggers:
          - EvolvableSoftShell is restored to the pre-permeation snapshot
          - Amendment status → ROLLED_BACK
          - Proposing niche accumulates a rollback strike
          - Returns True (caller may log the event)

        Rollback threshold: current_phi_ratio < activation_phi × 0.90
        (Φ dropped >10% from the level recorded when the amendment went ACTIVE)

        Args:
            current_phi_ratio: phi_current / (phi_peak + ε) this tick.

        Returns:
            True if a rollback was executed, False otherwise.
        """
        ledger = self.shared.constitutional_diff_ledger
        shell = self.shared.evolvable_soft_shell
        active = ledger.active()

        for amendment in active:
            rollback_threshold = amendment.activation_phi * 0.90
            if current_phi_ratio < rollback_threshold:
                # Restore the pre-permeation snapshot
                if shell._last_permeated_snapshot is not None:
                    try:
                        shell.restore(shell._last_permeated_snapshot)
                    except ConstitutionalViolationError:
                        pass  # snapshot was clean at creation; this is a bug
                ledger.update_status(amendment.amendment_id, "ROLLED_BACK")
                strike_count = ledger.rollback_count_for_niche(amendment.proposing_niche)
                print(
                    f"[srca] FEDERATION ROLLBACK: amendment {amendment.amendment_id} "
                    f"rolled back. phi_ratio={current_phi_ratio:.4f} < "
                    f"threshold={rollback_threshold:.4f}. "
                    f"niche={amendment.proposing_niche} strikes={strike_count}"
                )
                return True
        return False

    def tick_boundary(self) -> Dict[str, Any]:
        """Execute one boundary update cycle (TICK 21.1 breathing rhythm).

        Uses mx.value_and_grad for analytical gradient computation through
        the full boundary graph, applied via Adam optimizer.
        """
        boundary = self.shared.boundary
        usage = self.shared.usage

        # Compute telemetry-facing loss components (materialized).
        phi_task_val = max(0.0, 1.0 - self.shared.phi_current)
        # TICK 26.0: Read dependency risk and switching friction for telemetry
        dep_risk = self.shared.dependency_ledger.dependency_risk()
        switching_friction = self.shared.boundary_report.get("switching_friction", 0.0)
        components = compute_loss_components(
            boundary, phi_task_val, usage,
            dependency_risk=dep_risk,
            switching_friction=switching_friction,
        )
        self.shared.loss_components = components

        # ── TICK 39.0: ARSL thermodynamic gate before boundary update ──
        # Build a RIC representing the boundary modification and run the ARSL
        # gate check.  If the gate is closed (ARSLGateError), log and skip
        # this breathing cycle — DO NOT raise, the Immortal Loop must survive.
        _ric_boundary = ric_for_constraint_mod(
            modifier_id="boundary_updater",
            target_categories=["boundary_operator"],
            phi_budget=self.shared.phi_current,
        )
        try:
            _GOVERNANCE_ARSL.gate_check(_ric_boundary)
        except ARSLGateError as _arsl_exc:
            print(f"[tick_boundary] ARSL gate CLOSED — skipping boundary update: {_arsl_exc}")
            return {
                "phase": "arsl_blocked",
                "permeability": 0.0,
                "loss": 0.0,
                "effective_lr": self.boundary_updater.base_lr,
                "loss_components": components,
                "arsl_blocked": True,
                "arsl_detail": str(_arsl_exc),
            }

        # Update boundary via value_and_grad + Adam breathing.
        # TICK 30.3: Wrapped in try/except to expose any MLX crash with a full
        # traceback before re-raising.  Without this, a TypeError deep inside
        # nn.value_and_grad() produced a blank exception message that the outer
        # _governor_loop silencer swallowed completely.
        try:
            report = self.boundary_updater.update(
                boundary=boundary,
                phi_current=self.shared.phi_current,
                phi_peak=self.shared.phi_peak,
                usage=usage,
            )
        except Exception as _upd_exc:
            import traceback as _tb
            print(
                f"[tick_boundary] FATAL: boundary_updater.update() crashed — "
                f"{type(_upd_exc).__name__}: {_upd_exc}"
            )
            _tb.print_exc()
            raise
        report["loss_components"] = components
        self.shared.boundary_report = report

        # ── TICK 29.0: Federation-Level Rollback monitor ─────────────────
        # Run check_rollback() after every boundary tick so that any ACTIVE
        # amendment that degrades Φ by >10% is caught and reverted immediately.
        phi_ratio_now = (
            self.shared.phi_current / (self.shared.phi_peak + 1e-8)
            if self.shared.phi_peak > 0 else 1.0
        )
        rollback_fired = self.check_rollback(phi_ratio_now)
        if rollback_fired:
            report["srca_rollback"] = True

        # ── TICK 30.0: Heritable Fission monitor ──────────────────────────
        # check_fission() records one observation to FissionTrigger on every
        # tick.  Non-blocking unless the dual trigger fires (RAM pressure +
        # Φ stagnation).  When it fires the report carries "hfsr_fission"=True
        # and SharedState.fission_events is updated.
        fission_result = self.check_fission(phi_ratio_now)
        if fission_result is not None:
            report["hfsr_fission"] = True

        # Reset per-epoch usage tracking.
        self.shared.usage = UsageSnapshot(ram_mb=usage.ram_mb)

        # ── TICK 30.1: Forbidden Transition Enforcement ───────────────────
        # check_forbidden_transition() classifies the current system state
        # against the teleological spec's forbidden_transitions list.
        # Called last (after all TICK 29/30 monitors) so it has the freshest
        # phi_ratio_now.  Non-fatal transitions trigger a severity-3.0
        # epigenetic penalty.  IDENTITY_DISSOLUTION is always fatal.
        self.check_forbidden_transition(phi_ratio_now, report)

        # ── TICK 39.1: CCL Amortized Depreciation ─────────────────────────
        # Process one tick of Φ debt amortization from the CCL PhiDebtLedger.
        # The deducted amount is subtracted from phi_current so the system
        # cannot zero-out its historical sunk costs by rewriting credentials.
        # This enforces thermodynamic honesty: past failures reduce present capacity.
        phi_debt_deducted = _GOVERNANCE_CCL.amortize_historical_cost(
            n_ticks=1,
            oscillation_freq_hz=1.0 / _BREATHING_PERIOD_S,
        )
        if phi_debt_deducted > 0.0:
            self.shared.phi_current = max(
                0.0,
                self.shared.phi_current - phi_debt_deducted,
            )
            report["phi_debt_deducted"] = phi_debt_deducted
            report["phi_after_amortization"] = self.shared.phi_current

        return report

    def check_forbidden_transition(
        self,
        phi_ratio: float,
        report: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """TICK 30.1: Detect and penalize forbidden teleological transitions.

        Inspects the current system state against spec_final.json's
        forbidden_transitions list.  Enforcement rules:

          UNCATCHABLE_OOM_DEATH
            Triggered when ram_mb / budget_ram_mb > 0.97 AND phi_ratio < 0.05.
            Outcome: severity-3.0 epigenetic OOM penalty + log.

          UNVERIFIED_CROSS_NICHE_POLLUTION
            Triggered when the NegativeTransferFirewall has recorded ≥ 3
            un-attenuated morphisms (original_severity > shadow_severity × 3)
            in the last tick window — indicating raw penalties crossed niches
            without shadow attenuation.
            Outcome: severity-3.0 epigenetic PERMISSION_VIOLATION penalty + log.

          IDENTITY_DISSOLUTION
            Triggered when phi_ratio < _PHI_SOVEREIGNTY_MIN and the
            IdentityMembrane has been fully eroded (all invariant categories
            at their minimum floor simultaneously).
            Outcome: raises ConstitutionalViolationError — FATAL.

        Args:
            phi_ratio: current phi_current / phi_peak ratio.
            report:    the tick_boundary report dict (mutated in place with
                       "forbidden_transition" key if one is detected).

        Returns:
            The name of the forbidden transition that fired, or None.
        """
        forbidden = self.shared.forbidden_transitions
        if not forbidden:
            return None

        fired: Optional[str] = None

        # ── 1. UNCATCHABLE_OOM_DEATH ─────────────────────────────────────
        if "UNCATCHABLE_OOM_DEATH" in forbidden:
            ram_used = self.shared.usage.ram_mb
            ram_budget = _DEFAULT_BUDGET.get("ram_mb", 8192.0)
            ram_ratio = ram_used / (ram_budget + 1.0)
            if ram_ratio > 0.97 and phi_ratio < 0.05:
                fired = "UNCATCHABLE_OOM_DEATH"
                print(
                    f"[tic] ⚠  FORBIDDEN TRANSITION: {fired} "
                    f"(ram_ratio={ram_ratio:.3f} phi_ratio={phi_ratio:.4f}) — "
                    f"severity-3.0 OOM epigenetic penalty applied."
                )
                if self.shared.constraint_matrix is not None:
                    try:
                        self.shared.constraint_matrix.apply_epigenetic_penalty(
                            EpigeneticFailureType.OOM,
                            severity=3.0,
                        )
                    except Exception:
                        pass

        # ── 2. UNVERIFIED_CROSS_NICHE_POLLUTION ──────────────────────────
        if fired is None and "UNVERIFIED_CROSS_NICHE_POLLUTION" in forbidden:
            fw = self.shared.negative_transfer_firewall
            recent_morphisms = fw.recent(10)
            pollution_count = sum(
                1 for m in recent_morphisms
                if m.original_severity > m.shadow_severity * 3.0 + 1e-9
            )
            if pollution_count >= 3:
                fired = "UNVERIFIED_CROSS_NICHE_POLLUTION"
                print(
                    f"[tic] ⚠  FORBIDDEN TRANSITION: {fired} "
                    f"(unattenuated morphisms={pollution_count}/10) — "
                    f"severity-3.0 PERMISSION_VIOLATION epigenetic penalty applied."
                )
                if self.shared.constraint_matrix is not None:
                    try:
                        self.shared.constraint_matrix.apply_epigenetic_penalty(
                            EpigeneticFailureType.PERMISSION_VIOLATION,
                            severity=3.0,
                        )
                    except Exception:
                        pass

        # ── 3. IDENTITY_DISSOLUTION — FATAL ──────────────────────────────
        if fired is None and "IDENTITY_DISSOLUTION" in forbidden:
            if phi_ratio < _PHI_SOVEREIGNTY_MIN:
                membrane = self.shared.identity_membrane
                floors = membrane.get_floors()
                cm = self.shared.constraint_matrix
                all_eroded = (
                    cm is not None and len(floors) > 0 and
                    all(
                        cm.C[i][0] <= floor + 1e-6
                        for name, floor in floors.items()
                        for i in [__import__("rule_ir").CAT_IDX.get(name, -1)]
                        if i >= 0
                    )
                )
                if all_eroded:
                    fired = "IDENTITY_DISSOLUTION"
                    raise ConstitutionalViolationError(
                        f"CONSTITUTIONAL VIOLATION: IDENTITY_DISSOLUTION detected.\n"
                        f"  phi_ratio={phi_ratio:.4f} < sovereignty_floor={_PHI_SOVEREIGNTY_MIN}\n"
                        f"  All IdentityMembrane invariant categories are at their minimum floor.\n"
                        f"  The organism has lost its thermodynamic identity.\n"
                        f"  The teleological attractor A* cannot be reached from this state.\n"
                        f"  ConstitutionalViolationError raised — fatal stop."
                    )

        if fired is not None and report is not None:
            report["forbidden_transition"] = fired

        return fired

    def format_status(self) -> str:
        boundary = self.shared.boundary
        phase = self.shared.boundary_report.get("phase", "init")
        perm = boundary.permeability()
        # TICK 30.2: If loss_components hasn't been populated yet (pre-first
        # boundary tick), compute phi_strain live from the boundary's current
        # sigmoid outputs so the dashboard always shows the true thermodynamic
        # heartbeat rather than the misleading 0.0000 default.
        if self.shared.loss_components:
            loss_total = self.shared.loss_components.get("total", 0.0)
        else:
            phi_strain_live = mx.mean(mx.abs(boundary.m_t)) + mx.mean(mx.abs(boundary.g_t))
            mx.eval(phi_strain_live)
            loss_total = _LAMBDA_STRAIN * phi_strain_live.item()
        return (
            f"Phi={self.shared.phi_current:.4f} "
            f"peak={self.shared.phi_peak:.4f} "
            f"expansion={self.expansion_factor:.2f}x "
            f"D(A*)={self.shared.distance_to_attractor:.4f} "
            f"| d: perm={perm:.3f} phase={phase} "
            f"L={loss_total:.4f}"
        )


# ═══════════════════════════════════════════════════════════════
# UNIFIED COMPUTATION GRAPH
# ═══════════════════════════════════════════════════════════════

_BOUNDARY_CHECKPOINT = "island_meta/boundary_operator.json"


class AutopoieticGraph:
    """The collapsed computation graph -- a single unified entity.

    TICK 21.1: All boundary tensors live in MLX Unified Memory.
    The governor loop breathes the boundary via value_and_grad + Adam.
    """

    def __init__(self, workspace: str = "agi_workspace") -> None:
        self.workspace = workspace
        self.fs = FileSystemBus(root=workspace)
        self.shared = SharedState()
        self.governor = PhiGovernor(self.shared)

        # Load or compile constraint matrix
        self.shared.constraint_matrix = load_or_compile_matrix(workspace)

        # Restore boundary operator from checkpoint if available.
        boundary_path = os.path.join(workspace, _BOUNDARY_CHECKPOINT)
        if os.path.isfile(boundary_path):
            try:
                self.shared.boundary = BoundaryOperator.from_checkpoint(boundary_path)
                print(f"[boundary] Restored from {boundary_path}")
            except Exception as exc:
                print(f"[boundary] Failed to restore ({exc}), using defaults")
                self.shared.boundary = BoundaryOperator()
        else:
            self.shared.boundary = BoundaryOperator()

        # Persistence writer (batched, async)
        self._persist_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._persist_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        boundary = self.shared.boundary
        mx.eval(boundary.parameters())

        print(f"\n{'=' * 70}")
        print(f"  TICK 21.1: MLX SUBSTRATE CONVERSION")
        print(f"  Immersed in the Unified Memory ocean.")
        print(f"  MLX backend: {'Metal' if mx.metal.is_available() else 'CPU'}")
        print(f"  Workspace: {self.workspace}")
        print(f"  Constraint Matrix: v{self.shared.constraint_matrix.version}")
        print(f"  Attractor: Phi_max={self.shared.attractor.phi_max:.4f}")
        print(f"  Boundary: dim={boundary.state_logits.shape[0]} "
              f"perm={boundary.permeability():.3f}")
        g_vals = mx.sigmoid(boundary.gate_logits)
        mx.eval(g_vals)
        print(f"  Gates: {', '.join(f'{k}={v:.2f}' for k, v in zip(boundary._gate_keys, g_vals.tolist()))}")
        b_vals = boundary.resource_budget
        mx.eval(b_vals)
        print(f"  Budget: {', '.join(f'{k}={v:.0f}' for k, v in zip(boundary._budget_keys, b_vals.tolist()))}")
        print(f"  Optimizer: Adam(lr={_BOUNDARY_LR})")
        print(f"  Loss: lambda_r={_LAMBDA_RESOURCE} lambda_s={_LAMBDA_STRAIN} lambda_v={_LAMBDA_VIOLATION:.0e}")
        print(f"{'=' * 70}\n")

        # Start persistence writer
        self._persist_thread = threading.Thread(
            target=self._persistence_loop,
            daemon=True,
            name="persist",
        )
        self._persist_thread.start()

        print("[autopoietic] Computation graph initialized (MLX substrate).")
        print("[autopoietic] Boundary breathing via value_and_grad + Adam.")

        self._governor_loop()

    def _governor_loop(self) -> None:
        interval_s = 10.0
        boundary_interval_s = _BREATHING_PERIOD_S
        last_boundary_tick = time.time()

        while not self.shared.shutdown_requested:
            # ── TICK 39.1: Genesis Tether Attestation ─────────────────────
            # IdentityDissolutionError is BaseException — it BYPASSES the
            # `except Exception` guard below and physically halts the loop.
            # This is intentional: a drifted hard core means the node is no
            # longer constitutionally valid and MUST cease operation.
            if _GENESIS_TETHER.is_due():
                rec = _GENESIS_TETHER.attest(IMMUTABLE_HARD_CORE)  # raises if drifted
                print(
                    f"[genesis-tether] attestation #{rec.attest_count} OK "
                    f"(genesis={rec.genesis_hash[:12]}...)"
                )

            try:
                status = self.governor.format_status()
                cm = self.shared.constraint_matrix
                if cm:
                    proj = cm.project_all()
                    print(f"[governor] {status} | "
                          f"temp={proj['temperature']:.3f} "
                          f"scope={proj['structural_scope']:.3f} "
                          f"parsimony={proj['parsimony_strength']:.3f}")

                # Boundary breathing cycle
                now = time.time()
                if now - last_boundary_tick >= boundary_interval_s:
                    report = self.governor.tick_boundary()
                    last_boundary_tick = now

                    phase = report.get("phase", "neutral")
                    perm = report.get("permeability", 0.0)
                    loss = report.get("loss", 0.0)
                    lr = report.get("effective_lr", _BOUNDARY_LR)
                    comps = report.get("loss_components", {})
                    print(f"[boundary] phase={phase} perm={perm:.3f} "
                          f"L={loss:.4f} lr={lr:.4f} | "
                          f"task={comps.get('phi_task', 0):.4f} "
                          f"res={comps.get('phi_resource', 0):.4f} "
                          f"str={comps.get('phi_strain', 0):.4f} "
                          f"vio={comps.get('phi_violation', 0):.1f}")

                    # Persist boundary checkpoint
                    boundary_path = os.path.join(
                        self.workspace, _BOUNDARY_CHECKPOINT
                    )
                    try:
                        self.shared.boundary.save_checkpoint(boundary_path)
                    except OSError as exc:
                        print(f"[boundary] Persist error: {exc}")

                if cm and cm.version > 0:
                    save_matrix(self.workspace, cm)

                self._persist_queue.put({
                    "type": "governor_heartbeat",
                    "phi": self.shared.phi_current,
                    "phi_peak": self.shared.phi_peak,
                    "expansion": self.shared.phi_expansion_factor,
                    "distance_to_attractor": self.shared.distance_to_attractor,
                    "best_epi": self.shared.best_epi,
                    "tick": self.shared.current_tick,
                    "boundary": self.shared.boundary.state_dict_compact(),
                    "loss": self.shared.loss_components,
                    "boundary_phase": self.shared.boundary_report.get("phase", "init"),
                    "t": time.time(),
                })

                time.sleep(interval_s)

            except KeyboardInterrupt:
                self.shared.shutdown_requested = True
                print("\n[autopoietic] Shutdown requested.")
                break
            except Exception as exc:
                # TICK 30.3: Expose the full traceback — do NOT silently swallow.
                # The previous bare print(f"[governor] Error: {exc}") was masking
                # MLX TypeErrors from tick_boundary() as a blank message, leaving
                # phase="INIT" frozen in the dashboard indefinitely.
                import traceback as _tb
                print(f"[governor] ERROR — {type(exc).__name__}: {exc}")
                _tb.print_exc()
                time.sleep(interval_s)

    def _persistence_loop(self) -> None:
        log_path = Path(self.workspace) / "logs" / "autopoietic_events.ndjson"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        batch: List[Dict[str, Any]] = []
        flush_interval = 5.0
        last_flush = time.time()

        while not self.shared.shutdown_requested:
            try:
                record = self._persist_queue.get(timeout=1.0)
                batch.append(record)
            except queue.Empty:
                pass

            if batch and (time.time() - last_flush >= flush_interval
                          or len(batch) >= 50):
                try:
                    with open(log_path, "a") as f:
                        for rec in batch:
                            f.write(json.dumps(rec, default=str) + "\n")
                    batch.clear()
                    last_flush = time.time()
                except OSError:
                    pass

        if batch:
            try:
                with open(log_path, "a") as f:
                    for rec in batch:
                        f.write(json.dumps(rec, default=str) + "\n")
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════
# INTEGRATION HOOKS (for existing daemons during migration)
# ═══════════════════════════════════════════════════════════════

_GLOBAL_SHARED: Optional[SharedState] = None
_GLOBAL_GOVERNOR: Optional[PhiGovernor] = None


def get_shared_state() -> SharedState:
    global _GLOBAL_SHARED
    if _GLOBAL_SHARED is None:
        _GLOBAL_SHARED = SharedState()
    return _GLOBAL_SHARED


def get_phi_governor() -> PhiGovernor:
    global _GLOBAL_GOVERNOR, _GLOBAL_SHARED
    if _GLOBAL_GOVERNOR is None:
        _GLOBAL_GOVERNOR = PhiGovernor(get_shared_state())
    return _GLOBAL_GOVERNOR


def get_boundary() -> BoundaryOperator:
    """Get the global boundary operator (TICK 21.0)."""
    return get_shared_state().boundary


def check_authorization(action: str) -> bool:
    """Check if an action is authorized by the boundary gate.
    Records the attempt for violation tracking.
    """
    shared = get_shared_state()
    shared.record_action(action)
    return shared.boundary.is_authorized(action)


# ═══════════════════════════════════════════════════════════════
# META-EVOLUTION INTEGRATION (Rule-IR Constraint Gradient)
# ═══════════════════════════════════════════════════════════════

def run_constraint_meta_evolution(
    workspace: str,
    cm: ConstraintMatrix,
    failure_summary: str,
    perf_history: str = "",
) -> Optional[Dict[str, float]]:
    """Execute a Rule-IR meta-evolution cycle.
    TICK 21.0: Checks boundary authorization before proceeding.
    """
    if not check_authorization("meta_evolve"):
        print("[rule-ir] Meta-evolution BLOCKED by boundary gate.")
        return None

    # ── TICK 39.0: ARSL thermodynamic gate before constraint modification ──
    # Build a RIC for the constraint modification and check the ARSL gate.
    # If the gate is closed, log and abort — do NOT raise so callers survive.
    _ric_cm = ric_for_constraint_mod(
        modifier_id="meta_evolve",
        target_categories=list(cm.project_all().keys()) if cm else ["unknown"],
        phi_budget=get_shared_state().phi_current if _GLOBAL_SHARED is not None else 1.0,
    )
    try:
        _GOVERNANCE_ARSL.gate_check(_ric_cm)
    except ARSLGateError as _arsl_exc:
        print(f"[rule-ir] Meta-evolution BLOCKED by ARSL gate: {_arsl_exc}")
        return None

    import urllib.request

    from stateless_tick import _LLM_MODEL, _LLM_ENDPOINT

    system_prompt, user_prompt = build_constraint_meta_prompt(
        cm, failure_summary, perf_history,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # TICK 21.5: Thermodynamic API Constraints
    payload = json.dumps({
        "model": _LLM_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": 0,
        "options": {
            "temperature": 0.5,
            "top_p": 0.90,
            "num_ctx": 8192,
            "num_predict": 1024,
        },
    }).encode("utf-8")

    check_authorization("api_call")

    try:
        req = urllib.request.Request(
            _LLM_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            llm_raw = body["message"]["content"]
    except Exception as exc:
        print(f"[rule-ir] Meta-evolution LLM error: {exc}")
        return None

    shared = get_shared_state()
    shared.usage.api_calls += 1

    gradient = extract_constraint_gradient(llm_raw)
    if gradient is None:
        print(f"[rule-ir] No valid <constraint_gradient> in LLM response.")
        return None

    applied = cm.apply_gradient(gradient)
    cm.apply_decay()
    cm.lineage.append(f"meta-evo gradient: {gradient} -> applied: {applied}")

    save_matrix(workspace, cm)
    print(f"[rule-ir] Constraint Matrix updated to v{cm.version}")
    print(f"[rule-ir] Applied gradients: {applied}")
    print(f"[rule-ir] Projected: {cm.project_all()}")

    return applied


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TICK 21.1 -- MLX Substrate Conversion. "
        "Phi-Boundary Duality Engine on Apple Silicon Unified Memory."
    )
    parser.add_argument(
        "--workspace", type=str, default="agi_workspace",
        help="Workspace root directory (default: agi_workspace)",
    )
    parser.add_argument(
        "--state-dim", type=int, default=_DEFAULT_STATE_DIM,
        help=f"State mask dimension (default: {_DEFAULT_STATE_DIM})",
    )
    args = parser.parse_args()

    graph = AutopoieticGraph(workspace=args.workspace)
    try:
        graph.start()
    except KeyboardInterrupt:
        print("\n[autopoietic] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
