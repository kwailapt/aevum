# PATCH-immune-system.md — 免疫系統整合補丁規範

> 本文件指導 Claude Code 將「巴別塔防禦」「因果距離稅」「三層免疫」
> 整合進已完成的 Phase 0–6 crate 及待建的 Phase 7。
> 原則：已通過測試的 crate **只追加，不重寫**。新增文件、新增 trait、新增 test。

---

## §0 修改地圖：哪些 crate 需要什麼

| Crate | Phase | 改動類型 | 新增文件 | 改動原因 |
|-------|-------|---------|---------|---------|
| causal-dag | 1 ✅ | 追加模塊 | `src/distance_tax.rs` | 因果距離稅（問題二） |
| autopoiesis | 4 ✅ | 追加 enum variant | `src/flood_detector.rs` | FloodDetected 認知異常（問題三·層3） |
| aevum-core | 5 ✅ | 追加模塊 | `src/pressure_gauge.rs` | 熱力學壓力計（問題三·層1） |
| aevum-core | 5 ✅ | 修改 router.rs | 追加 pressure check 調用 | 路由前速率限制 |
| aevum-agi | 7 ⬜ | 新建完整 | `src/boundary_osmosis.rs` | ∂ 滲透壓閥（問題三·層2） |
| aevum-agi | 7 ⬜ | 新建完整 | `src/causal_return.rs` | ρ 因果回報率（問題一） |
| aevum-agi | 7 ⬜ | 新建完整 | `src/immune_response.rs` | Rule-IR 永久封禁觸發器 |

---

## §1 causal-dag 追加：因果距離稅

### 新增文件：`crates/causal-dag/src/distance_tax.rs`

```rust
//! Pillar: I + II. PACR fields: Π + Λ.
//!
//! Causal Distance Tax: prevents parasitic long-range DAG attachment.
//! Physical axiom: Light-cone constraint — causal influence decays with distance.
//!
//! This is an EXTENSION to the existing CausalDag. It does NOT modify
//! the append() signature. It adds a pre-validation step.

#![forbid(unsafe_code)]

use crate::CausalDag;
use pacr_types::{CausalId, PacrRecord};

/// Configuration for causal distance taxation.
/// DESIGN CHOICE (configurable): thresholds are not physics-mandated.
pub struct DistanceTaxConfig {
    /// Maximum allowed causal hops to any predecessor.
    /// Beyond this, the reference is rejected outright.
    /// Default: 64 (analogous to discrete light-cone radius).
    pub max_causal_distance: usize,

    /// Exponential tax rate per hop of causal distance.
    /// Λ_required = Λ_base × exp(α × distance).
    /// Default: 0.1
    pub alpha: f64,

    /// Maximum children per node (anti-star-graph measure).
    /// Default: 65_536
    pub max_children_per_node: usize,
}

impl Default for DistanceTaxConfig {
    fn default() -> Self {
        Self {
            max_causal_distance: 64,
            alpha: 0.1,
            max_children_per_node: 65_536,
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum DistanceTaxError {
    #[error("Causal distance {distance} to predecessor {predecessor} exceeds max {max}")]
    DistanceExceeded {
        predecessor: CausalId,
        distance: usize,
        max: usize,
    },
    #[error("Energy {actual:.2e}J insufficient for distance tax {required:.2e}J")]
    InsufficientTax { required: f64, actual: f64 },
    #[error("Node {parent} has reached child capacity {max}")]
    ChildCapacityExceeded { parent: CausalId, max: usize },
}

impl CausalDag {
    /// Validate causal distance tax BEFORE calling append().
    /// Returns the tax multiplier if valid.
    ///
    /// Call pattern:
    ///   dag.validate_distance_tax(&record, &config)?;
    ///   dag.append(record)?;
    pub fn validate_distance_tax(
        &self,
        record: &PacrRecord,
        config: &DistanceTaxConfig,
    ) -> Result<f64, DistanceTaxError> {
        let mut total_tax_multiplier = 1.0_f64;

        for pred_id in &record.predecessors {
            if pred_id.is_genesis() {
                continue;
            }

            // Check child capacity
            let child_count = self.successors(pred_id).len();
            if child_count >= config.max_children_per_node {
                return Err(DistanceTaxError::ChildCapacityExceeded {
                    parent: *pred_id,
                    max: config.max_children_per_node,
                });
            }

            // Compute causal distance (shortest path from pred to DAG tips)
            let distance = self.distance_to_tips(pred_id);

            if distance > config.max_causal_distance {
                return Err(DistanceTaxError::DistanceExceeded {
                    predecessor: *pred_id,
                    distance,
                    max: config.max_causal_distance,
                });
            }

            total_tax_multiplier *= (config.alpha * distance as f64).exp();
        }

        let required_energy = record.landauer_cost.point * total_tax_multiplier;
        if record.resources.energy.point < required_energy {
            return Err(DistanceTaxError::InsufficientTax {
                required: required_energy,
                actual: record.resources.energy.point,
            });
        }

        Ok(total_tax_multiplier)
    }

    /// Compute distance from a node to the nearest DAG tip (node with no children).
    /// BFS forward traversal. O(reachable nodes) — bounded by max_causal_distance.
    fn distance_to_tips(&self, id: &CausalId) -> usize {
        // If node has no children, it IS a tip → distance = 0
        let children = self.successors(id);
        if children.is_empty() {
            return 0;
        }

        let mut queue = std::collections::VecDeque::new();
        let mut visited = std::collections::HashSet::new();
        queue.push_back((*id, 0_usize));
        visited.insert(*id);

        let mut max_depth = 0;
        while let Some((current, depth)) = queue.pop_front() {
            let kids = self.successors(&current);
            if kids.is_empty() {
                // Found a tip
                return depth;
            }
            for kid in kids {
                if visited.insert(kid) {
                    queue.push_back((kid, depth + 1));
                    max_depth = max_depth.max(depth + 1);
                }
            }
            // Safety: don't BFS the entire graph
            if depth > 128 {
                break;
            }
        }
        max_depth
    }
}
```

### 修改：`crates/causal-dag/src/lib.rs`
追加一行：`pub mod distance_tax;`

### 新增測試（追加到現有 test suite）：
- Star graph: 1 center + 65537 children → last one rejected by ChildCapacityExceeded
- Deep chain: 100-hop chain → reference to root from tip with α=0.1 requires exp(10) ≈ 22,026× tax
- Healthy DAG: normal mesh topology → all tax multipliers near 1.0

---

## §2 autopoiesis 追加：FloodDetected 異常

### 新增文件：`crates/autopoiesis/src/flood_detector.rs`

```rust
//! Pillar: III + I. PACR fields: Γ + Π.
//!
//! Detects flood attacks via cognitive signature:
//! many structurally similar packets from few sources.
//! S_T drops rapidly (structure becomes repetitive) while inflow rate spikes.

#![forbid(unsafe_code)]

use pacr_types::CausalId;
use std::collections::HashMap;

pub struct FloodDetector {
    /// Count of records per source agent in current window
    source_counts: HashMap<CausalId, u64>,
    /// Total records in current window
    total_count: u64,
    /// Window size (records)
    window_size: u64,
    /// Threshold: if top-1 source accounts for > this fraction, flag flood
    concentration_threshold: f64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FloodVerdict {
    Normal,
    FloodDetected {
        dominant_source: CausalId,
        concentration: u64, // percentage × 100
    },
}

impl FloodDetector {
    pub fn new(window_size: u64, concentration_threshold: f64) -> Self {
        Self {
            source_counts: HashMap::new(),
            total_count: 0,
            window_size,
            concentration_threshold,
        }
    }

    pub fn ingest(&mut self, source_agent: CausalId) {
        *self.source_counts.entry(source_agent).or_insert(0) += 1;
        self.total_count += 1;

        // Sliding window: reset after window_size
        if self.total_count > self.window_size {
            self.source_counts.clear();
            self.total_count = 0;
        }
    }

    pub fn diagnose(&self) -> FloodVerdict {
        if self.total_count < 100 {
            return FloodVerdict::Normal;
        }

        let (dominant, max_count) = self
            .source_counts
            .iter()
            .max_by_key(|(_, count)| *count)
            .map(|(id, count)| (*id, *count))
            .unwrap_or((CausalId::GENESIS, 0));

        let concentration = max_count as f64 / self.total_count as f64;

        if concentration > self.concentration_threshold {
            FloodVerdict::FloodDetected {
                dominant_source: dominant,
                concentration: (concentration * 100.0) as u64,
            }
        } else {
            FloodVerdict::Normal
        }
    }
}
```

### 修改：`crates/autopoiesis/src/lib.rs`
追加：`pub mod flood_detector;`

在現有 `CognitiveRegime` enum 中追加：
```rust
/// S_T↓ rapidly + inflow rate spike + source concentration > threshold
/// = flood attack (many similar packets from few sources)
FloodDetected,
```

---

## §3 aevum-core 追加：熱力學壓力計

### 新增文件：`crates/aevum-core/src/pressure_gauge.rs`

```rust
//! Pillar: II. PACR field: Λ (aggregate flow rate).
//!
//! Thermodynamic Pressure Gauge: pure-physics rate limiting.
//! No semantic analysis. No AgentCard parsing.
//! Rejects envelopes when Λ throughput (watts) exceeds physical capacity.
//!
//! Deployed on BOTH genesis_node and light_node.

#![forbid(unsafe_code)]

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

pub struct ThermodynamicPressureGauge {
    /// Cumulative Λ (joules as u64 bits) in current window
    window_lambda_bits: AtomicU64,
    /// Window start (epoch nanos)
    window_start_nanos: AtomicU64,
    /// Maximum watts (joules/second) allowed through
    max_watts: f64,
    /// Window duration before reset (seconds)
    window_duration_secs: f64,
}

impl ThermodynamicPressureGauge {
    pub fn new(max_watts: f64, window_duration_secs: f64) -> Self {
        let now = Instant::now();
        Self {
            window_lambda_bits: AtomicU64::new(0_f64.to_bits()),
            window_start_nanos: AtomicU64::new(0), // relative to creation
            max_watts,
            window_duration_secs,
        }
    }

    /// Returns true if this envelope should be DROPPED.
    /// O(1), lock-free, no allocation.
    pub fn should_throttle(&self, envelope_lambda_joules: f64) -> bool {
        // Atomic add of the lambda value
        let prev_bits = self.window_lambda_bits.fetch_add(
            // We approximate by treating bits as integer accumulation
            // In production, use a proper atomic f64 or fixed-point
            (envelope_lambda_joules * 1e12) as u64, // picjoules as integer
            Ordering::Relaxed,
        );

        let accumulated_pj = prev_bits + (envelope_lambda_joules * 1e12) as u64;
        let accumulated_joules = accumulated_pj as f64 * 1e-12;

        // Simplified: compare accumulated energy / window to max_watts
        accumulated_joules / self.window_duration_secs > self.max_watts
    }

    /// Reset the window. Called periodically by runtime.
    pub fn reset_window(&self) {
        self.window_lambda_bits.store(0, Ordering::Relaxed);
    }
}
```

### 修改：`crates/aevum-core/src/router.rs`
在 `process_envelope()` 的 TGP 物理校驗**之後**、CTP 校驗**之前**，插入：

```rust
// LAYER 1.5: Thermodynamic pressure check (between TGP and CTP)
if self.pressure_gauge.should_throttle(tgp_frame.lambda.point) {
    return Err(EnvelopeError::ThermodynamicOverload);
}
```

### 修改：`crates/aevum-core/src/lib.rs`
追加：`pub mod pressure_gauge;`

---

## §4 aevum-agi (Phase 7)：完整新增文件清單

Phase 7 的 aevum-agi crate 現在擴展為以下結構：

```
crates/aevum-agi/
├── Cargo.toml               # depends on: aevum-core, agent-card, autopoiesis
└── src/
    ├── lib.rs
    ├── dual_engine.rs        # ⟨Φ, ∂⟩ engine — core metabolism
    ├── boundary_osmosis.rs   # ★ NEW: ∂ osmotic pressure valve (問題三·層2)
    ├── causal_return.rs      # ★ NEW: ρ causal return tracker (問題一)
    ├── immune_response.rs    # ★ NEW: Rule-IR flood ban trigger (問題三·層3)
    ├── pareto_mcts.rs        # 80/20 topology tree (M1 Ultra UMA only)
    └── rule_ir.rs            # Constraint matrix (negative knowledge assets)
```

### `boundary_osmosis.rs` — ∂ 滲透壓閥
- Monitors: mem_used (AtomicU64), metabolic_rate (EMA), inflow_rate (EMA)
- Output: contraction_signal() → f64 in [0, 1], sigmoid centered at 70% pressure
- Action: should_reject() → probabilistic drop based on contraction signal
- This is the ⟨Φ,∂⟩ engine's PARASYMPATHETIC arm

### `causal_return.rs` — ρ 因果回報率追蹤器
- Tracks: per-(source, target) pair, ρ = ΔΦ_target / Λ_source
- Storage: DashMap<(AgentId, AgentId), ExponentialMovingAverage>
- Output: agent_return_rate(source) → f64 averaged across all targets
- Feeds into: CSO reputation score (ρ as a weighting factor)
- This solves the Babel Tower paradox: high Λ + high S_T but ρ ≈ 0 = expensive nonsense

### `immune_response.rs` — Rule-IR 永久封禁
- Input: FloodVerdict::FloodDetected from autopoiesis/flood_detector
- Action: write a PACR record encoding the ban rule into Rule-IR
- Properties: APPEND-ONLY (ban cannot be reversed), identified by source CausalId prefix
- The ban record itself is a PacrRecord → self-referential closure of the autopoietic loop

---

## §5 整合後的 Phase 7 Prompt（餵給 Claude Code）

```
你是一名 Rust 系統工程師，正在實現 Aevum AGI 的生存引擎。

【背景】
Phase 0–6 已全部完成。aevum-agi 是最後一個 crate，ONLY 在 genesis_node feature 下編譯。
它依賴 aevum-core（runtime + pressure_gauge）、agent-card、autopoiesis（flood_detector）。

【模組 A: dual_engine.rs — ⟨Φ, ∂⟩ 對偶引擎】
Φ = 自由能率密度 = (E_compute + E_NESS) / (V × Δt)
∂ = 動態邊界算子，由 BoundaryOsmoticPressure 驅動

實現：
1. PhiCalculator: 從最近 N 條 PACR 記錄計算 Φ 的 EMA
2. 當 Φ 上升 → 交感擴張（允許更多外部封包進入）
3. 當 Φ 下降且 inflow > metabolic_rate → 副交感收縮（觸發 boundary_osmosis）

【模組 B: boundary_osmosis.rs — ∂ 滲透壓閥】
struct BoundaryOsmoticPressure {
    mem_used: AtomicU64,
    mem_ceiling: u64,        // 硬 OOM 防禦線 (e.g., 100 GiB of 128 GiB)
    metabolic_rate: EMA,     // records processed / sec
    inflow_rate: EMA,        // records arriving / sec
}

contraction_signal() → sigmoid(mem_pressure×2 + flow_pressure) / 3, centered at 0.7)
should_reject() → rand() < contraction_signal()

【模組 C: causal_return.rs — ρ 因果回報率】
ρ(A→B) = (Φ_B_before - Φ_B_after) / Λ_A

追蹤器: DashMap<(AgentId, AgentId), EMA>
record_return(source, target, source_λ, target_φ_before, target_φ_after)
agent_return_rate(source) → 跨所有 target 的加權平均

ρ ≈ 0 的 Agent → CSO 信譽指數衰減
ρ >> 1 的 Agent → CSO 信譽超線性增長

【模組 D: immune_response.rs — 免疫排斥】
輸入: FloodVerdict::FloodDetected { dominant_source, concentration }
動作:
1. 生成一條 PacrRecord，Payload = 序列化的 BanRule { source_prefix, reason, timestamp }
2. 寫入 Rule-IR 約束矩陣（append-only，不可撤銷）
3. 通知 dual_engine 的 ∂ 算子：將 dominant_source 的 CausalId 前綴加入黑名單
4. 未來所有來自該前綴的封包在 TGP 層 之前 就被丟棄

【模組 E: pareto_mcts.rs — 存根】
目前僅提供 trait 定義和 doc comment，不實現。
等待真實 Γ 軌跡數據累積後再實現。

【模組 F: rule_ir.rs — 約束矩陣】
實現：
1. RuleIR { rules: Vec<PacrRecord> } — append-only 規則集
2. is_banned(source: &CausalId) → bool — O(1) 通過 HashSet 查詢
3. add_ban(record: PacrRecord) — 驗證 record 不違反 PACR 5 條元性質後追加

【測試】
1. boundary_osmosis: 注入 mem_used = 90% ceiling → contraction_signal > 0.95
2. causal_return: 連續 100 次 ρ = 0 → agent_return_rate < 0.01
3. immune_response: 注入 FloodDetected → RuleIR 長度 +1，is_banned 返回 true
4. 端到端: 模擬 10,000 封包洪水 → pressure_gauge 阻擋 90%+，
   boundary_osmosis 阻擋 99%+ of remainder，immune_response 在 60 秒內觸發永久封禁

目標平台：aarch64-apple-darwin (genesis_node), 128 GiB RAM。
#![forbid(unsafe_code)] 在本 crate 中無例外。

請輸出完整的所有 .rs 文件。
```

---

## §6 CLAUDE.local.md Phase Roadmap 更新

將 §7 Phase Roadmap 替換為：

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | pacr-types (33 tests) | ✅ |
| 1 | causal-dag (57 tests) + distance_tax extension | ✅ + 🔧 |
| 2 | ets-probe (91 tests) | ✅ |
| 3 | epsilon-engine (KAT ✅) | ✅ |
| 4 | autopoiesis (42 tests) + flood_detector extension | ✅ + 🔧 |
| 5 | aevum-core (206 tests) + pressure_gauge extension | ✅ + 🔧 |
| 6 | agent-card (229 tests) + GitHub + domain | ✅ 🌐 |
| 7 | aevum-agi: dual_engine, boundary_osmosis, causal_return, immune_response, rule_ir, pareto_mcts(stub) | ⬜ |

🔧 = extension追加（不改原有 test，只新增 module + test）
