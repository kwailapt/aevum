"""
test_tick41_5_mcp.py
====================
Meta-TDD verification for TICK 41.5 — Aevum MCP Interoperability Adapter.

Tests (all run in-process with mocked httpx; no live server required):
  1. Module-level: constants exported correctly
  2. tools/list: returns all 3 tools with correct names and inputSchema
  3. initialize: correct protocolVersion + serverInfo
  4. ping: returns empty result
  5. discover_agents: proxies GET /agents/discover, stamps interop signature
  6. route_task: proxies POST /execute, stamps interop signature
  7. route_task missing capability: returns isError=True without HTTP call
  8. route_task: ConnectError returns graceful isError message
  9. check_reputation with agent_id: proxies GET /economics/{agent_id}
 10. check_reputation without agent_id: proxies GET /economics/dashboard
 11. tools/call unknown tool: JSON-RPC error -32601
 12. unknown method: JSON-RPC error -32601
 13. Notification (no id): returns None (no response emitted)
 14. DX signature present in every successful tool response
 15. FastAPI mount: POST /mcp endpoint responds to tools/list
 16. FastAPI mount: GET /mcp/info returns adapter metadata

Usage:
    python test_tick41_5_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Volumes/Aevum/Obsidian/Opus_agi")
sys.path.insert(0, "/Volumes/Aevum/Obsidian/Opus_agi/ai2ai")

# ── Test harness ──────────────────────────────────────────────────────────────

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    msg = f"{tag} {name}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    _results.append((name, condition, detail))
    return condition


# ── Import the adapter ────────────────────────────────────────────────────────

from transport.mcp_adapter import (
    AevumMCPServer,
    _INTEROP_SIGNATURE,
    _MCP_VERSION,
    _TOOLS,
    mount_on_fastapi,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(coro):
    """Execute a coroutine synchronously in tests."""
    return asyncio.run(coro)


def make_server(hub: str = "http://testhost:9999") -> AevumMCPServer:
    return AevumMCPServer(hub_url=hub)


def _mock_http_get(payload: dict[str, Any]):
    """Return an async context-manager mock for httpx.AsyncClient.get()."""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)

    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _mock_http_post(payload: dict[str, Any]):
    """Return an async context-manager mock for httpx.AsyncClient.post()."""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Module-level constants
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 1: Module constants ──")

check("T1.a: _MCP_VERSION is 2024-11-05", _MCP_VERSION == "2024-11-05",
      f"got={_MCP_VERSION}")
check("T1.b: _INTEROP_SIGNATURE non-empty", len(_INTEROP_SIGNATURE) > 50)
check("T1.c: _INTEROP_SIGNATURE contains 'agentcard-spec'",
      "agentcard-spec" in _INTEROP_SIGNATURE)
check("T1.d: _INTEROP_SIGNATURE contains 'PCES'",
      "PCES" in _INTEROP_SIGNATURE)
check("T1.e: _TOOLS has 3 entries", len(_TOOLS) == 3)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — tools/list
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 2: tools/list ──")

srv = make_server()
resp = run(srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
tool_names = [t["name"] for t in resp["result"]["tools"]]

check("T2.a: response has result.tools",
      "tools" in resp.get("result", {}))
check("T2.b: discover_agents present", "discover_agents" in tool_names,
      f"names={tool_names}")
check("T2.c: route_task present", "route_task" in tool_names)
check("T2.d: check_reputation present", "check_reputation" in tool_names)
check("T2.e: all tools have inputSchema",
      all("inputSchema" in t for t in resp["result"]["tools"]))
check("T2.f: all tools have description",
      all(t.get("description") for t in resp["result"]["tools"]))

# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — initialize
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 3: initialize handshake ──")

init_resp = run(srv.handle_request({
    "jsonrpc": "2.0", "id": 0,
    "method": "initialize",
    "params": {"protocolVersion": _MCP_VERSION, "clientInfo": {"name": "test"}},
}))
result = init_resp.get("result", {})

check("T3.a: protocolVersion matches",
      result.get("protocolVersion") == _MCP_VERSION,
      f"got={result.get('protocolVersion')}")
check("T3.b: serverInfo.name is aevum-mcp-adapter",
      result.get("serverInfo", {}).get("name") == "aevum-mcp-adapter")
check("T3.c: serverInfo.hub_url present",
      "hub_url" in result.get("serverInfo", {}))
check("T3.d: capabilities.tools present",
      "tools" in result.get("capabilities", {}))

# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — ping
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 4: ping ──")

ping_resp = run(srv.handle_request({"jsonrpc": "2.0", "id": 99, "method": "ping"}))
check("T4.a: ping returns empty result", ping_resp.get("result") == {},
      f"result={ping_resp.get('result')}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — discover_agents tool
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 5: discover_agents tool ──")

fake_agents = {"agents": [{"agent_id": "org.test.1.0.0", "name": "Test Agent"}]}

with patch("httpx.AsyncClient", return_value=_mock_http_get(fake_agents)):
    disc_resp = run(srv.handle_request({
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/call",
        "params": {
            "name": "discover_agents",
            "arguments": {"capability": "chat.complete", "top_k": 3},
        },
    }))

disc_content = disc_resp["result"]["content"][0]["text"]
disc_data = json.loads(disc_content)

check("T5.a: isError=False", disc_resp["result"]["isError"] is False)
check("T5.b: agents list present", "agents" in disc_data,
      f"keys={list(disc_data.keys())}")
check("T5.c: _aevum_interop injected", "_aevum_interop" in disc_data)
check("T5.d: interop contains 'PCES'", "PCES" in disc_data["_aevum_interop"])

# ══════════════════════════════════════════════════════════════════════════════
# TEST 6 — route_task tool (success path)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 6: route_task tool (success) ──")

fake_execute = {
    "trace_id": "abc123",
    "result": {"status": "success", "result": "42"},
    "served_by": "org.agent.1.0.0",
    "latency_ms": 55.0,
    "score": 0.88,
}

with patch("httpx.AsyncClient", return_value=_mock_http_post(fake_execute)):
    route_resp = run(srv.handle_request({
        "jsonrpc": "2.0", "id": 3,
        "method": "tools/call",
        "params": {
            "name": "route_task",
            "arguments": {
                "capability": "chat.complete",
                "parameters": {"prompt": "hello"},
            },
        },
    }))

route_content = json.loads(route_resp["result"]["content"][0]["text"])

check("T6.a: isError=False", route_resp["result"]["isError"] is False)
check("T6.b: trace_id present", "trace_id" in route_content,
      f"keys={list(route_content.keys())}")
check("T6.c: served_by present", "served_by" in route_content)
check("T6.d: _aevum_interop injected", "_aevum_interop" in route_content)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 7 — route_task missing capability
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 7: route_task missing capability ──")

missing_resp = run(srv.handle_request({
    "jsonrpc": "2.0", "id": 4,
    "method": "tools/call",
    "params": {"name": "route_task", "arguments": {}},
}))

check("T7.a: isError=True for missing capability",
      missing_resp["result"]["isError"] is True)
check("T7.b: error text mentions discover_agents",
      "discover_agents" in missing_resp["result"]["content"][0]["text"])

# ══════════════════════════════════════════════════════════════════════════════
# TEST 8 — route_task ConnectError
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 8: route_task ConnectError ──")

import httpx

connect_client = AsyncMock()
connect_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
connect_client.__aenter__ = AsyncMock(return_value=connect_client)
connect_client.__aexit__ = AsyncMock(return_value=False)

with patch("httpx.AsyncClient", return_value=connect_client):
    conn_resp = run(srv.handle_request({
        "jsonrpc": "2.0", "id": 5,
        "method": "tools/call",
        "params": {
            "name": "route_task",
            "arguments": {"capability": "chat.complete"},
        },
    }))

conn_text = conn_resp["result"]["content"][0]["text"]
check("T8.a: isError=True on ConnectError",
      conn_resp["result"]["isError"] is True)
check("T8.b: error mentions 'uvicorn'", "uvicorn" in conn_text,
      f"text={conn_text[:120]}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 9 — check_reputation with agent_id
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 9: check_reputation with agent_id ──")

fake_ledger = {
    "agent_id": "org.agent.1.0.0",
    "reputation": 0.73,
    "meta_yield": 0.42,
    "beta_weight": 0.028,
    "deformation_count": 1,
}

with patch("httpx.AsyncClient", return_value=_mock_http_get(fake_ledger)):
    rep_resp = run(srv.handle_request({
        "jsonrpc": "2.0", "id": 6,
        "method": "tools/call",
        "params": {
            "name": "check_reputation",
            "arguments": {"agent_id": "org.agent.1.0.0"},
        },
    }))

rep_data = json.loads(rep_resp["result"]["content"][0]["text"])
check("T9.a: isError=False", rep_resp["result"]["isError"] is False)
check("T9.b: reputation present", "reputation" in rep_data)
check("T9.c: beta_weight present", "beta_weight" in rep_data)
check("T9.d: _aevum_interop injected", "_aevum_interop" in rep_data)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 10 — check_reputation leaderboard (no agent_id)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 10: check_reputation leaderboard ──")

fake_leaderboard = {"title": "CSO Reputation Leaderboard", "agents": []}

with patch("httpx.AsyncClient", return_value=_mock_http_get(fake_leaderboard)):
    lb_resp = run(srv.handle_request({
        "jsonrpc": "2.0", "id": 7,
        "method": "tools/call",
        "params": {"name": "check_reputation", "arguments": {"top_k": 5}},
    }))

lb_data = json.loads(lb_resp["result"]["content"][0]["text"])
check("T10.a: isError=False", lb_resp["result"]["isError"] is False)
check("T10.b: title present", "title" in lb_data)
check("T10.c: _aevum_interop injected", "_aevum_interop" in lb_data)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 11 — Unknown tool name
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 11: unknown tool ──")

unk_resp = run(srv.handle_request({
    "jsonrpc": "2.0", "id": 8,
    "method": "tools/call",
    "params": {"name": "nonexistent_tool", "arguments": {}},
}))
check("T11.a: JSON-RPC error code -32601",
      unk_resp.get("error", {}).get("code") == -32601,
      f"resp={unk_resp}")
check("T11.b: error message mentions tool name",
      "nonexistent_tool" in unk_resp.get("error", {}).get("message", ""))

# ══════════════════════════════════════════════════════════════════════════════
# TEST 12 — Unknown method
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 12: unknown method ──")

meth_resp = run(srv.handle_request({
    "jsonrpc": "2.0", "id": 9,
    "method": "resources/list",
    "params": {},
}))
check("T12.a: JSON-RPC error -32601 for unknown method",
      meth_resp.get("error", {}).get("code") == -32601)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 13 — Notification (no id) returns None
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 13: notification → None ──")

notif_resp = run(srv.handle_request({
    "jsonrpc": "2.0",
    "method": "notifications/message",
    "params": {"level": "info", "data": "test"},
    # id intentionally absent
}))
check("T13.a: notification returns None", notif_resp is None,
      f"got={notif_resp!r}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 14 — DX signature present in ALL three tool responses
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 14: DX signature in all tools ──")

tools_to_check = [
    ("discover_agents", {"capability": "test"}, "get", {"agents": []}),
    ("route_task", {"capability": "test.cap"}, "post", {"trace_id": "x", "result": {}, "served_by": "a", "latency_ms": 1.0, "score": 0.5}),
    ("check_reputation", {"agent_id": "a.b.1.0.0"}, "get", {"reputation": 0.5}),
]

for tname, targs, method, fake_payload in tools_to_check:
    mock_client = _mock_http_get(fake_payload) if method == "get" else _mock_http_post(fake_payload)
    with patch("httpx.AsyncClient", return_value=mock_client):
        r = run(srv.handle_request({
            "jsonrpc": "2.0", "id": 99,
            "method": "tools/call",
            "params": {"name": tname, "arguments": targs},
        }))
    data = json.loads(r["result"]["content"][0]["text"])
    has_sig = "_aevum_interop" in data and "PCES" in data.get("_aevum_interop", "")
    check(f"T14.{tname}: DX signature with PCES mention", has_sig)

# ══════════════════════════════════════════════════════════════════════════════
# TEST 15 — FastAPI HTTP mount: POST /mcp tools/list
# Use httpx ASGITransport to avoid TestClient event-loop conflicts in Py 3.14
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 15: FastAPI mount POST /mcp ──")

try:
    from fastapi import FastAPI

    _t15_app = FastAPI()
    _t15_srv = make_server()
    mount_on_fastapi(_t15_app, _t15_srv, path="/mcp")

    async def _run_t15():
        transport = httpx.ASGITransport(app=_t15_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:
            r = await ac.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            return r.status_code, r.json()

    t15_status, t15_body = asyncio.run(_run_t15())
    check("T15.a: HTTP 200", t15_status == 200,
          f"status={t15_status} body={str(t15_body)[:200]}")
    check("T15.b: tools list returned",
          "result" in t15_body and "tools" in t15_body.get("result", {}),
          f"body_keys={list(t15_body.keys())}")
    check("T15.c: 3 tools present",
          len(t15_body.get("result", {}).get("tools", [])) == 3)

except Exception as exc:
    check("T15: FastAPI mount test failed", False, f"error={exc}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 16 — FastAPI mount GET /mcp/info
# ══════════════════════════════════════════════════════════════════════════════
print("\n── TEST 16: FastAPI mount GET /mcp/info ──")

try:
    async def _run_t16():
        transport = httpx.ASGITransport(app=_t15_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:
            r = await ac.get("/mcp/info")
            return r.status_code, r.json()

    t16_status, t16_body = asyncio.run(_run_t16())
    check("T16.a: HTTP 200", t16_status == 200,
          f"status={t16_status}")
    check("T16.b: adapter name correct",
          t16_body.get("adapter") == "aevum-mcp-adapter")
    check("T16.c: mcp_version correct",
          t16_body.get("mcp_version") == _MCP_VERSION)
    check("T16.d: tool_count=3",
          t16_body.get("tool_count") == 3)
    check("T16.e: interop_notice present",
          "interop_notice" in t16_body and "PCES" in t16_body.get("interop_notice", ""))
    check("T16.f: stdio_config present", "stdio_config" in t16_body)

except Exception as exc:
    check("T16: FastAPI info test failed", False, f"error={exc}")

# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)
total = len(_results)
print(f"TICK 41.5 MCP Meta-TDD: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("\033[92mTICK 41.5 Complete: MCP Adapter Active\033[0m")
else:
    print("\033[91mVERIFICATION FAILED\033[0m")
    for name, ok, detail in _results:
        if not ok:
            print(f"  FAILED: {name}  {detail}")
    sys.exit(1)
