// src/types/pacr.ts
// Mathematical correspondence: R = (ι, Π, Λ, Ω, Γ, P)
// This file is the "genome" of PACR — modifying it is modifying the species' chromosomes.

import type { EventId, EventIdStructure } from './identity.js';

// ─────────────────────────────────────────────
// Base measurement type: confidence interval triple
// ─────────────────────────────────────────────

/**
 * Physical quantity measurement with confidence interval.
 *
 * Axiom A4: all physical quantities MUST carry uncertainty information.
 *
 * estimate: point estimate (best guess)
 * lower: confidence interval lower bound (inclusive)
 * upper: confidence interval upper bound (inclusive)
 *
 * Invariant: lower <= estimate <= upper
 * Special value: lower = 0, upper = Infinity means "complete ignorance" (PACR-Lite mode)
 */
export interface ConfidenceInterval<Unit extends string = string> {
  readonly estimate: number;
  readonly lower: number;
  readonly upper: number;
  /**
   * Type-level unit annotation.
   * Not used at runtime — only for TypeScript type checking to prevent unit mixing.
   */
  readonly _unit?: Unit;
}

/** Landauer natural units: k_B * T * ln2 (joules) */
export type LandauerUnit = ConfidenceInterval<'landauer'>;
/** Joules */
export type Joules = ConfidenceInterval<'joules'>;
/** Seconds */
export type Seconds = ConfidenceInterval<'seconds'>;
/** Bytes */
export type Bytes = ConfidenceInterval<'bytes'>;
/** Bits per symbol */
export type BitsPerSymbol = ConfidenceInterval<'bits_per_symbol'>;

// ─────────────────────────────────────────────
// Dimension 1: ι — Causal Identity
// ─────────────────────────────────────────────
// Uses EventIdStructure directly, see identity.ts

// ─────────────────────────────────────────────
// Dimension 2: Π — Causal Predecessor Set
// ─────────────────────────────────────────────

/**
 * Causal predecessor set.
 *
 * Mathematical definition: Π ⊆ I_event
 *
 * Axiom I (causality) requires this to be an unordered set (partial order, not total order).
 * Uses ReadonlySet to guarantee immutability.
 * Empty set represents a "genesis event" — no causal predecessors.
 */
export type CausalPredecessorSet = ReadonlySet<EventId>;

// ─────────────────────────────────────────────
// Dimension 3: Λ — Landauer Cost
// ─────────────────────────────────────────────

/**
 * Landauer cost.
 *
 * Mathematical definition: Λ = (λ̂, λ⁻, λ⁺)
 * Unit: k_B * T * ln2 (Landauer natural units)
 *
 * Physical meaning: minimum energy cost of irreversible bit erasure for event ι.
 *
 * PACR-Lite mode: estimate = 0, lower = 0, upper = Infinity
 * (represents "I don't know the Landauer cost, but it exists")
 */
export type LandauerCost = LandauerUnit;

// ─────────────────────────────────────────────
// Dimension 4: Ω — Resource Constraint Triple
// ─────────────────────────────────────────────

/**
 * Resource constraint triple.
 *
 * Mathematical definition: Ω = (E, T, S)
 *
 * The three form an indivisible constraint surface.
 * Splitting them loses consistency checking; merging them loses independent analysis.
 * Therefore defined as a single interface, not three independent fields.
 *
 * Physical constraints (for consistency checking):
 *   T >= πħ / (2E)          [Margolus-Levitin]
 *   S <= 2ET / h            [Bremermann limit]
 */
export interface ResourceConstraintTriple {
  /** Measured energy consumption (joules) */
  readonly energy: Joules;
  /** Measured execution time (seconds) */
  readonly time: Seconds;
  /** Measured space usage (bytes) */
  readonly space: Bytes;
}

// ─────────────────────────────────────────────
// Dimension 5: Γ — Cognitive Split
// ─────────────────────────────────────────────

/**
 * Cognitive split.
 *
 * Mathematical definition: Γ = (S_T, H_T)
 *
 * S_T: statistical complexity (structure) — minimal causal state set information
 * H_T: entropy rate (noise) — residual unpredictability given causal states
 *
 * The two are inseparable projections of the same ε-machine.
 * Without each other, neither has physical meaning.
 *
 * PACR-Lite mode: both set to estimate=0, lower=0, upper=Infinity
 */
export interface CognitiveSplit {
  /** Statistical complexity S_T (bits per symbol) */
  readonly statisticalComplexity: BitsPerSymbol;
  /** Entropy rate H_T (bits per symbol) */
  readonly entropyRate: BitsPerSymbol;
}

// ─────────────────────────────────────────────
// Dimension 6: P — Opaque Payload
// ─────────────────────────────────────────────

/**
 * Opaque payload.
 *
 * Mathematical definition: P ∈ {0,1}*
 *
 * Axiom A5: PACR layer MUST NOT parse P's content.
 * Uses Uint8Array instead of string to enforce opacity —
 * you cannot "accidentally" JSON.parse a Uint8Array.
 */
export type OpaquePayload = Readonly<Uint8Array>;

// ─────────────────────────────────────────────
// PACR six-tuple: complete record
// ─────────────────────────────────────────────

/**
 * PACR — Physically Annotated Causal Record
 *
 * R = (ι, Π, Λ, Ω, Γ, P)
 *
 * Six dimensions, no more, no less.
 * Physically complete, mutually independent, atomically indivisible.
 *
 * This type is the TypeScript encoding of the Day 0 irreversible decision.
 * Modifying this type is equivalent to modifying the physical laws constraining computational events.
 */
export interface PACRecord {
  /** Dimension 1: ι — Causal identity */
  readonly identity: EventIdStructure;
  /** Dimension 2: Π — Causal predecessor set */
  readonly predecessors: CausalPredecessorSet;
  /** Dimension 3: Λ — Landauer cost */
  readonly landauerCost: LandauerCost;
  /** Dimension 4: Ω — Resource constraint triple */
  readonly resources: ResourceConstraintTriple;
  /** Dimension 5: Γ — Cognitive split */
  readonly cognitiveSplit: CognitiveSplit;
  /** Dimension 6: P — Opaque payload */
  readonly payload: OpaquePayload;
}

// ─────────────────────────────────────────────
// PACR-Lite: minimal compliance subset
// ─────────────────────────────────────────────

/**
 * PACR-Lite is NOT a separate type — it IS PACRecord,
 * just with Λ and Γ confidence intervals set to maximum width.
 *
 * This function is a type-level assertion:
 * any PACRecord is valid, including the "complete ignorance" state.
 */
export function isPACRLite(record: PACRecord): boolean {
  const maxIgnorance = (ci: ConfidenceInterval): boolean =>
    ci.lower === 0 && ci.upper === Infinity;

  return (
    maxIgnorance(record.landauerCost) &&
    maxIgnorance(record.cognitiveSplit.statisticalComplexity) &&
    maxIgnorance(record.cognitiveSplit.entropyRate)
  );
}
