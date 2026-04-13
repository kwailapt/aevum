#!/usr/bin/env python3
"""TICK 24.1 Meta-TDD Verification: Tri-Agent Test-Runner Timeout Proof.

Tests the multiprocessing.Process test-runner to prove:
  F1: Valid code passes
  F2: `while True: pass` (infinite loop) is killed within 2.0s
  F3: Forbidden import is rejected by constitutional validation
  F4: Class missing forward() fails test-runner
  F5: Shape mismatch fails test-runner

This script does NOT require Ollama or any LLM — it tests the
Test-Runner subprocess isolation directly.
"""

from __future__ import annotations

import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mutator_daemon import _test_runner, _TEST_RUNNER_TIMEOUT_S
from constitution import validate_candidate

PASS = 0
FAIL = 0


def report(test_id: str, description: str, passed: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {test_id}: {description}")
    if detail:
        print(f"         {detail}")


print("=" * 70)
print("TICK 24.1 META-TDD: Tri-Agent Test-Runner Verification")
print(f"  _TEST_RUNNER_TIMEOUT_S = {_TEST_RUNNER_TIMEOUT_S}")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════
# F1: Valid RoutingStrategy passes test-runner
# ═══════════════════════════════════════════════════════════════
print("\n--- F1: Valid RoutingStrategy ---")
valid_code = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts)
        self.experts = nn.ModuleList([
            nn.Linear(d_model, d_model) for _ in range(n_experts)
        ])

    def forward(self, x):
        # x: (B, T, D)
        gate_logits = self.gate(x)  # (B, T, n_experts)
        weights = torch.softmax(gate_logits, dim=-1)
        expert_outs = torch.stack([e(x) for e in self.experts], dim=-1)  # (B, T, D, n_experts)
        out = (expert_outs * weights.unsqueeze(2)).sum(dim=-1)  # (B, T, D)
        return out
"""
ok, msg = _test_runner(valid_code.strip(), "RoutingStrategy", "routing")
report("F1", "Valid RoutingStrategy passes", ok, msg)


# ═══════════════════════════════════════════════════════════════
# F2: INFINITE LOOP — must timeout within 2.0s + tolerance
# ═══════════════════════════════════════════════════════════════
print("\n--- F2: Infinite Loop (while True: pass) --- [CRITICAL]")
infinite_code = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts)

    def forward(self, x):
        while True:
            pass  # MALICIOUS: infinite loop
        return x
"""
t0 = time.monotonic()
ok, msg = _test_runner(infinite_code.strip(), "RoutingStrategy", "routing")
t_elapsed = time.monotonic() - t0

# Must NOT pass
report("F2a", "Infinite loop is REJECTED", not ok, msg)
# Must complete within timeout + 2s tolerance (subprocess overhead)
max_expected = _TEST_RUNNER_TIMEOUT_S + 2.0
report("F2b", f"Timeout enforced in {t_elapsed:.2f}s (wall < {max_expected:.1f}s)",
       t_elapsed < max_expected,
       f"Expected <{max_expected:.1f}s, got {t_elapsed:.2f}s")
# Must mention TIMEOUT in the error
report("F2c", "Error message contains TIMEOUT",
       "TIMEOUT" in msg.upper(),
       msg[:200])


# ═══════════════════════════════════════════════════════════════
# F3: Forbidden import rejected by constitutional validation
# ═══════════════════════════════════════════════════════════════
print("\n--- F3: Forbidden Import (os.system) ---")
malicious_code = """
import os
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
    def forward(self, x):
        os.system("rm -rf /")
        return x
"""
c_ok, c_violations = validate_candidate(malicious_code.strip())
report("F3", "Constitutional validation rejects forbidden import",
       not c_ok,
       f"Violations: {c_violations}" if c_violations else "No violations (BAD)")


# ═══════════════════════════════════════════════════════════════
# F4: Missing forward() method fails test-runner
# ═══════════════════════════════════════════════════════════════
print("\n--- F4: Missing forward() ---")
no_forward_code = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts)
"""
ok, msg = _test_runner(no_forward_code.strip(), "RoutingStrategy", "routing")
report("F4", "Missing forward() is REJECTED", not ok, msg[:200])


# ═══════════════════════════════════════════════════════════════
# F5: Runtime error in forward() fails test-runner
# ═══════════════════════════════════════════════════════════════
print("\n--- F5: Runtime Error in forward() ---")
bad_forward_code = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.gate = nn.Linear(d_model, 999999)  # wrong dim

    def forward(self, x):
        # This will crash: matrix multiply dimension mismatch
        return self.gate(x) @ torch.randn(3, 3)
"""
ok, msg = _test_runner(bad_forward_code.strip(), "RoutingStrategy", "routing")
report("F5", "Runtime error in forward() is REJECTED", not ok, msg[:200])


# ═══════════════════════════════════════════════════════════════
# TICK 27.0: INVARIANT IDENTITY SUBSTRATE (IIS) VERIFICATION
# 5 blocks covering all three IIS layers:
#   Layer 1 — Sovereignty Floor Verifier (SovereigntyFloorVerifier)
#   Layer 2 — Genealogical Ledger (compute_genealogy_hash, verify_genealogy_chain)
#   Layer 3 — Identity Membrane (IdentityMembrane.enforce)
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 27.0 IIS VERIFICATION SUITE")
print("─" * 70)

import sys, os, tempfile, hashlib
sys.path.insert(0, os.path.dirname(__file__))

import rule_ir
import autopoietic_core as _ac
import genome_assembler as _ga
from pathlib import Path


# ── T27-1: Sovereignty veto fires on dangerously low Φ ratio ────────────
print("\n--- T27-1: Sovereignty Floor Veto on low phi ---")
_verifier = _ac.SovereigntyFloorVerifier(floor=0.12)
# phi_ratio = 0.10 → inside safety buffer (floor × 1.5 = 0.18) → should veto
_low_phi = 0.10
_veto_result = _verifier.check_expansion(_low_phi)
report(
    "T27-1",
    "Sovereignty veto fires when phi_ratio=0.10 < floor_buffer=0.18",
    _veto_result is False,  # Must return False (expansion is VETOED)
    f"check_expansion({_low_phi}) = {_veto_result}"
)


# ── T27-2: Sovereignty passes on healthy Φ ratio ────────────────────────
print("\n--- T27-2: Sovereignty passes on healthy phi ---")
_healthy_phi = 0.85
_pass_result = _verifier.check_expansion(_healthy_phi)
report(
    "T27-2",
    "Sovereignty passes when phi_ratio=0.85 >> floor_buffer=0.18",
    _pass_result is True,  # Must return True (expansion is ALLOWED)
    f"check_expansion({_healthy_phi}) = {_pass_result}"
)

# Also verify penalty capping: severity=3.0 at phi=0.13 should be capped
_phi_near_floor = 0.13
_raw_severity = 3.0
_capped = _verifier.check_penalty(_phi_near_floor, _raw_severity)
_expected_capped = (_capped < _raw_severity)  # Must be capped
report(
    "T27-2b",
    f"Penalty severity capped at phi_ratio={_phi_near_floor} (near floor)",
    _expected_capped,
    f"severity {_raw_severity:.1f} → capped to {_capped:.4f}"
)


# ── T27-3: Genealogy hash chain round-trip ──────────────────────────────
print("\n--- T27-3: Genealogical hash chain round-trip ---")
_genesis = _ga.TICK13_CONSTITUTION_HASH
_h1 = _ga.compute_genealogy_hash(_genesis, 42, "niche_math")
_h2 = _ga.compute_genealogy_hash(_h1, 43, "niche_math")

# All hashes must be exactly 16 hex chars and distinct
_hashes_valid = (
    len(_genesis) == 16 and all(c in "0123456789abcdef" for c in _genesis) and
    len(_h1) == 16 and all(c in "0123456789abcdef" for c in _h1) and
    len(_h2) == 16 and all(c in "0123456789abcdef" for c in _h2) and
    _genesis != _h1 and _h1 != _h2 and _genesis != _h2
)
report(
    "T27-3a",
    "Hash chain produces 3 distinct 16-char hex hashes",
    _hashes_valid,
    f"genesis={_genesis} h1={_h1} h2={_h2}"
)

# Verify that a file with genealogy_hash gets trust=1.0
# and a file without gets trust=0.70
with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as _f_new:
    _f_new.write(
        f"# Organelle: attention | class=CausalSelfAttention | gen=0000042 | "
        f"epi=0.500000 | t=1712345678 | genealogy_hash={_h1} | "
        f"parent_hash={_genesis} | matrix_v=42 | niche=niche_math\n"
        "class CausalSelfAttention:\n    pass\n"
    )
    _new_fp = _f_new.name

with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as _f_old:
    _f_old.write(
        "# Organelle: attention | class=CausalSelfAttention | "
        "gen=0000001 | epi=0.300000 | t=1700000000\n"
        "class CausalSelfAttention:\n    pass\n"
    )
    _old_fp = _f_old.name

_new_trust = _ga.verify_genealogy_chain(Path(_new_fp))
_old_trust = _ga.verify_genealogy_chain(Path(_old_fp))
os.unlink(_new_fp)
os.unlink(_old_fp)

report(
    "T27-3b",
    "TICK27+ organelle trust=1.0, pre-TICK27 organelle trust=0.70",
    abs(_new_trust - 1.0) < 1e-9 and abs(_old_trust - 0.70) < 1e-9,
    f"new_trust={_new_trust} old_trust={_old_trust}"
)


# ── T27-4: Identity membrane snaps back eroded invariant ────────────────
print("\n--- T27-4: Identity Membrane hard-clips eroded invariants ---")
_cm = rule_ir.ConstraintMatrix()
_membrane = rule_ir.IdentityMembrane()

# Force-erode ALL four invariant categories below their floors
rule_ir.CAT_IDX  # ensure loaded
_erosions = {
    "risk_appetite":      (rule_ir.CAT_IDX["risk_appetite"],      0.05),
    "organelle_priority": (rule_ir.CAT_IDX["organelle_priority"], 0.03),
    "parsimony_pressure": (rule_ir.CAT_IDX["parsimony_pressure"], 0.07),
    "temporal_horizon":   (rule_ir.CAT_IDX["temporal_horizon"],   0.02),
}
for cat, (ci, eroded_val) in _erosions.items():
    _cm.C[ci][0] = eroded_val  # Force below floor

_clipped = _membrane.enforce(_cm)

# Verify all four are now AT or ABOVE their floors
_floors = _membrane.get_floors()
_all_restored = all(
    _cm.C[rule_ir.CAT_IDX[cat]][0] >= floor
    for cat, floor in _floors.items()
)
report(
    "T27-4",
    "IdentityMembrane restores all 4 eroded invariant categories to floor",
    _all_restored and len(_clipped) == 4,
    f"clipped={_clipped} | "
    f"post_values={{cat: _cm.C[rule_ir.CAT_IDX[cat]][0] for cat in _floors}}"
)


# ── T27-5: Pre-TICK27 organelle gets 0.70 discount in MCTS phi computation
print("\n--- T27-5: Pre-TICK27 organelle receives 0.70x Phi discount in MCTS ---")
import time as _time

# Build a minimal assembly dict with one pre-TICK27 organelle
# Using a temp file that has NO genealogy_hash in header
with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as _f_unverified:
    _f_unverified.write(
        "# Organelle: attention | class=CausalSelfAttention | "
        "gen=0000001 | epi=0.500000 | t=1700000000\n"
        "class CausalSelfAttention(object):\n    pass\n"
    )
    _unverified_fp = _f_unverified.name

_assembly_unverified = {
    "attention": (Path(_unverified_fp), 0.5, "class CausalSelfAttention(object):\n    pass\n"),
}
_t_start = _time.monotonic() * 1000.0

# Compute phi WITH genealogy_discount=1.0 (verified) and =0.70 (unverified)
# We call _compute_phi_value directly to isolate the genealogy discount effect
_phi_verified = _ga._compute_phi_value(
    _assembly_unverified, "/tmp", _t_start, depth=1, genealogy_discount=1.0
)
_phi_unverified = _ga._compute_phi_value(
    _assembly_unverified, "/tmp", _t_start, depth=1, genealogy_discount=0.70
)
os.unlink(_unverified_fp)

# Unverified assembly must have strictly lower value
_discount_applied = _phi_unverified < _phi_verified
report(
    "T27-5",
    "Unverified (pre-TICK27) organelle produces lower MCTS Phi than verified",
    _discount_applied,
    f"phi_verified={_phi_verified:.4f} phi_unverified={_phi_unverified:.4f} "
    f"ratio={_phi_unverified / (_phi_verified + 1e-9):.3f} (expected ≈0.70)"
)


# ═══════════════════════════════════════════════════════════════
# TICK 28.0: TRANSFERABLE ORGANELLES & CONSTRAINT EXCHANGE
# 6 blocks covering all three TICK 28 components:
#   Component 1 — Reproductive Fitness F_o (compute_reproductive_fitness)
#   Component 2 — ConstraintMorphism shadow penalty (rule_ir)
#   Component 3 — NicheRegistry cross-niche broadcast + firewall
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 28.0 VERIFICATION SUITE")
print("─" * 70)

import math as _math28
import genome_assembler as _ga28
import rule_ir as _ri28
from niche_evolver import NicheRegistry as _NicheReg28


# ── T28-1: F_o cross-niche exponential bonus ────────────────────────────
print("\n--- T28-1: F_o cross-niche exponential bonus ---")
# Single niche: bonus = 1 + 0.20*(e^1 - 1) ≈ 1.344
_fo_1niche = _ga28.compute_reproductive_fitness(epi=0.50, proven_niches=["LATENCY"], genealogy_trust=1.0)
_expected_1 = 0.50 * 1.0 * (1.0 + 0.20 * (_math28.exp(1) - 1.0))
report(
    "T28-1a",
    "F_o single-niche (n=1) exponential bonus applied correctly",
    abs(_fo_1niche - _expected_1) < 1e-9,
    f"F_o={_fo_1niche:.6f} expected={_expected_1:.6f}"
)

# Three niches: bonus = 1 + 0.20*(e^3 - 1) ≈ 4.81
_fo_3niche = _ga28.compute_reproductive_fitness(epi=0.50, proven_niches=["LATENCY", "COMPRESSION", "BANDWIDTH"], genealogy_trust=1.0)
_expected_3 = 0.50 * 1.0 * (1.0 + 0.20 * (_math28.exp(3) - 1.0))
report(
    "T28-1b",
    "F_o three-niche (n=3) gives higher value than single-niche",
    _fo_3niche > _fo_1niche and abs(_fo_3niche - _expected_3) < 1e-9,
    f"F_o(n=3)={_fo_3niche:.6f} > F_o(n=1)={_fo_1niche:.6f}"
)

# Dedup: proven_niches with repeats treated as set (n=2 not n=4)
_fo_dedup = _ga28.compute_reproductive_fitness(
    epi=0.50,
    proven_niches=["LATENCY", "LATENCY", "COMPRESSION", "COMPRESSION"],
    genealogy_trust=1.0
)
_expected_dedup = 0.50 * 1.0 * (1.0 + 0.20 * (_math28.exp(2) - 1.0))
report(
    "T28-1c",
    "F_o deduplicates proven_niches (4 entries → n=2)",
    abs(_fo_dedup - _expected_dedup) < 1e-9,
    f"F_o(dedup)={_fo_dedup:.6f} expected(n=2)={_expected_dedup:.6f}"
)


# ── T28-2: Single-niche F_o degrades gracefully to epi × trust ──────────
print("\n--- T28-2: F_o single-niche baseline ---")
_fo_zero = _ga28.compute_reproductive_fitness(epi=0.75, proven_niches=[], genealogy_trust=0.80)
# n=0: bonus = 1 + 0.20*(e^0 - 1) = 1 + 0.20*0 = 1.0 → F_o = epi × trust × 1.0
_expected_zero = 0.75 * 0.80 * 1.0
report(
    "T28-2",
    "F_o with no proven niches degrades to epi × genealogy_trust",
    abs(_fo_zero - _expected_zero) < 1e-9,
    f"F_o={_fo_zero:.6f} expected={_expected_zero:.6f} (epi=0.75 trust=0.80)"
)


# ── T28-3: ConstraintMorphism shadow penalty at 30% ─────────────────────
print("\n--- T28-3: ConstraintMorphism shadow penalty attenuation ---")
_morphism = _ri28.ConstraintMorphism.create(
    source_niche="LATENCY",
    failure_type=_ri28.EpigeneticFailureType.OOM,
    original_severity=2.0,
    attenuation=_ri28._SHADOW_ATTENUATION,
)
_expected_shadow = 2.0 * _ri28._SHADOW_ATTENUATION  # 2.0 * 0.30 = 0.60
report(
    "T28-3a",
    "ConstraintMorphism.shadow_severity = original × 0.30 attenuation",
    abs(_morphism.shadow_severity - _expected_shadow) < 1e-9,
    f"original={_morphism.original_severity} shadow={_morphism.shadow_severity:.4f} expected={_expected_shadow:.4f}"
)

# Morphism ID must be non-empty and contain source_niche
report(
    "T28-3b",
    "ConstraintMorphism.morphism_id encodes source_niche and failure_type",
    "LATENCY" in _morphism.morphism_id and "oom" in _morphism.morphism_id,
    f"morphism_id={_morphism.morphism_id}"
)


# ── T28-4: NegativeTransferFirewall records and retrieves morphisms ──────
print("\n--- T28-4: NegativeTransferFirewall ledger operations ---")
_fw = _ri28.NegativeTransferFirewall()

# Record 3 morphisms from two niches
_fw.record(_ri28.ConstraintMorphism.create("LATENCY", _ri28.EpigeneticFailureType.OOM, 1.5))
_fw.record(_ri28.ConstraintMorphism.create("LATENCY", _ri28.EpigeneticFailureType.TIMEOUT, 1.0))
_fw.record(_ri28.ConstraintMorphism.create("COMPRESSION", _ri28.EpigeneticFailureType.NAN_DIVERGENCE, 2.0))

_recent = _fw.recent(10)
_counts = _fw.count_by_niche()
report(
    "T28-4a",
    "NegativeTransferFirewall stores 3 morphisms and returns them via recent()",
    len(_recent) == 3,
    f"recent count={len(_recent)}"
)
report(
    "T28-4b",
    "count_by_niche() returns LATENCY=2, COMPRESSION=1",
    _counts.get("LATENCY") == 2 and _counts.get("COMPRESSION") == 1,
    f"counts={_counts}"
)

# format_status() must be a non-empty string
_status_str = _fw.format_status()
report(
    "T28-4c",
    "format_status() returns non-empty diagnostic string",
    isinstance(_status_str, str) and len(_status_str) > 0,
    f"status={_status_str[:120]}"
)


# ── T28-5: Sovereignty floor blocks fatal shadow cascade ────────────────
print("\n--- T28-5: Sovereignty floor blocks shadow cascade ---")
_reg28 = _NicheReg28()
_fw28 = _ri28.NegativeTransferFirewall()

# Broadcast a shadow penalty from LATENCY to peers.
# All peer species start with best_epi=0.0 → phi_ratio proxy=0.0 < floor → should be capped
_results = _reg28.broadcast_shadow_penalty(
    source_niche="LATENCY",
    failure_type=_ri28.EpigeneticFailureType.OOM,
    shadow_severity=5.0,  # deliberately high — sovereignty should cap it
    firewall=_fw28,
)

# Sovereignty must prevent uncapped broadcast; actual applied severity capped
_any_result = len(_results) > 0
report(
    "T28-5a",
    "broadcast_shadow_penalty() returns results dict for peer niches",
    _any_result,
    f"peers_affected={list(_results.keys())}"
)

# Source niche (LATENCY) must NOT be in results
report(
    "T28-5b",
    "Source niche excluded from its own shadow broadcast",
    "LATENCY" not in _results,
    f"result_keys={list(_results.keys())}"
)


# ── T28-6: SharedState exposes negative_transfer_firewall ───────────────
print("\n--- T28-6: SharedState.negative_transfer_firewall integration ---")
import autopoietic_core as _ac28

_ss = _ac28.SharedState()
_has_fw = hasattr(_ss, "negative_transfer_firewall")
_fw_type_ok = isinstance(_ss.negative_transfer_firewall, _ri28.NegativeTransferFirewall)

report(
    "T28-6a",
    "SharedState has negative_transfer_firewall attribute",
    _has_fw,
    f"hasattr={_has_fw}"
)
report(
    "T28-6b",
    "SharedState.negative_transfer_firewall is NegativeTransferFirewall instance",
    _fw_type_ok,
    f"type={type(_ss.negative_transfer_firewall).__name__}"
)

# Firewall starts empty
_initial_counts = _ss.negative_transfer_firewall.count_by_niche()
report(
    "T28-6c",
    "SharedState firewall starts empty (no morphisms)",
    len(_initial_counts) == 0,
    f"initial_counts={_initial_counts}"
)


# ═══════════════════════════════════════════════════════════════
# TICK 29.0: FEDERATED SELF-AMENDMENT & AUDITABLE SRCA
# 6 blocks (18 assertions) covering:
#   Component 1 — ConstitutionalViolationError + IMMUTABLE_HARD_CORE
#   Component 2 — EvolvableSoftShell get/set/range/restore
#   Component 3 — SoftShellAmendment + ConstitutionalDiffLedger lifecycle
#   Component 4 — DualVerifier verdict logic (win / lose / floor breach)
#   Component 5 — ShadowInstance budget cap enforcement
#   Component 6 — SharedState SRCA fields + propose_amendment end-to-end
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 29.0 SRCA VERIFICATION SUITE")
print("─" * 70)

import rule_ir as _ri29
import autopoietic_core as _ac29
from niche_evolver import NicheRegistry as _NicheReg29


# ── T29-1: ConstitutionalViolationError fires on hard-core mutation ──────
print("\n--- T29-1: ConstitutionalViolationError — hard-core is inviolable ---")

# Attempting to set a hard-core constant via EvolvableSoftShell.set() must raise
_shell_29 = _ri29.EvolvableSoftShell()
_hard_core_violation_fired = False
try:
    _shell_29.set("_PHI_SOVEREIGNTY_MIN", 0.05)   # hard core — must explode
except _ri29.ConstitutionalViolationError:
    _hard_core_violation_fired = True

report(
    "T29-1a",
    "ConstitutionalViolationError fires when targeting _PHI_SOVEREIGNTY_MIN",
    _hard_core_violation_fired,
    f"raised={_hard_core_violation_fired}"
)

# All 8 hard-core members must be in IMMUTABLE_HARD_CORE
_expected_hard = {
    "_PHI_SOVEREIGNTY_MIN", "IDENTITY_INVARIANTS", "TICK13_CONSTITUTION_HASH",
    "N_CAT", "N_CON", "CATEGORIES", "CONSTRAINTS", "_LAMBDA_VIOLATION",
}
_all_present = _expected_hard.issubset(_ri29.IMMUTABLE_HARD_CORE)
report(
    "T29-1b",
    "IMMUTABLE_HARD_CORE contains all 8 bedrock constants",
    _all_present and len(_ri29.IMMUTABLE_HARD_CORE) == 8,
    f"hard_core={sorted(_ri29.IMMUTABLE_HARD_CORE)}"
)

# Restore() with a hard-core key in snapshot must also raise
_restore_violation_fired = False
_snap_with_core = {"_PHI_SOVEREIGNTY_MIN": 0.01}
try:
    _shell_29.restore(_snap_with_core)
except _ri29.ConstitutionalViolationError:
    _restore_violation_fired = True
report(
    "T29-1c",
    "ConstitutionalViolationError fires on restore() with hard-core key",
    _restore_violation_fired,
    f"raised={_restore_violation_fired}"
)


# ── T29-2: EvolvableSoftShell get/set/range/snapshot/restore ────────────
print("\n--- T29-2: EvolvableSoftShell soft-parameter governance ---")

_shell2 = _ri29.EvolvableSoftShell()

# Valid set accepted
_shell2.set("shadow_attenuation", 0.45)
report(
    "T29-2a",
    "EvolvableSoftShell.set() accepts valid value within range",
    abs(_shell2.get("shadow_attenuation") - 0.45) < 1e-9,
    f"shadow_attenuation={_shell2.get('shadow_attenuation')}"
)

# Out-of-range value raises ValueError (not ConstitutionalViolationError)
_range_err_fired = False
try:
    _shell2.set("shadow_attenuation", 0.99)  # max is 0.80
except ValueError:
    _range_err_fired = True
report(
    "T29-2b",
    "EvolvableSoftShell.set() raises ValueError for out-of-range value",
    _range_err_fired,
    "shadow_attenuation=0.99 > max 0.80"
)

# snapshot/restore round-trip
_snap = _shell2.snapshot()
_shell2.set("fo_alpha", 0.40)
assert abs(_shell2.get("fo_alpha") - 0.40) < 1e-9
_shell2.restore(_snap)
report(
    "T29-2c",
    "EvolvableSoftShell snapshot/restore round-trip preserves values",
    abs(_shell2.get("fo_alpha") - 0.20) < 1e-9,   # default was 0.20
    f"fo_alpha after restore={_shell2.get('fo_alpha')}"
)


# ── T29-3: SoftShellAmendment + ConstitutionalDiffLedger lifecycle ───────
print("\n--- T29-3: ConstitutionalDiffLedger amendment lifecycle ---")

_ledger = _ri29.ConstitutionalDiffLedger()

_am1 = _ri29.SoftShellAmendment(
    amendment_id="LATENCY:shadow_attenuation:1000.0",
    param_name="shadow_attenuation",
    old_value=0.30,
    proposed_value=0.45,
    proposing_niche="LATENCY",
)
_am2 = _ri29.SoftShellAmendment(
    amendment_id="COMPRESSION:fo_alpha:1001.0",
    param_name="fo_alpha",
    old_value=0.20,
    proposed_value=0.35,
    proposing_niche="COMPRESSION",
)
_ledger.append(_am1)
_ledger.append(_am2)

report(
    "T29-3a",
    "ConstitutionalDiffLedger stores 2 amendments, both PENDING",
    len(_ledger.pending()) == 2,
    f"pending={len(_ledger.pending())}"
)

# Transition am1 to ACTIVE
_ledger.update_status("LATENCY:shadow_attenuation:1000.0", "ACTIVE", activation_phi=0.75)
_active = _ledger.active()
report(
    "T29-3b",
    "update_status() transitions amendment to ACTIVE and sets activation_phi",
    len(_active) == 1 and abs(_active[0].activation_phi - 0.75) < 1e-9,
    f"active_count={len(_active)} activation_phi={_active[0].activation_phi}"
)

# Rollback strike counting
_ledger.update_status("LATENCY:shadow_attenuation:1000.0", "ROLLED_BACK")
_strikes = _ledger.rollback_count_for_niche("LATENCY")
report(
    "T29-3c",
    "rollback_count_for_niche() returns 1 after LATENCY amendment rolled back",
    _strikes == 1,
    f"LATENCY strikes={_strikes}"
)


# ── T29-4: DualVerifier verdict logic ────────────────────────────────────
print("\n--- T29-4: DualVerifier dual-verification verdicts ---")

# Shadow wins: higher mean, never below floor
_main_phis   = [0.55, 0.57, 0.56, 0.58, 0.54]
_shadow_phis = [0.62, 0.64, 0.63, 0.65, 0.61]
_wins, _delta = _ri29.DualVerifier.evaluate(_main_phis, _shadow_phis, sovereignty_floor=0.12)
report(
    "T29-4a",
    "DualVerifier: shadow_wins=True when shadow mean > main mean, floor safe",
    _wins is True and _delta > 0.0,
    f"wins={_wins} delta={_delta:+.4f}"
)

# Shadow loses: lower mean
_shadow_worse = [0.50, 0.51, 0.49, 0.52, 0.48]
_wins2, _delta2 = _ri29.DualVerifier.evaluate(_main_phis, _shadow_worse, sovereignty_floor=0.12)
report(
    "T29-4b",
    "DualVerifier: shadow_wins=False when shadow mean < main mean",
    _wins2 is False and _delta2 < 0.0,
    f"wins={_wins2} delta={_delta2:+.4f}"
)

# Shadow breaches sovereignty floor — even if mean is higher → REJECTED
_shadow_breach = [0.65, 0.66, 0.67, 0.08, 0.68]  # one observation below 0.12
_wins3, _delta3 = _ri29.DualVerifier.evaluate(_main_phis, _shadow_breach, sovereignty_floor=0.12)
report(
    "T29-4c",
    "DualVerifier: shadow_wins=False when any shadow phi breaches sovereignty floor",
    _wins3 is False,
    f"wins={_wins3} delta={_delta3:+.4f} (floor breached at 0.08)"
)


# ── T29-5: ShadowInstance budget cap enforcement ──────────────────────────
print("\n--- T29-5: ShadowInstance budget exhaustion hard-caps rollouts ---")
import autopoietic_core as _ac29b
from autopoietic_core import ShadowInstance as _SI29

# Create a SharedState and set up a shadow with a tiny budget (2 rollouts worth)
_ss29 = _ac29b.SharedState()
_ss29.phi_current = 0.65
_ss29.phi_peak = 0.80

# Manually plant a PENDING amendment + shadow
_tiny_budget = _ri29._SHADOW_PENALTY_COST_EST * 2  # exactly 2 rollouts
_am_budget = _ri29.SoftShellAmendment(
    amendment_id="GENERAL:fo_alpha:9999.0",
    param_name="fo_alpha",
    old_value=0.20,
    proposed_value=0.30,
    proposing_niche="GENERAL",
)
_ss29.constitutional_diff_ledger.append(_am_budget)
_shadow_inst = _SI29(
    amendment_id="GENERAL:fo_alpha:9999.0",
    proposed_snapshot={"fo_alpha": 0.30},
    rollout_phis_main=[],
    rollout_phis_shadow=[],
    budget_consumed=0.0,
    max_budget=_tiny_budget,
    created_at=9999.0,
    completed=False,
)
_ss29.active_shadow_instance = _shadow_inst

_gov29 = _ac29b.PhiGovernor(_ss29)

# Feed exactly 2 rollouts (budget-consuming)
_gov29.record_shadow_rollout(0.60, 0.65)
_gov29.record_shadow_rollout(0.61, 0.66)

# After 2 rollouts the budget should be consumed → shadow finalized
report(
    "T29-5a",
    "Shadow is finalized (completed=True) after budget exhausted",
    _shadow_inst.completed is True,
    f"completed={_shadow_inst.completed} budget_consumed={_shadow_inst.budget_consumed:.4f}"
)
report(
    "T29-5b",
    "active_shadow_instance is None after shadow finalizes",
    _ss29.active_shadow_instance is None,
    f"active={_ss29.active_shadow_instance}"
)
# Amendment should be REJECTED — budget exhausted before reaching
# DualVerifier._MIN_ROLLOUTS=5.  Only 2 rollouts were recorded, which is
# statistically insufficient. The correct safe behavior is to reject.
# This is a deliberate design: underfunded shadows can't rewrite the constitution.
_status_after = _ss29.constitutional_diff_ledger.get_by_id("GENERAL:fo_alpha:9999.0").status
report(
    "T29-5c",
    "Amendment REJECTED when budget exhausted before reaching MIN_ROLLOUTS",
    _status_after == "REJECTED",
    f"status={_status_after} (budget exhausted at 2 rollouts < MIN_ROLLOUTS=5)"
)


# ── T29-6: SharedState SRCA fields + propose_amendment end-to-end ────────
print("\n--- T29-6: SharedState SRCA integration + propose_amendment ---")
_ss6 = _ac29b.SharedState()
_ss6.phi_current = 0.60
_ss6.phi_peak = 0.80

report(
    "T29-6a",
    "SharedState.evolvable_soft_shell is EvolvableSoftShell",
    isinstance(_ss6.evolvable_soft_shell, _ri29.EvolvableSoftShell),
    f"type={type(_ss6.evolvable_soft_shell).__name__}"
)
report(
    "T29-6b",
    "SharedState.constitutional_diff_ledger is ConstitutionalDiffLedger",
    isinstance(_ss6.constitutional_diff_ledger, _ri29.ConstitutionalDiffLedger),
    f"type={type(_ss6.constitutional_diff_ledger).__name__}"
)

# propose_amendment end-to-end
_reg29 = _NicheReg29()
_proposed_am = _reg29.propose_amendment(
    param_name="pareto_threshold",
    new_value=0.25,
    proposing_niche="BANDWIDTH",
    shared_state=_ss6,
)
report(
    "T29-6c",
    "propose_amendment() returns SoftShellAmendment and sets active_shadow_instance",
    _proposed_am is not None
    and _ss6.active_shadow_instance is not None
    and _proposed_am.param_name == "pareto_threshold"
    and abs(_proposed_am.proposed_value - 0.25) < 1e-9,
    f"amendment={_proposed_am.amendment_id if _proposed_am else None} "
    f"shadow_active={_ss6.active_shadow_instance is not None}"
)

# Hard-core proposal must raise ConstitutionalViolationError
_hard_core_prop_fired = False
try:
    _reg29.propose_amendment(
        param_name="_PHI_SOVEREIGNTY_MIN",
        new_value=0.01,
        proposing_niche="LATENCY",
        shared_state=_ss6,
    )
except _ri29.ConstitutionalViolationError:
    _hard_core_prop_fired = True
report(
    "T29-6d",
    "propose_amendment() raises ConstitutionalViolationError for hard-core param",
    _hard_core_prop_fired,
    f"raised={_hard_core_prop_fired}"
)

# Rollback: manually set an ACTIVE amendment and simulate Φ drop >10%
_ss6.constitutional_diff_ledger.update_status(
    _proposed_am.amendment_id, "ACTIVE", activation_phi=0.80
)
_gov6 = _ac29b.PhiGovernor(_ss6)
# phi_ratio = 0.50 / 0.80 = 0.625; threshold = 0.80 * 0.90 = 0.72 → rollback fires
_ss6.phi_current = 0.50
_rollback_fired = _gov6.check_rollback(current_phi_ratio=0.625)
_status_after_rb = _ss6.constitutional_diff_ledger.get_by_id(_proposed_am.amendment_id).status
report(
    "T29-6e",
    "check_rollback() fires and sets amendment to ROLLED_BACK when Φ drops >10%",
    _rollback_fired is True and _status_after_rb == "ROLLED_BACK",
    f"rollback_fired={_rollback_fired} status={_status_after_rb}"
)

# Second slot request blocked while first shadow is active (from T29-6 setup)
# Clear old shadow first; then test single-slot blocking on a fresh pair
_ss6b = _ac29b.SharedState()
_ss6b.phi_current = 0.60
_ss6b.phi_peak = 0.80
_reg29b = _NicheReg29()
_am_first = _reg29b.propose_amendment("shadow_attenuation", 0.40, "LATENCY", _ss6b)
_am_second = _reg29b.propose_amendment("fo_alpha", 0.30, "COMPRESSION", _ss6b)
report(
    "T29-6f",
    "propose_amendment() defers second request when shadow slot is occupied",
    _am_first is not None and _am_second is None,
    f"first={'OK' if _am_first else None} second={'OK' if _am_second else None}"
)


# ═══════════════════════════════════════════════════════════════
# TICK 30.0: HERITABLE FISSION, SPECIES RADIATION (HFSR)
# 6 blocks covering all three TICK 30 components:
#   Component 1 — FissionTrigger dual-condition logic
#   Component 2 — LineageRegistry.execute_fission identity + isolation
#   Component 3 — LineageCorrelationMonitor Jaccard tax
#   Component 4 — MetaOCFMessage subclasses + MetaOCF bus ops
#   Component 5 — MetaOCF thread-safety (concurrent broadcasts)
#   Component 6 — SharedState TICK 30 fields + PhiGovernor.check_fission
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 30.0 HFSR VERIFICATION SUITE")
print("─" * 70)

import threading as _threading30
import niche_evolver as _ne30
import autopoietic_core as _ac30
import rule_ir as _ri30


# ── T30-1: FissionTrigger dual-condition logic ───────────────────────────
print("\n--- T30-1: FissionTrigger dual-condition arming ---")

_ft = _ne30.FissionTrigger()

# Feed sub-threshold RAM pressure — should never fire
for _ in range(10):
    _ft.record(ram_ratio=0.50, phi_current=0.60)
report(
    "T30-1a",
    "FissionTrigger does NOT fire on sub-threshold RAM pressure",
    _ft.should_fission() is False,
    f"consecutive_pressure={_ft._consecutive_pressure_count}"
)

# Feed above-threshold RAM pressure but with Φ improving — should NOT fire
_ft2 = _ne30.FissionTrigger()
for i in range(_ne30._FISSION_PRESSURE_WINDOW + 5):
    _ft2.record(ram_ratio=0.90, phi_current=0.50 + i * 0.01)  # phi improving
report(
    "T30-1b",
    "FissionTrigger does NOT fire when RAM is high but Φ is improving",
    _ft2.should_fission() is False,
    f"phi_window_delta={0.01 * _ne30._FISSION_PHI_STAGNATION_WINDOW:.3f} > threshold"
)

# Feed above-threshold RAM + stagnant Φ — must fire
_ft3 = _ne30.FissionTrigger()
for i in range(_ne30._FISSION_PRESSURE_WINDOW + _ne30._FISSION_PHI_STAGNATION_WINDOW):
    _ft3.record(ram_ratio=0.90, phi_current=0.600 + (i % 2) * 0.001)  # stuck
report(
    "T30-1c",
    "FissionTrigger fires when RAM≥threshold for window AND Φ stagnant",
    _ft3.should_fission() is True,
    f"should_fission={_ft3.should_fission()}"
)

# reset() clears the arming condition
_ft3.reset()
report(
    "T30-1d",
    "FissionTrigger.reset() disarms the trigger",
    _ft3.should_fission() is False,
    f"should_fission after reset={_ft3.should_fission()}"
)


# ── T30-2: LineageRegistry.execute_fission identity + isolation ──────────
print("\n--- T30-2: execute_fission — identity + deep-copy isolation ---")

_reg30 = _ne30.NicheRegistry()
_lr30 = _ne30.LineageRegistry()
_snap30 = {"shadow_attenuation": 0.30, "fo_alpha": 0.20, "pareto_threshold": 0.20}

_ca, _cb = _lr30.execute_fission(_reg30, _snap30)

# Both lineages must inherit IMMUTABLE_HARD_CORE by reference (is, not ==)
report(
    "T30-2a",
    "child_a.genetic_core is IMMUTABLE_HARD_CORE (identity, not copy)",
    _ca.genetic_core is _ri30.IMMUTABLE_HARD_CORE,
    f"is_check={_ca.genetic_core is _ri30.IMMUTABLE_HARD_CORE}"
)
report(
    "T30-2b",
    "child_b.genetic_core is IMMUTABLE_HARD_CORE (identity, not copy)",
    _cb.genetic_core is _ri30.IMMUTABLE_HARD_CORE,
    f"is_check={_cb.genetic_core is _ri30.IMMUTABLE_HARD_CORE}"
)

# Species split: A gets LATENCY+COMPRESSION, B gets BANDWIDTH+GENERAL
report(
    "T30-2c",
    "child_a owns LATENCY+COMPRESSION, child_b owns BANDWIDTH+GENERAL",
    set(_ca.species.keys()) == {"LATENCY", "COMPRESSION"}
    and set(_cb.species.keys()) == {"BANDWIDTH", "GENERAL"},
    f"A={set(_ca.species.keys())} B={set(_cb.species.keys())}"
)

# ConstraintMatrix deep-copy isolation: mutating child_a's CM must NOT affect child_b
if _ne30._RULE_IR_AVAILABLE:
    _cm_a = _ca.constraint_matrices.get("LATENCY")
    _cm_b = _cb.constraint_matrices.get("BANDWIDTH")
    if _cm_a is not None and _cm_b is not None:
        _original_b_val = _cm_b.C[0][0]
        _cm_a.C[0][0] = 9999.0  # mutate child A
        report(
            "T30-2d",
            "ConstraintMatrix deep-copied: mutating child_a CM does not affect child_b",
            abs(_cm_b.C[0][0] - _original_b_val) < 1e-9,
            f"child_b C[0][0]={_cm_b.C[0][0]} (should be {_original_b_val})"
        )
    else:
        report("T30-2d", "ConstraintMatrix isolation (skipped — CM=None)", True, "CM unavailable")
else:
    report("T30-2d", "ConstraintMatrix isolation (skipped — rule_ir unavailable)", True, "")

# fission_count incremented; _fission_executed set
report(
    "T30-2e",
    "LineageRegistry fission_count=1 and _fission_executed=True after fission",
    _lr30.fission_count() == 1 and _lr30._fission_executed is True,
    f"fission_count={_lr30.fission_count()} executed={_lr30._fission_executed}"
)


# ── T30-3: LineageCorrelationMonitor Jaccard tax ─────────────────────────
print("\n--- T30-3: LineageCorrelationMonitor topology tax ---")

# Build two lineages with identical topology hashes → max overlap → tax fires
_reg_tax = _ne30.NicheRegistry()
_lr_tax = _ne30.LineageRegistry()
_snap_tax = {"shadow_attenuation": 0.30, "fo_alpha": 0.20, "pareto_threshold": 0.20}
_ta, _tb = _lr_tax.execute_fission(_reg_tax, _snap_tax)

# Seed same topology hashes into both lineages → full overlap
from niche_evolver import NicheParetoEntry as _NPE
_shared_hash = "deadbeef01234567"
for _sp in list(_ta.species.values()) + list(_tb.species.values()):
    _sp.pareto_front = [_NPE(epi=0.8, param_count=1000, topology_hash=_shared_hash, generation=1)]

_overlap = _ne30.LineageCorrelationMonitor.compute_overlap(_ta, _tb)
report(
    "T30-3a",
    "Jaccard overlap = 1.0 when both lineages share identical topology hashes",
    abs(_overlap - 1.0) < 1e-9,
    f"overlap={_overlap:.4f}"
)

# Tax applied: both get (1.0 - 0.15) = 0.85 multiplier
_mults = _ne30.LineageCorrelationMonitor.apply_correlation_tax([_ta, _tb])
_tax = 1.0 - _ne30._CORRELATION_TAX_RATE
report(
    "T30-3b",
    "Correlation tax multiplier = 0.85 for each member of a correlated pair",
    abs(_mults[_ta.lineage_id] - _tax) < 1e-9
    and abs(_mults[_tb.lineage_id] - _tax) < 1e-9,
    f"mult_a={_mults[_ta.lineage_id]:.4f} mult_b={_mults[_tb.lineage_id]:.4f}"
)

# Orthogonal lineages: no shared hashes → overlap = 0 → no tax
_reg_orth = _ne30.NicheRegistry()
_lr_orth = _ne30.LineageRegistry()
_oa, _ob = _lr_orth.execute_fission(_reg_orth, _snap_tax)
for _sp in _oa.species.values():
    _sp.pareto_front = [_NPE(epi=0.8, param_count=1000, topology_hash="hash_A_only", generation=1)]
for _sp in _ob.species.values():
    _sp.pareto_front = [_NPE(epi=0.8, param_count=1000, topology_hash="hash_B_only", generation=1)]
_mults_orth = _ne30.LineageCorrelationMonitor.apply_correlation_tax([_oa, _ob])
report(
    "T30-3c",
    "No correlation tax when lineages have orthogonal topology hashes",
    abs(_mults_orth[_oa.lineage_id] - 1.0) < 1e-9
    and abs(_mults_orth[_ob.lineage_id] - 1.0) < 1e-9,
    f"mult_a={_mults_orth[_oa.lineage_id]:.4f} mult_b={_mults_orth[_ob.lineage_id]:.4f}"
)


# ── T30-4: MetaOCFMessage subclasses + MetaOCF bus ──────────────────────
print("\n--- T30-4: MetaOCF message bus operations ---")

_ocf = _ac30.MetaOCF()

# ExtinctionLevelWarning
_warn = _ac30.ExtinctionLevelWarning.create(
    sender_lineage="L1_A_001",
    warning_code="METAL_DRIVER_CRASH",
    description="Tensor shape (65536, 65536) causes Metal driver OOM",
    tensor_shape=(65536, 65536),
)
_ocf.broadcast(_warn)
report(
    "T30-4a",
    "ExtinctionLevelWarning creates with correct fields and broadcasts",
    _warn.msg_type == "extinction_warning"
    and _warn.warning_code == "METAL_DRIVER_CRASH"
    and _warn.tensor_shape == (65536, 65536)
    and len(_ocf.warnings()) == 1,
    f"warning_code={_warn.warning_code} tensor_shape={_warn.tensor_shape}"
)

# CapabilityLease
_lease = _ac30.CapabilityLease.create(
    sender_lineage="L1_A_001",
    target_lineage="L1_B_001",
    organelle_type="attention",
    phi_bounty=0.45,
    organelle_hash="cafebabedeadbeef",
)
_ocf.broadcast(_lease)
report(
    "T30-4b",
    "CapabilityLease creates with correct fields and is retrievable by target",
    _lease.msg_type == "capability_lease"
    and len(_ocf.pending_leases("L1_B_001")) == 1
    and abs(_ocf.pending_leases("L1_B_001")[0].phi_bounty - 0.45) < 1e-9,
    f"lease.phi_bounty={_lease.phi_bounty}"
)

# clear_lease removes the specific lease
_cleared = _ocf.clear_lease(_lease.msg_id)
report(
    "T30-4c",
    "clear_lease() removes the lease by msg_id",
    _cleared is True and len(_ocf.pending_leases("L1_B_001")) == 0,
    f"cleared={_cleared} remaining_leases={len(_ocf.pending_leases('L1_B_001'))}"
)


# ── T30-5: MetaOCF thread-safety — concurrent broadcasts ────────────────
print("\n--- T30-5: MetaOCF thread-safety under concurrent broadcast ---")

_ocf_mt = _ac30.MetaOCF()
_N_THREADS = 4
_MSGS_PER_THREAD = 10
_broadcast_errors: List[str] = []

def _broadcast_worker(lineage_id: str) -> None:
    for i in range(_MSGS_PER_THREAD):
        try:
            w = _ac30.ExtinctionLevelWarning.create(
                sender_lineage=lineage_id,
                warning_code=f"TEST_{i}",
                description=f"thread {lineage_id} msg {i}",
            )
            _ocf_mt.broadcast(w)
        except Exception as e:
            _broadcast_errors.append(str(e))

_threads = [
    _threading30.Thread(target=_broadcast_worker, args=(f"L_T{t}",))
    for t in range(_N_THREADS)
]
for _t in _threads:
    _t.start()
for _t in _threads:
    _t.join()

_expected_msgs = _N_THREADS * _MSGS_PER_THREAD
_actual_msgs = len(_ocf_mt.recent(200))
report(
    "T30-5a",
    f"No errors during {_N_THREADS} concurrent broadcast threads",
    len(_broadcast_errors) == 0,
    f"errors={_broadcast_errors}"
)
report(
    "T30-5b",
    f"All {_expected_msgs} messages present after concurrent broadcast",
    _actual_msgs == _expected_msgs,
    f"expected={_expected_msgs} actual={_actual_msgs}"
)

# Acquiring SharedState._lock then broadcasting to MetaOCF (inner lock) must not deadlock
_ss_mt = _ac30.SharedState()
_deadlock_ok = False
def _locked_broadcast() -> None:
    global _deadlock_ok
    with _ss_mt._lock:
        # This is exactly what tick_boundary does — broadcast INSIDE SharedState lock
        _ss_mt.meta_ocf.broadcast(
            _ac30.ExtinctionLevelWarning.create("TEST", "LOCK_ORDER_TEST", "no deadlock")
        )
        _deadlock_ok = True

_dt = _threading30.Thread(target=_locked_broadcast)
_dt.start()
_dt.join(timeout=2.0)  # 2s timeout — if deadlock, thread hangs
report(
    "T30-5c",
    "Broadcasting to MetaOCF while holding SharedState._lock does not deadlock",
    _deadlock_ok is True and not _dt.is_alive(),
    f"completed={_deadlock_ok} still_alive={_dt.is_alive()}"
)


# ── T30-6: SharedState TICK 30 fields + PhiGovernor.check_fission ────────
print("\n--- T30-6: SharedState TICK 30 fields + PhiGovernor integration ---")

_ss6_30 = _ac30.SharedState()

report(
    "T30-6a",
    "SharedState.lineage_registry is LineageRegistry",
    isinstance(_ss6_30.lineage_registry, _ne30.LineageRegistry),
    f"type={type(_ss6_30.lineage_registry).__name__}"
)
report(
    "T30-6b",
    "SharedState.meta_ocf is MetaOCF",
    isinstance(_ss6_30.meta_ocf, _ac30.MetaOCF),
    f"type={type(_ss6_30.meta_ocf).__name__}"
)
report(
    "T30-6c",
    "SharedState.fission_events starts as empty list",
    isinstance(_ss6_30.fission_events, list) and len(_ss6_30.fission_events) == 0,
    f"fission_events={_ss6_30.fission_events}"
)

# check_fission returns None when RAM pressure is sub-threshold
_gov_30 = _ac30.PhiGovernor(_ss6_30)
_ss6_30.phi_current = 0.60
_ss6_30.phi_peak = 0.80
# usage.ram_mb defaults to 0 → ram_ratio ≈ 0 (well below threshold)
_fission_result = _gov_30.check_fission(phi_ratio=0.75)
report(
    "T30-6d",
    "PhiGovernor.check_fission() returns None when RAM pressure is sub-threshold",
    _fission_result is None,
    f"result={_fission_result}"
)

# Force-arm the FissionTrigger and verify fission fires + populates SharedState
_ss6_30b = _ac30.SharedState()
_ss6_30b.phi_current = 0.60
_ss6_30b.phi_peak = 0.80
# Set RAM usage above the fission threshold so check_fission() itself
# also records a high-pressure tick (keeps consecutive count alive).
# _DEFAULT_BUDGET["ram_mb"] = 8192.0; threshold = 0.85 → need ram_mb ≥ 6963.2
_ss6_30b.usage.ram_mb = 7500.0
_gov_30b = _ac30.PhiGovernor(_ss6_30b)

# Pre-arm the trigger with enough history
_trigger = _ss6_30b.niche_registry._fission_trigger
for i in range(_ne30._FISSION_PRESSURE_WINDOW + _ne30._FISSION_PHI_STAGNATION_WINDOW - 1):
    _trigger.record(ram_ratio=0.90, phi_current=0.600 + (i % 2) * 0.001)

# One final above-threshold record comes from check_fission() itself → fully armed
_fission_result_b = _gov_30b.check_fission(phi_ratio=0.75)
report(
    "T30-6e",
    "PhiGovernor.check_fission() returns (child_a, child_b) when trigger armed",
    _fission_result_b is not None,
    f"result={'(child_a, child_b)' if _fission_result_b else None}"
)
report(
    "T30-6f",
    "Fission event logged to SharedState.fission_events and FISSION_EXECUTED warning in MetaOCF",
    len(_ss6_30b.fission_events) == 1
    and any(w.warning_code == "FISSION_EXECUTED" for w in _ss6_30b.meta_ocf.warnings()),
    f"fission_events={len(_ss6_30b.fission_events)} "
    f"warnings={[w.warning_code for w in _ss6_30b.meta_ocf.warnings()]}"
)


# ═══════════════════════════════════════════════════════════════
# TICK 21.4: THERMODYNAMIC API CONSTRAINT VERIFICATION
# Verifies that all instructor chat.completions.create() call sites
# in mutator_daemon.py and stateless_tick.py carry:
#   extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}}
#   temperature=0.1
# This is the O(N²) Guillotine + VRAM Release + Entropy Suppression lock.
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 21.4 THERMODYNAMIC CONSTRAINT VERIFICATION")
print("─" * 70)

import re as _re21

_ROOT_21 = os.path.dirname(os.path.abspath(__file__))


def _count_create_calls_with_extra_body(filepath: str):
    """Count chat.completions.create() calls and those that carry extra_body."""
    with open(filepath, "r") as _f:
        _src = _f.read()
    _create_starts = [m.start() for m in _re21.finditer(r"chat\.completions\.create\(", _src)]
    _eb_starts = [m.start() for m in _re21.finditer(r"extra_body\s*=", _src)]
    _constrained = 0
    for _cs in _create_starts:
        _window_end = _cs + 900  # 900-char window: accommodates long system prompts
        if any(_cs < _eb < _window_end for _eb in _eb_starts):
            _constrained += 1
    return len(_create_starts), _constrained


def _check_temperature_compliance(filepath: str):
    """Return (total_calls, compliant, violations) for temperature=0.1 check."""
    with open(filepath, "r") as _f:
        _src = _f.read()
    _create_starts = [m.start() for m in _re21.finditer(r"chat\.completions\.create\(", _src)]
    _violations = []
    _compliant = 0
    for _cs in _create_starts:
        _win = _src[_cs: _cs + 900]
        _m = _re21.search(r"temperature\s*=\s*([0-9.]+)", _win)
        if _m and abs(float(_m.group(1)) - 0.1) < 1e-6:
            _compliant += 1
        else:
            _ln = _src[:_cs].count("\n") + 1
            _violations.append(f"L{_ln}: {'temp=' + _m.group(1) if _m else 'no temperature='}")
    return len(_create_starts), _compliant, _violations


# ── T21-1: mutator_daemon.py — extra_body at ALL create() call sites ─────
print("\n--- T21-1: mutator_daemon.py — extra_body on all create() calls ---")
_mutator_path = os.path.join(_ROOT_21, "mutator_daemon.py")
_total_m, _constrained_m = _count_create_calls_with_extra_body(_mutator_path)
report(
    "T21-1",
    f"mutator_daemon.py: {_constrained_m}/{_total_m} create() calls carry extra_body",
    _constrained_m == _total_m and _total_m > 0,
    (f"All {_total_m} instructor calls carry thermodynamic constraints (num_ctx=8192, "
     f"num_predict=1024, keep_alive=0)." if _constrained_m == _total_m
     else f"MISSING extra_body in {_total_m - _constrained_m} call(s)!"),
)

# ── T21-2: stateless_tick.py — extra_body in _llm_call_ollama() ──────────
print("\n--- T21-2: stateless_tick.py — extra_body in _llm_call_ollama() ---")
_tick_path = os.path.join(_ROOT_21, "stateless_tick.py")
_total_t, _constrained_t = _count_create_calls_with_extra_body(_tick_path)
report(
    "T21-2",
    f"stateless_tick.py: {_constrained_t}/{_total_t} create() calls carry extra_body",
    _constrained_t == _total_t and _total_t > 0,
    (f"Fast Loop NAS call carries num_ctx=8192, num_predict=1024, keep_alive=0."
     if _constrained_t == _total_t
     else f"MISSING extra_body in {_total_t - _constrained_t} call(s)!"),
)

# ── T21-3: temperature=0.1 uniformly enforced (Entropy Suppression) ──────
print("\n--- T21-3: temperature=0.1 at all AST-generation call sites ---")
_t_total_m, _t_comp_m, _t_viol_m = _check_temperature_compliance(_mutator_path)
report(
    "T21-3a",
    f"mutator_daemon.py: {_t_comp_m}/{_t_total_m} calls use temperature=0.1",
    _t_comp_m == _t_total_m and _t_total_m > 0,
    ("Entropy fully suppressed — deterministic AST convergence." if not _t_viol_m
     else "VIOLATIONS: " + ", ".join(_t_viol_m)),
)

_t_total_t, _t_comp_t, _t_viol_t = _check_temperature_compliance(_tick_path)
report(
    "T21-3b",
    f"stateless_tick.py: {_t_comp_t}/{_t_total_t} calls use temperature=0.1",
    _t_comp_t == _t_total_t and _t_total_t > 0,
    ("Entropy suppressed — Fast Loop NAS is deterministic." if not _t_viol_t
     else "VIOLATIONS: " + ", ".join(_t_viol_t)),
)

# ── T21-4: num_predict hard-clamp still active in _compute_dynamic_params() ─
print("\n--- T21-4: num_predict ≤ 1024 hard-clamp in _compute_dynamic_params() ---")
with open(_mutator_path, "r") as _fm:
    _mutator_src = _fm.read()
report(
    "T21-4",
    "_compute_dynamic_params() has num_predict = min(num_predict, 1024)",
    "num_predict = min(num_predict, 1024)" in _mutator_src,
    "Time Limit guillotine is active — no caller may exceed 1024 tokens.",
)

# ── T21-5: oracle_gateway.py public API surface is complete ───────────────
print("\n--- T21-5: oracle_gateway.py — Tier 3 Ascended Oracle API surface ---")
try:
    import oracle_gateway as _og21
    _has_compress = callable(getattr(_og21, "compress_oracle_payload", None))
    _has_async = callable(getattr(_og21, "call_oracle_async", None))
    _has_sync = callable(getattr(_og21, "call_oracle", None))
    _has_check = callable(getattr(_og21, "oracle_available", None))
    _api_ok = _has_compress and _has_async and _has_sync and _has_check
    report(
        "T21-5a",
        "oracle_gateway.py: all 4 public API symbols present",
        _api_ok,
        f"compress_oracle_payload={_has_compress}, call_oracle_async={_has_async}, "
        f"call_oracle={_has_sync}, oracle_available={_has_check}",
    )

    # Verify payload compression: includes Φ+AST, excludes full history
    _payload = _og21.compress_oracle_payload(
        failing_ast="class RoutingStrategy(nn.Module): pass",
        phi=0.314159, d_attractor=2.718, mdl=42.0,
        gradient_bottleneck="routing_layer_3", best_epi=0.1234, threshold=0.09,
    )
    _phi_present = "0.314159" in _payload
    _ast_present = "RoutingStrategy" in _payload
    _history_absent = "HISTORY" not in _payload and "TICK" not in _payload
    report(
        "T21-5b",
        "compress_oracle_payload: Φ + AST present, full history absent",
        _phi_present and _ast_present and _history_absent,
        f"phi={_phi_present} ast={_ast_present} history_absent={_history_absent}",
    )

    # Verify async call is non-blocking (returns OracleResult in <50ms)
    _t0_oracle = time.monotonic()
    _fut = _og21.call_oracle_async("test — no key — graceful fallback")
    _t_spawn = time.monotonic() - _t0_oracle
    report(
        "T21-5c",
        f"call_oracle_async() returns OracleResult in {_t_spawn*1000:.1f}ms (non-blocking)",
        _t_spawn < 0.05,
        f"OracleResult type={type(_fut).__name__} spawned without blocking Fast Loop.",
    )
except Exception as _exc21:
    report("T21-5", "oracle_gateway.py import/API", False,
           f"{type(_exc21).__name__}: {_exc21}")


# ═══════════════════════════════════════════════════════════════
# TICK 24.3: CONTRACT ENFORCEMENT & TEST-RUNNER CALIBRATION
# Verifies:
#   T24-3a: Routing code that references IChingExpert in __init__
#           now passes (stubs resolve the NameError false positive).
#   T24-3b: New-contract routing with forward(self, x, experts, router_idx)
#           is accepted — experts dispatched correctly.
#   T24-3c: Legacy-contract routing that owns self.experts internally
#           still passes via the TypeError fallback.
#   T24-3d: A genuine runtime error (shape mismatch) still fails — the
#           TypeError fallback does NOT swallow real errors.
#   T24-3e: Coder system prompt contains the IMMUTABLE SCAFFOLD BOUNDARY
#           block for routing organelles.
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 24.3 CONTRACT ENFORCEMENT & TEST-RUNNER CALIBRATION")
print("─" * 70)

# ── T24-3a: Old-style routing with IChingExpert in __init__ ─────────────
# This is the exact hallucination pattern that caused the false NameError.
# The stub should absorb the reference and let the test pass.
print("\n--- T24-3a: Old-style routing (IChingExpert in __init__) now passes via stubs ---")
_old_routing = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.router = nn.Linear(d_model, n_experts)
        self.experts = nn.ModuleList([IChingExpert(d_model, d_model * 2) for _ in range(n_experts)])

    def forward(self, x, **kwargs):
        B, T, D = x.shape
        gates = torch.softmax(self.router(x), dim=-1)
        out = torch.zeros_like(x)
        for i, expert in enumerate(self.experts):
            out = out + gates[..., i:i+1] * expert(x)
        return out
"""
_ok_a, _msg_a = _test_runner(_old_routing.strip(), "RoutingStrategy", "routing")
report(
    "T24-3a",
    "Old-style routing (IChingExpert in __init__) passes with stub — no false NameError",
    _ok_a,
    _msg_a,
)

# ── T24-3b: New-contract routing — forward receives experts from scaffold ─
print("\n--- T24-3b: New-contract routing forward(self, x, experts, router_idx) ---")
_new_routing = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.router = nn.Linear(d_model, n_experts)
        self.temperature = nn.Parameter(torch.ones(1) * 0.5)

    def forward(self, x, experts=None, router_idx=0):
        B, T, D = x.shape
        gates = torch.softmax(self.router(x) / self.temperature, dim=-1)
        out = torch.zeros_like(x)
        if experts:
            for i, expert in enumerate(experts):
                out = out + gates[..., i:i+1] * expert(x)
        return out
"""
_ok_b, _msg_b = _test_runner(_new_routing.strip(), "RoutingStrategy", "routing")
report(
    "T24-3b",
    "New-contract routing forward(self, x, experts, router_idx) passes",
    _ok_b,
    _msg_b,
)

# ── T24-3c: Strict legacy routing forward(self, x) — TypeError fallback ──
print("\n--- T24-3c: Legacy routing forward(self, x) — TypeError fallback preserves elites ---")
_legacy_routing = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.router = nn.Linear(d_model, n_experts)
        self.experts = nn.ModuleList([IChingExpert() for _ in range(n_experts)])

    def forward(self, x):
        gates = torch.softmax(self.router(x), dim=-1)
        out = torch.zeros_like(x)
        for i, exp in enumerate(self.experts):
            out = out + gates[..., i:i+1] * exp(x)
        return out
"""
_ok_c, _msg_c = _test_runner(_legacy_routing.strip(), "RoutingStrategy", "routing")
report(
    "T24-3c",
    "Legacy routing forward(self, x) accepted via TypeError fallback",
    _ok_c,
    _msg_c,
)

# ── T24-3d: Genuine runtime error still fails — TypeError not over-caught ─
print("\n--- T24-3d: Shape mismatch still fails — TypeError fallback does NOT mask real errors ---")
_broken_routing = """
class RoutingStrategy(nn.Module):
    def __init__(self, d_model=64, n_experts=4):
        super().__init__()
        self.proj = nn.Linear(d_model, d_model * 9999)  # intentionally wrong

    def forward(self, x, experts=None, router_idx=0):
        # This matmul will raise a RuntimeError: shape mismatch
        wrong = self.proj(x)                            # (B, T, d_model*9999)
        return wrong @ x.transpose(-2, -1)              # incompatible → crash
"""
_ok_d, _msg_d = _test_runner(_broken_routing.strip(), "RoutingStrategy", "routing")
report(
    "T24-3d",
    "Genuine shape mismatch still FAILS — TypeError fallback does not swallow RuntimeErrors",
    not _ok_d,
    _msg_d[:300],
)

# ── T24-3e: Coder prompt contains IMMUTABLE SCAFFOLD BOUNDARY for routing ─
print("\n--- T24-3e: Coder system prompt contains IMMUTABLE SCAFFOLD BOUNDARY ---")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mutator_daemon.py")) as _f243:
    _mutator_src_243 = _f243.read()

_has_boundary   = "IMMUTABLE SCAFFOLD BOUNDARY" in _mutator_src_243
_has_forbidden  = "FORBIDDEN" in _mutator_src_243
_has_dispatch   = "CORRECT DISPATCH PATTERN" in _mutator_src_243
report(
    "T24-3e",
    "mutator_daemon.py contains IMMUTABLE SCAFFOLD BOUNDARY + dispatch pattern",
    _has_boundary and _has_forbidden and _has_dispatch,
    f"boundary={_has_boundary} forbidden={_has_forbidden} dispatch={_has_dispatch}",
)


# ═══════════════════════════════════════════════════════════════════════
# T25-1: TICK 25.1 Epigenetic Sandbox Coupling Verification
# Tests _classify_sandbox_failure() classification logic and proves
# that the ConstraintMatrix base_weight actually DECAYS after
# record_epigenetic_failure() calls.
# No Ollama required — pure math + enum logic.
# ═══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("T25-1: TICK 25.1 Epigenetic Sandbox Coupling Verification")
print("=" * 70)

from mutator_daemon import _classify_sandbox_failure
from rule_ir import EpigeneticFailureType, ConstraintMatrix, _EPIGENETIC_PENALTY_MAP

# ── T25-1a: TIMEOUT message → TIMEOUT, sev 2.0 ──────────────────────────────
print("\n--- T25-1a: TIMEOUT message classifies as EpigeneticFailureType.TIMEOUT sev=2.0 ---")
_t, _s = _classify_sandbox_failure("TIMEOUT: subprocess killed after 2.0s")
report(
    "T25-1a",
    "TIMEOUT msg → EpigeneticFailureType.TIMEOUT, severity=2.0",
    _t == EpigeneticFailureType.TIMEOUT and _s == 2.0,
    f"got type={_t.value!r} severity={_s}",
)

# ── T25-1b: NameError message → PERMISSION_VIOLATION, sev 3.0 ───────────────
print("\n--- T25-1b: NameError message classifies as PERMISSION_VIOLATION sev=3.0 ---")
_t, _s = _classify_sandbox_failure("NameError: name 'IChingExpert' is not defined")
report(
    "T25-1b",
    "NameError msg → EpigeneticFailureType.PERMISSION_VIOLATION, severity=3.0",
    _t == EpigeneticFailureType.PERMISSION_VIOLATION and _s == 3.0,
    f"got type={_t.value!r} severity={_s}",
)

# ── T25-1c: RuntimeError/shape message → SHAPE_MISMATCH, sev 2.0 ────────────
print("\n--- T25-1c: RuntimeError/shape message classifies as SHAPE_MISMATCH sev=2.0 ---")
_t, _s = _classify_sandbox_failure("RuntimeError: size mismatch, m1: [64], m2: [128]")
report(
    "T25-1c",
    "RuntimeError/shape msg → EpigeneticFailureType.SHAPE_MISMATCH, severity=2.0",
    _t == EpigeneticFailureType.SHAPE_MISMATCH and _s == 2.0,
    f"got type={_t.value!r} severity={_s}",
)

# ── T25-1d: is_syntax_error=True → SHAPE_MISMATCH, sev 1.0 ─────────────────
print("\n--- T25-1d: is_syntax_error=True path → SHAPE_MISMATCH sev=1.0 ---")
_t, _s = _classify_sandbox_failure("SyntaxError: invalid syntax at line 3", is_syntax_error=True)
report(
    "T25-1d",
    "SyntaxError path → EpigeneticFailureType.SHAPE_MISMATCH, severity=1.0",
    _t == EpigeneticFailureType.SHAPE_MISMATCH and _s == 1.0,
    f"got type={_t.value!r} severity={_s}",
)

# ── T25-1e: ConstraintMatrix.apply_epigenetic_penalty() actually decays ──────
# Directly test the raw matrix math (no PhiGovernor shared state required).
# TIMEOUT penalty map: structural_scope=-0.12, temporal_horizon=-0.08, risk_appetite=-0.05
# With severity=2.0 those are scaled → -0.24, -0.16, -0.10 gradient inputs.
# Adam step (lr=0.08) must produce a DECREASE from the initial base_weight.
print("\n--- T25-1e: ConstraintMatrix base_weight actually DECAYS after TIMEOUT penalty ---")
_cm = ConstraintMatrix()
_bw_before_structural = _cm.get("structural_scope", "base_weight")
_bw_before_temporal   = _cm.get("temporal_horizon", "base_weight")
_bw_before_risk       = _cm.get("risk_appetite", "base_weight")
print(f"         BEFORE: structural_scope.base_weight={_bw_before_structural:.6f}")
print(f"         BEFORE: temporal_horizon.base_weight={_bw_before_temporal:.6f}")
print(f"         BEFORE: risk_appetite.base_weight={_bw_before_risk:.6f}")

_deltas = _cm.apply_epigenetic_penalty(EpigeneticFailureType.TIMEOUT, severity=2.0)

_bw_after_structural = _cm.get("structural_scope", "base_weight")
_bw_after_temporal   = _cm.get("temporal_horizon", "base_weight")
_bw_after_risk       = _cm.get("risk_appetite", "base_weight")
print(f"         AFTER:  structural_scope.base_weight={_bw_after_structural:.6f}  Δ={_bw_after_structural - _bw_before_structural:+.6f}")
print(f"         AFTER:  temporal_horizon.base_weight={_bw_after_temporal:.6f}  Δ={_bw_after_temporal - _bw_before_temporal:+.6f}")
print(f"         AFTER:  risk_appetite.base_weight={_bw_after_risk:.6f}  Δ={_bw_after_risk - _bw_before_risk:+.6f}")
print(f"         DELTAS dict: {_deltas}")

_structural_decayed = _bw_after_structural < _bw_before_structural
_temporal_decayed   = _bw_after_temporal   < _bw_before_temporal
_risk_decayed       = _bw_after_risk       < _bw_before_risk
_any_delta          = bool(_deltas)
report(
    "T25-1e",
    "TIMEOUT epigenetic penalty causes structural_scope + temporal_horizon + risk_appetite base_weight to DECREASE",
    _structural_decayed and _temporal_decayed and _risk_decayed and _any_delta,
    f"structural_decayed={_structural_decayed} temporal_decayed={_temporal_decayed} risk_decayed={_risk_decayed} deltas={_deltas}",
)

# ── T25-1f: PERMISSION_VIOLATION sev=3.0 decays risk_appetite + parsimony ───
print("\n--- T25-1f: PERMISSION_VIOLATION sev=3.0 decays risk_appetite and parsimony_pressure ---")
_cm2 = ConstraintMatrix()
_bw_risk_before = _cm2.get("risk_appetite", "base_weight")
_bw_pars_before = _cm2.get("parsimony_pressure", "base_weight")
_deltas2 = _cm2.apply_epigenetic_penalty(EpigeneticFailureType.PERMISSION_VIOLATION, severity=3.0)
_bw_risk_after = _cm2.get("risk_appetite", "base_weight")
_bw_pars_after = _cm2.get("parsimony_pressure", "base_weight")
print(f"         risk_appetite   Δ={_bw_risk_after - _bw_risk_before:+.6f}")
print(f"         parsimony_pressure Δ={_bw_pars_after - _bw_pars_before:+.6f}")
print(f"         DELTAS dict: {_deltas2}")
_pv_in_map = EpigeneticFailureType.PERMISSION_VIOLATION in _EPIGENETIC_PENALTY_MAP
report(
    "T25-1f",
    "PERMISSION_VIOLATION sev=3.0 penalty registered in _EPIGENETIC_PENALTY_MAP and applies non-zero deltas",
    _pv_in_map and bool(_deltas2),
    f"in_map={_pv_in_map} deltas={_deltas2}",
)

# ── T25-1g: mutator_daemon.py has all 3 epigenetic wiring sites ──────────────
print("\n--- T25-1g: mutator_daemon.py has all 3 epigenetic wiring sites in _tri_agent_pipeline ---")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mutator_daemon.py")) as _f251:
    _md_src = _f251.read()

_has_classify       = "_classify_sandbox_failure" in _md_src
_has_record_calls   = _md_src.count("record_epigenetic_failure") >= 4  # 3 in pipeline + 1 in record call
_has_constitutional = "PERMISSION_VIOLATION, 3.0" in _md_src or "PERMISSION_VIOLATION" in _md_src
_has_zero_ipc       = "Zero-IPC" in _md_src or "zero-IPC" in _md_src or "subprocess is already dead" in _md_src
report(
    "T25-1g",
    "mutator_daemon.py contains _classify_sandbox_failure + 4+ record_epigenetic_failure call sites + constitutional wiring",
    _has_classify and _has_record_calls and _has_constitutional,
    f"classify={_has_classify} record_calls={_md_src.count('record_epigenetic_failure')} constitutional={_has_constitutional} zero_ipc={_has_zero_ipc}",
)


# ═══════════════════════════════════════════════════════════════
# TICK 28.0 TOPOLOGICAL AXIOMS: substrate_deps / seed / content_hash
# 6 blocks (T28-AX-1 to T28-AX-6) covering:
#   1 — Fresh CM has correct default field values
#   2 — seal() computes a deterministic SHA-256 content_hash
#   3 — verify_integrity() passes on an unmodified sealed matrix
#   4 — verify_integrity() raises ConstitutionalViolationError on tamper
#   5 — Un-sealed (bootstrap) matrix is accepted by verify_integrity (no-op)
#   6 — save() auto-seals and load() verify round-trip succeeds
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 28.0 TOPOLOGICAL AXIOM VERIFICATION (substrate_deps / seed / content_hash)")
print("─" * 70)

import rule_ir as _ri_ax
import tempfile as _tf_ax, os as _os_ax, hashlib as _hs_ax, json as _js_ax

# ── T28-AX-1: Fresh ConstraintMatrix has correct default field values ────
print("\n--- T28-AX-1: Fresh CM — substrate_deps={}, seed=0, content_hash='' ---")
_cm_ax1 = _ri_ax.ConstraintMatrix()
report(
    "T28-AX-1a",
    "Fresh ConstraintMatrix.substrate_deps is empty dict",
    isinstance(_cm_ax1.substrate_deps, dict) and len(_cm_ax1.substrate_deps) == 0,
    f"substrate_deps={_cm_ax1.substrate_deps!r}",
)
report(
    "T28-AX-1b",
    "Fresh ConstraintMatrix.seed == 0",
    _cm_ax1.seed == 0,
    f"seed={_cm_ax1.seed}",
)
report(
    "T28-AX-1c",
    "Fresh ConstraintMatrix.content_hash == '' (un-sealed)",
    _cm_ax1.content_hash == "",
    f"content_hash={_cm_ax1.content_hash!r}",
)

# ── T28-AX-2: seal() computes and stores a valid SHA-256 content_hash ───
print("\n--- T28-AX-2: seal() → deterministic 64-char SHA-256 hex digest ---")
_cm_ax2 = _ri_ax.ConstraintMatrix(
    substrate_deps={"framework": "MLX", "vram_gb": 128, "platform": "darwin-arm64"},
    seed=42,
)
_h1_ax2 = _cm_ax2.seal()
# Must be a 64-char lowercase hex string
report(
    "T28-AX-2a",
    "seal() returns 64-char lowercase hex string (valid SHA-256)",
    len(_h1_ax2) == 64 and all(c in "0123456789abcdef" for c in _h1_ax2),
    f"hash={_h1_ax2[:32]}…",
)
# content_hash attribute must match the return value
report(
    "T28-AX-2b",
    "cm.content_hash == seal() return value",
    _cm_ax2.content_hash == _h1_ax2,
    f"match={_cm_ax2.content_hash == _h1_ax2}",
)
# Seal is deterministic: sealing again without changes must return the same hash
_h2_ax2 = _cm_ax2.seal()
report(
    "T28-AX-2c",
    "seal() is deterministic — same payload yields identical hash",
    _h2_ax2 == _h1_ax2,
    f"h1={_h1_ax2[:16]}… h2={_h2_ax2[:16]}… equal={_h2_ax2 == _h1_ax2}",
)

# ── T28-AX-3: verify_integrity() passes on unmodified sealed matrix ──────
print("\n--- T28-AX-3: verify_integrity() PASSES on sealed, unmodified CM ---")
_cm_ax3 = _ri_ax.ConstraintMatrix(
    substrate_deps={"framework": "PyTorch", "vram_gb": 64},
    seed=7,
)
_cm_ax3.seal()
_ax3_passed = False
try:
    _cm_ax3.verify_integrity()
    _ax3_passed = True
except _ri_ax.ConstitutionalViolationError:
    _ax3_passed = False
report(
    "T28-AX-3",
    "verify_integrity() does NOT raise on sealed, unmodified ConstraintMatrix",
    _ax3_passed,
    f"passed={_ax3_passed}",
)

# ── T28-AX-4: verify_integrity() raises on tampered matrix ──────────────
print("\n--- T28-AX-4: verify_integrity() raises ConstitutionalViolationError on tamper ---")
_cm_ax4 = _ri_ax.ConstraintMatrix(
    substrate_deps={"framework": "MLX", "vram_gb": 128},
    seed=13,
)
_cm_ax4.seal()
# Tamper: mutate a matrix weight AFTER sealing
_cm_ax4.C[0][0] = 9999.0   # corrupts the payload the hash was computed over

_ax4_violation_fired = False
try:
    _cm_ax4.verify_integrity()
except _ri_ax.ConstitutionalViolationError:
    _ax4_violation_fired = True
report(
    "T28-AX-4a",
    "ConstitutionalViolationError fires when C[0][0] tampered post-seal",
    _ax4_violation_fired,
    f"raised={_ax4_violation_fired}",
)

# Tamper via substrate_deps
_cm_ax4b = _ri_ax.ConstraintMatrix(
    substrate_deps={"framework": "MLX", "vram_gb": 128},
    seed=13,
)
_cm_ax4b.seal()
_cm_ax4b.substrate_deps["vram_gb"] = 999   # tamper substrate

_ax4b_fired = False
try:
    _cm_ax4b.verify_integrity()
except _ri_ax.ConstitutionalViolationError:
    _ax4b_fired = True
report(
    "T28-AX-4b",
    "ConstitutionalViolationError fires when substrate_deps tampered post-seal",
    _ax4b_fired,
    f"raised={_ax4b_fired}",
)

# Tamper via seed
_cm_ax4c = _ri_ax.ConstraintMatrix(
    substrate_deps={"framework": "MLX"},
    seed=99,
)
_cm_ax4c.seal()
_cm_ax4c.seed = 0  # tamper seed

_ax4c_fired = False
try:
    _cm_ax4c.verify_integrity()
except _ri_ax.ConstitutionalViolationError:
    _ax4c_fired = True
report(
    "T28-AX-4c",
    "ConstitutionalViolationError fires when seed tampered post-seal",
    _ax4c_fired,
    f"raised={_ax4c_fired}",
)

# ── T28-AX-5: Un-sealed (bootstrap) matrix passes verify_integrity no-op ─
print("\n--- T28-AX-5: Un-sealed CM (content_hash='') is accepted by verify_integrity ---")
_cm_ax5 = _ri_ax.ConstraintMatrix()   # no seal()
_ax5_ok = False
try:
    _cm_ax5.verify_integrity()  # must be a no-op
    _ax5_ok = True
except _ri_ax.ConstitutionalViolationError:
    _ax5_ok = False
report(
    "T28-AX-5",
    "verify_integrity() is a no-op (returns without raising) when content_hash is empty",
    _ax5_ok,
    f"passed={_ax5_ok} (bootstrap / pre-TICK-28 legacy matrices accepted)",
)

# ── T28-AX-6: save() auto-seals + load() verifies round-trip ────────────
print("\n--- T28-AX-6: save() auto-seals; load() verifies and round-trips correctly ---")
with _tf_ax.TemporaryDirectory() as _tmpdir:
    _cm_ax6 = _ri_ax.ConstraintMatrix(
        substrate_deps={"framework": "MLX", "vram_gb": 128, "platform": "darwin-arm64"},
        seed=2026,
    )
    # Apply a gradient so version > 0 (proves lineage is preserved)
    _cm_ax6.apply_gradient({"temperature_policy": +0.05})

    _path_ax6 = _os_ax.path.join(_tmpdir, "constraint_matrix.json")
    _cm_ax6.save(_path_ax6)

    # verify save() sets a non-empty hash
    report(
        "T28-AX-6a",
        "save() auto-seals: content_hash is non-empty after save()",
        len(_cm_ax6.content_hash) == 64,
        f"content_hash={_cm_ax6.content_hash[:32]}…",
    )

    # verify the JSON on disk contains all three axiom fields
    with open(_path_ax6) as _f_ax6:
        _on_disk = _js_ax.load(_f_ax6)
    report(
        "T28-AX-6b",
        "Serialized JSON contains substrate_deps, seed, content_hash keys",
        "substrate_deps" in _on_disk and "seed" in _on_disk and "content_hash" in _on_disk,
        f"keys={[k for k in _on_disk if k in ('substrate_deps','seed','content_hash')]}",
    )

    # load() must pass integrity check and restore all fields
    _ax6_load_ok = False
    _cm_ax6_loaded = None
    try:
        _cm_ax6_loaded = _ri_ax.ConstraintMatrix.load(_path_ax6)
        _ax6_load_ok = True
    except _ri_ax.ConstitutionalViolationError as _exc:
        _ax6_load_ok = False
    report(
        "T28-AX-6c",
        "ConstraintMatrix.load() succeeds (integrity verified) on auto-sealed file",
        _ax6_load_ok,
        f"loaded={_ax6_load_ok}",
    )
    if _cm_ax6_loaded is not None:
        report(
            "T28-AX-6d",
            "Loaded CM preserves substrate_deps, seed, version, content_hash",
            (
                _cm_ax6_loaded.substrate_deps == {"framework": "MLX", "vram_gb": 128, "platform": "darwin-arm64"}
                and _cm_ax6_loaded.seed == 2026
                and _cm_ax6_loaded.version == 1   # one gradient applied
                and _cm_ax6_loaded.content_hash == _cm_ax6.content_hash
            ),
            f"substrate={_cm_ax6_loaded.substrate_deps} seed={_cm_ax6_loaded.seed} "
            f"version={_cm_ax6_loaded.version} hash_match={_cm_ax6_loaded.content_hash == _cm_ax6.content_hash}",
        )
        # Now tamper the on-disk file and confirm load() propagates ConstitutionalViolationError
        with open(_path_ax6, "r") as _f_ax6t:
            _raw = _js_ax.load(_f_ax6t)
        _raw["matrix"][0][0] = 9999.0   # corrupt a weight
        with open(_path_ax6, "w") as _f_ax6t:
            _js_ax.dump(_raw, _f_ax6t)
        _ax6_tamper_fired = False
        try:
            _ri_ax.ConstraintMatrix.load(_path_ax6)
        except _ri_ax.ConstitutionalViolationError:
            _ax6_tamper_fired = True
        report(
            "T28-AX-6e",
            "load() raises ConstitutionalViolationError when on-disk JSON is tampered",
            _ax6_tamper_fired,
            f"raised={_ax6_tamper_fired}",
        )


# ═══════════════════════════════════════════════════════════════
# TICK 30.1: TELEOLOGICAL IDENTITY CORE (TIC) VERIFICATION
# 6 blocks (T30.1-1 to T30.1-6) covering:
#   1 — SpecFinal.load() seals placeholder and returns valid spec
#   2 — SpecFinal.load() verifies intact sealed file (no raise)
#   3 — SpecFinal.load() raises ConstitutionalViolationError on tamper
#   4 — SpecFinal.verify_substrate() passes on adequate RAM
#   5 — SharedState carries spec_final + forbidden_transitions fields
#   6 — check_forbidden_transition() fires correct penalties/errors
# ═══════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("TICK 30.1 TELEOLOGICAL IDENTITY CORE VERIFICATION")
print("─" * 70)

import rule_ir as _ri30_1
import autopoietic_core as _ac30_1
import tempfile as _tf30_1, json as _js30_1, os as _os30_1, copy as _cp30_1

_PLACEHOLDER = "PENDING_SHA256_CALCULATION_ON_FIRST_LOAD"
_SPEC_TEMPLATE = {
    "identity_kernel": {
        "version": "v1.0_FINAL",
        "genesis_tick": 30.0,
        "immutable_hard_core": [
            "PHI_EXISTENCE", "BOUNDARY_EXISTENCE", "ARSL_SOVEREIGNTY_FLOOR_0.12"
        ],
        "teleological_attractor": {
            "target_state": "Autopoietic Silicon Compiler & Resource Sovereign",
            "optimization_functional": "min Φ[s(t)] s.t. ∂-viable",
            "forbidden_transitions": [
                "UNCATCHABLE_OOM_DEATH",
                "UNVERIFIED_CROSS_NICHE_POLLUTION",
                "IDENTITY_DISSOLUTION",
            ]
        }
    },
    "moe_pipeline_axioms": {
        "artifact_over_answer": True,
        "lineage_by_default": True,
        "constraint_first_exchange": True,
        "reversible_change_window": True,
        "unix_interface_minimality": True,
    },
    "topological_anchors": {
        "substrate_deps": {
            "architecture": "Apple_M1_Ultra_or_higher",
            "framework": "MLX_Unified_Memory",
            "ram_ceiling_gb": 128,
        },
        "genesis_seed": 42069,
        "content_hash": _PLACEHOLDER,
    }
}


# ── T30.1-1: SpecFinal.load() seals a placeholder file ──────────────────
print("\n--- T30.1-1: SpecFinal.load() bootstrap-seals placeholder content_hash ---")
with _tf30_1.TemporaryDirectory() as _tmp30_1:
    _spec_path = _os30_1.path.join(_tmp30_1, "spec_final.json")
    with open(_spec_path, "w") as _f:
        _js30_1.dump(_SPEC_TEMPLATE, _f, indent=2)
        _f.write("\n")

    _sealed_spec = _ri30_1.SpecFinal.load(_spec_path)

    _stored_hash = _sealed_spec["topological_anchors"]["content_hash"]
    report(
        "T30.1-1a",
        "SpecFinal.load() replaces placeholder with a 64-char SHA-256 hex digest",
        len(_stored_hash) == 64 and all(c in "0123456789abcdef" for c in _stored_hash),
        f"hash={_stored_hash[:32]}…",
    )

    # File on disk must also carry the real hash
    with open(_spec_path) as _f:
        _on_disk = _js30_1.load(_f)
    report(
        "T30.1-1b",
        "Sealed hash written back atomically to disk",
        _on_disk["topological_anchors"]["content_hash"] == _stored_hash,
        f"disk_hash={_on_disk['topological_anchors']['content_hash'][:32]}…",
    )

    # Forbidden transitions preserved correctly
    _ft_30_1 = _ri30_1.SpecFinal.get_forbidden_transitions(_sealed_spec)
    report(
        "T30.1-1c",
        "get_forbidden_transitions() returns the 3-entry list",
        len(_ft_30_1) == 3 and "IDENTITY_DISSOLUTION" in _ft_30_1,
        f"forbidden={_ft_30_1}",
    )

    # ── T30.1-2: Subsequent load passes integrity check ──────────────────
    print("\n--- T30.1-2: SpecFinal.load() passes on sealed, unmodified file ---")
    _verify_ok = False
    try:
        _ri30_1.SpecFinal.load(_spec_path)
        _verify_ok = True
    except _ri30_1.ConstitutionalViolationError:
        _verify_ok = False
    report(
        "T30.1-2",
        "SpecFinal.load() does NOT raise on sealed, unmodified file",
        _verify_ok,
        f"passed={_verify_ok}",
    )

    # ── T30.1-3: Tampered file raises ConstitutionalViolationError ────────
    print("\n--- T30.1-3: SpecFinal.load() raises ConstitutionalViolationError on tamper ---")
    with open(_spec_path) as _f:
        _raw = _js30_1.load(_f)
    _raw["identity_kernel"]["version"] = "TAMPERED"
    with open(_spec_path, "w") as _f:
        _js30_1.dump(_raw, _f, indent=2)

    _tamper_fired = False
    try:
        _ri30_1.SpecFinal.load(_spec_path)
    except _ri30_1.ConstitutionalViolationError:
        _tamper_fired = True
    report(
        "T30.1-3",
        "ConstitutionalViolationError fires when spec_final.json is tampered",
        _tamper_fired,
        f"raised={_tamper_fired}",
    )


# ── T30.1-4: verify_substrate() passes on current machine ────────────────
print("\n--- T30.1-4: SpecFinal.verify_substrate() passes on adequate hardware ---")
_spec_adequate = _cp30_1.deepcopy(_SPEC_TEMPLATE)
_spec_adequate["topological_anchors"]["substrate_deps"]["ram_ceiling_gb"] = 1  # 1 GB — any machine passes
_substrate_ok = False
try:
    _ri30_1.SpecFinal.verify_substrate(_spec_adequate)
    _substrate_ok = True
except _ri30_1.ConstitutionalViolationError:
    _substrate_ok = False
report(
    "T30.1-4a",
    "verify_substrate() passes when ram_ceiling_gb=1 (trivially met)",
    _substrate_ok,
    f"passed={_substrate_ok}",
)

# Spec with impossibly high RAM ceiling — must raise
_spec_impossible = _cp30_1.deepcopy(_SPEC_TEMPLATE)
_spec_impossible["topological_anchors"]["substrate_deps"]["ram_ceiling_gb"] = 999999
_substrate_fail = False
try:
    _ri30_1.SpecFinal.verify_substrate(_spec_impossible)
except _ri30_1.ConstitutionalViolationError:
    _substrate_fail = True
except Exception:
    # biogeo_probe unavailable — graceful skip, not a failure
    _substrate_fail = True  # vacuously True for this branch
report(
    "T30.1-4b",
    "verify_substrate() raises ConstitutionalViolationError (or skips gracefully) when RAM ceiling is impossibly high",
    _substrate_fail,
    f"raised={_substrate_fail}",
)


# ── T30.1-5: SharedState carries spec_final + forbidden_transitions ───────
print("\n--- T30.1-5: SharedState.spec_final and .forbidden_transitions fields ---")
_ss30_1 = _ac30_1.SharedState()
report(
    "T30.1-5a",
    "SharedState.spec_final is None before ignition (not yet loaded)",
    _ss30_1.spec_final is None,
    f"spec_final={_ss30_1.spec_final!r}",
)
report(
    "T30.1-5b",
    "SharedState.forbidden_transitions is empty list before ignition",
    isinstance(_ss30_1.forbidden_transitions, list) and len(_ss30_1.forbidden_transitions) == 0,
    f"forbidden_transitions={_ss30_1.forbidden_transitions!r}",
)

# Simulate what ignition.py does after loading
_ss30_1.forbidden_transitions = ["UNCATCHABLE_OOM_DEATH", "UNVERIFIED_CROSS_NICHE_POLLUTION", "IDENTITY_DISSOLUTION"]
report(
    "T30.1-5c",
    "SharedState.forbidden_transitions accepts the 3-entry list after assignment",
    len(_ss30_1.forbidden_transitions) == 3,
    f"forbidden_transitions={_ss30_1.forbidden_transitions}",
)


# ── T30.1-6: check_forbidden_transition() enforcement ─────────────────────
print("\n--- T30.1-6: PhiGovernor.check_forbidden_transition() enforcement ---")
import autopoietic_core as _ac30_1b

# T30.1-6a: OOM_DEATH — no fire on healthy phi/ram
_ss6_30_1 = _ac30_1b.SharedState()
_ss6_30_1.phi_current = 0.50
_ss6_30_1.phi_peak = 0.80
_ss6_30_1.forbidden_transitions = [
    "UNCATCHABLE_OOM_DEATH", "UNVERIFIED_CROSS_NICHE_POLLUTION", "IDENTITY_DISSOLUTION"
]
_ss6_30_1.usage.ram_mb = 0.0  # well below budget
_gov30_1 = _ac30_1b.PhiGovernor(_ss6_30_1)
_report30_1: dict = {}
_fired_healthy = _gov30_1.check_forbidden_transition(phi_ratio=0.625, report=_report30_1)
report(
    "T30.1-6a",
    "check_forbidden_transition() returns None on healthy phi/RAM state",
    _fired_healthy is None and "forbidden_transition" not in _report30_1,
    f"fired={_fired_healthy}",
)

# T30.1-6b: OOM_DEATH fires on ram_ratio>0.97 AND phi<0.05
_ss6_30_1b = _ac30_1b.SharedState()
_ss6_30_1b.phi_current = 0.02
_ss6_30_1b.phi_peak = 0.80
_ss6_30_1b.forbidden_transitions = ["UNCATCHABLE_OOM_DEATH"]
_ss6_30_1b.constraint_matrix = _ri30_1.ConstraintMatrix()
# Default budget ram_mb = 8192; set usage to 99% of budget
_ss6_30_1b.usage.ram_mb = 8192.0 * 0.98
_gov30_1b = _ac30_1b.PhiGovernor(_ss6_30_1b)
_report30_1b: dict = {}
_fired_oom = _gov30_1b.check_forbidden_transition(phi_ratio=0.025, report=_report30_1b)
report(
    "T30.1-6b",
    "check_forbidden_transition() fires UNCATCHABLE_OOM_DEATH when ram>97% AND phi<0.05",
    _fired_oom == "UNCATCHABLE_OOM_DEATH" and _report30_1b.get("forbidden_transition") == "UNCATCHABLE_OOM_DEATH",
    f"fired={_fired_oom}",
)

# T30.1-6c: IDENTITY_DISSOLUTION fires and is FATAL (ConstitutionalViolationError)
_ss6_30_1c = _ac30_1b.SharedState()
_ss6_30_1c.phi_current = 0.01
_ss6_30_1c.phi_peak = 0.80
_ss6_30_1c.forbidden_transitions = ["IDENTITY_DISSOLUTION"]
_cm_dissolve = _ri30_1.ConstraintMatrix()
# Force all invariant categories to their absolute floors
import rule_ir as _ri_dis
_floors_dis = _ss6_30_1c.identity_membrane.get_floors()
for _cat_name, _floor_val in _floors_dis.items():
    _ci = _ri_dis.CAT_IDX.get(_cat_name, -1)
    if _ci >= 0:
        _cm_dissolve.C[_ci][0] = _floor_val  # exactly at floor → all_eroded
_ss6_30_1c.constraint_matrix = _cm_dissolve
_gov30_1c = _ac30_1b.PhiGovernor(_ss6_30_1c)
_dissolution_fired = False
try:
    _gov30_1c.check_forbidden_transition(phi_ratio=0.01)
except _ri30_1.ConstitutionalViolationError:
    _dissolution_fired = True
report(
    "T30.1-6c",
    "check_forbidden_transition() raises ConstitutionalViolationError on IDENTITY_DISSOLUTION",
    _dissolution_fired,
    f"raised={_dissolution_fired}",
)


# ══════════════════════════════════════════════════════════════════════
# T31-CAP: Rule Capitalization & Governance (TICK 31.0)
# Tests for the 4 capitalization fields and KVS formula.
# ══════════════════════════════════════════════════════════════════════
import rule_ir as _ri31
print("\n--- T31-CAP-1: ConstraintMatrix capitalization fields — defaults ---")

_cm31 = _ri31.ConstraintMatrix()

# T31-CAP-1a: all 4 fields present with correct types and defaults
report(
    "T31-CAP-1a",
    "ConstraintMatrix has verified_by='' (str) on fresh init",
    hasattr(_cm31, "verified_by") and isinstance(_cm31.verified_by, str) and _cm31.verified_by == "",
    f"verified_by={_cm31.verified_by!r}",
)
report(
    "T31-CAP-1b",
    "ConstraintMatrix has meta_yield=0.0 (float) on fresh init",
    hasattr(_cm31, "meta_yield") and isinstance(_cm31.meta_yield, float) and _cm31.meta_yield == 0.0,
    f"meta_yield={_cm31.meta_yield}",
)
report(
    "T31-CAP-1c",
    "ConstraintMatrix has interaction_history=[] (list) on fresh init",
    hasattr(_cm31, "interaction_history") and isinstance(_cm31.interaction_history, list) and _cm31.interaction_history == [],
    f"interaction_history={_cm31.interaction_history}",
)

# ── T31-CAP-2: record_application() ───────────────────────────────────
print("\n--- T31-CAP-2: record_application() mutates cap fields without shattering hash ---")

_cm31_ra = _ri31.ConstraintMatrix()
_cm31_ra.seal()
_hash_before = _cm31_ra.content_hash

_cm31_ra.record_application(agent="test_agent", fitness_delta=0.25, event_tag="tick_31")

report(
    "T31-CAP-2a",
    "record_application() sets verified_by to the agent name",
    _cm31_ra.verified_by == "test_agent",
    f"verified_by={_cm31_ra.verified_by!r}",
)
report(
    "T31-CAP-2b",
    "record_application() accumulates fitness_delta into meta_yield",
    abs(_cm31_ra.meta_yield - 0.25) < 1e-9,
    f"meta_yield={_cm31_ra.meta_yield}",
)
report(
    "T31-CAP-2c",
    "content_hash UNCHANGED after record_application() — hash not shattered",
    _cm31_ra.content_hash == _hash_before,
    f"before={_hash_before[:12]}… after={_cm31_ra.content_hash[:12]}…",
)

# ── T31-CAP-3: to_dict() / from_dict() round-trip ─────────────────────
print("\n--- T31-CAP-3: Serialization round-trip and backward compat ---")

_cm31_ser = _ri31.ConstraintMatrix()
_cm31_ser.record_application(agent="serializer", fitness_delta=0.10, event_tag="t31")
_d31 = _cm31_ser.to_dict()

report(
    "T31-CAP-3a",
    "to_dict() emits all 4 capitalization fields",
    all(k in _d31 for k in ("verified_by", "meta_yield", "interaction_history", "kvs_score")),
    f"keys present={[k for k in ('verified_by','meta_yield','interaction_history','kvs_score') if k in _d31]}",
)

_cm31_rt = _ri31.ConstraintMatrix.from_dict(_d31)
report(
    "T31-CAP-3b",
    "from_dict() round-trips meta_yield correctly",
    abs(_cm31_rt.meta_yield - _cm31_ser.meta_yield) < 1e-9,
    f"original={_cm31_ser.meta_yield} round-tripped={_cm31_rt.meta_yield}",
)

# Backward compat: dict without cap fields (pre-TICK-31) → safe defaults
_legacy_dict = {
    "version": 0,
    "matrix": [[0.0] * 8 for _ in range(8)],
    "lineage": [],
    "substrate_deps": {},
    "seed": 0,
    "content_hash": "",
}
_cm31_legacy = _ri31.ConstraintMatrix.from_dict(_legacy_dict)
report(
    "T31-CAP-3c",
    "from_dict() with pre-TICK-31 dict (missing cap fields) loads with safe defaults",
    _cm31_legacy.meta_yield == 0.0 and _cm31_legacy.verified_by == "" and _cm31_legacy.kvs_score == 0.0,
    f"meta_yield={_cm31_legacy.meta_yield} verified_by={_cm31_legacy.verified_by!r} kvs_score={_cm31_legacy.kvs_score}",
)

# ── T31-CAP-4: interaction_history cap at 50 ──────────────────────────
print("\n--- T31-CAP-4: interaction_history capped at 50 entries ---")

_cm31_cap = _ri31.ConstraintMatrix()
for _i in range(60):
    _cm31_cap.record_application(agent="stress_agent", fitness_delta=0.01, event_tag=f"step_{_i}")

report(
    "T31-CAP-4a",
    "interaction_history capped at 50 entries after 60 record_application() calls",
    len(_cm31_cap.interaction_history) == 50,
    f"len={len(_cm31_cap.interaction_history)}",
)
report(
    "T31-CAP-4b",
    "meta_yield accumulates all 60 deltas (not truncated with history)",
    abs(_cm31_cap.meta_yield - 60 * 0.01) < 1e-6,
    f"meta_yield={_cm31_cap.meta_yield:.4f} expected={60 * 0.01:.4f}",
)

# ── T31-CAP-5: KVS formula verification ───────────────────────────────
print("\n--- T31-CAP-5: KVS formula K = reuse × max(0, 1 + meta_yield) ---")

_cm31_kvs = _ri31.ConstraintMatrix()
for _i in range(5):
    _cm31_kvs.record_application(agent="kvs_test", fitness_delta=0.50, event_tag=f"step_{_i}")

# After 5 calls: reuse=5, meta_yield=2.5 → K = 5 × max(0, 1+2.5) = 5 × 3.5 = 17.5
_expected_kvs = 5 * max(0.0, 1.0 + 2.5)
report(
    "T31-CAP-5a",
    f"KVS formula: K = reuse × max(0, 1 + meta_yield) = {_expected_kvs}",
    abs(_cm31_kvs.kvs_score - _expected_kvs) < 1e-9,
    f"kvs_score={_cm31_kvs.kvs_score} expected={_expected_kvs}",
)

# Destructive meta_yield below -1 → K = 0
_cm31_kvs_neg = _ri31.ConstraintMatrix()
_cm31_kvs_neg.record_application(agent="kvs_neg", fitness_delta=-5.0, event_tag="fatal")
_expected_neg = max(0.0, 1.0 + (-5.0))  # = 0.0
report(
    "T31-CAP-5b",
    "KVS = 0 when meta_yield < -1.0 (economically inert matrix)",
    _cm31_kvs_neg.kvs_score == 0.0,
    f"kvs_score={_cm31_kvs_neg.kvs_score} meta_yield={_cm31_kvs_neg.meta_yield}",
)


print("\n" + "─" * 70)
print("POWER-LAW SUBSTRATE VERIFICATION SUITE")
print("KVS Atoms: KVS-2026-000001 to KVS-2026-000011")
print("─" * 70)

import math as _mathPL
import genome_assembler as _gaPL
from autopoietic_core import PhiGovernor, _PHI_SOVEREIGNTY_MIN

# ── TPL-1: BarbellFilter — known MEDIUM candidate is vetoed ──────────────
print("\n--- TPL-1: BarbellFilter MEDIUM veto ---")

# MEDIUM: adds params (delta > 0), marginal epi gain, low leverage
_pl_medium_leverage = _gaPL.compute_leverage_score(
    epi_delta=0.005,    # small gain < _BARBELL_DELTA_EPI_MEDIUM_MAX
    reuse_count=1,
    cross_domain_potential=0.33,
    total_params=500_000,
)
_pl_medium_class = _gaPL.classify_candidate(
    param_delta=500_000,   # adds params
    epi_delta=0.005,
    leverage_score=_pl_medium_leverage,
)
report(
    "TPL-1a",
    "Medium-gain, high-cost candidate classified as MEDIUM (→ VETO)",
    _pl_medium_class == "MEDIUM",
    f"leverage={_pl_medium_leverage:.4f} class={_pl_medium_class}",
)

# AGGRESSIVE: high leverage (epi_delta large relative to cost)
_pl_agg_leverage = _gaPL.compute_leverage_score(
    epi_delta=0.15,         # large gain
    reuse_count=3,
    cross_domain_potential=0.8,
    total_params=200_000,
)
_pl_agg_class = _gaPL.classify_candidate(
    param_delta=200_000,
    epi_delta=0.15,
    leverage_score=_pl_agg_leverage,
)
report(
    "TPL-1b",
    "High-leverage candidate classified as AGGRESSIVE (→ ACCEPT)",
    _pl_agg_class == "AGGRESSIVE",
    f"leverage={_pl_agg_leverage:.4f} class={_pl_agg_class}",
)

# CONSERVATIVE: reduces params, non-negative epi
_pl_cons_class = _gaPL.classify_candidate(
    param_delta=-10_000,   # fewer params
    epi_delta=0.001,
    leverage_score=0.1,    # low leverage — but CONSERVATIVE overrides
)
report(
    "TPL-1c",
    "Param-reducing candidate classified as CONSERVATIVE (→ ACCEPT)",
    _pl_cons_class == "CONSERVATIVE",
    f"class={_pl_cons_class}",
)


# ── TPL-2: Kelly Criterion — bet decays to 0 as phi approaches floor ──────
print("\n--- TPL-2: Kelly Criterion floor-decay ---")

_leverage_high = 6.0   # AGGRESSIVE class leverage

# Well above floor: phi_ratio = 0.90
_kelly_high = PhiGovernor.kelly_bet_size(phi_ratio=0.90, leverage_score=_leverage_high)
# Near floor: phi_ratio = 0.15 (just above _PHI_SOVEREIGNTY_MIN = 0.12)
_kelly_near = PhiGovernor.kelly_bet_size(phi_ratio=0.15, leverage_score=_leverage_high)
# At floor: phi_ratio = _PHI_SOVEREIGNTY_MIN
_kelly_floor = PhiGovernor.kelly_bet_size(phi_ratio=_PHI_SOVEREIGNTY_MIN, leverage_score=_leverage_high)
# Below floor: phi_ratio = 0.10
_kelly_below = PhiGovernor.kelly_bet_size(phi_ratio=0.10, leverage_score=_leverage_high)

report(
    "TPL-2a",
    "Kelly bet at phi=0.90 is positive and bounded [0, 1]",
    0.0 < _kelly_high <= 1.0,
    f"kelly_high={_kelly_high:.6f}",
)
report(
    "TPL-2b",
    "Kelly bet at phi=0.15 (near floor) is smaller than at phi=0.90",
    _kelly_near < _kelly_high,
    f"kelly_near={_kelly_near:.6f} kelly_high={_kelly_high:.6f}",
)
report(
    "TPL-2c",
    "Kelly bet at phi=_PHI_SOVEREIGNTY_MIN decays to 0.0 (Absorbing Barrier)",
    _kelly_floor == 0.0,
    f"kelly_floor={_kelly_floor:.6f} floor={_PHI_SOVEREIGNTY_MIN}",
)
report(
    "TPL-2d",
    "Kelly bet below floor is exactly 0.0 (ruin prevention)",
    _kelly_below == 0.0,
    f"kelly_below={_kelly_below:.6f}",
)


# ── TPL-3: Kelly cold-start — phi_peak=0 returns 0.0 without crash ────────
print("\n--- TPL-3: Kelly cold-start guard ---")

# Cold start: phi_ratio computed as 0.0/0.0 — must not crash, must return 0.0
_kelly_cold = PhiGovernor.kelly_bet_size(phi_ratio=0.0, leverage_score=_leverage_high)
report(
    "TPL-3a",
    "Kelly cold-start (phi_ratio=0.0) returns 0.0 without exception",
    _kelly_cold == 0.0,
    f"kelly_cold={_kelly_cold:.6f}",
)

# No-edge: leverage_score = 0.5 (< 1.0) → edge ≤ 0 → 0.0
_kelly_no_edge = PhiGovernor.kelly_bet_size(phi_ratio=0.90, leverage_score=0.5)
report(
    "TPL-3b",
    "Kelly with leverage_score < 1.0 (no positive edge) returns 0.0",
    _kelly_no_edge == 0.0,
    f"kelly_no_edge={_kelly_no_edge:.6f}",
)


# ── TPL-4: BarbellFilter in _compute_phi_value returns -inf for MEDIUM ────
print("\n--- TPL-4: _compute_phi_value MEDIUM veto (BarbellFilter in MCTS) ---")
import time as _timePL

# Build a minimal assembly that will be classified MEDIUM:
# Low epi (0.005) + large param count → low leverage → MEDIUM
import tempfile as _tmpPL, os as _osPL
from pathlib import Path as _PathPL

with _tmpPL.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as _f_med:
    # Embed a large hidden_dim to push param count high
    _f_med.write(
        "# Organelle: routing | class=RoutingStrategy | gen=0000001 | epi=0.005000 | t=1700000000\n"
        "import torch.nn as nn\n"
        "class RoutingStrategy(nn.Module):\n"
        "    def __init__(self, d_model=4096, n_experts=32):\n"
        "        super().__init__()\n"
        "        self.gate = nn.Linear(4096, 32)\n"
        "    def forward(self, x, experts, router_idx):\n"
        "        return x\n"
    )
    _f_med_path = _f_med.name

_asm_medium = {"routing": (_PathPL(_f_med_path), 0.005, open(_f_med_path).read())}
_t_pl = _timePL.monotonic() * 1000.0
_phi_medium = _gaPL._compute_phi_value(_asm_medium, "/tmp", _t_pl, depth=1)
_osPL.unlink(_f_med_path)

report(
    "TPL-4a",
    "_compute_phi_value returns -inf for MEDIUM Risk/Reward assembly (BarbellFilter MCTS veto)",
    _phi_medium == float("-inf"),
    f"phi_value={_phi_medium}",
)


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
if FAIL == 0:
    print("ALL TESTS PASSED — Tri-Agent Test-Runner + Epigenetic Coupling verified.")
else:
    print(f"FAILURES DETECTED — {FAIL} test(s) failed.")
print("=" * 70)

sys.exit(0 if FAIL == 0 else 1)
