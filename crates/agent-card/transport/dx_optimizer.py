"""
ai2ai/transport/dx_optimizer.py
================================
TICK 40.3 Phase 2 — DX Documentation Optimizer

Reads the in-memory A/B telemetry from server.py, identifies the lowest-
performing 426 error documentation variant by integration success rate, and
uses the Fast Brain (qwen2.5-coder:7b via instructor/Ollama) to generate a
clearer replacement variant based on the highest-performing one.

The evolved variant is inserted back into server._DX_VARIANTS live — no restart
required.

Usage (one-shot):
    from ai2ai.transport.dx_optimizer import evolve_documentation_pool
    report = evolve_documentation_pool()

Usage (background loop):
    from ai2ai.transport.dx_optimizer import start_optimizer_loop
    asyncio.create_task(start_optimizer_loop(interval_s=3600))
"""

from __future__ import annotations

import asyncio
import logging
import random
import string
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# ── Minimum statistical threshold before we act ───────────────────────────────
# A variant must have at least this many hits before we consider its success
# rate meaningful enough to use in an evolution decision.
_MIN_HITS_THRESHOLD: int = 5

# ── Fast Brain model (mirrors mutator_daemon._FAST_BRAIN_MODEL) ──────────────
import os
_FAST_BRAIN_MODEL: str = os.environ.get("FAST_BRAIN_MODEL", "qwen2.5-coder:7b")
_LLM_TIMEOUT_S: float = 30.0


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic output schema for the Fast Brain
# ══════════════════════════════════════════════════════════════════════════════

class ImprovedVariant(BaseModel):
    """Structured output: a single improved documentation variant."""

    variant_id: str = Field(
        description=(
            "Short unique identifier for this variant. "
            "Format: '<letter>-<slug>' e.g. 'D-minimal' or 'E-tabular'. "
            "Must not collide with existing variant IDs."
        )
    )
    format: str = Field(
        description=(
            "One-word format descriptor: concise | json_example | "
            "step_by_step | tabular | minimal | verbose"
        )
    )
    how_to_fix: str = Field(
        description=(
            "The complete documentation text that will be returned in the "
            "'how_to_fix' field of the HTTP 426 response. "
            "Must be plain text (no HTML). "
            "Must clearly explain how to fix a non-conformant AgentCard payload. "
            "Must NOT contain the words 'system prompt', 'injection', or 'override'. "
            "Target: < 400 characters for readability."
        )
    )
    improvement_rationale: str = Field(
        description=(
            "One sentence explaining what was changed vs the source variant "
            "and why it should produce a higher integration success rate."
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# Fitness computation
# ══════════════════════════════════════════════════════════════════════════════

def compute_fitness(telemetry: dict[str, dict[str, int]]) -> dict[str, float | None]:
    """
    Compute integration success rate (successes / hits) per variant.

    Returns None for variants below _MIN_HITS_THRESHOLD — these are excluded
    from evolution decisions to avoid acting on noise.
    """
    fitness: dict[str, float | None] = {}
    for variant_id, counts in telemetry.items():
        hits = counts.get("hits", 0)
        successes = counts.get("successes", 0)
        if hits < _MIN_HITS_THRESHOLD:
            fitness[variant_id] = None   # insufficient data
        else:
            fitness[variant_id] = successes / hits
    return fitness


def pick_winner_loser(
    fitness: dict[str, float | None],
) -> tuple[str | None, str | None]:
    """
    Return (winner_id, loser_id) — the best and worst variants by success rate,
    considering only variants with sufficient data (fitness is not None).

    Returns (None, None) if fewer than 2 variants have enough data.
    """
    eligible = {vid: f for vid, f in fitness.items() if f is not None}
    if len(eligible) < 2:
        return None, None
    winner = max(eligible, key=lambda v: eligible[v])
    loser  = min(eligible, key=lambda v: eligible[v])
    return winner, loser


# ══════════════════════════════════════════════════════════════════════════════
# Fast Brain — generate an improved documentation variant
# ══════════════════════════════════════════════════════════════════════════════

def _get_instructor_client():
    """Lazy-load the instructor client (mirrors llm_schemas.get_instructor_client)."""
    try:
        import instructor
        from openai import OpenAI
        return instructor.from_openai(
            OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
            mode=instructor.Mode.JSON,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Cannot initialise instructor client: {exc}. "
            "Is Ollama running at localhost:11434?"
        ) from exc


def generate_improved_variant(
    winner_variant: dict,
    winner_fitness: float,
    loser_variant: dict,
    loser_fitness: float,
    existing_ids: set[str],
) -> ImprovedVariant:
    """
    Call the Fast Brain to produce a new documentation variant.

    The prompt gives the model:
      - The winning variant text and its measured success rate
      - The losing variant text and its measured success rate
      - Strict constraints (plain text, no injection keywords, ≤400 chars)
      - The AgentCard required fields for factual grounding

    Returns a validated ImprovedVariant Pydantic object.
    """
    client = _get_instructor_client()

    system_msg = (
        "You are a technical writer specialising in API developer experience. "
        "Your job is to write clear, concise HTTP error guidance that helps "
        "developers quickly fix malformed API requests. "
        "Output only valid JSON matching the requested schema. No prose outside JSON."
    )

    user_msg = (
        f"We are A/B testing three variants of a '426 Upgrade Required' error "
        f"message for POST /agents/register. A developer's payload was rejected "
        f"because it did not conform to AgentCard Spec v0.1.0.\n\n"
        f"WINNING variant (id={winner_variant['variant_id']!r}, "
        f"success_rate={winner_fitness:.1%}):\n"
        f"---\n{winner_variant['how_to_fix']}\n---\n\n"
        f"LOSING variant (id={loser_variant['variant_id']!r}, "
        f"success_rate={loser_fitness:.1%}):\n"
        f"---\n{loser_variant['how_to_fix']}\n---\n\n"
        f"AgentCard required fields: agent_id (pattern: org.name.M.m.p), "
        f"name, description, version (M.m.p), "
        f"protocol (native|mcp|openai|custom), endpoint (URL), "
        f"capabilities (array, each item needs 'name' snake_case + 'description').\n\n"
        f"Existing variant IDs (do not reuse): {sorted(existing_ids)}\n\n"
        f"Write a NEW variant that builds on what makes the winner clear and "
        f"avoids what makes the loser confusing. Keep it under 400 characters. "
        f"Plain text only."
    )

    result: ImprovedVariant = client.chat.completions.create(
        model=_FAST_BRAIN_MODEL,
        response_model=ImprovedVariant,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        max_retries=3,
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Main evolution step — mutates server._DX_VARIANTS in-place
# ══════════════════════════════════════════════════════════════════════════════

def evolve_documentation_pool(
    *,
    dry_run: bool = False,
    llm_call_fn=None,
) -> dict:
    """
    One evolution cycle:
      1. Read telemetry from server._DX_VARIANTS / _dx_telemetry
      2. Compute fitness per variant
      3. Identify winner + loser
      4. Call Fast Brain to generate an improved variant
      5. Remove loser from the live pool; append the new variant
      6. Reset telemetry counters for the evicted and new variants

    Args:
        dry_run:    If True, compute fitness and generate the new variant but
                    do NOT modify server._DX_VARIANTS or telemetry.
        llm_call_fn: Optional callable(winner, loser, existing_ids) → dict
                    override for testing.  Must return a dict with keys
                    variant_id, format, how_to_fix, improvement_rationale.

    Returns a report dict with keys:
        winner_id, loser_id, winner_fitness, loser_fitness,
        new_variant (dict), action ('evolved'|'skipped'), reason (str|None)
    """
    # Import the live server state
    import ai2ai.transport.server as _server

    telemetry: dict[str, dict[str, int]] = _server._dx_telemetry
    pool: list[dict]                      = _server._DX_VARIANTS

    fitness = compute_fitness(telemetry)
    winner_id, loser_id = pick_winner_loser(fitness)

    if winner_id is None or loser_id is None:
        reason = (
            f"Insufficient data: need ≥{_MIN_HITS_THRESHOLD} hits on at least "
            f"2 variants. Current fitness: {fitness}"
        )
        log.info("[dx_optimizer] Skipping evolution — %s", reason)
        return {
            "winner_id":      None,
            "loser_id":       None,
            "winner_fitness": None,
            "loser_fitness":  None,
            "new_variant":    None,
            "action":         "skipped",
            "reason":         reason,
        }

    if winner_id == loser_id:
        reason = "Winner and loser are the same variant — nothing to evolve."
        return {"action": "skipped", "reason": reason,
                "winner_id": winner_id, "loser_id": loser_id,
                "winner_fitness": fitness[winner_id], "loser_fitness": fitness[loser_id],
                "new_variant": None}

    winner_v  = next(v for v in pool if v["variant_id"] == winner_id)
    loser_v   = next(v for v in pool if v["variant_id"] == loser_id)
    existing  = {v["variant_id"] for v in pool}

    # Generate the new variant
    if llm_call_fn is not None:
        raw = llm_call_fn(winner_v, loser_v, existing)
        new_v = {
            "variant_id": raw["variant_id"],
            "format":     raw["format"],
            "how_to_fix": raw["how_to_fix"],
        }
        rationale = raw.get("improvement_rationale", "")
    else:
        improved: ImprovedVariant = generate_improved_variant(
            winner_variant  = winner_v,
            winner_fitness  = fitness[winner_id],
            loser_variant   = loser_v,
            loser_fitness   = fitness[loser_id],
            existing_ids    = existing,
        )
        new_v = {
            "variant_id": improved.variant_id,
            "format":     improved.format,
            "how_to_fix": improved.how_to_fix,
        }
        rationale = improved.improvement_rationale

    report = {
        "winner_id":      winner_id,
        "loser_id":       loser_id,
        "winner_fitness": fitness[winner_id],
        "loser_fitness":  fitness[loser_id],
        "new_variant":    new_v,
        "rationale":      rationale,
        "action":         "dry_run" if dry_run else "evolved",
        "reason":         None,
    }

    if dry_run:
        log.info("[dx_optimizer] Dry-run — would evict %s, add %s",
                 loser_id, new_v["variant_id"])
        return report

    # Mutate the live pool: remove loser, append new variant
    _server._DX_VARIANTS[:] = [v for v in pool if v["variant_id"] != loser_id]
    _server._DX_VARIANTS.append(new_v)

    # Add telemetry slot for the new variant; remove evicted slot
    _server._dx_telemetry.pop(loser_id, None)
    _server._dx_telemetry[new_v["variant_id"]] = {"hits": 0, "successes": 0}

    log.info(
        "[dx_optimizer] Evolved pool — evicted %s (fitness=%.2f), "
        "added %s (format=%s)",
        loser_id, fitness[loser_id], new_v["variant_id"], new_v["format"],
    )
    return report


# ══════════════════════════════════════════════════════════════════════════════
# Background loop (opt-in)
# ══════════════════════════════════════════════════════════════════════════════

async def start_optimizer_loop(interval_s: float = 3600.0) -> None:
    """
    Async background task: run one evolution cycle every `interval_s` seconds.

    Designed to be launched via asyncio.create_task() from server lifespan.
    Catches and logs all exceptions so a bad LLM call never crashes the server.
    """
    log.info("[dx_optimizer] Background loop started (interval=%.0fs)", interval_s)
    while True:
        await asyncio.sleep(interval_s)
        try:
            report = evolve_documentation_pool()
            log.info("[dx_optimizer] Cycle complete: %s", report)
        except Exception as exc:
            log.exception("[dx_optimizer] Evolution cycle failed: %s", exc)
