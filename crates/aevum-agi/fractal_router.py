# fractal_router.py — Kronecker Fractal Router (Phase P0 / P0.1 / P1)
# 64-base hexagram-aligned, O(1) bitwise addressing, depth hard-locked d ≤ 2.
# Completely decoupled from legacy routing logic in atomic_core.py.
#
# P0.1: ASTHasher rewritten — DFS structural-only, ignores leaf semantics,
#        FNV-1a hash with end-fold (no mid-step masking).
# P1:   MitoticBatchBuffer — accumulates per-slot until batch ≥ 64 for
#        MPS-aligned bulk kernel dispatch.

import ast
import hashlib
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────────
FRACTAL_BASE: int = 64    # 2^6 — hexagram-aligned (I Ching hexagram count)
BITS:         int = 6     # bits per Kronecker level
MASK:         int = 0x3F  # 0b0011_1111  — 6-bit mask
MAX_DEPTH:    int = 3     # Phase P1.5: d ≤ 3 with dynamic expansion
CAPACITY:     int = 128   # Thermal threshold: max ASTs per slot before fission

HEXAGRAM_CHARS: List[str] = [chr(0x4DC0 + i) for i in range(64)]

# ── Node bucket table ──────────────────────────────────────────────────────────
# Deterministic assignment: Python AST node type name → [0, 63].
# Ordered intentionally so structurally similar nodes cluster in the same
# hexagram region.  Unknown types fall back to sha256 mod 64.
_NODE_TYPES: List[str] = [
    # Control flow  (0–9)
    "If", "For", "While", "With", "Try", "ExceptHandler",
    "Break", "Continue", "Return", "Yield",
    # Functions / classes  (10–19)
    "FunctionDef", "AsyncFunctionDef", "ClassDef", "Lambda",
    "arguments", "arg", "Call", "Attribute", "Subscript", "AsyncFor",
    # Assignments  (20–29)
    "Assign", "AugAssign", "AnnAssign", "Delete", "Global", "Nonlocal",
    "NamedExpr", "Starred", "Name", "Constant",
    # Expressions  (30–39)
    "BinOp", "UnaryOp", "BoolOp", "Compare", "IfExp",
    "ListComp", "SetComp", "DictComp", "GeneratorExp", "Await",
    # Data structures  (40–49)
    "List", "Tuple", "Set", "Dict", "Slice",
    "Index", "ExtSlice", "FormattedValue", "JoinedStr", "Bytes",
    # Imports  (50–55)
    "Import", "ImportFrom", "alias", "Module", "Interactive", "Expression",
    # Operators  (56–63)
    "Add", "Sub", "Mult", "Div", "Mod", "Pow", "BitXor", "MatMult",
]
_BUCKET: Dict[str, int] = {name: i % FRACTAL_BASE for i, name in enumerate(_NODE_TYPES)}


def _name_bucket(name: str) -> int:
    if name in _BUCKET:
        return _BUCKET[name]
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) & MASK


def _node_bucket(node: ast.AST) -> int:
    """Map an AST node to its [0, 63] structural bucket."""
    return _name_bucket(type(node).__name__)


# ── FNV-1a (32-bit) ────────────────────────────────────────────────────────────
# Accumulates in 32 bits; folds to 6 bits only at the end.
# Much better avalanche than poly_fold with mid-step 6-bit masking.

_FNV_PRIME:  int = 0x01000193   # 16777619
_FNV_OFFSET: int = 0x811C9DC5   # 2166136261


def _fnv32(values: List[int], seed: int = _FNV_OFFSET) -> int:
    """FNV-1a 32-bit hash of an integer sequence, folded to 6 bits at end."""
    h = seed & 0xFFFF_FFFF
    for v in values:
        h ^= v & 0xFF
        h = (h * _FNV_PRIME) & 0xFFFF_FFFF
    # XOR-fold 32 bits → 6 bits across five non-overlapping 6-bit windows
    # (preserves entropy far better than a single low-bit mask)
    return (h ^ (h >> 6) ^ (h >> 12) ^ (h >> 18) ^ (h >> 24)) & MASK


# ── Structural node filter (P0.1) ──────────────────────────────────────────────
# Leaf-semantic nodes carry variable names / literal values — thermodynamic
# noise that increases collision rate without adding topological information.
# Only structural / control-flow nodes are hashed.

_IGNORE: frozenset = frozenset({
    "Name", "Constant", "arg", "alias",
    "Store", "Load", "Del",          # context singletons
    "And", "Or",                     # BoolOp operators (not structure)
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
})

_STRUCTURAL: frozenset = frozenset({
    # control flow
    "If", "For", "While", "With", "Try", "ExceptHandler",
    "Break", "Continue", "Return", "Yield", "YieldFrom", "Raise",
    # functions / classes
    "FunctionDef", "AsyncFunctionDef", "AsyncFor", "AsyncWith",
    "ClassDef", "Lambda",
    # assignments
    "Assign", "AugAssign", "AnnAssign", "NamedExpr",
    # expressions
    "BinOp", "UnaryOp", "BoolOp", "Compare", "IfExp", "Call",
    "ListComp", "SetComp", "DictComp", "GeneratorExp", "Await",
    # data structures
    "List", "Tuple", "Set", "Dict", "Subscript", "Slice",
    # imports
    "Import", "ImportFrom",
})


# ── FractalAddress ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FractalAddress:
    """Immutable d-level address in the 64^d Kronecker space.

    coords[0] = macro level (hexagram ䷀–䷿)
    coords[1] = micro level  (sub-hexagram)

    flat property gives O(1) integer index via bitwise shift:
        d=1 → 6-bit  [0, 63]
        d=2 → 12-bit [0, 4095]
    """
    coords: Tuple[int, ...]

    def __post_init__(self) -> None:
        if not (1 <= len(self.coords) <= MAX_DEPTH):
            raise ValueError(
                f"depth {len(self.coords)} violates constraint d ≤ {MAX_DEPTH}"
            )
        for i, c in enumerate(self.coords):
            if not (0 <= c < FRACTAL_BASE):
                raise ValueError(f"coords[{i}]={c} out of range [0, {FRACTAL_BASE})")

    @property
    def depth(self) -> int:
        return len(self.coords)

    @property
    def flat(self) -> int:
        """O(1) bitwise flat index.  No branches, no loops unrolled by depth."""
        idx = 0
        for c in self.coords:
            idx = (idx << BITS) | c   # shift left 6, OR in next 6-bit coord
        return idx

    @staticmethod
    def from_flat(flat: int, depth: int) -> "FractalAddress":
        """Reverse of flat: extract coords from a packed integer."""
        if not (1 <= depth <= MAX_DEPTH):
            raise ValueError(f"depth {depth} violates d ≤ {MAX_DEPTH}")
        coords: List[int] = []
        for _ in range(depth):
            coords.append(flat & MASK)
            flat >>= BITS
        return FractalAddress(tuple(reversed(coords)))

    def __repr__(self) -> str:
        hx = "".join(HEXAGRAM_CHARS[c] for c in self.coords)
        return f"FA[{hx} d={self.depth} flat={self.flat:#05x}]"


# ── ASTHasher (P0.1 rewrite) ──────────────────────────────────────────────────

class ASTHasher:
    """Stateless: converts ast.AST → FractalAddress.

    P0.1 design — pure topological skeleton:
    · DFS traversal; leaf semantics (Name, Constant, arg, alias) are
      silently discarded — they are thermodynamic noise, not topology.
    · Each structural node contributes (bucket * 67 + depth) & 0xFF to
      the hash stream, encoding both node type and relative position.
    · FNV-1a accumulates in 32 bits; a 5-window XOR-fold collapses to 6
      bits only at the very end — no mid-step entropy destruction.

    Two-level split:
        h1 (macro, coords[0]): structural nodes at DFS depth ≤ 3
            Captures top-level control-flow skeleton.
        h2 (micro, coords[1]): structural nodes at DFS depth > 3
            Captures sub-expression nesting patterns.
            Falls back to full-tree mix if the tree is shallow.
    """

    @staticmethod
    def _dfs_structural(tree: ast.AST) -> Iterator[Tuple[int, int]]:
        """DFS, yielding (bucket, depth) for structural nodes only.

        Ignores leaf-semantic nodes (_IGNORE set) but continues DFS through
        their children so deeper structural nodes are still discovered.
        """
        stack = [(tree, 0)]
        while stack:
            node, depth = stack.pop()
            name = type(node).__name__
            if name not in _IGNORE:
                yield _name_bucket(name), depth
            # Always recurse — a Name child may have Call grandchildren
            for child in reversed(list(ast.iter_child_nodes(node))):
                stack.append((child, depth + 1))

    def hash(self, tree: ast.AST, depth: int = MAX_DEPTH) -> FractalAddress:
        """Hash an ast.AST into a FractalAddress of the requested depth."""
        if not (1 <= depth <= MAX_DEPTH):
            raise ValueError(f"depth {depth} violates d ≤ {MAX_DEPTH}")

        macro_vals: List[int] = []
        micro_vals: List[int] = []
        deep_vals: List[int] = []

        for bucket, d in self._dfs_structural(tree):
            # Encode type + position into a single byte
            encoded = (bucket * 67 + d) & 0xFF
            if d <= 3:
                macro_vals.append(encoded)
            elif d <= 6:
                micro_vals.append(encoded)
            else:
                deep_vals.append(encoded)

        h1 = _fnv32(macro_vals, seed=_FNV_OFFSET)

        if depth == 1:
            return FractalAddress((h1,))

        if micro_vals:
            h2 = _fnv32(micro_vals, seed=_FNV_OFFSET ^ 0xCAFE_BABE)
        else:
            # Shallow tree: re-hash macro with a different seed for h2
            h2 = _fnv32(macro_vals, seed=_FNV_OFFSET ^ 0xDEAD_BEEF)

        if depth == 2:
            return FractalAddress((h1, h2))

        if deep_vals:
            h3 = _fnv32(deep_vals, seed=_FNV_OFFSET ^ 0xBADC0FFE)
        else:
            # Re-hash with different seed for h3
            h3 = _fnv32(macro_vals + micro_vals, seed=_FNV_OFFSET ^ 0xFEEDFACE)

        return FractalAddress((h1, h2, h3))

    def hash_source(self, source: str, depth: int = MAX_DEPTH) -> Optional[FractalAddress]:
        """Parse Python source and hash it.  Returns None on SyntaxError."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        return self.hash(tree, depth)


# ── RouterStats ────────────────────────────────────────────────────────────────

@dataclass
class RouterStats:
    """Routing distribution statistics for one KroneckerFractalRouter."""
    total_routed:     int
    active_slots:     int           # slots with at least one hit
    max_slots:        int           # FRACTAL_BASE ** depth, adjusted for fission
    coverage:         float         # active_slots / max_slots
    routing_variance: float         # CV²: σ²/μ² over all slots including expanded (0 = uniform)
    entropy_bits:     float         # Shannon entropy of routing distribution
    depth:            int
    isomorphism_ratio: float       # P2: ratio of slots with multi-domain condition
    fission_events:   int          # Number of slots that underwent fission
    verdict:          str          # Stability assessment: "FISSION STABILIZED" or other
    top5:             List[Tuple[int, int, int]] = field(default_factory=list)  # (flat_addr, hit_count, address_depth)

    def __str__(self) -> str:
        top = "  ".join(
            f"{FractalAddress.from_flat(a, d)}×{n}"
            for a, n, d in self.top5
        )
        return (
            f"RouterStats(\n"
            f"  depth={self.depth}  total={self.total_routed}  "
            f"active={self.active_slots}/{self.max_slots}  "
            f"coverage={self.coverage:.4f}\n"
            f"  fission_events={self.fission_events}  verdict='{self.verdict}'\n"
            f"  routing_variance(CV²)={self.routing_variance:.6f}  "
            f"entropy={self.entropy_bits:.4f} bits / {math.log2(self.max_slots):.2f} max\n"
            f"  top-5 slots: {top}\n"
            f")"
        )


# ── KroneckerFractalRouter ─────────────────────────────────────────────────────

class KroneckerFractalRouter:
    """64-base Kronecker Fractal Router with O(1) flat-address lookup and dynamic depth expansion.

    Routing table:  flat_addr (int) → hit_count (int)
    Address space:  FRACTAL_BASE^depth = 64^depth slots
                    d=1 → 64 slots
                    d=2 → 4096 slots
                    d=3 → 262,144 slots (Phase P1.5 addition)

    All arithmetic is integer bitwise; no floating point on the hot path.

    P1.5 Dynamic Depth Expansion: When a slot hits CAPACITY threshold,
    it triggers fission - creating a new depth-3 sub-space exclusively for that slot.
    """

    def __init__(self, depth: int = 2) -> None:
        if not (1 <= depth <= MAX_DEPTH):
            raise ValueError(f"depth {depth} violates constraint d ≤ {MAX_DEPTH}")
        self.depth: int = depth
        self.max_slots: int = FRACTAL_BASE ** depth
        self.routing_table: Dict[int, int] = {}
        self.total_routed: int = 0

        # Track which slots have triggered fission
        self.fission_slots: set = set()

        # Expanded routers for slots that have triggered fission (these will be depth 3)
        self.expanded_slot_routers: Dict[int, KroneckerFractalRouter] = {}

    def route(self, addr: FractalAddress) -> int:
        """Route an address with potential dynamic depth expansion.

        O(1): dict lookup + increment, with local expansion when needed.

        Returns the flat integer index of the slot.
        May trigger fission if a slot exceeds capacity.
        """
        # Determine if this address should go to an expanded router
        # For addresses with greater depth than our router, we check if the prefix matches a fissioned slot

        # Extract the flat address at this router's depth (for d=2 router, use first 2 coordinates)
        if addr.depth > self.depth:
            # This is a higher-depth address (e.g. d=3), check if its prefix has triggered fission
            prefix_coords = addr.coords[:self.depth]
            prefix_idx = 0
            for c in prefix_coords:
                prefix_idx = (prefix_idx << BITS) | c

            if prefix_idx in self.expanded_slot_routers:
                # Route to the expanded router for this specific slot
                expanded_router = self.expanded_slot_routers[prefix_idx]

                # Route the full address to the expanded router
                result = expanded_router.route(addr)

                # Also increment the original slot counter to reflect that items went to this slot
                self.routing_table[prefix_idx] = self.routing_table.get(prefix_idx, 0) + 1
                self.total_routed += 1
                return result

        # For addresses matching this router's depth, handle normally but check for fission
        if addr.depth != self.depth:
            raise ValueError(
                f"address depth {addr.depth} ≠ router depth {self.depth}"
            )

        flat = addr.flat                           # O(1) bitwise

        # Normal routing in main router
        hit_count = self.routing_table.get(flat, 0) + 1
        self.routing_table[flat] = hit_count
        self.total_routed += 1

        # Check for fission trigger
        if hit_count == CAPACITY and self.depth < MAX_DEPTH:  # Exactly at capacity threshold - first time triggering fission
            self._trigger_fission(flat)

        return flat

    def _trigger_fission(self, flat_addr: int) -> None:
        """Trigger fission for an overloaded slot, creating a depth-3 router for it."""
        if flat_addr not in self.fission_slots:
            # Create a new depth-3 router for this overloaded slot
            expanded_router = KroneckerFractalRouter(depth=3)

            # Store the expanded router
            self.expanded_slot_routers[flat_addr] = expanded_router
            self.fission_slots.add(flat_addr)
            print(f"  ⚡ Fission triggered for slot {flat_addr:#05x}: expanded to depth-3 sub-space")

    def variance(self) -> float:
        """Coefficient of variation squared (CV²) over the full address space.

        Includes the many zero-hit slots in the denominator so sparse routing
        (many unused slots) scores higher variance than dense uniform routing.
        CV² = 0 → perfect uniform.  CV² >> 1 → highly concentrated.
        """
        if self.total_routed == 0:
            return 0.0
        mu = self.total_routed / self.max_slots
        sq_sum = sum(
            (v - mu) ** 2 for v in self.routing_table.values()
        )
        # Remaining slots have hit count 0
        zero_slots = self.max_slots - len(self.routing_table)
        sq_sum += zero_slots * (mu ** 2)
        sigma2 = sq_sum / self.max_slots
        return sigma2 / max(mu ** 2, 1e-12)

    def entropy(self) -> float:
        """Shannon entropy of the routing distribution in bits."""
        if self.total_routed == 0:
            return 0.0
        h = 0.0
        for count in self.routing_table.values():
            if count > 0:
                p = count / self.total_routed
                h -= p * math.log2(p)
        return h

    def stats(self) -> RouterStats:
        # Collect all routing counts: original and from expanded routers
        all_routing_entries = []  # List of (flat_addr, hit_count, depth)

        # Add entries from main router
        for flat_addr, hit_count in self.routing_table.items():
            all_routing_entries.append((flat_addr, hit_count, self.depth))

        # Add entries from expanded routers with their correct depth
        for expanded_router in self.expanded_slot_routers.values():
            for flat_addr, hit_count in expanded_router.routing_table.items():
                all_routing_entries.append((flat_addr, hit_count, expanded_router.depth))

        # Calculate total routed (including from expanded routers)
        total_routed = sum(entry[1] for entry in all_routing_entries)

        # Calculate total active slots
        total_active_slots = len(all_routing_entries)

        # Calculate dynamic max slots based on fission events
        original_max_slots = FRACTAL_BASE ** self.depth
        fission_events = len(self.expanded_slot_routers)

        # When a slot undergoes fission, we lose 1 slot at original depth but gain FRACTAL_BASE slots at new depth
        # So net change: -1 + FRACTAL_BASE = +FRACTAL_BASE - 1
        max_slots = original_max_slots - fission_events + (fission_events * (FRACTAL_BASE ** 3 // FRACTAL_BASE ** 2))

        # For d=2 to d=3 fission: -1 original slot + 64 new slots = +63 per fission
        max_slots = original_max_slots - fission_events + (fission_events * FRACTAL_BASE)

        # Calculate variance across all slots
        if total_routed == 0:
            variance = 0.0
            entropy = 0.0
        else:
            mu = total_routed / max_slots
            sq_sum = sum((count - mu) ** 2 for _, count, _ in all_routing_entries)
            # Account for remaining zero-count slots
            zero_slots = max_slots - len(all_routing_entries)
            sq_sum += zero_slots * (mu ** 2)
            sigma2 = sq_sum / max_slots
            variance = sigma2 / max(mu ** 2, 1e-12)

            # Calculate Shannon entropy considering all slots
            entropy = 0.0
            for _, count, _ in all_routing_entries:
                if count > 0:
                    p = count / total_routed if total_routed > 0 else 0
                    if p > 0:  # Avoid log(0)
                        entropy -= p * math.log2(p)

        # Get top 5 slots by hit count
        top5 = sorted(all_routing_entries, key=lambda x: x[1], reverse=True)[:5]

        # Determine verdict based on fission activity
        if fission_events > 0:
            verdict = "FISSION STABILIZED"
        else:
            verdict = "NO FISSION REQUIRED"

        coverage = total_active_slots / max_slots if max_slots > 0 else 0.0

        # Calculate isomorphism ratio - this would be based on slots that have triggered multi-domain condition
        isomorphism_ratio = 0.0

        return RouterStats(
            total_routed=total_routed,
            active_slots=total_active_slots,
            max_slots=max_slots,
            coverage=coverage,
            routing_variance=variance,
            entropy_bits=entropy,
            depth=self.depth,
            isomorphism_ratio=isomorphism_ratio,
            fission_events=fission_events,
            verdict=verdict,
            top5=top5,
        )

    def reset(self) -> None:
        """Clear routing table without changing depth."""
        self.routing_table.clear()
        self.fission_slots.clear()
        self.expanded_slot_routers.clear()
        self.total_routed = 0


# ── MitoticBatchBuffer (P1) ───────────────────────────────────────────────────

@dataclass
class BatchReady:
    """A batch of ASTs ready for bulk MPS kernel dispatch."""
    flat_addr:  int
    address:    FractalAddress
    trees:      List[ast.AST]

    @property
    def size(self) -> int:
        return len(self.trees)


class MitoticBatchBuffer:
    """O(1) per-slot accumulation buffer for MPS-aligned bulk dispatch (P1).

    The Kronecker router scatters inputs across 4096 memory slots.
    Dispatching one AST at a time destroys Apple Silicon spatial locality
    (MPS prefers contiguous 64-byte-aligned tensor batches).

    This buffer holds incoming (addr, tree) pairs per slot.  When a slot
    accumulates ≥ min_batch items, it returns a BatchReady for bulk launch.
    Call flush() at end-of-stream to drain remaining partial batches.

    Usage:
        buf = MitoticBatchBuffer(min_batch=64)
        for tree in stream:
            addr = hasher.hash(tree)
            router.route(addr)
            batch = buf.add(addr, tree)
            if batch:
                dispatch_to_mps(batch)
        for batch in buf.flush():
            dispatch_to_mps(batch)
    """

    def __init__(self, min_batch: int = 64) -> None:
        if min_batch < 1:
            raise ValueError("min_batch must be ≥ 1")
        self.min_batch = min_batch
        self._slots: Dict[int, List[ast.AST]] = defaultdict(list)
        self._addr_map: Dict[int, FractalAddress] = {}
        self.total_dispatched: int = 0
        self.total_buffered: int = 0

    def add(self, addr: FractalAddress, tree: ast.AST) -> Optional[BatchReady]:
        """Add one AST to its slot.

        Returns a BatchReady (and clears the slot) when the slot reaches
        min_batch, otherwise returns None.
        """
        flat = addr.flat
        self._slots[flat].append(tree)
        self._addr_map[flat] = addr
        self.total_buffered += 1
        if len(self._slots[flat]) >= self.min_batch:
            return self._pop(flat)
        return None

    def _pop(self, flat: int) -> BatchReady:
        trees = self._slots.pop(flat)
        addr = self._addr_map.pop(flat)
        self.total_dispatched += len(trees)
        return BatchReady(flat_addr=flat, address=addr, trees=trees)

    def flush(self) -> List[BatchReady]:
        """Drain all pending slots regardless of size (end-of-stream)."""
        batches = [self._pop(flat) for flat in list(self._slots.keys())]
        return batches

    @property
    def pending(self) -> int:
        """Total ASTs currently buffered (not yet dispatched)."""
        return sum(len(v) for v in self._slots.values())

    @property
    def active_slots(self) -> int:
        return len(self._slots)


# ── Cross-domain isomorphism interface (P2 stub) ──────────────────────────────
# Activated when ASTs from OpenMathInstruct-1 and formal logic (proof-pile)
# route to the identical FractalAddress [H1, H2].  Triggers an Epiplexity
# Reward multiplier in the evolution loop.
#
# Full implementation deferred to P2 (proof-pile ingestion pipeline).

class IsomorphismRewardStub:
    """Placeholder for P2 cross-domain isomorphism reward.

    When enabled, records which fractal slots receive inputs from multiple
    domains.  A slot hit by both OpenMath Python ASTs and formal-logic DAGs
    signals a topological isomorphism — rewarded by an Epiplexity multiplier.
    """
    DOMAIN_OPENMATH   = "openmath"
    DOMAIN_PROOF_PILE = "proof_pile"   # reserved for P2

    def __init__(self) -> None:
        # slot → set of domains that have routed here
        self._slot_domains: Dict[int, set] = defaultdict(set)

    def record(self, addr: FractalAddress, domain: str) -> bool:
        """Record a routing event.  Returns True if this slot is now
        multi-domain (isomorphism detected → trigger reward)."""
        flat = addr.flat
        self._slot_domains[flat].add(domain)
        return len(self._slot_domains[flat]) > 1

    def isomorphic_slots(self) -> List[int]:
        """Return flat addresses that have seen ≥ 2 domains."""
        return [k for k, v in self._slot_domains.items() if len(v) > 1]

    def isomorphism_ratio(self, total_active_slots: int) -> float:
        """Calculate the ratio of slots with multi-domain condition."""
        if total_active_slots == 0:
            return 0.0
        return len(self.isomorphic_slots()) / total_active_slots


# ── Quick smoke-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import textwrap

    print("=== Kronecker Fractal Router P1.5 — Dynamic Depth Expansion Test ===\n")

    hasher = ASTHasher()
    router = KroneckerFractalRouter(depth=2)  # Start with depth 2
    buf    = MitoticBatchBuffer(min_batch=3)   # small for smoke test

    samples = [
        "x = 1 + 2",
        "for i in range(10): print(i)",
        "def f(x): return x ** 2",
        "[i**2 for i in range(100) if i % 2 == 0]",
        "import math; y = math.sqrt(sum(x**2 for x in range(50)))",
        textwrap.dedent("""
            from sympy import symbols, solve
            x = symbols('x')
            sol = solve(x**2 - 4, x)
        """),
    ]

    print("--- Initial routing ---")
    for src in samples:
        tree = ast.parse(src.strip())
        addr = hasher.hash(tree, depth=2)
        router.route(addr)
        batch = buf.add(addr, tree)
        print(f"  {addr}  ← {src.strip()[:55]!r}")
        if batch:
            print(f"    ⚡ batch ready: slot={batch.flat_addr:#05x}  size={batch.size}")

    print()
    print(router.stats())

    # Test capacity triggering fission by adding many of the same type of code
    print("\n--- Testing fission trigger with repeated code ---")
    test_code = "z = a + b"

    # Add the same code multiple times to trigger capacity threshold
    for i in range(CAPACITY + 10):  # Exceed capacity threshold
        tree = ast.parse(test_code)
        addr = hasher.hash(tree, depth=2)

        # Print every 30th insertion to show progress
        if i % 30 == 0:
            print(f"  Insertion #{i}: {addr} ← {test_code}")

        router.route(addr)

        if i == CAPACITY - 1:  # At capacity threshold
            print(f"  Capacity threshold ({CAPACITY}) reached for slot - fission should trigger")

    print(f"\nAfter {CAPACITY + 10} insertions:")
    print(router.stats())

    # Flush remaining
    remaining = buf.flush()
    if remaining:
        print(f"  flush: {len(remaining)} partial batch(es)")
        for b in remaining:
            print(f"    slot={b.flat_addr:#05x}  size={b.size}")

    # Test proper re-routing to expanded routers
    print("\n--- Testing Re-Routing to Expanded Routers ---")

    # Create a new router for demonstration of the full flow
    demo_router = KroneckerFractalRouter(depth=2)

    # Add items to a specific slot until it triggers fission
    test_tree = ast.parse("x = 1 + 2")
    addr_to_fill = hasher.hash(test_tree, depth=2)
    print(f"Filling slot {addr_to_fill} (flat: 0x{addr_to_fill.flat:03x}) to trigger fission...")

    # Fill the slot up to capacity
    for i in range(CAPACITY):
        demo_router.route(addr_to_fill)

    print(f"Slot filled to capacity ({CAPACITY}). Fission should have triggered.")

    # Now create multiple depth-3 addresses that would map to the expanded router
    # For this, we create addresses where the first two coordinates match the fissioned slot
    print("Creating multiple expanded addresses with same prefix...")
    for i in range(5):  # Create 5 expanded addresses
        coords_3d = list(addr_to_fill.coords)  # Start with the 2D coordinates
        coords_3d.append(i)  # Add a third coordinate to make it 3D
        expanded_addr = FractalAddress(tuple(coords_3d))

        print(f"  Created expanded address {expanded_addr} with same prefix as original slot")

        # This should route to the expanded router internally
        result = demo_router.route(expanded_addr)
        print(f"  Routed expanded address to flat address: 0x{result:04x}")

    # Show the stats to demonstrate the expanded routers are being counted properly
    print(f"\nDemo router stats after expanded routing:")
    print(demo_router.stats())

    # Verify that expanded routers were created and are being tracked
    print(f"Number of expanded slot routers: {len(demo_router.expanded_slot_routers)}")
    if demo_router.expanded_slot_routers:
        print("Expanded routers exist for these slots:", list(demo_router.expanded_slot_routers.keys()))
        # Check contents of expanded routers
        for slot, expanded_router in demo_router.expanded_slot_routers.items():
            print(f"  Slot 0x{slot:03x} expanded router has {expanded_router.total_routed} routed items")
            if expanded_router.routing_table:
                print(f"    Expanded router top slots: {list(expanded_router.routing_table.items())[:3]}")

    # from_flat round-trip
    for d in (1, 2, 3):
        for flat in (0, 1, 63, 64, 4095, 262143):  # Added higher values for d=3
            if flat >= FRACTAL_BASE ** d:
                continue
            addr = FractalAddress.from_flat(flat, d)
            assert addr.flat == flat, f"round-trip failed: {flat} → {addr} → {addr.flat}"
    print("\n  from_flat round-trip: OK")

    # P2 stub - test isomorphism tracking
    print("\n--- Testing P2 Isomorphism Reward ---")
    iso = IsomorphismRewardStub()
    for src in samples[:3]:
        addr = hasher.hash_source(src)
        if addr:
            hit = iso.record(addr, IsomorphismRewardStub.DOMAIN_OPENMATH)
            if hit:
                print(f"  Isomorphism detected at {addr}")

    # Simulate another domain hitting the same slots
    for src in samples[1:3]:  # Some overlapping codes from different domain
        addr = hasher.hash_source(src)
        if addr:
            hit = iso.record(addr, IsomorphismRewardStub.DOMAIN_PROOF_PILE)
            if hit:
                print(f"  Cross-domain isomorphism confirmed at {addr}")

    print(f"  IsomorphismRewardStub: {len(iso.isomorphic_slots())} isomorphic slots")
    print(f"  Isomorphism ratio: {iso.isomorphism_ratio(max(len(demo_router.routing_table), 1)):.4f}")
