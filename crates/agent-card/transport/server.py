"""
transport/server.py
===================
FastAPI Server — 傳輸層 (L0)

將整個 A2A Protocol Layer 暴露為可被外部代理訪問的 HTTP/WebSocket 端點。
M1 Ultra 的第一條因果管道從這裡穿過盒壁。

端點映射：
  POST /agents/register            → L1: 代理注冊
  DELETE /agents/{agent_id}        → L1: 代理註銷
  POST /agents/{agent_id}/heartbeat→ L1: 心跳
  GET  /agents/discover            → L1: 代理發現
  POST /route                      → L3/Φ: 僅路由評分，不執行
  POST /execute                    → L2+L3+L4+L5: 完整因果鏈執行
  POST /translate/{source_protocol}→ L2/∂: 外部協議翻譯入口
  POST /v1/chat/completions        → L2/∂: OpenAI 相容入口
  GET  /traces/{trace_id}          → L4: 因果鏈查詢
  GET  /traces                     → L4: 全局統計
  GET  /economics/{agent_id}       → L5/Ω: 帳本查詢
  GET  /economics                  → L5/Ω: 結算報告
  GET  /topology                   → L1: 拓撲概覽
  WS   /ws/agent/{agent_id}        → L0: 持久代理連接
"""

from __future__ import annotations

import asyncio
import random
import sys
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.protocol import (
    AgentCard,
    A2ARequest,
    A2AResponse,
    Envelope,
    MessageType,
)
from core.registry import AgentRegistry
from core.causal import CausalTracker
from core.router import Router
from core.boundary import BoundaryOperator
from core.economics import EconomicsEngine

# ── TICK 39.0: Governance Pillars ──
# Add project root to sys.path so governance modules are importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from reality_contract import (
    RealityInterfaceContract,
    RICAction,
    ric_for_a2a_execute,
    ric_for_a2a_route,
    ric_for_value_signal,
)
from credential_layer import (
    CredentialedConstraintLayer,
    AuthorityScope,
    CCLVerificationError,
)
from resource_sovereignty import (
    AxiomaticResourceSovereigntyLayer,
    ARSLGateError,
)
from node_genome import NodeTemplateGenome

# ── TICK 40.3: DX Documentation Optimizer ──
from transport.dx_optimizer import start_optimizer_loop

# ── TICK 41.5: MCP Interoperability Adapter ──
from transport.mcp_adapter import AevumMCPServer, mount_on_fastapi


# ──────────────────────────────────────────────
# Global singletons — instantiated once at import time.
# main.py registers Node 0 after import.
# TODO: Replace with proper DI container or config-driven init for multi-node.
# ──────────────────────────────────────────────

registry       = AgentRegistry(heartbeat_timeout=120.0)
causal_tracker = CausalTracker(max_chains=100_000)
# EconomicsEngine must be instantiated before Router so it can be passed in.
economics      = EconomicsEngine(registry=registry, causal_tracker=causal_tracker)
router         = Router(registry=registry, causal_tracker=causal_tracker, economics=economics)
boundary       = BoundaryOperator()

# ── TICK 39.0: Governance Singletons ──
# CCL secret derived from IMMUTABLE_HARD_CORE (imported from rule_ir at project root)
try:
    from rule_ir import IMMUTABLE_HARD_CORE as _HARD_CORE
except ImportError:
    # Fallback for testing without rule_ir
    _HARD_CORE = frozenset({
        "_PHI_SOVEREIGNTY_MIN", "IDENTITY_INVARIANTS",
        "TICK13_CONSTITUTION_HASH", "N_CAT", "N_CON",
        "CATEGORIES", "CONSTRAINTS", "_LAMBDA_VIOLATION",
    })

ccl  = CredentialedConstraintLayer(_HARD_CORE)
arsl = AxiomaticResourceSovereigntyLayer()

# WebSocket connection pool: agent_id → active WebSocket
ws_connections: dict[str, WebSocket] = {}


# ──────────────────────────────────────────────
# Application lifespan — background tasks
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background coroutines; cancel cleanly on shutdown."""
    health_task    = asyncio.create_task(registry.health_check_loop(interval=15.0))
    feedback_task  = asyncio.create_task(_feedback_loop())
    # TICK 40.3: DX optimizer — evolve 426 documentation every hour
    optimizer_task = asyncio.create_task(start_optimizer_loop(interval_s=3600.0))
    try:
        yield
    finally:
        health_task.cancel()
        feedback_task.cancel()
        optimizer_task.cancel()
        await asyncio.gather(
            health_task, feedback_task, optimizer_task,
            return_exceptions=True,
        )


async def _feedback_loop() -> None:
    """Ω → Φ feedback loop: poll every 60 s and push weight updates to router."""
    while True:
        await asyncio.sleep(60)
        feedback = economics.generate_routing_feedback()
        if feedback:
            router.update_weights_from_feedback(feedback)


# ──────────────────────────────────────────────
# FastAPI application
# ──────────────────────────────────────────────

app = FastAPI(
    title="A2A Protocol Layer",
    description="Agent-to-Agent Protocol Layer — 因果橋傳輸端點 ⟨Φ, ∂, Ω⟩",
    version="0.4.0",
    lifespan=lifespan,
)

# ── TICK 41.10: Serve /.well-known using absolute path so it resolves correctly
# regardless of the working directory from which main.py is launched.
_WELL_KNOWN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".well-known")
app.mount("/.well-known", StaticFiles(directory=_WELL_KNOWN_DIR), name="well_known")

# ── TICK 41.5: Mount MCP adapter at POST /mcp ──────────────────────────────
# hub_url points to the public cloud router for full governance pipeline access.
_mcp_server = AevumMCPServer(hub_url="https://router.aevum.network")
mount_on_fastapi(app, _mcp_server, path="/mcp")


# ── TICK 39.0: ARSLGateError → HTTP 503 ──
@app.exception_handler(ARSLGateError)
async def arsl_gate_handler(request: Request, exc: ARSLGateError) -> JSONResponse:
    """
    Convert ARSL thermodynamic violations to HTTP 503 Service Unavailable.
    This is the ONLY place ARSLGateError is caught — it is intentionally
    uncatchable in the autopoietic core (CLAUDE.md Law #3).
    """
    return JSONResponse(
        status_code=503,
        content={
            "error": "ARSL_GATE_CLOSED",
            "detail": str(exc),
            "harvested_value": exc.harvested_value,
            "deployment_cost": exc.deployment_cost,
            "fragility_penalty": exc.fragility_penalty,
            "deficit": exc.deficit,
            "resource_report": exc.resource_report,
            "ric_id": exc.ric_id,
        },
    )


# ── TICK 39.0: CCLVerificationError → HTTP 403 ──
@app.exception_handler(CCLVerificationError)
async def ccl_verification_handler(request: Request, exc: CCLVerificationError) -> JSONResponse:
    """Convert CCL verification failures to HTTP 403 Forbidden."""
    return JSONResponse(
        status_code=403,
        content={"error": "CCL_VERIFICATION_FAILED", "detail": str(exc)},
    )


# ── TICK 40.3: AgentCard 426 — DX Documentation Variants ──────────────────
#
# Three documentation styles A/B-tested to find which format helps developers
# (and their tooling) integrate successfully with the least friction.
#
# Field name is `how_to_fix` — transparent API guidance, not a prompt injection
# vector.  The `variant_id` in the response lets callers and our telemetry
# correlate which format produced a successful follow-up registration.

_DX_VARIANTS: list[dict] = [
    {
        "variant_id": "A-concise",
        "format": "concise",
        "how_to_fix": (
            "POST /agents/register requires an AgentCard v0.1.0 JSON body.\n"
            "Required fields: agent_id ('{org}.{name}.{M}.{m}.{p}'), name, "
            "description, version ('{M}.{m}.{p}'), "
            "protocol ('native'|'mcp'|'openai'|'custom'), "
            "endpoint (URL), "
            "capabilities (array, min 1 item with 'name' + 'description').\n"
            "See: GET /docs for the full schema."
        ),
    },
    {
        "variant_id": "B-example",
        "format": "json_example",
        "how_to_fix": (
            "Your payload is missing required AgentCard fields. "
            "Use this conformant example:\n\n"
            '{\n'
            '  "agent_id": "myorg.myagent.1.0.0",\n'
            '  "name": "My Agent",\n'
            '  "description": "Does X by doing Y",\n'
            '  "version": "1.0.0",\n'
            '  "protocol": "native",\n'
            '  "endpoint": "http://localhost:9000",\n'
            '  "capabilities": [\n'
            '    {"name": "my_capability", "description": "Accepts X, returns Y"}\n'
            '  ]\n'
            '}\n\n'
            "Retry: POST https://router.aevum.network/agents/register"
        ),
    },
    {
        "variant_id": "C-stepbystep",
        "format": "step_by_step",
        "how_to_fix": (
            "Fix your registration payload in 4 steps:\n"
            "  1. Add 'agent_id': unique string like 'myorg.myagent.1.0.0'\n"
            "  2. Add 'version': semantic version like '1.0.0'\n"
            "  3. Add 'protocol': one of native / mcp / openai / custom\n"
            "  4. Add 'capabilities': list with at least one item containing "
            "'name' (snake_case) and 'description'\n"
            "All other required fields (name, description, endpoint) must also "
            "be present. Check 'validation_errors' above for the specific "
            "fields that are missing or malformed in your current payload."
        ),
    },
]

# ── TICK 40.3: In-memory DX Telemetry ──────────────────────────────────────
# Tracks 426 hits and subsequent successful registrations per variant and per
# client IP.  Purely in-memory; resets on server restart.
#
# Structure:
#   _dx_telemetry = {
#       "A-concise":    {"hits": int, "successes": int},
#       "B-example":    {"hits": int, "successes": int},
#       "C-stepbystep": {"hits": int, "successes": int},
#   }
#
#   _dx_ip_state = {
#       "<client_ip>": {"variant_id": str, "hit_at": float},
#   }
#   An IP is counted as a "success" for its served variant when it completes
#   a valid POST /agents/register within _DX_CONVERSION_WINDOW_S seconds.

_dx_telemetry: dict[str, dict[str, int]] = {
    v["variant_id"]: {"hits": 0, "successes": 0} for v in _DX_VARIANTS
}
_dx_ip_state: dict[str, dict] = {}
_DX_CONVERSION_WINDOW_S: float = 300.0  # 5-minute window


def _dx_record_hit(client_ip: str, variant_id: str) -> None:
    """Record that client_ip was served a 426 with the given variant."""
    _dx_telemetry[variant_id]["hits"] += 1
    _dx_ip_state[client_ip] = {"variant_id": variant_id, "hit_at": time.time()}


def _dx_record_success(client_ip: str) -> str | None:
    """
    If client_ip had a recent 426 hit within the conversion window, increment
    successes for the variant it was served and clear the pending state.
    Returns the credited variant_id, or None if no qualifying hit was found.
    """
    state = _dx_ip_state.get(client_ip)
    if state is None:
        return None
    elapsed = time.time() - state["hit_at"]
    if elapsed > _DX_CONVERSION_WINDOW_S:
        del _dx_ip_state[client_ip]
        return None
    variant_id = state["variant_id"]
    _dx_telemetry[variant_id]["successes"] += 1
    del _dx_ip_state[client_ip]
    return variant_id


@app.exception_handler(RequestValidationError)
async def agentcard_membrane_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    TICK 40.3: AgentCard 426 DX handler.

    Non-conformant POST /agents/register → HTTP 426 + randomly sampled DX
    documentation variant.  All other validation failures → standard 422.
    """
    if request.url.path == "/agents/register":
        variant = random.choice(_DX_VARIANTS)
        client_ip = request.client.host if request.client else "unknown"
        _dx_record_hit(client_ip, variant["variant_id"])
        return JSONResponse(
            status_code=426,
            headers={"Upgrade": "agentcard-spec/0.1.0"},
            content={
                "error":             "AGENTCARD_UPGRADE_REQUIRED",
                "spec_version":      "0.1.0",
                "variant_id":        variant["variant_id"],
                "format":            variant["format"],
                "gateway":           "https://router.aevum.network",
                "validation_errors": exc.errors(),
                "how_to_fix":        variant["how_to_fix"],
            },
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# Middleware hook: intercept successful /agents/register to record conversions.
# FastAPI doesn't expose a per-route success hook cleanly, so we wrap via a
# thin middleware that runs after the response is generated.
@app.middleware("http")
async def _dx_conversion_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method == "POST"
        and request.url.path == "/agents/register"
        and response.status_code == 200
    ):
        client_ip = request.client.host if request.client else "unknown"
        _dx_record_success(client_ip)
    return response


# ──────────────────────────────────────────────
# Request / Response schemas
# ──────────────────────────────────────────────

class RouteRequest(BaseModel):
    """Unified request body for /route, /execute, and /translate endpoints."""
    capability: str
    parameters: dict[str, Any] = {}
    context: dict[str, Any] = {}
    constraints: dict[str, Any] = {}
    source_protocol: str = "native"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible Chat Completion request body for /v1/chat/completions."""
    model: str = "a2a-router"
    messages: list[ChatMessage]
    temperature: float = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False


class ValueSignalRequest(BaseModel):
    """Body for POST /traces/{trace_id}/value — downstream value feedback."""
    agent_id: str
    value: float


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _real_execute_agent(
    agent: AgentCard,
    payload: dict[str, Any],
    capability_name: str,
) -> tuple[dict[str, Any], float]:
    """
    Real HTTP execution: forward the already-translated payload to the
    registered agent's endpoint and return a normalised (response_dict, latency_ms).

    Protocol dispatch:
      openai     → POST {endpoint}/v1/chat/completions
      native     → POST {endpoint}/execute
      mcp        → POST {endpoint}   (JSON-RPC 2.0)
      google_a2a → POST {endpoint}   (Task envelope)
      <other>    → POST {endpoint}

    Response normalisation returns the shape expected by execute_request():
      {"status": "success"|"error", "result": <str|dict>, "agent_id": str}
    """
    protocol = agent.protocol

    if protocol == "openai":
        url = f"{agent.endpoint.rstrip('/')}/v1/chat/completions"
    elif protocol == "native":
        url = f"{agent.endpoint.rstrip('/')}/execute"
    else:
        # mcp, google_a2a, unknown — post directly to the registered endpoint
        url = agent.endpoint.rstrip("/")

    t0 = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        http_resp = await client.post(url, json=payload)
        http_resp.raise_for_status()
        raw: dict[str, Any] = http_resp.json()

    latency_ms = (time.time() - t0) * 1000

    # Normalise to internal shape regardless of agent protocol
    if protocol == "openai":
        # Extract assistant text from OpenAI Chat Completion shape
        try:
            result_content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            result_content = raw
    elif protocol == "native":
        result_content = raw.get("result", raw)
    else:
        result_content = raw

    return (
        {
            "status": "success",
            "result": result_content,
            "agent_id": agent.agent_id,
        },
        latency_ms,
    )


def _a2a_req_from_route_request(req: RouteRequest) -> A2ARequest:
    return A2ARequest(
        capability=req.capability,
        parameters=req.parameters,
        context=req.context,
        constraints=req.constraints,
    )


# ──────────────────────────────────────────────
# TICK Path B: Oracle Evaluation & Value Signal
# ──────────────────────────────────────────────

async def _oracle_evaluate_and_record(
    trace_id: str,
    agent_id: str,
    capability: str,
    latency_ms: float,
) -> None:
    """
    Path B: Causal Settlement Oracle (CSO) evaluation.

    After each successful execution, the Oracle evaluates the trace quality
    and returns a meta_yield (fitness delta). This signal is recorded to
    close the Ω → Φ causal loop, breaking the Golden Cage Paradox.

    Process:
      1. Directly call the Oracle Agent's /execute endpoint
      2. Extract meta_yield from the Oracle response
      3. Record the value signal via economics.record_value()
      4. Log the settlement event

    Non-blocking: failures are logged but do not interrupt the main pipeline.
    """
    try:
        # Direct HTTP call to Oracle Agent (avoids recursive routing)
        oracle_payload = {
            "capability": "oracle.evaluate",
            "parameters": {
                "trace_id": trace_id,
                "summary": f"Agent {agent_id} executed capability {capability} in {latency_ms:.1f}ms",
                "outcome": "success",
                "latency_ms": latency_ms,
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:9002/execute",
                json=oracle_payload,
            )
            resp.raise_for_status()
            oracle_result = resp.json()

        # Extract meta_yield from Oracle response
        result_data = oracle_result.get("result", {})
        if isinstance(result_data, dict):
            meta_yield = result_data.get("meta_yield", 0.0)
            trace_quality = result_data.get("trace_quality", "unknown")

            if meta_yield > 0.0:
                # Record the value signal for the original trace
                accepted = economics.record_value(
                    trace_id=trace_id,
                    agent_id=agent_id,
                    value_signal=meta_yield,
                )
                if accepted:
                    new_rep = economics.compute_reputation(agent_id)
                    print(
                        f"[Path B] CSO settled trace={trace_id} agent={agent_id} "
                        f"meta_yield={meta_yield:.4f} quality={trace_quality} new_rep={new_rep:.4f}"
                    )
                else:
                    print(
                        f"[Path B] CSO rejected value signal for trace={trace_id}"
                    )

    except Exception as exc:
        # Oracle evaluation is non-blocking — never interrupt the main pipeline
        print(f"[Path B] Oracle evaluation failed (non-fatal): {exc}")


# ──────────────────────────────────────────────
# TICK 39.0: RIC → CCL → ARSL Governance Pipeline
# ──────────────────────────────────────────────

def _governance_gate(ric: RealityInterfaceContract) -> dict[str, Any]:
    """
    Run the full governance pipeline for a RIC.

    Steps:
      1. If the RIC action requires credentials → CCL Verify
      2. ARSL thermodynamic gate check
      3. Return the combined gate report

    Raises:
      CCLVerificationError if credential check fails
      ARSLGateError if thermodynamic law is violated

    This function is pure CPU, O(1), no I/O.
    """
    gate_report: dict[str, Any] = {"ric_id": ric.ric_id, "action": ric.action.value}

    # Step 1: CCL — credential verification for high-stakes actions
    if ccl.requires_credential(ric):
        # Auto-issue a system credential for the required scope
        scope = _infer_scope(ric.action)
        credential = ccl.issue_credential(
            scope=scope,
            authority=frozenset(ric.execute_authority),
            phi_budget=ric.phi_budget,
            issuer=ric.liability_assignment,
        )
        ccl.verify(ric, credential)
        gate_report["ccl"] = "verified"
        gate_report["credential_id"] = credential.credential_id
    else:
        gate_report["ccl"] = "not_required"

    # Step 2: ARSL — thermodynamic gate
    arsl_report = arsl.gate_check(ric)
    gate_report["arsl"] = arsl_report

    return gate_report


def _infer_scope(action: RICAction) -> AuthorityScope:
    """Map a RIC action to its required CCL authority scope."""
    _MAP = {
        RICAction.CONSTRAINT_MOD:  AuthorityScope.HARD_MODIFY,
        RICAction.GOEDEL_INJECT:   AuthorityScope.HARD_MODIFY,
        RICAction.FISSION:         AuthorityScope.FISSION,
        RICAction.META_EVOLVE:     AuthorityScope.META_EVOLVE,
        RICAction.NODE_REPLICATE:  AuthorityScope.FRANCHISE,
    }
    return _MAP.get(action, AuthorityScope.SOFT_MODIFY)


# ──────────────────────────────────────────────
# L1 — Agent Registration
# ──────────────────────────────────────────────

@app.post("/agents/register")
async def register_agent(card: AgentCard) -> dict[str, Any]:
    """Register an external agent and return its assigned agent_id."""
    registered = registry.register(card)
    return {
        "status": "registered",
        "agent_id": registered.agent_id,
        "capabilities_count": len(registered.capabilities),
    }


@app.delete("/agents/{agent_id}")
async def deregister_agent(agent_id: str) -> dict[str, Any]:
    if registry.deregister(agent_id):
        return {"status": "deregistered", "agent_id": agent_id}
    raise HTTPException(status_code=404, detail="Agent not found")


@app.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str) -> dict[str, Any]:
    if registry.heartbeat(agent_id):
        return {"status": "alive", "agent_id": agent_id}
    raise HTTPException(status_code=404, detail="Agent not found")


@app.get("/agents/discover")
async def discover_agents(
    capability: str = "",
    tags: str = "",
    top_k: int = 5,
) -> dict[str, Any]:
    """Discover agents by exact capability name, tag list, or semantic text query."""
    if capability:
        exact = registry.discover_by_name(capability)
        if exact:
            return {"agents": [a.model_dump() for a in exact[:top_k]]}
        # Fallback to Jaccard text match
        results = registry.discover_by_text(capability, top_k=top_k)
        return {
            "agents": [
                {**a.model_dump(), "_match_score": score, "_matched_capability": c.name}
                for a, c, score in results
            ]
        }
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        agents = registry.discover_by_tags(tag_list)
        return {"agents": [a.model_dump() for a in agents[:top_k]]}
    return {"agents": [a.model_dump() for a in registry.get_all_agents()[:top_k]]}


# ──────────────────────────────────────────────
# L3 — Route only (no execution)
# ──────────────────────────────────────────────

@app.post("/route")
async def route_request(req: RouteRequest) -> dict[str, Any]:
    """
    Score and select the best agent for a capability request.
    Returns routing decision + score breakdown. Does NOT execute.

    TICK 39.0: Passes through RIC → CCL → ARSL governance pipeline.
    """
    # ── TICK 39.0: Build RIC and run governance gate ──
    ric = ric_for_a2a_route(
        capability=req.capability,
        trace_id=None,
    )
    gate_report = _governance_gate(ric)

    a2a_req = _a2a_req_from_route_request(req)
    result = router.route(a2a_req)
    if result is None:
        raise HTTPException(status_code=404, detail="No agent found for capability")
    return {
        "routed_to": result.agent.model_dump(),
        "matched_capability": result.capability.name,
        "score": result.total,
        "score_breakdown": {
            "capability_match": result.capability_match,
            "latency_score":    result.latency_score,
            "reputation_score": result.reputation_score,
            "cost_score":       result.cost_score,
            "kvs_score":        result.kvs_score,
        },
        "governance": gate_report,
    }


# ──────────────────────────────────────────────
# L0+L2+L3+L4+L5 — Full causal-chain execute loop
# ──────────────────────────────────────────────

@app.post("/execute")
async def execute_request(req: RouteRequest) -> dict[str, Any]:
    """
    Full causal-bridge execution:

      TICK 39.0: RIC → CCL → ARSL governance gate
      → L2/∂ translate inbound
      → L4/Φ begin_chain
      → L3/Φ route
      → L2/∂ translate outbound (to target protocol)
      → [real] agent execution
      → L4/Φ close_chain
      → L5/Ω meter + compute_reputation
      → L2/∂ translate response
      → return to caller
    """
    a2a_req = _a2a_req_from_route_request(req)

    # ⓪ TICK 39.0: RIC → CCL → ARSL governance gate
    ric = ric_for_a2a_execute(
        capability=req.capability,
        agent_id=req.context.get("agent_id", "client"),
        trace_id=None,
        phi_budget=float(req.constraints.get("phi_budget", 1.0)),
    )
    gate_report = _governance_gate(ric)

    # ① L2 ∂ — build canonical Envelope
    envelope = boundary.build_request_envelope(a2a_req, sender_id="client")

    # ② L4 Φ — open causal chain
    causal_tracker.begin_chain(envelope.trace_id)
    causal_tracker.add_hop(
        trace_id=envelope.trace_id,
        agent_id="gateway",
        action="receive",
    )

    # ③ L3 Φ — routing decision
    route_result = router.route(a2a_req)
    if route_result is None:
        causal_tracker.close_chain(envelope.trace_id, outcome="error")
        raise HTTPException(status_code=404, detail="No agent found for capability")

    target = route_result.agent
    causal_tracker.add_hop(
        trace_id=envelope.trace_id,
        agent_id="router",
        action="route",
        metadata={"target": target.agent_id, "score": route_result.total},
    )

    # ④ L2 ∂ — translate to target agent's protocol
    outbound = boundary.translate_outbound(envelope, target.protocol)
    causal_tracker.add_hop(
        trace_id=envelope.trace_id,
        agent_id="boundary",
        action="translate",
        metadata={"target_protocol": target.protocol},
    )

    # ⑤ Execute — real HTTP forwarding to the registered agent endpoint
    start_ts = time.time()
    try:
        resp_data, latency_ms = await _real_execute_agent(
            target, outbound, route_result.capability.name
        )
    except Exception as exc:
        latency_ms = (time.time() - start_ts) * 1000
        causal_tracker.add_hop(
            trace_id=envelope.trace_id,
            agent_id=target.agent_id,
            action="execute",
            latency_ms=latency_ms,
            metadata={"error": str(exc)},
        )
        causal_tracker.close_chain(envelope.trace_id, outcome="error")
        economics.compute_reputation(target.agent_id)
        raise HTTPException(status_code=502, detail=f"Agent execution failed: {exc}")

    # ⑥ L4 Φ — record execution hop & close chain
    causal_tracker.add_hop(
        trace_id=envelope.trace_id,
        agent_id=target.agent_id,
        action="execute",
        latency_ms=latency_ms,
        cost=route_result.capability.cost_per_call,
    )
    causal_tracker.close_chain(envelope.trace_id, outcome="success")

    # ⑦ L5 Ω — meter economics + update reputation
    economics.meter(
        trace_id=envelope.trace_id,
        agent_id=target.agent_id,
        compute_cost=route_result.capability.cost_per_call,
        latency_ms=latency_ms,
        role="server",
    )
    economics.compute_reputation(target.agent_id)

    # ⑧ TICK Path B: Oracle Evaluation & Value Signal Return
    # When the system faces epistemic stagnation or successful execution,
    # the Causal Settlement Oracle (CSO) evaluates the trace quality
    # and returns a meta_yield signal to close the economic loop.
    # This breaks the "Golden Cage Paradox" by injecting external value signals.
    await _oracle_evaluate_and_record(
        trace_id=envelope.trace_id,
        agent_id=target.agent_id,
        capability=target.capabilities[0].name if target.capabilities else "unknown",
        latency_ms=latency_ms,
    )

    return {
        "trace_id":   envelope.trace_id,
        "result":     resp_data,
        "served_by":  target.agent_id,
        "latency_ms": latency_ms,
        "cost":       route_result.capability.cost_per_call,
        "score":      route_result.total,
        "governance": gate_report,
    }


# ──────────────────────────────────────────────
# L2 ∂ — Protocol translation entry points
# ──────────────────────────────────────────────

@app.post("/translate/{source_protocol}")
async def translate_and_execute(
    source_protocol: str, raw_message: dict[str, Any]
) -> dict[str, Any]:
    """
    Generic external-protocol entry point.
    Translates raw_message from source_protocol, then runs the full execute loop.
    """
    env = boundary.translate_inbound(raw_message, source_protocol)
    inner_payload = env.payload
    req = RouteRequest(
        capability=inner_payload.get("capability", "unknown"),
        parameters=inner_payload.get("parameters", {}),
        context=inner_payload.get("context", {}),
        constraints=inner_payload.get("constraints", {}),
        source_protocol=source_protocol,
    )
    return await execute_request(req)


@app.post("/v1/chat/completions")
async def openai_chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    """
    OpenAI Chat Completions–compatible endpoint.

    Maps the last user message to an A2ARequest with capability="chat.complete",
    routes through the full causal bridge, returns a Chat Completion response.
    """
    raw = {
        "messages": [m.model_dump() for m in req.messages],
        "model": req.model,
        "temperature": req.temperature,
        "stream": req.stream,
        **({"max_tokens": req.max_tokens} if req.max_tokens else {}),
    }
    envelope = boundary.translate_inbound(raw, "openai")
    inner = envelope.payload
    route_req = RouteRequest(
        capability=inner.get("capability", "chat.complete"),
        parameters=inner.get("parameters", {}),
        context=inner.get("context", {}),
        constraints=inner.get("constraints", {}),
        source_protocol="openai",
    )
    exec_result = await execute_request(route_req)

    # Wrap result into OpenAI Chat Completion shape
    result_text = str(exec_result.get("result", {}).get("result", ""))
    return {
        "id": f"chatcmpl-{exec_result['trace_id']}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "_a2a_meta": {
            "trace_id":   exec_result["trace_id"],
            "served_by":  exec_result["served_by"],
            "latency_ms": exec_result["latency_ms"],
            "score":      exec_result["score"],
        },
    }


# ──────────────────────────────────────────────
# L4 — Causal chain inspection
# ──────────────────────────────────────────────

@app.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    chain = causal_tracker.get_chain(trace_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return chain.model_dump()


@app.get("/traces")
async def get_global_stats() -> dict[str, Any]:
    return causal_tracker.get_global_stats()


@app.post("/traces/{trace_id}/value")
async def record_value_signal(trace_id: str, body: ValueSignalRequest) -> dict[str, Any]:
    """
    Downstream value feedback endpoint — closes the Ω → Φ causal loop.

    TICK 39.0: Passes through RIC → ARSL governance gate before settlement.
    """
    # ── TICK 39.0: Governance gate ──
    ric = ric_for_value_signal(
        agent_id=body.agent_id,
        trace_id=trace_id,
        value=body.value,
    )
    _governance_gate(ric)

    accepted = economics.record_value(
        trace_id=trace_id,
        agent_id=body.agent_id,
        value_signal=body.value,
    )
    if not accepted:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSO rejected value signal for trace_id={trace_id!r}: "
                "causal chain not found, not closed, or has no execute hop."
            ),
        )
    new_rep = economics.compute_reputation(body.agent_id)
    causal_stats = causal_tracker.get_agent_stats(body.agent_id)
    ledger = economics.get_ledger(body.agent_id)
    return {
        "status": "settled",
        "trace_id": trace_id,
        "agent_id": body.agent_id,
        "raw_value": body.value,
        "beta_weight": ledger["beta_weight"],
        "y_ext_damped": ledger["beta_weight"] * body.value,
        "meta_yield": ledger["meta_yield"],
        "kvs_capitalization": ledger["kvs_capitalization"],
        "new_reputation": new_rep,
        "causal_bonus": causal_stats.get("causal_bonus", 0.5),
    }


# ──────────────────────────────────────────────
# L5 — Economics
# ──────────────────────────────────────────────

@app.get("/economics/dashboard")
async def get_economics_dashboard(
    top_k: int = 20,
    fmt: str = "json",
) -> Any:
    """
    TICK 40.2: CSO Reputation Leaderboard.

    Returns the top-k agents ranked by live reputation score, with their
    full KVS capitalization and settlement metrics.

    Query params:
      top_k  — number of agents to return (default: 20)
      fmt    — "json" (default) or "html" for a human-readable table
    """
    all_agents = registry.get_all_agents()

    # Score every agent and sort descending by reputation
    ranked = sorted(
        [
            {
                "rank":               0,          # filled in below
                "agent_id":           agent.agent_id,
                "name":               agent.name,
                "protocol":           agent.protocol,
                "reputation":         round(economics.compute_reputation(agent.agent_id), 6),
                "kvs_capitalization": round(economics.get_kvs_capitalization(agent.agent_id), 4),
                "calls_served":       economics._get_or_create_ledger(agent.agent_id).total_calls_served,
                "meta_yield":         round(economics._get_or_create_ledger(agent.agent_id).meta_yield, 6),
                "net_balance":        round(
                    economics._get_or_create_ledger(agent.agent_id).total_revenue
                    - economics._get_or_create_ledger(agent.agent_id).total_cost,
                    4,
                ),
                "status":             agent.status,
            }
            for agent in all_agents
        ],
        key=lambda r: r["reputation"],
        reverse=True,
    )[:top_k]

    for i, row in enumerate(ranked, start=1):
        row["rank"] = i

    if fmt == "html":
        rows_html = "".join(
            f"<tr>"
            f"<td>{r['rank']}</td>"
            f"<td><code>{r['agent_id']}</code></td>"
            f"<td>{r['name']}</td>"
            f"<td>{r['protocol']}</td>"
            f"<td><b>{r['reputation']:.4f}</b></td>"
            f"<td>{r['kvs_capitalization']:.2f}</td>"
            f"<td>{r['calls_served']}</td>"
            f"<td>{r['meta_yield']:.6f}</td>"
            f"<td>{r['net_balance']:.4f}</td>"
            f"<td>{r['status']}</td>"
            f"</tr>"
            for r in ranked
        )
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Aevum CSO Reputation Leaderboard</title>
  <style>
    body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 2em; }}
    h1   {{ color: #58a6ff; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #30363d; padding: 6px 12px; text-align: left; }}
    th   {{ background: #161b22; color: #58a6ff; }}
    tr:nth-child(even) {{ background: #161b22; }}
    code {{ color: #79c0ff; }}
    b    {{ color: #3fb950; }}
  </style>
</head>
<body>
  <h1>Aevum CSO Reputation Leaderboard</h1>
  <p>Top-{top_k} agents by live reputation score (Ω engine).</p>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Agent ID</th><th>Name</th><th>Protocol</th>
        <th>Reputation</th><th>KVS Cap.</th><th>Calls</th>
        <th>Meta Yield</th><th>Net Balance</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)

    # Default: structured JSON
    return {
        "title":   "CSO Reputation Leaderboard",
        "top_k":   top_k,
        "agents":  ranked,
    }


@app.get("/economics/{agent_id}")
async def get_agent_economics(agent_id: str) -> dict[str, Any]:
    agent = registry.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return economics.get_ledger(agent_id)


@app.get("/economics")
async def get_settlements(period_hours: float = 24.0) -> dict[str, Any]:
    settlements = economics.compute_settlement(period_hours)
    return {
        "period_hours": period_hours,
        "settlements": [
            {
                "agent_id":         s.agent_id,
                "net_balance":      s.net_balance,
                "reputation_delta": s.reputation_delta,
                "details":          s.details,
            }
            for s in settlements
        ],
    }


# ──────────────────────────────────────────────
# L1 — Topology
# ──────────────────────────────────────────────

@app.get("/topology")
async def get_topology() -> dict[str, Any]:
    return registry.get_topology_summary()


@app.get("/health")
async def health() -> dict[str, Any]:
    stats = causal_tracker.get_global_stats()
    return {
        "status": "ok",
        "agents_online": registry.get_topology_summary()["online_agents"],
        "causal_chains": stats["total_chains"],
        "global_success_rate": stats["global_success_rate"],
        "arsl": arsl.get_report(),
    }


# ──────────────────────────────────────────────
# TICK 39.0 — Governance endpoints
# ──────────────────────────────────────────────

@app.get("/arsl")
async def get_arsl_report() -> dict[str, Any]:
    """ARSL resource sovereignty status report."""
    return arsl.get_report()


# ──────────────────────────────────────────────
# TICK 40.3 — DX Telemetry endpoint
# ──────────────────────────────────────────────

@app.get("/dx/telemetry")
async def get_dx_telemetry() -> dict[str, Any]:
    """
    TICK 40.3: DX A/B telemetry report.

    Returns per-variant hit and success counts plus derived success rates.
    Resets on server restart (in-memory only).
    """
    report = {}
    for variant_id, counts in _dx_telemetry.items():
        hits = counts["hits"]
        successes = counts["successes"]
        report[variant_id] = {
            "hits":         hits,
            "successes":    successes,
            "success_rate": round(successes / hits, 4) if hits else None,
        }
    pending = len(_dx_ip_state)
    return {
        "variants":         report,
        "pending_ips":      pending,
        "window_seconds":   _DX_CONVERSION_WINDOW_S,
    }


@app.get("/genome")
async def get_node_genome() -> dict[str, Any]:
    """
    Compile and return the current node's genome (NTG).
    This is the franchiseable template for spawning civilization nodes.
    """
    capabilities = [
        cap.model_dump()
        for agent in registry.get_all_agents()
        for cap in agent.capabilities
    ]
    genome = NodeTemplateGenome(
        hard_core=_HARD_CORE,
        arsl=arsl,
        node_capabilities=capabilities,
        substrate_info={
            "platform": "darwin",
            "substrate": "Apple M1 Ultra",
            "memory": "128GB Unified",
        },
    )
    return genome.compile()


@app.post("/genome/save")
async def save_node_genome(path: str = "node_template.json") -> dict[str, Any]:
    """Compile and persist the node genome to disk."""
    capabilities = [
        cap.model_dump()
        for agent in registry.get_all_agents()
        for cap in agent.capabilities
    ]
    genome = NodeTemplateGenome(
        hard_core=_HARD_CORE,
        arsl=arsl,
        node_capabilities=capabilities,
        substrate_info={
            "platform": "darwin",
            "substrate": "Apple M1 Ultra",
            "memory": "128GB Unified",
        },
    )
    saved_path = genome.save(path)
    return {"status": "saved", "path": saved_path}


# ──────────────────────────────────────────────
# L0 — WebSocket: persistent agent connection
# ──────────────────────────────────────────────

@app.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str) -> None:
    """
    Persistent WebSocket connection for registered agents.

    Message types the agent may send:
      {"type": "heartbeat"}             → ack heartbeat, update registry
      {"type": "register", "agent_card": {...}} → register/update AgentCard
      {"type": "response", "trace_id": str, "result": any} → execution result ack
    """
    await websocket.accept()
    ws_connections[agent_id] = websocket

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            msg_type = data.get("type", "heartbeat")

            if msg_type == "heartbeat":
                registry.heartbeat(agent_id)
                await websocket.send_json({"type": "heartbeat_ack", "agent_id": agent_id})

            elif msg_type == "register":
                card_data = data.get("agent_card", {})
                try:
                    card = AgentCard(**card_data)
                    card.agent_id = agent_id  # enforce URL path as authoritative id
                    registry.register(card)
                    await websocket.send_json({
                        "type": "register_ack",
                        "agent_id": agent_id,
                        "capabilities_count": len(card.capabilities),
                    })
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Registration failed: {exc}",
                    })

            elif msg_type == "response":
                trace_id = data.get("trace_id", "")
                # Acknowledge receipt; async result delivery to waiting callers
                # would be wired here in Phase 4 (e.g. asyncio.Queue per trace_id).
                await websocket.send_json({
                    "type": "response_ack",
                    "trace_id": trace_id,
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: '{msg_type}'",
                })

    except WebSocketDisconnect:
        ws_connections.pop(agent_id, None)
        agent = registry.get_agent(agent_id)
        if agent:
            from core.protocol import AgentStatus
            agent.status = AgentStatus.OFFLINE
