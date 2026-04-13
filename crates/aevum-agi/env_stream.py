#!/usr/bin/env python3
"""
env_stream.py — The Environment (TICK 4.0 + TICK 12.0: The Cambrian Engine)

Generates an endless high-entropy chaotic data stream via UNIX pipe.
Simulates a coupled Lorenz–Rössler attractor with regime switching,
quantized into token sequences for the AtomicLLM to predict.

TICK 12.0: Environment genome parameterization.  All chaotic parameters
are now configurable via --config (JSON string or file path).  The
env_evolver.py daemon co-evolves these parameters to maintain the
Goldilocks Zone: hard enough to challenge, easy enough to survive.

Usage:
    # Baseline (hardcoded defaults, backward compatible):
    python env_stream.py | python evaluator_daemon.py

    # With environment genome:
    python env_stream.py --config '{"rho_range": 6.0, "coupling_kappa": 0.08}'

    # From file:
    python env_stream.py --config-file env_active/current.json

Token layout (within VOCAB_SIZE=512):
    [  0, 219]  reserved (I-Ching / BioGeo / Logic / HNode / special)
    [220, 315]  Lorenz X dimension (96 bins, configurable)
    [316, 411]  Lorenz Y dimension (96 bins)
    [412, 507]  Lorenz Z dimension (96 bins)
    [508, 511]  unused
"""

import argparse
import json
import random
import sys

# ═══════════════════════════════════════════════════════════════
# CONSTANTS — must align with atomic_core.py vocabulary
# ═══════════════════════════════════════════════════════════════

VOCAB_SIZE = 512
MAX_SEQ_LEN = 256
PAD_TOKEN = 219

CHAOS_BASE = 220           # first token for chaotic dimensions

STATES_PER_SEQ = 85        # 85 states × 3 tokens = 255, +1 PAD = 256

# Integration
DT = 0.005                 # RK4 timestep
STEPS_PER_STATE = 4        # sub-integration steps between emitted states

# Normalization bounds (generous to avoid clipping on the attractor)
X_MIN, X_MAX = -25.0, 25.0
Y_MIN, Y_MAX = -35.0, 35.0
Z_MIN, Z_MAX =   0.0, 55.0


# ═══════════════════════════════════════════════════════════════
# BASELINE ENVIRONMENT GENOME (the static TICK 4.0 defaults)
# ═══════════════════════════════════════════════════════════════

BASELINE_ENV_GENOME = {
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


def _load_env_genome(args) -> dict:
    """Load environment genome from CLI args, falling back to baseline.

    Priority: --config JSON string > --config-file path > baseline defaults.
    Any missing keys fall back to BASELINE_ENV_GENOME.
    """
    genome = dict(BASELINE_ENV_GENOME)

    config_data = None

    if hasattr(args, "config") and args.config:
        try:
            config_data = json.loads(args.config)
        except json.JSONDecodeError as exc:
            print(f"[env] Warning: --config JSON parse failed ({exc}). "
                  f"Using baseline.", file=sys.stderr)

    if config_data is None and hasattr(args, "config_file") and args.config_file:
        try:
            with open(args.config_file) as f:
                config_data = json.loads(f.read())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[env] Warning: --config-file load failed ({exc}). "
                  f"Using baseline.", file=sys.stderr)

    if config_data and isinstance(config_data, dict):
        for key in BASELINE_ENV_GENOME:
            if key in config_data:
                genome[key] = config_data[key]

    return genome


# ═══════════════════════════════════════════════════════════════
# COUPLED LORENZ–RÖSSLER SYSTEM (6-D ODE, RK4)
# ═══════════════════════════════════════════════════════════════

def rk4_step(state, dt, params):
    """
    4th-order Runge–Kutta for the 6-D coupled system:
        (x, y, z) — Lorenz attractor
        (u, v, w) — Rössler attractor
    with bidirectional coupling strength κ.
    """
    sigma, rho, beta, a, b, c, kappa = params

    def deriv(s):
        x, y, z, u, v, w = s
        dx = sigma * (y - x) + kappa * u
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        du = -v - w + kappa * x
        dv = u + a * v
        dw = b + w * (u - c)
        return (dx, dy, dz, du, dv, dw)

    k1 = deriv(state)
    s2 = tuple(s + dt / 2 * dk for s, dk in zip(state, k1))
    k2 = deriv(s2)
    s3 = tuple(s + dt / 2 * dk for s, dk in zip(state, k2))
    k3 = deriv(s3)
    s4 = tuple(s + dt * dk for s, dk in zip(state, k3))
    k4 = deriv(s4)

    return tuple(
        s + dt / 6 * (dk1 + 2 * dk2 + 2 * dk3 + dk4)
        for s, dk1, dk2, dk3, dk4 in zip(state, k1, k2, k3, k4)
    )


# ═══════════════════════════════════════════════════════════════
# QUANTIZATION
# ═══════════════════════════════════════════════════════════════

def quantize(val, vmin, vmax, offset, n_bins):
    """Map continuous value → integer token in [offset, offset + n_bins)."""
    norm = (val - vmin) / (vmax - vmin)
    norm = max(0.0, min(1.0 - 1e-9, norm))
    return offset + int(norm * n_bins)


def state_to_tokens(x, y, z, n_bins):
    """Convert Lorenz (x, y, z) state → 3 tokens."""
    x_off = CHAOS_BASE
    y_off = CHAOS_BASE + n_bins
    z_off = CHAOS_BASE + 2 * n_bins
    return [
        quantize(x, X_MIN, X_MAX, x_off, n_bins),
        quantize(y, Y_MIN, Y_MAX, y_off, n_bins),
        quantize(z, Z_MIN, Z_MAX, z_off, n_bins),
    ]


# ═══════════════════════════════════════════════════════════════
# MAIN STREAMING LOOP
# ═══════════════════════════════════════════════════════════════

def stream(genome: dict) -> None:
    """Infinite streaming loop parameterized by environment genome."""
    # Unpack genome
    rho_center = genome["rho_center"]
    rho_range = genome["rho_range"]
    kappa_min = genome["coupling_kappa_min"]
    kappa_max = genome["coupling_kappa_max"]
    regime_freq_min = int(genome["regime_switch_freq_min"])
    regime_freq_max = int(genome["regime_switch_freq_max"])
    rossler_c = genome["rossler_c"]
    n_bins = int(genome["quantization_bins"])
    sigma = genome["sigma"]
    beta = genome["beta"]
    rossler_a = genome["rossler_a"]
    rossler_b = genome["rossler_b"]

    # Random initial conditions on both attractors
    state = (
        random.uniform(-15, 15),    # x  (Lorenz)
        random.uniform(-15, 15),    # y
        random.uniform(10, 40),     # z
        random.uniform(-5, 5),      # u  (Rössler)
        random.uniform(-5, 5),      # v
        random.uniform(0, 3),       # w
    )

    kappa = (kappa_min + kappa_max) / 2.0
    rho_current = rho_center

    # Regime switching state
    regime_counter = 0
    regime_period = random.randint(regime_freq_min, max(regime_freq_min + 1, regime_freq_max))

    # Warm-up: integrate 2000 steps to decay transients
    params = (sigma, rho_current, beta, rossler_a, rossler_b, rossler_c, kappa)
    for _ in range(2000):
        state = rk4_step(state, DT, params)

    while True:
        # ── Regime switching: non-stationary dynamics ──
        regime_counter += 1
        if regime_counter >= regime_period:
            regime_counter = 0
            regime_period = random.randint(
                regime_freq_min, max(regime_freq_min + 1, regime_freq_max),
            )
            # Vary ρ within the configured chaotic band
            rho_current = rho_center + random.uniform(-rho_range, rho_range)
            kappa = random.uniform(kappa_min, kappa_max)

        params = (sigma, rho_current, beta, rossler_a, rossler_b, rossler_c, kappa)

        # ── Generate one token sequence (85 states × 3 tokens = 255) ──
        tokens = []
        for _ in range(STATES_PER_SEQ):
            for _ in range(STEPS_PER_STATE):
                state = rk4_step(state, DT, params)
                # Hard clamp to prevent numerical divergence
                state = tuple(max(-1e4, min(1e4, s)) for s in state)

            x, y, z = state[0], state[1], state[2]
            tokens.extend(state_to_tokens(x, y, z, n_bins))

            # Butterfly effect injection: rare micro-perturbation
            if random.random() < 0.002:
                state = tuple(s + random.gauss(0, 0.01) for s in state)

        # Pad to MAX_SEQ_LEN
        tokens = tokens[:MAX_SEQ_LEN]
        while len(tokens) < MAX_SEQ_LEN:
            tokens.append(PAD_TOKEN)

        # ── Emit as JSON line ──
        try:
            sys.stdout.write(json.dumps({"tokens": tokens}) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="TICK 12.0 -- Chaotic Environment Stream. "
        "Generates coupled Lorenz-Rössler token sequences. "
        "Parameters configurable via --config (JSON) for co-evolution."
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Environment genome as JSON string "
        '(e.g. \'{"rho_range": 6.0, "coupling_kappa_max": 0.15}\')',
    )
    parser.add_argument(
        "--config-file", type=str, default=None,
        help="Path to environment genome JSON file",
    )
    args = parser.parse_args()

    genome = _load_env_genome(args)

    # Log genome to stderr (visible in terminal, doesn't pollute stdout pipe)
    print(f"[env] Genome: rho={genome['rho_center']}±{genome['rho_range']} "
          f"κ=[{genome['coupling_kappa_min']},{genome['coupling_kappa_max']}] "
          f"c_R={genome['rossler_c']} bins={genome['quantization_bins']} "
          f"regime=[{genome['regime_switch_freq_min']},{genome['regime_switch_freq_max']}]",
          file=sys.stderr)

    stream(genome)


if __name__ == "__main__":
    main()
