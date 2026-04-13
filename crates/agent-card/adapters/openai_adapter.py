"""
adapters/openai_adapter.py
==========================
OpenAI Function Calling Adapter — OpenAI Tool Use 適配器

映射：L2/∂ 的 OpenAI 特化實現
此模組封裝了與 OpenAI API Function Calling / Tool Use 格式的互譯邏輯，
作為 BoundaryOperator._translate_inbound_openai / _translate_outbound_openai 的高層封裝。

OpenAI 格式映射：
  tool_calls[].function.name      → capability name
  tool_calls[].function.arguments → parameters (JSON string → dict)
  tool_calls[].id                 → context.tool_call_id
"""

from __future__ import annotations

from typing import Any

from core.protocol import AgentCard, Capability


class OpenAIAdapter:
    """
    OpenAI Function Calling 協議適配器。

    職責：
    1. 將 OpenAI tool schema 轉換為 A2A Capability
    2. 暴露 A2A 能力為 OpenAI function definitions
    3. 處理 tool_calls 數組格式
    """

    def capability_from_openai_function(self, func_def: dict[str, Any]) -> Capability:
        """將 OpenAI function definition 轉換為 A2A Capability。"""
        pass

    def to_openai_function_definitions(self, agent_card: AgentCard) -> list[dict[str, Any]]:
        """將 A2A AgentCard 的能力列表轉換為 OpenAI function definitions 格式。"""
        pass

    def parse_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """解析 OpenAI tool_calls 數組，返回規範化的請求列表。"""
        pass
