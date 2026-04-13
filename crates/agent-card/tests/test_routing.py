"""
tests/test_routing.py
=====================
Routing Tests — 路由層測試套件

Phase 1: 結構測試（驗證 Pydantic 模型和類定義正確）
Phase 2: 完整路由邏輯測試（在 Router 實現後啟用）
"""

from __future__ import annotations

import pytest

from core.protocol import (
    AgentCard,
    AgentStatus,
    Capability,
    Envelope,
    MessageType,
    A2ARequest,
    A2AResponse,
    CausalHop,
    CausalChain,
)


# ──────────────────────────────────────────────
# Phase 1: Protocol Model Tests
# ──────────────────────────────────────────────

def test_capability_creation():
    """Capability model instantiates with correct defaults."""
    cap = Capability(name="text.summarize", description="Summarize text")
    assert cap.name == "text.summarize"
    assert cap.cost_per_call == 0.0
    assert cap.embedding is None


def test_agent_card_creation():
    """AgentCard model instantiates with auto-generated agent_id."""
    card = AgentCard(
        name="Test Agent",
        endpoint="http://localhost:9000",
        capabilities=[
            Capability(name="test.ping", description="Health check")
        ],
    )
    assert card.agent_id is not None
    assert len(card.agent_id) == 12
    assert card.status == AgentStatus.ONLINE
    assert card.reputation == 0.5
    assert card.capability_names() == ["test.ping"]


def test_envelope_creation():
    """Envelope model instantiates with auto-generated IDs and defaults."""
    env = Envelope(payload={"key": "value"})
    assert env.message_id is not None
    assert env.trace_id is not None
    assert env.message_type == MessageType.REQUEST
    assert env.hop_count == 0
    assert env.ttl == 10


def test_a2a_request_creation():
    """A2ARequest model requires capability field."""
    req = A2ARequest(
        capability="text.summarize",
        parameters={"text": "Hello world"},
        constraints={"max_latency_ms": 5000},
    )
    assert req.capability == "text.summarize"
    assert req.parameters["text"] == "Hello world"


def test_causal_chain_creation():
    """CausalChain model initializes in pending state."""
    chain = CausalChain(trace_id="test-trace-001")
    assert chain.outcome == "pending"
    assert chain.hops == []
    assert chain.closed_at is None


# ──────────────────────────────────────────────
# Phase 2: Router Tests (deferred — stubs)
# ──────────────────────────────────────────────

@pytest.mark.skip(reason="Router implementation pending Phase 2")
def test_router_exact_match():
    """Router selects agent with exact capability name match."""
    pass


@pytest.mark.skip(reason="Router implementation pending Phase 2")
def test_router_semantic_fallback():
    """Router falls back to text-semantic matching when no exact match."""
    pass


@pytest.mark.skip(reason="Router implementation pending Phase 2")
def test_router_no_agents():
    """Router returns None when no agents are registered."""
    pass


@pytest.mark.skip(reason="Causal tracker implementation pending Phase 2")
def test_causal_tracker_full_lifecycle():
    """CausalTracker records complete request lifecycle."""
    pass
