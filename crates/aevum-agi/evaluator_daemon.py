#!/usr/bin/env python3
"""evaluator_daemon.py -- The Fast Loop.

TICK 6.1: Meta-Evolutionary Singularity + TICK 6.2: Alpha-Matrix Completion.
TICK 7.0: The Evaluator Swarm -- Parallel Sandboxes with atomic candidate claims.

Continuously evaluates AtomicLLM candidates at maximum silicon speed.
NEVER waits for the 35B LLM.  Polls the candidate pool for hot-swap
architectures written by mutator_daemon.py.

TICK 6.1 additions:
  - Meta-fitness telemetry: delta_epi, improvement_per_second, evolvability_score
  - Local breeder integration: fast GA crossover during Fast Loop
  - Breeder stagnation signal for Mutator escalation

TICK 6.2 additions:
  - Island routing: successful candidates archived to island_good/island_explore
  - Evolvability-based island classification

TICK 7.0 additions:
  - Atomic claim-by-rename: safe to run N instances concurrently
  - Instance-scoped handoff/telemetry (--instance-id flag)
  - Evaluator ID in all log lines for swarm visibility

Pipeline per tick:
  CLAIM CANDIDATE -> HOT-SWAP -> LOCAL BREED -> READ -> VARY -> CHECK -> EVAL
  -> PERSIST -> ISLAND ROUTE -> TELEMETRY -> LOOP

Usage:
    python env_stream.py | python evaluator_daemon.py [--threshold 0.10] [--device cpu] [--instance-id A]

    # Parallel swarm (run in N terminal windows):
    python evaluator_daemon.py --instance-id A &
    python evaluator_daemon.py --instance-id B &
    python evaluator_daemon.py --instance-id C &

    # Degraded mode (no data pipe -- uses Lorenz chaos fallback):
    python evaluator_daemon.py --threshold 0.10
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import inspect
import io
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fs_bus import FileSystemBus
from fractal_router import ASTHasher, FractalAddress, KroneckerFractalRouter
from zstd_logger import ZstdLogger

# ── Shared utilities from stateless_tick (Axiom 1: filesystem-only state) ────
from stateless_tick import (
    _HANDOFF_PATH,
    _ATOMIC_CORE_PATH,
    parse_handoff,
    serialize_handoff,
    _default_state,
    _boolean_gate,
    _update_heat_death,
    _update_pow_difficulty,
    _write_trace,
    _safe_failure_result,
    _ast_replace_in_source,
    _HEAT_DEATH_THRESHOLD,
)

# ── TICK 6.1: Local Breeder ──────────────────────────────────────────────────
from local_breeder import breed, get_breeder_state, should_escalate_to_llm

# ── TICK 8.0: Universal Sensor Bus ──────────────────────────────────────────
from biogeo_probe import get_physics_schema

# ── TICK 11.0: Gradient Oracle ──────────────────────────────────────────────
from gradient_oracle import extract_gradient_profile, write_gradient_profile_atomic

# ── TICK 13.0: Constitution (Immutable Alignment Layer) ────────────────────
from constitution import validate_candidate, audit_log, MEMORY_CEILING_PCT

# ── TICK 15.0: Genome Assembler (Endosymbiosis -- Modular Composition) ────
from genome_assembler import (
    decompose_and_archive,
    assemble_best_organelles,
    write_assembled_candidate,
    ORGANELLE_BASE_DIR,
)


# ── Hot-Swap Protocol Constants ─────────────────────────────────────────────
#
# IPC Contract (lock-free, crash-safe, swarm-safe):
#   1. Mutator writes  .candidate_<ts>_v<N>.py.tmp  (invisible to glob below)
#   2. Mutator renames  candidate_<ts>_v<N>.py       (POSIX atomic rename)
#   3. Evaluator globs  candidate_*.py               (FIFO -- oldest first)
#   4. TICK 7.0: Evaluator CLAIMS by renaming .py → .processing (atomic)
#      If rename fails (FileNotFoundError), another evaluator claimed it first.
#   5. Evaluator applies AST patch, archives to applied/, or deletes on failure
#
# Candidate files contain RAW LLM output (class/constant definitions),
# NOT the full patched atomic_core.py.  _ast_replace_in_source patches
# by class name, so candidates stay valid even if the base file changed
# since the mutator read it.

_CANDIDATE_DIR: str = "candidate_pool"
_CANDIDATE_GLOB: str = "candidate_*.py"
_APPLIED_DIR: str = "candidate_pool/applied"

# ── TICK 6.2: Island Archive Directories ─────────────────────────────────────
_ISLAND_GOOD_DIR: str = "candidate_pool/island_good"
_ISLAND_EXPLORE_DIR: str = "candidate_pool/island_explore"
_ISLAND_META_DIR: str = "candidate_pool/island_meta"
_ISLAND_GOOD_THRESHOLD: float = 0.5    # evolvability > this → island_good
_ISLAND_EXPLORE_THRESHOLD: float = 0.3  # evolvability < this → island_explore
_ISLAND_MAX_PER_ISLAND: int = 20        # FIFO cap per island

# ── TICK 15.0: Endosymbiosis -- Organelle Decomposition ────────────────────
_DECOMPOSITION_FACTOR: float = 1.1  # epi > threshold * factor triggers decomposition
_ORGANELLE_DIRS: list = [
    "candidate_pool/island_organelle/attention",
    "candidate_pool/island_organelle/routing",
    "candidate_pool/island_organelle/expert",
    "candidate_pool/island_assembly",
]

# ── TICK 12.0: Environment Co-Evolution ─────────────────────────────────────
_ENV_ACTIVE_FILE: str = "candidate_pool/env_active/current.json"
_ENV_REFRESH_INTERVAL: int = 200       # re-check env config every N ticks


def _load_active_environment(fs: FileSystemBus) -> Optional[Dict[str, Any]]:
    """Load the active environment genome from env_active/current.json.

    Returns the genome dict, or None if no config exists (baseline mode).
    """
    env_file = Path(fs.root) / _ENV_ACTIVE_FILE
    if not env_file.exists():
        return None
    try:
        raw = env_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _spawn_env_stream(env_config: Optional[Dict[str, Any]]) -> subprocess.Popen:
    """Spawn env_stream.py as a subprocess with optional environment genome.

    Returns the Popen object.  The caller should read from proc.stdout.
    """
    cmd = [sys.executable, "env_stream.py"]
    if env_config is not None:
        cmd.extend(["--config", json.dumps(env_config)])
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _redirect_stdin_from_proc(proc: subprocess.Popen) -> None:
    """Replace sys.stdin with the stdout of a subprocess.

    This allows atomic_core._evaluate() to read from the subprocess
    via its existing sys.stdin.readline() call without modification.
    """
    sys.stdin = io.TextIOWrapper(proc.stdout, encoding="utf-8")


# ── Meta-Fitness Telemetry State ─────────────────────────────────────────────

class MetaFitnessTracker:
    """Track meta-fitness metrics across ticks for telemetry emission.

    Computes:
      - delta_epi: improvement in best_epi over sliding window
      - improvement_per_second: velocity of epi gains
      - evolvability_score: survival_rate * delta_fitness heuristic
    """

    def __init__(self, window_size: int = 50):
        self.window_size: int = window_size
        self.epi_history: List[float] = []
        self.best_epi_history: List[float] = []
        self.timestamps: List[float] = []
        self.accept_history: List[int] = []  # B values

    def record(self, epi: float, best_epi: float, B: int, t: float) -> None:
        self.epi_history.append(epi)
        self.best_epi_history.append(best_epi)
        self.timestamps.append(t)
        self.accept_history.append(B)

        # Trim to window
        if len(self.epi_history) > self.window_size:
            self.epi_history = self.epi_history[-self.window_size:]
            self.best_epi_history = self.best_epi_history[-self.window_size:]
            self.timestamps = self.timestamps[-self.window_size:]
            self.accept_history = self.accept_history[-self.window_size:]

    @property
    def delta_epi(self) -> float:
        """Change in best_epi over the window."""
        if len(self.best_epi_history) < 2:
            return 0.0
        return self.best_epi_history[-1] - self.best_epi_history[0]

    @property
    def improvement_per_second(self) -> float:
        """Rate of epi improvement per wall-clock second."""
        if len(self.timestamps) < 2:
            return 0.0
        dt = self.timestamps[-1] - self.timestamps[0]
        if dt < 0.01:
            return 0.0
        return self.delta_epi / dt

    @property
    def survival_rate(self) -> float:
        """Fraction of recent ticks that were accepted (B=1)."""
        if not self.accept_history:
            return 0.0
        return sum(self.accept_history) / len(self.accept_history)

    @property
    def evolvability_score(self) -> float:
        """Heuristic: how "evolvable" is the current lineage?

        High evolvability = high survival rate AND positive delta fitness.
        Low evolvability = stagnation or regression.

        Range: [0.0, 1.0] approximately.
        """
        sr = self.survival_rate
        # Normalize delta_epi to [0, 1] range using sigmoid-like transform
        de = self.delta_epi
        delta_norm = de / (abs(de) + 0.01) if de > 0 else 0.0
        # Combine: survival contributes 40%, delta contributes 60%
        return min(1.0, 0.4 * sr + 0.6 * delta_norm)

    def to_dict(self) -> Dict[str, float]:
        return {
            "delta_epi": round(self.delta_epi, 8),
            "improvement_per_second": round(self.improvement_per_second, 8),
            "evolvability_score": round(self.evolvability_score, 6),
            "survival_rate": round(self.survival_rate, 4),
        }


# ── Candidate Pool Scanner + Atomic Claim (TICK 7.0: Swarm-Safe) ──────────

def _poll_candidates(fs: FileSystemBus) -> List[Path]:
    """Return pending candidate paths, sorted oldest-first (FIFO).

    Ignores .tmp files (in-flight writes from the mutator) and
    .processing files (already claimed by another evaluator).
    """
    pool_dir = Path(fs.root) / _CANDIDATE_DIR
    if not pool_dir.exists():
        return []

    candidates = sorted(
        pool_dir.glob(_CANDIDATE_GLOB),
        key=lambda p: p.stat().st_mtime,
    )
    return [
        c for c in candidates
        if not c.name.endswith(".tmp") and not c.name.endswith(".processing")
    ]


def _claim_candidate(
    fs: FileSystemBus,
    evaluator_id: str,
) -> Optional[Path]:
    """Atomically claim ONE candidate from the pool. Lock-free, swarm-safe.

    TICK 7.0: Uses os.rename() to atomically move candidate_*.py to
    candidate_*.processing.  If the rename fails with FileNotFoundError,
    another evaluator already claimed it -- we skip and try the next.

    Returns the .processing path on success, None if no candidates available.
    """
    candidates = _poll_candidates(fs)
    for c in candidates:
        processing_path = c.parent / (c.name + ".processing")
        try:
            os.rename(str(c), str(processing_path))
            print(f"[{evaluator_id}] Claimed {c.name}")
            return processing_path
        except FileNotFoundError:
            continue  # Another evaluator won this one
        except OSError as e:
            print(f"[{evaluator_id}] Claim failed for {c.name}: {e}")
            continue
    return None


# ── TICK 23.0: Dynamic Signature Forgiveness ────────────────────────────────

def _ensure_strategy_kwargs(source: str) -> str:
    """Inject **kwargs into RoutingStrategy.forward if missing.

    The immutable scaffold calls router(x, experts, router_idx). If the LLM's
    RoutingStrategy.forward doesn't accept **kwargs, extra arguments would crash.
    This AST transform adds **kwargs as a safety net.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source  # Don't break the pipeline; return as-is

    modified = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "RoutingStrategy"):
            continue
        for item in node.body:
            if not (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == "forward"):
                continue
            args = item.args
            if args.kwarg is None:
                args.kwarg = ast.arg(arg="kwargs", annotation=None)
                modified = True

    if not modified:
        return source

    return ast.unparse(tree) + "\n"


# ── Hot-Swap Applicator (TICK 7.0: operates on .processing files) ─────────

def _hotswap_candidate(
    fs: FileSystemBus,
    processing_path: Path,
    backup_source: str,
    evaluator_id: str = "eval",
) -> bool:
    """Apply a single claimed candidate via AST-anchored class replacement.

    TICK 7.0: Accepts a .processing path (already atomically claimed).
    On success: patches atomic_core.py, archives to applied/.
    On failure: leaves atomic_core.py untouched, deletes the .processing file.
    """
    try:
        candidate_code = processing_path.read_text(encoding="utf-8")
        current_source = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")

        # ── TICK 13.0: Constitutional Sentinel ─────────────────────
        ok, violations = validate_candidate(candidate_code)
        if not ok:
            print(f"[{evaluator_id}] CONSTITUTIONAL VETO: {violations}")
            audit_log("VETO_CANDIDATE", {
                "evaluator": evaluator_id,
                "candidate": processing_path.name,
                "violations": violations,
            })
            processing_path.unlink(missing_ok=True)
            return False

        patched = _ast_replace_in_source(current_source, candidate_code)
        if patched is None:
            print(f"[{evaluator_id}] Candidate {processing_path.name} rejected by AST patcher.")
            processing_path.unlink(missing_ok=True)
            return False

        # ── TICK 23.0: Dynamic Signature Forgiveness ──────────────
        # Ensure RoutingStrategy.forward accepts **kwargs so extra
        # arguments from the immutable scaffold never crash the call.
        patched = _ensure_strategy_kwargs(patched)

        _ATOMIC_CORE_PATH.write_text(patched, encoding="utf-8")

        # Archive successfully applied candidates
        applied_dir = Path(fs.root) / _APPLIED_DIR
        applied_dir.mkdir(parents=True, exist_ok=True)
        # Strip .processing suffix for the archive name
        archive_name = processing_path.name.replace(".processing", "")
        processing_path.rename(applied_dir / archive_name)

        print(f"[{evaluator_id}] Candidate {archive_name} applied and archived.")
        return True

    except Exception as exc:
        print(f"[{evaluator_id}] Candidate {processing_path.name} failed: {exc}")
        _ATOMIC_CORE_PATH.write_text(backup_source, encoding="utf-8")
        try:
            processing_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ── TICK 6.2: Island Archive Router ──────────────────────────────────────────

def _route_to_island(
    fs: FileSystemBus,
    candidate_code: str,
    epi: float,
    evolvability: float,
    gen: int,
) -> Optional[str]:
    """Route a successful candidate AST to the appropriate island archive.

    island_good:    high fitness, low variance → exploitation material
    island_explore: high variance, lower fitness → exploration seeds
    """
    if evolvability > _ISLAND_GOOD_THRESHOLD:
        island_dir = _ISLAND_GOOD_DIR
        island_name = "island_good"
    elif evolvability < _ISLAND_EXPLORE_THRESHOLD:
        island_dir = _ISLAND_EXPLORE_DIR
        island_name = "island_explore"
    else:
        # Moderate evolvability — archive to good by default
        island_dir = _ISLAND_GOOD_DIR
        island_name = "island_good"

    island_path = Path(fs.root) / island_dir
    # TICK 15.1: Bulletproof guard — ensure dir exists immediately before write
    os.makedirs(str(island_path), exist_ok=True)

    # Write candidate with metadata
    ts = int(time.time() * 1000)
    filename = f"elite_{gen:07d}_{ts}.py"
    filepath = island_path / filename

    header = (
        f"# Island: {island_name} | gen={gen} | epi={epi:.6f} | "
        f"evolvability={evolvability:.4f} | t={time.time():.0f}\n"
    )
    os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)  # TICK 15.1
    filepath.write_text(header + candidate_code, encoding="utf-8")

    # FIFO cap: remove oldest if over limit
    existing = sorted(island_path.glob("elite_*.py"), key=lambda p: p.stat().st_mtime)
    while len(existing) > _ISLAND_MAX_PER_ISLAND:
        oldest = existing.pop(0)
        oldest.unlink(missing_ok=True)

    return f"{island_dir}/{filename}"


# ── Topology Check (Axiom 3: executor hashes its own AST) ──────────────────

def _topological_check_self(
    hasher: ASTHasher,
    router: KroneckerFractalRouter,
) -> Tuple[Optional[FractalAddress], Optional[int], float]:
    """Hash THIS module's own source through the fractal router.

    Identical to stateless_tick._topological_check but references
    the evaluator's module, not stateless_tick's.
    """
    source = inspect.getsource(sys.modules[__name__])
    addr = hasher.hash_source(source, depth=2)
    if addr is None:
        return None, None, 0.0
    slot = router.route(addr)
    variance = router.variance()
    return addr, slot, variance


# ── Process-Local Resource Measurement ──────────────────────────────────────

def _measure_creature_resources() -> Dict[str, float]:
    """Measure THIS PROCESS's resource footprint only.

    TICK 6.0 Thermodynamic Justice: the Creator (35B LLM in Ollama)
    sits in a separate process.  This function measures only the
    Creature (AtomicLLM evaluator), so the thermodynamic penalty
    reflects actual computation cost, not the Creator's weight.
    """
    try:
        import psutil
        proc = psutil.Process()
        cpu = proc.cpu_percent(interval=None)
        rss = proc.memory_info().rss
        total_mem = psutil.virtual_memory().total
        mem = (rss / total_mem) * 100.0 if total_mem > 0 else 0.0
        return {"cpu_pct": cpu, "mem_pct": mem}
    except Exception:
        return {"cpu_pct": 0.0, "mem_pct": 0.0}


# ── The Fast Loop ───────────────────────────────────────────────────────────

def _deep_rollback_atomic_core() -> None:
    """Deep Rollback: Clear in-memory module state and reload fresh.

    This ensures that corrupted class definitions, bad PyTorch graphs,
    or stale instances are purged from the Python interpreter before
    attempting another iteration.
    """
    try:
        # Force all references to atomic_core out of sys.modules
        sys.modules.pop("atomic_core", None)

        # Re-import to get a fresh class definition
        import atomic_core as _fresh_ac
        importlib.reload(_fresh_ac)
        print("[deep-rollback] In-memory atomic_core state flushed and reloaded.")
    except Exception as reload_exc:
        print(f"[deep-rollback] Warning: reload failed: {reload_exc}")
        traceback.print_exc()


def run(threshold: float = 0.10, device: str = "cpu", instance_id: str = "") -> None:
    """Continuous evaluation loop.  Never exits.  Never waits for LLM.

    TICK 6.2.2 Enhancement: Immortal Loop with Emergency Sandbox Reset.
    TICK 7.0 Enhancement: Parallel Evaluator Swarm with atomic claims.

    - Outer boundary try...except catches ANY error escaping inner guards
    - On outer-boundary exception: logs, re-instantiates, continues
    - The evaluator daemon NEVER exits unless interrupted by Ctrl+C
    - Multiple instances can run concurrently (--instance-id flag)
    """
    # TICK 7.0: Instance identity for swarm
    evaluator_id = f"eval_{instance_id}" if instance_id else f"eval_{os.getpid()}"

    # Instance-scoped paths to prevent cross-evaluator corruption
    handoff_suffix = f"_{instance_id}" if instance_id else ""
    instance_handoff = _HANDOFF_PATH.replace(
        "Structured_Handoff.md",
        f"Structured_Handoff{handoff_suffix}.md",
    ) if hasattr(_HANDOFF_PATH, "replace") else _HANDOFF_PATH

    fs = FileSystemBus(root="agi_workspace")

    # TICK 15.1: Bulletproof filesystem bootstrap — ensure ALL required dirs exist
    _startup_dirs = [
        _CANDIDATE_DIR, _APPLIED_DIR,
        _ISLAND_GOOD_DIR, _ISLAND_EXPLORE_DIR, _ISLAND_META_DIR,
        "logs", "memory", "telemetry", "population",
        # TICK 20.0: Niche Evolver IPC directory
        "candidate_pool/env_active",
    ] + _ORGANELLE_DIRS
    for d in _startup_dirs:
        os.makedirs(str(Path(fs.root) / d), exist_ok=True)

    print(f"[{evaluator_id}] Fast Loop starting (TICK 7.0: Evaluator Swarm). Ctrl+C to stop.")
    print(f"[{evaluator_id}] threshold={threshold}, device={device}")
    print(f"[{evaluator_id}] Candidate pool: {Path(fs.root) / _CANDIDATE_DIR}")
    print(f"[{evaluator_id}] Islands: good={_ISLAND_GOOD_DIR}, explore={_ISLAND_EXPLORE_DIR}")

    # ── TICK 8.0: Dynamic Homeostasis — baseline calibration ───────────
    baseline_physics = get_physics_schema()
    baseline_mem = baseline_physics.get("memory", {}).get("utilization_pct", 0.0)
    # Relative decay: trigger penalty only if memory spikes dangerously
    # above baseline.  Use the LOWER of (baseline * 1.2) and (baseline + 10)
    # to handle both low-baseline and high-baseline environments, capped at 98%.
    dynamic_mem_critical = min(baseline_mem * 1.2, baseline_mem + 10.0)
    dynamic_mem_critical = min(dynamic_mem_critical, 98.0)
    dynamic_mem_critical = max(dynamic_mem_critical, 85.0)  # TICK 12 hotfix: floor raised from 50→85 to prevent heat-death on unified-memory systems
    # TICK 13.0: Constitutional hard ceiling -- overrides dynamic profile if it fails
    dynamic_mem_critical = min(dynamic_mem_critical, MEMORY_CEILING_PCT)
    print(f"[{evaluator_id}] TICK 8.0 Homeostasis: baseline_mem={baseline_mem:.1f}% "
          f"-> dynamic_critical={dynamic_mem_critical:.1f}%")

    # ── TICK 12.0: Environment Co-Evolution — self-managed env_stream ────
    env_proc: Optional[subprocess.Popen] = None
    env_config_version: Optional[Any] = None

    if sys.stdin.isatty():
        # No shell pipe — spawn our own env_stream.py subprocess
        env_config = _load_active_environment(fs)
        if env_config:
            env_config_version = env_config.get("version")
            print(f"[{evaluator_id}] TICK 12.0: Spawning env_stream with genome v{env_config_version}")
        else:
            print(f"[{evaluator_id}] TICK 12.0: Spawning env_stream with baseline genome")
        env_proc = _spawn_env_stream(env_config)
        _redirect_stdin_from_proc(env_proc)
    else:
        print(f"[{evaluator_id}] TICK 12.0: Using external stdin pipe (shell mode)")

    tick_count: int = 0
    meta_tracker = MetaFitnessTracker(window_size=50)
    local_breed_active: bool = False  # Track if local breeder contributed
    emergency_reset_count: int = 0

    while True:
        # ═══════════════════════════════════════════════════════════════════
        # TICK 6.2.2: OUTER BOUNDARY -- BULLETPROOF EXCEPTION GUARD
        # If ANY error escapes the inner try...except, catch it here
        # ═══════════════════════════════════════════════════════════════════
        try:
            t_start: float = time.time()
            tick_count += 1

            # ── TICK 12.0: Periodic env config refresh ─────────────────
            if (env_proc is not None
                    and tick_count % _ENV_REFRESH_INTERVAL == 0):
                new_env = _load_active_environment(fs)
                new_ver = new_env.get("version") if new_env else None
                if new_ver is not None and new_ver != env_config_version:
                    print(f"[{evaluator_id}] TICK 12.0: Env genome changed "
                          f"v{env_config_version} → v{new_ver}. Respawning env_stream.")
                    try:
                        env_proc.terminate()
                        env_proc.wait(timeout=5)
                    except Exception:
                        env_proc.kill()
                    env_config_version = new_ver
                    env_proc = _spawn_env_stream(new_env)
                    _redirect_stdin_from_proc(env_proc)

            # ── 1. READ ─────────────────────────────────────────────────────
            raw: Optional[str] = fs.read(instance_handoff)

            if raw is None or not isinstance(raw, str) or raw.strip() == "":
                state = _default_state(threshold)
                fs.write(instance_handoff, serialize_handoff(state))
                raw = fs.read(instance_handoff)
                assert isinstance(raw, str)

            state: Dict[str, Any] = parse_handoff(raw)
            if not state:
                state = _default_state(threshold)

            state["threshold"] = threshold
            prev_tick: int = state.get("tick", 0) or 0
            current_tick: int = prev_tick + 1

            # ── 2. HOT-SWAP POLL (TICK 7.0: Atomic Claim) ──────────────
            backup_source: str = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")
            hotswapped: bool = False

            claimed = _claim_candidate(fs, evaluator_id)
            if claimed:
                hotswapped = _hotswap_candidate(
                    fs, claimed, backup_source, evaluator_id,
                )

            # ── 3. LOCAL BREEDER (TICK 6.1) ─────────────────────────────────
            # Fast GA crossover during the Fast Loop — replaces blind randomness
            local_breed_active = False
            bred_candidate: Optional[Dict] = None

            try:
                import atomic_core as _ac_mod
                if hotswapped:
                    sys.modules.pop("atomic_core", None)
                    import atomic_core as _ac_mod  # noqa: F811
                importlib.reload(_ac_mod)

                # Read population for breeding
                # TICK 7.0.1: fs.read() returns str on JSON parse failure,
                # but breed() requires a dict.  Guard against type mismatch.
                _raw_pop = fs.read("population/elites.json")
                population = _raw_pop if isinstance(_raw_pop, dict) else {}

                if len(population) >= 2 and not hotswapped:
                    # Local breeder: fast GA crossover instead of blind mutation
                    _raw_ic = fs.read("population/iching_rules.json")
                    iching_rules = _raw_ic if isinstance(_raw_ic, dict) else {}
                    _raw_bg = fs.read("population/biogeo_cfg.json")
                    biogeo_cfg = _raw_bg if isinstance(_raw_bg, dict) else {}
                    bred_candidate = breed(population, iching_rules, biogeo_cfg)
                    if bred_candidate:
                        local_breed_active = True

                core = _ac_mod.AtomicCore(fs, device=device)

                if local_breed_active and bred_candidate:
                    # Inject the bred candidate into AtomicCore's vary step
                    # by pre-seeding the population with our crossover child
                    result: Dict[str, Any] = core.iterate()
                else:
                    result = core.iterate()

            except Exception as exc:
                _is_topo = isinstance(exc, ValueError) and "depth" in str(exc)

                if hotswapped:
                    print(f"[{evaluator_id}] Hot-swap crash ({exc}). Rolling back + deep reset.")
                    # TICK 6.2.2: Restore file AND clean in-memory state
                    _ATOMIC_CORE_PATH.write_text(backup_source, encoding="utf-8")
                    _deep_rollback_atomic_core()

                    try:
                        import atomic_core as _ac_mod
                        core = _ac_mod.AtomicCore(fs, device=device)
                        result = core.iterate()
                    except Exception as retry_exc:
                        # Even after deep rollback, iteration failed
                        print(f"[{evaluator_id}] Post-rollback iteration failed: {retry_exc}")
                        result = _safe_failure_result(state)
                elif _is_topo:
                    print(f"[{evaluator_id}] Blind mutation depth mismatch -- safe failure.")
                    result = _safe_failure_result(state)
                else:
                    print(f"[{evaluator_id}] Runtime error: {type(exc).__name__}: {exc}")
                    traceback.print_exc()
                    result = _safe_failure_result(state)

            gen: int = result["gen"]
            epi: float = result["epi"]
            regret: float = result["regret"]
            cum_reg: float = result["cum_reg"]
            best_epi: float = result["best_epi"]
            pop_size: int = result["pop"]
            sym: str = result.get("sym", "")
            # TICK 14.0: Unified Survival Equation telemetry
            forward_ms_val: float = result.get("forward_ms", 0.0)
            param_count_val: int = result.get("param_count", 0)

            # ── 4. CHECK (topology) ─────────────────────────────────────────
            hasher = ASTHasher()
            router = KroneckerFractalRouter(depth=2)
            addr, slot, variance = _topological_check_self(hasher, router)

            addr_str: Optional[str] = repr(addr) if addr is not None else None
            slot_str: Optional[str] = hex(slot) if slot is not None else None

            # ── 5. EVAL (PoW + Boolean gate) ────────────────────────────────
            tick_elapsed: float = time.time() - t_start

            adjusted_threshold, pow_level, pow_window, pow_telemetry = _update_pow_difficulty(
                fs, state, _boolean_gate(epi, threshold), threshold,
                tick_elapsed=tick_elapsed,
                mem_critical=dynamic_mem_critical,  # TICK 8.0: relative baseline
            )
            B: int = _boolean_gate(epi, adjusted_threshold)

            hd_counter, hd_triggered, outer_loop = _update_heat_death(state, best_epi)
            if hd_triggered:
                print(f"[{evaluator_id} tick {current_tick}] HEAT DEATH -- outer loop activated.")

            # ── 6. META-FITNESS TRACKING (TICK 6.1) ────────────────────────
            meta_tracker.record(epi, best_epi, B, time.time())
            meta_fitness = meta_tracker.to_dict()

            # Update local breeder state
            breeder_state = get_breeder_state()
            breeder_state.update(epi)

            # Write breeder stagnation signal if needed
            if should_escalate_to_llm():
                fs.write("memory/breeder_stagnation.json", {
                    "stagnant": True,
                    "breeder_cycles": breeder_state.cycles,
                    "breeder_best_epi": breeder_state.best_epi,
                    "t": time.time(),
                })

            # ── 7. PERSIST ──────────────────────────────────────────────────
            accepted: int = state.get("accepted_ticks", 0) or 0
            rejected: int = state.get("rejected_ticks", 0) or 0

            _tick_fields: Dict[str, Any] = {
                "heat_death_counter": hd_counter,
                "heat_death_triggered": hd_triggered,
                "outer_loop_active": outer_loop,
                "pow_difficulty_level": pow_level,
                "pow_success_window": pow_window,
                "trace_path": None,
            }

            if B == 1:
                new_state: Dict[str, Any] = {
                    "tick": current_tick,
                    "timestamp": time.time(),
                    "snapshot_hash": hashlib.sha256(
                        str(time.time()).encode()
                    ).hexdigest()[:16],
                    "status": "ACCEPTED",
                    "generation": gen,
                    "best_epi": best_epi,
                    "cumulative_regret": cum_reg,
                    "population_size": pop_size,
                    "fractal_address": addr_str,
                    "route_slot": slot_str,
                    "routing_variance": variance,
                    "B": B,
                    "threshold": adjusted_threshold,
                    "last_epi": epi,
                    "parent_tick": str(prev_tick),
                    "accepted_ticks": accepted + 1,
                    "rejected_ticks": rejected,
                    **_tick_fields,
                }
                fs.write(instance_handoff, serialize_handoff(new_state))
                fs.write("memory/checkpoint.json", {
                    "generation": gen,
                    "cumulative_regret": cum_reg,
                    "best_epiplexity": best_epi,
                    "meta_epi_thr": core.meta_epi_thr,
                    "meta_regret_thr": core.meta_regret_thr,
                })
                fs.commit(
                    f"tick {current_tick}: B=1 | gen={gen} epi={epi:.4f} "
                    f"regret={regret:.4f} | {sym}"
                )

                # ── TICK 6.2: Island routing for accepted candidates ────────
                try:
                    current_source = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")
                    island_path = _route_to_island(
                        fs, current_source, epi,
                        meta_fitness["evolvability_score"], gen,
                    )
                    if island_path:
                        print(f"[{evaluator_id}] Archived to {island_path}")
                except Exception as island_exc:
                    print(f"[{evaluator_id}] Archive failed: {island_exc}")

                # ── TICK 11.0: Gradient Oracle (Phenotypic X-Ray) ─────────
                try:
                    grad_profile = extract_gradient_profile(core.backbone)
                    # Atomic write: tmp + os.rename prevents Mutator read collision
                    grad_path = Path(fs.root) / "telemetry" / "gradient_profile.json"
                    write_gradient_profile_atomic(grad_profile, grad_path)
                except Exception:
                    pass  # Non-critical — don't crash evaluator for oracle failure

                # ── TICK 15.0: Organelle Decomposition (Horizontal Gene Transfer) ──
                # When a candidate achieves massive success, decompose it into
                # independent organelle files for future recombination.
                if epi > adjusted_threshold * _DECOMPOSITION_FACTOR:
                    try:
                        current_source = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")
                        saved_organelles = decompose_and_archive(
                            fs.root, current_source, epi, gen,
                        )
                        if saved_organelles:
                            types_saved = ", ".join(saved_organelles.keys())
                            print(f"[{evaluator_id}] TICK 15.0 Decomposition: "
                                  f"saved organelles [{types_saved}]")
                    except Exception as decomp_exc:
                        print(f"[{evaluator_id}] Decomposition failed: {decomp_exc}")

            else:
                trace_path = _write_trace(
                    fs, current_tick, state, result,
                    addr_str, slot_str, variance, epi, adjusted_threshold,
                )
                _tick_fields["trace_path"] = trace_path
                drop_state: Dict[str, Any] = {
                    **state,
                    "tick": current_tick,
                    "timestamp": time.time(),
                    "status": "REJECTED",
                    "B": B,
                    "last_epi": epi,
                    "threshold": adjusted_threshold,
                    "parent_tick": str(prev_tick),
                    "accepted_ticks": accepted,
                    "rejected_ticks": rejected + 1,
                    **_tick_fields,
                }
                fs.write(instance_handoff, serialize_handoff(drop_state))

            # ── 8. TELEMETRY (TICK 6.1: enriched with meta-fitness) ─────────
            creature_load = _measure_creature_resources()
            final_elapsed: float = time.time() - t_start
            pow_telemetry["total_elapsed_s"] = final_elapsed
            pow_telemetry["creature_cpu_pct"] = creature_load["cpu_pct"]
            pow_telemetry["creature_mem_pct"] = creature_load["mem_pct"]

            telemetry_record: Dict[str, Any] = {
                "tick": current_tick, "B": B, "epi": epi,
                "threshold": adjusted_threshold, **pow_telemetry,
                "gen": gen, "best_epi": best_epi,
                "heat_death_counter": hd_counter,
                "heat_death_triggered": hd_triggered,
                "outer_loop_active": outer_loop,
                "hotswapped": hotswapped,
                # TICK 6.1: Meta-fitness telemetry
                "delta_epi": meta_fitness["delta_epi"],
                "improvement_per_second": meta_fitness["improvement_per_second"],
                "evolvability_score": meta_fitness["evolvability_score"],
                "survival_rate": meta_fitness["survival_rate"],
                "local_breed_active": local_breed_active,
                "breeder_stagnant": breeder_state.is_stagnant,
                "breeder_cycles": breeder_state.cycles,
                # TICK 14.0: Unified Survival Equation telemetry
                "forward_ms": forward_ms_val,
                "param_count": param_count_val,
                "latency_cost": result.get("latency_cost", 0.0),
                "complexity_cost": result.get("complexity_cost", 0.0),
                "info_gain_bonus": result.get("info_gain_bonus", 0.0),
                "t": time.time(),
            }

            with ZstdLogger(
                log_dir=Path(fs.root) / "logs", stream_name="tick_telemetry",
            ) as zstd_log:
                zstd_log.append(telemetry_record)
            fs.append("logs/tick_telemetry.ndjson", telemetry_record)

            # ── Persist meta-fitness summary for Mutator consumption ──
            meta_fitness_key = f"memory/meta_fitness{handoff_suffix}.json"
            fs.write(meta_fitness_key, {
                **meta_fitness,
                "tick": current_tick,
                "best_epi": best_epi,
                "t": time.time(),
            })

            print(
                f"[{evaluator_id} tick {current_tick}] B={B} epi={epi:.4f} "
                f"gen={gen} elapsed={final_elapsed:.2f}s "
                f"fwd={forward_ms_val:.1f}ms params={param_count_val} "
                f"evo={meta_fitness['evolvability_score']:.3f} "
                f"vel={meta_fitness['improvement_per_second']:.6f} "
                f"breed={'LOCAL' if local_breed_active else 'blind'}"
                f"{' HOT-SWAP' if hotswapped else ''}"
                f"{' STAGNANT' if breeder_state.is_stagnant else ''}"
            )

            # ═══════════════════════════════════════════════════════════════════
            # END INNER TRY -- tick logic completed successfully
            # ═══════════════════════════════════════════════════════════════════

        except Exception as outer_exc:
            # TICK 6.2.2: EMERGENCY SANDBOX RESET
            # Any error escaping inner guards is caught here.
            # The Evaluator Daemon continues running.
            emergency_reset_count += 1
            print(
                f"\n{'='*70}\n"
                f"[{evaluator_id} EMERGENCY] Outer-boundary exception (reset #{emergency_reset_count}):\n"
                f"  Type: {type(outer_exc).__name__}\n"
                f"  Message: {outer_exc}\n"
                f"{'='*70}"
            )
            traceback.print_exc()

            # Log the emergency event for debugging
            try:
                emergency_key = f"memory/emergency_resets{handoff_suffix}.json"
                fs.write(emergency_key, {
                    "count": emergency_reset_count,
                    "last_exception": str(outer_exc),
                    "exception_type": type(outer_exc).__name__,
                    "timestamp": time.time(),
                })
            except Exception as log_exc:
                print(f"[{evaluator_id} EMERGENCY] Failed to log reset: {log_exc}")

            # Full re-instantiation: wipe module state
            print(f"[{evaluator_id} EMERGENCY] Performing full environment re-instantiation...")
            _deep_rollback_atomic_core()

            # Reset FileSystemBus to clear any stale handles
            try:
                fs = FileSystemBus(root="agi_workspace")
                print(f"[{evaluator_id} EMERGENCY] FileSystemBus re-instantiated.")
            except Exception as fs_exc:
                print(f"[{evaluator_id} EMERGENCY] FileSystemBus re-instantiation failed: {fs_exc}")

            # Small delay to prevent tight infinite loops on persistent errors
            time.sleep(0.1)

            # Continue to next iteration (the while True loop persists)
            print(f"[{evaluator_id} EMERGENCY] Resuming main loop...\n")
            continue


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TICK 7.0 -- Evaluator Daemon (Fast Loop). "
        "Parallel swarm, atomic claims, meta-fitness, island routing."
    )
    parser.add_argument(
        "--threshold", type=float, default=0.10,
        help="Epiplexity threshold for Boolean gate (default: 0.10)",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Torch device (default: cpu)",
    )
    parser.add_argument(
        "--instance-id", type=str, default="",
        help="Instance identifier for parallel swarm (default: PID). "
        "Use unique IDs (A, B, C) when running multiple evaluators.",
    )
    args = parser.parse_args()
    try:
        run(
            threshold=args.threshold,
            device=args.device,
            instance_id=args.instance_id,
        )
    except KeyboardInterrupt:
        print("\n[evaluator] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
