"""
resource_sovereignty.py
=======================
Axiomatic Resource Sovereignty Layer (ARSL) — TICK 39.0 Pillar 3

Translates external physical limits (API quotas, bandwidth, latency, GPU load)
into a differentiable constraint hypergraph.

Core Thermodynamic Law:
  If Harvested_Value <= (Deployment_Cost + Fragility_Penalty):
      raise ARSLGateError  (UNCATCHABLE in autopoietic core — see Law #3)

The ARSL gate ensures the system acts as a strict Resource Sovereign,
not merely a compute optimizer.

ARSLGateError propagation:
  - In FastAPI async handlers → caught by exception_handler → HTTP 503
  - In autopoietic_core subprocess → NEVER raised there (Law #3)
  - The gate is only called from the A2A transport layer (server.py)

All constraint evaluation is O(1) arithmetic. No I/O.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from reality_contract import RealityInterfaceContract, RICAction


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

# Physical resource dimensions in the constraint hypergraph
RESOURCE_DIMENSIONS: Tuple[str, ...] = (
    "api_quota",          # remaining API calls (count)
    "bandwidth_mbps",     # available network bandwidth
    "latency_budget_ms",  # remaining latency budget
    "ram_headroom_mb",    # free RAM above sovereignty floor
    "disk_write_mb",      # remaining disk write budget
    "gpu_utilization",    # GPU/ANE utilization ratio [0,1]
    "phi_reserve",        # current Φ reserve ratio [0,1]
)

# Fragility penalty scaling factors per dimension
# Higher = more fragile when that resource is constrained
_FRAGILITY_WEIGHTS: Dict[str, float] = {
    "api_quota":         0.15,
    "bandwidth_mbps":    0.10,
    "latency_budget_ms": 0.20,
    "ram_headroom_mb":   0.25,
    "disk_write_mb":     0.05,
    "gpu_utilization":   0.15,
    "phi_reserve":       0.10,
}

# Action-specific deployment cost multipliers
_ACTION_COST_MULTIPLIER: Dict[RICAction, float] = {
    RICAction.A2A_ROUTE:       0.05,
    RICAction.A2A_EXECUTE:     0.30,
    RICAction.API_CALL:        0.25,
    RICAction.RESOURCE_ALLOC:  0.40,
    RICAction.CONSTRAINT_MOD:  0.20,
    RICAction.FISSION:         0.80,
    RICAction.META_EVOLVE:     0.60,
    RICAction.GOEDEL_INJECT:   0.15,
    RICAction.VALUE_SIGNAL:    0.02,
    RICAction.NODE_REPLICATE:  1.00,
}

# Minimum value harvest required for the system to not bleed
_MIN_HARVEST_RATIO: float = 1.0  # Harvested_Value > Deployment_Cost + Fragility


# ──────────────────────────────────────────────
# ARSLGateError — The Uncatchable
# ──────────────────────────────────────────────

class ARSLGateError(Exception):
    """
    Thermodynamic sovereignty violation.

    This error is INTENTIONALLY never caught inside the autopoietic core
    (CLAUDE.md Law #3). It propagates up to the FastAPI exception handler
    where it becomes an HTTP 503 Service Unavailable.

    Fields:
      harvested_value:  estimated value of the proposed operation
      deployment_cost:  estimated cost of executing it
      fragility_penalty: cost of operating under current resource constraints
      resource_report:  per-dimension resource state at time of rejection
    """

    def __init__(
        self,
        harvested_value: float,
        deployment_cost: float,
        fragility_penalty: float,
        resource_report: Dict[str, float],
        ric_id: str = "",
    ) -> None:
        self.harvested_value = harvested_value
        self.deployment_cost = deployment_cost
        self.fragility_penalty = fragility_penalty
        self.resource_report = resource_report
        self.ric_id = ric_id
        self.deficit = (deployment_cost + fragility_penalty) - harvested_value
        super().__init__(
            f"ARSL GATE CLOSED: V={harvested_value:.4f} <= "
            f"C={deployment_cost:.4f} + F={fragility_penalty:.4f} "
            f"(deficit={self.deficit:.4f}, ric={ric_id})"
        )


# ──────────────────────────────────────────────
# Resource State Snapshot
# ──────────────────────────────────────────────

@dataclass
class ResourceHypergraph:
    """
    A snapshot of the system's physical resource state.

    Each dimension is normalized to [0, 1] where:
      0.0 = resource exhausted (maximum fragility)
      1.0 = resource fully available (zero fragility)

    Updated by the transport layer before each gate check.
    """
    api_quota: float = 1.0
    bandwidth_mbps: float = 1.0
    latency_budget_ms: float = 1.0
    ram_headroom_mb: float = 1.0
    disk_write_mb: float = 1.0
    gpu_utilization: float = 1.0   # inverted: 1.0 = idle, 0.0 = saturated
    phi_reserve: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "api_quota": self.api_quota,
            "bandwidth_mbps": self.bandwidth_mbps,
            "latency_budget_ms": self.latency_budget_ms,
            "ram_headroom_mb": self.ram_headroom_mb,
            "disk_write_mb": self.disk_write_mb,
            "gpu_utilization": self.gpu_utilization,
            "phi_reserve": self.phi_reserve,
        }

    def fragility_penalty(self) -> float:
        """
        Compute the weighted fragility penalty across all dimensions.

        F = Σ_i  w_i * (1 - x_i)^2

        Quadratic penalty: gentle near full availability, severe near exhaustion.
        """
        total = 0.0
        state = self.to_dict()
        for dim, weight in _FRAGILITY_WEIGHTS.items():
            x = max(0.0, min(1.0, state.get(dim, 1.0)))
            total += weight * (1.0 - x) ** 2
        return total


# ──────────────────────────────────────────────
# ARSL Core
# ──────────────────────────────────────────────

class AxiomaticResourceSovereigntyLayer:
    """
    The thermodynamic gate for the entire system.

    Gate check:
      1. Estimate Harvested_Value(RIC) from the RIC's Φ budget and action type
      2. Estimate Deployment_Cost(RIC) from the action cost multiplier
      3. Compute Fragility_Penalty from the current ResourceHypergraph
      4. If V <= C + F: raise ARSLGateError (uncatchable)

    The resource hypergraph is updated by the caller (server.py) before
    each gate check. The ARSL itself never does I/O.
    """

    def __init__(self) -> None:
        self._resources = ResourceHypergraph()
        self._gate_calls: int = 0
        self._gate_rejections: int = 0
        self._last_gate_ts: float = 0.0

    # ──────────────────────────────────────────
    # Resource State Updates
    # ──────────────────────────────────────────

    def update_resource(self, dimension: str, value: float) -> None:
        """Update a single resource dimension (normalized to [0,1])."""
        value = max(0.0, min(1.0, value))
        if hasattr(self._resources, dimension):
            setattr(self._resources, dimension, value)

    def update_resources(self, snapshot: Dict[str, float]) -> None:
        """Bulk update from a dict of dimension→value."""
        for dim, val in snapshot.items():
            self.update_resource(dim, val)

    def get_resources(self) -> ResourceHypergraph:
        return self._resources

    # ─────────────────────────────────���────────
    # The Gate
    # ──────────────────────────────────────────

    def gate_check(self, ric: RealityInterfaceContract) -> Dict[str, float]:
        """
        The core thermodynamic gate.

        Returns a report dict on success.
        Raises ARSLGateError if the operation would bleed the system.
        """
        self._gate_calls += 1
        self._last_gate_ts = time.time()

        # 1. Harvested Value estimate
        # The RIC's phi_budget represents the maximum value this operation
        # can harvest. Scale by a base value factor.
        harvested_value = ric.phi_budget * self._value_multiplier(ric.action)

        # 2. Deployment Cost
        cost_mult = _ACTION_COST_MULTIPLIER.get(ric.action, 0.30)
        deployment_cost = cost_mult * ric.phi_budget

        # 3. Fragility Penalty
        fragility = self._resources.fragility_penalty()

        # 4. THE THERMODYNAMIC LAW
        if harvested_value <= (deployment_cost + fragility):
            self._gate_rejections += 1
            raise ARSLGateError(
                harvested_value=harvested_value,
                deployment_cost=deployment_cost,
                fragility_penalty=fragility,
                resource_report=self._resources.to_dict(),
                ric_id=ric.ric_id,
            )

        return {
            "harvested_value": harvested_value,
            "deployment_cost": deployment_cost,
            "fragility_penalty": fragility,
            "surplus": harvested_value - deployment_cost - fragility,
            "gate_calls": self._gate_calls,
            "gate_rejections": self._gate_rejections,
        }

    def _value_multiplier(self, action: RICAction) -> float:
        """
        Estimate the value extraction ratio for an action type.

        Execute and replicate have the highest value potential.
        Route-only and value signals have modest returns.
        """
        _VALUE_MULT: Dict[RICAction, float] = {
            RICAction.A2A_ROUTE:       1.2,
            RICAction.A2A_EXECUTE:     2.0,
            RICAction.API_CALL:        1.5,
            RICAction.RESOURCE_ALLOC:  1.0,
            RICAction.CONSTRAINT_MOD:  1.3,
            RICAction.FISSION:         1.8,
            RICAction.META_EVOLVE:     2.5,
            RICAction.GOEDEL_INJECT:   1.6,
            RICAction.VALUE_SIGNAL:    3.0,
            RICAction.NODE_REPLICATE:  2.0,
        }
        return _VALUE_MULT.get(action, 1.0)

    # ──────────────────────────────────────────
    # Reporting
    # ──────────────────────────────────────────

    def get_report(self) -> Dict[str, Any]:
        """Full ARSL status report for the /health endpoint."""
        return {
            "resources": self._resources.to_dict(),
            "fragility_penalty": self._resources.fragility_penalty(),
            "gate_calls": self._gate_calls,
            "gate_rejections": self._gate_rejections,
            "rejection_rate": (
                self._gate_rejections / self._gate_calls
                if self._gate_calls > 0 else 0.0
            ),
            "last_gate_ts": self._last_gate_ts,
        }

    def get_limits_for_genome(self) -> Dict[str, float]:
        """
        Export the ARSL constraint hypergraph as a pure dict
        for serialization into node_template.json (NTG Pillar 4).
        No MLX arrays, no live objects.
        """
        return {
            "resource_state": self._resources.to_dict(),
            "fragility_weights": dict(_FRAGILITY_WEIGHTS),
            "action_cost_multipliers": {
                k.value: v for k, v in _ACTION_COST_MULTIPLIER.items()
            },
            "min_harvest_ratio": _MIN_HARVEST_RATIO,
            "gate_statistics": {
                "total_calls": self._gate_calls,
                "total_rejections": self._gate_rejections,
            },
        }
