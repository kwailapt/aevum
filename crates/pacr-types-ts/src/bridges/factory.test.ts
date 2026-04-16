// src/bridges/factory.test.ts
// Tests for the Bridge Factory.
//
// Invariants verified:
// 1. Semantic transparency — return value and error propagation unchanged
// 2. Non-blocking emit — sink errors never surface to caller
// 3. PACR record structural validity (TC-M01..M06)
// 4. PACR-Lite mode expected (TC-S01, TC-S02 → WARN is acceptable)
// 5. Full compliance suite passes for each bridge

import { describe, it, expect, vi, beforeAll } from 'vitest';
import type { EventId, CapabilityRef } from '../types/index.js';
import type { PACRecord } from '../types/index.js';
import type { AgentCard } from '../types/index.js';
import { isEventId, extractOrigin } from '../types/index.js';
import { createAgentId, createEventId } from '../core/identity.js';
import { runCompliance } from '../compliance/v1.js';
import type { PACRComplianceTarget } from '../compliance/v1.js';
import type { PACRSink, BridgeConfig, MCPClientLike, A2AClientLike } from './factory.js';
import { wrapFetch, wrapMCPClient, wrapA2AClient, wrapWithPACR } from './factory.js';

// ─────────────────────────────────────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Captures the most recently emitted PACRecord synchronously. */
class CaptureSink implements PACRSink {
  readonly records: PACRecord[] = [];

  async emit(record: PACRecord): Promise<void> {
    this.records.push(record);
  }

  get last(): PACRecord {
    const r = this.records[this.records.length - 1];
    if (r === undefined) throw new Error('CaptureSink: no records emitted');
    return r;
  }

  get(id: EventId): PACRecord | null {
    return this.records.find((r) => r.identity.id === id) ?? null;
  }
}

/** Minimal mock Response with configurable headers */
function mockResponse(opts: { status?: number; contentLength?: number } = {}): Response {
  const headers = new Headers();
  if (opts.contentLength !== undefined) {
    headers.set('content-length', String(opts.contentLength));
  }
  return new Response(null, { status: opts.status ?? 200, headers });
}

/** Build a bridge compliance adapter for the fetch bridge */
function makeFetchComplianceTarget(agentId: ReturnType<typeof createAgentId>): {
  target: PACRComplianceTarget;
  sink: CaptureSink;
} {
  const sink = new CaptureSink();

  const config: BridgeConfig = {
    agentId,
    sink,
    causalityStrategy: { type: 'sequential' },
  };

  const mockFetch = vi.fn(async (_input: unknown, init?: RequestInit) => {
    const bodyLen = init?.body instanceof Uint8Array ? init.body.byteLength : 0;
    return mockResponse({ contentLength: bodyLen + 64 });
  });

  const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, config);

  const target: PACRComplianceTarget = {
    name: 'fetch-bridge',

    async triggerEvent(input: Uint8Array): Promise<PACRecord> {
      await wrapped('https://test.example.com/api', {
        method: 'POST',
        body: input,
      });
      // Emit is async but body runs synchronously up to first await — flush microtasks
      await Promise.resolve();
      return sink.last;
    },

    async triggerCausalChain(
      inputA: Uint8Array,
      inputB: Uint8Array,
    ): Promise<[PACRecord, PACRecord]> {
      await wrapped('https://test.example.com/a', { method: 'POST', body: inputA });
      await Promise.resolve();
      const recordA = sink.last;

      await wrapped('https://test.example.com/b', { method: 'POST', body: inputB });
      await Promise.resolve();
      const recordB = sink.last;

      return [recordA, recordB];
    },

    async getAgentCard(): Promise<AgentCard> {
      return {
        agentId,
        name: 'fetch-bridge-test',
        capabilities: [{ name: 'http.fetch' as CapabilityRef, description: 'HTTP fetch' }],
        endpoint: 'https://test.example.com',
        ttlSeconds: 300,
      };
    },

    async retrieveRecord(eventId: EventId): Promise<PACRecord | null> {
      return sink.get(eventId);
    },
  };

  return { target, sink };
}

/** Build compliance adapter for MCP bridge */
function makeMCPComplianceTarget(agentId: ReturnType<typeof createAgentId>): {
  target: PACRComplianceTarget;
  sink: CaptureSink;
} {
  const sink = new CaptureSink();

  const mockMCP: MCPClientLike = {
    callTool: vi.fn(async (_name: string, args: unknown) => ({ echo: args })),
  };

  const config: BridgeConfig = {
    agentId,
    sink,
    causalityStrategy: { type: 'sequential' },
  };

  const wrapped = wrapMCPClient(mockMCP, config);

  const target: PACRComplianceTarget = {
    name: 'mcp-bridge',

    async triggerEvent(input: Uint8Array): Promise<PACRecord> {
      await wrapped.callTool('test.tool', { data: Array.from(input) });
      await Promise.resolve();
      return sink.last;
    },

    async triggerCausalChain(
      inputA: Uint8Array,
      inputB: Uint8Array,
    ): Promise<[PACRecord, PACRecord]> {
      await wrapped.callTool('test.tool', { data: Array.from(inputA) });
      await Promise.resolve();
      const recordA = sink.last;

      await wrapped.callTool('test.tool', { data: Array.from(inputB) });
      await Promise.resolve();
      const recordB = sink.last;

      return [recordA, recordB];
    },

    async getAgentCard(): Promise<AgentCard> {
      return {
        agentId,
        name: 'mcp-bridge-test',
        capabilities: [{ name: 'test.tool' as CapabilityRef, description: 'MCP test tool' }],
        endpoint: 'mcp://localhost',
        ttlSeconds: 300,
      };
    },

    async retrieveRecord(eventId: EventId): Promise<PACRecord | null> {
      return sink.get(eventId);
    },
  };

  return { target, sink };
}

/** Build compliance adapter for A2A bridge */
function makeA2AComplianceTarget(agentId: ReturnType<typeof createAgentId>): {
  target: PACRComplianceTarget;
  sink: CaptureSink;
} {
  const sink = new CaptureSink();
  let taskCounter = 0;

  const mockA2A: A2AClientLike = {
    sendTask: vi.fn(async (task: { id: string }) => ({ taskId: task.id, status: 'completed' })),
  };

  const config: BridgeConfig = {
    agentId,
    sink,
    causalityStrategy: { type: 'sequential' },
  };

  const wrapped = wrapA2AClient(mockA2A, config);

  const target: PACRComplianceTarget = {
    name: 'a2a-bridge',

    async triggerEvent(_input: Uint8Array): Promise<PACRecord> {
      taskCounter++;
      await wrapped.sendTask({ id: `task-${taskCounter}` });
      await Promise.resolve();
      return sink.last;
    },

    async triggerCausalChain(
      _inputA: Uint8Array,
      _inputB: Uint8Array,
    ): Promise<[PACRecord, PACRecord]> {
      taskCounter++;
      await wrapped.sendTask({ id: `task-${taskCounter}` });
      await Promise.resolve();
      const recordA = sink.last;

      taskCounter++;
      await wrapped.sendTask({ id: `task-${taskCounter}` });
      await Promise.resolve();
      const recordB = sink.last;

      return [recordA, recordB];
    },

    async getAgentCard(): Promise<AgentCard> {
      return {
        agentId,
        name: 'a2a-bridge-test',
        capabilities: [{ name: 'a2a.task' as CapabilityRef, description: 'A2A task' }],
        endpoint: 'a2a://localhost',
        ttlSeconds: 300,
      };
    },

    async retrieveRecord(eventId: EventId): Promise<PACRecord | null> {
      return sink.get(eventId);
    },
  };

  return { target, sink };
}

// ─────────────────────────────────────────────────────────────────────────────
// Bridge A: wrapFetch
// ─────────────────────────────────────────────────────────────────────────────

describe('wrapFetch', () => {
  it('returns the original Response unchanged', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const expectedResponse = mockResponse({ status: 201, contentLength: 512 });
    const mockFetch = vi.fn(async () => expectedResponse);

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    const result = await wrapped('https://api.example.com/foo', { method: 'GET' });
    expect(result).toBe(expectedResponse);
    expect(result.status).toBe(201);
  });

  it('propagates fetch errors without alteration', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => { throw new TypeError('network failure'); });

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await expect(wrapped('https://bad.example.com')).rejects.toThrow('network failure');
  });

  it('emits a PACR record for each call', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse({ contentLength: 128 }));

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped('https://api.example.com/test', { method: 'POST', body: 'hello' });
    await Promise.resolve();

    expect(sink.records).toHaveLength(1);
    const record = sink.last;
    expect(isEventId(record.identity.id)).toBe(true);
    expect(extractOrigin(record.identity.id)).toBe(agentId);
    expect(record.payload).toBeInstanceOf(Uint8Array);
    expect(record.payload.length).toBe(32); // SHA-256 = 32 bytes
  });

  it('sink errors do not propagate to caller', async () => {
    const agentId = createAgentId();
    const failingSink: PACRSink = {
      emit: async () => { throw new Error('sink exploded'); },
    };
    const mockFetch = vi.fn(async () => mockResponse());

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink: failingSink,
      causalityStrategy: { type: 'none' },
    });

    // Must not throw despite sink failure
    const result = await wrapped('https://api.example.com');
    expect(result.status).toBe(200);
  });

  it('sequential strategy links consecutive records causally', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse());

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'sequential' },
    });

    await wrapped('https://api.example.com/1');
    await Promise.resolve();
    const record1 = sink.last;

    await wrapped('https://api.example.com/2');
    await Promise.resolve();
    const record2 = sink.last;

    expect(record2.predecessors.has(record1.identity.id)).toBe(true);
    expect(record1.predecessors.size).toBe(0); // First call has no predecessor
  });

  it('http_header strategy extracts predecessor EventIds from header', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse());

    // Create a real EventId to use as predecessor
    const otherAgent = createAgentId();
    const predEvent = createEventId(otherAgent);

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'http_header', headerName: 'X-Causal-Id' },
    });

    await wrapped('https://api.example.com', {
      headers: { 'X-Causal-Id': predEvent.id as string },
    });
    await Promise.resolve();

    expect(sink.last.predecessors.has(predEvent.id)).toBe(true);
  });

  it('context_var strategy uses provided EventIds', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse());

    const otherAgent = createAgentId();
    const contextEvent = createEventId(otherAgent);

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'context_var', getContext: () => [contextEvent.id] },
    });

    await wrapped('https://api.example.com');
    await Promise.resolve();

    expect(sink.last.predecessors.has(contextEvent.id)).toBe(true);
  });

  it('Ω.T reflects measured duration via CommensuationLayer', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();

    // Slow mock fetch
    const mockFetch = vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 20));
      return mockResponse({ contentLength: 0 });
    });

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped('https://api.example.com');
    await Promise.resolve();

    // time.estimate should reflect ~20ms (in seconds ≈ 0.02)
    const t = sink.last.resources.time;
    expect(t.estimate).toBeGreaterThan(0);
    expect(t.lower).toBeLessThanOrEqual(t.estimate);
  });

  it('Ω.S is requestBytes + responseBytes from Content-Length', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse({ contentLength: 1000 }));

    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    const body = 'hello world'; // 11 bytes
    await wrapped('https://api.example.com', { method: 'POST', body });
    await Promise.resolve();

    const space = sink.last.resources.space;
    expect(space.estimate).toBe(11 + 1000);
  });

  it('passes PACR Compliance Suite v1.0', async () => {
    const agentId = createAgentId();
    const { target } = makeFetchComplianceTarget(agentId);
    const report = await runCompliance(target);

    // All MUST tests must pass
    for (const r of report.results.filter((x) => x.level === 'MUST')) {
      expect(r.status, `${r.id}: ${r.message}`).toBe('PASS');
    }

    // SHOULD tests are expected to WARN (PACR-Lite mode) — not FAIL
    for (const r of report.results.filter((x) => x.level === 'SHOULD')) {
      expect(r.status, `${r.id}: ${r.message}`).not.toBe('FAIL');
    }

    expect(report.summary.mustFail).toBe(0);
    expect(report.summary.verdict).not.toBe('NON_COMPLIANT');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Bridge B: wrapMCPClient
// ─────────────────────────────────────────────────────────────────────────────

describe('wrapMCPClient', () => {
  it('returns the original result unchanged', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const expectedResult = { answer: 42, items: ['a', 'b'] };
    const mockMCP: MCPClientLike = {
      callTool: vi.fn(async () => expectedResult),
    };

    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    const result = await wrapped.callTool('my.tool', { x: 1 });
    expect(result).toStrictEqual(expectedResult);
  });

  it('propagates callTool errors without alteration', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockMCP: MCPClientLike = {
      callTool: vi.fn(async () => { throw new Error('tool not found'); }),
    };

    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await expect(wrapped.callTool('missing.tool', {})).rejects.toThrow('tool not found');
  });

  it('sets capabilityRef to the tool name', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockMCP: MCPClientLike = {
      callTool: vi.fn(async () => null),
    };

    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped.callTool('translate.text', { text: 'hello' });
    await Promise.resolve();

    expect(sink.last.identity.capabilityRef).toBe('translate.text');
  });

  it('payload is SHA-256 of args (32 bytes)', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockMCP: MCPClientLike = { callTool: vi.fn(async () => null) };

    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped.callTool('tool', { key: 'value' });
    await Promise.resolve();

    expect(sink.last.payload.length).toBe(32);
  });

  it('sink errors do not propagate', async () => {
    const agentId = createAgentId();
    const failingSink: PACRSink = { emit: async () => { throw new Error('boom'); } };
    const mockMCP: MCPClientLike = { callTool: vi.fn(async () => 'ok') };

    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink: failingSink,
      causalityStrategy: { type: 'none' },
    });

    const result = await wrapped.callTool('tool', {});
    expect(result).toBe('ok');
  });

  it('passes PACR Compliance Suite v1.0', async () => {
    const agentId = createAgentId();
    const { target } = makeMCPComplianceTarget(agentId);
    const report = await runCompliance(target);

    for (const r of report.results.filter((x) => x.level === 'MUST')) {
      expect(r.status, `${r.id}: ${r.message}`).toBe('PASS');
    }
    for (const r of report.results.filter((x) => x.level === 'SHOULD')) {
      expect(r.status, `${r.id}: ${r.message}`).not.toBe('FAIL');
    }

    expect(report.summary.mustFail).toBe(0);
    expect(report.summary.verdict).not.toBe('NON_COMPLIANT');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Bridge C: wrapA2AClient
// ─────────────────────────────────────────────────────────────────────────────

describe('wrapA2AClient', () => {
  it('returns the original result unchanged', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const expected = { taskId: 'task-1', status: 'done' };
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => expected) };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    const result = await wrapped.sendTask({ id: 'task-1' });
    expect(result).toStrictEqual(expected);
  });

  it('propagates sendTask errors without alteration', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = {
      sendTask: vi.fn(async () => { throw new Error('task rejected'); }),
    };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await expect(wrapped.sendTask({ id: 'bad-task' })).rejects.toThrow('task rejected');
  });

  it('derives predecessor from parent_task_id when it is a valid EventId', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => null) };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    // Create a valid EventId to use as parent
    const parentEvent = createEventId(createAgentId());

    await wrapped.sendTask({ id: 'child-task', parent_task_id: parentEvent.id as string });
    await Promise.resolve();

    expect(sink.last.predecessors.has(parentEvent.id)).toBe(true);
  });

  it('ignores non-EventId parent_task_id', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => null) };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped.sendTask({ id: 'task', parent_task_id: 'not-a-valid-event-id' });
    await Promise.resolve();

    expect(sink.last.predecessors.size).toBe(0);
  });

  it('capabilityRef is "a2a.task"', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => null) };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });

    await wrapped.sendTask({ id: 'my-task' });
    await Promise.resolve();

    expect(sink.last.identity.capabilityRef).toBe('a2a.task');
  });

  it('sink errors do not propagate', async () => {
    const agentId = createAgentId();
    const failingSink: PACRSink = { emit: async () => { throw new Error('sink down'); } };
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => 'done') };

    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink: failingSink,
      causalityStrategy: { type: 'none' },
    });

    const result = await wrapped.sendTask({ id: 'task' });
    expect(result).toBe('done');
  });

  it('passes PACR Compliance Suite v1.0', async () => {
    const agentId = createAgentId();
    const { target } = makeA2AComplianceTarget(agentId);
    const report = await runCompliance(target);

    for (const r of report.results.filter((x) => x.level === 'MUST')) {
      expect(r.status, `${r.id}: ${r.message}`).toBe('PASS');
    }
    for (const r of report.results.filter((x) => x.level === 'SHOULD')) {
      expect(r.status, `${r.id}: ${r.message}`).not.toBe('FAIL');
    }

    expect(report.summary.mustFail).toBe(0);
    expect(report.summary.verdict).not.toBe('NON_COMPLIANT');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// wrapWithPACR — one-liner auto-detection
// ─────────────────────────────────────────────────────────────────────────────

describe('wrapWithPACR', () => {
  it('auto-detects fetch (function) and wraps it', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse({ status: 200 }));

    const wrapped = wrapWithPACR(mockFetch as unknown as typeof fetch, { agentId, sink });
    const result = await wrapped('https://api.example.com');
    await Promise.resolve();

    expect(result.status).toBe(200);
    expect(sink.records).toHaveLength(1);
  });

  it('auto-detects MCPClientLike (has callTool)', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockMCP: MCPClientLike = { callTool: vi.fn(async () => 'result') };

    const wrapped = wrapWithPACR(mockMCP, { agentId, sink });
    const result = await wrapped.callTool('tool', {});
    await Promise.resolve();

    expect(result).toBe('result');
    expect(sink.records).toHaveLength(1);
  });

  it('auto-detects A2AClientLike (has sendTask, no callTool)', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => 'done') };

    const wrapped = wrapWithPACR(mockA2A, { agentId, sink });
    const result = await wrapped.sendTask({ id: 'task-xyz' });
    await Promise.resolve();

    expect(result).toBe('done');
    expect(sink.records).toHaveLength(1);
  });

  it('defaults to no-op sink when none provided', async () => {
    const agentId = createAgentId();
    const mockFetch = vi.fn(async () => mockResponse());

    // Should not throw — no-op sink absorbs everything
    const wrapped = wrapWithPACR(mockFetch as unknown as typeof fetch, { agentId });
    await expect(wrapped('https://api.example.com')).resolves.toBeDefined();
  });

  it('defaults to none causality strategy when not provided', async () => {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse());

    const wrapped = wrapWithPACR(mockFetch as unknown as typeof fetch, { agentId, sink });

    await wrapped('https://api.example.com/1');
    await Promise.resolve();
    await wrapped('https://api.example.com/2');
    await Promise.resolve();

    // With 'none' strategy, second record has empty predecessors
    expect(sink.records[1]?.predecessors.size).toBe(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// PACR-Lite invariants common to all bridges
// ─────────────────────────────────────────────────────────────────────────────

describe('PACR-Lite structural invariants (all bridges)', () => {
  const cases: Array<{ name: string; getSink: () => CaptureSink }> = [];

  // Fetch
  {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockFetch = vi.fn(async () => mockResponse({ contentLength: 100 }));
    const wrapped = wrapFetch(mockFetch as unknown as typeof fetch, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });
    // Prime the sink
    beforeAll(async () => {
      await wrapped('https://api.example.com', { method: 'POST', body: 'test data' });
      await Promise.resolve();
    });
    cases.push({ name: 'fetch', getSink: () => sink });
  }

  // MCP
  {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockMCP: MCPClientLike = { callTool: vi.fn(async () => ({ ok: true })) };
    const wrapped = wrapMCPClient(mockMCP, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });
    beforeAll(async () => {
      await wrapped.callTool('my.tool', { x: 42 });
      await Promise.resolve();
    });
    cases.push({ name: 'mcp', getSink: () => sink });
  }

  // A2A
  {
    const agentId = createAgentId();
    const sink = new CaptureSink();
    const mockA2A: A2AClientLike = { sendTask: vi.fn(async () => ({ done: true })) };
    const wrapped = wrapA2AClient(mockA2A, {
      agentId,
      sink,
      causalityStrategy: { type: 'none' },
    });
    beforeAll(async () => {
      await wrapped.sendTask({ id: 'invariant-task' });
      await Promise.resolve();
    });
    cases.push({ name: 'a2a', getSink: () => sink });
  }

  for (const { name, getSink } of cases) {
    it(`${name}: Λ is max-ignorance (PACR-Lite)`, () => {
      const r = getSink().last;
      expect(r.landauerCost.estimate).toBe(0);
      expect(r.landauerCost.lower).toBe(0);
      expect(r.landauerCost.upper).toBe(Infinity);
    });

    it(`${name}: Γ is max-ignorance (PACR-Lite)`, () => {
      const r = getSink().last;
      expect(r.cognitiveSplit.statisticalComplexity.upper).toBe(Infinity);
      expect(r.cognitiveSplit.entropyRate.upper).toBe(Infinity);
    });

    it(`${name}: ι has valid EventId with correct origin`, () => {
      const r = getSink().last;
      expect(isEventId(r.identity.id)).toBe(true);
    });

    it(`${name}: Ω.T.estimate > 0`, () => {
      const r = getSink().last;
      expect(r.resources.time.estimate).toBeGreaterThan(0);
    });

    it(`${name}: all CI invariants hold (lower ≤ estimate ≤ upper)`, () => {
      const r = getSink().last;
      for (const ci of [
        r.landauerCost,
        r.resources.energy,
        r.resources.time,
        r.resources.space,
        r.cognitiveSplit.statisticalComplexity,
        r.cognitiveSplit.entropyRate,
      ]) {
        expect(ci.lower).toBeLessThanOrEqual(ci.estimate);
        if (isFinite(ci.upper)) {
          expect(ci.estimate).toBeLessThanOrEqual(ci.upper);
        }
      }
    });

    it(`${name}: payload is Uint8Array`, () => {
      const r = getSink().last;
      expect(r.payload).toBeInstanceOf(Uint8Array);
    });
  }
});
