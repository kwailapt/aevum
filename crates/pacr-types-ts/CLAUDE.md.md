# CLAUDE.md — Aevum Day 0 Foundation

## 項目身份
本項目是 Aevum 生態的 Day 0 基因組：定義 AgentCard（agent 靜態描述）與
PACR（計算事件動態記錄）之間不可變的共基契約。
本項目產出的每一個類型定義、每一個接口、每一條測試，
都將被未來十年內產生的 10^11 條記錄所依賴。
因此：正確性 > 完備性 > 性能 > 便利性。

## 不可違反的公理（Axioms — 絕對不可妥協）

### A1: PACR 六元組不可變性
PACR 是且僅是六元組 R = (ι, Π, Λ, Ω, Γ, P)。
- 不允許新增第七個頂層維度
- 不允許刪除任何維度
- 不允許合併任何兩個維度
- ι 的內部結構（origin, capability_ref）不算新維度
如果你發現某個需求似乎需要第七維度，停下來，在 /docs/axiom-challenges/ 
下寫一份分析文件，論證為什麼六維不夠。不要直接改類型。

### A2: 身份空間統一性
AgentCard.agent_id 和 PACR.ι.origin 必須來自同一個身份空間 I。
不允許存在任何代碼路徑產生一個 PACR 記錄，其 ι.origin 
不是一個合法的 AgentCard.agent_id。違反此規則等同於因果鏈斷裂。

### A3: 度量通約性
PACR 的物理單位（焦耳、秒、位元組）和 AgentCard 的操作單位
（毫秒、美元、MB）之間的映射，必須經過 CommensuationLayer 的顯式轉換。
不允許在任何地方進行 hardcoded 的單位換算（如 `latency * 1000`）。
所有換算必須經過 commensuration.ts 中定義的函數。

### A4: 置信區間不可省略
所有物理量字段（Λ, Ω, Γ）必須表示為 (estimate, lower, upper) 三元組。
不允許出現裸標量。如果測量系統只能提供點估計，
必須填入 lower = 0, upper = +Infinity（即最大無知狀態）。
PACR-Lite 就是這個規則的自然結果，不是一個特例。

### A5: Payload 不透明性
任何 PACR 層的代碼不允許解析、反序列化、或以任何方式「理解」 P 的內容。
P 是 {0,1}*，PACR 層只能測量它的長度（用於 Ω.S 計算）。
如果需要按語義類型聚合事件，使用 ι.capability_ref，不要打開 P。

## 目錄結構約定
src/  
├── types/ # 純類型定義，零運行時代碼  
│ ├── identity.ts # I_agent, I_event, 共享身份空間  
│ ├── pacr.ts # PACR 六元組的完整類型  
│ ├── agent-card.ts # AgentCard 的完整類型  
│ ├── envelope.ts # Envelope = AgentCard路由頭 + PACR元數據頭 + Body  
│ └── commensuration.ts # 度量通約層的接口類型  
├── core/ # 核心邏輯，僅依賴 types/  
│ ├── identity.ts # 身份生成與驗證  
│ ├── projection.ts # π 算子：PACR DAG → Agent 交互圖  
│ ├── aggregation.ts # Σ 算子：PACR Γ → AgentCard H̄_T  
│ ├── commensuration.ts # 度量通約的參考實現  
│ └── envelope.ts # Envelope 的構造與解析  
├── compliance/ # 合規測試套件  
│ ├── pacr-compliance.test.ts  
│ ├── identity-compliance.test.ts  
│ └── bridge-compliance.test.ts  
├── bridges/ # 橋接適配器接口  
│ ├── openapi-adapter.ts  
│ ├── mcp-adapter.ts  
│ └── a2a-adapter.ts  
└── docs/  
├── axiom-challenges/ # 對公理的質疑必須寫在這裡  
├── decisions/ # ADR (Architecture Decision Records)  
└── proofs/ # 完備性/獨立性證明的形式化版本

## 編碼規範 
### TypeScript 嚴格模式 
- strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true 
- 所有 PACR/AgentCard 類型使用 branded types（不是裸 string/number） - 零 `any`。
- 零 `as` 類型斷言（除非在 bridge adapter 的邊界處，且必須附帶註釋說明為什麼安全） 
- 
- ### 測試哲學
- types/ 下的文件通過 tsc --noEmit 測試（純類型級正確性） 
- core/ 下的每個函數必須有 property-based tests（使用 fast-check） 
- compliance/ 是面向外部實現者的黑盒測試，不依賴內部實現 
- 
- ### 命名規範 
- 類型名：PascalCase，與數學符號的對應關係寫在 JSDoc 中 
- 函數名：camelCase，動詞開頭 
- 常量：SCREAMING_SNAKE_CASE 
- 文件名：kebab-case.ts 
- 
- ### Commit 規範 
- feat(types): ... — 類型定義變更（需要 /docs/decisions/ 中的 ADR） 
- feat(core): ... — 核心邏輯變更 
- feat(compliance): ... — 合規測試變更 
- fix: ... — 修復 
- docs: ... — 文檔 
- 任何對 types/ 的變更必須在 commit message 中引用對應的 ADR 編號 
- 
- ## 與 Claude Code 的交互協議 
- 當我說「實現 P0-1」時，意味著我要你實現 src/types/identity.ts 和 src/core/identity.ts 
- 當我說「實現 P0-2」時，意味著我要你實現 src/core/projection.ts 
- 當我說「實現 P0-3」時，意味著我要你實現 src/types/commensuration.ts 和 src/core/commensuration.ts 
- 當我說「證明完備性」時，意味著我要你在 src/docs/proofs/ 下寫形式化論證 
- 當我說「挑戰公理 AX」時，意味著我要你在 src/docs/axiom-challenges/ 下寫分析 
- 在實現任何 core/ 模塊之前，必須先確認對應的 types/ 已經存在且通過 tsc 
- 在實現任何 bridge/ 之前，必須先確認 compliance/ 測試已經存在 
- 
- ## 物理常數（用於 commensuration 層） 
- k_B = 1.380649e-23 J/K （精確值，2019 SI 重新定義） 
- ln2 = 0.6931471805599453 
- h = 6.62607015e-34 J·s （精確值） 
- ħ = h / (2π) 
- c = 299792458 m/s （精確值） 
- LANDAUER_UNIT_AT_300K = k_B * 300 * ln2 ≈ 2.8705e-21 J 
- 
- ## 此文件本身的版本控制 
- 本 CLAUDE.md 的任何修改必須經過以下流程： 
1. 在 docs/decisions/ 中寫 ADR 說明為什麼要改 
2. 確認修改不違反 A1-A5 公理 
3. 如果修改涉及公理本身，必須在 docs/axiom-challenges/ 中有完整論證
