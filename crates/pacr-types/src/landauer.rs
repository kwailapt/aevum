//! Pillar: II. PACR field: Λ (Landauer Cost).
//!
//! Landauer's principle (1961): any logically irreversible computation — i.e.
//! any operation that erases information — must dissipate at least
//!
//!   E_min = k_B × T × ln(2)   [joules per erased bit]
//!
//! into the environment as heat.  This is a corollary of the Second Law of
//! Thermodynamics, not an engineering limitation.
//!
//! `LandauerCost` is a type alias for `Estimate<f64>` measured in **joules**.
//! It represents the theoretical lower bound on energy dissipation for a
//! given computation event.  Actual energy `Ω.energy ≥ Λ` always.
//! The gap `E − Λ` is thermodynamic waste and drives all optimisation.

use crate::estimate::Estimate;

// ── Physical constants ────────────────────────────────────────────────────────

/// Boltzmann constant (J K⁻¹), 2019 SI exact redefinition.
pub const K_B: f64 = 1.380_649e-23;

/// Reduced Planck constant (J s), 2019 SI exact redefinition.
pub const H_BAR: f64 = 1.054_571_817e-34;

/// Landauer floor at 300 K room temperature (J per erased bit).
/// E_min = k_B × 300 K × ln(2) = 1.380_649e-23 × 300 × ln(2) ≈ 2.870_979 × 10⁻²¹ J
///
/// Derived from the 2019 SI exact value of k_B.
/// The previously cited value of 2.854e-21 was a rough approximation.
pub const LANDAUER_JOULES_300K: f64 = 2.870_979e-21;

// ── Type alias ────────────────────────────────────────────────────────────────

/// Landauer cost of a computation event, in joules.
///
/// This is the **theoretical lower bound** on energy dissipation.
/// Invariant: `point ≥ 0` (energy is non-negative).
///
/// PACR field Λ.  Derived from Pillar II (Landauer's principle).
pub type LandauerCost = Estimate<f64>;

// ── Helper ────────────────────────────────────────────────────────────────────

/// Computes the Landauer floor for `bits_erased` at a given temperature.
///
/// Returns `Λ = bits_erased × k_B × T × ln(2)` as an exact estimate
/// (zero uncertainty, since the formula is derived from exact physical constants
/// and the bit count is known precisely).
///
/// # Arguments
/// * `bits_erased` — number of bits irreversibly erased
/// * `temperature_k` — environment temperature in Kelvin
#[must_use]
#[allow(clippy::cast_precision_loss)] // bits_erased: realistic counts fit f64 mantissa
pub fn landauer_floor_joules(bits_erased: u64, temperature_k: f64) -> LandauerCost {
    let joules = bits_erased as f64 * K_B * temperature_k * std::f64::consts::LN_2;
    Estimate::exact(joules)
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn landauer_floor_at_300k_one_bit() {
        let cost = landauer_floor_joules(1, 300.0);
        // Should be ≈ 2.854e-21 J (within 0.1 %)
        let expected = LANDAUER_JOULES_300K;
        let ratio = cost.point / expected;
        assert!((ratio - 1.0).abs() < 1e-3, "ratio={ratio}");
    }

    #[test]
    fn landauer_floor_scales_linearly_with_bits() {
        let one  = landauer_floor_joules(1,    300.0).point;
        let mega = landauer_floor_joules(1_000_000, 300.0).point;
        let ratio = mega / one;
        assert!((ratio - 1_000_000.0).abs() < 1.0, "ratio={ratio}");
    }

    #[test]
    fn landauer_floor_scales_linearly_with_temperature() {
        let at_300 = landauer_floor_joules(1, 300.0).point;
        let at_600 = landauer_floor_joules(1, 600.0).point;
        let ratio  = at_600 / at_300;
        assert!((ratio - 2.0).abs() < 1e-10, "ratio={ratio}");
    }

    #[test]
    fn landauer_floor_zero_bits_is_zero() {
        let cost = landauer_floor_joules(0, 300.0);
        assert_eq!(cost.point, 0.0);
    }
}
