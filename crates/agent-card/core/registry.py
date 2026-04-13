"""
core/registry.py
================
Agent Registry — 代理發現與注冊

映射：L1 (Identity Layer)
這是網絡的「電話簿」。沒有它，路由層無法知道任何外部代理的存在。

設計原則：
- 首先在 M1 Ultra 本地運行（單節點注冊表）
- 預留聯邦化介面，未來可跨節點同步
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import numpy as np

from .protocol import AgentCard, AgentStatus, Capability


class AgentRegistry:
    """
    代理注冊表。維護所有已知代理的 AgentCard，
    並提供基於能力的語義發現。

    L1 身份層的核心組件：提供 Ed25519 驗證預留介面，
    維護去中心化零信任拓撲。
    """

    def __init__(self, heartbeat_timeout: float = 60.0):
        # agent_id → AgentCard (primary store)
        self._agents: dict[str, AgentCard] = {}
        # capability_name → [agent_ids] (inverted index for O(1) exact lookup)
        self._capability_index: dict[str, list[str]] = {}
        self._heartbeat_timeout = heartbeat_timeout
        # TODO: Implement persistent DB/Redis storage here

    # ── 注冊 / 註銷 ──

    def register(self, card: AgentCard) -> AgentCard:
        """註冊一個代理。如果已存在則更新（upsert 語義）。"""
        card.last_heartbeat = time.time()
        card.status = AgentStatus.ONLINE
        self._agents[card.agent_id] = card

        # Rebuild capability inverted index for this agent
        for cap in card.capabilities:
            if cap.name not in self._capability_index:
                self._capability_index[cap.name] = []
            if card.agent_id not in self._capability_index[cap.name]:
                self._capability_index[cap.name].append(card.agent_id)

        return card

    def deregister(self, agent_id: str) -> bool:
        """註銷一個代理，並清理其能力索引條目。"""
        if agent_id not in self._agents:
            return False
        card = self._agents.pop(agent_id)
        for cap in card.capabilities:
            if cap.name in self._capability_index:
                self._capability_index[cap.name] = [
                    aid
                    for aid in self._capability_index[cap.name]
                    if aid != agent_id
                ]
        return True

    def heartbeat(self, agent_id: str) -> bool:
        """更新代理心跳時間戳並確保其狀態為 ONLINE。"""
        if agent_id not in self._agents:
            return False
        self._agents[agent_id].last_heartbeat = time.time()
        self._agents[agent_id].status = AgentStatus.ONLINE
        return True

    # ── 發現 ──

    def discover_by_name(self, capability_name: str) -> list[AgentCard]:
        """按能力名稱精確匹配，僅返回 ONLINE 代理。"""
        agent_ids = self._capability_index.get(capability_name, [])
        return [
            self._agents[aid]
            for aid in agent_ids
            if aid in self._agents and self._agents[aid].status == AgentStatus.ONLINE
        ]

    def discover_by_tags(self, tags: list[str]) -> list[AgentCard]:
        """按標籤模糊匹配：返回具有任一指定標籤的 ONLINE 代理（無重複）。"""
        tag_set = set(tags)
        seen: set[str] = set()
        results: list[AgentCard] = []
        for card in self._agents.values():
            if card.status != AgentStatus.ONLINE or card.agent_id in seen:
                continue
            for cap in card.capabilities:
                if tag_set & set(cap.tags):
                    results.append(card)
                    seen.add(card.agent_id)
                    break
        return results

    def discover_by_semantic(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> list[tuple[AgentCard, Capability, float]]:
        """
        語義發現：使用嵌入向量的餘弦相似度匹配能力。
        返回 (AgentCard, 最佳匹配能力, 相似度分數) 的列表。
        需要能力的 embedding 字段已預計算。
        """
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0.0:
            return []

        scored: list[tuple[AgentCard, Capability, float]] = []

        for card in self._agents.values():
            if card.status != AgentStatus.ONLINE:
                continue
            for cap in card.capabilities:
                if cap.embedding is None:
                    continue
                c = np.array(cap.embedding, dtype=np.float32)
                c_norm = float(np.linalg.norm(c))
                if c_norm == 0.0:
                    continue
                similarity = float(np.dot(q, c) / (q_norm * c_norm))
                if similarity >= min_similarity:
                    scored.append((card, cap, similarity))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]

    def discover_by_text(
        self, query: str, top_k: int = 5
    ) -> list[tuple[AgentCard, Capability, float]]:
        """
        基於文本關鍵字的輕量級匹配（無需嵌入模型）。
        使用 Jaccard 相似度對能力名稱、描述和標籤進行匹配。

        Both the query and capability names are normalised identically
        (dots and hyphens → spaces, lower-cased) before tokenisation so
        that a query like "chat.completion" correctly matches a registered
        capability named "chat.completion" (and vice-versa).
        """
        # Normalise query the same way we normalise capability names:
        # replace dots and hyphens with spaces so "chat.completion" →
        # {"chat", "completion"} instead of the single opaque token {"chat.completion"}.
        query_tokens = set(
            query.lower().replace(".", " ").replace("-", " ").split()
        )
        scored: list[tuple[AgentCard, Capability, float]] = []

        for card in self._agents.values():
            if card.status != AgentStatus.ONLINE:
                continue
            for cap in card.capabilities:
                cap_tokens = set(
                    cap.name.lower().replace(".", " ").replace("-", " ").split()
                )
                cap_tokens |= set(cap.description.lower().split())
                cap_tokens |= {t.lower() for t in cap.tags}

                intersection = query_tokens & cap_tokens
                union = query_tokens | cap_tokens
                if not union:
                    continue
                jaccard = len(intersection) / len(union)
                if jaccard > 0.0:
                    scored.append((card, cap, jaccard))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]

    # ── 拓撲 ──

    def get_all_agents(self) -> list[AgentCard]:
        """返回所有已注冊代理（包括 OFFLINE）。"""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """按 agent_id 精確查詢，未找到返回 None。"""
        return self._agents.get(agent_id)

    def get_topology_summary(self) -> dict:
        """返回網絡拓撲概要快照。"""
        online = [a for a in self._agents.values() if a.status == AgentStatus.ONLINE]
        all_caps: set[str] = set()
        for a in online:
            all_caps.update(a.capability_names())
        return {
            "total_agents": len(self._agents),
            "online_agents": len(online),
            "unique_capabilities": len(all_caps),
            "capability_names": sorted(all_caps),
        }

    # ── 健康檢查 ──

    async def health_check_loop(self, interval: float = 15.0) -> None:
        """後台協程：定期將心跳超時的代理標記為 OFFLINE。"""
        while True:
            now = time.time()
            for card in self._agents.values():
                if now - card.last_heartbeat > self._heartbeat_timeout:
                    card.status = AgentStatus.OFFLINE
            await asyncio.sleep(interval)
