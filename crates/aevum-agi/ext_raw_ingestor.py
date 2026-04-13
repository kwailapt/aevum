#!/usr/bin/env python3
"""ext_raw_ingestor.py — External Raw Value Capture Daemon (TICK 38.1-38.3).

"Let the universe feed the organism with alien knowledge."

A background daemon that simulates pulling from external feeds (ArXiv/GitHub)
and distills the top 5% of discovered knowledge into two thermodynamic outputs:

1. Markdown wisdom files → routed by Dual-Track classifier
   Track A (Heavy-Tail Capital): high T+L dominance
       - Gödelian .json  → candidate_pool/goedel_pending/
       - Distilled .md   → /Volumes/MYWORK/Chaos/Aevum_wiki/raw/inbox/
   Track B (Urgent Metabolic Cure): high R dominance
       - Both .json + .md → candidate_pool/immediate_applicable/

2. Gödelian constraint payloads (schema below).

══════════════════════════════════════════════════════════════════════════════
SCORING FORMULA  (TICK 38.2 — hardcoded)
══════════════════════════════════════════════════════════════════════════════

    Score = 0.25*R + 0.20*N + 0.15*E + 0.15*C + 0.15*T + 0.10*L

Where:
    R = Relevance       — how aligned the item is with current AGI focus
    N = Novelty         — how far from the current knowledge frontier
    E = Evidence        — strength of empirical backing (citations, tests)
    C = Impact          — downstream influence (stars, forks, citations)
    T = Transferability — how directly the insight can be applied
    L = Leverage        — compression ratio: insight-to-token density

Top 5% percentile by Score → distill → dual-track route.

══════════════════════════════════════════════════════════════════════════════
THERMODYNAMIC CLOCK  (TICK 38.1)
══════════════════════════════════════════════════════════════════════════════

The daemon wakes exactly twice per day (every 43 200 seconds = 12 hours).
Over-polling generates thermodynamic waste; twice-daily ingestion is sufficient
for the organism to absorb new alien knowledge between mutation cycles.

══════════════════════════════════════════════════════════════════════════════
DUAL-TRACK ROUTING  (TICK 38.3)
══════════════════════════════════════════════════════════════════════════════

Classification rule:
    Track A if (T + L) >= (R + N)   → Heavy-Tail Capital
    Track B if  R     >  T + L      → Urgent Metabolic Cure  (high-R dominant)

══════════════════════════════════════════════════════════════════════════════
IPC CONTRACT
══════════════════════════════════════════════════════════════════════════════

All file writes use the atomic tmp→os.rename() protocol to prevent partial
reads by concurrent processes (mirrors TICK 12.0 env_evolver.py pattern).

Gödelian constraint payload schema:
    {
        "axiom_name": str,           — human-readable label
        "target_category": int,      — ConstraintMatrix row index (0-7)
        "perturbation_vector": [float x8],  — additive delta to C[target_category]
        "source_score": float,       — the distilled Score that produced this
        "timestamp": float,          — Unix timestamp of ingestion
        "source_type": str,          — "arxiv" | "github" | "synthetic"
        "title": str,                — feed item title
        "abstract": str,             — brief summary
        "track": str,                — "A" | "B"
    }

══════════════════════════════════════════════════════════════════════════════
DESIGN CONSTRAINT: NO CSO DEPENDENCY
══════════════════════════════════════════════════════════════════════════════

External ingestion has no causal chain — it is thermodynamic fuel, not an
economic value claim. The Causal Settlement Oracle (TICK 37) MUST NOT gate
this path. Gödelian constraints flow through filesystem IPC exclusively and
are consumed by niche_evolver.py's execute_fission() method.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# ── Output Paths ──────────────────────────────────────────────────────────────
_GOEDEL_PENDING_PATH: str = "candidate_pool/goedel_pending"
_IMMEDIATE_APPLICABLE_PATH: str = "candidate_pool/immediate_applicable"
_WIKI_INBOX_PATH: str = "/Volumes/MYWORK/Chaos/Aevum_wiki/raw/inbox"

# ── Scoring Weights (TICK 38.2 — hardcoded, single source of truth) ──────────
_a: float = 0.25   # R — Relevance
_b: float = 0.20   # N — Novelty
_c: float = 0.15   # E — Evidence
_d: float = 0.15   # C — Impact
_e: float = 0.15   # T — Transferability
_f: float = 0.10   # L — Leverage

# ── Top-K Selection ──────────────────────────────────────────────────────────
_TOP_PERCENTILE: float = 0.05   # strict top 5%

# ── Thermodynamic Clock (TICK 38.1) ──────────────────────────────────────────
_CLOCK_INTERVAL_S: float = 43200.0   # 12 hours — universe feeds the organism twice/day

# ── Simulation parameters ─────────────────────────────────────────────────────
_AGI_FOCUS_KEYWORDS: List[str] = [
    "mixture of experts", "sparse routing", "neural architecture search",
    "meta-learning", "autopoiesis", "self-organization", "sinkhorn",
    "kronecker", "hilbert space", "causal inference", "information geometry",
    "free energy principle", "thermodynamic", "active inference",
    "evolutionary algorithm", "constraint matrix", "topological",
]

_SOURCE_DOMAINS: List[str] = [
    "cs.AI", "cs.LG", "cs.NE", "stat.ML",
    "quant-ph", "cond-mat", "math.OC", "cs.SY",
]

_CM_CATEGORIES: List[str] = [
    "temperature_policy",
    "structural_scope",
    "probe_strategy",
    "risk_appetite",
    "organelle_priority",
    "recombination_bias",
    "parsimony_pressure",
    "temporal_horizon",
]
_N_CAT: int = len(_CM_CATEGORIES)   # 8
_N_CON: int = 8                     # must match rule_ir.py N_CON


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeedItem:
    """Raw item pulled from a simulated external feed."""
    item_id: str
    title: str
    abstract: str
    source_type: str           # "arxiv" | "github"
    domain: str
    citations: int
    forks: int
    days_since_published: int
    keyword_overlap: int


@dataclass
class ScoredItem:
    """Feed item with computed Score components."""
    item: FeedItem
    R: float   # Relevance
    N: float   # Novelty
    E: float   # Evidence
    C: float   # Impact
    T: float   # Transferability
    L: float   # Leverage
    score: float = field(init=False)

    def __post_init__(self) -> None:
        self.score = _score_formula(self.R, self.N, self.E, self.C, self.T, self.L)


@dataclass
class GoedelConstraint:
    """Alien parameter perturbation distilled from a top-5% feed item."""
    axiom_name: str
    target_category: int
    perturbation_vector: List[float]
    source_score: float
    timestamp: float
    source_type: str
    title: str
    abstract: str
    track: str   # "A" | "B"

    def to_dict(self) -> dict:
        return {
            "axiom_name": self.axiom_name,
            "target_category": self.target_category,
            "perturbation_vector": self.perturbation_vector,
            "source_score": self.source_score,
            "timestamp": self.timestamp,
            "source_type": self.source_type,
            "title": self.title,
            "abstract": self.abstract,
            "track": self.track,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Scoring Engine (TICK 38.2 — hardcoded formula)
# ─────────────────────────────────────────────────────────────────────────────

def _score_formula(R: float, N: float, E: float, C: float, T: float, L: float) -> float:
    """Hardcoded scoring formula.  Single source of truth for all callers.

    Score = a*R + b*N + c*E + d*C + e*T + f*L
          = 0.25*R + 0.20*N + 0.15*E + 0.15*C + 0.15*T + 0.10*L
    """
    return _a * R + _b * N + _c * E + _d * C + _e * T + _f * L


def score_item(item: FeedItem) -> ScoredItem:
    """Apply the 6-factor scoring formula to a feed item.

    All sub-scores are normalized to [0, 1] before weighting.

    R — Relevance: keyword_overlap / len(_AGI_FOCUS_KEYWORDS), clamped to [0,1].
    N — Novelty: inversely proportional to days_since_published.
                 Papers/repos within 30 days score 1.0; 2-year-old → 0.0.
    E — Evidence: log-normalized citation count.
    C — Impact: log-normalized (citations + forks).
    T — Transferability: fixed per source_type + keyword overlap bonus.
    L — Leverage: abstract length compression proxy.
    """
    R = min(1.0, item.keyword_overlap / len(_AGI_FOCUS_KEYWORDS))
    N = max(0.0, 1.0 - item.days_since_published / 730.0)
    E = math.log(item.citations + 1) / math.log(1001.0)
    C = math.log(item.citations + item.forks + 1) / math.log(2001.0)
    T = min(1.0, (0.7 + 0.3 * R) if item.source_type == "github" else (0.5 + 0.5 * R))
    word_count = len(item.abstract.split())
    L = min(1.0, max(0.0, 1.0 - word_count / 400.0) + (0.5 if item.citations > 50 else 0.0))
    return ScoredItem(item=item, R=R, N=N, E=E, C=C, T=T, L=L)


def filter_top_percentile(
    scored_items: List[ScoredItem],
    percentile: float = _TOP_PERCENTILE,
) -> List[ScoredItem]:
    """Return items in the strict top `percentile` fraction by score.

    For n=100 items and percentile=0.05, returns exactly 5 items.
    For smaller batches, returns at least 1 item.
    """
    if not scored_items:
        return []
    scored_items.sort(key=lambda x: x.score, reverse=True)
    k = max(1, int(math.ceil(len(scored_items) * percentile)))
    return scored_items[:k]


# ─────────────────────────────────────────────────────────────────────────────
# Dual-Track Routing (TICK 38.3)
# ─────────────────────────────────────────────────────────────────────────────

def classify_track(item: ScoredItem) -> str:
    """Return "A" (Heavy-Tail Capital) or "B" (Urgent Metabolic Cure).

    Track A: T + L >= R + N  — transferability/leverage dominant.
             → High external value capital; feeds the long-term wiki ontology.
    Track B: R > T + L       — relevance dominant.
             → Immediate cure for current bottlenecks; fast-brain consumable.
    """
    if (item.T + item.L) >= (item.R + item.N):
        return "A"
    return "B"


# ─────────────────────────────────────────────────────────────────────────────
# Wisdom Extraction (TICK 38.2 — first-principles distillation only)
# ─────────────────────────────────────────────────────────────────────────────

def extract_wisdom(item: ScoredItem) -> str:
    """Distill item into a Markdown wisdom block.

    Strips all pleasantries and abstract noise.
    Extracts ONLY:
        1. First-Principle constraints
        2. Algorithmic topology
        3. Counter-intuitive insights
    """
    category = _CM_CATEGORIES[item.item.citations % _N_CAT]
    track = classify_track(item)
    track_label = "Heavy-Tail Capital" if track == "A" else "Urgent Metabolic Cure"

    return f"""# {item.item.title}

**Track**: {track} — {track_label}
**Score**: {item.score:.4f} | R={item.R:.3f} N={item.N:.3f} E={item.E:.3f} C={item.C:.3f} T={item.T:.3f} L={item.L:.3f}
**Source**: {item.item.source_type.upper()} / {item.item.domain}
**Distilled**: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

---

## First-Principle Constraints

- Constraint target: **{category}** (ConstraintMatrix row {item.item.citations % _N_CAT})
- Transferability ceiling: T={item.T:.3f} — {'directly executable' if item.T >= 0.8 else 'requires abstraction layer'}
- Evidence depth: E={item.E:.3f} — {'peer-reviewed / citation-dense' if item.E >= 0.5 else 'early signal, low validation'}
- Leverage ratio: L={item.L:.3f} — {'high compression, dense insight' if item.L >= 0.6 else 'moderate density'}

## Algorithmic Topology

Domain: `{item.item.domain}` | Keywords matched: {item.item.keyword_overlap}/{len(_AGI_FOCUS_KEYWORDS)}
Impact vector: citations={item.item.citations}, forks={item.item.forks}, age={item.item.days_since_published}d

Raw abstract signal:
> {item.item.abstract}

## Counter-Intuitive Insights

- Score={item.score:.4f} places this in the top-5% heavy tail — the organism has never encountered this topology endogenously.
- Perturbation target `{category}`: injecting alien gradient here forces resolution of a paradox incompatible with the current ConstraintMatrix.
- {'GitHub implementation exists — skip theory, inject topology directly.' if item.item.source_type == 'github' else 'ArXiv theory paper — extract the proof skeleton, not the experiment narrative.'}

## Gödelian Injection

Perturbation vector queued in `{'candidate_pool/goedel_pending/' if track == 'A' else 'candidate_pool/immediate_applicable/'}`.
Next lineage fission event will resolve this alien constraint.
"""


def derive_perturbation_vector(item: ScoredItem) -> List[float]:
    """Derive an 8-element perturbation vector from a scored item."""
    return [
        0.15 * (item.R - 0.5) * 2.0,   # base_weight
        0.05 * item.N,                   # momentum
        -0.01 * item.E,                  # decay_rate
        -0.05 * item.C,                  # min_bound
        0.10 * item.T,                   # max_bound
        0.0,                             # gradient_accumulator (reserved)
        0.0,                             # squared_grad_acc (reserved)
        0.0,                             # update_count (counter)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Feed Simulation
# ─────────────────────────────────────────────────────────────────────────────

def _item_id(title: str, ts: float) -> str:
    return hashlib.sha256(f"{title}:{ts}".encode()).hexdigest()[:12]


def simulate_feed_batch(
    n: int = 100,
    seed: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> List[FeedItem]:
    """Generate n synthetic feed items (ArXiv papers + GitHub repos)."""
    if rng is None:
        rng = random.Random(seed)
    ts = time.time()
    items: List[FeedItem] = []
    for i in range(n):
        source_type = rng.choice(["arxiv", "arxiv", "github"])
        domain = rng.choice(_SOURCE_DOMAINS)
        k_count = rng.randint(0, min(5, len(_AGI_FOCUS_KEYWORDS)))
        keywords = rng.sample(_AGI_FOCUS_KEYWORDS, k_count)
        title = (
            f"[{domain}] {'On ' if source_type == 'arxiv' else 'Impl: '}"
            f"{' & '.join(keywords[:2]) if keywords else 'Deep Learning Study'}"
        )
        abstract = (
            f"We {'present' if source_type == 'arxiv' else 'implement'} a novel approach to "
            f"{' and '.join(keywords) if keywords else 'neural network optimization'}. "
            f"Experiments demonstrate significant improvements. "
            f"The method is validated on standard benchmarks with "
            f"{'p<0.01 significance' if rng.random() > 0.5 else 'ablation studies'}."
        )
        citations = int(rng.expovariate(1 / 30))
        forks = int(rng.expovariate(1 / 10)) if source_type == "github" else 0
        days = rng.randint(1, 730)
        items.append(FeedItem(
            item_id=_item_id(title, ts + i),
            title=title,
            abstract=abstract,
            source_type=source_type,
            domain=domain,
            citations=citations,
            forks=forks,
            days_since_published=days,
            keyword_overlap=k_count,
        ))
    return items


# ─────────────────────────────────────────────────────────────────────────────
# IPC Writers
# ─────────────────────────────────────────────────────────────────────────────

def _atomic_write(path: str, content: str) -> None:
    """Write string content atomically using tmp→rename."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.rename(tmp_path, path)


def _atomic_write_json(path: str, data: dict) -> None:
    """Write JSON atomically using tmp→rename."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.rename(tmp_path, path)


def write_goedel_pending(constraint: GoedelConstraint, base_dir: str = _GOEDEL_PENDING_PATH) -> str:
    """Write Gödelian constraint to candidate_pool/goedel_pending/. Returns path."""
    os.makedirs(base_dir, exist_ok=True)
    filename = f"{constraint.timestamp:.0f}_{constraint.axiom_name[:24].replace(' ', '_')}.json"
    path = os.path.join(base_dir, filename)
    _atomic_write_json(path, constraint.to_dict())
    return path


def write_wiki_inbox(item: ScoredItem, ts: float) -> str:
    """Track A: Write distilled .md to /Volumes/MYWORK/Chaos/Aevum_wiki/raw/inbox/."""
    os.makedirs(_WIKI_INBOX_PATH, exist_ok=True)
    filename = f"{ts:.0f}_{item.item.item_id}.md"
    path = os.path.join(_WIKI_INBOX_PATH, filename)
    _atomic_write(path, extract_wisdom(item))
    return path


def write_immediate_applicable(
    item: ScoredItem, constraint: GoedelConstraint, ts: float
) -> Tuple[str, str]:
    """Track B: Write both .md + .json to candidate_pool/immediate_applicable/."""
    os.makedirs(_IMMEDIATE_APPLICABLE_PATH, exist_ok=True)
    ts_str = f"{ts:.0f}"
    md_path = os.path.join(_IMMEDIATE_APPLICABLE_PATH, f"{ts_str}_{item.item.item_id}.md")
    json_path = os.path.join(
        _IMMEDIATE_APPLICABLE_PATH,
        f"{ts_str}_{constraint.axiom_name[:24].replace(' ', '_')}.json",
    )
    _atomic_write(md_path, extract_wisdom(item))
    _atomic_write_json(json_path, constraint.to_dict())
    return md_path, json_path


# ─────────────────────────────────────────────────────────────────────────────
# Distillation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def distill_item(item: ScoredItem, ts: float) -> dict:
    """Full distillation pipeline for a single top-5% item.

    Returns a dict with keys: track, goedel_path, md_path, [json_path].
    """
    track = classify_track(item)
    perturbation = derive_perturbation_vector(item)
    category_idx = item.item.citations % _N_CAT
    axiom_name = (
        f"{_CM_CATEGORIES[category_idx]}::{item.item.domain.replace('.', '_')}"
        f"_{item.item.item_id[:8]}"
    )
    constraint = GoedelConstraint(
        axiom_name=axiom_name,
        target_category=category_idx,
        perturbation_vector=perturbation,
        source_score=item.score,
        timestamp=ts,
        source_type=item.item.source_type,
        title=item.item.title,
        abstract=item.item.abstract,
        track=track,
    )

    if track == "A":
        goedel_path = write_goedel_pending(constraint)
        md_path = write_wiki_inbox(item, ts)
        print(f"[Track A: Heavy-Tail] score={item.score:.4f} '{item.item.title[:48]}' "
              f"→ wiki/inbox + goedel_pending")
        return {"track": "A", "goedel_path": goedel_path, "md_path": md_path}
    else:
        md_path, json_path = write_immediate_applicable(item, constraint, ts)
        print(f"[Track B: Urgent Cure] score={item.score:.4f} R={item.R:.3f} "
              f"'{item.item.title[:44]}' → immediate_applicable")
        return {"track": "B", "md_path": md_path, "json_path": json_path}


# ─────────────────────────────────────────────────────────────────────────────
# Daemon
# ─────────────────────────────────────────────────────────────────────────────

class ExtRawIngestor:
    """Background daemon: ingest → score → top-5% → dual-track distillation.

    Thermodynamic clock: wakes every 12 hours (43 200 s).

    Usage:
        ingestor = ExtRawIngestor()
        ingestor.run_forever()   # blocking — run in a background process

    Single-shot (tests):
        results = ingestor.run_one_cycle(seed=42)
    """

    def __init__(
        self,
        batch_size: int = 100,
        poll_interval_s: float = _CLOCK_INTERVAL_S,
        verbose: bool = True,
    ) -> None:
        self.batch_size = batch_size
        self.poll_interval_s = poll_interval_s
        self.verbose = verbose
        self._cycle_count: int = 0

    def run_one_cycle(
        self,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
    ) -> List[dict]:
        """Execute one ingestion cycle. Returns list of distillation result dicts."""
        ts = time.time()
        raw_items = simulate_feed_batch(n=self.batch_size, seed=seed, rng=rng)
        scored = [score_item(it) for it in raw_items]
        elite = filter_top_percentile(scored, percentile=_TOP_PERCENTILE)

        outputs: List[dict] = []
        for item in elite:
            result = distill_item(item, ts)
            outputs.append(result)

        self._cycle_count += 1
        track_a = sum(1 for o in outputs if o["track"] == "A")
        track_b = sum(1 for o in outputs if o["track"] == "B")
        if self.verbose:
            print(
                f"[ext_raw] Cycle {self._cycle_count}: "
                f"{len(raw_items)} items → {len(elite)} elite "
                f"[Track A={track_a} Track B={track_b}]"
            )
        return outputs

    def run_forever(self) -> None:
        """Blocking daemon loop. Thermodynamic clock: sleeps 12 hours between cycles."""
        print(
            f"[ext_raw] Daemon started. batch={self.batch_size} "
            f"clock={self.poll_interval_s}s (12h thermodynamic cycle)"
        )
        while True:
            try:
                self.run_one_cycle()
            except Exception as exc:
                print(f"[ext_raw] Cycle error (non-fatal): {exc}")
            time.sleep(self.poll_interval_s)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_score(
    R: float, N: float, E: float, C: float, T: float, L: float
) -> float:
    """Pure scoring formula. Single source of truth — delegates to _score_formula."""
    return _score_formula(R, N, E, C, T, L)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ext Raw Ingestor Daemon (TICK 38.1-38.3)")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--interval", type=float, default=_CLOCK_INTERVAL_S)
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    ingestor = ExtRawIngestor(
        batch_size=args.batch_size,
        poll_interval_s=args.interval,
    )
    if args.once:
        results = ingestor.run_one_cycle(seed=args.seed)
        track_a = sum(1 for r in results if r["track"] == "A")
        track_b = sum(1 for r in results if r["track"] == "B")
        print(f"One-shot complete: {len(results)} items distilled "
              f"[Track A={track_a} Track B={track_b}].")
    else:
        ingestor.run_forever()
