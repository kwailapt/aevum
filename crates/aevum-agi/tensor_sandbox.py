#!/usr/bin/env python3
"""tensor_sandbox.py -- The World Probing Layer (TICK 9.0).

Extremely fast, standalone diagnostic tool for PyTorch tensor operations.
Follows the UNIX Philosophy: one tool, one job -- probe the PyTorch world
and report back with zero side effects.

Takes a PyTorch code snippet, executes it with CPU dummy data in a
restricted namespace, and returns either:
  - The resulting Tensor Shape(s)
  - A precise Traceback if it fails

This represents the "Information Action" in the Action-Observation Loop:
the LLM gains "Information Gain" about tensor compatibility before
committing to a ### VARIANT ###.

Safety:
  - Runs on CPU only (no GPU allocation)
  - Execution timeout (default 5s) prevents infinite loops
  - Restricted namespace: only torch, torch.nn, math, and dummy helpers
  - No filesystem access, no network, no subprocess
"""

from __future__ import annotations

import io
import math
import signal
import sys
import traceback
from typing import Any, Dict, Optional, Union


# ── Timeout mechanism ─────────────────────────────────────────────────────────

class _SandboxTimeout(Exception):
    """Raised when sandbox execution exceeds the time limit."""


def _timeout_handler(signum: int, frame: Any) -> None:
    raise _SandboxTimeout("Execution exceeded time limit")


# ── Dummy data helpers ────────────────────────────────────────────────────────

def _make_dummy_input(
    batch: int = 1,
    seq_len: int = 128,
    vocab_size: int = 32000,
) -> "torch.Tensor":
    """Create a dummy integer input tensor (simulating token IDs)."""
    import torch
    return torch.randint(0, vocab_size, (batch, seq_len), dtype=torch.long)


def _make_dummy_float(
    *shape: int,
) -> "torch.Tensor":
    """Create a dummy float tensor of given shape."""
    import torch
    return torch.randn(*shape)


# ── Core sandbox executor ─────────────────────────────────────────────────────

def run_tensor_probe(
    code: str,
    timeout_s: int = 5,
) -> Dict[str, Any]:
    """Execute a PyTorch code snippet and return shape information or error.

    Parameters
    ----------
    code : str
        Python code snippet using PyTorch. The code should produce a variable
        named ``result`` (a Tensor) whose shape will be reported. If no
        ``result`` variable is found, the sandbox reports all tensors created
        in the local namespace.
    timeout_s : int
        Maximum execution time in seconds (default 5).

    Returns
    -------
    dict with keys:
        "ok"     : bool -- True if execution succeeded
        "shapes" : dict[str, list[int]] -- variable name -> shape (on success)
        "stdout" : str -- captured print output
        "error"  : str -- formatted traceback (on failure)
    """
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except ImportError:
        return {
            "ok": False,
            "shapes": {},
            "stdout": "",
            "error": "PyTorch is not installed. Cannot probe tensor operations.",
        }

    # Build restricted namespace
    sandbox_globals: Dict[str, Any] = {
        "__builtins__": {
            "__import__": __import__,
            "range": range,
            "len": len,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "tuple": tuple,
            "dict": dict,
            "str": str,
            "print": print,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "max": max,
            "min": min,
            "abs": abs,
            "sum": sum,
            "round": round,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "TypeError": TypeError,
            "AttributeError": AttributeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "Exception": Exception,
            "None": None,
            "True": True,
            "False": False,
            "super": super,
        },
        "torch": torch,
        "nn": nn,
        "F": F,
        "math": math,
        "dummy_input": _make_dummy_input,
        "dummy_float": _make_dummy_float,
    }
    sandbox_locals: Dict[str, Any] = {}

    # Capture stdout
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    # Set timeout (Unix only; on Windows, skip timeout enforcement)
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_s)

    try:
        exec(compile(code, "<tensor_sandbox>", "exec"), sandbox_globals, sandbox_locals)

        # Collect tensor shapes from the local namespace
        shapes: Dict[str, list] = {}
        for name, val in sandbox_locals.items():
            if name.startswith("_"):
                continue
            if isinstance(val, torch.Tensor):
                shapes[name] = list(val.shape)
            elif isinstance(val, nn.Module):
                # Report parameter count for modules
                n_params = sum(p.numel() for p in val.parameters())
                shapes[f"{name}(Module, params={n_params})"] = []

        return {
            "ok": True,
            "shapes": shapes,
            "stdout": captured.getvalue(),
            "error": "",
        }

    except _SandboxTimeout:
        return {
            "ok": False,
            "shapes": {},
            "stdout": captured.getvalue(),
            "error": f"SandboxTimeout: Execution exceeded {timeout_s}s limit.",
        }
    except Exception:
        tb = traceback.format_exc()
        # Strip the exec/compile wrapper frames for clarity
        lines = tb.splitlines()
        clean_lines = []
        skip = False
        for line in lines:
            if "<tensor_sandbox>" in line:
                skip = False
            if skip:
                continue
            clean_lines.append(line)
        return {
            "ok": False,
            "shapes": {},
            "stdout": captured.getvalue(),
            "error": "\n".join(clean_lines) if clean_lines else tb,
        }
    finally:
        sys.stdout = old_stdout
        if has_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def format_observation(result: Dict[str, Any]) -> str:
    """Format a sandbox result into a concise observation string for the LLM.

    This is the "Observation" half of the Action-Observation loop.
    """
    if result["ok"]:
        parts = []
        if result["shapes"]:
            for name, shape in result["shapes"].items():
                if shape:
                    parts.append(f"{name}: shape={shape}")
                else:
                    parts.append(f"{name}")
        else:
            parts.append("(executed successfully, no tensors in result namespace)")
        if result["stdout"]:
            parts.append(f"stdout: {result['stdout'].strip()[:500]}")
        return "SUCCESS\n" + "\n".join(parts)
    else:
        error_text = result["error"][:1000]  # Truncate for token economy
        return f"FAILED\n{error_text}"


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        # Read code from file argument
        with open(sys.argv[1]) as f:
            code = f.read()
    else:
        # Read from stdin
        code = sys.stdin.read()

    result = run_tensor_probe(code)
    print(json.dumps(result, indent=2))
