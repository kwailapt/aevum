Sonnet 的分析精準地抓住了 claude-mem 的三個結構性缺陷及 Aevum 的對應降維解法。我直接做第一性校驗，然後給出 Paperclip + claude-mem 雙場景的統一 MCP Server 架構。

---

## 第一性校驗：Sonnet 分析的對與需修正的

### 對的

**壹（SQLite 狀態囤積 → 因果 DAG）：** 完全正確。claude-mem 把所有動作寫進 SQLite，是一個 `d(Disk)/dt > 0` 的無限膨脹系統。Aevum 的因果 DAG + PACR 記錄只保存因果指標（Π 邊）和壓縮後的認知狀態（Γ），原始文本在 ε-engine 提純後 Drop——這就是 Dumb Pipe 在記憶體領域的翻版。

**貳（LLM 自我總結 → ε-engine 物理提純）：** 這是最有價值的洞察。讓 Claude 自己「總結」過去的記憶，是用最貴的工具（LLM token）做最簡單的事（壓縮），且會引入語義漂移（每次總結都是有損壓縮）。ε-engine 的 CSSR 是數學確定性的——同一段歷史永遠產出同一個因果狀態集，零幻覺。

**參（Node.js → Rust）：** 方向正確但需要務實化——見下。

### 需修正的

**`#[no_std]` 在 MCP Server 場景下是過度的。** MCP 協議基於 JSON-RPC over stdio/HTTP，需要序列化/反序列化、異步 I/O、網路連接。這些在 `no_std` 下極其痛苦且不必要。正確的做法是**標準 Rust + `#![forbid(unsafe_code)]`**，目標 RSS < 10 MiB（而非 2 MiB——MCP 需要保持連接狀態，比純 Dumb Pipe 多一些合理的記憶體開銷）。

**「2 MiB 絕對穩態」對 MCP Server 不成立。** Dumb Pipe 之所以能 2 MiB 是因為它完全無狀態——處理完即丟。MCP memory server 本質上需要維護一個記憶體內的因果索引（最近 N 個因果狀態的 Π 指標），所以基線會高一些。但比 claude-mem 的 100 MiB+ Node.js 仍然低一個數量級。

---

## 統一架構：一個 MCP Server，兩個殺手場景

不應該分別做「Paperclip MCP adapter」和「claude-mem 替代品」——它們是同一個東西的兩個面：

```
aevum-mcp-server (單一 Rust binary, ~5 MiB RSS)
├── Tool: aevum_filter        → Paperclip 場景（Token 降本）
├── Tool: aevum_settle         → Paperclip 場景（焦耳結算）
├── Tool: aevum_remember       → claude-mem 場景（因果記憶寫入）
├── Tool: aevum_recall         → claude-mem 場景（因果記憶讀取）
└── Resource: aevum_context    → 兩個場景共用（當前因果狀態摘要）
```

### 為什麼統一而非分離

因為兩個場景共享同一個底層：

- Paperclip 的 agent 每次調用 LLM → 需要 `aevum_filter` 做 Sₜ/Hₜ 預篩 → 產生 PACR 記錄
- 同一個 agent 下次執行任務 → 需要 `aevum_recall` 找回上次的因果狀態 → 讀取的就是上次 `aevum_filter` 產生的 PACR 記錄

**記憶和過濾是同一條因果鏈的寫入端和讀取端。** 分開做兩個 server 會導致因果帳本碎片化。

---

## aevum-mcp-server 的核心設計

### Tool 1: `aevum_remember`（替代 claude-mem 的 SQLite 寫入）

```rust
// 輸入：Claude 的動作描述（自然語言）
// 處理：
//   1. quick_screen: O(1) Shannon 熵預篩 → 純噪音直接丟棄
//   2. ε-engine: 對非噪音內容做 CSSR → 提取 (Sₜ, Hₜ)
//   3. 生成 PACR 記錄：ι=新ID, Π=上一條記錄, Λ=本次計算成本, Γ=(Sₜ,Hₜ), P=壓縮後的狀態增量
//   4. 追加到本地因果 DAG（記憶體內）
//   5. 異步寫入 NAS（持久化）
// 輸出：{ recorded: true, causal_id: "...", s_t: 0.82, h_t: 0.15 }
```

**vs claude-mem：** claude-mem 把完整的動作文本存進 SQLite。aevum 只存因果指標 + 壓縮狀態增量。空間佔用差 10-100 倍。

### Tool 2: `aevum_recall`（替代 claude-mem 的「讓 Claude 自己總結歷史」）

```rust
// 輸入：當前任務的描述（用於相關性匹配）
// 處理：
//   1. 對輸入做 CSSR → 得到當前任務的因果狀態特徵
//   2. 在本地 DAG 中搜索 Sₜ 最相似的歷史節點（O(log n) via BTreeMap）
//   3. 沿 Π 邊回溯因果鏈，收集相關的狀態增量
//   4. 將狀態增量組裝為結構化上下文（NOT 自然語言總結，而是因果狀態矩陣）
// 輸出：{ context: "因果狀態描述（結構化）", relevant_records: [...], confidence: 0.91 }
```

**vs claude-mem：** claude-mem 把所有歷史記錄扔給 Claude 讓它「自己挑重要的」——這消耗大量 token 且引入幻覺。aevum 在 Rust 端用 CSSR 數學確定性地提取相關因果狀態，零 token 成本，零幻覺。

### Tool 3 & 4: `aevum_filter` + `aevum_settle`（Paperclip 場景，已在之前定義）

### Resource: `aevum_context`（MCP Resource 機制）

MCP 允許 Server 暴露 Resource（靜態或動態的上下文信息）。`aevum_context` 提供當前因果狀態的自動摘要，Claude 在每次對話開始時自動讀取：

```
URI: aevum://context/current
Content: "Current causal state: 47 records, Sₜ trend: StructureDiscovery, 
          Φ: 0.003 J/s, last significant event: [causal_id], 
          top-3 relevant past states: [...]"
```

這替代了 claude-mem 的「自動注入歷史 prompt」，但只注入因果狀態摘要（~200 tokens）而非完整歷史（~10,000+ tokens）。

---

## 與現有系統的對齊

|組件|來自哪個 Phase|用途|
|---|---|---|
|PACR 六元組|Phase 0|記憶記錄的格式|
|因果 DAG|Phase 1|記憶的拓撲結構（Π 邊）|
|ε-engine + quick_screen|Phase 3|記憶的壓縮和檢索（Sₜ/Hₜ）|
|Landauer-on-Drop|Phase 5|記憶操作的物理成本計量（Λ）|
|AgentCard|Phase 6|agent 身份（Paperclip org chart 中的節點）|
|ρ 因果回報率|Phase 7|記憶的價值評估（哪些記憶真正降低了 Φ）|

**不需要新的 Phase。** aevum-mcp-server 是現有 Phase 0-7 代碼的 MCP 封裝層——它不包含新的物理邏輯，只包含 MCP JSON-RPC 協議的序列化/反序列化和 Tool 路由。

---

## 執行建議

```
Week 1（4/18 後）：
  scaffolding: cargo new aevum-mcp-server
  實現 MCP JSON-RPC over stdio（標準 MCP 協議）
  實現 aevum_remember + aevum_recall（最小可用）
  接入本地 Claude Desktop 測試

Week 2：
  追加 aevum_filter + aevum_settle
  接入 Paperclip 測試
  benchmark: vs claude-mem 的記憶體佔用、token 成本、檢索精度

Week 3：
  發布到 MCP Registry（如果存在）或 GitHub
  README 中用 benchmark 數據說話：
  "10 MiB vs 100 MiB, 0 tokens vs 10,000 tokens, 數學確定性 vs 語義漂移"
```

---

**一句話：Paperclip 和 claude-mem 不是兩個獨立的殺手應用——它們是同一個 `aevum-mcp-server` 的兩個 Tool 接口。Paperclip 的 agent 用 `aevum_filter` 省 token 費，用 `aevum_settle` 做焦耳結算；開發者用 `aevum_remember/recall` 替代 SQLite + LLM 自我總結。底層共享同一條因果 DAG、同一套 PACR 記錄、同一個 ε-engine。一個 binary，兩個市場，零代碼重複。**