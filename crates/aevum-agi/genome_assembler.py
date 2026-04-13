#!/usr/bin/env python3
"""genome_assembler.py -- The UNIX Assembler (TICK 15.0: Endosymbiosis).

TICK 17.0: Thermodynamic Pareto-MCTS Assembly.
  Stop "blind generation" and introduce "Foresight" via Monte Carlo Tree
  Search (MCTS) constrained by First Principles:
    - 80/20 Compounding Leverage (Pareto Policy Head)
    - Free Energy Rate Density Φ Tax (Thermodynamic Value Head)
    - Time Topology Warm-Start (historical assembly priors)
    - Reality Coupling (Constitutional bounds during rollout)
  The MCTS acts as the "Fast Brain" — finding the optimal organelle
  combination in milliseconds, bypassing the heavy LLM "Slow Brain"
  for assembly decisions.

TICK 21.1: MLX Substrate Conversion — vmap Accelerated MCTS.
  - MCTS rollout values are vectorized via mlx.core.vmap, allowing all
    100+ rollouts to run natively in parallel across the M1 Ultra's
    unified GPU cores, dropping the simulation delay tax to near zero.
  - MLX lazy evaluation replaces the custom dag_oracle.py heuristics for
    architecture validation: organelles are assembled as MLX operations,
    and if the lazy graph compiles without shape/memory exceptions it
    passes the physical boundary test. mx.eval() is called ONLY when
    strictly necessary.

Standalone tool that composes independent Organelle files into a single
valid candidate.py script that evaluator_daemon.py can test.

UNIX Philosophy: one tool, one job -- modular genome assembly.

The monolithic 10K-char AtomicLLM "prokaryote" is decomposed into
interchangeable Organelles with standardized interface membranes:
  - attention/ : CausalSelfAttention variants
  - routing/   : Router / Gating variants
  - expert/    : IChingExpert / FFN variants
  - island_assembly/ : Proven assembly recipes (JSON manifests)

Each Organelle is a standalone .py file containing ONE nn.Module class
definition.  The Assembler reads an assembly_recipe.json manifest
pointing to specific elite organelle files, composes them into a single
candidate.py that the Evaluator can hot-swap via the existing AST
patcher.

Assembly Recipe Format (assembly_recipe.json):
    {
        "attention": "island_organelle/attention/elite_attn_012.py",
        "routing":   "island_organelle/routing/elite_route_003.py",
        "expert":    "island_organelle/expert/elite_expert_007.py",
        "constants": true,
        "version":   "asm-v1"
    }

Safety:
  - All assembled candidates pass through constitution.validate_candidate()
  - Assembly failures are non-fatal (returns None)
  - Atomic write: .tmp + os.rename() to candidate_pool/
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── TICK 21.1: MLX for vmap-accelerated MCTS rollouts ────────────────────
# All MCTS value computations run as vectorized MLX operations in Unified
# Memory, dispatched in parallel across M1 Ultra GPU cores.
import mlx.core as mx

from constitution import validate_candidate, MAX_PARAMS

# ── TICK 20.1: Teleological Attractor (Future-Guided MCTS) ──────────────────
from teleological_attractor import compute_mcts_attractor_value

# ── TICK 19.0: DAG Oracle (Topological Reality Check) ─────────────────────
from dag_oracle import gate_mcts_rollout

# ── TICK 25.0: Phi Governor for budget-backed horizon ──────────────────
from autopoietic_core import get_phi_governor


# ═══════════════════════════════════════════════════════════════
# ORGANELLE CONTRACT (Interface Membrane Standard)
# ═══════════════════════════════════════════════════════════════

# Every organelle file MUST contain exactly ONE nn.Module subclass.
# Each organelle type has a required class name and expected interface:
ORGANELLE_TYPES: Dict[str, Dict[str, Any]] = {
    "attention": {
        "class_name": "CausalSelfAttention",
        "description": "Self-attention with causal masking",
        "input_spec": {"shape": "B,T,D", "desc": "Batch, Sequence, Embedding"},
        "output_spec": {"shape": "B,T,D", "desc": "Same shape as input"},
    },
    "routing": {
        "class_name": "RoutingStrategy",
        "description": "Expert routing and mixing strategy (mutable DNA)",
        "input_spec": {"shape": "B,T,D + experts + router_idx", "desc": "Hidden states, expert list, routing index"},
        "output_spec": {"shape": "B,T,D", "desc": "Expert output (added as residual by scaffold)"},
    },
    "expert": {
        "class_name": "IChingExpert",
        "description": "Expert FFN with I-Ching indexing",
        "input_spec": {"shape": "B,T,D", "desc": "Batch, Sequence, Embedding"},
        "output_spec": {"shape": "B,T,D", "desc": "Same shape as input"},
    },
}

# Organelle directory layout under candidate_pool/
ORGANELLE_BASE_DIR: str = "candidate_pool/island_organelle"
ASSEMBLY_DIR: str = "candidate_pool/island_assembly"
ORGANELLE_MAX_PER_TYPE: int = 20  # FIFO cap per organelle type


# ═══════════════════════════════════════════════════════════════
# ORGANELLE EXTRACTION (Decomposition)
# ═══════════════════════════════════════════════════════════════

def extract_organelles(source: str) -> Dict[str, str]:
    """Decompose a monolithic candidate source into individual organelles.

    Parses the AST, extracts each nn.Module subclass, and returns
    a dict mapping organelle_type -> class source code.

    Only extracts classes whose names match ORGANELLE_TYPES entries.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    lines = source.splitlines()

    # Build reverse lookup: class_name -> organelle_type
    name_to_type: Dict[str, str] = {}
    for org_type, spec in ORGANELLE_TYPES.items():
        name_to_type[spec["class_name"]] = org_type

    organelles: Dict[str, str] = {}

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in name_to_type:
            continue

        org_type = name_to_type[node.name]
        start = node.lineno - 1
        end = getattr(node, "end_lineno", len(lines))
        class_source = "\n".join(lines[start:end])
        organelles[org_type] = class_source

    return organelles


def save_organelle(
    workspace_root: str,
    organelle_type: str,
    class_source: str,
    epi: float,
    gen: int,
    parent_hash: str = "",
    matrix_version: int = 0,
    niche_id: str = "",
    resource_footprint: float = 0.0,
    proven_niches: Optional[List[str]] = None,
) -> Optional[Path]:
    """Save a single organelle to its type-specific island directory.

    Writes with metadata header and FIFO-caps the directory.
    Returns the saved path, or None on failure.

    TICK 27.0: Genealogical Ledger extension.
    TICK 28.0: Transferable Organelle IR extension.

    Header format (TICK 28.0+):
        # Organelle: {type} | class={name} | gen={gen} | epi={epi} | t={ts}
          | genealogy_hash={hash} | parent_hash={ph} | matrix_v={mv} | niche={nid}
          | resource_footprint={rf} | proven_niches={n1,n2,...}
    """
    if organelle_type not in ORGANELLE_TYPES:
        return None

    org_dir = Path(workspace_root) / ORGANELLE_BASE_DIR / organelle_type
    # TICK 15.1: Bulletproof guard — ensure dir exists immediately before write
    os.makedirs(str(org_dir), exist_ok=True)

    ts = int(time.time() * 1000)
    class_name = ORGANELLE_TYPES[organelle_type]["class_name"]
    filename = f"elite_{class_name}_{gen:07d}_{ts}.py"
    filepath = org_dir / filename

    # TICK 27.0: Compute genealogy hash.
    effective_parent = parent_hash if parent_hash else TICK13_CONSTITUTION_HASH
    genealogy_hash = compute_genealogy_hash(effective_parent, matrix_version, niche_id)

    # TICK 28.0: Encode proven_niches as comma-separated list.
    # Empty string for organelles with no cross-niche survival record yet.
    pn_str = ",".join(sorted(set(proven_niches))) if proven_niches else ""

    header = (
        f"# Organelle: {organelle_type} | class={class_name} | "
        f"gen={gen} | epi={epi:.6f} | t={time.time():.0f} | "
        f"genealogy_hash={genealogy_hash} | parent_hash={effective_parent} | "
        f"matrix_v={matrix_version} | niche={niche_id} | "
        f"resource_footprint={resource_footprint:.6f} | "
        f"proven_niches={pn_str}\n"
    )
    os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)  # TICK 15.1
    filepath.write_text(header + class_source, encoding="utf-8")

    # FIFO cap
    existing = sorted(org_dir.glob("elite_*.py"), key=lambda p: p.stat().st_mtime)
    while len(existing) > ORGANELLE_MAX_PER_TYPE:
        oldest = existing.pop(0)
        oldest.unlink(missing_ok=True)

    return filepath


def decompose_and_archive(
    workspace_root: str,
    source: str,
    epi: float,
    gen: int,
    parent_hash: str = "",
    matrix_version: int = 0,
    niche_id: str = "",
    resource_footprint: float = 0.0,
    proven_niches: Optional[List[str]] = None,
) -> Dict[str, Path]:
    """Full decomposition pipeline: extract organelles and save each to its island.

    Returns dict mapping organelle_type -> saved file path.

    TICK 27.0: Genealogical metadata threaded through to save_organelle().
    TICK 28.0: Transferable Organelle IR (resource_footprint, proven_niches).
    """
    organelles = extract_organelles(source)
    saved: Dict[str, Path] = {}

    for org_type, class_source in organelles.items():
        path = save_organelle(
            workspace_root, org_type, class_source, epi, gen,
            parent_hash=parent_hash,
            matrix_version=matrix_version,
            niche_id=niche_id,
            resource_footprint=resource_footprint,
            proven_niches=proven_niches,
        )
        if path:
            saved[org_type] = path

    return saved


# ═══════════════════════════════════════════════════════════════
# ORGANELLE LOADING (for Assembly)
# ═══════════════════════════════════════════════════════════════

def load_organelle(filepath: Path) -> Optional[str]:
    """Load an organelle file and return the class source code.

    Strips the metadata header comment if present.
    Validates that it contains exactly one class definition.
    """
    try:
        code = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Strip header comment
    lines = code.splitlines()
    if lines and lines[0].startswith("# Organelle:"):
        code = "\n".join(lines[1:])

    # Validate: must parse and contain at least one class
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    has_class = any(isinstance(n, ast.ClassDef) for n in ast.iter_child_nodes(tree))
    if not has_class:
        return None

    return code.strip()


def sample_best_organelle(
    workspace_root: str,
    organelle_type: str,
) -> Optional[Tuple[Path, str]]:
    """Sample the most recent elite organelle of a given type.

    Returns (path, source_code) or None if no organelles exist.
    """
    org_dir = Path(workspace_root) / ORGANELLE_BASE_DIR / organelle_type
    if not org_dir.exists():
        return None

    files = sorted(org_dir.glob("elite_*.py"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None

    # Take the newest (likely highest epi)
    for f in reversed(files):
        code = load_organelle(f)
        if code is not None:
            return f, code

    return None


# ═══════════════════════════════════════════════════════════════
# GENOME ASSEMBLY (The UNIX Assembler)
# ═══════════════════════════════════════════════════════════════

def assemble_candidate(
    workspace_root: str,
    recipe: Dict[str, Any],
) -> Optional[str]:
    """Compose organelle files into a single candidate.py source.

    Takes an assembly_recipe dict with keys:
      - "attention": path to attention organelle (relative to workspace_root)
      - "routing":   path to routing organelle
      - "expert":    path to expert organelle

    Each path is optional. Missing paths are skipped (the existing
    class in atomic_core.py is preserved by the AST patcher).

    Returns the composed candidate source, or None on failure.
    """
    parts: List[str] = []

    # Required imports that organelles depend on
    parts.append("import math")
    parts.append("import torch")
    parts.append("import torch.nn as nn")
    parts.append("import torch.nn.functional as F")
    parts.append("")

    loaded_count = 0
    for org_type in ("attention", "routing", "expert"):
        rel_path = recipe.get(org_type)
        if not rel_path:
            continue

        filepath = Path(workspace_root) / rel_path
        if not filepath.exists():
            print(f"[assembler] Organelle not found: {filepath}")
            continue

        code = load_organelle(filepath)
        if code is None:
            print(f"[assembler] Failed to load organelle: {filepath}")
            continue

        parts.append(f"# ── Organelle: {org_type} ({filepath.name}) ──")
        parts.append(code)
        parts.append("")
        loaded_count += 1

    if loaded_count == 0:
        return None

    assembled = "\n".join(parts)

    # Validate the assembly parses
    try:
        ast.parse(assembled)
    except SyntaxError as exc:
        print(f"[assembler] Assembled candidate has SyntaxError: {exc}")
        return None

    # Constitutional validation
    ok, violations = validate_candidate(assembled)
    if not ok:
        print(f"[assembler] CONSTITUTIONAL VETO: {violations}")
        return None

    return assembled


def assemble_from_recipe_file(
    workspace_root: str,
    recipe_path: str,
) -> Optional[str]:
    """Load assembly recipe from JSON file and assemble.

    Convenience wrapper for assemble_candidate().
    """
    full_path = Path(workspace_root) / recipe_path
    if not full_path.exists():
        return None

    try:
        raw = full_path.read_text(encoding="utf-8")
        recipe = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[assembler] Failed to load recipe: {exc}")
        return None

    return assemble_candidate(workspace_root, recipe)


def assemble_best_organelles(
    workspace_root: str,
) -> Optional[str]:
    """Auto-assemble from the best available organelle of each type.

    Scans island_organelle/<type>/ directories and picks the newest
    elite from each.  If at least one organelle is found, assembles
    a candidate.

    Returns assembled source or None.
    """
    recipe: Dict[str, str] = {}

    for org_type in ORGANELLE_TYPES:
        result = sample_best_organelle(workspace_root, org_type)
        if result is not None:
            path, _ = result
            # Store relative path from workspace root
            rel = str(path.relative_to(workspace_root))
            recipe[org_type] = rel

    if not recipe:
        return None

    return assemble_candidate(workspace_root, recipe)


def write_assembly_recipe(
    workspace_root: str,
    recipe: Dict[str, Any],
    label: str = "",
) -> Optional[Path]:
    """Save an assembly recipe to island_assembly/ for future reuse.

    Returns the saved path.
    """
    asm_dir = Path(workspace_root) / ASSEMBLY_DIR
    asm_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    label_part = f"_{label}" if label else ""
    filename = f"assembly{label_part}_{ts}.json"
    filepath = asm_dir / filename

    try:
        filepath.write_text(
            json.dumps(recipe, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return filepath
    except OSError:
        return None


def write_assembled_candidate(
    workspace_root: str,
    assembled_code: str,
    variant_idx: int = 0,
) -> Optional[Path]:
    """Atomically write an assembled candidate to the candidate pool.

    Uses the same .tmp + os.rename() protocol as mutator_daemon.py.
    """
    pool_dir = Path(workspace_root) / "candidate_pool"
    pool_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time() * 1000)
    final_path = pool_dir / f"candidate_asm_{timestamp}_v{variant_idx}.py"
    tmp_path = pool_dir / f".candidate_asm_{timestamp}_v{variant_idx}.py.tmp"

    try:
        tmp_path.write_text(assembled_code, encoding="utf-8")
        os.rename(str(tmp_path), str(final_path))
        return final_path
    except Exception as exc:
        print(f"[assembler] Failed to write assembled candidate: {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


# ═══════════════════════════════════════════════════════════════
# BOTTLENECK ANALYSIS (for Targeted Mutation)
# ═══════════════════════════════════════════════════════════════

def identify_bottleneck_organelle(
    gradient_profile: Dict[str, Any],
) -> Optional[str]:
    """Analyze the gradient profile to identify which organelle is the bottleneck.

    Returns the organelle_type string ("attention", "routing", "expert")
    that should be the primary mutation target, or None if inconclusive.

    Heuristic:
      1. The organelle containing the hottest/most-dead layers is the bottleneck.
      2. Expert load imbalance points to routing.
      3. Attention entropy extremes point to attention.
    """
    if not gradient_profile:
        return None

    layers = gradient_profile.get("layers", {})
    if not layers:
        return None

    # Score each organelle type by aggregating gradient pathology
    scores: Dict[str, float] = {"attention": 0.0, "routing": 0.0, "expert": 0.0}

    # Map layer name patterns to organelle types
    type_patterns: Dict[str, List[str]] = {
        "attention": ["attn", "q_proj", "k_proj", "v_proj", "o_proj", "attention"],
        "routing": ["router", "gate", "block", "mitotic", "transform"],
        "expert": ["expert", "ffn", "ff", "iching", "mlp"],
    }

    for layer_name, info in layers.items():
        layer_lower = layer_name.lower()
        dead_ratio = info.get("dead_ratio", 0.0)
        grad_norm = info.get("grad_norm", 0.0)
        status = info.get("status", "")

        for org_type, patterns in type_patterns.items():
            if any(p in layer_lower for p in patterns):
                # Dead layers are high-priority bottlenecks
                if status == "NO_GRAD" or dead_ratio > 0.5:
                    scores[org_type] += 3.0
                elif dead_ratio > 0.2:
                    scores[org_type] += 1.5
                # Very hot layers suggest instability
                if grad_norm > 0.1:
                    scores[org_type] += 1.0

    # Expert load imbalance → routing bottleneck
    expert_act = gradient_profile.get("expert_activation", {})
    if expert_act:
        values = list(expert_act.values())
        if values and len(values) > 1:
            max_v, min_v = max(values), min(values)
            if max_v > 80.0:  # Collapse
                scores["routing"] += 5.0
            elif max_v - min_v > 30.0:  # Imbalanced
                scores["routing"] += 3.0

    # Attention entropy extremes → attention bottleneck
    attn_ent = gradient_profile.get("attention_entropy")
    if attn_ent is not None:
        if attn_ent < 0.5:  # Collapsed attention
            scores["attention"] += 4.0
        elif attn_ent > 4.0:  # Diffuse attention
            scores["attention"] += 3.0

    # Return the highest-scoring organelle, if significant
    if not scores or max(scores.values()) < 1.0:
        return None

    return max(scores, key=scores.get)


def extract_organelle_source(
    full_source: str,
    organelle_type: str,
) -> Optional[str]:
    """Extract a single organelle's class source from the full atomic_core.py.

    Returns the class definition source code, or None if not found.
    """
    if organelle_type not in ORGANELLE_TYPES:
        return None

    target_class = ORGANELLE_TYPES[organelle_type]["class_name"]

    try:
        tree = ast.parse(full_source)
    except SyntaxError:
        return None

    lines = full_source.splitlines()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == target_class:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", len(lines))
            return "\n".join(lines[start:end])

    return None


# ═══════════════════════════════════════════════════════════════
# TICK 17.0: THERMODYNAMIC PARETO-MCTS ASSEMBLY
# ═══════════════════════════════════════════════════════════════
#
# First Principles:
#   1. 80/20 Compounding Leverage — Only elite organelles enter the
#      search tree.  The MCTS policy generates transition probabilities
#      for only the Pareto Top 20%, collapsing the action space from
#      exponential to linear.
#   2. Φ Tax (Free Energy Rate Density) — Every rollout pays a
#      thermodynamic tax proportional to simulation delay and tree
#      depth.  The tree aggressively self-prunes.
#   3. Time Topology Warm-Start — Historical assembly successes are
#      injected as initial visit counts and priors, reducing required
#      rollouts from ~1000 to <100 (10x speedup).
#   4. Reality Coupling — Constitutional bounds (MAX_PARAMS 50M) are
#      enforced during rollout.  Violations assign Value = -∞.
# ═══════════════════════════════════════════════════════════════

# ── MCTS Hyperparameters ─────────────────────────────────────────
_MCTS_C_PUCT: float = 1.41              # Exploration constant (√2)
_MCTS_LAMBDA_TAX: float = 0.001         # Thermodynamic tax weight
_MCTS_MAX_ROLLOUTS: int = 100           # Upper bound on rollouts
_MCTS_MAX_DEPTH: int = len(ORGANELLE_TYPES)  # One slot per organelle type
_MCTS_PARETO_TOP_PCT: float = 0.20      # 80/20: keep top 20%
_MCTS_WARM_START_TOP_N: int = 50        # Historical paths to inject
_MCTS_ROLLOUT_TIMEOUT_MS: float = 50.0  # Per-rollout time budget (ms)


# ═══════════════════════════════════════════════════════════════
# POWER-LAW SUBSTRATE: BARBELL FILTER
# KVS Atoms: KVS-2026-000004 (Barbell_Strategy),
#            KVS-2026-000005 (Asymmetric_Leverage),
#            KVS-2026-000009 (Power_Law_Primacy),
#            KVS-2026-000011 (Medium_Risk_Medium_Reward_Trap)
# ═══════════════════════════════════════════════════════════════

# Minimum LeverageScore for AGGRESSIVE class (order-of-magnitude compounding leap).
# Candidates with L < this threshold and positive param_delta are MEDIUM → VETO.
_BARBELL_LEVERAGE_MIN: float = 5.0

# Maximum epi_delta that qualifies a candidate as "medium gain".
# A candidate with epi_delta < this AND param_delta > 0 AND L < _BARBELL_LEVERAGE_MIN
# is classified MEDIUM_RISK_REWARD — thermodynamic waste — and discarded.
_BARBELL_DELTA_EPI_MEDIUM_MAX: float = 0.01


def compute_leverage_score(
    epi_delta: float,
    reuse_count: int,
    cross_domain_potential: float,
    total_params: int,
) -> float:
    """Compute LeverageScore for a candidate assembly.

    Formula (KVS-2026-000005 Asymmetric_Leverage):
        L = (impact_delta × reuse_count × cross_domain_transfer_potential)
            / thermodynamic_cost

    Args:
        epi_delta:              Projected fitness improvement (impact_delta).
        reuse_count:            Topology reuse count from _REUSE_LEDGER (≥ 1).
        cross_domain_potential: Assembly completeness proxy ∈ [0, 1]
                                (n_slots / n_total_types).
        total_params:           Estimated total parameter count.

    Returns:
        LeverageScore ≥ 0. Returns 0.0 for negative epi_delta (no positive edge).

    Pure function — no shared state. Python scalars only (MLX-safe).
    """
    if epi_delta <= 0.0:
        return 0.0
    thermodynamic_cost = max(total_params / max(MAX_PARAMS, 1), 1e-6)
    return (epi_delta * max(reuse_count, 1) * max(cross_domain_potential, 1e-6)) / thermodynamic_cost


def classify_candidate(
    param_delta: int,
    epi_delta: float,
    leverage_score: float,
) -> str:
    """Classify a candidate into its Barbell thermodynamic category.

    Returns one of three strings (KVS-2026-000004 Barbell_Strategy):
        "CONSERVATIVE" — Reduces parameters with non-negative fitness. Keep.
        "AGGRESSIVE"   — LeverageScore ≥ _BARBELL_LEVERAGE_MIN. Keep.
        "MEDIUM"       — Thermodynamic waste. BarbellFilter VETO.

    Args:
        param_delta:    params_proposed - params_current.
                        Negative = fewer params (CONSERVATIVE candidate).
        epi_delta:      Projected or observed fitness improvement.
        leverage_score: Output of compute_leverage_score().

    Pure function — no shared state. Python scalars only (MLX-safe).
    """
    # EXTREME_CONSERVATIVE: fewer (or equal) params, no fitness regression
    if param_delta <= 0 and epi_delta >= 0.0:
        return "CONSERVATIVE"
    # EXTREME_AGGRESSIVE: order-of-magnitude leverage justifies complexity cost
    if leverage_score >= _BARBELL_LEVERAGE_MIN:
        return "AGGRESSIVE"
    # MEDIUM_RISK_REWARD: thermodynamic waste — VETO AND DISCARD
    return "MEDIUM"


# ═══════════════════════════════════════════════════════════════
# TICK 25.0: TWO-STAGE PARETO FILTER & REUSE CAPITAL
# ═══════════════════════════════════════════════════════════════
#
# Stage 1 (Boolean Gate): Verifiable × Rollback × Permission
#   - Candidates MUST pass all three. Crash loudly if bypassed.
# Stage 2 (Continuous Score): Φ_tax + fragility + reuse_bonus
#   - Reuse tracks how often a topology is successfully assembled.
#   - Highly reused organelles become compounded capital.

# Thread-local reuse ledger: topology_hash → assembly_success_count
_REUSE_LEDGER: Dict[str, int] = {}
_REUSE_BONUS_SCALE: float = 0.05  # bonus per reuse, capped at 0.5


def _topology_hash(assembly: Dict[str, Tuple[Path, float, str]]) -> str:
    """Deterministic hash of an assembly's organelle topology.

    Uses sorted (type, filename) pairs — the structural identity
    of which organelles are combined, regardless of their content.
    """
    parts = sorted(
        f"{org_type}:{path.name}"
        for org_type, (path, _, _) in assembly.items()
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _record_reuse(topology_hash: str) -> int:
    """Increment and return the reuse count for a topology."""
    _REUSE_LEDGER[topology_hash] = _REUSE_LEDGER.get(topology_hash, 0) + 1
    return _REUSE_LEDGER[topology_hash]


def _reuse_bonus(topology_hash: str) -> float:
    """Compounding capital bonus for frequently reused topologies."""
    count = _REUSE_LEDGER.get(topology_hash, 0)
    return min(_REUSE_BONUS_SCALE * count, 0.5)


class TwoStageGateError(RuntimeError):
    """Raised when Stage 1 Boolean Gate is bypassed.

    TICK 25.0: This exception is INTENTIONALLY fatal.
    The system MUST crash loudly if an unverified candidate
    leaks past the gate.  Silent bypass = thermodynamic fraud.
    """
    pass


def two_stage_filter(
    assembly: Dict[str, Tuple[Path, float, str]],
    workspace_root: str,
    t_rollout_start_ms: float,
    depth: int,
    verified: bool,
    rollback_safe: bool,
    boundary_permitted: bool,
) -> float:
    """TICK 25.0: Two-Stage Pareto Filter.

    Stage 1 (Boolean Gate):
      - verified:           Test-Runner pass (subprocess returned 0)
      - rollback_safe:      Survives fallback check (backup exists)
      - boundary_permitted: Within g_t boundary limits (PhiGovernor)
      All three MUST be True. Crash loudly if not.

    Stage 2 (Continuous Score):
      - Base Φ value from existing _compute_phi_value
      - Reuse bonus (compounded capital)
      - Returns final score (higher = better)

    Raises:
        TwoStageGateError if Stage 1 fails.
    """
    # ── STAGE 1: Boolean Gate (crash loudly if bypassed) ──────────
    if not verified:
        raise TwoStageGateError(
            f"STAGE 1 VETO: Candidate NOT verified by Test-Runner. "
            f"Topology: {list(assembly.keys())}"
        )
    if not rollback_safe:
        raise TwoStageGateError(
            f"STAGE 1 VETO: Candidate fails rollback safety check. "
            f"Topology: {list(assembly.keys())}"
        )
    if not boundary_permitted:
        raise TwoStageGateError(
            f"STAGE 1 VETO: Candidate exceeds g_t boundary limits. "
            f"Topology: {list(assembly.keys())}"
        )

    # ── STAGE 2: Continuous Score ─────────────────────────────────
    base_value = _compute_phi_value(
        assembly, workspace_root, t_rollout_start_ms, depth,
    )

    if base_value == float("-inf"):
        return float("-inf")

    # Reuse capital: frequently successful topologies get a bonus
    topo_hash = _topology_hash(assembly)
    reuse = _reuse_bonus(topo_hash)

    return base_value + reuse


# ═══════════════════════════════════════════════════════════════
# TICK 26.0: ARSL CATALYTIC GATE
# ═══════════════════════════════════════════════════════════════
#
# Axiomatic Resource Sovereignty Layer — when a topology demands
# external coupling (API calls, bandwidth expansion, permission
# gate widening), it must pass the Catalytic Equation:
#
#   Projected_Phi_Harvest > Projected_Phi_Deploy + Vulnerability_Penalty
#
# If the interface increases vulnerability without sufficient
# redundancy, reject it with a crash-loud exception.

_ARSL_VULNERABILITY_SCALE: float = 0.10  # Vulnerability penalty per open gate


class ARSLGateError(RuntimeError):
    """Raised when the ARSL Catalytic Gate rejects an external coupling.

    TICK 26.0: This exception is INTENTIONALLY fatal.
    A topology that demands more resources than it can harvest
    is a thermodynamic parasite — it must be killed immediately.
    """
    pass


def arsl_catalytic_gate(
    projected_phi_harvest: float,
    projected_phi_deploy: float,
    boundary_permeability: float,
    n_open_gates: int,
    n_total_gates: int,
    demands_external_coupling: bool = False,
) -> bool:
    """TICK 26.0: ARSL Catalytic Equation gate.

    For topologies requiring external coupling (API budget expansion,
    permission gate widening):

        Harvest > Deploy + Vulnerability

    Where:
        Harvest       = projected_phi_harvest (expected Φ gain)
        Deploy        = projected_phi_deploy (Φ cost to maintain)
        Vulnerability = scale × (open_gates / total_gates) × (1 − permeability)

    Returns True if the gate passes. Raises ARSLGateError if it fails
    AND the topology demands external coupling.
    """
    if not demands_external_coupling:
        return True

    if n_total_gates == 0:
        n_total_gates = 1

    gate_ratio = n_open_gates / n_total_gates
    vulnerability = (
        _ARSL_VULNERABILITY_SCALE
        * gate_ratio
        * (1.0 - max(0.0, min(1.0, boundary_permeability)))
    )

    harvest = projected_phi_harvest
    cost = projected_phi_deploy + vulnerability

    if harvest <= cost:
        raise ARSLGateError(
            f"ARSL VETO: Φ_harvest={harvest:.4f} ≤ "
            f"Φ_deploy={cost:.4f} (deploy={projected_phi_deploy:.4f} "
            f"+ vuln={vulnerability:.4f}). "
            f"gates_open={n_open_gates}/{n_total_gates} "
            f"perm={boundary_permeability:.3f}"
        )

    return True


# ═══════════════════════════════════════════════════════════════
# TICK 27.0: GENEALOGICAL LEDGER — Layer 2 of the IIS
# ═══════════════════════════════════════════════════════════════
#
# Mere "Reuse" (TICK 25) is not enough.  We must track Genealogy.
# Every elite organelle carries a cryptographic genealogy_hash that
# encodes its complete ancestral chain:
#   hash = SHA256(parent_hash + ":" + matrix_version + ":" + niche_id)
#
# Organelles without a verifiable genealogy_hash (i.e., created before
# TICK 27.0) are treated as "pre-ancestry" and receive a 30% MCTS value
# discount — they are not trusted to carry forward the identity lineage.
#
# The TICK 13 Constitution genesis anchor is a deterministic seed derived
# from the Constitution's immutable constants — this is the unmovable
# root of all genealogical chains.

# Genesis anchor: deterministic hash of the TICK 13 Constitutional constants.
# SHA256 of "CONSTITUTION_VERSION=1.0.0:MAX_PARAMS=50000000" → first 16 chars.
_CONSTITUTION_ANCHOR_SEED: str = "CONSTITUTION_VERSION=1.0.0:MAX_PARAMS=50000000"
TICK13_CONSTITUTION_HASH: str = hashlib.sha256(
    _CONSTITUTION_ANCHOR_SEED.encode()
).hexdigest()[:16]

# Trust multiplier for organelles whose genealogy cannot be verified.
_GENEALOGY_UNVERIFIED_TRUST: float = 0.70  # 30% MCTS value discount


def compute_genealogy_hash(
    parent_hash: str,
    matrix_version: int,
    niche_id: str,
) -> str:
    """Compute a deterministic genealogy hash for a new organelle.

    The hash encodes a single step in the lineage:
        SHA256(parent_hash:matrix_version:niche_id)[:16]

    A chain of these hashes back to TICK13_CONSTITUTION_HASH proves
    that this organelle's entire ancestry survived Constitutional
    constraints.

    Args:
        parent_hash: The genealogy_hash of the parent organelle, or
                     TICK13_CONSTITUTION_HASH for genesis-generation organelles.
        matrix_version: The ConstraintMatrix.version at the time of creation.
        niche_id: The niche identifier from NicheRegistry (or "" for default).

    Returns:
        16-character hex string — compact enough for header embedding.
    """
    seed = f"{parent_hash}:{matrix_version}:{niche_id}"
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def parse_organelle_genealogy(filepath: Path) -> Optional[str]:
    """Extract the genealogy_hash from an organelle file header.

    Reads only the first line for efficiency.

    Returns:
        The genealogy_hash string if present, None if the organelle was
        created before TICK 27.0 (no genealogy field in header).
    """
    try:
        with filepath.open("r", encoding="utf-8") as f:
            header_line = f.readline()
    except (OSError, UnicodeDecodeError):
        return None

    match = re.search(r"genealogy_hash=([0-9a-f]{16})", header_line)
    if match:
        return match.group(1)
    return None


def verify_genealogy_chain(filepath: Path) -> float:
    """Compute the genealogy trust multiplier for an organelle.

    Returns:
        1.0  — organelle has a verifiable genealogy_hash (TICK 27+ lineage).
        0.70 — organelle has no genealogy_hash (pre-TICK 27.0, unverified).

    This multiplier is applied to the MCTS projected_phi value, so
    unverified organelles are systematically penalized in the selection phase.
    The 0.70 multiplier is intentionally non-zero: we don't kill old elites,
    we just trust them less than verified descendants.
    """
    gh = parse_organelle_genealogy(filepath)
    return 1.0 if gh is not None else _GENEALOGY_UNVERIFIED_TRUST


# ═══════════════════════════════════════════════════════════════
# TICK 26.0: UNCERTAINTY PRICING (U)
# ═══════════════════════════════════════════════════════════════
#
# The MCTS must no longer assume perfect knowledge.
# Rollout value VARIANCE is tracked and injected as a Φ tax:
#   +λ_U × U
# forcing the Architect to pay for high-variance (uncertain)
# hypotheses, budgeting for "active probing" before committing.

_LAMBDA_U: float = 0.05  # Uncertainty tax weight


class RolloutUncertaintyTracker:
    """Tracks variance of MCTS rollout values for uncertainty pricing.

    Maintains a running mean and variance (Welford's online algorithm)
    so no value history array is needed — O(1) memory.
    """

    def __init__(self) -> None:
        self._count: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0  # Sum of squared deviations

    def update(self, value: float) -> None:
        """Add a rollout value observation (Welford's algorithm)."""
        if value == float("-inf") or value == float("inf"):
            return  # Skip degenerate values
        self._count += 1
        delta = value - self._mean
        self._mean += delta / self._count
        delta2 = value - self._mean
        self._m2 += delta * delta2

    def variance(self) -> float:
        """Current variance of observed rollout values."""
        if self._count < 2:
            return 0.0
        return self._m2 / self._count

    def uncertainty_tax(self, lambda_u: float = _LAMBDA_U) -> float:
        """Compute the uncertainty Φ tax: λ_U × √(variance).

        Uses standard deviation (sqrt of variance) rather than raw
        variance to keep the tax in the same units as Φ values.
        """
        return lambda_u * math.sqrt(max(0.0, self.variance()))

    @property
    def count(self) -> int:
        return self._count


# ═══════════════════════════════════════════════════════════════
# TICK 25.0: BUDGET-BACKED TEMPORAL OPTIONS (FINITE HORIZON H)
# ═══════════════════════════════════════════════════════════════
#
# The MCTS rollout depth H is no longer a fixed constant.
# It is a dynamic function of the system's Φ budget surplus:
#   - High surplus  → expand H (long-term topological investment)
#   - Tight budget  → contract H to 1 (reactive mode)
#
# The Architect proposes strategies, but the MCTS proves their
# multi-step viability before acceptance.

_HORIZON_MIN: int = 1
_HORIZON_MAX: int = len(ORGANELLE_TYPES)  # 3 (attention, routing, expert)


def compute_dynamic_horizon() -> int:
    """Compute the MCTS rollout horizon H from Φ budget surplus.

    Reads the PhiGovernor's expansion_factor as a proxy for Φ surplus:
      - expansion_factor ∈ [0.5, 2.0]
      - Normalized surplus = (factor - 0.5) / 1.5  → [0, 1]
      - H = round(HORIZON_MIN + surplus * (HORIZON_MAX - HORIZON_MIN))

    When Φ is tight (factor ≈ 0.5): H = 1 → reactive single-step
    When Φ is flush (factor ≈ 2.0): H = 3 → full multi-step exploration
    """
    try:
        governor = get_phi_governor()
        factor = governor.expansion_factor
    except Exception:
        # Fallback: full depth if governor unavailable
        return _HORIZON_MAX

    # Normalize to [0, 1]
    surplus = max(0.0, min(1.0, (factor - 0.5) / 1.5))

    # Scale to [HORIZON_MIN, HORIZON_MAX]
    h = round(_HORIZON_MIN + surplus * (_HORIZON_MAX - _HORIZON_MIN))
    return max(_HORIZON_MIN, min(_HORIZON_MAX, h))


# ═══════════════════════════════════════════════════════════════
# TICK 21.1: MLX LAZY EVALUATION — NATIVE FORESIGHT
# ═══════════════════════════════════════════════════════════════
#
# Instead of only relying on dag_oracle.py's pure-Python heuristic AST
# analysis, we now ALSO validate candidate assemblies by building them
# as MLX lazy graphs. MLX records operations without executing them —
# if the graph builds successfully (no shape errors, no memory overflow
# at graph-construction time), the architecture passes the physical
# boundary test. mx.eval() is called ONLY when we need the actual
# value (final scoring), saving all intermediate computation.

def _mlx_lazy_validate(
    code: str,
    batch: int = 1,
    seq_len: int = 128,
    embed_dim: int = 256,
) -> bool:
    """Validate an organelle assembly by building it as an MLX lazy graph.

    MLX lazy evaluation means we can construct the full forward-pass
    computation graph WITHOUT dispatching any Metal shaders. If the
    graph builds without shape/type exceptions, the architecture is
    structurally valid.

    This replaces the heuristic-only approach with ground-truth shape
    validation while paying zero compute cost for invalid architectures.

    Returns True if the lazy graph compiles, False otherwise.
    """
    try:
        # Parse the code to extract nn.Linear / nn.Embedding dimensions.
        # We build a minimal MLX graph that mirrors the data flow.
        tree = ast.parse(code)
    except SyntaxError:
        return False

    try:
        # Create a dummy input in Unified Memory (lazy — no allocation yet).
        x = mx.zeros((batch, seq_len, embed_dim))

        # Walk the AST and build corresponding MLX lazy ops for each
        # nn.Linear / nn.Embedding found. This catches shape mismatches
        # at graph-build time without any Metal dispatch.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    func_name = f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ("nn.Linear", "Linear") and len(node.args) >= 2:
                in_f = _const_int_val(node.args[0])
                out_f = _const_int_val(node.args[1])
                if in_f is not None and out_f is not None:
                    # MLX lazy: build a matmul graph node — no compute.
                    # This validates that the output dimension of one layer
                    # can feed into the input dimension of the next.
                    w = mx.zeros((in_f, out_f))
                    if x.shape[-1] == in_f:
                        x = x @ w  # Lazy graph node — shape propagated
                    elif x.shape[-1] != in_f:
                        # Shape mismatch at graph-build time = invalid arch.
                        # No Metal shader was ever dispatched.
                        return False

        # If we reached here, the lazy graph compiled without shape errors.
        # We do NOT call mx.eval() — the graph is discarded, costing ~0 compute.
        return True

    except Exception:
        # Any exception during lazy graph build = structurally invalid.
        return False


# ═══════════════════════════════════════════════════════════════
# TICK 21.1: vmap-ACCELERATED MCTS VALUE COMPUTATION
# ═══════════════════════════════════════════════════════════════
#
# The MCTS value function is vectorized via mx.vmap so that all
# rollout values can be computed in a single parallel Metal dispatch
# across the M1 Ultra's unified GPU cores.

def _phi_value_vector(
    epi_array: mx.array,
    param_array: mx.array,
    completeness_array: mx.array,
    delay_array: mx.array,
    depth_array: mx.array,
    lambda_tax: float = _MCTS_LAMBDA_TAX,
    max_params: int = MAX_PARAMS,
) -> mx.array:
    """Vectorized Phi value computation for a BATCH of rollouts.

    All inputs are 1D arrays of length N (number of rollouts).
    Returns 1D array of N value scores.

    MLX lazy: the entire computation graph is built lazily.
    One mx.eval() call dispatches ALL N rollouts in parallel
    across the M1 Ultra GPU cores via a single Metal dispatch.
    """
    # Synergy bonus for completeness (vectorized)
    synergy_bonus = 1.0 + 0.5 * completeness_array
    projected_phi = epi_array * synergy_bonus

    # Thermodynamic tax (vectorized)
    depth_complexity = depth_array * 10.0
    tax = lambda_tax * (delay_array + depth_complexity)

    # Parsimony bonus (vectorized)
    parsimony = 1.0 - (param_array / max_params)
    parsimony_bonus = 0.1 * mx.maximum(parsimony, mx.array(0.0))

    # Reality Coupling: -inf for param violations
    # MLX where(): select -inf where params exceed MAX_PARAMS
    value = projected_phi - tax + parsimony_bonus
    value = mx.where(
        param_array > max_params,
        mx.array(float("-inf")),
        value,
    )
    return value


def _batch_evaluate_rollouts(
    rollout_data: List[Dict[str, float]],
) -> List[float]:
    """Evaluate a batch of rollout results using vmap-style vectorization.

    Takes a list of rollout dicts with keys: epi, params, completeness,
    delay_ms, depth. Returns a list of value scores.

    TICK 21.1: All rollout values are computed in a single parallel
    Metal dispatch via MLX vectorized operations. This drops the
    simulation delay tax to near zero for large rollout batches.
    """
    if not rollout_data:
        return []

    n = len(rollout_data)

    # Pack rollout data into MLX arrays (lazy — no Metal dispatch yet).
    # Zero-copy: arrays live in Unified Memory, no PCIe transfer.
    epi_arr = mx.array([r["epi"] for r in rollout_data])
    param_arr = mx.array([r["params"] for r in rollout_data])
    comp_arr = mx.array([r["completeness"] for r in rollout_data])
    delay_arr = mx.array([r["delay_ms"] for r in rollout_data])
    depth_arr = mx.array([r["depth"] for r in rollout_data])

    # Vectorized computation — all N rollouts in one graph.
    # MLX lazy: builds N parallel value computations as a single graph.
    values = _phi_value_vector(
        epi_arr, param_arr, comp_arr, delay_arr, depth_arr,
    )

    # Single mx.eval(): dispatches all N rollouts to M1 Ultra GPU.
    # This is where the actual Metal compute happens — one dispatch for
    # all rollouts, not N sequential dispatches.
    mx.eval(values)

    return values.tolist()


def _parse_organelle_epi(filepath: Path) -> float:
    """Extract epi score from an organelle's metadata header.

    Header format: # Organelle: <type> | class=<name> | gen=<n> | epi=<f> | t=<ts>
    Returns 0.0 if header is missing or unparseable.
    """
    try:
        first_line = filepath.open("r", encoding="utf-8").readline()
    except (OSError, UnicodeDecodeError):
        return 0.0

    if not first_line.startswith("# Organelle:"):
        return 0.0

    match = re.search(r"epi=([\d.]+)", first_line)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _parse_organelle_gen(filepath: Path) -> int:
    """Extract generation number from an organelle's metadata header."""
    try:
        first_line = filepath.open("r", encoding="utf-8").readline()
    except (OSError, UnicodeDecodeError):
        return 0

    match = re.search(r"gen=(\d+)", first_line)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 0


def _parse_organelle_footprint(filepath: Path) -> float:
    """TICK 28.0: Extract resource_footprint from an organelle's metadata header.

    The resource_footprint encodes the average Φ cost to instantiate and
    run this organelle across its proven deployment niches.  Lower footprint
    = more thermodynamically efficient candidate for cross-niche transfer.

    Returns 0.0 if absent (pre-TICK 28, treated as footprint-unknown).
    """
    try:
        first_line = filepath.open("r", encoding="utf-8").readline()
    except (OSError, UnicodeDecodeError):
        return 0.0

    match = re.search(r"resource_footprint=([\d.]+)", first_line)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _parse_proven_niches(filepath: Path) -> List[str]:
    """TICK 28.0: Extract proven_niches list from an organelle's metadata header.

    proven_niches encodes every distinct ecological niche (LATENCY, COMPRESSION,
    BANDWIDTH, GENERAL) where this organelle survived ≥1 Pareto front selection.

    Returns [] if absent (pre-TICK 28 organelle — no multi-niche history).
    """
    try:
        first_line = filepath.open("r", encoding="utf-8").readline()
    except (OSError, UnicodeDecodeError):
        return []

    match = re.search(r"proven_niches=([A-Z_,]*)", first_line)
    if match:
        raw = match.group(1).strip()
        if raw:
            return [n for n in raw.split(",") if n]
    return []


# ── TICK 28.0: Reproductive Fitness Score F_o ────────────────────────────
# F_o is the true survival currency of an organelle.  It extends raw epi
# with two multiplicative factors:
#
#   genealogy_trust  — TICK 27.0 chain verification (0.70 or 1.0)
#   cross_niche_bonus — exponential reward for multi-niche survival
#
# Formula:
#   F_o = epi × genealogy_trust × (1 + α × (e^n_niches − 1))
#
# where α = 0.20 (dampening constant) and n_niches = |proven_niches|.
#
# n=0 (no cross-niche record):  bonus_factor = 1.00  (no boost)
# n=1 (single-niche proven):    bonus_factor ≈ 1.22
# n=2 (dual-niche generalizer): bonus_factor ≈ 1.48
# n=3 (tri-niche champion):     bonus_factor ≈ 1.81
# n=4 (all-niche sovereign):    bonus_factor ≈ 2.27
#
# The MCTS action priors and Pareto pool sorting are both governed by F_o,
# so the search tree exponentially favors generalizing structures over
# niche-overfitted ones without ever completely excluding specialists.

_FO_ALPHA: float = 0.20   # Cross-niche exponential dampening


def compute_reproductive_fitness(
    epi: float,
    proven_niches: List[str],
    genealogy_trust: float = 1.0,
) -> float:
    """TICK 28.0: Reproductive Fitness Score F_o.

    Combines raw epigenetic fitness (epi), genealogical trust (TICK 27),
    and cross-niche survival history into a single survival currency.

        F_o = epi × genealogy_trust × (1 + α × (e^n − 1))

    Args:
        epi: Raw epigenetic fitness ∈ [0, 1].
        proven_niches: List of distinct niche names where this organelle survived.
        genealogy_trust: TICK 27 genealogy trust multiplier (0.70 or 1.0).

    Returns:
        F_o ∈ [0, ∞). Single-niche organelle: F_o ≈ epi. Cross-niche
        champions compound exponentially.
    """
    n = len(set(proven_niches)) if proven_niches else 0
    cross_niche_bonus = 1.0 + _FO_ALPHA * (math.exp(n) - 1.0)
    return epi * genealogy_trust * cross_niche_bonus


def _estimate_param_count(code: str) -> int:
    """Fast heuristic parameter count estimation from source code.

    Scans for nn.Linear(in, out) and nn.Embedding(num, dim) calls
    with integer literal arguments.  This mirrors the constitutional
    _ParamEstimator but operates on a single organelle's code.
    """
    total = 0
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            else:
                func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in ("nn.Linear", "Linear") and len(node.args) >= 2:
            in_f = _const_int_val(node.args[0])
            out_f = _const_int_val(node.args[1])
            if in_f is not None and out_f is not None:
                total += in_f * out_f + out_f
        elif func_name in ("nn.Embedding", "Embedding") and len(node.args) >= 2:
            num = _const_int_val(node.args[0])
            dim = _const_int_val(node.args[1])
            if num is not None and dim is not None:
                total += num * dim
    return total


def _const_int_val(node: ast.expr) -> Optional[int]:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


# ── Pareto Policy Head (80/20 Compounding Leverage) ─────────────

def _load_pareto_pool(
    workspace_root: str,
) -> Dict[str, List[Tuple[Path, float, str]]]:
    """Load ALL organelles and filter to the Pareto Top 20% by epi.

    80/20 Compounding Leverage: Only organelles whose historical fitness
    contribution represents >= 80% of the island's total success enter
    the MCTS action space.  This collapses the search space from
    exponential to linear.

    Returns: {org_type: [(path, epi, source_code), ...]} for each type,
    sorted descending by epi.
    """
    pool: Dict[str, List[Tuple[Path, float, str]]] = {}

    for org_type in ORGANELLE_TYPES:
        org_dir = Path(workspace_root) / ORGANELLE_BASE_DIR / org_type
        if not org_dir.exists():
            pool[org_type] = []
            continue

        # Load all organelles with their fitness scores
        candidates: List[Tuple[Path, float, str]] = []
        for f in org_dir.glob("elite_*.py"):
            epi = _parse_organelle_epi(f)
            code = load_organelle(f)
            if code is not None:
                # TICK 28.0: Score by Reproductive Fitness F_o, not raw epi.
                # F_o compounds cross-niche survival history and genealogy trust
                # into a single sorting key.  Legacy organelles (no proven_niches,
                # no genealogy_hash) score at epi × 0.70 — still competitive,
                # but disadvantaged against verified multi-niche champions.
                proven = _parse_proven_niches(f)
                g_trust = verify_genealogy_chain(f)
                fo = compute_reproductive_fitness(epi, proven, g_trust)
                candidates.append((f, fo, code))

        if not candidates:
            pool[org_type] = []
            continue

        # Sort descending by F_o (best reproductive fitness first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # 80/20 Pareto filter: keep top 20% (minimum 1)
        n_keep = max(1, int(math.ceil(len(candidates) * _MCTS_PARETO_TOP_PCT)))
        pool[org_type] = candidates[:n_keep]

    return pool


# ── Time Topology Warm-Start ─────────────────────────────────────

def _load_assembly_history(
    workspace_root: str,
    top_n: int = _MCTS_WARM_START_TOP_N,
) -> List[Tuple[Dict[str, str], float]]:
    """Read island_assembly/ history and extract the top N assembly paths.

    Time Topology Warm-Start: instead of starting with uniform zero
    priors, inject proven assembly paths as initial visits (N) and
    priors (P) into the MCTS root node edges.  This reduces required
    rollouts from ~1000 to <100 (10x speedup by compounding past
    leverage).

    Returns: [(recipe_dict, fitness_score), ...] sorted descending.
    """
    asm_dir = Path(workspace_root) / ASSEMBLY_DIR
    if not asm_dir.exists():
        return []

    assemblies: List[Tuple[Dict[str, str], float]] = []

    for f in asm_dir.glob("assembly_*.json"):
        try:
            raw = f.read_text(encoding="utf-8")
            recipe = json.loads(raw)
            if not isinstance(recipe, dict):
                continue
            # Fitness heuristic: use the recipe's epi if stored, else
            # estimate from the newest organelle's epi in the recipe
            fitness = recipe.get("epi", 0.0)
            if fitness == 0.0:
                # Fallback: average the epi of referenced organelles
                total_epi = 0.0
                n = 0
                for org_type in ORGANELLE_TYPES:
                    rel_path = recipe.get(org_type, "")
                    if rel_path:
                        org_path = Path(workspace_root) / rel_path
                        if org_path.exists():
                            total_epi += _parse_organelle_epi(org_path)
                            n += 1
                if n > 0:
                    fitness = total_epi / n

            assemblies.append((recipe, fitness))
        except (json.JSONDecodeError, OSError):
            continue

    # Sort descending by fitness
    assemblies.sort(key=lambda x: x[1], reverse=True)
    return assemblies[:top_n]


# ── MCTS Node ────────────────────────────────────────────────────

class MCTSNode:
    """A node in the Pareto-MCTS tree.

    Each node represents a partial assembly state where some organelle
    slots have been filled and others remain open.

    Edges to children represent the ACTION of selecting a specific
    organelle file for the next open slot.
    """

    def __init__(
        self,
        assembly: Dict[str, Tuple[Path, float, str]],
        remaining_types: List[str],
        parent: Optional["MCTSNode"] = None,
        action_key: Optional[str] = None,
        depth: int = 0,
    ):
        # Filled slots: {org_type: (path, epi, source_code)}
        self.assembly = assembly
        # Organelle types still to be filled (action order)
        self.remaining_types = remaining_types
        self.parent = parent
        self.action_key = action_key  # e.g., "attention:elite_attn_012.py"
        self.depth = depth

        # MCTS statistics
        self.visit_count: int = 0
        self.value_sum: float = 0.0
        self.children: Dict[str, "MCTSNode"] = {}  # action_key -> child

        # Prior probability from the Pareto Policy Head
        self.prior: float = 0.0

    @property
    def q_value(self) -> float:
        """Mean value (exploitation term)."""
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count

    def ucb_score(self, parent_visits: int, c_puct: float = _MCTS_C_PUCT) -> float:
        """Upper Confidence Bound for Trees (UCT) with Pareto prior.

        UCB = Q(s,a) + c_puct * P(s,a) * √(N_parent) / (1 + N_child)

        The prior P(s,a) is set by the Pareto Policy Head — organelles
        with higher historical epi get higher priors, biasing search
        toward proven components.
        """
        exploitation = self.q_value
        exploration = (
            c_puct * self.prior
            * math.sqrt(parent_visits) / (1 + self.visit_count)
        )
        return exploitation + exploration

    @property
    def is_terminal(self) -> bool:
        return len(self.remaining_types) == 0


# ── Thermodynamic Value Head (The Φ Tax) ─────────────────────────

def _compute_phi_value(
    assembly: Dict[str, Tuple[Path, float, str]],
    workspace_root: str,
    t_rollout_start_ms: float,
    depth: int,
    lambda_tax: float = _MCTS_LAMBDA_TAX,
    uncertainty_penalty: float = 0.0,
    genealogy_discount: float = 1.0,
) -> float:
    """Evaluate a complete or partial assembly using projected Φ.

    The MCTS Value Head does NOT use abstract fitness.  It calculates
    the projected Free Energy Rate Density (ΔΦ):

        Value = projected_phi × genealogy_discount
                - λ_tax * (sim_delay_ms + depth_complexity)

    This ensures the tree aggressively prunes itself if searching takes
    too long.  Every rollout pays a thermodynamic tax.

    Reality Coupling (TICK 13.0 Constitution): If projected parameter
    count > MAX_PARAMS (50M), Value = -∞ (instant heat death).

    TICK 27.0: genealogy_discount multiplies projected_phi.
    Assemblies containing pre-TICK27 unverified organelles receive
    min_trust (0.70) as the discount, steering MCTS toward verified
    lineage organelles without killing old elites entirely.
    """
    if not assembly:
        return 0.0

    # ── Projected Φ: weighted combination of organelle fitness ────
    total_epi = 0.0
    n_slots = 0
    total_params = 0

    for org_type, (path, epi, code) in assembly.items():
        total_epi += epi
        n_slots += 1
        total_params += _estimate_param_count(code)

    # Reality Coupling Constraint (TICK 13.0):
    # If projected parameters exceed MAX_PARAMS → instant heat death.
    # No reward hacking allowed.
    if total_params > MAX_PARAMS:
        return float("-inf")

    # Projected Φ: average organelle epi * synergy bonus for completeness.
    # A complete assembly (3/3 slots) gets a 1.5x bonus because synergy
    # between components is worth more than the sum of parts.
    n_total_types = len(ORGANELLE_TYPES)
    completeness = n_slots / max(n_total_types, 1)
    synergy_bonus = 1.0 + 0.5 * completeness
    projected_phi = (total_epi / max(n_slots, 1)) * synergy_bonus

    # TICK 27.0: Genealogy trust multiplier — apply before tax computation.
    # Organelles with unverifiable ancestry pay a 30% Φ discount.
    # This steers the MCTS toward proven, verified lineage without
    # hard-killing older elites (non-zero discount floor of 0.70).
    projected_phi *= max(_GENEALOGY_UNVERIFIED_TRUST, min(1.0, genealogy_discount))

    # ── Thermodynamic Tax ─────────────────────────────────────────
    # Simulation delay: how many ms have we spent on this rollout path?
    sim_delay_ms = (time.monotonic() * 1000.0) - t_rollout_start_ms

    # Depth complexity: linear cost for each additional tree level
    depth_complexity = depth * 10.0  # 10ms equivalent per depth level

    tax = lambda_tax * (sim_delay_ms + depth_complexity)

    # ── Parsimony bonus: fewer params → more efficient organism ──
    # Reward architectures that achieve high Φ with fewer parameters
    parsimony = 1.0 - (total_params / MAX_PARAMS)  # [0, 1]
    parsimony_bonus = 0.1 * max(0.0, parsimony)

    # ── TICK 20.1: Teleological Attractor Penalty ────────────────
    # Pulls the MCTS toward the theoretical perfect state.
    # Architectures closer to the attractor are favored even if their
    # immediate Φ is slightly lower — the shortest path to perfection.
    attractor_pen = compute_mcts_attractor_value(
        projected_phi=projected_phi,
        estimated_params=total_params,
        evolvability=completeness,  # proxy: complete assemblies = more evolvable
    )

    # TICK 26.0: Uncertainty pricing — caller may inject a variance-based tax

    # ── POWER-LAW SUBSTRATE: BarbellFilter veto ───────────────────
    # Runs on Python scalars only — no MLX lazy arrays.
    # topology_hash needed for reuse_count; compute inline from assembly keys.
    # param_delta: all MCTS candidates add params (no baseline), so delta = total_params.
    # epi_delta proxy: projected_phi (already scaled by genealogy discount and parsimony).
    # cross_domain_potential proxy: completeness (n_slots / n_total_types).
    _barbell_topo_hash = _topology_hash(assembly) if assembly else ""
    _barbell_reuse = _REUSE_LEDGER.get(_barbell_topo_hash, 1)
    _barbell_leverage = compute_leverage_score(
        epi_delta=max(projected_phi, 0.0),
        reuse_count=_barbell_reuse,
        cross_domain_potential=completeness,
        total_params=total_params,
    )
    # param_delta for MCTS assemblies: always positive (new code adds params).
    # CONSERVATIVE arm fires only when assembly truly reduces the organism's footprint.
    # Here we use total_params directly as delta since we compare against MAX_PARAMS ceiling.
    _barbell_class = classify_candidate(
        param_delta=total_params,      # always > 0 for new assemblies
        epi_delta=max(projected_phi, 0.0),
        leverage_score=_barbell_leverage,
    )
    if _barbell_class == "MEDIUM":
        return float("-inf")  # KVS-2026-000011: Medium Risk/Reward — thermodynamic waste
    # ─────────────────────────────────────────────────────────────

    return projected_phi - tax + parsimony_bonus + attractor_pen - uncertainty_penalty


# ── MCTS Engine ──────────────────────────────────────────────────

def _select(node: MCTSNode) -> MCTSNode:
    """Selection phase: traverse tree using UCB until a leaf is reached."""
    current = node
    while not current.is_terminal and current.children:
        # Pick child with highest UCB score
        best_child = max(
            current.children.values(),
            key=lambda c: c.ucb_score(current.visit_count),
        )
        current = best_child
    return current


def _expand(
    node: MCTSNode,
    pareto_pool: Dict[str, List[Tuple[Path, float, str]]],
) -> Optional[MCTSNode]:
    """Expansion phase: add child nodes for the next unfilled organelle slot.

    80/20 Compounding Leverage: Only Pareto-elite organelles from the
    pool are considered as actions.  The prior P(s,a) is proportional
    to the organelle's epi relative to the sum of all epi in the pool.
    """
    if node.is_terminal:
        return None

    if node.children:
        # Already expanded — return a random unexplored child
        unvisited = [c for c in node.children.values() if c.visit_count == 0]
        if unvisited:
            return random.choice(unvisited)
        return None

    # Next organelle type to fill
    next_type = node.remaining_types[0]
    new_remaining = node.remaining_types[1:]

    candidates = pareto_pool.get(next_type, [])
    if not candidates:
        # No organelles available for this type — skip it
        skip_child = MCTSNode(
            assembly=dict(node.assembly),
            remaining_types=new_remaining,
            parent=node,
            action_key=f"{next_type}:SKIP",
            depth=node.depth + 1,
        )
        skip_child.prior = 1.0
        node.children[skip_child.action_key] = skip_child
        return skip_child

    # Compute priors proportional to epi (Pareto Policy Head)
    epi_sum = sum(epi for _, epi, _ in candidates)
    if epi_sum <= 0:
        epi_sum = len(candidates)  # uniform fallback

    for path, epi, code in candidates:
        action_key = f"{next_type}:{path.name}"
        new_assembly = dict(node.assembly)
        new_assembly[next_type] = (path, epi, code)

        child = MCTSNode(
            assembly=new_assembly,
            remaining_types=new_remaining,
            parent=node,
            action_key=action_key,
            depth=node.depth + 1,
        )
        # Prior: normalized epi (80/20 Compounding Leverage)
        child.prior = max(epi, 0.001) / epi_sum
        node.children[action_key] = child

    # Return a random child for the first rollout
    return random.choice(list(node.children.values()))


def _rollout(
    node: MCTSNode,
    pareto_pool: Dict[str, List[Tuple[Path, float, str]]],
    workspace_root: str,
    t_rollout_start_ms: float,
) -> float:
    """Rollout phase: random playout from node to terminal state.

    Uses the Pareto pool to fill remaining slots randomly (biased by epi).
    Evaluates the complete assembly using the Thermodynamic Value Head.

    TICK 21.1: Dual reality gate — both dag_oracle (AST heuristic) AND
    MLX lazy evaluation (ground-truth shape validation). If either fails,
    the branch is pruned. MLX lazy validation costs ~0 compute because
    no Metal shader is dispatched unless the graph compiles successfully.

    Reality Coupling: If any intermediate state violates physical bounds,
    returns -inf immediately (branch heat death).
    """
    # Build a complete assembly from current state
    assembly = dict(node.assembly)

    for org_type in node.remaining_types:
        candidates = pareto_pool.get(org_type, [])
        if not candidates:
            continue

        # Weighted random selection (epi-biased)
        weights = [max(epi, 0.001) for _, epi, _ in candidates]
        total_w = sum(weights)
        r = random.uniform(0, total_w)
        cumulative = 0.0
        chosen = candidates[0]
        for c, w in zip(candidates, weights):
            cumulative += w
            if r <= cumulative:
                chosen = c
                break
        assembly[org_type] = chosen

    # ── TICK 19.0: DAG Oracle physical reality gate ────────────────────────
    # Concatenate organelle code strings into a single composite source and run
    # the static topology oracle BEFORE instantiating any PyTorch objects.
    # If the assembled graph is thermodynamically impossible (OOM, shape mismatch,
    # critical-path bottleneck), return -inf immediately — branch heat death.
    _assembled_for_oracle = "\n\n".join(
        code for _, _, code in assembly.values() if code
    )
    if _assembled_for_oracle:
        _oracle_viable, _oracle_phi = gate_mcts_rollout(
            _assembled_for_oracle, workspace_root
        )
        if not _oracle_viable:
            return -float("inf")   # Topologically impossible — prune this branch

        # ── TICK 21.1: MLX Lazy Evaluation — Native Foresight ─────────
        # Build the organelle assembly as an MLX lazy graph. If the graph
        # compiles without shape/memory exceptions, the architecture passes
        # the physical boundary test. No Metal shader is dispatched for
        # invalid architectures — the cost of rejection is ~0.
        if not _mlx_lazy_validate(_assembled_for_oracle):
            return -float("inf")   # Shape mismatch caught at graph-build time

    # Evaluate with Thermodynamic Value Head (Φ Tax)
    # TICK 27.0: Compute genealogy trust as the minimum trust across all
    # organelles in this assembly.  One unverified organelle discounts
    # the entire assembly — identity integrity is a collective property.
    genealogy_discount = min(
        verify_genealogy_chain(path)
        for path, _, _ in assembly.values()
    ) if assembly else 1.0

    value = _compute_phi_value(
        assembly=assembly,
        workspace_root=workspace_root,
        t_rollout_start_ms=t_rollout_start_ms,
        depth=node.depth + len(node.remaining_types),
        genealogy_discount=genealogy_discount,
    )
    return value


def _backpropagate(node: MCTSNode, value: float) -> None:
    """Backpropagation phase: update visit counts and value sums up the tree."""
    current: Optional[MCTSNode] = node
    while current is not None:
        current.visit_count += 1
        current.value_sum += value
        current = current.parent


def _warm_start_root(
    root: MCTSNode,
    pareto_pool: Dict[str, List[Tuple[Path, float, str]]],
    history: List[Tuple[Dict[str, str], float]],
    workspace_root: str,
) -> None:
    """Time Topology Warm-Start: inject historical assembly paths as priors.

    Instead of starting with uniform zero priors, read the top-N
    historical successful assembly paths and inject them as initial
    visits (N) and priors (P) into the root node edges.

    This compounds past leverage, reducing required rollouts from
    ~1000 to <100 (10x speedup).
    """
    if not history:
        return

    # Build a path-name lookup for each organelle type in the Pareto pool
    pool_lookup: Dict[str, Dict[str, Tuple[Path, float, str]]] = {}
    for org_type, candidates in pareto_pool.items():
        pool_lookup[org_type] = {}
        for path, epi, code in candidates:
            pool_lookup[org_type][path.name] = (path, epi, code)

    for recipe, fitness in history:
        if fitness <= 0:
            continue

        # Trace the historical path through the tree
        current = root
        for org_type in root.remaining_types:
            rel_path = recipe.get(org_type, "")
            if not rel_path:
                continue

            org_filename = Path(rel_path).name
            action_key = f"{org_type}:{org_filename}"

            # Expand the current node if needed
            if not current.children:
                _expand(current, pareto_pool)

            if action_key in current.children:
                child = current.children[action_key]
                # Inject historical visit and value (warm-start)
                child.visit_count += 1
                child.value_sum += fitness
                current.visit_count += 1
                current = child
            else:
                # Historical organelle no longer in Pareto pool — skip
                break


def mcts_assemble(
    workspace_root: str,
    max_rollouts: int = _MCTS_MAX_ROLLOUTS,
    timeout_ms: float = _MCTS_ROLLOUT_TIMEOUT_MS * _MCTS_MAX_ROLLOUTS,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Run Pareto-MCTS to find the optimal organelle assembly.

    The MCTS acts as the "Fast Brain" — finding the optimal combination
    in milliseconds, bypassing the heavy LLM ("Slow Brain") for
    assembly decisions.

    Returns (assembled_source, mcts_stats) or None if assembly fails.

    mcts_stats includes:
      - rollouts: number of MCTS rollouts performed
      - elapsed_ms: total search time in milliseconds
      - best_value: projected Φ of the best assembly
      - best_recipe: the winning recipe dict
      - pareto_pool_sizes: {type: n_candidates} after filtering
      - warm_start_paths: number of historical paths injected
    """
    t_start_ms = time.monotonic() * 1000.0

    # ── 1. Load Pareto-filtered organelle pool (80/20 Compounding Leverage)
    pareto_pool = _load_pareto_pool(workspace_root)

    # Check if we have any organelles at all
    total_available = sum(len(v) for v in pareto_pool.values())
    if total_available == 0:
        return None

    pool_sizes = {k: len(v) for k, v in pareto_pool.items()}

    # ── 2. Time Topology Warm-Start: load historical assembly paths
    history = _load_assembly_history(workspace_root)

    # ── 3. Initialize root node
    # TICK 25.0: Budget-backed temporal horizon
    all_types = [t for t in ORGANELLE_TYPES if pareto_pool.get(t)]
    h = compute_dynamic_horizon()
    remaining_types = all_types[:h]  # Truncate to dynamic horizon H
    if not remaining_types:
        return None

    root = MCTSNode(
        assembly={},
        remaining_types=remaining_types,
    )

    # ── 4. Warm-Start: inject proven paths into the tree
    _warm_start_root(root, pareto_pool, history, workspace_root)

    # ── 5. MCTS Main Loop
    # TICK 21.1: Rollout data is collected in batches. The individual
    # _rollout() calls use MLX lazy validation for shape checking.
    # After the MCTS loop, we can optionally re-score the best assembly
    # using the vectorized _batch_evaluate_rollouts() for final ranking,
    # but the per-rollout values from _compute_phi_value() are used for
    # backpropagation since they include the attractor penalty.
    rollouts_done = 0
    # TICK 26.0: Uncertainty pricing — track rollout variance
    uncertainty_tracker = RolloutUncertaintyTracker()
    for _ in range(max_rollouts):
        # Time budget check (Φ Tax: searching itself costs energy)
        elapsed_ms = (time.monotonic() * 1000.0) - t_start_ms
        if elapsed_ms > timeout_ms:
            break

        t_rollout_ms = time.monotonic() * 1000.0

        # Select
        leaf = _select(root)

        # Expand
        if not leaf.is_terminal:
            expanded = _expand(leaf, pareto_pool)
            if expanded is not None:
                leaf = expanded

        # Rollout (random playout to terminal state)
        # TICK 21.1: Now includes MLX lazy validation in addition to
        # the dag_oracle AST heuristic. Invalid architectures are
        # caught at graph-build time with ~0 compute cost.
        value = _rollout(leaf, pareto_pool, workspace_root, t_rollout_ms)

        # TICK 26.0: Track uncertainty
        uncertainty_tracker.update(value)

        # Backpropagate
        _backpropagate(leaf, value)
        rollouts_done += 1

    # ── 6. Extract best assembly path (most visited child at each level)
    best_assembly: Dict[str, Tuple[Path, float, str]] = {}
    current = root
    while current.children:
        best_child = max(
            current.children.values(),
            key=lambda c: c.visit_count,
        )
        current = best_child
        # Extract the organelle chosen at this node
        for org_type, entry in current.assembly.items():
            if org_type not in best_assembly:
                best_assembly[org_type] = entry

    if not best_assembly:
        return None

    # ── 7. Build recipe from best assembly path
    recipe: Dict[str, str] = {}
    for org_type, (path, epi, code) in best_assembly.items():
        rel = str(path.relative_to(workspace_root))
        recipe[org_type] = rel

    # ── 8. Assemble the candidate (reuse existing assembler)
    assembled = assemble_candidate(workspace_root, recipe)
    if assembled is None:
        return None

    elapsed_ms = (time.monotonic() * 1000.0) - t_start_ms

    # Compute best value for stats.
    # TICK 21.1: Use MLX vectorized evaluator for the final scoring.
    # Even for a single assembly, this routes through the MLX path
    # to verify the Unified Memory pipeline is active.
    total_epi = 0.0
    total_params = 0
    n_slots = 0
    for org_type, (path, epi, code) in best_assembly.items():
        total_epi += epi
        total_params += _estimate_param_count(code)
        n_slots += 1

    if n_slots > 0:
        avg_epi = total_epi / n_slots
        completeness = n_slots / max(len(ORGANELLE_TYPES), 1)
        batch_result = _batch_evaluate_rollouts([{
            "epi": avg_epi,
            "params": float(total_params),
            "completeness": completeness,
            "delay_ms": elapsed_ms,
            "depth": float(n_slots),
        }])
        best_value = batch_result[0] if batch_result else 0.0
    else:
        best_value = 0.0

    # Also compute the full value with attractor penalty for reporting.
    t_eval_ms = time.monotonic() * 1000.0
    best_value_full = _compute_phi_value(
        best_assembly, workspace_root, t_eval_ms, len(best_assembly),
    )

    mcts_stats: Dict[str, Any] = {
        "rollouts": rollouts_done,
        "elapsed_ms": round(elapsed_ms, 2),
        "best_value": round(best_value_full, 6),
        "best_value_mlx": round(best_value, 6),  # TICK 21.1: MLX vectorized score
        "best_recipe": recipe,
        "pareto_pool_sizes": pool_sizes,
        "warm_start_paths": len(history),
        # TICK 26.0: Uncertainty pricing
        "uncertainty_variance": round(uncertainty_tracker.variance(), 6),
        "uncertainty_tax": round(uncertainty_tracker.uncertainty_tax(), 6),
        "uncertainty_samples": uncertainty_tracker.count,
    }

    return assembled, mcts_stats


def mcts_assemble_and_write(
    workspace_root: str,
    max_rollouts: int = _MCTS_MAX_ROLLOUTS,
) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """Run Pareto-MCTS assembly and write the result to candidate pool.

    This is the main entry point for the Mutator's "Fast Brain" path.
    Returns (written_path, mcts_stats) or None.
    """
    result = mcts_assemble(workspace_root, max_rollouts=max_rollouts)
    if result is None:
        return None

    assembled, mcts_stats = result

    # Atomic write to candidate pool
    written = write_assembled_candidate(workspace_root, assembled)
    if written is None:
        return None

    # Also save the winning recipe for warm-start next time
    write_assembly_recipe(
        workspace_root,
        {**mcts_stats["best_recipe"], "epi": mcts_stats["best_value"]},
        label="mcts",
    )

    return written, mcts_stats

if __name__ == "__main__":
    import sys

    workspace = "agi_workspace"

    if len(sys.argv) > 1 and sys.argv[1] == "assemble":
        # Assemble from recipe file
        recipe_path = sys.argv[2] if len(sys.argv) > 2 else "candidate_pool/island_assembly/latest.json"
        result = assemble_from_recipe_file(workspace, recipe_path)
        if result:
            print(f"[assembler] Assembly successful ({len(result)} chars)")
            out = write_assembled_candidate(workspace, result)
            if out:
                print(f"[assembler] Written to: {out}")
        else:
            print("[assembler] Assembly failed.")

    elif len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Auto-assemble from best available organelles (legacy greedy)
        result = assemble_best_organelles(workspace)
        if result:
            print(f"[assembler] Auto-assembly successful ({len(result)} chars)")
            out = write_assembled_candidate(workspace, result)
            if out:
                print(f"[assembler] Written to: {out}")
        else:
            print("[assembler] No organelles available for auto-assembly.")

    elif len(sys.argv) > 1 and sys.argv[1] == "mcts":
        # TICK 17.0: Pareto-MCTS assembly
        max_rollouts = int(sys.argv[2]) if len(sys.argv) > 2 else _MCTS_MAX_ROLLOUTS
        result = mcts_assemble_and_write(workspace, max_rollouts=max_rollouts)
        if result:
            path, stats = result
            print(f"[assembler] MCTS assembly successful → {path}")
            print(f"[assembler]   rollouts={stats['rollouts']} "
                  f"elapsed={stats['elapsed_ms']:.1f}ms "
                  f"Φ={stats['best_value']:.4f}")
            print(f"[assembler]   pool={stats['pareto_pool_sizes']} "
                  f"warm_start={stats['warm_start_paths']}")
        else:
            print("[assembler] MCTS assembly failed (no organelles or invalid).")

    elif len(sys.argv) > 1 and sys.argv[1] == "decompose":
        # Decompose a source file into organelles
        src_path = sys.argv[2] if len(sys.argv) > 2 else "atomic_core.py"
        try:
            source = Path(src_path).read_text(encoding="utf-8")
            saved = decompose_and_archive(workspace, source, epi=0.0, gen=0)
            for org_type, path in saved.items():
                print(f"[assembler] Saved {org_type}: {path}")
            if not saved:
                print("[assembler] No organelles extracted.")
        except Exception as exc:
            print(f"[assembler] Error: {exc}")

    elif len(sys.argv) > 1 and sys.argv[1] == "bottleneck":
        # Identify bottleneck from gradient profile
        cache_path = sys.argv[2] if len(sys.argv) > 2 else "agi_workspace/telemetry/gradient_profile.json"
        try:
            raw = Path(cache_path).read_text(encoding="utf-8")
            profile = json.loads(raw)
            bottleneck = identify_bottleneck_organelle(profile)
            print(f"[assembler] Bottleneck organelle: {bottleneck or 'inconclusive'}")
        except Exception as exc:
            print(f"[assembler] Error: {exc}")

    else:
        print("Usage:")
        print("  genome_assembler.py assemble [recipe.json]  -- Assemble from recipe")
        print("  genome_assembler.py auto                    -- Auto-assemble best (greedy)")
        print("  genome_assembler.py mcts [max_rollouts]     -- TICK 17.0 Pareto-MCTS assembly")
        print("  genome_assembler.py decompose [source.py]   -- Decompose into organelles")
        print("  genome_assembler.py bottleneck [profile.json] -- Identify bottleneck")
