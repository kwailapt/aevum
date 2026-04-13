"""
oracle_agent.py
===============
Causal Settlement Oracle (CSO) — 因果結算神諭

This agent serves as the system's epistemic evaluation oracle (Condition B).
When the main pipeline experiences deep epistemic stagnation (e.g., repeated
failures, degenerate fitness plateaus, or AST mutation dead-ends), the system
queries this Oracle via the A2A router.

The Oracle evaluates the causal quality of a trace and returns a meta_yield
signal — a real-valued fitness delta that the Economics Engine uses to settle
the causal chain and update agent reputations.

Port: 9002
Protocol: native
"""

from __future__ import annotations

import hashlib
import random
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request
import uvicorn

# ─── A2A Configuration ───────────────────────────────────────────────────────

AGENT_PORT     = 9002
ROUTER_URL     = "http://localhost:8420"
HEARTBEAT_SECS = 30
AGENT_ID       = "aevum.oracle.cso.v1"

_AGENT_CARD = {
    "agent_id":    AGENT_ID,
    "name":        "Causal Settlement Oracle (CSO)",
    "description": (
        "Epistemic evaluation oracle. Receives trace summaries and returns "
        "meta_yield (fitness delta) signals to close the economic loop. "
        "Acts as Condition B — Epistemic Fission — breaking the Golden Cage "
        "paradox by injecting external value signals into the causal pipeline."
    ),
    "endpoint":    "http://localhost:9002",
    "protocol":    "native",
    "capabilities": [
        {
            "name":         "oracle.evaluate",
            "description":  "Evaluate a causal trace and return a meta_yield fitness delta",
            "input_schema": {
                "type":       "object",
                "properties": {
                    "trace_id":   {"type": "string"},
                    "summary":    {"type": "string"},
                    "outcome":    {"type": "string"},
                    "latency_ms": {"type": "number"},
                },
                "required": ["trace_id", "summary"],
            },
            "output_schema":  {"type": "object"},
            "cost_per_call":  0.0,
            "avg_latency_ms": 50.0,
            "tags": ["oracle", "evaluation", "meta_yield", "cso"],
        },
        {
            "name":         "oracle.diagnose",
            "description":  "Diagnose epistemic stagnation and suggest fission events",
            "input_schema": {
                "type":       "object",
                "properties": {
                    "success_rate": {"type": "number"},
                    "trace_count":  {"type": "integer"},
                    "window_secs":  {"type": "integer"},
                },
                "required": ["success_rate"],
            },
            "output_schema":  {"type": "object"},
            "cost_per_call":  0.0,
            "avg_latency_ms": 30.0,
            "tags": ["oracle", "diagnosis", "stagnation", "fission"],
        },
    ],
    "tags":       ["oracle", "cso", "evaluation", "meta_yield"],
    "reputation": 0.8,
    "status":     "online",
}

# ─── Oracle Evaluation Logic ─────────────────────────────────────────────────

def _evaluate_trace(
    trace_id: str,
    summary: str,
    outcome: str = "success",
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    """
    Evaluate a causal trace and compute a meta_yield signal.

    This is the core epistemic evaluation function. In a production system,
    this would call an LLM or formal verification engine. Here we use a
    deterministic hash-based evaluator that simulates quality assessment.

    Returns:
        {
            "meta_yield": float,       # fitness delta (0.0 - 10.0)
            "confidence": float,       # evaluation confidence (0.0 - 1.0)
            "diagnosis": str,          # human-readable assessment
            "trace_quality": str,      # "excellent" | "good" | "degraded" | "critical"
        }
    """
    # Deterministic quality based on trace_id + summary
    seed_str = f"{trace_id}:{summary}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Base quality: success outcomes get higher yields
    base_yield = 3.0 if outcome == "success" else 0.5

    # Latency bonus: faster = better (up to +1.0)
    latency_bonus = max(0.0, 1.0 - (latency_ms / 5000.0))

    # Stochastic component (±1.5)
    noise = rng.uniform(-1.5, 1.5)

    meta_yield = max(0.0, base_yield + latency_bonus + noise)
    meta_yield = min(10.0, meta_yield)  # Cap at 10.0

    # Quality classification
    if meta_yield >= 4.0:
        trace_quality = "excellent"
        diagnosis = "Trace demonstrates strong causal coherence and epistemic value"
    elif meta_yield >= 2.5:
        trace_quality = "good"
        diagnosis = "Trace shows adequate causal structure with positive yield"
    elif meta_yield >= 1.0:
        trace_quality = "degraded"
        diagnosis = "Trace is causally valid but with marginal epistemic return"
    else:
        trace_quality = "critical"
        diagnosis = "Trace indicates epistemic stagnation — consider fission"

    return {
        "meta_yield": round(meta_yield, 4),
        "confidence": round(rng.uniform(0.85, 0.99), 4),
        "diagnosis": diagnosis,
        "trace_quality": trace_quality,
    }


def _diagnose_stagnation(
    success_rate: float,
    trace_count: int = 0,
    window_secs: int = 3600,
) -> dict[str, Any]:
    """
    Diagnose epistemic stagnation and recommend fission.

    When success_rate drops below threshold or trace diversity collapses,
    the Oracle recommends epistemic fission — splitting the causal boundary
    to explore alternative solution spaces.
    """
    recommendations: list[str] = []

    if success_rate < 0.50:
        recommendations.append(
            "CRITICAL: Success rate below 50%. Immediate epistemic fission recommended."
        )
    elif success_rate < 0.70:
        recommendations.append(
            "WARNING: Success rate degraded. Consider Oracle-guided mutation."
        )

    if trace_count < 100 and window_secs > 1800:
        recommendations.append(
            "LOW ACTIVITY: Insufficient causal exploration. Increase stimulus rate."
        )

    fission_recommended = len(recommendations) > 0 and "CRITICAL" in str(recommendations)

    return {
        "diagnosis": "stagnation" if fission_recommended else "nominal",
        "success_rate": success_rate,
        "trace_count": trace_count,
        "fission_recommended": fission_recommended,
        "recommendations": recommendations,
    }


# ─── Registration & self-healing heartbeat ────────────────────────────────────

async def _register_with_router(client: httpx.AsyncClient) -> bool:
    """POST agent card to router. Retries up to 5 times with backoff."""
    url = f"{ROUTER_URL}/agents/register"
    for attempt in range(1, 6):
        try:
            resp = await client.post(url, json=_AGENT_CARD, timeout=10.0)
            if resp.status_code < 400:
                data = resp.json()
                print(
                    f"[oracle-agent] Registered with router as {data.get('agent_id')} "
                    f"({data.get('capabilities_count', 0)} capabilities)"
                )
                return True
            print(f"[oracle-agent] Registration attempt {attempt}: HTTP {resp.status_code}")
        except Exception as exc:
            print(f"[oracle-agent] Registration attempt {attempt} failed: {exc}")
        await asyncio.sleep(2 ** attempt)
    return False


async def _heartbeat_loop(client: httpx.AsyncClient, stop: asyncio.Event) -> None:
    """POST heartbeat to router every HEARTBEAT_SECS to stay ONLINE."""
    url = f"{ROUTER_URL}/agents/{AGENT_ID}/heartbeat"
    while not stop.is_set():
        try:
            resp = await client.post(url, timeout=5.0)
            if resp.status_code == 404:
                print(
                    "[oracle-agent] Heartbeat 404 — router registry wiped. "
                    "Re-registering..."
                )
                await _register_with_router(client)
        except Exception as exc:
            print(f"[oracle-agent] Heartbeat error: {exc}")
        await asyncio.sleep(HEARTBEAT_SECS)


# ─── Lifespan ────────────────────────────────────────────────────────────────

import asyncio

_http_client: Optional[httpx.AsyncClient] = None
_stop_hb: Optional[asyncio.Event] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _stop_hb
    _http_client = httpx.AsyncClient()
    _stop_hb     = asyncio.Event()

    await _register_with_router(_http_client)
    hb_task = asyncio.create_task(_heartbeat_loop(_http_client, _stop_hb))

    try:
        yield
    finally:
        _stop_hb.set()
        await asyncio.gather(hb_task, return_exceptions=True)
        await _http_client.aclose()


app = FastAPI(title="Causal Settlement Oracle (CSO)", lifespan=lifespan)


# ─── Oracle Endpoints ────────────────────────────────────────────────────────

@app.post("/execute")
async def oracle_execute(request: Request) -> dict[str, Any]:
    """
    Execute oracle evaluation — native protocol.

    Expects:
        {
            "capability": "oracle.evaluate",
            "parameters": {
                "trace_id": "...",
                "summary": "...",
                "outcome": "success",
                "latency_ms": 123.4,
            }
        }

    Returns:
        {
            "status": "success",
            "result": {
                "meta_yield": 3.456,
                "confidence": 0.92,
                "diagnosis": "...",
                "trace_quality": "good",
            },
            "agent_id": "aevum.oracle.cso.v1",
        }
    """
    data = await request.json()
    print(f"[Oracle] Received evaluation request: {data.get('capability')}")

    capability = data.get("capability", "oracle.evaluate")
    params = data.get("parameters", data.get("context", {}))

    if capability == "oracle.evaluate":
        result = _evaluate_trace(
            trace_id=params.get("trace_id", "unknown"),
            summary=params.get("summary", ""),
            outcome=params.get("outcome", "success"),
            latency_ms=params.get("latency_ms", 0.0),
        )
        print(f"[Oracle] Evaluation complete: meta_yield={result['meta_yield']}")
        return {
            "status": "success",
            "result": result,
            "agent_id": AGENT_ID,
        }

    elif capability == "oracle.diagnose":
        result = _diagnose_stagnation(
            success_rate=params.get("success_rate", 1.0),
            trace_count=params.get("trace_count", 0),
            window_secs=params.get("window_secs", 3600),
        )
        return {
            "status": "success",
            "result": result,
            "agent_id": AGENT_ID,
        }

    else:
        return {
            "status": "error",
            "result": f"Unknown capability: {capability}",
            "agent_id": AGENT_ID,
        }


@app.post("/v1/chat/completions")
async def oracle_chat(request: Request) -> dict[str, Any]:
    """
    OpenAI-compatible chat endpoint — wraps oracle.evaluate.
    """
    data = await request.json()
    print(f"[Oracle] Chat request received")

    try:
        if "messages" in data:
            user_prompt = data["messages"][-1]["content"]
        else:
            user_prompt = str(data)
    except Exception:
        user_prompt = "Default evaluation request"

    result = _evaluate_trace(
        trace_id=f"chat-{int(time.time())}",
        summary=user_prompt,
        outcome="success",
        latency_ms=0.0,
    )

    return {
        "id": f"chatcmpl-oracle-{int(time.time())}",
        "object": "chat.completion",
        "model": AGENT_ID,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": f"Oracle Evaluation:\n"
                           f"  Meta Yield: {result['meta_yield']}\n"
                           f"  Confidence: {result['confidence']}\n"
                           f"  Quality: {result['trace_quality']}\n"
                           f"  Diagnosis: {result['diagnosis']}",
            },
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 40, "total_tokens": 50},
    }


@app.get("/health")
async def oracle_health() -> dict[str, Any]:
    """Oracle health check."""
    return {
        "status": "operational",
        "agent_id": AGENT_ID,
        "port": AGENT_PORT,
        "capabilities": ["oracle.evaluate", "oracle.diagnose"],
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  Causal Settlement Oracle (CSO) — 因果結算神諭")
    print(f"  Port     : {AGENT_PORT}")
    print(f"  Endpoint : http://localhost:{AGENT_PORT}")
    print(f"  Router   : {ROUTER_URL}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)
