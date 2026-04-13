//! Pillar: II. PACR field: Λ (aggregate flow rate).
//!
//! **Thermodynamic Pressure Gauge** — pure-physics rate limiting.
//!
//! # Physical Axiom
//!
//! No channel can sustain an average power (watts) exceeding its thermodynamic
//! capacity.  This gauge accumulates Λ (joules) across envelopes and rejects
//! further envelopes once the accumulated power (`accumulated_J / window_s`)
//! exceeds `max_watts`.
//!
//! The check is O(1), lock-free, allocation-free, and runs on **both**
//! `genesis_node` and `light_node` deployments.
//!
//! # Usage
//!
//! ```rust
//! use aevum_core::pressure_gauge::ThermodynamicPressureGauge;
//!
//! let gauge = ThermodynamicPressureGauge::new(1e-3, 1.0); // 1 mW cap, 1 s window
//! // Inject a small envelope — should pass.
//! assert!(!gauge.should_throttle(1e-10));
//! ```
//!
//! Call [`ThermodynamicPressureGauge::reset_window`] periodically (e.g. every
//! `window_duration_secs`) from a background task to slide the window forward.

#![forbid(unsafe_code)]

use std::sync::atomic::{AtomicU64, Ordering};

// ── ThermodynamicPressureGauge ────────────────────────────────────────────────

/// Lock-free thermodynamic pressure gauge.
///
/// Accumulates envelope Λ values as integer picojoule counts (u64).
/// When the implied power `accumulated_J / window_s` exceeds `max_watts`
/// the gauge signals that the envelope must be throttled.
pub struct ThermodynamicPressureGauge {
    /// Cumulative Λ in the current window, stored as picojoules (×10^12 J).
    ///
    /// Using integer picojoules avoids floating-point atomics while giving
    /// 1 pJ resolution — sufficient for Landauer-scale bookkeeping.
    window_pj: AtomicU64,

    /// Maximum allowed average power in watts (joules per second).
    max_watts: f64,

    /// Duration of one accounting window in seconds.
    window_duration_secs: f64,
}

impl ThermodynamicPressureGauge {
    /// Create a new gauge.
    ///
    /// # Arguments
    ///
    /// * `max_watts`           — maximum allowed average power (W).
    ///   Use `f64::MAX` to disable throttling (pass-through mode).
    /// * `window_duration_secs` — accounting window length in seconds.
    #[must_use]
    pub fn new(max_watts: f64, window_duration_secs: f64) -> Self {
        Self {
            window_pj:            AtomicU64::new(0),
            max_watts,
            window_duration_secs,
        }
    }

    /// Returns `true` if this envelope should be **dropped** (throttled).
    ///
    /// O(1), lock-free, no allocation.
    ///
    /// # Arguments
    ///
    /// * `envelope_lambda_joules` — the Λ field of the incoming envelope.
    pub fn should_throttle(&self, envelope_lambda_joules: f64) -> bool {
        // Convert joules to picojoules and clamp to u64 range.
        let delta_pj = (envelope_lambda_joules * 1e12) as u64;

        // Atomic accumulation — Relaxed is sufficient: we care only about the
        // final value within the window, not synchronisation order across threads.
        let prev_pj = self.window_pj.fetch_add(delta_pj, Ordering::Relaxed);
        let total_pj = prev_pj.saturating_add(delta_pj);

        // Implied power: total_joules / window_duration_secs
        let total_joules = total_pj as f64 * 1e-12;
        total_joules / self.window_duration_secs > self.max_watts
    }

    /// Reset the accounting window.
    ///
    /// Must be called periodically (every `window_duration_secs`) by the
    /// runtime to slide the window forward.  O(1), lock-free.
    pub fn reset_window(&self) {
        self.window_pj.store(0, Ordering::Relaxed);
    }

    /// Read the current accumulated Λ in picojoules without modifying state.
    #[must_use]
    pub fn accumulated_pj(&self) -> u64 {
        self.window_pj.load(Ordering::Relaxed)
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Basic pass/throttle ───────────────────────────────────────────────────

    #[test]
    fn pass_through_mode_never_throttles() {
        let gauge = ThermodynamicPressureGauge::new(f64::MAX, 1.0);
        for _ in 0..10_000 {
            assert!(!gauge.should_throttle(1e-3), "MAX watts should never throttle");
        }
    }

    #[test]
    fn throttles_after_budget_exceeded() {
        // Budget: 1 nW over 1 s window = 1e-9 J total.
        let gauge = ThermodynamicPressureGauge::new(1e-9, 1.0);

        // First envelope: 5e-10 J → accumulated 5e-10 J → 5e-10 W < 1e-9 W → pass.
        assert!(!gauge.should_throttle(5e-10), "first envelope should pass");

        // Second envelope: adds another 5e-10 J → total 1e-9 J → exactly 1e-9 W.
        // Strictly greater than max_watts is required for throttle, so 1e-9 == 1e-9 passes.
        // Add a tiny bit more.
        gauge.should_throttle(1e-13); // push just past budget
        assert!(gauge.should_throttle(1e-3), "should throttle after budget exceeded");
    }

    // ── Reset window ──────────────────────────────────────────────────────────

    #[test]
    fn reset_clears_accumulator() {
        let gauge = ThermodynamicPressureGauge::new(1e-15, 1.0);
        // Fill well past budget.
        for _ in 0..1_000 {
            gauge.should_throttle(1e-12);
        }
        assert!(gauge.should_throttle(1e-12), "should be throttled before reset");

        gauge.reset_window();
        assert_eq!(gauge.accumulated_pj(), 0, "accumulator must be zero after reset");
        // After reset the first small envelope should pass.
        assert!(!gauge.should_throttle(1e-20), "first envelope after reset should pass");
    }

    // ── Accumulated reading ───────────────────────────────────────────────────

    #[test]
    fn accumulated_pj_reflects_ingested_lambda() {
        let gauge = ThermodynamicPressureGauge::new(f64::MAX, 1.0);
        gauge.should_throttle(1e-12); // 1 pJ
        gauge.should_throttle(1e-12); // 1 pJ
        // Expect ≈ 2 pJ total.
        let pj = gauge.accumulated_pj();
        assert!(pj >= 1 && pj <= 4, "accumulated ≈ 2 pJ, got {pj}");
    }

    // ── Zero-lambda envelopes ─────────────────────────────────────────────────

    #[test]
    fn zero_lambda_never_throttles_by_itself() {
        let gauge = ThermodynamicPressureGauge::new(1e-20, 1.0);
        for _ in 0..10_000 {
            assert!(!gauge.should_throttle(0.0), "zero Λ should never throttle");
        }
    }
}
