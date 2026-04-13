#!/usr/bin/env python3
"""env_evolver.py -- The Ecology Loop (TICK 12.0: The Cambrian Engine).

Fourth member of the Evolutionary Quartet:
  evaluator_daemon.py  (Fast Loop  — tests organism × environment pairs)
  mutator_daemon.py    (Slow Loop  — evolves organisms via LLM)
  env_evolver.py       (Ecology Loop — co-evolves environments via POET)
  local_breeder.py     (Micro Loop — fast GA crossover)

Implements Paired Open-Ended Trailblazer (POET) principles:
  - The environment genome parameterizes the coupled Lorenz-Rössler
    chaotic attractor (rho_range, coupling_kappa, regime_switch_freq, etc.)
  - The Goldilocks Zone (Minimal Viability): environments must be hard
    enough that not all organisms pass, but easy enough that at least
    one can survive.  Too-easy and too-hard mutations are rejected.
  - Atomic IPC: writes env_active/current.json via tmp + os.rename()
    to prevent read/write collision with the Evaluator Swarm.

Usage:
    python env_evolver.py [--poll-interval 120]
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fs_bus import FileSystemBus


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

_TELEMETRY_PATH: str = "logs/tick_telemetry.ndjson"
_ENV_ACTIVE_DIR: str = "candidate_pool/env_active"
_ENV_ACTIVE_FILE: str = "candidate_pool/env_active/current.json"
_ISLAND_ENV_DIR: str = "candidate_pool/island_env"

# Goldilocks Zone thresholds
_EASY_EPI_THRESHOLD: float = 0.3   # best_epi above this for N ticks → too easy
_HARD_EPI_THRESHOLD: float = 0.02  # best_epi below this for N ticks → too hard
_GOLDILOCKS_WINDOW: int = 30       # ticks to observe before deciding
_MIN_TICKS_BETWEEN_MUTATIONS: int = 50  # anti-spam: don't mutate env too frequently

# Mutation parameters
_MUTATION_RATE: float = 0.08       # ±8% per parameter
_MAX_ARCHIVED_ENVS: int = 20       # FIFO cap for island_env

# Baseline environment genome (matches env_stream.py defaults)
_BASELINE_GENOME: Dict[str, Any] = {
    "rho_center": 28.0,
    "rho_range": 4.0,
    "coupling_kappa_min": 0.01,
    "coupling_kappa_max": 0.12,
    "regime_switch_freq_min": 150,
    "regime_switch_freq_max": 300,
    "rossler_c": 5.7,
    "quantization_bins": 96,
    "sigma": 10.0,
    "beta": 8.0 / 3.0,
    "rossler_a": 0.2,
    "rossler_b": 0.2,
}

# Hard limits: parameters must stay within these bounds to prevent
# numerical divergence in the chaotic attractor
_PARAM_BOUNDS: Dict[str, tuple] = {
    "rho_center": (20.0, 40.0),
    "rho_range": (1.0, 12.0),
    "coupling_kappa_min": (0.001, 0.5),
    "coupling_kappa_max": (0.01, 0.8),
    "regime_switch_freq_min": (50, 500),
    "regime_switch_freq_max": (100, 800),
    "rossler_c": (3.0, 12.0),
    "quantization_bins": (48, 96),
    "sigma": (5.0, 20.0),
    "beta": (1.0, 5.0),
    "rossler_a": (0.05, 0.5),
    "rossler_b": (0.05, 0.5),
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
# GOLDILOCKS ZONE DETECTOR
# ═══════════════════════════════════════════════════════════════

def _assess_goldilocks(
    records: List[Dict[str, Any]],
) -> str:
    """Assess whether the current environment is in the Goldilocks Zone.

    Returns one of:
        "too_easy"   — best_epi consistently high, environment lacks pressure
        "too_hard"   — best_epi near zero, mass extinction
        "goldilocks" — healthy evolutionary pressure
        "unknown"    — insufficient data
    """
    if len(records) < _GOLDILOCKS_WINDOW:
        return "unknown"

    tail = records[-_GOLDILOCKS_WINDOW:]
    best_epis = [r.get("best_epi", 0.0) for r in tail]
    recent_epis = [r.get("epi", 0.0) for r in tail]

    avg_best = sum(best_epis) / len(best_epis)
    avg_recent = sum(recent_epis) / len(recent_epis)

    # Too easy: high best_epi AND high acceptance rate
    accepts = sum(1 for r in tail if r.get("B", 0) == 1)
    accept_rate = accepts / len(tail)

    if avg_best > _EASY_EPI_THRESHOLD and accept_rate > 0.4:
        return "too_easy"

    # Too hard: best_epi near zero OR zero acceptances
    if avg_best < _HARD_EPI_THRESHOLD or (avg_recent < _HARD_EPI_THRESHOLD and accepts == 0):
        return "too_hard"

    return "goldilocks"


# ═══════════════════════════════════════════════════════════════
# ENVIRONMENT GENOME MUTATION
# ═══════════════════════════════════════════════════════════════

def _mutate_genome(genome: Dict[str, Any], direction: str) -> Dict[str, Any]:
    """Mutate the environment genome.

    direction:
        "harder" — increase chaos parameters (wider rho_range, stronger coupling,
                   faster regime switches, higher rossler_c)
        "easier" — decrease chaos parameters (narrow rho_range, weaker coupling,
                   slower regime switches)

    Each numeric parameter is perturbed by ±_MUTATION_RATE with directional bias.
    Parameters are clamped to _PARAM_BOUNDS to prevent numerical divergence.
    """
    mutated = copy.deepcopy(genome)

    # Parameters that increase difficulty when raised
    harder_up = {
        "rho_range", "coupling_kappa_min", "coupling_kappa_max",
        "rossler_c", "rossler_a",
    }
    # Parameters that increase difficulty when lowered
    harder_down = {
        "regime_switch_freq_min", "regime_switch_freq_max",
    }

    for key, value in mutated.items():
        if key not in _PARAM_BOUNDS:
            continue
        if not isinstance(value, (int, float)):
            continue

        lo, hi = _PARAM_BOUNDS[key]

        # Decide mutation direction
        if direction == "harder":
            if key in harder_up:
                delta = abs(value) * _MUTATION_RATE * random.uniform(0.5, 1.5)
            elif key in harder_down:
                delta = -abs(value) * _MUTATION_RATE * random.uniform(0.5, 1.5)
            else:
                delta = value * _MUTATION_RATE * random.uniform(-0.5, 1.0)
        else:  # "easier"
            if key in harder_up:
                delta = -abs(value) * _MUTATION_RATE * random.uniform(0.5, 1.5)
            elif key in harder_down:
                delta = abs(value) * _MUTATION_RATE * random.uniform(0.5, 1.5)
            else:
                delta = value * _MUTATION_RATE * random.uniform(-1.0, 0.5)

        new_val = value + delta

        # Type preservation
        if isinstance(value, int):
            new_val = int(round(new_val))

        # Clamp to bounds
        new_val = max(lo, min(hi, new_val))
        mutated[key] = new_val

    # Ensure freq_min < freq_max
    if mutated["regime_switch_freq_min"] >= mutated["regime_switch_freq_max"]:
        mutated["regime_switch_freq_max"] = mutated["regime_switch_freq_min"] + 50

    # Ensure kappa_min < kappa_max
    if mutated["coupling_kappa_min"] >= mutated["coupling_kappa_max"]:
        mutated["coupling_kappa_max"] = mutated["coupling_kappa_min"] + 0.02

    return mutated


# ═══════════════════════════════════════════════════════════════
# ATOMIC IPC: Write active environment config
# ═══════════════════════════════════════════════════════════════

def _write_active_env_atomic(fs: FileSystemBus, genome: Dict[str, Any]) -> None:
    """Atomically write the active environment config.

    Uses tmp + os.rename() to prevent read/write collision with the
    Evaluator Swarm (same IPC pattern as candidate_pool).
    """
    active_dir = Path(fs.root) / _ENV_ACTIVE_DIR
    active_dir.mkdir(parents=True, exist_ok=True)

    dest = active_dir / "current.json"
    tmp = active_dir / ".current.json.tmp"

    content = json.dumps(genome, indent=2, ensure_ascii=False, default=str)
    tmp.write_text(content, encoding="utf-8")
    os.rename(str(tmp), str(dest))


def _load_active_env(fs: FileSystemBus) -> Dict[str, Any]:
    """Load the current active environment genome, or return baseline."""
    active_file = Path(fs.root) / _ENV_ACTIVE_FILE
    if not active_file.exists():
        return dict(_BASELINE_GENOME)

    try:
        raw = active_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            # Merge with baseline to fill any missing keys
            merged = dict(_BASELINE_GENOME)
            merged.update(data)
            return merged
    except (json.JSONDecodeError, OSError):
        pass

    return dict(_BASELINE_GENOME)


def _archive_env(fs: FileSystemBus, genome: Dict[str, Any], tag: str) -> Path:
    """Archive an environment genome to island_env/ with timestamp."""
    env_dir = Path(fs.root) / _ISLAND_ENV_DIR
    env_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    fname = f"env_{tag}_{ts}.json"
    dest = env_dir / fname
    dest.write_text(
        json.dumps(genome, indent=2, default=str),
        encoding="utf-8",
    )

    # FIFO pruning: keep only the newest _MAX_ARCHIVED_ENVS
    files = sorted(env_dir.glob("env_*.json"), key=lambda p: p.stat().st_mtime)
    if len(files) > _MAX_ARCHIVED_ENVS:
        for old_file in files[:-_MAX_ARCHIVED_ENVS]:
            try:
                old_file.unlink()
            except OSError:
                pass

    return dest


# ═══════════════════════════════════════════════════════════════
# THE ECOLOGY LOOP
# ═══════════════════════════════════════════════════════════════

def run(poll_interval: float = 120.0) -> None:
    """Continuous environment co-evolution loop.

    1. Load current environment genome.
    2. Poll evaluator telemetry.
    3. Assess Goldilocks Zone.
    4. If too easy: mutate harder, write new config.
    5. If too hard: rollback to previous or mutate easier.
    6. If goldilocks: do nothing (healthy pressure).
    7. Sleep and repeat.
    """
    fs = FileSystemBus(root="agi_workspace")

    # Ensure directory structure
    for d in [_ENV_ACTIVE_DIR, _ISLAND_ENV_DIR]:
        (Path(fs.root) / d).mkdir(parents=True, exist_ok=True)

    # Load or initialize the active environment
    current_genome = _load_active_env(fs)
    previous_genome = copy.deepcopy(current_genome)

    # Write baseline if no active config exists
    active_file = Path(fs.root) / _ENV_ACTIVE_FILE
    if not active_file.exists():
        _write_active_env_atomic(fs, current_genome)
        _archive_env(fs, current_genome, "baseline")
        print("[env_evolver] Initialized baseline environment genome.")

    last_mutation_tick: int = 0
    mutations_total: int = 0

    print(f"[env_evolver] Ecology Loop starting (TICK 12.0: The Cambrian Engine).")
    print(f"[env_evolver] poll={poll_interval}s | "
          f"goldilocks_window={_GOLDILOCKS_WINDOW} | "
          f"easy_thr={_EASY_EPI_THRESHOLD} | hard_thr={_HARD_EPI_THRESHOLD}")
    print(f"[env_evolver] Current genome: rho={current_genome['rho_center']}"
          f"±{current_genome['rho_range']} "
          f"κ=[{current_genome['coupling_kappa_min']},{current_genome['coupling_kappa_max']}]")

    while True:
        # ── 1. READ EVALUATOR TELEMETRY ────────────────────────────
        records = _read_recent_telemetry(fs, window=_GOLDILOCKS_WINDOW * 2)

        if not records:
            time.sleep(poll_interval)
            continue

        latest_tick = records[-1].get("tick", 0)

        # Anti-spam gate
        if latest_tick - last_mutation_tick < _MIN_TICKS_BETWEEN_MUTATIONS:
            time.sleep(poll_interval)
            continue

        # ── 2. ASSESS GOLDILOCKS ZONE ──────────────────────────────
        zone = _assess_goldilocks(records)

        if zone == "unknown":
            time.sleep(poll_interval)
            continue

        if zone == "goldilocks":
            # Healthy pressure — do nothing
            time.sleep(poll_interval)
            continue

        # ── 3. MUTATE ENVIRONMENT ──────────────────────────────────
        best_epi = records[-1].get("best_epi", 0.0)

        if zone == "too_easy":
            print(f"\n[env_evolver] ENVIRONMENT TOO EASY (best_epi={best_epi:.4f})")
            print(f"[env_evolver] Mutating environment HARDER to increase pressure...")

            previous_genome = copy.deepcopy(current_genome)
            current_genome = _mutate_genome(current_genome, "harder")

            # Stamp the genome
            current_genome["version"] = mutations_total + 1
            current_genome["timestamp"] = time.time()
            current_genome["mutation_direction"] = "harder"
            current_genome["trigger_epi"] = best_epi

            _write_active_env_atomic(fs, current_genome)
            archive_path = _archive_env(fs, current_genome, "harder")
            mutations_total += 1
            last_mutation_tick = latest_tick

            print(f"[env_evolver] New genome v{mutations_total}: "
                  f"rho={current_genome['rho_center']:.1f}"
                  f"±{current_genome['rho_range']:.1f} "
                  f"κ=[{current_genome['coupling_kappa_min']:.3f},"
                  f"{current_genome['coupling_kappa_max']:.3f}]")
            print(f"[env_evolver] Archived: {archive_path.name}")

            # Log event
            fs.append("logs/env_evolver_events.ndjson", {
                "event": "mutation",
                "direction": "harder",
                "version": mutations_total,
                "trigger_epi": best_epi,
                "zone": zone,
                "genome": current_genome,
                "t": time.time(),
            })

        elif zone == "too_hard":
            print(f"\n[env_evolver] ENVIRONMENT TOO HARD (best_epi={best_epi:.4f})")
            print(f"[env_evolver] MASS EXTINCTION detected. Rolling back...")

            # Rollback: restore previous genome or mutate easier
            if previous_genome != current_genome:
                current_genome = copy.deepcopy(previous_genome)
                print(f"[env_evolver] Rolled back to previous genome.")
            else:
                current_genome = _mutate_genome(current_genome, "easier")
                print(f"[env_evolver] No previous genome to rollback. Mutating easier.")

            current_genome["version"] = mutations_total + 1
            current_genome["timestamp"] = time.time()
            current_genome["mutation_direction"] = "rollback"
            current_genome["trigger_epi"] = best_epi

            _write_active_env_atomic(fs, current_genome)
            _archive_env(fs, current_genome, "rollback")
            mutations_total += 1
            last_mutation_tick = latest_tick

            print(f"[env_evolver] Restored genome v{mutations_total}: "
                  f"rho={current_genome['rho_center']:.1f}"
                  f"±{current_genome['rho_range']:.1f} "
                  f"κ=[{current_genome['coupling_kappa_min']:.3f},"
                  f"{current_genome['coupling_kappa_max']:.3f}]")

            fs.append("logs/env_evolver_events.ndjson", {
                "event": "rollback",
                "direction": "easier",
                "version": mutations_total,
                "trigger_epi": best_epi,
                "zone": zone,
                "genome": current_genome,
                "t": time.time(),
            })

        time.sleep(poll_interval)


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TICK 12.0 -- Ecology Loop (Environment Co-Evolution). "
        "POET-inspired Goldilocks Zone maintenance for the "
        "coupled Lorenz-Rössler chaotic attractor."
    )
    parser.add_argument(
        "--poll-interval", type=float, default=120.0,
        help="Seconds between telemetry checks (default: 120)",
    )
    args = parser.parse_args()
    try:
        run(poll_interval=args.poll_interval)
    except KeyboardInterrupt:
        print("\n[env_evolver] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
