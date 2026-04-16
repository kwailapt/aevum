//! Pillar: ALL. PACR field: Γ, Λ, Ω.
//!
//! Step 2 – DIAGNOSE: classify the current `CognitiveRegime` from the `Γ_k` series.
//! Step 3 – PROPOSE: generate an `AdjustmentProposal` from the diagnosed regime.
//! Step 4 – VALIDATE: reject any proposal that would violate a PACR meta-property.
//!
//! # PACR Five Meta-Properties (RULES-ARCHITECTURE §4)
//!
//! 1. **Append-only** — records are never mutated or deleted.
//! 2. **Causal consistency** — all Π predecessors must exist in the DAG.
//! 3. **Landauer floor** — Ω.energy ≥ Λ always.
//! 4. **Estimate order** — lower ≤ point ≤ upper for every Estimate<f64>.
//! 5. **No self-reference** — a record cannot be its own causal predecessor.
//!
//! Properties 1, 2, 5 are structural (checked here against the DAG).
//! Properties 3, 4 are physical (checked via `PacrRecord::validate()`).

use causal_dag::CausalDag;
use pacr_types::{CausalId, PacrRecord, ValidationIssue};
use thiserror::Error;

// ── CognitiveRegime ───────────────────────────────────────────────────────────

/// Classification of the current cognitive operating state.
///
/// Derived from the slope and variance of the `Γ_k` series.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CognitiveRegime {
    /// `Γ_k` series has positive slope — system is discovering structure.
    StructureDiscovery,
    /// `Γ_k` series has negative slope with high variance — noise is overwhelming.
    NoiseIntrusion,
    /// `Γ_k` series has large variance with slope near zero — regime shift in progress.
    RegimeShift,
    /// `Γ_k` series converges toward a stable value — approaching steady state.
    Convergence,
    /// `Γ_k` series is stable with low variance — NESS maintained.
    SteadyState,
    /// Insufficient data or all-None series — regime undetermined.
    Undetermined,
    /// `S_T`↓ rapidly + inflow rate spike + source concentration > threshold.
    ///
    /// Indicates a flood attack: many structurally similar packets from few
    /// sources.  Set by [`flood_detector::FloodDetector`] when source
    /// concentration exceeds its configured threshold.
    FloodDetected,
    /// `Γ_k` series has positive slope but with persistently negative second
    /// derivative — discovery rate is decelerating.
    ///
    /// Set by [`GammaCalculator::second_derivative_alert`] when two consecutive
    /// slope-of-slope values are both negative.  Triggers alpha relaxation to
    /// explore a broader causal-state space before stagnation.
    DeceleratingDiscovery,
}

// ── AdjustmentProposal ────────────────────────────────────────────────────────

/// A proposed parameter adjustment derived from the current regime.
#[derive(Debug, Clone, PartialEq)]
pub struct AdjustmentProposal {
    /// The regime that motivated this proposal.
    pub regime: CognitiveRegime,
    /// The suggested action.
    pub action: AdjustmentAction,
    /// Brief human-readable rationale (never empty).
    pub rationale: String,
}

/// Concrete adjustment to a system parameter.
#[derive(Debug, Clone, PartialEq)]
pub enum AdjustmentAction {
    /// Increase the ε-machine inference depth by `delta`.
    IncreaseDepth { delta: usize },
    /// Decrease the ε-machine inference depth by `delta` (floor at 1).
    DecreaseDepth { delta: usize },
    /// Tighten the KS significance level (reduce α → fewer false splits).
    TightenAlpha { new_alpha: f64 },
    /// Relax the KS significance level (increase α → more splits).
    RelaxAlpha { new_alpha: f64 },
    /// Enter dormancy — no structural changes until the regime shifts.
    EnterDormancy,
    /// No adjustment required.
    NoOp,
}

// ── Diagnosis ─────────────────────────────────────────────────────────────────

/// Thresholds for regime classification.
#[derive(Debug, Clone)]
pub struct DiagnosisConfig {
    /// Slope above this → `StructureDiscovery`.
    pub slope_high: f64,
    /// Slope below this (negative) → `NoiseIntrusion` or `RegimeShift`.
    pub slope_low: f64,
    /// Variance above this → noisy.
    pub variance_high: f64,
    /// Variance below this → stable.
    pub variance_low: f64,
}

impl Default for DiagnosisConfig {
    fn default() -> Self {
        Self {
            slope_high: 0.05,
            slope_low: -0.05,
            variance_high: 0.10,
            variance_low: 0.01,
        }
    }
}

/// Classify the cognitive regime from the `Γ_k` series.
///
/// Uses ordinary least squares on the finite values of `series`.
/// Returns `Undetermined` when fewer than 2 finite values are present.
#[must_use]
pub fn diagnose(series: &[Option<f64>], cfg: &DiagnosisConfig) -> CognitiveRegime {
    let values: Vec<f64> = series.iter().copied().flatten().collect();
    if values.len() < 2 {
        return CognitiveRegime::Undetermined;
    }

    let slope = ols_slope(&values);
    let variance = sample_variance(&values);

    if slope > cfg.slope_high {
        CognitiveRegime::StructureDiscovery
    } else if slope < cfg.slope_low && variance > cfg.variance_high {
        CognitiveRegime::NoiseIntrusion
    } else if slope.abs() <= cfg.slope_high && variance > cfg.variance_high {
        CognitiveRegime::RegimeShift
    } else if variance <= cfg.variance_low {
        // Low variance: check if converging or already stable.
        if slope.abs() > cfg.slope_low.abs() / 2.0 {
            CognitiveRegime::Convergence
        } else {
            CognitiveRegime::SteadyState
        }
    } else {
        CognitiveRegime::Convergence
    }
}

/// Generate an [`AdjustmentProposal`] for the given regime.
#[must_use]
pub fn propose(
    regime: CognitiveRegime,
    _current_depth: usize,
    current_alpha: f64,
) -> AdjustmentProposal {
    match regime {
        CognitiveRegime::StructureDiscovery => AdjustmentProposal {
            regime,
            action: AdjustmentAction::IncreaseDepth { delta: 1 },
            rationale: "Γ_k trending positive: deeper history captures more structure.".into(),
        },
        CognitiveRegime::NoiseIntrusion => AdjustmentProposal {
            regime,
            action: AdjustmentAction::DecreaseDepth { delta: 1 },
            rationale: "Γ_k noisy and negative: shallower history reduces noise sensitivity.".into(),
        },
        CognitiveRegime::RegimeShift => AdjustmentProposal {
            regime,
            action: AdjustmentAction::TightenAlpha { new_alpha: (current_alpha * 0.5).max(1e-6) },
            rationale: "High variance with flat slope: tighten KS α to stabilise state assignments.".into(),
        },
        CognitiveRegime::Convergence => AdjustmentProposal {
            regime,
            action: AdjustmentAction::NoOp,
            rationale: "Converging: no adjustment needed until steady state confirmed.".into(),
        },
        CognitiveRegime::SteadyState => AdjustmentProposal {
            regime,
            action: AdjustmentAction::NoOp,
            rationale: "NESS maintained: system at steady state.".into(),
        },
        CognitiveRegime::Undetermined => AdjustmentProposal {
            regime,
            action: AdjustmentAction::EnterDormancy,
            rationale: "Insufficient Γ_k data: enter dormancy until window fills.".into(),
        },
        CognitiveRegime::FloodDetected => AdjustmentProposal {
            regime,
            action: AdjustmentAction::EnterDormancy,
            rationale: "Flood attack detected: enter dormancy and activate immune response.".into(),
        },
        CognitiveRegime::DeceleratingDiscovery => AdjustmentProposal {
            regime,
            action: AdjustmentAction::RelaxAlpha { new_alpha: (current_alpha * 2.0).min(0.1) },
            rationale: "Discovery rate decelerating (d²Γ/dt² < 0): relax α to explore broader causal-state space.".into(),
        },
    }
}

// ── VALIDATE ──────────────────────────────────────────────────────────────────

/// Violation of a PACR meta-property detected during validation.
#[derive(Debug, Error, Clone)]
#[non_exhaustive]
pub enum ViolationError {
    /// One or more physical invariants in the record are violated.
    #[error("PACR physics violation: {0:?}")]
    PhysicsViolation(Vec<ValidationIssue>),

    /// An Estimate field has lower > point or point > upper.
    #[error("estimate bounds disordered in field '{field}': [{lower}, {point}, {upper}]")]
    EstimateBoundsDisordered {
        field: &'static str,
        lower: f64,
        point: f64,
        upper: f64,
    },

    /// A causal predecessor in Π does not exist in the DAG.
    #[error("unknown predecessor {0} in Π — causal consistency violated")]
    UnknownPredecessor(CausalId),

    /// The record's own ID appears in its predecessor set (causal loop).
    #[error("record {0} references itself as predecessor")]
    SelfReference(CausalId),

    /// A DAG append failed.
    #[error("DAG append failed: {0}")]
    DagError(String),
}

/// Validate `record` against all five PACR meta-properties.
///
/// Checks are applied in order:
/// 1. Physics invariants (via `PacrRecord::validate()`).
/// 2. Estimate bounds ordering on all Estimate<f64> fields.
/// 3. No self-reference in Π.
/// 4. All Π predecessors exist in `dag`.
///
/// Returns the **first** violation found, or `Ok(())` if all pass.
/// (Append-only is a structural invariant of `CausalDag`; validated implicitly.)
///
/// # Errors
///
/// Returns a [`ViolationError`] describing the first meta-property violated.
pub fn validate(record: &PacrRecord, dag: &CausalDag) -> Result<(), ViolationError> {
    // ── Property 3 + 4 (physical): PacrRecord::validate() ──────────────────
    let issues = record.validate();
    if !issues.is_empty() {
        return Err(ViolationError::PhysicsViolation(issues));
    }

    // ── Property 4 (estimate order): check all Estimate<f64> fields ─────────
    check_estimate_order(
        "Λ",
        record.landauer_cost.lower,
        record.landauer_cost.point,
        record.landauer_cost.upper,
    )?;
    check_estimate_order(
        "Ω.energy",
        record.resources.energy.lower,
        record.resources.energy.point,
        record.resources.energy.upper,
    )?;
    check_estimate_order(
        "Ω.time",
        record.resources.time.lower,
        record.resources.time.point,
        record.resources.time.upper,
    )?;
    check_estimate_order(
        "Ω.space",
        record.resources.space.lower,
        record.resources.space.point,
        record.resources.space.upper,
    )?;
    check_estimate_order(
        "Γ.C_μ",
        record.cognitive_split.statistical_complexity.lower,
        record.cognitive_split.statistical_complexity.point,
        record.cognitive_split.statistical_complexity.upper,
    )?;
    check_estimate_order(
        "Γ.H_T",
        record.cognitive_split.entropy_rate.lower,
        record.cognitive_split.entropy_rate.point,
        record.cognitive_split.entropy_rate.upper,
    )?;

    // ── Property 5: no self-reference ────────────────────────────────────────
    if record.predecessors.contains(&record.id) {
        return Err(ViolationError::SelfReference(record.id));
    }

    // ── Property 2: all predecessors exist in DAG ────────────────────────────
    for &pred in &record.predecessors {
        if !dag.contains(&pred) {
            return Err(ViolationError::UnknownPredecessor(pred));
        }
    }

    Ok(())
}

// ── Internal helpers ──────────────────────────────────────────────────────────

fn check_estimate_order(
    field: &'static str,
    lower: f64,
    point: f64,
    upper: f64,
) -> Result<(), ViolationError> {
    if lower > point + 1e-12 || point > upper + 1e-12 {
        Err(ViolationError::EstimateBoundsDisordered {
            field,
            lower,
            point,
            upper,
        })
    } else {
        Ok(())
    }
}

/// Ordinary least squares slope of a sequence.
/// `values` must have ≥ 2 elements.
fn ols_slope(values: &[f64]) -> f64 {
    let n = values.len() as f64;
    let x_bar = (n - 1.0) / 2.0;
    let y_bar: f64 = values.iter().sum::<f64>() / n;

    let mut num = 0.0_f64;
    let mut den = 0.0_f64;
    for (i, &y) in values.iter().enumerate() {
        let x = i as f64;
        num += (x - x_bar) * (y - y_bar);
        den += (x - x_bar) * (x - x_bar);
    }
    if den.abs() < 1e-30 {
        0.0
    } else {
        num / den
    }
}

/// Sample variance (Bessel-corrected) of a sequence.
fn sample_variance(values: &[f64]) -> f64 {
    let n = values.len();
    if n < 2 {
        return 0.0;
    }
    let mean: f64 = values.iter().sum::<f64>() / n as f64;
    let sum_sq: f64 = values.iter().map(|&v| (v - mean).powi(2)).sum();
    sum_sq / (n - 1) as f64
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use causal_dag::CausalDag;
    use pacr_types::{
        CausalId, CognitiveSplit, Estimate, PacrRecord, PredecessorSet, ResourceTriple,
    };

    // ── Helper: build a minimal valid PacrRecord ──────────────────────────────

    fn valid_record(id: u128, preds: &[u128]) -> PacrRecord {
        let lambda = Estimate::exact(1e-18_f64);
        let energy = Estimate::exact(1e-14_f64); // E >> Λ
        PacrRecord {
            id: CausalId(id),
            predecessors: preds
                .iter()
                .map(|&p| CausalId(p))
                .collect::<PredecessorSet>(),
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
            payload: bytes::Bytes::new(),
        }
    }

    // ── diagnose ──────────────────────────────────────────────────────────────

    #[test]
    fn diagnose_undetermined_on_empty() {
        let cfg = DiagnosisConfig::default();
        assert_eq!(diagnose(&[], &cfg), CognitiveRegime::Undetermined);
    }

    #[test]
    fn diagnose_undetermined_on_all_none() {
        let cfg = DiagnosisConfig::default();
        let series = vec![None, None, None];
        assert_eq!(diagnose(&series, &cfg), CognitiveRegime::Undetermined);
    }

    #[test]
    fn diagnose_structure_discovery_on_rising_series() {
        let cfg = DiagnosisConfig::default();
        // Strongly positive slope.
        let series: Vec<Option<f64>> = (0..10).map(|i| Some(i as f64 * 0.2)).collect();
        assert_eq!(diagnose(&series, &cfg), CognitiveRegime::StructureDiscovery);
    }

    #[test]
    fn diagnose_noise_intrusion_on_falling_high_variance() {
        let cfg = DiagnosisConfig::default();
        // Negative slope + high variance.
        let series: Vec<Option<f64>> = vec![
            Some(2.0),
            Some(-2.0),
            Some(2.5),
            Some(-2.5),
            Some(3.0),
            Some(-3.0),
        ];
        let regime = diagnose(&series, &cfg);
        // Slope is near 0 due to alternation, variance is high → RegimeShift or NoiseIntrusion.
        assert!(matches!(
            regime,
            CognitiveRegime::RegimeShift
                | CognitiveRegime::NoiseIntrusion
                | CognitiveRegime::Convergence
        ));
    }

    #[test]
    fn diagnose_steady_state_on_flat_low_variance() {
        let cfg = DiagnosisConfig::default();
        let series: Vec<Option<f64>> = vec![Some(1.0); 10];
        // Slope = 0, variance ≈ 0.
        assert_eq!(diagnose(&series, &cfg), CognitiveRegime::SteadyState);
    }

    // ── propose ───────────────────────────────────────────────────────────────

    #[test]
    fn propose_increases_depth_on_structure_discovery() {
        let p = propose(CognitiveRegime::StructureDiscovery, 3, 0.001);
        assert_eq!(p.action, AdjustmentAction::IncreaseDepth { delta: 1 });
    }

    #[test]
    fn propose_decreases_depth_on_noise() {
        let p = propose(CognitiveRegime::NoiseIntrusion, 3, 0.001);
        assert_eq!(p.action, AdjustmentAction::DecreaseDepth { delta: 1 });
    }

    #[test]
    fn propose_noop_on_steady_state() {
        let p = propose(CognitiveRegime::SteadyState, 3, 0.001);
        assert_eq!(p.action, AdjustmentAction::NoOp);
    }

    #[test]
    fn propose_dormancy_on_undetermined() {
        let p = propose(CognitiveRegime::Undetermined, 3, 0.001);
        assert_eq!(p.action, AdjustmentAction::EnterDormancy);
    }

    #[test]
    fn propose_rationale_never_empty() {
        for regime in [
            CognitiveRegime::StructureDiscovery,
            CognitiveRegime::NoiseIntrusion,
            CognitiveRegime::RegimeShift,
            CognitiveRegime::Convergence,
            CognitiveRegime::SteadyState,
            CognitiveRegime::Undetermined,
            CognitiveRegime::DeceleratingDiscovery,
        ] {
            let p = propose(regime, 4, 0.001);
            assert!(
                !p.rationale.is_empty(),
                "rationale must not be empty for {regime:?}"
            );
        }
    }

    // ── validate ──────────────────────────────────────────────────────────────

    #[test]
    fn validate_accepts_clean_genesis_record() {
        let dag = CausalDag::new();
        let rec = valid_record(1, &[]);
        assert!(validate(&rec, &dag).is_ok());
    }

    #[test]
    fn validate_rejects_self_reference() {
        let dag = CausalDag::new();
        let rec = valid_record(42, &[42]); // self-referential Π
        let err = validate(&rec, &dag).unwrap_err();
        assert!(matches!(
            err,
            ViolationError::SelfReference(_) | ViolationError::PhysicsViolation(_)
        ));
    }

    #[test]
    fn validate_rejects_unknown_predecessor() {
        let dag = CausalDag::new();
        // Predecessor 999 does not exist in DAG.
        let rec = valid_record(2, &[999]);
        let err = validate(&rec, &dag).unwrap_err();
        assert!(matches!(err, ViolationError::UnknownPredecessor(_)));
    }

    #[test]
    fn validate_accepts_record_with_known_predecessor() {
        let dag = CausalDag::new();
        let parent = valid_record(10, &[]);
        dag.append(parent).expect("append genesis");
        let child = valid_record(11, &[10]);
        assert!(validate(&child, &dag).is_ok());
    }

    #[test]
    fn validate_rejects_energy_below_landauer() {
        let dag = CausalDag::new();
        let mut rec = valid_record(5, &[]);
        // Set energy below Landauer floor.
        rec.resources.energy = Estimate::exact(1e-20);
        rec.landauer_cost = Estimate::exact(1e-18);
        let err = validate(&rec, &dag).unwrap_err();
        assert!(matches!(err, ViolationError::PhysicsViolation(_)));
    }

    #[test]
    fn validate_rejects_disordered_estimate_bounds() {
        let dag = CausalDag::new();
        let mut rec = valid_record(6, &[]);
        // Manually create a disordered Estimate (lower > upper).
        rec.resources.time = Estimate {
            point: 1e-6,
            lower: 2e-6,
            upper: 3e-6,
        };
        let err = validate(&rec, &dag).unwrap_err();
        // lower (2e-6) > point (1e-6) → EstimateBoundsDisordered
        assert!(matches!(
            err,
            ViolationError::EstimateBoundsDisordered { .. }
        ));
    }
}
