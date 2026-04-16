//! Pillar: III + I. PACR fields: Γ + Π.
//!
//! **Flood Detector** — detects flood attacks via cognitive signature.
//!
//! # Physical Axiom
//!
//! A flood attack exhibits a characteristic cognitive signature: many
//! structurally similar packets from few sources.  Statistically, `S_T` drops
//! rapidly (structure becomes repetitive) while the inflow rate spikes.
//!
//! This module monitors source concentration in a sliding window.  When one
//! source dominates beyond a configurable threshold, the verdict flips to
//! [`FloodVerdict::FloodDetected`], triggering the immune response chain.
//!
//! # Usage
//!
//! ```rust
//! use autopoiesis::flood_detector::{FloodDetector, FloodVerdict};
//! use pacr_types::CausalId;
//!
//! let mut detector = FloodDetector::new(1000, 0.8);
//! for _ in 0..900 {
//!     detector.ingest(CausalId(42)); // dominant source
//! }
//! for _ in 0..100 {
//!     detector.ingest(CausalId(1));  // minority source
//! }
//! assert!(matches!(detector.diagnose(), FloodVerdict::FloodDetected { .. }));
//! ```

use std::collections::HashMap;

use pacr_types::CausalId;

// ── FloodDetector ─────────────────────────────────────────────────────────────

/// Sliding-window source-concentration monitor.
///
/// Tracks how many records each source agent contributes within a window.
/// When the dominant source's share exceeds `concentration_threshold`, the
/// detector emits [`FloodVerdict::FloodDetected`].
pub struct FloodDetector {
    /// Record count per source agent in the current window.
    source_counts: HashMap<CausalId, u64>,
    /// Total records ingested in the current window.
    total_count: u64,
    /// Window size in records.  After `window_size` records the window resets.
    window_size: u64,
    /// Fraction of total inflow from a single source that triggers a flood verdict.
    concentration_threshold: f64,
}

impl FloodDetector {
    /// Create a new detector.
    ///
    /// # Arguments
    ///
    /// * `window_size`              — number of records per sliding window.
    /// * `concentration_threshold`  — fraction in `(0, 1]`; when the dominant
    ///   source's share exceeds this value the detector emits `FloodDetected`.
    #[must_use]
    pub fn new(window_size: u64, concentration_threshold: f64) -> Self {
        Self {
            source_counts: HashMap::new(),
            total_count: 0,
            window_size,
            concentration_threshold,
        }
    }

    /// Ingest one record from `source_agent`.
    ///
    /// When the window is full the counters are reset so the next call starts
    /// a fresh window.
    pub fn ingest(&mut self, source_agent: CausalId) {
        // Sliding window: reset after window_size records.
        if self.total_count >= self.window_size {
            self.source_counts.clear();
            self.total_count = 0;
        }

        *self.source_counts.entry(source_agent).or_insert(0) += 1;
        self.total_count += 1;
    }

    /// Diagnose the current window.
    ///
    /// Returns [`FloodVerdict::Normal`] if the window has fewer than 100 records
    /// (insufficient data) or if no single source exceeds the threshold.
    ///
    /// Returns [`FloodVerdict::FloodDetected`] with the dominant source and its
    /// concentration (as percentage × 100 integer) when the threshold is breached.
    #[must_use]
    pub fn diagnose(&self) -> FloodVerdict {
        if self.total_count < 100 {
            return FloodVerdict::Normal;
        }

        let Some((&dominant, &max_count)) =
            self.source_counts.iter().max_by_key(|(_, count)| *count)
        else {
            return FloodVerdict::Normal;
        };

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

// ── FloodVerdict ──────────────────────────────────────────────────────────────

/// Diagnosis emitted by [`FloodDetector::diagnose`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FloodVerdict {
    /// No flood detected — inflow is within normal bounds.
    Normal,
    /// Flood detected — a single source dominates inflow beyond the threshold.
    FloodDetected {
        /// The source agent contributing the most records this window.
        dominant_source: CausalId,
        /// Concentration as percentage × 100 (e.g. 8500 = 85%).
        concentration: u64,
    },
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[allow(dead_code)]
    fn flood_from_one_source(window: u64, threshold: f64, dominant_count: u64) -> FloodVerdict {
        let mut d = FloodDetector::new(window, threshold);
        for _ in 0..dominant_count {
            d.ingest(CausalId(1));
        }
        // Fill the rest of the minimum-100 quota with other sources.
        let remaining = 100_u64.saturating_sub(dominant_count);
        for i in 0..remaining {
            d.ingest(CausalId(u128::from(i) + 2));
        }
        d.diagnose()
    }

    // ── Below minimum count ───────────────────────────────────────────────────

    #[test]
    fn normal_below_minimum_count() {
        let mut d = FloodDetector::new(1000, 0.5);
        for _ in 0..99 {
            d.ingest(CausalId(1));
        }
        assert_eq!(d.diagnose(), FloodVerdict::Normal);
    }

    // ── Flood detection ───────────────────────────────────────────────────────

    #[test]
    fn detects_flood_above_threshold() {
        // 900 out of 1000 records from source 1 → 90% concentration, threshold 0.8
        let mut d = FloodDetector::new(1000, 0.8);
        for _ in 0..900 {
            d.ingest(CausalId(1));
        }
        for i in 1..=100 {
            d.ingest(CausalId(i + 1));
        }
        let verdict = d.diagnose();
        assert!(
            matches!(
                verdict,
                FloodVerdict::FloodDetected {
                    dominant_source: CausalId(1),
                    ..
                }
            ),
            "expected FloodDetected from source 1, got: {verdict:?}"
        );
    }

    #[test]
    fn flood_concentration_encoded_as_percentage_times_100() {
        // 950/1000 = 95% → concentration field = 95
        let mut d = FloodDetector::new(1000, 0.5);
        for _ in 0..950 {
            d.ingest(CausalId(42));
        }
        for i in 0..50 {
            d.ingest(CausalId(i + 100));
        }
        let verdict = d.diagnose();
        if let FloodVerdict::FloodDetected { concentration, .. } = verdict {
            assert!(
                concentration >= 94 && concentration <= 96,
                "expected ≈95, got {concentration}"
            );
        } else {
            panic!("expected FloodDetected, got Normal");
        }
    }

    // ── Normal traffic ────────────────────────────────────────────────────────

    #[test]
    fn normal_when_traffic_distributed() {
        // 10 sources, 100 records each → 10% each, threshold 0.8
        let mut d = FloodDetector::new(2000, 0.8);
        for source in 0..10_u128 {
            for _ in 0..100 {
                d.ingest(CausalId(source));
            }
        }
        assert_eq!(d.diagnose(), FloodVerdict::Normal);
    }

    // ── Window reset ──────────────────────────────────────────────────────────

    #[test]
    fn window_resets_after_window_size() {
        let mut d = FloodDetector::new(200, 0.8);
        // Fill first window with flood traffic.
        for _ in 0..200 {
            d.ingest(CausalId(1));
        }
        // Next ingest resets the window. Then add balanced traffic.
        for source in 0..10_u128 {
            for _ in 0..10 {
                d.ingest(CausalId(source));
            }
        }
        // Window now has 100 records, spread evenly — should be Normal.
        assert_eq!(d.diagnose(), FloodVerdict::Normal);
    }

    // ── Threshold boundary ────────────────────────────────────────────────────

    #[test]
    fn normal_exactly_at_threshold() {
        // Exactly at threshold (not above) → Normal.
        let mut d = FloodDetector::new(1000, 0.5);
        for _ in 0..500 {
            d.ingest(CausalId(1));
        }
        for i in 0..500 {
            d.ingest(CausalId(i + 2));
        }
        // concentration = 0.5, threshold = 0.5 → NOT strictly greater → Normal
        assert_eq!(d.diagnose(), FloodVerdict::Normal);
    }
}
