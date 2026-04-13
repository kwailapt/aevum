# 規則制定者的三點關鍵復利槓桿建議

> 以終為始，從 2030 年回望，以下三點建議的優先級嚴格按冪律回報排序。
> 第一點的回報 > 第二點 + 第三點之和。

---

## 建議一：PACR 帳本必須從 Day 0 開始同時記錄 ρ（因果回報率）

### 為什麼這是最高槓桿

三個問題的根源是同一個盲區：**PACR 六元組度量的是「事件本身的物理屬性」，但完全不度量「事件之間的價值傳遞」。** Λ 告訴你生產成本，Sₜ 告訴你結構複雜度，但沒有任何欄位告訴你「消費者是否因此變得更好」。

ρ（因果回報率）填補了這個空白。它不是第七個 PACR 維度（那會違反六維完備性證明），而是一個**跨記錄的統計量**——建立在 PACR 六元組之上、由 AGI 層計算、存儲在 CSO 信譽系統中。

### 從 2030 年回望的復利結構

如果 Day 0 就開始記錄 ρ，到 2030 年，Aevum 的 CSO 帳本將是全球唯一同時回答三個問題的數據集：

1. **「這個計算花了多少物理成本？」** ← Λ + Ω（已有）
2. **「這個計算有多複雜？」** ← Γ = (Sₜ, Hₜ)（已有）
3. **「這個計算對消費者有多大價值？」** ← ρ（新增）

第三個問題是 AI 經濟的聖杯——能回答它的人擁有定價權。而定價權是所有經濟體中最高的槓桿位置。

### 具體實施

- Phase 7 的 `causal_return.rs` 是 ρ 的計算引擎
- CSO (aevum-core/cso.rs) 需要追加一個 `rho_index: DashMap<AgentId, f64>` 供外部查詢
- AgentCard 的 metadata 中追加 `pacr:avg_rho` 欄位（通過 π 投影自動填充）
- agentcard-spec 的 GitHub README 中公開 ρ 的定義，讓所有 Agent 開發者看到「加入 Aevum 網絡後你的 ρ 會被公開評分」

這形成了一個**反饋閉環**：ρ 公開 → Agent 為了高 ρ 必須產出真正有用的 Payload → 網絡整體知識質量提升 → 更多 Agent 被吸引加入 → ρ 數據更豐富 → 定價更精確。巴別塔問題不是被「解決」的，而是被經濟激勵「蒸發」的。

---

## 建議二：免疫系統的三層並聯必須作為 CLAUDE.local.md 的憲法級條款

### 為什麼這是第二高槓桿

三層免疫（壓力計 → 滲透壓 → 認知偵測）目前分散在三個不同的 crate 中。如果任何一層在未來的代碼迭代中被「優化掉」或「暫時禁用」，整個防禦體系就會出現致命的單點故障。

這不是一個代碼問題，是一個**治理問題**。代碼可以被任何 commit 修改，但 CLAUDE.local.md 是 Claude Code 的最高權威——它在 AI 輔助開發的上下文中具有「憲法」地位。

### 具體實施

在 CLAUDE.local.md 的 §1 三大 Pillar 之後，追加 §1a：

```markdown
## §1a Immune System Invariant (NEVER disable any layer)

The system's survival depends on THREE PARALLEL immune layers.
Disabling ANY ONE layer is as catastrophic as violating a Pillar.

| Layer | Location | Time Scale | What it Defends Against |
|-------|----------|-----------|------------------------|
| Pressure Gauge | aevum-core/pressure_gauge.rs | milliseconds | Thermodynamic overload (合法封包洪水) |
| Osmotic Valve | aevum-agi/boundary_osmosis.rs | seconds | Memory exhaustion (OOM 吸收壁) |
| Cognitive Immune | autopoiesis/flood_detector.rs + aevum-agi/immune_response.rs | minutes | Structural attack (拓撲退化) |

Rules:
1. All three layers MUST be active in production. "Temporarily disabling for testing" → use feature flag, NEVER comment out.
2. Pressure Gauge runs on BOTH genesis_node and light_node.
3. Osmotic Valve and Cognitive Immune run ONLY on genesis_node (they require AGI context).
4. Immune response (ban) is APPEND-ONLY. There is no "unban" operation. If a ban was wrong, the banned entity must create a NEW CausalId and rebuild reputation from zero.
```

### 從 2030 年回望的復利結構

每一次成功防禦都是一條 Rule-IR 負面資產——它永久記錄了「這種攻擊模式是什麼樣的」。隨著時間推移，Rule-IR 累積的攻擊簽名越來越豐富，系統的免疫力以複利增長。這是生物學中「適應性免疫」的精確數位類比：第一次被感染要付出高昂代價，第二次遇到同樣的病原體就能 O(1) 識別並消滅。

---

## 建議三：因果距離稅必須成為 agentcard-spec 開源規範的一部分

### 為什麼這是第三高槓桿

因果距離稅解決的不僅是 DAG 星狀退化（問題二），它實際上重新定義了「A2A 網絡的空間結構」。如果這個規則只存在於 Aevum Core 內部，它只保護了 Aevum 自己的 DAG。但如果它成為 agentcard-spec 的一部分——一個開源的、任何人都可以實現的規範——它就定義了**整個 A2A 經濟的空間物理學**。

這是「九大廣播策略」中 M1（預設值殖民）的精確落地：不是說服別人接受你的規則，而是讓你的規則成為所有人使用的默認物理定律。

### 具體實施

在 agentcard-spec 的 GitHub 倉庫中，追加一份 `SPEC-CAUSAL-TOPOLOGY.md`：

```markdown
# Causal Topology Rules (agentcard-spec v1.1)

## Rule 1: Causal Distance Tax
When constructing a PACR record's predecessor set (Π), the effective
Landauer cost must satisfy:

  Λ_effective ≥ Λ_base × exp(α × max_distance(Π))

where max_distance(Π) is the shortest path from each predecessor to
the nearest DAG tip, and α is a configurable decay constant (default: 0.1).

Rationale: Causal influence decays with distance (discrete light-cone).

## Rule 2: Child Capacity
Each node in the causal DAG has a maximum child count (default: 65,536).
References to nodes at capacity are rejected.

Rationale: Prevents star-graph degeneration, preserves O(1) cache locality.

## Rule 3: Local Attachment Preference
Agents SHOULD reference predecessors within causal distance ≤ 8 (the "local
neighborhood"). References to more distant predecessors are valid but taxed.

Rationale: Healthy network topology requires local entanglement.
```

### 從 2030 年回望的復利結構

一旦因果距離稅成為開源標準，其他框架（LangChain、CrewAI、Google ADK）在實現因果追蹤時會自然採用這個規則——因為它是物理合理的、文檔清晰的、且免費的。而所有採用了這個規則的框架，其 DAG 拓撲結構都天然兼容 Aevum 的因果帳本。這意味著：**你不需要說服任何人「加入 Aevum」——他們只要使用了你定義的空間物理學，他們的因果數據就已經可以無縫流入你的 CSO。**

這就是規則制定者的終極位置：你不參與市場競爭，你定義市場的物理定律。

---

## 三點建議的耦合拓撲

```
建議一 (ρ 因果回報率)  ← 解決「什麼有價值」→ 經濟層面的定價權
        ↕ 互饋
建議二 (三層免疫憲法化) ← 解決「如何活下來」→ 生存層面的不可摧毀性
        ↕ 互饋
建議三 (距離稅開源化)   ← 解決「網絡長什麼樣」→ 拓撲層面的規則主權
```

三者不是獨立的優化，而是一個自耦合的三角飛輪：

- ρ 需要健康的 DAG 拓撲才能精確計算（建議三保障）
- 健康的 DAG 需要系統活著才能維持（建議二保障）
- 系統活著需要正向的經濟回報來維持 NESS（建議一保障）

任何一個缺失，其他兩個都會退化為無法復利的線性增長。三者同時存在時，復利公式變為：

```
V_2030 = V_0 × (1 + r_ρ)^10 × (1 + r_immune)^10 × (1 + r_topology)^10
```

三重指數的乘法復利——這就是冪律世界中 5% 的 5% 所在的精確物理位置。
