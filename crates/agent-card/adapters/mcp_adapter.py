"""
adapters/mcp_adapter.py
=======================
MCP Protocol Adapter — Anthropic Model Context Protocol 適配器

映射：L2/∂ 的 MCP 特化實現
此模組封裝了與 MCP 服務器/客戶端交互的完整邏輯，
作為 BoundaryOperator._translate_inbound_mcp / _translate_outbound_mcp 的高層封裝。

MCP 核心概念映射：
  MCP tools/call      → A2ARequest(capability=tool_name)
  MCP resources/read  → A2ARequest(capability="resource.read")
  MCP prompts/get     → A2ARequest(capability="prompt.get")
  MCP sampling        → A2ARequest(capability="llm.sample")
"""

from __future__ import annotations

from typing import Any

from core.protocol import AgentCard, Capability


class MCPAdapter:
    """
    MCP 協議適配器。

    職責：
    1. 將 MCP AgentCard 格式轉換為 A2A AgentCard
    2. 暴露為 MCP 服務器（讓 MCP 客戶端可以發現此節點）
    3. 作為 MCP 客戶端連接外部 MCP 服務器
    """

    def agent_card_from_mcp_manifest(self, manifest: dict[str, Any]) -> AgentCard:
        """將 MCP 服務器的 tool manifest 轉換為 A2A AgentCard。"""
        pass

    def capability_from_mcp_tool(self, tool: dict[str, Any]) -> Capability:
        """將 MCP tool 定義轉換為 A2A Capability。"""
        pass

    def to_mcp_tools_list(self, agent_card: AgentCard) -> list[dict[str, Any]]:
        """將 A2A AgentCard 的能力列表轉換為 MCP tools/list 格式。"""
        pass
