// src/core/aggregation.ts
// Σ 算子：PACR 逐事件 Γ → AgentCard 級 H̄_T
//
// 聚合方式：以 Ω.T 為權重的加權聚合
// 物理直覺：執行時間越長的事件，對 agent 行為特徵的貢獻越大

import type { AgentId } from '../types/identity';
import { extractOrigin } from '../types/identity';
import type { PACRecord, BitsPerSymbol } from '../types/pacr';
import type { AgentBehaviorEntropy } from '../types/agent-card';

/**
 * Σ 算子：從一批 PACR 記錄聚合出指定 agent 的行為熵
 * 
 * @param records - PACR 記錄集合
 * @param agentId - 目標 agent
 * @param windowSeconds - 聚合窗口寬度（通常等於 AgentCard.ttlSeconds）
 * @param nowMs - 當前時間（毫秒），用於窗口裁剪
 */
export function aggregateBehaviorEntropy(
  records: Iterable<PACRecord>,
  agentId: AgentId,
  windowSeconds: number,
  nowMs: number
): AgentBehaviorEntropy {
  const windowStartMs = nowMs - windowSeconds * 1000;

  let totalWeight = 0;
  let weightedSumST = 0;
  let weightedSumHT = 0;
  let sampleCount = 0;

  // 用於加權方差的在線算法 (West's online weighted variance)
  let wSumST_M2 = 0;
  let wMeanST = 0;
  let wSumHT_M2 = 0;
  let wMeanHT = 0;

  for (const record of records) {
    // 只聚合屬於目標 agent 且在時間窗口內的記錄
    if (extractOrigin(record.identity.id) !== agentId) continue;
    if (record.identity.timestampMs < windowStartMs) continue;

    // 權重 = 執行時間的點估計
    const weight = record.resources.time.estimate;
    if (weight <= 0) continue; // 零權重事件不參與聚合

    const st = record.cognitiveSplit.statisticalComplexity.estimate;
    const ht = record.cognitiveSplit.entropyRate.estimate;

    sampleCount += 1;
    totalWeight += weight;

    // West's online weighted mean and variance
    const oldWMeanST = wMeanST;
    wMeanST = oldWMeanST + (weight / totalWeight) * (st - oldWMeanST);
    wSumST_M2 += weight * (st - oldWMeanST) * (st - wMeanST);

    const oldWMeanHT = wMeanHT;
    wMeanHT = oldWMeanHT + (weight / totalWeight) * (ht - oldWMeanHT);
    wSumHT_M2 += weight * (ht - oldWMeanHT) * (ht - wMeanHT);

    weightedSumST += weight * st;
    weightedSumHT += weight * ht;
  }

  if (sampleCount === 0 || totalWeight === 0) {
    return {
      aggregatedEntropyRate: {
        estimate: 0,
        lower: 0,
        upper: Infinity,
      },
      aggregatedStatisticalComplexity: {
        estimate: 0,
        lower: 0,
        upper: Infinity,
      },
      sampleCount: 0,
      windowSeconds,
    };
  }

  // 加權標準誤差（用於置信區間）
  const wVarST = wSumST_M2 / totalWeight;
  const wVarHT = wSumHT_M2 / totalWeight;
  const serrST = Math.sqrt(wVarST / sampleCount);
  const serrHT = Math.sqrt(wVarHT / sampleCount);
  const z = 1.96; // 95% CI

  return {
    aggregatedStatisticalComplexity: {
      estimate: wMeanST,
      lower: Math.max(0, wMeanST - z * serrST),
      upper: wMeanST + z * serrST,
    },
    aggregatedEntropyRate: {
      estimate: wMeanHT,
      lower: Math.max(0, wMeanHT - z * serrHT),
      upper: wMeanHT + z * serrHT,
    },
    sampleCount,
    windowSeconds,
  };
}
