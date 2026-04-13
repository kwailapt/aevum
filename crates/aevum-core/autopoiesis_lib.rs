// crates/autopoiesis/src/lib.rs
//
// Pillar: ALL (meta-module). PACR field: primarily Γ (cognitive split).
// The autopoietic loop is the compound interest engine of Aevum.
// It observes the system's own cognitive trajectory (S_T, H_T over time),
// diagnoses regime changes, and proposes evolutionary adaptations.
//
// This is where Aevum becomes self-modifying — but in a disciplined way,
// constrained by physics. Every proposed change must pass the
// PACR 5-property validation before it can be committed.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use pacr_types::{CausalId, CognitiveSplit, Estimate, PacrRecord};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

/// The cognitive regime of the system, diagnosed from Γ trends.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CognitiveRegime {
    /// S_T rising, H_T stable: system is discovering learnable structure.
    /// Action: continue current strategy, increase resource allocation.
    StructureDiscovery,

    /// S_T stable, H_T rising: system is encountering more noise.
    /// Action: investigate data quality, potential adversarial inputs.
    NoiseIntrusion,

    /// Both S_T and H_T rising: new regime detected, old ε-machine inadequate.
    /// Action: prepare schema evolution proposal, expand model capacity.
    RegimeShift,

    /// Both S_T and H_T falling: system is simplifying (converging).
    /// Action: may indicate overfitting or environmental stationarity.
    Convergence,

    /// S_T stable, H_T stable: steady state reached.
    /// Action: maintain NESS, optimize thermodynamic waste.
    SteadyState,

    /// Insufficient data to diagnose.
    Undetermined,
}

/// A window of recent cognitive splits, used for trend analysis.
pub struct CognitiveTrajectory {
    /// Sliding window of (CausalId, CognitiveSplit) pairs, ordered by insertion.
    window: VecDeque<(CausalId, CognitiveSplit)>,
    /// Maximum window size (bounded memory = O(1) space per diagnosis).
    max_window: usize,
}

impl CognitiveTrajectory {
    /// Creates a new trajectory tracker with the given window size.
    #[must_use]
    pub fn new(max_window: usize) -> Self {
        Self {
            window: VecDeque::with_capacity(max_window),
            max_window,
        }
    }

    /// Ingests a new PACR record's cognitive split.
    pub fn ingest(&mut self, id: CausalId, split: CognitiveSplit) {
        if self.window.len() >= self.max_window {
            self.window.pop_front();
        }
        self.window.push_back((id, split));
    }

    /// Diagnoses the current cognitive regime from the trajectory.
    ///
    /// Uses simple linear regression on S_T and H_T over the window.
    /// A slope > threshold = "rising", < -threshold = "falling", else "stable".
    #[must_use]
    pub fn diagnose(&self, slope_threshold: f64) -> CognitiveRegime {
        if self.window.len() < 10 {
            return CognitiveRegime::Undetermined;
        }

        let n = self.window.len() as f64;
        let mut sum_i = 0.0_f64;
        let mut sum_st = 0.0_f64;
        let mut sum_ht = 0.0_f64;
        let mut sum_i_st = 0.0_f64;
        let mut sum_i_ht = 0.0_f64;
        let mut sum_i2 = 0.0_f64;

        for (i, (_id, split)) in self.window.iter().enumerate() {
            let idx = i as f64;
            let st = split.statistical_complexity.point;
            let ht = split.entropy_rate.point;

            sum_i += idx;
            sum_st += st;
            sum_ht += ht;
            sum_i_st += idx * st;
            sum_i_ht += idx * ht;
            sum_i2 += idx * idx;
        }

        let denominator = n * sum_i2 - sum_i * sum_i;
        if denominator.abs() < f64::EPSILON {
            return CognitiveRegime::Undetermined;
        }

        let slope_st = (n * sum_i_st - sum_i * sum_st) / denominator;
        let slope_ht = (n * sum_i_ht - sum_i * sum_ht) / denominator;

        let st_trend = classify_trend(slope_st, slope_threshold);
        let ht_trend = classify_trend(slope_ht, slope_threshold);

        match (st_trend, ht_trend) {
            (Trend::Rising, Trend::Stable) => CognitiveRegime::StructureDiscovery,
            (Trend::Stable, Trend::Rising) => CognitiveRegime::NoiseIntrusion,
            (Trend::Rising, Trend::Rising) => CognitiveRegime::RegimeShift,
            (Trend::Falling, Trend::Falling) => CognitiveRegime::Convergence,
            (Trend::Stable, Trend::Stable) => CognitiveRegime::SteadyState,
            (Trend::Falling, Trend::Stable)
            | (Trend::Stable, Trend::Falling)
            | (Trend::Rising, Trend::Falling)
            | (Trend::Falling, Trend::Rising) => CognitiveRegime::Undetermined,
        }
    }

    /// Returns the average thermodynamic structure-noise ratio over the window.
    #[must_use]
    pub fn average_structure_noise_ratio(&self) -> Option<f64> {
        if self.window.is_empty() {
            return None;
        }
        let mut sum = 0.0;
        let mut count = 0_usize;
        for (_id, split) in &self.window {
            if let Some(ratio) = split.structure_noise_ratio() {
                sum += ratio;
                count += 1;
            }
        }
        if count == 0 {
            None
        } else {
            Some(sum / count as f64)
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Trend {
    Rising,
    Falling,
    Stable,
}

fn classify_trend(slope: f64, threshold: f64) -> Trend {
    if slope > threshold {
        Trend::Rising
    } else if slope < -threshold {
        Trend::Falling
    } else {
        Trend::Stable
    }
}

/// An evolution proposal generated by the autopoietic loop.
/// This is itself encoded as a PACR record (self-referential closure).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionProposal {
    /// What regime triggered this proposal
    pub trigger: CognitiveRegime,

    /// Human/AI-readable description of the proposed change
    pub description: String,

    /// Which PACR meta-property must be verified before acceptance
    pub required_validations: Vec<MetaPropertyCheck>,

    /// The causal IDs of the evidence records that support this proposal
    pub evidence: Vec<CausalId>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MetaPropertyCheck {
    /// Verify the proposal doesn't remove any PACR dimension
    PhysicalCompleteness,
    /// Verify the proposal doesn't merge independent dimensions
    MutualIndependence,
    /// Verify the proposal doesn't split an atomic dimension
    AtomicIrreducibility,
    /// Verify the proposal preserves Estimate<T> format
    MeasurementTolerance,
    /// Verify the proposal is append-only (no semantic changes)
    TemporalImmutability,
}

