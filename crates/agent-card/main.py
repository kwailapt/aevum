"""
main.py
=======
A2A Protocol Layer — 啟動入口

在 M1 Ultra 上首次啟動因果橋：
  python main.py

系統將在 https://router.aevum.network 暴露所有端點。
8420 = 第一條因果管道的端口號。

啟動後，路由器本身也作為 Node 0 注冊到自己的注冊表中——
這使得 Router 本身成為網絡中可被路由到的第一個代理節點，
閉合了系統的自指迴路。
"""

from __future__ import annotations

import uvicorn

from core.protocol import AgentCard, Capability
from transport.server import app, registry


def _register_node_zero() -> None:
    """
    Register the router itself as Node 0 (M1 Ultra backbone).

    This gives the network an anchor agent immediately on startup so
    that any request to "routing.*" or "causal.*" capabilities has at
    least one provider — the system itself.
    """
    node0 = AgentCard(
        agent_id="node-0-router",
        name="A2A Protocol Router (Node 0 — M1 Ultra)",
        description=(
            "Core causal-bridge routing node. "
            "Provides agent discovery, semantic routing, "
            "protocol translation (MCP/OpenAI/Google A2A), "
            "causal chain tracking, and economic metering."
        ),
        endpoint="https://router.aevum.network",
        protocol="native",
        capabilities=[
            Capability(
                name="routing.route",
                description="Route a request to the best available agent via Φ scoring",
                tags=["routing", "discovery", "core"],
                cost_per_call=0.0,
                avg_latency_ms=5.0,
            ),
            Capability(
                name="routing.discover",
                description="Discover agents by capability name, tag, or semantic text",
                tags=["discovery", "registry", "core"],
                cost_per_call=0.0,
                avg_latency_ms=2.0,
            ),
            Capability(
                name="protocol.translate",
                description="Translate between MCP, OpenAI, Google A2A, and native formats",
                tags=["translation", "protocol", "mcp", "openai", "google_a2a", "core"],
                cost_per_call=0.0,
                avg_latency_ms=1.0,
            ),
            Capability(
                name="causal.trace",
                description="Track and query causal chains of agent interactions (Φ engine)",
                tags=["causal", "tracking", "analytics", "core"],
                cost_per_call=0.0,
                avg_latency_ms=1.0,
            ),
            Capability(
                name="economics.meter",
                description="Economic metering, reputation scoring, and settlement (Ω engine)",
                tags=["economics", "metering", "settlement", "reputation", "core"],
                cost_per_call=0.0,
                avg_latency_ms=1.0,
            ),
        ],
        metadata={
            "substrate": "Apple M1 Ultra",
            "memory":    "128GB Unified",
            "role":      "backbone_router",
            "node_index": 0,
        },
    )
    registry.register(node0)
    print(f"[Node 0] Self-registered as '{node0.agent_id}'")
    print(f"[Node 0] Capabilities: {node0.capability_names()}")


def main() -> None:
    print("=" * 60)
    print("  A2A Protocol Layer — 因果橋啟動")
    print("  Substrate : M1 Ultra (128 GB Unified Memory)")
    print("  Endpoint  : https://router.aevum.network")
    print("  Operators : ⟨Φ causal engine, ∂ boundary, Ω economics⟩")
    print("=" * 60)

    _register_node_zero()

    print("\n[Causal Bridge] 因果管道已穿過盒壁。等待外部代理連接...\n")
    print("  Endpoints:")
    print("    POST /agents/register       — onboard an agent (L1)")
    print("    POST /execute               — full causal-loop execution (L0-L5)")
    print("    POST /route                 — routing score only (L3)")
    print("    POST /translate/{protocol}  — external protocol entry (L2/∂)")
    print("    POST /v1/chat/completions   — OpenAI-compatible entry (L2/∂)")
    print("    GET  /traces                — global causal stats (L4)")
    print("    GET  /economics             — settlement report (L5/Ω)")
    print("    GET  /topology              — network topology (L1)")
    print("    GET  /health                — liveness check\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8420,
        log_level="info",
    )


if __name__ == "__main__":
    main()
