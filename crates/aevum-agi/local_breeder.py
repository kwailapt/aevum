#!/usr/bin/env python3
"""local_breeder.py -- Fast Micro-Evolution Engine.

TICK 6.1: Hybrid Mutation -- algorithmic GA during the Fast Loop.

During the Evaluator's Fast Loop, instead of purely blind random mutation,
this module applies rapid GA operations: crossover between elite parents,
minor parameter tweaks, and structural recombination.

Performance contract: breed() MUST execute in <100ms.

Design principles:
  - Pure Python + torch (no LLM calls).
  - Operates on population elites from population/elites.json.
  - Returns a candidate dict compatible with AtomicCore._vary() output.
  - Tracks stagnation: if local breeding fails to improve for N cycles,
    signals the Mutator Daemon to fire the 35B LLM.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

# Reuse core constants (no torch dependency at module level)
try:
    from atomic_core import (
        ICHING_COUNT, BIOGEO_COUNT, LOGIC_COUNT, HNODE_COUNT,
        StateCodec, HyperRewriter,
    )
except ImportError:
    # Fallback constants if atomic_core can't be imported at load time
    ICHING_COUNT = 64
    BIOGEO_COUNT = 16
    LOGIC_COUNT = 8
    HNODE_COUNT = 128
    StateCodec = None
    HyperRewriter = None


# ═══════════════════════════════════════════════════════════════
# BREEDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Stagnation: if no improvement in this many breed cycles, signal LLM
BREEDER_STAGNATION_LIMIT: int = 30

# Crossover probability for each gene
CROSSOVER_RATE: float = 0.5

# Small mutation amplitude for parameter tweaks
PARAM_MUTATION_SIGMA: float = 0.05

# Edge recombination: probability of swapping edge subsets
EDGE_SWAP_RATE: float = 0.3

# Maximum edges to prevent combinatorial explosion
MAX_EDGES: int = 48


# ═══════════════════════════════════════════════════════════════
# BREEDER STATE (per-session, not persisted)
# ═══════════════════════════════════════════════════════════════

class BreederState:
    """Tracks local breeder performance across cycles."""

    def __init__(self):
        self.cycles: int = 0
        self.best_epi: float = 0.0
        self.stagnation_counter: int = 0
        self.last_improvement_time: float = time.time()
        self.total_breed_time_ms: float = 0.0

    def update(self, epi: float) -> None:
        self.cycles += 1
        if epi > self.best_epi:
            self.best_epi = epi
            self.stagnation_counter = 0
            self.last_improvement_time = time.time()
        else:
            self.stagnation_counter += 1

    @property
    def is_stagnant(self) -> bool:
        return self.stagnation_counter >= BREEDER_STAGNATION_LIMIT

    @property
    def improvement_velocity(self) -> float:
        """Improvement per second since last reset."""
        elapsed = time.time() - self.last_improvement_time
        if elapsed < 0.01:
            return 0.0
        return self.best_epi / max(elapsed, 0.01)


# Global singleton -- lives for the evaluator daemon's lifetime
_state = BreederState()


def get_breeder_state() -> BreederState:
    return _state


def reset_breeder_state() -> None:
    global _state
    _state = BreederState()


# ═══════════════════════════════════════════════════════════════
# SELECTION: Tournament Selection from Population
# ═══════════════════════════════════════════════════════════════

def _tournament_select(
    population: Dict[str, Any],
    k: int = 3,
) -> Dict[str, Any]:
    """Tournament selection: pick k random elites, return the fittest."""
    if not isinstance(population, dict) or not population:
        return {}
    keys = list(population.keys())
    tournament = random.sample(keys, min(k, len(keys)))
    best_key = max(tournament, key=lambda k: population[k].get("epi", 0.0))
    return population[best_key]


# ═══════════════════════════════════════════════════════════════
# CROSSOVER: Recombine Two Parents
# ═══════════════════════════════════════════════════════════════

def _crossover_iching(p1: List[int], p2: List[int]) -> List[int]:
    """Uniform crossover on I-Ching indices."""
    length = max(len(p1), len(p2))
    p1 = p1 + [random.randint(0, ICHING_COUNT - 1)] * (length - len(p1))
    p2 = p2 + [random.randint(0, ICHING_COUNT - 1)] * (length - len(p2))
    return [
        p1[i] if random.random() > CROSSOVER_RATE else p2[i]
        for i in range(length)
    ][:16]


def _crossover_biogeo(p1: List[int], p2: List[int]) -> List[int]:
    """Crossover BioGeometry indices."""
    length = max(len(p1), len(p2), 4)
    p1 = (p1 + [random.randint(0, BIOGEO_COUNT - 1)] * length)[:length]
    p2 = (p2 + [random.randint(0, BIOGEO_COUNT - 1)] * length)[:length]
    return [
        p1[i] if random.random() > CROSSOVER_RATE else p2[i]
        for i in range(length)
    ][:4]


def _crossover_logic(p1: List[int], p2: List[int]) -> List[int]:
    """Crossover logic gate indices."""
    length = max(len(p1), len(p2), 4)
    p1 = (p1 + [random.randint(0, LOGIC_COUNT - 1)] * length)[:length]
    p2 = (p2 + [random.randint(0, LOGIC_COUNT - 1)] * length)[:length]
    return [
        p1[i] if random.random() > CROSSOVER_RATE else p2[i]
        for i in range(length)
    ][:4]


def _crossover_edges(
    e1: List[Tuple[int, ...]],
    e2: List[Tuple[int, ...]],
) -> Tuple[List[int], List[Tuple[int, ...]]]:
    """Edge recombination: take subset from each parent, merge, deduplicate.

    Returns (nodes, edges).
    """
    # Split point crossover
    if not e1 and not e2:
        if HyperRewriter is not None:
            nodes, edges = HyperRewriter.seed(16, 8)
            return nodes, edges
        return list(range(16)), [(0, 1, 2)]

    # Take random subset from each parent
    split1 = max(1, len(e1) // 2) if e1 else 0
    split2 = max(1, len(e2) // 2) if e2 else 0

    from_p1 = random.sample(e1, min(split1, len(e1))) if e1 else []
    from_p2 = random.sample(e2, min(split2, len(e2))) if e2 else []

    merged = list(set(tuple(sorted(e)) for e in from_p1 + from_p2))

    # Cap edges
    if len(merged) > MAX_EDGES:
        merged = merged[:MAX_EDGES]

    if not merged:
        if HyperRewriter is not None:
            nodes, edges = HyperRewriter.seed(16, 8)
            return nodes, edges
        return list(range(16)), [(0, 1, 2)]

    nodes = sorted(set(n for e in merged for n in e))
    return nodes, merged


# ═══════════════════════════════════════════════════════════════
# MUTATION: Small Parameter Perturbations
# ═══════════════════════════════════════════════════════════════

def _mutate_iching(indices: List[int], rate: float = 0.1) -> List[int]:
    """Point mutation on I-Ching indices."""
    return [
        random.randint(0, ICHING_COUNT - 1) if random.random() < rate else i
        for i in indices
    ]


def _mutate_biogeo(indices: List[int], rate: float = 0.1) -> List[int]:
    """Point mutation on BioGeo indices."""
    return [
        random.randint(0, BIOGEO_COUNT - 1) if random.random() < rate else i
        for i in indices
    ]


def _mutate_logic(indices: List[int], rate: float = 0.1) -> List[int]:
    """Point mutation on logic gate indices."""
    return [
        random.randint(0, LOGIC_COUNT - 1) if random.random() < rate else i
        for i in indices
    ]


def _mutate_edges(
    nodes: List[int],
    edges: List[Tuple[int, ...]],
    rate: float = 0.15,
) -> Tuple[List[int], List[Tuple[int, ...]]]:
    """Minor edge rewrites -- lighter than HyperRewriter for speed."""
    if not edges:
        return nodes, edges

    out: List[Tuple[int, ...]] = []
    for e in edges:
        if random.random() < rate and len(e) >= 2:
            # Swap one node in the edge with a nearby node
            idx = random.randint(0, len(e) - 1)
            new_node = e[idx] + random.choice([-1, 1])
            new_node = max(0, new_node)
            e_list = list(e)
            e_list[idx] = new_node
            out.append(tuple(e_list))
            if new_node not in nodes:
                nodes.append(new_node)
        else:
            out.append(e)

    # Occasional edge addition
    if random.random() < 0.1 and len(out) < MAX_EDGES and len(nodes) >= 2:
        new_edge = tuple(random.sample(nodes, min(3, len(nodes))))
        out.append(new_edge)

    return sorted(set(nodes)), list(set(tuple(sorted(e)) for e in out))


# ═══════════════════════════════════════════════════════════════
# SINGLE-PARENT MUTATION FALLBACK (TICK 7.0.1)
# ═══════════════════════════════════════════════════════════════

def _mutate_single_parent(
    population: Dict[str, Any],
    t_start: float,
) -> Optional[Dict[str, Any]]:
    """Apply point-mutations to a single parent when crossover is impossible.

    Used when population has exactly 1 entry -- cannot do tournament
    selection or crossover, but can still apply parameter tweaks,
    index mutations, and minor edge rewrites.
    """
    # Get the sole parent
    key = next(iter(population))
    parent = population[key]
    if not isinstance(parent, dict):
        return None

    # Adaptive mutation rate: higher when stagnant
    mr = 0.15 + (0.25 * min(_state.stagnation_counter / BREEDER_STAGNATION_LIMIT, 1.0))

    child_iching = _mutate_iching(
        parent.get("ic_idx", [random.randint(0, ICHING_COUNT - 1) for _ in range(16)]),
        rate=mr,
    )
    child_biogeo = _mutate_biogeo(
        parent.get("bg_idx", [random.randint(0, BIOGEO_COUNT - 1) for _ in range(4)]),
        rate=mr,
    )
    child_logic = _mutate_logic(
        parent.get("lg_idx", [random.randint(0, LOGIC_COUNT - 1) for _ in range(4)]),
        rate=mr,
    )

    nodes = parent.get("nodes", list(range(16)))
    edges = [tuple(e) for e in parent.get("edges", [(0, 1, 2)])]
    child_nodes, child_edges = _mutate_edges(nodes, edges, rate=mr)

    # Safety: ensure non-empty
    if not child_edges:
        if HyperRewriter is not None:
            child_nodes, child_edges_t = HyperRewriter.seed(16, 8)
            child_edges = [list(e) for e in child_edges_t]
        else:
            child_nodes = list(range(16))
            child_edges = [(0, 1, 2), (3, 4, 5)]
    if not child_iching:
        child_iching = [random.randint(0, ICHING_COUNT - 1) for _ in range(16)]
    if not child_biogeo:
        child_biogeo = [random.randint(0, BIOGEO_COUNT - 1) for _ in range(4)]
    if not child_logic:
        child_logic = [random.randint(0, LOGIC_COUNT - 1) for _ in range(4)]
    if len(child_edges) > MAX_EDGES:
        child_edges = child_edges[:MAX_EDGES]

    sym_str = ""
    if StateCodec is not None:
        sym_str = StateCodec.format_symbols(child_iching, child_biogeo, child_logic)

    elapsed_ms = (time.time() - t_start) * 1000
    _state.total_breed_time_ms += elapsed_ms

    return {
        "nodes": child_nodes,
        "edges": child_edges,
        "ic_idx": child_iching,
        "bg_idx": child_biogeo,
        "lg_idx": child_logic,
        "sym_str": sym_str,
        "_breed_ms": round(elapsed_ms, 2),
        "_parents": "single_mutate",
    }


# ═══════════════════════════════════════════════════════════════
# BREED: The Main Entry Point
# ═══════════════════════════════════════════════════════════════

def breed(
    population: Dict[str, Any],
    iching_rules: Optional[Dict] = None,
    biogeo_cfg: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """Breed a new candidate from the population via GA crossover + mutation.

    Performance target: <100ms.

    TICK 7.0.1: If population is not a dict or has < 2 entries, falls back
    to single-parent point-mutation instead of crashing.

    Args:
        population: Elite population dict from population/elites.json.
        iching_rules: Optional I-Ching rule weights for biased sampling.
        biogeo_cfg: Optional BioGeometry configuration.

    Returns:
        Candidate dict compatible with AtomicCore._vary() output,
        or None if population is empty or invalid.
    """
    t_start = time.time()

    # TICK 7.0.1: Type guard -- population MUST be a dict
    if not isinstance(population, dict) or not population:
        return None

    # Single-parent fallback: mutate-only (no crossover possible)
    if len(population) < 2:
        return _mutate_single_parent(population, t_start)

    # ── Select two parents via tournament ──
    parent_a = _tournament_select(population, k=3)
    parent_b = _tournament_select(population, k=3)

    # Retry if same parent selected
    for _ in range(3):
        if parent_a is not parent_b:
            break
        parent_b = _tournament_select(population, k=3)

    # ── Crossover ──
    ic_a = parent_a.get("ic_idx", list(range(16)))
    ic_b = parent_b.get("ic_idx", list(range(16)))
    child_iching = _crossover_iching(ic_a, ic_b)

    bg_a = parent_a.get("bg_idx", list(range(4)))
    bg_b = parent_b.get("bg_idx", list(range(4)))
    child_biogeo = _crossover_biogeo(bg_a, bg_b)

    lg_a = parent_a.get("lg_idx", list(range(4)))
    lg_b = parent_b.get("lg_idx", list(range(4)))
    child_logic = _crossover_logic(lg_a, lg_b)

    # Edges: recombination from both parents
    edges_a = [tuple(e) for e in parent_a.get("edges", [])]
    edges_b = [tuple(e) for e in parent_b.get("edges", [])]
    child_nodes, child_edges = _crossover_edges(edges_a, edges_b)

    # ── Mutation ──
    # Adaptive mutation rate: higher when stagnant
    mr = 0.1 + (0.2 * min(_state.stagnation_counter / BREEDER_STAGNATION_LIMIT, 1.0))

    child_iching = _mutate_iching(child_iching, rate=mr)
    child_biogeo = _mutate_biogeo(child_biogeo, rate=mr)
    child_logic = _mutate_logic(child_logic, rate=mr)
    child_nodes, child_edges = _mutate_edges(child_nodes, child_edges, rate=mr)

    # ── Apply HyperRewriter rewrite if available (lightweight) ──
    if HyperRewriter is not None and random.random() < 0.3:
        h0 = child_iching[0] if child_iching else 0
        rewrite_rate = 0.15
        if iching_rules:
            rewrite_rate = iching_rules.get(str(h0), {}).get("mr", 0.25)
            rewrite_rate = max(0.1, rewrite_rate * 0.5)  # lighter for speed
        child_nodes, child_edges = HyperRewriter.rewrite(
            child_nodes, child_edges, rate=rewrite_rate,
        )

    # ── Safety: ensure non-empty ──
    if not child_edges:
        if HyperRewriter is not None:
            child_nodes, child_edges_t = HyperRewriter.seed(16, 8)
            child_edges = [list(e) for e in child_edges_t]
        else:
            child_nodes = list(range(16))
            child_edges = [(0, 1, 2), (3, 4, 5)]

    if not child_iching:
        child_iching = [random.randint(0, ICHING_COUNT - 1) for _ in range(16)]
    if not child_biogeo:
        child_biogeo = [random.randint(0, BIOGEO_COUNT - 1) for _ in range(4)]
    if not child_logic:
        child_logic = [random.randint(0, LOGIC_COUNT - 1) for _ in range(4)]

    # Cap edges
    if len(child_edges) > MAX_EDGES:
        child_edges = child_edges[:MAX_EDGES]

    # ── Format symbols ──
    sym_str = ""
    if StateCodec is not None:
        sym_str = StateCodec.format_symbols(child_iching, child_biogeo, child_logic)

    elapsed_ms = (time.time() - t_start) * 1000
    _state.total_breed_time_ms += elapsed_ms

    return {
        "nodes": child_nodes,
        "edges": child_edges,
        "ic_idx": child_iching,
        "bg_idx": child_biogeo,
        "lg_idx": child_logic,
        "sym_str": sym_str,
        "_breed_ms": round(elapsed_ms, 2),
        "_parents": "crossover",
    }


def should_escalate_to_llm() -> bool:
    """Check if the local breeder has stagnated and the 35B LLM should fire.

    The Evaluator calls this to decide whether to write a stagnation
    signal to the filesystem, which the Mutator picks up.
    """
    return _state.is_stagnant
