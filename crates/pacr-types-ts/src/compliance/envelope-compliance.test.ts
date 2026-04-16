// src/compliance/envelope-compliance.test.ts
// Property-based compliance tests for Envelope construction, extraction, and serialization.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { AgentId, CapabilityRef, EventId } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type { EnvelopePrimaryHeader } from '../types/envelope.js';
import { createAgentId, createEventId } from '../core/identity.js';
import {
  createEnvelope,
  extractPACRecord,
  serializeEnvelope,
  deserializeEnvelope,
  readTargetAgentId,
  readSourceAgentId,
  readTTL,
} from '../core/envelope.js';

// ─────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────

function makeHeader(): EnvelopePrimaryHeader {
  return {
    targetAgentId: createAgentId(),
    targetCapability: 'text.summarize' as CapabilityRef,
    sourceAgentId: createAgentId(),
    ttl: 10,
    protocolVersion: '1.0.0',
  };
}

function makePACRecord(origin: AgentId, predecessorIds: EventId[]): PACRecord {
  const event = createEventId(origin);
  return {
    identity: event,
    predecessors: new Set(predecessorIds),
    landauerCost: { estimate: 1.5, lower: 0.5, upper: 3.0 },
    resources: {
      energy: { estimate: 0.005, lower: 0.001, upper: 0.01 },
      time: { estimate: 0.25, lower: 0.1, upper: 0.5 },
      space: { estimate: 2048, lower: 1024, upper: 4096 },
    },
    cognitiveSplit: {
      statisticalComplexity: { estimate: 3.2, lower: 1.0, upper: 5.5 },
      entropyRate: { estimate: 2.1, lower: 0.8, upper: 4.0 },
    },
    payload: new Uint8Array([0xDE, 0xAD, 0xBE, 0xEF, 0x42]),
  };
}

/** Generate a random PACRecord with variable-length predecessors and payload */
function recordArbitrary(): fc.Arbitrary<{ header: EnvelopePrimaryHeader; record: PACRecord }> {
  return fc.tuple(
    fc.integer({ min: 1, max: 255 }),
    fc.integer({ min: 0, max: 5 }),
    fc.uint8Array({ minLength: 0, maxLength: 200 }),
  ).map(([ttl, predCount, payloadArr]) => {
    const target = createAgentId();
    const source = createAgentId();
    const origin = createAgentId();

    // Generate predecessors from distinct agents
    const preds: EventId[] = [];
    for (let i = 0; i < predCount; i++) {
      const predAgent = createAgentId();
      preds.push(createEventId(predAgent).id);
    }

    const event = createEventId(origin);
    const record: PACRecord = {
      identity: event,
      predecessors: new Set(preds),
      landauerCost: { estimate: Math.random() * 10, lower: 0, upper: Math.random() * 20 + 10 },
      resources: {
        energy: { estimate: Math.random(), lower: 0, upper: Math.random() * 2 },
        time: { estimate: Math.random(), lower: 0, upper: Math.random() * 2 },
        space: { estimate: Math.floor(Math.random() * 10000), lower: 0, upper: 20000 },
      },
      cognitiveSplit: {
        statisticalComplexity: { estimate: Math.random() * 10, lower: 0, upper: 20 },
        entropyRate: { estimate: Math.random() * 10, lower: 0, upper: 20 },
      },
      payload: new Uint8Array(payloadArr),
    };

    const header: EnvelopePrimaryHeader = {
      targetAgentId: target,
      targetCapability: 'cap.test' as CapabilityRef,
      sourceAgentId: source,
      ttl,
      protocolVersion: '1.0.0',
    };

    return { header, record };
  });
}

/** Compare two PACRecords for structural equality */
function expectRecordsEqual(a: PACRecord, b: PACRecord): void {
  // Identity
  expect(a.identity.id).toBe(b.identity.id);
  expect(a.identity.origin).toBe(b.identity.origin);
  expect(a.identity.timestampMs).toBe(b.identity.timestampMs);

  // Predecessors
  const aPreds = [...a.predecessors].sort();
  const bPreds = [...b.predecessors].sort();
  expect(aPreds).toEqual(bPreds);

  // Landauer cost
  expect(a.landauerCost.estimate).toBe(b.landauerCost.estimate);
  expect(a.landauerCost.lower).toBe(b.landauerCost.lower);
  expect(a.landauerCost.upper).toBe(b.landauerCost.upper);

  // Resources
  for (const dim of ['energy', 'time', 'space'] as const) {
    expect(a.resources[dim].estimate).toBe(b.resources[dim].estimate);
    expect(a.resources[dim].lower).toBe(b.resources[dim].lower);
    expect(a.resources[dim].upper).toBe(b.resources[dim].upper);
  }

  // Cognitive split
  expect(a.cognitiveSplit.statisticalComplexity.estimate).toBe(b.cognitiveSplit.statisticalComplexity.estimate);
  expect(a.cognitiveSplit.entropyRate.estimate).toBe(b.cognitiveSplit.entropyRate.estimate);

  // Payload
  expect(new Uint8Array(a.payload)).toEqual(new Uint8Array(b.payload));
}

// ─────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────

describe('Envelope (P1-3) Compliance', () => {
  // ─────────────────────────────────────────────
  // P1: extractPACRecord(createEnvelope(header, record)) ≡ record
  // ─────────────────────────────────────────────
  it('P1: createEnvelope/extractPACRecord round-trip', () => {
    fc.assert(
      fc.property(recordArbitrary(), ({ header, record }) => {
        const envelope = createEnvelope(header, record);
        const recovered = extractPACRecord(envelope);
        expectRecordsEqual(recovered, record);
      }),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // P2: deserializeEnvelope(serializeEnvelope(env)) ≡ env
  // ─────────────────────────────────────────────
  it('P2: serialize/deserialize round-trip', () => {
    fc.assert(
      fc.property(recordArbitrary(), ({ header, record }) => {
        const envelope = createEnvelope(header, record);
        const bytes = serializeEnvelope(envelope);
        const recovered = deserializeEnvelope(bytes);

        // Primary header
        expect(recovered.primaryHeader.targetAgentId).toBe(header.targetAgentId);
        expect(recovered.primaryHeader.sourceAgentId).toBe(header.sourceAgentId);
        expect(recovered.primaryHeader.targetCapability).toBe(header.targetCapability);
        expect(recovered.primaryHeader.ttl).toBe(header.ttl);
        expect(recovered.primaryHeader.protocolVersion).toBe(header.protocolVersion);

        // Extensions: verify PACR record survives full round-trip
        const originalRecord = extractPACRecord(envelope);
        const recoveredRecord = extractPACRecord(recovered);
        expectRecordsEqual(recoveredRecord, originalRecord);

        // Body
        expect(new Uint8Array(recovered.body)).toEqual(new Uint8Array(envelope.body));
      }),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // P3: Zero-copy routing — read fixed-offset fields without full parse
  // ─────────────────────────────────────────────
  it('P3: zero-copy routing reads from fixed offsets', () => {
    fc.assert(
      fc.property(recordArbitrary(), ({ header, record }) => {
        const envelope = createEnvelope(header, record);
        const bytes = serializeEnvelope(envelope);

        // Read routing fields from raw bytes without deserializing
        expect(readTargetAgentId(bytes)).toBe(header.targetAgentId);
        expect(readSourceAgentId(bytes)).toBe(header.sourceAgentId);
        expect(readTTL(bytes)).toBe(header.ttl);
      }),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // P4: Empty payload and empty predecessors
  // ─────────────────────────────────────────────
  it('P4: empty payload and empty predecessors survive round-trip', () => {
    const origin = createAgentId();
    const record: PACRecord = {
      identity: createEventId(origin),
      predecessors: new Set(),
      landauerCost: { estimate: 0, lower: 0, upper: Infinity },
      resources: {
        energy: { estimate: 0, lower: 0, upper: Infinity },
        time: { estimate: 0, lower: 0, upper: Infinity },
        space: { estimate: 0, lower: 0, upper: Infinity },
      },
      cognitiveSplit: {
        statisticalComplexity: { estimate: 0, lower: 0, upper: Infinity },
        entropyRate: { estimate: 0, lower: 0, upper: Infinity },
      },
      payload: new Uint8Array(0),
    };

    const envelope = createEnvelope(makeHeader(), record);
    const bytes = serializeEnvelope(envelope);
    const recovered = deserializeEnvelope(bytes);
    const recoveredRecord = extractPACRecord(recovered);

    expectRecordsEqual(recoveredRecord, record);
  });

  // ─────────────────────────────────────────────
  // P5: Infinity values survive JSON serialization
  // ─────────────────────────────────────────────
  it('P5: Infinity values in CI survive serialize/deserialize', () => {
    const origin = createAgentId();
    const record: PACRecord = {
      identity: createEventId(origin),
      predecessors: new Set(),
      landauerCost: { estimate: 0, lower: 0, upper: Infinity },
      resources: {
        energy: { estimate: 1, lower: 0, upper: Infinity },
        time: { estimate: 1, lower: 0, upper: Infinity },
        space: { estimate: 1, lower: 0, upper: Infinity },
      },
      cognitiveSplit: {
        statisticalComplexity: { estimate: 0, lower: 0, upper: Infinity },
        entropyRate: { estimate: 0, lower: 0, upper: Infinity },
      },
      payload: new Uint8Array(0),
    };

    const envelope = createEnvelope(makeHeader(), record);
    const bytes = serializeEnvelope(envelope);
    const recovered = deserializeEnvelope(bytes);
    const recoveredRecord = extractPACRecord(recovered);

    // JSON.stringify turns Infinity → null, so we need to handle this
    expect(recoveredRecord.landauerCost.upper).toBe(record.landauerCost.upper);
  });
});
