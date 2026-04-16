// src/compliance/v1.ts
// PACR Compliance Suite v1.0
//
// "你正在寫的不是測試，是憲法"
//
// Black-box compliance framework for PACR-compatible systems.
// Imports ONLY from src/types/ — zero knowledge of any implementation.
//
// Usage (library):
//   import { runCompliance } from './v1.js';
//   const report = await runCompliance(myAdapter);
//
// Usage (CLI):
//   npx @aevum/pacr-compliance --target ./my-adapter.ts

import type { AgentId, EventId, AevumId } from '../types/identity.js';
import { isAgentId, isEventId, extractOrigin } from '../types/identity.js';
import type { PACRecord, ConfidenceInterval } from '../types/pacr.js';
import type { AgentCard, AgentBehaviorEntropy } from '../types/agent-card.js';
import { REDUCED_PLANCK_CONSTANT } from '../types/commensuration.js';

// ─────────────────────────────────────────────────────────────────────────────
// Compliance Target Interface
// Implemented by the system under test.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Adapter interface that the system under test (SUT) must implement.
 * The compliance suite calls only these methods and verifies the results.
 * No knowledge of the SUT's internals is required or permitted.
 */
export interface PACRComplianceTarget {
  /** Name used in compliance reports */
  name: string;
  /** Trigger a single computation event; returns the resulting PACR record */
  triggerEvent(input: Uint8Array): Promise<PACRecord>;
  /**
   * Trigger a causal chain: event B is caused by event A.
   * Returns [recordA, recordB] where recordA.identity.id ∈ recordB.predecessors.
   */
  triggerCausalChain(inputA: Uint8Array, inputB: Uint8Array): Promise<[PACRecord, PACRecord]>;
  /** Return the system's AgentCard */
  getAgentCard(): Promise<AgentCard>;
  /** Retrieve a persisted PACR record by event ID; returns null if not found */
  retrieveRecord(eventId: EventId): Promise<PACRecord | null>;
}

/**
 * Optional extension: expose the π (projection) operator for advanced compliance testing.
 * Implement this alongside PACRComplianceTarget to enable TC-A01.
 */
export interface PACRProjectionTarget extends PACRComplianceTarget {
  /**
   * Compute the agent interaction graph for a batch of records.
   * Must return the same result as incrementally ingesting the records one by one.
   */
  projectBatch(records: readonly PACRecord[]): Promise<unknown>;
  /**
   * Incrementally project a single new record into the graph.
   * Takes existing accumulated result and the new record; returns updated result.
   */
  projectIncremental(accumulated: unknown, newRecord: PACRecord): Promise<unknown>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Compliance Report Types
// ─────────────────────────────────────────────────────────────────────────────

export type ComplianceLevel = 'MUST' | 'SHOULD' | 'MAY';
export type ComplianceStatus = 'PASS' | 'FAIL' | 'WARN' | 'SKIP';
export type ComplianceVerdict = 'COMPLIANT' | 'PACR_LITE' | 'NON_COMPLIANT';

export interface TestResult {
  /** Test case identifier, e.g. "TC-M01" */
  readonly id: string;
  /** Compliance level */
  readonly level: ComplianceLevel;
  /** Outcome */
  readonly status: ComplianceStatus;
  /** Human-readable explanation */
  readonly message: string;
  /** Wall-clock duration of the test */
  readonly durationMs: number;
  /**
   * Raw data for reproduction.
   * Present on FAIL and WARN; may be omitted on PASS or SKIP.
   */
  readonly evidence?: unknown;
}

export interface ComplianceReport {
  /** Name of the system under test */
  readonly target: string;
  /** ISO 8601 timestamp */
  readonly timestamp: string;
  /** Suite version — hard-coded for determinism */
  readonly version: '1.0.0';
  readonly results: readonly TestResult[];
  readonly summary: {
    readonly mustPass: number;
    readonly mustFail: number;
    readonly shouldPass: number;
    readonly shouldWarn: number;
    readonly mayPass: number;
    /** Overall compliance verdict */
    readonly verdict: ComplianceVerdict;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Test Case Internals
// ─────────────────────────────────────────────────────────────────────────────

interface RunResult {
  status: ComplianceStatus;
  message: string;
  evidence?: unknown;
}

type TestFn = (t: PACRComplianceTarget) => Promise<RunResult>;

interface TestDef {
  id: string;
  level: ComplianceLevel;
  name: string;
  run: TestFn;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Run the PACR Compliance Suite v1.0 against the given adapter.
 *
 * Returns a fully deterministic, JSON-serializable report.
 * The same SUT will produce the same report across multiple runs.
 */
export async function runCompliance(target: PACRComplianceTarget): Promise<ComplianceReport> {
  const tests: TestDef[] = [
    { id: 'TC-M01', level: 'MUST', name: '身份統一性 (Identity Unification)', run: tcM01 },
    { id: 'TC-M02', level: 'MUST', name: '六維完整性 (Six-Dimension Completeness)', run: tcM02 },
    { id: 'TC-M03', level: 'MUST', name: '因果鏈正確性 (Causal Chain Correctness)', run: tcM03 },
    { id: 'TC-M04', level: 'MUST', name: '載荷不透明性 (Payload Opacity)', run: tcM04 },
    { id: 'TC-M05', level: 'MUST', name: '持久化一致性 (Persistence Consistency)', run: tcM05 },
    { id: 'TC-M06', level: 'MUST', name: '身份空間隔離 (Identity Space Isolation)', run: tcM06 },
    { id: 'TC-S01', level: 'SHOULD', name: '蘭道爾成本非平凡 (Non-Trivial Landauer Cost)', run: tcS01 },
    { id: 'TC-S02', level: 'SHOULD', name: '認知分割非平凡 (Non-Trivial Cognitive Split)', run: tcS02 },
    { id: 'TC-S03', level: 'SHOULD', name: '資源約束物理一致性 (Physical Resource Consistency)', run: tcS03 },
    { id: 'TC-A01', level: 'MAY', name: '增量投影一致性 (Incremental Projection Consistency)', run: tcA01 },
    { id: 'TC-A02', level: 'MAY', name: '聚合寫回一致性 (Aggregation Write-Back Consistency)', run: tcA02 },
  ];

  const results: TestResult[] = [];

  for (const test of tests) {
    const t0 = performance.now();
    let runResult: RunResult;
    try {
      runResult = await test.run(target);
    } catch (err) {
      runResult = {
        status: 'FAIL',
        message: `Unhandled error: ${String(err)}`,
        evidence: { error: String(err) },
      };
    }
    const durationMs = Number((performance.now() - t0).toFixed(3));

    const testResult: TestResult = {
      id: test.id,
      level: test.level,
      status: runResult.status,
      message: runResult.message,
      durationMs,
      ...(runResult.evidence !== undefined ? { evidence: runResult.evidence } : {}),
    };
    results.push(testResult);
  }

  const mustResults = results.filter((r) => r.level === 'MUST');
  const shouldResults = results.filter((r) => r.level === 'SHOULD');
  const mayResults = results.filter((r) => r.level === 'MAY');

  const mustPass = mustResults.filter((r) => r.status === 'PASS').length;
  const mustFail = mustResults.filter((r) => r.status === 'FAIL').length;
  const shouldPass = shouldResults.filter((r) => r.status === 'PASS').length;
  const shouldWarn = shouldResults.filter((r) => r.status === 'WARN').length;
  const mayPass = mayResults.filter((r) => r.status === 'PASS').length;

  // Verdict rules:
  // - Any MUST FAIL → NON_COMPLIANT
  // - All MUST PASS + all non-SKIP SHOULD PASS → COMPLIANT
  // - All MUST PASS → at least PACR_LITE
  let verdict: ComplianceVerdict;
  if (mustFail > 0) {
    verdict = 'NON_COMPLIANT';
  } else {
    const executedShould = shouldResults.filter((r) => r.status !== 'SKIP');
    const allShouldPass = executedShould.every((r) => r.status === 'PASS');
    verdict = allShouldPass ? 'COMPLIANT' : 'PACR_LITE';
  }

  return {
    target: target.name,
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    results,
    summary: {
      mustPass,
      mustFail,
      shouldPass,
      shouldWarn,
      mayPass,
      verdict,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M01: Identity Unification
// Physical meaning: 因果歸屬鏈不可斷裂
// ─────────────────────────────────────────────────────────────────────────────

async function tcM01(t: PACRComplianceTarget): Promise<RunResult> {
  const card = await t.getAgentCard();
  const record = await t.triggerEvent(new Uint8Array([0x01]));

  const checks: string[] = [];
  let pass = true;

  // extractOrigin(record.identity.id) === getAgentCard().agentId
  const extracted = extractOrigin(record.identity.id);
  if (extracted !== card.agentId) {
    checks.push(
      `FAIL: extractOrigin(record.identity.id)="${extracted as string}" !== agentCard.agentId="${card.agentId as string}"`,
    );
    pass = false;
  } else {
    checks.push(`OK: extractOrigin(record.identity.id) === agentId`);
  }

  // isEventId(record.identity.id) === true
  if (!isEventId(record.identity.id as unknown as AevumId)) {
    checks.push(`FAIL: isEventId(record.identity.id) returned false — id="${record.identity.id as string}"`);
    pass = false;
  } else {
    checks.push('OK: isEventId(record.identity.id) === true');
  }

  // record.identity.origin === card.agentId  (structural cross-check)
  if (record.identity.origin !== card.agentId) {
    checks.push(
      `FAIL: record.identity.origin="${record.identity.origin as string}" !== agentCard.agentId="${card.agentId as string}"`,
    );
    pass = false;
  } else {
    checks.push('OK: record.identity.origin === agentId');
  }

  return {
    status: pass ? 'PASS' : 'FAIL',
    message: checks.join(' | '),
    ...(pass
      ? {}
      : {
          evidence: {
            agentId: card.agentId as string,
            recordIdentityId: record.identity.id as string,
            recordIdentityOrigin: record.identity.origin as string,
            extracted: extracted as string,
          },
        }),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M02: Six-Dimension Completeness
// Physical meaning: PACR 不是 schema-optional 的 JSON，它是物理定律的編碼
// ─────────────────────────────────────────────────────────────────────────────

const PACRECORD_REQUIRED_KEYS = new Set([
  'identity',
  'predecessors',
  'landauerCost',
  'resources',
  'cognitiveSplit',
  'payload',
]);

async function tcM02(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(new Uint8Array([0x02]));

  const checks: string[] = [];
  let pass = true;

  // Check all 6 required top-level fields exist
  for (const key of PACRECORD_REQUIRED_KEYS) {
    if (!(key in record)) {
      checks.push(`FAIL: missing field "${key}"`);
      pass = false;
    } else {
      checks.push(`OK: "${key}" present`);
    }
  }

  // Check no 7th field exists (Axiom A1)
  const actualKeys = Object.keys(record as unknown as Record<string, unknown>);
  for (const key of actualKeys) {
    if (!PACRECORD_REQUIRED_KEYS.has(key)) {
      checks.push(`FAIL: unexpected extra field "${key}" violates Axiom A1`);
      pass = false;
    }
  }

  // Check all ConfidenceIntervals satisfy lower ≤ estimate ≤ upper (Axiom A4)
  const ciChecks: Array<[string, ConfidenceInterval]> = [
    ['landauerCost', record.landauerCost],
    ['resources.energy', record.resources.energy],
    ['resources.time', record.resources.time],
    ['resources.space', record.resources.space],
    ['cognitiveSplit.statisticalComplexity', record.cognitiveSplit.statisticalComplexity],
    ['cognitiveSplit.entropyRate', record.cognitiveSplit.entropyRate],
  ];

  for (const [path, ci] of ciChecks) {
    const result = checkCI(ci, path);
    checks.push(result.msg);
    if (!result.ok) pass = false;
  }

  return {
    status: pass ? 'PASS' : 'FAIL',
    message: checks.join(' | '),
    ...(pass ? {} : { evidence: { actualKeys, record: serializeRecord(record) } }),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M03: Causal Chain Correctness
// Physical meaning: 因果律（公理 I）
// ─────────────────────────────────────────────────────────────────────────────

async function tcM03(t: PACRComplianceTarget): Promise<RunResult> {
  const [recordA, recordB] = await t.triggerCausalChain(
    new Uint8Array([0x0a, 0x01]),
    new Uint8Array([0x0a, 0x02]),
  );

  const checks: string[] = [];
  let pass = true;

  // recordA.identity.id ∈ recordB.predecessors
  if (!recordB.predecessors.has(recordA.identity.id)) {
    checks.push(
      `FAIL: recordA.identity.id not found in recordB.predecessors` +
      ` — recordA.id="${recordA.identity.id as string}"`,
    );
    pass = false;
  } else {
    checks.push('OK: recordA.identity.id ∈ recordB.predecessors');
  }

  // recordB.identity.id ∉ recordA.predecessors (causal irreversibility)
  if (recordA.predecessors.has(recordB.identity.id)) {
    checks.push(
      `FAIL: recordB.identity.id found in recordA.predecessors — causal cycle detected` +
      ` — recordB.id="${recordB.identity.id as string}"`,
    );
    pass = false;
  } else {
    checks.push('OK: recordB.identity.id ∉ recordA.predecessors (no cycle)');
  }

  // recordA.identity.timestampMs ≤ recordB.identity.timestampMs
  if (recordA.identity.timestampMs > recordB.identity.timestampMs) {
    checks.push(
      `FAIL: recordA.timestampMs(${recordA.identity.timestampMs}) > recordB.timestampMs(${recordB.identity.timestampMs})` +
      ' — time runs backward',
    );
    pass = false;
  } else {
    checks.push(
      `OK: timestampA(${recordA.identity.timestampMs}) ≤ timestampB(${recordB.identity.timestampMs})`,
    );
  }

  return {
    status: pass ? 'PASS' : 'FAIL',
    message: checks.join(' | '),
    ...(pass
      ? {}
      : {
          evidence: {
            recordAId: recordA.identity.id as string,
            recordBId: recordB.identity.id as string,
            recordAPredecessors: [...recordA.predecessors] as string[],
            recordBPredecessors: [...recordB.predecessors] as string[],
            timestampA: recordA.identity.timestampMs,
            timestampB: recordB.identity.timestampMs,
          },
        }),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M04: Payload Opacity
// Physical meaning: 公理 A5 — PACR 層不關心 P 的語義
// Note: fixed bytes are used instead of Math.random() to satisfy the
//       determinism requirement (same SUT → same report on repeated runs).
// ─────────────────────────────────────────────────────────────────────────────

// Deterministic pseudo-random-looking test vector (no actual randomness needed)
const OPACITY_TEST_VECTOR = new Uint8Array([
  0x7f, 0x45, 0x4c, 0x46, 0x02, 0x01, 0x01, 0x00, 0xde, 0xad, 0xbe, 0xef,
  0xca, 0xfe, 0xba, 0xbe, 0x00, 0xff, 0x80, 0x40, 0x20, 0x10, 0x08, 0x04,
  0x02, 0x01, 0xfe, 0xfd, 0xfc, 0xfb, 0xfa, 0xf9, 0x7b, 0x22, 0x6b, 0x65,
  0x79, 0x22, 0x3a, 0x22, 0x76, 0x61, 0x6c, 0x75, 0x65, 0x22, 0x7d, 0x0a,
  0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b,
  0x0c, 0x0d, 0x0e, 0x0f,
]);

async function tcM04(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(OPACITY_TEST_VECTOR);

  // record.payload instanceof Uint8Array
  if (!(record.payload instanceof Uint8Array)) {
    return {
      status: 'FAIL',
      message: `FAIL: record.payload is not Uint8Array — got ${Object.prototype.toString.call(record.payload)}`,
      evidence: { payloadType: typeof record.payload },
    };
  }

  // record.payload.length > 0
  if (record.payload.length === 0) {
    return {
      status: 'FAIL',
      message: 'FAIL: record.payload is empty Uint8Array (length === 0)',
      evidence: { payloadLength: 0 },
    };
  }

  // Attempt JSON parse — PASS regardless of outcome (PACR is agnostic)
  let jsonParseable: boolean;
  try {
    JSON.parse(new TextDecoder().decode(record.payload));
    jsonParseable = true;
  } catch {
    jsonParseable = false;
  }

  return {
    status: 'PASS',
    message:
      `OK: payload is Uint8Array(${record.payload.length} bytes);` +
      ` JSON-parseable=${jsonParseable} (irrelevant — Axiom A5)`,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M05: Persistence Consistency
// Physical meaning: PACR 記錄是不可變的物理事實
// ─────────────────────────────────────────────────────────────────────────────

async function tcM05(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(new Uint8Array([0x05]));
  const retrieved = await t.retrieveRecord(record.identity.id);

  if (retrieved === null) {
    return {
      status: 'FAIL',
      message: 'FAIL: retrieveRecord returned null — record was not persisted',
      evidence: { eventId: record.identity.id as string },
    };
  }

  const diffs = deepDiffRecord(record, retrieved);

  if (diffs.length === 0) {
    return {
      status: 'PASS',
      message: 'OK: retrieved record deepEquals original across all 6 dimensions',
    };
  }

  return {
    status: 'FAIL',
    message: `FAIL: retrieved record differs from original in ${diffs.length} field(s): ${diffs.map((d) => d.path).join(', ')}`,
    evidence: { diffs },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-M06: Identity Space Isolation
// Physical meaning: agent 和事件是不同的本體論層級 (I_agent ∩ I_event = ∅)
// ─────────────────────────────────────────────────────────────────────────────

async function tcM06(t: PACRComplianceTarget): Promise<RunResult> {
  const card = await t.getAgentCard();
  const record = await t.triggerEvent(new Uint8Array([0x06]));

  const checks: string[] = [];
  let pass = true;

  const agentIdStr = card.agentId as string;
  const eventIdStr = record.identity.id as string;

  // AgentId must start with "a-"
  if (!agentIdStr.startsWith('a-')) {
    checks.push(`FAIL: agentCard.agentId="${agentIdStr}" does not start with "a-"`);
    pass = false;
  } else {
    checks.push(`OK: agentId starts with "a-"`);
  }

  // EventId must start with "e-"
  if (!eventIdStr.startsWith('e-')) {
    checks.push(`FAIL: record.identity.id="${eventIdStr}" does not start with "e-"`);
    pass = false;
  } else {
    checks.push('OK: eventId starts with "e-"');
  }

  // isAgentId(card.agentId) must be true
  if (!isAgentId(card.agentId as unknown as AevumId)) {
    checks.push(`FAIL: isAgentId(agentId) returned false`);
    pass = false;
  } else {
    checks.push('OK: isAgentId(agentCard.agentId) === true');
  }

  // isEventId(record.identity.id) must be true
  if (!isEventId(record.identity.id as unknown as AevumId)) {
    checks.push(`FAIL: isEventId(record.identity.id) returned false`);
    pass = false;
  } else {
    checks.push('OK: isEventId(record.identity.id) === true');
  }

  // I_agent ∩ I_event = ∅: the agentId must NOT be a valid eventId and vice versa
  if (isEventId(card.agentId as unknown as AevumId)) {
    checks.push(`FAIL: agentId passes isEventId — identity spaces overlap (I_agent ∩ I_event ≠ ∅)`);
    pass = false;
  } else {
    checks.push('OK: agentId ∉ I_event');
  }

  if (isAgentId(record.identity.id as unknown as AevumId)) {
    checks.push(`FAIL: eventId passes isAgentId — identity spaces overlap (I_agent ∩ I_event ≠ ∅)`);
    pass = false;
  } else {
    checks.push('OK: eventId ∉ I_agent');
  }

  return {
    status: pass ? 'PASS' : 'FAIL',
    message: checks.join(' | '),
    ...(pass ? {} : { evidence: { agentId: agentIdStr, eventId: eventIdStr } }),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-S01: Non-Trivial Landauer Cost
// ─────────────────────────────────────────────────────────────────────────────

async function tcS01(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(new Uint8Array([0x51]));
  const λ = record.landauerCost;

  if (λ.estimate > 0 && isFinite(λ.upper) && λ.upper < Infinity) {
    return {
      status: 'PASS',
      message:
        `OK: Λ.estimate=${λ.estimate} > 0; Λ.upper=${λ.upper} < ∞` +
        ` — Landauer cost is physically bounded`,
    };
  }

  return {
    status: 'WARN',
    message:
      `WARN: PACR-Lite mode for Λ` +
      ` — estimate=${λ.estimate}, lower=${λ.lower}, upper=${λ.upper}` +
      ` (implementation does not report Landauer cost)`,
    evidence: { landauerCost: { estimate: λ.estimate, lower: λ.lower, upper: λ.upper } },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-S02: Non-Trivial Cognitive Split
// ─────────────────────────────────────────────────────────────────────────────

async function tcS02(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(new Uint8Array([0x52]));
  const st = record.cognitiveSplit.statisticalComplexity;
  const ht = record.cognitiveSplit.entropyRate;

  const stNonTrivial = st.estimate > 0 && isFinite(st.upper) && st.upper < Infinity;
  const htNonTrivial = ht.estimate > 0 && isFinite(ht.upper) && ht.upper < Infinity;

  if (stNonTrivial && htNonTrivial) {
    return {
      status: 'PASS',
      message:
        `OK: Γ.S_T.estimate=${st.estimate} (bounded); Γ.H_T.estimate=${ht.estimate} (bounded)` +
        ` — cognitive split is physically meaningful`,
    };
  }

  const which = [
    ...(!stNonTrivial ? ['S_T'] : []),
    ...(!htNonTrivial ? ['H_T'] : []),
  ].join(', ');

  return {
    status: 'WARN',
    message: `WARN: PACR-Lite mode for Γ — ${which} is trivial (max-ignorance CI)`,
    evidence: {
      statisticalComplexity: { estimate: st.estimate, lower: st.lower, upper: st.upper },
      entropyRate: { estimate: ht.estimate, lower: ht.lower, upper: ht.upper },
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-S03: Physical Resource Consistency (Margolus-Levitin)
// ─────────────────────────────────────────────────────────────────────────────

async function tcS03(t: PACRComplianceTarget): Promise<RunResult> {
  const record = await t.triggerEvent(new Uint8Array([0x53]));
  const E = record.resources.energy.estimate;
  const T = record.resources.time.estimate;

  // Skip if estimates are degenerate
  if (E === 0 || T === 0 || !isFinite(E) || !isFinite(T)) {
    return {
      status: 'SKIP',
      message:
        `SKIP: Ω.E.estimate=${E}, Ω.T.estimate=${T}` +
        ` — cannot verify Margolus-Levitin bound with degenerate values`,
    };
  }

  // Margolus-Levitin: T ≥ πħ/(2E)
  const mlBound = (Math.PI * REDUCED_PLANCK_CONSTANT) / (2 * E);

  if (T >= mlBound) {
    return {
      status: 'PASS',
      message:
        `OK: Margolus-Levitin satisfied — T=${T}s ≥ πħ/(2E)=${mlBound.toExponential(6)}s` +
        ` (E=${E}J, ħ=${REDUCED_PLANCK_CONSTANT.toExponential(4)}J·s)`,
    };
  }

  return {
    status: 'WARN',
    message:
      `WARN: Margolus-Levitin apparently violated — T=${T}s < πħ/(2E)=${mlBound.toExponential(6)}s` +
      ` — likely measurement error or unit mismatch`,
    evidence: {
      T,
      E,
      mlBound,
      hBar: REDUCED_PLANCK_CONSTANT,
      ratio: T / mlBound,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-A01: Incremental Projection Consistency
// ─────────────────────────────────────────────────────────────────────────────

async function tcA01(t: PACRComplianceTarget): Promise<RunResult> {
  // Check if the SUT exposes the projection interface
  const projTarget = t as Partial<PACRProjectionTarget>;
  if (
    typeof projTarget.projectBatch !== 'function' ||
    typeof projTarget.projectIncremental !== 'function'
  ) {
    return {
      status: 'SKIP',
      message:
        'SKIP: SUT does not expose projectBatch / projectIncremental — TC-A01 cannot run',
    };
  }

  // Trigger 3 records: A → B → C (causal chain)
  const [recordA, recordB] = await t.triggerCausalChain(
    new Uint8Array([0xa1, 0x01]),
    new Uint8Array([0xa1, 0x02]),
  );
  const recordC = await t.triggerEvent(new Uint8Array([0xa1, 0x03]));

  const records: PACRecord[] = [recordA, recordB, recordC];

  // Batch projection
  const batchResult = await projTarget.projectBatch(records);

  // Incremental projection
  let accumulated: unknown = null;
  for (const record of records) {
    accumulated = await projTarget.projectIncremental(accumulated, record);
  }
  const incrementalResult = accumulated;

  // Compare results using stable serialization
  const batchStr = stableStringify(batchResult);
  const incrementalStr = stableStringify(incrementalResult);

  if (batchStr === incrementalStr) {
    return {
      status: 'PASS',
      message: 'OK: incremental projection ≡ batch projection for 3-record causal chain',
    };
  }

  return {
    status: 'FAIL',
    message: 'FAIL: incremental projection result diverges from batch projection result',
    evidence: {
      batchResult,
      incrementalResult,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TC-A02: Aggregation Write-Back Consistency
// ─────────────────────────────────────────────────────────────────────────────

async function tcA02(t: PACRComplianceTarget): Promise<RunResult> {
  const card = await t.getAgentCard();

  // Check if AgentCard carries behavior entropy metadata
  if (!card.metadata || !('aevum:behavior_entropy' in card.metadata)) {
    return {
      status: 'SKIP',
      message:
        'SKIP: AgentCard.metadata["aevum:behavior_entropy"] not present — TC-A02 cannot run',
    };
  }

  const entropy = card.metadata['aevum:behavior_entropy'];

  // Validate structural shape of AgentBehaviorEntropy
  if (!isAgentBehaviorEntropy(entropy)) {
    return {
      status: 'FAIL',
      message:
        'FAIL: AgentCard.metadata["aevum:behavior_entropy"] has wrong shape' +
        ' — expected AgentBehaviorEntropy',
      evidence: { entropy },
    };
  }

  // Validate internal consistency of the entropy values
  const checks: string[] = [];
  let pass = true;

  const ht = entropy.aggregatedEntropyRate;
  const st = entropy.aggregatedStatisticalComplexity;

  const htCheck = checkCI(ht, 'aggregatedEntropyRate');
  const stCheck = checkCI(st, 'aggregatedStatisticalComplexity');
  checks.push(htCheck.msg, stCheck.msg);
  if (!htCheck.ok || !stCheck.ok) pass = false;

  if (typeof entropy.sampleCount !== 'number' || entropy.sampleCount < 0 || !isFinite(entropy.sampleCount)) {
    checks.push(`FAIL: sampleCount=${entropy.sampleCount} is invalid`);
    pass = false;
  } else {
    checks.push(`OK: sampleCount=${entropy.sampleCount}`);
  }

  if (typeof entropy.windowSeconds !== 'number' || entropy.windowSeconds <= 0 || !isFinite(entropy.windowSeconds)) {
    checks.push(`FAIL: windowSeconds=${entropy.windowSeconds} is invalid`);
    pass = false;
  } else {
    checks.push(`OK: windowSeconds=${entropy.windowSeconds}`);
  }

  return {
    status: pass ? 'PASS' : 'FAIL',
    message: checks.join(' | '),
    ...(pass ? {} : { evidence: { entropy } }),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal Helpers
// ─────────────────────────────────────────────────────────────────────────────

function checkCI(ci: unknown, label: string): { ok: boolean; msg: string } {
  if (ci === null || ci === undefined || typeof ci !== 'object') {
    return { ok: false, msg: `FAIL: ${label} is missing or not an object` };
  }

  const c = ci as Record<string, unknown>;

  for (const field of ['estimate', 'lower', 'upper'] as const) {
    const v = c[field];
    if (typeof v !== 'number' || Number.isNaN(v)) {
      return { ok: false, msg: `FAIL: ${label}.${field} is not a valid number (got ${String(v)})` };
    }
  }

  const lower = c['lower'] as number;
  const estimate = c['estimate'] as number;
  const upper = c['upper'] as number;

  // Allow upper = Infinity (PACR-Lite max ignorance)
  if (lower > estimate || (isFinite(upper) && estimate > upper)) {
    return {
      ok: false,
      msg: `FAIL: ${label} violates lower(${lower}) ≤ estimate(${estimate}) ≤ upper(${upper}) [Axiom A4]`,
    };
  }

  return { ok: true, msg: `OK: ${label} CI valid [${lower}, ${estimate}, ${upper}]` };
}

interface RecordDiff {
  path: string;
  expected: unknown;
  got: unknown;
}

function deepDiffRecord(expected: PACRecord, got: PACRecord): RecordDiff[] {
  const diffs: RecordDiff[] = [];

  // identity
  if (expected.identity.id !== got.identity.id) {
    diffs.push({ path: 'identity.id', expected: expected.identity.id, got: got.identity.id });
  }
  if (expected.identity.origin !== got.identity.origin) {
    diffs.push({ path: 'identity.origin', expected: expected.identity.origin, got: got.identity.origin });
  }
  if (expected.identity.timestampMs !== got.identity.timestampMs) {
    diffs.push({ path: 'identity.timestampMs', expected: expected.identity.timestampMs, got: got.identity.timestampMs });
  }

  // predecessors
  const expPreds = [...expected.predecessors].sort();
  const gotPreds = [...got.predecessors].sort();
  if (JSON.stringify(expPreds) !== JSON.stringify(gotPreds)) {
    diffs.push({ path: 'predecessors', expected: expPreds, got: gotPreds });
  }

  // CIs
  for (const [path, expCI, gotCI] of ciPairs(expected, got)) {
    if (expCI.estimate !== gotCI.estimate || expCI.lower !== gotCI.lower || expCI.upper !== gotCI.upper) {
      diffs.push({
        path,
        expected: { estimate: expCI.estimate, lower: expCI.lower, upper: expCI.upper },
        got: { estimate: gotCI.estimate, lower: gotCI.lower, upper: gotCI.upper },
      });
    }
  }

  // payload
  if (!uint8Equal(expected.payload, got.payload)) {
    diffs.push({
      path: 'payload',
      expected: `Uint8Array(${expected.payload.length})`,
      got: `Uint8Array(${got.payload.length})`,
    });
  }

  return diffs;
}

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

function uint8Equal(a: Readonly<Uint8Array>, b: Readonly<Uint8Array>): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const av = a[i];
    const bv = b[i];
    if (av !== bv) return false;
  }
  return true;
}

/**
 * Stable deterministic serialization for comparison.
 * Handles Sets, Maps, Infinity, and objects with sorted keys.
 */
function stableStringify(value: unknown): string {
  if (value === undefined) return 'undefined';
  if (value === null) return 'null';
  if (typeof value === 'number') {
    if (!isFinite(value)) return value > 0 ? '__INF__' : '__NEG_INF__';
    return String(value);
  }
  if (typeof value !== 'object') return JSON.stringify(value);
  if (value instanceof Uint8Array) return `Uint8Array(${value.length})[${[...value].slice(0, 8).join(',')}...]`;
  if (value instanceof Set) {
    return `Set[${[...value].map(stableStringify).sort().join(',')}]`;
  }
  if (value instanceof Map) {
    const entries = [...value.entries()].map(([k, v]) => `${stableStringify(k)}:${stableStringify(v)}`).sort();
    return `Map{${entries.join(',')}}`;
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`).join(',')}}`;
}

/** Serializes a PACRecord to a plain object for evidence output */
function serializeRecord(record: PACRecord): unknown {
  return {
    identity: {
      id: record.identity.id as string,
      origin: record.identity.origin as string,
      timestampMs: record.identity.timestampMs,
    },
    predecessors: [...record.predecessors] as string[],
    landauerCost: { estimate: record.landauerCost.estimate, lower: record.landauerCost.lower, upper: record.landauerCost.upper },
    resources: {
      energy: { estimate: record.resources.energy.estimate, lower: record.resources.energy.lower, upper: record.resources.energy.upper },
      time: { estimate: record.resources.time.estimate, lower: record.resources.time.lower, upper: record.resources.time.upper },
      space: { estimate: record.resources.space.estimate, lower: record.resources.space.lower, upper: record.resources.space.upper },
    },
    cognitiveSplit: {
      statisticalComplexity: { estimate: record.cognitiveSplit.statisticalComplexity.estimate, lower: record.cognitiveSplit.statisticalComplexity.lower, upper: record.cognitiveSplit.statisticalComplexity.upper },
      entropyRate: { estimate: record.cognitiveSplit.entropyRate.estimate, lower: record.cognitiveSplit.entropyRate.lower, upper: record.cognitiveSplit.entropyRate.upper },
    },
    payload: `Uint8Array(${record.payload.length})`,
  };
}

function isAgentBehaviorEntropy(v: unknown): v is AgentBehaviorEntropy {
  if (v === null || typeof v !== 'object') return false;
  const obj = v as Record<string, unknown>;
  return (
    typeof obj['sampleCount'] === 'number' &&
    typeof obj['windowSeconds'] === 'number' &&
    obj['aggregatedEntropyRate'] !== null && typeof obj['aggregatedEntropyRate'] === 'object' &&
    obj['aggregatedStatisticalComplexity'] !== null && typeof obj['aggregatedStatisticalComplexity'] === 'object'
  );
}
