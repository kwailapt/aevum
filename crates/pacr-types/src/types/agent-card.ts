// src/types/agent-card.ts
// AgentCard: agent's static capability description
// Relationship with PACR: AgentCard is the aggregation projection surface of PACR records

import type { AgentId, CapabilityRef } from './identity.js';
import type { BitsPerSymbol, ConfidenceInterval } from './pacr.js';

// ─────────────────────────────────────────────
// AgentCard core fields
// ─────────────────────────────────────────────

export interface Capability {
  /** Capability name, also serves as the value space for PACR EventId's capabilityRef */
  readonly name: CapabilityRef;
  /** Human-readable description */
  readonly description: string;
  /** Machine-readable input schema (JSON Schema or equivalent) */
  readonly inputSchema?: unknown;
  /** Machine-readable output schema */
  readonly outputSchema?: unknown;
}

export interface AgentCardMetadata {
  /**
   * Namespaced metadata.
   * Format: `namespace:key`
   *
   * Aevum reserved namespaces:
   * - `aevum:behavior_entropy` → AgentCard-level H̄_T (aggregated from PACR Γ by Σ operator)
   * - `pacr:interaction_summary` → Agent interaction graph (projected from PACR Π by π operator)
   * - `pacr:landauer_efficiency` → Landauer efficiency (aggregated from Ω.E - Λ)
   */
  readonly [namespacedKey: string]: unknown;
}

/**
 * AgentCard — Agent's static capability description.
 *
 * Design principles:
 * - Required fields are the hourglass waist (routing necessities)
 * - Metadata is extensible (infinite evolution space)
 * - Relationship with PACR is bridged through aevum:* and pacr:* namespaces
 */
export interface AgentCard {
  // ═══ Routing required fields (hourglass waist) ═══

  /** Agent identity, shares identity space with PACR ι.origin */
  readonly agentId: AgentId;
  /** Agent's human-readable name */
  readonly name: string;
  /** Agent's capability list */
  readonly capabilities: readonly Capability[];
  /**
   * Agent's endpoint URL (routing target).
   * Can be HTTP, WebSocket, gRPC, etc.
   */
  readonly endpoint: string;
  /**
   * Time to live (seconds).
   * Defines AgentCard's cache validity period.
   * Also implicitly defines the sliding window width for PACR aggregation.
   */
  readonly ttlSeconds: number;

  // ═══ Operational metric fields ═══

  /**
   * Estimated latency (milliseconds).
   * Note: this value is an aggregated projection of PACR Ω.T, converted through the commensuration layer.
   * MUST NOT be obtained by manually multiplying PACR's seconds value by 1000.
   */
  readonly estimatedLatencyMs?: number | undefined;
  /**
   * Cost per call (monetary units).
   * Note: this value is the result of converting PACR Ω.E through exchange rate function f(E, Context).
   */
  readonly costPerCall?: number | undefined;
  /** Cost currency unit (ISO 4217) */
  readonly costCurrency?: string | undefined;

  // ═══ Tags & discovery ═══

  readonly tags?: readonly string[] | undefined;
  readonly version?: string | undefined;

  // ═══ Extensible metadata ═══

  readonly metadata?: AgentCardMetadata | undefined;
}

// ─────────────────────────────────────────────
// AgentCard fields populated by PACR aggregation
// ─────────────────────────────────────────────

/**
 * Agent behavior entropy — aggregated from PACR Γ by Σ operator.
 * Written to AgentCard.metadata['aevum:behavior_entropy']
 */
export interface AgentBehaviorEntropy {
  /** Aggregated H̄_T */
  readonly aggregatedEntropyRate: BitsPerSymbol;
  /** Aggregated S̄_T */
  readonly aggregatedStatisticalComplexity: BitsPerSymbol;
  /** Number of PACR records in the aggregation window */
  readonly sampleCount: number;
  /** Time span of the aggregation window (seconds) */
  readonly windowSeconds: number;
}

/**
 * Agent interaction summary — projected from PACR Π by π operator.
 * Written to AgentCard.metadata['pacr:interaction_summary']
 */
export interface AgentInteractionSummary {
  /** Other agents this agent has called, with frequency */
  readonly callees: ReadonlyMap<AgentId, InteractionEdge>;
  /** Other agents that have called this agent, with frequency */
  readonly callers: ReadonlyMap<AgentId, InteractionEdge>;
}

export interface InteractionEdge {
  readonly callCount: number;
  readonly averageLatency: ConfidenceInterval<'seconds'>;
  readonly averageEnergy: ConfidenceInterval<'joules'>;
  readonly lastInteractionTimestampMs: number;
}
