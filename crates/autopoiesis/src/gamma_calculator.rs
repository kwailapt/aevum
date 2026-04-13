//! Pillar: II + III.  PACR field: Γ, Λ.
//!
//! Step 1 – OBSERVE: sliding-window aggregation of (S_T, H_T, Λ) snapshots.
//! Step 3 – PROPOSE metric: Γ_k = (ΔC_μ,k / C̄_μ,k) / (ΔΛ_k / Λ̄_k)
//!
//! Physical interpretation:
//! - Γ_k > 1 : cognition improves faster than thermodynamic cost grows — healthy.
//! - Γ_k ≈ 1 : neutral equilibrium.
//! - Γ_k < 0 : cognition degrades while cost grows — wasteful.
//! - Γ_k = None: insufficient data or denominator degenerate.
//!
//! The window is a fixed-capacity ring buffer; oldest entry is evicted when full.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use std::collections::VecDeque;

// ── Snapshot ──────────────────────────────────────────────────────────────────

/// One observation of the system's cognitive and thermodynamic state.
#[derive(Debug, Clone, PartialEq)]
pub struct Snapshot {
    /// Statistical complexity C_μ (bits) — from Γ.statistical_complexity.point.
    pub c_mu: f64,
    /// Entropy rate H_T (bits/sym) — from Γ.entropy_rate.point.
    pub h_t: f64,
    /// Landauer cost Λ (joules) — from the most-recent PacrRecord.landauer_cost.point.
    pub lambda: f64,
}

// ── GammaCalculator ───────────────────────────────────────���───────────────────

/// Sliding-window observer that tracks (C_μ, H_T, Λ) and computes Γ_k.
///
/// # Design
///
/// `capacity` sets the maximum number of snapshots retained.  A capacity of
/// `w` means at most `w` observations are used for Γ_k computation.  The
/// minimum meaningful capacity is 2 (need two snapshots to compute a delta).
#[derive(Debug, Clone)]
pub struct GammaCalculator {
    window: VecDeque<Snapshot>,
    capacity: usize,
}

impl GammaCalculator {
    /// Create a new calculator with the given window capacity (≥ 2).
    ///
    /// # Panics
    ///
    /// Panics if `capacity < 2` (cannot compute deltas from fewer than 2 points).
    #[must_use]
    pub fn new(capacity: usize) -> Self {
        assert!(capacity >= 2, "GammaCalculator capacity must be ≥ 2");
        Self {
            window: VecDeque::with_capacity(capacity),
            capacity,
        }
    }

    /// Push a new snapshot into the window, evicting the oldest if full.
    pub fn push(&mut self, snap: Snapshot) {
        if self.window.len() == self.capacity {
            self.window.pop_front();
        }
        self.window.push_back(snap);
    }

    /// Current number of snapshots in the window.
    #[must_use]
    pub fn len(&self) -> usize {
        self.window.len()
    }

    /// Returns `true` if the window is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.window.is_empty()
    }

    /// Returns `true` if the window has at least 2 snapshots (Γ_k computable).
    #[must_use]
    pub fn ready(&self) -> bool {
        self.window.len() >= 2
    }

    /// Compute Γ_k between the two most recent snapshots.
    ///
    /// ```text
    /// C̄_μ = (C_μ[k] + C_μ[k-1]) / 2          ΔC_μ = C_μ[k] − C_μ[k-1]
    /// Λ̄   = (Λ[k]   + Λ[k-1])   / 2          ΔΛ   = Λ[k]   − Λ[k-1]
    ///
    /// Γ_k = (ΔC_μ / C̄_μ) / (ΔΛ / Λ̄)
    /// ```
    ///
    /// Returns `None` when:
    /// - Fewer than 2 snapshots are present.
    /// - C̄_μ ≈ 0 (fully incompressible baseline — undefined normalisation).
    /// - ΔΛ ≈ 0 **and** ΔC_μ ≈ 0 → neutral (caller should treat as Γ_k = 1.0).
    /// - ΔΛ ≈ 0 but ΔC_μ ≠ 0 → unbounded (caller should treat as large |Γ_k|).
    ///
    /// # Stability
    ///
    /// The result is clamped to `[−100.0, 100.0]` to prevent upstream
    /// accumulation of floating-point extremes.
    #[must_use]
    pub fn gamma_k(&self) -> Option<f64> {
        if self.window.len() < 2 {
            return None;
        }
        let n = self.window.len();
        let prev = &self.window[n - 2];
        let curr = &self.window[n - 1];

        let delta_c = curr.c_mu - prev.c_mu;
        let c_bar   = (curr.c_mu + prev.c_mu) / 2.0;

        let delta_lambda = curr.lambda - prev.lambda;
        let lambda_bar   = (curr.lambda + prev.lambda) / 2.0;

        // Guard: C̄_μ ≈ 0 → undefined.
        if c_bar.abs() < 1e-15 {
            return None;
        }

        let rel_c = delta_c / c_bar;

        // Guard: ΔΛ ≈ 0.
        if delta_lambda.abs() < 1e-30 {
            // Both stable → neutral.  One nonzero → unbounded (return None).
            return if delta_c.abs() < 1e-15 { Some(1.0) } else { None };
        }

        // Guard: Λ̄ ≈ 0 (should not occur for real Landauer costs, but guard anyway).
        if lambda_bar.abs() < 1e-30 {
            return None;
        }

        let rel_lambda = delta_lambda / lambda_bar;
        let gamma = rel_c / rel_lambda;

        Some(gamma.clamp(-100.0, 100.0))
    }

    /// Compute Γ_k for every consecutive pair in the window.
    ///
    /// Returns a `Vec` of length `window.len() - 1`.  `None` entries indicate
    /// degenerate pairs (see [`gamma_k`]).
    #[must_use]
    pub fn gamma_series(&self) -> Vec<Option<f64>> {
        if self.window.len() < 2 {
            return Vec::new();
        }
        self.window
            .iter()
            .zip(self.window.iter().skip(1))
            .map(|(prev, curr)| {
                let delta_c      = curr.c_mu - prev.c_mu;
                let c_bar        = (curr.c_mu + prev.c_mu) / 2.0;
                let delta_lambda = curr.lambda - prev.lambda;
                let lambda_bar   = (curr.lambda + prev.lambda) / 2.0;

                if c_bar.abs() < 1e-15 {
                    return None;
                }
                let rel_c = delta_c / c_bar;
                if delta_lambda.abs() < 1e-30 {
                    return if delta_c.abs() < 1e-15 { Some(1.0) } else { None };
                }
                if lambda_bar.abs() < 1e-30 {
                    return None;
                }
                let rel_lambda = delta_lambda / lambda_bar;
                Some((rel_c / rel_lambda).clamp(-100.0, 100.0))
            })
            .collect()
    }

    /// Mean of all finite Γ_k values in the series.  Returns `None` if no
    /// finite values exist.
    #[must_use]
    pub fn mean_gamma(&self) -> Option<f64> {
        let series: Vec<f64> = self.gamma_series().into_iter().flatten().collect();
        if series.is_empty() {
            return None;
        }
        Some(series.iter().sum::<f64>() / series.len() as f64)
    }

    /// Most recent snapshot, if any.
    #[must_use]
    pub fn latest(&self) -> Option<&Snapshot> {
        self.window.back()
    }

    /// All snapshots in chronological order.
    #[must_use]
    pub fn snapshots(&self) -> &VecDeque<Snapshot> {
        &self.window
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(c: f64, h: f64, l: f64) -> Snapshot {
        Snapshot { c_mu: c, h_t: h, lambda: l }
    }

    #[test]
    fn gamma_k_neutral_when_both_stable() {
        let mut calc = GammaCalculator::new(4);
        calc.push(snap(1.0, 0.5, 1e-18));
        calc.push(snap(1.0, 0.5, 1e-18)); // no change in either
        // Both ΔC_μ=0 and ΔΛ=0 → neutral Γ_k = 1.0.
        assert_eq!(calc.gamma_k(), Some(1.0));
    }

    #[test]
    fn gamma_k_positive_when_cognition_grows_faster() {
        let mut calc = GammaCalculator::new(4);
        // C_μ doubles (rel_c = 2/1.5 ≈ 1.333), Λ grows 10 % (rel_λ = 0.1/1.05 ≈ 0.095).
        calc.push(snap(1.0, 0.5, 1.0e-18));
        calc.push(snap(2.0, 0.7, 1.1e-18));
        let g = calc.gamma_k().unwrap();
        assert!(g > 1.0, "Γ_k={g:.3} should be > 1");
    }

    #[test]
    fn gamma_k_negative_when_cognition_shrinks_cost_grows() {
        let mut calc = GammaCalculator::new(4);
        calc.push(snap(2.0, 0.8, 1.0e-18));
        calc.push(snap(1.0, 0.5, 2.0e-18)); // C_μ halves, Λ doubles
        let g = calc.gamma_k().unwrap();
        assert!(g < 0.0, "Γ_k={g:.3} should be < 0");
    }

    #[test]
    fn gamma_k_none_when_only_one_snapshot() {
        let mut calc = GammaCalculator::new(4);
        calc.push(snap(1.0, 0.5, 1e-18));
        assert_eq!(calc.gamma_k(), None);
    }

    #[test]
    fn gamma_k_none_when_c_bar_is_zero() {
        // C̄_μ = 0 → undefined normalisation.
        let mut calc = GammaCalculator::new(4);
        calc.push(snap(0.0, 0.0, 1e-18));
        calc.push(snap(0.0, 0.0, 2e-18));
        assert_eq!(calc.gamma_k(), None);
    }

    #[test]
    fn gamma_k_none_when_delta_lambda_zero_but_delta_c_nonzero() {
        let mut calc = GammaCalculator::new(4);
        calc.push(snap(1.0, 0.5, 1e-18));
        calc.push(snap(2.0, 0.7, 1e-18)); // ΔΛ = 0, ΔC_μ ≠ 0 → unbounded
        assert_eq!(calc.gamma_k(), None);
    }

    #[test]
    fn window_evicts_oldest_when_full() {
        let mut calc = GammaCalculator::new(2);
        calc.push(snap(1.0, 0.5, 1e-18));
        calc.push(snap(2.0, 0.6, 2e-18));
        assert_eq!(calc.len(), 2);
        // Push third — should evict first.
        calc.push(snap(3.0, 0.7, 3e-18));
        assert_eq!(calc.len(), 2);
        assert_eq!(calc.latest().unwrap().c_mu, 3.0);
    }

    #[test]
    fn gamma_series_length() {
        let mut calc = GammaCalculator::new(5);
        for i in 0..5 {
            calc.push(snap(1.0 + i as f64 * 0.1, 0.5, 1e-18 * (1.0 + i as f64 * 0.01)));
        }
        assert_eq!(calc.gamma_series().len(), 4);
    }

    #[test]
    fn mean_gamma_on_uniform_series() {
        let mut calc = GammaCalculator::new(5);
        for i in 0..5 {
            let f = 1.0 + i as f64;
            calc.push(snap(f, 0.5, f * 1e-18));
        }
        // All pairs have the same ΔC/C̄ / ΔΛ/Λ̄ pattern; mean should be finite.
        assert!(calc.mean_gamma().is_some());
    }
}
