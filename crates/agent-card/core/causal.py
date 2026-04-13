"""
core/causal.py
==============
Causal Chain Tracker — 因果鏈追蹤器

映射：Φ 因果引擎 (L4)
每條穿越系統的請求都會產生一條因果鏈 (CausalChain)。
這些鏈的統計性質驅動路由權重的演化。

核心洞見：這不僅是「日誌」——這是系統學習和改進路由品質的
唯一數據來源。因果鏈是系統的「經驗記憶」。

數據流：
  請求進入 → begin_chain(trace_id)
  每個處理步驟 → add_hop(trace_id, agent_id, action, ...)
  請求完成 → close_chain(trace_id, outcome, value_signal)
  路由評分 ← get_agent_causal_bonus(agent_id)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from .protocol import CausalChain, CausalHop


class CausalTracker:
    """
    因果鏈追蹤器 (L4/Φ)。

    每條 trace_id 對應一條完整的因果鏈。
    系統中的每個處理步驟（路由、翻譯、執行、計量）
    都作為一個 CausalHop 記錄在鏈上。

    Shapley 值計算代理的因果貢獻度，驅動路由層演化。
    異常因果路徑偵測功能預留於 Phase 3 實現。
    """

    def __init__(self, max_chains: int = 100_000):
        # Primary chain store: trace_id → CausalChain
        self._chains: dict[str, CausalChain] = {}

        # Per-agent counters — the raw material for causal_bonus
        self._agent_total_count: dict[str, int] = defaultdict(int)
        self._agent_success_count: dict[str, int] = defaultdict(int)
        self._agent_total_value: dict[str, float] = defaultdict(float)

        # Index: agent_id → list of trace_ids they participated in
        self._agent_chains: dict[str, list[str]] = defaultdict(list)

        self._max_chains = max_chains

        # TODO: Implement persistent DB/Redis storage here

    # ──────────────────────────────────────────────
    # Chain lifecycle
    # ──────────────────────────────────────────────

    def begin_chain(self, trace_id: str) -> CausalChain:
        """開始一條新的因果鏈。"""
        chain = CausalChain(trace_id=trace_id)
        self._chains[trace_id] = chain
        self._maybe_evict()
        return chain

    def add_hop(
        self,
        trace_id: str,
        agent_id: str,
        action: str,
        latency_ms: float = 0.0,
        cost: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> Optional[CausalHop]:
        """在因果鏈上追加一個跳躍。"""
        chain = self._chains.get(trace_id)
        if chain is None:
            return None

        hop = CausalHop(
            hop_index=len(chain.hops),
            agent_id=agent_id,
            action=action,
            latency_ms=latency_ms,
            cost=cost,
            metadata=metadata or {},
        )
        chain.hops.append(hop)
        chain.total_latency_ms += latency_ms
        chain.total_cost += cost

        # Keep per-agent participation index up to date.
        # Only "execute" hops count toward the success-rate denominator,
        # mirroring what close_chain() credits in _agent_success_count.
        self._agent_chains[agent_id].append(trace_id)
        if action == "execute":
            self._agent_total_count[agent_id] += 1

        return hop

    def close_chain(
        self,
        trace_id: str,
        outcome: str = "success",
        value_signal: Optional[float] = None,
    ) -> Optional[CausalChain]:
        """關閉因果鏈並記錄結果。更新代理成功率統計。"""
        chain = self._chains.get(trace_id)
        if chain is None:
            return None

        chain.outcome = outcome
        chain.closed_at = time.time()
        chain.value_signal = value_signal

        # Walk hops: credit executing agents with the outcome
        for hop in chain.hops:
            if hop.action == "execute":
                if outcome == "success":
                    self._agent_success_count[hop.agent_id] += 1
                if value_signal is not None:
                    self._agent_total_value[hop.agent_id] += value_signal

        return chain

    def get_chain(self, trace_id: str) -> Optional[CausalChain]:
        """按 trace_id 查詢因果鏈。"""
        return self._chains.get(trace_id)

    # ──────────────────────────────────────────────
    # Causal bonus — the L4 → L3 signal
    # ──────────────────────────────────────────────

    def get_agent_causal_bonus(self, agent_id: str) -> float:
        """
        計算代理的因果加成分數 (0-1)。

        Formula:
            bonus = 0.7 * success_rate + 0.3 * value_score

        新代理獲得中性分數 0.5（避免冷啟動懲罰）。
        此值直接注入路由評分函數的 causal_bonus 維度。
        """
        total = self._agent_total_count.get(agent_id, 0)
        if total == 0:
            return 0.5  # cold-start: neutral score

        success = self._agent_success_count.get(agent_id, 0)
        success_rate = success / total

        # Normalise cumulative value signal: avg value per call, capped at 1.0
        value = self._agent_total_value.get(agent_id, 0.0)
        value_score = min(1.0, value / max(total, 1))

        return 0.7 * success_rate + 0.3 * value_score

    # ──────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────

    def get_agent_stats(self, agent_id: str) -> dict:
        """獲取代理的因果統計：成功率、總次數、累積價值。"""
        total = self._agent_total_count.get(agent_id, 0)
        success = self._agent_success_count.get(agent_id, 0)
        value = self._agent_total_value.get(agent_id, 0.0)
        return {
            "agent_id": agent_id,
            "total_interactions": total,
            "successful": success,
            "success_rate": success / total if total > 0 else 0.0,
            "total_value": value,
            "causal_bonus": self.get_agent_causal_bonus(agent_id),
        }

    def get_global_stats(self) -> dict:
        """全局因果統計：成功率、平均延遲、平均成本。"""
        chains = list(self._chains.values())
        closed = [c for c in chains if c.closed_at is not None]
        successful = [c for c in closed if c.outcome == "success"]
        return {
            "total_chains": len(chains),
            "closed_chains": len(closed),
            "successful_chains": len(successful),
            "global_success_rate": (
                len(successful) / len(closed) if closed else 0.0
            ),
            "avg_latency_ms": (
                sum(c.total_latency_ms for c in closed) / len(closed)
                if closed else 0.0
            ),
            "avg_cost": (
                sum(c.total_cost for c in closed) / len(closed)
                if closed else 0.0
            ),
        }

    # ──────────────────────────────────────────────
    # Memory management
    # ──────────────────────────────────────────────

    def _maybe_evict(self) -> None:
        """當鏈數超過上限時，淘汰最舊的已關閉鏈（LRU by close timestamp）。"""
        if len(self._chains) <= self._max_chains:
            return

        closed = [
            (tid, c)
            for tid, c in self._chains.items()
            if c.closed_at is not None
        ]
        if not closed:
            return  # all open — cannot evict; caller must wait

        # Sort ascending by close time, evict oldest 1 000 + overflow
        closed.sort(key=lambda x: x[1].closed_at or 0.0)
        evict_count = len(self._chains) - self._max_chains + 1_000
        for tid, _ in closed[:evict_count]:
            del self._chains[tid]
