// src/compliance/bridge-compliance.test.ts
// Compliance tests for the OpenAPI bridge adapter.
// Verifies that bridge output is a structurally valid PACRecord.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { EventId, CapabilityRef } from '../types/identity.js';
import { isEventId, extractOrigin } from '../types/identity.js';
import { isPACRLite } from '../types/pacr.js';
import type { AgentCard } from '../types/agent-card.js';
import { createAgentId, createEventId } from '../core/identity.js';
import { createCommensuationLayer } from '../core/commensuration.js';
import type { OpenAPIEventContext } from '../bridges/openapi-adapter.js';
import { openAPIToPACRLite } from '../bridges/openapi-adapter.js';
import type { PACRComplianceTarget } from './pacr-compliance.js';
import { runComplianceSuite } from './pacr-compliance.js';

// ─────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────

const ctxArbitrary: fc.Arbitrary<OpenAPIEventContext> = fc.record({
  requestId: fc.uuid(),
  referer: fc.option(fc.constant(undefined), { nil: undefined }),
  requestChain: fc.option(fc.constant(undefined), { nil: undefined }),
  responseTimeMs: fc.double({ min: 0.1, max: 30000, noNaN: true }),
  requestBodyBytes: fc.integer({ min: 0, max: 10_000_000 }),
  responseBodyBytes: fc.integer({ min: 0, max: 50_000_000 }),
});

// ─────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────

describe('OpenAPI Bridge Adapter Compliance', () => {
  // ─────────────────────────────────────────────
  // P1: Output is a structurally valid PACRecord (TC-002)
  // ─────────────────────────────────────────────
  it('P1: output has all six dimensions with valid CIs', () => {
    fc.assert(
      fc.property(ctxArbitrary, (ctx) => {
        const agent = createAgentId();
        const record = openAPIToPACRLite(agent, ctx);

        // Dimension 1: identity
        expect(record.identity).toBeDefined();
        expect(isEventId(record.identity.id)).toBe(true);
        expect(extractOrigin(record.identity.id)).toBe(agent);
        expect(record.identity.origin).toBe(agent);

        // Dimension 2: predecessors (Set, possibly empty)
        expect(record.predecessors).toBeDefined();
        expect(typeof record.predecessors[Symbol.iterator]).toBe('function');

        // Dimension 3: landauerCost (PACR-Lite)
        expect(record.landauerCost.estimate).toBe(0);
        expect(record.landauerCost.lower).toBe(0);
        expect(record.landauerCost.upper).toBe(Infinity);

        // Dimension 4: resources
        // Ω.T: estimate > 0 (from responseTimeMs)
        expect(record.resources.time.estimate).toBeGreaterThan(0);
        expect(record.resources.time.lower).toBeLessThanOrEqual(record.resources.time.estimate);

        // Ω.E: PACR-Lite
        expect(record.resources.energy.estimate).toBe(0);
        expect(record.resources.energy.upper).toBe(Infinity);

        // Ω.S: from body sizes
        expect(record.resources.space.estimate).toBe(ctx.requestBodyBytes + ctx.responseBodyBytes);

        // Dimension 5: cognitiveSplit (PACR-Lite)
        expect(record.cognitiveSplit.statisticalComplexity.upper).toBe(Infinity);
        expect(record.cognitiveSplit.entropyRate.upper).toBe(Infinity);

        // Dimension 6: payload (Uint8Array)
        expect(record.payload).toBeInstanceOf(Uint8Array);
      }),
      { numRuns: 500 },
    );
  });

  // ─────────────────────────────────────────────
  // P2: A3 compliance — time conversion uses CommensuationLayer
  // ─────────────────────────────────────────────
  it('P2: Ω.T uses CommensuationLayer, not bare division', () => {
    const layer = createCommensuationLayer();
    const agent = createAgentId();
    const ctx: OpenAPIEventContext = {
      requestId: 'test-123',
      responseTimeMs: 250,
      requestBodyBytes: 1024,
      responseBodyBytes: 2048,
    };

    const record = openAPIToPACRLite(agent, ctx, layer);

    // Verify the estimate matches what the layer produces
    const expectedTime = layer.latencyMsToTime(250);
    expect(record.resources.time.estimate).toBe(expectedTime.estimate);
  });

  // ─────────────────────────────────────────────
  // P3: Valid EventIds in requestChain are included as predecessors
  // ─────────────────────────────────────────────
  it('P3: valid EventIds from requestChain become predecessors', () => {
    const agent = createAgentId();
    const otherAgent = createAgentId();
    const predEvent = createEventId(otherAgent);

    const ctx: OpenAPIEventContext = {
      requestId: 'test-chain',
      requestChain: [predEvent.id as string],
      responseTimeMs: 100,
      requestBodyBytes: 0,
      responseBodyBytes: 0,
    };

    const record = openAPIToPACRLite(agent, ctx);
    expect(record.predecessors.size).toBe(1);
    expect(record.predecessors.has(predEvent.id)).toBe(true);
  });

  // ─────────────────────────────────────────────
  // P4: Invalid strings in requestChain are silently dropped
  // ─────────────────────────────────────────────
  it('P4: invalid requestChain entries are dropped', () => {
    const agent = createAgentId();
    const ctx: OpenAPIEventContext = {
      requestId: 'test-invalid',
      requestChain: ['not-a-valid-event-id', 'also-bad', ''],
      responseTimeMs: 50,
      requestBodyBytes: 0,
      responseBodyBytes: 0,
    };

    const record = openAPIToPACRLite(agent, ctx);
    expect(record.predecessors.size).toBe(0);
  });

  // ─────────────────────────────────────────────
  // P5: Referer as EventId becomes a predecessor
  // ─────────────────────────────────────────────
  it('P5: valid EventId in referer becomes a predecessor', () => {
    const agent = createAgentId();
    const otherAgent = createAgentId();
    const refEvent = createEventId(otherAgent);

    const ctx: OpenAPIEventContext = {
      requestId: 'test-referer',
      referer: refEvent.id as string,
      responseTimeMs: 100,
      requestBodyBytes: 0,
      responseBodyBytes: 0,
    };

    const record = openAPIToPACRLite(agent, ctx);
    expect(record.predecessors.size).toBe(1);
    expect(record.predecessors.has(refEvent.id)).toBe(true);
  });

  // ─────────────────────────────────────────────
  // P6: Bridge output passes full PACR compliance suite
  // ─────────────────────────────────────────────
  it('P6: bridge output passes TC-001 through TC-007', async () => {
    const agent = createAgentId();
    const store = new Map<string, import('../types/pacr.js').PACRecord>();
    let lastEventId: EventId | null = null;

    const target: PACRComplianceTarget = {
      async triggerEvent(input: Uint8Array) {
        const ctx: OpenAPIEventContext = {
          requestId: `req-${Date.now()}`,
          requestChain: lastEventId !== null ? [lastEventId as string] : undefined,
          responseTimeMs: 50 + Math.random() * 200,
          requestBodyBytes: input.length,
          responseBodyBytes: 128,
        };

        const record = openAPIToPACRLite(agent, ctx);
        store.set(record.identity.id as string, record);
        lastEventId = record.identity.id;
        return record;
      },

      async getAgentCard(): Promise<AgentCard> {
        return {
          agentId: agent,
          name: 'openapi-bridge-test',
          capabilities: [{ name: 'http.proxy' as CapabilityRef, description: 'HTTP proxy' }],
          endpoint: 'https://api.example.com',
          ttlSeconds: 300,
        };
      },

      async retrieveRecord(eventId: EventId) {
        return store.get(eventId as string) ?? null;
      },
    };

    const report = await runComplianceSuite(target);

    for (const r of report.results) {
      expect(
        r.verdict === 'PASS' || r.verdict === 'WARN' || r.verdict === 'SKIP',
        `${r.id} ${r.name}: ${r.verdict} — ${r.details}`,
      ).toBe(true);
    }

    expect(report.summary.fail).toBe(0);
  });
});
