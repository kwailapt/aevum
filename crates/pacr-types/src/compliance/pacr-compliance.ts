// src/compliance/pacr-compliance.ts
// PACR Compliance Test Suite — black-box tests for external implementers.
// Depends ONLY on src/types/ (no internal core/ imports).

import type { EventId } from '../types/identity.js';
import { isEventId, extractOrigin } from '../types/identity.js';
import type { PACRecord, ConfidenceInterval } from '../types/pacr.js';
import { isPACRLite } from '../types/pacr.js';
import type { AgentCard } from '../types/agent-card.js';
import { REDUCED_PLANCK_CONSTANT } from '../types/commensuration.js';

// ─────────────────────────────────────────────
// Compliance target interface (implemented by SUT)
// ─────────────────────────────────────────────

/**
 * Adapter interface that the system under test must implement.
 * The compliance suite calls these methods and verifies the results.
 */
export interface PACRComplianceTarget {
  /** Trigger a computation event, return the resulting PACR record */
  triggerEvent(input: Uint8Array): Promise<PACRecord>;
  /** Return the system's AgentCard */
  getAgentCard(): Promise<AgentCard>;
  /** Retrieve a persisted PACR record by event ID */
  retrieveRecord(eventId: EventId): Promise<PACRecord | null>;
}

// ─────────────────────────────────────────────
// Report types
// ─────────────────────────────────────────────

export type TestVerdict = 'PASS' | 'FAIL' | 'WARN' | 'SKIP';

export interface TestCaseResult {
  readonly id: string;
  readonly name: string;
  readonly verdict: TestVerdict;
  readonly details: string;
  readonly durationMs: number;
}

export interface ComplianceReport {
  readonly timestamp: string;
  readonly targetAgentId: string;
  readonly results: readonly TestCaseResult[];
  readonly summary: {
    readonly total: number;
    readonly pass: number;
    readonly fail: number;
    readonly warn: number;
    readonly skip: number;
  };
}

// ─────────────────────────────────────────────
// Test runner
// ─────────────────────────────────────────────

/**
 * Run the full PACR compliance suite against a target implementation.
 * Returns a structured JSON-serializable report.
 */
export async function runComplianceSuite(
  target: PACRComplianceTarget,
): Promise<ComplianceReport> {
  const results: TestCaseResult[] = [];

  const testCases: Array<{
    id: string;
    name: string;
    run: (t: PACRComplianceTarget) => Promise<{ verdict: TestVerdict; details: string }>;
  }> = [
    { id: 'TC-001', name: 'Identity consistency', run: tc001 },
    { id: 'TC-002', name: 'Six-dimension completeness', run: tc002 },
    { id: 'TC-003', name: 'Causal chain correctness', run: tc003 },
    { id: 'TC-004', name: 'Persistence consistency', run: tc004 },
    { id: 'TC-005', name: 'PACR-Lite legality', run: tc005 },
    { id: 'TC-006', name: 'Payload opacity', run: tc006 },
    { id: 'TC-007', name: 'Resource constraint physical consistency (bonus)', run: tc007 },
  ];

  let agentId = 'unknown';
  try {
    const card = await target.getAgentCard();
    agentId = card.agentId as string;
  } catch { /* report will show unknown */ }

  for (const tc of testCases) {
    const start = performance.now();
    let result: { verdict: TestVerdict; details: string };
    try {
      result = await tc.run(target);
    } catch (err) {
      result = { verdict: 'FAIL', details: `Unhandled error: ${String(err)}` };
    }
    const durationMs = Math.round((performance.now() - start) * 100) / 100;
    results.push({ id: tc.id, name: tc.name, verdict: result.verdict, details: result.details, durationMs });
  }

  const summary = {
    total: results.length,
    pass: results.filter((r) => r.verdict === 'PASS').length,
    fail: results.filter((r) => r.verdict === 'FAIL').length,
    warn: results.filter((r) => r.verdict === 'WARN').length,
    skip: results.filter((r) => r.verdict === 'SKIP').length,
  };

  return {
    timestamp: new Date().toISOString(),
    targetAgentId: agentId,
    results,
    summary,
  };
}

// ─────────────────────────────────────────────
// TC-001: Identity consistency
// ─────────────────────────────────────────────

async function tc001(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const card = await t.getAgentCard();
  const record = await t.triggerEvent(new Uint8Array([0x01]));
  const checks: string[] = [];
  let pass = true;

  // record.identity.origin === card.agentId
  if (record.identity.origin !== card.agentId) {
    checks.push(`FAIL: origin (${record.identity.origin as string}) !== agentId (${card.agentId as string})`);
    pass = false;
  } else {
    checks.push('OK: origin === agentId');
  }

  // isEventId(record.identity.id)
  if (!isEventId(record.identity.id)) {
    checks.push(`FAIL: isEventId returned false for ${record.identity.id as string}`);
    pass = false;
  } else {
    checks.push('OK: isEventId(id) === true');
  }

  // extractOrigin(id) === agentId
  const extracted = extractOrigin(record.identity.id);
  if (extracted !== card.agentId) {
    checks.push(`FAIL: extractOrigin (${extracted as string}) !== agentId (${card.agentId as string})`);
    pass = false;
  } else {
    checks.push('OK: extractOrigin(id) === agentId');
  }

  return { verdict: pass ? 'PASS' : 'FAIL', details: checks.join('; ') };
}

// ─────────────────────────────────────────────
// TC-002: Six-dimension completeness
// ─────────────────────────────────────────────

async function tc002(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const record = await t.triggerEvent(new Uint8Array([0x02]));
  const checks: string[] = [];
  let pass = true;

  // Dimension 1: identity
  if (!record.identity || !record.identity.id || !record.identity.origin || typeof record.identity.timestampMs !== 'number') {
    checks.push('FAIL: identity (ι) incomplete');
    pass = false;
  } else {
    checks.push('OK: ι present');
  }

  // Dimension 2: predecessors
  if (!record.predecessors || typeof record.predecessors[Symbol.iterator] !== 'function') {
    checks.push('FAIL: predecessors (Π) missing or not iterable');
    pass = false;
  } else {
    checks.push('OK: Π present');
  }

  // Dimension 3: landauerCost
  const lcCheck = validateCI(record.landauerCost, 'Λ');
  checks.push(lcCheck.msg);
  if (!lcCheck.ok) pass = false;

  // Dimension 4: resources (Ω triple)
  for (const dim of ['energy', 'time', 'space'] as const) {
    const rCheck = validateCI(record.resources[dim], `Ω.${dim}`);
    checks.push(rCheck.msg);
    if (!rCheck.ok) pass = false;
  }

  // Dimension 5: cognitiveSplit
  const stCheck = validateCI(record.cognitiveSplit.statisticalComplexity, 'Γ.S_T');
  checks.push(stCheck.msg);
  if (!stCheck.ok) pass = false;
  const htCheck = validateCI(record.cognitiveSplit.entropyRate, 'Γ.H_T');
  checks.push(htCheck.msg);
  if (!htCheck.ok) pass = false;

  // Dimension 6: payload
  if (!(record.payload instanceof Uint8Array)) {
    checks.push('FAIL: payload (P) is not Uint8Array');
    pass = false;
  } else {
    checks.push('OK: P present (Uint8Array)');
  }

  return { verdict: pass ? 'PASS' : 'FAIL', details: checks.join('; ') };
}

// ─────────────────────────────────────────────
// TC-003: Causal chain correctness
// ─────────────────────────────────────────────

async function tc003(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const input1 = new Uint8Array([0x03, 0x01]);
  const record1 = await t.triggerEvent(input1);

  // Second event causally depends on first
  const input2 = new Uint8Array([0x03, 0x02]);
  const record2 = await t.triggerEvent(input2);

  // Check if record1.identity.id ∈ record2.predecessors
  const hasCausalLink = record2.predecessors.has(record1.identity.id);

  if (hasCausalLink) {
    return { verdict: 'PASS', details: 'record1.id ∈ record2.predecessors — causal link present' };
  }

  // If the implementation doesn't guarantee sequential causality, this is still valid
  // (events could be independent). Check that predecessors are at least valid EventIds.
  let allValid = true;
  for (const predId of record2.predecessors) {
    if (!isEventId(predId)) {
      allValid = false;
      break;
    }
  }

  if (record2.predecessors.size === 0) {
    return {
      verdict: 'PASS',
      details: 'record2 has no predecessors (independent event — valid if implementation does not auto-chain)',
    };
  }

  return {
    verdict: allValid ? 'PASS' : 'FAIL',
    details: allValid
      ? `record2 has ${record2.predecessors.size} predecessor(s), all valid EventIds (no auto-chain to record1)`
      : 'FAIL: some predecessors are not valid EventIds',
  };
}

// ─────────────────────────────────────────────
// TC-004: Persistence consistency
// ─────────────────────────────────────────────

async function tc004(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const record = await t.triggerEvent(new Uint8Array([0x04]));
  const retrieved = await t.retrieveRecord(record.identity.id);

  if (retrieved === null) {
    return { verdict: 'FAIL', details: 'retrieveRecord returned null — record not persisted' };
  }

  const checks: string[] = [];
  let pass = true;

  // Identity
  if (retrieved.identity.id !== record.identity.id) {
    checks.push('FAIL: identity.id mismatch');
    pass = false;
  }
  if (retrieved.identity.origin !== record.identity.origin) {
    checks.push('FAIL: identity.origin mismatch');
    pass = false;
  }
  if (retrieved.identity.timestampMs !== record.identity.timestampMs) {
    checks.push('FAIL: timestampMs mismatch');
    pass = false;
  }

  // Predecessors
  const origPreds = [...record.predecessors].sort();
  const retPreds = [...retrieved.predecessors].sort();
  if (JSON.stringify(origPreds) !== JSON.stringify(retPreds)) {
    checks.push('FAIL: predecessors mismatch');
    pass = false;
  }

  // CI fields
  for (const [path, origCI, retCI] of ciPairs(record, retrieved)) {
    if (origCI.estimate !== retCI.estimate || origCI.lower !== retCI.lower || origCI.upper !== retCI.upper) {
      checks.push(`FAIL: ${path} CI mismatch`);
      pass = false;
    }
  }

  // Payload
  if (!uint8Equal(record.payload, retrieved.payload)) {
    checks.push('FAIL: payload mismatch');
    pass = false;
  }

  if (pass) {
    checks.push('OK: retrieved record deeply equals original');
  }

  return { verdict: pass ? 'PASS' : 'FAIL', details: checks.join('; ') };
}

// ─────────────────────────────────────────────
// TC-005: PACR-Lite legality
// ─────────────────────────────────────────────

async function tc005(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const record = await t.triggerEvent(new Uint8Array([0x05]));

  if (!isPACRLite(record)) {
    return {
      verdict: 'PASS',
      details: 'Record is full PACR (not Lite) — Λ and Γ have non-trivial CIs',
    };
  }

  // If it IS PACR-Lite, verify the structure is still complete
  const checks: string[] = [];
  let pass = true;

  // Λ must be [0, 0, Infinity]
  if (record.landauerCost.lower !== 0 || record.landauerCost.upper !== Infinity) {
    checks.push('FAIL: PACR-Lite Λ bounds incorrect');
    pass = false;
  } else {
    checks.push('OK: Λ = max ignorance');
  }

  // Γ.S_T and Γ.H_T must be [0, 0, Infinity]
  const st = record.cognitiveSplit.statisticalComplexity;
  const ht = record.cognitiveSplit.entropyRate;
  if (st.lower !== 0 || st.upper !== Infinity || ht.lower !== 0 || ht.upper !== Infinity) {
    checks.push('FAIL: PACR-Lite Γ bounds incorrect');
    pass = false;
  } else {
    checks.push('OK: Γ = max ignorance');
  }

  // ι, Π, Ω, P must still be complete
  if (!record.identity.id || !record.identity.origin) {
    checks.push('FAIL: ι incomplete in PACR-Lite');
    pass = false;
  } else {
    checks.push('OK: ι complete');
  }

  if (typeof record.predecessors[Symbol.iterator] !== 'function') {
    checks.push('FAIL: Π missing in PACR-Lite');
    pass = false;
  } else {
    checks.push('OK: Π present');
  }

  if (!record.resources.energy || !record.resources.time || !record.resources.space) {
    checks.push('FAIL: Ω incomplete in PACR-Lite');
    pass = false;
  } else {
    checks.push('OK: Ω complete');
  }

  if (!(record.payload instanceof Uint8Array)) {
    checks.push('FAIL: P not Uint8Array in PACR-Lite');
    pass = false;
  } else {
    checks.push('OK: P present');
  }

  return { verdict: pass ? 'PASS' : 'FAIL', details: checks.join('; ') };
}

// ─────────────────────────────────────────────
// TC-006: Payload opacity
// ─────────────────────────────────────────────

async function tc006(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  // Send random input
  const input = new Uint8Array(64);
  for (let i = 0; i < 64; i++) {
    input[i] = Math.floor(Math.random() * 256);
  }

  const record = await t.triggerEvent(input);

  if (!(record.payload instanceof Uint8Array)) {
    return { verdict: 'FAIL', details: 'payload is not Uint8Array' };
  }

  if (record.payload.length === 0) {
    return {
      verdict: 'PASS',
      details: 'payload is empty Uint8Array (implementation chose not to echo input — valid)',
    };
  }

  return {
    verdict: 'PASS',
    details: `payload present: ${record.payload.length} bytes (Uint8Array)`,
  };
}

// ─────────────────────────────────────────────
// TC-007: Resource constraint physical consistency (bonus)
// ─────────────────────────────────────────────

async function tc007(t: PACRComplianceTarget): Promise<{ verdict: TestVerdict; details: string }> {
  const record = await t.triggerEvent(new Uint8Array([0x07]));

  const E = record.resources.energy.estimate;
  const T = record.resources.time.estimate;

  // Skip if estimates are zero or Infinity (PACR-Lite mode for Ω)
  if (E === 0 || T === 0 || !isFinite(E) || !isFinite(T)) {
    return { verdict: 'SKIP', details: 'Ω estimates are zero or non-finite — cannot check physical bounds' };
  }

  // Margolus-Levitin: T >= πħ / (2E)
  const mlBound = (Math.PI * REDUCED_PLANCK_CONSTANT) / (2 * E);

  if (T >= mlBound) {
    return {
      verdict: 'PASS',
      details: `Margolus-Levitin satisfied: T=${T}s >= πħ/(2E)=${mlBound.toExponential(4)}s`,
    };
  }

  return {
    verdict: 'WARN',
    details: `Margolus-Levitin violated: T=${T}s < πħ/(2E)=${mlBound.toExponential(4)}s`
      + ' — may be measurement error',
  };
}

// ─────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────

function validateCI(ci: ConfidenceInterval, label: string): { ok: boolean; msg: string } {
  if (ci === undefined || ci === null) {
    return { ok: false, msg: `FAIL: ${label} missing` };
  }
  if (typeof ci.estimate !== 'number' || typeof ci.lower !== 'number' || typeof ci.upper !== 'number') {
    return { ok: false, msg: `FAIL: ${label} has non-number fields` };
  }
  if (ci.lower > ci.estimate || ci.estimate > ci.upper) {
    // Allow NaN/Infinity edge cases
    if (!isFinite(ci.upper) && ci.lower <= ci.estimate) {
      return { ok: true, msg: `OK: ${label} (upper=Infinity)` };
    }
    return { ok: false, msg: `FAIL: ${label} violates lower(${ci.lower}) <= estimate(${ci.estimate}) <= upper(${ci.upper})` };
  }
  return { ok: true, msg: `OK: ${label}` };
}

function uint8Equal(a: Readonly<Uint8Array>, b: Readonly<Uint8Array>): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

/** Extract all CI pairs from two records for comparison */
function* ciPairs(
  a: PACRecord,
  b: PACRecord,
): Generator<[string, ConfidenceInterval, ConfidenceInterval]> {
  yield ['landauerCost', a.landauerCost, b.landauerCost];
  yield ['resources.energy', a.resources.energy, b.resources.energy];
  yield ['resources.time', a.resources.time, b.resources.time];
  yield ['resources.space', a.resources.space, b.resources.space];
  yield ['cognitiveSplit.statisticalComplexity', a.cognitiveSplit.statisticalComplexity, b.cognitiveSplit.statisticalComplexity];
  yield ['cognitiveSplit.entropyRate', a.cognitiveSplit.entropyRate, b.cognitiveSplit.entropyRate];
}
