"""
reality_contract.py
===================
Reality Interface Contract (RIC) — TICK 39.0 Pillar 1

Every external interface (A2A request, API call, physical resource allocation)
MUST be wrapped in a RealityInterfaceContract before crossing the boundary.

The RIC defines the legal envelope of a single external operation:
  - read_scope:          what external state may be observed
  - execute_authority:   what actions are permitted
  - rollback_protocol:   how to revert on failure or Φ breach
  - liability_assignment: who pays the reputation/Φ tax on failure
  - artifact_yield:      the immutable KVS artifact generated on success

RIC validation is O(1) Pydantic construction — no I/O, no async.
"""

from __future__ import annotations

import hashlib
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class RICAction(str, Enum):
    """Canonical action types that cross the boundary."""
    A2A_ROUTE       = "a2a_route"
    A2A_EXECUTE     = "a2a_execute"
    API_CALL        = "api_call"
    RESOURCE_ALLOC  = "resource_alloc"
    CONSTRAINT_MOD  = "constraint_mod"
    FISSION         = "fission"
    META_EVOLVE     = "meta_evolve"
    GOEDEL_INJECT   = "goedel_inject"
    VALUE_SIGNAL    = "value_signal"
    NODE_REPLICATE  = "node_replicate"


class RollbackStrategy(str, Enum):
    """How to revert a failed RIC execution."""
    NOOP            = "noop"
    REVERT_ENVELOPE = "revert_envelope"
    RESTORE_MATRIX  = "restore_matrix"
    DEREGISTER      = "deregister"
    REFUND_METER    = "refund_meter"


# ──────────────────────────────────────────────
# Core RIC Model
# ──────────────────────────────────────────────

class RealityInterfaceContract(BaseModel):
    """
    The atomic unit of governance for any external operation.

    Every operation that crosses the system boundary (inbound or outbound)
    must be wrapped in a RIC. The RIC is validated at construction time
    (Pydantic) and then passed through the CCL → ARSL pipeline before
    the operation is permitted to execute.
    """

    # Identity
    ric_id: str = Field(
        default_factory=lambda: hashlib.sha256(
            str(time.time_ns()).encode()
        ).hexdigest()[:16]
    )
    timestamp: float = Field(default_factory=time.time)
    action: RICAction

    # Scope definition
    read_scope: List[str] = Field(
        default_factory=list,
        description="External state keys this operation may observe",
    )
    execute_authority: List[str] = Field(
        default_factory=list,
        description="Actions this operation is permitted to perform",
    )

    # Failure handling
    rollback_protocol: RollbackStrategy = RollbackStrategy.NOOP
    rollback_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Accountability
    liability_assignment: str = Field(
        default="system",
        description="Agent ID or 'system' — who pays reputation/Φ tax on failure",
    )
    phi_budget: float = Field(
        default=0.0, ge=0.0,
        description="Maximum Φ cost this operation may incur",
    )

    # Output
    artifact_yield: Dict[str, Any] = Field(
        default_factory=dict,
        description="KVS artifact schema generated on success",
    )

    # Upstream trace for causal chain continuity
    trace_id: Optional[str] = None
    parent_ric_id: Optional[str] = None

    @field_validator("execute_authority")
    @classmethod
    def _authority_not_empty(cls, v: List[str], info) -> List[str]:
        """An RIC with no execute authority is useless — reject at construction."""
        if not v:
            raise ValueError("execute_authority must contain at least one action")
        return v

    def content_hash(self) -> str:
        """Deterministic hash over the immutable fields for audit trail."""
        payload = (
            f"{self.action.value}|"
            f"{sorted(self.read_scope)}|"
            f"{sorted(self.execute_authority)}|"
            f"{self.rollback_protocol.value}|"
            f"{self.liability_assignment}|"
            f"{self.phi_budget}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def to_artifact(self, result: Any = None) -> Dict[str, Any]:
        """
        Seal the RIC into an immutable KVS artifact after successful execution.
        This is the permanent record that enters the causal chain.
        """
        return {
            "ric_id": self.ric_id,
            "action": self.action.value,
            "content_hash": self.content_hash(),
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "liability": self.liability_assignment,
            "artifact_yield": self.artifact_yield,
            "result_summary": str(result)[:256] if result is not None else None,
            "sealed_at": time.time(),
        }


# ──────────────────────────────────────────────
# RIC Factory — canonical builders for common operations
# ──────────────────────────────────────────────

def ric_for_a2a_execute(
    capability: str,
    agent_id: str,
    trace_id: Optional[str] = None,
    phi_budget: float = 1.0,
) -> RealityInterfaceContract:
    """Build a RIC for a full A2A execute operation."""
    return RealityInterfaceContract(
        action=RICAction.A2A_EXECUTE,
        read_scope=["registry", "causal_chain", "economics"],
        execute_authority=["route", "translate", "forward", "meter"],
        rollback_protocol=RollbackStrategy.REFUND_METER,
        liability_assignment=agent_id,
        phi_budget=phi_budget,
        trace_id=trace_id,
        artifact_yield={"type": "execution_receipt", "capability": capability},
    )


def ric_for_a2a_route(
    capability: str,
    trace_id: Optional[str] = None,
) -> RealityInterfaceContract:
    """Build a RIC for a route-only operation (no execution)."""
    return RealityInterfaceContract(
        action=RICAction.A2A_ROUTE,
        read_scope=["registry", "causal_chain"],
        execute_authority=["route"],
        rollback_protocol=RollbackStrategy.NOOP,
        liability_assignment="system",
        phi_budget=0.1,
        trace_id=trace_id,
        artifact_yield={"type": "route_score"},
    )


def ric_for_constraint_mod(
    modifier_id: str,
    target_categories: List[str],
    phi_budget: float = 0.5,
) -> RealityInterfaceContract:
    """Build a RIC for a constraint matrix modification."""
    return RealityInterfaceContract(
        action=RICAction.CONSTRAINT_MOD,
        read_scope=["constraint_matrix", "identity_membrane"],
        execute_authority=["modify_constraint", "apply_gradient"],
        rollback_protocol=RollbackStrategy.RESTORE_MATRIX,
        liability_assignment=modifier_id,
        phi_budget=phi_budget,
        artifact_yield={
            "type": "constraint_delta",
            "target_categories": target_categories,
        },
    )


def ric_for_api_call(
    endpoint: str,
    caller_id: str = "system",
    phi_budget: float = 0.3,
) -> RealityInterfaceContract:
    """Build a RIC for an external API call (LLM, HTTP, etc.)."""
    return RealityInterfaceContract(
        action=RICAction.API_CALL,
        read_scope=["api_quota", "latency_budget"],
        execute_authority=["api_call"],
        rollback_protocol=RollbackStrategy.NOOP,
        liability_assignment=caller_id,
        phi_budget=phi_budget,
        artifact_yield={"type": "api_receipt", "endpoint": endpoint},
    )


def ric_for_value_signal(
    agent_id: str,
    trace_id: str,
    value: float,
) -> RealityInterfaceContract:
    """Build a RIC for a downstream value signal submission."""
    return RealityInterfaceContract(
        action=RICAction.VALUE_SIGNAL,
        read_scope=["causal_chain", "economics"],
        execute_authority=["record_value", "compute_reputation"],
        rollback_protocol=RollbackStrategy.NOOP,
        liability_assignment=agent_id,
        phi_budget=0.05,
        trace_id=trace_id,
        artifact_yield={"type": "value_receipt", "raw_value": value},
    )


def ric_for_node_replicate(
    source_node_id: str,
    target_host: str,
    phi_budget: float = 5.0,
) -> RealityInterfaceContract:
    """Build a RIC for franchising a node to a new host."""
    return RealityInterfaceContract(
        action=RICAction.NODE_REPLICATE,
        read_scope=["node_genome", "arsl_limits", "ccl_credentials"],
        execute_authority=["compile_genome", "serialize_template", "deploy"],
        rollback_protocol=RollbackStrategy.DEREGISTER,
        liability_assignment=source_node_id,
        phi_budget=phi_budget,
        artifact_yield={
            "type": "franchise_receipt",
            "target_host": target_host,
        },
    )
