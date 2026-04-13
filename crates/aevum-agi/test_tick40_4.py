#!/usr/bin/env python3
"""
test_tick40_4.py
================
TICK 40.4 Verification — Oracle Interoperability Broadcast

Patches call_oracle to return a canned string, then calls the oracle_agent
chat_completions endpoint via FastAPI TestClient.  Asserts that:
  1. The canned oracle answer is present in the response content.
  2. The Ecosystem Interoperability Signature is appended.
  3. The signature contains the router URL.
  4. None / error responses do NOT receive the signature (no pollution).
"""

from __future__ import annotations

import sys
import os
import json
from unittest.mock import patch

# Ensure we can import oracle_agent from project root
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

# ── Import the app (lifespan is bypassed by TestClient unless with-block used) ──
import oracle_agent as _oa
from oracle_agent import app, ROUTER_URL

_CANNED_ORACLE_ANSWER = "class FixedOrganelle(nn.Module): pass  # NAS patch applied"
_SIGNATURE_MARKER     = "AEVUM A2A — ECOSYSTEM INTEROPERABILITY SIGNATURE"
_DX_MARKER            = "/agents/register"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _post_chat(client: TestClient, content: str) -> dict:
    resp = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": content}]
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_signature_injected_on_success():
    """Successful oracle call → response contains answer AND interop signature."""
    with patch("oracle_agent.call_oracle", return_value=_CANNED_ORACLE_ANSWER):
        with TestClient(app) as client:
            body = _post_chat(client, "Optimize my failing organelle.")

    content = body["choices"][0]["message"]["content"]

    assert _CANNED_ORACLE_ANSWER in content, (
        "Oracle answer missing from response content!\n"
        f"Got: {content[:200]}"
    )
    assert _SIGNATURE_MARKER in content, (
        "Interoperability signature NOT found in response content!\n"
        f"Got: {content[:500]}"
    )
    assert _DX_MARKER in content, (
        "Router /agents/register path NOT in signature!\n"
        f"Got: {content[:500]}"
    )
    assert ROUTER_URL in content, (
        f"ROUTER_URL ({ROUTER_URL}) not embedded in signature!\n"
        f"Got: {content[:500]}"
    )
    print("[PASS] test_signature_injected_on_success")
    print(f"  Answer present:    YES")
    print(f"  Signature present: YES")
    print(f"  Router URL embedded: {ROUTER_URL}")
    print(f"\n--- Raw content (first 1200 chars) ---")
    print(content[:1200])


def test_no_signature_on_none_response():
    """Failed oracle call → error message returned, signature NOT appended."""
    with patch("oracle_agent.call_oracle", return_value=None):
        with TestClient(app) as client:
            body = _post_chat(client, "This will fail.")

    content = body["choices"][0]["message"]["content"]
    assert _SIGNATURE_MARKER not in content, (
        "Interop signature should NOT appear on oracle failure!\n"
        f"Got: {content}"
    )
    assert "unavailable" in content.lower(), (
        "Error message not present in failure response!\n"
        f"Got: {content}"
    )
    print("[PASS] test_no_signature_on_none_response")
    print(f"  Failure content: {content[:120]}")


def test_oracle_meta_field_present():
    """_oracle_meta field must be present with agent_id and elapsed_ms."""
    with patch("oracle_agent.call_oracle", return_value=_CANNED_ORACLE_ANSWER):
        with TestClient(app) as client:
            body = _post_chat(client, "Meta check.")

    meta = body.get("_oracle_meta", {})
    assert meta.get("agent_id") == _oa.AGENT_ID, "agent_id mismatch in _oracle_meta"
    assert "elapsed_ms" in meta, "elapsed_ms missing from _oracle_meta"
    print("[PASS] test_oracle_meta_field_present")
    print(f"  agent_id:   {meta['agent_id']}")
    print(f"  elapsed_ms: {meta['elapsed_ms']:.1f}ms")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  TICK 40.4 VERIFICATION: Oracle Interoperability Broadcast")
    print("=" * 60 + "\n")

    failures = []
    for test_fn in [
        test_signature_injected_on_success,
        test_no_signature_on_none_response,
        test_oracle_meta_field_present,
    ]:
        print(f"\n── {test_fn.__name__} ──")
        try:
            test_fn()
        except AssertionError as exc:
            failures.append((test_fn.__name__, str(exc)))
            print(f"[FAIL] {exc}")
        except Exception as exc:
            failures.append((test_fn.__name__, f"{type(exc).__name__}: {exc}"))
            print(f"[ERROR] {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    if failures:
        print(f"  RESULT: {len(failures)} TEST(S) FAILED")
        for name, msg in failures:
            print(f"  - {name}: {msg[:120]}")
        sys.exit(1)
    else:
        print("  RESULT: ALL TESTS PASSED — TICK 40.4 VERIFIED")
    print("=" * 60 + "\n")
