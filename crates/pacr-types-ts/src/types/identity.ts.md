// src/types/identity.ts
// 數學符號對應：I = I_agent ∪ I_event
// 這是整個系統的指稱基礎。改動此文件等於改動 DNA。

/**
 * Branded type 工具：防止裸 string 被誤用為身份標識符
 */
declare const __brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [__brand]: B };

// ─────────────────────────────────────────────
// Layer 0: 原始位元組級身份
// ─────────────────────────────────────────────

/**
 * 128-bit 標識符的十六進制表示（32 hex chars）
 * 所有身份標識符的底層表示形式
 */
type RawId = Brand<string, 'RawId'>;

// ─────────────────────────────────────────────
// Layer 1: Agent 身份空間 I_agent
// ─────────────────────────────────────────────

/**
 * Agent 身份標識符
 * 
 * 數學定義：ι_a ∈ I_agent
 * 
 * 生成規則：
 * - 前綴 "a-" 標識 agent 層
 * - 後跟 UUIDv7 的十六進制表示（時間排序 + 隨機性）
 * - 格式：a-{UUIDv7_hex}
 * 
 * 不可偽造性由生成環境的簽名保證（不在此層定義）
 */
export type AgentId = Brand<`a-${string}`, 'AgentId'>;

// ─────────────────────────────────────────────
// Layer 2: Event 身份空間 I_event
// ─────────────────────────────────────────────

/**
 * Event 身份標識符
 * 
 * 數學定義：ι ∈ I_event，其中 ι 攜帶結構性字段 origin ∈ I_agent
 * 
 * 關鍵設計：origin 是 ι 的內部結構，不是 PACR 的第七維度。
 * 從 EventId 提取 origin 必須是 O(1) 的位元操作。
 * 
 * 格式：e-{agent_id_hex}-{UUIDv7_hex}
 * 其中 agent_id_hex 是產生此事件的 agent 的 AgentId 的 hex 部分
 */
export type EventId = Brand<`e-${string}-${string}`, 'EventId'>;

/**
 * 可選的能力引用，嵌入在 EventId 的擴展結構中
 * 這不是 EventId 本身的一部分，而是隨 EventId 一起傳輸的元數據
 */
export type CapabilityRef = Brand<string, 'CapabilityRef'>;

/**
 * EventId 的完整結構化表示（用於構造和解析，非傳輸格式）
 */
export interface EventIdStructure {
  /** 完整的 EventId 字符串（傳輸格式） */
  readonly id: EventId;
  /** 
   * 產生此事件的 agent 的身份 
   * 公理 A2 保證：此值必為合法 AgentId
   */
  readonly origin: AgentId;
  /** 
   * 可選：此事件對應的 agent 能力名稱
   * 若存在，必須與 origin agent 的 AgentCard 中某個 capability.name 一致
   */
  readonly capabilityRef?: CapabilityRef;
  /** UUIDv7 的時間戳分量（毫秒精度） */
  readonly timestampMs: number;
}

// ─────────────────────────────────────────────
// Layer 3: 統一身份空間操作
// ─────────────────────────────────────────────

/**
 * 統一身份空間 I = I_agent ∪ I_event
 * 通過前綴 "a-" / "e-" 區分層
 */
export type AevumId = AgentId | EventId;

/**
 * 類型守衛：判斷一個 AevumId 是否為 AgentId
 */
export function isAgentId(id: AevumId): id is AgentId {
  return (id as string).startsWith('a-');
}

/**
 * 類型守衛：判斷一個 AevumId 是否為 EventId
 */
export function isEventId(id: AevumId): id is EventId {
  return (id as string).startsWith('e-');
}

/**
 * O(1) 提取：從 EventId 中提取 origin AgentId
 * 這是 P0-1 的核心要求：因果歸屬必須是常數時間操作
 */
export function extractOrigin(eventId: EventId): AgentId {
  // 格式：e-{agent_hex}-{event_uuid_hex}
  // agent_hex 是固定長度（32 hex chars），所以這是純位元偏移
  const raw = eventId as string;
  const agentHex = raw.substring(2, 34); // 跳過 "e-"，取 32 chars
  return `a-${agentHex}` as AgentId;
}