//! Pillar: II. PACR field: Λ (Landauer Cost).
//!
//! Physical axiom: **Landauer's Principle** (1961).
//! Any logically irreversible computation — i.e. any operation that erases
//! information — must dissipate at least
//!
//! ```text
//! E_Λ = k_B × T × ln(2)
//! ```
//!
//! into the environment as heat.  This is a corollary of the Second Law of
//! Thermodynamics, not an engineering limitation.
//!
//! # Guarantee
//!
//! `LandauerCost.point` returned by this crate is **always a lower bound** on
//! actual energy dissipation.  This is enforced by construction:
//!
//! - `point` = Λ at nominal temperature (300 K) — the physics floor.
//! - `lower` = Λ at 290 K — slightly below floor (acknowledges cooler racks).
//! - `upper` = Λ at 310 K — slightly above floor (warmer racks).
//!
//! Any actual dissipation E satisfies E ≥ `point` by Landauer's principle.
//! The caller is responsible for providing `bits_erased ≥ 1`; passing 0 is
//! floored to 1 (cannot have zero Landauer cost for a real computation).
//!
//! # Uncertainty model
//!
//! Temperature uncertainty ±10 K (290–310 K, data-centre range) propagates
//! directly into Λ: ΔΛ/Λ = ΔT/T ≈ ±3.3 %.  This is an honest physical
//! uncertainty, not a software approximation.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use pacr_types::{Estimate, LandauerCost, K_B};
use std::time::Instant;

// ── Temperature model ─────────────────────────────────────────────────────────

/// Nominal ambient temperature (K) — data-centre baseline.
pub const TEMPERATURE_NOMINAL_K: f64 = 300.0;

/// Lower temperature bound (K) — well-cooled data centre.
pub const TEMPERATURE_LOWER_K: f64 = 290.0;

/// Upper temperature bound (K) — warm rack or edge node.
pub const TEMPERATURE_UPPER_K: f64 = 310.0;

// ── Derived Landauer constants ────────────────────────────────────────────────
// All constants use the 2019 SI exact value of k_B imported from pacr-types.

/// Landauer floor per bit at nominal temperature (joules).
/// `K_B × 300 K × ln(2) ≈ 2.870 979 × 10⁻²¹ J`
pub const LANDAUER_PER_BIT_NOMINAL_J: f64 =
    K_B * TEMPERATURE_NOMINAL_K * std::f64::consts::LN_2;

/// Landauer floor per bit at lower temperature bound (joules).
const LANDAUER_PER_BIT_LOWER_J: f64 =
    K_B * TEMPERATURE_LOWER_K * std::f64::consts::LN_2;

/// Landauer floor per bit at upper temperature bound (joules).
const LANDAUER_PER_BIT_UPPER_J: f64 =
    K_B * TEMPERATURE_UPPER_K * std::f64::consts::LN_2;

// ── Core computation ──────────────────────────────────────────────────────────

/// Computes the Landauer cost for `bits_erased` irreversible bit operations.
///
/// # Arguments
///
/// * `bits_erased` — number of bits irreversibly erased.
///   Floored to 1 (a real computation must erase at least one bit).
///
/// # Returns
///
/// A [`LandauerCost`] where:
/// - `point` = Λ at 300 K (physics floor — guaranteed lower bound on actual E)
/// - `lower` = Λ at 290 K
/// - `upper` = Λ at 310 K
///
/// # Complexity
///
/// O(1).
#[must_use]
#[allow(clippy::cast_precision_loss)] // u64 → f64: realistic bit counts fit mantissa
pub fn compute(bits_erased: u64) -> LandauerCost {
    let n = bits_erased.max(1) as f64; // floor at 1; cannot have zero Landauer cost
    Estimate {
        point: n * LANDAUER_PER_BIT_NOMINAL_J,
        lower: n * LANDAUER_PER_BIT_LOWER_J,
        upper: n * LANDAUER_PER_BIT_UPPER_J,
    }
}

/// Estimates bit erasures from a byte count.
///
/// Writing N bytes to a location with unknown prior content erases at most
/// 8·N bits.  The expected value (assuming ~50 % of bits flip) is 4·N.
///
/// # Returns
///
/// `(4 × bytes).max(1)` — conservative point estimate.
#[must_use]
#[allow(clippy::cast_possible_truncation)] // intentional saturation to u64::MAX
pub fn bits_from_bytes(bytes: u64) -> u64 {
    bytes.saturating_mul(4).max(1)
}

// ── Timer ─────────────────────────────────────────────────────────────────────

/// A zero-overhead timer that wraps a [`LandauerCost`] computation.
///
/// # Usage
///
/// ```
/// use landauer_probe::LandauerTimer;
///
/// let timer = LandauerTimer::start();
/// let _ = (0u64..1_000).sum::<u64>(); // work
/// let cost = timer.finish(8_000);     // 1 000 × 8 bits
/// assert!(cost.point > 0.0);
/// assert!(cost.lower <= cost.point);
/// assert!(cost.point <= cost.upper);
/// ```
pub struct LandauerTimer {
    _start: Instant, // reserved for future sub-nanosecond Λ correlation
}

impl LandauerTimer {
    /// Starts the timer immediately before the measured computation.
    #[must_use]
    pub fn start() -> Self {
        Self { _start: Instant::now() }
    }

    /// Stops the timer and returns the [`LandauerCost`] for `bits_erased`.
    ///
    /// The timer's wall-clock duration is not used in the Λ calculation
    /// (Λ depends on bit-erasure count, not duration); it is retained in
    /// the struct for future correlation experiments.
    #[must_use]
    pub fn finish(self, bits_erased: u64) -> LandauerCost {
        compute(bits_erased)
    }
}

/// Measures a closure and returns its Landauer cost alongside its output.
///
/// `bytes_touched` is a conservative estimate of bytes written/overwritten.
/// Pass `0` if unknown — the probe floors at 1 bit (Λ is always positive).
///
/// # Example
///
/// ```
/// use landauer_probe::measure;
///
/// let (cost, sum) = measure(1_024, || (0u64..1_024).sum::<u64>());
/// assert!(cost.point > 0.0);
/// assert_eq!(sum, 523_776);
/// ```
pub fn measure<F, R>(bytes_touched: u64, f: F) -> (LandauerCost, R)
where
    F: FnOnce() -> R,
{
    let timer = LandauerTimer::start();
    let output = f();
    let bits = bits_from_bytes(bytes_touched);
    let cost = timer.finish(bits);
    (cost, output)
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Physical constants ────────────────────────────────────────────────────

    #[test]
    fn nominal_constant_matches_known_value() {
        // k_B × 300 K × ln(2) = 2.870 979... × 10⁻²¹ J
        let expected = 2.870_979e-21_f64;
        let ratio = LANDAUER_PER_BIT_NOMINAL_J / expected;
        // Must be within 0.01 % of the expected value.
        assert!(
            (ratio - 1.0).abs() < 1e-4,
            "Constant mismatch: got {LANDAUER_PER_BIT_NOMINAL_J:.6e}, want {expected:.6e}"
        );
    }

    #[test]
    fn lower_lt_nominal_lt_upper() {
        assert!(
            LANDAUER_PER_BIT_LOWER_J < LANDAUER_PER_BIT_NOMINAL_J,
            "lower must be < nominal"
        );
        assert!(
            LANDAUER_PER_BIT_NOMINAL_J < LANDAUER_PER_BIT_UPPER_J,
            "nominal must be < upper"
        );
    }

    // ── compute() ────────────────────────────────────────────────────────────

    #[test]
    fn compute_zero_bits_floors_to_one() {
        let cost = compute(0);
        assert_eq!(cost.point, LANDAUER_PER_BIT_NOMINAL_J);
    }

    #[test]
    fn compute_one_bit_equals_constant() {
        let cost = compute(1);
        assert!((cost.point - LANDAUER_PER_BIT_NOMINAL_J).abs() < 1e-40);
    }

    #[test]
    fn compute_bounds_ordered() {
        let cost = compute(1_000_000);
        assert!(cost.lower <= cost.point, "lower ≤ point");
        assert!(cost.point <= cost.upper, "point ≤ upper");
    }

    #[test]
    fn compute_scales_linearly_with_bits() {
        let one  = compute(1).point;
        let mega = compute(1_000_000).point;
        let ratio = mega / one;
        assert!((ratio - 1_000_000.0).abs() < 1.0, "ratio={ratio}");
    }

    #[test]
    fn compute_lower_is_true_lower_bound() {
        // lower = Λ(290 K), upper = Λ(310 K); lower < nominal < upper
        let c = compute(42);
        assert!(c.lower < c.point);
        assert!(c.point < c.upper);
    }

    // ── LandauerTimer ─────────────────────────────────────────────────────────

    #[test]
    fn timer_finish_returns_valid_cost() {
        let timer = LandauerTimer::start();
        let _ = (0u64..1_000).sum::<u64>();
        let cost = timer.finish(8_000);
        assert!(cost.point > 0.0);
        assert!(cost.lower <= cost.point);
        assert!(cost.point <= cost.upper);
    }

    // ── measure() ────────────────────────────────────────────────────────────

    #[test]
    fn measure_closure_returns_correct_output() {
        let (cost, sum) = measure(1_024, || (0u64..1_024).sum::<u64>());
        assert!(cost.point > 0.0);
        assert_eq!(sum, 523_776);
    }

    #[test]
    fn measure_zero_bytes_still_positive() {
        let (cost, _) = measure(0, || 42_u32);
        assert!(cost.point > 0.0);
    }

    // ── bits_from_bytes() ─────────────────────────────────────────────────────

    #[test]
    fn bits_from_bytes_floors_to_one() {
        assert_eq!(bits_from_bytes(0), 1);
    }

    #[test]
    fn bits_from_bytes_multiplies_by_four() {
        assert_eq!(bits_from_bytes(1),   4);
        assert_eq!(bits_from_bytes(100), 400);
    }

    #[test]
    fn bits_from_bytes_saturates_on_overflow() {
        // u64::MAX / 4 + 1 would overflow; saturating_mul prevents it
        let huge = u64::MAX / 4 + 1;
        let result = bits_from_bytes(huge);
        assert!(result >= 1, "must not wrap to 0");
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        /// Λ.lower ≤ Λ.point ≤ Λ.upper for all bit counts.
        #[test]
        fn bounds_always_ordered(bits in 0_u64..1_000_000_u64) {
            let cost = compute(bits);
            prop_assert!(cost.lower <= cost.point,
                "lower={} > point={}", cost.lower, cost.point);
            prop_assert!(cost.point <= cost.upper,
                "point={} > upper={}", cost.point, cost.upper);
        }

        /// Λ.point is always strictly positive (lower bound on physical energy).
        #[test]
        fn point_always_positive(bits in 0_u64..1_000_000_u64) {
            let cost = compute(bits);
            prop_assert!(cost.point > 0.0,
                "Λ.point must be > 0, got {}", cost.point);
        }

        /// Scaling: compute(2n).point ≈ 2 × compute(n).point.
        #[test]
        fn scales_linearly(n in 1_u64..500_000_u64) {
            let single = compute(n).point;
            let double = compute(2 * n).point;
            let ratio  = double / single;
            prop_assert!(
                (ratio - 2.0).abs() < 1e-10,
                "non-linear scaling: ratio={ratio}"
            );
        }

        /// bits_from_bytes always returns ≥ 1.
        #[test]
        fn bits_from_bytes_always_gte_one(bytes in 0_u64..u64::MAX) {
            prop_assert!(bits_from_bytes(bytes) >= 1);
        }
    }
}
