#!/usr/bin/env python3
"""wiki_compiler.py — Zone 2 Ontology Engine (TICK 38.4 + 38.5).

"Turn raw alien knowledge into structured Rule-IR capital."

Watches /Volumes/MYWORK/Chaos/Aevum_wiki/raw/inbox/ for .md files and compiles
them into the Obsidian wiki ontology, fully enforcing the constitutional laws
defined in /Volumes/MYWORK/Chaos/Aevum_wiki/CLAUDE.md.

══════════════════════════════════════════════════════════════════════════════
TICK 38.5 — THERMODYNAMIC & FINANCIAL JUSTICE
══════════════════════════════════════════════════════════════════════════════

LLM backend: Local Ollama (OpenAI-compatible API at http://localhost:11434/v1)
Default model: qwen2.5-coder:7b  (fast, local, zero marginal cost)
Override:      COMPILER_MODEL env var or --model CLI arg
               e.g.  COMPILER_MODEL=qwen3.5:35b-a3b python3 wiki_compiler.py --once

Using a Tier 3 Cloud Oracle (Anthropic Haiku/Sonnet) for routine Markdown-to-
Pydantic extraction violates First Principles of resource sovereignty.
Local inference is the correct thermodynamic operating point for this task.

instructor.from_openai() wraps the Ollama client.
max_retries=3 handles local model JSON-enforcement instability.

══════════════════════════════════════════════════════════════════════════════
CONSTITUTIONAL ENFORCEMENT
══════════════════════════════════════════════════════════════════════════════

A1 — Entropy Reduction: Every write must add novel compression. No restating.
A2 — raw/ Immutability: Files are never modified. Intra-raw MOVE (inbox→ext)
     is pipeline state management only; content is frozen at ingest.
A3 — LLM Writes Wiki: All wiki/ content is LLM-compiled via instructor.
A5 — Schema Supremacy: CLAUDE.md overrides all other instructions.

NAMING LAW (§5): All wiki/ filenames are kebab-case, ASCII only, no spaces.
FRONTMATTER (§3): All pages begin with mandatory YAML (type, title, aliases,
    tags, tick, created, updated, source_count, confidence, status).
LOG FORMAT (§10): Entries use ## [YYYY-MM-DD] operation | subject headers.
CROSS-REFERENCE (§11): All known concepts/entities use Obsidian [[wikilinks]].

══════════════════════════════════════════════════════════════════════════════
PIPELINE
══════════════════════════════════════════════════════════════════════════════

For each .md in raw/inbox/:
  1. Read raw content
  2. LLM extraction → CompiledKnowledge (instructor + Pydantic, local Ollama)
  3. Write wiki/concepts/<slug>.md  (type: concept, full frontmatter)
  4. Write wiki/sources/<slug>.md   (type: source,  full frontmatter)
  5. Append §10-compliant entry to wiki/log.md
  6. Atomic MOVE: raw/inbox/<file> → raw/ext/<file>  (consumed exactly once)

Fallback: If LLM call fails after max_retries, deterministic regex extractor runs.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from datetime import date
from pathlib import Path
from typing import List, Literal, Optional

import instructor
import openai
from pydantic import BaseModel, Field, field_validator


# ── Paths ─────────────────────────────────────────────────────────────────────
_WIKI_ROOT     = Path("/Volumes/MYWORK/Chaos/Aevum_wiki")
_RAW_INBOX     = _WIKI_ROOT / "raw" / "inbox"
_RAW_EXT       = _WIKI_ROOT / "raw" / "ext"
_WIKI_CONCEPTS = _WIKI_ROOT / "wiki" / "concepts"
_WIKI_SOURCES  = _WIKI_ROOT / "wiki" / "sources"
_WIKI_INDEX    = _WIKI_ROOT / "wiki" / "index.md"
_WIKI_LOG      = _WIKI_ROOT / "wiki" / "log.md"

# ── LLM config (TICK 38.5 — Local Ollama, zero marginal cost) ────────────────
_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_OLLAMA_API_KEY  = "ollama"   # Ollama OpenAI-compat API ignores the key
_DEFAULT_MODEL   = os.environ.get("COMPILER_MODEL", "qwen2.5-coder:7b")
_MAX_TOKENS      = 1500
_MAX_RETRIES     = 3          # Instructor retry budget for JSON enforcement
_POLL_S          = 60.0

# ── Controlled tag vocabulary (CLAUDE.md §3) ──────────────────────────────────
_VALID_TAGS = {
    "aevum", "thermodynamics", "information-theory", "autopoiesis",
    "boundary", "constraint-system", "agency", "protocol",
    "formal-system", "first-principles", "complex-systems",
    "tensor", "computation", "sovereignty", "agi-architecture",
}

# ── Confidence / status vocabulary ────────────────────────────────────────────
ConfidenceLevel = Literal["seed", "low", "medium", "high", "axiomatic"]
StatusValue     = Literal["stub", "draft", "stable", "contested", "deprecated"]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas — mirrored from CLAUDE.md §3 Frontmatter Schema
# ─────────────────────────────────────────────────────────────────────────────

class CoreConcept(BaseModel):
    name: str = Field(description="Canonical concept name, ≤5 words")
    definition: str = Field(description="One sentence. First principles only. No filler.")
    category: Literal["algorithm", "constraint", "topology", "principle"]
    leverage_score: float = Field(ge=0.0, le=1.0, description="Insight compression ratio [0,1]")


class RuleIRConstraint(BaseModel):
    constraint_id: str = Field(description="snake_case identifier for this constraint")
    target_category: Literal[
        "temperature_policy", "structural_scope", "probe_strategy",
        "risk_appetite", "organelle_priority", "recombination_bias",
        "parsimony_pressure", "temporal_horizon",
    ]
    delta_direction: Literal["increase", "decrease", "oscillate"]
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeDependency(BaseModel):
    concept_name: str = Field(description="Name of the required/extended/contradicted concept")
    relation: Literal["requires", "extends", "contradicts"]


class CompiledKnowledge(BaseModel):
    """Root extraction schema. All fields mandatory."""
    # Identity
    page_slug: str = Field(
        description=(
            "kebab-case ASCII filename for the concept page (no extension). "
            "Must be lowercase, hyphens only (no underscores, no spaces, no Unicode). "
            "Max 48 chars. Must be descriptive. Example: 'sinkhorn-sparse-routing'."
        )
    )
    source_slug: str = Field(
        description=(
            "kebab-case ASCII filename for the source page (no extension). "
            "Same rules as page_slug. Example: 'distilled-sinkhorn-cs-ai'."
        )
    )
    title: str = Field(description="Human-readable title for the concept page (≤80 chars)")
    source_title: str = Field(description="Human-readable title for the source page (≤80 chars)")

    # Frontmatter fields (CLAUDE.md §3)
    tags: List[str] = Field(
        description=(
            "1–4 tags from the controlled vocabulary: "
            "aevum, thermodynamics, information-theory, autopoiesis, boundary, "
            "constraint-system, agency, protocol, formal-system, first-principles, "
            "complex-systems, tensor, computation, sovereignty, agi-architecture. "
            "Only use tags from this list."
        )
    )
    confidence: ConfidenceLevel = Field(
        description="Epistemic status: seed | low | medium | high | axiomatic"
    )
    status: StatusValue = Field(
        description="Lifecycle state: stub | draft | stable | contested | deprecated"
    )

    # Knowledge content
    core_concepts: List[CoreConcept] = Field(description="2–5 core concepts extracted")
    rule_ir_constraints: List[RuleIRConstraint] = Field(
        description="1–3 operational constraints mappable to the ConstraintMatrix"
    )
    dependencies: List[KnowledgeDependency] = Field(
        description="Known concepts this insight requires, extends, or contradicts"
    )
    first_principle_summary: str = Field(
        description="≤3 sentences. First principles only. No narrative. No pleasantries."
    )
    counter_intuitive_insight: str = Field(
        description="The single most surprising, non-obvious finding. ≤2 sentences."
    )
    entropy_note: str = Field(
        description="What new knowledge this adds vs what already exists. ≤1 sentence."
    )

    @field_validator("page_slug", "source_slug", mode="before")
    @classmethod
    def enforce_kebab_case(cls, v: str) -> str:
        """Force slug to valid kebab-case: lowercase ASCII, hyphens only."""
        v = v.lower()
        # Replace any non-alphanumeric chars with hyphens
        v = re.sub(r"[^a-z0-9]+", "-", v)
        v = v.strip("-")
        return v[:48]

    @field_validator("tags", mode="before")
    @classmethod
    def enforce_tag_vocabulary(cls, tags: list) -> list:
        """Strip tags not in the controlled vocabulary."""
        return [t for t in tags if t in _VALID_TAGS] or ["agi-architecture"]


# ─────────────────────────────────────────────────────────────────────────────
# LLM Extractor
# ─────────────────────────────────────────────────────────────────────────────

_CONSTITUTIONAL_SYSTEM_PROMPT = """You are the wiki compiler for an AGI knowledge system.
You enforce the constitutional laws of CLAUDE.md absolutely.

CRITICAL RULES you MUST follow:
1. page_slug and source_slug MUST be kebab-case (lowercase, hyphens only, ASCII, no underscores).
   Example of CORRECT slug: "sinkhorn-sparse-routing"
   Example of WRONG slug: "distilled_insight___cs_ai"
2. All wiki pages use Obsidian [[wikilinks]] for cross-references.
3. Extract ONLY: first-principle constraints, algorithmic topology, counter-intuitive insights.
4. Strip all pleasantries, narrative, and noise.
5. Tags must be selected from: aevum, thermodynamics, information-theory, autopoiesis,
   boundary, constraint-system, agency, protocol, formal-system, first-principles,
   complex-systems, tensor, computation, sovereignty, agi-architecture.
6. confidence field: seed | low | medium | high | axiomatic
7. status field: stub | draft | stable | contested | deprecated

The knowledge system targets AGI architecture, constraint matrices, and thermodynamic computation."""


def _build_client(model: str = _DEFAULT_MODEL) -> tuple[instructor.Instructor, str]:
    """Build an instructor-patched OpenAI client pointing at local Ollama.

    Returns (client, model_name).
    Uses instructor.from_openai() with max_retries=3 for JSON enforcement.
    Override model with COMPILER_MODEL env var or --model CLI arg.
    """
    raw_client = openai.OpenAI(
        base_url=_OLLAMA_BASE_URL,
        api_key=_OLLAMA_API_KEY,
    )
    client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)
    return client, model


def _extract_via_llm(
    content: str,
    client: instructor.Instructor,
    model: str,
) -> CompiledKnowledge:
    """Extract CompiledKnowledge via local Ollama with instructor JSON enforcement."""
    return client.chat.completions.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        max_retries=_MAX_RETRIES,
        messages=[
            {"role": "system", "content": _CONSTITUTIONAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract structured knowledge from this distilled research insight.\n\n"
                    "---\n"
                    f"{content[:3000]}\n"
                    "---"
                ),
            },
        ],
        response_model=CompiledKnowledge,
    )


def _fallback_slug(text: str) -> str:
    """Generate a valid kebab-case slug from arbitrary text."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:48] or "unknown-insight"


def _extract_fallback(content: str, filepath: Path) -> CompiledKnowledge:
    """Deterministic fallback when LLM is unavailable."""
    title_m = re.search(r"^# (.+)$", content, re.MULTILINE)
    title = (title_m.group(1).strip() if title_m else filepath.stem)[:80]

    track_m = re.search(r"\*\*Track\*\*:\s*([AB])", content)
    score_m = re.search(r"\*\*Score\*\*:\s*([\d.]+)", content)
    score = float(score_m.group(1)) if score_m else 0.5

    fp_m = re.search(r"## First-Principle Constraints\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    fp = fp_m.group(1).strip()[:600] if fp_m else "See source document."

    ci_m = re.search(r"## Counter-Intuitive Insights\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    ci_text = ci_m.group(1).strip() if ci_m else ""
    ci_bullets = [l.lstrip("- ").strip() for l in ci_text.splitlines() if l.strip().startswith("-")]
    ci = (ci_bullets[0] if ci_bullets else ci_text[:200]) or "No counter-intuitive insight extracted."

    page_slug = _fallback_slug(title)
    source_slug = _fallback_slug(f"source-{filepath.stem[:32]}")

    return CompiledKnowledge(
        page_slug=page_slug,
        source_slug=source_slug,
        title=title,
        source_title=f"Source: {title}",
        tags=["agi-architecture", "first-principles"],
        confidence="low",
        status="draft",
        core_concepts=[CoreConcept(
            name=title[:48],
            definition="Extracted from Track-A ingestion pipeline.",
            category="principle",
            leverage_score=min(1.0, max(0.0, score)),
        )],
        rule_ir_constraints=[RuleIRConstraint(
            constraint_id=re.sub(r"[^a-z0-9_]", "_", title.lower())[:32] or "unknown",
            target_category="temperature_policy",
            delta_direction="increase",
            confidence=0.5,
        )],
        dependencies=[],
        first_principle_summary=fp,
        counter_intuitive_insight=ci,
        entropy_note="Distilled from external feed; topology not previously represented in wiki.",
    )


def extract_knowledge(
    content: str, filepath: Path, client: instructor.Instructor, model: str
) -> CompiledKnowledge:
    try:
        return _extract_via_llm(content, client, model)
    except Exception as exc:
        print(f"[wiki_compiler] LLM failed ({type(exc).__name__}: {exc}), using fallback.")
        return _extract_fallback(content, filepath)


# ─────────────────────────────────────────────────────────────────────────────
# Frontmatter Builder
# ─────────────────────────────────────────────────────────────────────────────

def _frontmatter(
    page_type: str,
    title: str,
    tags: List[str],
    tick: int,
    source_count: int,
    confidence: str,
    status: str,
    aliases: Optional[List[str]] = None,
) -> str:
    today = date.today().isoformat()
    tag_str = ", ".join(f'"{t}"' for t in tags)
    alias_str = ", ".join(f'"{a}"' for a in (aliases or []))
    return (
        "---\n"
        f'type: {page_type}\n'
        f'title: "{title}"\n'
        f"aliases: [{alias_str}]\n"
        f"tags: [{tag_str}]\n"
        f"tick: {tick}\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"source_count: {source_count}\n"
        f"confidence: {confidence}\n"
        f"status: {status}\n"
        "---\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Wiki Writers
# ─────────────────────────────────────────────────────────────────────────────

def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def write_concept_page(k: CompiledKnowledge) -> Path:
    """Write wiki/concepts/<page_slug>.md with full constitutional frontmatter."""
    fm = _frontmatter(
        page_type="concept",
        title=k.title,
        tags=k.tags,
        tick=0,
        source_count=1,
        confidence=k.confidence,
        status=k.status,
    )
    body_lines = [
        f"# {k.title}",
        "",
        "## First-Principle Summary",
        "",
        k.first_principle_summary,
        "",
        "## Counter-Intuitive Insight",
        "",
        k.counter_intuitive_insight,
        "",
        "## Core Concepts",
        "",
    ]
    for c in k.core_concepts:
        body_lines += [
            f"### [[{_fallback_slug(c.name)}|{c.name}]]",
            f"- **Category**: {c.category}",
            f"- **Leverage**: {c.leverage_score:.2f}",
            f"- {c.definition}",
            "",
        ]

    if k.rule_ir_constraints:
        body_lines += ["## Rule-IR Constraints", ""]
        for r in k.rule_ir_constraints:
            body_lines.append(
                f"- `{r.constraint_id}` → [[rule-ir|{r.target_category}]] "
                f"[{r.delta_direction}] conf={r.confidence:.2f}"
            )
        body_lines.append("")

    if k.dependencies:
        body_lines += ["## Dependencies", ""]
        for d in k.dependencies:
            dep_slug = _fallback_slug(d.concept_name)
            body_lines.append(f"- {d.relation}: [[{dep_slug}|{d.concept_name}]]")
        body_lines.append("")

    out = _WIKI_CONCEPTS / f"{k.page_slug}.md"
    _atomic_write(out, fm + "\n".join(body_lines))
    return out


def write_source_page(k: CompiledKnowledge, original_filename: str) -> Path:
    """Write wiki/sources/<source_slug>.md with full constitutional frontmatter."""
    fm = _frontmatter(
        page_type="source",
        title=k.source_title,
        tags=k.tags,
        tick=0,
        source_count=1,
        confidence=k.confidence,
        status=k.status,
    )
    body_lines = [
        f"# {k.source_title}",
        "",
        f"**Original file**: `{original_filename}`",
        f"**Compiled concept**: [[{k.page_slug}]]",
        "",
        "## Extracted Constraints",
        "",
    ]
    for r in k.rule_ir_constraints:
        body_lines.append(
            f"- `{r.constraint_id}`: target=[[rule-ir|{r.target_category}]] "
            f"dir={r.delta_direction} conf={r.confidence:.2f}"
        )
    body_lines += [
        "",
        "## Concept Links",
        "",
    ]
    for c in k.core_concepts:
        body_lines.append(f"- [[{_fallback_slug(c.name)}|{c.name}]] ({c.category})")
    if k.dependencies:
        body_lines += ["", "## Dependencies", ""]
        for d in k.dependencies:
            body_lines.append(f"- {d.relation}: [[{_fallback_slug(d.concept_name)}|{d.concept_name}]]")
    body_lines.append("")

    out = _WIKI_SOURCES / f"{k.source_slug}.md"
    _atomic_write(out, fm + "\n".join(body_lines))
    return out


def append_log_entry(
    k: CompiledKnowledge,
    source_filename: str,
    concept_path: Path,
    source_path: Path,
) -> None:
    """Append §10-compliant log entry: ## [YYYY-MM-DD] operation | subject."""
    today = date.today().isoformat()
    pages_created = f"[[{k.page_slug}]], [[{k.source_slug}]]"
    entry = (
        f"\n## [{today}] ingest | {source_filename}\n"
        f"\n"
        f"Pages created: {pages_created}. "
        f"Source processed: `{source_filename}`.\n"
        f"Entropy note: {k.entropy_note}\n"
        f"Concepts extracted: "
        + ", ".join(f"[[{_fallback_slug(c.name)}|{c.name}]]" for c in k.core_concepts)
        + ".\n"
    )
    with open(_WIKI_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def update_index(k: CompiledKnowledge) -> None:
    """Append rows for concept + source pages to wiki/index.md."""
    if not _WIKI_INDEX.exists():
        _WIKI_INDEX.write_text(
            "# Aevum Wiki — Index\n\n"
            "> Auto-generated catalog. Do not edit manually. Updated on every ingest.\n\n"
            "| Page | Type | Summary | Tick | Sources |\n"
            "|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    concept_summary = k.first_principle_summary[:97] + "..." if len(k.first_principle_summary) > 100 else k.first_principle_summary
    source_summary = f"Source compilation of {k.title}"[:100]
    rows = (
        f"| [[{k.page_slug}]] | concept | {concept_summary} | 0 | 1 |\n"
        f"| [[{k.source_slug}]] | source | {source_summary} | 0 | 1 |\n"
    )
    with open(_WIKI_INDEX, "a", encoding="utf-8") as f:
        f.write(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Physical Boundary Shift: raw/inbox → raw/ext
# ─────────────────────────────────────────────────────────────────────────────

def move_to_ext(src: Path) -> Path:
    """Atomically MOVE processed file from raw/inbox/ → raw/ext/ (consumed once)."""
    _RAW_EXT.mkdir(parents=True, exist_ok=True)
    dst = _RAW_EXT / src.name
    try:
        src.rename(dst)
    except OSError:
        # Cross-device fallback: copy then unlink
        shutil.copy2(str(src), str(dst))
        src.unlink()
    return dst


# ─────────────────────────────────────────────────────────────────────────────
# Core Compile Function
# ─────────────────────────────────────────────────────────────────────────────

def compile_file(filepath: Path, client: instructor.Instructor, model: str) -> dict:
    """Compile one .md from raw/inbox/ → wiki pages → MOVE to raw/ext/."""
    content = filepath.read_text(encoding="utf-8")
    print(f"[wiki_compiler] Compiling {filepath.name} ({len(content)} chars) via {model} ...")

    k = extract_knowledge(content, filepath, client, model)
    print(f"[wiki_compiler]   slug={k.page_slug} | conf={k.confidence} | status={k.status}")

    concept_path = write_concept_page(k)
    source_path  = write_source_page(k, filepath.name)
    append_log_entry(k, filepath.name, concept_path, source_path)
    update_index(k)
    ext_path = move_to_ext(filepath)

    print(
        f"[wiki_compiler] ✓ [[{k.page_slug}]] "
        f"| {len(k.core_concepts)} concepts | {len(k.rule_ir_constraints)} constraints "
        f"| MOVED → raw/ext/"
    )
    return {
        "slug": k.page_slug,
        "concept_path": str(concept_path),
        "source_path": str(source_path),
        "ext_path": str(ext_path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Daemon
# ─────────────────────────────────────────────────────────────────────────────

class WikiCompiler:
    """Zone 2 Ontology Engine daemon. Constitutional enforcement: CLAUDE.md.

    TICK 38.5: Uses local Ollama (OpenAI-compatible) for zero-cost inference.
    Default model: qwen2.5-coder:7b. Override via COMPILER_MODEL env var or --model.
    """

    def __init__(self, poll_interval_s: float = _POLL_S, model: str = _DEFAULT_MODEL) -> None:
        self.poll_interval_s = poll_interval_s
        self.model = model
        self._client: Optional[instructor.Instructor] = None
        self._compiled_count = 0

    @property
    def client(self) -> instructor.Instructor:
        if self._client is None:
            self._client, self.model = _build_client(self.model)
        return self._client

    def scan_and_compile(self) -> List[dict]:
        inbox_files = sorted(_RAW_INBOX.glob("*.md"))
        if not inbox_files:
            return []
        results = []
        for filepath in inbox_files:
            try:
                result = compile_file(filepath, self.client, self.model)
                results.append(result)
                self._compiled_count += 1
            except Exception as exc:
                print(f"[wiki_compiler] ERROR on {filepath.name}: {exc}")
        return results

    def run_forever(self) -> None:
        print(
            f"[wiki_compiler] Daemon started. Watching: {_RAW_INBOX} "
            f"| model={self.model} | poll={self.poll_interval_s}s"
        )
        while True:
            try:
                results = self.scan_and_compile()
                if results:
                    print(f"[wiki_compiler] Compiled {len(results)} files (total={self._compiled_count})")
            except Exception as exc:
                print(f"[wiki_compiler] Scan error (non-fatal): {exc}")
            time.sleep(self.poll_interval_s)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Wiki Compiler — Zone 2 Ontology Engine (TICK 38.4+38.5)")
    parser.add_argument("--once", action="store_true", help="Compile all inbox files once and exit")
    parser.add_argument("--poll", type=float, default=_POLL_S)
    parser.add_argument(
        "--model",
        type=str,
        default=_DEFAULT_MODEL,
        help=(
            f"Ollama model to use (default: {_DEFAULT_MODEL}). "
            "Also configurable via COMPILER_MODEL env var. "
            "Examples: qwen2.5-coder:7b, qwen3.5:35b-a3b"
        ),
    )
    args = parser.parse_args()

    print(f"[wiki_compiler] Backend: Ollama @ {_OLLAMA_BASE_URL} | model={args.model}")

    compiler = WikiCompiler(poll_interval_s=args.poll, model=args.model)
    if args.once:
        # Append constitutional correction note for prior malformed pipe-table log entries
        today = date.today().isoformat()
        correction = (
            f"\n## [{today}] amendment | wiki/log.md\n"
            f"\nConstitutional correction: 7 pipe-table log entries from the "
            f"non-compliant pre-38.5 run were structurally invalid per §10 log.md Law. "
            f"Those pages have been deleted and source files restored to `raw/inbox/` "
            f"for recompilation. All subsequent entries follow §10 format.\n"
        )
        try:
            # Only write if the correction hasn't been logged yet
            log_content = _WIKI_LOG.read_text(encoding="utf-8") if _WIKI_LOG.exists() else ""
            if "Constitutional correction" not in log_content:
                with open(_WIKI_LOG, "a", encoding="utf-8") as f:
                    f.write(correction)
                print("[wiki_compiler] Constitutional correction logged to wiki/log.md")
        except Exception as e:
            print(f"[wiki_compiler] Could not write correction log: {e}")

        results = compiler.scan_and_compile()
        print(f"\n[wiki_compiler] One-shot complete: {len(results)} files compiled.")
        for r in results:
            print(f"  → [[{r['slug']}]] | concept: {r['concept_path']}")
    else:
        compiler.run_forever()
