// src/types/envelope.ts
// Envelope = Primary Header (AgentCard routing) + Extension Header (PACR metadata) + Body (P)
// This is the system's "blood format"

import type { AgentId, EventId, CapabilityRef } from './identity.js';
import type { OpaquePayload } from './pacr.js';

// ─────────────────────────────────────────────
// Primary Header: routing required (hourglass waist)
// ─────────────────────────────────────────────

export interface EnvelopePrimaryHeader {
  /** Target agent */
  readonly targetAgentId: AgentId;
  /** Requested capability */
  readonly targetCapability: CapabilityRef;
  /** Source agent */
  readonly sourceAgentId: AgentId;
  /** TTL countdown (remaining hops or remaining seconds) */
  readonly ttl: number;
  /** Protocol version (semantic version, Day 0 is "1.0.0") */
  readonly protocolVersion: string;
}

// ─────────────────────────────────────────────
// Extension Header: PACR metadata (pacr:* namespace)
// ─────────────────────────────────────────────

export interface EnvelopePACRExtension {
  /** pacr:event_id — the event identity for this Envelope */
  readonly 'pacr:event_id': EventId;
  /** pacr:predecessors — serialized form of causal predecessor set */
  readonly 'pacr:predecessors': readonly EventId[];
  /** pacr:landauer_cost — Landauer cost triple */
  readonly 'pacr:landauer_cost': {
    readonly estimate: number;
    readonly lower: number;
    readonly upper: number;
  };
  /** pacr:resources — resource constraint triple */
  readonly 'pacr:resources': {
    readonly energy: { readonly estimate: number; readonly lower: number; readonly upper: number };
    readonly time: { readonly estimate: number; readonly lower: number; readonly upper: number };
    readonly space: { readonly estimate: number; readonly lower: number; readonly upper: number };
  };
  /** pacr:cognitive_split — cognitive split */
  readonly 'pacr:cognitive_split': {
    readonly statisticalComplexity: { readonly estimate: number; readonly lower: number; readonly upper: number };
    readonly entropyRate: { readonly estimate: number; readonly lower: number; readonly upper: number };
  };
}

// ─────────────────────────────────────────────
// Complete Envelope
// ─────────────────────────────────────────────

export interface Envelope {
  readonly primaryHeader: EnvelopePrimaryHeader;
  readonly extensions: EnvelopePACRExtension & {
    /** Allow other namespace extensions */
    readonly [key: string]: unknown;
  };
  /** Body = PACR's P (opaque payload) */
  readonly body: OpaquePayload;
}
