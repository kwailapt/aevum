// src/core/commensuration.ts
// CommensuationLayer reference implementation
//
// Axiom A3: This module is the SINGLE authorized location for unit conversions
// between PACR physical units and AgentCard operational units.
// Any `* 1000` or `/ 1000` elsewhere in the codebase is a violation.

import type { ConfidenceInterval } from '../types/pacr.js';
import type { CommensuationContext, CommensuationLayer } from '../types/commensuration.js';

// ─────────────────────────────────────────────
// Conversion constants (named, not magic numbers)
// ─────────────────────────────────────────────

/** 1 second = 1000 milliseconds (exact, definitional) */
const MS_PER_SECOND = 1000;

// ─────────────────────────────────────────────
// Reference implementation
// ─────────────────────────────────────────────

/**
 * Create a CommensuationLayer instance.
 *
 * Design decisions:
 *
 * 1. Forward mappings (PACR → AgentCard) extract the point estimate and convert.
 *    The CI bounds are intentionally discarded — AgentCard fields are scalars.
 *
 * 2. Reverse mappings (AgentCard → PACR) reconstruct a CI from a scalar.
 *    Since the original bounds are lost, the reverse CI uses PACR-Lite bounds
 *    (lower=0, upper=Infinity) to honestly represent maximum ignorance.
 *    This guarantees: reverse CI width >= any original forward CI width.
 *
 * 3. For costToEnergy, non-USD currencies return maximum ignorance
 *    (estimate=0, lower=0, upper=Infinity) because we lack forex rates.
 */
export function createCommensuationLayer(): CommensuationLayer {
  return {
    // ═══ Forward: PACR → AgentCard ═══

    timeToLatencyMs(seconds: ConfidenceInterval<'seconds'>): number {
      return seconds.estimate * MS_PER_SECOND;
    },

    energyToCost(
      joules: ConfidenceInterval<'joules'>,
      ctx: CommensuationContext,
    ): number {
      // cost = energy / (joules_per_usd)
      // energyPriceJoulesPerUSD is "how many joules you get per 1 USD"
      // so cost_in_usd = joules / energyPriceJoulesPerUSD
      return joules.estimate / ctx.energyPriceJoulesPerUSD;
    },

    spaceToBytes(bytes: ConfidenceInterval<'bytes'>): number {
      return bytes.estimate;
    },

    // ═══ Reverse: AgentCard → PACR ═══

    latencyMsToTime(ms: number): ConfidenceInterval<'seconds'> {
      const estimate = ms / MS_PER_SECOND;
      // We lost the original CI — return PACR-Lite bounds (maximum ignorance)
      return { estimate, lower: 0, upper: Infinity };
    },

    costToEnergy(
      cost: number,
      currency: string,
      ctx: CommensuationContext,
    ): ConfidenceInterval<'joules'> {
      if (currency !== 'USD') {
        // Without forex rates, we cannot convert — return maximum ignorance
        return { estimate: 0, lower: 0, upper: Infinity };
      }
      // joules = cost_in_usd * joules_per_usd
      const estimate = cost * ctx.energyPriceJoulesPerUSD;
      // The exchange rate itself has uncertainty we can't quantify from a point estimate.
      // Return PACR-Lite bounds to be honest about this.
      return { estimate, lower: 0, upper: Infinity };
    },
  };
}
