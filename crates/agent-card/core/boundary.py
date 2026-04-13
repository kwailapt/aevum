"""
core/boundary.py
================
Boundary Operator — 邊界算子 / 協議互譯層

映射：∂ 算子 (L2)
這是系統因果錐穿過盒壁的精確位置。
所有外部協議（MCP, OpenAI, Google A2A）在此被翻譯為
內部規範格式 (Envelope)，出去時再翻譯回目標協議。

設計原則：
- 入方向：任何協議 → Envelope (正則化)
- 出方向：Envelope → 目標代理的協議 (特化)
- 翻譯過程本身也被記錄在因果鏈上 (action="translate")

因果迴路位置：∂ → Φ → Ω → ∂
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from .protocol import (
    A2ARequest,
    A2AResponse,
    Envelope,
    MessageType,
)


class BoundaryOperator:
    """
    邊界算子 ∂ (L2)：負責所有內外協議的互譯。

    目前支援的協議：
    - native:     A2A Protocol Layer 原生格式
    - mcp:        Anthropic Model Context Protocol
    - openai:     OpenAI Function Calling / Tool Use  (incl. Chat Completions)
    - google_a2a: Google Agent-to-Agent Protocol

    擴展方式：新增 _translate_inbound_xxx / _translate_outbound_xxx 方法對。
    """

    SUPPORTED_PROTOCOLS = {"native", "mcp", "openai", "google_a2a"}

    # ──────────────────────────────────────────────
    # Public: top-level dispatch
    # ──────────────────────────────────────────────

    def translate_inbound(
        self, raw_message: dict[str, Any], source_protocol: str
    ) -> Envelope:
        """
        外部消息 → 內部 Envelope (因果錐擴張的入口)。

        Dispatches to the protocol-specific translator; unknown protocols fall
        back to the generic best-effort parser.
        """
        if source_protocol == "native":
            return Envelope(**raw_message)
        elif source_protocol == "mcp":
            return self._translate_inbound_mcp(raw_message)
        elif source_protocol == "openai":
            return self._translate_inbound_openai(raw_message)
        elif source_protocol == "google_a2a":
            return self._translate_inbound_google(raw_message)
        else:
            return self._translate_inbound_generic(raw_message)

    def translate_outbound(
        self, envelope: Envelope, target_protocol: str
    ) -> dict[str, Any]:
        """
        內部 Envelope → 外部消息格式 (因果效應離開系統的出口)。
        """
        if target_protocol == "native":
            return envelope.model_dump()
        elif target_protocol == "mcp":
            return self._translate_outbound_mcp(envelope)
        elif target_protocol == "openai":
            return self._translate_outbound_openai(envelope)
        elif target_protocol == "google_a2a":
            return self._translate_outbound_google(envelope)
        else:
            return envelope.model_dump()

    # ──────────────────────────────────────────────
    # Public: convenience envelope builders
    # ──────────────────────────────────────────────

    def build_request_envelope(
        self,
        request: A2ARequest,
        sender_id: str = "",
        trace_id: Optional[str] = None,
    ) -> Envelope:
        """從 A2ARequest 構建完整 Envelope，可指定 trace_id 以延續因果鏈。"""
        return Envelope(
            message_id=str(uuid.uuid4()),
            trace_id=trace_id or str(uuid.uuid4())[:16],
            message_type=MessageType.REQUEST,
            sender_id=sender_id,
            payload=request.model_dump(),
        )

    def build_response_envelope(
        self,
        response: A2AResponse,
        original_envelope: Envelope,
    ) -> Envelope:
        """從 A2AResponse 構建回應 Envelope，繼承原始請求的 trace_id。"""
        return Envelope(
            trace_id=original_envelope.trace_id,
            message_type=MessageType.RESPONSE,
            sender_id=original_envelope.receiver_id,
            receiver_id=original_envelope.sender_id,
            payload=response.model_dump(),
        )

    # ──────────────────────────────────────────────
    # MCP (Anthropic Model Context Protocol)
    # ──────────────────────────────────────────────

    def _translate_inbound_mcp(self, raw: dict[str, Any]) -> Envelope:
        """
        MCP JSON-RPC 2.0 → Envelope.

        Supported MCP methods:
          tools/call      → capability = tool name
          resources/read  → capability = "resource.read"
          prompts/get     → capability = "prompt.get"
          <other>         → capability = method with "/" → "."
        """
        method = raw.get("method", "")
        params = raw.get("params", {})

        if method == "tools/call":
            # params: {"name": str, "arguments": dict}
            request = A2ARequest(
                capability=params.get("name", "unknown"),
                parameters=params.get("arguments", {}),
                context={"source_protocol": "mcp", "mcp_method": method},
            )
        elif method == "resources/read":
            request = A2ARequest(
                capability="resource.read",
                parameters={"uri": params.get("uri", "")},
                context={"source_protocol": "mcp", "mcp_method": method},
            )
        elif method == "prompts/get":
            request = A2ARequest(
                capability="prompt.get",
                parameters={"name": params.get("name", ""), "arguments": params.get("arguments", {})},
                context={"source_protocol": "mcp", "mcp_method": method},
            )
        else:
            request = A2ARequest(
                capability=method.replace("/", ".") or "unknown",
                parameters=params,
                context={"source_protocol": "mcp", "mcp_method": method},
            )

        return Envelope(
            message_id=str(raw.get("id", str(uuid.uuid4()))),
            message_type=MessageType.REQUEST,
            payload=request.model_dump(),
        )

    def _translate_outbound_mcp(self, envelope: Envelope) -> dict[str, Any]:
        """Envelope → MCP JSON-RPC 2.0 response."""
        payload = envelope.payload
        is_error = payload.get("status") == "error"
        return {
            "jsonrpc": "2.0",
            "id": envelope.message_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": str(payload.get("result", "")),
                    }
                ],
                "isError": is_error,
            },
        }

    # ──────────────────────────────────────────────
    # OpenAI  (Function Calling + Chat Completions)
    # ──────────────────────────────────────────────

    # Known OpenAI-hosted model prefixes that should NOT be used as capability names.
    # Any model string that doesn't start with one of these is treated as a
    # capability / agent-id routing hint directly.
    _OPENAI_BUILTIN_PREFIXES = (
        "gpt-", "o1", "o3", "o4", "chatgpt", "text-davinci",
        "text-embedding", "whisper", "tts-", "dall-e",
    )

    @classmethod
    def _capability_from_model(cls, model: str) -> str:
        """
        Derive the A2A capability name from an OpenAI `model` field.

        Rules (applied in order):
          1. Empty string  → default "chat.completion"
          2. Known OpenAI model prefix (gpt-*, o1, o3, …) → "chat.completion"
          3. Anything else (e.g. "chat.completion", "text.generate",
             "aevum.mock.chat.v1") → use verbatim as the capability name

        This lets callers address registered agents directly via the `model`
        field without any extra routing fields, which is the idiomatic way
        OpenAI-compatible clients express intent.
        """
        if not model:
            return "chat.completion"
        model_lower = model.lower()
        if any(model_lower.startswith(p) for p in cls._OPENAI_BUILTIN_PREFIXES):
            return "chat.completion"
        # Custom value → treat as a direct capability / agent-capability selector
        return model

    def _translate_inbound_openai(self, raw: dict[str, Any]) -> Envelope:
        """
        OpenAI tool_calls / Chat Completion request → Envelope.

        Supports two shapes:
          1. tool_call / tool_calls[]  — function calling format
             capability = function.name
          2. messages[]                — Chat Completions format
             capability = _capability_from_model(model)
               • known OpenAI model names → "chat.completion"
               • custom strings (e.g. "chat.completion", "aevum.mock.chat.v1")
                 → used verbatim, enabling direct agent routing via model field
        """
        # Shape 1: explicit tool call
        tool_call = raw.get("tool_call") or (
            raw.get("tool_calls", [None])[0] if raw.get("tool_calls") else None
        )
        if tool_call:
            func = tool_call.get("function", {})
            # arguments may arrive as a JSON string
            arguments = func.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}
            request = A2ARequest(
                capability=func.get("name", "unknown"),
                parameters=arguments,
                context={
                    "source_protocol": "openai",
                    "tool_call_id": tool_call.get("id", ""),
                },
            )
            return Envelope(
                message_type=MessageType.REQUEST,
                payload=request.model_dump(),
            )

        # Shape 2: Chat Completions (messages array)
        messages = raw.get("messages", [])
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break

        model = raw.get("model", "")
        capability = self._capability_from_model(model)

        request = A2ARequest(
            capability=capability,
            parameters={"messages": messages, "query": user_content},
            context={
                "source_protocol": "openai",
                "model": model,
                "temperature": raw.get("temperature", 1.0),
                "stream": raw.get("stream", False),
            },
            constraints={
                "max_tokens": raw.get("max_tokens", 0),
            },
        )
        return Envelope(
            message_type=MessageType.REQUEST,
            payload=request.model_dump(),
        )

    def _translate_outbound_openai(self, envelope: Envelope) -> dict[str, Any]:
        """
        Envelope → OpenAI response.

        If context carries a tool_call_id → tool response format.
        Otherwise → Chat Completion response format.
        """
        payload = envelope.payload
        ctx = payload.get("context", {})
        result_text = str(payload.get("result", ""))

        tool_call_id = ctx.get("tool_call_id", "")
        if tool_call_id:
            # tool response
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "content": result_text,
            }

        # Chat Completion response
        return {
            "id": f"chatcmpl-{envelope.trace_id}",
            "object": "chat.completion",
            "model": ctx.get("model", "a2a-router"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result_text,
                    },
                    "finish_reason": "stop" if payload.get("status") == "success" else "error",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    # ──────────────────────────────────────────────
    # Google A2A Protocol
    # ──────────────────────────────────────────────

    def _translate_inbound_google(self, raw: dict[str, Any]) -> Envelope:
        """
        Google A2A Task → Envelope.

        Task schema:
          { "id": str, "sessionId": str, "skill": str,
            "message": { "parts": [{"text": str}, ...] } }
        """
        task = raw.get("task", raw)
        message = task.get("message", {})
        parts = message.get("parts", [])
        text_content = " ".join(p.get("text", "") for p in parts if "text" in p)

        request = A2ARequest(
            capability=task.get("skill", "general"),
            parameters={"text": text_content},
            context={
                "source_protocol": "google_a2a",
                "task_id": task.get("id", ""),
                "session_id": task.get("sessionId", ""),
            },
        )
        return Envelope(
            message_type=MessageType.REQUEST,
            payload=request.model_dump(),
        )

    def _translate_outbound_google(self, envelope: Envelope) -> dict[str, Any]:
        """Envelope → Google A2A Task response (artifacts format)."""
        payload = envelope.payload
        ctx = payload.get("context", {})
        return {
            "id": ctx.get("task_id", envelope.message_id),
            "status": {
                "state": "completed" if payload.get("status") == "success" else "failed",
            },
            "artifacts": [
                {
                    "parts": [{"text": str(payload.get("result", ""))}]
                }
            ],
        }

    # ──────────────────────────────────────────────
    # Generic fallback
    # ──────────────────────────────────────────────

    def _translate_inbound_generic(self, raw: dict[str, Any]) -> Envelope:
        """
        Best-effort parser for unknown protocols.
        Probes common field names for capability and parameters.
        """
        capability = raw.get(
            "capability",
            raw.get("method", raw.get("action", raw.get("skill", "unknown"))),
        )
        parameters = raw.get(
            "parameters",
            raw.get("params", raw.get("arguments", raw.get("input", {}))),
        )
        if not isinstance(parameters, dict):
            parameters = {"raw": parameters}

        request = A2ARequest(
            capability=str(capability),
            parameters=parameters,
            context={"source_protocol": "unknown"},
        )
        return Envelope(
            message_type=MessageType.REQUEST,
            payload=request.model_dump(),
        )
