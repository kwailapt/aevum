"""
adapters/a2a_google_adapter.py
==============================
Google A2A Protocol Adapter — Google Agent-to-Agent Protocol 適配器

映射：L2/∂ 的 Google A2A 特化實現
此模組封裝了與 Google A2A Protocol 的互譯邏輯，
作為 BoundaryOperator._translate_inbound_google / _translate_outbound_google 的高層封裝。

Google A2A 核心概念映射：
  Task.skill          → capability name
  Task.message.parts  → parameters.text (聚合所有 text parts)
  Task.id             → context.task_id
  Task.sessionId      → context.session_id
  Artifact.parts      → result output
"""

from __future__ import annotations

from typing import Any

from core.protocol import AgentCard, Capability


class GoogleA2AAdapter:
    """
    Google A2A 協議適配器。

    職責：
    1. 將 Google A2A Task 格式轉換為 A2A Envelope
    2. 暴露 A2A 能力為 Google A2A AgentCard 格式
    3. 處理 streaming artifacts 格式（Phase 2）
    """

    def capability_from_google_skill(self, skill: dict[str, Any]) -> Capability:
        """將 Google A2A skill 定義轉換為 A2A Capability。"""
        pass

    def to_google_agent_card(self, agent_card: AgentCard) -> dict[str, Any]:
        """將 A2A AgentCard 轉換為 Google A2A AgentCard 格式。"""
        pass

    def build_task_response(
        self, task_id: str, result: Any, status: str = "completed"
    ) -> dict[str, Any]:
        """構建 Google A2A Task response with artifacts。"""
        pass
