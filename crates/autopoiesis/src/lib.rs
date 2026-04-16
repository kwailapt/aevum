//! Pillar: ALL. PACR field: Γ (self-modifying feedback loop).
//!
//! Five-step autopoietic loop (RULES-ARCHITECTURE §5):
//!
//! ```text
//! 1. OBSERVE   — GammaCalculator::push(snapshot)
//! 2. DIAGNOSE  — diagnose(gamma_series, &cfg) → CognitiveRegime
//! 3. PROPOSE   — propose(regime, depth, alpha) → AdjustmentProposal
//! 4. VALIDATE  — validate(&record, &dag)       → Ok(()) | Err(ViolationError)
//! 5. COMMIT    — dag.append(proposal_record)   → Arc<PacrRecord>
//! ```
//!
//! A violation at step 4 causes the proposal to be **rejected** and logged.
//! Silent application of an invalid proposal is **forbidden**.
//!
//! # Self-referential COMMIT
//!
//! The committed record's Π predecessor set links back to the observed records,
//! creating the causal chain: observed events → autopoietic response.
//! The record itself is NOT in its own Π (that would violate meta-property 5).

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::must_use_candidate,
    clippy::needless_pass_by_value,
    clippy::missing_panics_doc,
    clippy::missing_errors_doc,
    clippy::return_self_not_must_use,
    clippy::unreadable_literal
)]

pub mod adjuster;
pub mod dormancy;
pub mod flood_detector;
pub mod gamma_calculator;

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use bytes::Bytes;
use causal_dag::CausalDag;
use pacr_types::{CausalId, CognitiveSplit, Estimate, PacrRecord, PredecessorSet, ResourceTriple};

pub use adjuster::{
    diagnose, propose, validate, AdjustmentAction, AdjustmentProposal, CognitiveRegime,
    DiagnosisConfig, ViolationError,
};
pub use dormancy::{DormancyDecision, DormancyJudge, DormancyThresholds};
pub use gamma_calculator::{GammaCalculator, Snapshot};

// ── ID generation ─────────────────────────────────────────────────────────────

/// Monotonic counter for autopoiesis-generated `CausalIds`.
/// High 64 bits: sentinel `0xA070_0000` (identifies autopoiesis records).
/// Low  64 bits: atomic counter (monotonically increasing).
static AUTOPOIESIS_COUNTER: AtomicU64 = AtomicU64::new(1);

/// Generate a unique [`CausalId`] for an autopoiesis-committed record.
#[must_use]
fn new_causal_id() -> CausalId {
    let seq = AUTOPOIESIS_COUNTER.fetch_add(1, Ordering::Relaxed);
    let high: u128 = 0xA070_0000_0000_0000_0000_0000_0000_0000;
    CausalId(high | u128::from(seq))
}

// ── Config ────────────────────────────────────────────────────────────────────

/// Configuration for the autopoietic loop.
#[derive(Debug, Clone)]
pub struct AutopoiesisConfig {
    /// Window capacity for [`GammaCalculator`].
    pub window_capacity: usize,
    /// Initial ε-machine inference depth.
    pub initial_depth: usize,
    /// Initial KS significance level α.
    pub initial_alpha: f64,
    /// Regime diagnosis thresholds.
    pub diagnosis: DiagnosisConfig,
    /// Dormancy thresholds.
    pub dormancy: DormancyThresholds,
}

impl Default for AutopoiesisConfig {
    fn default() -> Self {
        Self {
            window_capacity: 20,
            initial_depth: 4,
            initial_alpha: 0.001,
            diagnosis: DiagnosisConfig::default(),
            dormancy: DormancyThresholds::default(),
        }
    }
}

// ── StepOutcome ───────────────────────────────────────────────────────────────

/// Result of one autopoietic step.
#[derive(Debug)]
pub enum StepOutcome {
    /// Proposal validated and committed; returns the appended record.
    Committed(Arc<PacrRecord>),
    /// Proposal was rejected (meta-property violated); contains the error.
    Rejected(ViolationError),
    /// Loop is dormant this tick; no proposal generated.
    Dormant,
    /// Insufficient data in the window yet; observation stored.
    Observing,
}

// ── AutopoiesisLoop ───────────────────────────────────────────────────────────

/// Orchestrates the five-step autopoietic feedback loop.
pub struct AutopoiesisLoop {
    calc: GammaCalculator,
    judge: DormancyJudge,
    is_dormant: bool,
    depth: usize,
    alpha: f64,
    diag_cfg: DiagnosisConfig,
}

impl AutopoiesisLoop {
    /// Create a new loop from configuration.
    #[must_use]
    pub fn new(cfg: AutopoiesisConfig) -> Self {
        Self {
            calc: GammaCalculator::new(cfg.window_capacity),
            judge: DormancyJudge::new(cfg.dormancy),
            is_dormant: false,
            depth: cfg.initial_depth,
            alpha: cfg.initial_alpha,
            diag_cfg: cfg.diagnosis,
        }
    }

    /// Current inference depth.
    #[must_use]
    pub fn depth(&self) -> usize {
        self.depth
    }

    /// Current KS α.
    #[must_use]
    pub fn alpha(&self) -> f64 {
        self.alpha
    }

    /// Whether the loop is currently dormant.
    #[must_use]
    pub fn is_dormant(&self) -> bool {
        self.is_dormant
    }

    /// Execute one step of the autopoietic loop.
    ///
    /// # Arguments
    ///
    /// * `snap`  — the observed (`C_μ`, `H_T`, Λ) snapshot (steps 1–3).
    /// * `preds` — causal predecessor IDs for the COMMIT record (must exist in `dag`).
    /// * `dag`   — the shared append-only causal DAG.
    ///
    /// # Returns
    ///
    /// [`StepOutcome`] describing what happened this tick.
    pub fn step(&mut self, snap: Snapshot, preds: &[CausalId], dag: &CausalDag) -> StepOutcome {
        // ── Step 1: OBSERVE ───────────────────────────────────────────────────
        let h_t = snap.h_t;
        self.calc.push(snap);

        if !self.calc.ready() {
            return StepOutcome::Observing;
        }

        // ── Dormancy check ────────────────────────────────────────────────────
        let mean_g = self.calc.mean_gamma();
        let decision = self.judge.evaluate(mean_g, h_t, self.is_dormant);
        match decision {
            DormancyDecision::EnterDormancy { .. } => {
                self.is_dormant = true;
                return StepOutcome::Dormant;
            }
            DormancyDecision::WakeUp => {
                self.is_dormant = false;
                // fall through to full step
            }
            DormancyDecision::Active => {}
        }

        // ── Step 2: DIAGNOSE ──────────────────────────────────────────────────
        let series = self.calc.gamma_series();
        let mut regime = diagnose(&series, &self.diag_cfg);

        // ── Second-derivative override ────────────────────────────────────────
        // If the discovery rate itself is decelerating (d²Γ/dt² < 0 persistently),
        // upgrade regime to DeceleratingDiscovery regardless of primary diagnosis,
        // so the adjuster can relax α before stagnation occurs.
        if self.calc.second_derivative_alert() {
            regime = CognitiveRegime::DeceleratingDiscovery;
        }

        // ── Step 3: PROPOSE ───────────────────────────────────────────────────
        let proposal = propose(regime, self.depth, self.alpha);

        // ── Build proposal record (Ω, Γ from window) ─────────────────────────
        let record = build_proposal_record(&proposal, &self.calc, preds);

        // ── Step 4: VALIDATE ──────────────────────────────────────────────────
        if let Err(e) = validate(&record, dag) {
            return StepOutcome::Rejected(e);
        }

        // ── Step 5: COMMIT ────────────────────────────────────────────────────
        match dag.append(record) {
            Ok(arc) => {
                // Apply proposed adjustment ONLY after successful commit.
                self.apply_action(&proposal.action);
                StepOutcome::Committed(arc)
            }
            Err(e) => StepOutcome::Rejected(ViolationError::DagError(format!("{e:?}"))),
        }
    }

    /// Apply the accepted action to the loop's own parameters.
    fn apply_action(&mut self, action: &AdjustmentAction) {
        match action {
            AdjustmentAction::IncreaseDepth { delta } => {
                self.depth = self.depth.saturating_add(*delta).min(16);
            }
            AdjustmentAction::DecreaseDepth { delta } => {
                self.depth = self.depth.saturating_sub(*delta).max(1);
            }
            AdjustmentAction::TightenAlpha { new_alpha } => {
                self.alpha = new_alpha.max(1e-6);
            }
            AdjustmentAction::RelaxAlpha { new_alpha } => {
                self.alpha = new_alpha.min(0.1);
            }
            AdjustmentAction::EnterDormancy => {
                self.is_dormant = true;
            }
            AdjustmentAction::NoOp => {}
        }
    }
}

// ── COMMIT record construction ────────────────────────────────────────────────

/// Build the PACR record that represents the autopoietic proposal.
///
/// Physical estimates are conservative wide-CI values reflecting the fact that
/// we cannot measure userspace Landauer cost precisely without hardware counters.
fn build_proposal_record(
    proposal: &AdjustmentProposal,
    calc: &GammaCalculator,
    preds: &[CausalId],
) -> PacrRecord {
    // Λ: autopoiesis overhead ≈ 256 bits at 300 K (conservative estimate).
    // k_B = 1.380_649e-23, 300 K, ln(2) → per bit ≈ 2.871e-21 J.
    const BITS_OVERHEAD: f64 = 256.0;
    const LANDAUER_PER_BIT: f64 = 2.871e-21;
    let lambda_point = BITS_OVERHEAD * LANDAUER_PER_BIT;
    let lambda = Estimate {
        point: lambda_point,
        lower: lambda_point * 0.97,
        upper: lambda_point * 1.03,
    };

    // Ω: wide CI — we know the process uses memory but can't measure precisely.
    let energy = Estimate {
        point: lambda_point * 1e4, // CMOS efficiency factor (ets-probe model)
        lower: lambda_point * 1e3,
        upper: lambda_point * 1e6,
    };
    let time_s = 1e-3_f64; // ≈ 1 ms per loop tick
    let time = Estimate {
        point: time_s,
        lower: (time_s - 1e-6).max(0.0),
        upper: time_s + 1e-6,
    };
    let space = Estimate {
        point: 0.0,
        lower: 0.0,
        upper: 1e12,
    }; // honest wide CI

    // Γ: use the latest snapshot's values if available.
    let (c_mu, h_t) = calc.latest().map_or((0.0, 0.0), |s| (s.c_mu, s.h_t));
    let cognitive_split = CognitiveSplit {
        statistical_complexity: Estimate::exact(c_mu.max(0.0)),
        entropy_rate: Estimate::exact(h_t.max(0.0)),
    };

    // P: encode the rationale as UTF-8 bytes.
    let payload = Bytes::from(proposal.rationale.as_bytes().to_vec());

    PacrRecord {
        id: new_causal_id(),
        predecessors: preds.iter().copied().collect::<PredecessorSet>(),
        landauer_cost: lambda,
        resources: ResourceTriple {
            energy,
            time,
            space,
        },
        cognitive_split,
        payload,
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use causal_dag::CausalDag;
    use pacr_types::{
        CausalId, CognitiveSplit, Estimate, PacrRecord, PredecessorSet, ResourceTriple,
    };

    fn make_parent(id: u128) -> PacrRecord {
        let lambda = Estimate::exact(1e-18_f64);
        let energy = Estimate::exact(1e-14_f64);
        PacrRecord {
            id: CausalId(id),
            predecessors: PredecessorSet::new(),
            landauer_cost: lambda,
            resources: ResourceTriple {
                energy,
                time: Estimate::exact(1e-6),
                space: Estimate::exact(4096.0),
            },
            cognitive_split: CognitiveSplit {
                statistical_complexity: Estimate::exact(0.9),
                entropy_rate: Estimate::exact(0.7),
            },
            payload: Bytes::new(),
        }
    }

    fn snap(c: f64, h: f64, l: f64) -> Snapshot {
        Snapshot {
            c_mu: c,
            h_t: h,
            lambda: l,
        }
    }

    // ── Commit path ───────────────────────────────────────────────────────────

    #[test]
    fn step_commits_when_window_ready_and_preds_exist() {
        let dag = CausalDag::new();
        let parent = make_parent(1);
        dag.append(parent).unwrap();

        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 2,
            ..AutopoiesisConfig::default()
        });

        // Two snaps with stable values → SteadyState → NoOp.
        lp.step(snap(1.0, 0.5, 1e-18), &[CausalId(1)], &dag);
        let outcome = lp.step(snap(1.0, 0.5, 1e-18), &[CausalId(1)], &dag);

        assert!(
            matches!(outcome, StepOutcome::Committed(_) | StepOutcome::Dormant),
            "expected Committed or Dormant, got {outcome:?}"
        );
    }

    #[test]
    fn step_returns_observing_before_window_ready() {
        let dag = CausalDag::new();
        let parent = make_parent(2);
        dag.append(parent).unwrap();

        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 5,
            ..AutopoiesisConfig::default()
        });

        // Only one snap → window not ready.
        let outcome = lp.step(snap(1.0, 0.5, 1e-18), &[CausalId(2)], &dag);
        assert!(matches!(outcome, StepOutcome::Observing));
    }

    #[test]
    fn step_rejects_unknown_predecessor() {
        let dag = CausalDag::new();
        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 2,
            ..AutopoiesisConfig::default()
        });

        lp.step(snap(1.0, 0.5, 1e-18), &[], &dag);
        let outcome = lp.step(snap(1.0, 0.5, 1e-18), &[CausalId(999)], &dag);

        // Predecessor 999 does not exist → Rejected.
        assert!(matches!(
            outcome,
            StepOutcome::Rejected(_) | StepOutcome::Dormant
        ));
    }

    #[test]
    fn apply_action_increases_depth() {
        let dag = CausalDag::new();
        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 2,
            initial_depth: 3,
            ..AutopoiesisConfig::default()
        });

        lp.apply_action(&AdjustmentAction::IncreaseDepth { delta: 2 });
        assert_eq!(lp.depth(), 5);
    }

    #[test]
    fn apply_action_depth_floor_at_one() {
        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 2,
            initial_depth: 1,
            ..AutopoiesisConfig::default()
        });
        lp.apply_action(&AdjustmentAction::DecreaseDepth { delta: 10 });
        assert_eq!(lp.depth(), 1, "depth must never fall below 1");
    }

    #[test]
    fn apply_action_depth_cap_at_16() {
        let mut lp = AutopoiesisLoop::new(AutopoiesisConfig {
            window_capacity: 2,
            initial_depth: 15,
            ..AutopoiesisConfig::default()
        });
        lp.apply_action(&AdjustmentAction::IncreaseDepth { delta: 100 });
        assert_eq!(lp.depth(), 16, "depth must not exceed 16");
    }

    // ── Rejected path ─────────────────────────────────────────────────────────

    #[test]
    fn build_proposal_record_energy_exceeds_landauer() {
        let calc = {
            let mut c = GammaCalculator::new(2);
            c.push(snap(1.0, 0.5, 1e-18));
            c
        };
        let proposal = AdjustmentProposal {
            regime: CognitiveRegime::SteadyState,
            action: AdjustmentAction::NoOp,
            rationale: "test".to_string(),
        };
        let rec = build_proposal_record(&proposal, &calc, &[]);
        // Energy must be > Λ (physics invariant).
        assert!(
            rec.resources.energy.point >= rec.landauer_cost.point,
            "E={} must be ≥ Λ={}",
            rec.resources.energy.point,
            rec.landauer_cost.point
        );
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        /// A clean genesis record always passes PACR validation.
        #[test]
        fn valid_genesis_always_passes(
            c_mu in 0.0_f64..2.0_f64,
            h_t  in 0.0_f64..2.0_f64,
        ) {
            let dag = CausalDag::new();
            let lambda = Estimate::exact(1e-18_f64);
            let rec = PacrRecord {
                id: new_causal_id(),
                predecessors: PredecessorSet::new(),
                landauer_cost: lambda,
                resources: ResourceTriple {
                    energy: Estimate::exact(1e-14),
                    time:   Estimate::exact(1e-6),
                    space:  Estimate::exact(4096.0),
                },
                cognitive_split: CognitiveSplit {
                    statistical_complexity: Estimate::exact(c_mu),
                    entropy_rate:           Estimate::exact(h_t),
                },
                payload: bytes::Bytes::new(),
            };
            prop_assert!(validate(&rec, &dag).is_ok());
        }

        /// Γ_k is finite whenever both C_μ and Λ are strictly positive.
        #[test]
        fn gamma_k_finite_for_positive_inputs(
            c1 in 0.1_f64..10.0_f64,
            c2 in 0.1_f64..10.0_f64,
            l1 in 1e-20_f64..1e-15_f64,
            l2 in 1e-20_f64..1e-15_f64,
        ) {
            prop_assume!((l2 - l1).abs() > 1e-30);
            let mut calc = GammaCalculator::new(4);
            calc.push(Snapshot { c_mu: c1, h_t: 0.5, lambda: l1 });
            calc.push(Snapshot { c_mu: c2, h_t: 0.6, lambda: l2 });
            if let Some(g) = calc.gamma_k() {
                prop_assert!(g.is_finite(), "Γ_k={g} must be finite");
                prop_assert!(g >= -100.0 && g <= 100.0, "Γ_k={g} out of clamp range");
            }
        }
    }
}
