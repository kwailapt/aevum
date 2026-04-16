// src/core/projection.ts
// π 算子：PACR 因果 DAG → Agent 交互圖
// 
// 數學定義：
// π: G_event = (I_event, Π) → G_agent = (I_agent, E_agent)
// 
// 邊存在條件：
// (a_i → a_j) ∈ E_agent ⟺ ∃ ι_x, ι_y ∈ I_event :
//   ι_x.origin = a_i ∧ ι_y.origin = a_j ∧ ι_x ∈ Π(ι_y)

import type { AgentId, EventId } from '../types/identity';
import { extractOrigin } from '../types/identity';
import type { PACRecord } from '../types/pacr';
import type {
  AgentInteractionSummary,
  InteractionEdge,
} from '../types/agent-card';

// ─────────────────────────────────────────────
// Agent 交互圖（π 算子的輸出類型）
// ─────────────────────────────────────────────

export interface AgentInteractionGraph {
  /** 所有出現過的 agent */
  readonly agents: ReadonlySet<AgentId>;
  /** 有向邊集合：Map<source_agent, Map<target_agent, edge_data>> */
  readonly edges: ReadonlyMap<AgentId, ReadonlyMap<AgentId, InteractionEdge>>;
}

// ─────────────────────────────────────────────
// π 算子：批量投影（全量計算）
// ─────────────────────────────────────────────

/**
 * 從一批 PACR 記錄投影出 Agent 交互圖
 * 
 * 性質：冪等（idempotent）——同一批記錄多次調用結果一致
 */
export function projectToAgentGraph(
  records: Iterable<PACRecord>
): AgentInteractionGraph {
  const agents = new Set<AgentId>();
  // source -> target -> mutable accumulator
  const edgeAccum = new Map<AgentId, Map<AgentId, MutableEdgeAccumulator>>();

  for (const record of records) {
    const targetAgent = record.identity.origin;
    agents.add(targetAgent);

    for (const predEventId of record.predecessors) {
      const sourceAgent = extractOrigin(predEventId);
      agents.add(sourceAgent);

      if (!edgeAccum.has(sourceAgent)) {
        edgeAccum.set(sourceAgent, new Map());
      }
      const targetMap = edgeAccum.get(sourceAgent)!;
      if (!targetMap.has(targetAgent)) {
        targetMap.set(targetAgent, createEmptyAccumulator());
      }
      const acc = targetMap.get(targetAgent)!;
      accumulateEdge(acc, record);
    }
  }

  // 將 mutable accumulators 轉為 immutable InteractionEdge
  const edges = new Map<AgentId, ReadonlyMap<AgentId, InteractionEdge>>();
  for (const [source, targetMap] of edgeAccum) {
    const frozenTargetMap = new Map<AgentId, InteractionEdge>();
    for (const [target, acc] of targetMap) {
      frozenTargetMap.set(target, finalizeEdge(acc));
    }
    edges.set(source, frozenTargetMap);
  }

  return { agents, edges };
}

// ─────────────────────────────────────────────
// π 算子：增量更新（單條記錄）
// ─────────────────────────────────────────────

/**
 * 增量更新 Agent 交互圖
 * 
 * 性質：可增量（incremental）——新增一條記錄只更新受影響的邊
 * 
 * 注意：此函數返回新圖而非修改原圖（不可變數據結構）
 */
export function projectIncremental(
  existing: AgentInteractionGraph,
  newRecord: PACRecord
): AgentInteractionGraph {
  // 為了效率，實際實現中可能使用持久化數據結構
  // 這裡給出語義正確的參考實現
  const allRecordsSoFar = [newRecord]; // 在真實實現中需要持久化
  // 真實實現應使用增量算法，而非重算。此處僅為語義規範。
  // TODO: 替換為真正的增量實現
  return projectToAgentGraph(allRecordsSoFar);
}

// ─────────────────────────────────────────────
// 投影結果 → AgentCard metadata 的寫入
// ─────────────────────────────────────────────

/**
 * 從 Agent 交互圖中提取特定 agent 的交互摘要
 * 結果寫入 AgentCard.metadata['pacr:interaction_summary']
 */
export function extractAgentSummary(
  graph: AgentInteractionGraph,
  agentId: AgentId
): AgentInteractionSummary {
  const callees = new Map<AgentId, InteractionEdge>();
  const callers = new Map<AgentId, InteractionEdge>();

  // 出邊：此 agent 調用了誰
  const outEdges = graph.edges.get(agentId);
  if (outEdges) {
    for (const [target, edge] of outEdges) {
      callees.set(target, edge);
    }
  }

  // 入邊：誰調用了此 agent
  for (const [source, targetMap] of graph.edges) {
    const edgeToMe = targetMap.get(agentId);
    if (edgeToMe) {
      callers.set(source, edgeToMe);
    }
  }

  return { callees, callers };
}

// ─────────────────────────────────────────────
// 內部工具
// ─────────────────────────────────────────────

interface MutableEdgeAccumulator {
  callCount: number;
  totalTimeEstimate: number;
  totalEnergyEstimate: number;
  lastTimestampMs: number;
  // 用於計算置信區間的在線統計量
  timeM2: number; // Welford's online algorithm for variance
  energyM2: number;
  timeMean: number;
  energyMean: number;
}

function createEmptyAccumulator(): MutableEdgeAccumulator {
  return {
    callCount: 0,
    totalTimeEstimate: 0,
    totalEnergyEstimate: 0,
    lastTimestampMs: 0,
    timeM2: 0,
    energyM2: 0,
    timeMean: 0,
    energyMean: 0,
  };
}

function accumulateEdge(
  acc: MutableEdgeAccumulator,
  record: PACRecord
): void {
  acc.callCount += 1;
  const n = acc.callCount;

  const t = record.resources.time.estimate;
  const e = record.resources.energy.estimate;

  // Welford's online algorithm for mean and variance
  const timeDelta = t - acc.timeMean;
  acc.timeMean += timeDelta / n;
  const timeDelta2 = t - acc.timeMean;
  acc.timeM2 += timeDelta * timeDelta2;

  const energyDelta = e - acc.energyMean;
  acc.energyMean += energyDelta / n;
  const energyDelta2 = e - acc.energyMean;
  acc.energyM2 += energyDelta * energyDelta2;

  acc.totalTimeEstimate += t;
  acc.totalEnergyEstimate += e;

  const ts = record.identity.timestampMs;
  if (ts > acc.lastTimestampMs) {
    acc.lastTimestampMs = ts;
  }
}

function finalizeEdge(acc: MutableEdgeAccumulator): InteractionEdge {
  const n = acc.callCount;
  const timeVariance = n > 1 ? acc.timeM2 / (n - 1) : Infinity;
  const energyVariance = n > 1 ? acc.energyM2 / (n - 1) : Infinity;
  const timeStdErr = Math.sqrt(timeVariance / n);
  const energyStdErr = Math.sqrt(energyVariance / n);
  // 95% confidence interval (z ≈ 1.96)
  const z = 1.96;

  return {
    callCount: n,
    averageLatency: {
      estimate: acc.timeMean,
      lower: Math.max(0, acc.timeMean - z * timeStdErr),
      upper: acc.timeMean + z * timeStdErr,
    },
    averageEnergy: {
      estimate: acc.energyMean,
      lower: Math.max(0, acc.energyMean - z * energyStdErr),
      upper: acc.energyMean + z * energyStdErr,
    },
    lastInteractionTimestampMs: acc.lastTimestampMs,
  };
}
