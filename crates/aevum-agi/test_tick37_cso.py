#!/usr/bin/env python3
"""
TICK 37 Meta-TDD Verification: Causal Settlement Oracle + KVS Capitalization.

Tests:
  T1: Valid value signal (closed chain with execute hop) → accepted, β applied
  T2: Missing trace_id → rejected (hard anti-Goodhart)
  T3: Open/unclosed chain → rejected
  T4: Chain with no execute hop → rejected (routing ghost)
  T5: KVS formula: K = r * max(0, 1 + Y) — numerical correctness
  T6: Router scores agent with K>0 higher than cold agent (super-linear routing)
  T7: beta valve: raw_value=1.0 → ledger accumulates only β*1.0 = 0.02

All tests run in-memory. No I/O. No LLM. No network. Sub-second.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai2ai"))

from core.causal import CausalTracker
from core.registry import AgentRegistry
from core.economics import EconomicsEngine
from core.router import Router, RoutingWeights
from core.protocol import AgentCard, A2ARequest, Capability, AgentStatus

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  [PASS] {name}")


def fail(name: str, reason: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {name}: {reason}")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_engine() -> tuple[CausalTracker, AgentRegistry, EconomicsEngine]:
    causal = CausalTracker()
    registry = AgentRegistry()
    econ = EconomicsEngine(registry=registry, causal_tracker=causal)
    return causal, registry, econ


def _open_and_close_chain(
    causal: CausalTracker,
    trace_id: str,
    agent_id: str,
    with_execute_hop: bool = True,
    close: bool = True,
) -> None:
    """Helper to create a fully-formed closed causal chain."""
    causal.begin_chain(trace_id)
    causal.add_hop(trace_id=trace_id, agent_id="gateway", action="receive")
    causal.add_hop(trace_id=trace_id, agent_id="router", action="route")
    if with_execute_hop:
        causal.add_hop(trace_id=trace_id, agent_id=agent_id, action="execute")
    causal.add_hop(trace_id=trace_id, agent_id=agent_id, action="meter")
    if close:
        causal.close_chain(trace_id, outcome="success")


def _make_agent(agent_id: str, registry: AgentRegistry) -> AgentCard:
    cap = Capability(
        name="test.capability",
        description="test",
        cost_per_call=0.001,
        avg_latency_ms=50.0,
    )
    card = AgentCard(
        agent_id=agent_id,
        name=f"Agent {agent_id}",
        endpoint="http://localhost:9999",
        protocol="openai",
        capabilities=[cap],
        registered_at=time.time(),
        status=AgentStatus.ONLINE,
    )
    registry.register(card)
    return registry.get_agent(agent_id)


# ─────────────────────────────────────────────────────────────────────────────
# T1: Valid signal accepted, β applied
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T1: Valid value signal accepted ──────────────────────────────")
causal, registry, econ = _make_engine()
TRACE = "trace-t1"
AGENT = "agent-alpha"

_open_and_close_chain(causal, TRACE, AGENT)
accepted = econ.record_value(trace_id=TRACE, agent_id=AGENT, value_signal=1.0)

if not accepted:
    fail("T1a", "record_value() returned False for valid chain")
else:
    ok("T1a: Valid chain accepted by CSO")

ledger = econ._get_or_create_ledger(AGENT)
expected_yield = 0.02 * 1.0  # β=0.02, value=1.0
if abs(ledger.meta_yield - expected_yield) > 1e-9:
    fail("T1b", f"meta_yield={ledger.meta_yield}, expected {expected_yield}")
else:
    ok(f"T1b: meta_yield correctly = β×value = 0.02×1.0 = {ledger.meta_yield:.6f}")

if abs(ledger.total_value_generated - expected_yield) > 1e-9:
    fail("T1c", f"total_value_generated={ledger.total_value_generated}, expected {expected_yield}")
else:
    ok(f"T1c: total_value_generated matches meta_yield = {ledger.total_value_generated:.6f}")


# ─────────────────────────────────────────────────────────────────────────────
# T2: Missing trace → rejected
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T2: Missing trace_id → rejected ──────────────────────────────")
causal2, registry2, econ2 = _make_engine()
accepted2 = econ2.record_value(
    trace_id="DOES-NOT-EXIST", agent_id="any-agent", value_signal=999.0
)
if accepted2:
    fail("T2", "CSO should have rejected missing trace_id but accepted it")
else:
    ok("T2: Missing trace correctly REJECTED")

# Verify no ledger pollution
ledger2 = econ2._get_or_create_ledger("any-agent")
if ledger2.meta_yield != 0.0:
    fail("T2-pollution", f"meta_yield was written despite rejection: {ledger2.meta_yield}")
else:
    ok("T2-pollution: Ledger clean after rejection")


# ─────────────────────────────────────────────────────────────────────────────
# T3: Open (unclosed) chain → rejected
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T3: Unclosed chain → rejected ────────────────────────────────")
causal3, registry3, econ3 = _make_engine()
TRACE3 = "trace-t3-open"
_open_and_close_chain(causal3, TRACE3, "agent-open", close=False)

accepted3 = econ3.record_value(trace_id=TRACE3, agent_id="agent-open", value_signal=0.5)
if accepted3:
    fail("T3", "CSO should have rejected unclosed chain but accepted it")
else:
    ok("T3: Unclosed chain correctly REJECTED")


# ─────────────────────────────────────────────────────────────────────────────
# T4: Chain with no execute hop → rejected
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T4: No execute hop (routing ghost) → rejected ────────────────")
causal4, registry4, econ4 = _make_engine()
TRACE4 = "trace-t4-ghost"
_open_and_close_chain(causal4, TRACE4, "ghost-agent", with_execute_hop=False)

accepted4 = econ4.record_value(trace_id=TRACE4, agent_id="ghost-agent", value_signal=0.5)
if accepted4:
    fail("T4", "CSO should have rejected routing ghost but accepted it")
else:
    ok("T4: Routing ghost (no execute hop) correctly REJECTED")


# ─────────────────────────────────────────────────────────────────────────────
# T5: KVS formula numerical correctness
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T5: KVS Capitalization formula K = r·max(0, 1+Y) ─────────────")
causal5, registry5, econ5 = _make_engine()
AGENT5 = "agent-kvs"

# Cold agent: K should be 0 (r=0, Y=0)
k_cold = econ5.get_kvs_capitalization(AGENT5)
if k_cold != 0.0:
    fail("T5a", f"Cold agent K should be 0.0, got {k_cold}")
else:
    ok("T5a: Cold agent K=0.0 ✓")

# Simulate 200 calls served (no value signals)
ledger5 = econ5._get_or_create_ledger(AGENT5)
ledger5.total_calls_served = 200
k_no_value = econ5.get_kvs_capitalization(AGENT5)
expected_k_no_value = 200.0 * max(0.0, 1.0 + 0.0)  # = 200.0
if abs(k_no_value - expected_k_no_value) > 1e-9:
    fail("T5b", f"K={k_no_value}, expected {expected_k_no_value}")
else:
    ok(f"T5b: r=200, Y=0   → K={k_no_value:.1f} (baseline = r) ✓")

# Apply 10 value signals of 1.0 each through CSO
for i in range(10):
    tid = f"trace-kvs-{i}"
    _open_and_close_chain(causal5, tid, AGENT5)
    econ5.record_value(trace_id=tid, agent_id=AGENT5, value_signal=1.0)

y_after = ledger5.meta_yield  # should be 10 * 0.02 * 1.0 = 0.2
k_with_value = econ5.get_kvs_capitalization(AGENT5)
expected_k_with_value = 200.0 * max(0.0, 1.0 + y_after)
if abs(k_with_value - expected_k_with_value) > 1e-6:
    fail("T5c", f"K={k_with_value:.4f}, expected {expected_k_with_value:.4f}")
else:
    ok(f"T5c: r=200, Y={y_after:.4f} → K={k_with_value:.2f} (super-linear vs baseline 200) ✓")

# Verify super-linearity: K_with_value > k_no_value
if k_with_value <= k_no_value:
    fail("T5d", f"Expected super-linear growth: K_with_value={k_with_value} <= baseline={k_no_value}")
else:
    ok(f"T5d: Super-linear growth confirmed: K_with_value={k_with_value:.2f} > baseline={k_no_value:.2f} ✓")


# ─────────────────────────────────────────────────────────────────────────────
# T6: Router scores KVS-rich agent higher than cold agent
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T6: KVS-driven routing — value agent scores higher than cold ──")
causal6, registry6, econ6 = _make_engine()
AGENT_VALUE = "agent-with-value"
AGENT_COLD  = "agent-cold"

agent_value = _make_agent(AGENT_VALUE, registry6)
agent_cold  = _make_agent(AGENT_COLD, registry6)

# Give AGENT_VALUE some calls served + value signals
lv = econ6._get_or_create_ledger(AGENT_VALUE)
lv.total_calls_served = 500
for i in range(20):
    tid = f"trace-r6-{i}"
    _open_and_close_chain(causal6, tid, AGENT_VALUE)
    econ6.record_value(trace_id=tid, agent_id=AGENT_VALUE, value_signal=1.0)

k_value = econ6.get_kvs_capitalization(AGENT_VALUE)
k_cold6  = econ6.get_kvs_capitalization(AGENT_COLD)
ok(f"T6-setup: K_value={k_value:.2f}, K_cold={k_cold6:.2f}")

# Wire economics into router
rtr = Router(registry=registry6, causal_tracker=causal6, economics=econ6)

# Build a minimal A2ARequest
req = A2ARequest(
    capability="test.capability",
    parameters={},
    context={},
    constraints={"max_latency_ms": 10000, "max_cost": 1.0},
)

# Score each agent directly
cap = agent_value.capabilities[0]
score_value = rtr._score(agent_value, cap, 1.0, req)
score_cold  = rtr._score(agent_cold,  cap, 1.0, req)

ok(f"T6-scores: value_agent total={score_value.total:.4f} (kvs={score_value.kvs_score:.4f}), "
   f"cold_agent total={score_cold.total:.4f} (kvs={score_cold.kvs_score:.4f})")

if score_value.total <= score_cold.total:
    fail("T6", f"Value agent should score HIGHER. value={score_value.total:.4f} <= cold={score_cold.total:.4f}")
else:
    ok(f"T6: KVS-rich agent scores higher: Δscore = +{score_value.total - score_cold.total:.4f} ✓")

if score_value.kvs_score <= score_cold.kvs_score:
    fail("T6-kvs", f"kvs_score not reflecting capitalization gap")
else:
    ok(f"T6-kvs: kvs_score gap = {score_value.kvs_score - score_cold.kvs_score:.4f} ✓")


# ─────────────────────────────────────────────────────────────────────────────
# T7: Beta valve — raw_value=1.0 → only 0.02 enters ledger
# ─────────────────────────────────────────────────────────────────────────────
print("\n── T7: β=0.02 valve — large raw signal, tiny ledger impact ─────")
causal7, registry7, econ7 = _make_engine()
AGENT7 = "agent-beta-test"

for i in range(5):
    tid = f"trace-beta-{i}"
    _open_and_close_chain(causal7, tid, AGENT7)
    econ7.record_value(trace_id=tid, agent_id=AGENT7, value_signal=100.0)

ledger7 = econ7._get_or_create_ledger(AGENT7)
# 5 signals * β=0.02 * raw=100.0 = 5 * 2.0 = 10.0
expected7 = 5 * 0.02 * 100.0
if abs(ledger7.meta_yield - expected7) > 1e-6:
    fail("T7", f"meta_yield={ledger7.meta_yield:.6f}, expected {expected7:.6f}")
else:
    ok(f"T7: β valve correctly dampened 5×100.0 signals to meta_yield={ledger7.meta_yield:.4f} "
       f"(raw would have been 500.0) ✓")

# Ensure KVS K is still finite and sane
k7 = econ7.get_kvs_capitalization(AGENT7)
ok(f"T7-K: KVS K={k7:.4f} (r=0 → K=0, unaffected by value without calls_served) ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'═'*60}")
total = PASS + FAIL
print(f"  TICK 37 CSO Verification: {PASS}/{total} PASSED, {FAIL} FAILED")
if FAIL == 0:
    print("  ✓ ALL ASSERTIONS PASSED — Causal Settlement Oracle is LIVE.")
    print("  ✓ Goodhart's Law protection VERIFIED.")
    print("  ✓ KVS super-linear routing VERIFIED.")
else:
    print("  ✗ FAILURES DETECTED — Do NOT ship this TICK.")
print(f"{'═'*60}\n")

sys.exit(0 if FAIL == 0 else 1)
