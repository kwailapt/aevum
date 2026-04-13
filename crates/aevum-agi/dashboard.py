#!/usr/bin/env python3
"""dashboard.py — Holographic Glass Box Monitor (TICK 21.3)

Passive ANSI terminal UI that tails the unified universe.log stream.
Parses thermodynamic Governor metrics and unified evaluator logs to
render a live view of the Autopoietic Universe's biological state.

Breathing States (Φ-Boundary Duality Engine):
  [S] Sympathetic Expansion    — Φ rising, perm expanding, aggressive exploration
  [P] Parasympathetic Contract — Φ dropping, perm shrinking, shedding entropy
  [N] Nash Equilibrium         — High level, high success, Φ flat (local optimum)
  [C] Topological Collapse     — Continuous failures, D(A*) diverging from attractor

Usage:
    python3 dashboard.py [--log agi_workspace/universe.log] [--interval 1.5]
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys
import time
from pathlib import Path
from typing import Deque, Optional, Tuple

# ── ANSI Escape Codes ──────────────────────────────────────────────────────

_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_RED     = "\033[31m"
_GREEN   = "\033[32m"
_YELLOW  = "\033[33m"
_BLUE    = "\033[34m"
_MAGENTA = "\033[35m"
_CYAN    = "\033[36m"
_WHITE   = "\033[37m"

# ── Alternate Screen Buffer sequences (like top/htop) ─────────────────────
_ALT_SCREEN_ON  = "\033[?1049h"   # Enter alternate screen buffer
_ALT_SCREEN_OFF = "\033[?1049l"   # Exit alternate screen buffer
_CURSOR_HIDE    = "\033[?25l"     # Hide cursor
_CURSOR_SHOW    = "\033[?25h"     # Show cursor
_HOME           = "\033[H"        # Move cursor to top-left
_CLEAR_TO_EOS   = "\033[0J"       # Clear from cursor to end of screen

# ── Breathing State Definitions ────────────────────────────────────────────

_STATES = {
    "S": f"{_BOLD}{_GREEN}[S] Sympathetic Expansion{_RESET}",
    "P": f"{_BOLD}{_CYAN}[P] Parasympathetic Contraction{_RESET}",
    "N": f"{_BOLD}{_YELLOW}[N] Nash Equilibrium{_RESET}",
    "C": f"{_BOLD}{_RED}[C] Topological Collapse{_RESET}",
}

_STATE_DESC = {
    "S": "Φ rising · perm expanding · aggressively exploring fitness landscape",
    "P": "Φ dropping · perm shrinking · shedding entropy & consolidating gains",
    "N": "High level · high success · Φ flat (deep local optimum, watch D(A*))",
    "C": "Continuous failures · D(A*) diverging · organism losing attractor lock",
}

# ── Regex Patterns (decoupled — each metric extracted independently) ───────

# [governor] Phi=0.0786 peak=0.2186 expansion=1.04x D(A*)=0.7509 | d: perm=0.440 phase=init L=0.0000
_RE_GOV_TAG   = re.compile(r"\[governor\]")
_RE_PHI       = re.compile(r"[Pp]hi\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")
_RE_PEAK      = re.compile(r"peak\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")
_RE_EXPANSION = re.compile(r"expansion\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")
_RE_DATTR     = re.compile(r"D\(A\*\)\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?|inf)")
_RE_PERM      = re.compile(r"perm(?:eability)?\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")
_RE_PHASE     = re.compile(r"phase\s*=\s*(\w+)")
_RE_LOSS      = re.compile(r"(?:loss|L)\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")

# [eval_unified tick 25756] B=1 epi=0.1605 gen=26777 elapsed=0.51s fwd=2.8ms params=2706
_RE_EVAL_TAG  = re.compile(r"\[eval_unified(?:\s+tick\s+\d+)?\]")
_RE_GEN       = re.compile(r"\bgen\s*=?\s*(\d+)")
_RE_EPI       = re.compile(r"\bepi\s*=\s*([+-]?[\d.]+(?:e[+-]?\d+)?)")
_RE_ELAPSED   = re.compile(r"elapsed\s*=\s*([\d.]+)")
_RE_PARAMS    = re.compile(r"params\s*=\s*([\d.]+[MKBmkb]?)")
_RE_BEST      = re.compile(r"best\s*=\s*([\d.]+)")

# [pow] Success rate 1.00 > 0.3 — scaling threshold to 0.1150 (level 26292)
_RE_POW_TAG   = re.compile(r"\[pow\]")
_RE_SUCCESS   = re.compile(r"[Ss]uccess\s+rate\s+([\d.]+)")
_RE_LEVEL     = re.compile(r"level\s+(\d+)")

# ouroboros.log dense format fallback:
# "  gen  416500/516499 epi=     0.520 ... best= 0.639  8.9 g/s"
_RE_OUROBOROS = re.compile(
    r"\bgen\s+(\d+)/(\d+)\s+"
    r"epi\s*=\s*([\d.]+)"
    r"(?:.*?best\s*=\s*([\d.]+))?"
    r"(?:\s+([\d.]+)\s+g/s)?",
    re.IGNORECASE,
)

# ── State dataclasses (plain dicts for stdlib-only) ────────────────────────

def _empty_gov() -> dict:
    return {"phi": 0.0, "peak": 0.0, "expansion": 0.0,
            "d_attractor": 0.0, "perm": 0.5, "phase": "?", "loss": 0.0}

def _empty_eval() -> dict:
    return {"gen": 0, "epi": 0.0, "level": 0,
            "elapsed": 0.0, "params": "?", "success": 0.0, "best": 0.0}

# ── Log tailer ─────────────────────────────────────────────────────────────

class _LogTailer:
    """Persistent file handle that reads from the beginning and follows new lines.

    On first open the file is read from byte 0 so all historical lines are
    ingested immediately (populates sparklines on startup).  The handle is
    kept open between drain cycles; each call to drain() yields whatever new
    lines have been appended since the last read.  File rotation (different
    inode) is detected and the handle is transparently reopened.
    """

    def __init__(self, path: Path):
        self._path = path
        self._fh = None

    def _open(self):
        if self._path.exists():
            self._fh = open(self._path, "r", encoding="utf-8", errors="replace")
            # Read from byte 0 — ingest full history on first open
        return self._fh is not None

    def drain(self):
        """Yield all new lines available right now, then return."""
        if self._fh is None:
            if not self._open():
                return
        while True:
            line = self._fh.readline()
            if line:
                yield line.rstrip("\n")
            else:
                # EOF — check if file was rotated / replaced
                try:
                    if os.stat(self._path).st_ino != os.fstat(self._fh.fileno()).st_ino:
                        self._fh.close()
                        self._fh = None
                except OSError:
                    self._fh.close()
                    self._fh = None
                return


# ── Parsers ────────────────────────────────────────────────────────────────

def _safe_float(match, default: float = 0.0) -> float:
    if match:
        v = match.group(1)
        if v == "inf":
            return float("inf")
        return float(v)
    return default


def _parse_governor(line: str) -> Optional[dict]:
    if not _RE_GOV_TAG.search(line):
        return None
    g = _empty_gov()
    g["phi"]         = _safe_float(_RE_PHI.search(line))
    g["peak"]        = _safe_float(_RE_PEAK.search(line))
    g["expansion"]   = _safe_float(_RE_EXPANSION.search(line))
    g["d_attractor"] = _safe_float(_RE_DATTR.search(line))
    g["perm"]        = _safe_float(_RE_PERM.search(line), 0.5)
    m_phase = _RE_PHASE.search(line)
    if m_phase:
        g["phase"] = m_phase.group(1).upper()
    g["loss"]        = _safe_float(_RE_LOSS.search(line))
    return g


def _parse_eval(line: str) -> Optional[dict]:
    """Parse [eval_unified tick N] lines for gen, epi, elapsed, params."""
    if not _RE_EVAL_TAG.search(line):
        # Fallback: ouroboros dense format
        m2 = _RE_OUROBOROS.search(line)
        if m2:
            e = _empty_eval()
            e["gen"] = int(m2.group(1))
            if m2.group(3): e["epi"]  = float(m2.group(3))
            if m2.group(4): e["best"] = float(m2.group(4))
            return e
        return None
    # Must contain at least gen or epi to be a data line (not a status message)
    m_gen = _RE_GEN.search(line)
    m_epi = _RE_EPI.search(line)
    if not m_gen and not m_epi:
        return None
    e = _empty_eval()
    if m_gen:     e["gen"]     = int(m_gen.group(1))
    if m_epi:     e["epi"]     = float(m_epi.group(1))
    m_el = _RE_ELAPSED.search(line)
    if m_el:      e["elapsed"] = float(m_el.group(1))
    m_pa = _RE_PARAMS.search(line)
    if m_pa:      e["params"]  = m_pa.group(1)
    m_be = _RE_BEST.search(line)
    if m_be:      e["best"]    = float(m_be.group(1))
    return e


def _parse_pow(line: str) -> Optional[Tuple[float, int]]:
    """Parse [pow] lines for success rate and level."""
    if not _RE_POW_TAG.search(line):
        return None
    m_sr = _RE_SUCCESS.search(line)
    m_lv = _RE_LEVEL.search(line)
    if not m_sr and not m_lv:
        return None
    sr = float(m_sr.group(1)) if m_sr else 0.0
    lv = int(m_lv.group(1))   if m_lv else 0
    return (sr, lv)


# ── State Classifier ──────────────────────────────────────────────────────

def _classify_state(
    gov_hist: Deque[dict],
    eval_hist: Deque[dict],
) -> str:
    """Infer current breathing phase from recent governor/eval history."""

    if not gov_hist:
        return "N"

    latest = gov_hist[-1]
    phase_tag = latest.get("phase", "?")

    # If the governor explicitly reports a phase, honour it
    if phase_tag in ("S", "P", "N", "C"):
        return phase_tag

    # Derive from trends when no explicit phase tag is present
    phi_vals = [g["phi"] for g in gov_hist]
    perm_vals = [g["perm"] for g in gov_hist]
    d_vals = [g["d_attractor"] for g in gov_hist]

    phi_trend  = phi_vals[-1]  - phi_vals[0]  if len(phi_vals)  > 1 else 0.0
    perm_trend = perm_vals[-1] - perm_vals[0] if len(perm_vals) > 1 else 0.0
    d_trend    = d_vals[-1]    - d_vals[0]    if len(d_vals)    > 1 else 0.0

    # [C] Topological Collapse: D(A*) strictly increasing over window
    if d_trend > 0.05 and phi_trend < 0:
        return "C"

    # [S] Sympathetic Expansion: Φ rising AND perm expanding
    if phi_trend > 0.01 and perm_trend >= 0:
        return "S"

    # [P] Parasympathetic Contraction: Φ dropping OR perm shrinking
    if phi_trend < -0.01 or perm_trend < -0.02:
        return "P"

    # Evaluate Nash condition: high success + stagnant Φ
    if eval_hist:
        avg_success = sum(e["success"] for e in eval_hist) / len(eval_hist)
        if avg_success > 0.6 and abs(phi_trend) < 0.005:
            return "N"

    return "N"  # default: stagnant


# ── Rendering helpers ──────────────────────────────────────────────────────

def _bar(value: float, max_val: float, width: int = 30,
         color: str = _GREEN, invert_color: bool = False) -> str:
    """Render a Unicode block progress bar with dynamic colouring."""
    ratio = min(1.0, max(0.0, value / max(max_val, 1e-9)))
    filled = int(ratio * width)
    empty = width - filled

    if not invert_color:
        if ratio > 0.85:
            color = _RED
        elif ratio > 0.60:
            color = _YELLOW
    else:
        # Invert: green at high end (e.g. Phi, success_rate)
        if ratio < 0.30:
            color = _RED
        elif ratio < 0.60:
            color = _YELLOW
        else:
            color = _GREEN

    bar = f"{color}{'█' * filled}{_DIM}{'░' * empty}{_RESET}"
    return bar


def _phi_sparkline(gov_hist: Deque[dict], width: int = 20) -> str:
    """Render a mini sparkline of recent Φ values."""
    sparks = " ▁▂▃▄▅▆▇█"
    vals = [g["phi"] for g in gov_hist]
    if not vals:
        return _DIM + "─" * width + _RESET
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1e-9
    # Sample up to `width` points
    step = max(1, len(vals) // width)
    sampled = vals[::step][-width:]
    result = ""
    for v in sampled:
        idx = int(((v - mn) / rng) * (len(sparks) - 1))
        result += sparks[idx]
    result = result.rjust(width)
    # Colour the sparkline by phase
    last_phi = vals[-1]
    trend = vals[-1] - vals[0] if len(vals) > 1 else 0
    c = _GREEN if trend > 0 else (_RED if trend < -0.01 else _YELLOW)
    return f"{c}{result}{_RESET}"


def _fmt_phi(v: float) -> str:
    c = _GREEN if v > 0.7 else (_YELLOW if v > 0.4 else _RED)
    return f"{c}{_BOLD}{v:.4f}{_RESET}"


def _fmt_d(v: float) -> str:
    c = _GREEN if v < 0.2 else (_YELLOW if v < 0.5 else _RED)
    return f"{c}{_BOLD}{v:.4f}{_RESET}"


def _fmt_perm(v: float) -> str:
    c = _CYAN if v > 0.6 else (_YELLOW if v > 0.3 else _RED)
    return f"{c}{_BOLD}{v:.3f}{_RESET}"


# ── Frame renderer ────────────────────────────────────────────────────────

def _render_frame(
    gov_hist: Deque[dict],
    eval_hist: Deque[dict],
    lines_seen: int,
    log_path: Path,
) -> str:
    gov  = gov_hist[-1]  if gov_hist  else _empty_gov()
    ev   = eval_hist[-1] if eval_hist else _empty_eval()
    state = _classify_state(gov_hist, eval_hist)

    phi        = gov["phi"]
    peak       = gov["peak"]
    expansion  = gov["expansion"]
    d_att      = gov["d_attractor"]
    perm       = gov["perm"]
    loss       = gov["loss"]

    gen        = ev["gen"]
    epi        = ev["epi"]
    level      = ev["level"]
    elapsed    = ev["elapsed"]
    params     = ev["params"]
    success    = ev["success"]
    best_epi   = ev["best"]

    # Compute rolling success rate over eval history
    if eval_hist:
        avg_success = sum(e["success"] for e in eval_hist) / len(eval_hist)
        avg_epi     = sum(e["epi"] for e in eval_hist) / len(eval_hist)
    else:
        avg_success = 0.0
        avg_epi     = 0.0

    # Phi trend arrow
    if len(gov_hist) >= 2:
        phi_delta = gov_hist[-1]["phi"] - gov_hist[-2]["phi"]
        phi_arrow = f"{_GREEN}▲{_RESET}" if phi_delta > 0.001 else (
                    f"{_RED}▼{_RESET}"   if phi_delta < -0.001 else
                    f"{_YELLOW}─{_RESET}")
    else:
        phi_arrow = f"{_DIM}?{_RESET}"

    # D(A*) trend arrow (lower is better)
    if len(gov_hist) >= 2:
        d_delta = gov_hist[-1]["d_attractor"] - gov_hist[-2]["d_attractor"]
        d_arrow = f"{_RED}▲{_RESET}"   if d_delta > 0.005 else (
                  f"{_GREEN}▼{_RESET}" if d_delta < -0.005 else
                  f"{_DIM}─{_RESET}")
    else:
        d_arrow = f"{_DIM}?{_RESET}"

    W = 66  # inner box width (between ║ and ║)
    SEP = f"{_BOLD}{_CYAN}  {'─' * W}{_RESET}"

    out = [
        f"{_BOLD}{_CYAN}╔{'═' * W}╗{_RESET}",
        f"{_BOLD}{_CYAN}║{'ATOMIC META-EVOLVER  ·  HOLOGRAPHIC GLASS BOX  (TICK 21.3)':^{W}}║{_RESET}",
        f"{_BOLD}{_CYAN}╚{'═' * W}╝{_RESET}",
        "",
        f"  {_BOLD}Breathing State:{_RESET}  {_STATES[state]}",
        f"  {_DIM}{_STATE_DESC[state]}{_RESET}",
        "",

        # ── Thermodynamic State ────────────────────────────────────────────
        f"{_BOLD}  ┌─ Thermodynamic State (Φ Engine) {'─' * 29}┐{_RESET}",
        f"  │  Φ (Epiplexity):  {_fmt_phi(phi)}  {phi_arrow}   "
        f"Peak Φ: {_BOLD}{peak:.4f}{_RESET}",
        f"  │  Φ Sparkline (recent history):  {_phi_sparkline(gov_hist, 20)}",
        f"  │  Expansion factor: {_BOLD}{expansion:.3f}x{_RESET}   "
        f"Dual-Tension Loss: {_BOLD}{loss:.5f}{_RESET}",
        f"  │  {_bar(phi, 1.0, 30, _GREEN, invert_color=True)}  Φ={phi:.4f}",
        f"{_BOLD}  └{'─' * W}┘{_RESET}",
        "",

        # ── Membrane Permeability ──────────────────────────────────────────
        f"{_BOLD}  ┌─ Membrane Permeability (∂-Boundary) {'─' * 26}┐{_RESET}",
        f"  │  Permeability ψ: {_fmt_perm(perm)}   "
        f"[{'OPEN' if perm > 0.6 else ('GATED' if perm > 0.3 else 'SEALED')}]",
        f"  │  {_bar(perm, 1.0, 50, _CYAN)}",
        f"  │  Phase tag from governor:  {_BOLD}{gov['phase']}{_RESET}",
        f"{_BOLD}  └{'─' * W}┘{_RESET}",
        "",

        # ── Teleological Attractor D(A*) ───────────────────────────────────
        f"{_BOLD}  ┌─ Teleological Attractor D(A*) {'─' * 33}┐{_RESET}",
        f"  │  Distance D(A*): {_fmt_d(d_att)}  {d_arrow}  "
        f"{'CONVERGING' if d_att < 0.2 else ('DRIFTING' if d_att < 0.5 else 'DIVERGING')}",
        f"  │  {_bar(d_att, 1.0, 50, _BLUE)}",
        f"  │  Attractor lock:  {'🔒 STRONG' if d_att < 0.15 else ('⚡ WEAK' if d_att < 0.4 else '💀 LOST')}",
        f"{_BOLD}  └{'─' * W}┘{_RESET}",
        "",

        # ── Evolution Metrics ──────────────────────────────────────────────
        f"{_BOLD}  ┌─ Evolution Metrics {'─' * 44}┐{_RESET}",
        f"  │  Gen: {_BOLD}{gen:>10,}{_RESET}   PoW Level: {_BOLD}{level}{_RESET}   "
        f"Params: {_BOLD}{params}{_RESET}",
        f"  │  Epi (current): {_BOLD}{epi:.6f}{_RESET}   "
        f"Best: {_BOLD}{best_epi:.6f}{_RESET}   "
        f"Avg: {_BOLD}{avg_epi:.6f}{_RESET}",
        f"  │  Elapsed: {_BOLD}{elapsed:.1f}s{_RESET}",
        f"{_BOLD}  └{'─' * W}┘{_RESET}",
        "",

        # ── Evaluator Success Rate ─────────────────────────────────────────
        f"{_BOLD}  ┌─ Evaluator Success Rate {'─' * 39}┐{_RESET}",
        f"  │  Current success:  {_BOLD}{success:.1%}{_RESET}   "
        f"Rolling avg ({len(eval_hist)} samples): {_BOLD}{avg_success:.1%}{_RESET}",
        f"  │  {_bar(avg_success, 1.0, 50, _GREEN, invert_color=True)}",
        f"{_BOLD}  └{'─' * W}┘{_RESET}",
        "",

        f"  {_DIM}Log: {log_path}   Lines parsed: {lines_seen:,}   "
        f"Gov samples: {len(gov_hist)}   Eval samples: {len(eval_hist)}{_RESET}",
        f"  {_DIM}Passive tail — read-only — Press Ctrl+C to exit{_RESET}",
    ]
    return "\n".join(out)


# ── Main loop ─────────────────────────────────────────────────────────────

def run_dashboard(log: str = "agi_workspace/universe.log",
                  interval: float = 1.5,
                  history: int = 60) -> None:
    """Tail universe.log and render the Holographic Dashboard."""
    log_path = Path(log)

    gov_hist:  Deque[dict] = collections.deque(maxlen=history)
    eval_hist: Deque[dict] = collections.deque(maxlen=history)
    pow_success: float = 0.0
    pow_level: int = 0
    lines_seen = 0

    tailer = _LogTailer(log_path)
    _out = sys.stdout

    def _write_frame(text: str) -> None:
        """Overwrite the viewport in-place: home cursor, write, clear residual."""
        _out.write(_HOME + _CLEAR_TO_EOS + text)
        _out.flush()

    def _restore_terminal() -> None:
        """Unconditionally restore cursor and exit alternate screen buffer."""
        _out.write(_CURSOR_SHOW + _ALT_SCREEN_OFF)
        _out.flush()

    # ── Enter Alternate Screen Buffer ─────────────────────────────────────
    _out.write(_ALT_SCREEN_ON + _CURSOR_HIDE)
    _out.flush()

    try:
        while True:
            # Drain all new lines available right now
            for line in tailer.drain():
                lines_seen += 1

                g = _parse_governor(line)
                if g is not None:
                    gov_hist.append(g)
                    continue

                e = _parse_eval(line)
                if e is not None:
                    # Merge latest pow data into eval record
                    e["success"] = pow_success
                    e["level"]   = pow_level
                    eval_hist.append(e)
                    continue

                p = _parse_pow(line)
                if p is not None:
                    pow_success, pow_level = p

            if not gov_hist and not eval_hist:
                _write_frame(
                    f"{_BOLD}{_YELLOW}Waiting for log stream…{_RESET}\n"
                    f"{_DIM}No [governor] or [eval_unified] lines seen yet in\n"
                    f"  {log_path.resolve()}\n\n"
                    f"Start the universe (ouroboros.py / autopoietic_core.py) and\n"
                    f"pipe its output to {log_path}:{_RESET}\n\n"
                    f"  python3 ouroboros.py 2>&1 | tee {log_path}\n"
                )
            else:
                frame = _render_frame(gov_hist, eval_hist, lines_seen, log_path)
                _write_frame(frame)

            time.sleep(interval)

    except KeyboardInterrupt:
        pass
    except Exception:
        # Ensure terminal restoration even on unexpected errors
        _restore_terminal()
        raise
    finally:
        _restore_terminal()


# ── Entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Holographic Glass Box Monitor — TICK 21.3"
    )
    parser.add_argument(
        "--log", type=str, default="agi_workspace/universe.log",
        help="Path to the unified log stream (default: agi_workspace/universe.log)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.5,
        help="Refresh interval in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--history", type=int, default=60,
        help="Number of samples to keep per stream for trend analysis (default: 60)",
    )
    args = parser.parse_args()
    run_dashboard(log=args.log, interval=args.interval, history=args.history)


if __name__ == "__main__":
    main()
