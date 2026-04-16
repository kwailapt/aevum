//! Pillar: II + III. PACR field: Γ.
//!
//! Dormancy judge — decides whether the autopoietic loop should enter a
//! low-activity dormancy state to preserve thermodynamic resources.
//!
//! # Physical rationale (Pillar II)
//!
//! A system in NESS dissipates entropy continuously.  When no new structural
//! information is being discovered (Γ_k ≈ 0, low C_μ, H_T near 0), continued
//! full-rate computation is pure waste (E − Λ → large).  Dormancy reduces the
//! Landauer bill until a regime shift is detected.
//!
//! # Decision criteria
//!
//! | Condition                        | Decision      |
//! |----------------------------------|---------------|
//! | mean_Γ too low AND H_T < h_floor | EnterDormancy |
//! | mean_Γ is None (insufficient)    | EnterDormancy |
//! | mean_Γ above wake threshold      | WakeUp        |
//! | otherwise                        | Active        |

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

// ── Thresholds ────────────────────────────────────────────────────────────────

/// Thresholds for the dormancy decision.
#[derive(Debug, Clone)]
pub struct DormancyThresholds {
    /// If mean_Γ falls below this AND H_T < `h_t_floor`, enter dormancy.
    pub gamma_floor: f64,
    /// Entropy-rate floor below which dormancy is triggered (bits/sym).
    pub h_t_floor: f64,
    /// If mean_Γ rises above this, wake up from dormancy.
    pub gamma_wake: f64,
    /// Minimum consecutive dormancy ticks before wake-up is allowed.
    pub min_dormant_ticks: u32,
}

impl Default for DormancyThresholds {
    fn default() -> Self {
        Self {
            gamma_floor:       0.0,  // zero or below → cognitive stagnation
            h_t_floor:         0.05, // near-deterministic stream
            gamma_wake:        0.5,  // meaningful cognitive gain resuming
            min_dormant_ticks: 3,
        }
    }
}

// ── Decision ──────────────────────────────────────────────────────────────────

/// The dormancy judge's recommendation for this tick.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DormancyDecision {
    /// Continue normal operation.
    Active,
    /// Suspend full-rate computation; save thermodynamic resources.
    EnterDormancy {
        /// Human-readable reason for dormancy entry.
        reason: &'static str,
    },
    /// Regime shift detected; resume from dormancy.
    WakeUp,
}

// ── DormancyJudge ────────────────────────────────────���────────────────────────

/// Stateful dormancy judge that tracks consecutive dormant ticks.
#[derive(Debug, Clone)]
pub struct DormancyJudge {
    thresholds:    DormancyThresholds,
    dormant_ticks: u32,
}

impl DormancyJudge {
    /// Create a new judge with the given thresholds.
    #[must_use]
    pub fn new(thresholds: DormancyThresholds) -> Self {
        Self { thresholds, dormant_ticks: 0 }
    }

    /// Create a judge with default thresholds.
    #[must_use]
    pub fn default_judge() -> Self {
        Self::new(DormancyThresholds::default())
    }

    /// Evaluate the current state and return a dormancy recommendation.
    ///
    /// # Arguments
    ///
    /// * `mean_gamma` — mean Γ_k from [`GammaCalculator::mean_gamma`].
    ///   `None` means insufficient data.
    /// * `h_t`        — current entropy rate H_T (bits/sym).
    /// * `is_dormant` — whether the system is currently dormant.
    pub fn evaluate(&mut self, mean_gamma: Option<f64>, h_t: f64, is_dormant: bool) -> DormancyDecision {
        let t = &self.thresholds;

        if is_dormant {
            // Can we wake up?
            if self.dormant_ticks >= t.min_dormant_ticks {
                if let Some(g) = mean_gamma {
                    if g > t.gamma_wake {
                        self.dormant_ticks = 0;
                        return DormancyDecision::WakeUp;
                    }
                }
            }
            self.dormant_ticks += 1;
            return DormancyDecision::EnterDormancy { reason: "still dormant: awaiting regime shift" };
        }

        // Not currently dormant — should we enter?
        match mean_gamma {
            None => {
                self.dormant_ticks = 0;
                DormancyDecision::EnterDormancy { reason: "insufficient Γ_k data" }
            }
            Some(g) if g <= t.gamma_floor && h_t < t.h_t_floor => {
                self.dormant_ticks = 0;
                DormancyDecision::EnterDormancy { reason: "Γ_k ≤ floor and H_T below threshold" }
            }
            _ => DormancyDecision::Active,
        }
    }

    /// Current count of consecutive dormant ticks.
    #[must_use]
    pub fn dormant_ticks(&self) -> u32 {
        self.dormant_ticks
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn active_when_gamma_high_enough() {
        let mut judge = DormancyJudge::default_judge();
        let decision = judge.evaluate(Some(1.5), 0.9, false);
        assert_eq!(decision, DormancyDecision::Active);
    }

    #[test]
    fn enter_dormancy_when_gamma_low_and_h_t_low() {
        let mut judge = DormancyJudge::default_judge();
        // mean_gamma ≤ 0.0 AND h_t < 0.05
        let decision = judge.evaluate(Some(-0.1), 0.01, false);
        assert!(matches!(decision, DormancyDecision::EnterDormancy { .. }));
    }

    #[test]
    fn enter_dormancy_when_gamma_none() {
        let mut judge = DormancyJudge::default_judge();
        let decision = judge.evaluate(None, 0.9, false);
        assert!(matches!(decision, DormancyDecision::EnterDormancy { .. }));
    }

    #[test]
    fn no_wake_before_min_ticks() {
        let t = DormancyThresholds { min_dormant_ticks: 3, ..Default::default() };
        let mut judge = DormancyJudge::new(t);
        // Only 2 dormant ticks — even high gamma should not wake yet.
        judge.evaluate(None, 0.0, false); // tick 0
        judge.evaluate(None, 0.0, true);  // tick 1
        let d = judge.evaluate(Some(2.0), 0.9, true); // tick 2: 2 ticks < min 3
        assert!(matches!(d, DormancyDecision::EnterDormancy { .. }),
            "should not wake before min_dormant_ticks");
    }

    #[test]
    fn wakes_up_after_min_ticks_with_high_gamma() {
        let t = DormancyThresholds { min_dormant_ticks: 2, ..Default::default() };
        let mut judge = DormancyJudge::new(t);
        judge.evaluate(None, 0.0, true); // dormant tick 1
        judge.evaluate(None, 0.0, true); // dormant tick 2 → meets min
        // Now high gamma → WakeUp
        let d = judge.evaluate(Some(1.0), 0.9, true);
        assert_eq!(d, DormancyDecision::WakeUp);
    }

    #[test]
    fn active_when_gamma_low_but_h_t_above_floor() {
        let mut judge = DormancyJudge::default_judge();
        // gamma ≤ floor, but H_T is well above threshold → no dormancy.
        let decision = judge.evaluate(Some(-0.1), 0.8, false);
        assert_eq!(decision, DormancyDecision::Active);
    }

    #[test]
    fn dormant_tick_counter_increments_while_dormant() {
        let mut judge = DormancyJudge::default_judge();
        for _ in 0..5 {
            judge.evaluate(Some(0.1), 0.5, true);
        }
        assert_eq!(judge.dormant_ticks(), 5);
    }

    #[test]
    fn dormant_tick_resets_on_wake() {
        let t = DormancyThresholds { min_dormant_ticks: 2, gamma_wake: 0.5, ..Default::default() };
        let mut judge = DormancyJudge::new(t);
        judge.evaluate(None, 0.0, true);
        judge.evaluate(None, 0.0, true);
        judge.evaluate(Some(1.0), 0.9, true); // WakeUp
        assert_eq!(judge.dormant_ticks(), 0, "ticks should reset after wake");
    }
}
