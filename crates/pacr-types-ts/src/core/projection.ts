// src/core/projection.ts
// π operator: PACR causal DAG → Agent interaction graph
//
// Mathematical definition:
// π: G_event = (I_event, Π) → G_agent = (I_agent, E_agent)
//
// Edge existence condition:
// (a_i → a_j) ∈ E_agent ⟺ ∃ ι_x, ι_y ∈ I_event :
//   ι_x.origin = a_i ∧ ι_y.origin = a_j ∧ ι_x ∈ Π(ι_y)

import type { AgentId } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type {
  AgentInteractionSummary,
  InteractionEdge,
} from '../types/agent-card.js';

// ─────────────────────────────────────────────
// Agent interaction graph (π operator output type)
// ─────────────────────────────────────────────

export interface AgentInteractionGraph {
  /** All agents that appeared in the record set */
  readonly agents: ReadonlySet<AgentId>;
  /** Directed edge set: Map<source_agent, Map<target_agent, edge_data>> */
  readonly edges: ReadonlyMap<AgentId, ReadonlyMap<AgentId, InteractionEdge>>;
}

// ─────────────────────────────────────────────
// Mutable internal state for incremental updates
// ─────────────────────────────────────────────

/** Welford online accumulator for a single directed edge */
interface MutableEdgeAccumulator {
  callCount: number;
  timeMean: number;
  timeM2: number; // Welford's sum of squared deviations from mean
  energyMean: number;
  energyM2: number;
  lastTimestampMs: number;
}

/**
 * Mutable graph state — the live accumulator for incremental projection.
 *
 * This is an opaque handle: callers obtain it via createProjectionState(),
 * feed records via ingestRecord(), and read results via snapshot().
 */
export interface ProjectionState {
  /** Internal — do not access directly */
  readonly _agents: Set<AgentId>;
  /** Internal — do not access directly */
  readonly _edges: Map<AgentId, Map<AgentId, MutableEdgeAccumulator>>;
}

// ─────────────────────────────────────────────
// State management
// ─────────────────────────────────────────────

/** Create a fresh, empty projection state */
export function createProjectionState(): ProjectionState {
  return {
    _agents: new Set<AgentId>(),
    _edges: new Map<AgentId, Map<AgentId, MutableEdgeAccumulator>>(),
  };
}

// ─────────────────────────────────────────────
// π operator: batch projection (reference implementation)
// ─────────────────────────────────────────────

/**
 * Batch-project a set of PACR records into an Agent interaction graph.
 *
 * Properties:
 * - Idempotent: same input → same output
 * - Deterministic: no external state dependency
 * - O(Σ |predecessors_i|) time
 */
export function projectToAgentGraph(
  records: Iterable<PACRecord>,
): AgentInteractionGraph {
  const state = createProjectionState();
  for (const record of records) {
    ingestRecord(state, record);
  }
  return snapshot(state);
}

// ─────────────────────────────────────────────
// π operator: incremental update — O(|predecessors|)
// ─────────────────────────────────────────────

/**
 * Ingest a single PACR record into the mutable projection state.
 *
 * Time complexity: O(|record.predecessors|)
 * Only the edges involving record.identity.origin and the origins of
 * its predecessors are touched. Nothing else is scanned.
 *
 * Callers should use snapshot() to obtain an immutable view after ingestion.
 */
export function ingestRecord(state: ProjectionState, record: PACRecord): void {
  const targetAgent = record.identity.origin;
  state._agents.add(targetAgent);

  for (const predEventId of record.predecessors) {
    const sourceAgent = extractOrigin(predEventId);
    state._agents.add(sourceAgent);

    let targetMap = state._edges.get(sourceAgent);
    if (targetMap === undefined) {
      targetMap = new Map<AgentId, MutableEdgeAccumulator>();
      state._edges.set(sourceAgent, targetMap);
    }

    let acc = targetMap.get(targetAgent);
    if (acc === undefined) {
      acc = {
        callCount: 0,
        timeMean: 0,
        timeM2: 0,
        energyMean: 0,
        energyM2: 0,
        lastTimestampMs: 0,
      };
      targetMap.set(targetAgent, acc);
    }

    accumulateEdge(acc, record);
  }
}

/**
 * Take an immutable snapshot of the current projection state.
 *
 * The returned AgentInteractionGraph is a frozen read-only view.
 * Subsequent ingestRecord() calls will NOT affect previously returned snapshots
 * because we create new Map/Set instances.
 */
export function snapshot(state: ProjectionState): AgentInteractionGraph {
  const agents = new Set(state._agents) as ReadonlySet<AgentId>;

  const edges = new Map<AgentId, ReadonlyMap<AgentId, InteractionEdge>>();
  for (const [source, targetMap] of state._edges) {
    const frozenTargetMap = new Map<AgentId, InteractionEdge>();
    for (const [target, acc] of targetMap) {
      frozenTargetMap.set(target, finalizeEdge(acc));
    }
    edges.set(source, frozenTargetMap);
  }

  return { agents, edges };
}

/**
 * Convenience: ingest a record and return a snapshot in one call.
 *
 * This is the "incremental projection" API:
 * - Mutates state in O(|predecessors|)
 * - Returns a new frozen snapshot
 */
export function projectIncremental(
  state: ProjectionState,
  newRecord: PACRecord,
): AgentInteractionGraph {
  ingestRecord(state, newRecord);
  return snapshot(state);
}

// ─────────────────────────────────────────────
// Projection result → AgentCard metadata
// ─────────────────────────────────────────────

/**
 * Extract a specific agent's interaction summary from the graph.
 * Written to AgentCard.metadata['pacr:interaction_summary'].
 */
export function extractAgentSummary(
  graph: AgentInteractionGraph,
  agentId: AgentId,
): AgentInteractionSummary {
  const callees = new Map<AgentId, InteractionEdge>();
  const callers = new Map<AgentId, InteractionEdge>();

  // Outgoing edges: this agent called whom
  const outEdges = graph.edges.get(agentId);
  if (outEdges !== undefined) {
    for (const [target, edge] of outEdges) {
      callees.set(target, edge);
    }
  }

  // Incoming edges: who called this agent
  for (const [source, targetMap] of graph.edges) {
    const edgeToMe = targetMap.get(agentId);
    if (edgeToMe !== undefined) {
      callers.set(source, edgeToMe);
    }
  }

  return { callees, callers };
}

// ─────────────────────────────────────────────
// Internal: Welford's online algorithm
// ─────────────────────────────────────────────

/**
 * Update the edge accumulator with one new record's measurements.
 * Uses Welford's online algorithm for numerically stable mean and variance.
 */
function accumulateEdge(
  acc: MutableEdgeAccumulator,
  record: PACRecord,
): void {
  acc.callCount += 1;
  const n = acc.callCount;

  const t = record.resources.time.estimate;
  const e = record.resources.energy.estimate;

  // Welford's online update for time
  const timeDelta = t - acc.timeMean;
  acc.timeMean += timeDelta / n;
  const timeDelta2 = t - acc.timeMean;
  acc.timeM2 += timeDelta * timeDelta2;

  // Welford's online update for energy
  const energyDelta = e - acc.energyMean;
  acc.energyMean += energyDelta / n;
  const energyDelta2 = e - acc.energyMean;
  acc.energyM2 += energyDelta * energyDelta2;

  // Track most recent timestamp
  const ts = record.identity.timestampMs;
  if (ts > acc.lastTimestampMs) {
    acc.lastTimestampMs = ts;
  }
}

/**
 * Finalize an edge accumulator into an immutable InteractionEdge.
 * Computes 95% confidence intervals from the Welford statistics.
 */
function finalizeEdge(acc: MutableEdgeAccumulator): InteractionEdge {
  const n = acc.callCount;
  const Z = 1.96; // 95% CI

  // Sample variance → standard error of the mean
  const timeVariance = n > 1 ? acc.timeM2 / (n - 1) : Infinity;
  const energyVariance = n > 1 ? acc.energyM2 / (n - 1) : Infinity;
  const timeStdErr = Math.sqrt(timeVariance / n);
  const energyStdErr = Math.sqrt(energyVariance / n);

  return {
    callCount: n,
    averageLatency: {
      estimate: acc.timeMean,
      lower: Math.max(0, acc.timeMean - Z * timeStdErr),
      upper: acc.timeMean + Z * timeStdErr,
    },
    averageEnergy: {
      estimate: acc.energyMean,
      lower: Math.max(0, acc.energyMean - Z * energyStdErr),
      upper: acc.energyMean + Z * energyStdErr,
    },
    lastInteractionTimestampMs: acc.lastTimestampMs,
  };
}
