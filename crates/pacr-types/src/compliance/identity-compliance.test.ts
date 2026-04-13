// src/compliance/identity-compliance.test.ts
// Property-based compliance tests for the shared identity space.
// These are BLACK-BOX tests: they only use the public API surface.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { extractOrigin, isEventId } from '../types/identity.js';
import {
  createAgentId,
  createEventId,
  validateAgentId,
  validateEventId,
  parseEventId,
} from '../core/identity.js';

describe('Identity Space Compliance', () => {
  // ─────────────────────────────────────────────
  // P1: Round-trip extraction
  // ∀ agentId: extractOrigin(createEventId(agentId).id) === agentId
  // ─────────────────────────────────────────────
  it('P1: extractOrigin(createEventId(agentId).id) === agentId', () => {
    fc.assert(
      fc.property(
        fc.constant(null).map(() => createAgentId()),
        (agentId) => {
          const event = createEventId(agentId);
          const recovered = extractOrigin(event.id);
          expect(recovered).toBe(agentId);
        },
      ),
      { numRuns: 1000 },
    );
  });

  // ─────────────────────────────────────────────
  // P2: Validation consistency
  // ∀ eventId: isEventId(eventId) → validateAgentId(extractOrigin(eventId))
  // ─────────────────────────────────────────────
  it('P2: extracted origin from any EventId is a valid AgentId', () => {
    fc.assert(
      fc.property(
        fc.constant(null).map(() => {
          const agent = createAgentId();
          return createEventId(agent);
        }),
        (event) => {
          // isEventId must be true for factory-created EventIds
          expect(isEventId(event.id)).toBe(true);
          // The extracted origin must validate as a proper AgentId
          const origin = extractOrigin(event.id);
          expect(validateAgentId(origin as string)).toBe(true);
        },
      ),
      { numRuns: 1000 },
    );
  });

  // ─────────────────────────────────────────────
  // P3: Rejection of invalid prefixes
  // ∀ raw string not "a-" prefixed: validateAgentId(raw) === false
  // ─────────────────────────────────────────────
  it('P3: strings without "a-" prefix never validate as AgentId', () => {
    fc.assert(
      fc.property(
        fc.string().filter((s) => !s.startsWith('a-')),
        (raw) => {
          expect(validateAgentId(raw)).toBe(false);
        },
      ),
      { numRuns: 1000 },
    );
  });

  it('P3b: I_agent ∩ I_event = ∅ — EventId strings never validate as AgentId', () => {
    fc.assert(
      fc.property(
        fc.constant(null).map(() => {
          const agent = createAgentId();
          return createEventId(agent).id;
        }),
        (eventId) => {
          expect(validateAgentId(eventId as string)).toBe(false);
          expect(validateEventId(eventId as string)).toBe(true);
        },
      ),
      { numRuns: 1000 },
    );
  });

  // ─────────────────────────────────────────────
  // P4: Collision resistance
  // 1_000_000 createAgentId() calls → 0 collisions
  // ─────────────────────────────────────────────
  it('P4: 1M createAgentId() produces zero collisions', { timeout: 30_000 }, () => {
    const COUNT = 1_000_000;
    const seen = new Set<string>();
    for (let i = 0; i < COUNT; i++) {
      seen.add(createAgentId() as string);
    }
    expect(seen.size).toBe(COUNT);
  });

  // ─────────────────────────────────────────────
  // Supplementary: parseEventId structural correctness
  // ─────────────────────────────────────────────
  it('parseEventId recovers origin and produces valid timestamp', () => {
    fc.assert(
      fc.property(
        fc.constant(null).map(() => {
          const agent = createAgentId();
          return { agent, event: createEventId(agent) };
        }),
        ({ agent, event }) => {
          const parsed = parseEventId(event.id);
          expect(parsed.origin).toBe(agent);
          expect(parsed.id).toBe(event.id);
          expect(parsed.timestampMs).toBe(event.timestampMs);
          // timestamp should be a reasonable epoch ms (after 2020, before 2100)
          expect(parsed.timestampMs).toBeGreaterThan(1_577_836_800_000);
          expect(parsed.timestampMs).toBeLessThan(4_102_444_800_000);
        },
      ),
      { numRuns: 500 },
    );
  });
});
