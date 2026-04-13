// src/bridges/factory.ts
// PACR Bridge Factory — wrap any function or client with PACR-Lite tracing.
//
// Design: "影子一樣" — every call silently generates a PACRecord alongside the
// original operation. The wrapper is semantically transparent: return value,
// error propagation, and Promise behaviour are identical to the original.
//
// All bridges produce PACR-Lite records:
//   TC-M01..M06 → PASS (structural correctness guaranteed)
//   TC-S01, TC-S02 → WARN (Λ and Γ set to max ignorance — expected)

import { createHash } from 'node:crypto';
import type { AgentId, EventId, CapabilityRef, EventIdStructure } from '../types/identity.js';
import { validateEventId } from '../core/identity.js';
import { createEventId } from '../core/identity.js';
import type { PACRecord } from '../types/pacr.js';
import { createCommensuationLayer } from '../core/commensuration.js';

// ─────────────────────────────────────────────────────────────────────────────
// Public types
// ─────────────────────────────────────────────────────────────────────────────

/** PACR record output target. emit() is fire-and-forget: errors must be caught internally. */
export interface PACRSink {
  emit(record: PACRecord): Promise<void>;
}

export type CausalityStrategy =
  | { type: 'http_header'; headerName: string }
  | { type: 'context_var'; getContext: () => EventId[] }
  | { type: 'sequential' }
  | { type: 'none' };

export interface EnrichmentConfig {
  /** Attempt to measure energy via OS-level API (not yet implemented — reserved) */
  measureEnergy?: boolean;
  /** Estimate Γ via output compression ratio (not yet implemented — reserved) */
  estimateCognitiveSplit?: boolean;
}

export interface BridgeConfig {
  agentId: AgentId;
  sink: PACRSink;
  causalityStrategy: CausalityStrategy;
  enrichment?: EnrichmentConfig;
}

/** Simplified config for wrapWithPACR — sink and strategy are optional */
export interface WrapConfig {
  agentId: AgentId;
  sink?: PACRSink;
  causalityStrategy?: CausalityStrategy;
  enrichment?: EnrichmentConfig;
}

// External client shapes the bridges wrap
export interface MCPClientLike {
  callTool(name: string, args: unknown): Promise<unknown>;
}

export interface A2AClientLike {
  sendTask(task: { id: string; [key: string]: unknown }): Promise<unknown>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal constants
// ─────────────────────────────────────────────────────────────────────────────

const MAX_IGNORANCE = { estimate: 0, lower: 0, upper: Infinity } as const;
const NO_OP_SINK: PACRSink = { emit: () => Promise.resolve() };

function resolveConfig(c: WrapConfig): BridgeConfig {
  return {
    agentId: c.agentId,
    sink: c.sink ?? NO_OP_SINK,
    causalityStrategy: c.causalityStrategy ?? { type: 'none' },
    ...(c.enrichment !== undefined ? { enrichment: c.enrichment } : {}),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Sequential state tracker (one per wrapped instance)
// ─────────────────────────────────────────────────────────────────────────────

interface SequentialState {
  lastEventId: EventId | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Causality helpers
// ─────────────────────────────────────────────────────────────────────────────

function buildPredecessors(
  strategy: CausalityStrategy,
  state: SequentialState,
  headerValue?: string | null,
): ReadonlySet<EventId> {
  const preds = new Set<EventId>();

  switch (strategy.type) {
    case 'none':
      break;

    case 'sequential':
      if (state.lastEventId !== null) {
        preds.add(state.lastEventId);
      }
      break;

    case 'context_var': {
      for (const id of strategy.getContext()) {
        preds.add(id);
      }
      break;
    }

    case 'http_header': {
      if (headerValue !== null && headerValue !== undefined) {
        // May be comma-separated list of EventIds
        for (const raw of headerValue.split(',')) {
          const trimmed = raw.trim();
          if (validateEventId(trimmed)) {
            // Bridge boundary: safe after validation
            preds.add(trimmed as EventId);
          }
        }
      }
      break;
    }
  }

  return preds;
}

/** Extract a named header from any HeadersInit-compatible value */
function extractHeader(
  headers: Headers | string[][] | Record<string, string> | undefined | null,
  name: string,
): string | null {
  if (headers === undefined || headers === null) return null;
  const lower = name.toLowerCase();

  if (headers instanceof Headers) {
    return headers.get(lower);
  }

  if (Array.isArray(headers)) {
    for (const pair of headers) {
      const key = pair[0];
      const val = pair[1];
      if (key !== undefined && val !== undefined && key.toLowerCase() === lower) {
        return val;
      }
    }
    return null;
  }

  // Record<string, string>
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === lower) return v;
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Payload hashing (SHA-256 of body; stores fingerprint, not plaintext)
// ─────────────────────────────────────────────────────────────────────────────

function sha256Bytes(data: string | Uint8Array): Uint8Array {
  const hash = createHash('sha256');
  hash.update(data instanceof Uint8Array ? data : Buffer.from(data, 'utf-8'));
  return new Uint8Array(hash.digest());
}

// BodyInit is a DOM type; define a local subset covering string and binary bodies
type RequestBody = string | Uint8Array | ArrayBuffer | null | undefined;

function hashBody(body: RequestBody): Uint8Array {
  if (body === null || body === undefined) return new Uint8Array(0);
  if (typeof body === 'string') return sha256Bytes(body);
  if (body instanceof Uint8Array) return sha256Bytes(body);
  if (body instanceof ArrayBuffer) return sha256Bytes(new Uint8Array(body));
  return new Uint8Array(0);
}

function estimateBodySize(body: RequestBody): number {
  if (body === null || body === undefined) return 0;
  if (typeof body === 'string') return Buffer.byteLength(body, 'utf-8');
  if (body instanceof Uint8Array) return body.byteLength;
  if (body instanceof ArrayBuffer) return body.byteLength;
  return 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// Core PACR-Lite record builder
// ─────────────────────────────────────────────────────────────────────────────

const COMMENSURATION = createCommensuationLayer();

function buildRecord(opts: {
  identity: EventIdStructure;
  predecessors: ReadonlySet<EventId>;
  durationMs: number;
  requestBytes: number;
  responseBytes: number;
  payload: Uint8Array;
}): PACRecord {
  const time = COMMENSURATION.latencyMsToTime(opts.durationMs);
  const totalBytes = opts.requestBytes + opts.responseBytes;
  const space = { estimate: totalBytes, lower: 0, upper: totalBytes > 0 ? totalBytes * 2 : 1 };

  return {
    identity: opts.identity,
    predecessors: opts.predecessors,
    landauerCost: MAX_IGNORANCE,
    resources: {
      energy: MAX_IGNORANCE,
      time,
      space,
    },
    cognitiveSplit: {
      statisticalComplexity: MAX_IGNORANCE,
      entropyRate: MAX_IGNORANCE,
    },
    payload: opts.payload,
  };
}

/** Fire-and-forget emit. Errors are swallowed to protect the caller. */
function fireAndForget(sink: PACRSink, record: PACRecord): void {
  sink.emit(record).catch(() => {
    // Intentionally silent: PACR tracing must never break the main request
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Bridge A: fetch / HTTP
// ─────────────────────────────────────────────────────────────────────────────

type FetchFn = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

export function wrapFetch(fetchFn: FetchFn, config: BridgeConfig): FetchFn {
  const state: SequentialState = { lastEventId: null };

  return async function wrappedFetch(
    input: string | URL | Request,
    init?: RequestInit,
  ): Promise<Response> {
    // Extract header for http_header strategy before the call
    let headerValue: string | null = null;
    if (config.causalityStrategy.type === 'http_header') {
      const headers = init?.headers as Headers | string[][] | Record<string, string> | undefined;
      headerValue = extractHeader(headers, config.causalityStrategy.headerName);
    }

    const predecessors = buildPredecessors(config.causalityStrategy, state, headerValue);
    const requestBytes = estimateBodySize(init?.body as RequestBody);
    const requestPayload = hashBody(init?.body as RequestBody);

    const t0 = performance.now();
    const response = await fetchFn(input, init);
    const durationMs = performance.now() - t0;

    // Response size from Content-Length (non-destructive — body stream untouched)
    const contentLength = response.headers.get('content-length');
    const responseBytes = contentLength !== null ? (parseInt(contentLength, 10) || 0) : 0;

    const identity = createEventId(config.agentId);

    // Update sequential state before emit (synchronous, deterministic)
    if (config.causalityStrategy.type === 'sequential') {
      state.lastEventId = identity.id;
    }

    const record = buildRecord({
      identity,
      predecessors,
      durationMs,
      requestBytes,
      responseBytes,
      payload: requestPayload,
    });

    fireAndForget(config.sink, record);

    return response;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Bridge B: MCP Tool Call
// ─────────────────────────────────────────────────────────────────────────────

export function wrapMCPClient(client: MCPClientLike, config: BridgeConfig): MCPClientLike {
  const state: SequentialState = { lastEventId: null };

  return {
    async callTool(name: string, args: unknown): Promise<unknown> {
      const predecessors = buildPredecessors(config.causalityStrategy, state, null);

      // Encode args as payload fingerprint
      let argsBytes: Uint8Array;
      try {
        argsBytes = sha256Bytes(JSON.stringify(args));
      } catch {
        argsBytes = new Uint8Array(0);
      }

      const t0 = performance.now();
      const result = await client.callTool(name, args);
      const durationMs = performance.now() - t0;

      // ι.capabilityRef = MCP tool name (bridge boundary: trust tool name as capability)
      const identity = createEventId(
        config.agentId,
        name as CapabilityRef,
      );

      if (config.causalityStrategy.type === 'sequential') {
        state.lastEventId = identity.id;
      }

      const resultSize = (() => {
        try {
          return Buffer.byteLength(JSON.stringify(result), 'utf-8');
        } catch {
          return 0;
        }
      })();

      const record = buildRecord({
        identity,
        predecessors,
        durationMs,
        requestBytes: argsBytes.length,
        responseBytes: resultSize,
        payload: argsBytes,
      });

      fireAndForget(config.sink, record);

      return result;
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Bridge C: A2A Task
// ─────────────────────────────────────────────────────────────────────────────

export function wrapA2AClient(client: A2AClientLike, config: BridgeConfig): A2AClientLike {
  const state: SequentialState = { lastEventId: null };

  return {
    async sendTask(task: { id: string; [key: string]: unknown }): Promise<unknown> {
      const predecessors = buildPredecessors(config.causalityStrategy, state, null);

      // Π: also derive predecessor from A2A parent_task_id if it is a valid EventId
      const parentId = task['parent_task_id'];
      if (typeof parentId === 'string' && validateEventId(parentId)) {
        // Bridge boundary: safe after validation
        (predecessors as Set<EventId>).add(parentId as EventId);
      }

      const taskBytes = sha256Bytes(task.id);

      const t0 = performance.now();
      const result = await client.sendTask(task);
      const durationMs = performance.now() - t0;

      const identity = createEventId(config.agentId, 'a2a.task' as CapabilityRef);

      if (config.causalityStrategy.type === 'sequential') {
        state.lastEventId = identity.id;
      }

      const resultSize = (() => {
        try {
          return Buffer.byteLength(JSON.stringify(result), 'utf-8');
        } catch {
          return 0;
        }
      })();

      const record = buildRecord({
        identity,
        predecessors,
        durationMs,
        requestBytes: task.id.length,
        responseBytes: resultSize,
        payload: taskBytes,
      });

      fireAndForget(config.sink, record);

      return result;
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// wrapWithPACR — one-liner entry point
// ─────────────────────────────────────────────────────────────────────────────

export function wrapWithPACR(fn: FetchFn, config: WrapConfig): FetchFn;
export function wrapWithPACR(client: MCPClientLike, config: WrapConfig): MCPClientLike;
export function wrapWithPACR(client: A2AClientLike, config: WrapConfig): A2AClientLike;
export function wrapWithPACR(
  target: FetchFn | MCPClientLike | A2AClientLike,
  config: WrapConfig,
): FetchFn | MCPClientLike | A2AClientLike {
  const full = resolveConfig(config);

  if (typeof target === 'function') {
    return wrapFetch(target as FetchFn, full);
  }

  if ('callTool' in target && typeof (target as MCPClientLike).callTool === 'function') {
    return wrapMCPClient(target as MCPClientLike, full);
  }

  return wrapA2AClient(target as A2AClientLike, full);
}
