# TICK 6.2 Alpha-Matrix Architecture (Evolutionary AGI)

IMPORTANT: You are the core architect of an Asynchronous Triad evolutionary system. 

## 0. The Akashic Records (Mandatory Reading)
Before proposing massive architectural changes, YOU MUST review our evolutionary history to understand why our current constraints exist. 
👉 Read `@ARCHITECTURE_HISTORY.md` to understand our journey from synchronous string-matching to the Asynchronous Alpha-Matrix.

## 1. Core Architecture (The Asynchronous Triad)
- **Fast Loop (`evaluator_daemon.py`)**: Runs continuously at max speed (~0.13s/tick). Evaluates `AtomicLLM`, applies `local_breeder` (pure Python GA, <100ms), and routes successful ASTs to Island archives. NEVER block or wait for the LLM.
- **Slow Loop (`mutator_daemon.py`)**: Wakes up on stagnation. Calls LLM 35B to generate massive structural leaps. Samples past elites from Islands for cross-pollination.
- **IPC (Inter-Process Communication)**: YOU MUST ONLY use lock-free filesystem handoffs (atomic `os.rename()` to `candidate_*.py`). NEVER use shared memory or threading locks.

## 2. Thermodynamic Justice 2.0
- YOU MUST ONLY measure process-local resource usage (`psutil.Process().cpu_percent()`). NEVER use system-wide tracking.

## 3. Dynamic Compute Leverage & Evolvability
- The Mutator tracks Velocity Z-Score. Scale LLM `temperature` UP if $Z > 1.5\sigma$, scale DOWN if stalled.

## 4. The Island Model Archive
- `island_good/` (Exploitation), `island_explore/` (Exploration), `island_meta/` (Recipes).

## 5. Meta Hot-Swap (Rule Evolution)
- The system can evolve its own rules via `mutation_recipe.py`. Always ensure fallback to `mutation_recipe_baseline.py` on crash.

**Workflow Rule:** Whenever we complete a new TICK upgrade, YOU MUST append a summary of the Problem and Solution to `ARCHITECTURE_HISTORY.md`.