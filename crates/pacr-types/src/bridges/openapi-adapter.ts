// src/bridges/openapi-adapter.ts
// OpenAPI → PACR-Lite bridge adapter
//
// Maps HTTP request/response metadata into a structurally complete PACRecord.
// This is a bridge adapter (trust boundary): `as` assertions are permitted
// per CLAUDE.md coding standards, with comments explaining why they're safe.

import type { AgentId, EventId, CapabilityRef, EventIdStructure } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type { CommensuationLayer } from '../types/commensuration.js';
import { createCommensuationLayer } from '../core/commensuration.js';
import { createEventId, validateEventId } from '../core/identity.js';

// ─────────────────────────────────────────────
// OpenAPI event context (HTTP metadata)
// ─────────────────────────────────────────────

export interface OpenAPIEventContext {
  /** HTTP X-Request-Id header */
  readonly requestId: string;
  /** HTTP Referer header (approximate causal predecessor) */
  readonly referer?: string | undefined;
  /** X-Request-Chain header (if present) */
  readonly requestChain?: readonly string[] | undefined;
  /** Response time measured from HTTP request/response (milliseconds) */
  readonly responseTimeMs: number;
  /** Request body Content-Length (bytes) */
  readonly requestBodyBytes: number;
  /** Response body Content-Length (bytes) */
  readonly responseBodyBytes: number;
}

// ─────────────────────────────────────────────
// PACR-Lite CI constants
// ─────────────────────────────────────────────

const MAX_IGNORANCE = { estimate: 0, lower: 0, upper: Infinity } as const;

// ─────────────────────────────────────────────
// Bridge function
// ─────────────────────────────────────────────

/**
 * Convert an OpenAPI HTTP event into a PACR-Lite record.
 *
 * Mapping rules:
 * - ι: New EventId for the given agent (requestId is NOT used as raw ID
 *       because it may not conform to I_event format)
 * - Π: Approximate causality from referer/requestChain (marked as approximate)
 * - Λ: PACR-Lite (HTTP provides no Landauer cost information)
 * - Ω.T: Converted from responseTimeMs via CommensuationLayer (A3 compliant)
 * - Ω.E: PACR-Lite (HTTP provides no energy information)
 * - Ω.S: Estimated from request + response body sizes
 * - Γ: PACR-Lite (HTTP provides no cognitive split information)
 * - P: Empty (raw HTTP body not captured by default — privacy policy decision)
 *
 * The returned PACRecord passes TC-002 (six-dimension completeness).
 *
 * @param layer - Optional CommensuationLayer instance; creates default if not provided
 */
export function openAPIToPACRLite(
  agentId: AgentId,
  context: OpenAPIEventContext,
  layer?: CommensuationLayer,
): PACRecord {
  const commensuration = layer ?? createCommensuationLayer();

  // ── ι: Causal Identity ──
  // Generate a proper EventId; store the requestId as metadata on the side,
  // not as the raw identifier (requestId format is not guaranteed to be I_event)
  const identity = createEventId(agentId);

  // ── Π: Approximate Causal Predecessors ──
  const predecessors = buildApproximatePredecessors(agentId, context);

  // ── Λ: Landauer Cost — PACR-Lite ──
  // HTTP provides no thermodynamic information
  const landauerCost = { estimate: 0, lower: 0, upper: Infinity };

  // ── Ω: Resource Constraints ──
  // Ω.T: via CommensuationLayer (A3 compliant — no bare / 1000)
  const time = commensuration.latencyMsToTime(context.responseTimeMs);

  // Ω.E: PACR-Lite (HTTP provides no energy data)
  const energy = { estimate: 0, lower: 0, upper: Infinity };

  // Ω.S: request + response body sizes as space estimate
  const totalBytes = context.requestBodyBytes + context.responseBodyBytes;
  const space = { estimate: totalBytes, lower: 0, upper: totalBytes * 2 };

  // ── Γ: Cognitive Split — PACR-Lite ──
  const cognitiveSplit = {
    statisticalComplexity: MAX_IGNORANCE,
    entropyRate: MAX_IGNORANCE,
  };

  // ── P: Opaque Payload ──
  // Empty by default (privacy: don't capture raw HTTP bodies).
  // Implementers can override by wrapping this function.
  const payload = new Uint8Array(0);

  return {
    identity,
    predecessors,
    landauerCost,
    resources: { energy, time, space },
    cognitiveSplit,
    payload,
  };
}

// ─────────────────────────────────────────────
// Internal: approximate causality from HTTP headers
// ─────────────────────────────────────────────

/**
 * Build an approximate predecessor set from HTTP headers.
 *
 * This is NOT precise causal ordering — it's an approximation based on:
 * 1. X-Request-Chain: explicit chain of upstream request IDs
 * 2. Referer: single upstream reference
 *
 * Only entries that are valid EventId strings are included.
 * Invalid entries are silently dropped (HTTP headers are untrusted input).
 */
function buildApproximatePredecessors(
  _agentId: AgentId,
  context: OpenAPIEventContext,
): ReadonlySet<EventId> {
  const preds = new Set<EventId>();

  // X-Request-Chain takes priority (explicit causal chain)
  if (context.requestChain !== undefined) {
    for (const entry of context.requestChain) {
      // Only include entries that conform to EventId format
      // (bridge boundary: `as` assertion safe after validation)
      if (validateEventId(entry)) {
        preds.add(entry as EventId);
      }
    }
  }

  // Referer as fallback single predecessor
  if (context.referer !== undefined && validateEventId(context.referer)) {
    // Bridge boundary: safe after validation
    preds.add(context.referer as EventId);
  }

  return preds;
}
