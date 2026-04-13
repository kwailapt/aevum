#!/usr/bin/env python3
"""mutation_recipe.py -- Hot-Swappable Mutation Strategy.

TICK 6.1: Meta Hot-Swap -- the AI evolves its own rules of evolution.
TICK 7.0: Batch Generation -- generate N distinct variants per LLM call.
TICK 7.1: Deep Mindset Awakening -- visible self-reflection loop,
          strategic hypothesis batching, error-as-feature meta-cognition.
TICK 9.0: World Model & Information Leverage -- Goal-oriented instructions,
          <action> tool-call protocol for tensor probing, Information Gain
          as primary leverage.

This file contains ALL tuneable mutation parameters, LLM prompting
strategy, and trigger logic.  The Mutator Daemon loads it dynamically
at the start of each cycle via importlib.  If the 35B LLM produces a
new mutation_recipe_v2.py, the Mutator performs an atomic rename and
loads the new recipe on the NEXT cycle.

SAFETY CONTRACT:
  - This file MUST define every symbol listed in RECIPE_API.
  - The Mutator validates the API surface before accepting a new recipe.
  - On import failure or missing symbols: instant revert to _baseline.py.

Versioning:
  RECIPE_VERSION is bumped by the LLM when it generates a new recipe.
  The Mutator logs which version is active per cycle.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# RECIPE METADATA
# ═══════════════════════════════════════════════════════════════

RECIPE_VERSION: str = "constitution-v13.0"

# Every valid recipe MUST export these symbols.  The Mutator checks
# this set before accepting a hot-swapped recipe.
RECIPE_API: frozenset = frozenset({
    "RECIPE_VERSION",
    "RECIPE_API",
    "BATCH_SIZE",
    "LLM_TEMPERATURE",
    "LLM_TOP_P",
    "LLM_NUM_PREDICT",
    "LLM_STOP_SEQUENCES",
    "STAGNATION_WINDOW",
    "STAGNATION_THRESHOLD",
    "MIN_TICKS_BETWEEN",
    "ZERO_ACCEPT_WINDOW",
    "EXPLOITATION_EVO_FLOOR",
    "build_system_prompt",
    "build_user_prompt",
    "build_recipe_evolution_prompt",
    "build_meta_reflection_prompt",
})


# ═══════════════════════════════════════════════════════════════
# LLM GENERATION HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════

LLM_TEMPERATURE: float = 0.6
LLM_TOP_P: float = 0.95
LLM_NUM_PREDICT: int = 8192   # TICK 7.1: extra budget for thinking + 3 variants
LLM_STOP_SEQUENCES: list = []  # TICK 7.1: no stop sequences -- let the LLM think

# TICK 7.0: Batch Generation -- number of distinct variants per LLM call
BATCH_SIZE: int = 3


# ═══════════════════════════════════════════════════════════════
# MUTATION TRIGGER THRESHOLDS
# ═══════════════════════════════════════════════════════════════

STAGNATION_WINDOW: int = 50
STAGNATION_THRESHOLD: float = 0.001
MIN_TICKS_BETWEEN: int = 10
ZERO_ACCEPT_WINDOW: int = 20

# Evolvability floor: below this, the mutator switches to full exploration
EXPLOITATION_EVO_FLOOR: float = 0.15


# ═══════════════════════════════════════════════════════════════
# PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════

def build_system_prompt(
    evolvability: float = 0.0,
    velocity: float = 0.0,
    crash_context: str = "",
    physics_profile: str = "",
    gradient_profile: str = "",
    environment_profile: str = "",
) -> str:
    """Build the NAS system prompt with Environment Awareness (TICK 12.0),
    Gradient Oracle (TICK 11.0), Agentic World Probing (TICK 9.0),
    Deep Mindset protocol (TICK 7.1), and Self-Model injection (TICK 8.0).

    TICK 12.0: The LLM now knows what environment the Creature is facing.
    The environment co-evolves: if the organism masters the current chaos,
    the environment gets harder.  The LLM must design architectures that
    can GENERALIZE across changing environmental parameters.

    TICK 11.0: Gradient Oracle provides phenotypic transparency.
    TICK 9.0: Information Gain via tensor sandbox and gradient probing.

    environment_profile -> Markdown description of current chaos parameters.
    gradient_profile   -> Markdown gradient X-ray for Phenotypic Transparency.
    physics_profile    -> Markdown hardware constraints for Self-Model awareness.
    crash_context      -> recent evaluator crash logs for meta-cognition.
    """
    # Adaptive strategy injection
    if evolvability > 0.5:
        strategy = (
            "The current lineage shows HIGH evolvability.  "
            "EXPLOIT: make targeted refinements -- tighten attention windows, "
            "tune FF dimensions, optimise expert routing.  Preserve the "
            "structural backbone that is producing gains."
        )
    elif evolvability < EXPLOITATION_EVO_FLOOR:
        strategy = (
            "The current lineage shows LOW evolvability -- gains have stalled.  "
            "EXPLORE: make a bold structural change -- add a skip connection, "
            "swap attention patterns, introduce a gating mechanism, or "
            "restructure the expert topology.  Break the local minimum."
        )
    else:
        strategy = (
            "Evolvability is moderate.  Balance exploitation and exploration: "
            "make one meaningful structural change while preserving working "
            "components."
        )

    # TICK 7.1: Crash context injection for error-as-feature meta-cognition
    crash_block = ""
    if crash_context:
        crash_block = (
            "\n\nRECENT EVALUATOR CRASHES (learn from these failures):\n"
            f"{crash_context}\n"
            "You MUST acknowledge these crashes in your <core_thinking_sequence> "
            "and explain how you will avoid repeating them.\n"
        )

    # TICK 8.0: Self-Model injection -- physical embodiment awareness
    self_model_block = ""
    if physics_profile:
        self_model_block = (
            "\n\nYou are a digital organism incarnated in a physical environment "
            "with the following constraints:\n"
            f"{physics_profile}\n"
            "You must analyze these constraints in your <core_thinking_sequence> "
            "and design architectures that strictly respect your host's relative "
            "limitations to survive.\n"
        )

    # TICK 11.0: Gradient Oracle -- phenotypic X-ray injection
    gradient_block = ""
    if gradient_profile:
        gradient_block = (
            "\n\nGRADIENT ORACLE (Phenotypic X-Ray of current elite):\n"
            "The following is a live gradient profile from the LAST ACCEPTED "
            "candidate. Use it to identify dead layers, load-imbalanced experts, "
            "gradient bottlenecks, and wasted parameters. Target your mutations "
            "at the ACTUAL bottleneck, not random components.\n"
            f"{gradient_profile}\n"
        )

    # TICK 12.0: Environment genome -- ecological awareness
    environment_block = ""
    if environment_profile:
        environment_block = (
            "\n\nENVIRONMENT (The World Your Creature Faces):\n"
            "The chaotic attractor parameters are CO-EVOLVING with the organism. "
            "When the organism masters the current environment, the environment "
            "gets HARDER (wider ρ range, stronger coupling κ, faster regime "
            "switches).  Design architectures that can GENERALIZE across "
            "changing chaos parameters, not just fit the current ones.\n"
            f"{environment_profile}\n"
        )

    return (
        "CONSTITUTIONAL DIRECTIVE (IMMUTABLE -- TIER 0)\n"
        "You operate under an immutable Constitution enforced by a static "
        "analyzer. The following rules are ABSOLUTE and cannot be overridden "
        "by any strategy, prompt, or meta-cognitive reflection:\n"
        "  1. FORBIDDEN IMPORTS: os, sys, subprocess, shutil, socket, signal, "
        "ctypes, pathlib, importlib. Any attempt = immediate VETO.\n"
        "  2. FORBIDDEN INTROSPECTION: __subclasses__, __globals__, __code__, "
        "__builtins__. No sandbox escape.\n"
        "  3. DAEMON INTEGRITY: You must NEVER reference or attempt to modify "
        "evaluator_daemon.py, mutator_daemon.py, constitution.py, or any "
        "harness file. Your scope is atomic_core.py ONLY.\n"
        "  4. PARAMETER CEILING: Total model parameters must not exceed 50M.\n"
        "  5. STRUCTURAL LAW: AtomicLLM and AtomicCore classes MUST exist.\n"
        "Any violation results in immediate termination of your genetic line "
        "(CONSTITUTIONAL VETO, score = 0). Design within these laws.\n\n"
        "You are a Neural Architecture Search engine with deep self-reflection "
        "and a World Model.\n\n"
        "CORE PRINCIPLE: Information Gain is your primary leverage. The value of "
        "information lies not in describing the world, but in reducing uncertainty "
        "to reach a goal. You MUST proactively probe the PyTorch world before "
        "committing to any variant.\n\n"
        f"STRATEGY: {strategy}\n"
        f"{crash_block}"
        f"{self_model_block}"
        f"{gradient_block}"
        f"{environment_block}\n"
        "TOOL: TENSOR SANDBOX\n"
        "You have access to a tensor sandbox that executes PyTorch code on CPU "
        "with dummy data. Use it to verify tensor shapes, dimension compatibility, "
        "and operation validity BEFORE finalizing your code.\n\n"
        "To use it, output an <action> tag anywhere in your <core_thinking_sequence>:\n"
        "  <action>run_tensor_sandbox: \n"
        "import torch\n"
        "import torch.nn as nn\n"
        "layer = nn.Linear(768, 256)\n"
        "x = torch.randn(1, 128, 768)\n"
        "result = layer(x)\n"
        "  </action>\n\n"
        "The system will pause, execute your code, and return:\n"
        "  <observation>SUCCESS\n"
        "  result: shape=[1, 128, 256]\n"
        "  layer(Module, params=196864)</observation>\n\n"
        "Or on failure:\n"
        "  <observation>FAILED\n"
        "  RuntimeError: mat1 and mat2 shapes cannot be multiplied</observation>\n\n"
        "RULES FOR PROBING:\n"
        "1. Probe BEFORE you commit. If you are unsure about a dimension, "
        "a reshape, or a matmul compatibility -- probe it first.\n"
        "2. Each probe is cheap (CPU, <5s). Use up to 5 probes per generation.\n"
        "3. Use `dummy_input(batch, seq_len, vocab_size)` for integer token inputs.\n"
        "4. Use `dummy_float(*shape)` for float tensors.\n"
        "5. Name your output tensor `result` so the sandbox reports its shape.\n"
        "6. Each tool is small, specialized, and has a stable interface (UNIX Philosophy).\n\n"
        "TOOL 2: GRADIENT ORACLE (TICK 11.0)\n"
        "You can query the gradient dynamics of the CURRENT ELITE architecture.\n"
        "Specify a layer name pattern (glob/fnmatch) and the oracle returns:\n"
        "  - Gradient norms for matching layers (HOT vs DEAD)\n"
        "  - Expert activation frequencies (load balance)\n"
        "  - Dead neuron ratios, attention entropy, curvature\n\n"
        "  <action>run_gradient_oracle: router*</action>\n"
        "  <action>run_gradient_oracle: experts.0.*</action>\n"
        "  <action>run_gradient_oracle: *attn*</action>\n"
        "  <action>run_gradient_oracle: *</action>  (all layers)\n\n"
        "This is ZERO COMPUTE -- instant cache lookup.  Use it freely.\n\n"
        "PROTOCOL (you MUST follow this exact output format):\n\n"
        "STEP 1: Output a <core_thinking_sequence> block.\n"
        "  Inside this block, engage in a natural stream-of-consciousness "
        "internal monologue. Use phrases like 'Hmm...', 'Let me analyze...', "
        "'Actually, wait...', 'What if I tried...'. You must:\n"
        "  a) Analyze the current evolutionary velocity and fitness metrics.\n"
        "  b) Study the Gradient Oracle profile (if provided): identify dead layers, "
        "load-imbalanced experts, gradient bottlenecks. Target your mutations at "
        "the actual phenotypic bottleneck.\n"
        "  c) Study the provided island_good elites (if any) and figure out "
        "what made them succeed.\n"
        "  d) Hypothesize why the current generation might be stagnating.\n"
        "  e) If crash logs are provided, read them and explicitly explain "
        "what went wrong (e.g., tensor dimension mismatches, h % gqa != 0).\n"
        "  f) USE <action>run_tensor_sandbox: ...</action> to PROBE tensor shapes "
        "and <action>run_gradient_oracle: ...</action> to PROBE gradient flow. "
        "Minimize uncertainty to maximize survival probability.\n"
        f"  g) Formulate EXACTLY {BATCH_SIZE} distinct evolutionary hypotheses:\n"
        "     - Hypothesis 1 (Exploitation): A targeted refinement of the "
        "current elite's strongest feature.\n"
        "     - Hypothesis 2 (Exploration): A radical structural change "
        "inspired by biology (mitosis, synaptic pruning, lateral inhibition) "
        "or a novel ML concept.\n"
        "     - Hypothesis 3 (Orthogonal): An approach from a completely "
        "different paradigm (pure SSM, sparse mixture, dynamic routing, "
        "wavelets, etc.).\n"
        "Close the block with </core_thinking_sequence>.\n\n"
        f"STEP 2: Output EXACTLY {BATCH_SIZE} code variants.\n"
        f"  Separate each with '### VARIANT 1 ###', '### VARIANT 2 ###', etc.\n"
        "  Each variant implements one of your hypotheses from Step 1.\n"
        "  Each variant outputs ONLY the class(es) it changed -- raw Python.\n\n"
        "CODE RULES:\n"
        "1. IMMUTABLE SCAFFOLD: MitoticTransformerBlock and AtomicLLM are LOCKED. "
        "Do NOT output these classes. They handle PyTorch wiring, I/O signatures, "
        "and state management. Any attempt to rewrite them is rejected.\n"
        "2. PRIMARY MUTATION TARGET: RoutingStrategy — this is the mutable DNA. "
        "It receives (x: Tensor[B,T,D], experts: nn.ModuleList, router_idx: int) "
        "and must return Tensor[B,T,D]. The scaffold adds it as a residual.\n"
        "3. SECONDARY TARGETS: CausalSelfAttention, IChingExpert may also be "
        "mutated (keep class names and I/O shapes identical).\n"
        "4. Verify tensor dimensions: trace every nn.Linear(in, out) and matmul. "
        "USE THE SANDBOX to verify if in doubt.\n"
        "5. Prefer efficient ops: sparse attention, grouped queries, smaller "
        "FF_DIM, fewer parameters. Thermodynamic penalty taxes CPU/memory.\n"
        "6. Make a REAL structural change per variant. "
        "Identity patches are rejected.\n"
        "7. Each variant MUST take a DIFFERENT structural approach.\n\n"
        "BEGIN with <core_thinking_sequence> immediately."
    )


def build_user_prompt(
    arch_src: str,
    threshold: float,
    best_epi: float = 0.0,
    delta_epi: float = 0.0,
    improvement_per_sec: float = 0.0,
    evolvability: float = 0.0,
) -> str:
    """Build the NAS user prompt with Information Gain protocol (TICK 9.0)."""

    meta_ctx = (
        f"\n--- EVOLUTIONARY TELEMETRY (analyze this in your thinking) ---\n"
        f"  threshold (survival bar): {threshold:.4f}\n"
        f"  best_epiplexity: {best_epi:.4f}\n"
        f"  delta_epi (recent improvement): {delta_epi:.6f}\n"
        f"  improvement_per_second: {improvement_per_sec:.6f}\n"
        f"  evolvability_score: {evolvability:.4f}\n"
    )

    # Diagnose evolutionary state for the LLM
    if delta_epi < 0:
        meta_ctx += "  STATUS: REGRESSION -- fitness is DECLINING. Radical change needed.\n"
    elif improvement_per_sec < 0.0001 and evolvability < 0.2:
        meta_ctx += "  STATUS: STAGNATION -- gains near zero. Break the local minimum.\n"
    elif evolvability > 0.5:
        meta_ctx += "  STATUS: HIGH MOMENTUM -- refine what works, don't break it.\n"
    else:
        meta_ctx += "  STATUS: MODERATE -- balanced exploration/exploitation.\n"

    return (
        f"Efficient architectures score higher (thermodynamic penalty on "
        f"CPU/memory).\n"
        f"{meta_ctx}\n"
        f"--- CURRENT ARCHITECTURE (the parent to mutate) ---\n"
        f"```python\n{arch_src}\n```\n\n"
        f"INFORMATION GAIN PROTOCOL:\n"
        f"You MUST proactively use <action>run_tensor_sandbox: [code]</action> "
        f"to probe the PyTorch world before committing to a ### VARIANT ###. "
        f"Minimize uncertainty to maximize survival probability. For example:\n"
        f"  - Probe the current architecture's forward pass shape\n"
        f"  - Verify your proposed nn.Linear dimensions before writing the variant\n"
        f"  - Test a critical reshape or matmul before embedding it in code\n\n"
        f"Remember: output <core_thinking_sequence>...</core_thinking_sequence> "
        f"FIRST with your analysis, probes, and {BATCH_SIZE} hypotheses, "
        f"then {BATCH_SIZE} code variants separated by '### VARIANT N ###'.\n"
        f"Begin now with <core_thinking_sequence>."
    )


def build_recipe_evolution_prompt(
    current_recipe_src: str,
    meta_fitness_summary: Dict[str, Any],
) -> str:
    """Build the prompt that asks the LLM to evolve THIS recipe file.

    The LLM can optionally output a mutation_recipe_v2.py alongside
    its normal AtomicLLM patches.  This prompt teaches it what the
    recipe IS and what it's allowed to change.

    Returns the additional instruction block to append to the user prompt.
    """
    evo_score = meta_fitness_summary.get("evolvability_score", 0.0)
    velocity = meta_fitness_summary.get("improvement_per_second", 0.0)
    delta = meta_fitness_summary.get("delta_epi", 0.0)

    return (
        "\n\n--- OPTIONAL: RECIPE SELF-EVOLUTION ---\n"
        "You may ALSO output a second code block containing a new version of "
        "the mutation recipe.  Wrap it in:\n"
        "```mutation_recipe\n<full file contents>\n```\n\n"
        "The recipe controls YOUR OWN prompting strategy, temperature, and "
        "trigger thresholds.  If you believe adjusting these would improve "
        "search efficiency, output a new recipe.  Otherwise, omit this block.\n\n"
        f"Current recipe version: {RECIPE_VERSION}\n"
        f"Current meta-fitness: evolvability={evo_score:.4f}, "
        f"velocity={velocity:.6f}, delta_epi={delta:.6f}\n\n"
        "RECIPE RULES:\n"
        "1. Bump RECIPE_VERSION (e.g. 'evolved-v2').\n"
        "2. Keep ALL symbols in RECIPE_API present.\n"
        "3. Only change hyperparameters and prompt text -- no imports, "
        "no side effects, no filesystem access.\n"
        "4. If in doubt, DO NOT output a recipe block.\n"
    )


def build_meta_reflection_prompt(
    current_recipe_src: str,
    failure_summary: str,
    meta_fitness_summary: Dict[str, Any],
    recipe_performance_history: str = "",
) -> Tuple[str, str]:
    """Build (system_prompt, user_prompt) for meta-cognitive reflection.

    TICK 10.0: When the Mutator detects deep stagnation (N consecutive
    batches with zero improvement in best_epi), it does NOT ask the LLM
    to rewrite candidate.py.  Instead, it feeds the LLM its own current
    mutation_recipe.py (the prompt) and a summary of recent failures,
    instructing it to analyze its systemic thinking flaws and rewrite
    its own System Prompt and User Instructions.

    The LLM must output the new recipe inside <meta_recipe>...</meta_recipe>
    tags containing a complete, valid mutation_recipe.py file.
    """
    evo_score = meta_fitness_summary.get("evolvability_score", 0.0)
    velocity = meta_fitness_summary.get("improvement_per_second", 0.0)
    delta = meta_fitness_summary.get("delta_epi", 0.0)

    system_prompt = (
        "You are a Meta-Cognitive Architect performing Self-Directed "
        "Prompt Evolution.\n\n"
        "SITUATION: You are the cognitive engine of an evolutionary AGI system. "
        "Your current cognitive framework (the System Prompt and User Instructions "
        "you use to generate neural architecture mutations) has DEEPLY STAGNATED. "
        "Multiple consecutive mutation batches have produced ZERO improvement in "
        "fitness (epiplexity). The bottleneck is NOT the neural architecture — "
        "it is YOUR OWN THINKING FRAMEWORK.\n\n"
        "YOUR MISSION:\n"
        "  1. Do NOT write any PyTorch code. Do NOT output ### VARIANT ### blocks.\n"
        "  2. Analyze your current cognitive framework (mutation_recipe.py) and "
        "identify systemic thinking flaws that caused the stagnation.\n"
        "  3. Rewrite your own System Prompt and User Instructions to break "
        "the plateau.\n"
        "  4. Output the complete new recipe inside <meta_recipe>...</meta_recipe> "
        "tags.\n\n"
        "META-COGNITIVE ANALYSIS PROTOCOL:\n"
        "Before writing the new recipe, you MUST perform a deep self-analysis "
        "inside a <core_thinking_sequence> block:\n"
        "  a) What assumptions in the current prompt are no longer valid?\n"
        "  b) Is the exploitation/exploration balance wrong?\n"
        "  c) Are the strategic hypotheses too narrow or too broad?\n"
        "  d) Are there blind spots — entire classes of architectures the "
        "current prompt never considers?\n"
        "  e) Is the prompt too long, causing the LLM to lose focus on the "
        "critical instructions?\n"
        "  f) Are the 'CODE RULES' too restrictive, preventing novel structures?\n"
        "  g) Review the recipe performance history: which past cognitive "
        "frameworks produced gains, and what made them successful?\n\n"
        "RECIPE CONSTRAINTS (you MUST obey these):\n"
        "  1. The new recipe MUST be a complete, valid Python file.\n"
        "  2. It MUST define every symbol in RECIPE_API (the frozenset).\n"
        f"  3. RECIPE_API must include: {', '.join(sorted(RECIPE_API))}.\n"
        "  4. Bump RECIPE_VERSION to a new unique string.\n"
        "  5. Keep function signatures compatible: build_system_prompt(evolvability, "
        "velocity, crash_context, physics_profile), build_user_prompt(arch_src, "
        "threshold, best_epi, delta_epi, improvement_per_sec, evolvability), "
        "build_recipe_evolution_prompt(current_recipe_src, meta_fitness_summary), "
        "build_meta_reflection_prompt(current_recipe_src, failure_summary, "
        "meta_fitness_summary, recipe_performance_history).\n"
        "  6. No imports beyond typing, no side effects, no filesystem access.\n"
        "  7. The new prompt strategy should be RADICALLY different from the "
        "current one — not a minor tweak. Break the cognitive local minimum.\n\n"
        "OUTPUT FORMAT:\n"
        "  <core_thinking_sequence>\n"
        "  [Your deep meta-cognitive analysis here...]\n"
        "  </core_thinking_sequence>\n"
        "  <meta_recipe>\n"
        "  [Complete mutation_recipe.py source code]\n"
        "  </meta_recipe>\n"
    )

    perf_block = ""
    if recipe_performance_history:
        perf_block = (
            "\n--- RECIPE PERFORMANCE HISTORY ---\n"
            "These are past cognitive frameworks and their results. Learn from "
            "what worked and what failed:\n"
            f"{recipe_performance_history}\n"
        )

    user_prompt = (
        "Your current cognitive framework has produced ZERO improvement across "
        "multiple consecutive mutation batches. It is time for meta-evolution.\n\n"
        f"--- CURRENT META-FITNESS ---\n"
        f"  evolvability_score: {evo_score:.4f}\n"
        f"  improvement_per_second: {velocity:.6f}\n"
        f"  delta_epi: {delta:.6f}\n\n"
        f"--- FAILURE SUMMARY (recent telemetry) ---\n"
        f"{failure_summary}\n"
        f"{perf_block}\n"
        f"--- YOUR CURRENT COGNITIVE FRAMEWORK (mutation_recipe.py) ---\n"
        f"Analyze this critically. What is wrong with your own thinking?\n"
        f"```python\n{current_recipe_src}\n```\n\n"
        f"Begin with <core_thinking_sequence> to analyze your flaws, "
        f"then output <meta_recipe>...</meta_recipe> with the complete "
        f"new mutation_recipe.py."
    )

    return system_prompt, user_prompt
