// src/core/entropy-index.test.ts
// Tests for the Behavior Entropy Index.
//
// Coverage:
// 1. percentileRank correctness with a known distribution
// 2. Trend detection (improving / stable / degrading)
// 3. Confidence levels based on sampleCount
// 4. AgentCard enrichment
// 5. Anomaly detection: low_entropy, complexity_mismatch, cross_caller_inconsistency
// 6. Performance: 1M records ingested in < 10s

import { describe, it, expect } from 'vitest';
import type { AgentId, EventId, CapabilityRef, EventIdStructure } from '../types/identity.js';
import type { PACRecord, ConfidenceInterval } from '../types/pacr.js';
import type { AgentCard } from '../types/agent-card.js';
import { createAgentId, createEventId } from '../core/identity.js';
import { projectToAgentGraph } from '../core/projection.js';
import {
  createTrackedEntropyIndex,
  enrichAgentCardWithEntropy,
  detectAnomalies,
} from './entropy-index.js';

// ─────────────────────────────────────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────────────────────────────────────

const CAP_TRANSLATE = 'translate.text' as CapabilityRef;
const CAP_CODE = 'code.generate' as CapabilityRef;

/** Build a minimal PACRecord with controlled Γ values */
function makeRecord(opts: {
  identity: EventIdStructure;
  ht: number;
  st: number;
  weight?: number;
  predecessors?: Set<EventId>;
}): PACRecord {
  const w = opts.weight ?? 0.1;
  return {
    identity: opts.identity,
    predecessors: opts.predecessors ?? new Set<EventId>(),
    landauerCost: { estimate: 0, lower: 0, upper: Infinity },
    resources: {
      energy: { estimate: 0, lower: 0, upper: Infinity },
      time: { estimate: w, lower: 0, upper: w * 2 } as ConfidenceInterval<'seconds'>,
      space: { estimate: 0, lower: 0, upper: 0 } as ConfidenceInterval<'bytes'>,
    },
    cognitiveSplit: {
      statisticalComplexity: { estimate: opts.st, lower: Math.max(0, opts.st - 0.1), upper: opts.st + 0.1 } as ConfidenceInterval<'bits_per_symbol'>,
      entropyRate: { estimate: opts.ht, lower: Math.max(0, opts.ht - 0.1), upper: opts.ht + 0.1 } as ConfidenceInterval<'bits_per_symbol'>,
    },
    payload: new Uint8Array(0),
  };
}

/** Inject N records for an agent at a fixed timestamp with fixed Γ values */
function injectRecords(
  agentId: AgentId,
  ht: number,
  st: number,
  count: number,
  timestampMs: number,
  capability?: CapabilityRef,
  predecessors?: Set<EventId>,
): PACRecord[] {
  const records: PACRecord[] = [];
  for (let i = 0; i < count; i++) {
    const identity = createEventId(agentId, capability);
    // Override timestamp for deterministic tests
    const overriddenIdentity: EventIdStructure = {
      id: identity.id,
      origin: identity.origin,
      timestampMs,
      ...(capability !== undefined ? { capabilityRef: capability } : {}),
    };
    records.push(makeRecord({ identity: overriddenIdentity, ht, st, predecessors }));
  }
  return records;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. percentileRank
// ─────────────────────────────────────────────────────────────────────────────

describe('percentileRank', () => {
  it('single agent in bucket has rank 0', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    idx.ingest(injectRecords(agent, 2.0, 1.0, 10, Date.now()));
    const entry = idx.query(agent);
    expect(entry).not.toBeNull();
    expect(entry!.percentileRank).toBe(0);
  });

  it('five agents ranked by H̄_T ascending', () => {
    const agents = [
      createAgentId(),
      createAgentId(),
      createAgentId(),
      createAgentId(),
      createAgentId(),
    ];
    // H̄_T values: 1, 2, 3, 4, 5
    const htValues = [1, 2, 3, 4, 5];

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    const now = Date.now();

    for (let i = 0; i < agents.length; i++) {
      const agent = agents[i]!;
      const ht = htValues[i]!;
      idx.ingest(injectRecords(agent, ht, ht * 0.5, 20, now, CAP_TRANSLATE));
    }

    const ranks = agents.map((a) => idx.query(a, CAP_TRANSLATE)!.percentileRank);

    // Best agent (ht=1): 0 agents below → rank 0
    // Worst agent (ht=5): all others below → rank 100
    expect(ranks[0]).toBe(0);   // ht=1, no one below
    expect(ranks[4]).toBe(100); // ht=5, all below

    // Middle agents should be monotonically increasing
    expect(ranks[0]! < ranks[1]!).toBe(true);
    expect(ranks[1]! < ranks[2]!).toBe(true);
    expect(ranks[2]! < ranks[3]!).toBe(true);
    expect(ranks[3]! < ranks[4]!).toBe(true);
  });

  it('insufficient-confidence agents get rank -1 and are excluded from others ranking', () => {
    const highConf = createAgentId();
    const lowConf = createAgentId();
    const now = Date.now();

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    // highConf: 20 samples — 'low' confidence (≥10)
    idx.ingest(injectRecords(highConf, 3.0, 1.5, 20, now, CAP_TRANSLATE));
    // lowConf: 3 samples — 'insufficient'
    idx.ingest(injectRecords(lowConf, 10.0, 5.0, 3, now, CAP_TRANSLATE));

    const lowConfEntry = idx.query(lowConf, CAP_TRANSLATE);
    expect(lowConfEntry!.confidence).toBe('insufficient');
    expect(lowConfEntry!.percentileRank).toBe(-1);

    // highConf rank should not be affected by the insufficient-confidence agent
    const highConfEntry = idx.query(highConf, CAP_TRANSLATE);
    expect(highConfEntry!.percentileRank).toBe(0);
  });

  it('global rank is independent of per-capability rank', () => {
    const agent = createAgentId();
    const now = Date.now();

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    // inject with capability
    idx.ingest(injectRecords(agent, 2.0, 1.0, 20, now, CAP_TRANSLATE));

    const global = idx.query(agent);          // capability = undefined → global (null)
    const capEntry = idx.query(agent, CAP_TRANSLATE);

    expect(global).not.toBeNull();
    expect(capEntry).not.toBeNull();
    // Both report the same agent, but are separate buckets
    expect(global!.capability).toBeNull();
    expect(capEntry!.capability).toBe(CAP_TRANSLATE);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Trend detection
// ─────────────────────────────────────────────────────────────────────────────

describe('trend detection', () => {
  it('decreasing H̄_T over windows → improving', () => {
    const agent = createAgentId();
    const baseMs = 1_700_000_000_000;
    const windowMs = 3600 * 1000;

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600, trendEpsilon: 0.01 });

    // Inject 5 windows with decreasing entropy: 5.0 → 4.0 → 3.0 → 2.0 → 1.0
    for (let w = 0; w < 5; w++) {
      const ts = baseMs + w * windowMs + 1;
      const ht = 5.0 - w;
      idx.ingest(injectRecords(agent, ht, ht * 0.5, 10, ts));
    }

    const entry = idx.query(agent);
    expect(entry!.trend).toBe('improving');
  });

  it('increasing H̄_T over windows → degrading', () => {
    const agent = createAgentId();
    const baseMs = 1_700_000_000_000;
    const windowMs = 3600 * 1000;

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600, trendEpsilon: 0.01 });

    for (let w = 0; w < 5; w++) {
      const ts = baseMs + w * windowMs + 1;
      const ht = 1.0 + w;
      idx.ingest(injectRecords(agent, ht, ht * 0.5, 10, ts));
    }

    const entry = idx.query(agent);
    expect(entry!.trend).toBe('degrading');
  });

  it('flat H̄_T → stable', () => {
    const agent = createAgentId();
    const baseMs = 1_700_000_000_000;
    const windowMs = 3600 * 1000;

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600, trendEpsilon: 0.01 });

    for (let w = 0; w < 5; w++) {
      const ts = baseMs + w * windowMs + 1;
      idx.ingest(injectRecords(agent, 2.5, 1.2, 10, ts));
    }

    const entry = idx.query(agent);
    expect(entry!.trend).toBe('stable');
  });

  it('single window → stable (not enough data)', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    idx.ingest(injectRecords(agent, 2.0, 1.0, 15, Date.now()));
    const entry = idx.query(agent);
    expect(entry!.trend).toBe('stable');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Confidence levels
// ─────────────────────────────────────────────────────────────────────────────

describe('confidence levels', () => {
  it.each([
    [1000, 'high'],
    [999, 'medium'],
    [100, 'medium'],
    [99, 'low'],
    [10, 'low'],
    [9, 'insufficient'],
    [0, 'insufficient'],
  ] as const)('%i samples → %s', (count, expected) => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    if (count > 0) {
      idx.ingest(injectRecords(agent, 2.0, 1.0, count, Date.now()));
    }
    const entry = idx.query(agent);
    if (count === 0) {
      expect(entry).toBeNull();
    } else {
      expect(entry!.confidence).toBe(expected);
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. rank() — returns top-K by H̄_T ascending
// ─────────────────────────────────────────────────────────────────────────────

describe('rank()', () => {
  it('returns top-K agents sorted by H̄_T ascending', () => {
    const agents = Array.from({ length: 6 }, () => createAgentId());
    const htValues = [5, 1, 3, 2, 6, 4]; // unsorted
    const now = Date.now();

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    for (let i = 0; i < agents.length; i++) {
      idx.ingest(injectRecords(agents[i]!, htValues[i]!, 1.0, 15, now, CAP_TRANSLATE));
    }

    const top3 = idx.rank(CAP_TRANSLATE, 3);
    expect(top3).toHaveLength(3);

    const ranks = top3.map((e) => e.entropy.aggregatedEntropyRate.estimate);
    // Should be [1, 2, 3] roughly
    expect(ranks[0]!).toBeLessThanOrEqual(ranks[1]!);
    expect(ranks[1]!).toBeLessThanOrEqual(ranks[2]!);
    expect(ranks[0]!).toBeCloseTo(1, 0);
  });

  it('returns empty array for unknown capability', () => {
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    const result = idx.rank('unknown.cap' as CapabilityRef, 5);
    expect(result).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. AgentCard enrichment
// ─────────────────────────────────────────────────────────────────────────────

describe('enrichAgentCardWithEntropy', () => {
  it('writes global entropy, rank and trend to metadata', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    idx.ingest(injectRecords(agent, 2.5, 1.2, 20, Date.now()));

    const card: AgentCard = {
      agentId: agent,
      name: 'test-agent',
      capabilities: [],
      endpoint: 'https://test.example.com',
      ttlSeconds: 300,
    };

    const enriched = enrichAgentCardWithEntropy(card, idx);

    expect(enriched.metadata?.['aevum:behavior_entropy']).toBeDefined();
    expect(enriched.metadata?.['aevum:entropy_rank']).toBeDefined();
    expect(enriched.metadata?.['aevum:entropy_trend']).toBeDefined();
    // Original card unchanged
    expect(card.metadata).toBeUndefined();
  });

  it('writes per-capability entropy for each capability in AgentCard', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    const now = Date.now();
    idx.ingest(injectRecords(agent, 2.5, 1.2, 20, now, CAP_TRANSLATE));
    idx.ingest(injectRecords(agent, 3.0, 1.5, 20, now, CAP_CODE));

    const card: AgentCard = {
      agentId: agent,
      name: 'test-agent',
      capabilities: [
        { name: CAP_TRANSLATE, description: 'translate' },
        { name: CAP_CODE, description: 'code' },
      ],
      endpoint: 'https://test.example.com',
      ttlSeconds: 300,
    };

    const enriched = enrichAgentCardWithEntropy(card, idx);

    expect(enriched.metadata?.['aevum:behavior_entropy:translate.text']).toBeDefined();
    expect(enriched.metadata?.['aevum:behavior_entropy:code.generate']).toBeDefined();
  });

  it('returns original card unchanged if no data in index', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });

    const card: AgentCard = {
      agentId: agent,
      name: 'ghost',
      capabilities: [],
      endpoint: 'https://ghost.example.com',
      ttlSeconds: 300,
    };

    const enriched = enrichAgentCardWithEntropy(card, idx);
    expect(enriched.metadata?.['aevum:behavior_entropy']).toBeUndefined();
    expect(enriched.name).toBe('ghost');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Anomaly detection
// ─────────────────────────────────────────────────────────────────────────────

describe('detectAnomalies', () => {
  it('flags suspiciously_low_entropy when H̄_T < threshold with high confidence', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    const now = Date.now();
    // 1000 samples with ht=0.01 (below default threshold 0.05)
    idx.ingest(injectRecords(agent, 0.01, 0.5, 1000, now));

    const graph = projectToAgentGraph([]);
    const flags = detectAnomalies(idx, graph);

    const lowEntropyFlags = flags.filter((f) => f.agentId === agent && f.type === 'suspiciously_low_entropy');
    expect(lowEntropyFlags.length).toBeGreaterThan(0);
    expect(lowEntropyFlags[0]!.severity).toBe('critical'); // 1000 samples = 'high' confidence
  });

  it('does not flag when entropy is normal', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    idx.ingest(injectRecords(agent, 2.0, 1.0, 1000, Date.now()));

    const graph = projectToAgentGraph([]);
    const flags = detectAnomalies(idx, graph);

    const relevant = flags.filter((f) => f.agentId === agent);
    expect(relevant).toHaveLength(0);
  });

  it('flags complexity_mismatch when S_T is implausibly low vs H_T', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    // H_T = 2.0 bits, S_T = 0.01 bits — ratio < 10%, mismatch
    idx.ingest(injectRecords(agent, 2.0, 0.01, 100, Date.now()));

    const graph = projectToAgentGraph([]);
    const flags = detectAnomalies(idx, graph);

    const mismatch = flags.filter((f) => f.agentId === agent && f.type === 'complexity_mismatch');
    expect(mismatch.length).toBeGreaterThan(0);
  });

  it('flags cross_caller_inconsistency when callers observe divergent entropy', () => {
    const targetAgent = createAgentId();
    const callerA = createAgentId();
    const callerB = createAgentId();

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    const now = Date.now();

    // callerA records: it called targetAgent, targetAgent had ht=0.5
    const callerAEventIds: EventId[] = [];
    for (let i = 0; i < 10; i++) {
      const ev = createEventId(callerA);
      callerAEventIds.push(ev.id);
    }

    // Build records for targetAgent called by callerA (low entropy observations)
    const callerAObs: PACRecord[] = [];
    for (let i = 0; i < 10; i++) {
      const predecessors = new Set<EventId>([callerAEventIds[i]!]);
      const identity: EventIdStructure = {
        ...createEventId(targetAgent),
        timestampMs: now,
      };
      callerAObs.push(makeRecord({ identity, ht: 0.5, st: 0.3, predecessors }));
    }

    // Build records for targetAgent called by callerB (very high entropy observations)
    const callerBEvents: EventId[] = [];
    for (let i = 0; i < 10; i++) {
      callerBEvents.push(createEventId(callerB).id);
    }
    const callerBObs: PACRecord[] = [];
    for (let i = 0; i < 10; i++) {
      const predecessors = new Set<EventId>([callerBEvents[i]!]);
      const identity: EventIdStructure = {
        ...createEventId(targetAgent),
        timestampMs: now,
      };
      callerBObs.push(makeRecord({ identity, ht: 4.5, st: 2.0, predecessors }));
    }

    idx.ingest(callerAObs);
    idx.ingest(callerBObs);

    const graph = projectToAgentGraph([...callerAObs, ...callerBObs]);
    const flags = detectAnomalies(idx, graph);

    const crossCallerFlags = flags.filter(
      (f) => f.agentId === targetAgent && f.type === 'cross_caller_inconsistency',
    );
    expect(crossCallerFlags.length).toBeGreaterThan(0);
  });

  it('does not flag insufficient-confidence agents', () => {
    const agent = createAgentId();
    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    // Only 5 samples — insufficient confidence — should not flag anything
    idx.ingest(injectRecords(agent, 0.001, 0.001, 5, Date.now()));

    const graph = projectToAgentGraph([]);
    const flags = detectAnomalies(idx, graph);

    const relevant = flags.filter((f) => f.agentId === agent);
    expect(relevant).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. snapshot()
// ─────────────────────────────────────────────────────────────────────────────

describe('snapshot()', () => {
  it('includes global and per-capability entries for each agent', () => {
    const agent = createAgentId();
    const now = Date.now();

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });
    idx.ingest(injectRecords(agent, 2.0, 1.0, 15, now, CAP_TRANSLATE));

    const snap = idx.snapshot();
    const entries = snap.get(agent);
    expect(entries).toBeDefined();
    // Should have: global entry (capability=null) + cap entry
    expect(entries!.length).toBe(2);

    const global = entries!.find((e) => e.capability === null);
    const cap = entries!.find((e) => e.capability === CAP_TRANSLATE);
    expect(global).toBeDefined();
    expect(cap).toBeDefined();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. Performance: 1M records in < 10 seconds
// ─────────────────────────────────────────────────────────────────────────────

describe('performance', () => {
  it('ingests 1,000,000 records in < 10 seconds', { timeout: 30_000 }, () => {
    const NUM_RECORDS = 1_000_000;
    const NUM_AGENTS = 100;
    const NUM_CAPS = 5;

    // Pre-generate agents and EventId strings to isolate ingest perf
    const agents = Array.from({ length: NUM_AGENTS }, () => createAgentId());
    const caps = Array.from(
      { length: NUM_CAPS },
      (_, i) => `cap.${i}` as CapabilityRef,
    );

    // Pre-build all records before timing
    const records: PACRecord[] = new Array(NUM_RECORDS);
    const baseMs = 1_700_000_000_000;
    const windowMs = 3600 * 1000;

    for (let i = 0; i < NUM_RECORDS; i++) {
      const agentIdx = i % NUM_AGENTS;
      const capIdx = i % NUM_CAPS;
      const agent = agents[agentIdx]!;
      const cap = caps[capIdx]!;
      // Spread across 20 windows
      const epochOffset = Math.floor(i / (NUM_RECORDS / 20));
      const ts = baseMs + epochOffset * windowMs + (i % 1000);

      const identity: EventIdStructure = {
        id: createEventId(agent).id,
        origin: agent,
        timestampMs: ts,
        capabilityRef: cap,
      };

      records[i] = {
        identity,
        predecessors: new Set<EventId>(),
        landauerCost: { estimate: 0, lower: 0, upper: Infinity },
        resources: {
          energy: { estimate: 0, lower: 0, upper: Infinity },
          time: { estimate: 0.05, lower: 0, upper: 0.1 },
          space: { estimate: 0, lower: 0, upper: 0 },
        },
        cognitiveSplit: {
          statisticalComplexity: { estimate: 1.5, lower: 1.0, upper: 2.0 },
          entropyRate: { estimate: 2.0 + (i % 10) * 0.1, lower: 1.5, upper: 2.5 },
        },
        payload: new Uint8Array(0),
      };
    }

    const idx = createTrackedEntropyIndex({ windowSeconds: 3600 });

    const t0 = performance.now();
    idx.ingest(records);
    const elapsed = performance.now() - t0;

    // Must complete within 10 seconds
    expect(elapsed).toBeLessThan(10_000);

    // Sanity check: we can query results
    const entry = idx.query(agents[0]!);
    expect(entry).not.toBeNull();
    expect(entry!.entropy.sampleCount).toBeGreaterThan(0);

    // Log for visibility
    console.log(
      `[perf] Ingested ${NUM_RECORDS.toLocaleString()} records in ${elapsed.toFixed(0)}ms` +
      ` (${((NUM_RECORDS / elapsed) * 1000).toFixed(0)} rec/s)`,
    );
  });
});
