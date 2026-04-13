# Atomic Meta-Evolver

**A self-evolving Thermodynamic Neural Architecture Search (NAS) engine.** The system forces general computational primitives to emerge through strict deterministic state compression, chaotic environmental pressure, and thermodynamic survival constraints — eliminating context rot via stateless UNIX pipe execution.

**Current Version**: TICK 4.0 — The UNIX Cataclysm

---

## Architecture: The UNIX Pipe Cataclysm

The system is built on a single, radical design principle: **the Generator and the Environment must be physically separated processes**, connected only by a UNIX pipe. This is not a software abstraction — it is an OS-level enforcement of the Generator/Evaluator isolation axiom.

```
┌──────────────────────┐          ┌──────────────────────────────┐
│   THE ENVIRONMENT    │  UNIX    │      THE EVOLUTION ENGINE    │
│                      │  PIPE    │                              │
│   env_stream.py      │ ──────> │  run_evolution.py            │
│                      │  stdout  │                              │
│ Coupled Lorenz–      │  ──────> │  atomic_core.py              │
│ Rössler 6-D ODE      │  stdin   │    ├─ _evaluate()            │
│                      │          │    ├─ _vary()                │
│ Infinite chaotic     │  JSON    │    ├─ _meta_evolve()         │
│ token stream         │  Lines   │    └─ AtomicLLM (MoE)       │
└──────────────────────┘          └──────────────────────────────┘
```

**Why physical separation?** This aligns with [Anthropic's 2026 Harness philosophy](https://arxiv.org/abs/2603.28052): when the Generator and Evaluator share a process (or worse, a context window), the system develops *context anxiety* — the Generator learns to game the Evaluator's scoring heuristics rather than solving the actual problem. By placing the Environment in a separate OS process with no shared memory, reward hacking becomes physically impossible. The Generator receives raw chaotic data and must learn to predict it. There is no shortcut.

---

## The Chaotic Environment (`env_stream.py`)

The Environment is a continuously running chaotic dynamical system that streams high-entropy data to `stdout`.

### The Coupled Lorenz–Rössler System

A 6-dimensional ODE integrating two classical chaotic attractors with bidirectional coupling:

$$
\begin{aligned}
\dot{x} &= \sigma(y - x) + \kappa u & \dot{u} &= -v - w + \kappa x \\
\dot{y} &= x(\rho - z) - y & \dot{v} &= u + av \\
\dot{z} &= xy - \beta z & \dot{w} &= b + w(u - c)
\end{aligned}
$$

| Parameter | Value | Role |
|---|---|---|
| $\sigma$ | 10.0 | Lorenz Prandtl number |
| $\rho$ | 28.0 $\pm$ 4.0 | Lorenz Rayleigh number (regime-switched) |
| $\beta$ | 8/3 | Lorenz geometric factor |
| $a, b, c$ | 0.2, 0.2, 5.7 | Rössler parameters |
| $\kappa$ | [0.01, 0.12] | Bidirectional coupling strength |
| $\Delta t$ | 0.005 | RK4 integration timestep |

### Non-Stationary Dynamics

The system employs two mechanisms to prevent memorization:

1. **Regime Switching**: Every 150–300 sequences, $\rho$ shifts within the chaotic band [24, 32] and $\kappa$ is re-randomized. This creates distinct dynamical regimes that the NAS engine must continuously adapt to.

2. **Butterfly Effect Injection**: With probability 0.002 per state, a micro-perturbation $\mathcal{N}(0, 0.01)$ is added to all 6 dimensions. Due to chaotic sensitivity, this causes exponential trajectory divergence — a different future from a nearly identical present.

### Token Quantization

The continuous 3-D Lorenz state $(x, y, z)$ is quantized into discrete tokens within `VOCAB_SIZE = 512`:

| Dimension | Token Range | Bins | Physical Bounds |
|---|---|---|---|
| Lorenz $x$ | [220, 315] | 96 | [−25.0, 25.0] |
| Lorenz $y$ | [316, 411] | 96 | [−35.0, 35.0] |
| Lorenz $z$ | [412, 507] | 96 | [0.0, 55.0] |
| Reserved | [0, 219] | — | I-Ching / BioGeo / Logic / Special |
| Unused | [508, 511] | — | — |

Each sequence: **85 states × 3 tokens = 255 tokens + 1 PAD = 256** (`MAX_SEQ_LEN`).

Output format: one JSON line per sequence to `stdout`:
```json
{"tokens": [267, 384, 451, 243, 370, 489, ...]}
```

---

## The Evolution Engine (`atomic_core.py`)

### AtomicLLM: Mitotic Mixture-of-Experts Transformer

The backbone is a causal Transformer with a biologically-inspired **Mitotic MoE** architecture:

- **Experts** start as 1 (太極 — Tai Chi) and undergo binary fission: 1 → 2 → 4 → ... → 64
- Each fission creates a clone + Gaussian mutation ($\mathcal{N}(0, 0.05)$)
- Candidate I-Ching hexagram index determines expert routing: `router_idx % num_experts`
- Weight tying: `tok_emb.weight = head.weight`

### Evaluation: `_evaluate()`

The core fitness function reads chaotic data from `stdin` and scores the backbone's prediction:

1. **Read** one JSON line from the UNIX pipe (or fallback to local Lorenz if `stdin.isatty()`)
2. **Forward pass** through AtomicLLM with `router_idx = ic_idx[0] % 64`
3. **Cross-entropy loss** on next-token prediction (masked, excluding `PAD_TOKEN = 219`)
4. **Epiplexity** (effective structural complexity):

$$\text{epi} = \frac{\text{scale}}{\text{regret} + \epsilon} \cdot (1 + \text{div\_w} \cdot \text{unique})$$

Where:
- $\text{regret} = \text{loss} + \text{entropy\_penalty} + \text{topo\_penalty}$
- $\text{unique} = |\{t \in \text{tokens} : t \neq \text{PAD}\}| / V$
- $\text{entropy\_penalty}$ fires when diversity < 15% of vocabulary

5. **Thermodynamic penalty (Setting C)**: see below

### (1+1)-ES Meta-Evolution

Every 30 generations, the system evaluates whether a Gaussian perturbation to the rule parameters (I-Ching weights, BioGeometry routing weights, Epiplexity scaling) improved average Epiplexity:

- **Success** (improved): keep mutation, expand step sizes × 1.2
- **Failure** (regressed): rollback rules, shrink step sizes × 0.82
- Follows the **1/5th success rule** from Evolution Strategies

---

## Thermodynamic Survival — Setting C

> *"A neural network that consumes all available compute to solve a trivial task is not intelligent. Intelligence is the discovery of sparse, efficient structure."*

### The Self-Lobotomy Problem

When the evaluation task has low information entropy (e.g., predicting a simple graph encoding), the NAS engine discovers a degenerate optimum: **shrink the architecture to `FF_DIM=1`, `NUM_LAYERS=2`**. This minimizes the thermodynamic cost while still solving the trivial task — a rational but catastrophic "self-lobotomy."

### The Thermodynamic Penalty

Setting C forces the network to pay for the physical resources it consumes:

$$\text{thermo\_cost} = W_{\text{thermo}} \cdot \left(\frac{\text{CPU\%}}{100} + \frac{\text{RAM\%}}{100}\right)$$

$$\text{epi}_{\text{final}} = \max\left(\text{epi} - \text{thermo\_cost},\ \epsilon\right)$$

Where $W_{\text{thermo}} = 0.1$ (default). This creates a **game-theoretic tension**:

| Pressure | Direction | Effect |
|---|---|---|
| Chaotic prediction loss | Grow architecture | Need capacity to model 6-D attractor |
| Thermodynamic penalty | Shrink architecture | Pay less CPU/RAM tax |
| **Nash equilibrium** | **Sparse efficiency** | **Discover mathematical structure** |

The system converges toward architectures that are **maximally expressive per unit of compute** — the definition of intelligence under resource constraints.

---

## The Dual-Loop Meta-Harness (Tick 1)

### Inner-Loop (Code Evolution — Object-Level)
1. **Handoff**: Read `harness_contract.md` and `Structured_Handoff.md`
2. **Variation** (@Generator): LLM maps code to discrete matrices (I-Ching/BioGeometry)
3. **Evaluation** (@Evaluator): Dynamic PoW constraints, Boolean filter
4. **Selection**: $\mathbb{B} = 1$ → `git commit`, entropy decreases. $\mathbb{B} = 0$ → `.trace` file, hard drop.

### Outer-Loop (Meta-Harness Evolution — Meta-Level)
Triggered when Heat Death detected (Epiplexity stagnant for $N > 20$ consecutive ticks):

1. **Holographic Trace Access**: @Orchestrator reads raw `.trace` files (compiler stack traces, AST collision logs, Git hashes)
2. **Meta-Mutation**: Mutates `harness_contract.md` itself — altering prompting strategies, role definitions, evaluation metrics
3. **Dynamic PoW Scaling**: Success rate > 30% over 50 ticks → auto-escalate difficulty (× 1.15)

---

## System Axioms (Eternal Rules)

1. **Variation**: All mutations operate on executable atoms (hypergraph / I-Ching / BioGeometry / LLM block / Logic Gates). The atoms themselves are evolvable.

2. **Objective Feedback**: Evaluation returns exactly two scalars — Epiplexity (effective structure) and Regret (evolutionary gradient). No other signals.

3. **Selection + Compression**: Darwinian population retains high-Epiplexity / low-Regret elites. Pareto sparsification and fractal compression emerge naturally from sorting under gradient.

4. **Self-Referential**: The entire pipeline is file-based. The pipeline itself — backbone, atom rules, Epiplexity definition, selection thresholds — can be evolved by the same mechanism.

---

## Agent Roles

| Agent | Responsibility |
|---|---|
| **@Orchestrator** | Monitors Heat Death, triggers Outer-Loop, ingests `.trace` files, mutates harness |
| **@Generator** | Produces candidate mutations via I-Ching / BioGeometry topological variation |
| **@Evaluator** | Runs Dynamic PoW tests, writes `.trace` on rejection, manages difficulty scaling |

---

## Quick Start

```bash
# TICK 4.0: Pipe chaotic environment into the evolution engine
python env_stream.py | python run_evolution.py 500

# Standalone mode (fallback: internal Lorenz, degraded entropy)
python run_evolution.py 500

# Single stateless tick (for testing)
python stateless_tick.py --threshold 0.30 --device mps

# Autonomous multiverse daemon
python ouroboros.py
```

---

## Directory Structure

| File | Purpose |
|---|---|
| `env_stream.py` | Chaotic environment stream (Lorenz–Rössler 6-D ODE) |
| `atomic_core.py` | Core evolution engine (AtomicCore, AtomicLLM, StateCodec) |
| `run_evolution.py` | Evolution runner (checkpoint, logging, integrity checks) |
| `stateless_tick.py` | Single tick executor with `.trace` logging and LLM NAS |
| `harness_contract.md` | NLAH orchestrator contract (mutated during Outer-Loop) |
| `fractal_router.py` | Kronecker fractal routing and AST hashing |
| `fs_bus.py` | Filesystem I/O bus (Git-backed state persistence) |
| `ouroboros.py` | Autonomous multiverse evolution daemon |
| `git_msa_daemon.py` | Evolutionary conservation lock daemon |
| `meta_rules.json` | Eternal axioms and hardened rules (surviving >10k ticks) |
| `pow_difficulty.json` | Dynamic PoW difficulty state |
| `*.trace` | Raw compiler/AST diagnostic trace files |

---

## Model Minimum Threshold

The NAS architect role requires a model capable of:

1. **Spatial tensor reasoning** — understanding how `FF_DIM`, `NUM_HEADS`, `EMBED_DIM` interact as geometric constraints on representational capacity
2. **Physical constraint mapping** — translating Setting C's thermodynamic penalty into architectural decisions (e.g., "high CPU cost → reduce layer count, increase sparsity")
3. **Multi-objective optimization** — balancing prediction accuracy against resource consumption in a non-trivial Pareto landscape

Empirically, models below ~7B parameters (e.g., 0.8B) consistently **self-lobotomize**: they minimize the architecture to trivially small dimensions to avoid the thermodynamic penalty, because they lack the reasoning depth to discover that a *structured* larger architecture can achieve lower total cost (better prediction offsets higher compute). The 7B threshold is the empirical minimum for an AGI architect that can navigate this trade-off.

---

## References

- [Meta-Harness Architecture (arXiv:2603.28052)](https://arxiv.org/abs/2603.28052)
- Lorenz, E.N. (1963). "Deterministic Nonperiodic Flow." *Journal of the Atmospheric Sciences*, 20(2), 130–141.
- Rössler, O.E. (1976). "An Equation for Continuous Chaos." *Physics Letters A*, 57(5), 397–398.
- Landauer, R. (1961). "Irreversibility and Heat Generation in the Computing Process." *IBM Journal*, 5(3), 183–191.
- See [WHITEPAPER_EN.md](WHITEPAPER_EN.md) for full formal specification.
