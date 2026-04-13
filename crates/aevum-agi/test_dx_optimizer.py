"""
test_dx_optimizer.py
=====================
TICK 40.3 Phase 2 — Meta-TDD verification for the DX Documentation Optimizer.

Tests:
  1. compute_fitness() correctly converts raw counts to success rates and
     respects the minimum-hits threshold.
  2. pick_winner_loser() correctly identifies best and worst variants.
  3. evolve_documentation_pool() with a mock LLM call:
       - evicts the loser from _DX_VARIANTS
       - appends the new variant
       - updates _dx_telemetry
  4. evolve_documentation_pool() skips gracefully when data is insufficient.
  5. dry_run=True leaves the live pool unchanged.

No Ollama / real LLM required — all LLM calls are mocked.
No live server required — server module state is patched in-process.
"""

from __future__ import annotations

import sys
import os
import types
import copy

# ── Make project modules importable ──────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_AI2AI = os.path.join(_ROOT, "ai2ai")
for p in [_AI2AI, _ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Stub heavy server dependencies before importing server ───────────────────
# server.py imports fastapi, pydantic, governance modules etc.
# We only need its _DX_VARIANTS / _dx_telemetry globals, so we build a
# minimal stub module rather than loading the real server.

def _build_server_stub():
    stub = types.ModuleType("ai2ai.transport.server")
    stub._DX_VARIANTS = [
        {"variant_id": "A-concise",    "format": "concise",       "how_to_fix": "Use agent_id, name, description, version, protocol, endpoint, capabilities."},
        {"variant_id": "B-example",    "format": "json_example",  "how_to_fix": 'Example: {"agent_id":"org.agent.1.0.0",...}'},
        {"variant_id": "C-stepbystep", "format": "step_by_step",  "how_to_fix": "Step 1: add agent_id. Step 2: add version. Step 3: add capabilities."},
    ]
    stub._dx_telemetry = {
        "A-concise":    {"hits": 0,  "successes": 0},
        "B-example":    {"hits": 0,  "successes": 0},
        "C-stepbystep": {"hits": 0,  "successes": 0},
    }
    return stub

_server_stub = _build_server_stub()
# Register under every import alias the optimizer may resolve
sys.modules["ai2ai.transport.server"] = _server_stub
sys.modules["transport.server"]        = _server_stub

# Ensure parent package stubs exist so dotted imports don't crash
_ai2ai_pkg    = sys.modules.setdefault("ai2ai",          types.ModuleType("ai2ai"))
_transport_pkg = sys.modules.setdefault("ai2ai.transport", types.ModuleType("ai2ai.transport"))

# Now import the optimizer (it will resolve `import ai2ai.transport.server` to
# our stub above).
from transport.dx_optimizer import (
    compute_fitness,
    pick_winner_loser,
    evolve_documentation_pool,
    _MIN_HITS_THRESHOLD,
)

# ═════════════════════════════════════════════════════════════════════════════
# Test helpers
# ═════════════════════════════════════════════════════════════════════════════

_PASS = 0
_FAIL = 0

def _assert(condition: bool, label: str, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        → {detail}"
        print(msg)


def _reset_stub(telemetry_override: dict | None = None,
                pool_override: list | None = None) -> None:
    """Reset the stub server state before each test."""
    _server_stub._DX_VARIANTS[:] = [
        {"variant_id": "A-concise",    "format": "concise",       "how_to_fix": "Use required fields: agent_id, name, version, protocol, endpoint, capabilities."},
        {"variant_id": "B-example",    "format": "json_example",  "how_to_fix": 'Example body: {"agent_id":"org.x.1.0.0","version":"1.0.0",...}'},
        {"variant_id": "C-stepbystep", "format": "step_by_step",  "how_to_fix": "Step 1: agent_id. Step 2: version. Step 3: capabilities array."},
    ]
    _server_stub._dx_telemetry = {
        "A-concise":    {"hits": 0,  "successes": 0},
        "B-example":    {"hits": 0,  "successes": 0},
        "C-stepbystep": {"hits": 0,  "successes": 0},
    }
    if telemetry_override:
        _server_stub._dx_telemetry.update(telemetry_override)
    if pool_override:
        _server_stub._DX_VARIANTS[:] = pool_override


# Mock LLM call factory
def _make_mock_llm(new_id="D-generated", fmt="minimal",
                   how_to_fix="Add agent_id, version, capabilities. See /docs."):
    def _mock(winner_v, loser_v, existing_ids):
        return {
            "variant_id":            new_id,
            "format":                fmt,
            "how_to_fix":            how_to_fix,
            "improvement_rationale": f"Shorter than {winner_v['variant_id']}; clearer than {loser_v['variant_id']}.",
        }
    return _mock


# ═════════════════════════════════════════════════════════════════════════════
# Test Suite
# ═════════════════════════════════════════════════════════════════════════════

print()
print("══════════════════════════════════════════════════════")
print("  TICK 40.3 Phase 2 — DX Optimizer Test Report")
print("══════════════════════════════════════════════════════")
print()

# ─── Test 1: compute_fitness — correct rates and threshold enforcement ────────
print("── Test 1: compute_fitness() ──────────────────────────")
_reset_stub()
telem = {
    "A-concise":    {"hits": 10, "successes": 1},   # rate = 0.10
    "B-example":    {"hits": 10, "successes": 8},   # rate = 0.80
    "C-stepbystep": {"hits":  2, "successes": 1},   # below threshold → None
}
fit = compute_fitness(telem)
_assert(fit["A-concise"]    == 0.10,  "A-concise fitness = 0.10",    f"got {fit['A-concise']}")
_assert(fit["B-example"]    == 0.80,  "B-example fitness = 0.80",    f"got {fit['B-example']}")
_assert(fit["C-stepbystep"] is None,  "C-stepbystep → None (< threshold)", f"got {fit['C-stepbystep']}")
print()

# ─── Test 2: pick_winner_loser — correct identification ───────────────────────
print("── Test 2: pick_winner_loser() ───────────────────────")
winner, loser = pick_winner_loser(fit)
_assert(winner == "B-example",  f"Winner = B-example",  f"got {winner!r}")
_assert(loser  == "A-concise",  f"Loser  = A-concise",  f"got {loser!r}")
print()

# ─── Test 3: evolve_documentation_pool — full cycle with mock LLM ─────────────
print("── Test 3: evolve_documentation_pool() — mock LLM ────")
_reset_stub(telemetry_override={
    "A-concise":    {"hits": 10, "successes": 1},
    "B-example":    {"hits": 10, "successes": 8},
    "C-stepbystep": {"hits": 10, "successes": 4},
})
pool_before = [v["variant_id"] for v in _server_stub._DX_VARIANTS]
mock_llm = _make_mock_llm(new_id="D-generated", how_to_fix="Quick fix: add agent_id, version, capabilities.")

report = evolve_documentation_pool(llm_call_fn=mock_llm)

pool_after   = [v["variant_id"] for v in _server_stub._DX_VARIANTS]
telem_after  = dict(_server_stub._dx_telemetry)

_assert(report["action"]     == "evolved",    "action = 'evolved'",       f"got {report['action']!r}")
_assert(report["winner_id"]  == "B-example",  "winner identified correctly", f"got {report['winner_id']!r}")
_assert(report["loser_id"]   == "A-concise",  "loser identified correctly",  f"got {report['loser_id']!r}")
_assert("A-concise" not in pool_after,         "loser evicted from pool")
_assert("D-generated" in pool_after,           "new variant inserted into pool")
_assert("A-concise" not in telem_after,        "loser removed from telemetry")
_assert("D-generated" in telem_after,          "new variant has telemetry slot")
_assert(telem_after["D-generated"]["hits"] == 0, "new variant starts at 0 hits")

new_v = next(v for v in _server_stub._DX_VARIANTS if v["variant_id"] == "D-generated")
_assert("how_to_fix" in new_v,                 "new variant has how_to_fix field")
_assert("system_prompt" not in new_v,          "no system_prompt field (anti-pattern scrubbed)")
_assert("injection" not in new_v["how_to_fix"].lower(), "how_to_fix contains no injection language")
print()
print(f"  Pool before : {pool_before}")
print(f"  Pool after  : {pool_after}")
print(f"  New variant : variant_id={new_v['variant_id']!r}  format={new_v['format']!r}")
print(f"  how_to_fix  : {new_v['how_to_fix']!r}")
print(f"  Rationale   : {report.get('rationale','')!r}")
print()

# ─── Test 4: skip when insufficient data ──────────────────────────────────────
print("── Test 4: skip when data insufficient ───────────────")
_reset_stub(telemetry_override={
    "A-concise":    {"hits": 2, "successes": 1},   # all below threshold
    "B-example":    {"hits": 3, "successes": 2},
    "C-stepbystep": {"hits": 1, "successes": 0},
})
pool_snap = [v["variant_id"] for v in _server_stub._DX_VARIANTS]
report2 = evolve_documentation_pool(llm_call_fn=mock_llm)

_assert(report2["action"] == "skipped",        "action = 'skipped'",  f"got {report2['action']!r}")
_assert(report2["new_variant"] is None,         "new_variant = None")
_assert(
    [v["variant_id"] for v in _server_stub._DX_VARIANTS] == pool_snap,
    "pool unchanged when skipped",
)
print(f"  reason: {report2['reason']}")
print()

# ─── Test 5: dry_run leaves pool unchanged ────────────────────────────────────
print("── Test 5: dry_run=True leaves pool unchanged ────────")
_reset_stub(telemetry_override={
    "A-concise":    {"hits": 10, "successes": 1},
    "B-example":    {"hits": 10, "successes": 8},
    "C-stepbystep": {"hits": 10, "successes": 4},
})
pool_snap2 = copy.deepcopy(_server_stub._DX_VARIANTS)
telem_snap = copy.deepcopy(_server_stub._dx_telemetry)
report3    = evolve_documentation_pool(dry_run=True, llm_call_fn=mock_llm)

_assert(report3["action"] == "dry_run",             "action = 'dry_run'")
_assert(_server_stub._DX_VARIANTS == pool_snap2,    "pool unchanged after dry_run")
_assert(_server_stub._dx_telemetry == telem_snap,   "telemetry unchanged after dry_run")
_assert(report3["new_variant"] is not None,         "new_variant still generated in dry_run")
print()

# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════

total = _PASS + _FAIL
print("══════════════════════════════════════════════════════")
print(f"  Result : {_PASS}/{total} passed  ({_FAIL} failed)")
print("══════════════════════════════════════════════════════")
sys.exit(0 if _FAIL == 0 else 1)
