// src/types/commensuration.ts
// Commensuration layer interface types
// Axiom A3: all unit conversions between PACR physical units and AgentCard operational units
// MUST pass through explicitly defined conversion functions. No hardcoded conversions allowed.

import type { ConfidenceInterval } from './pacr.js';

// ─────────────────────────────────────────────
// Conversion context: environmental parameters
// ─────────────────────────────────────────────

/**
 * Environmental context for commensuration conversions.
 *
 * All energy-to-cost conversions are context-dependent:
 * - Energy prices vary by region, provider, and time
 * - The exchange rate itself carries uncertainty (but we model it as a point estimate here;
 *   the reverse mapping's wider CI accounts for this)
 */
export interface CommensuationContext {
  /** Timestamp of the conversion context (ms since epoch) */
  readonly timestampMs: number;
  /** Geographic region (ISO 3166-1 alpha-2) */
  readonly geoRegion: string;
  /** Infrastructure provider identifier */
  readonly infrastructureProvider: string;
  /** Energy price: joules per 1 USD — the exchange rate for energy ↔ cost */
  readonly energyPriceJoulesPerUSD: number;
}

// ─────────────────────────────────────────────
// Commensuration layer interface
// ─────────────────────────────────────────────

/**
 * CommensuationLayer — the explicit gateway between PACR physical units
 * and AgentCard operational units.
 *
 * Axiom A3 mandate: EVERY conversion between PACR's physical units
 * (joules, seconds, bytes) and AgentCard's operational units
 * (milliseconds, dollars) MUST go through this interface.
 *
 * Design asymmetry:
 * - Forward (PACR → AgentCard): returns number (point estimate for AgentCard's scalar fields)
 * - Reverse (AgentCard → PACR): returns ConfidenceInterval (restores uncertainty structure)
 *
 * The reverse mapping ALWAYS produces wider CI than the original,
 * because the forward mapping irreversibly discards uncertainty information.
 *
 * Violation example (FORBIDDEN):
 *   const latencyMs = pacrRecord.resources.time.estimate * 1000;
 *
 * Correct usage:
 *   const latencyMs = layer.timeToLatencyMs(pacrRecord.resources.time);
 */
export interface CommensuationLayer {
  // ═══ Forward: PACR physical → AgentCard operational ═══

  /** Convert PACR Ω.T (seconds CI) → AgentCard latency (milliseconds scalar) */
  timeToLatencyMs(seconds: ConfidenceInterval<'seconds'>): number;
  /** Convert PACR Ω.E (joules CI) → AgentCard cost (USD scalar) */
  energyToCost(joules: ConfidenceInterval<'joules'>, ctx: CommensuationContext): number;
  /** Convert PACR Ω.S (bytes CI) → AgentCard bytes (scalar) */
  spaceToBytes(bytes: ConfidenceInterval<'bytes'>): number;

  // ═══ Reverse: AgentCard operational → PACR physical (with precision loss marker) ═══

  /** Convert AgentCard latency (ms) → PACR Ω.T (seconds CI, widened bounds) */
  latencyMsToTime(ms: number): ConfidenceInterval<'seconds'>;
  /**
   * Convert AgentCard cost (USD) → PACR Ω.E (joules CI, widened bounds)
   * @param currency — ISO 4217 currency code; only 'USD' uses the context rate directly
   */
  costToEnergy(cost: number, currency: string, ctx: CommensuationContext): ConfidenceInterval<'joules'>;
}

// ─────────────────────────────────────────────
// Physical constants (SI 2019 exact values)
// ─────────────────────────────────────────────

/** Boltzmann constant k_B (J/K) — exact value since 2019 SI redefinition */
export const BOLTZMANN_CONSTANT = 1.380649e-23;
/** Natural logarithm of 2 */
export const LN2 = 0.6931471805599453;
/** Planck constant h (J·s) — exact value */
export const PLANCK_CONSTANT = 6.62607015e-34;
/** Reduced Planck constant ħ = h/(2π) (J·s) */
export const REDUCED_PLANCK_CONSTANT = PLANCK_CONSTANT / (2 * Math.PI);
/** Speed of light c (m/s) — exact value */
export const SPEED_OF_LIGHT = 299_792_458;
/** Landauer energy at 300K: k_B * 300 * ln2 ≈ 2.8705e-21 J */
export const LANDAUER_UNIT_AT_300K = BOLTZMANN_CONSTANT * 300 * LN2;
