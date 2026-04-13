//! Pillar: III + II. PACR field: Γ, Λ.
//!
//! **Causal Return Tracker** — measures ρ(A→B) = ΔΦ_B / Λ_A.
//!
//! # Theory
//!
//! The causal return rate ρ(A→B) answers: "for every joule agent A spent
//! transmitting to agent B, how many units of Φ did B gain?"
//!
//! ρ >> 1: agent A is a high-value contributor to B's cognition.
//! ρ ≈ 0:  agent A's transmissions have no measurable cognitive effect on B.
//!          This is the "Babel Tower" signal: high Λ, high S_T, but no causal
//!          impact. Such agents should have their CSO reputation decayed.
//! ρ < 0:  agent A actively degrades B's cognitive quality (adversarial).

#![forbid(unsafe_code)]

use std::sync::Arc;
use std::collections::HashSet;

use aevum_core::CsoIndex;
use dashmap::DashMap;
use pacr_types::CausalId;

// ── ReturnEma ─────────────────────────────────────────────────────────────────

/// An exponential moving average tracker for a single (source, target) pair.
#[derive(Debug, Clone)]
struct ReturnEma {
    /// Current EMA of ρ values.
    value: f64,
    /// Number of observations recorded.
    count: u64,
}

impl ReturnEma {
    fn new() -> Self {
        Self { value: 0.0, count: 0 }
    }

    /// Update the EMA with a new ρ observation. α = 0.1.
    fn update(&mut self, rho: f64) {
        const ALPHA: f64 = 0.1;
        self.value = ALPHA * rho + (1.0 - ALPHA) * self.value;
        self.count += 1;
    }
}

// ── CausalReturnTracker ───────────────────────────────────────────────────────

/// Concurrent tracker of ρ(A→B) causal return rates.
///
/// Uses a `DashMap` keyed by `(source, target)` pairs for O(1) amortised
/// reads and fine-grained concurrent writes.
pub struct CausalReturnTracker {
    /// (source_id, target_id) → EMA of ρ values.
    ema_map: DashMap<(CausalId, CausalId), ReturnEma>,
}

impl CausalReturnTracker {
    /// Create a new tracker.
    #[must_use]
    pub fn new() -> Self {
        Self { ema_map: DashMap::new() }
    }

    /// Record one ρ observation for the (source, target) pair.
    ///
    /// ρ = (phi_target_after - phi_target_before) / lambda_source
    ///
    /// When `lambda_source ≤ 0` the observation is silently ignored
    /// (undefined return for zero-cost transmission).
    pub fn record_return(
        &self,
        source:            CausalId,
        target:            CausalId,
        lambda_source:     f64,
        phi_target_before: f64,
        phi_target_after:  f64,
    ) {
        if lambda_source <= 0.0 {
            return;
        }
        let rho = (phi_target_after - phi_target_before) / lambda_source;
        self.ema_map
            .entry((source, target))
            .or_insert_with(ReturnEma::new)
            .update(rho);
    }

    /// Aggregate return rate for `source` across all observed targets.
    ///
    /// Returns the arithmetic mean of all (source, *) EMA values.
    /// Returns `0.0` when `source` has no recorded observations.
    #[must_use]
    pub fn agent_return_rate(&self, source: CausalId) -> f64 {
        let entries: Vec<f64> = self
            .ema_map
            .iter()
            .filter(|e| e.key().0 == source)
            .map(|e| e.value().value)
            .collect();
        if entries.is_empty() {
            0.0
        } else {
            entries.iter().sum::<f64>() / entries.len() as f64
        }
    }

    /// Number of distinct (source, target) pairs tracked.
    #[must_use]
    pub fn pair_count(&self) -> usize {
        self.ema_map.len()
    }

    /// Push each tracked source agent's aggregate return rate into the CSO index.
    ///
    /// Iterates over all unique source agents in the map and calls
    /// [`CsoIndex::update_rho`] with their current [`agent_return_rate`].
    ///
    /// Intended to be called periodically by the AGI dual-engine loop to
    /// propagate observed causal efficiency into the global reputation index.
    pub fn flush_to_cso(&self, cso: &Arc<CsoIndex>) {
        // Collect unique source IDs without holding the DashMap shard lock.
        let sources: HashSet<CausalId> = self
            .ema_map
            .iter()
            .map(|e| e.key().0)
            .collect();

        for source in sources {
            let rate = self.agent_return_rate(source);
            cso.update_rho(source, rate);
        }
    }
}

impl Default for CausalReturnTracker {
    fn default() -> Self {
        Self::new()
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_return_rate_for_unknown_source() {
        let tracker = CausalReturnTracker::new();
        assert_eq!(tracker.agent_return_rate(CausalId(1)), 0.0);
    }

    #[test]
    fn hundred_zero_rho_observations_converge_below_threshold() {
        let tracker = CausalReturnTracker::new();
        let source = CausalId(1);
        let target = CausalId(2);
        // Seed with rho=1.0, then push toward 0 with 100 observations.
        tracker.record_return(source, target, 1.0, 0.0, 1.0); // rho = 1.0
        for _ in 0..100 {
            tracker.record_return(source, target, 1.0, 0.0, 0.0); // rho = 0.0
        }
        let rate = tracker.agent_return_rate(source);
        assert!(rate < 0.01, "after 100 zero observations, rate={rate} should be < 0.01");
    }

    #[test]
    fn positive_return_pushes_rate_up() {
        let tracker = CausalReturnTracker::new();
        let source = CausalId(10);
        let target = CausalId(20);
        for _ in 0..20 {
            tracker.record_return(source, target, 1.0, 0.0, 2.0); // rho = 2.0
        }
        let rate = tracker.agent_return_rate(source);
        assert!(rate > 1.5, "after 20 rho=2.0 observations, rate={rate} should be > 1.5");
    }

    #[test]
    fn zero_lambda_is_ignored() {
        let tracker = CausalReturnTracker::new();
        tracker.record_return(CausalId(1), CausalId(2), 0.0, 0.0, 100.0);
        assert_eq!(tracker.pair_count(), 0, "zero lambda should produce no entry");
    }

    #[test]
    fn multiple_targets_averaged() {
        let tracker = CausalReturnTracker::new();
        let source = CausalId(1);
        // Target A: converges toward rho=4.0
        for _ in 0..50 {
            tracker.record_return(source, CausalId(100), 1.0, 0.0, 4.0);
        }
        // Target B: converges toward rho=0.0
        for _ in 0..50 {
            tracker.record_return(source, CausalId(200), 1.0, 0.0, 0.0);
        }
        let rate = tracker.agent_return_rate(source);
        // Average of ~4.0 and ~0.0 = ~2.0
        assert!(rate > 1.0 && rate < 3.5, "average rate={rate} should be ~2.0");
    }
}
