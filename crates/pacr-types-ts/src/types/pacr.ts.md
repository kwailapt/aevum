// src/types/pacr.ts
// 數學符號對應：R = (ι, Π, Λ, Ω, Γ, P)
// 此文件是 PACR 的「基因」——改動此文件就是改動物種的染色體

import type { EventId, EventIdStructure, AgentId } from './identity';

// ─────────────────────────────────────────────
// 基礎度量類型：置信區間三元組
// ─────────────────────────────────────────────

/**
 * 帶置信區間的物理量測量值
 * 
 * 公理 A4：所有物理量必須攜帶不確定性信息
 * 
 * estimate: 點估計（最佳猜測）
 * lower: 置信區間下界（含）
 * upper: 置信區間上界（含）
 * 
 * 不變量：lower <= estimate <= upper
 * 特殊值：lower = 0, upper = Infinity 表示「完全無知」（PACR-Lite 模式）
 */
export interface ConfidenceInterval<Unit extends string = string> {
  readonly estimate: number;
  readonly lower: number;
  readonly upper: number;
  /** 
   * 度量單位的類型級標註
   * 不在運行時使用，僅用於 TypeScript 類型檢查防止單位混用
   */
  readonly _unit?: Unit;
}

/** 蘭道爾自然單位：k_B * T * ln2（焦耳） */
export type LandauerUnit = ConfidenceInterval<'landauer'>;
/** 焦耳 */
export type Joules = ConfidenceInterval<'joules'>;
/** 秒 */
export type Seconds = ConfidenceInterval<'seconds'>;
/** 位元組 */
export type Bytes = ConfidenceInterval<'bytes'>;
/** 位元 / 符號 (bits per symbol) */
export type BitsPerSymbol = ConfidenceInterval<'bits_per_symbol'>;

// ─────────────────────────────────────────────
// 維度 1: ι — 因果身份 (Causal Identity)
// ─────────────────────────────────────────────
// 直接使用 EventIdStructure，見 identity.ts

// ─────────────────────────────────────────────
// 維度 2: Π — 因果前驅集 (Causal Predecessor Set)
// ─────────────────────────────────────────────

/**
 * 因果前驅集
 * 
 * 數學定義：Π ⊆ I_event
 * 
 * 公理 I（因果律）要求這是一個無序集合（偏序，非全序）。
 * 使用 ReadonlySet 保證不可變性。
 * 空集合表示「創世事件」——沒有因果前驅。
 */
export type CausalPredecessorSet = ReadonlySet<EventId>;

// ─────────────────────────────────────────────
// 維度 3: Λ — 蘭道爾成本 (Landauer Cost)
// ─────────────────────────────────────────────

/**
 * 蘭道爾成本
 * 
 * 數學定義：Λ = (λ̂, λ⁻, λ⁺)
 * 單位：k_B * T * ln2（蘭道爾自然單位）
 * 
 * 物理含義：事件 ι 涉及的不可逆位元擦除的最低能量成本
 * 
 * PACR-Lite 模式：estimate = 0, lower = 0, upper = Infinity
 * （表示「我不知道蘭道爾成本，但它存在」）
 */
export type LandauerCost = LandauerUnit;

// ─────────────────────────────────────────────
// 維度 4: Ω — 資源約束三元組 (Resource Constraint Triple)
// ─────────────────────────────────────────────

/**
 * 資源約束三元組
 * 
 * 數學定義：Ω = (E, T, S)
 * 
 * 三者構成不可分割的約束面（Constraint Surface）。
 * 拆開喪失一致性校驗，合併喪失獨立分析。
 * 因此定義為單一 interface，不是三個獨立字段。
 * 
 * 物理約束（可用於一致性校驗）：
 *   T >= πħ / (2E)          [Margolus-Levitin]
 *   S <= 2ET / h            [Bremermann limit]
 */
export interface ResourceConstraintTriple {
  /** 實測能量消耗（焦耳） */
  readonly energy: Joules;
  /** 實測執行時間（秒） */
  readonly time: Seconds;
  /** 實測空間佔用（位元組） */
  readonly space: Bytes;
}

// ─────────────────────────────────────────────
// 維度 5: Γ — 認知分割 (Cognitive Split)
// ─────────────────────────────────────────────

/**
 * 認知分割
 * 
 * 數學定義：Γ = (S_T, H_T)
 * 
 * S_T: 統計複雜度（結構量）— 生成數據流所需的最小因果態集合的信息量
 * H_T: 熵率（噪聲量）— 在已知因果態條件下的殘餘不可預測性
 * 
 * 二者是同一 ε-machine 的不可分割投影。
 * 脫離對方，任何一個都喪失物理意義。
 * 
 * PACR-Lite 模式：兩者均為 estimate=0, lower=0, upper=Infinity
 */
export interface CognitiveSplit {
  /** 統計複雜度 S_T (bits per symbol) */
  readonly statisticalComplexity: BitsPerSymbol;
  /** 熵率 H_T (bits per symbol) */
  readonly entropyRate: BitsPerSymbol;
}

// ─────────────────────────────────────────────
// 維度 6: P — 不透明載荷 (Opaque Payload)
// ─────────────────────────────────────────────

/**
 * 不透明載荷
 * 
 * 數學定義：P ∈ {0,1}*
 * 
 * 公理 A5：PACR 層不解析 P 的內容。
 * 使用 Uint8Array 而非 string 強制不透明性——
 * 你不能「不小心」對 Uint8Array 做 JSON.parse。
 */
export type OpaquePayload = Readonly<Uint8Array>;

// ─────────────────────────────────────────────
// PACR 六元組：完整記錄
// ─────────────────────────────────────────────

/**
 * PACR — Physically Annotated Causal Record
 * 
 * R = (ι, Π, Λ, Ω, Γ, P)
 * 
 * 六個維度，不多不少。
 * 物理完備、相互獨立、原子不可分解。
 * 
 * 此類型是 Day 0 不可逆決策的 TypeScript 編碼。
 * 修改此類型等同於修改物理定律對計算事件的約束表述。
 */
export interface PACRecord {
  /** 維度 1: ι — 因果身份 */
  readonly identity: EventIdStructure;
  /** 維度 2: Π — 因果前驅集 */
  readonly predecessors: CausalPredecessorSet;
  /** 維度 3: Λ — 蘭道爾成本 */
  readonly landauerCost: LandauerCost;
  /** 維度 4: Ω — 資源約束三元組 */
  readonly resources: ResourceConstraintTriple;
  /** 維度 5: Γ — 認知分割 */
  readonly cognitiveSplit: CognitiveSplit;
  /** 維度 6: P — 不透明載荷 */
  readonly payload: OpaquePayload;
}

// ─────────────────────────────────────────────
// PACR-Lite：最小合規子集
// ─────────────────────────────────────────────

/**
 * PACR-Lite 不是一個獨立的類型——它就是 PACRecord，
 * 只是 Λ 和 Γ 的置信區間被設為最大寬度。
 * 
 * 這個函數是一個類型級斷言：
 * 任何 PACRecord 都是合法的，包括「完全無知」狀態的。
 */
export function isPACRLite(record: PACRecord): boolean {
  const maxIgnorance = (ci: ConfidenceInterval): boolean =>
    ci.lower === 0 && ci.upper === Infinity;

  return (
    maxIgnorance(record.landauerCost) &&
    maxIgnorance(record.cognitiveSplit.statisticalComplexity) &&
    maxIgnorance(record.cognitiveSplit.entropyRate)
  );
}