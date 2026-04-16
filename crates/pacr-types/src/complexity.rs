//! Pillar: III. PACR field: Γ (Cognitive Split).
//!
//! Computational mechanics fundamental theorem (arXiv:2601.03220):
//! any data stream admits a unique decomposition into two inseparable projections
//! of the same ε-machine:
//!
//!   `S_T` — statistical complexity (bits)
//!         Minimum causal-state information needed to optimally predict the stream.
//!         Rising `S_T` → the system is discovering learnable structure.
//!
//!   `H_T` — entropy rate (bits per symbol)
//!         Residual unpredictability that cannot be further compressed.
//!         Rising `H_T` → the system is encountering irreducible noise.
//!
//! These two quantities are OBSERVER-DEPENDENT (the observer's computational
//! budget `T_budget` determines the ε-machine approximation order) and
//! INSEPARABLE — removing either one from the record permanently loses
//! information that cannot be recovered from the other.

use crate::estimate::Estimate;

// ── Core type ─────────────────────────────────────────────────────────────────

/// The cognitive split Γ = (`S_T`, `H_T`): intrinsic information structure of the
/// processed data stream, as computed by the ε-machine approximation.
///
/// PACR field Γ.  Derived from Pillar III (computational mechanics).
#[derive(Debug, Clone, Copy, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct CognitiveSplit {
    /// Statistical complexity `S_T` (bits).
    /// Minimum information needed to optimally predict the stream.
    pub statistical_complexity: Estimate<f64>,

    /// Entropy rate `H_T` (bits per symbol).
    /// Residual unpredictability even with the optimal predictor.
    pub entropy_rate: Estimate<f64>,
}

impl CognitiveSplit {
    /// Structure-to-noise ratio: `S_T` / `H_T`.
    ///
    /// - **High** → structured, predictable stream (e.g. chess move sequences).
    /// - **Low** → simple but random stream (e.g. fair-coin outputs).
    /// - `None` → `H_T` ≈ 0, stream is fully deterministic; ratio is effectively ∞.
    #[must_use]
    pub fn structure_noise_ratio(&self) -> Option<f64> {
        if self.entropy_rate.point.abs() < f64::EPSILON {
            return None; // deterministic stream; avoid division by near-zero
        }
        Some(self.statistical_complexity.point / self.entropy_rate.point)
    }

    /// Returns `true` when `S_T` > `H_T` (or `H_T` ≈ 0), indicating a stream with
    /// more learnable structure than irreducible randomness.
    #[must_use]
    pub fn is_structured(&self) -> bool {
        self.structure_noise_ratio().is_none_or(|r| r > 1.0)
    }
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::estimate::Estimate;

    #[test]
    fn structured_stream_ratio_gt_one() {
        let g = CognitiveSplit {
            statistical_complexity: Estimate::exact(4.0),
            entropy_rate:           Estimate::exact(1.0),
        };
        let r = g.structure_noise_ratio().unwrap();
        assert!((r - 4.0).abs() < f64::EPSILON);
        assert!(g.is_structured());
    }

    #[test]
    fn noisy_stream_ratio_lt_one() {
        let g = CognitiveSplit {
            statistical_complexity: Estimate::exact(0.5),
            entropy_rate:           Estimate::exact(2.0),
        };
        assert!(!g.is_structured());
    }

    #[test]
    fn deterministic_stream_returns_none_and_is_structured() {
        let g = CognitiveSplit {
            statistical_complexity: Estimate::exact(3.0),
            entropy_rate:           Estimate::exact(0.0),
        };
        assert!(g.structure_noise_ratio().is_none());
        assert!(g.is_structured()); // deterministic → always structured
    }

    #[test]
    fn equal_complexity_and_entropy_ratio_is_one() {
        let g = CognitiveSplit {
            statistical_complexity: Estimate::exact(2.0),
            entropy_rate:           Estimate::exact(2.0),
        };
        let r = g.structure_noise_ratio().unwrap();
        assert!((r - 1.0).abs() < f64::EPSILON);
    }
}
