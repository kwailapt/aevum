// src/types/envelope.ts
// Envelope = Primary Header (AgentCard 路由) + Extension Header (PACR 元數據) + Body (P)
// 這是系統的「血液格式」

import type { AgentId, EventId, CapabilityRef } from './identity';
import type {
  CausalPredecessorSet,
  LandauerCost,
  ResourceConstraintTriple,
  CognitiveSplit,
  OpaquePayload,
} from './pacr';

// ─────────────────────────────────────────────
// Primary Header：路由必需（沙漏窄腰）
// ─────────────────────────────────────────────

export interface EnvelopePrimaryHeader {
  /** 目標 agent */
  readonly targetAgentId: AgentId;
  /** 請求的能力 */
  readonly targetCapability: CapabilityRef;
  /** 發起方 agent */
  readonly sourceAgentId: AgentId;
  /** TTL countdown（剩餘跳數或剩餘秒數） */
  readonly ttl: number;
  /** 協議版本（語義版本號，Day 0 為 "1.0.0"） */
  readonly protocolVersion: string;
}

// ─────────────────────────────────────────────
// Extension Header：PACR 元數據（pacr:* 命名空間）
// ─────────────────────────────────────────────

export interface EnvelopePACRExtension {
  /** pacr:event_id — 此 Envelope 對應的事件身份 */
  readonly 'pacr:event_id': EventId;
  /** pacr:predecessors — 因果前驅集的序列化形式 */
  readonly 'pacr:predecessors': readonly EventId[];
  /** pacr:landauer_cost — 蘭道爾成本三元組 */
  readonly 'pacr:landauer_cost': {
    readonly estimate: number;
    readonly lower: number;
    readonly upper: number;
  };
  /** pacr:resources — 資源約束三元組 */
  readonly 'pacr:resources': {
    readonly energy: { estimate: number; lower: number; upper: number };
    readonly time: { estimate: number; lower: number; upper: number };
    readonly space: { estimate: number; lower: number; upper: number };
  };
  /** pacr:cognitive_split — 認知分割 */
  readonly 'pacr:cognitive_split': {
    readonly statisticalComplexity: { estimate: number; lower: number; upper: number };
    readonly entropyRate: { estimate: number; lower: number; upper: number };
  };
}

// ─────────────────────────────────────────────
// 完整 Envelope
// ─────────────────────────────────────────────

export interface Envelope {
  readonly primaryHeader: EnvelopePrimaryHeader;
  readonly extensions: EnvelopePACRExtension & {
    /** 允許其他命名空間的擴展 */
    readonly [key: string]: unknown;
  };
  /** Body = PACR 的 P（不透明載荷） */
  readonly body: OpaquePayload;
}
