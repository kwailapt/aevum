#!/usr/bin/env python3
"""mutator_daemon.py -- The Slow Loop.

TICK 6.1: Meta-Evolutionary Singularity + TICK 6.2: Alpha-Matrix Completion.
TICK 7.0: The Shotgun Mutator -- Batch Generation & Multi-Variant Parsing.
TICK 7.1: Deep Mindset Awakening -- Thinking-Claude protocol, crash-log
          injection, <core_thinking_sequence> extraction.
TICK 9.0: World Model & Information Leverage -- Agentic Loop with
          tensor_sandbox probing.  The LLM can issue <action> tool calls
          mid-generation, receive <observation> results, update its belief
          state, and continue reasoning before finalizing variants.
TICK 10.0: Meta-Cognitive Prompt Evolution -- Deep Stagnation Detection
           triggers META_EVOLUTION: the LLM rewrites its own prompt
           (mutation_recipe.py) instead of generating architecture variants.
           Meta-Archive tracks recipe performance and prunes failing frameworks.
TICK 11.0: The Gradient Oracle -- Phenotypic Transparency.  The LLM receives
           structured gradient profiles (per-layer grad norms, expert activation,
           dead neuron ratio, attention entropy).  Agentic tool expansion:
           <action>run_gradient_oracle: [code]</action> for mid-thought probing.
TICK 15.0: The Endosymbiosis -- Modular Composition.  The monolithic candidate
           is decomposed into interchangeable Organelles (attention, routing,
           expert).  Targeted mutation via Gradient Oracle bottleneck analysis.
           Horizontal Gene Transfer via genome assembly.
TICK 16.0: Double-Loop Meta-Governance -- Recipe A/B Testing.  New meta-recipes
           are NOT hot-swapped immediately.  Instead, they generate a shadow
           batch evaluated by the Fast Loop.  Only evidence-based approval
           (shadow fitness > baseline) triggers the hot-swap.
TICK 17.0: Thermodynamic Pareto-MCTS Assembly -- Organelle composition via
           Monte Carlo Tree Search constrained by 80/20 Pareto Policy,
           Free Energy Rate Density Φ Tax, Time Topology Warm-Start,
           and Constitutional Reality Coupling.  The MCTS acts as the
           "Fast Brain" bypassing the heavy LLM for assembly decisions.
TICK 20.1: The Grand Collapse -- Rule-IR Constraint Matrix (gradient meta-evo
           replaces text rewriting, eliminating semantic hallucination),
           Teleological Attractor (future-guided MCTS with distance-to-
           perfection penalty), Φ Governor (expansion/contraction of the
           unified computation graph), Autopoietic Core integration hooks.
TICK 21.4: Tri-Brain Architecture & Thermodynamic API Constraints --
           Refactored Dual-Brain into 3-tier cognitive hierarchy:
           Tier 1 Fast Brain (qwen2.5-coder:7b),
           Tier 2 Slow Brain (qwen3.5:35b-a3b),
           Tier 3 Ascended Oracle (cloud frontier models via oracle_gateway.py).
           Injected physical safety valves: num_ctx=8192, num_predict=1024,
           temperature=0.1 into ALL Ollama API payloads.

TICK 21.5: Absolute Thermodynamic Lock --
           Root cause: 35B model defaulting to 262K context, concurrent GPU lock.
           Fix: Every Ollama API payload now carries keep_alive=0 (immediate VRAM
           release after generation), num_ctx=8192 (hard cap — no 262K default),
           num_predict clamped to 1024 at EVERY call site AND in _compute_dynamic_params.
           Applied across: mutator_daemon.py, stateless_tick.py, autopoietic_core.py,
           m1_ab_test.py. Zero exceptions. Zero fallback paths that bypass limits.

Independent daemon that monitors evaluator telemetry, detects when
architectural mutation is needed, prompts the 35B model, AST-validates
the result, and atomically writes candidates to the candidate pool.

TICK 6.1 additions:
  - Hot-swappable mutation_recipe.py (meta hot-swap)
  - Meta-fitness aware decision engine (evolvability, velocity)
  - Breeder stagnation escalation handling
  - Recipe self-evolution: LLM can output new recipes

TICK 6.2 additions:
  - Island sampling: cross-pollinate from island_good/island_explore
  - Dynamic compute leverage: scale Ollama parameters by velocity
  - Long-term genetic memory via Island archives

TICK 7.0 additions:
  - Batch generation: LLM generates N distinct variants per prompt
  - Multi-variant parsing via ### VARIANT N ### delimiters
  - Each variant written as candidate_<ts>_v<idx>.py

TICK 7.1 additions:
  - Deep Mindset protocol: LLM outputs <core_thinking_sequence> before code
  - Crash-log injection: recent evaluator errors fed back into the prompt
  - Thinking extraction: <core_thinking_sequence> logged to console, stripped before AST
  - Removed <think> stop sequences to allow deep self-reflection

TICK 9.0 additions:
  - Agentic Loop: LLM outputs <action>run_tensor_sandbox: [code]</action>
  - Daemon pauses generation, executes probe in tensor_sandbox.py
  - Result fed back as <observation>[result]</observation>
  - LLM updates belief state and continues reasoning
  - Multi-turn: up to MAX_AGENTIC_TURNS probes per generation cycle

TICK 10.0 additions:
  - MetaStagnationTracker: counts consecutive zero-improvement mutation batches
  - META_EVOLUTION state: after N flat batches, feed the LLM its own prompt
  - <meta_recipe> extraction: LLM outputs a rewritten mutation_recipe.py
  - Recipe performance tracking: island_meta/recipe_performance.ndjson
  - Meta-Archive pruning: discard failing cognitive frameworks, keep top-K

TICK 11.0 additions:
  - Gradient Oracle: extract_gradient_profile() reads .grad attributes after backward
  - Evaluator writes gradient profile to telemetry/gradient_profile.json on B=1
  - Mutator injects Markdown gradient X-ray into LLM prompt
  - Agentic expansion: <action>run_gradient_oracle: [layer_pattern]</action>
  - _execute_gradient_action() does zero-compute cache lookup (no code exec)
  - _extract_action_tags() returns tagged (tool, code) tuples for dispatch

Usage:
    python mutator_daemon.py [--poll-interval 30]
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import os
import re
import shutil
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fs_bus import FileSystemBus

# ── TICK 8.0: Universal Sensor Bus ──────────────────────────────────────────
from biogeo_probe import get_physics_schema

# ── TICK 24.1: Subprocess Test-Runner (replaces in-process tensor_sandbox) ─
import tempfile

# ── TICK 11.0: Gradient Oracle (Phenotypic Transparency) ──────────────────
from gradient_oracle import (
    query_gradient_cache,
    format_gradient_markdown,
    format_cache_observation,
)

# ── TICK 13.0: Constitution (Immutable Alignment Layer) ────────────────────
from constitution import validate_candidate, validate_meta_recipe, audit_log

# ── TICK 15.0: Genome Assembler (Endosymbiosis -- Modular Composition) ────
from genome_assembler import (
    identify_bottleneck_organelle,
    extract_organelle_source,
    assemble_best_organelles,
    write_assembled_candidate,
    decompose_and_archive,
    sample_best_organelle,
    mcts_assemble_and_write,
    compute_leverage_score,
    classify_candidate,
    ORGANELLE_TYPES,
    ORGANELLE_BASE_DIR,
    ASSEMBLY_DIR,
)

# ── TICK 19.0: DAG Oracle (Topological Reality Check) ─────────────────────
from dag_oracle import (
    gate_fast_brain_variant,
    gate_slow_brain_variant,
    format_oracle_markdown,
)

# ── TICK 20.0: Niche Evolver (Thermodynamic MuZero Niche Construction) ────
from niche_evolver import (
    generate_niche,
    write_niche,
    load_active_niche,
    format_niche_markdown,
    _NICHE_COOLDOWN_S as _NICHE_COOLDOWN_S_DEFAULT,
)

# ── TICK 20.1: Rule-IR Constraint Matrix (The End of Semantic Hallucination) ─
from rule_ir import (
    ConstraintMatrix,
    EpigeneticFailureType,
    load_or_compile_matrix,
    save_matrix,
    override_dynamic_params,
    extract_constraint_gradient,
    build_constraint_meta_prompt,
)

# ── TICK 20.1: Teleological Attractor (Future-Guided MCTS) ──────────────────
from teleological_attractor import (
    AttractorState,
    OrganismState,
    distance_to_attractor,
    format_attractor_markdown,
    get_default_attractor,
)

# ── TICK 20.1: Autopoietic Core (Unified Computation Graph) ────────────────
from autopoietic_core import (
    get_shared_state,
    get_phi_governor,
    run_constraint_meta_evolution,
)

# ── TICK 21.4: Ascended Oracle (Tier 3 Cloud Bridge) ──────────────────────
from oracle_gateway import (
    oracle_available,
    compress_oracle_payload,
    call_oracle_async,
    OracleResult,
)

# ── Shared utilities from stateless_tick ─────────────────────────────────────
from stateless_tick import (
    _ATOMIC_CORE_PATH,
    _LLM_MODEL,
    _LLM_TIMEOUT,
    _LLM_ENDPOINT,
    _llm_call_ollama,
    _extract_nn_architecture,
    _ast_replace_in_source,
)

# ── TICK 22.0: Pydantic Structured Output Schemas ────────────────────────────
from llm_schemas import (
    ArchitectPlan,
    MutationBatch,
    get_instructor_client,
)


# ── Candidate Pool Constants ────────────────────────────────────────────────
_CANDIDATE_DIR: str = "candidate_pool"
_TELEMETRY_PATH: str = "logs/tick_telemetry.ndjson"

# ── TICK 6.2: Island Archive Paths ──────────────────────────────────────────
_ISLAND_GOOD_DIR: str = "candidate_pool/island_good"
_ISLAND_EXPLORE_DIR: str = "candidate_pool/island_explore"
_ISLAND_META_DIR: str = "candidate_pool/island_meta"

# ── TICK 7.1.2: Mutator-specific timeout (Deep Mindset needs minutes, not seconds)
_MUTATOR_LLM_TIMEOUT: int = 1200  # 20 min -- thinking + 3 variants on 35B

# ── TICK 24.1: Tri-Agent Test-Runner Constants ────────────────────────────
# 5.0s allows PyTorch cold-start import (~2-3s) + forward pass.
# subprocess.run kills the process on timeout — catches infinite loops.
_TEST_RUNNER_TIMEOUT_S: float = 5.0  # hard wall for subprocess test-runner

# ── TICK 10.0: Meta-Cognitive Prompt Evolution ────────────────────────────
_META_STAGNATION_BATCHES: int = 5   # consecutive flat batches before META_EVOLUTION
_META_EPI_EPSILON: float = 0.0001   # min improvement to count as "not flat"
_META_RECIPE_PERF_PATH: str = "island_meta/recipe_performance.ndjson"

# ── TICK 16.0: Double-Loop Meta-Governance (Recipe A/B Testing) ──────────
_SHADOW_BATCH_SIZE: int = 2           # smaller batch for shadow trial
_SHADOW_EVAL_WAIT_S: float = 120.0    # min wall-clock seconds to wait for eval
_SHADOW_MIN_TICKS: int = 20           # min ticks since shadow submission
_RECIPE_TRIAL_PATH: str = "telemetry/recipe_trial.json"
_SHADOW_CANDIDATE_PREFIX: str = "candidate_shadow_"

# ── TICK 6.1: Recipe Hot-Swap Paths ─────────────────────────────────────────
_RECIPE_PATH: Path = Path(__file__).resolve().parent / "mutation_recipe.py"
_RECIPE_BASELINE_PATH: Path = Path(__file__).resolve().parent / "mutation_recipe_baseline.py"
_RECIPE_STAGING_DIR: str = "candidate_pool/island_meta"

# ── TICK 6.2: Dynamic Compute Parameters ────────────────────────────────────
# Velocity thresholds (σ-based) for compute scaling
_VELOCITY_EXPLOSION_SIGMA: float = 1.5   # high velocity → exploration mode
_VELOCITY_STALL_SIGMA: float = -0.5      # low velocity → deterministic mode
_VELOCITY_HISTORY_SIZE: int = 20          # window for σ calculation

# ── TICK 18.0: Asymmetric Dual-Brain Engine ──────────────────────────────
# Model routing (override FAST_BRAIN_MODEL via env-var for hardware flexibility)
_FAST_BRAIN_MODEL: str = os.environ.get("FAST_BRAIN_MODEL", "qwen2.5-coder:7b")
# TICK 33.0: Gemma 4 Coronation. _SLOW_BRAIN_MODEL defaults to gemma4:26b.
# Override at runtime via SLOW_BRAIN_MODEL env-var if needed.
_SLOW_BRAIN_MODEL: str = os.environ.get("SLOW_BRAIN_MODEL", "gemma4:26b")
_FAST_BRAIN_TIMEOUT: int = 300                # 5-min hard cap for Fast Brain calls
_FAST_BRAIN_COMPUTE_BUDGET_PCT: float = 0.05  # ≤5% of cumulative compute budget
_FAST_BRAIN_MCTS_PREVIEW_STEPS: int = 100     # Monte Carlo steps for viability gate
_FAST_BRAIN_BUDGET_RESET_INTERVAL: int = 10   # reset Fast Brain budget every N mutations

# Slow Brain awakening thresholds (immutable structural constants)
_SLOW_BRAIN_PHI_DROP_PCT: float = 0.05        # Condition A: >5% Φ drop per gen
_SLOW_BRAIN_PHI_CONSECUTIVE_GENS: int = 5     # Condition A: N consecutive gens required
_SLOW_BRAIN_MDL_BLOAT_PCT: float = 0.02       # Condition B: ≥2% MDL increase
_SLOW_BRAIN_PARETO_TOP_PCT: float = 0.20      # Slow Brain sees only top 20% seeds
_SLOW_BRAIN_TAX_CEILING: float = 0.90         # 90% Thermodynamic Tax rule ceiling
_MAX_CANDIDATE_PARAMS: int = 50_000_000       # Constitutional MAX_PARAMS (50M)

# Tri-brain telemetry paths (TICK 21.4: renamed from dual-brain)
_DUAL_BRAIN_LOG_PATH: str = "logs/dual_brain_events.ndjson"
_SLOW_BRAIN_GAINS_PATH: str = "island_assembly/slow_brain_gains.ndjson"

# ── TICK 21.4: Tier 3 — Ascended Oracle (Cloud Bridge) ──────────────────
# Oracle is invoked ONLY when both local brains have failed/exhausted AND
# the system is in a deep stagnation (both Heat Death + budget exhaustion).
_ORACLE_CONSECUTIVE_LOCAL_FAILURES: int = 3   # trigger after N consecutive local failures
_ORACLE_LOG_PATH: str = "logs/oracle_events.ndjson"

# ── TICK 20.0: Niche Evolver (Thermodynamic MuZero Niche Construction) ────
# Niche generation is triggered ONLY by the Slow Brain on a Heat Death alert.
_NICHE_COOLDOWN_S: float = _NICHE_COOLDOWN_S_DEFAULT  # min seconds between niches
_NICHE_LOG_PATH: str = "logs/niche_evolver_events.ndjson"

# ── TICK 20.1: Rule-IR Constraint Matrix & Teleological Attractor ────────
_CONSTRAINT_MATRIX_PATH: str = "island_meta/constraint_matrix.json"
_RULE_IR_META_EVOLUTION: bool = True  # use constraint gradients instead of text rewrite


# ═══════════════════════════════════════════════════════════════
# RECIPE HOT-SWAP ENGINE (TICK 6.1)
# ═══════════════════════════════════════════════════════════════

def _load_recipe() -> Any:
    """Dynamically load mutation_recipe.py.  Falls back to baseline on failure.

    Validates that all required API symbols are present before accepting.
    """
    try:
        spec = importlib.util.spec_from_file_location("mutation_recipe", str(_RECIPE_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Validate API surface
        required = getattr(mod, "RECIPE_API", set())
        if not required:
            raise AttributeError("RECIPE_API not found")

        for symbol in required:
            if not hasattr(mod, symbol):
                raise AttributeError(f"Missing required symbol: {symbol}")

        return mod

    except Exception as exc:
        print(f"[recipe] Failed to load mutation_recipe.py ({exc}). Reverting to baseline.")
        return _load_baseline_recipe()


def _load_baseline_recipe() -> Any:
    """Load the immutable baseline recipe as fallback."""
    try:
        spec = importlib.util.spec_from_file_location(
            "mutation_recipe_baseline", str(_RECIPE_BASELINE_PATH),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        print(f"[recipe] CRITICAL: Cannot load baseline recipe: {exc}")
        # Return a minimal stub
        return _MinimalRecipeStub()


class _MinimalRecipeStub:
    """Emergency fallback when even the baseline recipe is broken."""
    RECIPE_VERSION = "emergency-stub"
    BATCH_SIZE = 1  # Safe single-variant fallback
    LLM_TEMPERATURE = 0.6
    LLM_TOP_P = 0.95
    LLM_NUM_PREDICT = 2048
    LLM_STOP_SEQUENCES = ["<think>", "</think>"]
    STAGNATION_WINDOW = 50
    STAGNATION_THRESHOLD = 0.001
    MIN_TICKS_BETWEEN = 10
    ZERO_ACCEPT_WINDOW = 20
    EXPLOITATION_EVO_FLOOR = 0.15

    @staticmethod
    def build_system_prompt(**kw): return "Output Python code only. No explanation."
    @staticmethod
    def build_user_prompt(arch_src, threshold, **kw):
        return f"Threshold: {threshold}\n```python\n{arch_src}\n```"
    @staticmethod
    def build_recipe_evolution_prompt(**kw): return ""
    @staticmethod
    def build_meta_reflection_prompt(**kw): return ("Rewrite the recipe.", "")


def _attempt_recipe_hotswap(
    fs: FileSystemBus,
    new_recipe_code: str,
) -> bool:
    """Validate and atomically install a new mutation recipe.

    Steps:
      1. Write to staging .tmp file
      2. Validate via import + API surface check
      3. Atomic rename to mutation_recipe.py
      4. Archive the new recipe to island_meta
    """
    tmp_path = _RECIPE_PATH.parent / ".mutation_recipe_new.py.tmp"
    try:
        # ── TICK 13.0: Constitutional Sentinel for recipe hot-swap ──
        r_ok, r_violations = validate_meta_recipe(new_recipe_code)
        if not r_ok:
            print(f"[recipe] CONSTITUTIONAL VETO: {r_violations}")
            audit_log("VETO_RECIPE_HOTSWAP", {"violations": r_violations})
            return False

        # Write to tmp
        tmp_path.write_text(new_recipe_code, encoding="utf-8")

        # Validate by importing
        spec = importlib.util.spec_from_file_location("_recipe_validate", str(tmp_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Check API surface
        required = getattr(mod, "RECIPE_API", set())
        if not required:
            raise ValueError("No RECIPE_API defined")
        for symbol in required:
            if not hasattr(mod, symbol):
                raise ValueError(f"Missing: {symbol}")

        # Atomic rename
        os.rename(str(tmp_path), str(_RECIPE_PATH))

        # Archive to island_meta
        meta_dir = Path(fs.root) / _ISLAND_META_DIR
        meta_dir.mkdir(parents=True, exist_ok=True)
        version = getattr(mod, "RECIPE_VERSION", "unknown")
        archive_name = f"recipe_{version}_{int(time.time())}.py"
        (meta_dir / archive_name).write_text(new_recipe_code, encoding="utf-8")

        print(f"[recipe] Hot-swapped to version: {version}")
        return True

    except Exception as exc:
        print(f"[recipe] New recipe rejected: {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ═══════════════════════════════════════════════════════════════
# ISLAND SAMPLER (TICK 6.2: Long-Term Genetic Memory)
# ═══════════════════════════════════════════════════════════════

def _safe_mtime(p: Path) -> float:
    """Return mtime or 0.0 if the file vanished (TOCTOU-safe)."""
    try:
        return p.stat().st_mtime
    except (FileNotFoundError, OSError):
        return 0.0


def _safe_read_text(p: Path) -> Optional[str]:
    """Return file text or None if the file vanished (TOCTOU-safe)."""
    try:
        return p.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _sample_island_asts(
    fs: FileSystemBus,
    n_good: int = 1,
    n_explore: int = 1,
) -> Dict[str, List[str]]:
    """Sample elite ASTs from island archives for cross-pollination.

    Returns {"good": [...], "explore": [...]} with raw code strings.
    Every I/O call is guarded against TOCTOU races from the fast-loop
    evaluator deleting files between glob(), stat(), and read().
    """
    import random

    samples: Dict[str, List[str]] = {"good": [], "explore": []}

    for island_dir, key, n in [
        (_ISLAND_GOOD_DIR, "good", n_good),
        (_ISLAND_EXPLORE_DIR, "explore", n_explore),
    ]:
        island_path = Path(fs.root) / island_dir
        if not island_path.exists():
            continue

        # glob -> list snapshot; files may vanish before sort
        try:
            raw_files = list(island_path.glob("elite_*.py"))
        except (FileNotFoundError, OSError):
            continue
        if not raw_files:
            continue

        # Sort by mtime — vanished files get mtime 0.0 (sorted to front, ignored)
        files = sorted(raw_files, key=_safe_mtime)
        # Drop any files that returned mtime 0.0 (already gone)
        files = [f for f in files if _safe_mtime(f) > 0.0]
        if not files:
            continue

        # Sample from recent elites (biased toward newest)
        candidates = files[-min(10, len(files)):]
        chosen = random.sample(candidates, min(n, len(candidates)))

        for f in chosen:
            code = _safe_read_text(f)
            if code is None:
                continue
            # Strip header comment
            lines = code.splitlines()
            if lines and lines[0].startswith("# Island:"):
                code = "\n".join(lines[1:])
            samples[key].append(code.strip())

    return samples


def _build_island_context(island_samples: Dict[str, List[str]]) -> str:
    """Build a cross-pollination context block for the LLM prompt.

    Injects elite ASTs from different islands to enable recombination.
    """
    parts: List[str] = []

    if island_samples.get("good"):
        parts.append(
            "\n--- HIGH-FITNESS ELITE (from island_good, proven architecture) ---\n"
            "Consider incorporating structural elements from this elite:\n"
        )
        # Only include the nn.Module classes, not the full file
        for ast_code in island_samples["good"][:1]:
            parts.append(f"```python\n{ast_code[:2000]}\n```\n")

    if island_samples.get("explore"):
        parts.append(
            "\n--- EXPLORATION SEED (from island_explore, novel structure) ---\n"
            "This variant showed high variance/novelty.  Consider cross-pollinating:\n"
        )
        for ast_code in island_samples["explore"][:1]:
            parts.append(f"```python\n{ast_code[:2000]}\n```\n")

    return "".join(parts)


# ═══════════════════════════════════════════════════════════════
# DYNAMIC COMPUTE LEVERAGE (TICK 6.2: Thermodynamic Justice 2.0)
# ═══════════════════════════════════════════════════════════════

class VelocityTracker:
    """Track improvement velocity for dynamic compute scaling."""

    def __init__(self, window: int = _VELOCITY_HISTORY_SIZE):
        self.velocities: List[float] = []
        self.window = window

    def record(self, velocity: float) -> None:
        self.velocities.append(velocity)
        if len(self.velocities) > self.window:
            self.velocities = self.velocities[-self.window:]

    @property
    def mean(self) -> float:
        if not self.velocities:
            return 0.0
        return sum(self.velocities) / len(self.velocities)

    @property
    def std(self) -> float:
        if len(self.velocities) < 2:
            return 0.01  # avoid division by zero
        m = self.mean
        var = sum((v - m) ** 2 for v in self.velocities) / len(self.velocities)
        return max(var ** 0.5, 0.001)

    @property
    def z_score(self) -> float:
        """Z-score of latest velocity relative to history."""
        if not self.velocities:
            return 0.0
        return (self.velocities[-1] - self.mean) / self.std


# ═══════════════════════════════════════════════════════════════
# META-STAGNATION TRACKER (TICK 10.0: Meta-Cognitive Detection)
# ═══════════════════════════════════════════════════════════════

class MetaStagnationTracker:
    """Track consecutive mutation cycles where best_epi shows zero improvement.

    When best_epi fails to improve for _META_STAGNATION_BATCHES consecutive
    mutation cycles, the tracker triggers META_EVOLUTION — the system
    rewrites its own cognitive framework instead of generating architecture
    variants.
    """

    def __init__(self, trigger_threshold: int = _META_STAGNATION_BATCHES):
        self.trigger_threshold = trigger_threshold
        self.best_epi_high_water: float = 0.0
        self.consecutive_flat: int = 0
        self.meta_evolution_count: int = 0

    def record(self, best_epi: float) -> bool:
        """Record a mutation cycle's best_epi.

        Returns True if META_EVOLUTION should trigger.
        """
        if best_epi > self.best_epi_high_water + _META_EPI_EPSILON:
            self.best_epi_high_water = best_epi
            self.consecutive_flat = 0
            return False
        self.consecutive_flat += 1
        return self.consecutive_flat >= self.trigger_threshold

    def reset(self) -> None:
        """Reset the counter after a META_EVOLUTION cycle."""
        self.consecutive_flat = 0
        self.meta_evolution_count += 1


# ═══════════════════════════════════════════════════════════════
# TICK 18.0: THERMODYNAMIC STATE TRACKERS (Φ & MDL)
# ═══════════════════════════════════════════════════════════════

class PhiTracker:
    """Track Free Energy Rate Density (Φ) to detect Heat Death.

    Condition A — Heat Death: Φ drops >5% from peak for 5 consecutive gens.
    When triggered, the Slow Brain awakens to reinvent the architectural paradigm.

    Φ proxy = best_epi × evolvability_score
    Captures how efficiently the organism converts compute into fitness gain.
    Higher Φ = more information per unit energy.  Sustained decline = Heat Death.
    """

    def __init__(
        self,
        drop_threshold: float = _SLOW_BRAIN_PHI_DROP_PCT,
        consecutive_required: int = _SLOW_BRAIN_PHI_CONSECUTIVE_GENS,
    ) -> None:
        self.drop_threshold = drop_threshold
        self.consecutive_required = consecutive_required
        self.phi_history: List[float] = []
        self.peak_phi: float = 0.0
        self.consecutive_drops: int = 0

    @staticmethod
    def compute_phi(record: Dict[str, Any]) -> float:
        """Compute Φ proxy from a single telemetry record."""
        best_epi = record.get("best_epi", 0.0)
        evolvability = max(record.get("evolvability_score", 0.01), 0.01)
        return best_epi * evolvability

    def record(self, phi: float) -> bool:
        """Record Φ value. Returns True if Heat Death condition A is triggered."""
        self.phi_history.append(phi)
        if len(self.phi_history) > 20:
            self.phi_history = self.phi_history[-20:]

        if phi > self.peak_phi:
            self.peak_phi = phi
            self.consecutive_drops = 0
            return False

        if self.peak_phi > 0:
            drop_pct = (self.peak_phi - phi) / self.peak_phi
            if drop_pct > self.drop_threshold:
                self.consecutive_drops += 1
            else:
                self.consecutive_drops = 0

        return self.consecutive_drops >= self.consecutive_required

    def reset(self) -> None:
        """Reset after Slow Brain paradigm shift; anchor to recent Φ."""
        self.consecutive_drops = 0
        if self.phi_history:
            self.peak_phi = max(self.phi_history[-3:]) if len(self.phi_history) >= 3 \
                else self.phi_history[-1]


class MDLTracker:
    """Track Minimum Description Length to detect Organizational Bloat.

    Condition B — Organizational Bloat: MDL increases ≥2%.
    MDL proxy = avg_elite_file_bytes / best_epi
    When fitness stagnates but code complexity grows, MDL rises → Bloat Alert.
    The Slow Brain then compresses the architecture back toward Occam's Razor.
    """

    def __init__(self, bloat_threshold: float = _SLOW_BRAIN_MDL_BLOAT_PCT) -> None:
        self.bloat_threshold = bloat_threshold
        self.mdl_history: List[float] = []
        self.baseline_mdl: float = 0.0
        self.current_mdl: float = 0.0
        self.bloat_active: bool = False

    def compute_mdl(self, fs: Any, best_epi: float) -> float:
        """Compute MDL from island_good elite pool file sizes and current fitness."""
        island_good = Path(fs.root) / _ISLAND_GOOD_DIR
        if not island_good.exists():
            return 0.0
        try:
            raw = list(island_good.glob("elite_*.py"))
        except (FileNotFoundError, OSError):
            return 0.0
        elite_files = sorted(raw, key=_safe_mtime)[-5:]
        elite_files = [f for f in elite_files if _safe_mtime(f) > 0.0]
        if not elite_files:
            return 0.0
        sizes = []
        for f in elite_files:
            try:
                sizes.append(f.stat().st_size)
            except (FileNotFoundError, OSError):
                continue
        avg_bytes = sum(sizes) / max(len(sizes), 1)
        return avg_bytes / max(best_epi, 1e-4)

    def record(self, mdl: float) -> bool:
        """Record MDL value. Returns True if Organizational Bloat condition B fires."""
        if mdl <= 0.0:
            return False
        self.current_mdl = mdl
        self.mdl_history.append(mdl)
        if len(self.mdl_history) > 10:
            self.mdl_history = self.mdl_history[-10:]

        if self.baseline_mdl == 0.0:
            self.baseline_mdl = mdl
            return False

        bloat_pct = (mdl - self.baseline_mdl) / max(self.baseline_mdl, 1e-6)
        self.bloat_active = bloat_pct >= self.bloat_threshold

        if not self.bloat_active:
            # Ratchet baseline downward — track compression gains
            self.baseline_mdl = min(self.baseline_mdl, mdl)

        return self.bloat_active

    def reset(self) -> None:
        """Reset after Slow Brain paradigm shift; anchor to current best MDL."""
        self.bloat_active = False
        if self.mdl_history:
            self.baseline_mdl = min(self.mdl_history)


class DualBrainRouter:
    """Φ-gated routing across the Tri-Brain cognitive hierarchy.

    TICK 18.0: The Asymmetric Dual-Brain Engine.
    TICK 21.4: Tri-Brain Architecture — added Tier 3 Ascended Oracle.

    Tier 1 — FAST BRAIN (Cerebellum): qwen2.5-coder:7b
      - Always active for routine mutations (breeder_stagnation)
      - Hard constraint: ≤5% of cumulative compute budget
      - Scope: routing tweaks, expert hyperparams only (no structural surgery)
      - Gate: MCTS mini-loop validates local viability before candidate write

    Tier 2 — SLOW BRAIN (Cerebrum): qwen3.5:35b-a3b
      - DORMANT until awakened by thermodynamic triggers
      - Awakening Trigger A (Heat Death): Φ drops >5% × 5 consecutive gens
      - Awakening Trigger B (Org. Bloat): MDL increases ≥2%
      - Mandate: invent new organelles from Pareto Top 20% seeds ONLY
      - 90% Tax Rule: new arch must be ≤90% as computationally expensive

    Tier 3 — ASCENDED ORACLE: frontier cloud model (claude/gpt-4o)
      - Invoked ONLY when local brains fail consecutively
      - Compressed payload: ONLY failing AST + metrics (Φ, D(A*), MDL)
      - Non-blocking: runs in a background thread
      - Graceful fallback to Tier 1/2 if API unavailable
    """

    def __init__(self) -> None:
        self.phi_tracker = PhiTracker()
        self.mdl_tracker = MDLTracker()
        self.slow_brain_active: bool = False
        self.slow_brain_trigger: str = ""      # "heat_death" | "mdl_bloat"
        self.total_compute_s: float = 0.0
        self.fast_brain_compute_s: float = 0.0
        self._budget_counter: int = 0
        # TICK 21.4: Oracle escalation tracking
        self._consecutive_local_failures: int = 0
        self._oracle_pending: Optional[OracleResult] = None
        self._oracle_available: bool = oracle_available()

    def record_local_failure(self) -> None:
        """Record a failed local brain cycle (no usable output)."""
        self._consecutive_local_failures += 1

    def record_local_success(self) -> None:
        """Reset failure counter on any successful local output."""
        self._consecutive_local_failures = 0

    @property
    def should_escalate_to_oracle(self) -> bool:
        """Check if local brains have failed enough to warrant oracle escalation."""
        return (
            self._oracle_available
            and self._consecutive_local_failures >= _ORACLE_CONSECUTIVE_LOCAL_FAILURES
        )

    @property
    def oracle_result_ready(self) -> bool:
        """Check if a pending async oracle result is available."""
        return self._oracle_pending is not None and self._oracle_pending.done

    def update(self, fs: Any, records: List[Dict[str, Any]]) -> None:
        """Update thermodynamic state from latest telemetry and fire awakening triggers."""
        if not records:
            return
        latest = records[-1]
        best_epi = latest.get("best_epi", 0.0)

        phi = PhiTracker.compute_phi(latest)
        mdl = self.mdl_tracker.compute_mdl(fs, best_epi)

        heat_death = self.phi_tracker.record(phi)
        org_bloat = self.mdl_tracker.record(mdl)

        if not self.slow_brain_active:
            if heat_death:
                self.slow_brain_active = True
                self.slow_brain_trigger = "heat_death"
                print(
                    f"\n[dual-brain] {'█'*62}\n"
                    f"[dual-brain] SLOW BRAIN AWAKENED — CONDITION A: HEAT DEATH\n"
                    f"[dual-brain] Φ dropped >{_SLOW_BRAIN_PHI_DROP_PCT*100:.0f}% "
                    f"for {self.phi_tracker.consecutive_drops} consecutive gens\n"
                    f"[dual-brain] Peak Φ={self.phi_tracker.peak_phi:.6f} "
                    f"Current Φ={phi:.6f}\n"
                    f"[dual-brain] {'█'*62}\n"
                )
            elif org_bloat:
                self.slow_brain_active = True
                self.slow_brain_trigger = "mdl_bloat"
                print(
                    f"\n[dual-brain] {'█'*62}\n"
                    f"[dual-brain] SLOW BRAIN AWAKENED — CONDITION B: ORGANIZATIONAL BLOAT\n"
                    f"[dual-brain] MDL increased "
                    f"≥{_SLOW_BRAIN_MDL_BLOAT_PCT*100:.0f}% "
                    f"(baseline={self.mdl_tracker.baseline_mdl:.1f} "
                    f"current={mdl:.1f})\n"
                    f"[dual-brain] {'█'*62}\n"
                )

    def fast_brain_within_budget(self) -> bool:
        """Check if Fast Brain LLM call is within the 5% compute budget ceiling."""
        if self.total_compute_s < 10.0:
            return True  # No meaningful history yet
        budget_ceiling = self.total_compute_s * _FAST_BRAIN_COMPUTE_BUDGET_PCT
        return self.fast_brain_compute_s < budget_ceiling

    def record_cost(self, elapsed_s: float, is_fast_brain: bool) -> None:
        """Record LLM compute cost.  Resets Fast Brain budget every N mutations."""
        self.total_compute_s += elapsed_s
        if is_fast_brain:
            self.fast_brain_compute_s += elapsed_s
        self._budget_counter += 1
        if self._budget_counter >= _FAST_BRAIN_BUDGET_RESET_INTERVAL:
            # Rolling window: prevent permanent Fast Brain lockout
            self.fast_brain_compute_s = 0.0
            self._budget_counter = 0

    def reset_slow_brain(self) -> None:
        """Return Slow Brain to dormant state after a successful paradigm shift."""
        prev_trigger = self.slow_brain_trigger
        self.slow_brain_active = False
        self.slow_brain_trigger = ""
        self.phi_tracker.reset()
        self.mdl_tracker.reset()
        print(f"[dual-brain] Slow Brain → DORMANT (resolved trigger: {prev_trigger})")

    @property
    def state_summary(self) -> str:
        brain = "SLOW" if self.slow_brain_active else "FAST"
        return (
            f"brain={brain} "
            f"phi_drops={self.phi_tracker.consecutive_drops}/"
            f"{_SLOW_BRAIN_PHI_CONSECUTIVE_GENS} "
            f"peak_phi={self.phi_tracker.peak_phi:.4f} "
            f"mdl_bloat={self.mdl_tracker.bloat_active} "
            f"trigger='{self.slow_brain_trigger}' "
            f"fast_budget={self.fast_brain_compute_s:.1f}/"
            f"{self.total_compute_s * _FAST_BRAIN_COMPUTE_BUDGET_PCT:.1f}s"
        )


def _compute_dynamic_params(
    recipe: Any,
    velocity_z: float,
    evolvability: float,
) -> Dict[str, Any]:
    """Scale LLM generation parameters based on evolutionary velocity.

    High velocity (z > 1.5σ): evolutionary explosion → explore harder
      - Higher temperature, more tokens, wider search
    Stalled (z < -0.5σ): stagnation → deterministic refinement
      - Lower temperature, constrained output
    Normal: use recipe defaults
    """
    base_temp = getattr(recipe, "LLM_TEMPERATURE", 0.6)
    base_top_p = getattr(recipe, "LLM_TOP_P", 0.95)
    base_num_predict = getattr(recipe, "LLM_NUM_PREDICT", 2048)

    if velocity_z > _VELOCITY_EXPLOSION_SIGMA:
        # Evolutionary explosion — push exploration
        temp = min(1.2, base_temp * 1.5)
        top_p = min(0.99, base_top_p * 1.05)
        num_predict = min(4096, int(base_num_predict * 1.5))
        mode = "EXPLORATION_BURST"
    elif velocity_z < _VELOCITY_STALL_SIGMA:
        # Stalled — deterministic, surgical
        temp = max(0.15, base_temp * 0.4)
        top_p = max(0.7, base_top_p * 0.85)
        num_predict = max(1024, int(base_num_predict * 0.7))
        mode = "DETERMINISTIC_REFINE"
    else:
        # Normal — use recipe defaults
        temp = base_temp
        top_p = base_top_p
        num_predict = base_num_predict
        mode = "BALANCED"

    # Evolvability override: if extremely low, force exploration
    if evolvability < 0.1 and mode != "EXPLORATION_BURST":
        temp = min(1.0, temp * 1.3)
        mode = "LOW_EVO_OVERRIDE"

    # TICK 21.5: Hard clamp — no caller may exceed the thermodynamic ceiling
    num_predict = min(num_predict, 1024)

    return {
        "temperature": round(temp, 3),
        "top_p": round(top_p, 3),
        "num_predict": num_predict,
        "mode": mode,
    }


# ═══════════════════════════════════════════════════════════════
# TELEMETRY READER
# ═══════════════════════════════════════════════════════════════

def _read_recent_telemetry(
    fs: FileSystemBus,
    window: int = 50,
) -> List[Dict[str, Any]]:
    """Read the last `window` telemetry records from the evaluator."""
    telemetry_file = Path(fs.root) / _TELEMETRY_PATH
    if not telemetry_file.exists():
        return []

    records: List[Dict[str, Any]] = []
    try:
        with open(telemetry_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    return records[-window:] if records else []


# ═══════════════════════════════════════════════════════════════
# MUTATION DECISION ENGINE (TICK 6.1: Meta-Fitness Aware)
# ═══════════════════════════════════════════════════════════════

def _should_mutate(
    records: List[Dict[str, Any]],
    last_mutation_tick: int,
    recipe: Any,
) -> Tuple[bool, str, float, float, Dict[str, float]]:
    """Analyze evaluator telemetry to decide if a new mutation is needed.

    Returns (should_mutate, reason, threshold, best_epi, meta_fitness).

    TICK 6.1: Now reads evolvability_score, delta_epi, improvement_per_second
    from the enriched telemetry stream.
    """
    meta_fitness: Dict[str, float] = {
        "evolvability_score": 0.0,
        "delta_epi": 0.0,
        "improvement_per_second": 0.0,
        "survival_rate": 0.0,
    }

    if not records:
        return False, "", 0.10, 0.0, meta_fitness

    latest = records[-1]
    current_tick: int = latest.get("tick", 0)
    threshold: float = latest.get("threshold", 0.10)
    best_epi: float = latest.get("best_epi", 0.0)

    # Extract meta-fitness from enriched telemetry
    meta_fitness["evolvability_score"] = latest.get("evolvability_score", 0.0)
    meta_fitness["delta_epi"] = latest.get("delta_epi", 0.0)
    meta_fitness["improvement_per_second"] = latest.get("improvement_per_second", 0.0)
    meta_fitness["survival_rate"] = latest.get("survival_rate", 0.0)

    # Load trigger thresholds from recipe
    stagnation_window = getattr(recipe, "STAGNATION_WINDOW", 50)
    stagnation_threshold = getattr(recipe, "STAGNATION_THRESHOLD", 0.001)
    min_ticks_between = getattr(recipe, "MIN_TICKS_BETWEEN", 10)
    zero_accept_window = getattr(recipe, "ZERO_ACCEPT_WINDOW", 20)

    # Anti-spam gate
    if current_tick - last_mutation_tick < min_ticks_between:
        return False, "", threshold, best_epi, meta_fitness

    # Trigger 0: Breeder stagnation escalation (TICK 6.1)
    if latest.get("breeder_stagnant", False):
        return True, "breeder_stagnation", threshold, best_epi, meta_fitness

    # Trigger 1: Heat death
    if latest.get("heat_death_triggered", 0):
        return True, "heat_death", threshold, best_epi, meta_fitness

    # Trigger 2: Outer loop active
    if latest.get("outer_loop_active", 0):
        return True, "outer_loop", threshold, best_epi, meta_fitness

    # Trigger 3: Epi stagnation (compare window halves)
    if len(records) >= stagnation_window:
        mid = len(records) // 2
        avg_first = sum(r.get("epi", 0) for r in records[:mid]) / mid
        avg_second = sum(r.get("epi", 0) for r in records[mid:]) / (len(records) - mid)
        improvement = avg_second - avg_first

        if improvement < stagnation_threshold:
            return (
                True,
                f"stagnation (delta_epi={improvement:.6f})",
                threshold, best_epi, meta_fitness,
            )

    # Trigger 4: Zero acceptances
    if len(records) >= zero_accept_window:
        tail = records[-zero_accept_window:]
        if sum(1 for r in tail if r.get("B", 0) == 1) == 0:
            return True, "zero_accepts", threshold, best_epi, meta_fitness

    return False, "", threshold, best_epi, meta_fitness


# ═══════════════════════════════════════════════════════════════
# CANDIDATE WRITER (POSIX atomic rename)
# ═══════════════════════════════════════════════════════════════

def _write_candidate(fs: FileSystemBus, code: str, variant_idx: int = 0) -> Optional[Path]:
    """Atomically write a validated candidate to the pool.

    TICK 7.0: variant_idx differentiates batch-generated variants
    within the same LLM call (e.g., candidate_<ts>_v1.py, _v2.py).
    """
    pool_dir = Path(fs.root) / _CANDIDATE_DIR
    pool_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time() * 1000)
    final_path = pool_dir / f"candidate_{timestamp}_v{variant_idx}.py"
    tmp_path = pool_dir / f".candidate_{timestamp}_v{variant_idx}.py.tmp"

    try:
        tmp_path.write_text(code, encoding="utf-8")
        os.rename(str(tmp_path), str(final_path))
        return final_path
    except Exception as exc:
        print(f"[mutator] Failed to write candidate: {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


# ═══════════════════════════════════════════════════════════════
# RECIPE BLOCK EXTRACTOR
# ═══════════════════════════════════════════════════════════════

def _extract_recipe_block(llm_response: str) -> Optional[str]:
    """Extract a mutation_recipe code block from the LLM response.

    Looks for ```mutation_recipe ... ``` fence.
    Returns the code if found, None otherwise.
    """
    pattern = r"```mutation_recipe\s*\n(.*?)```"
    matches = re.findall(pattern, llm_response, re.DOTALL)
    if not matches:
        return None

    # Take the largest block
    code = max(matches, key=len).strip()
    if not code:
        return None

    # Validate it parses
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        return None






# ═══════════════════════════════════════════════════════════════
# CRASH-LOG READER (TICK 7.1: Error-as-Feature Meta-Cognition)
# ═══════════════════════════════════════════════════════════════



def _read_recent_crash_logs(fs: FileSystemBus, max_entries: int = 3) -> str:
    """Read recent evaluator crash logs for injection into the LLM prompt.

    Scans memory/emergency_resets*.json files written by the Evaluator Swarm.
    Returns a formatted string of the most recent crashes, or "" if none.
    """
    crash_dir = Path(fs.root) / "memory"
    if not crash_dir.exists():
        return ""

    crash_entries: List[Dict[str, Any]] = []

    for crash_file in crash_dir.glob("emergency_resets*.json"):
        try:
            raw = crash_file.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict):
                crash_entries.append(data)
            elif isinstance(data, list):
                crash_entries.extend(data)
        except (json.JSONDecodeError, OSError):
            continue

    if not crash_entries:
        return ""

    # Sort by timestamp descending, take most recent
    crash_entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    recent = crash_entries[:max_entries]

    lines: List[str] = []
    for i, entry in enumerate(recent, 1):
        exc_type = entry.get("exception_type", "Unknown")
        exc_msg = entry.get("last_exception", "No message")
        count = entry.get("count", "?")
        lines.append(
            f"  Crash #{i}: {exc_type}: {exc_msg} "
            f"(reset count: {count})"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# GRADIENT PROFILE READER (TICK 11.0: Phenotypic Transparency)
# ═══════════════════════════════════════════════════════════════

def _read_gradient_profile(fs: FileSystemBus) -> str:
    """Read the latest gradient profile written by the evaluator.

    Returns a Markdown-formatted X-ray summary for LLM injection,
    or "" if no profile exists.
    """
    profile_raw = fs.read("telemetry/gradient_profile.json")
    if isinstance(profile_raw, dict):
        return format_gradient_markdown(profile_raw)
    return ""


# ═══════════════════════════════════════════════════════════════
# ENVIRONMENT PROFILE READER (TICK 12.0: Cambrian Engine)
# ═══════════════════════════════════════════════════════════════

_ENV_ACTIVE_FILE: str = "candidate_pool/env_active/current.json"


def _read_environment_profile(fs: FileSystemBus) -> str:
    """Read the active environment genome and format as Markdown for LLM.

    Returns a Markdown block describing the current chaotic environment
    parameters, or "" if no active config exists.
    """
    env_file = Path(fs.root) / _ENV_ACTIVE_FILE
    if not env_file.exists():
        return ""

    try:
        raw = env_file.read_text(encoding="utf-8")
        genome = json.loads(raw)
        if not isinstance(genome, dict):
            return ""
    except (json.JSONDecodeError, OSError):
        return ""

    lines = ["--- ENVIRONMENT GENOME (the world the Creature faces) ---"]
    # Core chaos parameters
    lines.append(f"- **Lorenz ρ**: {genome.get('rho_center', 28.0)}"
                 f" ± {genome.get('rho_range', 4.0)} (regime switch amplitude)")
    lines.append(f"- **Coupling κ**: [{genome.get('coupling_kappa_min', 0.01):.3f}, "
                 f"{genome.get('coupling_kappa_max', 0.12):.3f}] "
                 f"(Lorenz↔Rössler bidirectional)")
    lines.append(f"- **Regime switch freq**: [{genome.get('regime_switch_freq_min', 150)}, "
                 f"{genome.get('regime_switch_freq_max', 300)}] sequences")
    lines.append(f"- **Rössler c**: {genome.get('rossler_c', 5.7)} "
                 f"(chaos intensity)")
    lines.append(f"- **Quantization bins**: {genome.get('quantization_bins', 96)} "
                 f"(token resolution per dimension)")

    # Version and mutation info
    ver = genome.get("version")
    direction = genome.get("mutation_direction", "baseline")
    if ver is not None:
        lines.append(f"- **Genome version**: v{ver} (last mutation: {direction})")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# PHYSICS SCHEMA → MARKDOWN TRANSLATOR (TICK 8.0: Token Economics)
# ═══════════════════════════════════════════════════════════════

def _physics_to_markdown(schema: dict) -> str:
    """Translate a nested physics schema dict into a clean Markdown KV list.

    Crucial Token Economics: Markdown costs fewer tokens than raw JSON
    and improves LLM reasoning about physical constraints.

    Example output:
      - **Memory / Total Gb**: 128.0
      - **Compute / Cpu Cores**: 20
    """
    lines: List[str] = []

    def _flatten(d: dict, prefix: str = "") -> None:
        for key, value in d.items():
            label = f"{prefix} / {key}" if prefix else key
            if isinstance(value, dict):
                _flatten(value, label)
            else:
                human_label = label.replace("_", " ").title()
                if isinstance(value, float):
                    lines.append(f"- **{human_label}**: {value:.1f}")
                else:
                    lines.append(f"- **{human_label}**: {value}")

    _flatten(schema)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# META-COGNITIVE PROMPT EVOLUTION (TICK 10.0)
# ═══════════════════════════════════════════════════════════════

_META_RECIPE_RE = re.compile(
    r"<meta_recipe>(.*?)</meta_recipe>",
    re.DOTALL,
)


def _extract_meta_recipe(llm_response: str) -> Optional[str]:
    """Extract <meta_recipe>...</meta_recipe> block from LLM response.

    Returns the recipe source code if found and valid Python, None otherwise.
    """
    match = _META_RECIPE_RE.search(llm_response)
    if not match:
        return None

    code = match.group(1).strip()
    if not code:
        return None

    try:
        ast.parse(code)
    except SyntaxError as exc:
        print(f"[meta] Extracted <meta_recipe> has SyntaxError: {exc}")
        return None

    # ── TICK 13.0: Constitutional Sentinel for meta-recipes ────────
    ok, violations = validate_meta_recipe(code)
    if not ok:
        print(f"[meta] CONSTITUTIONAL VETO on meta_recipe: {violations}")
        audit_log("VETO_META_RECIPE", {"violations": violations})
        return None

    return code


def _build_failure_summary(records: List[Dict[str, Any]], window: int = 20) -> str:
    """Build a concise failure summary from recent telemetry for meta-reflection.

    Shows the stagnation pattern: best_epi flatline, rejection rates, etc.
    """
    if not records:
        return "No telemetry available."

    tail = records[-window:]
    lines: List[str] = []

    epis = [r.get("best_epi", 0.0) for r in tail]
    epi_min, epi_max = min(epis), max(epis)
    lines.append(
        f"  Last {len(tail)} ticks: best_epi range [{epi_min:.4f}, {epi_max:.4f}] "
        f"(delta={epi_max - epi_min:.6f})"
    )

    # Count acceptances vs rejections
    accepts = sum(1 for r in tail if r.get("B", 0) == 1)
    lines.append(f"  Acceptances: {accepts}/{len(tail)} ({100 * accepts / len(tail):.0f}%)")

    # Heat death triggers
    heat_deaths = sum(1 for r in tail if r.get("heat_death_triggered", 0))
    if heat_deaths:
        lines.append(f"  Heat deaths: {heat_deaths}")

    # Evolvability trend
    evos = [r.get("evolvability_score", 0.0) for r in tail if "evolvability_score" in r]
    if evos:
        lines.append(f"  Evolvability: mean={sum(evos)/len(evos):.4f}, latest={evos[-1]:.4f}")

    return "\n".join(lines)


def _track_recipe_performance(
    fs: FileSystemBus,
    recipe_version: str,
    best_epi: float,
    delta_epi: float,
) -> None:
    """Append a performance record for the current recipe version.

    Builds island_meta/recipe_performance.ndjson over time so the
    meta-reflection prompt can show the LLM which frameworks worked.
    """
    record = {
        "recipe_version": recipe_version,
        "best_epi": best_epi,
        "delta_epi": delta_epi,
        "t": time.time(),
    }
    fs.append(_META_RECIPE_PERF_PATH, record)


def _load_recipe_performance_history(fs: FileSystemBus, max_entries: int = 20) -> str:
    """Load recipe performance history as a formatted string for the LLM.

    Groups records by recipe_version and summarizes each version's tenure.
    """
    perf_file = Path(fs.root) / _META_RECIPE_PERF_PATH
    if not perf_file.exists():
        return ""

    records: List[Dict[str, Any]] = []
    try:
        with open(perf_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return ""

    if not records:
        return ""

    # Group by recipe_version
    versions: Dict[str, List[Dict[str, Any]]] = {}
    for r in records[-max_entries * 5:]:  # read a wider window
        v = r.get("recipe_version", "unknown")
        versions.setdefault(v, []).append(r)

    lines: List[str] = []
    for version, recs in versions.items():
        epis = [r.get("best_epi", 0.0) for r in recs]
        deltas = [r.get("delta_epi", 0.0) for r in recs]
        best = max(epis) if epis else 0.0
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        lines.append(
            f"  Recipe '{version}': {len(recs)} cycles, "
            f"peak_epi={best:.4f}, avg_delta={avg_delta:.6f}"
        )

    return "\n".join(lines[-max_entries:])


# ═══════════════════════════════════════════════════════════════
# RECIPE A/B TESTING (TICK 16.0: Double-Loop Meta-Governance)
# ═══════════════════════════════════════════════════════════════

class RecipeTrial:
    """State machine for A/B testing a candidate recipe before hot-swap.

    TICK 16.0: When a new <meta_recipe> is generated, it is NOT immediately
    installed.  Instead, it enters a trial:

      STAGING → SHADOW_PENDING → EVALUATING → APPROVED / REJECTED

    The trial recipe generates a small "shadow batch" of candidates.
    The Evaluator tests them normally.  The Mutator observes whether
    those candidates performed better than the incumbent recipe's baseline.
    Only then is the recipe hot-swapped.
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.trial_id: str = ""
        self.recipe_code: str = ""
        self.recipe_staging_path: Optional[Path] = None
        self.shadow_files: List[str] = []       # candidate filenames written
        self.baseline_best_epi: float = 0.0
        self.baseline_avg_epi: float = 0.0
        self.t_start: float = 0.0
        self.tick_at_start: int = 0
        self.last_rejection_reason: str = ""    # fed back to LLM on next meta-evo

    def start_trial(
        self,
        trial_id: str,
        recipe_code: str,
        staging_path: Path,
        baseline_best_epi: float,
        baseline_avg_epi: float,
        current_tick: int,
    ) -> None:
        self.active = True
        self.trial_id = trial_id
        self.recipe_code = recipe_code
        self.recipe_staging_path = staging_path
        self.shadow_files = []
        self.baseline_best_epi = baseline_best_epi
        self.baseline_avg_epi = baseline_avg_epi
        self.t_start = time.time()
        self.tick_at_start = current_tick
        self.last_rejection_reason = ""

    def reset(self) -> None:
        self.active = False
        self.trial_id = ""
        self.recipe_code = ""
        self.recipe_staging_path = None
        self.shadow_files = []
        self.baseline_best_epi = 0.0
        self.baseline_avg_epi = 0.0
        self.t_start = 0.0
        self.tick_at_start = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "trial_id": self.trial_id,
            "shadow_files": self.shadow_files,
            "baseline_best_epi": self.baseline_best_epi,
            "baseline_avg_epi": self.baseline_avg_epi,
            "t_start": self.t_start,
            "tick_at_start": self.tick_at_start,
        }



def _load_recipe_from_path(path: Path) -> Optional[Any]:
    """Load a recipe module from an arbitrary file path.

    Used to temporarily load a trial recipe for shadow batch generation.
    Returns the module, or None on failure.
    """
    try:
        spec = importlib.util.spec_from_file_location("_trial_recipe", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        required = getattr(mod, "RECIPE_API", set())
        if not required:
            return None
        for symbol in required:
            if not hasattr(mod, symbol):
                return None
        return mod
    except Exception as exc:
        print(f"[trial] Failed to load trial recipe: {exc}")
        return None


def _stage_trial_recipe(
    fs: FileSystemBus,
    recipe_code: str,
    trial_id: str,
) -> Optional[Path]:
    """Save a candidate recipe to staging for shadow evaluation.

    Returns the staging file path, or None on failure.
    """
    # Validate first
    r_ok, r_violations = validate_meta_recipe(recipe_code)
    if not r_ok:
        print(f"[trial] CONSTITUTIONAL VETO: {r_violations}")
        audit_log("VETO_TRIAL_RECIPE", {"trial_id": trial_id, "violations": r_violations})
        return None

    staging_dir = Path(fs.root) / _ISLAND_META_DIR
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f"recipe_trial_{trial_id}.py"

    try:
        staging_path.write_text(recipe_code, encoding="utf-8")
    except OSError as exc:
        print(f"[trial] Failed to write staging recipe: {exc}")
        return None

    # Validate it loads
    mod = _load_recipe_from_path(staging_path)
    if mod is None:
        staging_path.unlink(missing_ok=True)
        print(f"[trial] Staging recipe failed import validation.")
        return None

    return staging_path


def _write_shadow_candidate(
    fs: FileSystemBus,
    code: str,
    trial_id: str,
    variant_idx: int,
) -> Optional[Path]:
    """Write a shadow candidate with trial-tagged filename.

    Shadow candidates follow naming: candidate_shadow_<trial_id>_v<N>.py
    The Evaluator picks them up normally (they match candidate_*.py glob).
    """
    pool_dir = Path(fs.root) / _CANDIDATE_DIR
    pool_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time() * 1000)
    filename = f"{_SHADOW_CANDIDATE_PREFIX}{trial_id}_{timestamp}_v{variant_idx}.py"
    final_path = pool_dir / filename
    tmp_path = pool_dir / f".{filename}.tmp"

    try:
        tmp_path.write_text(code, encoding="utf-8")
        os.rename(str(tmp_path), str(final_path))
        return final_path
    except Exception as exc:
        print(f"[trial] Failed to write shadow candidate: {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _generate_shadow_batch(
    fs: FileSystemBus,
    trial: RecipeTrial,
    arch_src: str,
    full_source: str,
    threshold: float,
    best_epi: float,
    meta_fitness: Dict[str, float],
    physics_md: str = "",
    gradient_md: str = "",
    env_md: str = "",
    crash_context: str = "",
) -> int:
    """Generate a small shadow batch using the trial recipe.

    Loads the trial recipe temporarily, generates candidates via the
    standard LLM call pipeline, and writes them with shadow tags.

    Returns the number of shadow candidates written.
    """
    import urllib.request

    trial_recipe = _load_recipe_from_path(trial.recipe_staging_path)
    if trial_recipe is None:
        print("[trial] Cannot load trial recipe for shadow batch.")
        return 0

    trial_version = getattr(trial_recipe, "RECIPE_VERSION", "unknown")
    print(f"[trial] Generating shadow batch with trial recipe '{trial_version}'")

    # Use balanced compute params for fair comparison
    dynamic_params = {
        "temperature": getattr(trial_recipe, "LLM_TEMPERATURE", 0.6),
        "top_p": getattr(trial_recipe, "LLM_TOP_P", 0.95),
        "num_predict": min(getattr(trial_recipe, "LLM_NUM_PREDICT", 1024), 1024),
        "mode": "SHADOW_TRIAL",
    }

    # TICK 24.1: Use tri-agent pipeline for shadow batch generation
    # Identify bottleneck organelle for targeted mutation
    from genome_assembler import identify_bottleneck_organelle, extract_organelle_source
    grad_profile = _read_gradient_profile_raw(fs)
    bottleneck = identify_bottleneck_organelle(grad_profile) if grad_profile else None
    if bottleneck is None:
        bottleneck = "routing"  # default target
    organelle_src = extract_organelle_source(full_source, bottleneck)
    if organelle_src is None:
        print("[trial] Cannot extract organelle for shadow batch.")
        return 0
    class_name = ORGANELLE_TYPES[bottleneck]["class_name"]

    try:
        variants = _tri_agent_pipeline(
            fs=fs,
            organelle_src=organelle_src,
            class_name=class_name,
            organelle_type=bottleneck,
            meta_fitness=meta_fitness,
            dynamic_params=dynamic_params,
            recipe=trial_recipe,
            gradient_md=gradient_md,
            crash_context=crash_context,
        )
    except Exception as exc:
        print(f"[trial] Shadow batch tri-agent error: {type(exc).__name__}: {exc}")
        return 0

    if not variants:
        print("[trial] Shadow batch: no validated variants from tri-agent pipeline.")
        return 0

    # Limit to _SHADOW_BATCH_SIZE
    variants = variants[:_SHADOW_BATCH_SIZE]

    n_written = 0
    for vi, variant_code in enumerate(variants):
        patched = _ast_replace_in_source(full_source, variant_code)
        if patched is None:
            continue

        written = _write_shadow_candidate(
            fs, variant_code, trial.trial_id, vi + 1,
        )
        if written:
            trial.shadow_files.append(written.name)
            n_written += 1
            print(f"[trial] Shadow variant {vi + 1}: {written.name}")

    return n_written



def _check_shadow_results(
    fs: FileSystemBus,
    trial: RecipeTrial,
    current_tick: int,
) -> Optional[Tuple[bool, str]]:
    """Check if shadow candidates have been processed and decide approve/reject.

    Returns (approved, reason) if a decision can be made, None if still waiting.

    Decision criteria:
      - All shadow candidates must be processed (not in pool or .processing)
      - Wait minimum time (_SHADOW_EVAL_WAIT_S) and ticks (_SHADOW_MIN_TICKS)
      - Count how many shadow candidates landed in applied/ (B=1 acceptance)
      - Compare shadow acceptance rate vs baseline
      - Compare post-shadow best_epi vs pre-shadow best_epi
    """
    if not trial.shadow_files:
        return False, "No shadow candidates were generated"

    elapsed_s = time.time() - trial.t_start
    elapsed_ticks = current_tick - trial.tick_at_start

    # Minimum wait before checking
    if elapsed_s < _SHADOW_EVAL_WAIT_S and elapsed_ticks < _SHADOW_MIN_TICKS:
        return None  # Still waiting

    pool_dir = Path(fs.root) / _CANDIDATE_DIR
    applied_dir = Path(fs.root) / "candidate_pool" / "applied"

    # Check processing state of each shadow candidate
    n_pending = 0
    n_accepted = 0
    n_rejected = 0

    for fname in trial.shadow_files:
        in_pool = (pool_dir / fname).exists()
        in_processing = (pool_dir / (fname + ".processing")).exists()
        # Strip .processing suffix when checking applied
        base_name = fname.replace(".processing", "")
        in_applied = (applied_dir / base_name).exists()

        if in_pool or in_processing:
            n_pending += 1
        elif in_applied:
            n_accepted += 1
        else:
            n_rejected += 1  # Deleted = failed validation or AST patch

    total = len(trial.shadow_files)

    # If still pending and we haven't waited long enough, keep waiting
    if n_pending > 0:
        # Hard timeout: if we've waited >5min, count pending as rejected
        if elapsed_s < 300.0:
            return None  # Still waiting
        else:
            n_rejected += n_pending
            n_pending = 0

    # All shadow candidates processed -- make decision
    acceptance_rate = n_accepted / max(total, 1)

    # Read current best_epi from telemetry
    records = _read_recent_telemetry(fs, window=10)
    current_best_epi = 0.0
    if records:
        current_best_epi = records[-1].get("best_epi", 0.0)

    epi_improved = current_best_epi > trial.baseline_best_epi

    print(f"[trial] Shadow results: {n_accepted}/{total} accepted "
          f"({acceptance_rate:.0%}), epi {trial.baseline_best_epi:.4f} → "
          f"{current_best_epi:.4f}")

    # Acceptance condition: at least one shadow candidate accepted AND
    # (epi improved OR acceptance rate > 0)
    if n_accepted > 0 and (epi_improved or acceptance_rate > 0):
        return True, (
            f"Shadow batch: {n_accepted}/{total} accepted, "
            f"epi {trial.baseline_best_epi:.4f}→{current_best_epi:.4f}"
        )

    # Rejection: no shadow candidates survived
    reason = (
        f"Shadow batch FAILED: {n_accepted}/{total} accepted "
        f"({n_rejected} rejected), "
        f"epi {trial.baseline_best_epi:.4f}→{current_best_epi:.4f}"
    )
    return False, reason


def _persist_trial_state(fs: FileSystemBus, trial: RecipeTrial) -> None:
    """Write trial state to disk for crash recovery."""
    fs.write(_RECIPE_TRIAL_PATH, trial.to_dict())


def _clear_trial_state(fs: FileSystemBus) -> None:
    """Remove trial state file."""
    trial_path = Path(fs.root) / _RECIPE_TRIAL_PATH
    trial_path.unlink(missing_ok=True)


def _run_meta_evolution(
    fs: FileSystemBus,
    recipe: Any,
    records: List[Dict[str, Any]],
    meta_tracker: MetaStagnationTracker,
    meta_fitness: Dict[str, float],
    recipe_trial: Optional[RecipeTrial] = None,
    constraint_matrix: Optional[ConstraintMatrix] = None,
) -> bool:
    """Execute a META_EVOLUTION cycle via Rule-IR Constraint Gradient.

    TICK 20.1: The LLM outputs GRADIENT UPDATES to the Constraint Matrix
    instead of rewriting English text.  This eliminates semantic hallucination.

    TICK 29.0+: Text-based recipe rewriting has been permanently removed.
    If gradient extraction fails, meta-evolution simply defers to the next
    stagnation trigger — no fallback to English prompt rewriting.

    Returns True if constraint gradient was successfully applied.
    """

    print(f"\n{'═'*70}")
    print(f"[meta] ████ META-EVOLUTION TRIGGERED ████")
    print(f"[meta] Consecutive flat batches: {meta_tracker.consecutive_flat}")
    print(f"[meta] Meta-evolution count: {meta_tracker.meta_evolution_count + 1}")

    # ── TICK 20.1: Rule-IR Gradient Path (preferred) ─────────────────────
    if _RULE_IR_META_EVOLUTION and constraint_matrix is not None:
        print(f"[meta] MODE: Rule-IR Constraint Gradient (TICK 20.1)")
        print(f"[meta] Current matrix: v{constraint_matrix.version}")
        print(f"[meta] The LLM will output gradient updates, NOT English text.")

        failure_summary = _build_failure_summary(records)
        perf_history = _load_recipe_performance_history(fs)
        _workspace_root = str(Path(fs.root).resolve())

        applied = run_constraint_meta_evolution(
            workspace=_workspace_root,
            cm=constraint_matrix,
            failure_summary=failure_summary,
            perf_history=perf_history,
        )

        if applied is not None:
            fs.append("logs/mutator_events.ndjson", {
                "mutation": "meta_evolution_constraint_gradient",
                "meta_evolution_count": meta_tracker.meta_evolution_count + 1,
                "applied_gradients": applied,
                "matrix_version": constraint_matrix.version,
                "projected": constraint_matrix.project_all(),
                "t": time.time(),
            })
            print(f"[meta] ████ CONSTRAINT MATRIX EVOLVED ████")
            print(f"[meta] v{constraint_matrix.version}: {applied}")
            print(f"{'═'*70}\n")
            return True
        else:
            print(f"[meta] Rule-IR gradient path failed. No text fallback — "
                  f"meta-evolution deferred to next stagnation trigger.")
            print(f"{'═'*70}\n")
            return False

    # If gradient path not available (no matrix), fail
    print(f"[meta] No constraint matrix available. Meta-evolution skipped.")
    print(f"{'═'*70}\n")
    return False


# ═══════════════════════════════════════════════════════════════
# TARGETED MUTATION (TICK 15.0: Endosymbiosis -- Surgical Strike)
# ═══════════════════════════════════════════════════════════════

def _read_gradient_profile_raw(fs: FileSystemBus) -> Dict[str, Any]:
    """Read the raw gradient profile dict (not formatted as Markdown).

    Returns the profile dict, or {} if unavailable.
    """
    profile_raw = fs.read("telemetry/gradient_profile.json")
    if isinstance(profile_raw, dict):
        return profile_raw
    return {}


def _attempt_targeted_mutation(
    fs: FileSystemBus,
    full_source: str,
    threshold: float,
    best_epi: float,
    recipe: Any,
    meta_fitness: Dict[str, float],
    dynamic_params: Dict[str, Any],
    crash_context: str = "",
    physics_profile: str = "",
    gradient_md: str = "",
    environment_profile: str = "",
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """Attempt a TARGETED mutation on a single bottleneck organelle.

    TICK 15.0: Instead of giving the LLM the entire architecture, identify
    the bottleneck organelle via Gradient Oracle analysis and provide ONLY
    that organelle's source code for mutation.  The rest of the assembly
    is kept fixed.

    Returns (n_written, probe_stats) if targeted mutation succeeded,
    None if targeted mutation is not applicable (fall through to full mutation).
    """
    # 1. Read raw gradient profile for bottleneck analysis
    grad_profile = _read_gradient_profile_raw(fs)
    if not grad_profile:
        return None  # No gradient data -- cannot target

    # 2. Identify bottleneck organelle
    bottleneck = identify_bottleneck_organelle(grad_profile)
    if bottleneck is None:
        return None  # Inconclusive -- fall through to full mutation

    # 3. Extract the bottleneck organelle's source from current architecture
    organelle_src = extract_organelle_source(full_source, bottleneck)
    if organelle_src is None:
        return None  # Class not found -- fall through

    organelle_spec = ORGANELLE_TYPES[bottleneck]
    class_name = organelle_spec["class_name"]

    print(f"[mutator] TICK 15.0 TARGETED MUTATION: bottleneck={bottleneck} "
          f"class={class_name}")
    print(f"[mutator] Only the {bottleneck} organelle will be mutated. "
          f"Other components are FIXED.")

    # 4. Build a targeted prompt that only includes the bottleneck organelle
    import urllib.request

    evolvability = meta_fitness.get("evolvability_score", 0.0)
    velocity = meta_fitness.get("improvement_per_second", 0.0)
    delta_epi = meta_fitness.get("delta_epi", 0.0)

    batch_size = getattr(recipe, 'BATCH_SIZE', 3)

    # TICK 22.2: Pure single-turn system prompt — NO recipe.build_system_prompt().
    # The recipe injects tensor_sandbox / gradient_oracle tool docs and <action>
    # tag instructions, causing the LLM to emit XML instead of strict JSON.
    # This prompt is 100% tool-free and JSON-only.
    gradient_block = ""
    if gradient_md:
        gradient_block = (
            f"\n--- GRADIENT ORACLE PROFILE (read-only context) ---\n"
            f"{gradient_md}\n"
        )
    crash_block = ""
    if crash_context:
        crash_block = (
            f"\n--- RECENT CRASH LOG ---\n"
            f"{crash_context}\n"
        )
    physics_block = ""
    if physics_profile:
        physics_block = (
            f"\n--- PHYSICS PROFILE ---\n"
            f"{physics_profile}\n"
        )
    environment_block = ""
    if environment_profile:
        environment_block = (
            f"\n--- ENVIRONMENT PROFILE ---\n"
            f"{environment_profile}\n"
        )

    system_prompt = (
        "You are a Neural Architecture Search engine.\n\n"
        f"{crash_block}{gradient_block}{physics_block}{environment_block}"
        f"═══ TARGETED MUTATION MODE ═══\n"
        f"The Gradient Oracle has identified the **{bottleneck}** organelle "
        f"(class `{class_name}`) as the evolutionary bottleneck.\n\n"
        f"You MUST ONLY rewrite the `{class_name}` class. "
        f"Do NOT modify any other class.\n"
        f"The rest of the architecture is FIXED and will be preserved.\n\n"
        f"Organelle Interface Contract:\n"
        f"  Input:  {organelle_spec['input_spec']}\n"
        f"  Output: {organelle_spec['output_spec']}\n"
        f"  Class name MUST remain: `{class_name}`\n"
        f"  __init__ signature and forward() return shape MUST be preserved.\n\n"
        f"Produce {batch_size} structurally distinct variants.\n\n"
        "CRITICAL STRUCTURAL RULE: If you are mutating a PyTorch nn.Module "
        f"(like {class_name}), your python_code MUST contain both the "
        "__init__ and forward functions. The system will crash if forward "
        "is missing.\n\n"
        f"python_code MUST contain a COMPLETE, valid Python class `{class_name}` "
        "with both __init__ and forward methods fully implemented.\n"
        "Do NOT use ellipses (...) or comments like '# rest of code'.\n"
        "Use \\n for newlines within the python_code string.\n"
    )

    user_prompt = (
        f"--- TARGETED ORGANELLE: {bottleneck} ({class_name}) ---\n"
        f"```python\n{organelle_src}\n```\n\n"
        f"--- EVOLUTIONARY TELEMETRY ---\n"
        f"  threshold: {threshold:.4f}\n"
        f"  best_epi: {best_epi:.4f}\n"
        f"  delta_epi: {delta_epi:.6f}\n"
        f"  evolvability: {evolvability:.4f}\n"
        f"  velocity: {velocity:.6f}\n\n"
        f"Rewrite ONLY the `{class_name}` class. Produce {batch_size} variants."
    )

    # 5. Call LLM via Instructor (TICK 22.6)
    # Instructor handles schema injection, validation, and auto-retries.
    t_start = time.time()
    try:
        client = get_instructor_client()
        result = client.chat.completions.create(
            model=_LLM_MODEL,
            response_model=MutationBatch,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
            temperature=0.1,
            # TICK 21.4/21.5: Thermodynamic API Constraints.
            extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}},
        )
    except Exception as exc:
        t_elapsed = time.time() - t_start
        print(f"[mutator] Targeted mutation Instructor error after {t_elapsed:.1f}s: "
              f"{type(exc).__name__}: {exc}")
        return None

    t_elapsed = time.time() - t_start
    print(f"[mutator] Targeted mutation LLM responded in {t_elapsed:.1f}s")

    variants = [v.python_code for v in result.variants]
    print(f"[mutator] Targeted mutation: {len(variants)} variant(s) "
          f"via structured output")
    for v in result.variants:
        display = v.thought_process[:300]
        if len(v.thought_process) > 300:
            display += "..."
        print(f"[mutator] [{v.target_organelle}] {display}")

    if not variants:
        print("[mutator] Targeted mutation: no parseable variants.")
        return None

    probe_stats = {
        "total_probes": 0,
        "successful_probes": 0,
        "success_rate": 0.0,
        "agentic_turns": 0,
    }

    print(f"[mutator] Targeted mutation: {len(variants)} variants parsed")

    # 7. Validate + write each variant (TICK 22.1: indestructible AST)
    n_written = 0
    for vi, variant_code in enumerate(variants):
        # TICK 22.1: Dedent + tab expansion before any AST operation
        variant_code = textwrap.dedent(variant_code).expandtabs(4)

        c_ok, c_violations = validate_candidate(variant_code)
        if not c_ok:
            print(f"[mutator] CONSTITUTIONAL VETO targeted variant {vi + 1}: "
                  f"{c_violations}")
            audit_log("VETO_CANDIDATE", {
                "source": "mutator_targeted",
                "organelle": bottleneck,
                "variant": vi + 1,
                "violations": c_violations,
            })
            continue

        # Verify the variant contains the correct class
        try:
            vtree = ast.parse(variant_code)
            has_target = any(
                isinstance(n, ast.ClassDef) and n.name == class_name
                for n in ast.iter_child_nodes(vtree)
            )
            if not has_target:
                print(f"[mutator] Targeted variant {vi + 1}: missing {class_name}")
                continue
        except SyntaxError as syn_exc:
            print(f"[mutator] Targeted variant {vi + 1}: SyntaxError — "
                  f"{syn_exc.msg} (line {syn_exc.lineno})")
            if syn_exc.text:
                print(f"[mutator]   Offending line: {syn_exc.text!r}")
            # Show first 200 chars of the code for debugging
            print(f"[mutator]   Code preview: {variant_code[:200]!r}")
            continue

        patched = _ast_replace_in_source(full_source, variant_code)
        if patched is None:
            print(f"[mutator] Targeted variant {vi + 1}: AST patch failed")
            continue

        # ── POWER-LAW SUBSTRATE: BarbellFilter veto (Site 1 — Targeted Mutation) ──
        # Main thread only — subprocess is already dead. Python scalars only (MLX-safe).
        _v_params = sum(
            int(m) for m in __import__("re").findall(r"\b(\d+)\b", variant_code)
            if 64 <= int(m) <= 65536
        ) or 1
        _v_epi_delta = meta_fitness.get("delta_epi", 0.0)
        _v_evolvability = meta_fitness.get("evolvability_score", 0.01)
        _v_leverage = compute_leverage_score(
            epi_delta=max(_v_epi_delta, 0.0),
            reuse_count=1,
            cross_domain_potential=max(_v_evolvability, 1e-6),
            total_params=max(_v_params, 1),
        )
        _v_barbell = classify_candidate(
            param_delta=_v_params,
            epi_delta=max(_v_epi_delta, 0.0),
            leverage_score=_v_leverage,
        )
        if _v_barbell == "MEDIUM":
            print(
                f"[barbell] VETO: Medium Risk/Reward — thermodynamic waste discarded. "
                f"variant={vi + 1} epi_delta={_v_epi_delta:.4f} leverage={_v_leverage:.3f}"
            )
            continue
        # ─────────────────────────────────────────────────────────────────────────

        written = _write_candidate(fs, variant_code, variant_idx=vi + 1)
        if written:
            n_written += 1
            print(f"[mutator] Targeted variant {vi + 1} ({bottleneck}): {written.name}")

    return (n_written, probe_stats) if n_written > 0 else None


def _attempt_organelle_assembly(fs: FileSystemBus) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Attempt to assemble a new candidate via Pareto-MCTS.

    TICK 17.0: The MCTS acts as the "Fast Brain" — finding the optimal
    organelle combination in milliseconds via Monte Carlo Tree Search
    constrained by:
      - 80/20 Pareto Policy Head (top 20% organelles only)
      - Φ Tax (Free Energy Rate Density thermodynamic bound)
      - Time Topology Warm-Start (historical assembly priors)
      - Reality Coupling (Constitutional MAX_PARAMS check)

    Falls back to greedy assembly if MCTS fails.

    Returns (n_written, mcts_stats_or_None).
    """
    # ── TICK 17.0: Pareto-MCTS Assembly (Fast Brain) ─────────────
    result = mcts_assemble_and_write(fs.root)
    if result is not None:
        written_path, mcts_stats = result
        print(f"[mutator] TICK 17.0 MCTS Assembly (Fast Brain): "
              f"Φ={mcts_stats['best_value']:.4f} "
              f"rollouts={mcts_stats['rollouts']} "
              f"elapsed={mcts_stats['elapsed_ms']:.1f}ms → {written_path.name}")
        print(f"[mutator]   Pareto pool: {mcts_stats['pareto_pool_sizes']} "
              f"warm_start={mcts_stats['warm_start_paths']} paths")
        return 1, mcts_stats

    # Fallback: greedy assembly (pre-TICK 17.0 behavior)
    assembled = assemble_best_organelles(fs.root)
    if assembled is None:
        return 0, None

    written = write_assembled_candidate(fs.root, assembled)
    if written:
        print(f"[mutator] TICK 15.0 Greedy Assembly (fallback): {written.name}")
        return 1, None
    return 0, None


# ═══════════════════════════════════════════════════════════════
# TICK 18.0: DUAL-BRAIN HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _estimate_candidate_params(code: str) -> int:
    """Estimate parameter count from PyTorch source via lightweight AST scan.

    Scans nn.Linear(in, out) and nn.Embedding(num, dim) calls with
    integer literal arguments.  Returns a conservative upper-bound estimate.
    Used by the MCTS preview gate and the 90% Thermodynamic Tax validator.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0

    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name in ("Linear", "Embedding") and len(node.args) >= 2:
            try:
                a, b = node.args[0], node.args[1]
                if isinstance(a, ast.Constant) and isinstance(b, ast.Constant):
                    total += int(a.value) * int(b.value)
            except (ValueError, TypeError):
                pass
    return total


def _fast_brain_mcts_preview(
    variant_code: str,
    best_epi: float,
    meta_fitness: Dict[str, float],
) -> Tuple[bool, float]:
    """MCTS mini-loop viability gate for Fast Brain variants.

    Runs ≤_FAST_BRAIN_MCTS_PREVIEW_STEPS Monte Carlo steps to estimate
    the thermodynamic value of a proposed Fast Brain mutation before it
    is written to the candidate pool.

    Three sequential gates:
      1. Constitutional compliance (validate_candidate)
      2. Reality Coupling: param count ≤ MAX_CANDIDATE_PARAMS
      3. Monte Carlo Φ projection with parsimony bonus

    Returns (is_viable, projected_phi).
    """
    import random

    # Gate 1: Constitutional compliance
    c_ok, _ = validate_candidate(variant_code)
    if not c_ok:
        return False, -float("inf")

    # Gate 2: Reality Coupling (Constitutional param budget)
    est_params = _estimate_candidate_params(variant_code)
    if est_params > _MAX_CANDIDATE_PARAMS:
        return False, -float("inf")

    # Gate 3 (TICK 19.0): DAG Oracle — physical topology reality check.
    # Runs BEFORE the Monte Carlo projection to eliminate OOM / shape-mismatch
    # candidates in <2 ms (zero PyTorch compilation).
    oracle_viable, oracle_composite_phi, _oracle_result = gate_fast_brain_variant(
        variant_code, best_epi, meta_fitness,
    )
    if not oracle_viable:
        return False, -float("inf")

    # Gate 4: Monte Carlo Φ projection
    evolvability = max(meta_fitness.get("evolvability_score", 0.01), 0.01)
    delta_epi = meta_fitness.get("delta_epi", 0.0)
    n_steps = min(_FAST_BRAIN_MCTS_PREVIEW_STEPS, 50)  # cap for speed

    rng = random.Random(hash(variant_code) % (2 ** 31))
    phi_samples: List[float] = []
    for _ in range(n_steps):
        noise = rng.gauss(0.0, evolvability * 0.15)
        proj_phi = (best_epi + max(delta_epi, 0.0)) * max(evolvability + noise, 0.001)
        phi_samples.append(proj_phi)

    avg_phi = sum(phi_samples) / len(phi_samples)
    # Parsimony bonus: compact architectures get a small reward
    param_ratio = est_params / max(_MAX_CANDIDATE_PARAMS, 1)
    parsimony = max(0.0, 1.0 - param_ratio) * 0.05
    projected_phi = avg_phi + parsimony

    return projected_phi > 0.0, projected_phi


def _validate_slow_brain_tax(
    new_code: str,
    elite_param_baseline: int = 0,
) -> Tuple[bool, float, str]:
    """Enforce the 90% Thermodynamic Tax Rule for Slow Brain candidates.

    Any new architecture proposed by the Slow Brain MUST demonstrate a
    projected Thermodynamic Tax ≤ 90% of the previous elite's cost.
    Architectures heavier than the elite ceiling are discarded immediately —
    the Slow Brain must invent things that do MORE with LESS.

    Tax proxy: new_params / reference_params.
    reference_params = elite_param_baseline if known, else _MAX_CANDIDATE_PARAMS.

    Returns (passes, tax_ratio, rejection_reason).
    """
    new_params = _estimate_candidate_params(new_code)
    if new_params == 0:
        # Cannot estimate (dynamic dims) → pass with warning
        return True, 0.0, ""

    reference = elite_param_baseline if elite_param_baseline > 0 else _MAX_CANDIDATE_PARAMS
    tax_ratio = new_params / max(reference, 1)

    if tax_ratio > _SLOW_BRAIN_TAX_CEILING:
        reason = (
            f"90% Tax EXCEEDED: cost={tax_ratio*100:.1f}% > "
            f"ceiling={_SLOW_BRAIN_TAX_CEILING*100:.0f}% "
            f"({new_params:,} params vs {reference:,} reference). "
            f"Discarded — Slow Brain must compress, not expand."
        )
        return False, tax_ratio, reason

    return True, tax_ratio, ""


def _build_pareto_top20_context(fs: Any) -> str:
    """Build a context block from the Pareto Top 20% elites in island_good.

    TICK 18.0: The Slow Brain ONLY receives the top 20% of proven elites —
    preventing regression to mediocre patterns and forcing genuine invention.
    The Slow Brain must study these seeds and TRANSCEND them, not clone them.
    """
    island_good = Path(fs.root) / _ISLAND_GOOD_DIR
    if not island_good.exists():
        return ""

    try:
        raw = list(island_good.glob("elite_*.py"))
    except (FileNotFoundError, OSError):
        return ""
    elite_files = sorted(raw, key=_safe_mtime)
    elite_files = [f for f in elite_files if _safe_mtime(f) > 0.0]
    if not elite_files:
        return ""

    n_top = max(1, int(len(elite_files) * _SLOW_BRAIN_PARETO_TOP_PCT))
    top_files = elite_files[-n_top:]  # newest survivors = highest fitness elites

    parts: List[str] = [
        f"═══ PARETO TOP {int(_SLOW_BRAIN_PARETO_TOP_PCT*100)}% ELITE SEEDS "
        f"({n_top}/{len(elite_files)} from island_good) ═══\n"
        f"Study these proven architectural patterns.\n"
        f"Identify their structural INVARIANTS — then transcend them.\n"
        f"Do NOT clone. Do NOT minimally modify. INVENT.\n\n"
    ]
    for i, f in enumerate(top_files[:3], 1):  # at most 3 to preserve token budget
        try:
            code = f.read_text(encoding="utf-8")
            lines = code.splitlines()
            if lines and lines[0].startswith("# Island:"):
                code = "\n".join(lines[1:])
            parts.append(
                f"--- Pareto Elite #{i} ({f.name}) ---\n"
                f"```python\n{code[:3000]}\n```\n\n"
            )
        except Exception:
            continue

    return "".join(parts)


def _read_pareto_top20_epis(fs: Any) -> List[float]:
    """Return epi scores for the Pareto Top 20% elites in island_good.

    TICK 20.0: Used by the Niche Evolver to calibrate the ZPD difficulty
    bias — harder niches are generated when the organism is already strong.
    """
    island_good = Path(fs.root) / _ISLAND_GOOD_DIR
    if not island_good.exists():
        return []

    try:
        raw = list(island_good.glob("elite_*.py"))
    except (FileNotFoundError, OSError):
        return []
    elite_files = sorted(raw, key=_safe_mtime)
    elite_files = [f for f in elite_files if _safe_mtime(f) > 0.0]
    if not elite_files:
        return []

    n_top = max(1, int(len(elite_files) * _SLOW_BRAIN_PARETO_TOP_PCT))
    top_files = elite_files[-n_top:]

    epis: List[float] = []
    for f in top_files:
        try:
            header = _safe_read_text(f)
            if header is None:
                continue
            header = header.splitlines()[0]
            # Header format: "# Island: island_good | epi=0.1234 | ..."
            if "epi=" in header:
                epi_str = header.split("epi=")[1].split()[0].rstrip(",")
                epis.append(float(epi_str))
        except Exception:
            continue
    return epis


def _trigger_niche_if_heat_death(
    fs: Any,
    dual_brain: "DualBrainRouter",
    best_epi: float,
    workspace_root: str,
    niche_state: Dict[str, Any],
) -> None:
    """TICK 20.0: Generate a new Niche when Slow Brain is in Heat Death.

    Trigger condition (per spec):
      - dual_brain.slow_brain_active == True
      - dual_brain.slow_brain_trigger == "heat_death"
      - Cooldown: _NICHE_COOLDOWN_S seconds since last niche generation

    If a viable niche is found:
      - Writes it to candidate_pool/env_active/current.json (atomic IPC)
      - Evaluator Daemon (TICK 12.0) will respawn env_stream.py on the
        next _ENV_REFRESH_INTERVAL tick with the new challenge parameters.

    niche_state is a mutable dict with key "last_generated_t" (float) that
    persists across main loop iterations.
    """
    if not (dual_brain.slow_brain_active
            and dual_brain.slow_brain_trigger == "heat_death"):
        return

    now = time.time()
    if now - niche_state.get("last_generated_t", 0.0) < _NICHE_COOLDOWN_S:
        return  # Respect cooldown

    print(
        f"\n[niche] {'░'*60}\n"
        f"[niche] HEAT DEATH detected — triggering MuZero Niche Construction\n"
        f"[niche] elite_epi={best_epi:.4f} | "
        f"Phi_drops={dual_brain.phi_tracker.consecutive_drops}\n"
        f"[niche] {'░'*60}"
    )

    # Read Pareto Top 20% epi list for ZPD calibration
    pareto_epis = _read_pareto_top20_epis(fs)

    # Read elite param count for TICK 19.0 oracle gate (proxy only here)
    elite_param_count = 0
    island_good_path = Path(fs.root) / _ISLAND_GOOD_DIR
    if island_good_path.exists():
        try:
            raw_p = list(island_good_path.glob("elite_*.py"))
        except (FileNotFoundError, OSError):
            raw_p = []
        elite_files_for_p = sorted(raw_p, key=_safe_mtime)[-1:]
    else:
        elite_files_for_p = []
    if elite_files_for_p:
        try:
            txt = _safe_read_text(elite_files_for_p[0])
            if txt:
                elite_param_count = _estimate_candidate_params(txt)
        except Exception:
            pass

    env_config = generate_niche(
        workspace_root=workspace_root,
        elite_epi=best_epi,
        elite_param_count=elite_param_count,
        pareto_top20_epis=pareto_epis,
    )

    if env_config is not None:
        ok = write_niche(workspace_root, env_config)
        if ok:
            niche_state["last_generated_t"] = now
            niche_state["active_config"] = env_config
            fs.append("logs/mutator_events.ndjson", {
                "event": "niche_generated",
                "version": env_config.get("version"),
                "phi_pred": env_config.get("_niche_meta", {}).get("phi_pred"),
                "niche_value": env_config.get("_niche_meta", {}).get("niche_value"),
                "elite_epi": best_epi,
                "t": now,
            })
    else:
        print("[niche] No viable niche — organism remains in current environment.")


def _log_mdl_compression_gain(
    fs: Any,
    trigger: str,
    mdl_before: float,
    mdl_after: float,
    new_params: int,
    elapsed_s: float,
) -> None:
    """Log Slow Brain paradigm shift's MDL compression gain to island_assembly.

    TICK 18.0 × TICK 17.0 synergy: The MCTS Time Topology Warm-Start reads
    island_assembly history to warm-start future Fast Brain priors.
    By logging the Slow Brain's compression gain here, the Fast Brain's
    next search trees are seeded with the Slow Brain's architectural insight —
    compounding the leverage across both brains.
    """
    mdl_gain = (
        (mdl_before - mdl_after) / max(mdl_before, 1e-6)
        if mdl_before > 0 else 0.0
    )
    record: Dict[str, Any] = {
        "event": "slow_brain_paradigm_shift",
        "trigger": trigger,
        "mdl_before": round(mdl_before, 2),
        "mdl_after": round(mdl_after, 2),
        "mdl_compression_gain": round(mdl_gain, 6),
        "new_params": new_params,
        "elapsed_s": round(elapsed_s, 1),
        "t": time.time(),
    }
    gains_path = Path(fs.root) / _SLOW_BRAIN_GAINS_PATH
    try:
        gains_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gains_path, "a") as fh:
            fh.write(json.dumps(record) + "\n")
        print(
            f"[slow-brain] MDL compression gain "
            f"{mdl_gain*100:.2f}% logged → {gains_path.name} "
            f"(MCTS warm-start updated)"
        )
    except OSError as exc:
        print(f"[slow-brain] Warning: MDL gain log failed: {exc}")






# ═══════════════════════════════════════════════════════════════
# TICK 24.1: TRI-AGENT PIPELINE (Architect → Coder → Test-Runner)
# ═══════════════════════════════════════════════════════════════


def _architect_call(
    organelle_src: str,
    class_name: str,
    organelle_type: str,
    meta_fitness: Dict[str, float],
    gradient_md: str = "",
    crash_context: str = "",
    slow_brain_model: str = _SLOW_BRAIN_MODEL,
) -> Optional[ArchitectPlan]:
    """Agent 1 — Architect (Slow Brain): Analyze metrics, output strategy ONLY.

    TICK 24.1: The Architect sees gradient profiles, fitness history, and the
    current organelle source. It outputs a mathematical strategy with ZERO code.
    The Coder translates this plan into PyTorch AST.

    TICK 33.0: slow_brain_model remains injectable for future model experiments
    (e.g. recipe-trial routing). Defaults to _SLOW_BRAIN_MODEL (gemma4:26b).
    """
    evolvability = meta_fitness.get("evolvability_score", 0.0)
    velocity = meta_fitness.get("improvement_per_second", 0.0)
    delta_epi = meta_fitness.get("delta_epi", 0.0)
    best_epi = meta_fitness.get("best_epi", 0.0)

    gradient_block = ""
    if gradient_md:
        gradient_block = (
            f"\n--- GRADIENT ORACLE PROFILE (read-only) ---\n"
            f"{gradient_md}\n"
        )
    crash_block = ""
    if crash_context:
        crash_block = (
            f"\n--- RECENT CRASH LOG ---\n"
            f"{crash_context}\n"
        )

    system_prompt = (
        "You are the Architect of a Neural Architecture Search system.\n\n"
        "YOUR ROLE: Analyze metrics and gradients, then output a MATHEMATICAL "
        "MUTATION STRATEGY. You must NOT write any Python code.\n\n"
        "OUTPUT RULES:\n"
        "1. Describe WHAT mathematical transformation to apply (e.g., "
        "'replace softmax gating with sigmoid top-k', 'add layer norm before "
        "expert dispatch').\n"
        "2. Describe WHY based on the gradient profile and fitness data.\n"
        "3. List the CONSTRAINTS the implementation must preserve.\n"
        "4. Express strategy as mathematical operations, NOT code.\n\n"
        "CRITICAL JSON RULES:\n"
        "1. DO NOT use nested JSON objects for 'analysis' or 'strategy'. "
        "They MUST be flat, plain text strings.\n"
        "2. DO NOT use LaTeX math formatting, backslashes (\\), or special "
        "escape characters. Write math in plain English words "
        "(e.g., write 'matrix S' instead of 'S in R^{nxn}').\n"
        "3. Your response must survive strict json.loads parsing.\n\n"
        f"{crash_block}{gradient_block}"
    )

    user_prompt = (
        f"--- TARGET ORGANELLE: {organelle_type} ({class_name}) ---\n"
        f"```python\n{organelle_src}\n```\n\n"
        f"--- EVOLUTIONARY TELEMETRY ---\n"
        f"  best_epi: {best_epi:.4f}\n"
        f"  delta_epi: {delta_epi:.6f}\n"
        f"  evolvability: {evolvability:.4f}\n"
        f"  velocity: {velocity:.6f}\n\n"
        f"Analyze the bottleneck and output a mutation strategy. NO CODE."
    )

    t_start = time.time()
    try:
        client = get_instructor_client()
        plan = client.chat.completions.create(
            model=slow_brain_model,  # TICK 32.0: use injected param, not module constant
            response_model=ArchitectPlan,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
            temperature=0.1,
            # TICK 21.4/21.5: Thermodynamic API Constraints.
            # Slow Brain (35B) is the primary risk: defaults to 262K ctx.
            # num_ctx=8192 hard-caps the KV-cache. keep_alive=0 releases VRAM.
            extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}},
        )
        elapsed = time.time() - t_start
        print(f"[architect] Plan generated in {elapsed:.1f}s: "
              f"target={plan.target_organelle}, "
              f"constraints={len(plan.constraints)}")
        return plan
    except Exception as exc:
        elapsed = time.time() - t_start
        print(f"[architect] Error after {elapsed:.1f}s: "
              f"{type(exc).__name__}: {exc}")
        return None


def _coder_call(
    plan: ArchitectPlan,
    organelle_src: str,
    organelle_spec: Dict[str, Any],
    batch_size: int = 3,
    dynamic_params: Optional[Dict[str, Any]] = None,
) -> Optional[MutationBatch]:
    """Agent 2 — Coder (Fast Brain): Translate plan into PyTorch AST code.

    TICK 24.1: The Coder receives the Architect's plan + scaffold constraints.
    It outputs complete, executable Python class definitions.
    """
    class_name = organelle_spec["class_name"]

    constraint_block = "\n".join(
        f"  - {c}" for c in plan.constraints
    ) if plan.constraints else "  (none specified)"

    # ── TICK 24.3: Immutable Scaffold Boundary ────────────────────────────
    # Derive the organelle type from the class name to inject type-specific
    # contract rules.  This prevents the Coder from cross-pollinating
    # organelle classes and eliminates NameErrors in the isolated test-runner.
    _type_by_class = {spec["class_name"]: otype for otype, spec in ORGANELLE_TYPES.items()}
    _organelle_type = _type_by_class.get(class_name, "unknown")

    if _organelle_type == "routing":
        scaffold_boundary = (
            "═══════════════════════════════════════════════════════════\n"
            "IMMUTABLE SCAFFOLD BOUNDARY — READ BEFORE WRITING ANY CODE\n"
            "═══════════════════════════════════════════════════════════\n"
            "You are mutating ONLY `RoutingStrategy` — a PURE MATHEMATICAL ROUTER.\n\n"
            "WHAT RoutingStrategy IS:\n"
            "  - A gating/weighting function that decides HOW to mix expert outputs.\n"
            "  - It receives already-instantiated experts from the immutable scaffold.\n\n"
            "WHAT RoutingStrategy IS NOT:\n"
            "  - It is NOT a container of experts.\n"
            "  - It does NOT own or instantiate expert modules.\n\n"
            "FORBIDDEN — INSTANT VETO — DO NOT WRITE:\n"
            "  ✗  self.experts = nn.ModuleList([IChingExpert(...)])   # NEVER\n"
            "  ✗  self.experts = nn.ModuleList([...])                 # NEVER\n"
            "  ✗  IChingExpert(...)          anywhere in your code    # NEVER\n"
            "  ✗  CausalSelfAttention(...)   anywhere in your code    # NEVER\n"
            "  ✗  MitoticTransformerBlock(...) anywhere in your code  # NEVER\n"
            "  ✗  from atomic_core import ... / import atomic_core    # NEVER\n\n"
            "MANDATORY FORWARD SIGNATURE:\n"
            "  def forward(self, x: torch.Tensor,\n"
            "              experts=None,\n"
            "              router_idx: int = 0) -> torch.Tensor:\n"
            "      # x:       shape (B, T, D) — hidden states from scaffold\n"
            "      # experts:  list/ModuleList of IChingExpert already built by scaffold\n"
            "      # router_idx: integer routing index passed by MitoticTransformerBlock\n"
            "      # RETURN:  shape (B, T, D) — added as residual by immutable scaffold\n\n"
            "PERMITTED in __init__:\n"
            "  ✓  nn.Linear, nn.LayerNorm, nn.Embedding, nn.Parameter, nn.Dropout\n"
            "  ✓  Scalar hyperparameters (d_model, n_experts, top_k, temperature, …)\n"
            "  ✓  Any pure PyTorch primitive — NO cross-organelle class instantiation.\n\n"
            "CORRECT DISPATCH PATTERN (use this as your template):\n"
            "  def forward(self, x, experts=None, router_idx=0):\n"
            "      gates = ...compute routing weights from x...  # shape (B,T,n_experts)\n"
            "      out = torch.zeros_like(x)\n"
            "      if experts:\n"
            "          for i, expert in enumerate(experts):\n"
            "              out = out + gates[..., i:i+1] * expert(x)\n"
            "      return out\n"
            "═══════════════════════════════════════════════════════════\n\n"
        )
    elif _organelle_type == "attention":
        scaffold_boundary = (
            "═══════════════════════════════════════════════════════════\n"
            "IMMUTABLE SCAFFOLD BOUNDARY\n"
            "═══════════════════════════════════════════════════════════\n"
            "You are mutating ONLY `CausalSelfAttention`.\n"
            "FORBIDDEN: Do NOT instantiate RoutingStrategy, IChingExpert, "
            "MitoticTransformerBlock, or AtomicLLM anywhere in your code.\n"
            "SIGNATURE: forward(self, x: Tensor) -> Tensor  [B,T,D → B,T,D]\n"
            "═══════════════════════════════════════════════════════════\n\n"
        )
    elif _organelle_type == "expert":
        scaffold_boundary = (
            "═══════════════════════════════════════════════════════════\n"
            "IMMUTABLE SCAFFOLD BOUNDARY\n"
            "═══════════════════════════════════════════════════════════\n"
            "You are mutating ONLY `IChingExpert`.\n"
            "FORBIDDEN: Do NOT instantiate RoutingStrategy, CausalSelfAttention, "
            "MitoticTransformerBlock, or AtomicLLM anywhere in your code.\n"
            "SIGNATURE: forward(self, x: Tensor) -> Tensor  [B,T,D → B,T,D]\n"
            "═══════════════════════════════════════════════════════════\n\n"
        )
    else:
        scaffold_boundary = ""

    system_prompt = (
        f"{scaffold_boundary}"
        "You are the Coder of a Neural Architecture Search system.\n\n"
        "YOUR ROLE: Translate the Architect's strategy into executable "
        "PyTorch code. You receive a plan and must output complete Python "
        "class definitions.\n\n"
        "RULES:\n"
        f"1. Class name MUST remain: `{class_name}`\n"
        "2. MUST include both __init__ and forward methods.\n"
        f"3. Input spec: {organelle_spec['input_spec']}\n"
        f"4. Output spec: {organelle_spec['output_spec']}\n"
        "5. Use \\n for newlines in python_code.\n"
        "6. Code must be COMPLETE — no ellipses, no placeholders.\n\n"
        f"ARCHITECT CONSTRAINTS:\n{constraint_block}\n\n"
        f"ARCHITECT ANALYSIS:\n{plan.analysis}\n\n"
        f"ARCHITECT STRATEGY:\n{plan.strategy}\n"
    )

    user_prompt = (
        f"--- CURRENT {class_name} SOURCE ---\n"
        f"```python\n{organelle_src}\n```\n\n"
        f"Implement the Architect's strategy. Produce {batch_size} "
        f"structurally distinct variants of `{class_name}`.\n"
        f"Output ONLY the JSON block."
    )

    t_start = time.time()
    try:
        client = get_instructor_client()
        result = client.chat.completions.create(
            model=_FAST_BRAIN_MODEL,
            response_model=MutationBatch,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
            temperature=0.1,
            # TICK 21.4/21.5: Thermodynamic API Constraints.
            # Fast Brain (7B) is the high-frequency engine; keep_alive=0
            # ensures each call releases VRAM immediately for the Fast Loop.
            extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}},
        )
        elapsed = time.time() - t_start
        print(f"[coder] {len(result.variants)} variant(s) generated in {elapsed:.1f}s")
        return result
    except Exception as exc:
        elapsed = time.time() - t_start
        print(f"[coder] Error after {elapsed:.1f}s: "
              f"{type(exc).__name__}: {exc}")
        return None


def _test_runner(
    python_code: str,
    class_name: str,
    organelle_type: str,
) -> Tuple[bool, str]:
    """Agent 3 — Test-Runner: Validate code in isolated subprocess with 2.0s timeout.

    TICK 24.1: Writes a temp test script, launches subprocess.Popen,
    hard-kills after _TEST_RUNNER_TIMEOUT_S. NEVER runs untrusted code in
    the main thread.

    Uses subprocess.Popen (not multiprocessing.Process) for maximum isolation:
    completely separate Python interpreter, no shared memory, no import
    contamination from the parent process.
    """
    import subprocess as _sp

    # Build dummy args based on organelle type
    if organelle_type == "attention":
        init_args = "d_model=64, n_head=4"
        dummy_tensor = "torch.randn(1, 16, 64)"
    elif organelle_type == "routing":
        init_args = "d_model=64, n_experts=4"
        dummy_tensor = "torch.randn(1, 16, 64)"
    elif organelle_type == "expert":
        init_args = "d_model=64, ff_dim=128"
        dummy_tensor = "torch.randn(1, 16, 64)"
    else:
        init_args = "d_model=64"
        dummy_tensor = "torch.randn(1, 16, 64)"

    # ── TICK 24.3: Scaffold stub environment ─────────────────────────────
    # Inject nn.Module-based stubs BEFORE the LLM code so that any cross-
    # organelle reference (e.g. IChingExpert in a RoutingStrategy.__init__)
    # resolves to a passthrough module instead of raising a NameError.
    # These stubs are OVERRIDDEN if the LLM itself defines the same class,
    # which is fine — the LLM-generated definition takes precedence.
    # All stubs inherit nn.Module so nn.ModuleList([IChingExpert(...)]) works
    # without AttributeError on .parameters(), .to(), etc.
    stub_block = (
        "# ── Scaffold stubs (TICK 24.3): resolve cross-organelle references ──\n"
        "class _StubModule(nn.Module):\n"
        "    def __init__(self, *a, **kw): super().__init__()\n"
        "    def forward(self, x, *a, **kw): return x\n"
        "class IChingExpert(_StubModule): pass\n"
        "class CausalSelfAttention(_StubModule): pass\n"
        "class MitoticTransformerBlock(_StubModule): pass\n"
        "class AtomicLLM(_StubModule): pass\n"
        "\n"
    )

    # ── TICK 24.3: Routing forward call with backward-compatible fallback ─
    # Try the new contract first: forward(self, x, experts=..., router_idx=0).
    # If the model only accepts (self, x) or (self, x, **kwargs), TypeError
    # is raised by CPython's argument binding — not by logic inside forward().
    # We catch ONLY TypeError to avoid masking genuine runtime errors such as
    # shape mismatches, AttributeErrors, or index errors inside the body.
    if organelle_type == "routing":
        forward_call = (
            f"# Build dummy expert list (nn.Module stubs with correct d_model)\n"
            f"_dummy_experts = nn.ModuleList([_StubModule() for _ in range(4)])\n"
            f"try:\n"
            f"    # New contract: experts + router_idx passed by scaffold\n"
            f"    out = model(x, experts=_dummy_experts, router_idx=0)\n"
            f"except TypeError:\n"
            f"    # Legacy contract: model owns self.experts internally\n"
            f"    out = model(x)\n"
        )
    else:
        forward_call = f"out = model(x)\n"

    test_script = (
        "import torch\n"
        "import torch.nn as nn\n"
        "import torch.nn.functional as F\n"
        "import math\n\n"
        f"{stub_block}"
        f"# ── LLM-generated code under test ──\n"
        f"{python_code}\n\n"
        f"# ── Instantiate and run forward pass ──\n"
        f"try:\n"
        f"    model = {class_name}({init_args})\n"
        f"except TypeError:\n"
        f"    # Fallback: try with just d_model\n"
        f"    model = {class_name}(64)\n"
        f"x = {dummy_tensor}\n"
        f"{forward_call}"
        f"assert hasattr(out, 'shape'), 'forward() must return a tensor'\n"
        f"print(f'PASS: {{out.shape}}')\n"
    )

    # Write temp script
    fd, script_path = tempfile.mkstemp(suffix=".py", prefix="agi_test_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(test_script)

        # Launch in completely isolated subprocess
        try:
            result = _sp.run(
                [sys.executable, script_path],
                capture_output=True, text=True,
                timeout=_TEST_RUNNER_TIMEOUT_S,
            )
        except _sp.TimeoutExpired:
            return False, f"TIMEOUT: exceeded {_TEST_RUNNER_TIMEOUT_S}s hard wall"

        if result.returncode == 0:
            return True, f"PASS: {result.stdout.strip()}"
        else:
            stderr = result.stderr.strip()[:500]
            return False, f"FAIL: {stderr}"
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── TICK 25.1: Epigenetic Sandbox Coupling ───────────────────────────────────
# Pure classifier: maps a Test-Runner failure message to the appropriate
# EpigeneticFailureType and severity for the PhiGovernor penalty ledger.
# Called in the main mutator thread — NEVER in the subprocess.
# Zero-IPC: the subprocess is already dead by the time this is called;
# we parse only the returned string from _test_runner().
#
# Severity scale (matches the TICK 25.1 plan):
#   1.0 — Structural / syntactic error (Coder output malformed)
#   2.0 — Thermodynamic / mathematical error (compute runaway, tensor mismatch)
#   3.0 — Constitutional / scaffold violation (deep hallucination, NameError)
def _classify_sandbox_failure(
    msg: str,
    is_syntax_error: bool = False,
) -> Tuple[EpigeneticFailureType, float]:
    """Classify a sandbox rejection into (EpigeneticFailureType, severity).

    Args:
        msg:             The failure message string from _test_runner() or
                         the SyntaxError path.  Case-insensitive matching.
        is_syntax_error: True when called from the ast.parse() SyntaxError
                         path (before the subprocess) — always severity 1.0.

    Returns:
        (EpigeneticFailureType, severity) tuple for record_epigenetic_failure().
    """
    if is_syntax_error:
        # Malformed Python from the Coder — structural failure, lowest severity.
        return EpigeneticFailureType.SHAPE_MISMATCH, 1.0

    m = msg.upper()

    # TIMEOUT — compute runaway / thermodynamic waste
    if "TIMEOUT" in m:
        return EpigeneticFailureType.TIMEOUT, 2.0

    # NameError — scaffold contract violation (used forbidden class, missing stub)
    # This is the deepest mathematical hallucination: the Coder referenced a
    # symbol that doesn't exist in the target namespace.  Maximum severity.
    if "NAMEERROR" in m:
        return EpigeneticFailureType.PERMISSION_VIOLATION, 3.0

    # NaN / Inf — numerical instability in the forward pass
    if "NAN" in m or "INF" in m or "NANDIVERGENCE" in m:
        return EpigeneticFailureType.NAN_DIVERGENCE, 2.0

    # RuntimeError — typically tensor shape mismatch or matmul incompatibility
    if "RUNTIMEERROR" in m or "SIZE MISMATCH" in m or "SHAPE" in m:
        return EpigeneticFailureType.SHAPE_MISMATCH, 2.0

    # AttributeError — object missing expected method/attribute (structural)
    if "ATTRIBUTEERROR" in m:
        return EpigeneticFailureType.SHAPE_MISMATCH, 2.0

    # ImportError / ModuleNotFoundError — forbidden or missing import
    if "IMPORTERROR" in m or "MODULENOTFOUNDERROR" in m:
        return EpigeneticFailureType.PERMISSION_VIOLATION, 3.0

    # Fallback: generic structural failure
    return EpigeneticFailureType.SHAPE_MISMATCH, 1.0


def _tri_agent_pipeline(
    fs: Any,
    organelle_src: str,
    class_name: str,
    organelle_type: str,
    meta_fitness: Dict[str, float],
    dynamic_params: Dict[str, Any],
    recipe: Any,
    gradient_md: str = "",
    crash_context: str = "",
    slow_brain_model: str = _SLOW_BRAIN_MODEL,
) -> List[str]:
    """Orchestrate the Tri-Agent Pipeline: Architect -> Coder -> Test-Runner.

    TICK 24.1: Replaces all legacy dispatch paths (_dual_brain_dispatch,
    _enhanced_llm_call, _slow_brain_call). Single unified pipeline for
    ALL mutation modes.

    Returns list of validated python_code strings (may be empty on failure).
    """
    organelle_spec = ORGANELLE_TYPES.get(organelle_type)
    if organelle_spec is None:
        print(f"[tri-agent] Unknown organelle type: {organelle_type}")
        return []

    batch_size = getattr(recipe, 'BATCH_SIZE', 3)

    # ── Agent 1: Architect (Slow Brain) ──────────────────────────────
    print(f"\n[tri-agent] {'='*60}")
    print(f"[tri-agent] ARCHITECT (Slow Brain: {slow_brain_model})")
    print(f"[tri-agent] {'='*60}")

    plan = _architect_call(
        organelle_src=organelle_src,
        class_name=class_name,
        organelle_type=organelle_type,
        meta_fitness=meta_fitness,
        gradient_md=gradient_md,
        crash_context=crash_context,
        slow_brain_model=slow_brain_model,
    )
    if plan is None:
        print("[tri-agent] Architect failed — aborting pipeline.")
        return []

    print(f"[tri-agent] Architect strategy: {plan.strategy[:200]}...")

    # ── Agent 2: Coder (Fast Brain — 7B) ─────────────────────────────
    print(f"\n[tri-agent] {'='*60}")
    print(f"[tri-agent] CODER (Fast Brain: {_FAST_BRAIN_MODEL})")
    print(f"[tri-agent] {'='*60}")

    batch = _coder_call(
        plan=plan,
        organelle_src=organelle_src,
        organelle_spec=organelle_spec,
        batch_size=batch_size,
        dynamic_params=dynamic_params,
    )
    if batch is None or not batch.variants:
        print("[tri-agent] Coder failed — no variants generated.")
        return []

    # ── Agent 3: Test-Runner (subprocess, 2.0s hard timeout) ─────────
    print(f"\n[tri-agent] {'='*60}")
    print(f"[tri-agent] TEST-RUNNER (subprocess, {_TEST_RUNNER_TIMEOUT_S}s timeout)")
    print(f"[tri-agent] {'='*60}")

    validated: List[str] = []
    for i, variant in enumerate(batch.variants, 1):
        code = variant.python_code
        # Dedent + tab expansion
        code = textwrap.dedent(code).expandtabs(4)

        # Pre-filter: Constitutional validation (fast, no compute)
        c_ok, c_violations = validate_candidate(code)
        if not c_ok:
            print(f"[test-runner] Variant {i}: CONSTITUTIONAL VETO — {c_violations}")
            audit_log("VETO_CANDIDATE", {
                "source": "tri_agent_pipeline",
                "variant": i,
                "violations": c_violations,
            })
            # TICK 25.1: Constitutional veto = deepest scaffold violation.
            # PERMISSION_VIOLATION sev 3.0 — the Coder tried to escape the sandbox.
            _epi_type, _epi_sev = EpigeneticFailureType.PERMISSION_VIOLATION, 3.0
            try:
                get_phi_governor().record_epigenetic_failure(_epi_type, _epi_sev)
            except Exception as _epi_exc:
                print(f"[epigenetic] record failed (non-critical): {_epi_exc}")
            continue

        # AST parse check (fast)
        try:
            vtree = ast.parse(code)
            has_target = any(
                isinstance(n, ast.ClassDef) and n.name == class_name
                for n in ast.iter_child_nodes(vtree)
            )
            if not has_target:
                print(f"[test-runner] Variant {i}: missing class `{class_name}`")
                # TICK 25.1: Wrong output class — structural drift, sev 1.0.
                _epi_type, _epi_sev = _classify_sandbox_failure("", is_syntax_error=True)
                try:
                    get_phi_governor().record_epigenetic_failure(_epi_type, _epi_sev)
                except Exception as _epi_exc:
                    print(f"[epigenetic] record failed (non-critical): {_epi_exc}")
                continue
        except SyntaxError as syn_exc:
            print(f"[test-runner] Variant {i}: SyntaxError — {syn_exc.msg}")
            # TICK 25.1: Malformed Python from Coder — structural failure, sev 1.0.
            _epi_type, _epi_sev = _classify_sandbox_failure(
                str(syn_exc), is_syntax_error=True
            )
            try:
                get_phi_governor().record_epigenetic_failure(_epi_type, _epi_sev)
            except Exception as _epi_exc:
                print(f"[epigenetic] record failed (non-critical): {_epi_exc}")
            continue

        # Subprocess test
        passed, msg = _test_runner(code, class_name, organelle_type)
        if passed:
            print(f"[test-runner] Variant {i}: {msg}")
            validated.append(code)
        else:
            print(f"[test-runner] Variant {i}: REJECTED — {msg}")
            # TICK 25.1: Epigenetic Sandbox Coupling.
            # Parse the failure message in the main thread (subprocess already dead)
            # and inject the pain into the PhiGovernor penalty ledger.
            # Zero-IPC: we only read the returned string — no cross-process memory.
            _epi_type, _epi_sev = _classify_sandbox_failure(msg)
            try:
                get_phi_governor().record_epigenetic_failure(_epi_type, _epi_sev)
            except Exception as _epi_exc:
                print(f"[epigenetic] record failed (non-critical): {_epi_exc}")

    print(f"\n[tri-agent] Pipeline complete: "
          f"{len(validated)}/{len(batch.variants)} variants passed test-runner")

    return validated


# ═══════════════════════════════════════════════════════════════
# THE SLOW LOOP (TICK 6.1 + 6.2 + 7.1 + 10.0 + 24.1)
# ═══════════════════════════════════════════════════════════════


def _run_one_cycle(
    fs: Any,
    poll_interval: float,
    recipe_trial: "RecipeTrial",
    meta_stagnation_tracker: "MetaStagnationTracker",
    velocity_tracker: "VelocityTracker",
    dual_brain: "DualBrainRouter",
    constraint_matrix: Optional["ConstraintMatrix"],
    attractor: Any,
    physics_md: str,
    niche_state: Dict[str, Any],
    _workspace_root: str,
    _shared: Any,
    _loop_state: Dict[str, Any],
) -> None:
    """Single iteration of the mutator main loop.

    TICK 21.5: Extracted from run() to enable global try/except crash resilience.
    All cross-iteration mutable state lives in _loop_state dict.
    """
    # ── 0. HOT-RELOAD RECIPE (TICK 6.1) ────────────────────────────
    recipe = _load_recipe()
    recipe_version = getattr(recipe, "RECIPE_VERSION", "unknown")

    # ── 0b. TICK 16.0: CHECK RECIPE TRIAL STATE ───────────────────
    # If a recipe trial is active, check shadow batch status.
    if recipe_trial.active:
        records_for_trial = _read_recent_telemetry(fs)
        current_tick_for_trial = (
            records_for_trial[-1].get("tick", 0) if records_for_trial else 0
        )

        if not recipe_trial.shadow_files:
            # Shadow batch not yet generated — generate it now
            print(f"[trial] Generating shadow batch for trial "
                  f"{recipe_trial.trial_id}...")
            try:
                full_source_trial = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")
                arch_src_trial = _extract_nn_architecture(full_source_trial)
                if arch_src_trial:
                    trial_meta = {
                        "evolvability_score": 0.0,
                        "delta_epi": 0.0,
                        "improvement_per_second": 0.0,
                        "survival_rate": 0.0,
                    }
                    if records_for_trial:
                        latest = records_for_trial[-1]
                        trial_meta["evolvability_score"] = latest.get(
                            "evolvability_score", 0.0)
                        trial_meta["delta_epi"] = latest.get("delta_epi", 0.0)

                    n_shadow = _generate_shadow_batch(
                        fs=fs,
                        trial=recipe_trial,
                        arch_src=arch_src_trial,
                        full_source=full_source_trial,
                        threshold=latest.get("threshold", 0.1)
                            if records_for_trial else 0.1,
                        best_epi=recipe_trial.baseline_best_epi,
                        meta_fitness=trial_meta,
                        physics_md=physics_md,
                        gradient_md=_read_gradient_profile(fs),
                        env_md=_read_environment_profile(fs),
                        crash_context=_read_recent_crash_logs(fs),
                    )
                    if n_shadow > 0:
                        _persist_trial_state(fs, recipe_trial)
                        print(f"[trial] {n_shadow} shadow candidates submitted. "
                              f"Awaiting evaluation...")
                    else:
                        print(f"[trial] Shadow batch generation failed. "
                              f"Aborting trial.")
                        recipe_trial.last_rejection_reason = (
                            "Shadow batch generation produced zero valid candidates"
                        )
                        recipe_trial.reset()
                        _clear_trial_state(fs)
            except Exception as trial_exc:
                print(f"[trial] Shadow batch error: {trial_exc}")
                recipe_trial.last_rejection_reason = f"Shadow error: {trial_exc}"
                recipe_trial.reset()
                _clear_trial_state(fs)

        else:
            # Shadow batch already submitted — check results
            result = _check_shadow_results(
                fs, recipe_trial, current_tick_for_trial,
            )
            if result is not None:
                approved, reason = result
                if approved:
                    print(f"\n{'═'*70}")
                    print(f"[trial] ████ RECIPE TRIAL APPROVED ████")
                    print(f"[trial] {reason}")
                    print(f"[trial] Hot-swapping recipe to production...")
                    print(f"{'═'*70}\n")

                    success = _attempt_recipe_hotswap(
                        fs, recipe_trial.recipe_code,
                    )
                    if success:
                        fs.append("logs/mutator_events.ndjson", {
                            "mutation": "meta_evolution_approved",
                            "trial_id": recipe_trial.trial_id,
                            "reason": reason,
                            "t": time.time(),
                        })
                    else:
                        print(f"[trial] Hot-swap failed despite approval!")
                        recipe_trial.last_rejection_reason = (
                            "Approved but hot-swap failed"
                        )
                    recipe_trial.reset()
                    _clear_trial_state(fs)
                else:
                    print(f"\n{'═'*70}")
                    print(f"[trial] ████ RECIPE TRIAL REJECTED ████")
                    print(f"[trial] {reason}")
                    print(f"[trial] Keeping current recipe. "
                          f"Failure reason stored for next meta-evo.")
                    print(f"{'═'*70}\n")

                    recipe_trial.last_rejection_reason = reason
                    # Clean up staging file
                    if recipe_trial.recipe_staging_path:
                        recipe_trial.recipe_staging_path.unlink(
                            missing_ok=True)
                    recipe_trial.reset()
                    _clear_trial_state(fs)

                    fs.append("logs/mutator_events.ndjson", {
                        "mutation": "meta_evolution_rejected",
                        "trial_id": recipe_trial.trial_id,
                        "reason": reason,
                        "t": time.time(),
                    })

        # Don't run normal mutation while trial is active
        if recipe_trial.active:
            return

    # ── 1. READ EVALUATOR TELEMETRY ─────────────────────────────────
    records = _read_recent_telemetry(fs)
    should, reason, threshold, best_epi, meta_fitness = _should_mutate(
        records, _loop_state["last_mutation_tick"], recipe,
    )

    if not should:
        return

    # ── 2. VELOCITY TRACKING (TICK 6.2) ────────────────────────────
    velocity = meta_fitness.get("improvement_per_second", 0.0)
    velocity_tracker.record(velocity)
    velocity_z = velocity_tracker.z_score
    evolvability = meta_fitness.get("evolvability_score", 0.0)

    # Dynamic compute parameters — TICK 20.1: overridden by Constraint Matrix
    dynamic_params = _compute_dynamic_params(recipe, velocity_z, evolvability)
    if constraint_matrix is not None:
        dynamic_params = override_dynamic_params(constraint_matrix, dynamic_params)

    print(f"\n[mutator] Mutation triggered: {reason}")
    print(f"[mutator] threshold={threshold:.4f} best_epi={best_epi:.4f} "
          f"evo={evolvability:.3f} vel_z={velocity_z:.2f}")
    print(f"[mutator] Compute mode: {dynamic_params['mode']} "
          f"temp={dynamic_params['temperature']} "
          f"tokens={dynamic_params['num_predict']}")
    print(f"[mutator] Recipe: {recipe_version}")

    # ── 3. ISLAND SAMPLING (TICK 6.2) ───────────────────────────────
    island_samples = _sample_island_asts(fs, n_good=1, n_explore=1)
    island_context = _build_island_context(island_samples)
    n_sampled = sum(len(v) for v in island_samples.values())
    if n_sampled > 0:
        print(f"[mutator] Island cross-pollination: {n_sampled} AST(s) injected")

    # ── 3b. CRASH-LOG INJECTION (TICK 7.1) ─────────────────────────
    crash_context = _read_recent_crash_logs(fs, max_entries=3)
    if crash_context:
        print(f"[mutator] Crash logs injected for meta-cognition")

    # ── 3c. GRADIENT ORACLE (TICK 11.0: Phenotypic X-Ray) ────────
    gradient_md = _read_gradient_profile(fs)
    if gradient_md:
        print(f"[mutator] Gradient profile injected for phenotypic transparency")

    # ── 3d. ENVIRONMENT PROFILE (TICK 12.0: Cambrian Engine) ─────
    env_md = _read_environment_profile(fs)
    if env_md:
        print(f"[mutator] Environment genome injected for ecological awareness")

    # ── 3e. NICHE PROFILE (TICK 20.0: Autopoietic Niche Coupling) ──
    # Inject the active niche parameters into the Slow Brain prompt so
    # the LLM is aware of the hardware physics it must design within.
    _active_niche = niche_state.get("active_config") or load_active_niche(_workspace_root)
    niche_md = format_niche_markdown(_active_niche) if _active_niche else ""
    if niche_md:
        print(f"[mutator] Active Niche injected (TICK 20.0 M-Series Reality Coupling)")

    # ── 3f. TELEOLOGICAL ATTRACTOR (TICK 20.1: Future-Guided) ──────
    # Inject the attractor gradient direction so the LLM knows WHERE
    # to aim — not just what to change, but what perfection looks like.
    attractor_md = ""
    if records:
        org_state = OrganismState.from_telemetry(records[-1])
        attractor_md = format_attractor_markdown(org_state, attractor)
        # Update shared state for Φ governor
        _shared.push_telemetry(records[-1])
    if attractor_md:
        niche_md = (niche_md + "\n\n" + attractor_md).strip() if niche_md else attractor_md

    # ── 4. READ CURRENT ARCHITECTURE ────────────────────────────────
    try:
        full_source = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")
        arch_src = _extract_nn_architecture(full_source)
        if not arch_src:
            print("[mutator] No nn.Module classes found -- skipping.")
            return
    except Exception as exc:
        print(f"[mutator] Failed to read architecture: {exc}")
        return

    # ── 4b. TICK 15.0: TARGETED MUTATION (Surgical Strike) ─────────
    # If gradient data exists, try targeted mutation on the bottleneck
    # organelle FIRST.  If it succeeds, skip the full-architecture LLM call.
    targeted_result = _attempt_targeted_mutation(
        fs=fs,
        full_source=full_source,
        threshold=threshold,
        best_epi=best_epi,
        recipe=recipe,
        meta_fitness=meta_fitness,
        dynamic_params=dynamic_params,
        crash_context=crash_context,
        physics_profile=physics_md,
        gradient_md=gradient_md,
        environment_profile=env_md,
    )

    if targeted_result is not None:
        n_targeted, targeted_probe_stats = targeted_result
        _loop_state["last_mutation_tick"] = records[-1].get("tick", 0) if records else 0
        _loop_state["mutations_generated"] += n_targeted

        # Persist probe stats
        fs.write("telemetry/sandbox_probe_stats.json", {
            **targeted_probe_stats, "t": time.time(),
        })

        fs.append("logs/mutator_events.ndjson", {
            "mutation": _loop_state["mutations_generated"],
            "reason": f"targeted_{reason}",
            "mode": "targeted_organelle",
            "recipe_version": recipe_version,
            "variants_written": n_targeted,
            "t": time.time(),
        })

        print(f"[mutator] Targeted mutation complete: {n_targeted} candidates")

        # Also attempt organelle assembly (Horizontal Gene Transfer)
        n_assembled, _mcts_stats = _attempt_organelle_assembly(fs)
        if n_assembled:
            _loop_state["mutations_generated"] += n_assembled

        # ── TICK 18.0: Keep Φ/MDL current even on targeted-mutation fast-path
        dual_brain.update(fs, records)
        # ── TICK 20.0: Niche Construction on Heat Death ───────────────
        _trigger_niche_if_heat_death(
            fs=fs,
            dual_brain=dual_brain,
            best_epi=best_epi,
            workspace_root=_workspace_root,
            niche_state=niche_state,
        )

        # Track recipe performance and check meta-stagnation
        delta_epi = meta_fitness.get("delta_epi", 0.0)
        _track_recipe_performance(fs, recipe_version, best_epi, delta_epi)

        meta_triggered = meta_stagnation_tracker.record(best_epi)
        if meta_triggered:
            meta_success = _run_meta_evolution(
                fs=fs, recipe=recipe, records=records,
                meta_tracker=meta_stagnation_tracker,
                meta_fitness=meta_fitness,
                recipe_trial=recipe_trial,
                constraint_matrix=constraint_matrix,
            )
            meta_stagnation_tracker.reset()

        return

    # ── 5. TRI-AGENT PIPELINE (TICK 24.1) ────────────────────────────
    # Replaces _dual_brain_dispatch, _enhanced_llm_call, _slow_brain_call.
    # Single unified Architect → Coder → Test-Runner pipeline.
    dual_brain.update(fs, records)

    # Identify target organelle (gradient bottleneck or default)
    from genome_assembler import identify_bottleneck_organelle
    grad_profile_raw = _read_gradient_profile_raw(fs)
    bottleneck = identify_bottleneck_organelle(grad_profile_raw) if grad_profile_raw else None
    if bottleneck is None:
        bottleneck = "routing"  # default target per Immutable Scaffold (TICK 23.0)
    organelle_src = extract_organelle_source(full_source, bottleneck)
    if organelle_src is None:
        print(f"[mutator] Cannot extract {bottleneck} organelle — skipping.")
        return
    class_name = ORGANELLE_TYPES[bottleneck]["class_name"]

    t_pipeline_start = time.time()
    meta_fitness["best_epi"] = best_epi  # pass through for Architect
    variants = _tri_agent_pipeline(
        fs=fs,
        organelle_src=organelle_src,
        class_name=class_name,
        organelle_type=bottleneck,
        meta_fitness=meta_fitness,
        dynamic_params=dynamic_params,
        recipe=recipe,
        gradient_md=gradient_md,
        crash_context=crash_context,
    )
    t_pipeline_elapsed = time.time() - t_pipeline_start

    if not variants:
        print("[mutator] Tri-agent pipeline returned no validated variants.")
        dual_brain.record_local_failure()
        return

    dual_brain.record_local_success()

    # ── TICK 20.0: Niche Construction on Heat Death ──────────────────
    _trigger_niche_if_heat_death(
        fs=fs,
        dual_brain=dual_brain,
        best_epi=best_epi,
        workspace_root=_workspace_root,
        niche_state=niche_state,
    )

    # ── 6. WRITE VALIDATED VARIANTS ──────────────────────────────────
    # Variants are already validated by the Test-Runner subprocess.
    n_written = 0
    for vi, variant_code in enumerate(variants):
        patched = _ast_replace_in_source(full_source, variant_code)
        if patched is None:
            print(f"[mutator] Variant {vi + 1}: AST patch failed -- discarded.")
            continue

        # ── POWER-LAW SUBSTRATE: BarbellFilter veto (Site 2 — Slow Loop / Tri-Agent) ──
        # Main thread only — subprocess is already dead. Python scalars only (MLX-safe).
        _s_params = sum(
            int(m) for m in __import__("re").findall(r"\b(\d+)\b", variant_code)
            if 64 <= int(m) <= 65536
        ) or 1
        _s_epi_delta = meta_fitness.get("delta_epi", 0.0)
        _s_leverage = compute_leverage_score(
            epi_delta=max(_s_epi_delta, 0.0),
            reuse_count=1,
            cross_domain_potential=max(evolvability, 1e-6),
            total_params=max(_s_params, 1),
        )
        _s_barbell = classify_candidate(
            param_delta=_s_params,
            epi_delta=max(_s_epi_delta, 0.0),
            leverage_score=_s_leverage,
        )
        if _s_barbell == "MEDIUM":
            print(
                f"[barbell] VETO: Medium Risk/Reward — thermodynamic waste discarded. "
                f"variant={vi + 1} epi_delta={_s_epi_delta:.4f} leverage={_s_leverage:.3f}"
            )
            continue
        # ─────────────────────────────────────────────────────────────────────────

        written = _write_candidate(fs, variant_code, variant_idx=vi + 1)
        if written:
            n_written += 1
            _loop_state["mutations_generated"] += 1
            print(f"[mutator] Variant {vi + 1} [tri-agent] queued: {written.name}")

    if n_written > 0:
        _loop_state["last_mutation_tick"] = records[-1].get("tick", 0) if records else 0

        fs.append("logs/mutator_events.ndjson", {
            "mutation": _loop_state["mutations_generated"],
            "reason": reason,
            "llm_time_s": round(t_pipeline_elapsed, 1),
            "threshold": threshold,
            "best_epi": best_epi,
            "variants_written": n_written,
            "recipe_version": recipe_version,
            "compute_mode": dynamic_params["mode"],
            "evolvability_score": evolvability,
            "velocity_z_score": round(velocity_z, 3),
            "island_samples": n_sampled,
            "brain": "tri-agent",
            "organelle_target": bottleneck,
            "dual_brain_state": dual_brain.state_summary,
            "t": time.time(),
        })
        print(f"[mutator] Batch complete: {n_written} candidates "
              f"queued ({t_pipeline_elapsed:.1f}s) [tri-agent]")

        # ── Slow Brain post-shift bookkeeping ─────────────────────────
        if dual_brain.slow_brain_active:
            dual_brain.reset_slow_brain()
    else:
        print("[mutator] All variants failed AST patching.")

    # ── 8b. TICK 17.0: MCTS ASSEMBLY (Fast Brain) ────────────────────
    # After a normal mutation, the MCTS assembler runs as the "Fast Brain"
    # to find the optimal organelle combination in milliseconds, bypassing
    # the heavy LLM ("Slow Brain") for assembly decisions.
    n_assembled, mcts_stats = _attempt_organelle_assembly(fs)
    if n_assembled:
        _loop_state["mutations_generated"] += n_assembled
        if mcts_stats:
            fs.append("logs/mutator_events.ndjson", {
                "mutation": "mcts_assembly",
                "rollouts": mcts_stats.get("rollouts", 0),
                "elapsed_ms": mcts_stats.get("elapsed_ms", 0),
                "best_phi": mcts_stats.get("best_value", 0),
                "pareto_pool": mcts_stats.get("pareto_pool_sizes", {}),
                "warm_start_paths": mcts_stats.get("warm_start_paths", 0),
                "t": time.time(),
            })

    # ── 9. RECIPE PERFORMANCE TRACKING (TICK 10.0) ────────────────
    delta_epi = meta_fitness.get("delta_epi", 0.0)
    _track_recipe_performance(fs, recipe_version, best_epi, delta_epi)

    # ── 10. META-STAGNATION CHECK (TICK 10.0) ─────────────────────
    meta_triggered = meta_stagnation_tracker.record(best_epi)
    if meta_triggered:
        print(f"[mutator] Meta-stagnation detected: {meta_stagnation_tracker.consecutive_flat} "
              f"flat batches (high_water={meta_stagnation_tracker.best_epi_high_water:.4f})")

        meta_success = _run_meta_evolution(
            fs=fs,
            recipe=recipe,
            records=records,
            meta_tracker=meta_stagnation_tracker,
            meta_fitness=meta_fitness,
            recipe_trial=recipe_trial,
            constraint_matrix=constraint_matrix,
        )
        meta_stagnation_tracker.reset()

        if meta_success:
            # Force recipe reload on next cycle
            print("[mutator] Cognitive framework replaced. Reloading on next cycle.")



def run(poll_interval: float = 30.0) -> None:
    """Continuous mutation loop with meta-evolution capabilities.

    1. Load hot-swappable mutation recipe.
    2. Poll evaluator telemetry for mutation triggers (meta-fitness aware).
    3. Sample island archives for cross-pollination.
    4. Read recent crash logs for error-as-feature injection (TICK 7.1).
    5. Compute dynamic Ollama parameters from velocity.
    6. Prompt 35B model with Deep Mindset protocol (thinking + batch).
    7. Extract <core_thinking_sequence>, log to console (TICK 7.1).
    8. Parse N architectural variants from LLM response.
    9. Write each valid variant to pool as separate candidate files.
    10. Attempt recipe hot-swap if LLM proposed one.
    11. Track recipe performance and check meta-stagnation (TICK 10.0).
    12. If META_EVOLUTION triggered, rewrite own prompt instead of arch.
    13. Sleep and repeat.
    """
    fs = FileSystemBus(root="agi_workspace")

    # Ensure directory structure
    for d in [_CANDIDATE_DIR, _ISLAND_GOOD_DIR, _ISLAND_EXPLORE_DIR, _ISLAND_META_DIR]:
        (Path(fs.root) / d).mkdir(parents=True, exist_ok=True)
    # TICK 15.0: Organelle directories
    for org_type in ORGANELLE_TYPES:
        (Path(fs.root) / ORGANELLE_BASE_DIR / org_type).mkdir(parents=True, exist_ok=True)
    (Path(fs.root) / ASSEMBLY_DIR).mkdir(parents=True, exist_ok=True)

    velocity_tracker = VelocityTracker()
    meta_stagnation_tracker = MetaStagnationTracker()
    recipe_trial = RecipeTrial()          # TICK 16.0: A/B testing state machine
    dual_brain = DualBrainRouter()        # TICK 18.0: Φ-gated Dual-Brain Engine

    # Load recipe (hot-swappable)
    recipe = _load_recipe()
    recipe_version = getattr(recipe, "RECIPE_VERSION", "unknown")

    # ── TICK 20.1: Rule-IR Constraint Matrix ─────────────────────────────
    constraint_matrix = load_or_compile_matrix(
        str(Path(fs.root).resolve()), recipe,
    )
    attractor = get_default_attractor()
    # Connect to Autopoietic Core shared state (if running unified mode)
    _shared = get_shared_state()
    _shared.constraint_matrix = constraint_matrix
    _shared.attractor = attractor
    _phi_governor = get_phi_governor()

    print(f"[mutator] Slow Loop starting (TICK 20.1: Grand Collapse + Dual-Brain Engine).")
    print(f"[mutator] model={_LLM_MODEL} timeout={_MUTATOR_LLM_TIMEOUT}s poll={poll_interval}s")
    print(f"[mutator] Recipe version: {recipe_version} | batch_size={getattr(recipe, 'BATCH_SIZE', 1)}")
    print(f"[mutator] Islands: good={_ISLAND_GOOD_DIR}, explore={_ISLAND_EXPLORE_DIR}")
    print(f"[mutator] TICK 24.1 Tri-Agent: test_runner_timeout={_TEST_RUNNER_TIMEOUT_S}s")
    print(f"[mutator] TICK 10.0 Meta-Cognition: stagnation_trigger={_META_STAGNATION_BATCHES} batches")
    print(f"[mutator] TICK 15.0 Endosymbiosis: organelles={list(ORGANELLE_TYPES.keys())}")
    print(f"[mutator] TICK 16.0 Double-Loop: shadow_batch={_SHADOW_BATCH_SIZE}, "
          f"eval_wait={_SHADOW_EVAL_WAIT_S}s, min_ticks={_SHADOW_MIN_TICKS}")
    print(f"[mutator] TICK 17.0 Pareto-MCTS: Fast Brain assembly with Φ tax, "
          f"80/20 Pareto policy, warm-start")
    print(f"[mutator] TICK 18.0 Dual-Brain: Fast={_FAST_BRAIN_MODEL} "
          f"budget≤{_FAST_BRAIN_COMPUTE_BUDGET_PCT*100:.0f}% | "
          f"Slow={_SLOW_BRAIN_MODEL} "
          f"(Φ-drop>{_SLOW_BRAIN_PHI_DROP_PCT*100:.0f}%×{_SLOW_BRAIN_PHI_CONSECUTIVE_GENS}gens "
          f"| MDL-bloat≥{_SLOW_BRAIN_MDL_BLOAT_PCT*100:.0f}%) | "
          f"Tax≤{_SLOW_BRAIN_TAX_CEILING*100:.0f}%")
    print(f"[mutator] TICK 20.0 Niche Evolver: Heat Death trigger → MuZero Niche Construction"
          f"(cooldown={_NICHE_COOLDOWN_S:.0f}s, oracle_veto=80% tax)")
    print(f"[mutator] TICK 20.1 Rule-IR Matrix: v{constraint_matrix.version} "
          f"(gradient meta-evo={'ON' if _RULE_IR_META_EVOLUTION else 'OFF'})")
    print(f"[mutator] TICK 20.1 Attractor: Φ_max={attractor.phi_max:.4f} "
          f"lat_min={attractor.latency_min_ms:.3f}ms")

    # ── TICK 8.0: Physics schema for Self-Model injection ─────────────
    physics_schema = get_physics_schema()
    physics_md = _physics_to_markdown(physics_schema)
    print(f"[mutator] TICK 8.0 Sensor Bus: {physics_schema.get('memory', {}).get('total_gb', '?')} GB RAM, "
          f"{physics_schema.get('compute', {}).get('cpu_cores', '?')} cores")

    # ── TICK 20.0: Niche state (mutable, persists across loop iterations) ─
    niche_state: Dict[str, Any] = {"last_generated_t": 0.0, "active_config": None}
    # Pre-load workspace root for niche IPC writes
    _workspace_root: str = str(Path(fs.root).resolve())
    # TICK 21.5: Mutable loop state for crash-resilient function extraction
    _loop_state: Dict[str, Any] = {
        "last_mutation_tick": 0,
        "mutations_generated": 0,
    }

    _loop_cycle = 0
    while True:
        _loop_cycle += 1
        # ── TICK 21.5: Heartbeat (proof of life for silent-death diagnosis) ──
        print(f"[mutator] heartbeat cycle={_loop_cycle} t={time.time():.0f}",
              flush=True)
        try:
            _run_one_cycle(
                fs=fs,
                poll_interval=poll_interval,
                recipe_trial=recipe_trial,
                meta_stagnation_tracker=meta_stagnation_tracker,
                velocity_tracker=velocity_tracker,
                dual_brain=dual_brain,
                constraint_matrix=constraint_matrix,
                attractor=attractor,
                physics_md=physics_md,
                niche_state=niche_state,
                _workspace_root=_workspace_root,
                _shared=_shared,
                _loop_state=_loop_state,
            )
        except Exception:
            print(f"\n{'!'*70}", flush=True)
            print(f"[mutator] THREAD CRASH CAUGHT — cycle {_loop_cycle}",
                  flush=True)
            traceback.print_exc()
            print(f"[mutator] Resurrecting in {poll_interval}s...", flush=True)
            print(f"{'!'*70}\n", flush=True)
        time.sleep(poll_interval)


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TICK 20.1 -- Mutator Daemon (Slow Loop). "
        "Grand Collapse: Rule-IR Constraint Matrix (gradient meta-evo), "
        "Teleological Attractor (future-guided MCTS), Φ Governor, "
        "Asymmetric Dual-Brain Engine, Thermodynamic Pareto-MCTS Assembly, "
        "Double-Loop Meta-Governance, Endosymbiosis, Targeted Mutation, "
        "Gradient Oracle, Meta-Cognitive Prompt Evolution, Agentic Loop."
    )
    parser.add_argument(
        "--poll-interval", type=float, default=30.0,
        help="Seconds between telemetry checks (default: 30)",
    )
    args = parser.parse_args()
    try:
        run(poll_interval=args.poll_interval)
    except KeyboardInterrupt:
        print("\n[mutator] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
