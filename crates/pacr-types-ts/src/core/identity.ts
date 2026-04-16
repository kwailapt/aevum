// src/core/identity.ts
// Runtime identity generation and validation for the shared identity space I = I_agent ∪ I_event
// This module is the ONLY trust boundary for constructing branded identity types.

import { randomFillSync } from 'node:crypto';
import type { AgentId, EventId, CapabilityRef, EventIdStructure } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';

// ─────────────────────────────────────────────
// Internal: UUIDv7 generation
// ─────────────────────────────────────────────

/** Precomputed hex lookup table: index → 2-char hex string */
const HEX_TABLE: readonly string[] = /* @__PURE__ */ (() => {
  const table: string[] = [];
  for (let i = 0; i < 256; i++) {
    table.push(i.toString(16).padStart(2, '0'));
  }
  return table;
})();

/**
 * Generate a UUIDv7-compliant 128-bit identifier as a 32-char hex string.
 *
 * Layout (RFC 9562):
 *   bytes[0..5]  = 48-bit Unix timestamp in milliseconds (big-endian)
 *   bytes[6]     = 0x7_ (version 7 in high nibble, random in low nibble)
 *   bytes[7]     = random
 *   bytes[8]     = 0b10__ ____ (variant bits in high 2 bits, random in low 6 bits)
 *   bytes[9..15] = random
 */
function generateUUIDv7Hex(): string {
  const bytes = new Uint8Array(16);
  randomFillSync(bytes);

  // Write 48-bit ms timestamp into bytes[0..5] (big-endian)
  const now = Date.now();
  // We use division + modulo instead of bitwise ops to avoid 32-bit truncation
  let remaining = now;
  for (let i = 5; i >= 0; i--) {
    bytes[i] = remaining & 0xff;
    remaining = Math.floor(remaining / 256);
  }

  // Set version 7: byte[6] high nibble = 0111
  bytes[6] = (bytes[6]! & 0x0f) | 0x70;

  // Set variant 10: byte[8] high 2 bits = 10
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;

  // Convert to hex using lookup table (no indexed access on result)
  let hex = '';
  for (const byte of bytes) {
    hex += HEX_TABLE[byte]!;
  }
  return hex;
}

/**
 * Extract the 48-bit ms timestamp from a UUIDv7 hex string.
 * The first 12 hex chars encode the timestamp.
 * Safe for parseInt because 2^48 ≈ 2.8×10^14 < Number.MAX_SAFE_INTEGER (2^53).
 */
function extractTimestampFromUUIDv7Hex(hex: string): number {
  return parseInt(hex.substring(0, 12), 16);
}

// ─────────────────────────────────────────────
// Validation patterns
// ─────────────────────────────────────────────

// 32 hex chars with UUIDv7 structure:
//   chars[12] = version nibble = '7'
//   chars[16] = variant nibble ∈ {'8','9','a','b'}
const UUIDV7_HEX_PATTERN = /^[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$/;

/** Full AgentId pattern: "a-" + valid UUIDv7 hex */
const AGENT_ID_PATTERN = /^a-[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$/;

/** Full EventId pattern: "e-" + valid UUIDv7 hex + "-" + valid UUIDv7 hex */
const EVENT_ID_PATTERN =
  /^e-[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}-[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$/;

// ─────────────────────────────────────────────
// Public API: factory functions
// ─────────────────────────────────────────────

/**
 * Create a new AgentId using UUIDv7.
 *
 * This is a trust boundary: the `as AgentId` assertion is safe because
 * we just generated a valid UUIDv7 and prefixed it correctly.
 */
export function createAgentId(): AgentId {
  const hex = generateUUIDv7Hex();
  return `a-${hex}` as AgentId;
}

/**
 * Create a new EventId and return its full structured representation.
 *
 * The origin AgentId's hex is embedded in the EventId string, ensuring
 * that extractOrigin() can recover it in O(1).
 *
 * Trust boundary: `as EventId` is safe because we control the format.
 */
export function createEventId(
  origin: AgentId,
  capabilityRef?: CapabilityRef,
): EventIdStructure {
  const agentHex = (origin as string).substring(2); // strip "a-" prefix
  const eventHex = generateUUIDv7Hex();
  const id = `e-${agentHex}-${eventHex}` as EventId;
  const timestampMs = extractTimestampFromUUIDv7Hex(eventHex);

  if (capabilityRef !== undefined) {
    return { id, origin, capabilityRef, timestampMs };
  }
  return { id, origin, timestampMs };
}

// ─────────────────────────────────────────────
// Public API: validation functions
// ─────────────────────────────────────────────

/**
 * Validate that a raw string is a structurally valid AgentId.
 *
 * Checks:
 * 1. "a-" prefix
 * 2. 32 lowercase hex chars
 * 3. UUIDv7 version nibble = 7
 * 4. UUIDv7 variant nibble ∈ {8,9,a,b}
 */
export function validateAgentId(raw: string): raw is AgentId {
  return AGENT_ID_PATTERN.test(raw);
}

/**
 * Validate that a raw string is a structurally valid EventId.
 *
 * Checks:
 * 1. "e-" prefix
 * 2. Two 32-char hex segments separated by "-"
 * 3. Both segments have valid UUIDv7 version/variant bits
 */
export function validateEventId(raw: string): raw is EventId {
  return EVENT_ID_PATTERN.test(raw);
}

// ─────────────────────────────────────────────
// Public API: parsing
// ─────────────────────────────────────────────

/**
 * Parse an EventId into its structured components.
 *
 * Precondition: id is a valid EventId (branded type guarantees this).
 * The capabilityRef is NOT encoded in the EventId string,
 * so it is absent from the result.
 *
 * Trust boundary: `as AgentId` delegation is to extractOrigin() in types/.
 */
export function parseEventId(id: EventId): EventIdStructure {
  const origin = extractOrigin(id);
  // Event UUID hex starts after "e-" (2) + agent hex (32) + "-" (1) = position 35
  const eventHex = (id as string).substring(35);
  const timestampMs = extractTimestampFromUUIDv7Hex(eventHex);
  return { id, origin, timestampMs };
}
