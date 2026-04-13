// src/compliance/commensuration-compliance.test.ts
// Property-based compliance tests for the commensuration layer (Axiom A3).
// Black-box tests: only use the public API surface.

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { ConfidenceInterval } from '../types/pacr.js';
import type { CommensuationContext } from '../types/commensuration.js';
import { createCommensuationLayer } from '../core/commensuration.js';

const layer = createCommensuationLayer();

// ─────────────────────────────────────────────
// Test helpers: CI generators
// ─────────────────────────────────────────────

/** Generate a valid ConfidenceInterval with lower <= estimate <= upper */
function ciArbitrary<U extends string>(
  unit?: U,
): fc.Arbitrary<ConfidenceInterval<U>> {
  return fc
    .tuple(
      fc.double({ min: 0.001, max: 1e12, noNaN: true }),
      fc.double({ min: 0, max: 1, noNaN: true }),
    )
    .map(([estimate, spreadFrac]) => {
      const spread = estimate * spreadFrac;
      return {
        estimate,
        lower: estimate - spread,
        upper: estimate + spread,
      } as ConfidenceInterval<U>;
    });
}

/** Generate a valid CommensuationContext */
const ctxArbitrary: fc.Arbitrary<CommensuationContext> = fc.record({
  timestampMs: fc.double({ min: 1e12, max: 2e12, noNaN: true }),
  geoRegion: fc.constantFrom('US', 'JP', 'DE', 'SG'),
  infrastructureProvider: fc.constantFrom('aws', 'gcp', 'azure'),
  energyPriceJoulesPerUSD: fc.double({ min: 1e3, max: 1e9, noNaN: true }),
});

// ─────────────────────────────────────────────
// Property 1: Round-trip consistency
// latencyMsToTime(timeToLatencyMs(t)).estimate ≈ t.estimate
// ─────────────────────────────────────────────

describe('Commensuration Layer Compliance', () => {
  it('P1a: time round-trip preserves estimate', () => {
    fc.assert(
      fc.property(ciArbitrary<'seconds'>(), (seconds) => {
        const ms = layer.timeToLatencyMs(seconds);
        const recovered = layer.latencyMsToTime(ms);
        // IEEE 754 round-trip through * 1000 / 1000 has relative error ~ 2^-52
        const relErr = Math.abs(recovered.estimate - seconds.estimate) / (seconds.estimate || 1);
        expect(relErr).toBeLessThan(1e-10);
      }),
      { numRuns: 1000 },
    );
  });

  it('P1b: energy round-trip preserves estimate (USD)', () => {
    fc.assert(
      fc.property(ciArbitrary<'joules'>(), ctxArbitrary, (joules, ctx) => {
        const cost = layer.energyToCost(joules, ctx);
        const recovered = layer.costToEnergy(cost, 'USD', ctx);
        // Two divisions introduce cumulative floating-point error
        const relErr = Math.abs(recovered.estimate - joules.estimate) / (joules.estimate || 1);
        expect(relErr).toBeLessThan(1e-10);
      }),
      { numRuns: 1000 },
    );
  });

  it('P1c: space round-trip is identity on estimate', () => {
    fc.assert(
      fc.property(ciArbitrary<'bytes'>(), (bytes) => {
        const scalar = layer.spaceToBytes(bytes);
        expect(scalar).toBe(bytes.estimate);
      }),
      { numRuns: 500 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 2: Monotonicity
  // if energy1.estimate > energy2.estimate,
  // then energyToCost(energy1, ctx) >= energyToCost(energy2, ctx)
  // ─────────────────────────────────────────────

  it('P2a: energyToCost is monotonic in estimate', () => {
    fc.assert(
      fc.property(
        ciArbitrary<'joules'>(),
        ciArbitrary<'joules'>(),
        ctxArbitrary,
        (j1, j2, ctx) => {
          const cost1 = layer.energyToCost(j1, ctx);
          const cost2 = layer.energyToCost(j2, ctx);
          if (j1.estimate > j2.estimate) {
            expect(cost1).toBeGreaterThanOrEqual(cost2);
          } else if (j1.estimate < j2.estimate) {
            expect(cost1).toBeLessThanOrEqual(cost2);
          } else {
            expect(cost1).toBeCloseTo(cost2, 10);
          }
        },
      ),
      { numRuns: 1000 },
    );
  });

  it('P2b: timeToLatencyMs is monotonic in estimate', () => {
    fc.assert(
      fc.property(
        ciArbitrary<'seconds'>(),
        ciArbitrary<'seconds'>(),
        (s1, s2) => {
          const ms1 = layer.timeToLatencyMs(s1);
          const ms2 = layer.timeToLatencyMs(s2);
          if (s1.estimate > s2.estimate) {
            expect(ms1).toBeGreaterThanOrEqual(ms2);
          } else if (s1.estimate < s2.estimate) {
            expect(ms1).toBeLessThanOrEqual(ms2);
          } else {
            expect(ms1).toBeCloseTo(ms2, 10);
          }
        },
      ),
      { numRuns: 1000 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 3: Uncertainty propagation
  // Reverse mapping CI width >= forward (original) CI width
  // Since reverse returns PACR-Lite bounds (0, Infinity), this always holds.
  // ─────────────────────────────────────────────

  it('P3a: latencyMsToTime CI width >= original seconds CI width', () => {
    fc.assert(
      fc.property(ciArbitrary<'seconds'>(), (seconds) => {
        const originalWidth = seconds.upper - seconds.lower;
        const ms = layer.timeToLatencyMs(seconds);
        const recovered = layer.latencyMsToTime(ms);
        const recoveredWidth = recovered.upper - recovered.lower;
        expect(recoveredWidth).toBeGreaterThanOrEqual(originalWidth);
      }),
      { numRuns: 1000 },
    );
  });

  it('P3b: costToEnergy CI width >= original joules CI width', () => {
    fc.assert(
      fc.property(ciArbitrary<'joules'>(), ctxArbitrary, (joules, ctx) => {
        const originalWidth = joules.upper - joules.lower;
        const cost = layer.energyToCost(joules, ctx);
        const recovered = layer.costToEnergy(cost, 'USD', ctx);
        const recoveredWidth = recovered.upper - recovered.lower;
        expect(recoveredWidth).toBeGreaterThanOrEqual(originalWidth);
      }),
      { numRuns: 1000 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 4: Non-USD currencies return maximum ignorance
  // ─────────────────────────────────────────────

  it('P4: costToEnergy with non-USD returns maximum ignorance', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.01, max: 1e6, noNaN: true }),
        fc.constantFrom('EUR', 'JPY', 'GBP', 'CNY'),
        ctxArbitrary,
        (cost, currency, ctx) => {
          const result = layer.costToEnergy(cost, currency, ctx);
          expect(result.estimate).toBe(0);
          expect(result.lower).toBe(0);
          expect(result.upper).toBe(Infinity);
        },
      ),
      { numRuns: 200 },
    );
  });

  // ─────────────────────────────────────────────
  // Property 5: Forward conversion consistency with scale
  // timeToLatencyMs(seconds) === seconds.estimate * 1000
  // (This is the ONE authorized place where this multiplication exists)
  // ─────────────────────────────────────────────

  it('P5: timeToLatencyMs equals estimate × 1000', () => {
    fc.assert(
      fc.property(ciArbitrary<'seconds'>(), (seconds) => {
        const ms = layer.timeToLatencyMs(seconds);
        expect(ms).toBeCloseTo(seconds.estimate * 1000, 8);
      }),
      { numRuns: 500 },
    );
  });
});
