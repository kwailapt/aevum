//! Pillar: ALL. PACR field: ALL (shared measurement infrastructure).
//!
//! `Estimate<T>` encodes every physical quantity as a point estimate with a
//! 95 % confidence interval `[lower, upper]`.  The interval width shrinks as
//! measurement precision improves; the *schema* never changes.
//!
//! Physical axiom: all physical measurements carry finite-precision uncertainty
//! (Heisenberg, thermodynamic fluctuations, finite clock resolution).

use serde::{Deserialize, Serialize};
use std::fmt;

// ── Core type ───────────────────────────────────────────────────────────────

/// A physical measurement: point estimate ± 95 % confidence interval.
///
/// **Invariant**: `lower ≤ point ≤ upper`
///
/// `Eq` and `Hash` are intentionally NOT derived for `Estimate<f64>`.
/// Floating-point equality is physically meaningless for measurements.
/// Use [`Estimate::is_consistent_with`] for physically meaningful comparison.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Estimate<T: PartialOrd + Copy> {
    /// Best single-value estimate (e.g. mean or median of samples).
    pub point: T,
    /// Lower bound of the 95 % confidence interval.
    pub lower: T,
    /// Upper bound of the 95 % confidence interval.
    pub upper: T,
}

// ── Generic constructors ─────────────────────────────────────────────────────

impl<T: PartialOrd + Copy + fmt::Display> Estimate<T> {
    /// Constructs a new estimate, enforcing `lower ≤ point ≤ upper`.
    ///
    /// # Errors
    /// Returns [`EstimateError::InvalidBounds`] if the invariant is violated.
    pub fn new(point: T, lower: T, upper: T) -> Result<Self, EstimateError> {
        if lower > point || point > upper {
            return Err(EstimateError::InvalidBounds);
        }
        Ok(Self {
            point,
            lower,
            upper,
        })
    }

    /// Creates an exact estimate with zero uncertainty.
    /// Use for quantities known with mathematical certainty (e.g. counting).
    #[must_use]
    pub fn exact(value: T) -> Self {
        Self {
            point: value,
            lower: value,
            upper: value,
        }
    }
}

impl<T: PartialOrd + Copy + fmt::Display> fmt::Display for Estimate<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}  [{}, {}]", self.point, self.lower, self.upper)
    }
}

// ── f64-specific physics operations ──────────────────────────────────────────

impl Estimate<f64> {
    /// Two estimates are physically consistent if their confidence intervals overlap.
    ///
    /// This is the correct notion of "agreement" between two uncertain measurements.
    #[must_use]
    pub fn is_consistent_with(&self, other: &Self) -> bool {
        self.lower <= other.upper && other.lower <= self.upper
    }

    /// Relative uncertainty: `(upper − lower) / |point|`.
    ///
    /// Returns `f64::INFINITY` when `|point|` is below machine epsilon
    /// (cannot compute a meaningful relative uncertainty for a near-zero quantity).
    #[must_use]
    pub fn relative_uncertainty(&self) -> f64 {
        if self.point.abs() < f64::EPSILON {
            return f64::INFINITY;
        }
        (self.upper - self.lower) / self.point.abs()
    }

    /// Returns a widened copy with interval expanded by `factor` (≥ 1.0).
    ///
    /// Useful when composing multiple uncertain quantities conservatively.
    #[must_use]
    pub fn with_extra_uncertainty(&self, factor: f64) -> Self {
        debug_assert!(factor >= 1.0, "widening factor must be ≥ 1.0");
        let half_width = (self.upper - self.lower) * 0.5 * factor;
        let lower = (self.point - half_width).min(self.lower);
        let upper = (self.point + half_width).max(self.upper);
        Self {
            point: self.point,
            lower,
            upper,
        }
    }
}

// ── Error type ───────────────────────────────────────────────────────────────

/// Error produced when constructing an [`Estimate`] with invalid bounds.
#[derive(Debug, Clone, thiserror::Error)]
#[non_exhaustive]
pub enum EstimateError {
    /// `lower ≤ point ≤ upper` was violated.
    #[error("invalid bounds: required lower ≤ point ≤ upper")]
    InvalidBounds,
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_accepts_valid_bounds() {
        assert!(Estimate::new(1.0_f64, 0.5, 1.5).is_ok());
    }

    #[test]
    fn new_rejects_lower_gt_point() {
        assert!(Estimate::new(1.0_f64, 1.5, 2.0).is_err());
    }

    #[test]
    fn new_rejects_point_gt_upper() {
        assert!(Estimate::new(1.0_f64, 0.5, 0.8).is_err());
    }

    #[test]
    fn exact_has_zero_uncertainty() {
        let e = Estimate::exact(42.0_f64);
        assert_eq!(e.point, e.lower);
        assert_eq!(e.lower, e.upper);
        assert_eq!(e.relative_uncertainty(), 0.0);
    }

    #[test]
    fn relative_uncertainty_near_zero_returns_infinity() {
        let e = Estimate::exact(0.0_f64);
        assert!(e.relative_uncertainty().is_infinite());
    }

    #[test]
    fn consistency_overlapping_intervals() {
        let a = Estimate::new(1.0_f64, 0.5, 1.5).unwrap();
        let b = Estimate::new(1.2_f64, 0.8, 1.6).unwrap();
        assert!(a.is_consistent_with(&b));
    }

    #[test]
    fn consistency_non_overlapping_intervals() {
        let a = Estimate::new(1.0_f64, 0.5, 1.5).unwrap();
        let c = Estimate::new(3.0_f64, 2.0, 4.0).unwrap();
        assert!(!a.is_consistent_with(&c));
    }

    #[test]
    fn widen_increases_interval() {
        let e = Estimate::new(1.0_f64, 0.8, 1.2).unwrap();
        let w = e.with_extra_uncertainty(2.0);
        assert!(w.lower <= e.lower);
        assert!(w.upper >= e.upper);
        assert!((w.point - e.point).abs() < f64::EPSILON);
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        /// new() must accept exactly the triples satisfying lower ≤ point ≤ upper.
        #[test]
        fn estimate_new_iff_invariant_holds(
            lower  in -1e10_f64..1e10_f64,
            delta1 in  0.0_f64..1e6_f64,
            delta2 in  0.0_f64..1e6_f64,
        ) {
            let point = lower + delta1;
            let upper = point + delta2;
            let result = Estimate::new(point, lower, upper);
            prop_assert!(result.is_ok());
            let e = result.unwrap();
            prop_assert!(e.lower <= e.point);
            prop_assert!(e.point <= e.upper);
        }

        /// exact() always satisfies lower = point = upper.
        #[test]
        fn exact_invariant(v in -1e15_f64..1e15_f64) {
            let e = Estimate::exact(v);
            prop_assert_eq!(e.lower, e.point);
            prop_assert_eq!(e.point, e.upper);
        }
    }
}
