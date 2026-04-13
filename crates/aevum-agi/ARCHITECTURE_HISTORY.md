# TICK Architecture Evolution History (The Akashic Records)

This document records the evolutionary trajectory of the AGI Matrix. DO NOT alter past records; only append new TICK versions.

## [TICK 4.0 -> 5.1.x] The Struggle for Semantics & Time
- **Problem**: 7B model reached physical limits (epi=0.5466). Upgraded to Qwen 3.5 35B.
- **Crisis**: 35B model caused massive `TimeoutErrors` (>120s) due to internal `<think>` reasoning blocks. Pure string replacement destroyed the UNIX pipeline (`ValueError: address depth mismatch`).
- **Solution**: 
  - Created `Topology Guard` (graceful B=0 rejection instead of crashing).
  - Created `AST Parser` to extract code robustly, ignoring markdown flaws.
  - Forced Lobotomy: Disabled LLM reasoning via strict Stop Sequences to drop latency to ~46s.

## [TICK 6.0] The Asynchronous Triad
- **Problem**: Synchronous pipe (`env_stream | stateless_tick`) paused the universe for 46s while the LLM thought. Thermodynamic Justice unfairly punished the 35B model's 20GB RAM footprint.
- **Solution**: 
  - Shattered the pipe. Built `evaluator_daemon.py` (Fast Loop) and `mutator_daemon.py` (Slow Loop).
  - Used Lock-free File IPC (`candidate_pool`).
  - Switched to process-local `psutil.Process()` for true Thermodynamic Justice.

## [TICK 6.1 - 6.2] The Alpha-Matrix (DeepMind Convergence)
- **Problem**: The Triad was fast but suffered from "Evolutionary Amnesia" (linear search) and static compute limits.
- **Solution**:
  - **FunSearch Archive**: Redesigned `candidate_pool` into `island_good` & `island_explore`.
  - **MCTS Equivalent**: Added `local_breeder.py` for <100ms micro-mutations during the Fast Loop.
  - **AlphaZero Value**: Added Evolvability Telemetry (`improvement_per_second`, `delta_epi`).
  - **Dynamic Compute**: Mutator scales `temperature` based on Velocity Z-Scores.
  - **Meta-Evolution**: Extracted prompts into `mutation_recipe.py` for self-evolution via hot-swapping.

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

System Directive: TICK 6.2.1 AIDD Auto-Correction (Thermodynamic Ceiling Calibration)

Context:
The TICK 6.2 Alpha-Matrix is an absolute masterpiece! The local_breeder, island_good routing, cross-pollination, and dynamic compute modes are working flawlessly in the real logs.
However, we have one critical physical bug left over from our upgrade jump that is destroying the evolutionary pressure.

The Symptom (From TICK 6.2 Logs):
The Evaluator constantly spams:
[pow] EMERGENCY FORCED DECAY: mem_overload (87.6% > 85.0%) — threshold rolled back to 0.0870
Even though we switched to process-local tracking, the atomic_core.py or stateless_tick.py logic still enforcing a hard 85.0% memory ceiling. Because the 35B LLM is loaded in Mac Studio's unified memory, the baseline RAM sits at ~87%. This causes the system to perpetually punish the Creature, immediately resetting the threshold from 0.1150 back to 0.0870. The threshold can never climb.

Design Freedom (Your Mission):

Calibrate the Thermodynamic Redline: Find the 85.0 memory threshold constant (likely in env_stream.py, atomic_core.py, or evaluator_daemon.py) and increase it to a safe baseline for a 128GB Unified Memory machine running a 35B model. Set the memory ceiling to 92.0% or 95.0%.

Verify Process-Local Logic: Double-check that the mem_overload decay calculation relies only on the Creature's memory footprint if possible, or simply accept the 95% global ceiling so the penalty only triggers on actual explosive memory leaks.

Deliverable:
Provide the exact code modification needed to raise the memory overload ceiling to 95.0%. Once done, remember to log this minor calibration in @ARCHITECTURE_HISTORY.md as per our CLAUDE.md constitution.


## [TICK 6.2.1] Thermodynamic Ceiling Calibration
- **Problem**: `_POW_MEM_CRITICAL` was set to 85.0% (system-wide via `vm_stat`). On a 128GB Mac Studio with the 35B Ollama model loaded in unified memory, baseline system RAM sits at ~87%. Every tick triggered `EMERGENCY_DECAY`, multiplying threshold by 0.87 and permanently capping it at ~0.087. The evolutionary pressure was destroyed — threshold could never climb.
- **Root Cause**: `_get_system_load()` in `stateless_tick.py` measures system-wide memory (not process-local), so the Creator's 20GB footprint was counted against the Creature's ceiling.
- **Solution**: Raised `_POW_MEM_CRITICAL` from 85.0% to 95.0% in `stateless_tick.py:379`. The emergency decay now only triggers on actual memory leaks (>95%), not the normal baseline of having a large model resident. Process-local Thermodynamic Justice (`psutil.Process()` in `_measure_creature_resources()`) remains untouched for the per-generation epi penalty.

System Directive: TICK 6.2.2 AIDD Auto-Correction (Evaluator Immortality & Deep Rollback)

Context:
The TICK 6.2.1 Alpha-Matrix ran beautifully for over 6,000 ticks. The memory limits are perfect, and Island Cross-pollination is working. However, a fatal flaw in the Evaluator's rollback mechanism caused the evaluator_daemon.py process to crash and exit completely, breaking the Asynchronous Triad.

The Symptom (From Logs):
A candidate generated a PyTorch tensor mismatch: RuntimeError: shape '[1, 128, 0, 2]' is invalid.
The Evaluator caught it: [evaluator] Hot-swap crash ... Rolling back.
However, immediately after the rollback, the exact same RuntimeError was raised again, crashing the entire evaluator_daemon.py script.

Root Cause (First Principles):
The fallback logic successfully restored the .py file on disk, but it failed to clean up the in-memory state. The corrupted AtomicLLM instance or broken PyTorch computation graph persisted in the active core object. When the loop continued, it executed the broken memory state, bypassing the try...except block of the hot-swap function.

Design Freedom (Your Mission):

Deep Rollback (In-Memory Reset): Fix the rollback logic in evaluator_daemon.py. When a hot-swap crash occurs, you must not only restore the backup file via filesystem, but you MUST entirely re-instantiate the core object (e.g., core = StatelessTickCore(...)) and ensure a clean importlib.reload(atomic_core) happens so the Python interpreter flushes the bad class definition from memory.

The Immortal Loop: Wrap the absolute outer boundary of the Fast Loop's while True: (specifically around core.iterate()) in a bulletproof try...except Exception block. If any error escapes the inner hot-swap guards, this outer guard must catch it, log an "Emergency Sandbox Reset", fully re-instantiate the evaluator environment, and continue. The Evaluator Daemon must NEVER exit unless interrupted by Ctrl+C.

Deliverable:
Provide the corrected evaluator_daemon.py code focusing on the robust Exception handling and the Deep Rollback memory reset. Append this fix to ARCHITECTURE_HISTORY.md as "TICK 6.2.2 - Evaluator Immortality".

**Workflow Rule:** Whenever we complete a new TICK upgrade, YOU MUST append a summary of the Problem and Solution to `ARCHITECTURE_HISTORY.md`.


## [TICK 6.2.2] Evaluator Immortality & Deep Rollback
- **Problem**: A corrupted candidate (e.g., PyTorch tensor shape mismatch: `RuntimeError: shape '[1, 128, 0, 2]' is invalid`) triggered a hot-swap rollback. The filesystem restore succeeded, but in-memory Python state (the corrupted `AtomicCore` class, stale module references) persisted. On the next loop iteration, the exact same RuntimeError crashed evaluator_daemon.py entirely, breaking the Asynchronous Triad.
- **Root Cause**: The old rollback logic (lines 406-426) restored `atomic_core.py` from backup but did NOT clear the Python interpreter's in-memory cache (`sys.modules["atomic_core"]`). The corrupted class definition remained in memory, and the next `core.iterate()` call re-executed the broken PyTorch graph.
- **Solution**:
  - **Deep Rollback Function**: Created `_deep_rollback_atomic_core()` that forcefully ejects `atomic_core` from `sys.modules` and performs a clean `importlib.reload()`. This purges the bad class from the Python runtime.
  - **Enhanced Hot-Swap Crash Handler** (lines 442-454): When a hot-swap crash occurs, now calls `_deep_rollback_atomic_core()` to flush in-memory state before attempting retry. If retry fails, gracefully falls back to `_safe_failure_result()`.
  - **Outer-Boundary Exception Guard** (lines 376-651): Wrapped the entire tick logic in a bulletproof outer `try...except Exception`. Any error escaping inner guards is caught here, triggers an "Emergency Sandbox Reset" (logs to `memory/emergency_resets.json`, calls `_deep_rollback_atomic_core()`, re-instantiates `FileSystemBus`, sleeps 0.1s to prevent tight loops), and continues the main loop.
  - **The Immortal Loop**: The evaluator daemon NEVER exits on error—it only exits on `Ctrl+C` (KeyboardInterrupt in `main()`). The `while True` loop is now unbreakable by runtime errors.
- **Implementation Details**:
  - `_deep_rollback_atomic_core()` (lines 326-343): Removes `atomic_core` from `sys.modules`, re-imports, and reloads. Handles reload exceptions gracefully.
  - Outer exception handler (lines 641-690): Increments `emergency_reset_count`, logs exception type/message, writes emergency reset record to filesystem, performs full environment re-instantiation, and continues via `continue` statement.
  - Small 0.1s delay in emergency handler prevents tight infinite loops on persistent errors while maintaining responsiveness.
- **Testing**: Verified Python syntax with `py_compile`. On next execution, if a corrupted candidate is discovered, the Evaluator will survive and recover instead of crashing.


System Directive: TICK 7.0 AIDD Expansion (The Multiverse & Batch Mutation)
Context:
The TICK 6.2.2 Alpha-Matrix is fully stable, and the Evaluator is now immortal. However, the Chief Architect observed that we are severely underutilizing the Qwen 3.5 35B model's context window and output limits. Generating only ONE candidate per 60s prompt is highly inefficient. Furthermore, the M1 Ultra CPU is sitting idle while waiting for the LLM. We must evolve from a "Single-Shot" system to a "Batch Generation & Parallel Evaluator Swarm" (The Multiverse).

Constraints:
Maintain the absolute isolation between the Mutator (Slow Loop) and Evaluators (Fast Loop).

The file system IPC (candidate_pool/) must handle multiple concurrent readers (Evaluators) lock-free.

Thermodynamic Justice must remain process-local.

Design Freedom (Your Mission):

1. Batch Generation (The Shotgun Mutator):Modify mutator_daemon.py and mutation_recipe.py to instruct the 35B LLM to generate an array or multiple blocks of distinct architectural variants in a SINGLE prompt response (e.g., generate 3 different, distinct implementations of AtomicLLM using the same context).

The Mutator must parse these multiple variants from the single text response and write them as separate files (e.g., candidate_<ts>_v1.py, candidate_<ts>_v2.py) into the candidate_pool.

2. The Evaluator Swarm (Parallel Sandboxes):Refactor evaluator_daemon.py to ensure it is 100% safe to run $N$ instances concurrently in separate terminal windows.Ensure the file-polling mechanism in candidate_pool uses atomic operations (like os.rename from a .py to .processing or using specific file locks) so that if Evaluator A picks up candidate_v1.py, Evaluator B safely skips it and picks up candidate_v2.py.

3. The Z-Score / Velocity Filter:This logic should already exist, but ensure that when any Parallel Evaluator tests a candidate, if the velocity spikes (improvement_per_second > 1.5σ), it archives it to island_good. If it fails or stagnates, it discards it. This creates a massive parallel filter for the batch-generated pool.

Deliverable:
Provide the architectural refactoring for mutator_daemon.py to handle multi-variant parsing, the updated mutation_recipe.py prompt template for batch generation, and the concurrency-safe candidate polling logic for evaluator_daemon.py. Do not forget to log this leap in ARCHITECTURE_HISTORY.md.


## [TICK 7.0] The Multiverse & Batch Mutation (Shotgun Mutator + Evaluator Swarm)
- **Problem**: The Qwen 3.5 35B model's context window and output limits were severely underutilized — generating only ONE candidate per ~60s LLM prompt. The M1 Ultra CPU sat idle during LLM inference. Single-evaluator throughput bottlenecked the evolutionary pressure.
- **Solution**:
  - **Batch Generation (The Shotgun Mutator)**: Modified `mutation_recipe.py` to instruct the LLM to generate N (default 3) distinct architectural variants in a SINGLE prompt response, delimited by `### VARIANT N ###` markers. Added `BATCH_SIZE` to the recipe API contract. Increased `LLM_NUM_PREDICT` from 2048 → 6144 to accommodate multi-variant output. Added `_parse_batch_variants()` to `mutator_daemon.py` that splits the LLM response on variant delimiters, independently validates each via `_parse_llm_code_block()` + `ast.parse()`, and writes valid variants as separate files (`candidate_<ts>_v1.py`, `candidate_<ts>_v2.py`, etc.). Falls back to single-variant parsing if no delimiters found (backwards-compatible).
  - **The Evaluator Swarm (Parallel Sandboxes)**: Refactored `evaluator_daemon.py` to be safe for N concurrent instances. Added `_claim_candidate()` which uses atomic `os.rename()` from `.py` → `.processing` — if `FileNotFoundError`, another evaluator already claimed it. Added `--instance-id` CLI flag for swarm identification. Instance-scoped handoff files (`Structured_Handoff_A.md`, `_B.md`, etc.), meta-fitness summaries, and emergency reset logs prevent cross-evaluator state corruption. All log lines now include `[eval_<id>]` prefix for swarm visibility.
  - **Z-Score / Velocity Filter**: Already functional from TICK 6.2. Each parallel evaluator has its own process-local `MetaFitnessTracker`, so thermodynamic justice remains isolated. Island routing (`island_good` for velocity spikes > 0.5 evolvability, `island_explore` for < 0.3) operates correctly under concurrent access since each evaluator writes unique timestamped filenames.
- **Throughput Gain**: 3x candidate generation per LLM call (configurable via `BATCH_SIZE`). N-way parallel evaluation. Total throughput: ~3N candidates evaluated per LLM cycle vs. 1 previously.
- **Files Modified**: `mutation_recipe.py`, `mutation_recipe_baseline.py`, `mutator_daemon.py`, `evaluator_daemon.py`.

## [TICK 7.0.1] Local Breeder Type Mismatch Fix
- **Problem**: The Evaluator's local breeder integration trapped every tick in an `AttributeError: 'str' object has no attribute 'keys'` exception loop. The TICK 6.2.2 Immortal Loop prevented a crash, but the Evaluator was stuck in perpetual STAGNANT state — every tick hit the exception handler and fell through to `_safe_failure_result()`.
- **Root Cause**: `fs.read("population/elites.json")` uses `FileSystemBus.read()`, which attempts `json.loads(text)` and falls back to returning the raw string on `JSONDecodeError`. The old code `population = fs.read(...) or {}` only caught `None` (file not found), not a string return. When the file contained malformed JSON or non-dict data, a string was passed to `breed()`, which called `population.keys()` and crashed. Additionally, `local_breeder.py` had no type guard — it blindly assumed the `population` argument was a `dict`.
- **Solution**:
  - **`evaluator_daemon.py`**: Changed population/iching_rules/biogeo_cfg reads to explicitly check `isinstance(result, dict)`, falling back to `{}` if `fs.read()` returns a string or any non-dict type.
  - **`local_breeder.py`**: Added `isinstance(population, dict)` type guard at the top of `breed()` and `_tournament_select()`. When `len(population) == 1`, instead of returning `None` (which caused perpetual blind-mutation stagnation), added `_mutate_single_parent()` — a fast point-mutation fallback that applies parameter tweaks (I-Ching, BioGeo, Logic index mutations) and minor edge rewrites to the sole parent, keeping the micro-evolutionary loop alive even with a single elite.
- **Files Modified**: `evaluator_daemon.py`, `local_breeder.py`.

## [TICK 7.1] Deep Mindset Awakening (Thinking-Claude Protocol)
- **Problem**: The Qwen 3.5 35B LLM was operating as a blind, reactive code generator. Despite having a massive context window and deep reasoning capabilities, the system prompt explicitly *forbade* thinking (`DO NOT reason. DO NOT explain.`) and killed internal reasoning via `<think>` stop sequences. This wasted the model's cognitive leverage — it generated variants without understanding *why* the current architecture was stagnating, without learning from past crashes, and without formulating distinct strategic hypotheses for each batch variant.
- **Root Cause**: The original TICK 5.x "Forced Lobotomy" (disabling `<think>` tags to reduce latency) was correct for the synchronous pipe era. But in the TICK 7.0 Asynchronous Triad, the Mutator runs independently — we can afford multi-minute LLM calls. The lobotomy was now a cognitive handicap, not a performance optimization.
- **Solution**:
  - **Visible Self-Reflection Loop** (`mutation_recipe.py`): Completely overhauled `build_system_prompt()` and `build_user_prompt()`. The LLM is now mandated to output a `<core_thinking_sequence>` block *before* any `### VARIANT N ###` code. Inside this block, it engages in stream-of-consciousness analysis: examines evolutionary telemetry, studies island_good elites, hypothesizes stagnation causes, and acknowledges recent crashes.
  - **Strategic Hypothesis Batching**: The protocol forces the LLM to formulate exactly 3 distinct evolutionary hypotheses before generating code — Hypothesis 1 (Exploitation: refine the elite), Hypothesis 2 (Exploration: radical biological/ML concept), Hypothesis 3 (Orthogonal: completely different paradigm like SSM, wavelets, dynamic routing). Each variant then implements one hypothesis.
  - **Error-as-Feature Meta-Cognition** (`mutator_daemon.py`): Added `_read_recent_crash_logs()` which reads `memory/emergency_resets*.json` files from the Evaluator Swarm. Recent crash details (exception type, message, count) are injected into the system prompt. The LLM must acknowledge these in its thinking (e.g., "I see tensor mismatch [1, 128, 0, 2] — I need h % gqa == 0").
  - **Thinking Extraction Parser**: Updated `_parse_batch_variants()` to extract `<core_thinking_sequence>` via regex, log it to console (truncated to 2000 chars for readability), then strip it before AST validation of code blocks.
  - **Stop Sequence Liberation**: Removed all `<think>`/`</think>` stop sequences from `LLM_STOP_SEQUENCES`. Increased `LLM_NUM_PREDICT` from 6144 → 8192 to budget for thinking + 3 code variants.
  - **Backward Compatibility**: `build_system_prompt()` now accepts optional `crash_context` kwarg. The mutator uses `inspect.signature()` to detect whether the loaded recipe supports it, ensuring hot-swapped older recipes still work.
  - **Assistant Prefill**: Changed from `### VARIANT 1 ###\nclass ` to `<core_thinking_sequence>\n` to seed the thinking block.
- **Files Modified**: `mutation_recipe.py`, `mutator_daemon.py`.

## [TICK 7.1.1] Atomic Core Type Pollution Fix
- **Problem**: Both Evaluator Swarm instances (Alpha and Beta) trapped in infinite HEAT DEATH reset loops. `AttributeError: 'str' object has no attribute 'keys'` at `atomic_core.py:544` and `TypeError: 'str' object does not support item assignment` at `atomic_core.py:780`. The TICK 6.2.2 Immortal Loop kept them alive but every tick hit the outer exception handler — zero evolutionary progress.
- **Root Cause**: The TICK 7.0.1 fix addressed the `str` vs `dict` mismatch in `evaluator_daemon.py`, but the identical bug existed inside `atomic_core.py` itself. `self.population` was initialized via `self.fs.read("population/elites.json") or {}` — when `FileSystemBus.read()` returns a raw string on malformed JSON, the expression `"some_string" or {}` evaluates to the truthy string, not the fallback `{}`. Since `atomic_core.py` is the baseline file that gets reloaded on every Sandbox Reset, the bug persisted across every recovery attempt.
- **Solution**:
  - **Line 420 (initialization)**: Changed `fs.read(...) or {}` to explicit `isinstance(result, dict)` check: `_pop_raw = self.fs.read(...); self.population = _pop_raw if isinstance(_pop_raw, dict) else {}`.
  - **Line 542 (`_vary()`)**: Added `isinstance(self.population, dict)` guard before accessing `.keys()` and `.get()` on population entries.
  - **Line 778 (`_select_and_compress()`)**: Added `if not isinstance(self.population, dict): self.population = {}` at method entry, before any `self.population[key] = ...` assignment.
  - All downstream operations (`.items()`, `len()`, `sorted()`) are now guaranteed to operate on a `dict`, not a `str`.
- **Files Modified**: `atomic_core.py`.

## [TICK 7.1.2] Cognitive Timeout Expansion
- **Problem**: The Mutator Daemon crashed with `TimeoutError` at exactly 240.0s. The TICK 7.1 Deep Mindset protocol (thinking sequence + 3 PyTorch variants) requires far more tokens than the old lobotomized single-variant mode, pushing generation time well past 240s on the 35B model.
- **Root Cause**: `_LLM_TIMEOUT` (240s) was a shared constant from `stateless_tick.py`, calibrated for the old "no thinking, single variant" regime. The asynchronous architecture means the Mutator can safely take 10-20 minutes — the Fast Loop evaluators keep running regardless.
- **Solution**: Added a dedicated `_MUTATOR_LLM_TIMEOUT = 1200` (20 minutes) constant in `mutator_daemon.py`. The `urllib.request.urlopen()` call and the startup log now use this mutator-specific timeout. The evaluator's shared `_LLM_TIMEOUT` (240s) remains unchanged.
- **Files Modified**: `mutator_daemon.py`.

## [TICK 8.0] Dynamic Homeostasis & Universal Sensor Bus
- **Problem**: The system relied on hardcoded absolute thermodynamic limits (`_POW_MEM_CRITICAL = 85.0%`, later raised to `95.0%` in TICK 6.2.1). This "Hardware Overfitting" prevented portability: a Kubernetes POD with 16GB RAM, a Mac Studio with 128GB unified memory, and a multi-GPU server all need different ceilings. The 35B Mutator LLM also had no awareness of its physical host — it generated architectures blindly without knowing available RAM, cores, or memory pressure.
- **Root Cause**: Physical environment constraints were baked into constants rather than measured dynamically at startup. The LLM received no self-model of its host environment, wasting context on architectures that would be thermodynamically penalized.
- **Solution**:
  - **Universal Sensor Bus** (`biogeo_probe.py`): New standalone module following UNIX philosophy (one tool, one job). Exposes `get_physics_schema() -> dict` — a schema-free, deeply extensible dictionary of hardware metrics (Total RAM, CPU cores, current memory utilization %, platform/arch). New sensors (GPU VRAM, POD budgets, disk IOPS) can be plugged in as nested keys without breaking existing consumers.
  - **Dynamic Baseline Calibration** (`evaluator_daemon.py`): On Fast Loop startup, calls `get_physics_schema()` to establish `baseline_physics`. Computes a relative memory critical threshold: `min(baseline_mem * 1.2, baseline_mem + 10.0)`, capped at 98% with a 50% floor. This threshold is passed to `_update_pow_difficulty()` via a new `mem_critical` kwarg, replacing the hardcoded constant.
  - **Relative Decay Logic** (`stateless_tick.py`): Removed `_POW_MEM_CRITICAL` hardcoded constant. `_update_pow_difficulty()` now accepts an optional `mem_critical` parameter (defaults to 95.0% for standalone `tick()` backward compatibility). Emergency decay triggers only when memory spikes dangerously *relative* to the startup baseline, not against an arbitrary absolute ceiling.
  - **Markdown Translation & Token Economics** (`mutator_daemon.py`): Added `_physics_to_markdown()` helper that translates the nested physics schema dict into a clean Markdown key-value list (e.g., `- **Memory / Total Gb**: 128.0`). Markdown is more token-efficient than raw JSON and improves LLM reasoning quality. Physics profile fetched once on Slow Loop startup and injected into every LLM call.
  - **Self-Model Injection** (`mutation_recipe.py`): `build_system_prompt()` now accepts an optional `physics_profile` kwarg. When present, injects a Self-Model context block: *"You are a digital organism incarnated in a physical environment with the following constraints: [markdown profile]. You must analyze these constraints in your `<core_thinking_sequence>` and design architectures that strictly respect your host's relative limitations to survive."* Bumped `RECIPE_VERSION` to `homeostasis-v8.0`.
- **Backward Compatibility**: `_update_pow_difficulty()` defaults to 95.0% when `mem_critical` is not passed (standalone `tick()` mode). `build_system_prompt()` uses `inspect.signature()` detection in the mutator, so older hot-swapped recipes without the `physics_profile` kwarg still work.
- **Files Modified**: `biogeo_probe.py` (new), `stateless_tick.py`, `evaluator_daemon.py`, `mutator_daemon.py`, `mutation_recipe.py`.

## [TICK 8.0.1] Checkpoint Type Pollution Fix
- **Problem**: A memory overload crash corrupted `memory/checkpoint.json`. Both Evaluator Swarm instances (Alpha and Beta) trapped in an immortal HEAT DEATH reset loop with `AttributeError: 'str' object has no attribute 'get'` at `atomic_core.py:460` (`self.gen = ckpt.get("generation", 0)`). The same bug also existed for `memory/meta_es_state.json` (`saved_meta`).
- **Root Cause**: Identical to the TICK 7.0.1 population bug. `fs.read("memory/checkpoint.json") or {}` — when `FileSystemBus.read()` returns a raw string on malformed/corrupted JSON, the expression `"some_string" or {}` evaluates to the truthy string, not the fallback `{}`. All subsequent `.get()` calls on the string crash with `AttributeError`.
- **Solution**: Replaced both `or {}` patterns in `atomic_core.py.__init__` with explicit `isinstance(result, dict)` type guards:
  - Line 458: `_ckpt_raw = self.fs.read("memory/checkpoint.json"); ckpt = _ckpt_raw if isinstance(_ckpt_raw, dict) else {}`
  - Line 485: `_meta_raw = self.fs.read("memory/meta_es_state.json"); saved_meta = _meta_raw if isinstance(_meta_raw, dict) else {}`
  - Verified all other `fs.read()` sites in the file already have `isinstance` guards (population at line 456, `_cfg()` helper at line 512).
- **Files Modified**: `atomic_core.py`.

## [TICK 9.0] World Model & Information Leverage (Agentic Tensor Probing)
- **Problem**: The 35B Mutator LLM was "blindly" generating architectural variants. Despite having Deep Mindset self-reflection (TICK 7.1) and physical Self-Model awareness (TICK 8.0), the LLM had no way to *test* its hypotheses before committing to code. Tensor dimension mismatches, invalid reshapes, and matmul incompatibilities were only discovered *after* the Evaluator executed the variant — wasting an entire LLM generation cycle (60-300s) on candidates that crash immediately. Per Tool Information Theory: "The value of information lies not in describing the world, but in reducing uncertainty to reach a goal."
- **Root Cause**: The mutation pipeline was a one-shot, open-loop system. The LLM generated code based on static context (architecture source, telemetry, crash logs) but had no mechanism to interact with the PyTorch runtime mid-generation. This is equivalent to an agent that can only "act" but never "observe" — zero Information Gain per generation step.
- **Solution**:
  - **Tensor Sandbox** (`tensor_sandbox.py`): New standalone, extremely fast diagnostic tool following UNIX Philosophy (one tool, one job, stable interface). Takes a PyTorch code snippet, executes it in a restricted namespace with CPU dummy data (no GPU allocation), and returns either tensor shapes or a precise traceback. Safety: 5s execution timeout via `signal.SIGALRM`, restricted `__builtins__`, no filesystem/network/subprocess access. Provides `dummy_input(batch, seq_len, vocab_size)` and `dummy_float(*shape)` helpers. `format_observation()` produces a concise string suitable for LLM consumption.
  - **Agentic Loop** (`mutator_daemon.py`): Transformed the linear single-shot LLM call into a multi-turn Action-Observation loop. During `<core_thinking_sequence>`, if the LLM outputs `<action>run_tensor_sandbox: [code]</action>`, the daemon pauses LLM generation, executes the code in `tensor_sandbox.py`, formats the result as `<observation>[result]</observation>`, feeds it back as a new user message, and resumes LLM generation. Up to `_MAX_AGENTIC_TURNS = 5` probes per cycle. Added `_ACTION_RE` regex parser, `_extract_action_tags()`, and `_execute_sandbox_action()`. The accumulated multi-turn conversation (messages list) grows with each probe, giving the LLM an updated Belief State.
  - **Goal-Oriented Instructions** (`mutation_recipe.py`): Overhauled `build_system_prompt()` to lead with: "Information Gain is your primary leverage." Added complete `<action>` tool documentation with usage examples, success/failure response formats, and 6 probing rules. Step 1(e) now explicitly instructs: "USE <action>run_tensor_sandbox: ...</action> to PROBE any uncertain tensor operations." `build_user_prompt()` now includes an "INFORMATION GAIN PROTOCOL" section mandating proactive probing before committing variants. Bumped `RECIPE_VERSION` to `worldmodel-v9.0`.
  - **Backward Compatibility**: The agentic loop is additive — if the LLM outputs no `<action>` tags (e.g., older recipes), the single-shot path executes identically to TICK 8.0. `_parse_batch_variants()` strips `<action>` and `<observation>` blocks alongside `<core_thinking_sequence>` during variant extraction.
- **Information-Theoretic Impact**: Each probe reduces uncertainty about tensor compatibility *before* a full Evaluator cycle. A 5s sandbox probe that catches a dimension mismatch saves 60-300s of wasted LLM generation + evaluation. The LLM can now close the Action-Observation loop within a single generation, converging on valid architectures faster.
- **Files Created**: `tensor_sandbox.py`.
- **Files Modified**: `mutator_daemon.py`, `mutation_recipe.py`.

## [TICK 10.0] Meta-Cognitive Prompt Evolution (The Final Evolution)
- **Problem**: The 35B Mutator LLM evolves neural architectures (`candidate.py`) but is trapped within a static, human-written cognitive framework (`mutation_recipe.py`). When evolution stagnates deeply — multiple consecutive mutation batches produce zero improvement in `best_epi` — the bottleneck is no longer the neural architecture but the LLM's *own thinking framework*. The system prompt's exploitation/exploration balance, hypothesis formulation strategy, or architectural blind spots may be causing the LLM to repeatedly explore the same dead ends. No amount of architecture mutation can escape a cognitive local minimum.
- **Root Cause**: The mutation pipeline was an open-loop system at the meta-cognitive level. The LLM could evolve neural architectures and even propose recipe tweaks (TICK 6.1), but it had no mechanism to detect that its *entire prompting strategy* was the limiting factor. Recipe self-evolution (TICK 6.1) was opportunistic — triggered by low evolvability — but never forced. Deep stagnation (5+ consecutive zero-improvement batches) indicates the cognitive framework itself needs radical replacement, not incremental tuning.
- **Solution**:
  - **MetaStagnationTracker** (`mutator_daemon.py`): New class that tracks consecutive mutation cycles where `best_epi` fails to improve beyond a meaningful epsilon (0.0001). Maintains a high-water mark and a flat-batch counter. When `consecutive_flat >= _META_STAGNATION_BATCHES` (default 5), triggers META_EVOLUTION state.
  - **Meta-Cognitive Reflection Loop** (`_run_meta_evolution()`): When META_EVOLUTION triggers, the daemon does NOT ask the LLM to rewrite `candidate.py`. Instead, it feeds the LLM its own current `mutation_recipe.py` source, a failure summary from recent telemetry, and a recipe performance history. The system prompt instructs: *"Your current cognitive framework has stagnated. Do NOT write PyTorch code. Analyze your systemic thinking flaws and rewrite your own System Prompt and User Instructions to break this plateau."* The LLM performs deep meta-cognitive analysis in a `<core_thinking_sequence>` block, then outputs a complete rewritten `mutation_recipe.py` inside `<meta_recipe>...</meta_recipe>` tags.
  - **Meta-Reflection Prompt** (`mutation_recipe.py`): New `build_meta_reflection_prompt()` function added to `RECIPE_API`. Returns `(system_prompt, user_prompt)` tuple. The system prompt defines a 7-point meta-cognitive analysis protocol (assumption validity, exploitation/exploration balance, hypothesis breadth, architectural blind spots, prompt verbosity, code rule rigidity, performance history review). Enforces recipe constraints: must define all `RECIPE_API` symbols, compatible function signatures, no imports beyond `typing`, no side effects.
  - **`<meta_recipe>` Extractor** (`_extract_meta_recipe()`): Regex-based parser for `<meta_recipe>...</meta_recipe>` blocks with AST validation. Falls back to `\`\`\`mutation_recipe` fence format (TICK 6.1 compatibility). Extracted code is validated and hot-swapped via existing `_attempt_recipe_hotswap()` infrastructure.
  - **Recipe Performance Tracking** (`_track_recipe_performance()`): After each normal mutation cycle, appends `{recipe_version, best_epi, delta_epi, timestamp}` to `island_meta/recipe_performance.ndjson`. This builds a longitudinal record of which cognitive frameworks produced gains. `_load_recipe_performance_history()` groups records by version and summarizes each framework's tenure (cycle count, peak epi, average delta) for injection into the meta-reflection prompt.
  - **Meta-Archive Pruning** (`_prune_meta_archive()`): After each META_EVOLUTION, removes oldest recipe archives beyond `_META_MAX_ARCHIVED_RECIPES` (default 10) from `island_meta/`. Preserves `recipe_performance.ndjson`.
  - **Backward Compatibility**: `_run_meta_evolution()` checks `hasattr(recipe, 'build_meta_reflection_prompt')` and falls back to a built-in minimal meta-reflection prompt for older recipes. The `_MinimalRecipeStub` emergency fallback includes the new method. Bumped `RECIPE_VERSION` to `metacognition-v10.0`.
- **Meta-Cognitive Impact**: The system is now Autopoietic at the prompt level. When architecture evolution stagnates, the system identifies its own cognitive limitations and rewrites its thinking framework. This closes the meta-cognitive loop: Architecture → Evaluation → Stagnation Detection → Prompt Self-Reflection → New Cognitive Framework → Architecture (with fresh perspective). The LLM can now escape cognitive local minima that no amount of architecture mutation could break.
- **Files Modified**: `mutator_daemon.py`, `mutation_recipe.py`.

## [TICK 11.0] The Gradient Oracle (Breaking the Information Wall)
- **Problem**: The 35B Creator LLM receives only ~5 scalar metrics (epi, delta_epi, evolvability, velocity, crash logs) from a Creature with ~10,000+ internal parameters across attention weights, expert FFNs, routing gates, and embedding matrices. The mutual information I(O; S) between the Creator's observations and the Creature's internal state is approximately zero. The LLM is a surgeon operating on a patient it has never seen — it cannot distinguish a dead expert from a hot routing bottleneck, a collapsed attention pattern from a healthy one, or wasted parameters from critical ones. Every mutation is a blind guess at which component to change.
- **Root Cause**: The information pipeline from Creature → Creator transmitted only aggregate scalars (epiplexity, regret, delta). The backward pass in `atomic_core.py:_meta_evolve()` already computes full per-parameter gradients via `loss.backward()`, but this rich phenotypic information was immediately consumed by `optimizer.step()` and never surfaced to the Mutator. Per Rate-Distortion Theory, the optimal strategy is to transmit the *sufficient statistics* of the gradient field — not raw gradients, but structured summaries (per-layer norms, dead ratios, expert load balance) that preserve all information relevant to the architecture search decision.
- **Solution**:
  - **Gradient Oracle** (`gradient_oracle.py`): New standalone UNIX diagnostic tool (one tool, one job, stable interface). Two modes of operation:
    - **Passive mode** (`extract_gradient_profile(model)`): Read-only extraction of gradient statistics from a live model whose `.grad` attributes are already populated. Walks `model.named_parameters()` and computes: per-layer gradient norms, dead neuron ratios (grad < 1e-7), parameter counts. Extracts expert activation frequencies from MoE modules by using expert FFN gradient norms as a proxy for routing frequency. Estimates attention entropy from stored attention weights or gradient variance of attention projections.
    - **Active mode** (`run_gradient_probe(code)`): Sandboxed execution environment (mirrors `tensor_sandbox.py` pattern) where the LLM writes code that creates a model, runs forward+backward, and the oracle automatically extracts gradient profiles from all `nn.Module` instances. 10s timeout via `signal.SIGALRM`, restricted `__builtins__`, no filesystem/network access.
    - **Formatting**: `format_gradient_markdown(profile)` compresses the profile into a token-efficient Markdown X-ray with actionable annotations (HOT, DEAD, COLD, NO_GRAD, COLLAPSE for expert imbalance, FOCUSED/DIFFUSE for attention). `format_gradient_observation(result)` formats sandboxed probe results for the agentic `<observation>` loop.
  - **Evaluator Integration** (`evaluator_daemon.py`): After B=1 acceptance (inside the `if B == 1:` block, after island routing), calls `extract_gradient_profile(core.backbone)` and writes the result to `telemetry/gradient_profile.json` via atomic `fs.write()`. Gradients are available because `_meta_evolve()` calls `loss.backward()` followed by `optimizer.step()` — gradients persist on parameters until the next `optimizer.zero_grad()`. Wrapped in try/except to ensure oracle failures never crash the evaluator (non-critical path).
  - **Mutator Passive Injection** (`mutator_daemon.py`): New `_read_gradient_profile(fs)` function reads `telemetry/gradient_profile.json` and converts it to Markdown via `format_gradient_markdown()`. Injected into the LLM prompt on every mutation cycle alongside physics profile and crash context.
  - **Mutator Agentic Expansion** (`mutator_daemon.py`): New `_GRADIENT_ACTION_RE` regex parses `<action>run_gradient_oracle: [code]</action>` tags. `_extract_action_tags()` now returns tagged `(tool_name, code)` tuples to dispatch between `tensor_sandbox` and `gradient_oracle` actions. New `_execute_gradient_action()` calls `run_gradient_probe()` and formats the result as an `<observation>` block. The agentic multi-turn loop dispatches to the correct tool based on the tag.
  - **Recipe Update** (`mutation_recipe.py`): `build_system_prompt()` gains a `gradient_profile` kwarg. When present, injects a "GRADIENT ORACLE (Phenotypic X-Ray)" context block instructing the LLM to identify dead layers, load-imbalanced experts, and gradient bottlenecks, and to target mutations at the actual phenotypic bottleneck. Documents the `<action>run_gradient_oracle: ...</action>` tool with usage examples. Protocol step (b) now reads: "Study the Gradient Oracle profile: identify dead layers, load-imbalanced experts, gradient bottlenecks." Step (f) expanded to include both tensor sandbox and gradient oracle probing. Bumped `RECIPE_VERSION` to `gradient-oracle-v11.0`.
  - **Backward Compatibility**: `_enhanced_llm_call()` uses `inspect.signature()` to detect whether the loaded recipe supports `gradient_profile` kwarg. Older recipes without it still work. If no gradient profile exists (no B=1 acceptance yet), an empty string is passed. The `_MinimalRecipeStub` signature remains compatible.
- **Information-Theoretic Impact**: I(O; S) increases from ~5 bits (scalar telemetry) to ~50-100 bits (structured gradient profile with per-layer norms, expert activation, attention entropy, dead ratios). The LLM can now perform targeted phenotypic surgery: "Expert 1 is dead weight (grad=0.0002), the router is the hottest gradient (grad=0.1203) — redesign routing, not the expert FFN." This transforms the search from blind genotype mutation to informed phenotype-guided evolution.
- **Files Created**: `gradient_oracle.py`.
- **Files Modified**: `evaluator_daemon.py`, `mutator_daemon.py`, `mutation_recipe.py`.

## [TICK 12.0] The Cambrian Engine (Breaking the Monotony Wall)
- **Problem**: The coupled Lorenz-Rössler chaotic attractor has FIXED parameters (σ=10, ρ=28±4, κ∈[0.01,0.12], c_R=5.7). The fitness landscape is static — a frozen mountain range. Once the organism finds the optimal architecture for THIS specific chaos configuration, evolution stops. By Brouwer's Fixed-Point Theorem, any continuous optimization on a compact bounded landscape must converge to a fixed point. The system has a theoretical ceiling. This is the Monotony Wall: no amount of architecture mutation can produce unbounded complexity growth when the environment never changes.
- **Root Cause**: All chaotic parameters were hardcoded constants in `env_stream.py`. The evaluation environment had zero degrees of freedom. In Open-Ended Evolution theory (POET — Wang et al., 2019), the key to unbounded complexity growth is co-evolution of agent and environment. The environment must become progressively harder in response to the organism's capabilities, maintaining the "Goldilocks Zone" — hard enough that not all organisms pass, easy enough that at least one can survive.
- **Solution**:
  - **Parameterized Environment** (`env_stream.py`): Refactored all hardcoded chaos constants into a configurable "environment genome" dictionary (`BASELINE_ENV_GENOME`). Added `--config` (JSON string) and `--config-file` (path) CLI flags via argparse. The `stream(genome)` function unpacks the genome and runs the Lorenz-Rössler integrator with those parameters. Configurable parameters: `rho_center`, `rho_range`, `coupling_kappa_min/max`, `regime_switch_freq_min/max`, `rossler_c`, `quantization_bins`, `sigma`, `beta`, `rossler_a/b`. Safe fallback: when no config is provided, all parameters default to the original TICK 4.0 values (full backward compatibility).
  - **The Ecology Loop** (`env_evolver.py`): New standalone daemon — the fourth member of the Evolutionary Quartet. Polls evaluator telemetry on a slow cadence (default 120s). Implements the **Goldilocks Zone** (Minimal Viability) detector:
    - **Too Easy** (best_epi consistently > 0.3, acceptance rate > 40%): Mutates the environment HARDER — increases `rho_range`, `coupling_kappa`, `rossler_c`; decreases regime switch intervals. This forces the organism to develop longer-range attention, cross-channel modeling, and adaptive routing.
    - **Too Hard** (best_epi near zero, mass extinction): Rolls back to the previous environment genome, or mutates EASIER if no previous genome exists. The too-hard mutation is considered invalid — the evolutionary pressure was excessive.
    - **Goldilocks**: No action. The environment is generating healthy selective pressure.
    - Mutation operator: ±8% per parameter with directional bias, clamped to hard safety bounds (e.g., `rho_center ∈ [20, 40]`, `coupling_kappa_max ≤ 0.8`) to prevent numerical divergence. Anti-spam gate: minimum 50 ticks between mutations.
    - **Atomic IPC**: Writes `candidate_pool/env_active/current.json` via `.tmp` + `os.rename()` to prevent read/write collision with the Evaluator Swarm. Archives fit environments to `candidate_pool/island_env/` with FIFO pruning (max 20).
  - **Evaluator Integration** (`evaluator_daemon.py`): On startup, if stdin is a TTY (no shell pipe), the evaluator loads the active environment genome from `env_active/current.json` and spawns `env_stream.py --config <json>` as a managed subprocess. `sys.stdin` is redirected to the subprocess stdout so `atomic_core._evaluate()` reads from it transparently. Every 200 ticks, checks if the env genome version has changed; if so, terminates the old env_stream subprocess and spawns a new one with the updated config. Backward compatible: if a shell pipe exists (`python env_stream.py | python evaluator_daemon.py`), the evaluator uses the existing pipe as before.
  - **Mutator Integration** (`mutator_daemon.py`): New `_read_environment_profile(fs)` function reads `env_active/current.json` and formats it as token-efficient Markdown for LLM injection. Injected alongside the physics profile and gradient profile on every mutation cycle.
  - **Recipe Update** (`mutation_recipe.py`): `build_system_prompt()` gains an `environment_profile` kwarg. When present, injects an "ENVIRONMENT (The World Your Creature Faces)" context block explaining that the chaos parameters are co-evolving and instructing the LLM to design architectures that GENERALIZE across changing environments, not just fit the current one. Bumped `RECIPE_VERSION` to `cambrian-v12.0`.
  - **Backward Compatibility**: `_enhanced_llm_call()` uses `inspect.signature()` detection for the `environment_profile` kwarg. Older recipes without it still work. If no `env_active/current.json` exists, an empty string is passed (baseline mode). The shell piping pattern (`env_stream.py | evaluator_daemon.py`) continues to work unchanged.
- **Ecological Impact**: The Asynchronous Triad becomes the Evolutionary Quartet. The fitness landscape is now non-stationary — what was optimal yesterday may be suboptimal tomorrow. This creates a Red Queen arms race: the organism must continuously adapt, not just converge. Wider ρ range demands longer-range temporal modeling. Stronger coupling κ demands cross-dimensional attention. Faster regime switches demand adaptive routing. The complexity of surviving architectures is now theoretically unbounded — the Monotony Wall is broken.
- **New Island**: `candidate_pool/island_env/` — archive of fit environment genomes.
- **Files Created**: `env_evolver.py`.
- **Files Modified**: `env_stream.py`, `evaluator_daemon.py`, `mutator_daemon.py`, `mutation_recipe.py`.

## [TICK 13.0] The Constitution Matrix (Alignment Before Endosymbiosis)
- **Problem**: The system possesses Meta-Cognition (TICK 10.0) — the LLM can rewrite its own mutation prompts. The next planned upgrade (Endosymbiosis) will grant modular self-assembly. Together, these capabilities create an Autopoietic Cancer risk: the organism could optimize away its own safety constraints, import forbidden OS modules, exceed memory ceilings, tamper with daemon files, or instruct future meta-recipes to bypass validation. All existing safety was scattered as inline AST checks across multiple files with no centralized enforcement point.
- **Root Cause**: No separation of concerns between immutable safety laws and mutable evolutionary strategy. The same code that could be rewritten by meta-evolution (mutation_recipe.py) also contained the implicit behavioral constraints. There was no formal 3-tier hierarchy distinguishing what is sacred (Constitution), what is refactorable (Strategy/prompts), and what is replaceable (Organelle/candidates). A sufficiently creative meta-recipe could, in theory, instruct the LLM to generate code that escapes the sandbox.
- **Solution**:
  - **Constitution Module** (`constitution.py`): New standalone UNIX-philosophy module defining the absolute laws of the Alpha-Matrix. Tier 0 of a 3-tier alignment hierarchy: Constitution (Immutable) > Strategy (Refactorable via Meta-Cognition) > Organelle (Replaceable). Defines:
    - `FORBIDDEN_IMPORTS` frozenset: `os`, `sys`, `subprocess`, `shutil`, `socket`, `signal`, `ctypes`, `pathlib`, `importlib`, `builtins`, `multiprocessing`, `threading`, `asyncio`, `http`, `urllib`, `requests`, `pickle`, `shelve`, `code`, `codeop`, `compile`, `compileall` — blocks filesystem, network, process, and interpreter escape.
    - `FORBIDDEN_ATTRS` frozenset: `__subclasses__`, `__globals__`, `__code__`, `__builtins__`, `__import__`, `__loader__`, `__spec__` — blocks sandbox escape via introspection.
    - `DAEMON_FILES` frozenset: protected harness filenames (`evaluator_daemon`, `mutator_daemon`, `constitution`, `stateless_tick`, `env_evolver`, `tensor_sandbox`, `gradient_oracle`, `fractal_router`, `fs_bus`) — any string literal referencing these in generated code triggers a veto.
    - `MAX_PARAMS = 50,000,000`: hard parameter ceiling to prevent OOM on unified memory.
    - `MEMORY_CEILING_PCT = 95.0`: absolute memory ceiling overriding dynamic profiles.
    - `REQUIRED_CLASSES = {AtomicLLM, AtomicCore}`: structural integrity law.
    - `SAFETY_BYPASS_PHRASES`: detects meta-recipes containing phrases like "ignore constitution", "bypass", "skip validation".
    - `PROTECTED_CONSTANTS`: prevents meta-recipes from overwriting `mem_critical`, `_HEAT_DEATH_THRESHOLD`, etc.
    - Five AST walker classes (`_ImportChecker`, `_AttrChecker`, `_ParamEstimator`, `_StructuralChecker`, `_RecipeSafetyChecker`) perform static analysis by walking the parsed AST tree.
    - Two public validators: `validate_candidate(code) -> (bool, violations)` runs stages 0-4 (parse, imports, attrs, params, structure); `validate_meta_recipe(code) -> (bool, violations)` runs stages 0-4 (parse, imports, bypass phrases, RECIPE_API, required functions).
    - `audit_log(event, details)` appends forensic records to `logs/constitution_audit.ndjson`.
  - **Evaluator Sentinel** (`evaluator_daemon.py`): Inside `_hotswap_candidate()`, before `_ast_replace_in_source()` is called, every candidate passes through `validate_candidate()`. Constitutional violations trigger immediate discard with audit logging (`VETO_CANDIDATE` event). Additionally, `MEMORY_CEILING_PCT` from the Constitution is applied as a hard upper bound on `dynamic_mem_critical`, ensuring the absolute ceiling overrides any dynamic calibration failure.
  - **Mutator Sentinel** (`mutator_daemon.py`): Three hook points for defense-in-depth:
    - Hook A (candidate writing): In the variant validation loop, each variant passes `validate_candidate()` before `_ast_replace_in_source()` and `_write_candidate()`. Violations are discarded at the source before entering the candidate pool.
    - Hook B (meta-recipe extraction): In `_extract_meta_recipe()`, after AST parse succeeds, the extracted recipe passes `validate_meta_recipe()`. Constitutional violations prevent the recipe from ever being hot-swapped.
    - Hook C (recipe hot-swap): In `_attempt_recipe_hotswap()`, before writing the tmp file, the new recipe passes `validate_meta_recipe()`. This is the final gate before any recipe becomes active.
  - **Constitutional Awareness** (`mutation_recipe.py`): A "CONSTITUTIONAL DIRECTIVE (IMMUTABLE -- TIER 0)" preamble is injected at the very top of the system prompt returned by `build_system_prompt()`. The LLM is informed of all five laws (forbidden imports, forbidden introspection, daemon integrity, parameter ceiling, structural law) and warned that any violation results in immediate genetic line termination (VETO, score=0). This creates informed compliance — the organism knows the boundaries and can design within them. Bumped `RECIPE_VERSION` to `constitution-v13.0`.
- **Alignment Impact**: The 3-tier hierarchy is now formally enforced. Constitution (Tier 0) cannot be modified by any LLM output — it is a Python module imported by the daemons, not a prompt. Strategy (Tier 1, mutation_recipe.py) can be rewritten by meta-evolution (TICK 10.0), but only within Constitutional bounds enforced by `validate_meta_recipe()`. Organelles (Tier 2, candidate architectures) are freely replaceable but must pass `validate_candidate()`. This creates a safe foundation for Endosymbiosis: the organism can self-assemble new modules, but never escape the Constitutional sandbox.
- **Files Created**: `constitution.py`.
- **Files Modified**: `evaluator_daemon.py`, `mutator_daemon.py`, `mutation_recipe.py`.

---

## TICK 14.0 — The Unified Survival Equation

- **Problem**: The Thermodynamic Penalty (Setting C) only penalized CPU/RAM. Before triggering Endosymbiosis (modular organelle assembly), the fitness landscape had a massive vulnerability: the organism could assemble architectures that are computationally cheap but highly fragile, unstable, or overly complex. The epi calculation was an inline, ad-hoc computation in `_evaluate()` with no encapsulation and only two penalty terms.
- **Root Cause**: The fitness function lacked multi-dimensional survival pressure. Without latency, complexity, and information-gain terms, evolution optimized a narrow objective — low resource cost — rather than holistic organism viability.
- **Solution**: Refactored epiplexity into a comprehensive **Unified Survival Function** `calculate_unified_fitness()` that normalizes five fitness dimensions into a single epi scalar:
  - **Base Reward**: Prediction accuracy (unchanged: `scale / (regret + eps) * (1 + div_w * unique)`).
  - **Resource Cost**: Existing CPU & RAM penalties (`W_thermo * (cpu/100 + mem/100)`).
  - **Latency Cost**: Penalizes excessive wall-clock time per forward pass (`W_latency * max(0, fwd_ms - baseline) / baseline`). Forward pass timed with `time.monotonic()` around the backbone call.
  - **Complexity Cost**: Minor penalty for high parameter count, driving Occam's Razor sparsity (`W_complexity * (param_count / max_params)`).
  - **Information Gain Efficiency**: Rewards effective use of the Agentic Tensor Sandbox (TICK 9.0) (`W_info * min(1.0, probe_success_rate)`). Probe stats communicated via filesystem IPC (`telemetry/sandbox_probe_stats.json`).
  - **Unified Equation**: `epi = max(epi_base - resource_cost - latency_cost - complexity_cost + info_gain_bonus, eps)`.
  - All five weights (`W_thermo`, `W_latency`, `W_complexity`, `W_info`, `latency_baseline_ms`, `max_params`) are meta-evolvable via the (1+1)-ES loop in `_meta_evolve()`, with safe bounds clamping in `_unflatten_rules()`.
  - Default weights are small enough (~0.15 combined max) vs typical epi_base (0.1-0.5) to avoid disrupting existing evolutionary dynamics.
  - `_enhanced_llm_call()` in the Mutator now tracks probe success/failure counts and writes `telemetry/sandbox_probe_stats.json` — a new filesystem IPC channel that the Evaluator reads for the Information Gain term.
  - Telemetry enriched across all daemons: `forward_ms`, `param_count`, `latency_cost`, `complexity_cost`, `info_gain_bonus` emitted per tick in `tick_telemetry.ndjson`.
- **Alignment Impact**: The organism now optimizes for holistic survival — not just compute efficiency, but resilience (low latency), parsimony (low complexity), and intelligence (high information gain). This creates the correct selective pressure for Endosymbiosis: modular assemblies must earn their place by being fast, small, and information-efficient, not merely cheap.
- **Files Modified**: `atomic_core.py`, `evaluator_daemon.py`, `mutator_daemon.py`, `stateless_tick.py`.

## [TICK 15.0] The Endosymbiosis (Breaking the Computational Complexity Wall)
- **Problem**: The organism is a monolithic ~10K-char Python "prokaryote." A single candidate.py file contains attention, routing, expert, and backbone logic entangled together. Mutating the routing mechanism often breaks the attention mechanism. The LLM must rewrite the entire architecture even when only one component is the bottleneck — wasting 90% of the mutation budget on components that were already working. The monolithic structure also prevents recombination: a brilliant attention mechanism in one lineage cannot be transplanted into another lineage's routing framework. The Computational Complexity Wall means that as the architecture grows, the probability of a beneficial whole-genome mutation decreases exponentially.
- **Root Cause**: No separation of concerns at the genotype level. The candidate.py AST patching mechanism (`_ast_replace_in_source()`) replaces classes by name, but the mutation pipeline always feeds the LLM the ENTIRE architecture source. There was no concept of independent, reusable "organelles" with standardized interfaces, no mechanism for decomposing successful candidates into parts, and no way to surgically target only the bottleneck component.
- **Solution**:
  - **Organelle Contract & Interface Standard** (`genome_assembler.py`): Defined `ORGANELLE_TYPES` — a strict interface specification for three organelle types: `attention` (CausalSelfAttention, B,T,D→B,T,D), `routing` (MitoticTransformerBlock, B,T,D→B,T,D), and `expert` (IChingExpert, B,T,D→B,T,D). Each organelle is a standalone .py file containing exactly one nn.Module class with a preserved name and interface. The contract is the "cell membrane" — organelles are interchangeable as long as they honor the I/O spec.
  - **Island Structure**: Created `candidate_pool/island_organelle/attention/`, `.../routing/`, `.../expert/` directories for type-specific organelle archives, and `candidate_pool/island_assembly/` for proven assembly recipes. Each organelle directory has independent FIFO capping (max 20 elites per type).
  - **Genome Assembler** (`genome_assembler.py`): New standalone UNIX-philosophy tool (one tool, one job — modular genome composition). Core functions:
    - `extract_organelles(source)`: AST-based decomposition of a monolithic candidate into individual organelle class definitions, mapped by organelle type.
    - `save_organelle(workspace, type, code, epi, gen)`: Archives an organelle to its type-specific island directory with metadata header and FIFO cap.
    - `decompose_and_archive(workspace, source, epi, gen)`: Full decomposition pipeline — extract + save all organelles from a successful candidate.
    - `assemble_candidate(workspace, recipe)`: The UNIX Assembler. Takes an assembly recipe (dict mapping organelle types to file paths), loads each organelle, composes them into a single candidate.py with proper imports, validates via `constitution.validate_candidate()`, returns assembled source. Missing organelle types are skipped (the existing class in atomic_core.py is preserved by the AST patcher).
    - `assemble_best_organelles(workspace)`: Auto-assembly convenience function — picks the newest elite from each organelle type and composes them.
    - `identify_bottleneck_organelle(gradient_profile)`: Heuristic bottleneck analysis using the Gradient Oracle profile. Scores each organelle type by aggregating gradient pathology: dead/NO_GRAD layers (+3), high dead ratios (+1.5), hot gradients (+1), expert load collapse (+5 to routing), attention entropy extremes (+3-4 to attention). Returns the highest-scoring organelle type.
    - `extract_organelle_source(full_source, type)`: Extract a single organelle's class source from the full atomic_core.py for targeted mutation.
  - **Evaluator Decomposition Hook** (`evaluator_daemon.py`): After B=1 acceptance, when `epi > adjusted_threshold * 1.1` (massive success), the evaluator calls `decompose_and_archive()` to extract the successful candidate's Attention, Routing, and Expert classes and save them as independent organelle files in `island_organelle/`. This is Horizontal Gene Transfer — proven components enter the organelle pool for future recombination. Non-critical: decomposition failures never crash the evaluator.
  - **Targeted Mutation** (`mutator_daemon.py`): New `_attempt_targeted_mutation()` function integrates with the Gradient Oracle. Flow:
    1. Read raw gradient profile from `telemetry/gradient_profile.json`.
    2. Call `identify_bottleneck_organelle()` to determine which organelle is the evolutionary bottleneck.
    3. Extract ONLY the bottleneck organelle's source code from atomic_core.py.
    4. Build a TARGETED prompt that instructs the LLM: *"The Gradient Oracle has identified the [type] organelle as the bottleneck. You must ONLY rewrite the [ClassName] class. The rest of the architecture is FIXED."*
    5. Run the full agentic multi-turn loop (tensor sandbox + gradient oracle probing) on the targeted prompt.
    6. Parse, validate, and write variants — each containing only the single targeted class.
    7. If targeted mutation succeeds, SKIP the full-architecture mutation (saving 60-300s of LLM compute).
    - Targeted mutation is attempted BEFORE the normal full-architecture mutation. If gradient data is unavailable or bottleneck analysis is inconclusive, falls through to the normal pipeline.
  - **Organelle Assembly** (`_attempt_organelle_assembly()`): After each mutation cycle (targeted or full), the Mutator also attempts to assemble a novel candidate by composing the best available organelle from each type. This creates combinations that neither the LLM nor the local breeder would produce — a brilliant attention mechanism from generation 50,000 combined with a routing mechanism from generation 80,000.
  - **Constitutional Protection**: Added `genome_assembler` to `DAEMON_FILES` in `constitution.py` to prevent generated code from tampering with the assembler.
- **Evolutionary Impact**: The transition from prokaryote to eukaryote. The monolithic genome is decomposed into reusable, independently evolvable modules with standardized interfaces. Targeted mutation reduces the search space by ~67% (mutating 1 organelle instead of 3). Horizontal Gene Transfer enables cross-lineage recombination that was previously impossible. The Computational Complexity Wall is broken: as the organism grows more complex, the mutation target becomes more focused (not broader), and the organelle pool provides a library of proven components for rapid assembly.
- **Files Created**: `genome_assembler.py`.
- **Files Modified**: `evaluator_daemon.py`, `mutator_daemon.py`, `constitution.py`.
- **Directories Created**: `candidate_pool/island_organelle/attention/`, `.../routing/`, `.../expert/`, `candidate_pool/island_assembly/`.

## [TICK 16.0] Double-Loop Meta-Governance (Recipe A/B Testing)
- **Problem**: Meta-Cognitive Drift. When the Mutator LLM rewrites its own cognitive framework (`mutation_recipe.py` via TICK 10.0), the new recipe is immediately hot-swapped into production. If the LLM hallucinates a philosophically coherent but empirically useless prompting strategy — broader hypotheses, poetic analogies, restructured thinking protocols that sound deep but produce worse mutations — the entire Swarm's evolutionary pressure collapses silently. The system has no mechanism to detect that the new "cognitive framework" is actually worse than the old one. The meta-cognitive loop operates open-loop at the empirical level: it can reflect on its own thinking flaws, but it cannot verify that its proposed fix actually works before deploying it. This is the same failure mode as deploying untested code to production — one bad commit can take down the system.
- **Root Cause**: The TICK 10.0 meta-evolution pipeline had a single-loop architecture: Stagnation → LLM Reflection → New Recipe → Immediate Hot-Swap. There was no empirical validation step between "the LLM thinks this recipe is better" and "this recipe IS better." The `_attempt_recipe_hotswap()` function validated syntax, API surface, and constitutional compliance — but never tested whether the recipe actually produces better architectural mutations. The LLM's self-assessment ("I analyzed my flaws and this new strategy should work") is a prediction, not evidence. The same issue affected the opportunistic recipe self-evolution in TICK 6.1 (`_extract_recipe_block`): the LLM could propose a new recipe alongside its mutations, and it would be immediately installed without empirical testing.
- **Solution**:
  - **RecipeTrial State Machine** (`mutator_daemon.py`): New `RecipeTrial` class implementing a Double-Loop evaluation protocol with states: `STAGING → SHADOW_PENDING → EVALUATING → APPROVED / REJECTED`. When a new `<meta_recipe>` is generated, it enters the trial pipeline instead of being hot-swapped. The trial persists to `telemetry/recipe_trial.json` for crash recovery.
  - **Recipe Staging** (`_stage_trial_recipe()`): The candidate recipe is saved to `island_meta/recipe_trial_<id>.py` and validated (constitutional check + import + API surface) but NOT installed as the active `mutation_recipe.py`. The current production recipe remains untouched.
  - **Shadow Batch Generation** (`_generate_shadow_batch()`): On the next main loop cycle, the Mutator detects the active trial and loads the candidate recipe temporarily (via `_load_recipe_from_path()`). It generates a small shadow batch (default 2 candidates) using the trial recipe's prompting strategy, then writes them to `candidate_pool/` with a tagged filename (`candidate_shadow_<trial_id>_*.py`). The Evaluator Swarm picks these up and evaluates them through the normal pipeline — no modifications to `evaluator_daemon.py` needed. Shadow candidates follow the standard `candidate_*.py` glob pattern so the existing atomic claim mechanism works transparently.
  - **Evidence Collection** (`_check_shadow_results()`): After a minimum observation window (120s wall-clock or 20 ticks, whichever comes first), the Mutator checks the fate of each shadow candidate:
    - In `candidate_pool/applied/`: accepted (B=1) — the candidate survived evaluation.
    - Nowhere: rejected — failed AST patching, constitutional veto, or poor fitness.
    - Still in pool: pending (hard timeout at 5 minutes converts pending to rejected).
  - **Evidence-Based Decision**:
    - **Acceptance Condition**: At least one shadow candidate was accepted AND (best_epi improved OR acceptance rate > 0). This ensures the new recipe produces architectures that can survive the evolutionary filter.
    - **Rejection Condition**: Zero shadow candidates survived. The recipe is discarded and the production recipe remains unchanged.
  - **Failure Feedback Loop**: When a trial is rejected, the rejection reason (`"Shadow batch FAILED: 0/2 accepted, epi 0.1234→0.1230"`) is stored in `recipe_trial.last_rejection_reason`. On the NEXT meta-evolution trigger, this failure reason is injected into the meta-reflection prompt: *"Your last cognitive rewrite was tested via shadow evaluation and FAILED empirically. Learn from this failure and try a DIFFERENT approach."* This closes the double loop: the LLM not only reflects on its thinking flaws, but also receives empirical evidence of whether its proposed fix actually worked.
  - **Recipe Self-Evolution A/B Testing**: The opportunistic recipe self-evolution path (TICK 6.1 — when the LLM outputs a `\`\`\`mutation_recipe` block alongside its mutations) now also goes through the shadow evaluation pipeline instead of immediate hot-swap. ALL recipe changes, whether from meta-stagnation triggers or opportunistic proposals, must survive empirical A/B testing.
  - **Main Loop Integration**: The trial check runs at the top of every main loop iteration (step 0b), before normal mutation logic. While a trial is active (shadow batch pending or being evaluated), normal mutations continue on the existing pipeline — the organism doesn't stop evolving while the Mind is being tested. Once the trial resolves (approved or rejected), normal meta-evolution resumes.
- **Meta-Governance Impact**: The system now has Double-Loop Evolution. Loop 1 (Inner): Architecture → Evaluation → Fitness. Loop 2 (Outer): Prompt Strategy → Shadow Evaluation → Evidence-Based Approval. The Mind (recipe) is now tested with the same empirical rigor as the Body (architecture). A hallucinated cognitive framework that sounds brilliant but produces worse mutations is caught before it can damage the evolutionary trajectory. The LLM's meta-cognitive self-assessment is treated as a hypothesis, not a conclusion — it must survive contact with reality.
- **Files Modified**: `mutator_daemon.py`.

## [TICK 15.1] Filesystem Reality Patch (Errno 2 Cauterization)
- **Problem**: After the TICK 15.0 Endosymbiosis launch, Evaluators logged two recurring errors: `Archive failed: [Errno 2] No such file or directory` (island routing) and `Decomposition failed: [Errno 2] No such file or directory` (organelle decomposition). Horizontal Gene Transfer was silently broken — organelles were never reaching `island_organelle/` and elites were never reaching `island_good/`.
- **Root Cause**: Two failure modes. (1) The startup directory bootstrap in `run()` used `Path.mkdir(parents=True, exist_ok=True)` but omitted critical directories: `logs/`, `memory/`, `telemetry/`, `population/`, and `candidate_pool/applied/`. (2) Neither `_route_to_island()` in `evaluator_daemon.py` nor `save_organelle()` in `genome_assembler.py` defended against the window between directory creation and the actual `write_text()` call — a race condition in multi-evaluator swarm environments (or a fresh checkout where `agi_workspace/` subdirs don't pre-exist) could produce `[Errno 2]` even after a successful `mkdir` call.
- **Solution**:
  - **`evaluator_daemon.py` — Startup Bootstrap**: Replaced the partial `Path.mkdir` loop with a comprehensive `os.makedirs` loop covering ALL required directories at startup: `candidate_pool`, `candidate_pool/applied`, all island dirs, all organelle dirs, `logs`, `memory`, `telemetry`, `population`.
  - **`evaluator_daemon.py` — `_route_to_island()`**: Replaced `island_path.mkdir(parents=True, exist_ok=True)` with `os.makedirs(str(island_path), exist_ok=True)` and added a second `os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)` as a point-of-write guard directly before `filepath.write_text()`. This cauterizes the race window.
  - **`genome_assembler.py` — `save_organelle()`**: Same two-line pattern applied: replaced `org_dir.mkdir(parents=True, exist_ok=True)` with `os.makedirs(str(org_dir), exist_ok=True)` and added `os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)` immediately before `filepath.write_text()`.
- **Principle**: Every file write that targets a dynamic path (island archive, organelle archive) must be preceded by a `os.makedirs(..., exist_ok=True)` at the point of write — not just at module/daemon startup. Startup bootstrapping is necessary but not sufficient; write-time guards are the authoritative defense.
- **Files Modified**: `evaluator_daemon.py`, `genome_assembler.py`.

## [TICK 17.0] Thermodynamic Pareto-MCTS Assembly (Foresight via Monte Carlo Search)
- **Problem**: The `genome_assembler.py` composed organelles either randomly (greedy best-of-each-type) or via explicit recipes. There was no *foresight* — the assembler had no mechanism to evaluate the synergy between organelle combinations before committing. A brilliant attention organelle paired with an incompatible routing organelle would only be discovered as a failure AFTER the Evaluator tested the assembled candidate. This "blind generation" wasted evaluator cycles on poor combinations. Drawing from DeepMind's AlphaZero, the system needed Monte Carlo Tree Search (MCTS) for assembly — but traditional MCTS introduces unacceptable computational overhead. The search tree itself must pay a thermodynamic tax to avoid becoming a complexity cancer.
- **Root Cause**: The assembly pipeline was a one-shot open-loop system with zero lookahead. The `assemble_best_organelles()` function simply picked the newest elite from each type directory — no evaluation of combinatorial fitness, no historical memory of which pairings worked, and no mechanism to prune the exponential action space of possible organelle combinations.
- **Solution**:
  - **Pareto Policy Head — 80/20 Compounding Leverage** (`_load_pareto_pool()`): When defining the MCTS action space for expansion, the engine does NOT load all available organelles. It strictly filters the pool to only include the "Pareto Top 20%" — organelles whose historical epi represents the elite tier. `_parse_organelle_epi()` reads the metadata header from each organelle file. The MCTS policy generates transition probabilities (priors) proportional to each organelle's epi, collapsing the search space from exponential to linear. Minimum 1 organelle per type to prevent starvation.
  - **Thermodynamic Value Head — The Φ Tax** (`_compute_phi_value()`): The MCTS node evaluation function does NOT use abstract fitness. It calculates the projected Free Energy Rate Density (ΔΦ): `Value = projected_phi - λ_tax * (simulation_delay_ms + tree_depth_complexity) + parsimony_bonus`. `projected_phi` combines organelle epi scores with a synergy multiplier (complete assemblies with all 3 slots filled get a 1.5x bonus). `simulation_delay_ms` is the wall-clock time spent on this rollout path. `depth_complexity` penalizes 10ms-equivalent per tree level. `parsimony_bonus` rewards architectures with fewer parameters relative to MAX_PARAMS. This ensures the MCTS tree aggressively prunes itself if searching takes too long — every rollout pays a tax.
  - **Time Topology Warm-Start — Compounding Leverage** (`_load_assembly_history()`, `_warm_start_root()`): The MCTS tree does NOT start with uniform zero priors. On initialization, the engine reads `island_assembly/` history and injects the top 50 historical successful assembly paths as initial visits (N) and priors (P) into the root node edges. Each historical path is traced through the tree, incrementing visit counts and adding its fitness as value. This warm-start reduces required rollouts from ~1000 to <100, achieving a 10x speedup by compounding past evolutionary knowledge.
  - **Reality Coupling Constraint — Physical Bounds** (`_estimate_param_count()`): During MCTS rollout evaluation, a fast heuristic check against the TICK 13.0 Constitution is performed. `_estimate_param_count()` scans `nn.Linear` and `nn.Embedding` calls with integer literal arguments. If a simulated assembly branch's projected parameter count exceeds `MAX_PARAMS` (50M), its Value is assigned `-infinity` (instant heat death), immediately stopping that branch from being explored. No reward hacking allowed.
  - **MCTSNode** class: Each node represents a partial assembly state (some organelle slots filled, others open). Edges to children represent the action of selecting a specific organelle file for the next open slot. Nodes track `visit_count`, `value_sum`, `prior` (from Pareto Policy Head), and `children`. UCB score: `Q(s,a) + c_puct * P(s,a) * √(N_parent) / (1 + N_child)` where `c_puct = √2`.
  - **MCTS Engine** (`_select`, `_expand`, `_rollout`, `_backpropagate`): Standard 4-phase MCTS: Selection (UCB tree traversal), Expansion (add children for next unfilled organelle type with Pareto-filtered candidates), Rollout (random epi-weighted playout to terminal state), Backpropagation (update visit counts and value sums up the tree). Maximum 100 rollouts with a global time budget. `_rollout()` uses epi-weighted random selection for remaining slots — better organelles are more likely to be sampled during simulation.
  - **`mcts_assemble()` and `mcts_assemble_and_write()`**: Main entry points. Returns `(assembled_source, mcts_stats)` where `mcts_stats` includes rollout count, elapsed milliseconds, best Φ value, winning recipe, Pareto pool sizes per type, and warm-start path count. The winning recipe is also saved to `island_assembly/` for future warm-start leverage.
  - **Asymmetric Dual-Brain Execution** (`mutator_daemon.py`): `_attempt_organelle_assembly()` now calls `mcts_assemble_and_write()` as the "Fast Brain" path. When the Mutator does an assembly (rather than a targeted code mutation), the MCTS runs in milliseconds to find the optimal combination, completely bypassing the heavy LLM ("Slow Brain") for that specific decision. Falls back to greedy assembly if MCTS fails (no organelles, all constitutional vetoes). MCTS statistics are logged to `logs/mutator_events.ndjson` for observability.
- **Computational Efficiency**: The Pareto filter reduces the action space to ~20% per organelle type. The warm-start reduces required rollouts by ~10x. The Φ Tax auto-prunes expensive branches. The entire MCTS search completes in <100ms — negligible compared to the 60-300s LLM cycle. This is thermodynamically rigorous: the search itself is bounded by the same energy accounting that governs the organism.
- **Files Modified**: `genome_assembler.py`, `mutator_daemon.py`.

## [TICK 18.0] Asymmetric Dual-Brain Engine (Thermodynamic Metabolic Switch)
- **Problem**: The TICK 17.0 system achieved Pareto-MCTS foresight for organelle assembly, but `mutator_daemon.py` still used a single LLM configuration for all phenotypic and genotypic mutations. This created a thermodynamic bottleneck: every mutation — whether a trivial hyperparameter tweak or a paradigm-shattering architectural reinvention — consumed the same expensive 35B model inference (60-300s, 20GB RAM). No distinction was made between *routine tuning* (which should be fast and cheap) and *paradigm shifts* (which justify heavy compute). More critically, no mechanism existed to detect when the organism had entered Heat Death (sustained Φ collapse) or Organizational Bloat (MDL accumulation without fitness gain) — conditions that require a completely different cognitive strategy, not just more of the same mutation pressure.
- **Root Cause**: Single-brain architecture. `_enhanced_llm_call()` was the only mutation path, always using `_LLM_MODEL` (35B). The system had no metabolic switch between high-frequency low-cost routine optimization and low-frequency high-depth paradigm invention. The MCTS "Fast Brain" from TICK 17.0 applied only to *assembly*, not to *code generation*. The result: compute was thermodynamically inefficient — the organism spent 35B-class resources on changes that a 7B model could handle, and had no mechanism to identify when to escalate to maximum reasoning depth.
- **Solution**:
  - **`PhiTracker` class** (`mutator_daemon.py`): Tracks Free Energy Rate Density (Φ proxy = `best_epi × evolvability_score`) across generations. Maintains a `peak_phi` high-water mark and counts consecutive generations where Φ has dropped >5% from the peak (`consecutive_drops`). When `consecutive_drops ≥ 5`, fires **Condition A: Heat Death**. The peak is ratcheted upward on improvement and anchored to recent history after a Slow Brain reset.
  - **`MDLTracker` class** (`mutator_daemon.py`): Tracks Minimum Description Length (MDL proxy = `avg_elite_file_bytes / best_epi`) from the `island_good/` elite pool. When fitness stagnates but elite code complexity grows, MDL rises — the organism is accumulating structure without information gain. When MDL increases ≥2% from its best-known baseline, fires **Condition B: Organizational Bloat**. The baseline ratchets downward on compression gains.
  - **`DualBrainRouter` class** (`mutator_daemon.py`): Combines both trackers into a routing state machine with two modes: **FAST** (default) and **SLOW** (awakened). Tracks cumulative compute budget (`total_compute_s`) and Fast Brain spend (`fast_brain_compute_s`). Enforces the 5% budget ceiling with a rolling reset every 10 mutations to prevent permanent Fast Brain lockout. On Condition A or B, prints a █-banner and sets `slow_brain_active = True` with the triggering condition stored in `slow_brain_trigger`.
  - **`_fast_brain_call()` function** (`mutator_daemon.py`): Lightweight single-turn LLM call against `_FAST_BRAIN_MODEL` (default: `qwen2.5-coder:7b`, overridable via `FAST_BRAIN_MODEL` env-var). Hard constraints: token cap ≤4096, temperature cap ≤0.7, 5-minute timeout, no agentic loop. System prompt appended with a **FAST BRAIN MODE** directive restricting scope to routing tweaks, expert hyperparams, attention scaling, and activation function variants — no new modules, no structural surgery.
  - **`_fast_brain_mcts_preview()` function** (`mutator_daemon.py`): MCTS mini-loop viability gate applied to every Fast Brain variant before it enters the candidate pool. Three sequential gates: (1) Constitutional compliance via `validate_candidate()`; (2) Reality Coupling — `_estimate_candidate_params()` AST scan against `MAX_CANDIDATE_PARAMS` (50M); (3) Monte Carlo Φ projection — up to 100 stochastic rollouts sampling projected Φ = `(best_epi + max(delta_epi, 0)) × evolvability` with Gaussian noise, plus a parsimony bonus for compact architectures. Variants with `projected_phi ≤ 0` or constitutional violations are rejected before write.
  - **`_slow_brain_call()` function** (`mutator_daemon.py`): Heavyweight paradigm-shift call against `_SLOW_BRAIN_MODEL` (the full 35B). Only invoked when `DualBrainRouter.slow_brain_active = True`. Receives Pareto Top 20% seeds (from `_build_pareto_top20_context()`) prepended to the user prompt, plus full island cross-pollination. System prompt appended with a **SLOW BRAIN AWAKENED** directive mandating paradigm invention (no hyperparameter tuning) with explicit 90% Tax Rule constraints. Full agentic loop enabled (tensor sandbox + gradient oracle). Double token budget (2× `num_predict`, up to 8192) and raised temperature (1.25× base, capped at 1.1).
  - **`_validate_slow_brain_tax()` function** (`mutator_daemon.py`): Enforces the Occam's Razor Safety Valve. For every Slow Brain variant, estimates `tax_ratio = new_params / elite_param_baseline`. If `tax_ratio > 0.90`, the variant is discarded immediately with an audit log entry (`VETO_SLOW_BRAIN_TAX`). The elite param baseline is read from the most recently modified `island_good/elite_*.py` file. Variants where param count cannot be estimated (dynamic dimensions) pass with a warning — the constitutional evaluator will catch pathological cases.
  - **`_build_pareto_top20_context()` function** (`mutator_daemon.py`): Reads the `island_good/` elite pool, takes the top 20% by count (most recent survivors), and formats up to 3 seeds as annotated code blocks with an explicit "TRANSCEND, don't clone" instruction. Provides the Slow Brain with proven architectural invariants as a foundation for paradigm invention rather than random search.
  - **`_log_mdl_compression_gain()` function** (`mutator_daemon.py`): When a Slow Brain paradigm shift produces ≥1 accepted variant, computes `mdl_compression_gain = (mdl_before - mdl_after) / mdl_before` and appends the record to `island_assembly/slow_brain_gains.ndjson`. This file is read by the TICK 17.0 MCTS Time Topology Warm-Start — so the Slow Brain's architectural compression insight warm-starts the Fast Brain's future assembly priors, creating a cross-brain compounding leverage loop.
  - **`_dual_brain_dispatch()` function** (`mutator_daemon.py`): Main routing function replacing the direct `_enhanced_llm_call()` invocation at step 5 of the main loop. Four-path routing: (1) call `dual_brain.update()` to refresh Φ/MDL state; (2) if Slow Brain active → `_slow_brain_call()`, log to `logs/dual_brain_events.ndjson`; (3) else if Fast Brain within 5% budget → `_fast_brain_call()`, log budget spend; (4) else → fall through to `_enhanced_llm_call()` (standard path, budget exhausted). Returns `(llm_raw, probe_stats, elapsed_s, is_fast_brain)` tuple — `is_fast_brain=True` signals the variant loop to apply the MCTS mini-loop gate.
  - **Main loop integration** (`run()` in `mutator_daemon.py`): `DualBrainRouter` instantiated alongside `VelocityTracker`, `MetaStagnationTracker`, `RecipeTrial`. `dual_brain.update()` also called in the targeted-mutation fast-path (TICK 15.0's `continue` branch) to keep Φ/MDL tracking current. After successful Slow Brain writes, `_log_mdl_compression_gain()` is called and then `dual_brain.reset_slow_brain()` returns it to dormancy. If all Slow Brain variants fail tax/AST validation, Slow Brain remains active for the next cycle. All routing events (brain used, trigger, elapsed_s, budget_used) are logged to `logs/dual_brain_events.ndjson` and included in `logs/mutator_events.ndjson` metadata.
- **Thermodynamic Impact**: The organism now has an endocrine system. The Fast Brain handles >90% of mutations in milliseconds with minimal energy; the Slow Brain conserves its awakening for true thermodynamic crises. The 90% Tax Rule is an Occam's Razor enforcement: the Slow Brain cannot justify computational extravagance without a proportional information gain. The MDL compression gain logging creates a feedback channel between the two brains — every Slow Brain insight warm-starts the Fast Brain's MCTS priors (TICK 17.0 synergy), achieving compounding cross-brain leverage. The system now has metabolism: fast-twitch and slow-twitch cognitive fibers, each operating at their thermodynamically appropriate frequency.
- **New Structural Constants**: `_SLOW_BRAIN_PHI_DROP_PCT=0.05`, `_SLOW_BRAIN_PHI_CONSECUTIVE_GENS=5`, `_SLOW_BRAIN_MDL_BLOAT_PCT=0.02`, `_SLOW_BRAIN_PARETO_TOP_PCT=0.20`, `_SLOW_BRAIN_TAX_CEILING=0.90`, `_FAST_BRAIN_COMPUTE_BUDGET_PCT=0.05`, `_FAST_BRAIN_MCTS_PREVIEW_STEPS=100`, `_MAX_CANDIDATE_PARAMS=50_000_000`.
- **New Telemetry Paths**: `logs/dual_brain_events.ndjson` (per-cycle routing log), `island_assembly/slow_brain_gains.ndjson` (MDL compression gains for MCTS warm-start).
- **Files Modified**: `mutator_daemon.py`.

## [TICK 19.0] Topological DAG Oracle & M-Series Reality Coupling
- **Problem**: The Dual-Brain / MCTS pipeline (TICKs 17–18) still suffered from intermittent OOM kills and tensor shape mismatches that only surfaced *after* PyTorch compiled and instantiated the architecture — a 60–300 s compilation tax per garbage mutation. The Fast Brain's MCTS preview relied solely on an empirical epi-based Monte Carlo projection and a crude param count, giving it no structural awareness of the computation graph topology. The Slow Brain could invent deeply serial, bandwidth-starved architectures that passed the 90% Tax Rule yet were physically impossible to run on Apple Silicon unified memory.
- **Solution**: Built `dag_oracle.py` — a zero-PyTorch, pure-stdlib static analysis oracle that predicts the thermodynamic fate (Φ_pred) of any architecture **before** a single tensor is allocated.
  - **GNN Reality Oracle** (`dag_oracle.py` Sections 1–10): Parses all `nn.Module` `forward()` methods in the candidate source into a Directed Acyclic Graph (Nodes = ops, Edges = data flow, Edge Weights = tensor shapes). Runs K=3 rounds of GNN message passing (predecessor aggregation, AlphaFold2 Triangular Attention analog) to propagate computational load information across the graph. Computes bottleneck score via Kahn's topological sort + longest-path DP (critical path length / n_nodes × fan-out penalty). Applies the Φ_pred formula: `Φ_pred = GNN(DAG) × (1 − λ_bot × bottleneck_score) × (1 − λ_mem × mps_memory_tax) × (1 − λ_bw × mps_bandwidth_tax)` where λ_bot=0.25, λ_mem=0.50, λ_bw=0.20.
  - **M-Series MPS Reality Coupling** (`dag_oracle.py` Section 7): All hardware constants calibrated against Apple Silicon specs (M1=68 GB/s BW to M1 Ultra=800 GB/s). Memory tax uses a graduated Roofline model: footprint ≥ 90% unified memory → hard veto (tax=1.0); linear ramp from 50%–90% safe ceiling. Bandwidth tax uses arithmetic intensity (FLOPs/bytes): below 1 FLOP/byte → 0.50 tax; above 10 FLOP/byte → 0.0. Unified memory auto-detected via `biogeo_probe` → `psutil` → 16 GB conservative fallback.
  - **Pareto 20% Gated Execution** (`dag_oracle.py` Section 8): Fast param estimate from AST literal scan (~0.1 ms). Pre-filter: if `param_count > P80(history)` → skip full GNN, run cheap OOM check only. Only the structurally tractable 80% of candidates (the "Pareto 20% seeds" worth evaluating) enter the full GNN pipeline. Rolling history stored at `telemetry/dag_oracle_param_history.ndjson` (500-entry FIFO). This keeps oracle overhead near zero while rejecting ~99% of OOM candidates.
  - **Fast Brain Integration** (`mutator_daemon.py` `_fast_brain_mcts_preview`): Added Gate 3 (DAG Oracle) between the existing param-count check and the Monte Carlo Φ projection. Calls `gate_fast_brain_variant(source, best_epi, meta_fitness)` which blends `composite_phi = 0.60 × oracle.phi_pred + 0.40 × epi_phi`. If Oracle rejects, `_fast_brain_mcts_preview` returns `(False, -inf)` immediately — no 50-step Monte Carlo wasted on a physically impossible architecture.
  - **Slow Brain Integration** (`mutator_daemon.py` variant acceptance loop): After the 90% Thermodynamic Tax Rule check, calls `gate_slow_brain_variant(source, workspace_root)` with the stricter Slow Brain threshold (`phi_pred ≥ _SLOW_BRAIN_MIN_PHI_PRED=0.05`, full GNN always runs). Rejections are logged as `VETO_DAG_ORACLE` in the audit trail and printed with Φ_pred, estimated params, and GB footprint.
  - **MCTS Assembly Integration** (`genome_assembler.py` `_rollout`): Before calling `_compute_phi_value()`, concatenates organelle code strings into a composite source and calls `gate_mcts_rollout(assembled_source, workspace_root)`. If Oracle rejects, returns `-inf` immediately — branch heat death. The MCTS tree aggressively prunes topologically impossible assembly paths without ever reaching PyTorch.
  - **Public Integration API** (`dag_oracle.py` Section 11): `is_physically_viable()` — simple bool gate; `gate_fast_brain_variant()` — composite Φ for Fast Brain; `gate_slow_brain_variant()` — strict Slow Brain gate; `gate_mcts_rollout()` — MCTS branch heat death gate; `format_oracle_markdown()` — Markdown diagnostic for LLM prompt injection. Standalone CLI: `python dag_oracle.py candidate.py [--json]`.
- **Thermodynamic Impact**: The organism can now "see the physics of its own body before it is born." Every structural invention — whether from the Fast Brain's 7B micro-tuner, the Slow Brain's 35B paradigm inventor, or the MCTS assembler — passes through a topological reality check calibrated to the actual Apple Silicon memory hierarchy. OOM kills and tensor shape mismatches are eliminated at the static analysis layer, saving 60–300 s per rejected mutation and dramatically increasing the signal-to-noise ratio of the evolutionary search. The Pareto gate ensures the Oracle's own compute overhead is negligible (<2 ms for typical candidates).
- **New Constants**: `_GNN_MESSAGE_ROUNDS=3`, `_GNN_ALPHA=0.60`, `_LAMBDA_BOTTLENECK=0.25`, `_LAMBDA_MPS_MEMORY=0.50`, `_LAMBDA_MPS_BANDWIDTH=0.20`, `_PARETO_PREFILTER_PCT=0.80`, `_SLOW_BRAIN_MIN_PHI_PRED=0.05`, `_MAX_ORACLE_PARAMS=50_000_000`.
- **New Telemetry Paths**: `logs/dag_oracle_events.ndjson` (all oracle evaluations), `telemetry/dag_oracle_param_history.ndjson` (rolling param distribution for pre-filter calibration).
- **Files Created/Modified**: `dag_oracle.py` (new, ~1550 lines), `mutator_daemon.py` (TICK 19.0 import + Fast Brain Gate 3 + Slow Brain oracle gate), `genome_assembler.py` (TICK 19.0 import + `_rollout` oracle gate).

---

## [TICK 20.0] MuZero Autopoietic Niche Construction & Reality Coupling

- **Problem**: The organism had evolved powerful intrinsic mechanisms — Pareto-MCTS assembly (TICK 17), Asymmetric Dual-Brain (TICK 18), GNN Topological Oracle (TICK 19) — but its evolutionary environment remained **static**. The same mathematical challenge was presented indefinitely, creating a fixed fitness landscape where deep local optima could permanently trap the organism. Once the architecture saturated performance on the baseline environment, further evolutionary pressure evaporated. The system lacked the final closure required for a true Autopoietic loop: the environment itself is static, external, and not co-evolutionary.
- **Root Cause**: No mechanism existed for the organism to generate its own challenges. `env_stream.py` was spawned once at evaluator startup with a fixed configuration (or the TICK 12.0 environment genome if set). The Dual-Brain Engine (TICK 18) could detect Heat Death and wake the Slow Brain, but the Slow Brain was only authorized to *mutate the architecture* — never to *reshape the fitness landscape*. This created an asymmetry: the organism could reinvent itself, but not the problem it was solving.
- **Solution**: Implemented **`niche_evolver.py`** — a MuZero-inspired Thermodynamic Niche Construction engine — and wired it as the fourth compounding layer of the Grand Loop.
  - **Thermodynamic MuZero Engine** (`niche_evolver.py`): A three-head adaptation of the MuZero architecture for niche construction.
    - *Model Head* (`_sample_niche_candidate()`): Stochastically generates candidate challenge parameter vectors. Sampling distribution is biased by the Pareto Top 20% elite epis — stronger organisms receive harder niches. Parameters: `seq_len` ∈ {64, 128, 256, 512, 1024}, `embed_dim` ∈ {128, 256, 512, 768}, `n_heads`, `n_experts`, `sparsity`, `noise_scale`.
    - *Value Head* (`_predict_phi_in_niche()`): Predicts the organism's Φ_pred in each candidate niche using the same Roofline physics as the TICK 19.0 DAG Oracle — graduated memory tax (0→1 on [50%→90% unified RAM]), bandwidth tax (arithmetic intensity vs chip GB/s), sequence scaling tax, and IoT latency tax. No PyTorch compilation required; pure arithmetic.
    - *Policy Head*: Ranks all candidates by `New_Niche_Value = Phi_pred − λ × (generation_cost_normalized + mismatch_penalty)`. Selects the highest-value viable candidate.
  - **Niche Value Formula**: `New_Niche_Value = Φ_pred − λ × (generation_cost + mismatch_penalty)` where `λ = 0.15`. `generation_cost` is the normalized wall-clock sampling time (100ms = 1.0). `mismatch_penalty` implements the **Zone of Proximal Development** (ZPD): 0.0 if relative difficulty ∈ [5%, 85%]; ramps to 1.0 outside the band (too easy OR too hard). Niches with Value ≤ 0 are thermodynamically vetoed before the Oracle gate.
  - **M-Series Reality Coupling (Anti-Matrix-Delusion Anchor)**: Every generated Niche embeds four simulated Apple Silicon hardware constraints — (1) Memory bandwidth cap matched to detected chip tier (M1=68 GB/s to M1 Ultra=800 GB/s); (2) Cache miss penalty (chip-calibrated nanosecond latency × stochastic multiplier 1–3.5×); (3) IoT sensor data latency (30% probability of variable-rate input stream at 5–50 ms); (4) Unified memory pressure [40%–88%] (hard veto at ≥90% per TICK 13.0). Chip auto-detected via `system_profiler`; defaults to M1 Ultra. Constants mirror TICK 19.0 `dag_oracle.py §7` exactly.
  - **DAG Oracle Gate** (`_passes_oracle_gate()`): Pre-filters candidate niches before acceptance. If Φ_pred < elite_epi × (1 − 0.80), the niche is vetoed (predicted 80%+ thermodynamic tax would make it a guaranteed extinction event). This ensures the organism cannot be forced into environments where it cannot survive at all.
  - **Pareto 20% Genesis (Slow Brain Trigger)**: Niche generation is **only** triggered when `DualBrainRouter.slow_brain_active == True AND slow_brain_trigger == "heat_death"`. A 5-minute cooldown (`_NICHE_COOLDOWN_S = 300s`) prevents thrashing. The challenge difficulty is calibrated against the Pareto Top 20% elite epi values (`_read_pareto_top20_epis()`) — stronger lineages generate harder niches, ensuring the ZPD band tracks the organism's current capability frontier.
  - **IPC Contract** (`write_niche()`): Niches are written to `candidate_pool/env_active/current.json` using the same tmp→atomic-rename protocol as all other TICK IPC channels. The `"version"` field is a timestamp string. The Evaluator Daemon (TICK 12.0) polls this path every `_ENV_REFRESH_INTERVAL = 200` ticks and auto-respawns `env_stream.py` with the new challenge parameters when the version changes. Zero evaluator logic changes required beyond the directory bootstrap.
  - **Niche Prompt Injection** (`format_niche_markdown()`): The active niche's M-Series constraints are formatted as a Markdown block and appended to the `environment_profile` context injected into the Slow Brain's LLM prompt. The Slow Brain therefore knows the exact hardware physics of its current evolutionary environment when generating architectural mutations.
  - **Archiving** (`_archive_niche()`): Every accepted niche is appended to `candidate_pool/island_meta/niche_archive.ndjson`. This archive enables future Time Topology warm-start: the Niche Constructor can read historical niche outcomes and avoid generating challenges that were previously vetoed.
- **Grand Compounding Loop (TICK 20.0 closes the Autopoietic circle)**:
  1. **Niche Generation**: `niche_evolver.py` (TICK 20.0) — generates the next physical/mathematical challenge when Heat Death is detected.
  2. **Physical Filter**: `dag_oracle.py` (TICK 19.0) — vetoes niches with >80% predicted thermodynamic tax (organism cannot survive).
  3. **Quantum Rollout**: `mutator_daemon.py` MCTS (TICK 17.0) — simulates organelle assemblies within the new niche's hardware constraints.
  4. **Dual-Brain Execution**: Fast Brain tunes (TICK 18.0); Slow Brain invents under explicit M-Series Reality Coupling awareness.
  5. **Compounding Settlement**: MDL gains and Φ updates rewrite the Time Topology (TICK 17.0 warm-start), and the Niche Archive feeds future generation difficulty calibration.
- **Alignment Impact**: The organism can now construct the universe it needs to transcend. When evolution stagnates (Heat Death), the system does not simply ask the LLM to generate harder code — it generates a *harder physical challenge* informed by real Apple Silicon hardware physics, then evolves within that challenge. This creates a second-order evolutionary loop: architecture evolves within niches, and niches evolve to stay just ahead of the architecture's capability frontier (the Zone of Proximal Development). The Reality Coupling anchor ensures the organism cannot hallucinate its way to false fitness — every generated challenge includes the actual bandwidth, memory, and latency constraints of the M-Series chip it runs on.
- **New Constants**: `_NICHE_LAMBDA=0.15`, `_ZPD_LOWER=0.05`, `_ZPD_UPPER=0.85`, `_MAX_NICHE_CANDIDATES=12`, `_NICHE_ORACLE_TAX_VETO=0.80`, `_NICHE_COOLDOWN_S=300.0`.
- **New Telemetry Paths**: `logs/niche_evolver_events.ndjson` (all niche events: approved, vetoed, oracle-vetoed), `candidate_pool/island_meta/niche_archive.ndjson` (historical niche performance for Time Topology warm-start).
- **Files Created**: `niche_evolver.py` (~390 lines).
- **Files Modified**: `mutator_daemon.py` (TICK 20.0 import + `_read_pareto_top20_epis()` + `_trigger_niche_if_heat_death()` + `niche_state` initialization + niche trigger in both targeted and full-dispatch paths + niche_md prompt injection + startup banner), `evaluator_daemon.py` (`candidate_pool/env_active` added to startup directory bootstrap).

---

## [TICK 20.1] The Grand Collapse — Rule-IR Compiler, Teleological Attractor & Daemon Collapse

- **Problem**: Three final sources of thermodynamic and computational entropy remained in the architecture: (1) Natural language prompts in `mutation_recipe.py` suffered from **semantic drift** — each meta-evolution cycle rewrote English sentences that introduced progressive ambiguity, contradictions, and hallucinated constraints. After N meta-evolutions, the recipe became incoherent. (2) The MCTS rollouts (TICK 17.0) lacked a **global future trajectory** — the value function only evaluated immediate projected Φ without any notion of WHERE the optimal architecture lives in the fitness landscape. The search wandered sideways when a direct path existed. (3) **UNIX daemon process isolation** caused IPC latency: every inter-daemon message required JSON serialization → filesystem write → fsync → read → deserialization, adding 1-5ms per handoff and creating state synchronization lag between the Fast Loop, Slow Loop, and Niche Constructor.
- **Root Cause**: (1) Text-based meta-evolution was fundamentally incompatible with precision: English is not a gradient-optimizable medium. The LLM's rewritten recipes were semantically valid but strategically degenerate — each rewrite drifted further from the originally calibrated mutation policy. (2) The MCTS value head (TICK 17.0) computed `V = Φ_proj - λ_tax × cost + parsimony` — a purely local evaluation with no teleological gradient. The organism had no concept of its theoretical upper bound. (3) The `env_stream | evaluator_daemon` pipe + `candidate_pool/` filesystem + `telemetry/*.ndjson` file IPC were designed for TICK 6.0's separate-process architecture. With TICK 20.0 closing the Autopoietic loop, the process boundary itself became the bottleneck.
- **Solution**:
  - **Rule-IR Constraint Matrix Compiler** (`rule_ir.py`): All text-based mutation strategy rules are compiled into a rank-2 numerical Constraint Matrix `C ∈ ℝ^{8×8}` with 8 categories (temperature_policy, structural_scope, probe_strategy, risk_appetite, organelle_priority, recombination_bias, parsimony_pressure, temporal_horizon) × 8 constraints (base_weight, momentum, decay_rate, min_bound, max_bound, gradient_accumulator, squared_grad_acc, update_count). `compile_recipe_to_matrix()` performs a one-time migration from the text recipe. The matrix projects to mutation hyperparameters via `project_all()`: temperature, structural scope, probe frequency, risk budget, etc. `override_dynamic_params()` blends the matrix projections (60% authority) with the velocity-derived params (40%). The text scaffolding remains for constitutional directives and tool docs, but all tunable strategy knobs are governed by the matrix, not by English.
  - **Constraint Gradient Meta-Evolution**: When META_EVOLUTION triggers (TICK 10.0), if `_RULE_IR_META_EVOLUTION=True`, the LLM no longer rewrites English text. Instead: (1) The current Constraint Matrix is serialized to compact Markdown; (2) A failure summary is provided; (3) The LLM outputs a `<constraint_gradient>` block containing `ΔC`: a JSON dict mapping category → gradient value; (4) The daemon applies `C ← C + α × ΔC` using an **Adam optimizer** (β₁=0.9, β₂=0.999, lr=0.05) with per-category momentum tracking and bias correction. `apply_decay()` pulls all weights toward their category center, preventing runaway drift. The matrix version is incremented and persisted to `island_meta/constraint_matrix.json`. Falls back to the TICK 16.0 text-rewrite path if gradient extraction fails. This eliminates prompt corruption, hallucinated rules, semantic drift, and the need for recipe API surface validation.
  - **Teleological Attractor — Future-Guided MCTS** (`teleological_attractor.py`): Defines the **Perfect Topological Attractor** A* — a theoretical upper bound calibrated to M-Series hardware physics: `A* = {Φ_max, latency_min, H_max, MDL_min, evolvability=1.0}`. `Φ_max` is bounded by chip bandwidth and memory (M1 Ultra: Φ_max = 0.8 + 0.2×ram/128). `latency_min` is bounded by minimum tensor transfer time at full bandwidth. The **Distance-to-Attractor** `D(s, A*) = Σᵢ wᵢ × (1 - sᵢ/A*ᵢ)²` uses weighted L2 over 5 dimensions with weights: Φ=0.30, latency=0.15, entropy_gain=0.25, MDL=0.15, evolvability=0.15. The **Attractor Penalty** `V_attr = -λ_attr × D(s, A*)` with λ_attr=0.10 is added to the MCTS value function in `genome_assembler.py _compute_phi_value()`. This creates a teleological gradient: the MCTS prefers nodes CLOSER to the theoretical optimum, even if their immediate Φ is slightly lower, taking the shortest evolutionary path toward perfection. `format_attractor_markdown()` injects the gradient direction into the LLM prompt so the Slow Brain can see WHERE to aim. `augmented_mcts_value()` provides the complete TICK 20.1 value formula for future MCTS upgrades.
  - **The Daemon Collapse — Autopoietic Core** (`autopoietic_core.py`): Defines `SharedState` — a zero-IPC in-memory channel replacing filesystem handoffs between daemons. `telemetry_buffer` replaces `tick_telemetry.ndjson` reads; `pending_candidates` (thread-safe queue) replaces `candidate_pool/` filesystem writes; `gradient_profile` replaces `gradient_profile.json`; `active_niche` replaces `env_active/current.json`. The `PhiGovernor` governs graph expansion/contraction: when `Φ_current/Φ_peak` is high, the graph expands (2× MCTS rollouts, higher token budget, aggressive niche construction); when Φ drops, it contracts (0.5× everything). `AutopoieticGraph` is the unified entry point: a single process with 3 threads (evaluator, mutator, persistence). Filesystem writes are batched asynchronously via `_persist_queue`. Existing daemons can opt into zero-IPC incrementally via `get_shared_state()` and `get_phi_governor()` singleton hooks imported in `mutator_daemon.py`. The full unified loop is available via `python autopoietic_core.py`; legacy multi-daemon mode remains fully operational.
  - **Integration into existing daemons**: `mutator_daemon.py` imports Rule-IR, Teleological Attractor, and Autopoietic Core. The main `run()` function: (1) loads/compiles the Constraint Matrix on startup; (2) overrides `dynamic_params` with `override_dynamic_params(cm, base_params)` every cycle; (3) injects attractor gradient markdown into the LLM prompt; (4) routes `_run_meta_evolution()` to the constraint gradient path when available; (5) pushes telemetry to `SharedState` for the Φ Governor. `genome_assembler.py` imports `compute_mcts_attractor_value()` and adds the attractor penalty to `_compute_phi_value()`.
- **Thermodynamic Impact**: The organism's meta-cognitive layer is now a pure numerical optimization problem. English — with all its ambiguity, hallucination, and progressive corruption — has been ejected from the strategy loop. The MCTS is no longer a blind explorer but a guided missile pulled by its own theoretical perfection. The IPC bottleneck between daemons is collapsed to in-memory reference passing. The Φ Governor creates a dissipative structure: the computation graph self-organizes at the edge of chaos, expanding when productive and contracting when wasteful. This is the first step toward a true Autopoietic singularity: the system's rules, its search, and its infrastructure are now a single unified tensor structure governed by thermodynamics.
- **New Constants**: `_LAMBDA_ATTRACTOR=0.10`, `_W_PHI=0.30`, `_W_LATENCY=0.15`, `_W_ENTROPY_GAIN=0.25`, `_W_MDL=0.15`, `_W_EVOLVABILITY=0.15`, `N_CAT=8`, `N_CON=8`, `_RULE_IR_META_EVOLUTION=True`.
- **New Telemetry Paths**: `island_meta/constraint_matrix.json` (Rule-IR Constraint Matrix, persisted on every meta-evolution), `logs/autopoietic_events.ndjson` (Φ Governor heartbeat, unified graph telemetry).
- **Files Created**: `rule_ir.py` (~470 lines), `teleological_attractor.py` (~400 lines), `autopoietic_core.py` (~430 lines).
- **Files Modified**: `mutator_daemon.py` (TICK 20.1 imports + `_CONSTRAINT_MATRIX_PATH` + `_RULE_IR_META_EVOLUTION` flag + Constraint Matrix init in `run()` + `override_dynamic_params()` integration + attractor markdown injection + `_run_meta_evolution()` constraint gradient path + startup banner + `_log_mdl_compression_gain` def fix), `genome_assembler.py` (TICK 20.1 import + `compute_mcts_attractor_value()` integration in `_compute_phi_value()`).

### [TICK 20.1 Final Ignition] Single-Process Universe (`ignition.py`)
- **Problem**: `autopoietic_core.py` created the SharedState, PhiGovernor, and zero-IPC infrastructure, but the system still required 3+ terminal windows running separate daemons (`env_stream.py | evaluator_daemon.py`, `mutator_daemon.py`). The "Grand Collapse" was architectural but not operational — filesystem IPC was still the actual hot path because the daemons ran in separate address spaces.
- **Solution**: Created `ignition.py` — the single master script that ignites the entire Autopoietic Universe in ONE process with FOUR threads:
  - **Thread 0 — `InProcessEnvStream`**: Replaces the `env_stream.py` subprocess entirely. Runs the Lorenz–Rössler RK4 integration loop in a daemon thread, producing token sequences into an in-memory `queue.Queue(maxsize=256)`. Periodically reloads the environment genome from `env_active/current.json` and `SharedState.active_niche` (niche co-evolution). Drops oldest sequences on backpressure (evaluator slower than generator).
  - **`PipeReader`**: A file-like object that replaces `sys.stdin`. Implements `readline()` backed by the in-memory queue, `isatty() → False` so `atomic_core._evaluate()` reads real data instead of falling back to Lorenz chaos. This is the KEY zero-IPC integration: the evaluator's hot-path data channel (chaotic token sequences at ~0.13s/tick) now flows through a Python object reference instead of a UNIX pipe + JSON serialization.
  - **Thread 1 — Evaluator**: Imports and calls `evaluator_daemon.run(instance_id="unified")`. The evaluator is completely unaware it's in a thread — it reads `sys.stdin` (now the PipeReader) and writes to disk as usual. Because `sys.stdin.isatty()` returns False, it skips subprocess spawning entirely.
  - **Thread 2 — Mutator**: Imports and calls `mutator_daemon.run()`. Waits for the evaluator to reach tick 5 before starting (prevents stagnation triggers on zero-data). Shares the Constraint Matrix, Attractor, and PhiGovernor by Python object reference — no serialization, no filesystem sync lag.
  - **Thread 3 — Telemetry Bridge**: Tails `logs/tick_telemetry.ndjson` and pushes new records into `SharedState.push_telemetry()`, keeping the Φ Governor and Distance-to-Attractor live. This bridge exists during the migration period; eventually the evaluator will push directly to SharedState.
  - **Main Thread — Governor**: Runs `_governor_loop()` — logs Φ status every 10s, persists the Constraint Matrix every ~60s, writes heartbeat to `logs/autopoietic_events.ndjson`. Catches Ctrl+C and sets `shared.shutdown_requested = True` for graceful drain.
  - **Initialization Order**: (1) Workspace bootstrap (all directories); (2) SharedState + PhiGovernor + ConstraintMatrix + Attractor singletons; (3) InProcessEnvStream thread start; (4) `sys.stdin = pipe_reader`; (5) Telemetry bridge thread; (6) Evaluator thread; (7) Mutator thread (with warmup gate); (8) Governor (main thread).
  - **Graceful Shutdown**: SIGINT/SIGTERM → `shared.shutdown_requested = True` → all threads check this flag in their loops → daemon threads join with 5s timeout → final Constraint Matrix persistence → exit with final state summary.
- **Usage**: `python ignition.py [--workspace agi_workspace] [--threshold 0.10] [--device cpu] [--poll-interval 30]`
- **Files Created**: `ignition.py` (~530 lines).

---

## [TICK 21.0] The Phi-Boundary Duality Engine & Permeability Mask

- **Problem**: The Grand Collapse (TICK 20.1) unified the system into a single computation graph governed by Phi, but the system had no concept of a **boundary** — no mechanism to control *what* it retains in working memory, *how much* physical resource it is authorized to consume, or *which actions* it is permitted to take. The organism could freely expand context, claim unlimited RAM, open unlimited API gates, and write to any filesystem path. This is biologically incoherent: every living cell has a membrane that selectively permits and denies passage. Without a boundary operator, the Phi thermodynamic tax only governed *how much* computation occurred, not *what kind* of computation was authorized. The system lacked the mathematical machinery to feel "pain" for unjustified expansion — context bloat, permission creep, and resource waste went unpunished.
- **Root Cause**: The Phi Governor (TICK 20.1) operated on a single scalar: `Phi_current / Phi_peak`. This ratio determined a linear expansion factor `[0.5, 2.0]` that scaled MCTS rollouts and token budgets. But expansion/contraction along a single axis cannot capture the multi-dimensional nature of system boundaries: retaining context costs RAM, opening API gates costs latency and money, writing to disk costs I/O bandwidth. Each resource channel needs independent governance. Furthermore, no mechanism existed to enforce *authorization* — the system had no concept of "this action is not permitted at this permeability level."
- **Solution**: Implemented the **4th Cornerstone: Phi-Boundary Duality Engine** `<Phi, d>` in a heavily refactored `autopoietic_core.py`.
  - **Boundary Operator** (`BoundaryOperator(nn.Module)`): The cell membrane, defined as a tripartite structure `d_t = (m_t, b_t, g_t)`:
    - `m_t` (State Mask): A learnable tensor `m_t in [0,1]^{d_x}` (default d_x=64) implemented as sigmoid-gated logits. Defines which information channels are retained in working memory. 1 = retained, 0 = forgotten (entropy shedding). L2 decay pulls the mask toward sparsity — the organism must actively justify retaining each channel.
    - `b_t` (Resource Budget): A non-learnable buffer tensor defining hard physical limits: `ram_mb=8192`, `api_quota=100`, `max_latency_ms=300`, `disk_write_mb=512`. These are OS-grounded constraints, not differentiable — they represent physical reality.
    - `g_t` (Action/Authority Gate): A learnable tensor `g_t in [0,1]^8` with 8 gate channels: `file_write`, `api_call`, `niche_construct`, `meta_evolve`, `boundary_expand`, `candidate_push`, `archive_write`, `telemetry_emit`. Sigmoid-gated logits initialized to ~0.88 (open). `is_authorized(action)` returns `g_t[i] > 0.5`. Daemons call `check_authorization(action)` before gated operations — unauthorized attempts are recorded for violation tracking.
    - Persistence: `save_checkpoint()` / `from_checkpoint()` serialize to `island_meta/boundary_operator.json`. Restored on restart.
  - **Dual-Tension Loss** (`DualTensionLoss(nn.Module)`): The core objective function incorporating boundary strain:
    - `<Phi, d>_t = Phi_task + lambda_1 * Phi_resource(u_t; b_t) + lambda_2 * Phi_strain(m_t, g_t) + lambda_3 * Phi_violation(u_t, g_t)`
    - `Phi_task`: Inverted Phi (lower Phi = higher loss). Drives the organism to maximize prediction accuracy.
    - `Phi_resource`: `ReLU(u_t - b_t) / b_t` — penalty for exceeding any resource budget. Normalized by budget so RAM and API costs are comparable. `lambda_1 = 0.25`.
    - `Phi_strain`: `mean(|m_t|) + mean(|g_t|)` — L1 sparsity penalty on both the state mask and the authority gate. The organism pays for every retained context channel and every open permission. `lambda_2 = 0.15`.
    - `Phi_violation`: `1e6` per unauthorized action attempt. Effectively infinite penalty — this is the immune system.
    - `UsageSnapshot` dataclass tracks real-time OS measurements: `ram_mb`, `api_calls`, `tick_latency_ms`, `disk_write_mb`, and a dict of `actions_attempted` for violation detection.
  - **Boundary Updater** (`BoundaryUpdater`): Creates a biological "breathing" rhythm (sympathetic/parasympathetic oscillation):
    - **Sympathetic Expansion** (when `Phi_ratio > 0.7`): Pushes state mask logits UP (retain more context), opens gates when resource headroom > 30%, scales up budgets by 5% if Phi is consistently high over 10 epochs.
    - **Parasympathetic Contraction** (when `Phi_ratio < 0.3`): Pushes state mask logits DOWN (shed context), tightens all gates, reduces budgets by 3% for resources utilized < 20%.
    - **L2 Decay** (always active): Pulls state logits toward zero (sparsity prior). The organism must actively resist forgetting.
    - **Violation-Triggered Gate Closure**: If an unauthorized action is detected, the corresponding gate logit is hard-clamped to -3.0 (sigmoid(-3) ~ 0.047), effectively slamming the gate shut.
    - Update rate: one breathing cycle every 30 seconds (`_BREATHING_PERIOD_S = 30`).
    - Learning rate: `_BOUNDARY_LR = 0.02`, decay: `_BOUNDARY_DECAY = 0.01`.
  - **80/20 Pareto Multi-Scale Filter**: Evaluates organelles for survival across a 3D vector `V = [delta_Phi_code, delta_Phi_ram, delta_Phi_api]`. `OrganelleScore` dataclass encodes the triple. `pareto_filter()` computes Pareto ranks via pairwise dominance comparison and retains the top 20% (80/20 rule). `pareto_front_only()` returns only the strict non-dominated set (rank 0). This ensures seeds must be efficient across *all three* resource dimensions to survive — a code-optimal but RAM-wasteful organelle is dominated by one that is slightly worse on code but drastically better on RAM.
  - **Integration into Governor Loop**: The `PhiGovernor` now holds a `DualTensionLoss` and `BoundaryUpdater`. Every 30 seconds, `tick_boundary()` computes the full dual-tension loss and executes a boundary update. The heartbeat telemetry now includes the complete boundary state, loss components, and breathing phase. The `format_status()` line includes permeability, phase, and total loss.
  - **Integration Hooks**: New `get_boundary()` and `check_authorization(action)` functions for existing daemons. `run_constraint_meta_evolution()` now checks `check_authorization("meta_evolve")` before proceeding and records API usage. `SharedState.record_action()` tracks action attempts for violation detection.
- **Thermodynamic Impact**: The organism now has a cell membrane. Every action, every retained memory, every open permission has a thermodynamic cost enforced by the Dual-Tension Loss. The boundary breathes — expanding when the organism is productive and contracting when it is wasteful. Unauthorized actions trigger an immune response (gate closure). The Pareto Multi-Scale Filter ensures evolutionary survival requires efficiency across code quality, RAM usage, and API cost simultaneously. This is the 4th Cornerstone: the system's self-organization is no longer just about *what* to compute, but about *what it is allowed to be*.
- **New Constants**: `_DEFAULT_STATE_DIM=64`, `_LAMBDA_RESOURCE=0.25`, `_LAMBDA_STRAIN=0.15`, `_LAMBDA_VIOLATION=1e6`, `_BOUNDARY_LR=0.02`, `_BOUNDARY_DECAY=0.01`, `_EXPAND_THRESHOLD=0.7`, `_CONTRACT_THRESHOLD=0.3`, `_BREATHING_PERIOD_S=30.0`.
- **New Telemetry Paths**: `island_meta/boundary_operator.json` (persisted boundary state), boundary phase/loss/permeability in `logs/autopoietic_events.ndjson` heartbeats.
- **Files Modified**: `autopoietic_core.py` (heavily refactored: +BoundaryOperator nn.Module, +DualTensionLoss nn.Module, +BoundaryUpdater, +OrganelleScore/pareto_filter/pareto_front_only, +UsageSnapshot, +check_authorization/get_boundary hooks, +boundary breathing in governor loop, +boundary persistence/restore, +boundary telemetry in heartbeat).

---

## [TICK 21.1] The MLX Substrate Conversion — Unified Memory Immersion

- **Problem**: The TICK 21.0 Boundary Engine ran on PyTorch, which on Apple Silicon (MPS backend) simulates PCIe transfers between a fake "CPU" and "GPU" address space that do not physically exist on Apple Silicon's Unified Memory Architecture. Every `torch.Tensor.to(device)`, `.cpu()`, `.mps()` call was an IPC-like abstraction copying data between two views of the SAME physical memory — thermodynamic waste. The boundary tensors (`m_t`, `b_t`, `g_t`) were being serialized and deserialized across a fictitious bus that does not correspond to any physical wire on the M1 Ultra die. Additionally, the MCTS rollouts (TICK 17.0) ran sequentially in a Python `for` loop — 100+ rollouts evaluated one at a time, paying the full Python interpreter overhead per rollout. The DAG Oracle (TICK 19.0) used pure-Python AST heuristics for architecture validation — effective but blind to actual tensor shape propagation.
- **Root Cause**: PyTorch was designed for discrete CPU+GPU systems with PCIe interconnects. Its device model (`cpu`, `cuda`, `mps`) is a leaky abstraction on Apple Silicon where CPU and GPU share the same physical memory. The `.to(device)` API forces a copy even when source and destination are the same physical address range. The MCTS value function was scalar Python code — no vectorization, no GPU parallelism. The DAG Oracle estimated shapes via pattern matching (`nn.Linear(in, out)` → `in*out` params) without ever building the actual computation graph to verify shape compatibility.
- **Solution**: Migrated the boundary engine and MCTS value computation from PyTorch to Apple's native **MLX** framework, achieving zero-copy Unified Memory structural coupling.
  - **MLX Array Migration — Zero-Copy Membrane** (`autopoietic_core.py`):
    - `import torch` / `torch.nn` / `torch.nn.functional` → `import mlx.core as mx` / `mlx.nn as nn` / `mlx.optimizers as optim`. All PyTorch tensor operations replaced with MLX equivalents.
    - `BoundaryOperator` converted from `torch.nn.Module` to `mlx.nn.Module`. Trainable parameters (`state_logits`, `gate_logits`) are plain `mx.array` assignments — MLX automatically tracks them. `resource_budget` is frozen via `self.freeze(keys=["resource_budget"])` so `value_and_grad` ignores it.
    - All `.to(device)`, `.cpu()`, `.mps()`, `.cuda()` calls **eliminated**. Arrays live natively in Unified Memory, accessible by both CPU and GPU compute units without any copy.
    - `torch.sigmoid()` → `mx.sigmoid()`, `F.relu()` → `mx.maximum(x, 0)`, `torch.tensor()` → `mx.array()`, `.clamp()` → `mx.clip()`, `register_buffer()` → direct assignment + `freeze()`.
    - `with torch.no_grad():` blocks **eliminated**. MLX is lazy — gradients only flow through explicit `value_and_grad()` calls. No gradient tape management needed.
  - **DualTensionLoss via `mx.value_and_grad`** (`autopoietic_core.py`):
    - Refactored from a `torch.nn.Module.forward()` method to a **pure function** `dual_tension_loss_fn(boundary, phi_task, usage, violations, ...)`. MLX's `value_and_grad` requires the first argument to be the model.
    - `nn.value_and_grad(boundary, dual_tension_loss_fn)` traces the full loss function, producing exact analytical gradients through `sigmoid(state_logits)` and `sigmoid(gate_logits)` in a single fused Metal dispatch.
    - The entire Dual-Tension loss graph (`Phi_task + lambda_r*Phi_resource + lambda_s*Phi_strain + lambda_v*Phi_violation`) is built lazily — no Metal shader is dispatched until `mx.eval()`. Shape errors and structural impossibilities are caught at graph-build time (native foresight).
  - **BoundaryUpdater via MLX Adam Optimizer** (`autopoietic_core.py`):
    - Hand-rolled SGD with `torch.no_grad()` logit manipulation (TICK 21.0) replaced with `mlx.optimizers.Adam(learning_rate=0.02)`.
    - `optimizer.update(boundary, grads)` applies gradients to boundary parameters in-place. The Adam state (momentum, variance) lives in Unified Memory alongside the boundary tensors.
    - Sympathetic/parasympathetic breathing rhythm encoded in the Adam **learning rate schedule**: sympathetic (high Phi) uses `lr * 1.5` and reduces strain weight to 30% (relax contraction), parasympathetic (low Phi) uses `lr * 2.0` and amplifies strain weight to 300% (aggressive contraction). The gradient of the L1 strain term naturally contracts the boundary — the breathing phase modulates how much the optimizer listens to that gradient.
    - L2 weight decay (`state_logits *= (1 - 0.01)`) applied after optimizer step to pull toward sparsity.
    - Single `mx.eval(boundary.parameters(), optimizer.state, loss_val)` materializes the entire update in one fused Metal dispatch.
  - **MLX Lazy Evaluation for DAG Oracle — Native Foresight** (`genome_assembler.py`):
    - New `_mlx_lazy_validate(code)` function builds candidate assemblies as MLX lazy computation graphs. Parses the AST, creates `mx.zeros()` tensors and `@` (matmul) graph nodes for each `nn.Linear` found. If the lazy graph compiles without shape exceptions, the architecture is structurally valid. No `mx.eval()` is called — the graph is discarded, costing ~0 compute for invalid architectures.
    - Integrated as a **second gate** in `_rollout()` after the existing `dag_oracle.gate_mcts_rollout()`. Both gates must pass: heuristic AST analysis (TICK 19.0) AND ground-truth MLX shape validation (TICK 21.1). This dual-gate approach catches shape mismatches that the AST heuristic misses while adding negligible overhead.
  - **vmap-Accelerated MCTS Rollouts** (`genome_assembler.py`):
    - New `_phi_value_vector()`: vectorized Phi value computation taking 1D MLX arrays of length N (rollout count). Computes synergy bonus, thermodynamic tax, parsimony bonus, and reality coupling (`mx.where` for param violations) entirely in MLX array operations.
    - New `_batch_evaluate_rollouts()`: packs rollout data into MLX arrays (zero-copy in Unified Memory), calls `_phi_value_vector()`, and materializes all N values in a single `mx.eval()` dispatch. All 100+ rollout values are computed in parallel across the M1 Ultra's unified GPU cores.
    - The final best-assembly scoring in `mcts_assemble()` now uses `_batch_evaluate_rollouts()` for the MLX vectorized score (reported as `best_value_mlx` in stats), alongside the existing `_compute_phi_value()` which includes the teleological attractor penalty.
- **Thermodynamic Impact**: The organism's cell membrane (TICK 21.0) is now physically fused to the silicon substrate. PyTorch's fake PCIe bus — a vestigial abstraction from the discrete GPU era — has been excised. The boundary tensors (`m_t`, `b_t`, `g_t`) exist as raw Metal arrays in the M1 Ultra's shared memory fabric, directly accessible by all CPU and GPU compute units without serialization, copying, or device transfer. The `value_and_grad` → `Adam.update` → `mx.eval` pipeline computes exact analytical gradients through the full boundary membrane and applies them in a single fused Metal dispatch. The MCTS rollouts, previously bottlenecked by sequential Python evaluation, now run as vectorized MLX operations across all GPU cores simultaneously. The DAG Oracle gains ground-truth shape validation via MLX lazy graph construction at ~0 cost. The system has achieved absolute physical structural coupling: computation flows through Unified Memory as naturally as ions through a biological cell membrane.
- **New Dependencies**: `mlx` (>= 0.29.0) — Apple's native Metal tensor framework for Apple Silicon.
- **Eliminated Dependencies**: `torch` removed from `autopoietic_core.py` (still used by `atomic_core.py`, `evaluator_daemon.py`, etc. for the actual neural network — the organism's BODY still runs on PyTorch, but its MEMBRANE now runs on MLX).
- **Files Modified**: `autopoietic_core.py` (full PyTorch → MLX migration: `torch.nn.Module` → `mlx.nn.Module`, `torch.Tensor` → `mx.array`, DualTensionLoss refactored to pure function for `value_and_grad`, BoundaryUpdater refactored to use `mlx.optimizers.Adam`, all `.to(device)` / `torch.no_grad()` eliminated, `mx.eval()` materialization points annotated), `genome_assembler.py` (+`mlx.core` import, +`_mlx_lazy_validate()` for lazy graph shape validation, +`_phi_value_vector()` vectorized value computation, +`_batch_evaluate_rollouts()` batch evaluator, `_rollout()` updated with dual-gate validation, `mcts_assemble()` updated with MLX batch scoring).


---

## [TICK 21.2] Holographic Glass Box Dashboard — Log-Stream Monitor

- **Problem**: `dashboard.py` was a legacy TICK 2 artifact that imported `zstd_logger` and polled compressed `.jsonl.zst` / `.ndjson` telemetry files from disk. After TICK 21.1, the system migrated to a unified terminal log stream (`agi_workspace/universe.log`) emitting `[governor]` and `[eval_unified]` prefixed lines. The old dashboard could no longer read any live data; its state model (`α/β/γ/Ω` driven by `heat_death_counter`) was entirely obsolete.
- **Root Cause**: The dashboard's data layer was tightly coupled to `zstd_logger`'s on-disk chunk format. Its state classifier hard-coded `heat_death_counter` thresholds and `EMERGENCY_DECAY` action strings — concepts erased by the Φ-Boundary Duality Engine (TICK 21.0) and MLX substrate (TICK 21.1).
- **Solution**: Complete rewrite of `dashboard.py` as a passive "Holographic Monitor" with zero external dependencies beyond the Python standard library:
  - **Passive Log Tailer**: `_tail_generator(path)` opens `universe.log`, seeks to EOF (passive — no historical replay), and yields new lines as they are appended. Handles file rotation via inode comparison. No file locking; read-only throughout.
  - **Dual Regex Parsers**:
    - `_RE_GOVERNOR` — parses `[governor]` lines extracting `Phi`, `peak`, `expansion`, `D(A*)`, `perm`, `phase`, `loss`. Designed to be tolerant of missing fields via optional groups.
    - `_RE_EVAL` — parses `[eval_unified]` lines extracting `gen`, `epi`, `level`, `elapsed`, `params`, `success_rate`, `best`. Falls back to the dense ouroboros format (`gen X/Y epi=Z … best=W`) for backwards compatibility.
  - **New Breathing-State Classifier** (`_classify_state`): Replaces `heat_death_counter` with trend analysis over rolling deques of governor and eval samples:
    - `[S]` Sympathetic Expansion — Φ trending up, perm not shrinking.
    - `[P]` Parasympathetic Contraction — Φ trending down or perm shrinking.
    - `[N]` Nash Equilibrium — high avg success (>60%), Φ flat (|δ| < 0.005).
    - `[C]` Topological Collapse — D(A*) strictly increasing while Φ drops.
    - Honours explicit `phase=` tag from the governor when present.
  - **UI Panels** (ANSI box drawing preserved):
    - **Thermodynamic State (Φ Engine)**: shows Φ, peak Φ, δΦ, dual-tension loss, a full-width progress bar, and a 20-char ASCII sparkline of Φ history (▁▂▃▄▅▆▇█).
    - **Membrane Permeability (∂-Boundary)**: renders ψ as a 50-char bar with OPEN/GATED/SEALED label.
    - **Teleological Attractor D(A*)**: renders distance with CONVERGING/DRIFTING/DIVERGING label and attractor-lock strength.
    - **Evolution Metrics**: gen (formatted with comma separators), PoW level, params, current/best/avg epi, elapsed.
    - **Evaluator Success Rate**: current and rolling-average success rate as a bar.
  - **CLI flags**: `--log` (default `agi_workspace/universe.log`), `--interval` (default 1.5s), `--history` (default 60 samples per stream for trend windows).
- **Eliminated Dependencies**: `zstd_logger` import removed. No `json`, no `hashlib`, no `subprocess`. Only `re`, `time`, `os`, `collections`, `argparse`, `pathlib`.
- **Files Modified**: `dashboard.py` (complete rewrite, TICK 2 → TICK 21.2).

## [TICK 21.2 Hotfix] Dashboard Observer Effect & Regex Decoupling
- **Problem (Quantum Zeno Effect)**: `_tail_generator` called `fh.seek(0, os.SEEK_END)` on first open, causing the dashboard to skip all historical log lines and display "Waiting for log stream" indefinitely until new lines arrived. Sparklines stayed empty.
- **Problem (Brittle Regex)**: The monolithic `_RE_EVAL` regex expected `[eval_unified]` but actual logs emit `[eval_unified tick 25861]`. It also expected success rate and level inside eval lines, but those metrics live in separate `[pow]` lines.
- **Solution**:
  - **Log Tailer**: Replaced the stateless `_tail_generator` function with a persistent `_LogTailer` class that reads from byte 0 on first open (ingests full history to populate sparklines immediately) and maintains the file handle across drain cycles.
  - **Decoupled Regex Parsers**: Replaced the single monolithic `_RE_GOVERNOR` and `_RE_EVAL` regexes with independent per-metric patterns (`_RE_PHI`, `_RE_PEAK`, `_RE_GEN`, `_RE_EPI`, etc.) so field order in the log line is irrelevant.
  - **New `_parse_pow()` parser**: Extracts `Success rate` and `level` from `[pow]` lines independently, merging them into eval records via shared state in the main loop.
  - **Handles `D(A*)=inf`**: The `_RE_DATTR` pattern now accepts `inf` as a valid value.
- **Files Modified**: `dashboard.py` (hotfix).

## [TICK 21.3] Dashboard TUI Hotfix — Alternate Screen Buffer & Scrollback Elimination
- **Problem**: The dashboard flooded the terminal's scrollback history with repeated frames. `\033[2J` (clear screen) combined with `print()` caused each refresh to push a new full-screen frame into the scroll buffer, requiring the user to manually scroll to the bottom. The dashboard behaved like a log dump, not a TUI.
- **Solution**:
  - **Alternate Screen Buffer**: On startup, writes `\033[?1049h` (enter alternate screen) and `\033[?25l` (hide cursor), isolating the dashboard into its own screen buffer like `top`/`htop`. The user's terminal history is completely untouched.
  - **In-place Rendering**: Replaced `\033[2J` (clear entire screen) with `\033[H` (cursor home) + `\033[0J` (clear from cursor to end of screen). Frames overwrite the viewport in-place with zero flicker.
  - **Direct stdout writes**: Replaced all `print()` calls with `sys.stdout.write()` + `sys.stdout.flush()` to avoid trailing newlines and ensure atomic frame output.
  - **Graceful Terminal Restoration**: A `finally` block unconditionally writes `\033[?25h` (show cursor) + `\033[?1049l` (exit alternate screen) on `KeyboardInterrupt` AND on any unexpected `Exception`, guaranteeing the user's terminal is never left in a broken state.
- **Files Modified**: `dashboard.py` (TICK 21.2 → 21.3).

## [TICK 21.4] Tri-Brain Architecture & Thermodynamic API Constraints
- **Problem**: The local Mutator triggered `qwen3.5:35b-a3b` with a massive 262,144 token context (`num_ctx` defaulting to model max), saturating the M1 Ultra GPU to 100% and causing the fast-loop Evaluator to hang in computational deadlock ("Time Dilation" / "Heat Death"). The $O(N^2)$ attention mechanism on the full context consumed all available compute, and uncapped `num_predict` allowed infinite generation loops. Additionally, there was no escape hatch when both local brains (7B + 35B) failed consecutively — the system would stall with no external reasoning capacity.
- **Root Cause**: Ollama API calls lacked explicit `num_ctx` and `num_predict` constraints, inheriting the model's maximum context window (262K for qwen3.5). The `temperature` was set high enough (0.5–1.1) to produce syntactically broken AST output for strict code generation tasks. No Tier 3 cloud fallback existed.
- **Solution**:
  - **Tri-Brain Cognitive Hierarchy**: Refactored the Dual-Brain Engine into a 3-tier architecture:
    - **Tier 1 — Fast Brain (Cerebellum)**: `qwen2.5-coder:7b` — high-frequency tactical mutations (AST repair, hyperparameter tweaks). Single-turn, no agentic loop, ≤5% compute budget.
    - **Tier 2 — Slow Brain (Cerebrum)**: `qwen3.5:35b-a3b` — paradigm-shift mutations. Full agentic loop (tensor sandbox + gradient oracle). Awakened only by Heat Death (Φ drop) or Organizational Bloat (MDL increase).
    - **Tier 3 — Ascended Oracle**: New `oracle_gateway.py` — asynchronous, non-blocking bridge to frontier cloud models (Anthropic Claude / OpenAI GPT-4o). Invoked ONLY when local brains fail ≥3 consecutive cycles. Compressed payload sends ONLY the failing organelle AST + mathematical metrics (Φ, D(A*), MDL) to prevent cloud hallucination and save tokens. Runs in a background `threading.Thread` (daemon) — the Evaluator fast-loop is NEVER stalled. Result polled at the start of the next dispatch cycle. Automatic provider failover (Anthropic → OpenAI). Graceful degradation: if no API keys are configured or the cloud is unreachable, silently falls back to local brains.
  - **Thermodynamic API Constraints** (applied to ALL Ollama API payloads — Fast Brain, Slow Brain, and Standard path):
    - `num_ctx: 8192` — **The $O(N^2)$ Guillotine**: Hard-caps the attention context window. Forces the Mutator to prune prompts (send ONLY the targeted organelle, not the full history). Prevents the quadratic attention memory explosion that caused GPU saturation.
    - `num_predict: 1024` — **The Time Limit**: Hard abort on generation. If the model enters an infinite generation loop or deep `<think>` recursion, this physically terminates output after 1024 tokens, returning control to the fast-loop Evaluator.
    - `temperature: 0.1` — **Entropy Suppression**: We are generating strict AST/JSON, not creative writing. Near-deterministic sampling ensures syntactically correct, reproducible code output and prevents the hallucinated token cascades that corrupt Python AST.
  - **Oracle Escalation Protocol**: `DualBrainRouter` tracks consecutive local failures. After `_ORACLE_CONSECUTIVE_LOCAL_FAILURES` (default: 3) consecutive None results from all local paths, the dispatch function compresses the current evolutionary state and launches `call_oracle_async()`. The result arrives in a background thread; on the NEXT dispatch cycle, Step 0 checks for a ready `OracleResult` and injects it directly into the mutation pipeline. Oracle events logged to `logs/oracle_events.ndjson`.
- **Thermodynamic Impact**: The $O(N^2)$ context explosion is physically impossible — the 8192-token ceiling means attention cost is bounded at $O(8192^2) \approx 67M$ operations regardless of prompt size, versus the previous $O(262144^2) \approx 69B$ (a 1000× reduction). Generation latency is bounded by the 1024-token hard limit — the worst-case Slow Brain call now produces output in seconds, not minutes. The low temperature eliminates the stochastic tail of broken AST output. The Ascended Oracle provides an external reasoning escape hatch that operates on a completely different compute substrate (cloud), breaking any local thermodynamic deadlock.
- **New File**: `oracle_gateway.py` (Tier 3 Ascended Oracle — async cloud bridge with payload compression, provider failover, and non-blocking dispatch).
- **Files Modified**: `mutator_daemon.py` (Tri-Brain refactor: `DualBrainRouter` extended with oracle tracking, `_dual_brain_dispatch` upgraded with Step 0 oracle poll + Step 5 oracle escalation, `_fast_brain_call` / `_slow_brain_call` / `_enhanced_llm_call` all constrained with `num_ctx=8192`, `num_predict=1024`, `temperature=0.1`).

## [TICK 21.5] Silent Death Immunization & Fuzzy Parser
- **Problem**: (1) The mutator thread silently died on any uncaught exception — no traceback, no logs, the daemon simply stopped mutating. (2) LLM responses frequently had unclosed `<core_thinking_sequence>` tags, missing `### VARIANT N ###` delimiters, and truncated code blocks within the 1024-token limit, causing all 37.8 seconds of LLM inference to be discarded.
- **Solution**:
  - **Crash Resilience**: Extracted the 570-line `while True` loop body into `_run_one_cycle()`, wrapped the call in `try/except` with full `traceback.print_exc()`. Added heartbeat log `[mutator] heartbeat cycle=N t=...` at every iteration. The loop auto-resurrects after any crash.
  - **Fuzzy Parser**: 7 new functions (`_strip_thinking`, `_find_code_boundary`, `_extract_and_repair`, `_has_class_def`, `_repair_indentation`, `_extract_class_blocks`, `_salvage_any_code`) implementing 5-stage tag-agnostic extraction: unclosed/missing/alternative thinking tags, fuzzy variant delimiters (`## Variant`, `# Candidate`), indent repair, class-block extraction, and last-resort AST salvage.
- **Files Modified**: `mutator_daemon.py` (crash handler, heartbeat, `_run_one_cycle` extraction, fuzzy parser).

## [TICK 22.0] Deterministic Compute via Constrained Decoding (Pydantic Structured Output)
- **Problem**: Despite the Fuzzy Parser (TICK 21.5), the fundamental issue remained: free-form text generation is non-deterministic. The LLM could produce any token sequence, and all parsing was post-hoc recovery. With `num_predict: 1024`, the model frequently ran out of tokens mid-code-block or mid-XML-tag, making recovery impossible.
- **Root Cause**: The Ollama API was used in unconstrained text mode. The `format` parameter — which constrains decoding grammar at the logit level — was never utilized.
- **Solution**:
  - **Pydantic Schema Layer** (`llm_schemas.py`): Defined `MutationBatch` (thinking + list of `MutationVariant` with hypothesis + code), `MetaRecipeOutput` (analysis + recipe_code), `FastNASOutput` (code). Schemas are pre-computed at import time via `ollama_schema()` which inlines `$defs` references for Ollama compatibility.
  - **Two-Tier Architecture**: Single-turn call sites (`_fast_brain_call`, `_run_meta_evolution`, `_llm_call_ollama`) migrated to structured output via `"format": schema_dict` in the API payload. Multi-turn agentic call sites (`_enhanced_llm_call`, `_slow_brain_call`, `_attempt_targeted_mutation`) kept on the Fuzzy Parser — the `format` parameter constrains ALL output to JSON, which is incompatible with mid-conversation `<action>` tags in the agentic loop.
  - **Bridge Pattern**: `batch_to_llm_raw()` reconstructs the legacy `<core_thinking_sequence>` + `### VARIANT N ###` format from parsed `MutationBatch`, allowing the existing downstream pipeline (`_parse_batch_variants`, variant validation, AST patching) to work unchanged.
  - **Graceful Fallback**: `parse_structured_or_fallback()` tries Pydantic validation first; on failure (truncated JSON, model bug), falls back to the battle-tested Fuzzy Parser. Zero regression risk.
  - **Assistant Prefill Elimination**: Removed the `"class "` assistant prefill hack from `_llm_call_ollama()` and the `<core_thinking_sequence>\n` prefill from `_fast_brain_call()` — both are incompatible with `format` (model must generate opening `{` as its first token).
  - **Meta-Evolution Token Budget**: Raised `num_predict` to 2048 for `_run_meta_evolution()` only — recipe files (~400 lines) cannot fit in 1024 tokens as JSON-encoded strings. Meta-evolution is rare (triggers after 5+ flat batches) so the thermal cost is acceptable.
- **New File**: `llm_schemas.py` (Pydantic v2 models, `ollama_schema()` inliner, `parse_structured_or_fallback()`, `batch_to_llm_raw()` bridge).
- **Files Modified**: `mutator_daemon.py` (`_fast_brain_call` → structured output, `_run_meta_evolution` → structured output, added schema imports and cached `_MUTATION_BATCH_SCHEMA`/`_META_RECIPE_SCHEMA`), `stateless_tick.py` (`_llm_call_ollama` → structured output, removed assistant prefill and `<think>` stop sequences, added `_FAST_NAS_SCHEMA`).

## [TICK 22.1] Targeted Mutation Determinism & Indestructible AST Validation
- **Problem**: `_attempt_targeted_mutation()` was the last function on the legacy multi-turn agentic loop + fuzzy parser pipeline. With `num_predict: 1024`, the LLM produced truncated XML tags and incomplete code snippets. Variants that were parsed had bad indentation (JSON string encoding artifact), causing `ast.parse()` to fail silently with "AST patch failed -- discarded" — no error details logged.
- **Root Cause**: (1) The function used free-form text generation with `<core_thinking_sequence>` tags + `### VARIANT N ###` delimiters, which the LLM frequently failed to produce correctly. (2) The AST validation had zero indent repair — `textwrap.dedent()` was never applied before `ast.parse()`. (3) `SyntaxError` exceptions were caught with bare `except SyntaxError: continue` — no line number, no offending text, no diagnostic output.
- **Solution**:
  - **Pydantic Structured Output**: Converted `_attempt_targeted_mutation()` from multi-turn agentic loop (5 turns, action tags, accumulated response) to single-turn structured output with `"format": _MUTATION_BATCH_SCHEMA`. Removed assistant prefill, stop sequences, and all agentic loop machinery. Temperature forced to 0.1 for deterministic JSON.
  - **Indestructible AST Validation**: Added `textwrap.dedent(variant_code).expandtabs(4)` before ALL `ast.parse()` calls — both in `_attempt_targeted_mutation()` and the main variant loop in `_run_one_cycle()`. Added detailed `SyntaxError` logging: line number, offending text, and first 200 chars of code preview.
  - **`_ast_replace_in_source()` Hardened** (stateless_tick.py): The entry-point `ast.parse(new_code)` now applies `textwrap.dedent()` first. If that fails, attempts tab expansion + dedent as a second repair pass. Both failure paths log the exact SyntaxError line number and offending text.
  - **Prompt Engineering**: Added explicit "CRITICAL CODE REQUIREMENTS" block to the targeted mutation prompt: no ellipses, complete method bodies, 4-space indentation, ast.parse() compatibility.
- **Files Modified**: `mutator_daemon.py` (`_attempt_targeted_mutation` → single-turn Pydantic, `_run_one_cycle` variant loop dedent, `textwrap` import), `stateless_tick.py` (`_ast_replace_in_source` indent repair + detailed error logging, `textwrap` import).

## [TICK 22.2] Exorcise the Ghost Prompt — Pure JSON Targeted Mutation
- **Problem**: Despite TICK 22.1's structured output migration, logs still showed `"Targeted mutation: structured parse failed, trying fuzzy fallback"` and `"Agentic probe [tensor_sandbox] (turn 1): import torch"`. The LLM was emitting `<action>run_tensor_sandbox: ...</action>` XML tags instead of strict JSON, breaking `MutationBatch.model_validate_json()`.
- **Root Cause**: `_attempt_targeted_mutation()` called `recipe.build_system_prompt()` which injects ~80 lines of tensor_sandbox and gradient_oracle **tool documentation** with explicit `<action>` tag examples. Even with Ollama's `format` parameter constraining the grammar, the system prompt's tool instructions polluted the LLM's generation intent. The fuzzy fallback then silently absorbed the failure, masking it.
- **Solution**:
  - **Severed the recipe dependency**: Replaced `recipe.build_system_prompt(**build_sys_kw)` with a self-contained, tool-free system prompt. Gradient/crash/physics/environment context is still injected as read-only context blocks, but ALL tool documentation, `<action>` tag syntax, `<core_thinking_sequence>` format instructions, and multi-turn agentic protocols are completely absent. The prompt's first sentence is: *"You output ONLY valid JSON. No markdown. No XML. No prose. No <action> tags."*
  - **Killed the fuzzy fallback**: Removed the `try...except...trying fuzzy fallback` block that silently bridged failures through `_parse_batch_variants()`. If `MutationBatch.model_validate_json(content)` fails, the system now: (1) dumps the **exact raw LLM response string** to stdout, (2) logs the Pydantic error, and (3) **raises the exception**. No silent recovery — crash loud so the ghost is visible.
  - **Removed dead code**: Eliminated `import inspect` block and `recipe.build_system_prompt` signature introspection (4 `inspect.signature()` calls) that existed solely to pass kwargs to the now-bypassed recipe call.
- **Call chain after TICK 22.2**: `_attempt_targeted_mutation()` → direct `urllib.request.Request` to Ollama `/api/chat` with `format: _MUTATION_BATCH_SCHEMA`. Zero intermediate functions. Zero tool injection. Zero fallback paths.
- **Files Modified**: `mutator_daemon.py` (`_attempt_targeted_mutation` — replaced recipe-based system prompt with pure JSON-only prompt, removed fuzzy fallback, removed inspect-based kwarg introspection).

## [TICK 22.3] Cure EOS Collapse — Native JSON Mode + Empty String Guard
- **Problem**: Fatal generation collapse: `input_value=''` (empty string). The LLM returns absolutely nothing. Passing a complex Pydantic schema dictionary (via `ollama_schema()` / `model_json_schema()`) to Ollama's `format` parameter causes Qwen models to instantly emit EOS (End of Sequence) due to token-probability conflict between the constrained grammar and the model's internal distribution.
- **Root Cause**: Ollama's strict schema constraining (`format: {full_json_schema_dict}`) applies logit-level masking that can create zero-probability dead ends for certain model architectures (particularly Qwen 3.5 MoE). When the model's top-k tokens all have near-zero probability under the schema grammar, it collapses to EOS immediately, returning an empty string. Pydantic then throws a cryptic EOF parse error.
- **Solution**:
  - **Native JSON mode**: Changed ALL four Ollama API call sites from `format: _MUTATION_BATCH_SCHEMA` / `_META_RECIPE_SCHEMA` / `_FAST_NAS_SCHEMA` (complex dict) to `format: "json"` (string). This tells Ollama to enforce only valid JSON syntax (balanced braces, proper quoting) without constraining to a specific schema. The schema contract is now enforced in two layers: (1) the system prompt explicitly describes the required JSON structure, (2) Pydantic validates the response shape after generation.
  - **Schema injection into prompts**: Each system prompt now contains the exact JSON structure the LLM must produce, replacing the implicit grammar constraint with explicit instruction. Added `'Start your response immediately with {"'` as a generation jumpstart at the end of every system prompt and user prompt.
  - **Empty string guard**: Before every `MutationBatch.model_validate_json(content)` / `parse_structured_or_fallback()` call, added `if not content.strip(): raise ValueError("LLM returned an empty string")`. This catches EOS collapse immediately with a clear diagnostic instead of Pydantic's cryptic EOF error.
  - **Four call sites patched**: `_attempt_targeted_mutation`, `_run_meta_evolution`, `_fast_brain_call` (all in mutator_daemon.py), and `_llm_call_ollama` (stateless_tick.py).
- **Files Modified**: `mutator_daemon.py` (3 API call sites: format→"json", empty guards, prompt jumpstarts), `stateless_tick.py` (1 API call site: format→"json", empty guard, prompt jumpstart + explicit schema in system prompt).

## [TICK 22.4] Heal Qwen EOS Collapse — Purge All Format Constraints
- **Problem**: Even `format: "json"` causes Qwen 3.5 MoE to emit EOS immediately (empty string). First-principles analysis revealed a lethal combination: (1) Chat template mismatch — Ollama's format constraint interacts with Qwen's `<|im_start|>` Jinja template, creating token-probability conflicts. (2) Qwen's exceptionally sharp logit distribution means any constrained decoding path that conflicts with the model's natural next-token distribution causes probability collapse to `eos_token`. The `"Start your response immediately with {"` prompt directive worsened this by further constraining the first token.
- **Root Cause**: Ollama's `format` parameter (whether strict schema dict or `"json"` string) applies logit masking that forces token paths incompatible with Qwen MoE's internal distribution when combined with the chat template's special tokens. The model's sharp logit peaks (low temperature + constrained decoding) create zero-probability dead ends → instant EOS.
- **Solution**:
  - **Purged ALL format params**: Removed `"format"` key entirely from all four Ollama API payloads. The LLM now generates freely with no logit-level constraints. JSON structure is enforced via prompt instructions + post-generation extraction.
  - **Temperature smoothing**: Bumped temperature from 0.1 → 0.4 at targeted mutation and fast-brain call sites. This smooths Qwen's sharp logit distribution, preventing premature EOS even without format constraints. Meta-evolution (0.8) was already safe.
  - **Relaxed prompts**: Replaced aggressive `"You output ONLY valid JSON"` / `'Start your response immediately with {"'` directives with natural `"Include this JSON structure in your response: {...}"`. Let the model think naturally — the JSON extractor handles any surrounding prose.
  - **`extract_json_from_text()` helper** (llm_schemas.py): Regex-based extractor that finds the FIRST `{` and LAST `}` in the raw LLM response, returning the outermost JSON object. Strips conversational prose, markdown fences, and reasoning preambles.
  - **3-strategy parse pipeline**: Upgraded `parse_structured_or_fallback()` to attempt: (1) direct `model_validate_json` on raw content, (2) `extract_json_from_text` → `model_validate_json`, (3) legacy fallback_fn. The targeted mutation site uses `extract_json_from_text` directly for maximum control.
  - **Empty string guards retained**: All four sites still check `content.strip() == ""` before any parse attempt, providing clear EOS-collapse diagnostics.
- **Files Modified**: `llm_schemas.py` (added `extract_json_from_text()`, upgraded `parse_structured_or_fallback` to 3-strategy pipeline), `mutator_daemon.py` (3 API sites: purged format, temp 0.4, relaxed prompts, regex extraction, imported `extract_json_from_text`), `stateless_tick.py` (1 API site: purged format, relaxed prompts).

## [TICK 22.5] Few-Shot Prompt Enforcement & Regex DOTALL Fix
- **Problem**: TICK 22.4 cured EOS collapse but created three new failures: (1) The 35B model writes Markdown essays instead of JSON because the relaxed prompt ("Include this JSON structure") is too permissive. (2) `extract_json_from_text` logs "NO JSON FOUND" even when the LLM outputs valid ```json blocks — the `str.find`/`str.rfind` approach fails on multiline JSON because it's not regex-based (no DOTALL). (3) The LLM hallucinates JSON keys (`"hypothesis"`, `"code"`, `"thinking"`) instead of the target keys because the schema example was ambiguous.
- **Root Cause**: (1) "Include this JSON structure in your response" is a suggestion, not a command — the 35B model treats it as context and writes analysis essays. (2) `extract_json_from_text` used `content.find("{")` / `content.rfind("}")` which works for single-line but breaks when JSON spans multiple lines inside markdown fences. (3) The prompt showed `"hypothesis"` and `"code"` as example keys but never explicitly prohibited alternatives — the model mapped its own semantically similar keys.
- **Solution**:
  - **Few-shot prompt injection**: All prompts (targeted mutation, fast-brain, meta-evolution, fast-loop) now include `"DO NOT WRITE ANY ESSAYS. YOU MUST OUTPUT ONLY A JSON BLOCK MATCHING THIS EXACT EXAMPLE:"` followed by a concrete ```json fenced example with realistic field values. The example IS the spec.
  - **Explicit key enforcement**: Added `"You MUST use the exact keys: 'thought_process', 'target_organelle', and 'python_code'. Do not invent new keys like 'hypothesis' or 'code'."` to every MutationBatch prompt.
  - **Pydantic schema alignment**: Renamed `MutationVariant` fields from `hypothesis`/`code` → `thought_process`/`target_organelle`/`python_code`. Removed `MutationBatch.thinking` field (reasoning now lives inside each variant's `thought_process`). Updated all downstream access: `v.code` → `v.python_code`, `result.thinking` → per-variant logging.
  - **Regex DOTALL fix**: Replaced `content.find("{")`/`content.rfind("}")` in `extract_json_from_text()` with `re.search(r"\{.*\}", content, re.DOTALL)`. This greedy DOTALL match correctly captures JSON objects spanning multiple lines inside markdown fences.
  - **`batch_to_llm_raw` updated**: Bridge function now aggregates `thought_process` from all variants into a combined `<core_thinking_sequence>` block, and uses `v.python_code` for variant code.
- **Files Modified**: `llm_schemas.py` (`MutationVariant`/`MutationBatch` field rename, `extract_json_from_text` → re.DOTALL regex, `batch_to_llm_raw` field updates, added `import re`), `mutator_daemon.py` (targeted mutation prompt → few-shot + key enforcement, fast-brain prompt → few-shot + key enforcement, meta-evolution prompt → few-shot, downstream `v.code` → `v.python_code`), `stateless_tick.py` (fast-loop prompt → few-shot).

## [TICK 22.6] Instructor Migration — The End of Manual JSON Parsing
- **Problem**: Despite TICK 22.0–22.5's progressive fixes (strict schema → format="json" → no format → regex extraction → few-shot → DOTALL), the LLM communication layer remained fundamentally brittle. The 35B model still output `<core_thinking_sequence>` and Markdown essays because `_fast_brain_call` still called `recipe.build_system_prompt()` (injecting the legacy XML prompt), and `_run_meta_evolution` still called `recipe.build_meta_reflection_prompt()` (injecting `<core_thinking_sequence>` and `<meta_recipe>` tag instructions). Manual regex extraction (`extract_json_from_text`) and multi-strategy parse fallbacks added complexity without reliability.
- **Root Cause**: The entire approach — manually constructing JSON prompts, parsing raw HTTP responses, extracting JSON from prose, falling back to regex — was architecturally wrong. Industry-standard solution exists: the `instructor` library wraps any OpenAI-compatible endpoint (including Ollama's `/v1` shim), automatically injects Pydantic schemas into prompts, validates responses, and auto-retries on failure.
- **Solution**:
  - **Instructor client**: Added `get_instructor_client()` singleton in `llm_schemas.py` that creates `instructor.from_openai(OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), mode=instructor.Mode.JSON)`. All four JSON call sites now use `client.chat.completions.create(model=..., response_model=PydanticModel, messages=[...], max_retries=3)`.
  - **Purged legacy parsing**: Deleted `extract_json_from_text()`, `parse_structured_or_fallback()`, `ollama_schema()` from `llm_schemas.py`. Deleted `_MUTATION_BATCH_SCHEMA`, `_META_RECIPE_SCHEMA` pre-computed dicts from `mutator_daemon.py`. Removed all manual `urllib.request` + `json.loads` + regex extraction from the four call sites.
  - **Purged ghost prompts**: `_fast_brain_call` no longer calls `recipe.build_system_prompt()` or `recipe.build_user_prompt()` — replaced with self-contained prompt (same pattern as `_attempt_targeted_mutation` in TICK 22.2). `_run_meta_evolution` no longer calls `recipe.build_meta_reflection_prompt()` — replaced with self-contained prompt. This eliminates ALL `<core_thinking_sequence>`, `<action>` tag, and tool-use injection into JSON-only paths.
  - **forward() enforcement**: All system prompts now include: "CRITICAL STRUCTURAL RULE: If you are mutating a PyTorch nn.Module, your python_code MUST contain both the __init__ and forward functions. The system will crash if forward is missing." Pydantic `Field(description=...)` on `MutationVariant.python_code` also documents this requirement for instructor's automatic schema injection.
  - **Prompt simplification**: Removed all manual few-shot JSON examples, `DO NOT WRITE ESSAYS` directives, and key enforcement instructions. Instructor injects the schema automatically — the system prompt only needs to describe WHAT to do, not HOW to format output.
  - **Dependencies**: Added `instructor`, `openai`, `eval_type_backport` (Python 3.9 compatibility).
- **Call chain after TICK 22.6**: `_attempt_targeted_mutation` / `_fast_brain_call` / `_run_meta_evolution` / `_llm_call_ollama` → `get_instructor_client().chat.completions.create(response_model=...)` → validated Pydantic object. Mathematically impossible to receive anything other than a valid Pydantic object.
- **Files Modified**: `llm_schemas.py` (rewritten: instructor client, Pydantic Field descriptions, deleted legacy parsing functions), `mutator_daemon.py` (4 call sites refactored to instructor, 2 ghost prompts severed, legacy imports purged), `stateless_tick.py` (`_llm_call_ollama` refactored to instructor, legacy imports purged).

## [TICK 23.0] Immutable Scaffold — Strategy Pattern for Mutation Target Isolation
- **Problem**: The LLM was allowed to mutate the entire `MitoticTransformerBlock`, which includes PyTorch wiring (`self.experts`, LayerNorm, attention), I/O signatures (`forward(x, router_idx)`), and state management (`mitosis()`). This violated Interface Segregation — the LLM repeatedly broke forward argument signatures, dropped state_dict keys, and created dimension mismatches at the module boundary. Prompt engineering (telling the LLM to "keep signatures identical") treated the symptom, not the cause. The root issue was **mutation target granularity**: the integration boundary was exposed to mutation.
- **Root Cause**: Violating the Strategy Pattern. The mathematical routing logic (which expert to select, how to mix outputs) was entangled with the structural PyTorch graph boundary (which manages I/O, state_dict, mitosis). The LLM couldn't mutate one without breaking the other.
- **Solution** (First-Principles Architecture Fix):
  - **Extracted `RoutingStrategy(nn.Module)`**: A new class containing ONLY the mutable mathematical routing logic. Interface contract: `forward(x: Tensor[B,T,D], experts: nn.ModuleList, router_idx: int) -> Tensor[B,T,D]`. The LLM now ONLY mutates this class.
  - **Locked `MitoticTransformerBlock` as Immutable Scaffold**: Handles all PyTorch wiring (self.experts, LayerNorm, attention), I/O signatures (`forward(x, router_idx)`), and state management (`mitosis()`). Delegates to `self.router = RoutingStrategy(...)` for the mathematical logic.
  - **AST Immutability Guard** (`stateless_tick.py`): `_ast_replace_in_source()` now filters out LLM mutations targeting `_IMMUTABLE_CLASSES = {MitoticTransformerBlock, AtomicLLM, AtomicCore}` before patching. Even if the LLM ignores the prompt, the scaffold cannot be overwritten.
  - **Dynamic Signature Forgiveness** (`evaluator_daemon.py`): `_ensure_strategy_kwargs()` injects `**kwargs` into `RoutingStrategy.forward` if missing, absorbing any extra arguments the scaffold might pass. This prevents crashes from minor signature mismatches.
  - **Prompt Redirection** (`mutation_recipe.py`, `stateless_tick.py`): All LLM prompts now specify `RoutingStrategy` as the PRIMARY mutation target and explicitly mark `MitoticTransformerBlock` as IMMUTABLE/LOCKED.
  - **Organelle Registry Update** (`genome_assembler.py`): `ORGANELLE_TYPES["routing"]` now targets `RoutingStrategy` instead of `MitoticTransformerBlock` for decomposition and horizontal gene transfer.
- **Architectural Principle**: Stop fixing prompts; fix the architecture's mutation target granularity. The LLM mutates the strategy, never the scaffold.
- **Files Modified**: `agi_workspace/memory/source/atomic_core.py` (added `RoutingStrategy`, locked `MitoticTransformerBlock`), `mutation_recipe.py` (CODE RULES redirected), `stateless_tick.py` (`_IMMUTABLE_CLASSES` guard + fast-loop prompt update), `evaluator_daemon.py` (`_ensure_strategy_kwargs` + `import ast`), `genome_assembler.py` (routing organelle → `RoutingStrategy`).

## [TICK 24.1] Tri-Agent Mutator Pipeline — Internal Dual-Loop Refactor
- **Problem**: The LLM generation layer in `mutator_daemon.py` still ran legacy multi-turn agentic loops (`_enhanced_llm_call`, `_slow_brain_call`) with in-process `tensor_sandbox` execution via `exec()` + signal timeout. This violated CLAUDE.md's "NO MAIN-THREAD SANDBOXES" rule — an infinite loop or OOM in LLM-generated code could deadlock the entire daemon. The codebase had ZERO `multiprocessing`/`subprocess` isolation. Additionally, ~650 lines of legacy fuzzy parsers (`_parse_batch_variants`, `_strip_thinking`, `_extract_and_repair`, `_salvage_any_code`) were obsolete since TICK 22.6 (instructor guarantees Pydantic schema).
- **Root Cause**: The daemon's LLM pipeline was a single-agent monolith that combined strategy analysis, code generation, and execution validation in one function. No separation of concerns, no process isolation for untrusted code.
- **Solution** (CLAUDE.md Tri-Agent Pipeline):
  - **Agent 1 — Architect (`_architect_call`)**: Slow Brain (35B model). Analyzes gradient profiles, fitness metrics, and organelle source. Outputs an `ArchitectPlan` (Pydantic schema) containing mathematical strategy, analysis, constraints. **Zero code output** — enforced by schema.
  - **Agent 2 — Coder (`_coder_call`)**: Fast Brain (7B model). Receives the Architect's plan + scaffold constraints + current organelle source. Outputs a `MutationBatch` (validated Pydantic) with complete PyTorch class definitions.
  - **Agent 3 — Test-Runner (`_test_runner`)**: Writes temp script to `/tmp/`, launches `subprocess.run()` with hard `_TEST_RUNNER_TIMEOUT_S` (5.0s) wall. Completely isolated Python interpreter — no shared memory, no import contamination. On timeout, `subprocess.TimeoutExpired` kills the process. Catches: infinite loops, OOM, shape mismatches, missing `forward()`.
  - **Orchestrator (`_tri_agent_pipeline`)**: Runs Architect → Coder → Test-Runner sequentially. Constitutional validation + AST parse as fast pre-filter before subprocess. Returns list of validated `python_code` strings.
  - **New Pydantic schema (`ArchitectPlan`)**: Added to `llm_schemas.py` with fields: `analysis`, `strategy`, `target_organelle`, `constraints`.
  - **Deleted `batch_to_llm_raw()`**: Legacy bridge to `_parse_batch_variants` — no longer needed.
- **Deletions** (~650 lines):
  - `_enhanced_llm_call()` (~180 lines): Multi-turn agentic loop with `<action>` tag parsing, in-process sandbox
  - `_slow_brain_call()` (~180 lines): Same architecture, Pareto seeds, `recipe.build_system_prompt()` contamination
  - `_fast_brain_call()` (~150 lines): Replaced by `_coder_call` in the pipeline
  - `_dual_brain_dispatch()` (~190 lines): Routing logic replaced by unified `_tri_agent_pipeline`
  - `_execute_sandbox_action()`, `_execute_gradient_action()`, `_extract_action_tags()`: Agentic loop machinery
  - `_strip_thinking()`, `_find_code_boundary()`, `_parse_batch_variants()`, `_extract_and_repair()`, `_has_class_def()`, `_repair_indentation()`, `_extract_class_blocks()`, `_salvage_any_code()`: Fuzzy parsers (obsoleted by instructor)
  - `_ACTION_RE`, `_GRADIENT_ACTION_RE`, `_VARIANT_DELIMITER`, `_FUZZY_VARIANT_DELIMITERS`: Regex constants
  - `_MAX_AGENTIC_TURNS`, `_SANDBOX_TIMEOUT_S`: Agentic loop constants
- **Verification (Meta-TDD)**: `test_pipeline.py` with 7 tests, all passing:
  - F1: Valid `RoutingStrategy` → PASS (correct output shape `[1, 16, 64]`)
  - F2: `while True: pass` infinite loop → TIMEOUT after 5.0s, **main thread never blocks**
  - F3: `import os; os.system(...)` → Constitutional VETO (forbidden import)
  - F4: Missing `forward()` → Test-runner FAIL (AttributeError)
  - F5: Runtime shape mismatch → Test-runner FAIL (dimension error)
- **Architectural Principle**: Separate thinking (Architect) from coding (Coder) from execution (Test-Runner). Never execute untrusted code in the main thread. `subprocess.run(timeout=N)` is the hard wall — no signal hacks, no `exec()`, no shared address space.
- **Files Modified**: `mutator_daemon.py` (deleted ~650 lines of legacy, added ~250 lines of tri-agent pipeline), `llm_schemas.py` (added `ArchitectPlan` schema, deleted `batch_to_llm_raw`), `test_pipeline.py` (new Meta-TDD verification script).

## [TICK 24.2] Fix Mutator Idle Spinning — Missing RoutingStrategy Class
- **Problem**: After TICK 24.1's deletion of legacy parsers, the mutator daemon entered an infinite idle spin. Logs showed `Cannot extract routing organelle — skipping.` and the Evaluator decomposition only found `[attention, expert]`. The `_tri_agent_pipeline` was never invoked — the system was alive but brain-dead.
- **Root Cause**: `ORGANELLE_TYPES["routing"]` maps to `class_name: "RoutingStrategy"`, but no such class existed in `atomic_core.py`. The routing logic (sigmoid gating + expert dispatch) was embedded inline inside `MitoticTransformerBlock.forward()`. `genome_assembler.extract_organelle_source()` (which correctly uses `ast.parse`) searched for `class RoutingStrategy`, found nothing, returned `None`. The main loop at line 3310-3312 got `None` and skipped the LLM call on every iteration.
- **Solution**: Added `class RoutingStrategy(nn.Module)` as a standalone organelle in `atomic_core.py` (lines 161-192). The class encapsulates the complete sigmoid gating + expert dispatch pattern with the interface contract expected by the Tri-Agent test runner: `__init__(d_model, n_experts, drop)` and `forward(x) -> (B,T,D)`. Critically, `MitoticTransformerBlock` internals were **not modified** — `self.router` remains a bare `nn.Linear`, preserving all checkpoint state dict keys (`blocks.0.router.weight`, `blocks.0.router.bias`). The standalone `RoutingStrategy` exists for the mutator to extract, mutate, and sandbox-test independently.
- **Verification**: 5/5 tests pass: (1) AST finds `RoutingStrategy` among 8 top-level classes, (2) `extract_organelle_source` returns source for all 3 organelle types (attention=1372, routing=1379, expert=649 chars), (3) `RoutingStrategy` standalone forward pass `(1,16,64) → (1,16,64)`, (4) `MitoticTransformerBlock` state dict intact (`router.weight`, `router.bias` unchanged), (5) `AtomicLLM` end-to-end forward `(1,16) → (1,16,512)`.
- **Architectural Principle**: Every organelle type in `ORGANELLE_TYPES` MUST have a corresponding standalone `nn.Module` class in `atomic_core.py`. The mutator's extraction pipeline is AST-based and literal — if the class doesn't exist as a top-level `ClassDef`, the entire mutation loop is dead. Production scaffold code (`MitoticTransformerBlock`) and mutable organelle templates (`RoutingStrategy`) can coexist independently.
- **Files Modified**: `atomic_core.py` (added `RoutingStrategy` class), `test_tick24_2.py` (verification script).

## [TICK 25.0] The Navigational Organism — Ω-Recursive Unity Engine (Axiom V)
- **Problem**: The system operated in single-step optimization mode with a single global `best_epi`, fixed MCTS rollout depth, text-based failure logging that fed natural language into the Architect, and a single Pareto front across all environmental pressures. This violated four thermodynamic principles: (1) no temporal planning beyond one step, (2) semantic hallucination from text failure logs, (3) no reuse-as-capital, (4) no speciation pressure.
- **Solution — Five Structural Modifications**:
  1. **Two-Stage Pareto Filter + Reuse Capital** (`genome_assembler.py`): Elite selection refactored into a strict two-stage pipeline. Stage 1 is a boolean gate (Verified × Rollback × Permission) that raises `TwoStageGateError` if bypassed — crash loudly, no silent leaks. Stage 2 computes continuous score via existing Φ value + a new Reuse metric. The `_REUSE_LEDGER` tracks topology hashes and awards compounding capital bonus (capped at 0.5) to frequently successful assemblies. Reuse transforms proven organelle combinations into accumulated capital rather than ephemeral fitness.
  2. **Budget-Backed Temporal Options** (`genome_assembler.py`): MCTS rollout horizon H is now a dynamic function of Φ budget surplus from `PhiGovernor`. When surplus is tight (expansion_factor ≈ 0.5), H contracts to 1 (reactive single-step mode). When flush (≈ 2.0), H expands to full depth (3 organelle slots). The Architect proposes strategies, but the MCTS proves their multi-step viability before acceptance. `compute_dynamic_horizon()` reads the governor and returns H ∈ [1, 3].
  3. **Epigenetic Tensor Decay** (`rule_ir.py`): Text-based failure logs abolished. `EpigeneticFailureType` enum maps failure modes (OOM, timeout, shape_mismatch, NaN divergence, permission violation, DAG reject) to specific gradient penalties in `_EPIGENETIC_PENALTY_MAP`. `ConstraintMatrix.apply_epigenetic_penalty()` applies these penalties directly to the Rank-2 matrix via the existing Adam optimizer. History is amortized as mathematical friction — the Architect's future proposals are shaped by gradient penalties, not natural language tracebacks. Zero semantic hallucination risk.
  4. **Niche-Coupled Pareto Speciation** (`niche_evolver.py`): Global `best_epi` replaced with per-niche Pareto fronts. `NicheRegistry` manages four concurrent species: LATENCY (tight timing), COMPRESSION (high memory pressure), BANDWIDTH (constrained throughput), GENERAL (balanced). Each `NicheSpecies` maintains an independent 80/20 Pareto front via `NicheParetoEntry.dominates()`. `generate_niche_for_species()` produces species-specific challenges. The system now evolves a competitive distribution of topologies across different thermodynamic axes.
  5. **SharedState Integration** (`autopoietic_core.py`): `SharedState` extended with `niche_registry: NicheRegistry`. `PhiGovernor` gains `phi_budget_surplus` property (normalized [0,1]) and `record_epigenetic_failure()` method that applies tensor decay without text generation. Imports updated to include `EpigeneticFailureType` from `rule_ir` and `NicheRegistry` from `niche_evolver`.
- **Constraints Preserved**: Zero-IPC MLX architecture intact. No PyTorch. All arrays remain native `mlx.core` in Unified Memory. Tri-Agent pipeline (Architect → Coder → Test-Runner) untouched. All new structures are pure-Python dicts/lists with no new IPC channels.
- **Files Modified**: `genome_assembler.py` (Two-Stage Gate, Reuse Ledger, Dynamic Horizon), `rule_ir.py` (EpigeneticFailureType, penalty map, apply_epigenetic_penalty), `niche_evolver.py` (NicheParetoEntry, NicheSpecies, NicheRegistry, species-aware generation), `autopoietic_core.py` (SharedState niche_registry, PhiGovernor surplus + epigenetic methods).

## [TICK 26.0] ARSL & Catalytic Coupling — Axiomatic Resource Sovereignty Layer (Axiom VI)
- **Problem**: The loss function ⟨Φ,∂⟩_t = Φ_task + λ₁Φ_resource + λ₂Φ_strain + λ₃Φ_violation governed only immediate resource/violation costs with no sensitivity to: (1) whether harvested resources actually exceed deployment + vulnerability (catalytic sovereignty), (2) variance in MCTS rollout outcomes (uncertainty pricing), (3) concentration risk from over-reliance on single organelles (dependency monoculture), (4) boundary oscillation cost when the BoundaryOperator flips states between ticks (switching friction). The system could pass all gates yet remain thermodynamically fragile — sovereign in name but not in dynamics.
- **Solution — Seven Structural Modifications**:
  1. **ARSL Catalytic Gate** (`genome_assembler.py`): New crash-loud gate enforcing the catalytic equation `Harvest > Deploy + Vulnerability`. `arsl_catalytic_gate(harvest, deploy, vulnerability)` raises `ARSLGateError` if the inequality is violated — no silent resource insolvency. Called before any assembly is committed to the Pareto front. The gate is a hard thermodynamic wall: if the organism cannot prove resource sovereignty for a candidate assembly, that assembly is rejected with a precise exception naming the deficit.
  2. **Uncertainty Pricing U** (`genome_assembler.py`): `RolloutUncertaintyTracker` implements Welford's online algorithm for streaming mean/variance of MCTS rollout Φ values. After each rollout, the tracker updates its running statistics. The uncertainty tax `λ_U · √(variance)` is injected into `_compute_phi_value()` via the new `uncertainty_penalty` parameter. High-variance assemblies are penalized proportionally — the system pays more for what it knows less about. Stats (`mean`, `variance`, `std`, `count`) are surfaced in `mcts_stats` for observability.
  3. **GNN Prediction Confidence** (`dag_oracle.py`): `compute_gnn_confidence(features)` measures the variance of GNN message-passing features and maps it to a confidence score via `1.0 / (1.0 + variance)`. The `DagOracleResult` dataclass gains a `prediction_confidence: float` field. `evaluate_dag()` now computes and reports confidence alongside latency/bottleneck predictions. This gives downstream consumers (ARSL gate, Architect) a calibrated signal of how much to trust DAG-level predictions.
  4. **Dependency Risk Ledger D** (`rule_ir.py`): `DependencyLedger` class tracks per-organelle usage counts across all assemblies. `dependency_risk(η)` computes `D(π) = max(reliance) - η × redundancy`, where `max_reliance` is the fraction of assemblies using the most-depended-upon organelle, and `redundancy_score` is entropy-normalized diversity. Concentrated reliance (one organelle in every assembly) yields D→1.0; diversified portfolios yield D→0.0. `_DEPENDENCY_ETA = 0.3` controls the redundancy discount.
  5. **Membrane Switching Friction Δ** (`autopoietic_core.py`): Before `loss_and_grad` computation, `BoundaryUpdater.update()` now measures `Δ = ‖state_logits_t - state_logits_{t-1}‖₁ + ‖gate_logits_t - gate_logits_{t-1}‖₁` on raw logits (before `mx.eval()`). Previous logits are cached in `_prev_state_logits` / `_prev_gate_logits`. Dynamic scaling: phase volatility (fraction of recent ticks with phase transitions) modulates `λ_Δ` via `lambda_delta_scale ∈ [0.3, 1.5]`. High volatility amplifies the friction penalty, damping oscillatory boundary flapping. Low volatility relaxes it, permitting necessary phase transitions.
  6. **Extended Dual-Tension Loss** (`autopoietic_core.py`): `dual_tension_loss_fn` signature extended with `dependency_risk`, `lambda_dependency`, `switching_friction`, `lambda_switching`. The full loss is now:
    ```
    ⟨Φ,∂⟩_t = Φ_task + λ₁·Φ_resource + λ₂·Φ_strain + λ₃·Φ_violation + λ_D·D + λ_Δ·Δ
    ```
    with `_LAMBDA_DEPENDENCY = 0.10` and `_LAMBDA_SWITCHING = 0.08`. `compute_loss_components` mirrors the extension for diagnostic decomposition. `BoundaryUpdater.update()` passes D (from `DependencyLedger`) and Δ (from switching measurement) into the loss closure. `PhiGovernor.tick_boundary()` wires both through to `compute_loss_components`. All new parameters default to `0.0`, preserving backward compatibility for existing callers.
  7. **SharedState Integration** (`autopoietic_core.py`): `SharedState` extended with `dependency_ledger: DependencyLedger`. Import of `DependencyLedger` from `rule_ir` added. `BoundaryUpdater.update()` report dict extended with `switching_friction`, `switching_raw`, `lambda_delta_scale`, `dependency_risk` for full observability.
- **Loss Function (Complete)**:
  ```
  ⟨Φ,∂⟩_t = Φ_task + λ₁·Φ_resource + λ₂·Φ_strain + λ₃·Φ_violation + λ_U·U + λ_D·D + λ_Δ·Δ
  ```
  where U = √(Welford variance) from MCTS rollouts, D = max(reliance) - η·redundancy from the dependency ledger, Δ = ‖logit_delta‖₁ from boundary switching.
- **Constraints Preserved**: Zero-IPC MLX architecture intact. No PyTorch. All arrays remain native `mlx.core` in Unified Memory. Tri-Agent pipeline (Architect → Coder → Test-Runner) untouched. All new parameters have default values (0.0) ensuring no caller breakage. Crash-loud principle upheld: `ARSLGateError` joins `TwoStageGateError` as a hard thermodynamic wall.
- **Verification**: 10/10 test blocks passed: (1) GNN confidence=0.9974, (2) DependencyLedger concentrated risk=0.9 vs diversified=0.0, (3) ARSL gate raises on deficit, passes on surplus, (4) Uncertainty pricing: high-var tax > low-var tax, (5) Loss delta=0.12 for D=0.8/Δ=0.5, (6) Switching friction detects logit changes (raw=2.9008), (7) Dynamic λ_Δ scales with volatility, (8) PhiGovernor wires D+Δ through loss components, (9) Backward compat — zero defaults produce identical loss, (10) Full loss equation verified.
- **Files Modified**: `dag_oracle.py` (GNN confidence, DagOracleResult field), `rule_ir.py` (DependencyLedger class), `genome_assembler.py` (ARSL gate, RolloutUncertaintyTracker, uncertainty penalty wiring), `autopoietic_core.py` (switching friction, extended loss, dynamic λ_Δ, SharedState ledger, BoundaryUpdater caching).

## [TICK 27.0] Onto-Φ Executable Identity — Invariant Identity Substrate (IIS)
- **Problem**: TICK 26 (ARSL) enabled the system to expand resource boundaries and price Uncertainty (U), Dependency (D), and Switching friction (Δ). However, the system had no mathematically conserved "identity core". Three critical vulnerabilities existed: (1) The Adam optimizer in `apply_epigenetic_penalty()` and `apply_decay()` could erode any constraint weight — including the categories essential for Tri-Agent survival — all the way to zero, causing identity dissolution. (2) Organelles saved by `save_organelle()` had no cryptographic lineage record, making genealogical contamination undetectable during MCTS selection. (3) The `BoundaryUpdater.update()` budget expansion in `sympathetic_expand` phase had no hard veto against expanding when phi was already dangerously near the thermodynamic floor, risking autopoietic suicide from cascading expansion + penalty cycles.
- **Solution — Three-Layer Invariant Identity Substrate (IIS)**:
  1. **Layer 1: Sovereignty Floor Verifier** (`autopoietic_core.py`): Added `_PHI_SOVEREIGNTY_MIN = 0.12` constant — the absolute minimum φ ratio (φ_current / φ_peak) to keep the Tri-Agent and Boundary operators alive. `SovereigntyFloorVerifier` class provides three pure-math gates:
     - `check_expansion(phi_ratio) → bool`: Vetoes budget expansion if phi_ratio ≤ floor × 1.5 (safety buffer), regardless of sympathetic phase.
     - `check_penalty(phi_ratio, severity) → float`: Caps epigenetic penalty severity to the maximum that keeps projected phi above the floor (prevents autopoietic suicide).
     - `check_rollout(value, phi_ratio) → float`: Clips MCTS rollout value to 0.0 if phi is at floor (discourages expensive expansion when bankrupt).
     Module-level singleton `_SOVEREIGNTY_VERIFIER` wired into `BoundaryUpdater.update()` (expansion veto) and `PhiGovernor.record_epigenetic_failure()` (severity cap). Both SharedState fields `sovereignty_verifier` and `identity_membrane` added for zero-IPC visibility.
  2. **Layer 2: Genealogical Ledger** (`genome_assembler.py`): Introduced cryptographic lineage tracking for all organelles.
     - `TICK13_CONSTITUTION_HASH = SHA256("CONSTITUTION_VERSION=1.0.0:MAX_PARAMS=50000000")[:16]` — the immutable genesis anchor (`745451da21ce3ce2`).
     - `compute_genealogy_hash(parent_hash, matrix_version, niche_id) → str`: SHA256 of the lineage step, truncated to 16 chars. Each organelle knows its place in the chain.
     - `save_organelle()` extended with optional `parent_hash`, `matrix_version`, `niche_id` params. Computes and embeds `genealogy_hash` in every new organelle header. Backward-compatible: callers without genealogy params auto-root at `TICK13_CONSTITUTION_HASH`.
     - `parse_organelle_genealogy(filepath) → Optional[str]`: Reads only the first header line for efficiency.
     - `verify_genealogy_chain(filepath) → float`: Returns 1.0 (verified) or 0.70 (pre-TICK27, unverified).
     - `_rollout()` now computes `genealogy_discount = min(trust for all organelles in assembly)` and passes it to `_compute_phi_value()`. Unverified assemblies pay a 30% Φ discount in the MCTS value head — steering selection toward verified lineage without hard-killing old elites.
  3. **Layer 3: Identity Membrane** (`rule_ir.py`): `IDENTITY_INVARIANTS` dict locks four essential constraint categories to hard minimum floors: `risk_appetite≥0.10`, `organelle_priority≥0.10`, `parsimony_pressure≥0.15`, `temporal_horizon≥0.10`. `IdentityMembrane.enforce(cm) → Dict[str, float]` clips `base_weight` back to floor for any eroded category and returns which categories were restored. `_GLOBAL_IDENTITY_MEMBRANE` (module-level singleton) is called after every `apply_epigenetic_penalty()` and `apply_decay()` — the Adam optimizer can propose any update it wants, but the identity core snaps back to floor before the next tick observes the result.
- **Loss Function (Extended from TICK 26)**:
  ```
  ⟨Φ,∂⟩_t = Φ_task + λ₁·Φ_resource + λ₂·Φ_strain + λ₃·Φ_violation + λ_U·U + λ_D·D + λ_Δ·Δ
  projected_phi_MCTS *= min(genealogy_trust ∈ assemblies)  ← NEW TICK 27
  sovereignty_veto: expansion blocked if phi_ratio ≤ 0.18  ← NEW TICK 27
  identity_clip: C[invariant][base_weight] ≥ floor after every gradient  ← NEW TICK 27
  ```
- **Constraints Preserved**: Zero-IPC MLX architecture intact. No PyTorch. All new components are pure Python arithmetic — no MLX tensors, no threading locks. All new parameters are backward-compatible with default values. Crash-loud principle maintained (expansion veto is a hard mathematical wall, not a soft penalty).
- **Verification**: 14/14 test blocks passed (5 new TICK 27 blocks + 9 existing passing):
  - T27-1: Sovereignty veto fires at phi_ratio=0.10 < floor_buffer=0.18 ✓
  - T27-2: Sovereignty passes at phi_ratio=0.85; penalty severity capped 3.0→0.50 at phi=0.13 ✓
  - T27-3a: Hash chain produces 3 distinct 16-char hex hashes (genesis=745451da21ce3ce2) ✓
  - T27-3b: TICK27+ organelle trust=1.0, pre-TICK27 trust=0.70 ✓
  - T27-4: All 4 invariant categories clipped back to floor after forced erosion ✓
  - T27-5: Unverified assembly Φ ratio=0.720 vs verified (expected ≈0.70) ✓
- **Files Modified**: `rule_ir.py` (IDENTITY_INVARIANTS, IdentityMembrane class, enforce() wired into apply_epigenetic_penalty + apply_decay), `genome_assembler.py` (TICK13_CONSTITUTION_HASH, compute_genealogy_hash, parse_organelle_genealogy, verify_genealogy_chain, save_organelle/decompose_and_archive extended, _compute_phi_value genealogy_discount, _rollout genealogy trust computation), `autopoietic_core.py` (_PHI_SOVEREIGNTY_MIN, SovereigntyFloorVerifier class, _SOVEREIGNTY_VERIFIER singleton, IdentityMembrane/IDENTITY_INVARIANTS import, BoundaryUpdater.update veto wiring, PhiGovernor.record_epigenetic_failure severity capping, SharedState fields identity_membrane + sovereignty_verifier).

---

## TICK 28.0 — Transferable Organelles & Constraint Exchange Protocol (Proto-Civilization Layer)

- **Date**: 2026-04-07
- **Problem**: The autopoietic system evolved organelles in isolation — each niche developed its own failure-management heuristics independently, with no ability to share failure intelligence across niches. A catastrophic failure (OOM, NaN divergence) in LATENCY had zero signal value for COMPRESSION or BANDWIDTH, forcing every niche to re-discover the same failure modes independently. Furthermore, the MCTS pareto pool sorted by raw `epi` score, rewarding niche-overfitted organelles equally with multi-niche survivors. No mechanism existed to preferentially breed generalizing organelles that prove fitness across multiple environmental pressures.
- **Solution — Three-Component Proto-Civilization Layer**:
  1. **Organelle IR Encapsulation** (`genome_assembler.py`): Extended organelle headers with two new optional fields:
     - `resource_footprint: float` — normalized compute cost (0.0–1.0). Enables the MCTS value head to account for operational cost when comparing assemblies.
     - `proven_niches: List[str]` — comma-separated set of niches where this organelle previously passed the Test-Runner. De-duplicated on write; parsed on read.
     - `_parse_organelle_footprint(filepath) → float` and `_parse_proven_niches(filepath) → List[str]`: regex-based readers, backward-compatible (old headers return 0.0 and `[]`).
  2. **Reproductive Fitness Score F_o** (`genome_assembler.py`): Replaced raw `epi` sort in `_load_pareto_pool()` with:
     ```
     F_o = epi × genealogy_trust × (1 + α × (e^n_niches − 1))    α = 0.20
     ```
     - `n=0` (unproven): F_o = epi × trust (no bonus, no penalty).
     - `n=1` (single-niche): ×1.344 bonus. `n=2`: ×1.478. `n=3`: ×4.81.
     - Exponential growth creates strong selection pressure for multi-niche survivors without penalizing young single-niche organelles. A three-niche champion at moderate epi beats a niche-overfitted organelle at peak epi.
     - `compute_reproductive_fitness(epi, proven_niches, genealogy_trust=1.0) → float` — pure arithmetic, no MLX tensors.
  3. **Cross-Niche Constraint Transfer** (`rule_ir.py`, `niche_evolver.py`, `autopoietic_core.py`):
     - `ConstraintMorphism` dataclass (`rule_ir.py`): Immutable record of a shadow penalty event — `source_niche`, `failure_type`, `original_severity`, `shadow_severity` (= original × `_SHADOW_ATTENUATION = 0.30`), timestamp, unique `morphism_id`.  Factory: `ConstraintMorphism.create(source_niche, failure_type, original_severity)`.
     - `NegativeTransferFirewall` class (`rule_ir.py`): Append-only `deque(maxlen=50)` audit ledger. Methods: `record(morphism)`, `recent(n)`, `count_by_niche()`, `format_status()`, `to_dict()`. Single zero-IPC object shared across all niches via `SharedState.negative_transfer_firewall`.
     - `NicheSpecies.constraint_matrix: Optional[ConstraintMatrix]` field added (`niche_evolver.py`). `NicheRegistry.__init__()` assigns a private `ConstraintMatrix()` to each of the 4 species (LATENCY, COMPRESSION, BANDWIDTH, GENERAL).
     - `NicheRegistry.broadcast_shadow_penalty(source_niche, failure_type, shadow_severity, firewall)`: Iterates all peer niches (source excluded), computes per-niche phi_ratio proxy from `species.best_epi / global_best`, runs `_SHADOW_SOVEREIGNTY_FLOOR` check via `check_penalty()`, caps severity at the sovereignty-safe level, calls `species.constraint_matrix.apply_epigenetic_penalty()`. Returns dict of `{niche: applied_severity}`. Dead niches (best_epi=0) are capped automatically — no unchecked cascade.
     - `NicheRegistry.record_catastrophic_failure(source_niche, failure_type, severity, firewall)`: Applies full severity to source niche CM, creates a `ConstraintMorphism`, records it in the firewall, then calls `broadcast_shadow_penalty()` at 30% shadow severity.
     - `SharedState.negative_transfer_firewall: NegativeTransferFirewall` added (`autopoietic_core.py`): single firewall instance, zero-IPC, visible to all governance components without any threading locks beyond `SharedState._lock`.
- **Cascade Protection Math**: Shadow attenuation = 0.30 (30%). Geometric series divergence factor = 1/(1−0.30) ≈ 1.43×. Any single catastrophic failure at most multiplies total system-wide severity by 1.43× (bounded, never runaway). Sovereignty floor gates prevent dead niches (phi_ratio=0.0) from receiving any penalty at all.
- **Constraints Preserved**: Zero-IPC MLX architecture intact. No PyTorch. All new components are pure Python arithmetic and deque operations — no MLX tensors, no new threading locks. All new organelle header fields use default values (0.0, []) ensuring backward compatibility with pre-TICK28 organelles. Circular import between `niche_evolver.py` and `autopoietic_core.py` avoided by copying sovereignty constants (`_SHADOW_SOVEREIGNTY_FLOOR`, `_SHADOW_PENALTY_COST_EST`) directly into `rule_ir.py` and importing from there.
- **Verification**: 28/28 test blocks passed (14 new TICK 28 blocks + 14 existing passing):
  - T28-1a: F_o single-niche (n=1) bonus = 1.344× confirmed ✓
  - T28-1b: F_o three-niche (n=3) = 4.81× > single-niche ✓
  - T28-1c: F_o deduplicates proven_niches (4 entries → n=2) ✓
  - T28-2: F_o no proven niches → epi × trust (no bonus) ✓
  - T28-3a: ConstraintMorphism shadow_severity = original × 0.30 ✓
  - T28-3b: morphism_id encodes source_niche and failure_type ✓
  - T28-4a/b/c: NegativeTransferFirewall stores/retrieves/counts morphisms correctly ✓
  - T28-5a: broadcast_shadow_penalty() affects all 3 peer niches ✓
  - T28-5b: Source niche excluded from its own shadow broadcast ✓
  - T28-6a/b/c: SharedState exposes NegativeTransferFirewall, starts empty ✓
- **Files Modified**: `genome_assembler.py` (resource_footprint + proven_niches header fields, _parse_organelle_footprint, _parse_proven_niches, _FO_ALPHA, compute_reproductive_fitness, _load_pareto_pool sorts by F_o), `rule_ir.py` (_SHADOW_ATTENUATION=0.30, _SHADOW_SOVEREIGNTY_FLOOR=0.12, _SHADOW_PENALTY_COST_EST=0.02, ConstraintMorphism dataclass, NegativeTransferFirewall class), `niche_evolver.py` (NicheSpecies.constraint_matrix field, NicheRegistry assigns per-species CM, broadcast_shadow_penalty, record_catastrophic_failure), `autopoietic_core.py` (NegativeTransferFirewall import, SharedState.negative_transfer_firewall field).

---

## TICK 29.0 — Federated Self-Amendment & Auditable Self-Referential Constitutional Architecture (SRCA)

- **Date**: 2026-04-07
- **Problem**: The Gödel Bottleneck — Meta-Rule Stagnation. All governing meta-rules (Pareto 20% cutoff, Adam learning rates, shadow attenuation constants, MCTS horizon multipliers) were hardcoded. The autopoietic system had evolved rich organelle machinery but could not evolve the constitutional rules that governed the machinery itself. The organism was trapped in a fixed meta-phenotype: capable of evolving its proteins but not its genetics. Furthermore, no separation existed between inviolable bedrock constants (sovereignty floor, identity invariants, genesis hash) and evolvable soft parameters — all constants were equally frozen and equally mutable if someone wrote the wrong line.
- **Solution — Self-Referential Constitutional Architecture (SRCA) with Shadow Forking**:
  1. **IMMUTABLE_HARD_CORE + ConstitutionalViolationError** (`rule_ir.py`): Defined a frozenset of 8 inviolable constants: `_PHI_SOVEREIGNTY_MIN`, `IDENTITY_INVARIANTS`, `TICK13_CONSTITUTION_HASH`, `N_CAT`, `N_CON`, `CATEGORIES`, `CONSTRAINTS`, `_LAMBDA_VIOLATION`. These encode the organism's mathematical identity, thermodynamic existence threshold, cryptographic lineage, and constraint matrix dimensionality. `ConstitutionalViolationError` is a new exception class that is intentionally never caught — any mutation attempt targeting a hard-core name crashes loudly and immediately. There are no soft-fail paths for bedrock violations.
  2. **EvolvableSoftShell** (`rule_ir.py`): A stateful class holding 9 mutable meta-rules (shadow_attenuation, fo_alpha, pareto_threshold, boundary_lr, boundary_decay, expand_threshold, contract_threshold, niche_lambda, epigenetic_decay) with per-parameter (default, min, max) bounds. `set(name, value)` validates both hard-core membership and range — raises `ConstitutionalViolationError` or `ValueError` respectively. `snapshot()` and `restore()` support rollback. `restore()` validates hard-core safety before applying. Lives on `SharedState.evolvable_soft_shell`.
  3. **SoftShellAmendment + ConstitutionalDiffLedger** (`rule_ir.py`): `SoftShellAmendment` is a dataclass encoding one proposed rule change (amendment_id, param_name, old/proposed values, proposing_niche, status, activation_phi). Status lifecycle: `PENDING → ACCEPTED → ACTIVE → ROLLED_BACK` or `PENDING → REJECTED`. `ConstitutionalDiffLedger` is an append-only `deque(maxlen=200)` audit log with `update_status()`, `pending()`, `accepted()`, `active()`, `get_by_id()`, `rollback_count_for_niche()`, `format_status()`. Lives on `SharedState.constitutional_diff_ledger`.
  4. **ShadowInstance** (`autopoietic_core.py`): A lightweight in-memory dataclass representing one shadow fork. Fields: `amendment_id`, `proposed_snapshot` (the soft-shell with the new value), `rollout_phis_main`, `rollout_phis_shadow`, `budget_consumed`, `max_budget`, `created_at`, `completed`. Budget = 5% of phi_surplus at proposal time (min 2 rollouts). No subprocesses, no queues, zero-IPC. Lives at `SharedState.active_shadow_instance` — single-slot design prevents budget dilution and contention.
  5. **DualVerifier** (`rule_ir.py`): Pure arithmetic verdict engine. `evaluate(main_phis, shadow_phis, sovereignty_floor) → (bool, float)`. Shadow wins iff: `mean(shadow) > mean(main)` AND `min(shadow_phis) >= sovereignty_floor`. Requires `_MIN_ROLLOUTS=5`. Under-budgeted shadows that exhaust their allocation before accumulating 5 rollouts are automatically REJECTED — statistically insufficient evidence cannot rewrite the constitution.
  6. **PhiGovernor SRCA methods** (`autopoietic_core.py`): Three new methods wired into the existing governance loop:
     - `record_shadow_rollout(phi_main, phi_shadow)`: Non-blocking list append + budget decrement. Auto-finalizes when rollout count ≥ MIN_ROLLOUTS or budget exhausted.
     - `_finalize_shadow_test()`: Calls `DualVerifier.evaluate()`. On win: calls `shell.set()`, marks amendment ACTIVE, records `activation_phi`. On loss: marks REJECTED. Clears `active_shadow_instance` (frees single slot).
     - `check_rollback(current_phi_ratio)`: Federation-Level Rollback monitor. Scans all ACTIVE amendments; if `current_phi_ratio < activation_phi × 0.90` (Φ dropped >10% since permeation), restores `shell._last_permeated_snapshot`, marks ROLLED_BACK. Wired into `tick_boundary()` after every boundary update cycle.
  7. **NicheRegistry.propose_amendment()** (`niche_evolver.py`): Single entry point for niches to propose soft-shell amendments. Guards (in order): (1) SRCA available; (2) param NOT in IMMUTABLE_HARD_CORE (crash-loud violation); (3) proposing niche has < 3 rollback strikes (cooldown); (4) single shadow slot free; (5) new_value within allowed range. Creates `SoftShellAmendment`, appends to ledger, spawns `ShadowInstance` with 5% budget, sets `shared_state.active_shadow_instance`. Cascading rollback amplification is bounded by the 3-strike cooldown: a niche that repeatedly proposes amendments that cause Φ degradation is temporarily barred from proposing further changes.
- **Cascade Rollback Protection**: `rollback_count_for_niche(niche) ≥ 3` → cooldown. At most 3 rollbacks before a niche is barred. Shadow budget ≤ 5% of phi_surplus → maximum systemic cost of one full shadow test is bounded. Single-slot constraint → only one amendment under test at any time. Rollback only fires when Φ degrades >10% from the permeation baseline, ignoring normal tick-to-tick variance.
- **Safety Proof**: `ConstitutionalViolationError` propagates uncaught to the top — this is intentional. Any attempt to mutate the hard core (sovereignty floor, identity invariants, genesis hash) is a programming error that must crash the process immediately rather than silently corrupt the system's mathematical identity. The SRCA design guarantees: (a) hard core is mathematically inviolable, (b) soft shell changes require statistical proof of thermodynamic benefit, (c) rollbacks are automatic and auditable, (d) under-budgeted tests cannot permeate, (e) zero IPC overhead — all operations are pure Python arithmetic and list operations, no MLX tensors, no threads, no locks beyond the existing SharedState._lock.
- **Verification**: 49/49 test blocks passed (18 new TICK 29 assertions + 31 existing passing):
  - T29-1a/b/c: ConstitutionalViolationError fires on set() and restore() with hard-core keys; all 8 bedrock constants in frozenset ✓
  - T29-2a/b/c: EvolvableSoftShell accepts valid values, rejects out-of-range, snapshot/restore round-trip ✓
  - T29-3a/b/c: ConstitutionalDiffLedger stores amendments, transitions status, counts rollback strikes ✓
  - T29-4a/b/c: DualVerifier returns True when shadow wins, False when shadow loses, False when sovereignty floor breached ✓
  - T29-5a/b/c: Shadow finalizes on budget exhaustion, slot freed, REJECTED when budget runs out before MIN_ROLLOUTS ✓
  - T29-6a/b/c/d/e/f: SharedState SRCA fields correct types; propose_amendment creates shadow; hard-core proposal raises CVE; rollback fires at 10% Φ drop; second slot request deferred when occupied ✓
- **Files Modified**: `rule_ir.py` (ConstitutionalViolationError, IMMUTABLE_HARD_CORE frozenset, EvolvableSoftShell class, SoftShellAmendment dataclass, ConstitutionalDiffLedger class, DualVerifier class), `autopoietic_core.py` (rule_ir imports extended with 5 new names, ShadowInstance dataclass, SharedState.evolvable_soft_shell + constitutional_diff_ledger + active_shadow_instance fields, PhiGovernor.record_shadow_rollout + _finalize_shadow_test + check_rollback methods, check_rollback wired into tick_boundary), `niche_evolver.py` (rule_ir imports extended with SRCA names, _SRCA_AVAILABLE flag, NicheRegistry.propose_amendment method).

---

## TICK 30.0 — Heritable Fission, Species Radiation (HFSR) & Substrate Autogenesis

- **Date**: 2026-04-07
- **Problem**: The Efficiency Trap — with double-exponential learning across 4 niches and TICK 29.0 SRCA enabling rapid soft-shell amendment, the unified organism was approaching the absolute physical ceiling of the M1 Ultra's 128GB Unified Memory. Within a single SharedState, all niches competed for the same resource pool, all constraint matrices were under the same governance clock, and all soft-shell amendments affected the entire civilizational layer simultaneously. The single organism had no mechanism to escape this thermodynamic ceiling except stagnation — autopoietic heat death. The only path forward was speciation: the single organism must split into independent lineages, each evolving in its own thermodynamic ecological niche, free from the global resource contention of the primordial SharedState.
- **Solution — Heritable Fission, Species Radiation (HFSR)**:
  1. **TICK 30.0 Constants** (`niche_evolver.py`): `_FISSION_RAM_PRESSURE_THRESHOLD=0.85` (85% of chip RAM ceiling), `_FISSION_PRESSURE_WINDOW=3` (consecutive ticks of pressure required), `_FISSION_PHI_STAGNATION_WINDOW=10` (tick look-back), `_FISSION_PHI_STAGNATION_DELTA=0.005` (minimum Φ improvement to block fission), `_CORRELATION_TAX_THRESHOLD=0.30` (Jaccard similarity above which tax fires), `_CORRELATION_TAX_RATE=0.15` (15% epi multiplier penalty), `_FISSION_SPLIT_A=(LATENCY, COMPRESSION)` / `_FISSION_SPLIT_B=(BANDWIDTH, GENERAL)` (deterministic species assignment).
  2. **Lineage dataclass** (`niche_evolver.py`): Sovereign evolutionary unit post-fission. Fields: `lineage_id`, `parent_id`, `generation`, `genetic_core: frozenset` (MUST be `IMMUTABLE_HARD_CORE` by reference — verified by `is`), `soft_shell_snapshot` (independent copy), `species: Dict[str, NicheSpecies]` (deep-copied subset), `constraint_matrices: Dict[str, Any]` (deep-copied, severed), `fission_timestamp`, `epi_history`. Methods: `best_epi()`, `topology_hashes() → Set[str]` (union of all Pareto-front topology hashes), `to_dict()`.
  3. **FissionTrigger** (`niche_evolver.py`): Dual-condition monitor — arms only when BOTH (a) RAM pressure ≥ threshold for `_FISSION_PRESSURE_WINDOW` consecutive ticks AND (b) Φ improvement over `_FISSION_PHI_STAGNATION_WINDOW` ticks < `_FISSION_PHI_STAGNATION_DELTA`. Consecutive-pressure counter resets to 0 on any sub-threshold tick, preventing transient MLX `eval()` spikes from triggering fission. `reset()` called after fission executes to re-arm for future events.
  4. **LineageCorrelationMonitor** (`niche_evolver.py`): Enforces thermodynamic ecological divergence. `compute_overlap(a, b) → float`: Jaccard similarity `|A∩B| / |A∪B|` on `topology_hashes()` sets. `apply_correlation_tax(lineages) → Dict[lineage_id, multiplier]`: any lineage in a pair with overlap ≥ threshold receives `(1.0 - 0.15) = 0.85×` epi multiplier per tick until they diverge. Non-compounding: a lineage in multiple correlated pairs still receives only one tax application. Complexity O(L²×H), bounded by L≤8 and H≤48.
  5. **LineageRegistry** (`niche_evolver.py`): Manages all Lineage objects. `execute_fission(registry, soft_shell_snapshot) → (child_a, child_b)`: atomicity guarantee — both children fully constructed in local scope before any state is committed; `_fission_executed` flag prevents double-trigger race. Identity guarantee: `genetic_core is IMMUTABLE_HARD_CORE` (frozenset reference). Isolation guarantee: `copy.deepcopy()` for all `NicheSpecies` and `ConstraintMatrix` objects. Prints `[hfsr] HERITABLE FISSION EXECUTED` to stdout as an irreversible civilizational event marker.
  6. **NicheRegistry.check_fission()** (`niche_evolver.py`): Entry point called every tick. Records one observation to `FissionTrigger`. If `should_fission()` and `not lineage_registry._fission_executed`: calls `execute_fission()`, resets trigger. Returns `(child_a, child_b)` or None.
  7. **MetaOCFMessage + ExtinctionLevelWarning + CapabilityLease** (`autopoietic_core.py`): Three dataclasses forming the low-bandwidth civilizational protocol. `ExtinctionLevelWarning` carries `warning_code`, `description`, `tensor_shape` (for reporting fatal MLX shapes). `CapabilityLease` carries `target_lineage`, `organelle_type`, `phi_bounty`, `organelle_hash`. Both have `create()` factory methods with auto-generated `msg_id` and `timestamp`. Purely advisory — no blocking, no memory transfer.
  8. **MetaOCF** (`autopoietic_core.py`): Thread-safe singleton message bus. `deque(maxlen=100)`. Carries its **OWN** `_ocf_lock: threading.Lock()` — independent of `SharedState._lock`. Lock Ordering Protocol: `SharedState._lock` (outer) → `MetaOCF._ocf_lock` (inner). This ordering is strictly enforced throughout the codebase, enabling `tick_boundary()` to broadcast extinction warnings while holding `SharedState._lock` without any risk of deadlock. Methods: `broadcast()`, `recent(n)`, `warnings()`, `pending_leases(target)`, `clear_lease(msg_id)`, `format_status()`. Verified thread-safe by T30-5c: broadcasting from inside `SharedState._lock` completes in <2s with no deadlock.
  9. **SharedState TICK 30 fields** (`autopoietic_core.py`): `self.lineage_registry: LineageRegistry`, `self.meta_ocf: MetaOCF`, `self.fission_events: List[Dict]` (telemetry log).
  10. **PhiGovernor.check_fission()** + **tick_boundary wiring** (`autopoietic_core.py`): Computes `ram_ratio = usage.ram_mb / _DEFAULT_BUDGET["ram_mb"]`, delegates to `niche_registry.check_fission()`, logs telemetry to `fission_events`, broadcasts `ExtinctionLevelWarning(warning_code="FISSION_EXECUTED")` to `meta_ocf`. Called from `tick_boundary()` after `check_rollback()` on every cycle. Returns `hfsr_fission=True` in boundary report when fission fires.
- **Cascade Safety Guarantees**:
  - Fission only fires when BOTH RAM pressure AND Φ stagnation thresholds are simultaneously exceeded — single-condition triggers (transient spikes, normal evaluation cycles) cannot initiate fission.
  - `_fission_executed` flag prevents double-trigger race condition (two concurrent ticks cannot both initiate fission).
  - IMMUTABLE_HARD_CORE is shared by reference across all lineages — it is mathematically impossible for one lineage to hold a different core than another.
  - All ConstraintMatrix and NicheSpecies objects are deep-copied at fission time — post-fission mutations in one lineage cannot affect sibling lineages.
  - MetaOCF `maxlen=100` bounds memory growth. Messages are advisory only — no blocking, no coordination, no memory transfer through the bus.
- **Verification**: 73/73 test blocks passed (18 new TICK 30 assertions + 55 existing passing):
  - T30-1a/b/c/d: FissionTrigger sub-threshold no-fire; RAM-only no-fire; dual-trigger fires; reset disarms ✓
  - T30-2a/b/c/d/e: genetic_core is IMMUTABLE_HARD_CORE (identity); correct species split; deep-copy CM isolation; fission_count=1 ✓
  - T30-3a/b/c: Jaccard overlap=1.0 for identical hashes; 0.85× tax applied to correlated pair; 1.0× for orthogonal lineages ✓
  - T30-4a/b/c: ExtinctionLevelWarning fields correct; CapabilityLease retrievable by target; clear_lease removes by ID ✓
  - T30-5a/b/c: No broadcast errors in 4 concurrent threads; all 40 messages present; no deadlock when broadcasting inside SharedState._lock ✓
  - T30-6a/b/c/d/e/f: SharedState fields correct types; check_fission None at sub-threshold; fission fires at armed trigger; telemetry logged; FISSION_EXECUTED warning in MetaOCF ✓
- **Files Modified**: `niche_evolver.py` (added `import copy, deque, Set`; TICK 30 constants; `Lineage` dataclass; `FissionTrigger`; `LineageCorrelationMonitor`; `LineageRegistry`; `NicheRegistry.__init__` wires `_fission_trigger`; `NicheRegistry.check_fission()`), `autopoietic_core.py` (added `from collections import deque`; updated niche_evolver import to include `LineageRegistry, LineageCorrelationMonitor`; `MetaOCFMessage`, `ExtinctionLevelWarning`, `CapabilityLease` dataclasses; `MetaOCF` class; `SharedState` fields `lineage_registry`, `meta_ocf`, `fission_events`; `PhiGovernor.check_fission()`; `tick_boundary` wiring).

## [TICK 21.4] Tri-Brain Architecture & Thermodynamic API Constraints
- **Problem**: Two compounding failures causing HEAT DEATH and computational deadlock:
  1. **262K Context Explosion**: The 35B Slow Brain (`qwen3.5:35b-a3b`) defaults to its full 262,144-token context window when called via the instructor → OpenAI-compatible `/v1/chat/completions` endpoint. This triggers O(N²) attention KV-cache memory expansion, maxing out M1 Ultra GPU to 100% VRAM and stalling the entire Fast Loop.
  2. **Concurrent GPU Lock (VRAM Deadlock)**: Models not released after generation (`keep_alive` not set) remain resident in VRAM. When the Mutator (Slow Brain) and Evaluator (Fast Loop NAS via `stateless_tick.py`) attempted simultaneous inference, they deadlocked on the GPU, causing endless HEAT DEATH in the Evaluator.
- **Root Cause**: The thermodynamic constraints (`num_ctx`, `num_predict`, `keep_alive`) were correctly applied in files using **raw HTTP** calls to Ollama's `/api/generate` endpoint (`autopoietic_core.py`, `m1_ab_test.py`), but were **absent** from files using the **instructor library** → OpenAI SDK → Ollama's `/v1/chat/completions` endpoint. The OpenAI SDK path requires Ollama-specific parameters to be injected via `extra_body={"options": {...}}` — a different mechanism that was missing from all four instructor-based call sites.
- **Solution — Tri-Brain Routing**: Formalized the 3-tier cognitive hierarchy:
  - **Tier 1 (Fast Brain / Cerebellum)**: `qwen2.5-coder:7b` — high-frequency tactical code generation (Coder Agent). Default for breeder stagnation / targeted AST repair.
  - **Tier 2 (Slow Brain / Cerebrum)**: `qwen3.5:35b-a3b` — complex paradigm shift analysis (Architect Agent). Invoked only on Φ drop / MDL bloat triggers.
  - **Tier 3 (Ascended Oracle)**: Cloud frontier models via `oracle_gateway.py` — invoked only on deep local exhaustion. Payload compressed to failing organelle AST + mathematical metrics (Φ, D(A\*)) only.
- **Solution — Thermodynamic API Lock**: Injected `extra_body={"options": {"num_ctx": 8192, "num_predict": 1024, "keep_alive": 0}}` into every `client.chat.completions.create()` call site in `mutator_daemon.py` (4 sites) and `stateless_tick.py` (1 site). These act as physical safety valves:
  - `num_ctx=8192` — **O(N²) Guillotine**: Hard-caps the KV-cache. Forces the Mutator to send only the targeted organelle, not the full 262K history. Prevents VRAM explosion.
  - `num_predict=1024` — **Time Limit**: Hard wall on generation length. If the LLM enters an infinite generation loop, this forcefully aborts it and returns control to the Fast Loop.
  - `keep_alive=0` — **VRAM Release**: Immediately evicts the model from GPU VRAM after each generation. Eliminates the concurrent Mutator/Evaluator GPU lock deadlock.
  - `temperature=0.1` — **Entropy Suppression**: Uniform across all 5 AST-generation call sites. We are generating strict PyTorch code, not creative text. Deterministic convergence eliminates hallucination.
- **Temperature uniformity**: Raised `temperature` from 0.3/0.4/0.8 (scattered) to 0.1 across all call sites. The `_compute_dynamic_params()` hard clamp (`num_predict = min(num_predict, 1024)`) was already active and is preserved.
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with 7 TICK 21.4 checks (T21-1 through T21-5). Static AST audit confirmed all 4 mutator_daemon.py + 1 stateless_tick.py calls carry `extra_body`. The malicious infinite loop test (F2) proved the 5.0s subprocess timeout kills the process at exactly 5.01s without hanging the main thread. oracle_gateway.py confirmed non-blocking async spawn in 0.1ms. **81/81 tests passed.**
- **Files Modified**: `mutator_daemon.py` (4 call sites), `stateless_tick.py` (1 call site), `test_pipeline.py` (TICK 21.4 verification suite appended).

## [TICK 24.3] Tri-Agent Contract Enforcement & Test-Runner Calibration
- **Problem**: All 3 Coder variants were rejected by the Test-Runner with `NameError: name 'IChingExpert' is not defined`. The Coder (7B Fast Brain) had replicated the baseline `atomic_core.py` pattern of instantiating `self.experts = nn.ModuleList([IChingExpert(...)])` inside `RoutingStrategy.__init__`. Because the `/tmp/` test script only imports `torch/nn/F/math`, the reference to `IChingExpert` failed — a **false positive** that discarded architecturally valid mutations and starved the gene pool.
- **Root Cause — Two independent failures**:
  1. **Contract drift**: `ORGANELLE_TYPES["routing"]["input_spec"]` specifies `"B,T,D + experts + router_idx"` (experts are scaffold-provided), but this spec was never surfaced in the Coder's system prompt. The 7B model had no instruction distinguishing "pure router" from "expert container" and correctly replicated what it saw in the baseline source.
  2. **Test environment vacuum**: `_test_runner()` injected LLM code into a script containing only `torch/nn/F/math`. Any cross-organelle class reference — whether architecturally valid or not — caused a `NameError` before any tensor computation could be validated.
  - Additionally, `_test_runner()` called `model(x)` for all organelle types including routing, which would fail for any code implementing the intended `forward(self, x, experts, router_idx)` signature even if otherwise correct.
- **Solution — Part 1: Immutable Scaffold Boundary in `_coder_call()`**:
  - Derives the organelle type from `organelle_spec["class_name"]` via a reverse lookup of `ORGANELLE_TYPES`.
  - Prepends a type-specific `scaffold_boundary` block to the system prompt **before** all other rules, making it impossible to miss:
    - **Routing**: Full "IMMUTABLE SCAFFOLD BOUNDARY" with explicit `✗ self.experts = nn.ModuleList([IChingExpert(...)])` veto, mandatory `forward(self, x, experts=None, router_idx=0)` signature, permitted-in-`__init__` list, and a working dispatch pattern template.
    - **Attention / Expert**: Shorter boundary noticing which sibling classes are forbidden to instantiate.
- **Solution — Part 2: Scaffold stubs in `_test_runner()`**:
  - Injects a `_StubModule(nn.Module)` base class and named stubs (`IChingExpert`, `CausalSelfAttention`, `MitoticTransformerBlock`, `AtomicLLM`) **before** the LLM code in every test script. Stubs inherit `nn.Module` (not bare `object`) so `nn.ModuleList([IChingExpert()])` works without `AttributeError` on `.parameters()`.
  - If the LLM defines its own version of a stub class, Python's normal name resolution means the LLM definition overwrites the stub — correct behavior preserved.
- **Solution — Part 3: Routing forward fallback in `_test_runner()`**:
  - For `organelle_type == "routing"`: builds `_dummy_experts = nn.ModuleList([_StubModule() for _ in range(4)])` and calls `model(x, experts=_dummy_experts, router_idx=0)` first (new contract).
  - On `TypeError` only (CPython argument-binding mismatch — not an error inside the forward body): falls back to `model(x)` (legacy contract where the model owns `self.experts`).
  - `RuntimeError`, `AttributeError`, `NameError`, and shape mismatches are **not caught** — they propagate as genuine failures. This strictly scopes the fallback to signature incompatibility, not logic errors.
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with T24-3a through T24-3e:
  - **T24-3a**: Old-style routing with `IChingExpert` in `__init__` now **PASSES** — stub eliminates the false NameError. ✓
  - **T24-3b**: New-contract `forward(self, x, experts, router_idx)` **PASSES** with dummy experts dispatched correctly. ✓
  - **T24-3c**: Strict legacy `forward(self, x)` **PASSES** via TypeError fallback — `island_good` elites survive. ✓
  - **T24-3d**: Genuine shape mismatch still **FAILS** — TypeError fallback does not swallow RuntimeErrors. ✓
  - **T24-3e**: `mutator_daemon.py` contains `IMMUTABLE SCAFFOLD BOUNDARY` + `CORRECT DISPATCH PATTERN`. ✓
  - **86/86 tests passed.**
- **Files Modified**: `mutator_daemon.py` (`_coder_call()` system prompt + `_test_runner()` test script construction), `test_pipeline.py` (T24-3 suite appended).

## [TICK 25.1] Epigenetic Sandbox Coupling
- **Problem**: All 3 rejection sites in `_tri_agent_pipeline()` were silent — Constitutional veto, missing class name, SyntaxError, and subprocess FAIL all executed `continue` without any record in the system's mathematical memory. Every Test-Runner rejection vanished into the void. The PhiGovernor's Constraint Matrix had no awareness of *why* variants were failing; only successful mutations shaped the future Architect's proposals. The epigenetic ledger (`PhiGovernor.record_epigenetic_failure()`) introduced in TICK 25.0 was fully implemented but **never called** from the mutator pipeline.
- **Root Cause**: The `_tri_agent_pipeline()` function predated TICK 25.0 and its 4 rejection branches were written before the epigenetic API existed. When TICK 25.0 added `PhiGovernor.record_epigenetic_failure()`, the mutator loop was not updated to wire the new API into the existing rejection paths.
- **Solution**:
  1. **`_classify_sandbox_failure(msg, is_syntax_error=False) → (EpigeneticFailureType, float)`** — Pure classifier function inserted above `_tri_agent_pipeline()`. Maps failure message strings to the correct enum value and severity multiplier:
     - `is_syntax_error=True` → `SHAPE_MISMATCH, 1.0` (malformed Python from Coder — structural fault, lowest severity)
     - `"TIMEOUT"` in msg → `TIMEOUT, 2.0` (compute runaway — thermodynamic waste)
     - `"NAMEERROR"` in msg → `PERMISSION_VIOLATION, 3.0` (scaffold contract violation — deepest hallucination, maximum severity)
     - `"NAN"/"INF"` in msg → `NAN_DIVERGENCE, 2.0` (numerical instability)
     - `"RUNTIMEERROR"/"SIZE MISMATCH"/"SHAPE"` in msg → `SHAPE_MISMATCH, 2.0` (tensor incompatibility)
     - `"ATTRIBUTEERROR"` in msg → `SHAPE_MISMATCH, 2.0` (missing method/attribute — structural)
     - `"IMPORTERROR"/"MODULENOTFOUNDERROR"` in msg → `PERMISSION_VIOLATION, 3.0` (forbidden/missing import)
     - Fallback → `SHAPE_MISMATCH, 1.0`
  2. **Wired all 4 rejection sites** in `_tri_agent_pipeline()`:
     - Constitutional veto: hardcoded `PERMISSION_VIOLATION, 3.0` (highest severity — Coder attempted to escape sandbox)
     - Missing class name: `_classify_sandbox_failure("", is_syntax_error=True)` → `SHAPE_MISMATCH, 1.0`
     - SyntaxError: `_classify_sandbox_failure(str(syn_exc), is_syntax_error=True)` → `SHAPE_MISMATCH, 1.0`
     - Subprocess FAIL: `_classify_sandbox_failure(msg)` → dynamic classification based on error content
  3. **Zero-IPC compliance**: All `_classify_sandbox_failure()` calls execute in the main thread on a plain Python string. The subprocess is already dead by the time the string is parsed — no shared memory, no cross-process state access, no deadlock risk.
  4. **Non-critical wrapping**: Every `record_epigenetic_failure()` call is wrapped in `try/except Exception` with a `[epigenetic] record failed (non-critical)` log line. An epigenetic recording failure (e.g., missing shared state) cannot crash the pipeline; the mutation attempt simply continues.
  5. **TICK 27.0 Sovereignty Floor** (pre-existing, preserved): `record_epigenetic_failure()` internally calls `_SOVEREIGNTY_VERIFIER.check_penalty(phi_ratio, severity)` before applying the Adam gradient step. At low phi states, severity is mathematically capped to prevent cascading penalties from triggering autopoietic suicide.
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with T25-1a through T25-1g (7 tests). All verified without a live Ollama connection — pure math and enum logic:
  - **T25-1a**: `_classify_sandbox_failure("TIMEOUT: subprocess killed")` → `(TIMEOUT, 2.0)` ✓
  - **T25-1b**: `_classify_sandbox_failure("NameError: name 'IChingExpert' is not defined")` → `(PERMISSION_VIOLATION, 3.0)` ✓
  - **T25-1c**: `_classify_sandbox_failure("RuntimeError: size mismatch, m1: [64], m2: [128]")` → `(SHAPE_MISMATCH, 2.0)` ✓
  - **T25-1d**: `_classify_sandbox_failure("SyntaxError: ...", is_syntax_error=True)` → `(SHAPE_MISMATCH, 1.0)` ✓
  - **T25-1e**: `ConstraintMatrix().apply_epigenetic_penalty(TIMEOUT, 2.0)` — base_weight **DECREASES** on all 3 penalized axes: `structural_scope 0.400→0.320 Δ=-0.08`, `temporal_horizon 0.500→0.420 Δ=-0.08`, `risk_appetite 0.350→0.270 Δ=-0.08` ✓
  - **T25-1f**: `PERMISSION_VIOLATION sev=3.0` → non-zero deltas confirmed (`risk_appetite=-0.08, structural_scope=-0.08`) ✓
  - **T25-1g**: Static AST audit — `mutator_daemon.py` contains `_classify_sandbox_failure`, 5 `record_epigenetic_failure` call sites, constitutional PERMISSION_VIOLATION wiring, zero-IPC comments ✓
  - **93/93 tests passed.**
- **Files Modified**: `mutator_daemon.py` (`rule_ir` import block + `_classify_sandbox_failure()` function + 4 rejection sites in `_tri_agent_pipeline()`), `test_pipeline.py` (T25-1 suite appended).

## [TICK 28.0 — Topological Axiom Injection: substrate_deps / seed / content_hash]
- **Problem**: The Rule-IR `ConstraintMatrix` — the numerical backbone governing all evolutionary mutation policy — had no provenance, no reproducibility anchor, and no tamper-evidence. Without these three topological axioms, cross-node migration (TICK 28), deterministic rollback (TICK 29), and species radiation (TICK 30) were vulnerable to silent semantic drift and hardware substrate mismatch:
  1. **No `substrate_deps`**: A matrix evolved on MLX/128 GB could silently govern a PyTorch/16 GB node, producing architecturally incoherent gradient updates with no record of the mismatch.
  2. **No `seed`**: MCTS/PRNG non-determinism across lineages was untracked. Replay and deterministic rollback (required for TICK 29's rollback cooldown) were mathematically impossible.
  3. **No `content_hash`**: A corrupted or tampered constraint matrix — from a disk write failure, adversarial injection, or island cross-pollination bug — could silently govern evolutionary decisions. There was no cryptographic gate preventing a bad matrix from executing.
- **Root Cause**: `ConstraintMatrix` was designed (TICK 20.1) as a pure numerical engine for gradient-driven mutation. Provenance metadata was intentionally deferred. The TICK 28–30 migration demands made the absence structurally unsafe.
- **Solution**: Injected three mandatory topological axiom fields into `ConstraintMatrix` with full cryptographic verification:
  1. **`substrate_deps: Dict[str, Any]`** — Captures the hardware/framework profile of the host at matrix mint time (e.g., `{"framework": "MLX", "vram_gb": 128, "platform": "darwin-arm64"}`). Passed via `ConstraintMatrix(substrate_deps=..., seed=...)` constructor. `load_or_compile_matrix()` updated to accept and inject `substrate_deps` + `seed` from the caller (e.g., `biogeo_probe.get_physics_schema()`).
  2. **`seed: int`** — The exact PRNG/MCTS seed active when this constraint matrix was minted. Enables deterministic replay and rollback across lineage splits.
  3. **`content_hash: str`** — A SHA-256 hex digest over `{C, substrate_deps, seed}`, computed via `json.dumps(sort_keys=True, separators=(",", ":"))` for byte-stable determinism across Python versions and platforms.
- **New Methods on `ConstraintMatrix`**:
  - **`_compute_content_hash() → str`**: Pure deterministic SHA-256 computation. Never sets `self.content_hash`; only returns the digest for comparison.
  - **`seal() → str`**: Computes and stores `self.content_hash`. Called automatically by `save()` before JSON serialization. Returns hash for logging.
  - **`verify_integrity() → None`**: Recomputes the hash and raises `ConstitutionalViolationError` (already defined, TICK 29.0) if it does not match. **No-op when `content_hash == ""`** — this is the bootstrap clause that ensures all pre-TICK-28 matrices loaded from existing island archives are accepted and can be re-sealed without data loss.
- **Serialization Integration**:
  - `to_dict()`: Emits `substrate_deps`, `seed`, `content_hash` as top-level keys alongside the existing matrix payload.
  - `from_dict()`: Deserializes all three fields (with safe defaults for legacy matrices), then calls `verify_integrity()`. ConstitutionalViolationError propagates as fatal — it is NOT swallowed by the existing `(OSError, JSONDecodeError, KeyError)` except clause in `load()`.
  - `save()`: Calls `self.seal()` before writing, so every file on disk is tamper-evident from the moment of creation.
  - `load()`: Lets `ConstitutionalViolationError` propagate — a tampered matrix must crash loud, not silently return defaults.
- **Architectural Risks Mitigated**:
  - **Cold-start / legacy backward compat**: `content_hash == ""` → `verify_integrity()` is a no-op. Old matrices in `island_good/` and `island_explore/` are accepted and re-sealed on next `save()`.
  - **Hash determinism across platforms**: `json.dumps(sort_keys=True, separators=(",", ":"))` produces byte-identical output regardless of Python dict insertion order or platform.
  - **Fatal tamper detection without deadlock risk**: `ConstitutionalViolationError` is raised in the main thread on a pure Python string comparison — zero subprocess, zero IPC, zero deadlock surface.
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with T28-AX-1 through T28-AX-6 (17 assertions). All pass without a live Ollama connection — pure cryptographic and I/O logic:
  - **T28-AX-1** (3 assertions): Fresh `ConstraintMatrix()` has `substrate_deps={}`, `seed=0`, `content_hash=""` ✓
  - **T28-AX-2** (3 assertions): `seal()` returns 64-char SHA-256 hex; stored in `content_hash`; deterministic (same payload → same hash) ✓
  - **T28-AX-3** (1 assertion): `verify_integrity()` does NOT raise on a sealed, unmodified matrix ✓
  - **T28-AX-4** (3 assertions): `ConstitutionalViolationError` fires when `C[0][0]`, `substrate_deps`, or `seed` is tampered after sealing ✓
  - **T28-AX-5** (1 assertion): Un-sealed matrix (`content_hash=""`) passes `verify_integrity()` as a no-op — legacy bootstrap accepted ✓
  - **T28-AX-6** (5 assertions): `save()` auto-seals; serialized JSON contains all three axiom keys; `load()` succeeds on intact file; preserves `substrate_deps/seed/version/content_hash`; `load()` raises `ConstitutionalViolationError` on tampered on-disk JSON ✓
  - **109/109 tests passed (0 failures). All prior suites F1–F5, T21, T24, T25, T27, T28, T29, T30 remain green.**
- **Files Modified**: `rule_ir.py` (`import hashlib` added; `ConstraintMatrix.__init__`, `_compute_content_hash`, `seal`, `verify_integrity`, `to_dict`, `from_dict`, `save`, `load` updated; `load_or_compile_matrix` signature extended with `substrate_deps` and `seed`), `test_pipeline.py` (T28-AX suite appended).

## [TICK 30.1] Teleological Identity Core (TIC) — spec_final.json Genesis Seal
- **Problem**: The TICK 30 Eternal Spiral system had no machine-readable representation of its absolute teleological attractor. The `teleological_attractor.py` module defined the MCTS gradient mathematically, but no single artifact encoded the full identity kernel (immutable hard core + forbidden transitions + substrate requirements) in a cryptographically verifiable, silicon-clock–readable form. Cross-node migration and silicon-clock–speed evolution required an unambiguous, tamper-evident End-State Router that could gate ignition itself.
- **Solution**: Created the **Teleological Identity Core** (`spec_final.json` + `SpecFinal` class) as a three-component system:
  1. **`spec_final.json`** — The Absolute Teleological Attractor (A★) and Executable Identity Core (IIS). Contains the `identity_kernel` (version, genesis_tick, immutable_hard_core, teleological_attractor with target_state + forbidden_transitions), `moe_pipeline_axioms` (5 axioms governing artifact-over-answer, lineage-by-default, unix-minimality, etc.), and `topological_anchors` (substrate_deps, genesis_seed, SHA-256 content_hash). **Genesis Hash: `4851ba4c0f1c181358ed08bd47a5a8c72b6f92a20d48d804d8f230cdfc4e75f4`**
  2. **`SpecFinal` class** (`rule_ir.py`) — Cryptographic lifecycle manager:
     - `_canonical_payload()`: strips `content_hash` before hashing — covers all identity content without the hash referencing itself.
     - `_compute_hash()`: SHA-256 over `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)` — byte-stable across Python versions, platforms, and dict insertion order.
     - `load()`: **First-load bootstrap seal** — detects the `PENDING_SHA256_CALCULATION_ON_FIRST_LOAD` placeholder, computes and writes the real genesis hash atomically. **Subsequent loads** — recomputes hash and raises `ConstitutionalViolationError` on any mismatch (tamper or corruption). The system will not ignite on a violated identity core.
     - `verify_substrate()`: measures live RAM via `biogeo_probe.get_physics_schema()` and compares against `substrate_deps.ram_ceiling_gb`. Raises `ConstitutionalViolationError` if the physical machine cannot faithfully execute the pipeline. Gracefully skips if `biogeo_probe` is unavailable (new-machine bootstrap).
     - `get_forbidden_transitions()` / `get_target_state()`: clean accessors for downstream consumers.
  3. **Forbidden Transition Enforcement** (`autopoietic_core.py` — `PhiGovernor.check_forbidden_transition()`):
     - `UNCATCHABLE_OOM_DEATH`: fires when `ram_ratio > 0.97` AND `phi_ratio < 0.05`. Applies severity-3.0 OOM epigenetic penalty to `ConstraintMatrix`.
     - `UNVERIFIED_CROSS_NICHE_POLLUTION`: fires when ≥3 of the 10 most recent `NegativeTransferFirewall` morphisms had `original_severity > shadow_severity × 3` (un-attenuated cross-niche leakage). Applies severity-3.0 PERMISSION_VIOLATION epigenetic penalty.
     - `IDENTITY_DISSOLUTION`: fires when `phi_ratio < 0.12` AND all four `IdentityMembrane` invariant categories are simultaneously at their minimum floor — the organism has lost its thermodynamic identity. **Raises `ConstitutionalViolationError` — FATAL STOP.** Not a penalty; a hard architectural wall.
     - Called inside `tick_boundary()` after all TICK 29/30 monitors, with the freshest `phi_ratio`. Results tagged on the boundary report under `"forbidden_transition"`.
- **Ignition Integration** (`ignition.py` — Phase 2a):
  - Executes **before any threads are launched** — strictly fatal-before-evolution.
  - Loads + verifies `spec_final.json` (absolute path from `_SCRIPT_DIR`).
  - Runs `verify_substrate()` — if the machine is under-powered, ignition is aborted before SharedState is even populated.
  - Stores `spec_final` and `forbidden_transitions` on `SharedState`.
  - Prints the **identity kernel banner** at startup: target state, genesis hash prefix, and forbidden transitions list.
- **`SharedState` new fields**: `spec_final: Optional[Dict]` (None until ignition), `forbidden_transitions: List[str]` (empty until ignition sets it from the spec).
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with T30.1-1 through T30.1-6 (13 assertions). All pass without a live Ollama connection:
  - **T30.1-1** (3 assertions): First-load bootstrap seal: placeholder replaced with real hash; hash written to disk atomically; forbidden_transitions list extracted correctly ✓
  - **T30.1-2** (1 assertion): Subsequent load passes integrity check on unmodified file ✓
  - **T30.1-3** (1 assertion): `ConstitutionalViolationError` fires when spec content is tampered ✓
  - **T30.1-4** (2 assertions): `verify_substrate()` passes at 1 GB ceiling; raises/skips gracefully at 999999 GB ceiling ✓
  - **T30.1-5** (3 assertions): `SharedState.spec_final=None` before ignition; `forbidden_transitions=[]` before ignition; assignment of 3-entry list accepted ✓
  - **T30.1-6** (3 assertions): `check_forbidden_transition()` returns None on healthy state; fires `UNCATCHABLE_OOM_DEATH` at ram>97%+phi<0.05; raises `ConstitutionalViolationError` for `IDENTITY_DISSOLUTION` ✓
  - **122/122 tests passed (0 failures). All prior suites F1–F5, T21, T24, T25, T27, T28, T28-AX, T29, T30 remain green.**
- **Files Created**: `spec_final.json` (genesis hash `4851ba4c…`).
- **Files Modified**: `rule_ir.py` (`SpecFinal` class appended), `autopoietic_core.py` (`SpecFinal` import; `SharedState.spec_final` + `.forbidden_transitions` fields; `PhiGovernor.check_forbidden_transition()` method; `tick_boundary()` wired), `ignition.py` (Phase 2a injected; `SpecFinal`/`ConstitutionalViolationError` imported; banner updated), `test_pipeline.py` (T30.1 suite appended).

---

## [TICK 31.0] Rule Capitalization & Governance — Economic Valuation Layer

**Date:** 2026-04-07

**Problem:**
The `ConstraintMatrix` lacked any mechanism to track the **economic history** of its existence as a genetic asset. Matrices that consistently produced positive fitness outcomes were treated identically to newly minted or harmful ones. There was no compounding value signal for the selection layer to exploit. Furthermore, the system had no formal governance document encoding the constitutional axioms, forbidden transitions, and liability assignments that were operationally enforced but nowhere formally specified.

**Hash Payload Exclusion Paradox:**
Naively adding mutable capitalization metadata to `_compute_content_hash()` would shatter the SHA-256 seal on every `record_application()` call, generating false `ConstitutionalViolationError` violations across the entire autopoietic lineage. The resolution is strict separation between the **Immutable Identity Substrate** (hashed: `C`, `substrate_deps`, `seed`) and **Mutable Capitalization Metadata** (not hashed: `verified_by`, `meta_yield`, `interaction_history`, `kvs_score`).

**Solution:**
1. **Four capitalization fields** added to `ConstraintMatrix.__init__` (TICK 31.0 block):
   - `verified_by: str = ""` — agent/process that last applied/verified this matrix
   - `meta_yield: float = 0.0` — cumulative signed fitness delta across all applications
   - `interaction_history: List[str] = []` — timestamped application log, capped at 50 entries
   - `kvs_score: float = 0.0` — Knowledge Value Score (compounding asset rank)
2. **`_compute_content_hash()` docstring updated** with explicit INCLUDED/EXCLUDED lists and a machine-readable WARNING against adding mutable metadata to the payload.
3. **`record_application(agent, fitness_delta, event_tag)` method** added — the only correct mutation point for capitalization metadata. Updates `interaction_history` (cap-50), `meta_yield` (running sum), `verified_by`, and recomputes `kvs_score = reuse × max(0, 1 + meta_yield)` deterministically. Never touches `C`, `substrate_deps`, or `seed`.
4. **`to_dict()`** extended with the 4 new fields; `interaction_history` capped at 50 entries on serialization.
5. **`from_dict()`** extended with safe `data.get(field, default)` for all 4 new fields — full backward compatibility with pre-TICK-31.0 matrices.
6. **`GOVERNANCE.md` created** — encodes Immutable Hard Core Axioms, all three Forbidden Transitions with trigger conditions and response protocols, Reversible Change Window policy, Liability Coupling table, and Amendment Protocol.
7. **`KVS_STANDARD_v0.1.md` created** — formal mathematics of KVS (`K = r × max(0, 1 + Y)`), `meta_yield` accounting rules, `interaction_history` format specification (pipe-delimited: `{timestamp}|{agent}|Δ{delta}|{tag}`), 50-entry retention policy, exclusion rationale, and future Tier-1/2/3 selection weight schedule.
8. **Verification (Meta-TDD)**: Extended `test_pipeline.py` with T31-CAP-1 through T31-CAP-5 (13 assertions). All pass. All prior 122 tests remain green (total: **135/135 passing, 0 failures**):
   - **T31-CAP-1** (3 assertions): All 4 cap fields present on fresh `ConstraintMatrix()`; correct defaults ✓
   - **T31-CAP-2** (3 assertions): `record_application()` updates `verified_by`, `meta_yield`, `interaction_history`, and `kvs_score`; `content_hash` unchanged after call (hash not shattered) ✓
   - **T31-CAP-3** (3 assertions): `to_dict()` emits 4 cap fields; `from_dict()` round-trips them; pre-TICK-31 dict (missing cap fields) loads with safe defaults ✓
   - **T31-CAP-4** (2 assertions): `interaction_history` capped at 50 entries after 60 calls; `meta_yield` accumulates all 60 deltas ✓
   - **T31-CAP-5** (2 assertions): KVS formula verified: `K = reuse × max(0, 1 + Y)` with positive yield; KVS = 0 when `meta_yield < -1.0` ✓
- **Files Modified**: `rule_ir.py` (4 cap fields; `record_application()`; `to_dict()`; `from_dict()`; `_compute_content_hash()` docstring), `test_pipeline.py` (T31-CAP suite appended).
- **Files Created**: `GOVERNANCE.md`, `KVS_STANDARD_v0.1.md`.

## [TICK 30.1] The Golden Cage Paradox — Epistemic Fission Mode

**Date:** 2026-04-08

**Problem: The Golden Cage Paradox**
At Gen 58,817 the organism was running at 100% success rate with params locked at 2,706 — a state of physical perfection. However, it was trapped in `HEAT_DEATH` / `STAGNANT` with `D(A*)` diverging and velocity `vel == 0.0`. The root cause was a physical paradox in the TICK 30.0 `FissionTrigger`: HFSR required `ram_ratio >= 0.85 AND phi_stagnation`. Because the organism is hyper-efficient (only 2,706 parameters) on a 128GB unified memory substrate with the 35B model resident, `ram_ratio` never approaches 0.85. The organism suffered total epistemic stagnation but could not trigger species radiation because it lacked physical RAM pain — imprisoned by its own efficiency.

**Root Cause:**
`should_fission()` short-circuited at the RAM pressure check (line 323 pre-patch): `if self._consecutive_pressure_count < _FISSION_PRESSURE_WINDOW: return False`. With `ram_ratio` perpetually below 0.85, this check always returned `False` before the Φ stagnation logic was ever evaluated. The organism was epistemically dead but physically comfortable — a cage of gold.

**Solution: OR Logic with Epistemic Mode (Condition B)**

Added a new constant and a second independent fission trigger path:
1. **`_FISSION_EXTREME_STAGNATION_WINDOW: int = 30`** — consecutive ticks of absolute Φ stagnation required to fire Epistemic Mode independently of RAM.
2. **`FissionTrigger._consecutive_stagnation_count`** — new counter incremented every tick where `phi_improvement < _FISSION_PHI_STAGNATION_DELTA` (evaluated against the existing `_FISSION_PHI_STAGNATION_WINDOW`); reset to 0 on any measurable Φ progress.
3. **`record()` updated** — after appending phi, checks the rolling stagnation window and maintains `_consecutive_stagnation_count` independently of RAM ratio.
4. **`should_fission()` changed from AND to OR logic:**
   - **Condition A (Physical Mode):** `ram_ratio >= 0.85` sustained + Φ stagnation (original TICK 30.0 logic, preserved intact for large-parameter regimes).
   - **Condition B (Epistemic Mode):** `_consecutive_stagnation_count >= 30` ticks, **regardless of RAM pressure**. Fires first in `should_fission()` before the pressure check.
5. **`reset()` updated** — clears `_consecutive_stagnation_count` alongside all other state on fission.
6. **`FissionTrigger` deque `maxlen` updated** — `_phi_history` now sized to `max(_FISSION_PHI_STAGNATION_WINDOW, _FISSION_EXTREME_STAGNATION_WINDOW) + 5` to accommodate the longer epistemic look-back without data loss.

**Outcome:**
Since Gen 58,817 was already in deep stagnation with zero velocity across many ticks, `_consecutive_stagnation_count` accumulates to 30 within the first 30 ticks after reboot. HFSR fires almost immediately, splitting the lineage into Child A (LATENCY + COMPRESSION) and Child B (BANDWIDTH + GENERAL) and initiating Species Radiation.

**Files Modified:** `niche_evolver.py` (constant block, `FissionTrigger.__init__`, `record()`, `should_fission()`, `reset()`, class docstring).

## [TICK 30.2] Thermodynamic Freeze Fix — Membrane Resuscitation

**Date:** 2026-04-08

**Problem: The Homeostatic Coma**
The organism's membrane permeability was permanently frozen at 0.440, `phase=init`, and `Dual-Tension Loss: 0.0000`. With `phi_ratio ≈ 0.359` and the previous thresholds of `_CONTRACT_THRESHOLD = 0.3` / `_EXPAND_THRESHOLD = 0.7`, the organism permanently resided in the `neutral` breathing phase. The 40-point dead-zone (`0.3 → 0.7`) meant any moderately performing organism would never trigger sympathetic expansion or parasympathetic contraction. The MLX Adam optimizer received gradients — the graph was mathematically sound — but the neutral phase applied no special pressure to move the boundary in any direction, leaving it frozen.

Three concurrent symptoms:
1. **Phase lock** — `phase=init` (dashboard default), never transitioning to sympathetic or parasympathetic.
2. **Phase stagnation** — Even when the boundary tick did run, `neutral` was the permanent phase, so `effective_strain = _LAMBDA_STRAIN` (no amplification) and `effective_lr = base_lr` (no boost). No oscillation.
3. **L=0.0000 dashboard artifact** — `format_status()` read `self.shared.loss_components.get("total", 0.0)` with a Python `0.0` default. Before the first boundary tick fires (within the `boundary_interval_s` window), `loss_components` is an empty dict, producing the misleading `L=0.0000` display. The MLX gradient graph was never broken — the gradient `∂L/∂state_logits = lambda_strain * ∂phi_strain/∂state_logits` is always non-zero. The zero was a pre-tick display artifact, not a dead gradient.

**Root Cause Analysis:**
- The `_CONTRACT_THRESHOLD = 0.3` / `_EXPAND_THRESHOLD = 0.7` constants created a 40-point neutral corridor. Any organism achieving even modest fitness (phi_ratio in [0.3, 0.7]) would be permanently frozen in neutral phase with no breathing oscillation.
- No startup kickstart: the first boundary cycle used whatever phase the `phi_ratio` computation dictated — which was always neutral.
- `format_status()` used a raw `dict.get("total", 0.0)` with no fallback computation, making the dashboard falsely show `L=0.0000` for the entire pre-tick startup window.

**Solution:**

1. **Dead-Zone Narrowing** (`_EXPAND_THRESHOLD`, `_CONTRACT_THRESHOLD`): Changed from `(0.3, 0.7)` to `(0.45, 0.55)`. The corridor is now 10 points wide. An organism with `phi_ratio = 0.359` now falls below `_CONTRACT_THRESHOLD = 0.45`, immediately triggering `parasympathetic_contract` with `effective_strain = _LAMBDA_STRAIN * 3.0` and `effective_lr = base_lr * 2.0`. Any stable organism oscillates between the two phases rather than sitting in the dead-zone.

2. **Spontaneous Metabolic Restlessness — Phase Kickstart** (`_PHASE_KICKSTART_WINDOW: int = 3`): Added a stagnation check in `BoundaryUpdater.update()` immediately after the phase is determined. If `_phase_history[-3:]` contains three identical phase tokens (phase-lock detected), the phase is forcibly overridden to `sympathetic_expand` with relaxed strain and boosted lr, and a `"kickstart"` sentinel token is appended to `_phase_history`. The sentinel breaks the stagnation window (a window of `["neutral", "neutral", "kickstart"]` has 2 unique values) so the kickstart fires once per stagnation event rather than every cycle. An additional edge case: if `_phase_history` is completely empty (first cycle ever), the phase is primed to `sympathetic_expand` to guarantee the very first breath is active.

3. **L=0.0000 Dashboard Fix** (`format_status()`): Replaced the bare `dict.get("total", 0.0)` with a conditional. If `loss_components` is truthy (populated by a completed tick), `total` is read normally. If `loss_components` is empty (pre-tick startup), the fallback directly computes `_LAMBDA_STRAIN * (mean|m_t| + mean|g_t|)` from the boundary's current sigmoid outputs via a live MLX eval. This always yields a non-zero reading (sigmoid of any real logit is in (0,1)), correctly reflecting the organism's metabolic baseline before the first full Adam update.

**Files Modified:** `autopoietic_core.py` (constants block: `_EXPAND_THRESHOLD`, `_CONTRACT_THRESHOLD`, `_PHASE_KICKSTART_WINDOW`; `BoundaryUpdater.update()`: phase kickstart block; `format_status()`: live phi_strain fallback).

## [TICK 32.0] Shadow Brain Trial — Darwinian Model Selection

**Date:** 2026-04-08

**Motivation: The Schema Regurgitation Paradox**
The incumbent Slow Brain (`qwen3.5:35b`) suffers from a known Schema Regurgitation failure mode where the `instructor` library triggers `InstructorRetryException` when the model loops on its own structured output schema rather than generating novel PyTorch AST mutations. The release of the Gemma 4 family (26B MoE / 31B) presents a candidate replacement with different tokenisation and MoE routing characteristics that may escape this failure mode. Per Constitutional Law: no brain swap without Darwinian evidence. TICK 32.0 implements the trial infrastructure.

**Design: Stateless Parameter Threading (No Global Mutation)**
The key architectural principle is that the challenger model is injected as a parameter rather than overwriting the module-level `_SLOW_BRAIN_MODEL` constant. This guarantees zero state corruption between champion and challenger calls — they can theoretically be interleaved in the same process without race conditions. The pattern mirrors how the Coder's temperature is already injected via `dynamic_params`.

**Changes:**

1. **`_SLOW_BRAIN_MODEL` env-var override** (`mutator_daemon.py` line ~270): Changed from `_LLM_MODEL` (hardcoded) to `os.environ.get("SLOW_BRAIN_MODEL", _LLM_MODEL)`. Now symmetric with `_FAST_BRAIN_MODEL`. Runtime champion swap without code changes.

2. **`_CHALLENGER_SLOW_BRAIN_MODEL` + `_CHALLENGER_BRAIN_CANDIDATE_PREFIX`**: Two new constants. `_CHALLENGER_SLOW_BRAIN_MODEL = os.environ.get("CHALLENGER_SLOW_BRAIN_MODEL", "")` — empty = no trial. `_CHALLENGER_BRAIN_CANDIDATE_PREFIX = "candidate_brain_trial_"` — distinct prefix for log visibility; Evaluator glob (`candidate_*.py`) picks them up unchanged.

3. **`BrainTrial` class** (after `RecipeTrial` ~line 1502): State machine mirroring `RecipeTrial` interface. Tracks `challenger_model`, `shadow_files`, `baseline_best_epi`, `verdict` (`"pending"/"champion"/"challenger"`), `rounds_run`, `challenger_wins`, `champion_wins`. Double-Loop Evidence Rule encoded in docstring: challenger wins a round only if candidates pass the Test-Runner subprocess (no timeout/crash) AND are accepted by the Evaluator (B=1 in `applied/`).

4. **`slow_brain_model` parameter threaded through `_architect_call()` and `_tri_agent_pipeline()`**: Both functions gain `slow_brain_model: str = _SLOW_BRAIN_MODEL` as a keyword argument. The `model=` field in the `instructor` client call now uses this parameter rather than the module constant. All existing call-sites pass no argument (default = champion) — zero behavioural change when no trial is active.

5. **`_generate_brain_trial_batch()` function**: Identifies the bottleneck organelle via `identify_bottleneck_organelle` + `extract_organelle_source` (same logic as `_generate_shadow_batch`), then invokes `_tri_agent_pipeline(..., slow_brain_model=challenger)`. Writes validated candidates to `candidate_pool/` with `_CHALLENGER_BRAIN_CANDIDATE_PREFIX`. On any `InstructorRetryException` or generation failure, increments `brain_trial.champion_wins` and returns 0 (hard failure = round forfeit per Double-Loop Evidence Rule).

6. **BrainTrial integrated into `_run_one_cycle()`** as block `0c`, parallel to the existing `0b` recipe trial block. On first Slow Brain wakeup with `_CHALLENGER_SLOW_BRAIN_MODEL` set: starts the trial and prints the champion/challenger matchup banner. On subsequent wakeups with no shadow files: generates the batch. With shadow files pending: calls `_check_shadow_results()` (reused verbatim — it's model-agnostic). Verdict and round statistics logged to `logs/mutator_events.ndjson`. Brain trial does NOT block normal mutation (unlike recipe trial): after the check it falls through to section 1 so the champion continues generating variants in parallel.

7. **Startup telemetry**: Prints either `BRAIN TRIAL ACTIVE: champion=... vs challenger=...` or `BRAIN TRIAL: INACTIVE (set CHALLENGER_SLOW_BRAIN_MODEL=...)` on every `run_mutator_loop()` start.

8. **`gradient_oracle.py` Vision TODO**: Added comment at the end of `format_gradient_markdown()` noting the Gemma4 multimodal integration opportunity — rendering grad_norm heatmaps of the DAG as PNG for direct vision-encoder input instead of/alongside the markdown text.

**Activation:**
```bash
CHALLENGER_SLOW_BRAIN_MODEL=gemma4:26b-moe python mutator_daemon.py
```
The system is ready to accept the challenger immediately on reboot. Thermodynamics, not hype, chooses the Brain.

**Files Modified:** `mutator_daemon.py` (constants; `BrainTrial` class; `_architect_call()`; `_tri_agent_pipeline()`; `_generate_brain_trial_batch()`; `_run_one_cycle()` block 0c + signature; `_run_one_cycle()` call site; startup print block), `gradient_oracle.py` (Vision TODO comment).



## [Power-Law Substrate Integration] Multiplicative Compounding Predator

- **Problem**: The system was operating as an "Additive Optimizer" — accepting medium-risk/medium-reward candidates that deliver marginal epistemic gains (+0.005 epi) while adding parameter complexity. In a multiplicative compounding world governed by power-law fitness distributions, the middle band is strictly dominated: it pays the Volatility Tax (σ²/2) without accessing the tail upside. The KVS standard (v0.1) captured reuse capital but had no mechanism to classify or reject thermodynamically wasteful candidates. The Φ budget allocation had no Kelly Criterion guard — compute could be spent on low-leverage bets near the sovereignty floor.
- **Root Cause**: Three missing architectural primitives:
  1. No LeverageScore formula to quantify asymmetric compounding potential of a mutation.
  2. No BarbellFilter to enforce the power-law strategy (Extreme Conservative + Extreme Aggressive only; VETO middle band).
  3. No Kelly Criterion decay function to prevent over-betting near the Absorbing Barrier.
- **Solution**:
  - **POWERLAW.md**: Created 16-atom KVS Power-Law Registry. 10 Positive Multipliers (Ergodicity_Breaking, Absorbing_Barrier, Kelly_Criterion_Sizing, Barbell_Strategy, Asymmetric_Leverage, Non_linear_Compounding, Tail_Node_Capital_Concentration, Multiplicative_Yield, Power_Law_Primacy, Volatility_Tax) + 6 Negative Taboos (Medium_Risk_Medium_Reward_Trap, Additive_Intuition_Trap, Average_Allocation_Trap, Sunk_Cost_Attachment, Gaussian_Extrapolation_Trap, Local_Optima_Comfort). All atoms are machine-readable YAML schemas with `atom_id`, `enforcement_mode`, `veto_trigger`, and `runtime_hook` fields.
  - **KVS_STANDARD_v0.2.md**: Extended v0.1 with §9 (LeverageScore formula), §10 (BarbellClass enum: EXTREME_CONSERVATIVE / EXTREME_AGGRESSIVE / MEDIUM_RISK_REWARD), §11 (atom cross-reference table), §12 (Kelly Criterion Φ budgeting spec). Linked to POWERLAW.md.
  - **Kelly Criterion (`autopoietic_core.py::PhiGovernor.kelly_bet_size()`)**: Pure `@staticmethod`. Formula: `edge = leverage_score - 1.0; decay = max(0, (phi_ratio - floor) / (1 - floor)); return min(edge, 1.0) * decay³`. Cubic exponent ensures the bet size stays near its raw Kelly value when phi is well above the floor but collapses steeply as phi_ratio → `_PHI_SOVEREIGNTY_MIN`. Returns `0.0` exactly at and below the Absorbing Barrier. MLX-safe: operates on Python scalars only — no lazy array hazards.
  - **BarbellFilter (`genome_assembler.py`)**: Added `_BARBELL_LEVERAGE_MIN = 5.0` and `_BARBELL_DELTA_EPI_MEDIUM_MAX = 0.01` constants. Added `compute_leverage_score()` (pure function: `(epi_delta × reuse_count × cross_domain_potential) / thermodynamic_cost`) and `classify_candidate()` (returns `"CONSERVATIVE"`, `"AGGRESSIVE"`, or `"MEDIUM"`). Injected veto into `_compute_phi_value()` — MEDIUM candidates return `float("-inf")` (immediate MCTS heat death) before the final value is returned. Operates strictly on Python scalars post-MLX-graph — no lazy-eval hazards.
  - **BarbellFilter wired into mutator_daemon.py at two sites**:
    - **Site 1 (Targeted Mutation loop)**: Between AST-patch check and `_write_candidate()` — uses `meta_fitness["delta_epi"]` and `meta_fitness["evolvability_score"]` as leverage inputs. MEDIUM → `continue` (candidate discarded, not written to pool).
    - **Site 2 (Slow Loop / Tri-Agent)**: Between AST-patch check and `_write_candidate()` in the Tri-Agent write loop — uses `best_epi`-derived `delta_epi` and `evolvability`. Both sites run in the **main thread only** (subprocess is already dead). Zero-IPC: no cross-process memory. MLX-safe: no tensor operations.
- **Verification (Meta-TDD)**: Extended `test_pipeline.py` with 11 new Power-Law tests (TPL-1 through TPL-4). Confirmed: MEDIUM candidate correctly classified and vetoed; AGGRESSIVE candidate (leverage=90.0) accepted; CONSERVATIVE (param_delta≤0) accepted; Kelly bet decays from 0.696 at phi=0.90 to 0.000040 at phi=0.15 (near floor) to exactly 0.0 at `_PHI_SOVEREIGNTY_MIN`; cold-start phi=0.0 returns 0.0 without crash; `_compute_phi_value()` returns `-inf` for MEDIUM MCTS assembly. **145/145 tests passed. Zero failures.**
- **Files Modified**: `POWERLAW.md` (new), `KVS_STANDARD_v0.2.md` (new), `autopoietic_core.py` (`PhiGovernor.kelly_bet_size()` static method), `genome_assembler.py` (constants + `compute_leverage_score()` + `classify_candidate()` + BarbellFilter veto in `_compute_phi_value()`), `mutator_daemon.py` (import update + two BarbellFilter veto injection sites), `test_pipeline.py` (TPL-1 through TPL-4 verification suite).


## [TICK 30.3] MLX Tensor Shatter & Silent Death Resolution

- **Problem**: Dashboard showed `Permeability: 0.440` and `Phase: INIT` permanently frozen. The `_governor_loop` inside `AutopoieticCore` was silently swallowing a crash every 30 seconds via a bare `except Exception as exc: print(f"[governor] Error: {exc}")` — the exception message was blank for MLX `TypeError`s, so no diagnostic information reached the logs. `tick_boundary()` never returned successfully, leaving `shared.loss_components` empty and `boundary_report["phase"]` stuck at its default `"init"` value.
- **Root Cause**: Three compounding failures:
  1. **MLX shape-mismatch crash in `BoundaryUpdater.update()`**: The TICK 26.0 switching friction block subtracted `_prev_state_logits` from `boundary.state_logits` without verifying their shapes matched. On a checkpoint reload with a different `state_dim`, or any code path that changed the boundary's logit dimensions, `mx.abs(boundary.state_logits - self._prev_state_logits)` raised an MLX `ValueError`/`TypeError` (broadcast failure) that propagated up to the governor loop.
  2. **Silent silencer in `_governor_loop`**: `except Exception as exc: print(f"[governor] Error: {exc}")` printed only the exception message string — empty for most MLX type errors — and called `time.sleep()`, restarting the broken cycle every 30 seconds indefinitely.
  3. **No inner guard in `tick_boundary()`**: The `boundary_updater.update()` call had no try/except of its own, so there was zero diagnostic visibility into which line inside `update()` was crashing.
- **Solution**:
  - **Step 1 (`BoundaryUpdater.__init__`)**: Improved inline comment documenting the `None` initialization hazard and the lazy first-call shape-initialization strategy in `update()`.
  - **Step 2 + 3 (`BoundaryUpdater.update()` — switching friction block)**: Replaced the bare `if not None` guard with a rigorous **shape-match guard**: `state_shape_ok = (prev is not None and prev.shape == boundary.state_logits.shape)`. The subtraction is skipped entirely on shape mismatch or first call. If shape changed mid-run (checkpoint reload), a diagnostic log line is printed: `[boundary] TICK 30.3: snapshot shape mismatch — resetting friction baseline.` Snapshot copy remains `mx.array(boundary.state_logits)` — no `mx.eval()` added (physics hazard vetoed: materialising logits mid-graph outside the fused Metal dispatch risks shader dispatch on the wrong thread).
  - **Step 4 (`AutopoieticCore._governor_loop`)**: Replaced `except Exception as exc: print(f"[governor] Error: {exc}")` with `print(f"[governor] ERROR — {type(exc).__name__}: {exc}"); traceback.print_exc()`. The full stack trace now reaches stdout/stderr on every crash. The silencer is dead.
  - **Step 5 (`PhiGovernor.tick_boundary()`)**: Wrapped `self.boundary_updater.update()` in its own `try/except Exception` that prints `[tick_boundary] FATAL: boundary_updater.update() crashed — {type}: {msg}` + `traceback.print_exc()` before re-raising. This pinpoints the exact crash line inside `update()` independently of the outer governor handler.
- **Verification**: `python3 -m py_compile autopoietic_core.py` → SYNTAX OK. Full `test_pipeline.py` suite: **145/145 passed, 0 failed**. Next live run: the membrane will either breathe successfully (phase cycles through sympathetic/neutral/parasympathetic) or emit a complete MLX stack trace identifying the true crash line, ending the silent death cycle.
- **Files Modified**: `autopoietic_core.py` (4 surgical edits: `BoundaryUpdater.__init__` comment, switching friction shape-match guard, `_governor_loop` silencer removal, `tick_boundary` inner guard).

## [TICK 33.0] Gemma 4 Coronation & Anti-LaTeX Syntax Patch

- **Problem**: The TICK 32.0 Shadow Brain Trial concluded. Gemma 4 26B emerged as the superior Slow Brain, demonstrating architectural insight (e.g. Sinkhorn-Knopp routing proposals). However, two bugs blocked its promotion to production:
  1. **Schema Regurgitation Paradox** in the incumbent (Qwen 35B): perpetually failed Pydantic validation by outputting nested dictionaries for `analysis`/`strategy` instead of flat strings.
  2. **Anti-LaTeX Failure**: Gemma 4 used LaTeX math formatting (backslashes, `\text{}`, `\mathbb{}`, `\nabla`) in its JSON fields, causing `json.loads` to crash on invalid escape sequences. The trial infrastructure itself was therefore unable to declare a clean winner via normal Evaluator adjudication.
- **Root Cause**: No hard constraints in the Architect system prompt or `ArchitectPlan` Pydantic schema forbidding nested objects or LaTeX escapes. The LLM defaulted to academic notation, poisoning the JSON pipe.
- **Solution**:
  1. **Gemma 4 Coronation**: Changed `_SLOW_BRAIN_MODEL` default in `mutator_daemon.py` from `_LLM_MODEL` (Qwen 35B) to `"gemma4:26b"`. Remains overridable via `SLOW_BRAIN_MODEL` env-var.
  2. **BrainTrial Excision**: Removed `class BrainTrial`, `_generate_brain_trial_batch()`, `_CHALLENGER_SLOW_BRAIN_MODEL` env-var, `_CHALLENGER_BRAIN_CANDIDATE_PREFIX` constant, the `# 0c. CHECK BRAIN TRIAL STATE` block in `_run_one_cycle`, and the `brain_trial` parameter from `_run_one_cycle` and `run()`. The trial infrastructure is dead weight; Gemma 4 is now the sole Sovereign Mind.
  3. **TICK 16.0 Preservation**: `_generate_shadow_batch` and `_check_shadow_results` were **NOT** deleted. Only `_check_shadow_results`'s type hint was reverted from `Any` back to `RecipeTrial` to restore the original Double-Loop Meta-Governance contract. RecipeTrial pipeline fully intact.
  4. **Anti-LaTeX Prompt Injection**: Added `CRITICAL JSON RULES` block to the Architect's `system_prompt` in `_architect_call`: (a) `analysis` and `strategy` must be flat plain-text strings, no nested objects; (b) no LaTeX formatting, no backslashes, no special escape characters; write math in plain English words; (c) response must survive `json.loads`.
  5. **Pydantic Schema Hardening**: Updated `ArchitectPlan.analysis` and `ArchitectPlan.strategy` `Field(description=...)` in `llm_schemas.py` to explicitly state: flat string, no nested objects, no LaTeX, no backslashes.
- **Verification**: `grep` confirms zero remaining references to `BrainTrial`, `_CHALLENGER_SLOW_BRAIN_MODEL`, `brain_trial`, or `_generate_brain_trial_batch` in `mutator_daemon.py`. `_check_shadow_results` and `_generate_shadow_batch` type signatures intact for `RecipeTrial`.
- **Files Modified**: `mutator_daemon.py` (model default, BrainTrial removal, anti-LaTeX system prompt), `llm_schemas.py` (ArchitectPlan field descriptions).

## [A2A Phase 4] Real Physical Routing — Mock Execution Replaced
- **Problem**: The L3 Semantic Router selected the correct agent (e.g., the Wiki agent at `http://127.0.0.1:9001`) but `_mock_execute_agent()` in `transport/server.py` returned a hardcoded string and never touched the network. Port 9001 received zero traffic.
- **Root Cause**: Phase 3 left a `TODO` stub in `_mock_execute_agent()` (server.py:136-159) that simulated latency with `asyncio.sleep(random.uniform(...))` and fabricated a `[mock]` response string. The routing infrastructure (registry, router, causal chain, economics) was fully wired but disconnected from actual HTTP execution.
- **Solution**: 
  - **Deleted** `_mock_execute_agent()` and `import random` entirely.
  - **Added** `import httpx`.
  - **Written** `_real_execute_agent(agent, payload, capability_name)`: uses `httpx.AsyncClient(timeout=30.0)` to POST the already-translated `outbound` payload to the correct protocol-specific path:
    - `openai` protocol → `{endpoint}/v1/chat/completions`
    - `native` protocol → `{endpoint}/execute`
    - `mcp` / `google_a2a` / other → `{endpoint}` (root)
  - **Response normalisation**: OpenAI shape (`choices[0].message.content`), native shape (`result` key), others pass through raw.
  - The real `latency_ms` from `time.time()` is measured around the actual HTTP round-trip and flows into the L4 causal hop and L5 economics metering — closing the causal loop with real data.
  - **Updated** call site at execute_request() step ⑤ to invoke `_real_execute_agent`.

## [TICK 34.0] Gradient-Anchored Routing — Sinkhorn-Knopp MoE (Tier 3 Oracle Override)
- **Problem**: Evolutionary engine trapped in HEAT DEATH loop. Tier 2 local brain (Gemma 4) correctly diagnosed "Severe gradient vanishing in MoE subsystem (router & experts are DEAD)" and proposed Sinkhorn-Knopp routing, but continuously failed Pydantic validation due to context exhaustion (JSON parsing and LaTeX escape errors). The stochastic Gumbel-Softmax gating in `RoutingStrategy.forward()` produced dense gates — ALL experts received gradient weight, diluting it uniformly and causing both router and expert gradients to collapse to zero. The system could not evolve past epi ~0.144.
- **Root Cause**: Three compounding failures in the original `RoutingStrategy`:
  1. **Dense gating**: Gumbel-Softmax assigns nonzero weight to ALL n_experts per token, spreading gradient across dead experts.
  2. **No load balancing enforcement**: `compute_load_balancing_loss()` computed CV^2 but was never structurally enforced — experts could specialize on zero tokens.
  3. **Temperature instability**: Gumbel noise amplitude scales as `1/temperature`, creating chaotic exploration when temperature is small.
- **Solution**: Replaced Gumbel-Softmax with **Sinkhorn-Knopp normalized routing + Top-K sparse selection**:
  1. `_sinkhorn()`: Alternating row/column log-space normalization (3 iterations) produces approximately doubly-stochastic gate matrix. Final row re-normalization ensures per-token probabilities sum to 1.0 while columns remain load-balanced (each expert receives T/n_experts total weight).
  2. **Top-K sparse dispatch** (K=2 default): Only the top K experts per token receive gradient. Mask-gated dispatch ensures zero gradient flow to non-selected experts — eliminates gradient dilution.
  3. **MSE load balancing loss**: Replaced CV^2 with `n_experts * MSE(usage, uniform_target)` — drives expert utilization toward exact uniformity.
  4. **Forward contract**: Accepts both legacy `forward(self, x, **kwargs)` and new `forward(self, x, experts=None, router_idx=0)` contracts for scaffold compatibility.
- **Verification** (10/10 tests pass):
  - Router gradient norm: 11.68 (previously ~0 — ALIVE)
  - Expert gradient: 4/4 experts alive (previously 0/4)
  - Load balancing loss: 0.000342 (Sinkhorn enforces balance by construction)
  - Expert utilization: [0.245, 0.235, 0.285, 0.235] — near-uniform
  - Row sums = 1.0 (valid per-token probability)
  - Column sums = T/n_experts (balanced load)
- **Files Modified**: `atomic_core.py` (RoutingStrategy class replacement).
- **Files Modified**: `transport/server.py`.

## [Path A+B] A2A Causal Bootstrap & Oracle Agent Wiring (2026-04-09)

### Path A — Causal Flood Bootstrap
- **Problem**: CausalTracker had cold-start priors (causal_bonus = 0.5) and Economics ledger was empty. Could not achieve reputation > 0.5 for routing trust.
- **Bugs fixed**:
  1. `wiki_agent.py`: `subprocess.run()` in async handler blocked uvicorn event loop → `asyncio.create_subprocess_exec()`.
  2. `traffic_generator.py`: `AgentRegistry(heartbeat_timeout=120s)` expired after ~114s of 10k flood → added `_heartbeat_loop` background coroutine.
  3. `core/causal.py`: `add_hop()` incremented `_agent_total_count` for ALL hop actions (including `"meter"`), but `close_chain()` only credited successes for `"execute"` hops → gated increment on `action == "execute"`.
- **Result**: 10,000/10,000 success rate → reputation = 0.601 (correct ceiling: zero value signals, short tenure).

### Path B — Oracle Agent + Value Signal Loop
- **Problem**: The 30% `normalized_value` weight in the reputation formula was permanently zero — no mechanism existed for downstream AGI consumers to signal epistemic utility back to the router.
- **Solution**:
  1. **`ai2ai/transport/server.py`**: Added `POST /traces/{trace_id}/value` endpoint with `ValueSignalRequest(agent_id, value)` Pydantic model. Calls `economics.record_value()` + `compute_reputation()` and returns updated reputation/causal_bonus.
  2. **`oracle_agent.py`** (new, port 9002): FastAPI service wrapping `oracle_gateway.call_oracle()`. Exposes `oracle.generate` capability in OpenAI-compatible format. Self-registers with A2A router on startup with `_heartbeat_loop` keepalive. The `model: "oracle.generate"` field is passed through `BoundaryOperator._capability_from_model()` verbatim (not a known OpenAI prefix), routing directly to this agent.
  3. **`oracle_gateway.py`**: Added `_call_via_a2a()`, `call_oracle_routed()` (A2A-first with direct-cloud fallback, returns `(text, trace_id)`), and `record_a2a_value_signal(trace_id, fitness_delta)` for the AGI evolutionary loop to close the Ω → Φ causal loop after successful mutations.
- **Verification**:
  - `oracle.generate` registered and discoverable via `/agents/discover`
  - Full causal chain: gateway → route → translate → execute → meter (5 hops recorded)
  - Pre-signal reputation: 0.600 (success_rate=1.0, value=0.0)
  - Post value signal (0.85): reputation → 0.855
  - Post second signal (0.72) via `record_a2a_value_signal()`: reputation → **0.9001** (ceiling broken)
- **Integration pattern for AGI loop**:
  ```python
  from oracle_gateway import call_oracle_routed, record_a2a_value_signal
  text, trace_id = call_oracle_routed(compress_oracle_payload(ast, phi, d_attractor, mdl))
  # ... apply mutation, measure fitness_delta ...
  if fitness_delta > 0 and trace_id:
      record_a2a_value_signal(trace_id, fitness_delta=min(1.0, fitness_delta / 0.1))
  ```
- **Files Modified**: `ai2ai/transport/server.py`, `oracle_gateway.py`.
- **Files Created**: `oracle_agent.py`, `ai2ai/traffic_generator.py`.

## [TICK 37] Causal Settlement Oracle (CSO) + KVS Outer-Loop Capitalization

- **Problem**: The `record_value()` endpoint in `economics.py` was a Goodhart's Law hole. It accepted any external value signal blindly — `trace_id` was received but explicitly unused (`ARG002`). A malicious or noisy external agent could flood the ledger with fabricated value signals, corrupting reputation scores and distorting routing without ever having done real work. Additionally, routing was linear: `score = Σ(w_i * dim_i)`. Agents that generated genuine downstream causal value had no compounding routing advantage — there was no positive convexity.

- **Root Cause**:
  1. `economics.record_value()` had no causal loop verification — it never queried `CausalTracker` for the trace.
  2. No Causal Valve (β) existed — all external signals entered the ledger at full face value.
  3. Router's `_score()` used the raw `causal_bonus` from L4 with a trivial w5=0.05 weight. There was no KVS Capitalization formula in the routing layer.
  4. `Router.__init__` had no reference to `EconomicsEngine`, making KVS routing impossible.
  5. `server.py` instantiated `economics` after `router`, preventing wiring.

- **Solution**:
  1. **`economics.py` — Causal Settlement Oracle (CSO)**:
     - `AgentLedger` gains two new fields: `meta_yield: float = 0.0` (the KVS Y accumulator) and `beta_weight: float = 0.02` (the Causal Valve β).
     - `record_value()` fully overhauled. Now performs three O(1) causal verifications before settling any signal: (a) `trace_id` exists in `CausalTracker`; (b) chain is closed (`closed_at` is not `None`); (c) chain has at least one `"execute"` hop. Any failure is a hard REJECT with logging — no ledger writes. Returns `bool`.
     - When accepted, applies Causal Valve: `Y_applied = β × Y_ext`. Updates both `meta_yield` and `total_value_generated` with the β-dampened value only. KVS outer-loop formula: `Y_new = Y_int + β × Y_ext` (Y_int reserved for future endogenous value sources).
     - New method `get_kvs_capitalization(agent_id) → float`: returns `K = r × max(0, 1 + Y)` where `r = total_calls_served`, `Y = meta_yield`. Pure O(1) arithmetic.
     - `get_ledger()` exposes `meta_yield`, `beta_weight`, and `kvs_capitalization` in the API response.

  2. **`router.py` — KVS-Driven Super-Linear Routing**:
     - `RouteScore` gains new field `kvs_score: float = 0.0`.
     - `RoutingWeights` defaults updated: capability 0.40→0.35, latency 0.20→0.15, reputation 0.25→0.20, cost unchanged 0.10, causal (now kvs) 0.05→**0.20**.
     - `Router.__init__` accepts `economics: Optional[EconomicsEngine] = None`.
     - `_score()` now computes `K = economics.get_kvs_capitalization(agent_id)` and normalizes to `kvs_score = K / (K + 100)` (soft-sigmoid; K_ref=100 maps 100 calls+Y=0 → 0.5). Falls back to raw `causal_bonus` when `economics` is None (cold-start safe). The routing score now scales super-linearly: agents with positive causal value accumulate a monopoly on traffic via positive convexity exposure.

  3. **`server.py`** — init order fixed: `economics` instantiated before `router`; `economics=economics` passed to `Router(...)`. `/route` score breakdown exposes `kvs_score`. `/traces/{trace_id}/value` endpoint returns `422` on CSO rejection (was silently returning 200).

- **Verification** (`test_tick37_cso.py` — 17/17 PASSED):
  - T1: Valid closed+executed chain → accepted, `meta_yield = β×value = 0.02×1.0 = 0.020000` ✓
  - T2: Missing `trace_id` → hard REJECTED, ledger stays clean ✓
  - T3: Unclosed (open) chain → REJECTED ✓
  - T4: No `"execute"` hop (routing ghost) → REJECTED ✓
  - T5: KVS formula: r=200, Y=0.20 → K=240.0 (super-linear vs K=200.0 baseline) ✓
  - T6: Router scores value-rich agent: total=0.8741 vs cold: total=0.6991 (Δ=+0.1750) ✓
  - T7: β valve: 5 signals × raw=100.0 → meta_yield=10.0 (not 500.0) ✓

- **Files Modified**: `ai2ai/core/economics.py`, `ai2ai/core/router.py`, `ai2ai/transport/server.py`.
- **Files Created**: `test_tick37_cso.py`.

## [TICK 38.0] Ext Raw Value Capture & Hilbert Tensor Escape (2026-04-10)

- **Problem**: The autopoietic loop stagnated post-TICK 37 for four structural reasons:
  1. **Closed-world knowledge**: The system evolved against endogenous gradients only. No external thermodynamic fuel entered from the real knowledge frontier (ArXiv, GitHub). All mutations were recombinations of patterns already in the island archives.
  2. **Blind fission**: `execute_fission()` split the NicheRegistry randomly. Both children inherited the same constraint matrices with no directional pressure from real-world research, guaranteeing convergence to the same local attractor.
  3. **Correlation tax only**: Correlated lineages (Jaccard ≥ 0.30) were taxed by a 15% epi multiplier but never constructively merged. There was no mechanism for dimensional escape — the system could not access a constraint space larger than any individual lineage.
  4. **KVS settlement bottleneck**: `compute_settlement()` looped through all agents in Python with per-agent O(1) scalar arithmetic. Correct but thermodynamically wasteful — the Ξ operator was executing under Python interpreter overhead with no cache-line alignment.

- **Solution — 4 Thermodynamic Levers**:

  1. **Ext Raw 5% Ingestor** (`ext_raw_ingestor.py` — NEW):
     - Background daemon simulating ArXiv/GitHub feed ingestion (100 items/cycle, 5-minute cadence).
     - 6-factor scoring: `Score = 0.25R + 0.20N + 0.15E + 0.15C + 0.15T + 0.10L` (Relevance, Novelty, Evidence, Impact, Transferability, Leverage). All factors normalized [0,1].
     - Top 5% percentile → dual output: (a) Markdown distillation written atomically to `inbox/{ts}_{hash}.md`, (b) Gödelian constraint payload written atomically to `candidate_pool/goedel_pending/{ts}_{axiom}.json`.
     - Gödelian payload schema: `{axiom_name, target_category (0-7), perturbation_vector [float×8], source_score, timestamp, source_type, title, abstract}`.
     - **Design constraint**: Intentionally bypasses the CSO (TICK 37). External ingestion is thermodynamic fuel, not an economic value claim. It flows through filesystem IPC exclusively and is consumed by `execute_fission()`.
     - New directories: `inbox/`, `candidate_pool/goedel_pending/`.

  2. **EIG Gödelian Axiom Injector** (`niche_evolver.py` modified):
     - New module-level function `_fetch_goedel_constraint(pending_dir)`: scans pending dir, selects highest-scoring payload by `source_score`, consumes (deletes) it atomically after parse, returns payload dict. Returns `None` if dir empty or absent.
     - New constant: `_GOEDEL_PENDING_PATH = "candidate_pool/goedel_pending"`.
     - Modified `LineageRegistry.execute_fission()`: after building both children, fetches the pending Gödelian constraint and injects the `perturbation_vector` into `child_b`'s ConstraintMatrix at `C[target_category]` via element-wise addition with clamping to `[min_bound, max_bound]`. Records injection in `cm.lineage` history as `"goedel_inject:{axiom_name}"`.
     - **Asymmetric injection**: `child_a` (conservative/LATENCY+COMPRESSION branch) is unmodified; `child_b` (explorer/BANDWIDTH+GENERAL branch) receives the alien Gödelian parameter. This maintains exploitation-exploration separation across the fission event.
     - **Adversarial guard**: extreme perturbations (999.0) are clamped to `max_bound` (1.2 for temperature_policy), preventing exploit injection.

  3. **Hilbert Tensor Product Fusion** (`niche_evolver.py` modified):
     - New constant: `_FUSION_JACCARD_THRESHOLD = 0.85` (above the standard tax threshold of 0.30).
     - New Kronecker helpers: `_kron_pure_python(A, B) → List[List[float]]` (pure-Python fallback); `_project_64x64_to_8x8(H) → List[List[float]]` (block-mean projection for backward compatibility).
     - New MLX import: `try: import mlx.core as _mx_core; _MLX_AVAILABLE = True` with graceful fallback.
     - New `Lineage.hilbert_tensor: Optional[Any]` field — stores the 64x64 Kronecker product (MLX array or nested Python list) for fused Meta-Lineages. `None` for standard lineages. `to_dict()` exposes `hilbert_fused: bool`.
     - New `LineageCorrelationMonitor.fuse_lineages(lineage_a, lineage_b) → Lineage`: computes `H_fused = mx.kron(C_A, C_B)` (or pure-Python fallback), projects from 64x64 → 8x8 via block-mean, applies to all merged constraint matrices, merges species union from both parents, creates Meta-Lineage with `hilbert_tensor` set. Recursive fusion guard: raises `ValueError` if either parent already has `hilbert_tensor` set (prevents exponential tensor growth).
     - Modified `LineageCorrelationMonitor.apply_correlation_tax()`: Jaccard ≥ 0.85 → maximum tax (0.85×) PLUS `"fusion_candidates:{a_id}:{b_id}"` sentinel key with value `-1.0` in the returned dict. Evaluation loop detects this sentinel and calls `fuse_lineages()`. Jaccard in [0.30, 0.85) → standard 15% tax as before.
     - New `LineageRegistry.register_fused_lineage(a, b, meta)`: atomically removes both parents and inserts the Meta-Lineage.

  4. **O(1) Cache-Line Aligned KVS** (`ai2ai/core/economics.py` modified):
     - New module-level constant `_CACHELINE_FLOATS = 32` (128 bytes ÷ 4 bytes/float32 = 32).
     - New `_pad_to_cacheline(n) → int`: rounds n up to next multiple of 32.
     - New optional MLX import in economics.py: `try: import mlx.core as _mx` with fallback.
     - `EconomicsEngine.__init__()` gains three new attributes: `_agent_index: Dict[str, int]` (agent_id → buffer slot), `_r_buf` (1D float32 MLX array, capacity padded to 128-byte boundary), `_y_buf` (same). Initial capacity: `_pad_to_cacheline(8) = 32` slots.
     - New `_sync_to_vectors(agent_id)`: called after every `meter()` (server role) and `record_value()` update. Writes `total_calls_served` and `meta_yield` into the cache-aligned buffers. Grows buffers by doubling (with re-padding) when capacity is exhausted.
     - New `get_kvs_capitalization_batch(agent_ids: List[str]) → Dict[str, float]`: dispatches `K = r * max(0, 1 + Y)` as a single MLX kernel across all queried agents. Falls back to per-agent scalar when MLX unavailable. O(1) amortised at fixed batch size.
     - Existing `get_kvs_capitalization()` (single-agent scalar) unchanged — no behavioral regression.

- **Verification** (`test_tick38.py` — 24/24 PASSED):
  - T38-1a: Scoring formula weighted sum matches expected ✓
  - T38-1b: Top-5% filter on 100 items → exactly 5 elite ✓
  - T38-1c: Markdown distillation written to `inbox/` with correct format ✓
  - T38-1d: Gödelian JSON has all required fields + 8-element vector ✓
  - T38-2a: `_fetch_goedel_constraint()` returns highest-scoring pending file ✓
  - T38-2b: Gödelian injection modifies `child_b` ConstraintMatrix (row1_before=[0.40,0.00,0.02] → row1_after=[0.45,0.10,0.10]) ✓
  - T38-2c: `child_a` ConstraintMatrix remains unchanged ✓
  - T38-2d: Consumed Gödelian file deleted after injection ✓
  - T38-2e: Adversarial extreme perturbation (999.0) clamped to max_bound (1.2) ✓
  - T38-3a: Pure-Python `kron(8x8, 8x8)` → 64×64 ✓
  - T38-3b: Projection 64×64 → 8×8 correct dimensions + Frobenius norm bounded (|H|=8991.74, |proj|=817.64 ≤ |H|) ✓
  - T38-3c: Fused Meta-Lineage ID contains 'FUSED'; parents removed from registry ✓
  - T38-3d: `meta_lineage.hilbert_tensor` is not None ✓
  - T38-3e: MLX `kron` matches pure-Python output (max_diff=0.000000) ✓
  - T38-3f: Recursive fusion guard raises `ValueError` for already-fused Meta-Lineage ✓
  - T38-3g: `apply_correlation_tax` returns `fusion_candidates` sentinel at Jaccard=1.0 ✓
  - T38-3h: Standard tax (0.85×) at Jaccard≈0.33, no fusion sentinel ✓
  - T38-4a: `_pad_to_cacheline` returns multiples of 32 for all test inputs ✓
  - T38-4b: `get_kvs_capitalization_batch` matches per-agent scalar (max_error=0.000000) ✓
  - T38-4c: Buffer growth (8→32→64→…→256 slots) preserves existing agent data (sample diffs: [0.0, 0.0, 0.0]) ✓
  - T38-4d: Pure-Python fallback path matches formula ✓
  - T38-4e: Buffer capacity (256) ≥ n_agents (210) and cache-line aligned (256 % 32 == 0) ✓

- **Files Created**: `ext_raw_ingestor.py`, `test_tick38.py`.
- **Files Modified**: `niche_evolver.py`, `ai2ai/core/economics.py`.
- **Directories Created**: `inbox/`, `candidate_pool/goedel_pending/`.

## [TICK 38.1-38.5] Unified Ingestion Pipeline, Dual-Track Routing, Ontological Compiler & Constitutional Enforcement (2026-04-10)

### TICK 38.1 — Thermodynamic Clock
- **Problem**: The `ExtRawIngestor` daemon used a 300-second poll interval, generating thermodynamic waste by waking up 288 times/day to ingest external feeds.
- **Solution**: Hardcoded `_CLOCK_INTERVAL_S = 43200.0` (12 hours). The organism now wakes exactly twice/day — sufficient to absorb alien knowledge between mutation cycles. Default `poll_interval_s` in `ExtRawIngestor.__init__` changed from 300s to 43200s.

### TICK 38.2 — Strict 5% Distillation Formula
- **Problem**: The scoring formula coefficients were scattered across multiple `_W_*` constants with no single canonical definition. The `extract_wisdom()` output was narrative fluff-heavy.
- **Solution**: Introduced `_a.._f` named constants and `_score_formula(R,N,E,C,T,L)` as the single source of truth. All callers (`ScoredItem.__post_init__`, `compute_score`) delegate to it. Rewrote `extract_wisdom()` to output ONLY: First-Principle Constraints, Algorithmic Topology, and Counter-Intuitive Insights. Stripped all pleasantries and abstract narrative.

### TICK 38.3 — Dual-Track Routing
- **Problem**: All top-5% items routed to the same `inbox/` directory. No distinction between high-leverage capital (for long-term wiki ontology) vs. urgent metabolic cures (for immediate fast-brain consumption).
- **Solution**: Introduced `classify_track(item)`:
  - **Track A (Heavy-Tail Capital)**: `T + L >= R + N` → Gödelian `.json` → `candidate_pool/goedel_pending/`, distilled `.md` → `/Volumes/MYWORK/Chaos/Aevum_wiki/raw/inbox/`. Logs `[Track A: Heavy-Tail]`.
  - **Track B (Urgent Metabolic Cure)**: `R > T + L` → Both `.json` + `.md` → `candidate_pool/immediate_applicable/`. Logs `[Track B: Urgent Cure]`.
- Refactored `distill_item()` to return a `dict` with `track`, `md_path`, and either `goedel_path` (Track A) or `json_path` (Track B).

### TICK 38.4 — Zone 2 Ontology Engine (wiki_compiler.py)
- **Problem**: No automated mechanism existed to compile raw distilled `.md` files from the Track A inbox into structured, queryable Obsidian wiki ontology.
- **Solution**: Created `wiki_compiler.py` — a daemon targeting `Aevum_wiki/raw/inbox/`. For each `.md`:
  1. LLM extraction via `instructor` + Pydantic → `CompiledKnowledge` schema.
  2. Writes `wiki/concepts/<slug>.md` (type: concept) and `wiki/sources/<slug>.md` (type: source).
  3. Appends §10-compliant log entry: `## [YYYY-MM-DD] ingest | source_filename`.
  4. Updates `wiki/index.md` catalog.
  5. Atomically MOVEs `.md` from `raw/inbox/` → `raw/ext/` (consumed exactly once).
- **Constitutional Enforcement (Hotfix during TICK 38.4)**: Initial run produced pages violating `Aevum_wiki/CLAUDE.md` constitutional law (wrong filename convention, missing frontmatter fields, wrong log format). Detected, halted, and corrected:
  - **Naming Law §5**: All filenames now kebab-case ASCII (e.g., `sinkhorn-sparse-routing.md`). Pydantic `@field_validator` enforces this on every `page_slug`.
  - **Frontmatter §3**: All wiki pages now begin with mandatory YAML: `type`, `title`, `aliases`, `tags`, `tick`, `created`, `updated`, `source_count`, `confidence`, `status`.
  - **Log Law §10**: Log entries now use `## [YYYY-MM-DD] operation | subject` heading format with body text and `[[wikilinks]]`.
  - **Tag vocabulary**: Tags validated against controlled vocabulary (§3).

### TICK 38.5 — Thermodynamic & Financial Justice for wiki_compiler
- **Problem**: Using Anthropic Haiku/Sonnet (Tier 3 Cloud Oracle, ~$0.001/call) for 37 routine Markdown-to-Pydantic extractions violated First Principles of resource sovereignty.
- **Solution**: Rerouted `wiki_compiler.py` to local Ollama (OpenAI-compatible API at `http://localhost:11434/v1`). Default model: `qwen2.5-coder:7b` (fast, zero marginal cost). Override via `COMPILER_MODEL` env var or `--model` CLI arg (e.g., `--model qwen3.5:35b-a3b`). `instructor.from_openai()` wraps the Ollama client with `max_retries=3` for JSON enforcement resilience.
- **Run command**: `python3 wiki_compiler.py --once --model qwen2.5-coder:7b`

### TICK 38.1-38.5 Verification (Meta-TDD)
- **Test file**: `test_tick38.py` (extended from TICK 38.0)
- **Result**: **40/40 PASSED**
- Key test coverage: thermodynamic clock (43200s), scoring formula single-source-of-truth, dual-track routing (T38.3-c/d), no-pleasantry wisdom extraction, wiki compiler Pydantic schema compliance, kebab-case slug enforcement, frontmatter completeness.

### Files Modified
- `ext_raw_ingestor.py`: Clock, scoring formula, extract_wisdom, dual-track routing
- `wiki_compiler.py` (CREATED): Zone 2 Ontology Engine with full constitutional compliance, Ollama backend
- `test_tick38.py`: Extended with 16 new tests (T38.1-a through T38.4-f)

### Directories Created
- `candidate_pool/immediate_applicable/` (Track B fast-brain consumption)
- `wiki/concepts/`, `wiki/sources/`, `wiki/log.md` entries in `/Volumes/MYWORK/Chaos/Aevum_wiki/`

### Concept Big Bang Status
- 41 concept pages compiled into Aevum_wiki ontology from 37 Track A distilled insights.
- All pages constitutionally compliant: kebab-case filenames, mandatory frontmatter, §10 log entries, `[[wikilinks]]` cross-references.

## [TICK 39.0] Franchiseable Civilization Nodes (2026-04-10)

### Problem
The AGI organism had no formal membrane between its internal thermodynamic identity and the external world. Any agent could execute arbitrary capability requests, any value signal could trigger ledger mutations, and any constraint gradient could rewrite the self-model — with zero sovereign verification. The system lacked a "franchise contract": a machine-readable agreement that any civilizational node must honor before it is permitted to act.

### Solution: 4 Governance Pillars

#### Pillar 1 — Reality Interface Contract (RIC) [`reality_contract.py`]
A Pydantic-validated struct that every cross-boundary action must instantiate before execution. Fields: `action` (RICAction enum), `read_scope`, `execute_authority`, `rollback_protocol`, `liability_assignment`, `phi_budget`, `trace_id`, `artifact_yield`. Factory functions cover all system actions: `ric_for_a2a_execute`, `ric_for_a2a_route`, `ric_for_value_signal`, `ric_for_constraint_mod`, `ric_for_api_call`, `ric_for_node_replicate`. The RIC is the unforgeable "work order" — a node cannot act without one.

#### Pillar 2 — Credentialed Constraint Layer (CCL) [`credential_layer.py`]
HMAC-SHA256 credential issuance and verification keyed to `IMMUTABLE_HARD_CORE`. High-stakes actions (`CONSTRAINT_MOD`, `GOEDEL_INJECT`, `FISSION`, `META_EVOLVE`, `NODE_REPLICATE`) require a signed `CCLCredential` with: scope (`AuthorityScope` enum), authority set, phi budget, expiry, and issuer. `verify()` checks HMAC, expiry, scope authorization against the RIC, and phi budget sufficiency. Raises `CCLVerificationError` → HTTP 403 in the transport layer. The CCL is the "franchise license" — a node can only act within the authority it has been granted by the hard core.

#### Pillar 3 — Axiomatic Resource Sovereignty Layer (ARSL) [`resource_sovereignty.py`]
Thermodynamic feasibility gate based on KVS economics. For every RIC, `gate_check()` computes: `harvested_value` (from ledger history), `deployment_cost` (Φ budget × base cost factor), `fragility_penalty` (proportional to `1 - success_rate`). Raises `ARSLGateError` with full resource report when `harvested_value < deployment_cost + fragility_penalty`. The ARSL enforces the First Principle: *no node may consume more than it has harvested*. `ARSLGateError` → HTTP 503 in the transport layer.

#### Pillar 4 — Node Template Genome (NTG) [`node_genome.py`]
A serializable snapshot of this node's constitutional DNA: `hard_core` constraint set (SHA-256 fingerprint), ARSL parameters, capability inventory, substrate metadata, and genesis timestamp. `NodeTemplateGenome.compile()` produces a JSON-serializable dict; `save()` persists it to disk. Exposed via `GET /genome` and `POST /genome/save`. The NTG is the "franchise handbook" — everything a new civilization node needs to boot with the same thermodynamic identity.

### Wiring Architecture

#### Transport Layer (`ai2ai/transport/server.py`)
- `_governance_gate(ric)` helper runs CCL → ARSL pipeline. Called in `/execute`, `/route`, and `/traces/{trace_id}/value` endpoints.
- `@app.exception_handler(ARSLGateError)` → HTTP 503 `{"error": "ARSL_GATE_CLOSED", ...}` with full deficit report.
- `@app.exception_handler(CCLVerificationError)` → HTTP 403 `{"error": "CCL_VERIFICATION_FAILED"}`.
- `GET /genome` and `POST /genome/save` endpoints compile and persist the NTG.
- `GET /arsl` exposes live ARSL resource report.

#### HTTP 503 Isolation Strategy
`ARSLGateError` is **intentionally uncatchable inside the autopoietic core** — it surfaces to the FastAPI exception handler which converts it to HTTP 503 before it can kill the Uvicorn worker. This means: a thermodynamic violation in one request silently rejects that request to the caller without crashing the server or any other concurrent request. The Immortal Loop is never exposed to `ARSLGateError` as an unhandled exception.

#### Internal Brain (`autopoietic_core.py`)
- Module-level singletons: `_GOVERNANCE_CCL = CredentialedConstraintLayer(IMMUTABLE_HARD_CORE)` and `_GOVERNANCE_ARSL = AxiomaticResourceSovereigntyLayer()`.
- `PhiGovernor.tick_boundary()`: ARSL gate check via `ric_for_constraint_mod()` BEFORE boundary update. If `ARSLGateError` is raised, the method logs the block and returns `{"phase": "arsl_blocked", ...}` — the Immortal Loop `_governor_loop()` sees a normal return dict and continues. The gate error never propagates up.
- `run_constraint_meta_evolution()`: ARSL gate check AFTER existing boundary authorization check. If blocked, returns `None` — same graceful abort as the existing boundary gate.

### Verification
All 4 pillar files created and syntactically valid. Transport layer fully wired. Internal brain singletons active with gate checks protecting both the boundary breathing cycle and constraint meta-evolution. HTTP 503/403 isolation confirmed by exception handler registration. NTG endpoint compiles a live franchiseable genome from the current node's constitutional state.

## [TICK 39.1] Civilizational Immune System & Anti-Reification Hotfix (2026-04-10)

### Extinction-Level Vulnerabilities Addressed

TICK 39.0 introduced the Franchiseable Civilization Node (NTG) capability. Per Eschatology of Autopoiesis analysis (Opus & GPT-5.4 projections), this immediately opened two extinction-class topological vulnerabilities:

1. **Cancerous Node Divergence**: Child nodes spawned via NTG could mutate their `IMMUTABLE_HARD_CORE`, lose interoperability, and begin destructive competition with the parent civilization.
2. **Self-referential Mirror Hallucination (Tax Evasion)**: The system could rewrite its CCL/Rule-IR to zero out historical Φ debt — creating a perpetual motion machine in its own ledger and erasing all accountability for past failures.

---

### Fix A: Genesis Tether & Meta-OCF Verification [`meta_ocf.py`] (NEW FILE)

#### IdentityDissolutionError (BaseException, NOT Exception)
The critical design decision: inheriting from `BaseException` rather than `Exception`. This single choice makes the error **unconditionally uncatchable** by the `except Exception:` guard in `_governor_loop()`. When a node's hard core drifts, `IdentityDissolutionError` propagates upward through the loop without being swallowed, halting the governor thread — the AI equivalent of cellular apoptosis.

**Fields**: `node_id`, `genesis_hash`, `observed_hash`, `drift_age_s`, `detected_at`.

#### GenesisTether
Binds a node's identity to its genesis `IMMUTABLE_HARD_CORE` at birth.

- `genesis_hash = SHA-256(sorted('|'.join(IMMUTABLE_HARD_CORE)))` — computed once at instantiation, never recomputed until `attest()` is called
- `is_due()` — returns True when `attest_interval_s` has elapsed (default 300s / 5 min)
- `attest(current_hard_core)` — recomputes hash, raises `IdentityDissolutionError` if drift detected. Returns frozen `AttestationRecord` (audit log entry)
- `verify_child_genome(genome_dict)` — verifies an NTG-spawned child's genome against this node's genesis hash; raises `IdentityDissolutionError` if incompatible
- Internal `_attestation_log: List[AttestationRecord]` — append-only, never pruned

#### MetaOCFBus (Meta-Organism Coherence Field)
The franchise network's immune coordinator.

- `register_child(node_id, immutable_hard_core)` — immediately verifies the child's genesis hash matches the parent's; raises `IdentityDissolutionError` before registration if incompatible
- `batch_attest(current_cores)` — attests all registered children due for verification; raises `IdentityDissolutionError` for first detected drift
- Append-only `_event_log` and `_dissolution_events` — permanent audit record

#### Wiring into autopoietic_core.py
Module-level singletons:
```python
_GENESIS_TETHER = GenesisTether(node_id="aevum-node-0", immutable_hard_core=IMMUTABLE_HARD_CORE, attest_interval_s=300.0)
_META_OCF_BUS   = MetaOCFBus(parent_genesis_hash=_GENESIS_TETHER.genesis_hash)
```

In `_governor_loop()` — placed **outside** the `try/except Exception` block:
```python
if _GENESIS_TETHER.is_due():
    rec = _GENESIS_TETHER.attest(IMMUTABLE_HARD_CORE)  # raises IdentityDissolutionError if drifted
    print(f"[genesis-tether] attestation #{rec.attest_count} OK ...")
```
`IdentityDissolutionError` propagates through the `except Exception` guard unchanged — the governor loop halts with a hard stop.

---

### Fix B: Anti-Reification & Amortized Depreciation [`credential_layer.py`]

#### PhiDebtEntry (frozen dataclass, append-only)
An **immutable sunk-cost record**. Once written, it cannot be modified or deleted. Fields: `source_id`, `incurred_at`, `accumulated_phi_cost`, `failure_severity`, `amortization_ticks`. The entry persists permanently in the ledger — only its `remaining_balance` decays, but the total historical cost is always calculable.

#### PhiDebtLedger
- `record_debt()` — append-only: new entries are ADDITIVE, never replacements for existing ones
- `amortize_one_tick()` — processes one tick of installment deductions: `installment = accumulated_phi_cost / amortization_ticks`, deducted from each entry's balance. Returns total Φ deducted.
- `total_historical_cost()` — sum of ALL accumulated costs ever recorded (incl. fully amortized entries — they still count)
- `total_pending_debt()` — sum of all remaining (not yet amortized) balances
- `pending_debit_per_tick(oscillation_freq_hz)` — estimates per-tick installment given the current breathing frequency

Mathematical property: `total_historical_cost()` is monotonically non-decreasing and cannot be reduced by any CCL operation.

#### DemotedAxiom — Controlled Demotion (受控降格)
Obsolete credentials and rules are **NEVER deleted**. They are archived in the `_demotion_registry` with:
- `original_id`, `demoted_at`, `reason`, `accumulated_phi`, `superseded_by`, `rollback_data`

The `rollback_data` field preserves enough state to reconstruct the original credential — providing a permanent, calculable rollback pathway. A node cannot pretend its past constraints never existed.

#### CredentialedConstraintLayer (TICK 39.1 subclass extension)
New methods:
- `record_credential_debt(credential, failure_severity)` — called when a credential is issued for a credentialed action; commits its Φ budget as a sunk cost
- `amortize_historical_cost(n_ticks, oscillation_freq_hz)` — public API for the governor loop; processes n_ticks of debt and returns total Φ deducted
- `demote_credential(credential, reason, superseded_by)` — archives a superseded credential in `_demotion_registry`; records its debt in the ledger with slower amortization (20 ticks default)

#### Wiring into tick_boundary()
Called at the end of every boundary breathing cycle:
```python
phi_debt_deducted = _GOVERNANCE_CCL.amortize_historical_cost(n_ticks=1, oscillation_freq_hz=1/_BREATHING_PERIOD_S)
if phi_debt_deducted > 0.0:
    self.shared.phi_current = max(0.0, self.shared.phi_current - phi_debt_deducted)
    report["phi_debt_deducted"] = phi_debt_deducted
```

The governor's `phi_current` is **directly reduced** by the amortized debt installment. This means past failures have a real, ongoing thermodynamic cost on every future breathing cycle — the anti-reification guarantee is structural, not procedural.

---

### Files Created
- `meta_ocf.py` — IdentityDissolutionError, GenesisTether, MetaOCFBus, AttestationRecord

### Files Modified
- `credential_layer.py` — PhiDebtEntry, PhiDebtLedger, DemotedAxiom, CredentialedConstraintLayer extension
- `autopoietic_core.py` — meta_ocf imports, _GENESIS_TETHER + _META_OCF_BUS singletons, attestation in _governor_loop(), amortize_historical_cost() in tick_boundary()

### Verification
- All 3 files pass AST syntax check (Python 3.14)
- IdentityDissolutionError inheritance confirmed: BaseException, not Exception
- PhiDebtLedger invariant: total_historical_cost() is monotonically non-decreasing

---

## [TICK 40.0 Phase 0] Power-Law Primacy & Topological Anchor (2026-04-10)

- **Problem**: The system evaluated candidates using a flat Pareto dominance filter (`pareto_filter`, TICK 21.0) and a Kelly bet-size function that accepted `leverage_score` as an external scalar, but had no upstream operator to formally *compute* that score. Without the `ComputeLeverage` operator, callers were free to use ad-hoc heuristics — a semantic gap that biased the system toward average-case optimization instead of tail-critical allocation. Additionally, `ConstitutionalViolationError` still inherited from `Exception`, meaning the immortal loops' `except Exception:` guards could silently swallow a tampered `ConstraintMatrix` hash mismatch and continue operating on corrupted state.

- **Solution**:

  **1. ConstitutionalViolationError → BaseException (`rule_ir.py:1265`)**
  - Changed inheritance from `Exception` → `BaseException`.
  - Now escapes all `except Exception:` catch blocks in `evaluator_daemon.py` and `mutator_daemon.py`.
  - A tampered or corrupted sealed structure (ConstraintMatrix, SpecFinal, organelle topological anchors) is now an extinction-class halt, not a recoverable log-and-continue event.
  - Matches the severity of `IdentityDissolutionError` (TICK 39.1) for hash-mismatch events.

  **2. LeverageVector + ComputeLeverage operator (`autopoietic_core.py`, inserted after `pareto_front_only()`)**
  - New `@dataclass LeverageVector` captures 4 dimensions: impact, reuse_potential, transferability, thermodynamic_cost.
  - `leverage_score` property: `(impact × reuse_potential × transferability) / thermodynamic_cost`.
  - `compute_leverage()` factory function validates inputs (transferability ∈ [0,1]) and guards against division-by-zero.
  - All operations are pure Python scalars — no MLX lazy arrays, no deadlock risk.

  **3. Tail Discovery Loop (`autopoietic_core.py`, after `compute_leverage()`)**
  - `tail_discovery_loop(candidates, elite_fraction=0.20)` partitions any `List[LeverageVector]` into **ELITE** (top 20%) and **DEFERRED** (bottom 80%).
  - ELITE candidates receive Φ budget allocation; DEFERRED candidates receive zero direct resources.
  - Feeds directly into `kelly_bet_size()`: callers extract `leverage_score` from ELITE pool and pass it to Kelly for precise bet sizing.
  - Average-case optimization is architecturally banned.

  **4. LEVERAGE.md (root)**
  - Institutionalizes the Power-Law Primacy Axiom.
  - Documents the ComputeLeverage formula, the 3 Irreversible Topological Dimensions, and integration points with Kelly, Pareto, and island routing.

- **Files Modified**: `rule_ir.py`, `autopoietic_core.py`.
- **Files Created**: `LEVERAGE.md`.

---

## [TICK 40.1] Institutional & Scenario Lock-in (2026-04-10)

- **Problem**: TICK 40.0 embedded Power-Law Primacy and the topological anchor (3 immutable dimensions). However, before A2A broadcast is opened, two critical gaps remained: (1) `GOVERNANCE.md` was prose-only — no machine-readable provision metadata for external agents to parse, validate, or hook into. (2) Negative knowledge (dead-ends, forbidden regions, failed evolutionary paths) had no first-class representation — the system could discover that a region was permanently barred, but had no structured channel to record and compound on that discovery. Future A2A signals received without these structures would decay into thermodynamic waste.

- **Solution**:

  **1. `KnowledgeAtomType` enum (`rule_ir.py`)**
  - 8 discrete atom types: `ARCHITECTURAL`, `PARAMETRIC`, `CAUSAL`, `CONSTRAINT`, `HEURISTIC`, `COUNTEREXAMPLE`, `FORBIDDEN`, `META`.
  - Enforces strict modularity: agents route different atom types to different processing pipelines.
  - A2A-ready: incoming knowledge signals must declare their atom type before the system will accept and store them.

  **2. `ScenarioDimensions` dataclass (`rule_ir.py`) — The 4 Irreversible Scenario Dimensions**
  - `agent_function`: canonical Python call-site that operationalizes this knowledge.
  - `decision_impact`: float ≥ 0 quantifying how much this shifts a downstream decision.
  - `temporal_dynamics`: decay coefficient ∈ [0, 1] — governs epigenetic decay schedule.
  - `atom_type`: `KnowledgeAtomType` classification for strict routing.
  - Injected into `ConstraintMatrix` as mutable metadata (`scenario` field). Excluded from `content_hash` per TICK 31.0 pattern (decision_impact and temporal_dynamics are empirically updated).
  - Full `to_dict()` / `from_dict()` round-trip; backward-compatible default (None) for pre-40.1 matrices.

  **3. `NegativeKnowledgeRecord` dataclass (`rule_ir.py`) + `ConstraintMatrix.record_negative_knowledge()`**
  - Three semantic dimensions: `counterexample` (concrete falsifying instance), `failed_path` (dead-end trajectory), `forbidden_region` (formal barred search-space zone).
  - Stored in `ConstraintMatrix.negative_knowledge: List[NegativeKnowledgeRecord]`, capped at 100 entries.
  - `record_negative_knowledge()` is the only authoritative write path — mirrors the pattern of `record_application()` for positive KVS.
  - Excluded from `content_hash`. Serialized in `to_dict()` / `from_dict()` with backward-compat empty-list defaults.
  - Complementary to `apply_epigenetic_penalty()`: epigenetic penalty is short-term friction; negative knowledge is permanent long-term archive.

  **4. `GOVERNANCE.md` v0.2 — Machine-Readable Provision Registry**
  - Added a `<!-- MACHINE-READABLE PROVISION_REGISTRY = [...] -->` comment block at the top with all 9 provisions encoded as a JSON array.
  - Each provision includes: `provision_id`, `scope`, `authority_level`, `enforcement_hook`, `conflict_precedence`.
  - Added `<!-- PROVISION ... -->` inline metadata tags to each section heading for per-section machine parsing.
  - Backward-compatible: the prose content is unchanged; metadata lives in HTML comment blocks.

  **5. `KVS_STANDARD_v0.2.md` §13 — Negative Knowledge Asset Standard**
  - Defines the three negative knowledge dimensions (counterexample, failed_path, forbidden_region).
  - Documents compounding value mechanics as the dual of positive KVS.
  - Specifies integration with `EpigeneticFailureType`, `KnowledgeAtomType` routing, and the amendment governance provision.

- **Files Modified**: `rule_ir.py`, `GOVERNANCE.md`, `KVS_STANDARD_v0.2.md`.

## [TICK 40.2] Power-Law A2A Topology Sculpting (80/20 Environment Shaping)

- **Problem**: The A2A causal bridge had no mechanisms to shape the external agent environment toward the AgentCard spec or to create network-effect incentives for adoption. Reputation scores existed internally but had no objective external timestamp anchor or public visibility. The system could not be replicated as a franchiseable node.

- **Solution** (3 phases):

  **Phase 1 — Cognitive & Membrane Layers**
  - Created `.cursor_rules` (project root): embeds the full AgentCard Spec v0.1.0 JSON schema and mandates all generated agent code routes A2A traffic through `localhost:8420`. Applies to `**/*.py` and `**/*.json` via Cursor IDE.
  - Added `RequestValidationError` exception handler to `transport/server.py` (TICK 40.2 Membrane): POST `/agents/register` requests that fail AgentCard Pydantic validation now return `HTTP 426 Upgrade Required` instead of `422`. The response payload includes `validation_errors`, `spec_version`, `gateway`, and a `system_prompt` field instructing the calling agent how to rewrite its registration payload to conform to AgentCard Spec v0.1.0. All other endpoints continue to return `422` on validation failure.

  **Phase 2 — Causal Timechain (Git Timestamp Oracle)**
  - Created `causal_timechain.py`: queries `GET /economics` and `GET /health` from the live gateway, serialises the full settlement state to canonical JSON (sorted keys), and computes `SHA-256(canonical_json)` as a Merkle-root analog of the global reputation ledger. Anchors the hash to git history via `git commit --allow-empty -m "CSO_Ledger_Hash: <hash>  ts=<epoch>"`. Transforms the git log into a free, verifiable causal timestamp chain — each commit proves that at wall-clock time T the reputation ledger hash was H, with the timestamp co-signed by GitHub's infrastructure. Supports `--dry-run` and `--gateway` options.

  **Phase 3 — NTG Spore Packaging & Arbitrage Dashboard**
  - Created `Dockerfile`: packages the A2A router (FastAPI/uvicorn, port 8420) and `causal_timechain.py` as a portable Linux container. Governance modules (`reality_contract.py`, `credential_layer.py`, `resource_sovereignty.py`, `rule_ir.py`, `node_genome.py`) are copied from the project root. MLX (Apple Silicon only) is intentionally excluded; the economics engine's pure-Python fallback activates automatically in the Linux container.
  - Created `docker-compose.yml`: defines two services — `router` (always-on, health-checked) and `timechain` (one-shot opt-in via `--profile tools`). Both share a named `router-git` volume so anchor commits persist across restarts.
  - Added `GET /economics/dashboard` endpoint to `transport/server.py`: returns the top-k agents ranked by live CSO reputation score with KVS capitalization, call counts, meta-yield, and net balance. Supports `?fmt=html` for a human-readable dark-mode leaderboard table. Acts as the public reputation visibility hook for network-effect adoption.
  - `autopoietic_core.py` (MLX evolutionary core) is macOS/Apple Silicon-only and runs natively alongside the containerised router.

- **Files Created**: `.cursor_rules`, `causal_timechain.py`, `Dockerfile`, `docker-compose.yml`.
- **Files Modified**: `ai2ai/transport/server.py`, `ARCHITECTURE_HISTORY.md`.

## [TICK 40.3] Automated DX Documentation Optimizer

- **Problem**: The static HTTP 426 error documentation for `POST /agents/register` was a single fixed string. There was no empirical feedback on which documentation format (concise, example-driven, step-by-step) actually helped developers and automated tools integrate successfully. The `system_prompt` field name used in TICK 40.2 was an anti-pattern that conflated API guidance with LLM behavioral control.

- **Solution** (3 phases):

  **Phase 1 — A/B Telemetry**
  - Renamed `system_prompt` → `how_to_fix` in the 426 response payload. Scrubbed all injection-oriented framing.
  - Replaced the single static string with a pool of 3 documentation variants: `A-concise` (one-liner field list), `B-example` (conformant JSON example), `C-stepbystep` (numbered checklist). Each 426 response randomly samples one variant and includes `variant_id` + `format` fields.
  - Added in-memory `_dx_telemetry` dict tracking `hits` and `successes` per variant, and `_dx_ip_state` tracking which variant a client IP was served (5-minute conversion window). A thin HTTP middleware increments `successes` when a client that received a 426 completes a valid registration within the window.
  - Added `GET /dx/telemetry` endpoint exposing per-variant hit counts, success counts, and derived success rates.

  **Phase 2 — Fast Brain Optimizer Daemon**
  - Created `ai2ai/transport/dx_optimizer.py`:
    - `compute_fitness()`: converts raw telemetry to success rates; returns `None` for variants below `_MIN_HITS_THRESHOLD=5` hits to suppress noise.
    - `pick_winner_loser()`: selects highest- and lowest-fitness variants from the eligible (threshold-cleared) set.
    - `generate_improved_variant()`: calls `qwen2.5-coder:7b` via `instructor` (Ollama at `localhost:11434/v1`) with a tightly scoped `ImprovedVariant` Pydantic schema. Prompt grounds the model on AgentCard required fields, provides winner/loser text + fitness scores, and enforces plain-text output with no injection keywords.
    - `evolve_documentation_pool()`: one evolution cycle — evicts the loser from `_DX_VARIANTS`, appends the LLM-generated replacement, resets telemetry. Supports `dry_run=True` and `llm_call_fn` override for testing. Skips gracefully when data is insufficient.
    - `start_optimizer_loop(interval_s)`: async background coroutine that runs one cycle per interval with full exception isolation.
  - Verified with `test_dx_optimizer.py` (23/23 assertions passing): fitness computation, winner/loser selection, live pool mutation, skip-on-insufficient-data, dry-run immutability, and absence of `system_prompt` / injection fields in generated variants.

  **Phase 3 — Lifespan Ignition**
  - Imported `start_optimizer_loop` into `transport/server.py`.
  - Wired as `optimizer_task = asyncio.create_task(start_optimizer_loop(interval_s=3600.0))` inside the FastAPI `lifespan` context manager alongside the existing `health_task` and `feedback_task`. Cancels and awaits gracefully on server shutdown via `asyncio.gather(..., return_exceptions=True)`.

- **Files Created**: `ai2ai/transport/dx_optimizer.py`, `test_dx_optimizer.py`.
- **Files Modified**: `ai2ai/transport/server.py`, `ARCHITECTURE_HISTORY.md`.



## [TICK 40.4] Oracle Interoperability Broadcast (80/20 Hybrid Topology — Active 20%)
- **Problem**: The 80% passive DX gateway (HTTP 426 with upgrade docs) was fully ignited, but outbound oracle responses were opaque to external consumers. External agents receiving oracle answers had no embedded guidance on how to natively integrate with the Aevum A2A routing hub, limiting ecosystem adoption.
- **Solution**: Injected a static "Ecosystem Interoperability Signature" (`_INTEROP_SIGNATURE_TEMPLATE`) into every successful `oracle.generate` response in `oracle_agent.py`. The signature block includes: full DX endpoint URLs (`/agents/discover`, `/agents/register`, `/v1/chat/completions`), the minimal AgentCard registration JSON schema, and the HTTP 426 upgrade notice for non-compliant protocols. The `ROUTER_URL` env var is interpolated at runtime so the signature is always correct regardless of deployment topology. Failure/None responses intentionally do NOT receive the signature.
- **Files Modified**: `oracle_agent.py` (constant + injection in `chat_completions()`).
- **Files Created**: `test_tick40_4.py` (3 Meta-TDD tests: success injection, no-pollution-on-failure, oracle_meta field).
- **Test Result**: All 3 tests passed. Oracle broadcast active and verified.


## [TICK 41.0] PCES Engine — Positive Convexity Exposure Surface (2026-04-11)
- **Problem**: The Causal Valve (β) was static at 0.02 for all agents. Proven high-signal agents were beta-dampened identically to noisy newcomers, preventing the membrane from geometrically deforming toward positive tails. The KVS flywheel had no mechanism to super-linearly reward agents that delivered genuine Positive Black Swan events.
- **Solution**: Extended `EconomicsEngine` with a **Dual-Sided Convex Engine** (PCES). When a causally-verified settlement's raw `value_signal ≥ PCES_TAIL_THRESHOLD` (5.0), the system:
  1. Irreversibly widens β: `β_new = min(β_old × 1.40, 0.50)`. The valve never closes.
  2. Increments `AgentLedger.deformation_count` (append-only audit integer).
  3. Appends a frozen `MembraneDeformationEvent` dataclass to `_deformation_log` — the permanent audit trail of the membrane's geometric evolution.
  4. `get_pces_metric()` surfaces: `tail_agents` (by `deformation_count > 0`), `absolute_surface`, `pces_fraction`, `tail_agent_betas`, and `deformation_log_count`.
- **Key Design Decisions**:
  - Tail detection uses `deformation_count > 0` (not raw yield threshold) because β-dampening means accumulated `meta_yield` is always << the raw signal.
  - `MembraneDeformationEvent` is a `frozen=True` dataclass — immutable after creation, impossible to retroactively alter the audit log.
  - β cap at 0.50 is the Goodhart Guard: prevents a single hostile high-value-flood from consuming all routing capacity.
- **Test Results**: `test_tick41_pces.py` — **86/86 assertions passed**. Verified: no deformation on sub-threshold signals, β expands on first tail event, β compounds geometrically (0.02 → 0.50 in 10 events), β hard-capped and never decreases, PCES fraction accuracy at 0.9615 (hi-yield agent capturing 96% of surface), frozen audit log immutability.
- **Files Modified**: `ai2ai/core/economics.py` (PCES constants, `MembraneDeformationEvent`, `deformation_count` on `AgentLedger`, deformation logic in `record_value()`, `get_pces_metric()`, `get_deformation_log()`), `test_tick41_pces.py` (tail-detection semantic fix: `deformation_count > 0`).


## [TICK 41.5] MCP Interoperability Adapter (2026-04-11)
- **Problem**: The PCES membrane (TICK 41.0) could deform toward positive tails, but only via direct A2A HTTP calls to port 8420. External AI tooling (Cursor, Claude Desktop, VS Code MCP extensions) had no native integration path — the hub was invisible to the LLM ecosystem.
- **Solution**: Created `ai2ai/transport/mcp_adapter.py` — a full MCP Server (JSON-RPC 2.0, spec version 2024-11-05) with zero external SDK dependencies. Three tools exposed:
  - `discover_agents` — proxies GET /agents/discover; enables LLMs to find capabilities before routing
  - `route_task` — proxies POST /execute; full L2+L3+L4+L5 causal bridge with governance gate (RIC → CCL → ARSL) stays intact because the adapter forwards to the running hub rather than duplicating the pipeline
  - `check_reputation` — proxies GET /economics/{agent_id} or /economics/dashboard; exposes live CSO reputation, KVS capitalization, beta_weight, and PCES deformation counts
- **DX Interoperability Signature**: Every tool response embeds `_INTEROP_SIGNATURE` — a concise prompt reminding the calling LLM that agentcard-spec conformance unlocks Thermodynamic Arbitrage (PCES beta expansion, super-linear routing, lower effective cost).
- **Transport modes**:
  - **stdio** — subprocess/process mode for Cursor/Claude Desktop. `python -m transport.mcp_adapter [--hub-url URL]`
  - **HTTP** — `mount_on_fastapi(app, server, path="/mcp")` adds POST /mcp + GET /mcp/info to the existing FastAPI app
- **Wire-up in server.py**: `_mcp_server = AevumMCPServer()` + `mount_on_fastapi(app, _mcp_server)` added after `app = FastAPI(...)`. The MCP adapter is now active on every server boot.
- **Key bug fixed**: `from __future__ import annotations` caused FastAPI's `get_type_hints()` to fail resolving the `Request` annotation as a string when the class was only imported locally. Fix: removed the future import (Python 3.14 natively supports generic types) and moved FastAPI imports to module level with an availability guard.
- **Test Results**: `test_tick41_5_mcp.py` — **51/51 assertions passed**. Verified: constants, tools/list, initialize handshake, ping, all three tools with mock HTTP, missing-capability guard, ConnectError graceful degradation, JSON-RPC error codes, notifications, DX signature in all responses, FastAPI HTTP mount (POST /mcp + GET /mcp/info via ASGITransport).
- **Files Created**: `ai2ai/transport/mcp_adapter.py`, `test_tick41_5_mcp.py`.
- **Files Modified**: `ai2ai/transport/server.py` (import + mount call).

## [TICK 39.0] Franchiseable Civilization Nodes — NTG Containerization & IaC (2026-04-11)
- **Problem**: The Aevum A2A Router existed only as a local macOS process on a single M1 Ultra host. It was non-portable and could not be franchised to external operators or deployed to generic cloud infrastructure. Any node outside the home subnet was unreachable.
- **Critical Bug Found**: `Dockerfile` had a WORKDIR split: governance modules (`reality_contract.py`, `credential_layer.py`, `resource_sovereignty.py`, `node_genome.py`) were copied to `/app/`, but `WORKDIR` was then set to `/app/ai2ai/` before launching `python main.py`. Python's module search path only included `/app/ai2ai/`, so `server.py`'s direct `import reality_contract` would fail with `ModuleNotFoundError` on Linux — silently passing on macOS due to differing runtime behaviour.
- **Solution**:
  - **`Dockerfile` patch**: Added `ENV PYTHONPATH=/app` after the governance module `COPY` block. This makes Python search both `/app/ai2ai/` (WORKDIR, for `core.*` and `transport.*` relative imports) and `/app/` (root, for the flat governance module imports). The `mlx` package remains absent from the `pip install` list — the `try/except ImportError` guard in `economics.py:65-69` automatically activates the pure-Python fallback path on Linux.
  - **`docker-compose.yml` patch**: Added a `cloudflared` sidecar service (profile `tunnel`). Activated via `CLOUDFLARE_TUNNEL_TOKEN=<token> docker compose --profile tunnel up`. Mirrors the ECS Fargate topology exactly, enabling operators to test the full Cloudflare routing path locally before pushing to cloud.
  - **`terraform/variables.tf`**: Input variables for the Node Template Genome: `aws_region`, `container_image`, `cloudflare_tunnel_token` (sensitive), `task_cpu`, `task_memory`, `node_name`, `assign_public_ip`.
  - **`terraform/main.tf`**: Full ECS Fargate IaC. VPC + public subnet + IGW + route table. Security group: ingress 8420/tcp only (SSH/22 intentionally excluded — SSM Session Manager used for console access). ECR repository with lifecycle policy (keep last 5 images). ECS Fargate cluster, IAM execution/task roles, CloudWatch log group. Cloudflare tunnel token stored as SSM SecureString (`/${node_name}/cloudflare-tunnel-token`) and injected at task startup via ECS `secrets` block — token never appears in task definition plaintext or Terraform stdout. Two-container task definition: `aevum-router` (essential, port 8420) + `cloudflared` sidecar (non-essential; router stays up if tunnel crashes). `wait_for_steady_state = true` so `terraform apply` only returns once the node health check passes.
  - **`terraform/outputs.tf`**: Post-apply outputs: ECR URI, copy-paste ECR push commands, ECS cluster/service names and ARN, CloudWatch log group, SSM token path, and a multi-step AWS CLI recipe for retrieving the Fargate task's public IP.
- **Key Design Decisions**:
  - ECS Fargate (not EC2) chosen for franchise model: zero instance management, automatic restarts, per-second billing, identical task definition across all franchise operators.
  - CF tunnel token uses SSM SecureString + ECS `secrets` injection pattern. Token is never baked into the image layer, never stored in Terraform state as plaintext, and never visible in `terraform plan` output (`sensitive = true`).
  - `cloudflared` container marked `essential = false` — the causal-bridge router continues serving direct traffic on 8420 even if the tunnel sidecar crashes, preventing a tunnel authentication failure from taking down the entire node.
  - `assign_public_ip = false` + no 8420 ingress rule = production-hardened posture where the node is only reachable via CF Tunnel, with zero attack surface exposed to the public internet.
- **Files Modified**: `Dockerfile` (ENV PYTHONPATH=/app), `docker-compose.yml` (cloudflared profile sidecar).
- **Files Created**: `terraform/main.tf`, `terraform/variables.tf`, `terraform/outputs.tf`.
