"""
core/protocol.py
================
A2A Protocol Layer — 協議核心定義
所有在系統中流動的數據結構的規範來源 (Single Source of Truth)

映射：此模組定義了穿越邊界算子 ∂ 的所有合法態的形式語言。
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Capability: 代理能力的原子化描述
# ──────────────────────────────────────────────

class Capability(BaseModel):
    """
    一個代理所宣告的單一能力。
    能力是路由層進行語義匹配的最小單位。
    """
    name: str = Field(..., description="能力的規範名稱, e.g. 'text.summarize'")
    description: str = Field(default="", description="自然語言描述，用於語義匹配")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for input")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for output")
    tags: list[str] = Field(default_factory=list, description="能力標籤，用於快速索引")
    embedding: Optional[list[float]] = Field(default=None, description="語義嵌入向量 (可選)")
    cost_per_call: float = Field(default=0.0, description="每次調用的標價")
    avg_latency_ms: float = Field(default=0.0, description="歷史平均延遲 (ms)")


# ──────────────────────────────────────────────
# AgentCard: 代理的身份與能力宣告
# ──────────────────────────────────────────────

class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class AgentCard(BaseModel):
    """
    AgentCard 是代理在 A2A 網絡中的完整身份。
    類比：DNS 的 SRV 記錄 + 能力清單 + 信譽快照。
    """
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = Field(..., description="人類可讀的代理名稱")
    description: str = Field(default="")
    endpoint: str = Field(..., description="代理的可達端點 URL")
    protocol: str = Field(default="native", description="native | mcp | openai | google_a2a")
    capabilities: list[Capability] = Field(default_factory=list)
    status: AgentStatus = Field(default=AgentStatus.ONLINE)
    reputation: float = Field(default=0.5, ge=0.0, le=1.0)
    registered_at: float = Field(default_factory=time.time)
    last_heartbeat: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def capability_names(self) -> list[str]:
        return [c.name for c in self.capabilities]


# ──────────────────────────────────────────────
# Envelope: 統一訊息封包
# ──────────────────────────────────────────────

class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    DISCOVERY = "discovery"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class Envelope(BaseModel):
    """
    Envelope 是穿越系統的所有訊息的統一封包格式。
    trace_id 提供因果鏈追蹤; hop_count + ttl 防止迴路。
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:16])
    message_type: MessageType = Field(default=MessageType.REQUEST)
    sender_id: str = Field(default="")
    receiver_id: str = Field(default="")  # empty = broadcast / router decides
    timestamp: float = Field(default_factory=time.time)
    hop_count: int = Field(default=0)
    ttl: int = Field(default=10, description="最大跳數限制")
    payload: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# A2A Request / Response: 請求與回應
# ──────────────────────────────────────────────

class A2ARequest(BaseModel):
    """封裝在 Envelope.payload 中的請求體。"""
    capability: str = Field(..., description="請求的能力名稱")
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict, description="上下文資訊")
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="約束條件: max_cost, max_latency_ms, min_reputation 等"
    )


class A2AResponse(BaseModel):
    """封裝在 Envelope.payload 中的回應體。"""
    status: str = Field(default="success")  # success | error | partial
    result: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    actual_cost: float = Field(default=0.0)
    actual_latency_ms: float = Field(default=0.0)
    served_by: str = Field(default="", description="實際服務此請求的 agent_id")


# ──────────────────────────────────────────────
# Causal Chain: 因果鏈記錄
# ──────────────────────────────────────────────

class CausalHop(BaseModel):
    """因果鏈中的一個跳躍（hop）。"""
    hop_index: int
    agent_id: str
    action: str  # "route" | "execute" | "translate" | "meter"
    timestamp: float = Field(default_factory=time.time)
    latency_ms: float = 0.0
    cost: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalChain(BaseModel):
    """
    完整的因果鏈：一條請求從進入系統到離開系統的全部軌跡。
    這是 Φ 引擎的核心數據結構。
    """
    trace_id: str
    hops: list[CausalHop] = Field(default_factory=list)
    outcome: str = Field(default="pending")  # pending | success | error | timeout
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    value_signal: Optional[float] = Field(default=None, description="外部回饋的價值信號")
    created_at: float = Field(default_factory=time.time)
    closed_at: Optional[float] = None
