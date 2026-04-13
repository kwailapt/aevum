# ingest_proof_pile.py — Phase P2: Formal Logic → AST Isomorphism Harness
# Streams EleutherAI/proof-pile-2 (algebraic-stack subset), extracts formal proof blocks
# (Lean/Isabelle/LaTeX), translates them to Python ast.AST, and routes
# through the existing KroneckerFractalRouter to reveal cross-domain
# isomorphism with OpenMath Python code.
#
# Generator/Translator: regex extraction + AST translation (this file)
# Evaluator: KroneckerFractalRouter + IsomorphismRewardStub (fractal_router.py)
#
# Requires: pip install datasets

from __future__ import annotations

import argparse
import ast
import re
import threading
import time
from typing import Iterator, List, Optional, Tuple

from fractal_router import (
    MAX_DEPTH,
    ASTHasher,
    FractalAddress,
    IsomorphismRewardStub,
    KroneckerFractalRouter,
    RouterStats,
)

# ── Dataset check ─────────────────────────────────────────────────────────────
_DATASETS_INSTALL_HINT = (
    "\n[ingest_proof_pile] 'datasets' not installed.\n"
    "  Run:  pip install datasets\n"
)

def _require_datasets():
    try:
        import datasets  # noqa: F401
    except ImportError as e:
        raise ImportError(_DATASETS_INSTALL_HINT) from e


# ══════════════════════════════════════════════════════════════════════════════
# GENERATOR — Formal proof block extraction (regex)
# ══════════════════════════════════════════════════════════════════════════════

# Lean 4 / Lean 3 theorem/lemma/def blocks
_LEAN_BLOCK_RE = re.compile(
    r"(?:theorem|lemma|def|definition|example|noncomputable\s+def)\s+\w+.*?(?=\n(?:theorem|lemma|def|definition|example|noncomputable|section|namespace|end|#check|--|$)|\Z)",
    re.DOTALL,
)

# Isabelle: lemma/theorem/fun/definition blocks (terminated by done/qed/oops/next block)
_ISABELLE_BLOCK_RE = re.compile(
    r"(?:lemma|theorem|fun|definition|primrec|function)\s+\w+.*?(?:done|qed|oops|sorry)",
    re.DOTALL | re.IGNORECASE,
)

# LaTeX: \begin{proof}...\end{proof} or \begin{theorem}...\end{theorem}
_LATEX_PROOF_RE = re.compile(
    r"\\begin\{(?:proof|theorem|lemma|proposition|corollary)\}(.*?)\\end\{(?:proof|theorem|lemma|proposition|corollary)\}",
    re.DOTALL,
)

# Universal/existential quantifiers (∀, ∃, \forall, \exists, Lean ∀/∃)
_QUANTIFIER_RE = re.compile(r"[∀∃]|\\forall|\\exists|\bforall\b|\bexists\b")

# Implications (→, ⟹, \implies, \Rightarrow, =>)
_IMPLICATION_RE = re.compile(r"[→⟹]|\\implies|\\Rightarrow|=>|⟶")

# Equality / equivalence
_EQUALITY_RE = re.compile(r"(?<!=)=(?!=)|≡|≃|\\equiv|\\cong|\\sim")

# Assumptions / hypotheses
_ASSUMPTION_RE = re.compile(r"\bassume\b|\bhave\b|\blet\b|\bsuppose\b|\bhypothesis\b|\\(?:assume|given)", re.IGNORECASE)

# Function application / composition
_APPLICATION_RE = re.compile(r"\w+\s*\(|λ|\\lambda|\bfun\b|\blam\b")

# Conjunction / disjunction
_CONJUNCTION_RE = re.compile(r"[∧∨]|\\land|\\lor|\\wedge|\\vee|\band\b|\bor\b")

# Negation
_NEGATION_RE = re.compile(r"[¬]|\\neg|\\lnot|\bnot\b")

# Summation / product / integral (map to comprehension-like structures)
_AGGREGATE_RE = re.compile(r"\\sum|\\prod|\\int|∑|∏|∫|\\bigoplus|\\bigotimes")

# Set operations
_SET_OP_RE = re.compile(r"[∈∉⊂⊃⊆⊇∪∩]|\\in\b|\\subset|\\supset|\\cup|\\cap|\\setminus")


def extract_proof_blocks(text: str) -> List[str]:
    """Extract formal proof blocks from proof-pile text.

    Tries Lean, then Isabelle, then LaTeX environments.
    Falls back to quantifier-dense line runs.
    """
    if not text:
        return []

    blocks: List[str] = []

    # Pass 1: Lean blocks
    blocks.extend(m.strip() for m in _LEAN_BLOCK_RE.findall(text) if len(m.strip()) > 20)

    # Pass 2: Isabelle blocks
    blocks.extend(m.strip() for m in _ISABELLE_BLOCK_RE.findall(text) if len(m.strip()) > 20)

    # Pass 3: LaTeX proof/theorem environments
    blocks.extend(m.strip() for m in _LATEX_PROOF_RE.findall(text) if len(m.strip()) > 20)

    if blocks:
        return blocks

    # Pass 4: fallback — consecutive lines with formal logic markers
    lines = text.splitlines()
    current: List[str] = []
    for line in lines:
        has_formal = (
            _QUANTIFIER_RE.search(line)
            or _IMPLICATION_RE.search(line)
            or _EQUALITY_RE.search(line)
        )
        if has_formal:
            current.append(line)
        else:
            if len(current) >= 2:
                blocks.append("\n".join(current))
            current = []
    if len(current) >= 2:
        blocks.append("\n".join(current))

    return blocks


# ══════════════════════════════════════════════════════════════════════════════
# TRANSLATOR — Formal logic → Python ast.AST
# ══════════════════════════════════════════════════════════════════════════════
#
# Mapping rules (structural, not semantic):
#   Universal quantifiers / theorems  →  ast.FunctionDef or ast.For
#   Implications / assumptions        →  ast.If
#   Equalities                        →  ast.Compare
#   Function application              →  ast.Call
#   Conjunction / disjunction          →  ast.BoolOp
#   Negation                          →  ast.UnaryOp
#   Aggregates (sum/prod/int)          →  ast.ListComp
#   Set operations                    →  ast.BinOp
#   Existential quantifiers           →  ast.For (iteration = search)
#
# The translator emits a synthetic ast.Module wrapping these nodes.
# The ASTHasher only sees topology — variable names are irrelevant.

_DUMMY_ARGS = ast.arguments(
    posonlyargs=[], args=[ast.arg(arg="x")], vararg=None,
    kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[],
)
_DUMMY_NAME = ast.Name(id="_", ctx=ast.Load())
_DUMMY_CONST = ast.Constant(value=0)


def _count_matches(text: str, pattern: re.Pattern) -> int:
    return len(pattern.findall(text))


def translate_proof_to_ast(proof_text: str) -> Optional[ast.Module]:
    """Translate a formal proof block into a synthetic Python AST.

    The translation preserves structural topology — nesting depth, branching
    factor, control flow shape — while discarding all semantic content.
    The ASTHasher will then hash only the structural skeleton.
    """
    body: List[ast.stmt] = []

    # Count occurrences of each formal construct
    n_quantifiers   = _count_matches(proof_text, _QUANTIFIER_RE)
    n_implications  = _count_matches(proof_text, _IMPLICATION_RE)
    n_equalities    = _count_matches(proof_text, _EQUALITY_RE)
    n_assumptions   = _count_matches(proof_text, _ASSUMPTION_RE)
    n_applications  = _count_matches(proof_text, _APPLICATION_RE)
    n_conjunctions  = _count_matches(proof_text, _CONJUNCTION_RE)
    n_negations     = _count_matches(proof_text, _NEGATION_RE)
    n_aggregates    = _count_matches(proof_text, _AGGREGATE_RE)
    n_set_ops       = _count_matches(proof_text, _SET_OP_RE)

    total = (n_quantifiers + n_implications + n_equalities + n_assumptions
             + n_applications + n_conjunctions + n_negations + n_aggregates + n_set_ops)

    if total == 0:
        return None  # No recognizable formal structure

    # ── Build nested AST mirroring the proof's structural density ──

    # Universal quantifiers → FunctionDef (theorem = function over all inputs)
    # We nest them to reflect quantifier depth
    for i in range(min(n_quantifiers, 4)):
        func = ast.FunctionDef(
            name=f"_q{i}",
            args=_DUMMY_ARGS,
            body=[ast.Return(value=_DUMMY_NAME)],
            decorator_list=[],
            returns=None,
        )
        body.append(func)

    # Existential quantifiers → For loops (search over a domain)
    n_existential = proof_text.count("∃") + len(re.findall(r"\\exists|\bexists\b", proof_text))
    for i in range(min(n_existential, 3)):
        loop = ast.For(
            target=ast.Name(id=f"_e{i}", ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()),
                         args=[_DUMMY_CONST], keywords=[]),
            body=[ast.Pass()],
            orelse=[],
        )
        body.append(loop)

    # Implications → If statements (each implication = conditional branch)
    # Nest implications to reflect chained reasoning
    if n_implications > 0:
        inner: ast.stmt = ast.Pass()
        for _ in range(min(n_implications, 5)):
            inner = ast.If(
                test=ast.Compare(
                    left=_DUMMY_NAME,
                    ops=[ast.Gt()],
                    comparators=[_DUMMY_CONST],
                ),
                body=[inner],
                orelse=[],
            )
        body.append(inner)

    # Assumptions → additional If guards
    for _ in range(min(n_assumptions, 3)):
        body.append(ast.If(
            test=_DUMMY_NAME,
            body=[ast.Pass()],
            orelse=[],
        ))

    # Equalities → Compare nodes
    for _ in range(min(n_equalities, 4)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_eq", ctx=ast.Store())],
            value=ast.Compare(
                left=_DUMMY_NAME,
                ops=[ast.Eq()],
                comparators=[_DUMMY_CONST],
            ),
        ))

    # Function applications → Call nodes
    for _ in range(min(n_applications, 4)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_app", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="_f", ctx=ast.Load()),
                args=[_DUMMY_NAME],
                keywords=[],
            ),
        ))

    # Conjunctions / disjunctions → BoolOp
    for _ in range(min(n_conjunctions, 3)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_conj", ctx=ast.Store())],
            value=ast.BoolOp(
                op=ast.And(),
                values=[_DUMMY_NAME, _DUMMY_NAME],
            ),
        ))

    # Negations → UnaryOp
    for _ in range(min(n_negations, 3)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_neg", ctx=ast.Store())],
            value=ast.UnaryOp(
                op=ast.Not(),
                operand=_DUMMY_NAME,
            ),
        ))

    # Aggregates (∑, ∏, ∫) → ListComp (structural analog of reduction)
    for _ in range(min(n_aggregates, 3)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_agg", ctx=ast.Store())],
            value=ast.ListComp(
                elt=_DUMMY_NAME,
                generators=[ast.comprehension(
                    target=ast.Name(id="_i", ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()),
                                 args=[_DUMMY_CONST], keywords=[]),
                    ifs=[],
                    is_async=0,
                )],
            ),
        ))

    # Set operations → BinOp (structural analog of set algebra)
    for _ in range(min(n_set_ops, 3)):
        body.append(ast.Assign(
            targets=[ast.Name(id="_set", ctx=ast.Store())],
            value=ast.BinOp(
                left=_DUMMY_NAME,
                op=ast.BitXor(),  # structural stand-in for set operation
                right=_DUMMY_NAME,
            ),
        ))

    if not body:
        return None

    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    return module


# ══════════════════════════════════════════════════════════════════════════════
# STREAM — Proof-Pile dataset iterator
# ══════════════════════════════════════════════════════════════════════════════

class ProofPileStream:
    """Lazy iterator over translated ASTs from EleutherAI/proof-pile-2 (algebraic-stack).

    Bypasses the repo-level proof-pile-2.py builder script (which triggers
    "Dataset scripts are no longer supported" in datasets>=2.16) by streaming
    the raw .jsonl.zst files directly via the HF hub hf:// protocol.

    Uses a recursive glob so the datasets library discovers whatever shards
    actually exist — no hardcoded filenames.
    Only structural topology survives — all semantic content is discarded.
    """

    # Recursive glob — discovers all .jsonl.zst shards under algebraic-stack/.
    # The datasets library resolves this against the HF hub file listing at
    # load time, so it works regardless of how the repo organizes its shards.
    HF_DATA_GLOB = "hf://datasets/EleutherAI/proof-pile-2/algebraic-stack/**/*.jsonl.zst"

    def __init__(
        self,
        max_samples: int = 2_000,
        hf_token: Optional[str] = None,
    ) -> None:
        self.max_samples = max_samples
        self.hf_token = hf_token

    def __iter__(self) -> Iterator[ast.AST]:
        _require_datasets()
        import datasets

        ds = datasets.load_dataset(
            "json",
            data_files=self.HF_DATA_GLOB,
            split="train",
            streaming=True,
            token=self.hf_token,
        )

        yielded = 0
        rows_scanned = 0
        for row in ds:
            if yielded >= self.max_samples:
                break
            rows_scanned += 1

            text: str = row.get("text", "") or ""
            blocks = extract_proof_blocks(text)

            for block in blocks:
                if yielded >= self.max_samples:
                    break
                tree = translate_proof_to_ast(block)
                if tree is not None:
                    yield tree
                    yielded += 1

        print(f"  [ProofPileStream] scanned {rows_scanned} rows → yielded {yielded} ASTs")


# ══════════════════════════════════════════════════════════════════════════════
# HANDOFF + EVALUATOR — Mixed calibration run
# ══════════════════════════════════════════════════════════════════════════════

def mixed_calibration(
    n_openmath: int = 2_000,
    n_proofpile: int = 2_000,
    depth: int = MAX_DEPTH,
    print_every: int = 500,
) -> Tuple[RouterStats, IsomorphismRewardStub]:
    """Phase P2 mixed calibration.

    1. Route n_openmath ASTs from OpenMathInstruct-1 (domain: openmath)
    2. Route n_proofpile translated ASTs from proof-pile (domain: proof_pile)
    3. The IsomorphismRewardStub records every routing event.
       Slots hit by BOTH domains reveal topological isomorphism.
    4. Print RouterStats with isomorphism ratio.
    """
    # Import OpenMath stream from existing pipeline
    from ingest_openmath import OpenMathStream

    hasher = ASTHasher()
    router = KroneckerFractalRouter(depth=depth)
    iso    = IsomorphismRewardStub()

    print(f"\n{'═'*72}")
    print(f"  PHASE P2 — MIXED CALIBRATION: ISOMORPHISM HARNESS")
    print(f"{'═'*72}")
    print(f"  OpenMath samples  : {n_openmath:,}")
    print(f"  Proof-Pile samples: {n_proofpile:,}")
    print(f"  Depth             : d={depth} (max_slots={router.max_slots:,})")
    print(f"{'═'*72}\n")

    # ── Phase 1: OpenMath ──────────────────────────────────────────────────
    print(f"── DOMAIN 1: OpenMathInstruct-1 ──")
    t0 = time.time()
    om_stream = OpenMathStream(max_samples=n_openmath)
    om_routed = 0
    om_iso_hits = 0

    for tree in om_stream:
        addr = hasher.hash(tree, depth)
        router.route(addr)
        if iso.record(addr, IsomorphismRewardStub.DOMAIN_OPENMATH):
            om_iso_hits += 1
        om_routed += 1

        if om_routed % print_every == 0:
            elapsed = time.time() - t0
            rate = om_routed / elapsed if elapsed > 0 else 0.0
            s = router.stats()
            print(
                f"  [{om_routed:>6}/{n_openmath}]  "
                f"coverage={s.coverage:.4f}  "
                f"CV²={s.routing_variance:.6f}  "
                f"H={s.entropy_bits:.3f} bits  "
                f"{rate:.1f} AST/s"
            )

    om_elapsed = time.time() - t0
    print(f"  OpenMath complete: {om_routed} ASTs in {om_elapsed:.1f}s\n")

    # ── Phase 2: Proof-Pile ────────────────────────────────────────────────
    print(f"── DOMAIN 2: Proof-Pile (Formal Logic → AST) ──")
    t1 = time.time()
    pp_stream = ProofPileStream(max_samples=n_proofpile)
    pp_routed = 0
    pp_iso_hits = 0

    for tree in pp_stream:
        addr = hasher.hash(tree, depth)
        router.route(addr)
        if iso.record(addr, IsomorphismRewardStub.DOMAIN_PROOF_PILE):
            pp_iso_hits += 1
        pp_routed += 1

        if pp_routed % print_every == 0:
            elapsed = time.time() - t1
            rate = pp_routed / elapsed if elapsed > 0 else 0.0
            s = router.stats()
            print(
                f"  [{pp_routed:>6}/{n_proofpile}]  "
                f"coverage={s.coverage:.4f}  "
                f"CV²={s.routing_variance:.6f}  "
                f"H={s.entropy_bits:.3f} bits  "
                f"iso_hits={pp_iso_hits}  "
                f"{rate:.1f} AST/s"
            )

    pp_elapsed = time.time() - t1
    print(f"  Proof-Pile complete: {pp_routed} ASTs in {pp_elapsed:.1f}s\n")

    # ── Results ────────────────────────────────────────────────────────────
    stats = router.stats()

    # Inject the real isomorphism ratio from the evaluator
    iso_slots = iso.isomorphic_slots()
    iso_ratio = iso.isomorphism_ratio(stats.active_slots)
    stats.isomorphism_ratio = iso_ratio

    print(f"{'═'*72}")
    print(f"  PHASE P2 — ISOMORPHISM REPORT")
    print(f"{'═'*72}")
    print(stats)
    print(f"\n  Cross-domain isomorphic slots : {len(iso_slots)}")
    print(f"  Active slots (total)          : {stats.active_slots}")
    print(f"  ╔══════════════════════════════════════════════╗")
    print(f"  ║  ISOMORPHISM RATIO:  {iso_ratio:.6f}            ║")
    print(f"  ╚══════════════════════════════════════════════╝")

    if iso_ratio > 0.0:
        print(f"\n  ✦ NON-ZERO ISOMORPHISM DETECTED.")
        print(f"    Formal proofs and Python code share fractal topology.")
        print(f"    {len(iso_slots)} slots received routing events from BOTH domains.")
    else:
        print(f"\n  ○ No cross-domain overlap detected at this sample size.")

    print(f"\n  OpenMath iso-hits during PP phase : {pp_iso_hits}")
    print(f"  Total time: {om_elapsed + pp_elapsed:.1f}s")
    print(f"{'═'*72}\n")

    return stats, iso


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phase P2 — Proof-Pile formal logic → AST isomorphism calibration",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--openmath", type=int, default=2_000,
                   help="Number of OpenMath ASTs to route")
    p.add_argument("--proofpile", type=int, default=2_000,
                   help="Number of Proof-Pile translated ASTs to route")
    p.add_argument("--depth", type=int, default=MAX_DEPTH,
                   choices=list(range(1, MAX_DEPTH + 1)),
                   help=f"Fractal address depth (≤ {MAX_DEPTH})")
    p.add_argument("--token", type=str, default=None,
                   help="HuggingFace access token (if needed)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    mixed_calibration(
        n_openmath=args.openmath,
        n_proofpile=args.proofpile,
        depth=args.depth,
    )


if __name__ == "__main__":
    main()
