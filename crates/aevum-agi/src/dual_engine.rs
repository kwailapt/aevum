//! Pillar: II + III. PACR field: Γ, Λ.
//!
//! **⟨Φ, ∂⟩ Dual Engine** — reads the TGP cognitive state (Γ) and adjusts the
//! AGI boundary.
//!
//! # Theory
//!
//! The dual engine implements two coupled operations denoted ⟨Φ, ∂⟩:
//!
//! ## Φ — Integrated Information Measure
//!
//! Φ is a scalar derived from the current PACR cognitive split (Γ):
//!
//! ```text
//! Φ = S_T × (S_T / H_T)        when H_T > ε
//!   = S_T × S_T_hi_ceiling     when H_T ≤ ε  (entropy collapsed — highly structured)
//! ```
//!
//! `S_T` (statistical complexity) measures how much causal structure the system
//! has discovered.  `H_T` (entropy rate) measures residual unpredictability.
//! Their ratio `S_T / H_T` is the **Γ-ratio**: values > 1 mean the system is
//! extracting more structure than it leaves unexplained.
//!
//! Φ is high when the system has built rich internal models (high S_T) while
//! successfully compressing its environment (low H_T).  This is the signature
//! of genuine intelligence as defined in Pillar III.
//!
//! ## ∂ — Boundary Adjustment
//!
//! ∂ maps a Φ trajectory to a `BoundaryAdjustment`:
//!
//! ```text
//! dΦ/dt > 0  →  ExpandBoundary   (Φ is growing; explore more)
//! dΦ/dt ≈ 0  →  HoldBoundary     (stable NESS; maintain current regime)
//! dΦ/dt < 0  →  ContractBoundary (Φ declining; reduce exposure to entropy)
//! ```
//!
//! The boundary controls how aggressively the system expands into new causal
//! territory — specifically, how many new PACR records the runtime produces per
//! tick (`producer_interval_ms` and `epsilon_window` in `RuntimeConfig`).
//!
//! # Phase 7 Stub Status
//!
//! This is the Phase 7 stub.  The full ⟨Φ,∂⟩ engine (Phase 8) will:
//! - Compute Φ from the live DAG ancestry (not just the latest status snapshot)
//! - Compute ∂ via a second-order ODE integrator fed by the `GammaCalculator`
//! - Feed boundary adjustments back to `RuntimeConfig` via `mpsc::Sender`
//! - Log every boundary adjustment as a PACR record with `Π` linking back to
//!   the observations that triggered it (self-referential causal closure)
//!
//! For now, `DualEngine::step()` computes Φ from a `DualEngineSnapshot` and
//! returns the correct `BoundaryAdjustment` variant — all internal logic is
//! present; only the live-DAG integration is deferred.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};

// ── Configuration ─────────────────────────────────────────────────────────────

/// Configuration thresholds for the ⟨Φ,∂⟩ dual engine.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DualEngineConfig {
    /// Entropy floor ε below which H_T is treated as "structurally collapsed".
    ///
    /// When H_T ≤ `entropy_floor`, Φ uses `s_t_ceiling` as the effective
    /// entropy denominator to avoid division by zero.
    pub entropy_floor: f64,

    /// S_T ceiling applied when H_T ≤ `entropy_floor`.
    ///
    /// Prevents Φ from diverging when the environment is perfectly predictable.
    pub s_t_ceiling: f64,

    /// Minimum |dΦ/dt| magnitude considered "significant" (not steady-state).
    ///
    /// Differences smaller than this threshold are classified as `HoldBoundary`.
    pub delta_phi_threshold: f64,
}

impl Default for DualEngineConfig {
    fn default() -> Self {
        Self {
            entropy_floor:       1e-6,
            s_t_ceiling:         100.0,
            delta_phi_threshold: 0.01,
        }
    }
}

// ── Snapshot ──────────────────────────────────────────────────────────────────

/// One observation fed to the dual engine at each step.
///
/// Populated from `RuntimeStatus` produced by `aevum-core`'s runtime.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DualEngineSnapshot {
    /// Latest statistical complexity C_μ (Γ.S_T).  Non-negative.
    pub statistical_complexity: f64,

    /// Latest entropy rate h_μ (Γ.H_T).  Non-negative.
    pub entropy_rate: f64,

    /// Cumulative bits erased since process start (Landauer accounting).
    pub bits_erased: u64,

    /// Total PACR records produced so far.
    pub record_count: u64,
}

// ── Boundary Adjustment ───────────────────────────────────────────────────────

/// The ∂ output: how the engine wants to adjust the AGI boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BoundaryAdjustment {
    /// Φ is growing — increase exploration rate.
    ///
    /// Concretely: decrease `producer_interval_ms` and/or increase
    /// `epsilon_window` in `RuntimeConfig`.
    ExpandBoundary,

    /// Φ is stable — maintain the current NESS operating point.
    HoldBoundary,

    /// Φ is declining — reduce exposure to entropy sources.
    ///
    /// Concretely: increase `producer_interval_ms` and/or decrease
    /// `epsilon_window` to reduce cognitive load.
    ContractBoundary,
}

// ── Status ────────────────────────────────────────────────────────────────────

/// Current state of the dual engine after a `step()` call.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DualEngineStatus {
    /// Computed integrated information measure Φ for the latest step.
    pub phi: f64,

    /// Previous Φ value (used to compute dΦ/dt).
    ///
    /// `None` before the second call to `step()`.
    pub prev_phi: Option<f64>,

    /// Boundary adjustment emitted by this step.
    pub adjustment: BoundaryAdjustment,

    /// Total number of `step()` calls since construction.
    pub step_count: u64,
}

// ── DualEngine ────────────────────────────────────────────────────────────────

/// The ⟨Φ,∂⟩ dual engine.
///
/// Maintains a running Φ estimate and emits `BoundaryAdjustment` decisions
/// on each step based on the direction of change in Φ.
///
/// # Example (stub usage)
///
/// ```rust
/// # #[cfg(feature = "genesis_node")]
/// # {
/// use aevum_agi::dual_engine::{DualEngine, DualEngineConfig, DualEngineSnapshot};
///
/// let mut engine = DualEngine::new(DualEngineConfig::default());
///
/// // Step 1 — only one snapshot, so no delta yet → HoldBoundary
/// let snap1 = DualEngineSnapshot { statistical_complexity: 1.5, entropy_rate: 0.8,
///     bits_erased: 100_000, record_count: 10 };
/// let status1 = engine.step(snap1);
/// assert!(status1.prev_phi.is_none());
///
/// // Step 2 — Φ grew → ExpandBoundary
/// let snap2 = DualEngineSnapshot { statistical_complexity: 2.0, entropy_rate: 0.7,
///     bits_erased: 200_000, record_count: 20 };
/// let status2 = engine.step(snap2);
/// assert!(status2.prev_phi.is_some());
/// # }
/// ```
pub struct DualEngine {
    cfg:        DualEngineConfig,
    prev_phi:   Option<f64>,
    step_count: u64,
}

impl DualEngine {
    /// Construct a new dual engine with the given configuration.
    #[must_use]
    pub fn new(cfg: DualEngineConfig) -> Self {
        Self {
            cfg,
            prev_phi:   None,
            step_count: 0,
        }
    }

    /// Process one snapshot observation.
    ///
    /// Computes Φ from the snapshot's `statistical_complexity` and
    /// `entropy_rate` fields, then derives the boundary adjustment from
    /// the sign of `Φ_current − Φ_prev`.
    ///
    /// # Returns
    ///
    /// A [`DualEngineStatus`] containing the new Φ, the previous Φ (if any),
    /// the `BoundaryAdjustment`, and the running step count.
    #[must_use]
    pub fn step(&mut self, snap: DualEngineSnapshot) -> DualEngineStatus {
        self.step_count += 1;

        let phi = self.compute_phi(snap.statistical_complexity, snap.entropy_rate);
        let adjustment = self.compute_adjustment(phi);

        let status = DualEngineStatus {
            phi,
            prev_phi:   self.prev_phi,
            adjustment,
            step_count: self.step_count,
        };

        self.prev_phi = Some(phi);
        status
    }

    /// Reset the engine's Φ history without changing configuration.
    pub fn reset(&mut self) {
        self.prev_phi   = None;
        self.step_count = 0;
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    /// Compute Φ = S_T × (S_T / H_T_effective).
    fn compute_phi(&self, s_t: f64, h_t: f64) -> f64 {
        let h_eff = if h_t <= self.cfg.entropy_floor {
            // Entropy has collapsed — use ceiling to bound Φ
            self.cfg.s_t_ceiling
        } else {
            h_t
        };
        s_t * (s_t / h_eff)
    }

    /// Derive BoundaryAdjustment from the direction of change in Φ.
    fn compute_adjustment(&self, phi_now: f64) -> BoundaryAdjustment {
        let Some(phi_prev) = self.prev_phi else {
            // First observation: no delta available — hold boundary
            return BoundaryAdjustment::HoldBoundary;
        };

        let delta = phi_now - phi_prev;

        if delta > self.cfg.delta_phi_threshold {
            BoundaryAdjustment::ExpandBoundary
        } else if delta < -self.cfg.delta_phi_threshold {
            BoundaryAdjustment::ContractBoundary
        } else {
            BoundaryAdjustment::HoldBoundary
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(s_t: f64, h_t: f64) -> DualEngineSnapshot {
        DualEngineSnapshot {
            statistical_complexity: s_t,
            entropy_rate:           h_t,
            bits_erased:            0,
            record_count:           0,
        }
    }

    // ── Φ computation ─────────────────────────────────────────────────────────

    #[test]
    fn phi_normal_case() {
        let engine = DualEngine::new(DualEngineConfig::default());
        // Φ = 2.0 × (2.0 / 1.0) = 4.0
        let phi = engine.compute_phi(2.0, 1.0);
        assert!((phi - 4.0).abs() < 1e-10, "phi={phi}");
    }

    #[test]
    fn phi_uses_ceiling_when_h_t_at_floor() {
        let cfg = DualEngineConfig { entropy_floor: 1e-6, s_t_ceiling: 10.0, ..Default::default() };
        let engine = DualEngine::new(cfg);
        // H_T = 0 ≤ floor → h_eff = 10.0, Φ = 3.0 × (3.0 / 10.0) = 0.9
        let phi = engine.compute_phi(3.0, 0.0);
        assert!((phi - 0.9).abs() < 1e-10, "phi={phi}");
    }

    #[test]
    fn phi_zero_s_t_is_zero() {
        let engine = DualEngine::new(DualEngineConfig::default());
        let phi = engine.compute_phi(0.0, 1.0);
        assert_eq!(phi, 0.0);
    }

    // ── First step holds boundary ─────────────────────────────────────────────

    #[test]
    fn first_step_holds_boundary() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let status = engine.step(snap(1.5, 0.8));
        assert_eq!(status.adjustment, BoundaryAdjustment::HoldBoundary);
        assert!(status.prev_phi.is_none());
        assert_eq!(status.step_count, 1);
    }

    // ── Boundary adjustments ──────────────────────────────────────────────────

    #[test]
    fn growing_phi_expands_boundary() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let _ = engine.step(snap(1.0, 1.0)); // Φ = 1.0
        let status = engine.step(snap(2.0, 1.0)); // Φ = 4.0, delta = +3.0
        assert_eq!(status.adjustment, BoundaryAdjustment::ExpandBoundary);
    }

    #[test]
    fn shrinking_phi_contracts_boundary() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let _ = engine.step(snap(2.0, 1.0)); // Φ = 4.0
        let status = engine.step(snap(1.0, 1.0)); // Φ = 1.0, delta = -3.0
        assert_eq!(status.adjustment, BoundaryAdjustment::ContractBoundary);
    }

    #[test]
    fn stable_phi_holds_boundary() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let _ = engine.step(snap(2.0, 1.0)); // Φ = 4.0
        let status = engine.step(snap(2.0, 1.0)); // Φ = 4.0, delta = 0.0
        assert_eq!(status.adjustment, BoundaryAdjustment::HoldBoundary);
    }

    #[test]
    fn delta_below_threshold_holds_boundary() {
        let cfg = DualEngineConfig { delta_phi_threshold: 0.5, ..Default::default() };
        let mut engine = DualEngine::new(cfg);
        let _ = engine.step(snap(2.0, 1.0)); // Φ = 4.0
        // Phi increases by ~0.1 — below threshold of 0.5
        let status = engine.step(snap(2.025, 1.0)); // Φ ≈ 4.1
        assert_eq!(status.adjustment, BoundaryAdjustment::HoldBoundary);
    }

    // ── Step count and prev_phi ─���──────────────────────────────────────────────

    #[test]
    fn step_count_increments() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        for i in 1..=5_u64 {
            let status = engine.step(snap(1.0, 1.0));
            assert_eq!(status.step_count, i);
        }
    }

    #[test]
    fn prev_phi_set_after_second_step() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let _ = engine.step(snap(1.0, 1.0));
        let status = engine.step(snap(2.0, 1.0));
        assert!(status.prev_phi.is_some());
    }

    // ── Reset ─────────────────────────────────────────────────────────────────

    #[test]
    fn reset_clears_history() {
        let mut engine = DualEngine::new(DualEngineConfig::default());
        let _ = engine.step(snap(2.0, 1.0));
        engine.reset();
        let status = engine.step(snap(2.0, 1.0));
        assert!(status.prev_phi.is_none());
        assert_eq!(status.step_count, 1);
    }

    // ── Serde roundtrip ───────────────────────────────────────────────────────

    #[test]
    fn status_serde_roundtrip() {
        let status = DualEngineStatus {
            phi:        3.14,
            prev_phi:   Some(2.71),
            adjustment: BoundaryAdjustment::ExpandBoundary,
            step_count: 42,
        };
        let json = serde_json::to_string(&status).unwrap();
        let decoded: DualEngineStatus = serde_json::from_str(&json).unwrap();
        assert_eq!(status, decoded);
    }
}
