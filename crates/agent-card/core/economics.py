"""
core/economics.py
=================
Economics Engine — 經濟計量與結算引擎

映射：Ω 耦合算子 (L5)
這是因果迴路閉合的最後一環：將因果鏈的結果
轉化為可量化的經濟信號，回饋到路由層和注冊表。

Ω 的職責：
1. 計量每次路由的計算成本和延遲
2. 收集外部價值信號（用戶評分、下游使用量等）
3. 計算代理信譽分
4. 生成結算記錄
5. 向路由器回饋權重調整建議

信譽公式：
  reputation = 0.4 * success_rate
             + 0.3 * normalized_value
             + 0.2 * consistency
             + 0.1 * tenure

因果迴路：因果鏈關閉 → meter() → compute_reputation() → Router 評分更新

TICK 38.0 — O(1) Cache-Line Aligned KVS Vectorization:
  Optional MLX acceleration layer maintains parallel 1D arrays of all agents'
  `total_calls_served` (r) and `meta_yield` (Y) values, padded to 128-byte
  M1 Ultra cache-line boundaries.  Enables O(1) batch KVS capitalization
  queries without Python loop overhead.

TICK 41.0 — Positive Convexity Exposure Surface (PCES):
  The membrane operator is extended to a "Dual-Sided Convex Engine".  When a
  causally-verified settlement exceeds PCES_TAIL_THRESHOLD, the system treats
  it as a Positive Black Swan and irreversibly widens the Causal Valve (β) for
  that agent class.  The enlarged β means every future signal from that agent
  delivers a super-linearly larger ledger update — the membrane geometrically
  deforms toward the positive tail.

  PCES formula:
    tail_agents      = {a : ledger[a].meta_yield ≥ PCES_TAIL_THRESHOLD}
    absolute_surface = Σ meta_yield  for a in tail_agents
    pces_fraction    = absolute_surface / max(Σ all meta_yield, ε)

  Membrane deformation (irreversible):
    β_new = min(β_old × PCES_TAIL_BETA_MULTIPLIER, PCES_MAX_BETA)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .protocol import AgentCard
from .registry import AgentRegistry
from .causal import CausalTracker

log = logging.getLogger(__name__)

# ── TICK 38.0: Optional MLX import for vectorized KVS buffers ────────────────
# MLX lives only on Apple Silicon / macOS.  The pure-Python path remains fully
# functional when MLX is absent (non-Apple hosts, CI environments).
try:
    import mlx.core as _mx
    _MLX_AVAILABLE = True
except Exception:
    _mx = None  # type: ignore[assignment]
    _MLX_AVAILABLE = False

# ── TICK 38.0: Cache-line alignment constant ─────────────────────────────────
# M1 Ultra cache line = 128 bytes.  float32 = 4 bytes → 32 floats per line.
_CACHELINE_FLOATS: int = 32

# ── TICK 41.0: PCES (Positive Convexity Exposure Surface) constants ───────────
# A single causally-verified settlement at or above this raw value_signal
# triggers a Positive Black Swan event and irreversible membrane deformation.
PCES_TAIL_THRESHOLD: float = 5.0
# β is multiplied by this factor on each deformation event.  Chosen so that
# three successive tail events bring β from the default 0.02 to ~0.054, and
# ten events approach the cap — a super-linear but bounded expansion.
PCES_TAIL_BETA_MULTIPLIER: float = 1.40
# Hard ceiling on β.  Prevents runaway valve opening from a single hostile
# agent flooding the system with high-value signals (Goodhart guard).
PCES_MAX_BETA: float = 0.50


def _pad_to_cacheline(n: int) -> int:
    """Round n up to the next multiple of _CACHELINE_FLOATS (128-byte boundary).

    Examples:
        _pad_to_cacheline(1)  → 32
        _pad_to_cacheline(32) → 32
        _pad_to_cacheline(33) → 64
        _pad_to_cacheline(64) → 64
    """
    if n <= 0:
        return _CACHELINE_FLOATS
    remainder = n % _CACHELINE_FLOATS
    return n if remainder == 0 else n + (_CACHELINE_FLOATS - remainder)


@dataclass
class AgentLedger:
    """單個代理的經濟帳本。"""
    agent_id: str
    total_revenue: float = 0.0         # 作為服務方獲得的總收入
    total_cost: float = 0.0            # 作為請求方支出的總成本
    total_calls_served: int = 0        # 服務的總請求數
    total_calls_made: int = 0          # 發起的總請求數
    total_value_generated: float = 0.0 # 累計外部價值信號 (β-dampened)
    last_settlement: float = field(default_factory=time.time)
    # ── KVS (Knowledge Value Standard) fields ──────────────────────────────
    # meta_yield (Y): accumulated β-weighted external value signals.
    # Outer-loop KVS formula: Y_new = Y_int + β * Y_ext
    # where Y_int is the internally-generated yield (currently 0; reserved for
    # future endogenous value sources) and β * Y_ext is the dampened signal.
    meta_yield: float = 0.0
    # beta_weight (β): the Causal Valve.  Starts very low to prevent Goodhart's
    # Law exploits from noisy external agents.  Will be raised by the governance
    # layer once an agent has demonstrated sustained causal reliability.
    beta_weight: float = 0.02
    # ── TICK 41.0: PCES membrane deformation counter ───────────────────────
    # Number of times this agent has triggered a Positive Black Swan event and
    # caused an irreversible β expansion.  Append-only — never decremented.
    deformation_count: int = 0


@dataclass
class Settlement:
    """結算記錄。"""
    agent_id: str
    period_start: float
    period_end: float
    net_balance: float  # revenue - cost
    reputation_delta: float
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MembraneDeformationEvent:
    """TICK 41.0 — Immutable record of a single PCES membrane deformation.

    Written once per Positive Black Swan event and appended to
    EconomicsEngine._deformation_log.  Never modified or deleted —
    the deformation history is the permanent audit trail of the membrane's
    geometric evolution toward positive tails.
    """
    agent_id: str
    trace_id: str
    raw_value_signal: float   # The raw Y_ext that triggered the deformation
    beta_before: float        # β value immediately before expansion
    beta_after: float         # β value immediately after expansion (irreversible)
    meta_yield_at_event: float  # Agent's cumulative Y after this settlement
    deformation_index: int    # 1-based: how many times this agent has deformed
    timestamp: float          # wall-clock seconds (time.time())


class EconomicsEngine:
    """
    Ω 經濟引擎 (L5)。

    核心迴路：
    因果鏈關閉 → meter() 記錄成本 → record_value() 記錄價值
    → compute_reputation() 更新信譽 → 信譽回饋到 Router 的評分函數
    → Router 做出更好的路由決策 → 產生更好的因果鏈 → ...

    這就是自我融資迴路的數學結構：Ω → Φ。

    TICK 38.0 addition: Optional MLX vectorized KVS buffers.
    When MLX is available, maintains parallel 1D float32 arrays of all agents'
    `total_calls_served` (r_buf) and `meta_yield` (y_buf) padded to 128-byte
    cache-line boundaries.  get_kvs_capitalization_batch() dispatches a single
    MLX kernel for O(1) batch computation.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        causal_tracker: CausalTracker,
    ):
        self.registry = registry
        self.causal = causal_tracker
        # agent_id → AgentLedger
        self._ledgers: dict[str, AgentLedger] = {}
        # TODO: Implement persistent DB/Redis storage here

        # ── TICK 41.0: PCES deformation audit log ────────────────────────
        # Append-only list of every membrane deformation event.  Never pruned.
        self._deformation_log: list[MembraneDeformationEvent] = []

        # ── TICK 38.0: MLX vectorized KVS buffers ────────────────────────
        self._agent_index: Dict[str, int] = {}   # agent_id → buffer slot
        self._buf_capacity: int = _pad_to_cacheline(8)  # start with 1 cache line
        if _MLX_AVAILABLE and _mx is not None:
            self._r_buf = _mx.zeros((self._buf_capacity,), dtype=_mx.float32)
            self._y_buf = _mx.zeros((self._buf_capacity,), dtype=_mx.float32)
        else:
            self._r_buf = None
            self._y_buf = None

    # ──────────────────────────────────────────────
    # Metering — Ω input side
    # ──────────────────────────────────────────────

    def meter(
        self,
        trace_id: str,
        agent_id: str,
        compute_cost: float,
        latency_ms: float,
        role: str = "server",  # "server" | "client"
    ) -> None:
        """
        計量一次交互的成本，並同步記錄到因果鏈。

        role="server"  → 代理作為提供者，增加 total_revenue
        role="client"  → 代理作為請求者，增加 total_cost
        """
        ledger = self._get_or_create_ledger(agent_id)

        if role == "server":
            ledger.total_revenue += compute_cost
            ledger.total_calls_served += 1
            # TICK 38.0: sync r (calls served) to vectorized buffer
            self._sync_to_vectors(agent_id)
        else:
            ledger.total_cost += compute_cost
            ledger.total_calls_made += 1

        # Mirror the metering event into the causal chain for full auditability
        self.causal.add_hop(
            trace_id=trace_id,
            agent_id=agent_id,
            action="meter",
            cost=compute_cost,
            latency_ms=latency_ms,
            metadata={"role": role},
        )

    def record_value(
        self,
        trace_id: str,
        agent_id: str,
        value_signal: float,
    ) -> bool:
        """
        Causal Settlement Oracle (CSO) — 因果結算神諭.

        Records an external value signal ONLY after verifying that a strictly
        closed causal loop exists for the given trace_id.  This is the primary
        defence against Goodhart's Law: no physical proof → no economic settlement.

        Verification protocol (all three must pass):
          1. trace_id exists in the CausalTracker's live chain store.
          2. The chain is closed (closed_at is not None).
          3. The chain has at least one "execute" hop — i.e. an agent actually did
             work on this trace, not merely a routing ghost.

        Causal Valve (β):
          Accepted signals are damped by ledger.beta_weight before entering the
          ledger:  Y_new = Y_int + β * Y_ext
          β defaults to 0.02 (very conservative) to prevent any single noisy
          external agent from flooding the KVS with unverified value.

        Returns:
          True  — signal accepted and settled.
          False — rejected (causal verification failed or evicted chain).
        """
        # ── Causal verification (O(1) dict lookup) ──────────────────────────
        chain = self.causal.get_chain(trace_id)

        if chain is None:
            log.warning(
                "[CSO] REJECTED trace_id=%s agent=%s value=%.4f — "
                "chain not found (may have been LRU-evicted). No settlement.",
                trace_id, agent_id, value_signal,
            )
            return False

        if chain.closed_at is None:
            log.warning(
                "[CSO] REJECTED trace_id=%s agent=%s value=%.4f — "
                "chain is still open (not yet closed). No settlement.",
                trace_id, agent_id, value_signal,
            )
            return False

        has_execute_hop = any(h.action == "execute" for h in chain.hops)
        if not has_execute_hop:
            log.warning(
                "[CSO] REJECTED trace_id=%s agent=%s value=%.4f — "
                "no 'execute' hop found; routing ghost, not real work.",
                trace_id, agent_id, value_signal,
            )
            return False

        # ── Causal Valve: apply β dampening (O(1) arithmetic) ───────────────
        ledger = self._get_or_create_ledger(agent_id)
        y_ext_damped = ledger.beta_weight * value_signal  # β * Y_ext

        # KVS outer-loop formula: Y_new = Y_int + β * Y_ext
        # Y_int is currently 0.0 (endogenous value sources reserved for future).
        ledger.meta_yield += y_ext_damped
        # total_value_generated tracks the same β-dampened accumulation so that
        # compute_reputation()'s normalized_value component stays consistent.
        ledger.total_value_generated += y_ext_damped

        # TICK 38.0: Sync to vectorized MLX buffers after ledger update.
        self._sync_to_vectors(agent_id)

        log.info(
            "[CSO] SETTLED trace_id=%s agent=%s raw_value=%.4f "
            "beta=%.4f y_ext_damped=%.6f meta_yield_now=%.6f",
            trace_id, agent_id, value_signal,
            ledger.beta_weight, y_ext_damped, ledger.meta_yield,
        )

        # ── TICK 41.0: PCES Positive Black Swan detection ───────────────────
        # If the raw value_signal (pre-β) exceeds the tail threshold, this
        # settlement qualifies as a Positive Black Swan event.  The membrane
        # deforms irreversibly: β is expanded so that all future signals from
        # this agent class deliver a super-linearly larger yield.
        if value_signal >= PCES_TAIL_THRESHOLD:
            beta_before = ledger.beta_weight
            beta_after = min(
                ledger.beta_weight * PCES_TAIL_BETA_MULTIPLIER,
                PCES_MAX_BETA,
            )
            ledger.beta_weight = beta_after
            ledger.deformation_count += 1

            event = MembraneDeformationEvent(
                agent_id=agent_id,
                trace_id=trace_id,
                raw_value_signal=value_signal,
                beta_before=beta_before,
                beta_after=beta_after,
                meta_yield_at_event=ledger.meta_yield,
                deformation_index=ledger.deformation_count,
                timestamp=time.time(),
            )
            self._deformation_log.append(event)

            log.warning(
                "[PCES] MEMBRANE DEFORMED agent=%s deformation=#%d "
                "raw_value=%.4f beta %.4f → %.4f meta_yield_now=%.6f",
                agent_id, ledger.deformation_count,
                value_signal, beta_before, beta_after, ledger.meta_yield,
            )

        return True

    # ──────────────────────────────────────────────
    # Reputation computation — the Ω → L1 write-back
    # ──────────────────────────────────────────────

    def compute_reputation(self, agent_id: str) -> float:
        """
        計算代理信譽分 (0.0 – 1.0) 並寫回 AgentCard.reputation。

        Formula:
            reputation = 0.4 * success_rate
                       + 0.3 * normalized_value
                       + 0.2 * consistency
                       + 0.1 * tenure_score

        - success_rate: 來自 L4 CausalTracker 的歷史統計
        - normalized_value: 每次服務平均產生的外部價值，上限 1.0
        - consistency: 高成功率 ≈ 高一致性（此處的簡化近似）
        - tenure_score: 代理存活時長的對數正則化（24h → 1.0）

        此值直接寫入 AgentCard.reputation，通過 L3 Router 的評分函數
        影響後續路由決策——這是 Ω → Φ 迴路的物理接縫。
        """
        causal_stats = self.causal.get_agent_stats(agent_id)
        ledger = self._get_or_create_ledger(agent_id)

        # Component 1: success rate (from L4)
        success_rate = causal_stats.get("success_rate", 0.5)

        # Component 2: normalised value per call
        total_served = max(ledger.total_calls_served, 1)
        avg_value = ledger.total_value_generated / total_served
        normalized_value = min(1.0, avg_value)

        # Component 3: consistency (simplified: mirrors success_rate)
        consistency = success_rate

        # Component 4: tenure — how long this agent has been online
        agent = self.registry.get_agent(agent_id)
        if agent is not None:
            tenure_seconds = time.time() - agent.registered_at
            tenure_score = min(1.0, tenure_seconds / 86_400.0)  # 1 day → 1.0
        else:
            tenure_score = 0.0

        reputation = (
            0.4 * success_rate
            + 0.3 * normalized_value
            + 0.2 * consistency
            + 0.1 * tenure_score
        )

        # Write back to AgentCard so Router sees up-to-date value immediately
        if agent is not None:
            agent.reputation = reputation

        return reputation

    def get_kvs_capitalization(self, agent_id: str) -> float:
        """
        KVS Capitalization K — 知識價值標準資本化係數.

        Formula:  K = r · max(0, 1 + Y)

        Where:
          r = total_calls_served  — the reuse/success count (exposure breadth)
          Y = meta_yield          — accumulated β-dampened external value signals

        Interpretation:
          - A new agent (r=0) has K=0 — no routing advantage.
          - An agent with r=1000 and Y=0 has K=1000 — linear baseline.
          - An agent with r=1000 and Y=0.5 has K=1500 — super-linear bonus.
          - An agent with r=1000 and Y=2.0 has K=3000 — monopoly formation.

        The (1 + Y) multiplier creates positive convexity: agents that generate
        real downstream value capture a disproportionate share of routing traffic.
        This is the mathematical core of the infrastructure monopoly flywheel.

        Pure O(1) arithmetic.  No I/O.
        """
        ledger = self._get_or_create_ledger(agent_id)
        r = float(ledger.total_calls_served)
        y = ledger.meta_yield
        return r * max(0.0, 1.0 + y)

    # ──────────────────────────────────────────────
    # Ledger & settlement
    # ──────────────────────────────────────────────

    # ── TICK 41.0: PCES observable metric ────────────────────────────────────

    def get_pces_metric(self) -> dict:
        """Positive Convexity Exposure Surface (PCES) — observable membrane state.

        Computes:
          tail_agents      — agent IDs whose meta_yield ≥ PCES_TAIL_THRESHOLD
          absolute_surface — Σ meta_yield for all tail agents (raw area)
          total_yield      — Σ meta_yield across all agents
          pces_fraction    — absolute_surface / max(total_yield, 1e-9)
                             → fraction of total value flowing through tails
          deformation_log_count — number of irreversible membrane deformations
                                   recorded since engine init
          tail_agent_betas — dict of {agent_id: beta_weight} for tail agents
                             showing the expanded valves

        Returns a pure-Python dict; no I/O, O(n_agents) time.
        """
        tail_agents: list[str] = []
        absolute_surface: float = 0.0
        total_yield: float = 0.0
        tail_betas: dict[str, float] = {}

        for agent_id, ledger in self._ledgers.items():
            y = ledger.meta_yield
            total_yield += y
            # Tail classification: agent has experienced at least one irreversible
            # membrane deformation (Positive Black Swan event).  Using deformation_count
            # rather than raw meta_yield because β-dampening means the accumulated yield
            # is always << the raw signal threshold; the deformation flag is the canonical
            # record that a tail event actually occurred.
            if ledger.deformation_count > 0:
                tail_agents.append(agent_id)
                absolute_surface += y
                tail_betas[agent_id] = ledger.beta_weight

        pces_fraction = absolute_surface / max(total_yield, 1e-9)

        return {
            "tail_agents": tail_agents,
            "absolute_surface": absolute_surface,
            "total_yield": total_yield,
            "pces_fraction": pces_fraction,
            "deformation_log_count": len(self._deformation_log),
            "tail_agent_betas": tail_betas,
            "pces_tail_threshold": PCES_TAIL_THRESHOLD,
        }

    def get_deformation_log(self) -> list[MembraneDeformationEvent]:
        """Return a copy of the append-only membrane deformation audit log."""
        return list(self._deformation_log)

    def get_ledger(self, agent_id: str) -> dict:
        """獲取代理的經濟帳本快照，附帶即時計算的信譽分和KVS資本化係數。"""
        ledger = self._get_or_create_ledger(agent_id)
        return {
            "agent_id": agent_id,
            "total_revenue": ledger.total_revenue,
            "total_cost": ledger.total_cost,
            "net_balance": ledger.total_revenue - ledger.total_cost,
            "total_calls_served": ledger.total_calls_served,
            "total_calls_made": ledger.total_calls_made,
            "total_value_generated": ledger.total_value_generated,
            "meta_yield": ledger.meta_yield,
            "beta_weight": ledger.beta_weight,
            "deformation_count": ledger.deformation_count,
            "kvs_capitalization": self.get_kvs_capitalization(agent_id),
            "reputation": self.compute_reputation(agent_id),
        }

    def compute_settlement(self, period_hours: float = 24.0) -> list[Settlement]:
        """
        計算一個結算週期內的帳目快照。
        這是未來接入支付層或代幣合約的預留介面。
        """
        now = time.time()
        period_start = now - (period_hours * 3_600.0)
        settlements: list[Settlement] = []

        for agent_id, ledger in self._ledgers.items():
            net = ledger.total_revenue - ledger.total_cost
            rep = self.compute_reputation(agent_id)

            settlements.append(Settlement(
                agent_id=agent_id,
                period_start=period_start,
                period_end=now,
                net_balance=net,
                reputation_delta=rep - 0.5,  # delta relative to neutral baseline
                details=self.get_ledger(agent_id),
            ))

        return settlements

    # ──────────────────────────────────────────────
    # Ω → Φ feedback channel — the loop closure
    # ──────────────────────────────────────────────

    def generate_routing_feedback(self) -> dict[str, float]:
        """
        生成路由權重調整建議（Ω → Φ 的回饋通道）。

        邏輯：
        - global_success_rate < 0.70  → elevate reputation & capability weights
          (prioritise proven agents over cheap/fast ones)
        - avg_latency_ms > 5 000      → elevate latency weight
          (network is slow; latency becomes the bottleneck)

        Returns a partial dict; Router.update_weights_from_feedback() ignores
        missing keys, so only the dimensions that need adjustment are returned.
        """
        global_stats = self.causal.get_global_stats()
        success_rate = global_stats.get("global_success_rate", 1.0)
        avg_latency = global_stats.get("avg_latency_ms", 0.0)

        feedback: dict[str, float] = {}

        # Signal 1: quality is degrading — trust reputation more
        if success_rate < 0.70:
            feedback["reputation"] = 0.35
            feedback["capability"] = 0.35
            # Reduce cost weight to avoid routing to cheap-but-failing agents
            feedback["cost"] = 0.05

        # Signal 2: latency is the bottleneck
        if avg_latency > 5_000:
            feedback["latency"] = 0.30
            # Pull back from cost to compensate (weights must stay balanced)
            if "cost" not in feedback:
                feedback["cost"] = 0.05

        return feedback

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _get_or_create_ledger(self, agent_id: str) -> AgentLedger:
        """懶加載代理帳本：首次訪問時創建，後續直接返回。"""
        if agent_id not in self._ledgers:
            self._ledgers[agent_id] = AgentLedger(agent_id=agent_id)
        return self._ledgers[agent_id]

    # ── TICK 38.0: Cache-Line Aligned Vectorized KVS ─────────────────────────

    def _sync_to_vectors(self, agent_id: str) -> None:
        """Sync a single agent's r and Y scalars into the MLX buffer arrays.

        Called after any ledger update that changes total_calls_served or
        meta_yield.  Maintains the vectorized buffers in sync with the
        authoritative Python dict ledgers so get_kvs_capitalization_batch()
        can run entirely in the MLX kernel without Python loops.

        Buffer growth: when the agent_index is full, doubles capacity and
        re-allocates both buffers preserving existing data.

        No-op if MLX is unavailable.
        """
        if not _MLX_AVAILABLE or _mx is None or self._r_buf is None:
            return

        # Assign a buffer slot if this is the first time we see this agent
        if agent_id not in self._agent_index:
            slot = len(self._agent_index)
            if slot >= self._buf_capacity:
                # Grow: double capacity, pad to cache-line boundary
                new_cap = _pad_to_cacheline(self._buf_capacity * 2)
                r_new = _mx.zeros((new_cap,), dtype=_mx.float32)
                y_new = _mx.zeros((new_cap,), dtype=_mx.float32)
                # Copy old data via concatenation
                pad_r = _mx.zeros((new_cap - self._buf_capacity,), dtype=_mx.float32)
                pad_y = _mx.zeros((new_cap - self._buf_capacity,), dtype=_mx.float32)
                self._r_buf = _mx.concatenate([self._r_buf, pad_r])
                self._y_buf = _mx.concatenate([self._y_buf, pad_y])
                self._buf_capacity = new_cap
            self._agent_index[agent_id] = slot

        slot = self._agent_index[agent_id]
        ledger = self._ledgers.get(agent_id)
        if ledger is None:
            return

        # MLX arrays are immutable — build new arrays with the updated slice.
        # For buffer sizes ≤ 1024 agents this is effectively O(1) amortised.
        r_vals = self._r_buf.tolist()
        y_vals = self._y_buf.tolist()
        r_vals[slot] = float(ledger.total_calls_served)
        y_vals[slot] = float(ledger.meta_yield)
        self._r_buf = _mx.array(r_vals, dtype=_mx.float32)
        self._y_buf = _mx.array(y_vals, dtype=_mx.float32)

    def get_kvs_capitalization_batch(
        self,
        agent_ids: List[str],
    ) -> Dict[str, float]:
        """Vectorized batch KVS capitalization: K = r * max(0, 1 + Y).

        When MLX is available, dispatches a single Metal kernel for all agents
        in one shot — O(1) amortised wall-clock regardless of batch size.

        When MLX is unavailable, falls back to per-agent scalar computation
        (same results, Python loop overhead).

        Args:
            agent_ids: List of agent IDs to compute capitalization for.

        Returns:
            Dict mapping agent_id → float capitalization score K.
        """
        if not agent_ids:
            return {}

        if _MLX_AVAILABLE and _mx is not None and self._r_buf is not None:
            # Collect buffer slots (fall back to scalar for unseen agents)
            slots: List[int] = []
            unvectorized: List[str] = []
            for aid in agent_ids:
                if aid in self._agent_index:
                    slots.append(self._agent_index[aid])
                else:
                    unvectorized.append(aid)

            results: Dict[str, float] = {}

            if slots:
                # Gather from the cache-line-aligned buffers
                idx = _mx.array(slots, dtype=_mx.uint32)
                r_slice = self._r_buf[idx]
                y_slice = self._y_buf[idx]
                # K = r * max(0, 1 + Y)  — single kernel dispatch
                K = r_slice * _mx.maximum(
                    _mx.zeros_like(r_slice), _mx.ones_like(r_slice) + y_slice
                )
                _mx.eval(K)  # materialise on Metal
                k_list = K.tolist()
                for i, slot in enumerate(slots):
                    # Find the agent_id for this slot
                    aid = agent_ids[i]
                    results[aid] = float(k_list[i])

            # Scalar fallback for agents not yet in buffers
            for aid in unvectorized:
                results[aid] = self.get_kvs_capitalization(aid)

            return results

        # Pure-Python fallback (no MLX)
        return {aid: self.get_kvs_capitalization(aid) for aid in agent_ids}
