// src/compliance/pacr-compliance.test.ts
// Self-test: run the PACR compliance suite against a mock implementation
// to verify the framework itself works correctly.

import { describe, it, expect } from 'vitest';
import type { EventId } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type { AgentCard } from '../types/agent-card.js';
import type { CapabilityRef } from '../types/identity.js';
import { createAgentId, createEventId } from '../core/identity.js';
import type { PACRComplianceTarget } from './pacr-compliance.js';
import { runComplianceSuite } from './pacr-compliance.js';

// ─────────────────────────────────────────────
// Mock adapter: fully compliant PACR implementation
// ─────────────────────────────────────────────

function createCompliantMock(): PACRComplianceTarget {
  const agentId = createAgentId();
  const store = new Map<string, PACRecord>();
  let lastEventId: EventId | null = null;

  return {
    async triggerEvent(input: Uint8Array): Promise<PACRecord> {
      const event = createEventId(agentId);

      // Build predecessors: chain to previous event if exists
      const predecessors = new Set<EventId>();
      if (lastEventId !== null) {
        predecessors.add(lastEventId);
      }

      const record: PACRecord = {
        identity: event,
        predecessors,
        landauerCost: { estimate: 1e-18, lower: 5e-19, upper: 2e-18 },
        resources: {
          energy: { estimate: 0.005, lower: 0.001, upper: 0.01 },
          time: { estimate: 0.25, lower: 0.1, upper: 0.5 },
          space: { estimate: input.length, lower: 0, upper: input.length * 2 },
        },
        cognitiveSplit: {
          statisticalComplexity: { estimate: 3.2, lower: 1.0, upper: 5.5 },
          entropyRate: { estimate: 2.1, lower: 0.8, upper: 4.0 },
        },
        payload: new Uint8Array(input),
      };

      store.set(event.id as string, record);
      lastEventId = event.id;
      return record;
    },

    async getAgentCard(): Promise<AgentCard> {
      return {
        agentId,
        name: 'compliant-mock',
        capabilities: [{ name: 'test.echo' as CapabilityRef, description: 'Echo test' }],
        endpoint: 'mock://localhost',
        ttlSeconds: 3600,
      };
    },

    async retrieveRecord(eventId: EventId): Promise<PACRecord | null> {
      return store.get(eventId as string) ?? null;
    },
  };
}

// ─────────────────────────────────────────────
// Mock adapter: PACR-Lite compliant
// ─────────────────────────────────────────────

function createPACRLiteMock(): PACRComplianceTarget {
  const agentId = createAgentId();
  const store = new Map<string, PACRecord>();
  let lastEventId: EventId | null = null;

  return {
    async triggerEvent(input: Uint8Array): Promise<PACRecord> {
      const event = createEventId(agentId);
      const predecessors = new Set<EventId>();
      if (lastEventId !== null) {
        predecessors.add(lastEventId);
      }

      const record: PACRecord = {
        identity: event,
        predecessors,
        landauerCost: { estimate: 0, lower: 0, upper: Infinity },
        resources: {
          energy: { estimate: 0.003, lower: 0.001, upper: 0.005 },
          time: { estimate: 0.1, lower: 0.05, upper: 0.2 },
          space: { estimate: 512, lower: 256, upper: 1024 },
        },
        cognitiveSplit: {
          statisticalComplexity: { estimate: 0, lower: 0, upper: Infinity },
          entropyRate: { estimate: 0, lower: 0, upper: Infinity },
        },
        payload: new Uint8Array(input),
      };

      store.set(event.id as string, record);
      lastEventId = event.id;
      return record;
    },

    async getAgentCard(): Promise<AgentCard> {
      return {
        agentId,
        name: 'pacr-lite-mock',
        capabilities: [{ name: 'test.lite' as CapabilityRef, description: 'Lite test' }],
        endpoint: 'mock://localhost',
        ttlSeconds: 3600,
      };
    },

    async retrieveRecord(eventId: EventId): Promise<PACRecord | null> {
      return store.get(eventId as string) ?? null;
    },
  };
}

// ─────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────

describe('PACR Compliance Suite (P2-3)', () => {
  it('fully compliant mock passes all test cases', async () => {
    const mock = createCompliantMock();
    const report = await runComplianceSuite(mock);

    // Print report for visibility
    for (const r of report.results) {
      expect(
        r.verdict === 'PASS' || r.verdict === 'WARN',
        `${r.id} ${r.name}: ${r.verdict} — ${r.details}`,
      ).toBe(true);
    }

    expect(report.summary.fail).toBe(0);
    expect(report.summary.skip).toBe(0);
  });

  it('PACR-Lite mock passes all test cases', async () => {
    const mock = createPACRLiteMock();
    const report = await runComplianceSuite(mock);

    for (const r of report.results) {
      expect(
        r.verdict === 'PASS' || r.verdict === 'WARN' || r.verdict === 'SKIP',
        `${r.id} ${r.name}: ${r.verdict} — ${r.details}`,
      ).toBe(true);
    }

    expect(report.summary.fail).toBe(0);
  });

  it('report is JSON-serializable', async () => {
    const mock = createCompliantMock();
    const report = await runComplianceSuite(mock);
    const json = JSON.stringify(report);
    const parsed = JSON.parse(json);
    expect(parsed.summary.total).toBe(7);
    expect(parsed.results.length).toBe(7);
  });

  it('report contains correct TC IDs', async () => {
    const mock = createCompliantMock();
    const report = await runComplianceSuite(mock);
    const ids = report.results.map((r) => r.id);
    expect(ids).toEqual(['TC-001', 'TC-002', 'TC-003', 'TC-004', 'TC-005', 'TC-006', 'TC-007']);
  });
});
