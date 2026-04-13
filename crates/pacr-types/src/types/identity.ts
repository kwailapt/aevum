// src/types/identity.ts
// Mathematical correspondence: I = I_agent ∪ I_event
// This is the referential foundation of the entire system.

// ─────────────────────────────────────────────
// Branded type utility: prevents bare strings from being used as identifiers
// ─────────────────────────────────────────────

declare const __brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [__brand]: B };

// ─────────────────────────────────────────────
// Layer 0: Raw byte-level identity
// ─────────────────────────────────────────────

/**
 * 128-bit identifier in hexadecimal representation (32 hex chars).
 * The underlying representation for all identity identifiers.
 */
export type RawId = Brand<string, 'RawId'>;

// ─────────────────────────────────────────────
// Layer 1: Agent identity space I_agent
// ─────────────────────────────────────────────

/**
 * Agent identity identifier.
 *
 * Mathematical definition: ι_a ∈ I_agent
 *
 * Generation rules:
 * - Prefix "a-" identifies the agent layer
 * - Followed by UUIDv7 hex representation (time-ordered + random)
 * - Format: a-{UUIDv7_hex}
 *
 * Non-forgeability is guaranteed by signing in the generation environment (not defined at this layer).
 */
export type AgentId = Brand<`a-${string}`, 'AgentId'>;

// ─────────────────────────────────────────────
// Layer 2: Event identity space I_event
// ─────────────────────────────────────────────

/**
 * Event identity identifier.
 *
 * Mathematical definition: ι ∈ I_event, where ι carries structural field origin ∈ I_agent
 *
 * Key design: origin is ι's internal structure, NOT the 7th dimension of PACR.
 * Extracting origin from EventId MUST be an O(1) bitwise operation.
 *
 * Format: e-{agent_id_hex}-{UUIDv7_hex}
 * where agent_id_hex is the hex portion of the generating agent's AgentId.
 */
export type EventId = Brand<`e-${string}-${string}`, 'EventId'>;

/**
 * Optional capability reference, embedded in EventId's extended structure.
 * This is NOT part of EventId itself, but metadata transported alongside EventId.
 */
export type CapabilityRef = Brand<string, 'CapabilityRef'>;

/**
 * Structured representation of EventId (for construction and parsing, not wire format).
 */
export interface EventIdStructure {
  /** The complete EventId string (wire format) */
  readonly id: EventId;
  /**
   * The agent that produced this event.
   * Axiom A2 guarantees: this value MUST be a valid AgentId.
   */
  readonly origin: AgentId;
  /**
   * Optional: the agent capability name this event corresponds to.
   * If present, must match some capability.name in the origin agent's AgentCard.
   */
  readonly capabilityRef?: CapabilityRef | undefined;
  /** UUIDv7 timestamp component (millisecond precision) */
  readonly timestampMs: number;
}

// ─────────────────────────────────────────────
// Layer 3: Unified identity space operations
// ─────────────────────────────────────────────

/**
 * Unified identity space I = I_agent ∪ I_event
 * Distinguished by prefix "a-" / "e-"
 */
export type AevumId = AgentId | EventId;

/**
 * Type guard: determines if an AevumId is an AgentId.
 */
export function isAgentId(id: AevumId): id is AgentId {
  return (id as string).startsWith('a-');
}

/**
 * Type guard: determines if an AevumId is an EventId.
 */
export function isEventId(id: AevumId): id is EventId {
  return (id as string).startsWith('e-');
}

/**
 * O(1) extraction: extracts origin AgentId from an EventId.
 * This is the core requirement of P0-1: causal attribution must be constant-time.
 */
export function extractOrigin(eventId: EventId): AgentId {
  // Format: e-{agent_hex}-{event_uuid_hex}
  // agent_hex is fixed length (32 hex chars), so this is a pure bit offset
  const raw = eventId as string;
  const agentHex = raw.substring(2, 34); // skip "e-", take 32 chars
  return `a-${agentHex}` as AgentId;
}
