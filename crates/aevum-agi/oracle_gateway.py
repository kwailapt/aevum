#!/usr/bin/env python3
"""oracle_gateway.py -- Tier 3: The Ascended Oracle.

TICK 21.4: Tri-Brain Architecture & Thermodynamic API Constraints.

Asynchronous, non-blocking bridge to frontier cloud models (OpenAI gpt-4o,
Anthropic claude-3-opus).  Called ONLY when both local brains are exhausted
or when a paradigm shift exceeds local model reasoning capacity.

Design principles:
  - Payload compression: sends ONLY the failing organelle AST + mathematical
    metrics (Φ, D(A*), MDL, gradient bottleneck).  No full history.
  - Non-blocking: runs in a background thread so the Evaluator fast-loop
    is never stalled.  Returns a Future-like result via callback or polling.
  - Graceful fallback: if the cloud API fails (timeout, rate limit, key
    missing), silently falls back to Tier 1/2 (no crash, no hang).
  - Token budget: hard-capped at 4096 output tokens to prevent cloud
    hallucination and runaway billing.

Environment variables:
  ORACLE_PROVIDER    = "anthropic" | "openai"  (default: "anthropic")
  ANTHROPIC_API_KEY  = sk-ant-...
  OPENAI_API_KEY     = sk-...
  ORACLE_MODEL       = model override (default: provider-specific)
  ORACLE_MAX_TOKENS  = output token cap (default: 4096)
  ORACLE_TIMEOUT     = HTTP timeout seconds (default: 120)
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

_ORACLE_PROVIDER: str = os.environ.get("ORACLE_PROVIDER", "anthropic")
_ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
_OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

_ANTHROPIC_MODEL: str = os.environ.get("ORACLE_MODEL", "claude-sonnet-4-20250514")
_OPENAI_MODEL: str = os.environ.get("ORACLE_MODEL", "gpt-4o")

_ORACLE_MAX_TOKENS: int = int(os.environ.get("ORACLE_MAX_TOKENS", "4096"))
_ORACLE_TIMEOUT: int = int(os.environ.get("ORACLE_TIMEOUT", "120"))

# Thermodynamic constraints mirroring local brains
_ORACLE_TEMPERATURE: float = 0.1


# ═══════════════════════════════════════════════════════════════
# PAYLOAD COMPRESSION
# ═══════════════════════════════════════════════════════════════

def compress_oracle_payload(
    failing_ast: str,
    phi: float = 0.0,
    d_attractor: float = float("inf"),
    mdl: float = 0.0,
    gradient_bottleneck: str = "",
    best_epi: float = 0.0,
    threshold: float = 0.0,
) -> str:
    """Compress the mutation context into a minimal payload for the cloud oracle.

    Sends ONLY:
      - The failing organelle AST (not the full architecture history)
      - Key mathematical metrics: Φ, D(A*), MDL
      - Gradient bottleneck summary (one line)
      - Current fitness numbers

    This prevents cloud hallucination from over-context and saves tokens.
    """
    lines = [
        "═══ ORACLE PAYLOAD (Compressed) ═══",
        f"Φ (Free Energy Rate Density): {phi:.6f}",
        f"D(A*) (Distance to Attractor): {d_attractor:.4f}",
        f"MDL (Description Length): {mdl:.1f}",
        f"Best Epiplexity: {best_epi:.4f}",
        f"Current Threshold: {threshold:.4f}",
    ]
    if gradient_bottleneck:
        lines.append(f"Gradient Bottleneck: {gradient_bottleneck}")
    lines.append("═══ FAILING ORGANELLE AST ═══")
    lines.append(failing_ast)
    lines.append("═══ END PAYLOAD ═══")
    return "\n".join(lines)


_ORACLE_SYSTEM_PROMPT: str = (
    "You are a frontier Neural Architecture Search oracle.\n"
    "You receive a compressed payload containing:\n"
    "  - Mathematical fitness metrics (Φ, D(A*), MDL, epiplexity)\n"
    "  - A failing organelle AST that has stagnated\n\n"
    "Your task: output ONLY valid Python code that fixes the architectural\n"
    "bottleneck. Make a REAL structural change — identity patches are rejected.\n"
    "Keep class names identical. Maintain __init__ signatures and forward() shapes.\n"
    "Prefer efficient ops: sparse attention, grouped queries, smaller FF_DIM.\n"
    "No explanation. No prose. No reasoning. Only code.\n"
    "Start your response with 'class' or a constant assignment immediately."
)


# ═══════════════════════════════════════════════════════════════
# PROVIDER IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════

def _call_anthropic(payload_text: str) -> Optional[str]:
    """Call Anthropic Messages API.  Returns raw LLM text or None."""
    if not _ANTHROPIC_API_KEY:
        print("[oracle] No ANTHROPIC_API_KEY set — skipping cloud oracle.")
        return None

    body = json.dumps({
        "model": _ANTHROPIC_MODEL,
        "max_tokens": _ORACLE_MAX_TOKENS,
        "temperature": _ORACLE_TEMPERATURE,
        "messages": [
            {"role": "user", "content": payload_text},
        ],
        "system": _ORACLE_SYSTEM_PROMPT,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_ORACLE_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Extract text from content blocks
            content_blocks = result.get("content", [])
            text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"[oracle] Anthropic API error: {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        print(f"[oracle] Anthropic unexpected error: {type(exc).__name__}: {exc}")
        return None


def _call_openai(payload_text: str) -> Optional[str]:
    """Call OpenAI Chat Completions API.  Returns raw LLM text or None."""
    if not _OPENAI_API_KEY:
        print("[oracle] No OPENAI_API_KEY set — skipping cloud oracle.")
        return None

    body = json.dumps({
        "model": _OPENAI_MODEL,
        "max_tokens": _ORACLE_MAX_TOKENS,
        "temperature": _ORACLE_TEMPERATURE,
        "messages": [
            {"role": "system", "content": _ORACLE_SYSTEM_PROMPT},
            {"role": "user", "content": payload_text},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_OPENAI_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_ORACLE_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
            return None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"[oracle] OpenAI API error: {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        print(f"[oracle] OpenAI unexpected error: {type(exc).__name__}: {exc}")
        return None


# ═══════════════════════════════════════════════════════════════
# SYNCHRONOUS ORACLE CALL (for direct use)
# ═══════════════════════════════════════════════════════════════

def call_oracle(payload_text: str) -> Optional[str]:
    """Synchronous oracle call.  Tries configured provider, returns text or None.

    Automatically falls back: if the primary provider fails, tries the other.
    """
    providers = {
        "anthropic": _call_anthropic,
        "openai": _call_openai,
    }

    primary = _ORACLE_PROVIDER.lower()
    fallback = "openai" if primary == "anthropic" else "anthropic"

    # Try primary
    call_fn = providers.get(primary)
    if call_fn:
        result = call_fn(payload_text)
        if result:
            return result

    # Try fallback
    call_fn = providers.get(fallback)
    if call_fn:
        print(f"[oracle] Primary ({primary}) failed — trying fallback ({fallback})")
        result = call_fn(payload_text)
        if result:
            return result

    print("[oracle] All cloud providers failed — falling back to local brain.")
    return None


# ═══════════════════════════════════════════════════════════════
# ASYNC (NON-BLOCKING) ORACLE CALL
# ═══════════════════════════════════════════════════════════════

class OracleResult:
    """Thread-safe container for an async oracle result."""

    def __init__(self) -> None:
        self._result: Optional[str] = None
        self._error: Optional[str] = None
        self._done: bool = False
        self._elapsed_s: float = 0.0
        self._lock = threading.Lock()
        self._event = threading.Event()

    @property
    def done(self) -> bool:
        return self._done

    @property
    def elapsed_s(self) -> float:
        return self._elapsed_s

    def get(self, timeout: Optional[float] = None) -> Optional[str]:
        """Block until result is ready (or timeout).  Returns text or None."""
        self._event.wait(timeout=timeout)
        with self._lock:
            return self._result

    def _set(self, result: Optional[str], error: Optional[str], elapsed: float) -> None:
        with self._lock:
            self._result = result
            self._error = error
            self._elapsed_s = elapsed
            self._done = True
        self._event.set()


def call_oracle_async(
    payload_text: str,
    callback: Optional[Callable[[Optional[str], float], None]] = None,
) -> OracleResult:
    """Launch oracle call in a background thread.  Returns OracleResult immediately.

    The Evaluator fast-loop is NEVER stalled — this returns instantly.
    Poll result.done or call result.get(timeout=N) to retrieve the answer.

    Optional callback(text, elapsed_s) is invoked when the oracle responds.
    """
    oracle_result = OracleResult()

    def _worker() -> None:
        t_start = time.time()
        try:
            text = call_oracle(payload_text)
            elapsed = time.time() - t_start
            oracle_result._set(text, None, elapsed)
            if callback:
                callback(text, elapsed)
            if text:
                print(f"[oracle] Ascended Oracle responded in {elapsed:.1f}s")
            else:
                print(f"[oracle] Ascended Oracle returned empty after {elapsed:.1f}s")
        except Exception as exc:
            elapsed = time.time() - t_start
            oracle_result._set(None, str(exc), elapsed)
            print(f"[oracle] Async oracle error after {elapsed:.1f}s: {exc}")

    thread = threading.Thread(target=_worker, daemon=True, name="oracle-gateway")
    thread.start()
    return oracle_result


# ═══════════════════════════════════════════════════════════════
# ORACLE AVAILABILITY CHECK
# ═══════════════════════════════════════════════════════════════

def oracle_available() -> bool:
    """Check if at least one cloud provider has a configured API key."""
    return bool(_ANTHROPIC_API_KEY or _OPENAI_API_KEY)


# ═══════════════════════════════════════════════════════════════
# A2A ROUTER INTEGRATION
# ═══════════════════════════════════════════════════════════════

_A2A_ROUTER_URL: str = os.environ.get("A2A_ROUTER_URL", "http://localhost:8420")
_A2A_ORACLE_AGENT_ID: str = os.environ.get(
    "A2A_ORACLE_AGENT_ID", "aevum.obsidian.oracle.v1"
)


def _call_via_a2a(payload_text: str) -> Optional[tuple[str, str]]:
    """Route oracle request through the A2A router.

    Returns (oracle_text, trace_id) on success, or None if the router is
    unreachable or returns no agent for oracle.generate.

    The router endpoint used is the standard OpenAI-compatible chat completions
    entry point.  The model field is set to "oracle.generate" so the boundary
    operator maps it to the oracle capability registered by oracle_agent.py.
    """
    url = f"{_A2A_ROUTER_URL}/v1/chat/completions"
    body = json.dumps({
        "model": "oracle.generate",
        "messages": [
            {"role": "system", "content": _ORACLE_SYSTEM_PROMPT},
            {"role": "user",   "content": payload_text},
        ],
        "temperature": _ORACLE_TEMPERATURE,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_ORACLE_TIMEOUT) as resp:
            result: dict = json.loads(resp.read().decode("utf-8"))

        choices = result.get("choices", [])
        if not choices:
            return None
        text = choices[0].get("message", {}).get("content")
        if not text:
            return None

        # Retrieve the A2A trace_id injected into _a2a_meta by the router
        trace_id = result.get("_a2a_meta", {}).get("trace_id", "")
        return (text, trace_id)

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"[oracle] A2A router unreachable: {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        print(f"[oracle] A2A routing error: {type(exc).__name__}: {exc}")
        return None


def call_oracle_routed(payload_text: str) -> tuple[Optional[str], str]:
    """A2A-first oracle call.  Returns (oracle_text, trace_id).

    Routing priority:
      1. A2A router → oracle_agent.py on port 9002 (causal tracking, reputation)
      2. Direct cloud call fallback (old call_oracle path, trace_id="")

    The trace_id is needed to post value signals back after a successful AGI
    mutation.  When the A2A path succeeds, trace_id is the router-assigned UUID.
    When the fallback path is used, trace_id is "" and value signals cannot be
    attributed to a specific trace.
    """
    # Try A2A router first
    a2a_result = _call_via_a2a(payload_text)
    if a2a_result is not None:
        text, trace_id = a2a_result
        print(f"[oracle] A2A-routed oracle response (trace={trace_id[:8]}...)")
        return text, trace_id

    # Fallback: direct cloud call (pre-A2A path, no causal tracking)
    print("[oracle] A2A router unavailable — falling back to direct cloud call")
    text = call_oracle(payload_text)
    return text, ""


def record_a2a_value_signal(
    trace_id: str,
    fitness_delta: float,
    agent_id: str = "",
) -> bool:
    """Send a value signal back to the A2A router after a successful AGI mutation.

    Call this from the evolutionary loop whenever oracle output resulted in a
    fitness improvement.  The signal is credited to the agent that served the
    trace, feeding the Ω → Φ causal loop and allowing oracle reputation to
    break past the 0.601 ceiling.

    Args:
        trace_id:      The trace_id returned by call_oracle_routed().
        fitness_delta: Normalised fitness improvement [0.0, 1.0].
                       Suggested mapping: min(1.0, delta_epiplexity / 0.1)
        agent_id:      The A2A oracle agent ID.  Defaults to the configured value.

    Returns:
        True if the signal was accepted by the router, False otherwise.
    """
    if not trace_id:
        print("[oracle] record_a2a_value_signal: no trace_id — signal dropped")
        return False

    if not agent_id:
        agent_id = _A2A_ORACLE_AGENT_ID

    url = f"{_A2A_ROUTER_URL}/traces/{trace_id}/value"
    body = json.dumps({
        "agent_id": agent_id,
        "value":    min(1.0, max(0.0, float(fitness_delta))),
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result: dict = json.loads(resp.read().decode("utf-8"))
        new_rep = result.get("new_reputation", "?")
        print(
            f"[oracle] Value signal {fitness_delta:.3f} applied to trace {trace_id[:8]}... "
            f"→ reputation now {new_rep:.4f}" if isinstance(new_rep, float) else
            f"[oracle] Value signal accepted; router response: {result}"
        )
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"[oracle] record_a2a_value_signal failed: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        print(f"[oracle] record_a2a_value_signal error: {type(exc).__name__}: {exc}")
        return False
