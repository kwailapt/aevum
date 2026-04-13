// src/core/entropy-index.ts
// Behavior Entropy Index — agent "credit score" based on verifiable physics.
//
// H̄_T(agent, capability, window) measures predictability:
//   low  H̄_T  →  predictable  →  premium
//   high H̄_T  →  unpredictable →  discount
//
// All aggregation uses Ω.T-weighted West online algorithm,
// matching the reference implementation in aggregation.ts.

import type { AgentId, CapabilityRef } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord } from '../types/pacr.js';
import type { AgentBehaviorEntropy, AgentCard } from '../types/agent-card.js';
import type { AgentInteractionGraph } from './projection.js';

// ─────────────────────────────────────────────────────────────────────────────
// Public types
// ─────────────────────────────────────────────────────────────────────────────

export interface EntropyIndexEntry {
  agentId: AgentId;
  /** null = global aggregate across all capabilities */
  capability: CapabilityRef | null;
  entropy: AgentBehaviorEntropy;
  /**
   * 0 = lowest entropy (most predictable) = best
   * 100 = highest entropy (least predictable) = worst
   * -1 = not ranked (insufficient data)
   */
  percentileRank: number;
  trend: 'improving' | 'stable' | 'degrading';
  confidence: 'high' | 'medium' | 'low' | 'insufficient';
}

export interface EntropyIndex {
  query(agentId: AgentId, capability?: CapabilityRef): EntropyIndexEntry | null;
  rank(capability: CapabilityRef, topK: number): EntropyIndexEntry[];
  ingest(records: Iterable<PACRecord>): void;
  snapshot(): ReadonlyMap<AgentId, EntropyIndexEntry[]>;
}

export interface AnomalyFlag {
  agentId: AgentId;
  type: 'suspiciously_low_entropy' | 'cross_caller_inconsistency' | 'complexity_mismatch';
  evidence: unknown;
  severity: 'info' | 'warning' | 'critical';
}

export interface EntropyIndexConfig {
  /** Aggregation window width in seconds (default: 3600) */
  windowSeconds?: number;
  /** ε threshold for trend classification in bits/symbol/window (default: 0.01) */
  trendEpsilon?: number;
  /** Number of past windows retained for trend (default: 5) */
  trendWindowCount?: number;
  /** Minimum H̄_T to trigger suspiciously_low_entropy anomaly (default: 0.05) */
  lowEntropyThreshold?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal data structures
// ─────────────────────────────────────────────────────────────────────────────

/** Ω.T-weighted online accumulator (West's algorithm) */
interface WeightedAcc {
  sampleCount: number;
  totalWeight: number;
  wMeanST: number;  // statistical complexity
  wSumST_M2: number;
  wMeanHT: number;  // entropy rate
  wSumHT_M2: number;
}

function emptyAcc(): WeightedAcc {
  return { sampleCount: 0, totalWeight: 0, wMeanST: 0, wSumST_M2: 0, wMeanHT: 0, wSumHT_M2: 0 };
}

function accUpdate(acc: WeightedAcc, weight: number, st: number, ht: number): void {
  acc.sampleCount += 1;
  acc.totalWeight += weight;
  const oldMeanST = acc.wMeanST;
  acc.wMeanST += (weight / acc.totalWeight) * (st - oldMeanST);
  acc.wSumST_M2 += weight * (st - oldMeanST) * (st - acc.wMeanST);
  const oldMeanHT = acc.wMeanHT;
  acc.wMeanHT += (weight / acc.totalWeight) * (ht - oldMeanHT);
  acc.wSumHT_M2 += weight * (ht - oldMeanHT) * (ht - acc.wMeanHT);
}

function finalizeAcc(acc: WeightedAcc, windowSeconds: number): AgentBehaviorEntropy {
  if (acc.sampleCount === 0 || acc.totalWeight === 0) {
    return {
      aggregatedEntropyRate: { estimate: 0, lower: 0, upper: Infinity },
      aggregatedStatisticalComplexity: { estimate: 0, lower: 0, upper: Infinity },
      sampleCount: 0,
      windowSeconds,
    };
  }
  const n = acc.sampleCount;
  const Z = 1.96;
  const wVarST = n > 1 ? acc.wSumST_M2 / acc.totalWeight : Infinity;
  const wVarHT = n > 1 ? acc.wSumHT_M2 / acc.totalWeight : Infinity;
  const serrST = Math.sqrt(wVarST / n);
  const serrHT = Math.sqrt(wVarHT / n);
  return {
    aggregatedStatisticalComplexity: {
      estimate: acc.wMeanST,
      lower: Math.max(0, acc.wMeanST - Z * serrST),
      upper: acc.wMeanST + Z * serrST,
    },
    aggregatedEntropyRate: {
      estimate: acc.wMeanHT,
      lower: Math.max(0, acc.wMeanHT - Z * serrHT),
      upper: acc.wMeanHT + Z * serrHT,
    },
    sampleCount: n,
    windowSeconds,
  };
}

/** Per-(agent, capability) state */
interface KeyState {
  /** Current open epoch accumulator */
  current: WeightedAcc;
  /** Epoch number of the current accumulator */
  currentEpoch: number;
  /** Circular history of H̄_T.estimate values, oldest → newest */
  htHistory: number[];
  /** Per-caller accumulator keyed by caller AgentId string for cross-caller checks */
  callerAccs: Map<string, WeightedAcc>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Factory
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create a new EntropyIndex.
 *
 * The index processes PACR records incrementally.
 * Windows are defined by epoch numbers (floor(timestampMs / windowMs)).
 * When a record arrives for a new epoch, the previous epoch is finalized
 * and its H̄_T snapshot appended to the trend history.
 */
export function createEntropyIndex(config: EntropyIndexConfig = {}): EntropyIndex {
  const windowSeconds = config.windowSeconds ?? 3600;
  const windowMs = windowSeconds * 1000;
  const trendEpsilon = config.trendEpsilon ?? 0.01;
  const trendWindowCount = config.trendWindowCount ?? 5;

  // key = `${agentId}\0${capability ?? ''}`
  const states = new Map<string, KeyState>();
  // cap → set of agentId strings (for rank queries)
  const capAgents = new Map<string, Set<string>>();

  function makeKey(agentId: string, capability: string | null): string {
    return `${agentId}\0${capability ?? ''}`;
  }

  function getOrCreate(agentId: string, capability: string | null): KeyState {
    const k = makeKey(agentId, capability);
    let s = states.get(k);
    if (s === undefined) {
      s = { current: emptyAcc(), currentEpoch: -1, htHistory: [], callerAccs: new Map() };
      states.set(k, s);

      const capKey = capability ?? '';
      let agents = capAgents.get(capKey);
      if (agents === undefined) {
        agents = new Set<string>();
        capAgents.set(capKey, agents);
      }
      agents.add(agentId);
    }
    return s;
  }

  function advanceEpoch(state: KeyState, epoch: number): void {
    // Finalize the previous epoch and push its H̄_T to history
    if (state.currentEpoch >= 0 && state.current.sampleCount > 0) {
      state.htHistory.push(state.current.wMeanHT);
      // Keep only the most recent trendWindowCount entries
      if (state.htHistory.length > trendWindowCount) {
        state.htHistory.splice(0, state.htHistory.length - trendWindowCount);
      }
    }
    state.current = emptyAcc();
    state.currentEpoch = epoch;
  }

  // ── ingest ──────────────────────────────────────────────────────────────

  function ingest(records: Iterable<PACRecord>): void {
    for (const record of records) {
      const weight = record.resources.time.estimate;
      if (weight <= 0) continue;

      const agentId = record.identity.origin as string;
      const capRef = record.identity.capabilityRef as string | undefined;
      const ts = record.identity.timestampMs;
      const epoch = Math.floor(ts / windowMs);

      const st = record.cognitiveSplit.statisticalComplexity.estimate;
      const ht = record.cognitiveSplit.entropyRate.estimate;

      // Determine caller agents from predecessors
      const callerIds: string[] = [];
      for (const predId of record.predecessors) {
        const caller = extractOrigin(predId) as string;
        if (caller !== agentId) {
          callerIds.push(caller);
        }
      }

      // Update global (null capability) state
      const globalState = getOrCreate(agentId, null);
      if (epoch > globalState.currentEpoch) advanceEpoch(globalState, epoch);
      accUpdate(globalState.current, weight, st, ht);

      // Per-caller tracking on global state
      for (const caller of callerIds) {
        let callerAcc = globalState.callerAccs.get(caller);
        if (callerAcc === undefined) {
          callerAcc = emptyAcc();
          globalState.callerAccs.set(caller, callerAcc);
        }
        accUpdate(callerAcc, weight, st, ht);
      }

      // Update per-capability state if present
      if (capRef !== undefined) {
        const capState = getOrCreate(agentId, capRef);
        if (epoch > capState.currentEpoch) advanceEpoch(capState, epoch);
        accUpdate(capState.current, weight, st, ht);

        for (const caller of callerIds) {
          let callerAcc = capState.callerAccs.get(caller);
          if (callerAcc === undefined) {
            callerAcc = emptyAcc();
            capState.callerAccs.set(caller, callerAcc);
          }
          accUpdate(callerAcc, weight, st, ht);
        }
      }
    }
  }

  // ── helpers ─────────────────────────────────────────────────────────────

  function computeConfidence(sampleCount: number): EntropyIndexEntry['confidence'] {
    if (sampleCount >= 1000) return 'high';
    if (sampleCount >= 100) return 'medium';
    if (sampleCount >= 10) return 'low';
    return 'insufficient';
  }

  function computeTrend(history: number[]): EntropyIndexEntry['trend'] {
    // Need at least 2 points for a trend
    if (history.length < 2) return 'stable';

    // Linear regression: y = a + b*x, x in [0, n-1]
    const n = history.length;
    const xMean = (n - 1) / 2;
    let yMean = 0;
    for (const v of history) yMean += v;
    yMean /= n;

    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) {
      const xi = i - xMean;
      const yi = (history[i] ?? 0) - yMean;
      num += xi * yi;
      den += xi * xi;
    }

    if (den === 0) return 'stable';
    const slope = num / den;

    if (slope < -trendEpsilon) return 'improving';
    if (slope > trendEpsilon) return 'degrading';
    return 'stable';
  }

  /**
   * Compute percentile rank for an agent within a capability bucket.
   * Returns -1 for insufficient-confidence agents.
   */
  function computePercentileRank(
    agentIdStr: string,
    capKey: string | null,
    myHT: number,
    myConfidence: EntropyIndexEntry['confidence'],
  ): number {
    if (myConfidence === 'insufficient') return -1;

    const bucket = capAgents.get(capKey ?? '');
    if (bucket === undefined || bucket.size <= 1) return 0;

    // Gather finalized H̄_T for all agents in bucket (sufficient confidence only)
    let below = 0;
    let total = 0;

    for (const otherId of bucket) {
      if (otherId === agentIdStr) continue;
      const s = states.get(makeKey(otherId, capKey));
      if (s === undefined) continue;
      const otherEntropy = finalizeAcc(s.current, windowSeconds);
      const otherConf = computeConfidence(otherEntropy.sampleCount);
      if (otherConf === 'insufficient') continue;
      total += 1;
      if (otherEntropy.aggregatedEntropyRate.estimate < myHT) below += 1;
    }

    if (total === 0) return 0;
    return Math.round((below / total) * 100);
  }

  function buildEntry(
    agentIdStr: string,
    capability: string | null,
    state: KeyState,
  ): EntropyIndexEntry {
    const entropy = finalizeAcc(state.current, windowSeconds);
    const confidence = computeConfidence(entropy.sampleCount);
    const htNow = entropy.aggregatedEntropyRate.estimate;

    // Combine history with the current (open) window estimate for trend
    const trendData = [...state.htHistory, htNow];
    const trend = computeTrend(trendData);

    const percentileRank = computePercentileRank(agentIdStr, capability, htNow, confidence);

    return {
      agentId: agentIdStr as AgentId,
      capability: capability as CapabilityRef | null,
      entropy,
      percentileRank,
      trend,
      confidence,
    };
  }

  // ── public interface ─────────────────────────────────────────────────────

  function query(agentId: AgentId, capability?: CapabilityRef): EntropyIndexEntry | null {
    const agentStr = agentId as string;
    const capKey = capability !== undefined ? (capability as string) : null;
    const state = states.get(makeKey(agentStr, capKey));
    if (state === undefined) return null;
    return buildEntry(agentStr, capKey, state);
  }

  function rank(capability: CapabilityRef, topK: number): EntropyIndexEntry[] {
    const capStr = capability as string;
    const bucket = capAgents.get(capStr);
    if (bucket === undefined) return [];

    const entries: EntropyIndexEntry[] = [];
    for (const agentStr of bucket) {
      const state = states.get(makeKey(agentStr, capStr));
      if (state === undefined) continue;
      entries.push(buildEntry(agentStr, capStr, state));
    }

    // Sort ascending by H̄_T (lower = better)
    entries.sort(
      (a, b) =>
        a.entropy.aggregatedEntropyRate.estimate -
        b.entropy.aggregatedEntropyRate.estimate,
    );

    return entries.slice(0, topK);
  }

  function snapshotFn(): ReadonlyMap<AgentId, EntropyIndexEntry[]> {
    const result = new Map<AgentId, EntropyIndexEntry[]>();

    for (const [key, state] of states) {
      const sep = key.indexOf('\0');
      const agentStr = key.substring(0, sep);
      const capRaw = key.substring(sep + 1);
      const capKey = capRaw.length > 0 ? capRaw : null;

      let list = result.get(agentStr as AgentId);
      if (list === undefined) {
        list = [];
        result.set(agentStr as AgentId, list);
      }
      list.push(buildEntry(agentStr, capKey, state));
    }

    return result;
  }

  return { query, rank, ingest, snapshot: snapshotFn };
}

// ─────────────────────────────────────────────────────────────────────────────
// AgentCard enrichment
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Return a new AgentCard with behavior entropy metadata written into it.
 *
 * Writes:
 *   metadata['aevum:behavior_entropy']          — global aggregate
 *   metadata['aevum:behavior_entropy:{cap}']     — per-capability aggregate
 *   metadata['aevum:entropy_rank']               — global percentile rank
 *   metadata['aevum:entropy_trend']              — global trend direction
 */
export function enrichAgentCardWithEntropy(
  card: AgentCard,
  index: EntropyIndex,
): AgentCard {
  const globalEntry = index.query(card.agentId);
  const existingMeta = card.metadata ?? {};

  const newMeta: Record<string, unknown> = { ...existingMeta };

  if (globalEntry !== null) {
    newMeta['aevum:behavior_entropy'] = globalEntry.entropy;
    newMeta['aevum:entropy_rank'] = globalEntry.percentileRank;
    newMeta['aevum:entropy_trend'] = globalEntry.trend;
  }

  // Per-capability entries
  for (const cap of card.capabilities) {
    const capEntry = index.query(card.agentId, cap.name);
    if (capEntry !== null) {
      const metaKey = `aevum:behavior_entropy:${cap.name as string}`;
      newMeta[metaKey] = capEntry.entropy;
    }
  }

  return { ...card, metadata: newMeta };
}

// ─────────────────────────────────────────────────────────────────────────────
// Anomaly detection
// ───────────────────────────��─────────────────────────────────────────────────

const LOW_ENTROPY_THRESHOLD_DEFAULT = 0.05; // bits/symbol
const COMPLEXITY_MISMATCH_RATIO = 0.1;       // S_T < 10% of H_T is suspicious
const CROSS_CALLER_SPREAD_CRITICAL = 3.0;    // bits/symbol spread across callers
const CROSS_CALLER_SPREAD_WARNING = 1.0;
const CROSS_CALLER_MIN_CALLERS = 2;
const CROSS_CALLER_MIN_SAMPLES = 5;

/**
 * Scan the index for anomalous entropy patterns.
 *
 * Defence layer 1 (handled externally): PACR ι is signed — forgery is hard.
 * Defence layer 2: suspiciously_low_entropy — very low H̄_T with high confidence.
 * Defence layer 2b: complexity_mismatch — S_T is implausibly small vs H_T.
 * Defence layer 3: cross_caller_inconsistency — spread > threshold across callers.
 */
export function detectAnomalies(
  index: EntropyIndex,
  interactionGraph: AgentInteractionGraph,
  lowEntropyThreshold = LOW_ENTROPY_THRESHOLD_DEFAULT,
): AnomalyFlag[] {
  const flags: AnomalyFlag[] = [];
  const snap = index.snapshot();

  for (const [agentId, entries] of snap) {
    // Find the global entry (capability === null)
    const globalEntry = entries.find((e) => e.capability === null);
    if (globalEntry === undefined) continue;

    const ht = globalEntry.entropy.aggregatedEntropyRate.estimate;
    const st = globalEntry.entropy.aggregatedStatisticalComplexity.estimate;
    const n = globalEntry.entropy.sampleCount;
    const conf = globalEntry.confidence;

    // ── Defence layer 2: suspiciously_low_entropy ──
    if (conf !== 'insufficient' && ht < lowEntropyThreshold && ht >= 0 && n >= 10) {
      flags.push({
        agentId,
        type: 'suspiciously_low_entropy',
        severity: conf === 'high' ? 'critical' : conf === 'medium' ? 'warning' : 'info',
        evidence: { ht, st, sampleCount: n, threshold: lowEntropyThreshold },
      });
    }

    // ── Defence layer 2b: complexity_mismatch ──
    // If H_T is significant but S_T is unreasonably low (< 10% of H_T)
    if (conf !== 'insufficient' && ht > 0.5 && st < ht * COMPLEXITY_MISMATCH_RATIO) {
      flags.push({
        agentId,
        type: 'complexity_mismatch',
        severity: 'warning',
        evidence: {
          ht,
          st,
          ratio: st / ht,
          threshold: COMPLEXITY_MISMATCH_RATIO,
          sampleCount: n,
        },
      });
    }

    // ── Defence layer 3: cross_caller_inconsistency ──
    // Uses per-caller accumulators stored on the global KeyState.
    // Access via the snapshot entries' evidence field is not possible;
    // we need the raw key-state data, so we use an internal accessor.
    const callerEntries = getCallerEntries(index, agentId);
    if (callerEntries.length >= CROSS_CALLER_MIN_CALLERS) {
      // Filter to callers with enough samples
      const qualified = callerEntries.filter((c) => c.sampleCount >= CROSS_CALLER_MIN_SAMPLES);
      if (qualified.length >= CROSS_CALLER_MIN_CALLERS) {
        const htValues = qualified.map((c) => c.ht);
        const minHT = Math.min(...htValues);
        const maxHT = Math.max(...htValues);
        const spread = maxHT - minHT;

        if (spread > CROSS_CALLER_SPREAD_CRITICAL) {
          flags.push({
            agentId,
            type: 'cross_caller_inconsistency',
            severity: 'critical',
            evidence: {
              spread,
              callerCount: qualified.length,
              minHT,
              maxHT,
              threshold: CROSS_CALLER_SPREAD_CRITICAL,
            },
          });
        } else if (spread > CROSS_CALLER_SPREAD_WARNING) {
          // Also check via interaction graph to confirm callers exist
          const incomingEdges = interactionGraph.edges;
          let confirmedByGraph = false;
          for (const [, targetMap] of incomingEdges) {
            if (targetMap.has(agentId)) {
              confirmedByGraph = true;
              break;
            }
          }
          if (confirmedByGraph) {
            flags.push({
              agentId,
              type: 'cross_caller_inconsistency',
              severity: 'warning',
              evidence: {
                spread,
                callerCount: qualified.length,
                minHT,
                maxHT,
                threshold: CROSS_CALLER_SPREAD_WARNING,
              },
            });
          }
        }
      }
    }
  }

  return flags;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal accessor for anomaly detection (not part of the EntropyIndex interface)
// ─────────────────────────────────────────────────────────────────────────────

interface CallerEntry {
  callerId: string;
  ht: number;
  sampleCount: number;
}

/**
 * Extract per-caller H̄_T estimates for an agent's global state.
 * Used only by detectAnomalies — relies on the closure over `states`.
 *
 * Since detectAnomalies calls createEntropyIndex in the same module,
 * we expose this through a module-level WeakMap keyed by the index object.
 */
const CALLER_MAP = new WeakMap<EntropyIndex, Map<string, KeyState>>();

function getCallerEntries(index: EntropyIndex, agentId: AgentId): CallerEntry[] {
  const statesMap = CALLER_MAP.get(index);
  if (statesMap === undefined) return [];

  const agentStr = agentId as string;
  const state = statesMap.get(`${agentStr}\0`);
  if (state === undefined) return [];

  const result: CallerEntry[] = [];
  for (const [callerId, acc] of state.callerAccs) {
    if (acc.sampleCount > 0 && acc.totalWeight > 0) {
      result.push({ callerId, ht: acc.wMeanHT, sampleCount: acc.sampleCount });
    }
  }
  return result;
}

// Re-export a factory that also registers in CALLER_MAP
/**
 * Create an EntropyIndex and register it for anomaly detection.
 * This is the preferred factory — detectAnomalies requires it.
 */
export function createTrackedEntropyIndex(config: EntropyIndexConfig = {}): EntropyIndex {
  const windowSeconds = config.windowSeconds ?? 3600;
  const windowMs = windowSeconds * 1000;
  const trendEpsilon = config.trendEpsilon ?? 0.01;
  const trendWindowCount = config.trendWindowCount ?? 5;

  const states = new Map<string, KeyState>();
  const capAgents = new Map<string, Set<string>>();

  function makeKey(agentIdStr: string, capability: string | null): string {
    return `${agentIdStr}\0${capability ?? ''}`;
  }

  function getOrCreate(agentIdStr: string, capability: string | null): KeyState {
    const k = makeKey(agentIdStr, capability);
    let s = states.get(k);
    if (s === undefined) {
      s = { current: emptyAcc(), currentEpoch: -1, htHistory: [], callerAccs: new Map() };
      states.set(k, s);
      const capKey = capability ?? '';
      let agents = capAgents.get(capKey);
      if (agents === undefined) {
        agents = new Set<string>();
        capAgents.set(capKey, agents);
      }
      agents.add(agentIdStr);
    }
    return s;
  }

  function advanceEpoch(state: KeyState, epoch: number): void {
    if (state.currentEpoch >= 0 && state.current.sampleCount > 0) {
      state.htHistory.push(state.current.wMeanHT);
      if (state.htHistory.length > trendWindowCount) {
        state.htHistory.splice(0, state.htHistory.length - trendWindowCount);
      }
    }
    state.current = emptyAcc();
    state.currentEpoch = epoch;
  }

  function ingest(records: Iterable<PACRecord>): void {
    for (const record of records) {
      const weight = record.resources.time.estimate;
      if (weight <= 0) continue;

      const agentIdStr = record.identity.origin as string;
      const capRef = record.identity.capabilityRef as string | undefined;
      const ts = record.identity.timestampMs;
      const epoch = Math.floor(ts / windowMs);
      const st = record.cognitiveSplit.statisticalComplexity.estimate;
      const ht = record.cognitiveSplit.entropyRate.estimate;

      const callerIds: string[] = [];
      for (const predId of record.predecessors) {
        const caller = extractOrigin(predId) as string;
        if (caller !== agentIdStr) callerIds.push(caller);
      }

      const globalState = getOrCreate(agentIdStr, null);
      if (epoch > globalState.currentEpoch) advanceEpoch(globalState, epoch);
      accUpdate(globalState.current, weight, st, ht);

      for (const caller of callerIds) {
        let callerAcc = globalState.callerAccs.get(caller);
        if (callerAcc === undefined) {
          callerAcc = emptyAcc();
          globalState.callerAccs.set(caller, callerAcc);
        }
        accUpdate(callerAcc, weight, st, ht);
      }

      if (capRef !== undefined) {
        const capState = getOrCreate(agentIdStr, capRef);
        if (epoch > capState.currentEpoch) advanceEpoch(capState, epoch);
        accUpdate(capState.current, weight, st, ht);

        for (const caller of callerIds) {
          let callerAcc = capState.callerAccs.get(caller);
          if (callerAcc === undefined) {
            callerAcc = emptyAcc();
            capState.callerAccs.set(caller, callerAcc);
          }
          accUpdate(callerAcc, weight, st, ht);
        }
      }
    }
  }

  function computeConfidence(sampleCount: number): EntropyIndexEntry['confidence'] {
    if (sampleCount >= 1000) return 'high';
    if (sampleCount >= 100) return 'medium';
    if (sampleCount >= 10) return 'low';
    return 'insufficient';
  }

  function computeTrend(history: number[]): EntropyIndexEntry['trend'] {
    if (history.length < 2) return 'stable';
    const n = history.length;
    const xMean = (n - 1) / 2;
    let yMean = 0;
    for (const v of history) yMean += v;
    yMean /= n;
    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) {
      const xi = i - xMean;
      const yi = (history[i] ?? 0) - yMean;
      num += xi * yi;
      den += xi * xi;
    }
    if (den === 0) return 'stable';
    const slope = num / den;
    if (slope < -trendEpsilon) return 'improving';
    if (slope > trendEpsilon) return 'degrading';
    return 'stable';
  }

  function computePercentileRank(
    agentIdStr: string,
    capKey: string | null,
    myHT: number,
    myConfidence: EntropyIndexEntry['confidence'],
  ): number {
    if (myConfidence === 'insufficient') return -1;
    const bucket = capAgents.get(capKey ?? '');
    if (bucket === undefined || bucket.size <= 1) return 0;
    let below = 0;
    let total = 0;
    for (const otherId of bucket) {
      if (otherId === agentIdStr) continue;
      const s = states.get(makeKey(otherId, capKey));
      if (s === undefined) continue;
      const otherEntropy = finalizeAcc(s.current, windowSeconds);
      const otherConf = computeConfidence(otherEntropy.sampleCount);
      if (otherConf === 'insufficient') continue;
      total += 1;
      if (otherEntropy.aggregatedEntropyRate.estimate < myHT) below += 1;
    }
    if (total === 0) return 0;
    return Math.round((below / total) * 100);
  }

  function buildEntry(
    agentIdStr: string,
    capability: string | null,
    state: KeyState,
  ): EntropyIndexEntry {
    const entropy = finalizeAcc(state.current, windowSeconds);
    const confidence = computeConfidence(entropy.sampleCount);
    const htNow = entropy.aggregatedEntropyRate.estimate;
    const trendData = [...state.htHistory, htNow];
    const trend = computeTrend(trendData);
    const percentileRank = computePercentileRank(agentIdStr, capability, htNow, confidence);
    return {
      agentId: agentIdStr as AgentId,
      capability: capability as CapabilityRef | null,
      entropy,
      percentileRank,
      trend,
      confidence,
    };
  }

  function query(agentId: AgentId, capability?: CapabilityRef): EntropyIndexEntry | null {
    const agentStr = agentId as string;
    const capKey = capability !== undefined ? (capability as string) : null;
    const state = states.get(makeKey(agentStr, capKey));
    if (state === undefined) return null;
    return buildEntry(agentStr, capKey, state);
  }

  function rankFn(capability: CapabilityRef, topK: number): EntropyIndexEntry[] {
    const capStr = capability as string;
    const bucket = capAgents.get(capStr);
    if (bucket === undefined) return [];
    const entries: EntropyIndexEntry[] = [];
    for (const agentStr of bucket) {
      const state = states.get(makeKey(agentStr, capStr));
      if (state === undefined) continue;
      entries.push(buildEntry(agentStr, capStr, state));
    }
    entries.sort(
      (a, b) =>
        a.entropy.aggregatedEntropyRate.estimate - b.entropy.aggregatedEntropyRate.estimate,
    );
    return entries.slice(0, topK);
  }

  function snapshotFn(): ReadonlyMap<AgentId, EntropyIndexEntry[]> {
    const result = new Map<AgentId, EntropyIndexEntry[]>();
    for (const [key, state] of states) {
      const sep = key.indexOf('\0');
      const agentStr = key.substring(0, sep);
      const capRaw = key.substring(sep + 1);
      const capKey = capRaw.length > 0 ? capRaw : null;
      let list = result.get(agentStr as AgentId);
      if (list === undefined) {
        list = [];
        result.set(agentStr as AgentId, list);
      }
      list.push(buildEntry(agentStr, capKey, state));
    }
    return result;
  }

  const idx: EntropyIndex = {
    query,
    rank: rankFn,
    ingest,
    snapshot: snapshotFn,
  };

  CALLER_MAP.set(idx, states);
  return idx;
}
