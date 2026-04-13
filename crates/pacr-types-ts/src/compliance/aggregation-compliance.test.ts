// src/compliance/aggregation-compliance.test.ts
// Property-based compliance tests for the Σ aggregation operator.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { AgentId, CapabilityRef } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type { AgentCard } from '../types/agent-card.js';
import { createAgentId, createEventId } from '../core/identity.js';
import {
  aggregateBehaviorEntropy,
  aggregateBehaviorEntropyByCapability,
  updateAgentCardWithEntropy,
} from '../core/aggregation.js';

// ─────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────

const NOW_MS = Date.now();
const WINDOW_SECONDS = 3600; // 1 hour

function makePACRecord(
  origin: AgentId,
  opts: {
    stEstimate: number;
    htEstimate: number;
    timeEstimate: number;
    capabilityRef?: CapabilityRef;
    timestampMs?: number;
  },
): PACRecord {
  const event = createEventId(origin, opts.capabilityRef);
  // Override timestampMs if specified (for window tests)
  const identity = opts.timestampMs !== undefined
    ? { ...event, timestampMs: opts.timestampMs }
    : event;
  return {
    identity,
    predecessors: new Set(),
    landauerCost: { estimate: 0, lower: 0, upper: Infinity },
    resources: {
      energy: { estimate: 0.001, lower: 0, upper: 0.002 },
      time: { estimate: opts.timeEstimate, lower: 0, upper: opts.timeEstimate * 2 },
      space: { estimate: 1024, lower: 0, upper: 2048 },
    },
    cognitiveSplit: {
      statisticalComplexity: {
        estimate: opts.stEstimate,
        lower: opts.stEstimate * 0.5,
        upper: opts.stEstimate * 1.5,
      },
      entropyRate: {
        estimate: opts.htEstimate,
        lower: opts.htEstimate * 0.5,
        upper: opts.htEstimate * 1.5,
      },
    },
    payload: new Uint8Array(0),
  };
}

// ─────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────

describe('Aggregation Operator (Σ) Compliance', () => {
  // ─────────────────────────────────────────────
  // P1: Empty records → PACR-Lite maximum ignorance
  // ─────────────────────────────────────────────
  it('P1: empty records → maximum ignorance result', () => {
    const agent = createAgentId();
    const result = aggregateBehaviorEntropy([], agent, WINDOW_SECONDS, NOW_MS);

    expect(result.sampleCount).toBe(0);
    expect(result.aggregatedEntropyRate.estimate).toBe(0);
    expect(result.aggregatedEntropyRate.lower).toBe(0);
    expect(result.aggregatedEntropyRate.upper).toBe(Infinity);
    expect(result.aggregatedStatisticalComplexity.estimate).toBe(0);
    expect(result.aggregatedStatisticalComplexity.lower).toBe(0);
    expect(result.aggregatedStatisticalComplexity.upper).toBe(Infinity);
  });

  it('P1b: records from other agents → max ignorance for target', () => {
    const agentA = createAgentId();
    const agentB = createAgentId();
    const records = [
      makePACRecord(agentB, { stEstimate: 5, htEstimate: 3, timeEstimate: 0.1 }),
    ];
    const result = aggregateBehaviorEntropy(records, agentA, WINDOW_SECONDS, NOW_MS);
    expect(result.sampleCount).toBe(0);
    expect(result.aggregatedEntropyRate.upper).toBe(Infinity);
  });

  // ─────────────────────────────────────────────
  // P2: Single record → point estimate = Γ value, CI is maximum width
  // ─────────────────────────────────────────────
  it('P2: single record → estimate equals record Γ, CI is max width', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.01, max: 100, noNaN: true }),
        fc.double({ min: 0.01, max: 100, noNaN: true }),
        fc.double({ min: 0.01, max: 10, noNaN: true }),
        (st, ht, time) => {
          const agent = createAgentId();
          const records = [makePACRecord(agent, { stEstimate: st, htEstimate: ht, timeEstimate: time })];
          const result = aggregateBehaviorEntropy(records, agent, WINDOW_SECONDS, NOW_MS);

          expect(result.sampleCount).toBe(1);
          expect(result.aggregatedStatisticalComplexity.estimate).toBeCloseTo(st, 10);
          expect(result.aggregatedEntropyRate.estimate).toBeCloseTo(ht, 10);

          // With n=1, variance is undefined → stdErr is Infinity → CI is max width
          expect(result.aggregatedStatisticalComplexity.lower).toBe(0);
          expect(result.aggregatedStatisticalComplexity.upper).toBe(Infinity);
          expect(result.aggregatedEntropyRate.lower).toBe(0);
          expect(result.aggregatedEntropyRate.upper).toBe(Infinity);
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // P3: Window-outside records are excluded
  // ─────────────────────────────────────────────
  it('P3: records outside time window are excluded', () => {
    const agent = createAgentId();
    const insideTimestamp = NOW_MS - 100_000;    // 100 seconds ago (inside 1h window)
    const outsideTimestamp = NOW_MS - 7_200_000; // 2 hours ago (outside 1h window)

    const insideRecord = makePACRecord(agent, {
      stEstimate: 5,
      htEstimate: 3,
      timeEstimate: 0.1,
      timestampMs: insideTimestamp,
    });
    const outsideRecord = makePACRecord(agent, {
      stEstimate: 99,
      htEstimate: 99,
      timeEstimate: 0.1,
      timestampMs: outsideTimestamp,
    });

    const result = aggregateBehaviorEntropy(
      [insideRecord, outsideRecord],
      agent,
      WINDOW_SECONDS,
      NOW_MS,
    );

    expect(result.sampleCount).toBe(1);
    expect(result.aggregatedStatisticalComplexity.estimate).toBeCloseTo(5, 10);
    expect(result.aggregatedEntropyRate.estimate).toBeCloseTo(3, 10);
  });

  // ─────────────────────────────────────────────
  // P4: Weight correctness — identical H_T values with different Ω.T
  // yield aggregate = that H_T (weights don't affect constant values)
  // ─────────────────────────────────────────────
  it('P4: identical H_T with different weights → aggregate equals H_T', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.01, max: 100, noNaN: true }),
        fc.double({ min: 0.01, max: 100, noNaN: true }),
        (commonHT, commonST) => {
          const agent = createAgentId();
          // Create records with same Γ but very different execution times
          const records = [
            makePACRecord(agent, { stEstimate: commonST, htEstimate: commonHT, timeEstimate: 0.001 }),
            makePACRecord(agent, { stEstimate: commonST, htEstimate: commonHT, timeEstimate: 10.0 }),
            makePACRecord(agent, { stEstimate: commonST, htEstimate: commonHT, timeEstimate: 100.0 }),
          ];
          const result = aggregateBehaviorEntropy(records, agent, WINDOW_SECONDS, NOW_MS);

          expect(result.sampleCount).toBe(3);
          // Weighted mean of identical values = that value, regardless of weights
          expect(result.aggregatedEntropyRate.estimate).toBeCloseTo(commonHT, 8);
          expect(result.aggregatedStatisticalComplexity.estimate).toBeCloseTo(commonST, 8);
        },
      ),
      { numRuns: 500 },
    );
  });

  // ─────────────────────────────────────────────
  // P5: By-capability filtering
  // ─────────────────────────────────────────────
  it('P5: aggregateByCapability only includes matching records', () => {
    const agent = createAgentId();
    const capA = 'translate' as CapabilityRef;
    const capB = 'codegen' as CapabilityRef;

    const recordsA = [
      makePACRecord(agent, { stEstimate: 2, htEstimate: 1, timeEstimate: 0.5, capabilityRef: capA }),
      makePACRecord(agent, { stEstimate: 4, htEstimate: 3, timeEstimate: 0.5, capabilityRef: capA }),
    ];
    const recordsB = [
      makePACRecord(agent, { stEstimate: 20, htEstimate: 15, timeEstimate: 0.5, capabilityRef: capB }),
    ];
    const allRecords = [...recordsA, ...recordsB];

    const resultA = aggregateBehaviorEntropyByCapability(allRecords, agent, capA, WINDOW_SECONDS, NOW_MS);
    const resultB = aggregateBehaviorEntropyByCapability(allRecords, agent, capB, WINDOW_SECONDS, NOW_MS);

    expect(resultA.sampleCount).toBe(2);
    expect(resultB.sampleCount).toBe(1);

    // capA: equal weights → simple mean of (2,4)=3 for ST, (1,3)=2 for HT
    expect(resultA.aggregatedStatisticalComplexity.estimate).toBeCloseTo(3, 8);
    expect(resultA.aggregatedEntropyRate.estimate).toBeCloseTo(2, 8);

    // capB: single record
    expect(resultB.aggregatedStatisticalComplexity.estimate).toBeCloseTo(20, 10);
    expect(resultB.aggregatedEntropyRate.estimate).toBeCloseTo(15, 10);
  });

  // ─────────────────────────────────────────────
  // P6: updateAgentCardWithEntropy immutable update
  // ─────────────────────────────────────────────
  it('P6: updateAgentCardWithEntropy returns new card with entropy in metadata', () => {
    const agent = createAgentId();
    const card: AgentCard = {
      agentId: agent,
      name: 'test-agent',
      capabilities: [],
      endpoint: 'https://example.com',
      ttlSeconds: 3600,
    };

    const entropy = aggregateBehaviorEntropy(
      [makePACRecord(agent, { stEstimate: 5, htEstimate: 3, timeEstimate: 1 })],
      agent,
      WINDOW_SECONDS,
      NOW_MS,
    );

    const updated = updateAgentCardWithEntropy(card, entropy);

    // Original card is unchanged
    expect(card.metadata).toBeUndefined();

    // Updated card has entropy in metadata
    expect(updated.metadata).toBeDefined();
    expect(updated.metadata!['aevum:behavior_entropy']).toBe(entropy);

    // Other fields preserved
    expect(updated.agentId).toBe(card.agentId);
    expect(updated.name).toBe(card.name);
    expect(updated.endpoint).toBe(card.endpoint);
  });

  it('P6b: updateAgentCardWithEntropy preserves existing metadata', () => {
    const agent = createAgentId();
    const card: AgentCard = {
      agentId: agent,
      name: 'test-agent',
      capabilities: [],
      endpoint: 'https://example.com',
      ttlSeconds: 3600,
      metadata: { 'custom:key': 'value' },
    };

    const entropy = aggregateBehaviorEntropy([], agent, WINDOW_SECONDS, NOW_MS);
    const updated = updateAgentCardWithEntropy(card, entropy);

    expect(updated.metadata!['custom:key']).toBe('value');
    expect(updated.metadata!['aevum:behavior_entropy']).toBe(entropy);
  });

  // ─────────────────────────────────────────────
  // P7: Zero-weight records are excluded
  // ─────────────────────────────────────────────
  it('P7: records with zero execution time are excluded', () => {
    const agent = createAgentId();
    const records = [
      makePACRecord(agent, { stEstimate: 99, htEstimate: 99, timeEstimate: 0 }),
      makePACRecord(agent, { stEstimate: 5, htEstimate: 3, timeEstimate: 1 }),
    ];
    const result = aggregateBehaviorEntropy(records, agent, WINDOW_SECONDS, NOW_MS);

    expect(result.sampleCount).toBe(1);
    expect(result.aggregatedStatisticalComplexity.estimate).toBeCloseTo(5, 10);
    expect(result.aggregatedEntropyRate.estimate).toBeCloseTo(3, 10);
  });
});
