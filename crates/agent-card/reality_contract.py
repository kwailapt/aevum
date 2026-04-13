"""
reality_contract.py — Temporary stub for A2A Reality Interface Contract
"""

from typing import Any, Optional
from enum import Enum


class RICAction(str, Enum):
    """Stub RIC action."""
    A2A_ROUTE = "a2a.route"
    A2A_EXECUTE = "a2a.execute"
    VALUE_SIGNAL = "value.signal"


class RealityInterfaceContract:
    """Stub RIC interface."""
    
    def __init__(self, action: RICAction, capability: str = ""):
        self.ric_id = f"ric-{action.value}-{id(self)}"
        self.action = action
        self.capability = capability
        self.execute_authority = ["system"]
        self.phi_budget = 1.0
        self.liability_assignment = "system"


def ric_for_a2a_execute(capability: str = "", agent_id: str = "client", trace_id: str = None, phi_budget: float = 1.0) -> RealityInterfaceContract:
    """Stub RIC for A2A execute."""
    ric = RealityInterfaceContract(RICAction.A2A_EXECUTE, capability)
    ric.agent_id = agent_id
    ric.phi_budget = phi_budget
    return ric


def ric_for_a2a_route(capability: str = "", trace_id: str = None) -> RealityInterfaceContract:
    """Stub RIC for A2A route."""
    return RealityInterfaceContract(RICAction.A2A_ROUTE, capability)


def ric_for_value_signal(agent_id: str = "", trace_id: str = None, value: float = 0.0) -> RealityInterfaceContract:
    """Stub RIC for value signal."""
    ric = RealityInterfaceContract(RICAction.VALUE_SIGNAL)
    ric.agent_id = agent_id
    ric.value = value
    ric.trace_id = trace_id
    return ric
