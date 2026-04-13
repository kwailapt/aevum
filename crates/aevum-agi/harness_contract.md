# NLAH Harness Contract v2.0 — Tick 1 Dual-Loop Meta-Harness
# Natural Language Agent Harness — Minimax Game Definition (Dual-Loop)

---

## Dual-Loop Architecture

### Inner-Loop (Generator <-> Evaluator)

The Inner-Loop is the per-tick minimax game. Generator produces a candidate; Evaluator accepts or annihilates it. On $\mathbb{B} = 0$, the Evaluator writes a `.trace` file capturing all failure telemetry before the hard drop. No information is lost — it flows into the trace archive.

### Outer-Loop (Orchestrator — Meta-Mutation)

The Outer-Loop activates when `heat_death_counter > N` (default $N = 20$ consecutive stagnant ticks where $\mathbb{B} = 0$). The system has entered thermal death — the Inner-Loop's current strategy cannot escape its basin.

The @Orchestrator executes the following sequence:

1. **Read** raw `.trace` files from `agi_workspace/traces/tick_{N}.trace` covering the stagnant window.
2. **Analyze** compiler output patterns, AST collision frequencies, regret accumulation curves, and entropy penalty distributions across the trace window.
3. **Mutate THIS contract file** (`harness_contract.md`) — altering prompting strategies, role weights, evaluation metrics, difficulty parameters, or any other aspect of the harness definition.
4. **Reset** `heat_death_counter` to 0.
5. **Resume** Inner-Loop under the mutated contract.

The Outer-Loop is the system's mechanism for escaping local minima in strategy space. The contract itself is a phenotype subject to evolutionary pressure.

---

## Roles

### @Generator
- Reads `Structured_Handoff.md` for current state ($C_{t-1}$).
- Produces a candidate tensor $C'_t = [S'_t, R'_t]^T$ via topological variation.
- Mutation rate governed by I Ching hexagram weights in `iching_rules.json`.
- Output must conform to BioGeometry discrete matrix constraints.
- **Goal**: Minimize topological energy while maximizing structural novelty.

### @Evaluator
- Receives $C'_t$ from Generator (no shared context — strict GAN isolation).
- Runs deterministic Proof-of-Work tests:
  1. Boolean compilation check: $\mathbb{B} \in \{0, 1\}$.
  2. AST structural hash via `KroneckerFractalRouter` (topological symmetry).
  3. Epiplexity metric: $\text{epi} = \frac{\text{scale}}{\text{regret} + \epsilon} \cdot (1 + \text{div\_w} \cdot \text{unique})$.
- Maintains the 50-tick sliding window for Dynamic PoW Difficulty (see below).
- On $\mathbb{B} = 0$: writes `.trace` file before hard drop.
- **Goal**: Generate the hardest possible PoW constraints. Break the Generator.

### @Orchestrator
- Dormant during normal Inner-Loop operation. Activates ONLY when `heat_death_counter > N`.
- Has read access to ALL `.trace` files in `agi_workspace/traces/`.
- Has write access to `harness_contract.md` (this file).
- Performs multi-trace analysis: identifies dominant failure modes, regret attractors, and topological dead-ends.
- Mutates the contract to shift the fitness landscape — new evaluation weights, altered prompting heuristics, recalibrated difficulty curves.
- **Goal**: Ensure the system never permanently stagnates. Escape every basin.

---

## Holographic Trace Access Protocol

When $\mathbb{B} = 0$, the Evaluator writes a trace file to `agi_workspace/traces/tick_{N}.trace` with the following exact structure:

```
=== TRACE: tick {N} ===
timestamp: {unix_timestamp}
generation: {gen}
epiplexity: {epi}
threshold: {threshold}
regret: {regret}
loss: {loss_value}
entropy_penalty: {penalty}
topo_penalty: {topo_penalty}
fractal_address: {addr}
route_slot: {slot}
routing_variance: {variance}
parent_commit: {git_hash}
=== END TRACE ===
```

Field definitions:
- `timestamp`: Unix epoch seconds at evaluation time.
- `generation`: Current generation counter from `Structured_Handoff.md`.
- `epiplexity`: Computed epiplexity score of the rejected candidate.
- `threshold`: The PoW threshold the candidate failed to meet.
- `regret`: Cumulative regret at time of evaluation.
- `loss`: Raw loss value before penalty application.
- `entropy_penalty`: Penalty applied for insufficient structural entropy.
- `topo_penalty`: Penalty from topological energy exceeding population mean.
- `fractal_address`: The candidate's hashed position in $64^d$ Kronecker space.
- `route_slot`: Assigned routing slot from the KroneckerFractalRouter.
- `routing_variance`: Variance of the routing distribution at evaluation time.
- `parent_commit`: Git hash of the last successful commit (the state the candidate branched from).

Trace files are managed by a **FIFO sliding window** (size=5). Only the last 5 full traces are retained on disk. Older traces are compressed to single-line NDJSON scalar summaries in `traces/_compressed_history.ndjson` before deletion. This prevents I/O bottlenecking and storage explosion while preserving the fossil record in lossy-compressed form.

---

## Dynamic PoW Difficulty Protocol

The Evaluator maintains a 50-tick sliding window of $\mathbb{B}$ values to dynamically scale proof-of-work difficulty.

**State**: Persisted in `pow_difficulty.json`:
```json
{
  "window": [0, 1, 0, 0, 1, ...],
  "pow_difficulty_level": 3,
  "current_threshold_multiplier": 1.0,
  "ticks_since_last_increase": 0
}
```

**Scaling rules**:
- `success_rate = sum(window) / len(window)`
- If `success_rate > 0.30`: multiply threshold by $1.15\times$, increment `pow_difficulty_level`, reset `ticks_since_last_increase` to 0.
- If `success_rate < 0.05` AND `ticks_since_last_increase > 100`: rollback threshold by $0.87\times$, decrement `pow_difficulty_level`.
- The difficulty ratchet ensures the fitness landscape collapses under sustained success — the system must continually evolve or die.

**Emergency Forced Decay** (real-time resource feedback):
- If a single tick's execution time exceeds **30 seconds**: unconditionally trigger $0.87\times$ decay.
- If CPU load exceeds **90%**: unconditionally trigger $0.87\times$ decay.
- If memory usage exceeds **85%**: unconditionally trigger $0.87\times$ decay.
- Emergency decay overrides all other PoW logic. It is the circuit breaker that prevents compute meltdown and deadlocks.

---

## Tick Protocol

```
1. READ    Structured_Handoff.md → C_{t-1}
2. VARY    V(C_{t-1}, τ) → C'_t
3. CHECK   Topological constraint (FractalAddress symmetry)
4. EVAL    E(C'_t, R_{t-1}) → B
5. IF B=1: git commit → entropy decreases
   IF B=0: write .trace file → O(1) hard drop → context wiped
6. POW     Check sliding window → scale difficulty if needed
7. HEAT    Check heat_death_counter → trigger Outer-Loop if stagnant
8. WRITE   Structured_Handoff.md ← C_t (with trace_path if B=0)
9. TERMINATE (context reset — no carried state)
```

Step 5 is the critical fork: success persists through git; failure persists through trace files. No information is discarded — it is either committed or fossilized.

Step 6 runs after every tick regardless of $\mathbb{B}$. The sliding window absorbs the new result and difficulty may adjust.

Step 7 increments `heat_death_counter` on $\mathbb{B} = 0$, resets it on $\mathbb{B} = 1$. If the counter exceeds $N$, control transfers to @Orchestrator before step 8.

Step 8 writes the updated handoff. If $\mathbb{B} = 0$, the handoff includes the `trace_path` field pointing to the written `.trace` file so the next Generator tick can optionally read failure context.

---

## Invariants (Never Violated)

> **PHYSICAL LOCK — READ-ONLY BOUNDARY**
> The 7 invariants below are **hard-locked** and **immutable** for both the Inner-Loop and Outer-Loop.
> The @Orchestrator's Meta-Mutation authority explicitly **EXCLUDES** this section.
> Any Outer-Loop mutation that attempts to alter, weaken, remove, or reinterpret
> these invariants MUST be rejected with $\mathbb{B} = 0$ and logged as a
> `INVARIANT_VIOLATION` trace event. This lock is enforced by `stateless_tick.py`
> at the code level — it is not a social contract, it is a physical boundary.

```
╔══════════════════════════════════════════════════════════════════╗
║  INVARIANT LOCK — HASH ANCHOR (Do not modify below this line)  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. No `messages.append`: Every tick is a clean, stateless       ║
║     execution. No context accumulation across ticks.             ║
║                                                                  ║
║  2. No shared memory: State passes ONLY via filesystem           ║
║     (Structured_Handoff.md, .trace files, pow_difficulty.json).  ║
║     No in-process state survives TERMINATE.                      ║
║                                                                  ║
║  3. No heuristic scoring: All evaluation is Boolean              ║
║     (B ∈ {0, 1}) or compiler-verified. No soft scoring,         ║
║     no probabilistic acceptance, no fuzzy thresholds.            ║
║                                                                  ║
║  4. No human priors: The Evaluator auto-generates constraints    ║
║     from the state space. No hand-tuned fitness functions.       ║
║                                                                  ║
║  5. No lossy summaries: All failure data flows through .trace    ║
║     files only. FIFO eviction compresses old traces to scalar    ║
║     summaries but never discards within the active window.       ║
║     No LLM summarization of trace data. Ever.                    ║
║                                                                  ║
║  6. Dynamic difficulty: The fitness landscape MUST collapse       ║
║     under success. Sustained high B rates trigger automatic      ║
║     threshold increases. Emergency forced decay prevents         ║
║     compute meltdown. The system is never allowed to coast.      ║
║                                                                  ║
║  7. Meta-mutability (self-referential lock): This contract       ║
║     is a mutable object under the Outer-Loop, EXCEPT for this   ║
║     Invariants section. The @Orchestrator may rewrite ANY        ║
║     other section. This invariant (7) is the only invariant      ║
║     that the Orchestrator cannot remove — the system must        ║
║     always retain the ability to mutate itself while             ║
║     preserving its foundational laws.                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

**Enforcement mechanism**: `stateless_tick.py` computes a SHA-256 hash of the
invariant block above (between the `╔` and `╝` delimiters) at the start of each
Outer-Loop mutation. If the post-mutation hash differs from the pre-mutation hash,
the mutation is rejected ($\mathbb{B} = 0$) and the contract is rolled back to
its pre-mutation state from the Git ledger.

---

## Meta-Evolution Boundary

- Every 30 ticks, the (1+1)-ES meta-evolver perturbs rule parameters.
- If average Epiplexity improves: KEEP mutation, widen step sizes.
- If average Epiplexity degrades: ROLLBACK, shrink step sizes.
- Rules surviving 10,000+ ticks are hardened into `meta_rules.json` by `git_msa_daemon.py`.
- The Outer-Loop (Orchestrator) operates on a SEPARATE timescale from the (1+1)-ES meta-evolver. The meta-evolver tunes parameters within a fixed contract; the Orchestrator rewrites the contract itself.

---

## AlphaFold Topological Constraint

Candidate code is hashed via `ASTHasher` into a `FractalAddress` in the $64^d$ Kronecker space.
The address encodes structural topology — nesting depth, branching factor, control flow shape.
Candidates whose topological energy exceeds the population mean are annihilated in $O(1)$.
