"""
test_tick41_pces.py
===================
Meta-TDD verification for TICK 41.0 — Positive Convexity Exposure Surface.

Tests:
  1. Low-value CSO settlement → NO membrane deformation, PCES unchanged
  2. Massive positive tail event → PCES fraction updates, β expands irreversibly
  3. Repeated tail events → β compounds up to PCES_MAX_BETA cap
  4. Irreversibility guarantee → β never decreases across any sequence
  5. PCES metric accuracy — pces_fraction matches manual calculation
  6. Deformation log integrity — frozen dataclass, audit trail is complete

Usage:
    python test_tick41_pces.py
"""

from __future__ import annotations

import sys
import time
import uuid

# ── Bootstrap path ────────────────────────────────────────────────────────────
sys.path.insert(0, "/Volumes/Aevum/Obsidian/Opus_agi")

from ai2ai.core.economics import (
    EconomicsEngine,
    PCES_TAIL_THRESHOLD,
    PCES_TAIL_BETA_MULTIPLIER,
    PCES_MAX_BETA,
    MembraneDeformationEvent,
)
from ai2ai.core.registry import AgentRegistry
from ai2ai.core.causal import CausalTracker
from ai2ai.core.protocol import AgentCard, Capability

# ── Test harness ──────────────────────────────────────────────────────────────

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    msg = f"{tag} {name}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    _results.append((name, condition, detail))
    return condition


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_engine() -> EconomicsEngine:
    registry = AgentRegistry()
    causal = CausalTracker()
    return EconomicsEngine(registry=registry, causal_tracker=causal)


def register_agent(engine: EconomicsEngine, agent_id: str) -> str:
    card = AgentCard(
        agent_id=agent_id,
        name=agent_id,
        endpoint="http://localhost:9999",
        capabilities=[Capability(name="test.cap", version="1.0")],
    )
    engine.registry.register(card)
    return agent_id


def open_and_close_trace(engine: EconomicsEngine, agent_id: str) -> str:
    """Create a fully closed causal chain with an execute hop."""
    trace_id = uuid.uuid4().hex[:16]
    engine.causal.begin_chain(trace_id)
    engine.causal.add_hop(
        trace_id=trace_id,
        agent_id=agent_id,
        action="execute",
        cost=0.01,
        latency_ms=50.0,
    )
    engine.causal.close_chain(trace_id)
    return trace_id


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Low-value settlement: no membrane deformation
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 1: Low-value settlement → no deformation ──")

eng = make_engine()
agent_a = register_agent(eng, "agent-alpha")

# Settle with a value well below PCES_TAIL_THRESHOLD
low_trace = open_and_close_trace(eng, agent_a)
low_value = PCES_TAIL_THRESHOLD * 0.5   # e.g. 2.5
ok = eng.record_value(low_trace, agent_a, low_value)

ledger_a = eng._get_or_create_ledger(agent_a)
check("T1.a: CSO accepted", ok)
check("T1.b: beta_weight unchanged at 0.02", abs(ledger_a.beta_weight - 0.02) < 1e-9,
      f"beta={ledger_a.beta_weight:.6f}")
check("T1.c: deformation_count=0", ledger_a.deformation_count == 0,
      f"count={ledger_a.deformation_count}")

pces = eng.get_pces_metric()
# meta_yield = 0.02 * low_value < PCES_TAIL_THRESHOLD, so no tail agents
check("T1.d: no tail agents in PCES", len(pces["tail_agents"]) == 0,
      f"tail_agents={pces['tail_agents']}")
check("T1.e: deformation_log_count=0", pces["deformation_log_count"] == 0)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Massive positive tail event → PCES updates + β expands
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 2: Massive tail event → PCES update + β expansion ──")

eng2 = make_engine()
agent_b = register_agent(eng2, "agent-beta")

tail_trace = open_and_close_trace(eng2, agent_b)
tail_value = PCES_TAIL_THRESHOLD * 10.0   # e.g. 50.0  — clear positive Black Swan

beta_before_expected = 0.02
beta_after_expected = min(beta_before_expected * PCES_TAIL_BETA_MULTIPLIER, PCES_MAX_BETA)

ok2 = eng2.record_value(tail_trace, agent_b, tail_value)
ledger_b = eng2._get_or_create_ledger(agent_b)

check("T2.a: CSO accepted", ok2)
check("T2.b: beta expanded", ledger_b.beta_weight > beta_before_expected,
      f"beta={ledger_b.beta_weight:.6f} (expected >{beta_before_expected})")
check("T2.c: beta matches formula",
      abs(ledger_b.beta_weight - beta_after_expected) < 1e-9,
      f"got={ledger_b.beta_weight:.6f} expected={beta_after_expected:.6f}")
check("T2.d: deformation_count=1", ledger_b.deformation_count == 1)

pces2 = eng2.get_pces_metric()
# meta_yield = beta_after_expected * tail_value — check it exceeds threshold
meta_yield_b = ledger_b.meta_yield
check("T2.e: tail agent appears in PCES",
      agent_b in pces2["tail_agents"],
      f"tail_agents={pces2['tail_agents']}, meta_yield={meta_yield_b:.6f}")
check("T2.f: pces_fraction > 0", pces2["pces_fraction"] > 0,
      f"pces_fraction={pces2['pces_fraction']:.6f}")
check("T2.g: deformation_log_count=1", pces2["deformation_log_count"] == 1)

# Verify the deformation event record
log2 = eng2.get_deformation_log()
check("T2.h: deformation log has 1 entry", len(log2) == 1)
ev2: MembraneDeformationEvent = log2[0]
check("T2.i: event is frozen MembraneDeformationEvent",
      isinstance(ev2, MembraneDeformationEvent))
check("T2.j: event.agent_id correct", ev2.agent_id == agent_b)
check("T2.k: event.raw_value_signal correct", ev2.raw_value_signal == tail_value)
check("T2.l: event.beta_before=0.02", abs(ev2.beta_before - 0.02) < 1e-9)
check("T2.m: event.beta_after matches formula",
      abs(ev2.beta_after - beta_after_expected) < 1e-9)
check("T2.n: event.deformation_index=1", ev2.deformation_index == 1)

# Verify immutability of event
try:
    ev2.beta_after = 9999.0  # type: ignore[misc]
    check("T2.o: frozen event is immutable", False, "SHOULD have raised FrozenInstanceError")
except Exception:
    check("T2.o: frozen event is immutable", True)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Repeated tail events → β compounds, bounded by PCES_MAX_BETA
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 3: Repeated tail events → compound β expansion up to cap ──")

eng3 = make_engine()
agent_c = register_agent(eng3, "agent-gamma")

beta_track = 0.02
deform_count = 0
n_events = 30  # well beyond what's needed to hit the cap

for i in range(n_events):
    tr = open_and_close_trace(eng3, agent_c)
    eng3.record_value(tr, agent_c, PCES_TAIL_THRESHOLD * 2.0)
    ledger_c = eng3._get_or_create_ledger(agent_c)
    new_beta = ledger_c.beta_weight

    # β must be monotonically non-decreasing
    check(f"T3.{i}: β non-decreasing after event {i+1}",
          new_beta >= beta_track,
          f"beta {beta_track:.6f} → {new_beta:.6f}")
    beta_track = new_beta

    # β must never exceed cap
    check(f"T3.{i}.cap: β ≤ PCES_MAX_BETA after event {i+1}",
          new_beta <= PCES_MAX_BETA + 1e-9,
          f"beta={new_beta:.6f} cap={PCES_MAX_BETA}")

ledger_c_final = eng3._get_or_create_ledger(agent_c)
check("T3.final: β eventually reaches cap",
      abs(ledger_c_final.beta_weight - PCES_MAX_BETA) < 1e-9,
      f"beta_final={ledger_c_final.beta_weight:.6f}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Irreversibility: β never decreases regardless of low events after high
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 4: Irreversibility guarantee ──")

eng4 = make_engine()
agent_d = register_agent(eng4, "agent-delta")

# First: a massive tail event that expands β
tr_big = open_and_close_trace(eng4, agent_d)
eng4.record_value(tr_big, agent_d, PCES_TAIL_THRESHOLD * 20.0)
beta_after_big = eng4._get_or_create_ledger(agent_d).beta_weight

# Now flood with many tiny values
for _ in range(100):
    tr_tiny = open_and_close_trace(eng4, agent_d)
    eng4.record_value(tr_tiny, agent_d, 0.001)

beta_after_flood = eng4._get_or_create_ledger(agent_d).beta_weight
check("T4.a: β never decreases after tiny floods",
      beta_after_flood >= beta_after_big,
      f"beta_after_big={beta_after_big:.6f} beta_after_flood={beta_after_flood:.6f}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — PCES fraction accuracy
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 5: PCES fraction manual verification ──")

eng5 = make_engine()
agent_hi = register_agent(eng5, "agent-hi-yield")
agent_lo = register_agent(eng5, "agent-lo-yield")

# High-yield agent: a tail event
tr_hi = open_and_close_trace(eng5, agent_hi)
eng5.record_value(tr_hi, agent_hi, PCES_TAIL_THRESHOLD * 10.0)

# Low-yield agent: many tiny settlements (no tail)
for _ in range(20):
    tr_lo = open_and_close_trace(eng5, agent_lo)
    eng5.record_value(tr_lo, agent_lo, 0.1)

ledger_hi = eng5._get_or_create_ledger(agent_hi)
ledger_lo = eng5._get_or_create_ledger(agent_lo)

total_y = ledger_hi.meta_yield + ledger_lo.meta_yield
# Tail agents are those with deformation_count > 0; hi-yield agent was deformed,
# lo-yield agent (tiny settlements below threshold) was not.
expected_pces = ledger_hi.meta_yield / max(total_y, 1e-9)

pces5 = eng5.get_pces_metric()
check("T5.a: pces_fraction matches manual calculation",
      abs(pces5["pces_fraction"] - expected_pces) < 1e-9,
      f"pces={pces5['pces_fraction']:.6f} expected={expected_pces:.6f}")
check("T5.b: only hi-yield agent in tail_agents",
      pces5["tail_agents"] == [agent_hi],
      f"tail_agents={pces5['tail_agents']}")
check("T5.c: absolute_surface = hi ledger meta_yield",
      abs(pces5["absolute_surface"] - ledger_hi.meta_yield) < 1e-9,
      f"abs_surface={pces5['absolute_surface']:.6f} meta_yield_hi={ledger_hi.meta_yield:.6f}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 6 — PCES tail threshold in returned metric
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 6: PCES metric includes threshold constant ──")
check("T6: pces_tail_threshold reported correctly",
      pces5["pces_tail_threshold"] == PCES_TAIL_THRESHOLD,
      f"reported={pces5['pces_tail_threshold']} constant={PCES_TAIL_THRESHOLD}")

# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)
total = len(_results)
print(f"TICK 41.0 PCES Meta-TDD: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("\033[92mTICK 41.0 Complete: PCES Engine Active\033[0m")
else:
    print("\033[91mVERIFICATION FAILED — PCES engine has defects\033[0m")
    for name, ok, detail in _results:
        if not ok:
            print(f"  FAILED: {name}  {detail}")
    sys.exit(1)
