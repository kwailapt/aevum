// src/core/aggregation.ts
// Σ operator: PACR per-event Γ → AgentCard-level H̄_T
//
// Aggregation: Ω.T-weighted (execution time as weight)
// Physical intuition: longer-running events contribute more to the agent's behavioral profile

import type { AgentId, CapabilityRef } from '../types/identity.js';
import { extractOrigin } from '../types/identity.js';
import type { PACRecord, BitsPerSymbol } from '../types/pacr.js';
import type { AgentBehaviorEntropy, AgentCard } from '../types/agent-card.js';

// ─────────────────────────────────────────────
// Σ operator: full agent aggregation
// ─────────────────────────────────────────────

/**
 * Σ operator: aggregate behavior entropy for a specific agent
 * from a batch of PACR records within a sliding time window.
 *
 * Weight = record.resources.time.estimate (Ω.T)
 * Uses West's online weighted mean and variance algorithm.
 *
 * @param records    - PACR record set
 * @param agentId    - target agent
 * @param windowSeconds - aggregation window width (typically AgentCard.ttlSeconds)
 * @param nowMs      - current time (ms), used for window clipping
 */
export function aggregateBehaviorEntropy(
  records: Iterable<PACRecord>,
  agentId: AgentId,
  windowSeconds: number,
  nowMs: number,
): AgentBehaviorEntropy {
  return aggregateFiltered(records, agentId, undefined, windowSeconds, nowMs);
}

// ─────────────────────────────────────────────
// Σ operator: per-capability slice
// ─────────────────────────────────────────────

/**
 * Σ operator variant: aggregate behavior entropy for a specific agent
 * AND a specific capability.
 *
 * This answers: "What is this agent's H_T for its translation capability
 * vs its code generation capability?"
 *
 * Only records whose identity.capabilityRef matches are included.
 */
export function aggregateBehaviorEntropyByCapability(
  records: Iterable<PACRecord>,
  agentId: AgentId,
  capabilityRef: CapabilityRef,
  windowSeconds: number,
  nowMs: number,
): AgentBehaviorEntropy {
  return aggregateFiltered(records, agentId, capabilityRef, windowSeconds, nowMs);
}

// ─────────────────────────────────────────────
// AgentCard immutable update
// ─────────────────────────────────────────────

/**
 * Return a new AgentCard with metadata['aevum:behavior_entropy'] set.
 *
 * Immutable: does not modify the original card.
 */
export function updateAgentCardWithEntropy(
  card: AgentCard,
  entropy: AgentBehaviorEntropy,
): AgentCard {
  const existingMetadata = card.metadata ?? {};
  return {
    ...card,
    metadata: {
      ...existingMetadata,
      'aevum:behavior_entropy': entropy,
    },
  };
}

// ─────────────────────────────────────────────
// Internal: shared aggregation logic
// ─────────────────────────────────────────────

/** Maximum ignorance result — returned when no records match the filter */
const MAX_IGNORANCE_CI: BitsPerSymbol = {
  estimate: 0,
  lower: 0,
  upper: Infinity,
};

function aggregateFiltered(
  records: Iterable<PACRecord>,
  agentId: AgentId,
  capabilityRef: CapabilityRef | undefined,
  windowSeconds: number,
  nowMs: number,
): AgentBehaviorEntropy {
  const windowStartMs = nowMs - windowSeconds * 1000;

  let totalWeight = 0;
  let sampleCount = 0;

  // West's online weighted mean and variance
  let wMeanST = 0;
  let wSumST_M2 = 0;
  let wMeanHT = 0;
  let wSumHT_M2 = 0;

  for (const record of records) {
    // Filter: must belong to the target agent
    if (extractOrigin(record.identity.id) !== agentId) continue;

    // Filter: must be within the time window
    if (record.identity.timestampMs < windowStartMs) continue;

    // Filter: if capability specified, must match
    if (capabilityRef !== undefined && record.identity.capabilityRef !== capabilityRef) continue;

    // Weight = execution time estimate
    const weight = record.resources.time.estimate;
    if (weight <= 0) continue; // zero-weight events don't participate

    const st = record.cognitiveSplit.statisticalComplexity.estimate;
    const ht = record.cognitiveSplit.entropyRate.estimate;

    sampleCount += 1;
    totalWeight += weight;

    // West's online weighted mean and variance update
    const oldWMeanST = wMeanST;
    wMeanST += (weight / totalWeight) * (st - oldWMeanST);
    wSumST_M2 += weight * (st - oldWMeanST) * (st - wMeanST);

    const oldWMeanHT = wMeanHT;
    wMeanHT += (weight / totalWeight) * (ht - oldWMeanHT);
    wSumHT_M2 += weight * (ht - oldWMeanHT) * (ht - wMeanHT);
  }

  if (sampleCount === 0 || totalWeight === 0) {
    return {
      aggregatedEntropyRate: MAX_IGNORANCE_CI,
      aggregatedStatisticalComplexity: MAX_IGNORANCE_CI,
      sampleCount: 0,
      windowSeconds,
    };
  }

  // Weighted variance → weighted standard error of the mean
  // With n=1, variance is undefined — treat as Infinity (maximum ignorance)
  const wVarST = sampleCount > 1 ? wSumST_M2 / totalWeight : Infinity;
  const wVarHT = sampleCount > 1 ? wSumHT_M2 / totalWeight : Infinity;
  const serrST = Math.sqrt(wVarST / sampleCount);
  const serrHT = Math.sqrt(wVarHT / sampleCount);
  const Z = 1.96; // 95% CI

  return {
    aggregatedStatisticalComplexity: {
      estimate: wMeanST,
      lower: Math.max(0, wMeanST - Z * serrST),
      upper: wMeanST + Z * serrST,
    },
    aggregatedEntropyRate: {
      estimate: wMeanHT,
      lower: Math.max(0, wMeanHT - Z * serrHT),
      upper: wMeanHT + Z * serrHT,
    },
    sampleCount,
    windowSeconds,
  };
}
