"""
core/router.py
==============
Semantic Router — 語義路由引擎

映射：Φ 因果引擎的決策核心 (L3)
這是整個系統作為「結締組織」的核心價值所在。
路由品質直接決定系統在網絡中的不可替代性。

路由評分公式：
  score(agent, request) = w1 * capability_match
                        + w2 * (1 - normalized_latency)
                        + w3 * reputation
                        + w4 * (1 - normalized_cost)
                        + w5 * causal_bonus

其中 causal_bonus 來自歷史因果鏈的正向回饋。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .protocol import AgentCard, A2ARequest, Capability
from .registry import AgentRegistry
from .causal import CausalTracker

if TYPE_CHECKING:
    from .economics import EconomicsEngine


@dataclass
class RouteScore:
    """路由評分結果：包含代理選擇和各維度分數分解。"""
    agent: AgentCard
    capability: Capability
    capability_match: float = 0.0
    latency_score: float = 0.0
    reputation_score: float = 0.0
    cost_score: float = 0.0
    causal_bonus: float = 0.0
    kvs_score: float = 0.0   # KVS Capitalization score (super-linear routing signal)
    total: float = 0.0


@dataclass
class RoutingWeights:
    """路由評分的權重配置。可通過 Ω 層的反饋動態調整。

    Weight budget = 1.0:
      capability  0.35  (was 0.40) — slightly reduced to fund kvs
      latency     0.15  (was 0.20) — slightly reduced to fund kvs
      reputation  0.20  (was 0.25) — reduced; Y already captures value history
      cost        0.10  — unchanged
      causal      0.20  (was 0.05) — kvs_score flows through this dimension;
                                     raised to give capitalization room to dominate
    """
    capability: float = 0.35
    latency: float = 0.15
    reputation: float = 0.20
    cost: float = 0.10
    causal: float = 0.20


class Router:
    """
    語義路由引擎 (L3/Φ)。

    核心職責：
    1. 接收一個 A2ARequest
    2. 通過 Registry 發現候選代理
    3. 對候選代理進行多維評分
    4. 返回最優路由選擇

    這是系統成為「不可替代的結締組織」的關鍵——
    路由品質越高，越多代理願意通過此節點路由，
    越多流量 → 越多因果數據 → 路由品質進一步提升。
    這是一個正反饋迴路。
    """

    def __init__(
        self,
        registry: AgentRegistry,
        causal_tracker: CausalTracker,
        weights: Optional[RoutingWeights] = None,
        economics: Optional["EconomicsEngine"] = None,
    ):
        self.registry = registry
        self.causal = causal_tracker
        self.weights = weights or RoutingWeights()
        # EconomicsEngine reference for KVS capitalization scoring.
        # Optional — if None, falls back to raw causal_bonus (cold-start safe).
        self.economics = economics

    # ──────────────────────────────────────────────
    # Public routing API
    # ──────────────────────────────────────────────

    def route(self, request: A2ARequest) -> Optional[RouteScore]:
        """
        為一個請求選擇最優代理。
        返回 RouteScore 或 None (無可用代理)。

        探索-利用平衡：若前兩名分差 < 5%，使用加權隨機選擇
        避免系統陷入對單一代理的確定性偏愛。
        """
        candidates = self._gather_candidates(request)
        if not candidates:
            return None

        scored = [
            self._score(agent, cap, sim, request)
            for agent, cap, sim in candidates
        ]
        scored.sort(key=lambda s: s.total, reverse=True)

        # Exploration tie-break: top-2 within 5% → weighted random choice
        if len(scored) >= 2 and scored[0].total > 0:
            gap = (scored[0].total - scored[1].total) / scored[0].total
            if gap < 0.05:
                top_two = scored[:2]
                weights = [s.total for s in top_two]
                total_w = sum(weights)
                if total_w > 0:
                    probs = [w / total_w for w in weights]
                    return random.choices(top_two, weights=probs, k=1)[0]

        return scored[0]

    def route_multi(self, request: A2ARequest, top_k: int = 3) -> list[RouteScore]:
        """
        Fan-out 路由：返回前 k 個最優代理。
        用於需要多代理協作或冗餘執行的場景。
        """
        candidates = self._gather_candidates(request)
        if not candidates:
            return []

        scored = [
            self._score(agent, cap, sim, request)
            for agent, cap, sim in candidates
        ]
        scored.sort(key=lambda s: s.total, reverse=True)
        return scored[:top_k]

    # ──────────────────────────────────────────────
    # Internal: candidate gathering
    # ──────────────────────────────────────────────

    def _gather_candidates(
        self, request: A2ARequest
    ) -> list[tuple[AgentCard, Capability, float]]:
        """
        收集候選代理。

        Phase 1 — 精確名稱匹配（相似度固定為 1.0）。
        Phase 2 — 退回到 Jaccard 文本語義匹配（輕量，無需嵌入模型）。
        """
        # Phase 1: exact capability name lookup via inverted index
        exact_agents = self.registry.discover_by_name(request.capability)
        if exact_agents:
            candidates: list[tuple[AgentCard, Capability, float]] = []
            for agent in exact_agents:
                for cap in agent.capabilities:
                    if cap.name == request.capability:
                        candidates.append((agent, cap, 1.0))
                        break
            return candidates

        # Phase 2: Jaccard text-semantic fallback
        return self.registry.discover_by_text(request.capability, top_k=10)

    # ──────────────────────────────────────────────
    # Internal: multi-dimensional scoring (Φ core)
    # ──────────────────────────────────────────────

    def _score(
        self,
        agent: AgentCard,
        capability: Capability,
        capability_match: float,
        request: A2ARequest,
    ) -> RouteScore:
        """
        多維評分函數 (KVS-driven):

          score = w1·capability_match
                + w2·(1 − normalized_latency)
                + w3·reputation
                + w4·(1 − normalized_cost)
                + w5·kvs_score

        kvs_score is derived from KVS Capitalization K = r · max(0, 1 + Y):
          kvs_score = K / (K + K_ref)   where K_ref = 100

        This soft-sigmoid normalization preserves super-linear growth:
          - Cold agent (K=0):      kvs_score = 0.0
          - Baseline (K=100):     kvs_score = 0.5
          - Value-generating (K=300): kvs_score = 0.75
          - Monopoly (K=900):     kvs_score = 0.90

        Agents that generate real downstream causal value will form a monopoly
        on routing traffic through positive convexity (K grows faster than r).
        Falls back to raw causal_bonus when EconomicsEngine is not wired in.
        """
        w = self.weights
        _K_REF = 100.0  # soft-sigmoid reference point

        # 1. Capability match (from discovery phase, 0-1)
        cap_score = capability_match

        # 2. Latency score: lower is better; normalise against constraint ceiling
        max_latency = float(request.constraints.get("max_latency_ms", 10_000))
        if max_latency > 0:
            latency_score = max(0.0, 1.0 - capability.avg_latency_ms / max_latency)
        else:
            latency_score = 1.0

        # 3. Reputation (already normalised 0-1 by EconomicsEngine)
        rep_score = float(agent.reputation)

        # 4. Cost score: lower is better; normalise against constraint ceiling
        max_cost = float(request.constraints.get("max_cost", 1.0))
        if max_cost > 0:
            cost_score = max(0.0, 1.0 - capability.cost_per_call / max_cost)
        else:
            cost_score = 0.5  # unconstrained: neutral

        # 5. KVS Capitalization score — the super-linear routing signal.
        #    If economics engine is wired in, use K-based score.
        #    Otherwise fall back to raw causal_bonus (safe default for tests / cold start).
        if self.economics is not None:
            k = self.economics.get_kvs_capitalization(agent.agent_id)
            kvs_score = k / (k + _K_REF)   # soft-sigmoid: K_ref=100 → score=0.5
        else:
            kvs_score = self.causal.get_agent_causal_bonus(agent.agent_id)

        total = (
            w.capability  * cap_score
            + w.latency   * latency_score
            + w.reputation * rep_score
            + w.cost       * cost_score
            + w.causal     * kvs_score
        )

        return RouteScore(
            agent=agent,
            capability=capability,
            capability_match=cap_score,
            latency_score=latency_score,
            reputation_score=rep_score,
            cost_score=cost_score,
            causal_bonus=kvs_score,   # field kept for API compat; now carries kvs_score
            kvs_score=kvs_score,
            total=total,
        )

    # ──────────────────────────────────────────────
    # Ω → Φ feedback interface
    # ──────────────────────────────────────────────

    def update_weights_from_feedback(self, feedback: dict[str, float]) -> None:
        """
        Ω 算子的回饋介面：根據經濟層的信號動態調整路由權重。
        這是因果迴路 ∂ → Φ → Ω → ∂ 的閉合關鍵接縫。

        Accepted keys: 'capability', 'latency', 'reputation', 'cost', 'causal'.
        Unknown keys are silently ignored to allow partial updates.

        Note: weights are applied as-is; caller is responsible for ensuring
        they remain sensible (EconomicsEngine.generate_routing_feedback handles this).
        """
        if "capability" in feedback:
            self.weights.capability = float(feedback["capability"])
        if "latency" in feedback:
            self.weights.latency = float(feedback["latency"])
        if "reputation" in feedback:
            self.weights.reputation = float(feedback["reputation"])
        if "cost" in feedback:
            self.weights.cost = float(feedback["cost"])
        if "causal" in feedback:
            self.weights.causal = float(feedback["causal"])
