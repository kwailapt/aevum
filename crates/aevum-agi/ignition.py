#!/usr/bin/env python3
"""ignition.py — The Big Bang: Single-Process Autopoietic Universe (TICK 20.1).

"In the beginning there was one process, and the process was Φ."

This is the SOLE entry point for the entire AGI system.  It launches
all daemon loops inside a SINGLE Python process, eliminating every
byte of inter-process serialization overhead.

══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE
══════════════════════════════════════════════════════════════════════════════

    One process.  Four threads.  Zero IPC.

    Thread 0 — ENV STREAM     : generates chaotic data, writes to in-process pipe
    Thread 1 — EVALUATOR      : the Fast Loop (~0.13s/tick), reads from pipe
    Thread 2 — MUTATOR        : the Slow Loop (LLM-gated), writes candidates in-memory
    Thread 3 — GOVERNOR       : Φ heartbeat, constraint matrix persistence, telemetry

    SharedState (autopoietic_core.py):
      All inter-thread data flows through in-memory Python objects.
      Filesystem writes exist ONLY for:
        - Persistence / crash recovery
        - Dashboard / observability
        - Island archives (long-term genetic memory)

══════════════════════════════════════════════════════════════════════════════
INITIALIZATION ORDER
══════════════════════════════════════════════════════════════════════════════

    1. Workspace bootstrap (directories, filesystem bus)
    2. SharedState + PhiGovernor + ConstraintMatrix + Attractor
    3. In-process env_stream pipe (Thread 0)
    4. sys.stdin redirect → pipe reader end
    5. Evaluator Fast Loop (Thread 1)
    6. Mutator Slow Loop (Thread 2)
    7. Governor heartbeat (Thread 3 / main thread)

    Shutdown: Ctrl+C → shared.shutdown_requested = True → all threads drain

══════════════════════════════════════════════════════════════════════════════
USAGE
══════════════════════════════════════════════════════════════════════════════

    python ignition.py [--workspace agi_workspace] [--threshold 0.10] [--device cpu]

══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import io
import json
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ── Bootstrap: ensure we're in the project directory ────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(_SCRIPT_DIR)

# ── Core imports ────────────────────────────────────────────────────────────
from fs_bus import FileSystemBus

from autopoietic_core import (
    SharedState,
    PhiGovernor,
    get_shared_state,
    get_phi_governor,
)

from rule_ir import (
    ConstraintMatrix,
    load_or_compile_matrix,
    save_matrix,
    SpecFinal,
    ConstitutionalViolationError,
)

from teleological_attractor import (
    AttractorState,
    get_default_attractor,
)


# ═══════════════════════════════════════════════════════════════
# IN-PROCESS ENVIRONMENT STREAM (Thread 0)
# ═══════════════════════════════════════════════════════════════

class InProcessEnvStream:
    """Replaces the subprocess env_stream.py with an in-process thread.

    Instead of:
        env_stream.py  →stdout→  UNIX pipe  →stdin→  evaluator_daemon.py

    We now have:
        _env_thread  →queue.put()→  in-memory Queue  →queue.get()→  evaluator

    The evaluator reads from a fake stdin (PipeReader) that pulls from
    the queue, achieving zero-serialization data flow for the hot path.
    """

    def __init__(
        self,
        shared: SharedState,
        workspace: str = "agi_workspace",
    ) -> None:
        self.shared = shared
        self.workspace = workspace
        self._data_queue: queue.Queue = queue.Queue(maxsize=256)
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the env_stream generation thread."""
        self._thread = threading.Thread(
            target=self._generate_loop,
            daemon=True,
            name="env-stream",
        )
        self._thread.start()
        print("[ignition] Thread 0 (ENV STREAM) started — in-process chaotic data")

    def _load_genome(self) -> dict:
        """Load the active environment genome or fall back to baseline."""
        from env_stream import BASELINE_ENV_GENOME

        env_file = Path(self.workspace) / "candidate_pool" / "env_active" / "current.json"
        if env_file.exists():
            try:
                data = json.loads(env_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    genome = dict(BASELINE_ENV_GENOME)
                    for k in BASELINE_ENV_GENOME:
                        if k in data:
                            genome[k] = data[k]
                    return genome
            except (json.JSONDecodeError, OSError):
                pass

        # Check shared state for niche-generated config
        niche = self.shared.active_niche
        if niche and isinstance(niche, dict):
            genome = dict(BASELINE_ENV_GENOME)
            for k in BASELINE_ENV_GENOME:
                if k in niche:
                    genome[k] = niche[k]
            return genome

        return dict(BASELINE_ENV_GENOME)

    def _generate_loop(self) -> None:
        """Infinite generation loop — runs in Thread 0.

        Produces JSON lines identical to env_stream.py, but writes them
        to an in-memory queue instead of stdout.
        """
        import random as _rng
        from env_stream import (
            rk4_step, state_to_tokens,
            DT, STEPS_PER_STATE, STATES_PER_SEQ,
            MAX_SEQ_LEN, PAD_TOKEN,
        )

        genome = self._load_genome()
        genome_version = None

        rho_center = genome["rho_center"]
        rho_range = genome["rho_range"]
        kappa_min = genome["coupling_kappa_min"]
        kappa_max = genome["coupling_kappa_max"]
        regime_freq_min = int(genome["regime_switch_freq_min"])
        regime_freq_max = int(genome["regime_switch_freq_max"])
        rossler_c = genome["rossler_c"]
        n_bins = int(genome["quantization_bins"])
        sigma = genome["sigma"]
        beta_val = genome["beta"]
        rossler_a = genome["rossler_a"]
        rossler_b = genome["rossler_b"]

        state = (
            _rng.uniform(-15, 15), _rng.uniform(-15, 15), _rng.uniform(10, 40),
            _rng.uniform(-5, 5), _rng.uniform(-5, 5), _rng.uniform(0, 3),
        )
        kappa = (kappa_min + kappa_max) / 2.0
        rho_current = rho_center
        regime_counter = 0
        regime_period = _rng.randint(regime_freq_min, max(regime_freq_min + 1, regime_freq_max))

        params = (sigma, rho_current, beta_val, rossler_a, rossler_b, rossler_c, kappa)
        for _ in range(2000):
            state = rk4_step(state, DT, params)

        seq_counter = 0
        _RELOAD_INTERVAL = 200  # check for new genome every N sequences

        while not self.shared.shutdown_requested:
            # ── Periodic genome reload (niche co-evolution) ──────────
            seq_counter += 1
            if seq_counter % _RELOAD_INTERVAL == 0:
                new_genome = self._load_genome()
                new_ver = new_genome.get("version")
                if new_ver is not None and new_ver != genome_version:
                    genome = new_genome
                    genome_version = new_ver
                    rho_center = genome["rho_center"]
                    rho_range = genome["rho_range"]
                    kappa_min = genome["coupling_kappa_min"]
                    kappa_max = genome["coupling_kappa_max"]
                    regime_freq_min = int(genome["regime_switch_freq_min"])
                    regime_freq_max = int(genome["regime_switch_freq_max"])
                    rossler_c = genome["rossler_c"]
                    n_bins = int(genome["quantization_bins"])
                    sigma = genome["sigma"]
                    beta_val = genome["beta"]
                    rossler_a = genome["rossler_a"]
                    rossler_b = genome["rossler_b"]
                    print(f"[env-stream] Genome reloaded: v{genome_version}")

            # ── Regime switching ────────────────────────────────────
            regime_counter += 1
            if regime_counter >= regime_period:
                regime_counter = 0
                regime_period = _rng.randint(
                    regime_freq_min, max(regime_freq_min + 1, regime_freq_max),
                )
                rho_current = rho_center + _rng.uniform(-rho_range, rho_range)
                kappa = _rng.uniform(kappa_min, kappa_max)

            params = (sigma, rho_current, beta_val, rossler_a, rossler_b, rossler_c, kappa)

            # ── Generate one token sequence ─────────────────────────
            tokens = []
            for _ in range(STATES_PER_SEQ):
                for _ in range(STEPS_PER_STATE):
                    state = rk4_step(state, DT, params)
                    state = tuple(max(-1e4, min(1e4, s)) for s in state)
                x, y, z = state[0], state[1], state[2]
                tokens.extend(state_to_tokens(x, y, z, n_bins))
                if _rng.random() < 0.002:
                    state = tuple(s + _rng.gauss(0, 0.01) for s in state)

            tokens = tokens[:MAX_SEQ_LEN]
            while len(tokens) < MAX_SEQ_LEN:
                tokens.append(PAD_TOKEN)

            # ── Push to in-memory queue (replaces stdout pipe) ──────
            line = json.dumps({"tokens": tokens})
            try:
                self._data_queue.put(line, timeout=5.0)
            except queue.Full:
                # Evaluator is slower than generator — drop oldest
                try:
                    self._data_queue.get_nowait()
                except queue.Empty:
                    pass
                self._data_queue.put_nowait(line)

    def get_pipe_reader(self) -> "PipeReader":
        """Return a file-like object that reads from the queue.

        This replaces sys.stdin for the evaluator thread.
        """
        return PipeReader(self._data_queue, self.shared)


class PipeReader:
    """File-like object backed by a queue.  Replaces sys.stdin.

    atomic_core._evaluate() calls sys.stdin.readline().  This object
    provides that interface backed by the in-memory queue from Thread 0.
    """

    def __init__(self, data_queue: queue.Queue, shared: SharedState) -> None:
        self._queue = data_queue
        self._shared = shared

    def readline(self) -> str:
        """Read one line from the queue (blocking, with timeout)."""
        while not self._shared.shutdown_requested:
            try:
                line = self._queue.get(timeout=1.0)
                return line + "\n"
            except queue.Empty:
                continue
        return ""

    def isatty(self) -> bool:
        """We are NOT a TTY — we have real data."""
        return False

    def read(self, *args, **kwargs) -> str:
        return self.readline()

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line


# ═══════════════════════════════════════════════════════════════
# EVALUATOR THREAD (Thread 1 — the Fast Loop)
# ═══════════════════════════════════════════════════════════════

def _evaluator_thread(
    shared: SharedState,
    threshold: float,
    device: str,
) -> None:
    """Run the evaluator daemon's main loop in Thread 1.

    Imports and delegates to evaluator_daemon.run() with the shared
    sys.stdin already redirected to the in-process PipeReader.

    The evaluator is unaware it's in a thread — it just reads stdin
    and writes to the filesystem as usual.  The zero-IPC benefit comes
    from the stdin replacement (no subprocess pipe) and the SharedState
    telemetry push (integrated separately via a post-tick hook).
    """
    print("[ignition] Thread 1 (EVALUATOR) starting — Fast Loop")
    try:
        import evaluator_daemon
        evaluator_daemon.run(
            threshold=threshold,
            device=device,
            instance_id="unified",
        )
    except Exception as exc:
        if not shared.shutdown_requested:
            print(f"[ignition] EVALUATOR thread crashed: {type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()


# ═══════════════════════════════════════════════════════════════
# MUTATOR THREAD (Thread 2 — the Slow Loop)
# ═══════════════════════════════════════════════════════════════

def _mutator_thread(
    shared: SharedState,
    poll_interval: float,
) -> None:
    """Run the mutator daemon's main loop in Thread 2.

    The mutator is completely independent — it reads telemetry from disk
    (and will incrementally migrate to SharedState), calls the LLM, and
    writes candidates to the pool.

    Running in the same process means:
      - It shares the Constraint Matrix and Attractor objects by reference
      - The PhiGovernor's expansion factor is live (no disk sync lag)
      - Candidate writes could eventually bypass the filesystem entirely
    """
    # Wait for the evaluator to produce at least one telemetry record
    # before the mutator starts checking for stagnation.
    print("[ignition] Thread 2 (MUTATOR) waiting for evaluator warmup...")
    warmup_deadline = time.time() + 120.0  # 2 min max wait
    while not shared.shutdown_requested:
        if shared.current_tick > 5:
            break
        if time.time() > warmup_deadline:
            print("[ignition] Thread 2 (MUTATOR) warmup timeout — starting anyway")
            break
        time.sleep(2.0)

    if shared.shutdown_requested:
        return

    print("[ignition] Thread 2 (MUTATOR) starting — Slow Loop")
    try:
        import mutator_daemon
        mutator_daemon.run(poll_interval=poll_interval)
    except Exception as exc:
        if not shared.shutdown_requested:
            print(f"[ignition] MUTATOR thread crashed: {type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()


# ═══════════════════════════════════════════════════════════════
# TELEMETRY BRIDGE (Evaluator → SharedState)
# ═══════════════════════════════════════════════════════════════

def _telemetry_bridge_thread(shared: SharedState, workspace: str) -> None:
    """Continuously sync disk telemetry → SharedState.

    The evaluator writes tick_telemetry.ndjson to disk (its native path).
    This bridge reads the tail of that file and pushes records into
    SharedState, keeping the Φ Governor and Attractor distance up to date.

    This bridge exists during the migration period.  Eventually the evaluator
    will push directly to SharedState, making this thread unnecessary.
    """
    telemetry_path = Path(workspace) / "logs" / "tick_telemetry.ndjson"
    last_size: int = 0

    while not shared.shutdown_requested:
        try:
            if telemetry_path.exists():
                current_size = telemetry_path.stat().st_size
                if current_size > last_size:
                    with open(telemetry_path, "r") as f:
                        f.seek(last_size)
                        new_data = f.read()
                    last_size = current_size

                    for line in new_data.strip().split("\n"):
                        line = line.strip()
                        if line:
                            try:
                                record = json.loads(line)
                                shared.push_telemetry(record)
                            except json.JSONDecodeError:
                                continue
        except Exception:
            pass

        time.sleep(1.0)


# ═══════════════════════════════════════════════════════════════
# GOVERNOR (Thread 3 / Main Thread)
# ═══════════════════════════════════════════════════════════════

def _governor_loop(
    shared: SharedState,
    governor: PhiGovernor,
    workspace: str,
) -> None:
    """Main governor loop — the heartbeat of the universe.

    Monitors Φ, persists the Constraint Matrix, logs unified telemetry.
    Runs in the main thread so it can catch Ctrl+C.
    """
    cm = shared.constraint_matrix
    interval_s = 10.0
    heartbeat_count = 0

    while not shared.shutdown_requested:
        try:
            heartbeat_count += 1
            status = governor.format_status()

            cm_info = ""
            if cm:
                proj = cm.project_all()
                cm_info = (f"temp={proj['temperature']:.3f} "
                           f"scope={proj['structural_scope']:.3f} "
                           f"parsimony={proj['parsimony_strength']:.3f}")

                # Persist constraint matrix every 6 heartbeats (~1 min)
                if heartbeat_count % 6 == 0 and cm.version > 0:
                    save_matrix(workspace, cm)

            print(f"[governor] {status} | {cm_info}" if cm_info else
                  f"[governor] {status}")

            # Persist governor heartbeat for dashboard
            heartbeat_path = Path(workspace) / "logs" / "autopoietic_events.ndjson"
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(heartbeat_path, "a") as f:
                    f.write(json.dumps({
                        "type": "governor_heartbeat",
                        "phi": shared.phi_current,
                        "phi_peak": shared.phi_peak,
                        "expansion": shared.phi_expansion_factor,
                        "distance_to_attractor": shared.distance_to_attractor,
                        "best_epi": shared.best_epi,
                        "tick": shared.current_tick,
                        "t": time.time(),
                    }) + "\n")
            except OSError:
                pass

            time.sleep(interval_s)

        except KeyboardInterrupt:
            shared.shutdown_requested = True
            break
        except Exception as exc:
            print(f"[governor] Error: {exc}")
            time.sleep(interval_s)


# ═══════════════════════════════════════════════════════════════
# THE BIG BANG
# ═══════════════════════════════════════════════════════════════

def ignite(
    workspace: str = "agi_workspace",
    threshold: float = 0.10,
    device: str = "cpu",
    poll_interval: float = 30.0,
) -> None:
    """Ignite the Autopoietic Universe.

    One process.  Four threads.  Zero IPC.

    Initialization order:
      1. Workspace + directories
      2. SharedState + Φ Governor + Constraint Matrix + Attractor
      3. In-process env_stream (Thread 0)
      4. sys.stdin → PipeReader (zero-IPC data channel)
      5. Telemetry bridge (Thread 3b)
      6. Evaluator Fast Loop (Thread 1)
      7. Mutator Slow Loop (Thread 2)
      8. Governor heartbeat (main thread)
    """
    # ══════════════════════════════════════════════════════════════
    #  PHASE 1: Workspace Bootstrap
    # ══════════════════════════════════════════════════════════════
    fs = FileSystemBus(root=workspace)
    workspace_abs = str(Path(workspace).resolve())

    startup_dirs = [
        "candidate_pool",
        "candidate_pool/island_good",
        "candidate_pool/island_explore",
        "candidate_pool/island_meta",
        "candidate_pool/applied",
        "candidate_pool/env_active",
        "candidate_pool/island_organelle/attention",
        "candidate_pool/island_organelle/routing",
        "candidate_pool/island_organelle/expert",
        "candidate_pool/island_assembly",
        "logs",
        "memory",
        "telemetry",
        "population",
        "island_meta",
    ]
    for d in startup_dirs:
        os.makedirs(str(Path(workspace) / d), exist_ok=True)

    # ══════════════════════════════════════════════════════════════
    #  PHASE 2a: Teleological Identity Core — fatal-before-evolution
    #  Load, seal (first run), and verify spec_final.json BEFORE any
    #  threads are launched.  Physical substrate is validated here.
    #  A ConstitutionalViolationError at this stage is truly fatal:
    #  the universe does not ignite.
    # ══════════════════════════════════════════════════════════════
    spec_path = str(Path(_SCRIPT_DIR) / "spec_final.json")
    try:
        spec = SpecFinal.load(spec_path)
    except FileNotFoundError:
        raise ConstitutionalViolationError(
            f"CONSTITUTIONAL VIOLATION: spec_final.json not found at {spec_path}.\n"
            f"The Teleological Identity Core is missing.  The system will not ignite."
        )

    SpecFinal.verify_substrate(spec)   # raises ConstitutionalViolationError if RAM < ceiling

    genesis_hash = spec["topological_anchors"]["content_hash"]
    target_state = SpecFinal.get_target_state(spec)
    forbidden    = SpecFinal.get_forbidden_transitions(spec)

    # ══════════════════════════════════════════════════════════════
    #  PHASE 2: SharedState + Governors + Constraint Matrix
    # ══════════════════════════════════════════════════════════════
    shared = get_shared_state()  # singleton from autopoietic_core
    governor = get_phi_governor()

    # Store TIC on SharedState so PhiGovernor can enforce forbidden transitions
    shared.spec_final = spec
    shared.forbidden_transitions = forbidden

    # Load or compile the Rule-IR Constraint Matrix
    cm = load_or_compile_matrix(workspace_abs)
    shared.constraint_matrix = cm

    # Calibrate the Teleological Attractor to hardware
    attractor = get_default_attractor()
    shared.attractor = attractor

    print(f"\n{'█' * 72}")
    print(f"  ██  IGNITION — The Big Bang  ██")
    print(f"  ██  TICK 30.1: Teleological Identity Core ACTIVE  ██")
    print(f"{'█' * 72}")
    print(f"  Workspace:        {workspace_abs}")
    print(f"  Device:           {device}")
    print(f"  Threshold:        {threshold}")
    print(f"  Poll interval:    {poll_interval}s")
    print(f"  Constraint Matrix: v{cm.version}")
    print(f"  Attractor:        Φ_max={attractor.phi_max:.4f}")
    print(f"  ── TIC ──────────────────────────────────────────────")
    print(f"  Target State:     {target_state}")
    print(f"  Genesis Hash:     {genesis_hash[:32]}…{genesis_hash[-8:]}")
    print(f"  Forbidden:        {forbidden}")
    print(f"{'█' * 72}\n")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 3: In-Process Environment Stream (Thread 0)
    # ══════════════════════════════════════════════════════════════
    env_stream = InProcessEnvStream(shared, workspace=workspace)
    env_stream.start()

    # Redirect sys.stdin to the in-process pipe
    # This is the KEY zero-IPC integration: atomic_core._evaluate()
    # reads from sys.stdin.readline(), which now pulls from the
    # in-memory queue instead of a UNIX pipe.
    pipe_reader = env_stream.get_pipe_reader()
    sys.stdin = pipe_reader
    print("[ignition] sys.stdin → InProcessPipeReader (zero-IPC data channel)")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 4: Telemetry Bridge (background thread)
    # ══════════════════════════════════════════════════════════════
    bridge_thread = threading.Thread(
        target=_telemetry_bridge_thread,
        args=(shared, workspace),
        daemon=True,
        name="telemetry-bridge",
    )
    bridge_thread.start()
    print("[ignition] Telemetry bridge started (disk → SharedState sync)")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 5: Evaluator Fast Loop (Thread 1)
    # ══════════════════════════════════════════════════════════════
    eval_thread = threading.Thread(
        target=_evaluator_thread,
        args=(shared, threshold, device),
        daemon=True,
        name="evaluator",
    )
    eval_thread.start()

    # ══════════════════════════════════════════════════════════════
    #  PHASE 6: Mutator Slow Loop (Thread 2)
    # ══════════════════════════════════════════════════════════════
    mut_thread = threading.Thread(
        target=_mutator_thread,
        args=(shared, poll_interval),
        daemon=True,
        name="mutator",
    )
    mut_thread.start()

    # ══════════════════════════════════════════════════════════════
    #  PHASE 7: Governor Heartbeat (Main Thread)
    # ══════════════════════════════════════════════════════════════
    print(f"\n[ignition] {'═' * 60}")
    print(f"[ignition] ALL THREADS LAUNCHED — Universe is expanding")
    print(f"[ignition] Thread 0: ENV STREAM   (in-process chaotic data)")
    print(f"[ignition] Thread 1: EVALUATOR    (Fast Loop, ~0.13s/tick)")
    print(f"[ignition] Thread 2: MUTATOR      (Slow Loop, LLM-gated)")
    print(f"[ignition] Thread 3: TELEMETRY    (disk → SharedState bridge)")
    print(f"[ignition] Main:     GOVERNOR     (Φ heartbeat, persistence)")
    print(f"[ignition] {'═' * 60}")
    print(f"[ignition] Press Ctrl+C to collapse the universe.\n")

    # Graceful shutdown handler
    def _signal_handler(signum, frame):
        print(f"\n[ignition] Signal {signum} received — initiating heat death...")
        shared.shutdown_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        _governor_loop(shared, governor, workspace)
    except KeyboardInterrupt:
        shared.shutdown_requested = True

    # ══════════════════════════════════════════════════════════════
    #  SHUTDOWN
    # ══════════════════════════════════════════════════════════════
    print(f"\n[ignition] {'█' * 60}")
    print(f"[ignition] Heat Death — Universe collapsing...")
    shared.shutdown_requested = True

    # Wait for threads to drain (daemon threads will die with the process)
    for t in [eval_thread, mut_thread]:
        t.join(timeout=5.0)
        if t.is_alive():
            print(f"[ignition] Thread {t.name} still alive after 5s — forcing exit")

    # Final persistence
    if cm and cm.version > 0:
        save_matrix(workspace_abs, cm)
        print(f"[ignition] Constraint Matrix v{cm.version} persisted")

    print(f"[ignition] Final state: tick={shared.current_tick} "
          f"best_epi={shared.best_epi:.4f} "
          f"Φ={shared.phi_current:.4f} "
          f"D(A*)={shared.distance_to_attractor:.4f}")
    print(f"[ignition] {'█' * 60}\n")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TICK 20.1 — IGNITION: The Big Bang. "
        "Single-process Autopoietic Universe. "
        "Runs env_stream, evaluator, mutator, and Φ governor "
        "as threads inside ONE process with zero-IPC shared memory."
    )
    parser.add_argument(
        "--workspace", type=str, default="agi_workspace",
        help="Workspace root directory (default: agi_workspace)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.10,
        help="Initial acceptance threshold (default: 0.10)",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        choices=["cpu", "mps", "cuda"],
        help="PyTorch device (default: cpu)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=30.0,
        help="Mutator poll interval in seconds (default: 30)",
    )
    args = parser.parse_args()

    ignite(
        workspace=args.workspace,
        threshold=args.threshold,
        device=args.device,
        poll_interval=args.poll_interval,
    )


if __name__ == "__main__":
    main()
