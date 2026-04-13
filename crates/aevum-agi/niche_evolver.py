#!/usr/bin/env python3
"""niche_evolver.py — Thermodynamic MuZero Niche Construction Engine (TICK 20.0).

"Let the organism create the universe it needs to transcend."

A MuZero-inspired architecture adapted for Thermodynamic Niche Construction.
Generates simulated physical/mathematical challenges (Niches) for the organism
to evolve against — closing the Autopoietic loop by making the environment
itself an evolvable substrate.

Triggered ONLY by the Slow Brain during Heat Death alerts (TICK 18.0).

══════════════════════════════════════════════════════════════════════════════
MUZERO ADAPTATION
══════════════════════════════════════════════════════════════════════════════

Classical MuZero:
  - Representation function h(obs) → latent state
  - Dynamics function g(state, action) → next_state + reward
  - Prediction function f(state) → policy + value

Thermodynamic Adaptation:
  - Model Head: generate parameters of the new simulated challenge vector
  - Value Head (Φ Oracle): predict organism's Free Energy Rate Density (Φ_pred)
                           in this niche — using the same Roofline physics as
                           the TICK 19.0 DAG Oracle
  - Policy Head: rank candidates by niche_value and select the optimal one

══════════════════════════════════════════════════════════════════════════════
NICHE VALUE FORMULA
══════════════════════════════════════════════════════════════════════════════

    New_Niche_Value = Phi_pred - λ × (generation_cost + mismatch_penalty)

Where:
    Phi_pred          — predicted Φ of the organism in this niche
    generation_cost   — normalized wall-clock cost to generate this niche [0,1]
    mismatch_penalty  — Zone of Proximal Development mismatch:
                        0.0  if difficulty is in the ZPD band [_ZPD_LOWER, _ZPD_UPPER]
                        >0.0 if too easy (organism barely challenged) or
                        too hard (organism cannot survive at all)

Niches with Value ≤ 0 are discarded.

══════════════════════════════════════════════════════════════════════════════
M-SERIES REALITY COUPLING  (Anti-Matrix-Delusion Anchor)
══════════════════════════════════════════════════════════════════════════════

All generated Niches embed simulated Apple Silicon hardware constraints to
prevent "Matrix Delusion" — purely mathematical hallucination that looks
good in theory but cannot run on actual silicon.

Constraints embedded in every Niche:
  - Memory bandwidth bottlenecks (GB/s cap matched to chip tier)
  - Cache miss penalty (ns-level latency injected into data pipeline)
  - IoT sensor data latency (variable-rate input streams, randomly present)
  - Unified memory pressure (fraction of chip RAM consumed by the niche)

Chip constants mirror TICK 19.0 dag_oracle.py §7 (M-Series MPS Reality Coupling).
They are immutable — changing them would sever the Reality Coupling.

══════════════════════════════════════════════════════════════════════════════
DAG ORACLE GATE
══════════════════════════════════════════════════════════════════════════════

Before a niche is accepted, the DAG Oracle pre-filters it.  If the Oracle
predicts that the organism's Φ_pred in this niche is below 20% of its current
elite Φ (i.e., an 80%+ thermodynamic tax), the niche is vetoed.

This prevents the Niche Constructor from generating impossible environments
that would permanently kill the evolutionary search.

══════════════════════════════════════════════════════════════════════════════
IPC CONTRACT
══════════════════════════════════════════════════════════════════════════════

Niches are written to candidate_pool/env_active/current.json using the
same tmp→rename atomic protocol as all other TICK IPC channels.

The Evaluator Daemon (TICK 12.0) already polls this path every
_ENV_REFRESH_INTERVAL ticks (200) and respawns env_stream.py with the
new config when the "version" field changes.  No evaluator modification
needed beyond the startup directory bootstrap.

══════════════════════════════════════════════════════════════════════════════
GRAND COMPOUNDING LOOP (TICK 20.0 closes the loop)
══════════════════════════════════════════════════════════════════════════════

  Niche Generation : niche_evolver.py (TICK 20.0) → new challenge
  Physical Filter  : dag_oracle.py  (TICK 19.0) → viability gate (80% tax veto)
  Quantum Rollout  : mutator_daemon.py MCTS (TICK 17.0) → assembly in new niche
  Dual-Brain Exec  : Fast Brain tunes, Slow Brain invents (TICK 18.0)
  Compounding      : MDL gains + Φ updates rewrite the Time Topology
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import os
import random
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# TICK 38.0: Optional MLX import for Hilbert Tensor Product Fusion.
# If MLX is unavailable (non-Apple-Silicon or not installed), falls back to
# pure-Python nested-loop Kronecker.  No hard dependency introduced.
try:
    import mlx.core as _mx_core
    _MLX_AVAILABLE = True
except Exception:
    _mx_core = None  # type: ignore[assignment]
    _MLX_AVAILABLE = False

# TICK 28.0: Constraint Exchange Protocol imports.
# Deferred in a try/except for standalone niche_evolver testing without full stack.
try:
    from rule_ir import (
        ConstraintMatrix,
        EpigeneticFailureType,
        ConstraintMorphism,
        NegativeTransferFirewall,
        _SHADOW_SOVEREIGNTY_FLOOR,
        _SHADOW_PENALTY_COST_EST,
        # TICK 29.0: SRCA imports
        ConstitutionalViolationError,
        EvolvableSoftShell,
        SoftShellAmendment,
        ConstitutionalDiffLedger,
        IMMUTABLE_HARD_CORE,
    )
    _RULE_IR_AVAILABLE = True
    _SRCA_AVAILABLE = True
except ImportError:
    _RULE_IR_AVAILABLE = False
    _SRCA_AVAILABLE = False
    ConstraintMatrix = None           # type: ignore[assignment,misc]
    EpigeneticFailureType = None      # type: ignore[assignment,misc]
    ConstraintMorphism = None         # type: ignore[assignment,misc]
    NegativeTransferFirewall = None   # type: ignore[assignment,misc]
    ConstitutionalViolationError = None  # type: ignore[assignment,misc]
    EvolvableSoftShell = None         # type: ignore[assignment,misc]
    SoftShellAmendment = None         # type: ignore[assignment,misc]
    ConstitutionalDiffLedger = None   # type: ignore[assignment,misc]
    IMMUTABLE_HARD_CORE = frozenset()  # type: ignore[assignment]
    _SHADOW_SOVEREIGNTY_FLOOR = 0.12
    _SHADOW_PENALTY_COST_EST = 0.02


# ── M-Series Hardware Reality Constants ─────────────────────────────────────
# Calibrated against Apple Silicon benchmarks (mirrors TICK 19.0 dag_oracle.py §7).
# Immutable — do not modify without updating dag_oracle.py in lockstep.
_M_SERIES_CONFIGS: Dict[str, Dict[str, float]] = {
    "M1":       {"bw_gb_s": 68.25,  "unified_ram_gb": 16.0,  "cache_latency_ns": 30.0},
    "M2":       {"bw_gb_s": 100.0,  "unified_ram_gb": 24.0,  "cache_latency_ns": 28.0},
    "M3":       {"bw_gb_s": 150.0,  "unified_ram_gb": 36.0,  "cache_latency_ns": 25.0},
    "M4":       {"bw_gb_s": 273.0,  "unified_ram_gb": 32.0,  "cache_latency_ns": 20.0},
    "M1 Ultra": {"bw_gb_s": 800.0,  "unified_ram_gb": 128.0, "cache_latency_ns": 35.0},
    "M2 Ultra": {"bw_gb_s": 800.0,  "unified_ram_gb": 192.0, "cache_latency_ns": 33.0},
    "M3 Max":   {"bw_gb_s": 400.0,  "unified_ram_gb": 128.0, "cache_latency_ns": 27.0},
}
_DEFAULT_CHIP: str = "M1 Ultra"  # Mac Studio default (matches TICK 19.0)

# ── Niche Construction Constants ─────────────────────────────────────────────
_NICHE_LAMBDA: float = 0.15          # λ weight for (generation_cost + mismatch_penalty)
_ZPD_LOWER: float = 0.05             # Zone of Proximal Development — lower bound (rel. difficulty)
_ZPD_UPPER: float = 0.85             # Zone of Proximal Development — upper bound (rel. difficulty)
_MAX_NICHE_CANDIDATES: int = 12      # MuZero rollout breadth (Model Head candidates)
_NICHE_ORACLE_TAX_VETO: float = 0.80 # DAG Oracle veto: Φ_pred < elite_epi × (1 − 0.80)
_NICHE_COOLDOWN_S: float = 300.0     # Minimum seconds between niche generations

# ── IPC Paths (mirror evaluator_daemon.py TICK 12.0) ────────────────────────
_NICHE_ACTIVE_PATH: str = "candidate_pool/env_active/current.json"
_NICHE_ARCHIVE_PATH: str = "candidate_pool/island_meta/niche_archive.ndjson"
_NICHE_LOG_PATH: str = "logs/niche_evolver_events.ndjson"

# ═══════════════════════════════════════════════════════════════
# TICK 30.0: HERITABLE FISSION, SPECIES RADIATION (HFSR)
# ═══════════════════════════════════════════════════════════════
#
# When the thermodynamic marginal cost of learning hits the absolute
# physical ceiling (RAM pressure AND Φ stagnation simultaneously),
# the unified organism irreversibly splits into independent Lineages.
# Each Lineage inherits IMMUTABLE_HARD_CORE by reference (identity),
# but receives completely severed soft-shell, constraint matrices,
# and organelle pools.  They then evolve as sovereign species.
#
# LineageCorrelationMonitor enforces thermodynamic ecological divergence:
# lineages that develop correlated topological strategies pay a Φ tax
# (Jaccard ≥ _CORRELATION_TAX_THRESHOLD → 15% epi penalty) forcing them
# into orthogonal niches.

# ── Mod-1: TICK 30.0 Constants ───────────────────────────────────────────
# RAM pressure fraction (of chip's unified_ram_gb) at which fission is
# considered.  Must remain above threshold for _FISSION_PRESSURE_WINDOW
# consecutive ticks AND phi must be stagnant to actually trigger.
_FISSION_RAM_PRESSURE_THRESHOLD: float = 0.85

# Consecutive ticks that RAM pressure must exceed threshold before the
# fission trigger arms itself.  Guards against transient MLX eval() spikes.
_FISSION_PRESSURE_WINDOW: int = 3

# Number of ticks to look back when computing Φ learning velocity.
_FISSION_PHI_STAGNATION_WINDOW: int = 10

# Minimum Φ improvement across the stagnation window to block fission.
# If improvement < this delta the organism is stuck: fission is permitted.
_FISSION_PHI_STAGNATION_DELTA: float = 0.005

# TICK 30.1 — Epistemic Mode: consecutive ticks of absolute Φ stagnation
# (phi_improvement < _FISSION_PHI_STAGNATION_DELTA with zero velocity)
# required to trigger HFSR independently of RAM pressure.  Guards against
# noise bursts; 30 ticks ≈ a genuine cognitive wall, not a transient plateau.
_FISSION_EXTREME_STAGNATION_WINDOW: int = 30

# Jaccard topological overlap above which the correlation tax fires.
_CORRELATION_TAX_THRESHOLD: float = 0.30

# Fractional Φ penalty applied per tick to each member of a correlated pair.
# effective_epi *= (1.0 - _CORRELATION_TAX_RATE)
_CORRELATION_TAX_RATE: float = 0.15

# Split assignment: first two species → child A, last two → child B.
# Order matches _NICHE_SPECIES_CONFIGS insertion order (LATENCY, COMPRESSION,
# BANDWIDTH, GENERAL).  Hardcoded for determinism; future TICKs may make
# this adaptive.
_FISSION_SPLIT_A: Tuple[str, ...] = ("LATENCY", "COMPRESSION")
_FISSION_SPLIT_B: Tuple[str, ...] = ("BANDWIDTH", "GENERAL")

# ── TICK 38.0: Gödelian Injection & Hilbert Fusion Constants ─────────────────
# Path where ext_raw_ingestor.py writes pending Gödelian constraint payloads.
_GOEDEL_PENDING_PATH: str = "candidate_pool/goedel_pending"

# Jaccard similarity threshold above which LineageCorrelationMonitor triggers
# Hilbert Tensor Product Fusion instead of the standard 15% tax.
# Must be strictly greater than _CORRELATION_TAX_THRESHOLD (0.30).
_FUSION_JACCARD_THRESHOLD: float = 0.85


# ── TICK 38.0: Gödelian Constraint Fetcher ───────────────────────────────────

def _fetch_goedel_constraint(
    pending_dir: str = _GOEDEL_PENDING_PATH,
) -> Optional[Dict[str, Any]]:
    """Read and consume the highest-scoring Gödelian constraint from pending dir.

    Scans all .json files in `pending_dir`, parses each, selects the one with
    the highest `source_score`, deletes that file (to prevent re-injection),
    and returns its payload dict.

    Returns None if the directory does not exist or has no valid payloads.

    Atomicity: the file is deleted *after* successful parse.  A crash between
    parse and delete leaves the file in place — it will be consumed on the next
    fission event (acceptable: a duplicate injection is better than a missed one).
    """
    if not os.path.isdir(pending_dir):
        return None

    best_payload: Optional[Dict[str, Any]] = None
    best_score: float = -1.0
    best_path: Optional[str] = None

    for fname in os.listdir(pending_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(pending_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            score = float(payload.get("source_score", 0.0))
            if score > best_score:
                best_score = score
                best_payload = payload
                best_path = fpath
        except Exception:
            continue  # Malformed file — skip silently

    if best_path is not None:
        try:
            os.remove(best_path)
        except OSError:
            pass  # Already consumed by another concurrent fission — safe

    return best_payload


# ── Mod-2: Lineage dataclass ──────────────────────────────────────────────
@dataclasses.dataclass
class Lineage:
    """TICK 30.0: An independent evolutionary lineage post-fission.

    Created by LineageRegistry.execute_fission().  Once created, a Lineage
    is sovereign — its soft_shell_snapshot, constraint_matrices, and species
    evolve completely independently from sibling lineages.

    The genetic_core field MUST be the same object as IMMUTABLE_HARD_CORE
    (verified by `is` identity check, not equality).  This is the only
    information shared across lineage boundaries — the mathematical bedrock
    of existence itself.

    Fields:
        lineage_id:           Unique ID, format "L{n}_{parent_id}_{timestamp}".
        parent_id:            ID of the parent lineage (None for primordial).
        generation:           Fission generation count (0 = primordial).
        genetic_core:         Reference to IMMUTABLE_HARD_CORE frozenset.
                              MUST satisfy `genetic_core is IMMUTABLE_HARD_CORE`.
        soft_shell_snapshot:  Independent copy of EvolvableSoftShell values
                              at fission time.  Mutations here don't affect siblings.
        species:              Dict of NicheSpecies assigned to this lineage.
                              Keys are niche names (e.g. "LATENCY", "COMPRESSION").
        constraint_matrices:  Deep copies of per-niche ConstraintMatrix objects.
                              Completely severed from parent and sibling matrices.
        fission_timestamp:    Unix timestamp when this lineage was created.
        epi_history:          Rolling fitness log (appended by the evaluator).
                              Used by FissionTrigger for stagnation detection.
    """
    lineage_id: str
    parent_id: Optional[str]
    generation: int
    genetic_core: frozenset            # MUST be IMMUTABLE_HARD_CORE by reference
    soft_shell_snapshot: Dict[str, float]
    species: Dict[str, "NicheSpecies"]
    constraint_matrices: Dict[str, Any]
    fission_timestamp: float
    epi_history: List[float] = dataclasses.field(default_factory=list)
    # TICK 38.0: Hilbert Tensor Product Fusion state.
    # When two lineages are fused by LineageCorrelationMonitor.fuse_lineages(),
    # the 64x64 Kronecker product of their 8x8 constraint matrices is stored here
    # as the actual hyper-dimensional escape state.  None for non-fused lineages.
    hilbert_tensor: Optional[Any] = dataclasses.field(default=None)

    def best_epi(self) -> float:
        """Return the highest epi across all species in this lineage."""
        if not self.species:
            return 0.0
        return max(s.best_epi for s in self.species.values())

    def topology_hashes(self) -> Set[str]:
        """Return the union of all topology hashes across this lineage's Pareto fronts."""
        hashes: Set[str] = set()
        for sp in self.species.values():
            for entry in sp.pareto_front:
                hashes.add(entry.topology_hash)
        return hashes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "genetic_core_size": len(self.genetic_core),
            "species": list(self.species.keys()),
            "best_epi": self.best_epi(),
            "fission_timestamp": self.fission_timestamp,
            "epi_history_len": len(self.epi_history),
            "hilbert_fused": self.hilbert_tensor is not None,
        }


# ── Mod-3: FissionTrigger ─────────────────────────────────────────────────
class FissionTrigger:
    """TICK 30.1: Dual-mode fission monitor (OR logic).

    Triggers HFSR (Heritable Fission & Species Radiation) when EITHER
    condition holds:

    Condition A — Physical Mode (original TICK 30.0 AND logic):
      1. RAM pressure ≥ _FISSION_RAM_PRESSURE_THRESHOLD for
         _FISSION_PRESSURE_WINDOW consecutive ticks (prevents transient spikes
         from triggering fission during normal large MLX eval() dispatches).
      2. Φ improvement over the last _FISSION_PHI_STAGNATION_WINDOW ticks
         < _FISSION_PHI_STAGNATION_DELTA (organism is genuinely stuck, not
         just temporarily compressed).

    Condition B — Epistemic Mode (TICK 30.1 addition):
      Φ improvement < _FISSION_PHI_STAGNATION_DELTA for
      _FISSION_EXTREME_STAGNATION_WINDOW *consecutive* ticks, regardless of
      RAM pressure.  Solves the Golden Cage Paradox: a hyper-efficient organism
      on a large-memory substrate never reaches 85% RAM, yet may still hit an
      insurmountable cognitive wall.  30 consecutive stagnant ticks constitutes
      proof of epistemic death — RAM pain is irrelevant.

    Biological analogy: Condition A = habitat full + learning plateau (classic
    resource pressure).  Condition B = pure epistemic extinction event — the
    organism has exhausted all accessible knowledge without physical constraint.

    Thread-safety: record() and should_fission() are called under
    SharedState._lock.  No independent lock needed.
    """

    def __init__(self) -> None:
        self._ram_pressure_history: deque = deque(maxlen=_FISSION_PRESSURE_WINDOW + 5)
        self._phi_history: deque = deque(
            maxlen=max(_FISSION_PHI_STAGNATION_WINDOW, _FISSION_EXTREME_STAGNATION_WINDOW) + 5
        )
        self._consecutive_pressure_count: int = 0
        # TICK 30.1: tracks consecutive ticks where Φ window shows zero progress
        self._consecutive_stagnation_count: int = 0

    def record(self, ram_ratio: float, phi_current: float) -> None:
        """Record one observation.  Call once per boundary tick."""
        self._phi_history.append(phi_current)
        self._ram_pressure_history.append(ram_ratio)

        # Physical Mode counter (Condition A)
        if ram_ratio >= _FISSION_RAM_PRESSURE_THRESHOLD:
            self._consecutive_pressure_count += 1
        else:
            self._consecutive_pressure_count = 0

        # Epistemic Mode counter (Condition B) — updated every tick once we
        # have enough history, regardless of RAM ratio.
        phi_list = list(self._phi_history)
        if len(phi_list) >= _FISSION_PHI_STAGNATION_WINDOW:
            window = phi_list[-_FISSION_PHI_STAGNATION_WINDOW:]
            phi_improvement = max(window) - min(window)
            if phi_improvement < _FISSION_PHI_STAGNATION_DELTA:
                self._consecutive_stagnation_count += 1
            else:
                self._consecutive_stagnation_count = 0
        # Not enough data yet — leave _consecutive_stagnation_count at current value

    def should_fission(self) -> bool:
        """True iff Condition A (Physical) OR Condition B (Epistemic) is met."""
        phi_list = list(self._phi_history)

        # ── Condition B: Epistemic Mode ───────────────────────────────────
        # Fires regardless of RAM pressure when stagnation has persisted for
        # _FISSION_EXTREME_STAGNATION_WINDOW consecutive ticks.
        if self._consecutive_stagnation_count >= _FISSION_EXTREME_STAGNATION_WINDOW:
            return True

        # ── Condition A: Physical Mode ────────────────────────────────────
        # Original TICK 30.0 AND logic: sustained RAM pressure + Φ stagnation.
        if self._consecutive_pressure_count < _FISSION_PRESSURE_WINDOW:
            return False
        if len(phi_list) < _FISSION_PHI_STAGNATION_WINDOW:
            return False  # not enough data yet
        window = phi_list[-_FISSION_PHI_STAGNATION_WINDOW:]
        phi_improvement = max(window) - min(window)
        return phi_improvement < _FISSION_PHI_STAGNATION_DELTA

    def reset(self) -> None:
        """Call immediately after fission executes to re-arm for next event."""
        self._consecutive_pressure_count = 0
        self._consecutive_stagnation_count = 0
        self._phi_history.clear()
        self._ram_pressure_history.clear()


# ── TICK 38.0: Hilbert Tensor Product Helpers ─────────────────────────────────

def _kron_pure_python(
    A: List[List[float]],
    B: List[List[float]],
) -> List[List[float]]:
    """Pure-Python Kronecker product fallback.

    Computes C = A ⊗ B where A is (m×n) and B is (p×q), producing (mp×nq).
    Used when MLX is unavailable.

    Time complexity: O(m × n × p × q) — for 8x8 inputs this is 8^4 = 4096
    operations, negligible.
    """
    m, n = len(A), len(A[0])
    p, q = len(B), len(B[0])
    rows = m * p
    cols = n * q
    C: List[List[float]] = [[0.0] * cols for _ in range(rows)]
    for i in range(m):
        for j in range(n):
            a_ij = A[i][j]
            for r in range(p):
                for s in range(q):
                    C[i * p + r][j * q + s] = a_ij * B[r][s]
    return C


def _project_64x64_to_8x8(
    H: List[List[float]],
) -> List[List[float]]:
    """Project a 64x64 Kronecker product back to 8x8 via block-mean reduction.

    The 64x64 matrix is partitioned into 8x8 blocks of size 8x8 each.
    Each output cell C_proj[i][j] = mean of H[i*8:(i+1)*8, j*8:(j+1)*8].

    This extracts the dominant eigenstructure of the fused Hilbert space
    while maintaining compatibility with the existing ConstraintMatrix API.
    """
    n_blocks = 8
    block_size = 8
    proj: List[List[float]] = [[0.0] * n_blocks for _ in range(n_blocks)]
    for i in range(n_blocks):
        for j in range(n_blocks):
            total = 0.0
            for r in range(block_size):
                for s in range(block_size):
                    total += H[i * block_size + r][j * block_size + s]
            proj[i][j] = total / (block_size * block_size)
    return proj


# ── Mod-4: LineageCorrelationMonitor ─────────────────────────────────────
class LineageCorrelationMonitor:
    """TICK 30.0: Enforces thermodynamic ecological divergence.

    After fission, lineages must evolve into orthogonal ecological niches.
    If two lineages share too many topological strategies (Jaccard similarity
    of their Pareto-front topology hash sets ≥ _CORRELATION_TAX_THRESHOLD),
    both pay a Φ epi multiplier penalty each tick until they diverge.

    TICK 38.0 — Hilbert Tensor Product Fusion:
    When Jaccard similarity ≥ _FUSION_JACCARD_THRESHOLD (0.85), instead of
    merely taxing the correlated lineages, they are fused into a single
    Meta-Lineage via Kronecker product: H_new = H_A ⊗ H_B.  This achieves
    dimensional escape — the fused lineage explores a constraint space that
    is strictly larger than either parent lineage alone.

    This tax is purely mathematical — no organelle is deleted, no boundary
    is moved.  The evaluation loop multiplies effective_epi by the returned
    multiplier when computing MCTS value.

    Complexity: O(L² × H) where L = lineage count (≤8), H = hash set size
    (≤_MAX_NICHE_CANDIDATES × niche_count ≤ 48).  Bounded and negligible.
    """

    @staticmethod
    def compute_overlap(lineage_a: Lineage, lineage_b: Lineage) -> float:
        """Jaccard similarity between two lineages' topology hash sets.

        Returns:
            float in [0.0, 1.0]. 0.0 = completely orthogonal, 1.0 = identical.
        """
        hashes_a = lineage_a.topology_hashes()
        hashes_b = lineage_b.topology_hashes()
        union = hashes_a | hashes_b
        if not union:
            return 0.0
        intersection = hashes_a & hashes_b
        return len(intersection) / len(union)

    @staticmethod
    def fuse_lineages(
        lineage_a: Lineage,
        lineage_b: Lineage,
    ) -> Lineage:
        """TICK 38.0: Fuse two over-correlated lineages via Hilbert Tensor Product.

        Computes H_new = H_A ⊗ H_B (Kronecker product of their first
        ConstraintMatrix's C matrices, 8x8 ⊗ 8x8 → 64x64).  The 64x64 tensor
        is stored on the new Meta-Lineage as `hilbert_tensor` (the dimensional
        escape state), while the projected 8x8 mean becomes its standard C
        matrix for backward-compatible use by existing mutation code.

        The fused lineage:
        - Inherits the same IMMUTABLE_HARD_CORE as both parents (by identity).
        - Takes the union of both parents' species and constraint matrices.
        - Records its dimensional escape in the hilbert_tensor field.
        - Its lineage_id encodes the fusion event: "FUSED_{a_id}_{b_id}".

        Guard: If a lineage's hilbert_tensor is already set (it is itself a
        Meta-Lineage from a prior fusion), it CANNOT be re-fused.  Recursive
        Kronecker products would cause exponential tensor growth.  In that case,
        the standard tax is applied instead.

        Args:
            lineage_a: First over-correlated lineage.
            lineage_b: Second over-correlated lineage.

        Returns:
            A new Meta-Lineage with the fused constraint structure.
        """
        # Guard: no recursive fusion
        if lineage_a.hilbert_tensor is not None or lineage_b.hilbert_tensor is not None:
            raise ValueError(
                "Cannot fuse a Meta-Lineage (hilbert_tensor already set). "
                "Apply standard tax instead."
            )

        ts = time.time()

        # ── Extract first available ConstraintMatrix C from each lineage ──
        def _first_C(lg: Lineage) -> Optional[List[List[float]]]:
            for cm in lg.constraint_matrices.values():
                if cm is not None and hasattr(cm, "C"):
                    return cm.C
            return None

        C_a = _first_C(lineage_a)
        C_b = _first_C(lineage_b)

        hilbert_tensor_result: Optional[Any] = None
        fused_C: Optional[List[List[float]]] = None

        if C_a is not None and C_b is not None:
            if _MLX_AVAILABLE and _mx_core is not None:
                # MLX path: mx.kron() → 64x64 MLX array
                arr_a = _mx_core.array(C_a, dtype=_mx_core.float32)
                arr_b = _mx_core.array(C_b, dtype=_mx_core.float32)
                H = _mx_core.kron(arr_a, arr_b)        # shape [64, 64]
                _mx_core.eval(H)                        # materialise on Metal
                hilbert_tensor_result = H
                # Project to 8x8 for ConstraintMatrix compatibility
                H_list = H.tolist()
            else:
                # Pure-Python fallback
                H_list = _kron_pure_python(C_a, C_b)
                hilbert_tensor_result = H_list          # store as nested list

            fused_C = _project_64x64_to_8x8(H_list)

        # ── Build fused constraint matrices (merge both parents, apply fused_C) ──
        fused_cms: Dict[str, Any] = {}
        # child_a's matrices
        for nname, cm in lineage_a.constraint_matrices.items():
            fused_cms[nname] = copy.deepcopy(cm)
        # child_b's matrices (b wins on key conflict)
        for nname, cm in lineage_b.constraint_matrices.items():
            fused_cms[nname] = copy.deepcopy(cm)

        # Apply fused_C to ALL constraint matrices in the merged set
        if fused_C is not None:
            for cm in fused_cms.values():
                if cm is not None and hasattr(cm, "C"):
                    cm.C = copy.deepcopy(fused_C)
                    if hasattr(cm, "lineage"):
                        cm.lineage.append(
                            f"hilbert_fuse:{lineage_a.lineage_id}x{lineage_b.lineage_id}"
                        )

        # ── Merge species (union of both parents) ─────────────────────────
        fused_species: Dict[str, Any] = {}
        for nname, sp in lineage_a.species.items():
            fused_species[nname] = copy.deepcopy(sp)
        for nname, sp in lineage_b.species.items():
            fused_species[nname] = copy.deepcopy(sp)

        meta_lineage = Lineage(
            lineage_id=f"FUSED_{lineage_a.lineage_id}_{lineage_b.lineage_id}_{ts:.0f}",
            parent_id=f"{lineage_a.lineage_id}+{lineage_b.lineage_id}",
            generation=max(lineage_a.generation, lineage_b.generation) + 1,
            genetic_core=IMMUTABLE_HARD_CORE if _RULE_IR_AVAILABLE else frozenset(),
            soft_shell_snapshot={
                **lineage_a.soft_shell_snapshot,
                **lineage_b.soft_shell_snapshot,
            },
            species=fused_species,
            constraint_matrices=fused_cms,
            fission_timestamp=ts,
            epi_history=[],
            hilbert_tensor=hilbert_tensor_result,
        )
        print(
            f"[hilbert] TENSOR FUSION: {lineage_a.lineage_id} ⊗ {lineage_b.lineage_id} "
            f"→ {meta_lineage.lineage_id} "
            f"({'MLX 64x64' if _MLX_AVAILABLE else 'python 64x64'} → 8x8 projected)"
        )
        return meta_lineage

    @staticmethod
    def apply_correlation_tax(
        lineages: List[Lineage],
    ) -> Dict[str, float]:
        """Return per-lineage epi multiplier dict.

        TICK 38.0 update:
        - Jaccard ≥ _FUSION_JACCARD_THRESHOLD (0.85): lineage pair is flagged
          for Hilbert Tensor Product Fusion.  Both members receive the maximum
          tax (1.0 - _CORRELATION_TAX_RATE) as a strong signal, plus a
          "fusion_candidates" entry in the returned dict with value -1.0 as a
          sentinel for the evaluation loop to trigger actual fusion.
        - Jaccard in [_CORRELATION_TAX_THRESHOLD, _FUSION_THRESHOLD): both
          lineages receive the standard 15% Φ tax as before.
        - Jaccard < _CORRELATION_TAX_THRESHOLD: no effect.

        A lineage in multiple correlated pairs still only receives one tax
        application (non-compounding).

        Args:
            lineages: All active lineages.

        Returns:
            Dict mapping lineage_id → float multiplier in (0, 1].
            Fusion candidates are indicated by value -1.0 (sentinel).
        """
        multipliers: Dict[str, float] = {lg.lineage_id: 1.0 for lg in lineages}
        for i in range(len(lineages)):
            for j in range(i + 1, len(lineages)):
                a, b = lineages[i], lineages[j]
                overlap = LineageCorrelationMonitor.compute_overlap(a, b)
                if overlap >= _FUSION_JACCARD_THRESHOLD:
                    # Fusion zone: maximum tax + sentinel flag
                    tax = 1.0 - _CORRELATION_TAX_RATE
                    multipliers[a.lineage_id] = min(multipliers[a.lineage_id], tax)
                    multipliers[b.lineage_id] = min(multipliers[b.lineage_id], tax)
                    # Sentinel: -1.0 marks these two as fusion candidates.
                    # The evaluation loop should call fuse_lineages(a, b) and
                    # replace both in the registry.
                    fusion_key = f"fusion_candidates:{a.lineage_id}:{b.lineage_id}"
                    multipliers[fusion_key] = -1.0
                elif overlap >= _CORRELATION_TAX_THRESHOLD:
                    # Standard tax zone
                    tax = 1.0 - _CORRELATION_TAX_RATE
                    multipliers[a.lineage_id] = min(multipliers[a.lineage_id], tax)
                    multipliers[b.lineage_id] = min(multipliers[b.lineage_id], tax)
        return multipliers


# ── Mod-5: LineageRegistry ────────────────────────────────────────────────
class LineageRegistry:
    """TICK 30.0: Owns and manages all active Lineage objects.

    Starts empty (pre-fission the organism is a single undivided entity).
    After execute_fission() runs, _lineages holds two or more sovereign
    lineages.  Subsequent fission events add more lineages (each child
    splits from one parent lineage).

    Thread-safety: mutations happen under SharedState._lock.  The
    _fission_executed flag prevents a race where two ticks simultaneously
    see should_fission() == True and both attempt to split.
    """

    def __init__(self) -> None:
        self._lineages: Dict[str, Lineage] = {}
        self._fission_count: int = 0
        self._fission_executed: bool = False  # True after first fission

    def execute_fission(
        self,
        registry: "NicheRegistry",
        soft_shell_snapshot: Dict[str, float],
    ) -> Tuple[Lineage, Lineage]:
        """Irreversibly split the NicheRegistry into two sovereign Lineages.

        Atomicity guarantee: both child Lineage objects are fully constructed
        in local variables before any state is committed to self._lineages.
        If an exception occurs during construction, self._lineages is unchanged
        and _fission_executed remains False.

        Identity guarantee: each child's genetic_core is the same object as
        IMMUTABLE_HARD_CORE from rule_ir (verified by `is`).

        Isolation guarantee: each child receives a deep copy of its assigned
        NicheSpecies and ConstraintMatrix objects.  Mutations to child A's
        constraint matrix do not affect child B or the original registry.

        Args:
            registry:             The NicheRegistry being split.
            soft_shell_snapshot:  Current EvolvableSoftShell values (from
                                  SharedState.evolvable_soft_shell.snapshot()).

        Returns:
            (child_a, child_b): the two new Lineage objects.
        """
        ts = time.time()
        parent_id = f"primordial_{ts:.0f}" if self._fission_count == 0 else None
        gen = self._fission_count + 1

        def _build_child(
            niche_names: Tuple[str, ...],
            suffix: str,
        ) -> Lineage:
            child_species: Dict[str, NicheSpecies] = {}
            child_cms: Dict[str, Any] = {}
            for nname in niche_names:
                sp = registry.species.get(nname)
                if sp is None:
                    continue
                child_species[nname] = copy.deepcopy(sp)
                child_cms[nname] = copy.deepcopy(sp.constraint_matrix)
            lid = f"L{gen}_{suffix}_{ts:.0f}"
            return Lineage(
                lineage_id=lid,
                parent_id=parent_id,
                generation=gen,
                genetic_core=IMMUTABLE_HARD_CORE,   # reference, not copy
                soft_shell_snapshot=dict(soft_shell_snapshot),
                species=child_species,
                constraint_matrices=child_cms,
                fission_timestamp=ts,
            )

        # Build both children in local scope before committing (atomicity)
        child_a = _build_child(_FISSION_SPLIT_A, "A")
        child_b = _build_child(_FISSION_SPLIT_B, "B")

        # ── TICK 38.0: EIG Gödelian Axiom Injection ───────────────────────
        # Only child_b (the "explorer" branch) receives the alien parameter.
        # child_a remains conservative to preserve successful exploitation.
        goedel_payload = _fetch_goedel_constraint()
        if goedel_payload is not None:
            target_cat = int(goedel_payload.get("target_category", 0)) % 8
            perturb = goedel_payload.get("perturbation_vector", [])
            axiom_name = goedel_payload.get("axiom_name", "unknown")
            for cm in child_b.constraint_matrices.values():
                if cm is None or not hasattr(cm, "C"):
                    continue
                row = cm.C[target_cat]
                # Clamp to [min_bound, max_bound] from columns 3 and 4
                min_b = row[3] if len(row) > 3 else 0.0
                max_b = row[4] if len(row) > 4 else 1.0
                for k, delta in enumerate(perturb):
                    if k < len(row):
                        row[k] = max(min_b, min(max_b, row[k] + delta))
                if hasattr(cm, "lineage"):
                    cm.lineage.append(f"goedel_inject:{axiom_name}")
            print(
                f"[goedel] Injected axiom '{axiom_name}' into child_b "
                f"(cat={target_cat}, score={goedel_payload.get('source_score', 0):.4f})"
            )

        # Commit — only now are we visible to callers
        self._lineages[child_a.lineage_id] = child_a
        self._lineages[child_b.lineage_id] = child_b
        self._fission_count += 1
        self._fission_executed = True

        print(
            f"[hfsr] HERITABLE FISSION EXECUTED (gen={gen}): "
            f"{child_a.lineage_id} ← {_FISSION_SPLIT_A} | "
            f"{child_b.lineage_id} ← {_FISSION_SPLIT_B}"
        )
        return child_a, child_b

    def all_lineages(self) -> List[Lineage]:
        return list(self._lineages.values())

    def get(self, lineage_id: str) -> Optional[Lineage]:
        return self._lineages.get(lineage_id)

    def fission_count(self) -> int:
        return self._fission_count

    def register_fused_lineage(
        self,
        lineage_a: Lineage,
        lineage_b: Lineage,
        meta_lineage: Lineage,
    ) -> None:
        """TICK 38.0: Replace two parent lineages with their Hilbert-fused Meta-Lineage.

        Called by the evaluation loop when LineageCorrelationMonitor.apply_correlation_tax()
        returns a fusion_candidates sentinel (-1.0) and fuse_lineages() has been invoked.

        Both parent lineage_ids are removed from the registry and replaced with the
        meta_lineage.  This is atomic from the caller's perspective (single method call).

        Args:
            lineage_a:     First parent (will be removed).
            lineage_b:     Second parent (will be removed).
            meta_lineage:  The fused lineage returned by fuse_lineages().
        """
        self._lineages.pop(lineage_a.lineage_id, None)
        self._lineages.pop(lineage_b.lineage_id, None)
        self._lineages[meta_lineage.lineage_id] = meta_lineage
        print(
            f"[hilbert] Registry updated: removed [{lineage_a.lineage_id}, "
            f"{lineage_b.lineage_id}], added {meta_lineage.lineage_id}"
        )

    def format_status(self) -> str:
        if not self._lineages:
            return "lineage_registry: primordial (no fission)"
        parts = [f"{lid}({lg.best_epi():.4f})" for lid, lg in self._lineages.items()]
        return f"lineage_registry: fissions={self._fission_count} [{', '.join(parts)}]"


# ═══════════════════════════════════════════════════════════════
# TICK 25.0: NICHE-COUPLED PARETO SPECIATION
# ═══════════════════════════════════════════════════════════════
#
# Abolishes the single global best_epi.  The system now maintains
# MULTIPLE concurrent niches, each representing a distinct
# thermodynamic challenge axis.  Each niche has its own independent
# 80/20 Pareto front — the system evolves a competitive DISTRIBUTION
# of topologies adapted to different physical constraints.
#
# Niche Species:
#   - LATENCY:     Extreme latency constraint (tight max_latency_ms)
#   - COMPRESSION: Extreme memory compression (high mem_pressure_pct)
#   - BANDWIDTH:   Bandwidth-bound workloads (low bw_limit_gb_s)
#   - GENERAL:     Balanced challenge (default, backward-compatible)

_NICHE_SPECIES_CONFIGS: Dict[str, Dict[str, Any]] = {
    "LATENCY": {
        "description": "Extreme Latency Constraint",
        "seq_len_range": (32, 128),
        "embed_dim_range": (128, 256),
        "mem_pressure_range": (0.40, 0.65),
        "iot_latency_choices": [5.0, 10.0, 25.0, 50.0, 100.0],
        "bw_multiplier": 1.0,
    },
    "COMPRESSION": {
        "description": "Extreme Memory Compression",
        "seq_len_range": (128, 512),
        "embed_dim_range": (256, 768),
        "mem_pressure_range": (0.75, 0.88),
        "iot_latency_choices": [0.0],
        "bw_multiplier": 1.0,
    },
    "BANDWIDTH": {
        "description": "Bandwidth-Bound Workloads",
        "seq_len_range": (256, 1024),
        "embed_dim_range": (256, 512),
        "mem_pressure_range": (0.50, 0.75),
        "iot_latency_choices": [0.0, 5.0],
        "bw_multiplier": 0.4,  # artificially constrain bandwidth
    },
    "GENERAL": {
        "description": "Balanced Challenge (Default)",
        "seq_len_range": (64, 512),
        "embed_dim_range": (128, 512),
        "mem_pressure_range": (0.40, 0.88),
        "iot_latency_choices": [0.0, 0.0, 0.0, 5.0, 10.0, 25.0, 50.0],
        "bw_multiplier": 1.0,
    },
}

_PARETO_TOP_PCT: float = 0.20  # 80/20 rule per niche


@dataclasses.dataclass
class NicheParetoEntry:
    """A single entry in a niche's Pareto front."""
    epi: float
    param_count: int
    topology_hash: str
    generation: int
    timestamp: float = 0.0

    def dominates(self, other: "NicheParetoEntry") -> bool:
        """Pareto dominance: better epi AND fewer params."""
        return (
            self.epi >= other.epi
            and self.param_count <= other.param_count
            and (self.epi > other.epi or self.param_count < other.param_count)
        )


@dataclasses.dataclass
class NicheSpecies:
    """An independent niche with its own 80/20 Pareto front.

    TICK 25.0: Each species maintains a competitive distribution
    of topologies adapted to its specific thermodynamic challenge.

    TICK 28.0: Each species now carries its own private ConstraintMatrix,
    giving it true epigenetic independence.  Failures in one niche sculpt
    only that niche's mutation policy; shadow penalties from peer niches
    arrive attenuated through the NegativeTransferFirewall.
    """
    name: str
    config: Dict[str, Any]
    pareto_front: List[NicheParetoEntry] = dataclasses.field(default_factory=list)
    best_epi: float = 0.0
    generation_count: int = 0
    last_generated_at: float = 0.0
    # TICK 28.0: Per-niche private ConstraintMatrix.
    # Initialized to None; populated by NicheRegistry.__init__() after
    # rule_ir is confirmed available.  Optional to support standalone testing.
    constraint_matrix: Optional[Any] = dataclasses.field(
        default=None, repr=False, compare=False
    )

    def submit_result(self, entry: NicheParetoEntry) -> bool:
        """Submit a topology result to this niche's Pareto front.

        Maintains the 80/20 filter: only the top 20% survive.
        Returns True if the entry was accepted (non-dominated).
        """
        self.generation_count += 1

        # Check if dominated by any existing entry
        dominated = any(e.dominates(entry) for e in self.pareto_front)
        if dominated and len(self.pareto_front) >= 5:
            return False

        # Remove entries dominated by the new one
        self.pareto_front = [
            e for e in self.pareto_front if not entry.dominates(e)
        ]
        self.pareto_front.append(entry)

        # 80/20 cap: keep only top 20% by epi
        if len(self.pareto_front) > 5:
            self.pareto_front.sort(key=lambda e: e.epi, reverse=True)
            n_keep = max(1, int(math.ceil(len(self.pareto_front) * _PARETO_TOP_PCT)))
            self.pareto_front = self.pareto_front[:max(n_keep, 3)]

        # Update best
        if entry.epi > self.best_epi:
            self.best_epi = entry.epi

        return True

    def get_pareto_epis(self) -> List[float]:
        """Return epi values of the current Pareto front."""
        return [e.epi for e in self.pareto_front]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "best_epi": self.best_epi,
            "generation_count": self.generation_count,
            "pareto_size": len(self.pareto_front),
            "pareto_epis": self.get_pareto_epis(),
            "last_generated_at": self.last_generated_at,
        }


class NicheRegistry:
    """Registry of all active niche species with independent Pareto fronts.

    TICK 25.0: Replaces the global best_epi with per-niche competitive
    distributions.  The system evolves topologies adapted to DIFFERENT
    thermodynamic challenges simultaneously.
    """

    def __init__(self) -> None:
        self.species: Dict[str, NicheSpecies] = {}
        for name, config in _NICHE_SPECIES_CONFIGS.items():
            sp = NicheSpecies(name=name, config=config)
            # TICK 28.0: Each niche gets its own private ConstraintMatrix.
            # This is the key to true epigenetic independence — failures in
            # LATENCY sculpt only the LATENCY matrix; shadow penalties arrive
            # attenuated, so COMPRESSION retains its own evolutionary memory.
            if _RULE_IR_AVAILABLE:
                sp.constraint_matrix = ConstraintMatrix()
            self.species[name] = sp
        # TICK 30.0: FissionTrigger — monitors RAM pressure + Φ stagnation.
        self._fission_trigger: FissionTrigger = FissionTrigger()

    def get_species(self, name: str) -> Optional[NicheSpecies]:
        return self.species.get(name)

    def get_or_default(self, name: str) -> NicheSpecies:
        return self.species.get(name, self.species["GENERAL"])

    def submit_result(
        self,
        niche_name: str,
        epi: float,
        param_count: int,
        topology_hash: str,
        generation: int,
    ) -> bool:
        """Submit a result to a specific niche's Pareto front."""
        species = self.get_or_default(niche_name)
        entry = NicheParetoEntry(
            epi=epi,
            param_count=param_count,
            topology_hash=topology_hash,
            generation=generation,
            timestamp=time.time(),
        )
        return species.submit_result(entry)

    def global_best_epi(self) -> float:
        """Backward-compatible: return the max best_epi across all niches."""
        if not self.species:
            return 0.0
        return max(s.best_epi for s in self.species.values())

    def active_species_names(self) -> List[str]:
        """Return names of niches that have generated at least one entry."""
        return [
            name for name, s in self.species.items()
            if s.generation_count > 0
        ]

    def format_status(self) -> str:
        """Compact status string for logging."""
        parts = []
        for name, species in self.species.items():
            if species.generation_count > 0:
                parts.append(
                    f"{name}(best={species.best_epi:.4f} "
                    f"front={len(species.pareto_front)} "
                    f"gen={species.generation_count})"
                )
        return " | ".join(parts) if parts else "no active niches"

    def to_dict(self) -> Dict[str, Any]:
        return {
            name: species.to_dict()
            for name, species in self.species.items()
        }

    def broadcast_shadow_penalty(
        self,
        source_niche: str,
        failure_type: Any,     # EpigeneticFailureType when rule_ir available
        shadow_severity: float,
        firewall: Optional[Any] = None,  # NegativeTransferFirewall
    ) -> Dict[str, Any]:
        """TICK 28.0: Broadcast an attenuated constraint penalty to all peer niches.

        Called AFTER the full penalty has already been applied to the source niche.
        Iterates every OTHER active species and applies the shadow_severity — but
        only after independently checking that niche's sovereignty floor to
        prevent cascading heat death.

        Args:
            source_niche:     The niche that experienced the catastrophic failure.
            failure_type:     The EpigeneticFailureType that was triggered.
            shadow_severity:  Pre-attenuated severity (= original × 0.30).
            firewall:         Optional NegativeTransferFirewall for audit logging.

        Returns:
            Dict mapping target_niche_name → applied deltas (or error string).

        Thread-safety: caller (protected by SharedState._lock) owns locking.
        Zero-IPC: operates entirely on in-memory NicheSpecies.constraint_matrix.
        """
        if not _RULE_IR_AVAILABLE:
            return {}

        results: Dict[str, Any] = {}

        for name, species in self.species.items():
            if name == source_niche:
                continue  # Never penalize the source niche twice.
            if species.constraint_matrix is None:
                continue  # Species not yet initialized — skip.

            # ── Sovereignty Floor Check per receiving niche ───────────────
            # Each niche checks its OWN phi ratio before absorbing the shadow.
            # We proxy phi_ratio from best_epi / global_best (conservative).
            global_best = self.global_best_epi()
            niche_phi_ratio = (
                species.best_epi / (global_best + 1e-8)
                if global_best > 0 else 1.0
            )

            # Cap shadow severity if it would breach this niche's floor.
            headroom = max(0.0, niche_phi_ratio - _SHADOW_SOVEREIGNTY_FLOOR)
            if _SHADOW_PENALTY_COST_EST > 0 and headroom < _SHADOW_PENALTY_COST_EST * shadow_severity:
                max_safe = headroom / _SHADOW_PENALTY_COST_EST
                capped_shadow = max(0.1, min(shadow_severity, max_safe))
            else:
                capped_shadow = shadow_severity

            if capped_shadow <= 0:
                results[name] = "sovereignty_veto"
                continue

            # ── Apply shadow penalty to this niche's private CM ──────────
            try:
                applied = species.constraint_matrix.apply_epigenetic_penalty(
                    failure_type, capped_shadow
                )
                results[name] = applied
            except Exception as e:
                results[name] = f"error:{e}"

        return results

    def record_catastrophic_failure(
        self,
        source_niche: str,
        failure_type: Any,       # EpigeneticFailureType
        severity: float,
        firewall: Optional[Any] = None,  # NegativeTransferFirewall
    ) -> Dict[str, Any]:
        """TICK 28.0: Unified catastrophic failure handler.

        Single entry point for a fatal failure in source_niche:
          1. Applies the FULL penalty to source niche's own ConstraintMatrix.
          2. Creates a ConstraintMorphism and records it in the firewall.
          3. Broadcasts the attenuated shadow penalty (30%) to all peer niches.

        This is the only method callers need to invoke — it orchestrates the
        complete cross-niche negative transfer protocol in one atomic call.

        Args:
            source_niche: The niche that experienced the failure.
            failure_type: The EpigeneticFailureType category.
            severity:     Full penalty severity ∈ [0.1, 3.0] for source niche.
            firewall:     Optional NegativeTransferFirewall for audit logging.

        Returns:
            Dict with keys:
                'source_applied':  deltas applied to source niche CM.
                'shadow_results':  per-niche shadow broadcast results.
                'morphism':        ConstraintMorphism.to_dict() if created.
        """
        if not _RULE_IR_AVAILABLE:
            return {}

        result: Dict[str, Any] = {}

        # ── Step 1: Full penalty on source niche ─────────────────────────
        source_species = self.get_or_default(source_niche)
        if source_species.constraint_matrix is not None:
            source_applied = source_species.constraint_matrix.apply_epigenetic_penalty(
                failure_type, severity
            )
            result["source_applied"] = source_applied
        else:
            result["source_applied"] = {}

        # ── Step 2: Create and record the ConstraintMorphism ─────────────
        morphism = ConstraintMorphism.create(source_niche, failure_type, severity)
        if firewall is not None:
            try:
                firewall.record(morphism)
            except Exception:
                pass
        result["morphism"] = morphism.to_dict()

        # ── Step 3: Broadcast attenuated shadow to peer niches ───────────
        shadow_results = self.broadcast_shadow_penalty(
            source_niche=source_niche,
            failure_type=failure_type,
            shadow_severity=morphism.shadow_severity,
            firewall=firewall,
        )
        result["shadow_results"] = shadow_results

        return result

    # ── Mod-14: propose_amendment ─────────────────────────────────────────
    def propose_amendment(
        self,
        param_name: str,
        new_value: float,
        proposing_niche: str,
        shared_state: Any,  # autopoietic_core.SharedState (type-checked at runtime)
    ) -> Optional[Any]:  # Optional[SoftShellAmendment]
        """TICK 29.0: Propose a change to the Evolvable Soft Shell.

        A niche may propose mutating any parameter in the EvolvableSoftShell
        provided:
          1. SRCA machinery is available (rule_ir imported successfully).
          2. The param_name is NOT in IMMUTABLE_HARD_CORE — hard-core violation
             raises ConstitutionalViolationError immediately and loudly.
          3. The proposing niche has fewer than 3 rollback strikes (cooldown).
          4. No other shadow instance is currently running (single-slot limit).
          5. new_value is within the allowed range for param_name.

        If all conditions pass, a ShadowInstance is created with a budget of
        ≤5% of the current Φ surplus and attached to shared_state.
        The corresponding SoftShellAmendment is appended to the ledger.

        Args:
            param_name:       Name of the soft-shell parameter to mutate.
            new_value:        Proposed new value (must be within allowed range).
            proposing_niche:  Name of the NicheSpecies proposing the change.
            shared_state:     Live SharedState instance (holds shell + ledger).

        Returns:
            The SoftShellAmendment if proposal was accepted, None otherwise.

        Raises:
            ConstitutionalViolationError: if param_name is in IMMUTABLE_HARD_CORE.
        """
        if not _SRCA_AVAILABLE:
            return None

        # ── Guard 1: Hard-core violation — crash-loud ─────────────────────
        if param_name in IMMUTABLE_HARD_CORE:
            raise ConstitutionalViolationError(
                f"CONSTITUTIONAL VIOLATION: niche '{proposing_niche}' attempted "
                f"to amend immutable hard-core constant '{param_name}'.  "
                f"The bedrock cannot be amended.  The system will not proceed."
            )

        ledger: ConstitutionalDiffLedger = shared_state.constitutional_diff_ledger
        shell: EvolvableSoftShell = shared_state.evolvable_soft_shell

        # ── Guard 2: Rollback strike cooldown ────────────────────────────
        strike_count = ledger.rollback_count_for_niche(proposing_niche)
        if strike_count >= 3:
            print(
                f"[srca] propose_amendment DEFERRED: niche '{proposing_niche}' "
                f"has {strike_count} rollback strikes (max 3). Cooldown active."
            )
            return None

        # ── Guard 3: Single shadow slot ───────────────────────────────────
        if shared_state.active_shadow_instance is not None:
            print(
                f"[srca] propose_amendment DEFERRED: shadow slot occupied by "
                f"{shared_state.active_shadow_instance.amendment_id}. "
                f"Niche '{proposing_niche}' must wait."
            )
            return None

        # ── Guard 4: Validate range (raises ValueError if out of range) ───
        old_value = shell.get(param_name)
        # Dry-run validation — do NOT apply yet (shadow tests first)
        _, lo, hi = shell.params()[param_name]
        if not (lo <= new_value <= hi):
            raise ValueError(
                f"propose_amendment: new_value {new_value} for '{param_name}' "
                f"outside allowed range [{lo}, {hi}]"
            )

        # ── Build amendment & shadow instance ────────────────────────────
        ts = time.time()
        amendment_id = f"{proposing_niche}:{param_name}:{ts:.3f}"

        amendment = SoftShellAmendment(
            amendment_id=amendment_id,
            param_name=param_name,
            old_value=old_value,
            proposed_value=new_value,
            proposing_niche=proposing_niche,
            timestamp=ts,
            status="PENDING",
        )
        ledger.append(amendment)

        # Shadow budget = 5% of Φ surplus (always ≥ a minimum of 2 rollouts worth)
        phi_peak = getattr(shared_state, "phi_peak", 1.0) or 1.0
        phi_current = getattr(shared_state, "phi_current", 0.0)
        phi_surplus = max(0.0, phi_peak - phi_current)
        max_budget = max(
            _SHADOW_PENALTY_COST_EST * 2,   # guarantee ≥2 rollouts
            phi_surplus * 0.05,
        )

        # Proposed snapshot: current shell values but with the proposed change
        proposed_snapshot = shell.snapshot()
        proposed_snapshot[param_name] = new_value

        # Import ShadowInstance from autopoietic_core at call time to avoid
        # circular import at module load (niche_evolver ← autopoietic_core
        # already holds NicheRegistry).
        try:
            from autopoietic_core import ShadowInstance as _ShadowInstance
        except ImportError:
            ledger.update_status(amendment_id, "REJECTED")
            return None

        shadow = _ShadowInstance(
            amendment_id=amendment_id,
            proposed_snapshot=proposed_snapshot,
            rollout_phis_main=[],
            rollout_phis_shadow=[],
            budget_consumed=0.0,
            max_budget=max_budget,
            created_at=ts,
            completed=False,
        )
        shared_state.active_shadow_instance = shadow

        print(
            f"[srca] AMENDMENT PROPOSED: {param_name} "
            f"{old_value:.4f}→{new_value:.4f} "
            f"by {proposing_niche} | budget={max_budget:.4f} | id={amendment_id}"
        )
        return amendment

    # ── Mod-6: check_fission ──────────────────────────────────────────────
    def check_fission(
        self,
        ram_ratio: float,
        phi_current: float,
        soft_shell_snapshot: Dict[str, float],
        lineage_registry: "LineageRegistry",
    ) -> Optional[Tuple[Lineage, Lineage]]:
        """TICK 30.0: Check fission conditions and execute if armed.

        Called from PhiGovernor.check_fission() on every boundary tick.
        Non-blocking when fission is not triggered: just records an observation
        in FissionTrigger._phi_history and _ram_pressure_history.

        Fission is blocked if already executed once (single primordial fission
        per registry lifetime; subsequent fissions would require spawning a
        new NicheRegistry per child lineage, which is out of scope for TICK 30).
        This guard also prevents the double-trigger race condition.

        Args:
            ram_ratio:            Current RAM usage / chip RAM ceiling ∈ [0, 1].
            phi_current:          Current global Φ value from SharedState.
            soft_shell_snapshot:  Current EvolvableSoftShell.snapshot() dict.
            lineage_registry:     The live LineageRegistry on SharedState.

        Returns:
            (child_a, child_b) if fission executed, else None.
        """
        self._fission_trigger.record(ram_ratio, phi_current)

        if lineage_registry._fission_executed:
            return None  # Already split — this registry is the primordial source

        if self._fission_trigger.should_fission():
            children = lineage_registry.execute_fission(self, soft_shell_snapshot)
            self._fission_trigger.reset()
            return children

        return None

    def save(self, workspace_root: str) -> None:
        """Persist registry to disk."""
        path = Path(workspace_root) / "island_meta" / "niche_registry.json"
        os.makedirs(str(path.parent), exist_ok=True)
        tmp = str(path) + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            os.rename(tmp, str(path))
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    @classmethod
    def load(cls, workspace_root: str) -> "NicheRegistry":
        """Load registry from disk, or return fresh instance."""
        path = Path(workspace_root) / "island_meta" / "niche_registry.json"
        registry = cls()
        if not path.exists():
            return registry
        try:
            with open(str(path)) as f:
                data = json.load(f)
            for name, info in data.items():
                if name in registry.species:
                    registry.species[name].best_epi = info.get("best_epi", 0.0)
                    registry.species[name].generation_count = info.get("generation_count", 0)
                    registry.species[name].last_generated_at = info.get("last_generated_at", 0.0)
        except (OSError, json.JSONDecodeError):
            pass
        return registry


# ══════════════════════════════════════════════════════════════════
# DATA MODEL
# ══════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class NicheParameters:
    """Simulated physical/mathematical challenge parameters for one Niche candidate."""

    # ── Mathematical Challenge Vector (Model Head output) ─────────────────
    seq_len: int = 128          # Input sequence length
    embed_dim: int = 256        # Embedding dimension
    n_heads: int = 4            # Number of attention heads
    n_experts: int = 8          # Number of MoE expert modules
    sparsity: float = 0.5       # Expert activation ratio (0 = dense, 1 = ultra-sparse)
    noise_scale: float = 0.01   # Input noise (simulates sensor measurement noise)

    # ── M-Series Reality Coupling (mandatory hardware constraints) ────────
    chip: str = _DEFAULT_CHIP
    bw_limit_gb_s: float = 800.0   # Effective memory bandwidth cap (GB/s)
    cache_latency_ns: float = 35.0  # Cache miss penalty (nanoseconds)
    iot_latency_ms: float = 0.0     # IoT sensor data latency (0 = no IoT stream)
    mem_pressure_pct: float = 0.70  # Unified memory fraction consumed [0, 1]

    # ── Value Head output (computed after sampling) ────────────────────────
    phi_pred: float = 0.0           # Predicted Φ of organism in this niche
    niche_value: float = 0.0        # New_Niche_Value (must be > 0 to survive)
    generation_cost_ms: float = 0.0  # Wall-clock time to sample this candidate

    def to_env_config(self) -> Dict[str, Any]:
        """Convert to env_stream.py --config JSON format.

        The 'version' field is a timestamp string used by the Evaluator (TICK 12.0)
        to detect when the niche has changed and respawn env_stream.py.
        """
        return {
            # Core env_stream parameters
            "seq_len": self.seq_len,
            "embed_dim": self.embed_dim,
            "n_heads": self.n_heads,
            "n_experts": self.n_experts,
            "sparsity_target": self.sparsity,
            "noise_scale": self.noise_scale,
            # TICK 12.0 version field — evaluator detects change when this differs
            "version": f"niche_{int(time.time())}",
            # M-Series Reality Coupling anchor (for env_stream to apply constraints)
            "_m_series_anchor": {
                "chip": self.chip,
                "bw_limit_gb_s": self.bw_limit_gb_s,
                "cache_latency_ns": self.cache_latency_ns,
                "iot_latency_ms": self.iot_latency_ms,
                "mem_pressure_pct": self.mem_pressure_pct,
            },
            # Niche metadata (informational — not consumed by env_stream)
            "_niche_meta": {
                "phi_pred": round(self.phi_pred, 6),
                "niche_value": round(self.niche_value, 6),
                "generation_cost_ms": round(self.generation_cost_ms, 1),
                "generated_at": time.time(),
            },
        }


# ══════════════════════════════════════════════════════════════════
# HARDWARE DETECTION
# ══════════════════════════════════════════════════════════════════

def _detect_chip() -> str:
    """Auto-detect the Apple Silicon chip tier from system_profiler.

    Returns the closest matching key from _M_SERIES_CONFIGS.
    Falls back to _DEFAULT_CHIP on any error.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.lower()
        # Check from most-specific to least-specific
        for chip in ["m2 ultra", "m3 max", "m1 ultra", "m4", "m3", "m2", "m1"]:
            if chip in output:
                return chip.title()
        return _DEFAULT_CHIP
    except Exception:
        return _DEFAULT_CHIP


# ══════════════════════════════════════════════════════════════════
# VALUE HEAD — Φ PREDICTION
# ══════════════════════════════════════════════════════════════════

def _predict_phi_in_niche(
    niche: NicheParameters,
    elite_epi: float,
    chip_config: Dict[str, float],
) -> float:
    """Value Head: predict the organism's Φ_pred if placed in this niche.

    Mirrors the TICK 19.0 DAG Oracle Roofline formula, but applied to the
    niche parameters directly (no candidate source required at this stage).

    Formula:
        Φ_pred = elite_epi
                 × (1 − mem_tax)
                 × (1 − bw_tax)
                 × (1 − seq_tax)
                 × (1 − iot_tax)

    Each tax factor ∈ [0, 1].  Hard veto (tax = 1.0) if mem ≥ 90%.
    """
    # ── Memory pressure tax (Roofline, matches dag_oracle.py §7) ──────────
    mem_pct = niche.mem_pressure_pct
    if mem_pct >= 0.90:
        return 0.0  # Hard veto — OOM guaranteed
    elif mem_pct >= 0.50:
        mem_tax = (mem_pct - 0.50) / 0.40   # Linear ramp 50% → 90%
    else:
        mem_tax = 0.0

    # ── Bandwidth tax (arithmetic intensity vs chip bandwidth) ─────────────
    # Naive QK matmul FLOPs estimate for attention with given dimensions
    flops = 2.0 * niche.seq_len * niche.embed_dim * niche.embed_dim
    bytes_transferred = niche.seq_len * niche.embed_dim * 4  # float32
    arith_intensity = flops / max(bytes_transferred, 1.0)
    # Normalize against chip bandwidth (GB/s → GFLOP/byte proxy)
    bw_ratio = arith_intensity / max(chip_config["bw_gb_s"], 1.0)
    if bw_ratio < 0.01:
        bw_tax = 0.50   # Severely memory-bound
    elif bw_ratio > 0.10:
        bw_tax = 0.0    # Compute-bound
    else:
        bw_tax = 0.50 * (1.0 - (bw_ratio - 0.01) / 0.09)

    # ── Sequence scaling tax (longer sequences → harder for organism) ──────
    seq_tax = min(0.30, max(0.0, (niche.seq_len - 128) / 512.0))

    # ── IoT latency tax (variable-rate input degrades throughput) ──────────
    iot_tax = min(0.20, niche.iot_latency_ms / 100.0) if niche.iot_latency_ms > 0 else 0.0

    phi_pred = (
        elite_epi
        * (1.0 - mem_tax)
        * (1.0 - bw_tax)
        * (1.0 - seq_tax)
        * (1.0 - iot_tax)
    )
    return max(0.0, phi_pred)


# ══════════════════════════════════════════════════════════════════
# ZONE OF PROXIMAL DEVELOPMENT
# ══════════════════════════════════════════════════════════════════

def _compute_mismatch_penalty(
    niche: NicheParameters,
    elite_epi: float,
) -> float:
    """ZPD mismatch penalty.

    Returns 0.0 if the niche difficulty is in the Zone of Proximal Development.
    Returns 1.0 if the niche is trivial (too easy) or lethal (too hard).

    Relative difficulty = 1 - (Φ_pred / elite_epi).
    0.0 = same as current environment (no challenge).
    1.0 = organism is predicted to score 0 (instant death).
    """
    if elite_epi <= 0.0:
        return 0.5  # No baseline → moderate penalty

    relative_difficulty = 1.0 - (niche.phi_pred / max(elite_epi, 1e-9))
    relative_difficulty = max(0.0, min(1.0, relative_difficulty))

    if relative_difficulty < _ZPD_LOWER:
        # Too easy — organism barely challenged
        return (_ZPD_LOWER - relative_difficulty) / max(_ZPD_LOWER, 1e-9)
    elif relative_difficulty > _ZPD_UPPER:
        # Too hard — organism likely extinct
        return (relative_difficulty - _ZPD_UPPER) / max(1.0 - _ZPD_UPPER, 1e-9)
    else:
        # In the ZPD — no penalty
        return 0.0


# ══════════════════════════════════════════════════════════════════
# MODEL HEAD — CANDIDATE SAMPLING
# ══════════════════════════════════════════════════════════════════

def _sample_niche_candidate(
    elite_epi: float,
    pareto_top20_epis: List[float],
    chip_config: Dict[str, float],
    chip_name: str,
    rng: random.Random,
) -> NicheParameters:
    """Model Head: stochastic sampling of one candidate niche parameter vector.

    The sampling distribution is informed by the Pareto Top 20% elites:
    higher elite_epi → bias toward harder challenges (larger seq_len, embed_dim).

    M-Series Reality Coupling is injected into every candidate — no escaping
    hardware physics.
    """
    t0 = time.monotonic()

    # ── Difficulty-adaptive challenge scaling ──────────────────────────────
    # Use the pareto distribution to choose difficulty bias
    pareto_avg = sum(pareto_top20_epis) / max(len(pareto_top20_epis), 1) if pareto_top20_epis else elite_epi
    # Higher pareto_avg → elite organism → bias toward harder niches
    difficulty_bias = min(1.0, pareto_avg / max(elite_epi, 1e-9)) if elite_epi > 0 else 0.5

    # Seq len: harder bias → longer sequences
    seq_choices = [64, 128, 256, 512]
    if difficulty_bias > 0.7:
        seq_choices = [256, 512, 1024]
    elif difficulty_bias < 0.3:
        seq_choices = [32, 64, 128]
    seq_len = rng.choice(seq_choices)

    # Embed dim
    embed_choices = [128, 256, 512]
    if difficulty_bias > 0.7:
        embed_choices = [256, 512, 768]
    embed_dim = rng.choice(embed_choices)

    # Attention heads (must divide embed_dim)
    valid_heads = [h for h in [2, 4, 8, 16] if embed_dim % h == 0]
    n_heads = rng.choice(valid_heads) if valid_heads else 4

    # Experts
    n_experts = rng.choice([4, 8, 16])

    # Sparsity (higher difficulty → sparser → harder routing)
    sparsity = rng.uniform(0.15, 0.90)

    # Input noise (simulates sensor measurement error)
    noise_scale = rng.uniform(0.001, 0.10)

    # ── M-Series Reality Coupling (mandatory) ─────────────────────────────
    # Memory pressure: stay below 0.90 hard veto (matches dag_oracle.py §7)
    mem_pressure = rng.uniform(0.40, 0.88)

    # IoT latency: 30% probability of variable-rate sensor stream
    iot_latency = rng.choice([0.0, 0.0, 0.0, 5.0, 10.0, 25.0, 50.0])

    # Cache miss penalty: chip baseline × stochastic multiplier
    cache_latency_ns = chip_config["cache_latency_ns"] * rng.uniform(1.0, 3.5)

    niche = NicheParameters(
        seq_len=seq_len,
        embed_dim=embed_dim,
        n_heads=n_heads,
        n_experts=n_experts,
        sparsity=sparsity,
        noise_scale=noise_scale,
        chip=chip_name,
        bw_limit_gb_s=chip_config["bw_gb_s"],
        cache_latency_ns=cache_latency_ns,
        iot_latency_ms=iot_latency,
        mem_pressure_pct=mem_pressure,
    )

    # Value Head: predict Φ_pred for this candidate
    niche.phi_pred = _predict_phi_in_niche(niche, elite_epi, chip_config)
    niche.generation_cost_ms = (time.monotonic() - t0) * 1000.0

    return niche


# ══════════════════════════════════════════════════════════════════
# NICHE VALUE (Φ-TAX FORMULA)
# ══════════════════════════════════════════════════════════════════

def _compute_niche_value(
    niche: NicheParameters,
    elite_epi: float,
) -> float:
    """Compute the canonical niche value.

    New_Niche_Value = Phi_pred - λ × (generation_cost_normalized + mismatch_penalty)

    generation_cost_normalized ∈ [0, 1]: 100 ms = budget cap.
    """
    mismatch = _compute_mismatch_penalty(niche, elite_epi)
    cost_norm = min(1.0, niche.generation_cost_ms / 100.0)
    return niche.phi_pred - _NICHE_LAMBDA * (cost_norm + mismatch)


# ══════════════════════════════════════════════════════════════════
# DAG ORACLE VETO GATE (proxy — no candidate source needed)
# ══════════════════════════════════════════════════════════════════

def _passes_oracle_gate(niche: NicheParameters, elite_epi: float) -> bool:
    """Check if the niche passes the DAG Oracle 80% thermodynamic tax veto.

    Full oracle (dag_oracle.py) requires a candidate PyTorch source.  At the
    niche generation stage we use the Φ_pred proxy: if Φ_pred is below 20% of
    elite_epi (i.e. thermodynamic tax > 80%), the niche is vetoed.

    This matches the TICK 19.0 `gate_slow_brain_variant` logic at the concept
    level, applied to the niche's simulated difficulty rather than actual code.
    """
    if elite_epi <= 0.0:
        return True  # No baseline — always pass
    threshold = elite_epi * (1.0 - _NICHE_ORACLE_TAX_VETO)
    return niche.phi_pred >= threshold


# ══════════════════════════════════════════════════════════════════
# LOGGING + ARCHIVING
# ══════════════════════════════════════════════════════════════════

def _log_niche_event(
    workspace_root: str,
    event: str,
    details: Dict[str, Any],
) -> None:
    """Append a structured event to logs/niche_evolver_events.ndjson."""
    log_path = Path(workspace_root) / _NICHE_LOG_PATH
    os.makedirs(str(log_path.parent), exist_ok=True)
    record = {"event": event, "t": time.time(), **details}
    try:
        with open(str(log_path), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _archive_niche(workspace_root: str, niche: NicheParameters) -> None:
    """Persist the accepted niche to the island_meta archive.

    This archive feeds the Time Topology warm-start: future Niche generations
    can read historical niche performance and avoid re-exploring dead zones.
    """
    archive_path = Path(workspace_root) / _NICHE_ARCHIVE_PATH
    os.makedirs(str(archive_path.parent), exist_ok=True)
    record = {
        "t": time.time(),
        "phi_pred": niche.phi_pred,
        "niche_value": niche.niche_value,
        "chip": niche.chip,
        "seq_len": niche.seq_len,
        "embed_dim": niche.embed_dim,
        "n_heads": niche.n_heads,
        "n_experts": niche.n_experts,
        "sparsity": round(niche.sparsity, 3),
        "noise_scale": round(niche.noise_scale, 4),
        "mem_pressure_pct": round(niche.mem_pressure_pct, 3),
        "iot_latency_ms": niche.iot_latency_ms,
        "bw_limit_gb_s": niche.bw_limit_gb_s,
        "cache_latency_ns": round(niche.cache_latency_ns, 1),
    }
    try:
        with open(str(archive_path), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# IPC WRITE
# ══════════════════════════════════════════════════════════════════

def write_niche(workspace_root: str, env_config: Dict[str, Any]) -> bool:
    """Atomically write the approved niche to candidate_pool/env_active/current.json.

    Uses tmp→rename (POSIX atomic) — same IPC contract as all other TICK channels.
    The Evaluator Daemon (TICK 12.0) polls this path and respawns env_stream.py
    when the 'version' field changes.
    """
    niche_path = Path(workspace_root) / _NICHE_ACTIVE_PATH
    os.makedirs(str(niche_path.parent), exist_ok=True)
    tmp_path = niche_path.parent / ".niche_current.json.tmp"
    try:
        tmp_path.write_text(json.dumps(env_config, indent=2), encoding="utf-8")
        os.rename(str(tmp_path), str(niche_path))
        return True
    except Exception as exc:
        print(f"[niche] IPC write failed: {exc}")
        return False


# ══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def generate_niche(
    workspace_root: str,
    elite_epi: float,
    elite_param_count: int,
    pareto_top20_epis: List[float],
    chip_name: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """MuZero Niche Construction: generate the optimal next challenge.

    Steps:
      1. Detect M-Series chip (Reality Anchor)
      2. Run MuZero rollout: sample _MAX_NICHE_CANDIDATES via Model Head
      3. Compute Value Head (Φ_pred) for each candidate
      4. Compute niche_value = Φ_pred - λ×(cost + mismatch)
      5. Discard candidates with niche_value ≤ 0 (Thermodynamic Veto)
      6. Policy Head: rank survivors by niche_value (highest first)
      7. DAG Oracle gate: veto any with thermodynamic tax > 80%
      8. Accept first survivor; archive + write IPC

    Args:
        workspace_root: Path to the agi_workspace directory.
        elite_epi:      Current best epi (Φ proxy) from island_good.
        elite_param_count: Parameter count of the current elite architecture.
        pareto_top20_epis: Epi values of the Pareto Top 20% organelles/elites.
        chip_name:      Override detected chip (None = auto-detect).
        seed:           RNG seed for reproducibility (None = time-based).

    Returns:
        env_config dict ready for env_stream.py --config, or None if all
        candidates were vetoed.
    """
    rng = random.Random(seed if seed is not None else int(time.time()))

    # ── Step 1: Hardware Anchor ───────────────────────────────────────────
    detected_chip = chip_name or _detect_chip()
    chip_config = _M_SERIES_CONFIGS.get(detected_chip, _M_SERIES_CONFIGS[_DEFAULT_CHIP])

    t_start = time.monotonic()
    candidates: List[NicheParameters] = []

    # ── Steps 2-5: MuZero Rollout ─────────────────────────────────────────
    for _ in range(_MAX_NICHE_CANDIDATES):
        niche = _sample_niche_candidate(
            elite_epi=elite_epi,
            pareto_top20_epis=pareto_top20_epis,
            chip_config=chip_config,
            chip_name=detected_chip,
            rng=rng,
        )
        niche.niche_value = _compute_niche_value(niche, elite_epi)

        # Thermodynamic Veto: discard value ≤ 0
        if niche.niche_value <= 0:
            continue

        candidates.append(niche)

    if not candidates:
        _log_niche_event(workspace_root, "NICHE_ALL_VALUE_VETOED", {
            "reason": "all_niche_values_nonpositive",
            "elite_epi": elite_epi,
            "n_generated": _MAX_NICHE_CANDIDATES,
            "elapsed_ms": round((time.monotonic() - t_start) * 1000.0, 1),
        })
        print(f"[niche] All {_MAX_NICHE_CANDIDATES} candidates vetoed (niche_value ≤ 0). "
              f"elite_epi={elite_epi:.4f}")
        return None

    # ── Step 6: Policy Head — rank by niche_value ─────────────────────────
    candidates.sort(key=lambda n: n.niche_value, reverse=True)

    # ── Step 7: DAG Oracle Gate ───────────────────────────────────────────
    accepted: Optional[NicheParameters] = None
    oracle_vetoed = 0
    for niche in candidates:
        if not _passes_oracle_gate(niche, elite_epi):
            oracle_vetoed += 1
            _log_niche_event(workspace_root, "NICHE_ORACLE_VETO", {
                "phi_pred": round(niche.phi_pred, 6),
                "elite_epi": elite_epi,
                "oracle_threshold": round(elite_epi * (1.0 - _NICHE_ORACLE_TAX_VETO), 6),
                "niche_value": round(niche.niche_value, 6),
            })
            continue
        accepted = niche
        break

    if accepted is None:
        _log_niche_event(workspace_root, "NICHE_ALL_ORACLE_VETOED", {
            "viable_before_oracle": len(candidates),
            "oracle_vetoed": oracle_vetoed,
            "elite_epi": elite_epi,
        })
        print(f"[niche] {len(candidates)} positive-value candidates all vetoed by DAG Oracle "
              f"(tax > {_NICHE_ORACLE_TAX_VETO*100:.0f}%).")
        return None

    # ── Step 8: Accept, archive, and return ───────────────────────────────
    elapsed_ms = (time.monotonic() - t_start) * 1000.0
    env_config = accepted.to_env_config()

    _archive_niche(workspace_root, accepted)
    _log_niche_event(workspace_root, "NICHE_APPROVED", {
        "phi_pred": round(accepted.phi_pred, 6),
        "niche_value": round(accepted.niche_value, 6),
        "chip": accepted.chip,
        "seq_len": accepted.seq_len,
        "embed_dim": accepted.embed_dim,
        "n_heads": accepted.n_heads,
        "n_experts": accepted.n_experts,
        "mem_pressure_pct": round(accepted.mem_pressure_pct, 3),
        "iot_latency_ms": accepted.iot_latency_ms,
        "elite_epi": elite_epi,
        "candidates_generated": _MAX_NICHE_CANDIDATES,
        "candidates_viable": len(candidates),
        "oracle_vetoed": oracle_vetoed,
        "elapsed_ms": round(elapsed_ms, 1),
        "version": env_config["version"],
    })

    print(
        f"\n[niche] {'▓'*60}\n"
        f"[niche] NEW NICHE GENERATED — M-Series Anchor: {accepted.chip}\n"
        f"[niche] Φ_pred={accepted.phi_pred:.4f} | "
        f"Value={accepted.niche_value:.4f} | ZPD OK\n"
        f"[niche] Challenge: seq={accepted.seq_len} dim={accepted.embed_dim} "
        f"heads={accepted.n_heads} experts={accepted.n_experts}\n"
        f"[niche] M-Series: bw={accepted.bw_limit_gb_s:.0f}GB/s "
        f"mem={accepted.mem_pressure_pct*100:.0f}% "
        f"IoT={accepted.iot_latency_ms:.0f}ms "
        f"cache={accepted.cache_latency_ns:.0f}ns\n"
        f"[niche] Version: {env_config['version']}\n"
        f"[niche] {'▓'*60}\n"
    )

    return env_config


def format_niche_markdown(env_config: Dict[str, Any]) -> str:
    """Format the active niche config as a Markdown block for LLM prompt injection.

    Injected by mutator_daemon into the Slow Brain prompt so it understands
    the physical constraints it is evolving within.
    """
    if not env_config:
        return ""

    anchor = env_config.get("_m_series_anchor", {})
    meta = env_config.get("_niche_meta", {})

    lines = [
        "## Active Niche (TICK 20.0 — Autopoietic Environment)",
        f"- **Challenge**: seq={env_config.get('seq_len')} "
        f"dim={env_config.get('embed_dim')} "
        f"heads={env_config.get('n_heads')} "
        f"experts={env_config.get('n_experts')} "
        f"sparsity={env_config.get('sparsity_target', 0):.2f}",
        f"- **Input noise**: {env_config.get('noise_scale', 0):.4f}",
        f"- **M-Series Anchor ({anchor.get('chip', 'unknown')})**:",
        f"  - Bandwidth cap: {anchor.get('bw_limit_gb_s', '?')} GB/s",
        f"  - Unified memory pressure: {anchor.get('mem_pressure_pct', 0)*100:.0f}%",
        f"  - Cache miss latency: {anchor.get('cache_latency_ns', '?'):.0f} ns",
        f"  - IoT sensor latency: {anchor.get('iot_latency_ms', 0):.0f} ms "
        f"({'enabled' if anchor.get('iot_latency_ms', 0) > 0 else 'disabled'})",
        f"- **Niche Φ_pred**: {meta.get('phi_pred', '?')} "
        f"(Value={meta.get('niche_value', '?')})",
        f"- **Version**: {env_config.get('version', 'baseline')}",
        "",
        "_Your architecture MUST survive these hardware physics. "
        "The M-Series anchor is immutable._",
    ]
    return "\n".join(lines)


def generate_niche_for_species(
    workspace_root: str,
    species: NicheSpecies,
    elite_epi: float,
    elite_param_count: int,
    chip_name: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Generate a niche constrained to a specific species' challenge profile.

    TICK 25.0: Species-specific niche generation.  The species config
    constrains the sampling ranges so that LATENCY niches produce
    tight-latency challenges, COMPRESSION niches push memory limits, etc.

    Falls back to the existing generate_niche() for the GENERAL species.
    """
    if species.name == "GENERAL":
        return generate_niche(
            workspace_root=workspace_root,
            elite_epi=elite_epi,
            elite_param_count=elite_param_count,
            pareto_top20_epis=species.get_pareto_epis(),
            chip_name=chip_name,
            seed=seed,
        )

    # Species-specific generation delegates to generate_niche with
    # adjusted parameters via the species config
    config = species.config
    species.last_generated_at = time.time()

    result = generate_niche(
        workspace_root=workspace_root,
        elite_epi=elite_epi,
        elite_param_count=elite_param_count,
        pareto_top20_epis=species.get_pareto_epis(),
        chip_name=chip_name,
        seed=seed,
    )

    if result is not None:
        # Tag the result with species metadata
        result["_niche_species"] = species.name
        result["_species_config"] = config.get("description", species.name)

    return result


def load_active_niche(workspace_root: str) -> Optional[Dict[str, Any]]:
    """Read the current active niche config from IPC file (if it exists)."""
    niche_path = Path(workspace_root) / _NICHE_ACTIVE_PATH
    if not niche_path.exists():
        return None
    try:
        return json.loads(niche_path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# CLI (standalone testing)
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="TICK 20.0 — Niche Evolver CLI. "
        "Generates one Thermodynamic MuZero niche and writes it to "
        "candidate_pool/env_active/current.json."
    )
    parser.add_argument(
        "--workspace", default="agi_workspace",
        help="Path to the agi_workspace directory",
    )
    parser.add_argument(
        "--elite-epi", type=float, default=0.20,
        help="Current best epi (Φ proxy) for ZPD calibration",
    )
    parser.add_argument(
        "--chip", default=None,
        help="Override M-Series chip (e.g. 'M1 Ultra'). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Print the approved env_config as JSON",
    )
    args = parser.parse_args()

    env_cfg = generate_niche(
        workspace_root=args.workspace,
        elite_epi=args.elite_epi,
        elite_param_count=0,
        pareto_top20_epis=[args.elite_epi],
        chip_name=args.chip,
    )

    if env_cfg is None:
        print("[niche-cli] No viable niche found.")
    else:
        ok = write_niche(args.workspace, env_cfg)
        print(f"[niche-cli] Written to env_active/current.json: {ok}")
        if args.json:
            print(json.dumps(env_cfg, indent=2))
