// src/compliance/projection-compliance.test.ts
// Property-based compliance tests for the π projection operator.
// Black-box tests: only use public API surfaces.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { AgentId, EventId, EventIdStructure } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import { createAgentId, createEventId } from '../core/identity.js';
import {
  projectToAgentGraph,
  createProjectionState,
  ingestRecord,
  snapshot,
  extractAgentSummary,
} from '../core/projection.js';

// ─────────────────────────────────────────────
// Test helpers: PACR record generation
// ─────────────────────────────────────────────

/** Create a minimal valid PACRecord for a given agent with specified predecessors */
function makePACRecord(
  origin: AgentId,
  predecessors: EventId[],
  opts?: { timeEstimate?: number; energyEstimate?: number },
): PACRecord {
  const event = createEventId(origin);
  const timeEst = opts?.timeEstimate ?? 0.1;
  const energyEst = opts?.energyEstimate ?? 0.001;
  return {
    identity: event,
    predecessors: new Set(predecessors),
    landauerCost: { estimate: 0, lower: 0, upper: Infinity },
    resources: {
      energy: { estimate: energyEst, lower: 0, upper: energyEst * 2 },
      time: { estimate: timeEst, lower: 0, upper: timeEst * 2 },
      space: { estimate: 1024, lower: 0, upper: 2048 },
    },
    cognitiveSplit: {
      statisticalComplexity: { estimate: 0, lower: 0, upper: Infinity },
      entropyRate: { estimate: 0, lower: 0, upper: Infinity },
    },
    payload: new Uint8Array(0),
  };
}

/**
 * Generate a coherent scenario: N agents, each producing events,
 * some events referencing predecessors from other agents.
 *
 * Returns an array of PACRecords with valid causal structure.
 */
function scenarioArbitrary(
  agentCount: number,
  recordsPerAgent: number,
): fc.Arbitrary<PACRecord[]> {
  return fc.constant(null).map(() => {
    const agents: AgentId[] = [];
    for (let i = 0; i < agentCount; i++) {
      agents.push(createAgentId());
    }

    // Each agent produces some events; we track them for predecessor references
    const eventPool: EventIdStructure[] = [];
    const records: PACRecord[] = [];

    for (let round = 0; round < recordsPerAgent; round++) {
      for (const agent of agents) {
        // Pick predecessors from the existing event pool (events from OTHER agents)
        const predecessors: EventId[] = [];
        for (const past of eventPool) {
          if (past.origin !== agent && Math.random() < 0.3) {
            predecessors.push(past.id);
          }
        }

        const timeEst = 0.01 + Math.random() * 0.5;
        const energyEst = 0.0001 + Math.random() * 0.01;
        const record = makePACRecord(agent, predecessors, {
          timeEstimate: timeEst,
          energyEstimate: energyEst,
        });
        records.push(record);
        eventPool.push(record.identity);
      }
    }

    return records;
  });
}

/** Count total directed edges in the graph (sum of inner map sizes) */
function countGraphEdges(
  edges: ReadonlyMap<AgentId, ReadonlyMap<AgentId, unknown>>,
): number {
  let count = 0;
  for (const [, targetMap] of edges) {
    count += targetMap.size;
  }
  return count;
}

/** Count total causal edges across all records (sum of predecessor set sizes) */
function countRecordEdges(records: PACRecord[]): number {
  let count = 0;
  for (const r of records) {
    count += r.predecessors.size;
  }
  return count;
}

/**
 * Count distinct (sourceAgent, targetAgent) pairs across all records.
 * This is the true upper bound for graph edges — records with the same
 * agent pair contribute to the SAME graph edge.
 */
function countDistinctAgentPairs(records: PACRecord[]): number {
  const pairs = new Set<string>();
  for (const record of records) {
    const targetAgent = record.identity.origin as string;
    for (const predId of record.predecessors) {
      const sourceAgent = extractOrigin(predId) as string;
      pairs.add(`${sourceAgent}->${targetAgent}`);
    }
  }
  return pairs.size;
}

// ─────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────

describe('Projection Operator (π) Compliance', () => {
  // ─────────────────────────────────────────────
  // Property 1: Edge count bound
  // Graph edges ≤ distinct (source,target) agent pairs in records
  // (projection merges per-event edges into per-agent edges)
  // ─────────────────────────────────────────────
  it('P1: graph edge count ≤ distinct agent pairs in records', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(4, 3),
        (records) => {
          const graph = projectToAgentGraph(records);
          const graphEdges = countGraphEdges(graph.edges);
          const distinctPairs = countDistinctAgentPairs(records);
          expect(graphEdges).toBeLessThanOrEqual(distinctPairs);
          // Equality holds because each pair appears at least once
          expect(graphEdges).toBe(distinctPairs);
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 2: No ghost agents
  // ∀ agent in output.agents, ∃ record r where r.identity.origin = agent
  //   OR agent appears as extractOrigin(pred) for some record
  // ─────────────────────────────────────────────
  it('P2: no ghost agents — every agent is witnessed by a record', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(5, 2),
        (records) => {
          const graph = projectToAgentGraph(records);

          // Collect all agents that appear in the records
          const witnessedAgents = new Set<AgentId>();
          for (const r of records) {
            witnessedAgents.add(r.identity.origin);
            for (const predId of r.predecessors) {
              witnessedAgents.add(extractOrigin(predId));
            }
          }

          // Every agent in the graph must be witnessed
          for (const agent of graph.agents) {
            expect(witnessedAgents.has(agent)).toBe(true);
          }

          // And conversely: every witnessed agent must be in the graph
          for (const agent of witnessedAgents) {
            expect(graph.agents.has(agent)).toBe(true);
          }
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 3: Incremental === Batch equivalence
  // Feeding records one-by-one into ingestRecord() then snapshot()
  // produces identical structure to projectToAgentGraph()
  // ─────────────────────────────────────────────
  it('P3: incremental accumulation ≡ batch projection', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(4, 3),
        (records) => {
          // Batch
          const batchGraph = projectToAgentGraph(records);

          // Incremental
          const state = createProjectionState();
          for (const record of records) {
            ingestRecord(state, record);
          }
          const incGraph = snapshot(state);

          // Same agent set
          expect(new Set(incGraph.agents)).toEqual(new Set(batchGraph.agents));

          // Same edge structure
          expect(incGraph.edges.size).toBe(batchGraph.edges.size);

          for (const [source, batchTargetMap] of batchGraph.edges) {
            const incTargetMap = incGraph.edges.get(source);
            expect(incTargetMap).toBeDefined();
            expect(incTargetMap!.size).toBe(batchTargetMap.size);

            for (const [target, batchEdge] of batchTargetMap) {
              const incEdge = incTargetMap!.get(target);
              expect(incEdge).toBeDefined();
              expect(incEdge!.callCount).toBe(batchEdge.callCount);
              expect(incEdge!.averageLatency.estimate).toBeCloseTo(
                batchEdge.averageLatency.estimate,
                10,
              );
              expect(incEdge!.averageEnergy.estimate).toBeCloseTo(
                batchEdge.averageEnergy.estimate,
                10,
              );
              expect(incEdge!.lastInteractionTimestampMs).toBe(
                batchEdge.lastInteractionTimestampMs,
              );
            }
          }
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 4: Idempotency
  // projectToAgentGraph(records) called twice → same result
  // ─────────────────────────────────────────────
  it('P4: batch projection is idempotent', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(3, 3),
        (records) => {
          const g1 = projectToAgentGraph(records);
          const g2 = projectToAgentGraph(records);

          expect(new Set(g1.agents)).toEqual(new Set(g2.agents));

          for (const [source, targetMap1] of g1.edges) {
            const targetMap2 = g2.edges.get(source);
            expect(targetMap2).toBeDefined();
            for (const [target, edge1] of targetMap1) {
              const edge2 = targetMap2!.get(target);
              expect(edge2).toBeDefined();
              expect(edge2!.callCount).toBe(edge1.callCount);
              expect(edge2!.averageLatency.estimate).toBeCloseTo(
                edge1.averageLatency.estimate,
                10,
              );
              expect(edge2!.averageEnergy.estimate).toBeCloseTo(
                edge1.averageEnergy.estimate,
                10,
              );
            }
          }
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 5: No ghost edges
  // Every edge in the graph must be witnessed by a (predecessor, record) pair
  // ─────────────────────────────────────────────
  it('P5: no ghost edges — every edge is witnessed by records', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(4, 3),
        (records) => {
          const graph = projectToAgentGraph(records);

          // Collect all witnessed agent-level edges
          const witnessedEdges = new Set<string>();
          for (const record of records) {
            const target = record.identity.origin as string;
            for (const predId of record.predecessors) {
              const source = extractOrigin(predId) as string;
              witnessedEdges.add(`${source}->${target}`);
            }
          }

          // Every graph edge must have a witness
          for (const [source, targetMap] of graph.edges) {
            for (const [target] of targetMap) {
              const key = `${source as string}->${target as string}`;
              expect(witnessedEdges.has(key)).toBe(true);
            }
          }
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 6: Empty input → empty graph
  // ─────────────────────────────────────────────
  it('P6: empty records → empty graph', () => {
    const graph = projectToAgentGraph([]);
    expect(graph.agents.size).toBe(0);
    expect(graph.edges.size).toBe(0);
  });

  // ─────────────────────────────────────────────
  // Property 7: Genesis events (no predecessors) add agents but no edges
  // ─────────────────────────────────────────────
  it('P7: genesis events create agents but no edges', () => {
    fc.assert(
      fc.property(
        fc.constant(null).map(() => {
          const agents = [createAgentId(), createAgentId(), createAgentId()];
          return agents.map((a) => makePACRecord(a, []));
        }),
        (records) => {
          const graph = projectToAgentGraph(records);
          // Agents with no predecessors appear in the graph as isolated nodes
          // But since they have no predecessors, they generate no edges.
          // They also won't appear in graph.agents because they are neither
          // the origin of a predecessor nor a target of an edge.
          // Actually: they ARE targets — they are record.identity.origin.
          // Wait — looking at the code: we only add agents when processing
          // predecessor edges. Let me check...
          //
          // In ingestRecord: we add targetAgent to agents, THEN iterate predecessors.
          // So genesis events DO appear in agents but create no edges. ✓
          expect(graph.agents.size).toBe(records.length);
          expect(countGraphEdges(graph.edges)).toBe(0);
        },
      ),
      { numRuns: 50 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 8: extractAgentSummary consistency
  // ─────────────────────────────────────────────
  it('P8: extractAgentSummary callees/callers are consistent with graph edges', () => {
    fc.assert(
      fc.property(
        scenarioArbitrary(4, 3),
        (records) => {
          const graph = projectToAgentGraph(records);

          for (const agent of graph.agents) {
            const summary = extractAgentSummary(graph, agent);

            // Callees should match outgoing edges
            const outEdges = graph.edges.get(agent);
            if (outEdges !== undefined) {
              expect(summary.callees.size).toBe(outEdges.size);
              for (const [target, edge] of outEdges) {
                expect(summary.callees.get(target)).toEqual(edge);
              }
            } else {
              expect(summary.callees.size).toBe(0);
            }

            // Callers should match all incoming edges
            let expectedCallerCount = 0;
            for (const [source, targetMap] of graph.edges) {
              const edgeToAgent = targetMap.get(agent);
              if (edgeToAgent !== undefined) {
                expectedCallerCount++;
                expect(summary.callers.get(source)).toEqual(edgeToAgent);
              }
            }
            expect(summary.callers.size).toBe(expectedCallerCount);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 9: Welford statistics correctness
  // For single-sample edges, CI should be [0, Infinity-ish]
  // For multi-sample edges, mean should be close to naive mean
  // ─────────────────────────────────────────────
  it('P9: Welford statistics match naive computation', () => {
    const agentA = createAgentId();
    const agentB = createAgentId();

    const times = [0.1, 0.2, 0.15, 0.12, 0.18];
    const energies = [0.001, 0.002, 0.0015, 0.0012, 0.0018];

    // Create records: A → B (agentA's events are predecessors of agentB's events)
    const records: PACRecord[] = [];
    const agentAEvents: EventId[] = [];

    for (let i = 0; i < times.length; i++) {
      // Agent A produces an event
      const aEvent = createEventId(agentA);
      agentAEvents.push(aEvent.id);

      // Agent B produces an event with A's event as predecessor
      const bRecord = makePACRecord(agentB, [aEvent.id], {
        timeEstimate: times[i]!,
        energyEstimate: energies[i]!,
      });
      records.push(bRecord);
    }

    const graph = projectToAgentGraph(records);
    const edgeAB = graph.edges.get(agentA)?.get(agentB);
    expect(edgeAB).toBeDefined();
    expect(edgeAB!.callCount).toBe(5);

    // Naive mean
    const naiveTimeMean = times.reduce((a, b) => a + b, 0) / times.length;
    const naiveEnergyMean = energies.reduce((a, b) => a + b, 0) / energies.length;

    expect(edgeAB!.averageLatency.estimate).toBeCloseTo(naiveTimeMean, 10);
    expect(edgeAB!.averageEnergy.estimate).toBeCloseTo(naiveEnergyMean, 10);

    // CI should be reasonable (lower < estimate < upper)
    expect(edgeAB!.averageLatency.lower).toBeLessThanOrEqual(
      edgeAB!.averageLatency.estimate,
    );
    expect(edgeAB!.averageLatency.upper).toBeGreaterThanOrEqual(
      edgeAB!.averageLatency.estimate,
    );
  });
});
