#!/usr/bin/env python3
"""stateless_tick.py — Stateless tick executor for the NLAH harness contract.

Each invocation is a clean run: READ -> VARY -> CHECK -> EVAL -> PERSIST -> TERMINATE.
No shared state. No messages.append. Memory lives only on the filesystem.

Axiom 1: No shared state. Memory ONLY in filesystem.
Axiom 2: Deterministic evaluation. Boolean logic only (B in {0, 1}).
Axiom 3: Code and Rules collapsed into single tensor.

Usage:
    python stateless_tick.py [--threshold 0.10] [--device cpu]
"""

from __future__ import annotations

import argparse
import ast
import glob as _glob
import hashlib
import importlib
import inspect
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Module imports (pure logic — no ML dependencies at module level) ──────────
from fs_bus import FileSystemBus
from fractal_router import ASTHasher, FractalAddress, KroneckerFractalRouter
from zstd_logger import ZstdLogger

# ── TICK 22.0: Pydantic Structured Output ─────────────────────────────────────
from llm_schemas import FastNASOutput, get_instructor_client


# ── Handoff parser / serializer ──────────────────────────────────────────────

_HANDOFF_PATH: str = "memory/Structured_Handoff.md"

_FIELD_MAP: Dict[str, Tuple[str, type]] = {
    "tick":              ("tick",              int),
    "timestamp":         ("timestamp",         float),
    "snapshot_hash":     ("snapshot_hash",     str),
    "status":            ("status",            str),
    "generation":        ("generation",        int),
    "best_epi":          ("best_epi",          float),
    "cumulative_regret": ("cumulative_regret", float),
    "population_size":   ("population_size",   int),
    "fractal_address":   ("fractal_address",   str),
    "route_slot":        ("route_slot",        str),
    "routing_variance":  ("routing_variance",  float),
    "B":                 ("B",                 int),
    "threshold":         ("threshold",         float),
    "last_epi":          ("last_epi",          float),
    "parent_tick":       ("parent_tick",       str),
    "accepted_ticks":    ("accepted_ticks",    int),
    "rejected_ticks":    ("rejected_ticks",    int),
    # Tick 1: Holographic Trace Access
    "trace_path":        ("trace_path",        str),
    # Tick 1: Heat Death Detection
    "heat_death_counter":   ("heat_death_counter",   int),
    "heat_death_triggered": ("heat_death_triggered", int),
    "outer_loop_active":    ("outer_loop_active",    int),
    # Tick 1: Dynamic PoW Difficulty
    "pow_difficulty_level": ("pow_difficulty_level",  int),
    "pow_success_window":   ("pow_success_window",   str),
}


def _parse_value(raw: str, target_type: type) -> Any:
    """Coerce a markdown value string to the target Python type."""
    stripped = raw.strip()
    if stripped in ("null", "None", ""):
        return None
    if target_type is int:
        return int(float(stripped))
    if target_type is float:
        return float(stripped)
    return stripped


def parse_handoff(text: str) -> Dict[str, Any]:
    """Parse Structured_Handoff.md into a flat dict."""
    state: Dict[str, Any] = {}
    pattern = re.compile(r"^-\s+(\w+):\s*(.*)$")
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            key, raw = m.group(1), m.group(2)
            if key in _FIELD_MAP:
                _, target_type = _FIELD_MAP[key]
                state[key] = _parse_value(raw, target_type)
    return state


def serialize_handoff(state: Dict[str, Any]) -> str:
    """Serialize state dict back to Structured_Handoff.md format."""

    def _fmt(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, float):
            return f"{v:.6f}" if abs(v) < 1e6 else f"{v:.6e}"
        return str(v)

    return f"""# Structured Handoff State

## Tick Metadata
- tick: {_fmt(state.get('tick', 0))}
- timestamp: {_fmt(state.get('timestamp', 0))}
- snapshot_hash: {_fmt(state.get('snapshot_hash'))}
- status: {_fmt(state.get('status', 'INIT'))}

## Evolution State
- generation: {_fmt(state.get('generation', 0))}
- best_epi: {_fmt(state.get('best_epi', 0.0))}
- cumulative_regret: {_fmt(state.get('cumulative_regret', 0.0))}
- population_size: {_fmt(state.get('population_size', 0))}

## Topological Constraint
- fractal_address: {_fmt(state.get('fractal_address'))}
- route_slot: {_fmt(state.get('route_slot'))}
- routing_variance: {_fmt(state.get('routing_variance', 0.0))}

## Boolean Gate
- B: {_fmt(state.get('B', 0))}
- threshold: {_fmt(state.get('threshold', 0.10))}
- last_epi: {_fmt(state.get('last_epi', 0.0))}

## Lineage
- parent_tick: {_fmt(state.get('parent_tick'))}
- accepted_ticks: {_fmt(state.get('accepted_ticks', 0))}
- rejected_ticks: {_fmt(state.get('rejected_ticks', 0))}

## Holographic Trace
- trace_path: {_fmt(state.get('trace_path'))}

## Heat Death Detection
- heat_death_counter: {_fmt(state.get('heat_death_counter', 0))}
- heat_death_triggered: {_fmt(state.get('heat_death_triggered', 0))}
- outer_loop_active: {_fmt(state.get('outer_loop_active', 0))}

## Dynamic PoW Difficulty
- pow_difficulty_level: {_fmt(state.get('pow_difficulty_level', 1))}
- pow_success_window: {_fmt(state.get('pow_success_window', ''))}
"""


# ── Default initial state ────────────────────────────────────────────────────

def _default_state(threshold: float) -> Dict[str, Any]:
    return {
        "tick": 0,
        "timestamp": 0.0,
        "snapshot_hash": None,
        "status": "INIT",
        "generation": 0,
        "best_epi": 0.0,
        "cumulative_regret": 0.0,
        "population_size": 0,
        "fractal_address": None,
        "route_slot": None,
        "routing_variance": 0.0,
        "B": 0,
        "threshold": threshold,
        "last_epi": 0.0,
        "parent_tick": None,
        "accepted_ticks": 0,
        "rejected_ticks": 0,
        # Tick 1: Holographic Trace Access
        "trace_path": None,
        # Tick 1: Heat Death Detection
        "heat_death_counter": 0,
        "heat_death_triggered": 0,
        "outer_loop_active": 0,
        # Tick 1: Dynamic PoW Difficulty
        "pow_difficulty_level": 1,
        "pow_success_window": "",
    }


# ── Topological constraint check ─────────────────────────────────────────────

def _topological_check(
    hasher: ASTHasher,
    router: KroneckerFractalRouter,
) -> Tuple[Optional[FractalAddress], Optional[int], float]:
    """Hash *this module's own source* through the fractal router.

    Returns (address, route_slot, routing_variance).
    The tick executor's own AST is the candidate — Axiom 3 collapse.
    """
    source = inspect.getsource(sys.modules[__name__])
    addr = hasher.hash_source(source, depth=2)
    if addr is None:
        return None, None, 0.0
    slot = router.route(addr)
    variance = router.variance()
    return addr, slot, variance


# ── Boolean gate (Axiom 2) ───────────────────────────────────────────────────

def _boolean_gate(epi: float, threshold: float) -> int:
    """Deterministic Boolean evaluation. B in {0, 1}. No gray zone."""
    return 1 if epi > threshold else 0


# ── Holographic Trace Access (FIFO Sliding Window) ─────────────────────────

_TRACE_FIFO_SIZE: int = 5  # Keep only last N full traces
_TRACE_DIR: str = "traces"
_TRACE_SUMMARY_FILE: str = "traces/_compressed_history.ndjson"


def _evict_old_traces(fs: FileSystemBus, current_tick: int) -> int:
    """FIFO eviction: keep last _TRACE_FIFO_SIZE full traces.

    Older traces are compressed to a single-line NDJSON summary and deleted.
    Returns the number of evicted traces.
    """
    trace_root = Path(fs.root) / _TRACE_DIR
    if not trace_root.exists():
        return 0

    # Collect all .trace files sorted by tick number (ascending)
    trace_files: List[Tuple[int, Path]] = []
    for p in trace_root.glob("tick_*.trace"):
        try:
            tick_num = int(p.stem.split("_", 1)[1])
            trace_files.append((tick_num, p))
        except (ValueError, IndexError):
            continue
    trace_files.sort(key=lambda x: x[0])

    evicted = 0
    # Keep only the last _TRACE_FIFO_SIZE files
    while len(trace_files) > _TRACE_FIFO_SIZE:
        old_tick, old_path = trace_files.pop(0)
        # Compress to lossy 1-line summary before deletion
        try:
            content = old_path.read_text(encoding="utf-8")
            summary = _compress_trace(old_tick, content)
            fs.append(_TRACE_SUMMARY_FILE, summary)
            old_path.unlink()
            evicted += 1
        except Exception:
            # If compression fails, still remove to prevent I/O bloat
            try:
                old_path.unlink()
                evicted += 1
            except Exception:
                pass

    return evicted


def _compress_trace(tick_num: int, raw_content: str) -> Dict[str, Any]:
    """Lossy compression: extract only the scalar metrics from a full trace."""
    compressed: Dict[str, Any] = {"tick": tick_num, "compressed": True}
    pattern = re.compile(r"^-\s+(\w+):\s*(.+)$", re.MULTILINE)
    for m in pattern.finditer(raw_content):
        key, val = m.group(1), m.group(2).strip()
        if key in ("epiplexity", "regret", "threshold", "routing_variance"):
            try:
                compressed[key] = float(val)
            except ValueError:
                compressed[key] = val
        elif key in ("tick", "generation"):
            try:
                compressed[key] = int(float(val))
            except ValueError:
                compressed[key] = val
    return compressed


def _write_trace(
    fs: FileSystemBus,
    current_tick: int,
    state: Dict[str, Any],
    result: Dict[str, Any],
    addr_str: Optional[str],
    slot_str: Optional[str],
    variance: float,
    epi: float,
    threshold: float,
) -> str:
    """Write a .trace file on rejection (B=0). Returns the trace path.

    Implements FIFO sliding window: only the last _TRACE_FIFO_SIZE full traces
    are retained on disk. Older traces are compressed to NDJSON summaries.
    """
    trace_file = f"{_TRACE_DIR}/tick_{current_tick}.trace"

    # Get parent git commit hash
    parent_commit = "unknown"
    try:
        git_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=fs.root if hasattr(fs, 'root') else "agi_workspace",
            capture_output=True, text=True, timeout=5,
        )
        if git_result.returncode == 0:
            parent_commit = git_result.stdout.strip()
    except Exception:
        pass

    trace_content = f"""=== TRACE: tick {current_tick} ===
timestamp: {time.time():.6f}
generation: {result.get('gen', 0)}
epiplexity: {epi:.6f}
threshold: {threshold:.6f}
regret: {result.get('regret', 0.0):.6f}
cumulative_regret: {result.get('cum_reg', 0.0):.6f}
loss: {result.get('loss', 'N/A')}
entropy_penalty: {result.get('penalty', 'N/A')}
topo_penalty: {result.get('topo_penalty', 'N/A')}
fractal_address: {addr_str}
route_slot: {slot_str}
routing_variance: {variance:.6f}
parent_commit: {parent_commit}
parent_tick: {state.get('parent_tick', 'null')}
=== END TRACE ===
"""
    fs.write(trace_file, trace_content)

    # FIFO eviction — Occam's Razor: only keep what's needed
    evicted = _evict_old_traces(fs, current_tick)
    if evicted > 0:
        print(f"[trace] FIFO eviction: {evicted} old traces compressed to {_TRACE_SUMMARY_FILE}")

    return trace_file


# ── Heat Death Detection ────────────────────────────────────────────────────

_HEAT_DEATH_THRESHOLD: int = 20


def _update_heat_death(
    state: Dict[str, Any],
    new_best_epi: float,
) -> Tuple[int, int, int]:
    """Track consecutive stagnant ticks. Returns (counter, triggered, outer_loop_active)."""
    prev_best = state.get("best_epi", 0.0) or 0.0
    counter = state.get("heat_death_counter", 0) or 0
    outer_loop = state.get("outer_loop_active", 0) or 0

    if new_best_epi > prev_best:
        # Improvement — reset counter
        counter = 0
        triggered = 0
    else:
        # Stagnant — increment
        counter += 1
        triggered = 1 if counter > _HEAT_DEATH_THRESHOLD else 0

    if triggered:
        outer_loop = 1

    return counter, triggered, outer_loop


# ── Dynamic PoW Difficulty (Real-Time Resource Feedback) ───────────────────

_POW_WINDOW_SIZE: int = 50
_POW_SCALE_UP: float = 1.15
_POW_ROLLBACK: float = 0.87
_POW_SUCCESS_CEIL: float = 0.30
_POW_COLLAPSE_FLOOR: float = 0.05
_POW_COLLAPSE_TICKS: int = 100
_POW_DIFFICULTY_PATH: str = "memory/pow_difficulty.json"
_POW_TICK_TIME_CRITICAL: float = 30.0  # seconds — emergency forced decay trigger
_POW_CPU_CRITICAL: float = 90.0        # percent — CPU load ceiling
# TICK 8.0: _POW_MEM_CRITICAL removed — replaced by Dynamic Homeostasis
# via biogeo_probe baseline calibration.  Evaluator daemon passes a
# relative threshold; standalone tick() uses a safe 95.0% default.
_POW_MEM_CRITICAL_DEFAULT: float = 95.0  # fallback for standalone tick() mode
_POW_COLDSTART_GRACE: int = 3            # ticks — suppress mem emergency during startup


def _get_system_load() -> Dict[str, float]:
    """Sample real-time CPU and memory load. Cross-platform (macOS/Linux)."""
    load: Dict[str, float] = {"cpu_pct": 0.0, "mem_pct": 0.0}
    try:
        # CPU: 1-minute load average normalized to core count
        loadavg = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        load["cpu_pct"] = min(100.0, (loadavg / cpu_count) * 100.0)
    except (OSError, AttributeError):
        pass
    try:
        # Memory: parse vm_stat (macOS) or /proc/meminfo (Linux)
        if sys.platform == "darwin":
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                lines = result.stdout
                page_size = 16384  # default macOS ARM
                m = re.search(r"page size of (\d+)", lines)
                if m:
                    page_size = int(m.group(1))
                free = _extract_vm_stat(lines, "Pages free")
                inactive = _extract_vm_stat(lines, "Pages inactive")
                total_pages = 0
                for label in ("Pages free", "Pages active", "Pages inactive",
                              "Pages speculative", "Pages wired down"):
                    total_pages += _extract_vm_stat(lines, label)
                if total_pages > 0:
                    used_pct = (1.0 - (free + inactive) / total_pages) * 100.0
                    load["mem_pct"] = max(0.0, min(100.0, used_pct))
        else:
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                text = meminfo.read_text()
                total = _extract_meminfo(text, "MemTotal")
                avail = _extract_meminfo(text, "MemAvailable")
                if total > 0:
                    load["mem_pct"] = (1.0 - avail / total) * 100.0
    except Exception:
        pass
    return load


def _extract_vm_stat(text: str, label: str) -> int:
    m = re.search(rf"{label}:\s+(\d+)", text)
    return int(m.group(1)) if m else 0


def _extract_meminfo(text: str, label: str) -> float:
    m = re.search(rf"{label}:\s+(\d+)", text)
    return float(m.group(1)) if m else 0.0


def _load_pow_state(fs: FileSystemBus) -> Dict[str, Any]:
    """Load PoW difficulty state from filesystem."""
    raw = fs.read(_POW_DIFFICULTY_PATH)
    if raw and isinstance(raw, dict):
        return raw
    if raw and isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass
    return {
        "difficulty_level": 1,
        "ticks_since_last_increase": 0,
        "base_threshold": None,
    }


def _save_pow_state(fs: FileSystemBus, pow_state: Dict[str, Any]) -> None:
    """Save PoW difficulty state to filesystem."""
    fs.write(_POW_DIFFICULTY_PATH, pow_state)


# ── Session Epoch Tracker (TICK 5.1.2: Cold-Start Grace Fix) ────────────────

_SESSION_EPOCH_PATH: str = "memory/session_epoch.json"
_SESSION_STALE_SECONDS: float = 3600.0  # 1 hour — new session if epoch older


def _load_or_create_session_epoch(fs: FileSystemBus, current_tick: int) -> int:
    """Return the tick number at which this session started.

    Writes a session_epoch.json marker on first call.  If the marker exists
    but is older than _SESSION_STALE_SECONDS, it's treated as stale and
    recreated — this correctly resets grace when the evolution loop restarts
    even if the global tick counter is at 1500+.
    """
    raw = fs.read(_SESSION_EPOCH_PATH)
    if raw and isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raw = None
    if raw and isinstance(raw, dict):
        epoch_time = raw.get("timestamp", 0)
        if (time.time() - epoch_time) < _SESSION_STALE_SECONDS:
            return raw.get("start_tick", current_tick)
    # Create new session epoch
    epoch = {"start_tick": current_tick, "timestamp": time.time()}
    fs.write(_SESSION_EPOCH_PATH, epoch)
    return current_tick


def _update_pow_difficulty(
    fs: FileSystemBus,
    state: Dict[str, Any],
    B: int,
    threshold: float,
    tick_elapsed: float = 0.0,
    mem_critical: Optional[float] = None,
) -> Tuple[float, int, str, Dict[str, Any]]:
    """Update PoW difficulty based on sliding window + real-time resource metrics.

    TICK 8.0: mem_critical is now a dynamic parameter.  When None, falls
    back to _POW_MEM_CRITICAL_DEFAULT (95.0%) for standalone tick() mode.
    The Evaluator Daemon passes a baseline-relative threshold computed
    from biogeo_probe at startup.

    Returns (adjusted_threshold, difficulty_level, updated_window_str, telemetry).
    """
    if mem_critical is None:
        mem_critical = _POW_MEM_CRITICAL_DEFAULT
    telemetry: Dict[str, Any] = {}

    # ── Real-time resource sampling ──
    sys_load = _get_system_load()
    telemetry["cpu_pct"] = sys_load["cpu_pct"]
    telemetry["mem_pct"] = sys_load["mem_pct"]
    telemetry["tick_elapsed_s"] = tick_elapsed

    # Parse the success window from handoff state
    window_str = state.get("pow_success_window", "") or ""
    window: List[int] = []
    if window_str:
        window = [int(x) for x in window_str.split(",") if x.strip() in ("0", "1")]

    # Append current result
    window.append(B)
    # Trim to sliding window size
    if len(window) > _POW_WINDOW_SIZE:
        window = window[-_POW_WINDOW_SIZE:]

    new_window_str = ",".join(str(x) for x in window)

    # Load persistent PoW state
    pow_state = _load_pow_state(fs)
    difficulty_level = pow_state.get("difficulty_level", 1)
    ticks_since_increase = pow_state.get("ticks_since_last_increase", 0)
    base_threshold = pow_state.get("base_threshold")

    if base_threshold is None:
        base_threshold = threshold
        pow_state["base_threshold"] = base_threshold

    # ── Emergency forced decay: tick timeout or resource overload ──
    # TICK 5.1.2: Cold-start grace uses SESSION-LOCAL tick age, not the
    # global tick counter.  session_epoch.json tracks when this evolution
    # session began; the first N ticks after a (re)start get grace while
    # PyTorch/Ollama allocation stabilises.
    current_tick = (state.get("tick", 0) or 0) + 1
    session_start = _load_or_create_session_epoch(fs, current_tick)
    session_age = current_tick - session_start  # ticks since session began
    emergency = False
    if tick_elapsed > _POW_TICK_TIME_CRITICAL:
        emergency = True
        telemetry["emergency_reason"] = f"tick_timeout ({tick_elapsed:.1f}s > {_POW_TICK_TIME_CRITICAL}s)"
    elif sys_load["cpu_pct"] > _POW_CPU_CRITICAL:
        emergency = True
        telemetry["emergency_reason"] = f"cpu_overload ({sys_load['cpu_pct']:.1f}% > {_POW_CPU_CRITICAL}%)"
    elif sys_load["mem_pct"] > mem_critical:
        if session_age > _POW_COLDSTART_GRACE:
            emergency = True
            telemetry["emergency_reason"] = f"mem_overload ({sys_load['mem_pct']:.1f}% > {mem_critical:.1f}%)"
        else:
            telemetry["coldstart_grace"] = True
            print(f"[pow] Cold-start grace: mem {sys_load['mem_pct']:.1f}% > {mem_critical:.1f}% "
                  f"but session tick {session_age} <= {_POW_COLDSTART_GRACE} -- suppressed.")

    if emergency:
        threshold = threshold * _POW_ROLLBACK
        difficulty_level = max(1, difficulty_level - 1)
        ticks_since_increase = 0
        telemetry["action"] = "EMERGENCY_DECAY"
        print(f"[pow] EMERGENCY FORCED DECAY: {telemetry.get('emergency_reason', 'unknown')} "
              f"— threshold rolled back to {threshold:.4f} (level {difficulty_level})")
    elif len(window) >= _POW_WINDOW_SIZE:
        # Standard sliding window logic
        success_rate = sum(window) / len(window)
        telemetry["success_rate"] = success_rate

        if success_rate > _POW_SUCCESS_CEIL:
            threshold = threshold * _POW_SCALE_UP
            difficulty_level += 1
            ticks_since_increase = 0
            telemetry["action"] = "SCALE_UP"
            print(f"[pow] Success rate {success_rate:.2f} > {_POW_SUCCESS_CEIL} "
                  f"— scaling threshold to {threshold:.4f} (level {difficulty_level})")
        elif success_rate < _POW_COLLAPSE_FLOOR and ticks_since_increase >= _POW_COLLAPSE_TICKS:
            threshold = threshold * _POW_ROLLBACK
            difficulty_level = max(1, difficulty_level - 1)
            ticks_since_increase = 0
            telemetry["action"] = "ANTI_COLLAPSE_ROLLBACK"
            print(f"[pow] Anti-collapse: success rate {success_rate:.2f} < {_POW_COLLAPSE_FLOOR} "
                  f"for {_POW_COLLAPSE_TICKS}+ ticks — rolling back to {threshold:.4f}")
        else:
            ticks_since_increase += 1
            telemetry["action"] = "HOLD"
    else:
        ticks_since_increase += 1
        telemetry["action"] = "WARMUP"

    telemetry["difficulty_level"] = difficulty_level
    telemetry["threshold"] = threshold

    # Save updated PoW state
    pow_state["difficulty_level"] = difficulty_level
    pow_state["ticks_since_last_increase"] = ticks_since_increase
    _save_pow_state(fs, pow_state)

    return threshold, difficulty_level, new_window_str, telemetry


# ── LLM Cognitive Adapter (TICK 3.1) ─────────────────────────────────────────
#
# Replaces the blind VARY phase with a guided mutation loop powered by
# qqwen3.5:35b-a3b via the local Ollama server.
#
# Physics constraints:
#   • LLM outputs a <find>/<replace> diff — never the full file.
#   • Strict 10-second socket timeout.  Ollama silence = dead.
#   • AST gate before any write: SyntaxError → discard.
#   • try/except wraps everything: any failure → blind mutation fallback.

_LLM_ENDPOINT: str = "http://localhost:11434/api/chat"  # Native Ollama — NOT /v1/ shim
_LLM_MODEL: str    = "qwen3.5:35b-a3b"
_LLM_TIMEOUT: int  = 240  # seconds — 35B model on M1 Ultra needs 120-200s for class rewrites
_ATOMIC_CORE_PATH: Path = Path(__file__).resolve().parent / "atomic_core.py"


def _extract_method_source(full_source: str, method_name: str) -> str:
    """Return a method's exact source lines from a class, via AST line metadata.

    Preserves the original indentation (including the leading 4-space class
    indent) so the extracted text can be used verbatim as the <find> target.
    """
    try:
        tree = ast.parse(full_source)
        lines = full_source.splitlines()
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == method_name
            ):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", len(lines))
                return "\n".join(lines[start:end])
    except Exception:
        pass
    return ""


def _extract_class_source(full_source: str, class_name: str) -> str:
    """Return a class definition's exact source lines from the module, via AST.

    Preserves original indentation so extracted text can serve as <find> target.
    """
    try:
        tree = ast.parse(full_source)
        lines = full_source.splitlines()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", len(lines))
                return "\n".join(lines[start:end])
    except Exception:
        pass
    return ""


# Architecture constants the NAS is allowed to mutate
_NN_CONSTANT_NAMES: frozenset = frozenset({
    "VOCAB_SIZE", "EMBED_DIM", "NUM_HEADS", "NUM_LAYERS",
    "FF_DIM", "MAX_SEQ_LEN", "DROPOUT", "BASE_LR",
})


def _extract_nn_architecture(full_source: str) -> str:
    """Extract neural network architecture constants + all nn.Module subclass definitions.

    Returns a single string containing:
      1. Module-level architecture constants (VOCAB_SIZE, FF_DIM, etc.)
      2. Every class that directly subclasses nn.Module
    Ordered by source position so the LLM sees them in logical reading order.
    """
    try:
        tree = ast.parse(full_source)
        lines = full_source.splitlines()
        # List of (start_line_0indexed, end_line_0indexed) segments
        segments: List[Tuple[int, int]] = []

        # ── 1. Architecture constants ──
        const_line_indices: List[int] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in _NN_CONSTANT_NAMES:
                        start = node.lineno - 1
                        end = getattr(node, "end_lineno", node.lineno)
                        for ln in range(start, end):
                            const_line_indices.append(ln)
        if const_line_indices:
            segments.append((min(const_line_indices), max(const_line_indices) + 1))

        # ── 2. All nn.Module subclasses ──
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                is_nn_module = any(
                    (isinstance(b, ast.Attribute)
                     and isinstance(b.value, ast.Name)
                     and b.value.id == "nn"
                     and b.attr == "Module")
                    for b in node.bases
                )
                if is_nn_module:
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", len(lines))
                    segments.append((start, end))

        if not segments:
            return ""

        # Sort by source position and join
        segments.sort(key=lambda s: s[0])
        parts: List[str] = []
        for start, end in segments:
            parts.append("\n".join(lines[start:end]))
        return "\n\n".join(parts)
    except Exception:
        return ""


def _llm_call_ollama(
    arch_src: str,
    threshold: float,
    best_epi: float = 0.0,
    timeout: int = _LLM_TIMEOUT,
) -> Optional[str]:
    """Call Ollama via Instructor for structured NAS output.

    TICK 22.6 — Instructor handles schema injection, Pydantic validation,
    and auto-retries. No manual JSON parsing, no regex, no fallback.
    """
    system_prompt = (
        "You are a Neural Architecture Search engine.\n\n"
        "RULES:\n"
        "1. Output ONLY the class(es) or constant(s) you MODIFIED. "
        "Omit unchanged classes.\n"
        "2. IMMUTABLE: MitoticTransformerBlock and AtomicLLM are LOCKED — "
        "do NOT output them. Mutate RoutingStrategy (primary target), "
        "CausalSelfAttention, or IChingExpert only.\n"
        "3. RoutingStrategy.forward receives (x, experts, router_idx) and "
        "must return Tensor[B,T,D]. The scaffold adds it as residual.\n"
        "4. Maintain __init__ signatures and forward() return shapes.\n"
        "5. Verify tensor dimensions: trace every nn.Linear(in, out) and matmul.\n"
        "6. Prefer efficient ops: sparse attention, grouped queries, smaller "
        "FF_DIM, fewer parameters. Thermodynamic penalty taxes CPU/memory.\n"
        "7. Make a REAL structural change. Identity patches "
        "are rejected.\n\n"
        "CRITICAL STRUCTURAL RULE: If you are mutating a PyTorch nn.Module, "
        "your code MUST contain both the __init__ and forward functions. "
        "The system will crash if forward is missing.\n\n"
        "Use \\n for newlines within the code string."
    )
    user_prompt = (
        f"Threshold: {threshold:.4f} | Best epiplexity: {best_epi:.4f}\n"
        f"Efficient architectures score higher (thermodynamic penalty on "
        f"CPU/memory).\n\n"
        f"```python\n{arch_src}\n```\n\n"
        f"Mutate 1-2 classes."
    )

    try:
        client = get_instructor_client()
        result = client.chat.completions.create(
            model=_LLM_MODEL,
            response_model=FastNASOutput,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_retries=3,
            temperature=0.1,
            # TICK 21.4/21.5: Thermodynamic API Constraints.
            # Enforces hardware-level safety valves through the Ollama /v1 endpoint.
            # num_ctx=8192  → O(N²) Guillotine: prevents 262K KV-cache explosion.
            # num_predict=1024 → Time Limit: aborts infinite generation loops.
            # keep_alive=0  → VRAM Release: Fast Loop never holds GPU lock.
            extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}},
        )
        print(f"[fast-loop] Structured output: {len(result.code)} chars")
        return result.code
    except Exception as exc:
        print(f"[fast-loop] Instructor error: {type(exc).__name__}: {exc}")
        # Fallback: legacy code block extraction
        return None


def _parse_llm_code_block(response: str) -> Optional[str]:
    """Multi-strategy Python code extraction from LLM response.

    TICK 5.1.2 — Absolute parser forgiveness:
      Stage 0: Try ast.parse() on entire cleaned response (pure code, no markup)
      Stage 1: Strip <think>...</think> reasoning blocks
      Stage 2: Fence extraction (largest AST-valid block wins)
      Stage 3: Raw unfenced scan (class/constant lines → progressive truncation)

    Returns extracted Python code string, or None if nothing usable found.
    """
    # ── Stage 1: Strip <think> reasoning blocks ──────────────────────────
    # Qwen 3.5 wraps chain-of-thought in <think>...</think>.  These blocks
    # often contain code-like fragments that confuse fence extraction.
    # Strip closed tags first, then any unclosed trailing <think>.
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL)
    if not cleaned.strip():
        cleaned = response  # stripping removed everything — use raw

    # ── Stage 0: Full-response AST parse (pure code, no markup) ────
    # If the model outputs raw Python without ANY markdown, this catches
    # it immediately — the most common failure mode from Pulse 3 logs.
    try:
        tree = ast.parse(cleaned)
        has_useful = any(
            isinstance(n, (ast.ClassDef, ast.Assign))
            for n in ast.iter_child_nodes(tree)
        )
        if has_useful:
            return cleaned.strip()
    except SyntaxError:
        pass

    # ── Stage 2: Fence extraction (largest AST-valid block wins) ─────────
    # Try both backtick and tilde fences, with or without language tag.
    # Collect ALL matches and return the largest one that passes AST parse.
    candidates: List[str] = []
    for m in re.finditer(r"```(?:\w*)\s*\n(.*?)```", cleaned, re.DOTALL):
        code = m.group(1).rstrip()
        if code:
            candidates.append(code)
    for m in re.finditer(r"~~~(?:\w*)\s*\n(.*?)~~~", cleaned, re.DOTALL):
        code = m.group(1).rstrip()
        if code:
            candidates.append(code)

    # Sort by length descending — prefer the most substantial block
    candidates.sort(key=len, reverse=True)
    for code in candidates:
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            continue

    # ── Stage 3: Raw extraction — no fences at all ───────────────────────
    # Scan for lines starting with `class Foo` or `UPPER_CONST =` and
    # extract a contiguous code block, validating via AST.
    lines = cleaned.splitlines()
    start_idx: Optional[int] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^class\s+\w+", stripped):
            start_idx = i
            break
        if re.match(r"^[A-Z][A-Z_]{1,}\s*=", stripped):
            start_idx = i
            break

    if start_idx is None:
        return None

    # Greedily take lines from start, then trim trailing non-code
    code_lines = list(lines[start_idx:])
    while code_lines and not code_lines[-1].strip():
        code_lines.pop()
    candidate = "\n".join(code_lines)

    try:
        ast.parse(candidate)
        return candidate
    except SyntaxError:
        pass

    # Progressive truncation: remove trailing lines until AST passes
    # (handles models that append prose after the code)
    while len(code_lines) > 3:
        code_lines.pop()
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        if not code_lines:
            break
        candidate = "\n".join(code_lines)
        try:
            tree = ast.parse(candidate)
            # Must contain at least one class to be useful for NAS
            if any(isinstance(n, ast.ClassDef) for n in ast.iter_child_nodes(tree)):
                return candidate
        except SyntaxError:
            continue

    return None


def _ast_replace_in_source(original_source: str, new_code: str) -> Optional[str]:
    """AST-anchored replacement: swap class definitions and constants by name.

    TICK 5.1 — Instead of fragile verbatim string matching (<find>/<replace>),
    this uses Python's AST to locate class definitions and architecture constants
    by name in the original source, then replaces their exact line ranges with
    the corresponding definitions from new_code.

    Returns the patched source on success, None on:
      - new_code fails AST parse
      - No matching class/constant names found in original
      - Patched result fails AST parse
      - Missing required classes after patch
      - Identity mutation (no actual change)
    """
    # ── Parse new code (TICK 22.1: dedent + detailed error logging) ──
    new_code = textwrap.dedent(new_code)
    try:
        new_tree = ast.parse(new_code)
    except SyntaxError as exc:
        print(f"[llm-nas] LLM code block failed AST parse: {exc}")
        print(f"[llm-nas]   Line {exc.lineno}: {exc.text!r}" if exc.text else "")
        # Attempt line-by-line indent repair as last resort
        lines = new_code.splitlines()
        repaired = "\n".join(
            l.expandtabs(4) for l in lines
        )
        repaired = textwrap.dedent(repaired)
        try:
            new_tree = ast.parse(repaired)
            new_code = repaired
            print(f"[llm-nas] Indent repair succeeded (tab expansion + dedent)")
        except SyntaxError as exc2:
            print(f"[llm-nas] Indent repair also failed: {exc2}")
            print(f"[llm-nas]   Line {exc2.lineno}: {exc2.text!r}" if exc2.text else "")
            return None

    new_lines = new_code.splitlines()

    # ── Extract class definitions from new code ──
    # TICK 23.0: Immutable Scaffold — reject mutations targeting locked classes
    _IMMUTABLE_CLASSES = {"MitoticTransformerBlock", "AtomicLLM", "AtomicCore"}
    new_classes: Dict[str, str] = {}
    for node in ast.iter_child_nodes(new_tree):
        if isinstance(node, ast.ClassDef):
            if node.name in _IMMUTABLE_CLASSES:
                print(f"[llm-nas] SCAFFOLD GUARD: Rejecting mutation of immutable class '{node.name}'")
                continue
            start = node.lineno - 1
            end = getattr(node, "end_lineno", len(new_lines))
            new_classes[node.name] = "\n".join(new_lines[start:end])

    # ── Extract architecture constants from new code ──
    new_constants: Dict[str, str] = {}
    for node in ast.iter_child_nodes(new_tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _NN_CONSTANT_NAMES:
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", node.lineno)
                    new_constants[target.id] = "\n".join(new_lines[start:end])

    if not new_classes and not new_constants:
        print("[llm-nas] No recognizable classes or constants in LLM output.")
        return None

    # ── Parse original source ──
    try:
        orig_tree = ast.parse(original_source)
    except SyntaxError:
        return None

    orig_lines = original_source.splitlines()

    # ── Build replacement list: (start_0idx, end_0idx, new_text) ──
    replacements: List[Tuple[int, int, str]] = []

    for node in ast.iter_child_nodes(orig_tree):
        if isinstance(node, ast.ClassDef) and node.name in new_classes:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", len(orig_lines))
            replacements.append((start, end, new_classes[node.name]))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in new_constants:
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", node.lineno)
                    replacements.append((start, end, new_constants[target.id]))

    if not replacements:
        print(f"[llm-nas] No matching classes/constants in original source. "
              f"LLM output classes: {list(new_classes.keys())}, "
              f"constants: {list(new_constants.keys())}")
        return None

    # ── Apply replacements (reverse order to preserve line numbers) ──
    replacements.sort(key=lambda r: r[0], reverse=True)
    result_lines = list(orig_lines)
    for start, end, new_text in replacements:
        result_lines[start:end] = new_text.splitlines()

    patched = "\n".join(result_lines)
    if not patched.endswith("\n"):
        patched += "\n"

    # ── Identity mutation check ──
    if patched.strip() == original_source.strip():
        print("[llm-nas] Patch rejected: identity mutation (no actual change).")
        return None

    # ── Final AST validation ──
    try:
        final_tree = ast.parse(patched)
    except SyntaxError as exc:
        print(f"[llm-nas] Patched source failed final AST validation: {exc}")
        return None

    # ── Structural integrity gate ──
    _REQUIRED_CLASSES = {"AtomicLLM", "AtomicCore"}
    found_classes: set = set()
    for node in ast.walk(final_tree):
        if isinstance(node, ast.ClassDef):
            found_classes.add(node.name)

    missing = _REQUIRED_CLASSES - found_classes
    if missing:
        print(f"[llm-nas] Patch rejected: missing required classes: {missing}")
        return None

    # ── Preview ──
    names = list(new_classes.keys()) + list(new_constants.keys())
    print(f"[llm-nas] AST patch: replacing {names} "
          f"({len(replacements)} segment(s), "
          f"{sum(len(r[2].splitlines()) for r in replacements)} new lines)")

    return patched


def _llm_guided_vary(current_threshold: float, best_epi: float = 0.0) -> bool:
    """TICK 5.1.2 — LLM NAS Architect via targeted class override protocol.

    Pipeline:
      1. Read atomic_core.py and extract the full NN architecture.
      2. POST to Ollama — prompt requests only MODIFIED classes (not all).
      3. Multi-strategy code extraction (AST parse / fence / raw scan).
      4. AST-anchored class/constant replacement (no verbatim string matching).
      5. Full AST validation + structural integrity check.
      6. On success: write patched file → return True (caller reloads module).
      7. On ANY failure: leave atomic_core.py untouched → return False.

    Hard constraints:
      • 240-second socket timeout — 35B model on M1 Ultra physical budget.
      • AST parse gate — SyntaxError = discard.
      • Structural integrity gate — missing required classes = discard.
      • Full try/except around everything — zero crash guarantee.
    """
    try:
        full_source = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")

        # ── Extract NN architecture (primary mutation target) ──
        arch_src = _extract_nn_architecture(full_source)
        if not arch_src:
            print(f"[llm-nas] model={_LLM_MODEL} | No nn.Module classes found — skipping.")
            return False

        print(f"[llm-nas] model={_LLM_MODEL} timeout={_LLM_TIMEOUT}s | Sending NAS prompt...")
        t_llm_start = time.time()

        llm_raw = _llm_call_ollama(
            arch_src, current_threshold,
            best_epi=best_epi, timeout=_LLM_TIMEOUT,
        )

        t_llm_elapsed = time.time() - t_llm_start
        print(f"[llm-nas] model={_LLM_MODEL} | LLM responded in {t_llm_elapsed:.1f}s")

        # ── Parse code fence (TICK 5.1 — replaces XML tag parsing) ──
        code_block = _parse_llm_code_block(llm_raw)
        if code_block is None:
            print(f"[llm-nas] model={_LLM_MODEL} | No parseable Python code in response — falling back.")
            return False

        # ── AST-anchored replacement (TICK 5.1 — replaces string matching) ──
        patched_source = _ast_replace_in_source(full_source, code_block)
        if patched_source is None:
            print(f"[llm-nas] model={_LLM_MODEL} | AST patch rejected — falling back.")
            return False

        _ATOMIC_CORE_PATH.write_text(patched_source, encoding="utf-8")
        print(f"[llm-nas] model={_LLM_MODEL} | NAS patch accepted and written in {t_llm_elapsed:.1f}s.")
        return True

    except Exception as exc:
        # Covers: socket.timeout (Ollama too slow), ConnectionRefusedError
        # (Ollama down), json.JSONDecodeError (malformed body), IOError, etc.
        print(f"[llm-nas] model={_LLM_MODEL} | Adapter error ({type(exc).__name__}: {exc}) — blind mutation fallback.")
        return False


# ── Topology Guard: safe failure result (TICK 5.1.1) ────────────────────────

def _safe_failure_result(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return a zero-epi result dict when blind mutation tears topology.

    Used when fractal address depth mismatches crash the evaluator.
    Produces a guaranteed-rejected result (epi=0 < any threshold) so
    the tick completes cleanly with B=0 instead of crashing.
    """
    return {
        "gen": (state.get("generation", 0) or 0) + 1,
        "epi": 0.0,
        "regret": 1.0,
        "cum_reg": (state.get("cumulative_regret", 0.0) or 0.0) + 1.0,
        "best_epi": state.get("best_epi", 0.0) or 0.0,
        "pop": state.get("population_size", 0) or 0,
        "sym": "☠ topo-guard",
    }


# ── TICK: the stateless executor ─────────────────────────────────────────────

def tick(threshold: float = 0.10, device: str = "cpu") -> int:
    """Execute one stateless tick. Returns exit code (0 = success)."""

    t_start: float = time.time()

    # ── 1. READ ──────────────────────────────────────────────────────────────
    fs = FileSystemBus(root="agi_workspace")
    raw: Optional[str] = fs.read(_HANDOFF_PATH)

    if raw is None or not isinstance(raw, str) or raw.strip() == "":
        state = _default_state(threshold)
        fs.write(_HANDOFF_PATH, serialize_handoff(state))
        print(f"[tick] No prior state found. Initialized Structured_Handoff.md.")
        raw = fs.read(_HANDOFF_PATH)
        assert isinstance(raw, str)

    state = parse_handoff(raw)
    if not state:
        state = _default_state(threshold)

    # Carry forward the threshold from CLI (override persisted value)
    state["threshold"] = threshold

    prev_tick: int = state.get("tick", 0) or 0
    current_tick: int = prev_tick + 1

    print(f"[tick {current_tick}] READ complete. "
          f"Prior gen={state.get('generation', 0)}, "
          f"best_epi={state.get('best_epi', 0.0):.4f}")

    # ── 2. VARY ──────────────────────────────────────────────────────────────
    # TICK 3.2 — LLM NAS Architect
    # Try to patch atomic_core.py neural architecture via qwen3.5:35b-a3b
    # before loading AtomicCore.  On ANY failure the blind-mutation path runs unchanged.

    # Snapshot atomic_core.py BEFORE any LLM mutation so we can restore it
    # on a runtime crash that slips past the AST gate.
    _backup_source: str = _ATOMIC_CORE_PATH.read_text(encoding="utf-8")

    _prior_threshold: float = state.get("threshold", threshold) or threshold
    _prior_best_epi: float = state.get("best_epi", 0.0) or 0.0
    t_vary_start: float = time.time()
    _llm_patched: bool = _llm_guided_vary(
        current_threshold=_prior_threshold,
        best_epi=_prior_best_epi,
    )
    t_llm_wall: float = time.time() - t_vary_start  # LLM oracle latency (excluded from PoW)

    # Lazy import: AtomicCore depends on torch — kept out of module scope
    # so parse_handoff/serialize_handoff remain importable without ML deps.

    # ── Import-Time Rollback Sandbox (TICK 3.1.2) ─────────────────────────────
    # + Topology Guard (TICK 5.1.1)
    #
    # The ENTIRE import → reload → iterate pipeline is wrapped in one try-except.
    # Previous design had `import atomic_core` OUTSIDE the guard, which meant a
    # SyntaxError in the patched file crashed at import time before any rollback
    # logic could run, producing a permanent death loop.
    #
    # TICK 5.1.1 addition: blind mutation can produce candidates with malformed
    # fractal addresses (depth 1 vs router depth 2), crashing _evaluate().
    # Instead of killing the tick, we catch the specific ValueError and return
    # a zero-epi safe failure (guaranteed B=0 rejection).
    #
    # Recovery steps on ANY exception (import-time OR runtime):
    #   1. Write _backup_source back to atomic_core.py.
    #   2. Evict the (possibly partially-loaded / corrupted) module from
    #      sys.modules so the next import re-reads from disk.
    #   3. Reload the clean module and run iterate() under blind mutation.
    # If _llm_patched is False AND it's not a topology tear — re-raise.
    try:
        import atomic_core as _ac_mod
        if _llm_patched:
            importlib.reload(_ac_mod)
            print(f"[tick {current_tick}] VARY: LLM NAS architecture patch active.")
        else:
            print(f"[tick {current_tick}] VARY: blind mutation (NAS skipped or fallback).")
        core = _ac_mod.AtomicCore(fs, device=device)
        result: Dict[str, Any] = core.iterate()
    except Exception as _rt_exc:
        # ── Topology Guard (TICK 5.1.1) ──────────────────────────────────
        # Detect fractal address depth mismatches from blind mutation.
        _is_topo_tear = (
            isinstance(_rt_exc, ValueError)
            and "depth" in str(_rt_exc)
            and "router" in str(_rt_exc)
        )

        if _is_topo_tear and not _llm_patched:
            # Blind mutation tore topology — safe failure, not a crash.
            print(
                f"[topology-guard] Blind mutation depth mismatch: {_rt_exc}\n"
                f"[topology-guard] Returning zero-epi safe failure."
            )
            result = _safe_failure_result(state)
        elif _llm_patched:
            # LLM patch caused crash — rollback and retry
            print(
                f"[resilience] Import/runtime crash after LLM patch "
                f"({type(_rt_exc).__name__}: {_rt_exc}). "
                f"Rolling back atomic_core.py."
            )
            _ATOMIC_CORE_PATH.write_text(_backup_source, encoding="utf-8")
            # Evict the cached (possibly corrupt) module entry so the reimport
            # loads the just-restored clean file from disk.
            sys.modules.pop("atomic_core", None)
            import atomic_core as _ac_mod  # noqa: F811
            importlib.reload(_ac_mod)
            print("[resilience] Rollback complete. Executing blind mutation fallback.")
            core = _ac_mod.AtomicCore(fs, device=device)
            try:
                result = core.iterate()
            except ValueError as _topo_exc2:
                if "depth" in str(_topo_exc2) and "router" in str(_topo_exc2):
                    print(f"[topology-guard] Rollback also hit depth mismatch — safe failure.")
                    result = _safe_failure_result(state)
                else:
                    raise
        else:
            raise  # not our fault and not topology — surface the real error

    gen: int = result["gen"]
    epi: float = result["epi"]
    regret: float = result["regret"]
    cum_reg: float = result["cum_reg"]
    best_epi: float = result["best_epi"]
    pop_size: int = result["pop"]
    sym: str = result.get("sym", "")

    print(f"[tick {current_tick}] VARY complete. "
          f"gen={gen}, epi={epi:.4f}, regret={regret:.4f}, sym={sym}")

    # ── 3. CHECK ─────────────────────────────────────────────────────────────
    hasher = ASTHasher()
    router = KroneckerFractalRouter(depth=2)
    addr, slot, variance = _topological_check(hasher, router)

    addr_str: Optional[str] = repr(addr) if addr is not None else None
    slot_str: Optional[str] = hex(slot) if slot is not None else None

    print(f"[tick {current_tick}] CHECK complete. "
          f"addr={addr_str}, slot={slot_str}, var={variance:.6f}")

    # ── 4. EVAL ──────────────────────────────────────────────────────────────
    # Measure tick elapsed time for emergency PoW decay.
    # TICK 5.1 — Exclude LLM oracle latency: thermodynamic penalty measures
    # computation cost, not time spent waiting for the inference server.
    tick_elapsed_so_far: float = time.time() - t_start
    tick_compute_time: float = tick_elapsed_so_far - t_llm_wall

    # Dynamic PoW difficulty adjustment (before Boolean gate)
    adjusted_threshold, pow_level, pow_window, pow_telemetry = _update_pow_difficulty(
        fs, state, _boolean_gate(epi, threshold), threshold,
        tick_elapsed=tick_compute_time,
    )
    # Use adjusted threshold for the actual gate
    B: int = _boolean_gate(epi, adjusted_threshold)

    print(f"[tick {current_tick}] EVAL: epi={epi:.4f} vs threshold={adjusted_threshold:.4f} "
          f"(pow_level={pow_level}) -> B={B}")

    # Heat death detection
    hd_counter, hd_triggered, outer_loop = _update_heat_death(state, best_epi)
    if hd_triggered:
        print(f"[tick {current_tick}] HEAT DEATH detected: {hd_counter} consecutive "
              f"stagnant ticks (>{_HEAT_DEATH_THRESHOLD}). Outer-loop activated.")

    # ── 5. PERSIST ───────────────────────────────────────────────────────────
    accepted: int = state.get("accepted_ticks", 0) or 0
    rejected: int = state.get("rejected_ticks", 0) or 0

    # Common new fields for both accept/reject paths
    _tick1_fields: Dict[str, Any] = {
        "heat_death_counter": hd_counter,
        "heat_death_triggered": hd_triggered,
        "outer_loop_active": outer_loop,
        "pow_difficulty_level": pow_level,
        "pow_success_window": pow_window,
        "trace_path": None,
    }

    if B == 1:
        # Accept: write updated state and commit
        new_state: Dict[str, Any] = {
            "tick": current_tick,
            "timestamp": time.time(),
            "snapshot_hash": hashlib.sha256(str(time.time()).encode()).hexdigest()[:16],
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
            **_tick1_fields,
        }
        fs.write(_HANDOFF_PATH, serialize_handoff(new_state))

        # Persist checkpoint for AtomicCore reload on next tick
        fs.write("memory/checkpoint.json", {
            "generation": gen,
            "cumulative_regret": cum_reg,
            "best_epiplexity": best_epi,
            "meta_epi_thr": core.meta_epi_thr,
            "meta_regret_thr": core.meta_regret_thr,
        })

        committed: bool = fs.commit(
            f"tick {current_tick}: B=1 | gen={gen} epi={epi:.4f} "
            f"regret={regret:.4f} | {sym}"
        )

        elapsed: float = time.time() - t_start
        print(f"[tick {current_tick}] PERSIST: ACCEPTED. "
              f"Committed={committed}. Elapsed={elapsed:.2f}s")

    else:
        # Reject: hard drop. Write trace file and update rejection counter.
        trace_path = _write_trace(
            fs, current_tick, state, result,
            addr_str, slot_str, variance, epi, adjusted_threshold,
        )
        _tick1_fields["trace_path"] = trace_path

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
            **_tick1_fields,
        }
        fs.write(_HANDOFF_PATH, serialize_handoff(drop_state))

        elapsed = time.time() - t_start
        print(f"[tick {current_tick}] PERSIST: REJECTED (hard drop). "
              f"epi={epi:.4f} < threshold={threshold:.4f}. Elapsed={elapsed:.2f}s")

    # ── 6. TERMINATE ─────────────────────────────────────────────────────────
    # Log telemetry via Zstd compressed stream (TICK 2: First-Principles Storage)
    final_elapsed: float = time.time() - t_start
    pow_telemetry["total_elapsed_s"] = final_elapsed

    telemetry_record = {
        "tick": current_tick, "B": B, "epi": epi,
        "threshold": adjusted_threshold, **pow_telemetry,
        "gen": gen, "best_epi": best_epi,
        "heat_death_counter": hd_counter,
        "heat_death_triggered": hd_triggered,
        "outer_loop_active": outer_loop,
        # TICK 14.0: Unified Survival Equation telemetry
        "forward_ms": result.get("forward_ms", 0.0),
        "param_count": result.get("param_count", 0),
        "latency_cost": result.get("latency_cost", 0.0),
        "complexity_cost": result.get("complexity_cost", 0.0),
        "info_gain_bonus": result.get("info_gain_bonus", 0.0),
        "t": time.time(),
    }

    # Primary: Zstd compressed telemetry stream
    # Use close() to guarantee flush + fsync before process exit
    with ZstdLogger(log_dir=Path(fs.root) / "logs", stream_name="tick_telemetry") as zstd_log:
        zstd_log.append(telemetry_record)

    # Legacy fallback: also append raw NDJSON (will be deprecated once dashboard
    # fully migrates to Zstd reader; kept for backward compat during TICK 2 rollout)
    fs.append("logs/tick_telemetry.ndjson", telemetry_record)

    # No carried state. Clean exit.
    print(f"[tick {current_tick}] TERMINATE. B={B} elapsed={final_elapsed:.2f}s "
          f"cpu={pow_telemetry.get('cpu_pct', 0):.1f}% mem={pow_telemetry.get('mem_pct', 0):.1f}%")
    return 0


# Public alias for external callers
run_tick = tick


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stateless tick executor — NLAH harness contract."
    )
    parser.add_argument(
        "--threshold", type=float, default=0.10,
        help="Epiplexity threshold for Boolean gate (default: 0.10)"
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Torch device (default: cpu)"
    )
    args = parser.parse_args()
    code: int = tick(threshold=args.threshold, device=args.device)
    sys.exit(code)


if __name__ == "__main__":
    main()
