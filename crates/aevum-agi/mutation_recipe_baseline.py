#!/usr/bin/env python3
"""mutation_recipe.py -- Hot-Swappable Mutation Strategy.

TICK 6.1: Meta Hot-Swap -- the AI evolves its own rules of evolution.
TICK 7.0: Batch Generation -- generate N distinct variants per LLM call.

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

from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════
# RECIPE METADATA
# ═══════════════════════════════════════════════════════════════

RECIPE_VERSION: str = "baseline-v1"

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
})


# ═══════════════════════════════════════════════════════════════
# LLM GENERATION HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════

LLM_TEMPERATURE: float = 0.6
LLM_TOP_P: float = 0.95
LLM_NUM_PREDICT: int = 6144   # TICK 7.0: 3x for batch generation
LLM_STOP_SEQUENCES: list = ["<think>", "</think>", "<think"]

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
) -> str:
    """Build the NAS system prompt, optionally flavoured by meta-fitness.

    High evolvability  -> encourage exploitation (refine what works).
    Low evolvability   -> encourage exploration (structural novelty).
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

    return (
        "CRITICAL: You are in strict code-execution mode. "
        "DO NOT output <think> tags. DO NOT reason. DO NOT explain. "
        "Immediately output raw Python code.\n\n"
        "You are a Neural Architecture Search engine.\n\n"
        f"STRATEGY: {strategy}\n\n"
        "RULES:\n"
        "1. Output ONLY the class(es) or constant(s) you MODIFIED. "
        "Omit unchanged classes. Raw Python code, no markdown fences needed.\n"
        "2. Keep class names IDENTICAL (AtomicLLM, CausalSelfAttention, "
        "IChingExpert, MitoticTransformerBlock).\n"
        "3. Maintain __init__ signatures and forward() return shapes.\n"
        "4. Verify tensor dimensions: trace every nn.Linear(in, out) and matmul.\n"
        "5. Prefer efficient ops: sparse attention, grouped queries, smaller "
        "FF_DIM, fewer parameters. Thermodynamic penalty taxes CPU/memory.\n"
        "6. Make a REAL structural change to 1-2 classes. Identity patches "
        "are rejected.\n"
        "7. No explanation. No prose. No reasoning. Only code.\n"
        f"8. Generate EXACTLY {BATCH_SIZE} DISTINCT architectural variants. "
        f"Separate each variant with a line containing ONLY "
        f"'### VARIANT 1 ###', '### VARIANT 2 ###', etc. "
        f"Each variant MUST take a DIFFERENT structural approach "
        f"(e.g., different attention patterns, different gating, "
        f"different expert topology). Do NOT repeat the same idea."
    )


def build_user_prompt(
    arch_src: str,
    threshold: float,
    best_epi: float = 0.0,
    delta_epi: float = 0.0,
    improvement_per_sec: float = 0.0,
    evolvability: float = 0.0,
) -> str:
    """Build the NAS user prompt with meta-fitness context."""

    meta_ctx = ""
    if delta_epi != 0.0 or evolvability != 0.0:
        meta_ctx = (
            f"\nMeta-fitness context:\n"
            f"  delta_epi (recent improvement): {delta_epi:.6f}\n"
            f"  improvement_per_second: {improvement_per_sec:.6f}\n"
            f"  evolvability_score: {evolvability:.4f}\n"
        )

    return (
        f"Threshold: {threshold:.4f} | Best epiplexity: {best_epi:.4f}\n"
        f"Efficient architectures score higher (thermodynamic penalty on "
        f"CPU/memory).{meta_ctx}\n\n"
        f"```python\n{arch_src}\n```\n\n"
        f"Generate EXACTLY {BATCH_SIZE} distinct variants.  "
        f"Start each variant with '### VARIANT N ###' on its own line "
        f"(N = 1, 2, 3, ...).  "
        f"Each variant outputs ONLY the class(es) it changed.  "
        f"No reasoning. No <think> tags.  "
        f"Start immediately with '### VARIANT 1 ###' then 'class'."
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
