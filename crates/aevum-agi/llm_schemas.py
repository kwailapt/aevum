"""TICK 22.6: Pydantic schemas + Instructor client for LLM structured output.

Industry-standard approach: instructor library wraps Ollama's OpenAI-compatible
endpoint, automatically injecting schema into prompts, validating responses via
Pydantic, and retrying on failure. No manual JSON parsing, no regex extraction.

Usage:
    from llm_schemas import get_instructor_client, MutationBatch

    client = get_instructor_client()
    result = client.chat.completions.create(
        model="qwen3.5:35b-a3b",
        response_model=MutationBatch,
        messages=[...],
        max_retries=3,
    )
    # result is a fully validated MutationBatch — guaranteed.
"""

from __future__ import annotations

from typing import Optional

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# INSTRUCTOR CLIENT (singleton)
# ═══════════════════════════════════════════════════════════════

_CLIENT: Optional[instructor.Instructor] = None


def get_instructor_client() -> instructor.Instructor:
    """Get or create the singleton Instructor client.

    Wraps Ollama's OpenAI-compatible endpoint at localhost:11434/v1.
    The api_key is required by the OpenAI SDK but ignored by Ollama.
    """
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = instructor.from_openai(
            OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            ),
            mode=instructor.Mode.JSON,
        )
    return _CLIENT


# ═══════════════════════════════════════════════════════════════
# MUTATION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class ArchitectPlan(BaseModel):
    """Output of the Architect (Slow Brain): mathematical strategy ONLY, no code.

    TICK 24.1: The Architect analyzes gradients/metrics and outputs a pure
    strategy.  The Coder then translates this into PyTorch AST.
    """
    analysis: str = Field(
        description=(
            "Mathematical analysis of current bottleneck and gradient landscape. "
            "Must be a single flat string — no nested objects. "
            "Do NOT use LaTeX, backslashes, or special escape characters; "
            "write math in plain English words."
        )
    )
    strategy: str = Field(
        description=(
            "Concrete mutation strategy: what to change, why, and expected effect. "
            "Express as mathematical transformations, NOT code. "
            "Must be a single flat string — no nested objects. "
            "Do NOT use LaTeX, backslashes, or special escape characters; "
            "write math in plain English words."
        )
    )
    target_organelle: str = Field(
        description="Class name to mutate (e.g. 'RoutingStrategy')"
    )
    constraints: list[str] = Field(
        description="List of invariants the Coder must preserve (shapes, interfaces, etc.)"
    )


class MutationVariant(BaseModel):
    """A single mutation variant produced by the LLM."""
    thought_process: str = Field(
        description="Brief reasoning about the mutation strategy"
    )
    target_organelle: str = Field(
        description="Class name being mutated (e.g. 'MitoticTransformerBlock')"
    )
    python_code: str = Field(
        description=(
            "Complete Python class definition — raw, executable. "
            "Must include both __init__ and forward methods for nn.Module classes. "
            "Use \\n for newlines."
        )
    )


class MutationBatch(BaseModel):
    """Batch of mutation variants."""
    variants: list[MutationVariant]


# ═══════════════════════════════════════════════════════════════
# FAST NAS SCHEMA (stateless_tick.py Fast Loop)
# ═══════════════════════════════════════════════════════════════

class FastNASOutput(BaseModel):
    """Output of a single NAS cycle in the Fast Loop."""
    code: str = Field(
        description=(
            "Raw Python class definitions — complete, executable. "
            "Must include both __init__ and forward methods for nn.Module classes."
        )
    )

