# ingest_openmath.py — OpenMathInstruct-1 AST ingest pipeline (Phase P0)
# Streams nvidia/OpenMathInstruct-1, extracts Python ASTs (strips all NLP text),
# pipes them through KroneckerFractalRouter, reports routing variance.
#
# Requires: pip install datasets
# Decoupled from all legacy routing logic in atomic_core.py.

from __future__ import annotations

import argparse
import ast
import re
import threading
import time
from typing import Iterator, List, Optional

from fractal_router import (
    MAX_DEPTH,
    ASTHasher,
    FractalAddress,
    KroneckerFractalRouter,
    RouterStats,
)

# ── Dataset check ──────────────────────────────────────────────────────────────
_DATASETS_INSTALL_HINT = (
    "\n[ingest_openmath] 'datasets' not installed.\n"
    "  Run:  pip install datasets\n"
)

def _require_datasets():
    try:
        import datasets  # noqa: F401
    except ImportError as e:
        raise ImportError(_DATASETS_INSTALL_HINT) from e


# ── Python block extraction ────────────────────────────────────────────────────

_FENCE_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# Heuristic: lines that look like Python code (not prose)
_CODE_LINE_RE = re.compile(
    r"^\s*(?:import |from |def |class |for |while |if |return |with |try:|"
    r"except|raise |yield |async |await |\w+\s*=\s*|\w+\s*\()",
    re.MULTILINE,
)


def extract_python_blocks(text: str) -> List[str]:
    """Extract Python code strings from a solution text.

    Strategy (in order):
    1. Fenced ```python ... ``` blocks  (most reliable)
    2. Consecutive runs of code-looking lines (fallback for unfenced solutions)

    Returns a list of code strings (may be empty).
    NLP prose is discarded — only structural code is returned.
    """
    if not text:
        return []

    # Pass 1: fenced blocks
    fenced = _FENCE_RE.findall(text)
    if fenced:
        return [b.strip() for b in fenced if b.strip()]

    # Pass 2: gather consecutive heuristic-matched lines
    lines = text.splitlines()
    blocks: List[str] = []
    current: List[str] = []

    for line in lines:
        if _CODE_LINE_RE.match(line):
            current.append(line)
        else:
            if len(current) >= 2:  # require at least 2 lines to reduce noise
                blocks.append("\n".join(current))
            current = []

    if len(current) >= 2:
        blocks.append("\n".join(current))

    return blocks


# ── AST parsing with timeout ───────────────────────────────────────────────────

def parse_ast(code: str, timeout_s: float = 0.1) -> Optional[ast.AST]:
    """Parse Python source into an AST.

    Enforces a hard 100 ms wall-clock timeout (Phase P0 deterministic timeout).
    Returns None on SyntaxError, timeout, or any other parse failure.
    Uses a daemon thread so it never blocks the main process.
    """
    result: List[Optional[ast.AST]] = [None]
    exc: List[Optional[Exception]] = [None]

    def _parse() -> None:
        try:
            result[0] = ast.parse(code)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_parse, daemon=True)
    t.start()
    t.join(timeout_s)

    if t.is_alive():
        return None   # timeout — discard (Phase P0: anomaly collapse = 0)
    if exc[0]:
        return None   # syntax/parse error
    return result[0]


# ── OpenMathStream ─────────────────────────────────────────────────────────────

class OpenMathStream:
    """Lazy iterator over Python ASTs extracted from OpenMathInstruct-1.

    Streams the dataset from HuggingFace (never loads full dataset into RAM).
    Only `generated_solution` text fields are consumed; all NLP is discarded.

    Each yielded item is a valid ast.AST — rows that yield no parseable Python
    are skipped silently.

    Args:
        max_samples:  Stop after yielding this many ASTs (not rows).
        split:        HuggingFace dataset split (default "train").
        hf_token:     Optional HuggingFace access token for gated datasets.
    """

    HF_REPO = "nvidia/OpenMathInstruct-1"

    def __init__(
        self,
        max_samples: int = 10_000,
        split: str = "train",
        hf_token: Optional[str] = None,
    ) -> None:
        self.max_samples = max_samples
        self.split = split
        self.hf_token = hf_token

    def __iter__(self) -> Iterator[ast.AST]:
        _require_datasets()
        import datasets  # local import — lazy

        ds = datasets.load_dataset(
            self.HF_REPO,
            split=self.split,
            streaming=True,
            trust_remote_code=False,
            token=self.hf_token,
        )

        yielded = 0
        for row in ds:
            if yielded >= self.max_samples:
                break

            solution: str = row.get("generated_solution", "") or ""
            blocks = extract_python_blocks(solution)

            for code in blocks:
                if yielded >= self.max_samples:
                    break
                tree = parse_ast(code)
                if tree is not None:
                    yield tree
                    yielded += 1


# ── Phase P0 calibration ───────────────────────────────────────────────────────

def calibrate(
    router: KroneckerFractalRouter,
    n_samples: int = 10_000,
    depth: int = MAX_DEPTH,
    print_every: int = 500,
) -> RouterStats:
    """Route n_samples Python ASTs from OpenMathInstruct-1 through router.

    Measures routing variance — the key Phase P0 quality signal.
    Target: CV² < 0.5 indicates reasonably uniform address distribution.

    Args:
        router:       A KroneckerFractalRouter (depth must match `depth`).
        n_samples:    Number of ASTs to route.
        depth:        Fractal address depth (hard-locked ≤ MAX_DEPTH=2).
        print_every:  Progress print interval.

    Returns:
        RouterStats with final distribution metrics.
    """
    if depth > MAX_DEPTH:
        raise ValueError(f"Phase P0 hard lock: depth {depth} > MAX_DEPTH {MAX_DEPTH}")

    hasher = ASTHasher()
    stream = OpenMathStream(max_samples=n_samples)

    print(f"\n{'='*68}")
    print(f"  PHASE P0 — BASELINE CALIBRATION")
    print(f"{'='*68}")
    print(f"  Dataset  : {OpenMathStream.HF_REPO}")
    print(f"  Samples  : {n_samples:,}")
    print(f"  Depth    : d={depth} (max_slots={router.max_slots:,})")
    print(f"{'='*68}\n")

    t0 = time.time()
    routed = 0
    skipped = 0

    for tree in stream:
        addr: Optional[FractalAddress] = hasher.hash(tree, depth)
        router.route(addr)
        routed += 1

        if routed % print_every == 0:
            elapsed = time.time() - t0
            rate = routed / elapsed if elapsed > 0 else 0.0
            s = router.stats()
            print(
                f"  [{routed:>6}/{n_samples}]  "
                f"coverage={s.coverage:.4f}  "
                f"CV²={s.routing_variance:.6f}  "
                f"H={s.entropy_bits:.3f} bits  "
                f"{rate:.1f} AST/s"
            )

    elapsed = time.time() - t0
    stats = router.stats()

    print(f"\n{'='*68}")
    print(f"  CALIBRATION COMPLETE  ({elapsed:.1f}s)")
    print(f"{'='*68}")
    print(stats)
    print(f"  Verdict: {stats.verdict}\n")

    return stats


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phase P0 — OpenMathInstruct-1 AST calibration for KroneckerFractalRouter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--samples", type=int, default=10_000,
                   help="Number of Python ASTs to route")
    p.add_argument("--depth", type=int, default=MAX_DEPTH, choices=[1, 2],
                   help=f"Fractal address depth (hard-locked ≤ {MAX_DEPTH})")
    p.add_argument("--split", type=str, default="train",
                   help="HuggingFace dataset split")
    p.add_argument("--token", type=str, default=None,
                   help="HuggingFace access token (if needed)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    router = KroneckerFractalRouter(depth=args.depth)
    calibrate(
        router,
        n_samples=args.samples,
        depth=args.depth,
    )


if __name__ == "__main__":
    main()
