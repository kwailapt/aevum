// src/types/agent-card.ts
// AgentCard：agent 的靜態能力描述
// 與 PACR 的關係：AgentCard 是 PACR 記錄的聚合投影面

import type { AgentId, CapabilityRef } from './identity';
import type { BitsPerSymbol, ConfidenceInterval } from './pacr';

// ─────────────────────────────────────────────
// AgentCard 核心字段
// ─────────────────────────────────────────────

export interface Capability {
  /** 能力名稱，同時作為 PACR EventId 中 capabilityRef 的取值空間 */
  readonly name: CapabilityRef;
  /** 人類可讀描述 */
  readonly description: string;
  /** 機器可讀的輸入 schema（JSON Schema 或等效物） */
  readonly inputSchema?: unknown;
  /** 機器可讀的輸出 schema */
  readonly outputSchema?: unknown;
}

export interface AgentCardMetadata {
  /** 
   * 命名空間化的元數據
   * 格式：`namespace:key`
   * 
   * Aevum 保留命名空間：
   * - `aevum:behavior_entropy` → AgentCard 級別的 H̄_T（由 Σ 算子從 PACR Γ 聚合）
   * - `pacr:interaction_summary` → Agent 交互圖（由 π 算子從 PACR Π 投影）
   * - `pacr:landauer_efficiency` → 蘭道爾效率（由 Ω.E - Λ 聚合）
   */
  readonly [namespacedKey: string]: unknown;
}

/**
 * AgentCard — Agent 的靜態能力描述
 * 
 * 設計原則：
 * - required fields 是沙漏窄腰（路由必需）
 * - metadata 是可擴展的（無限進化空間）
 * - 與 PACR 的關係通過 aevum:* 和 pacr:* 命名空間橋接
 */
export interface AgentCard {
  // ═══ 路由必需字段（沙漏窄腰）═══

  /** Agent 身份，與 PACR ι.origin 共享身份空間 */
  readonly agentId: AgentId;
  /** Agent 的人類可讀名稱 */
  readonly name: string;
  /** Agent 的能力列表 */
  readonly capabilities: readonly Capability[];
  /** 
   * Agent 的端點 URL（路由目標）
   * 可以是 HTTP、WebSocket、gRPC 等
   */
  readonly endpoint: string;
  /** 
   * 存活時間（秒）
   * 定義了 AgentCard 的緩存有效期
   * 也隱含定義了 PACR 聚合的滑動窗口寬度
   */
  readonly ttlSeconds: number;

  // ═══ 操作度量字段 ═══

  /** 
   * 估計延遲（毫秒）
   * 注意：此值是 PACR Ω.T 的聚合投影，經過 commensuration 層轉換
   * 不允許直接從 PACR 的秒值手動乘 1000 得到
   */
  readonly estimatedLatencyMs?: number;
  /** 
   * 每次調用成本（貨幣單位）
   * 注意：此值是 PACR Ω.E 經過匯率函數 f(E, Context) 轉換的結果
   */
  readonly costPerCall?: number;
  /** 成本的貨幣單位 (ISO 4217) */
  readonly costCurrency?: string;

  // ═══ 標籤與發現 ═══

  readonly tags?: readonly string[];
  readonly version?: string;

  // ═══ 可擴展元數據 ═══

  readonly metadata?: AgentCardMetadata;
}

// ─────────────────────────────────────────────
// AgentCard 中由 PACR 聚合填充的字段類型
// ─────────────────────────────────────────────

/**
 * Agent 行為熵 — 由 Σ 算子從 PACR Γ 聚合
 * 寫入 AgentCard.metadata['aevum:behavior_entropy']
 */
export interface AgentBehaviorEntropy {
  /** 聚合後的 H̄_T */
  readonly aggregatedEntropyRate: BitsPerSymbol;
  /** 聚合後的 S̄_T */
  readonly aggregatedStatisticalComplexity: BitsPerSymbol;
  /** 聚合窗口內的 PACR 記錄數 */
  readonly sampleCount: number;
  /** 聚合窗口的時間跨度（秒） */
  readonly windowSeconds: number;
}

/**
 * Agent 交互摘要 — 由 π 算子從 PACR Π 投影
 * 寫入 AgentCard.metadata['pacr:interaction_summary']
 */
export interface AgentInteractionSummary {
  /** 此 agent 調用過的其他 agent 及頻率 */
  readonly callees: ReadonlyMap<AgentId, InteractionEdge>;
  /** 調用過此 agent 的其他 agent 及頻率 */
  readonly callers: ReadonlyMap<AgentId, InteractionEdge>;
}

export interface InteractionEdge {
  readonly callCount: number;
  readonly averageLatency: ConfidenceInterval<'seconds'>;
  readonly averageEnergy: ConfidenceInterval<'joules'>;
  readonly lastInteractionTimestampMs: number;
}
