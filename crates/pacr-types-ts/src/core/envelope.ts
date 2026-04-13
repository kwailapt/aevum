// src/core/envelope.ts
// Envelope construction, extraction, serialization, and deserialization.
//
// Wire format layout:
//
// ┌──────────────────── PRIMARY HEADER (fixed routing prefix) ────────────────────┐
// │ [0..3]    Magic number: 0x50414352 ("PACR")                                  │
// │ [4..5]    Primary header total length (uint16 BE, includes variable fields)   │
// │ [6..39]   targetAgentId  (34 bytes ASCII: "a-" + 32 hex)                     │
// │ [40..73]  sourceAgentId  (34 bytes ASCII: "a-" + 32 hex)                     │
// │ [74..77]  ttl            (uint32 BE)                                         │
// │ ── fixed routing portion ends at byte 78 ──                                  │
// │ [78..79]  targetCapability length (uint16 BE)                                │
// │ [80..80+N-1] targetCapability (UTF-8)                                        │
// │ [80+N..80+N+1] protocolVersion length (uint16 BE)                            │
// │ [80+N+2..80+N+1+M] protocolVersion (UTF-8)                                  │
// └──────────────────────────────────────────────────────────────────────────────┘
// ┌──────────────────── EXTENSION HEADERS ───────────────────────────────────────┐
// │ [H..H+3]  Extensions total byte length (uint32 BE)                          │
// │ For each extension key-value pair:                                           │
// │   uint16 BE key length + key bytes (UTF-8)                                  │
// │   uint32 BE value length + value bytes (JSON-encoded)                       │
// └──────────────────────────────────────────────────────────────────────────────┘
// ┌──────────────────── BODY ────────────────────────────────────────────────────┐
// │ Remaining bytes = opaque payload (P)                                         │
// └──────────────────────────────────────────────────────────────────────────────┘
//
// Zero-copy routing: bytes [6..77] contain all fixed-offset routing fields.
// A router can read targetAgentId, sourceAgentId, and ttl without parsing
// the variable-length fields or extension headers.

import type { AgentId, EventId, CapabilityRef, EventIdStructure } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord, ConfidenceInterval, OpaquePayload } from '../types/pacr.js';
import type {
  Envelope,
  EnvelopePrimaryHeader,
  EnvelopePACRExtension,
} from '../types/envelope.js';

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const MAGIC = 0x50414352; // "PACR" in ASCII
const AGENT_ID_BYTES = 34; // "a-" + 32 hex chars
const FIXED_ROUTING_PREFIX = 78; // magic(4) + headerLen(2) + target(34) + source(34) + ttl(4)

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

// ─────────────────────────────────────────────
// Envelope construction: PACRecord → Envelope
// ─────────────────────────────────────────────

/**
 * Create an Envelope from a primary header and a PACR record.
 *
 * Extracts PACR metadata into extension headers (pacr:* namespace).
 * The record's payload becomes the envelope body.
 */
export function createEnvelope(
  primaryHeader: EnvelopePrimaryHeader,
  record: PACRecord,
): Envelope {
  const extensions: EnvelopePACRExtension = {
    'pacr:event_id': record.identity.id,
    'pacr:predecessors': [...record.predecessors],
    'pacr:landauer_cost': {
      estimate: record.landauerCost.estimate,
      lower: record.landauerCost.lower,
      upper: record.landauerCost.upper,
    },
    'pacr:resources': {
      energy: {
        estimate: record.resources.energy.estimate,
        lower: record.resources.energy.lower,
        upper: record.resources.energy.upper,
      },
      time: {
        estimate: record.resources.time.estimate,
        lower: record.resources.time.lower,
        upper: record.resources.time.upper,
      },
      space: {
        estimate: record.resources.space.estimate,
        lower: record.resources.space.lower,
        upper: record.resources.space.upper,
      },
    },
    'pacr:cognitive_split': {
      statisticalComplexity: {
        estimate: record.cognitiveSplit.statisticalComplexity.estimate,
        lower: record.cognitiveSplit.statisticalComplexity.lower,
        upper: record.cognitiveSplit.statisticalComplexity.upper,
      },
      entropyRate: {
        estimate: record.cognitiveSplit.entropyRate.estimate,
        lower: record.cognitiveSplit.entropyRate.lower,
        upper: record.cognitiveSplit.entropyRate.upper,
      },
    },
  };

  return {
    primaryHeader,
    extensions: extensions as Envelope['extensions'],
    body: record.payload,
  };
}

// ─────────────────────────────────────────────
// Envelope extraction: Envelope → PACRecord
// ─────────────────────────────────────────────

/**
 * Extract a PACRecord from an Envelope.
 * This is the precise inverse of createEnvelope.
 */
export function extractPACRecord(envelope: Envelope): PACRecord {
  const ext = envelope.extensions;
  const eventId = ext['pacr:event_id'];
  const origin = extractOrigin(eventId);

  // Reconstruct EventIdStructure
  // Extract timestamp from the event UUID portion of the EventId
  const eventHex = (eventId as string).substring(35);
  const timestampMs = parseInt(eventHex.substring(0, 12), 16);

  const identity: EventIdStructure = {
    id: eventId,
    origin,
    timestampMs,
  };

  const predecessors = new Set(ext['pacr:predecessors']) as ReadonlySet<EventId>;

  const lc = ext['pacr:landauer_cost'];
  const res = ext['pacr:resources'];
  const cs = ext['pacr:cognitive_split'];

  return {
    identity,
    predecessors,
    landauerCost: { estimate: lc.estimate, lower: lc.lower, upper: lc.upper },
    resources: {
      energy: { estimate: res.energy.estimate, lower: res.energy.lower, upper: res.energy.upper },
      time: { estimate: res.time.estimate, lower: res.time.lower, upper: res.time.upper },
      space: { estimate: res.space.estimate, lower: res.space.lower, upper: res.space.upper },
    },
    cognitiveSplit: {
      statisticalComplexity: {
        estimate: cs.statisticalComplexity.estimate,
        lower: cs.statisticalComplexity.lower,
        upper: cs.statisticalComplexity.upper,
      },
      entropyRate: {
        estimate: cs.entropyRate.estimate,
        lower: cs.entropyRate.lower,
        upper: cs.entropyRate.upper,
      },
    },
    payload: envelope.body,
  };
}

// ─────────────────────────────────────────────
// Serialization: Envelope → Uint8Array
// ─────────────────────────────────────────────

/**
 * Serialize an Envelope to a binary Uint8Array.
 *
 * Wire format ensures the fixed routing prefix (bytes 6–77) can be read
 * without parsing any variable-length fields.
 */
export function serializeEnvelope(envelope: Envelope): Uint8Array {
  const h = envelope.primaryHeader;

  // Encode variable-length primary header fields
  const capBytes = textEncoder.encode(h.targetCapability as string);
  const verBytes = textEncoder.encode(h.protocolVersion);
  const primaryHeaderLen = FIXED_ROUTING_PREFIX + 2 + capBytes.length + 2 + verBytes.length;

  // Encode extension headers as JSON key-value pairs
  const extEntries = encodeExtensions(envelope.extensions);
  const extTotalLen = extEntries.reduce((sum, e) => sum + e.length, 0);

  // Body
  const body = envelope.body;
  const totalLen = primaryHeaderLen + 4 + extTotalLen + body.length;
  const buf = new Uint8Array(totalLen);
  const view = new DataView(buf.buffer);
  let offset = 0;

  // ── Primary header: fixed routing prefix ──
  view.setUint32(offset, MAGIC); offset += 4;
  view.setUint16(offset, primaryHeaderLen); offset += 2;

  // targetAgentId (34 bytes ASCII)
  writeAscii(buf, offset, h.targetAgentId as string, AGENT_ID_BYTES); offset += AGENT_ID_BYTES;
  // sourceAgentId (34 bytes ASCII)
  writeAscii(buf, offset, h.sourceAgentId as string, AGENT_ID_BYTES); offset += AGENT_ID_BYTES;
  // ttl (uint32 BE)
  view.setUint32(offset, h.ttl); offset += 4;

  // ── Primary header: variable fields ──
  view.setUint16(offset, capBytes.length); offset += 2;
  buf.set(capBytes, offset); offset += capBytes.length;
  view.setUint16(offset, verBytes.length); offset += 2;
  buf.set(verBytes, offset); offset += verBytes.length;

  // ── Extension headers ──
  view.setUint32(offset, extTotalLen); offset += 4;
  for (const entry of extEntries) {
    buf.set(entry, offset); offset += entry.length;
  }

  // ── Body ──
  buf.set(body, offset);

  return buf;
}

// ─────────────────────────────────────────────
// Deserialization: Uint8Array → Envelope
// ─────────────────────────────────────────────

/**
 * Deserialize a binary Uint8Array back into an Envelope.
 *
 * Validates the magic number. Throws on format errors.
 */
export function deserializeEnvelope(bytes: Uint8Array): Envelope {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 0;

  // Magic number
  const magic = view.getUint32(offset); offset += 4;
  if (magic !== MAGIC) {
    throw new Error(`Invalid PACR envelope: bad magic 0x${magic.toString(16)}`);
  }

  // Primary header length
  const primaryHeaderLen = view.getUint16(offset); offset += 2;

  // Fixed routing fields
  const targetAgentId = readAscii(bytes, offset, AGENT_ID_BYTES) as AgentId;
  offset += AGENT_ID_BYTES;
  const sourceAgentId = readAscii(bytes, offset, AGENT_ID_BYTES) as AgentId;
  offset += AGENT_ID_BYTES;
  const ttl = view.getUint32(offset); offset += 4;

  // Variable fields
  const capLen = view.getUint16(offset); offset += 2;
  const targetCapability = textDecoder.decode(bytes.subarray(offset, offset + capLen)) as CapabilityRef;
  offset += capLen;
  const verLen = view.getUint16(offset); offset += 2;
  const protocolVersion = textDecoder.decode(bytes.subarray(offset, offset + verLen));
  offset += verLen;

  const primaryHeader: EnvelopePrimaryHeader = {
    targetAgentId,
    targetCapability,
    sourceAgentId,
    ttl,
    protocolVersion,
  };

  // Extension headers
  const extTotalLen = view.getUint32(offset); offset += 4;
  const extEnd = offset + extTotalLen;
  const extMap = new Map<string, unknown>();

  while (offset < extEnd) {
    const keyLen = view.getUint16(offset); offset += 2;
    const key = textDecoder.decode(bytes.subarray(offset, offset + keyLen));
    offset += keyLen;
    const valLen = view.getUint32(offset); offset += 4;
    const valStr = textDecoder.decode(bytes.subarray(offset, offset + valLen));
    offset += valLen;
    extMap.set(key, JSON.parse(valStr, jsonReviver));
  }

  const extensions = Object.fromEntries(extMap) as Envelope['extensions'];

  // Body = remaining bytes
  const body = bytes.slice(offset) as OpaquePayload;

  return { primaryHeader, extensions, body };
}

// ─────────────────────────────────────────────
// Zero-copy routing: read primary header fields at fixed offsets
// ─────────────────────────────────────────────

/**
 * Read the target AgentId from a serialized envelope WITHOUT parsing
 * extension headers or body. O(1) fixed-offset read.
 */
export function readTargetAgentId(bytes: Uint8Array): AgentId {
  return readAscii(bytes, 6, AGENT_ID_BYTES) as AgentId;
}

/**
 * Read the source AgentId from a serialized envelope. O(1) fixed-offset read.
 */
export function readSourceAgentId(bytes: Uint8Array): AgentId {
  return readAscii(bytes, 40, AGENT_ID_BYTES) as AgentId;
}

/**
 * Read the TTL from a serialized envelope. O(1) fixed-offset read.
 */
export function readTTL(bytes: Uint8Array): number {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return view.getUint32(74);
}

// ─────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────

/** Sentinel string for Infinity in JSON (JSON.stringify(Infinity) → null, which is lossy) */
const INF_SENTINEL = '__PACR_INF__';
const NEG_INF_SENTINEL = '__PACR_NEG_INF__';

/** JSON replacer: Infinity → sentinel string */
function jsonReplacer(_key: string, value: unknown): unknown {
  if (value === Infinity) return INF_SENTINEL;
  if (value === -Infinity) return NEG_INF_SENTINEL;
  return value;
}

/** JSON reviver: sentinel string → Infinity */
function jsonReviver(_key: string, value: unknown): unknown {
  if (value === INF_SENTINEL) return Infinity;
  if (value === NEG_INF_SENTINEL) return -Infinity;
  return value;
}

function writeAscii(buf: Uint8Array, offset: number, str: string, len: number): void {
  for (let i = 0; i < len && i < str.length; i++) {
    buf[offset + i] = str.charCodeAt(i);
  }
}

function readAscii(buf: Uint8Array, offset: number, len: number): string {
  let str = '';
  for (let i = 0; i < len; i++) {
    str += String.fromCharCode(buf[offset + i]!);
  }
  return str;
}

/** Encode extension entries as a flat list of (keyLen + key + valLen + valJSON) buffers */
function encodeExtensions(
  extensions: Envelope['extensions'],
): Uint8Array[] {
  const result: Uint8Array[] = [];
  for (const [key, value] of Object.entries(extensions)) {
    const keyBytes = textEncoder.encode(key);
    const valBytes = textEncoder.encode(JSON.stringify(value, jsonReplacer));
    const entry = new Uint8Array(2 + keyBytes.length + 4 + valBytes.length);
    const entryView = new DataView(entry.buffer);
    let off = 0;
    entryView.setUint16(off, keyBytes.length); off += 2;
    entry.set(keyBytes, off); off += keyBytes.length;
    entryView.setUint32(off, valBytes.length); off += 4;
    entry.set(valBytes, off);
    result.push(entry);
  }
  return result;
}
