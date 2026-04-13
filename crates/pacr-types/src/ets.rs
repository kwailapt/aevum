//! Pillar: II. PACR field: Ω (Resource Triple).
//!
//! Three physically coupled resource axes that cannot be simultaneously
//! minimised — the Energy-Time-Space trilemma:
//!
//!   E — energy consumed (joules)          conservation of energy
//!   T — execution time (seconds)          Margolus–Levitin: T ≥ πℏ/2E
//!   S — memory/storage used (bytes)       Bremermann / Holevo–von Neumann
//!
//! These three axes lie on a 2-D constraint surface, not three independent axes.
//! Storing them together as `ResourceTriple` makes their coupling explicit and
//! enables the Margolus–Levitin consistency check at every append.

use crate::estimate::Estimate;
use crate::landauer::LandauerCost;
use crate::landauer::H_BAR;

// ── Core type ─────────────────────────────────────────────────────────────────

/// The resource constraint triple (E, T, S) for a computation event.
///
/// All three values use `Estimate<f64>` to carry measurement uncertainty.
/// See [`ResourceTriple::validate_physics`] for the physical consistency checks.
///
/// PACR field Ω. Derived from Pillar II (conservation laws + Margolus–Levitin).
#[derive(Debug, Clone, Copy, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct ResourceTriple {
    /// Actual energy consumed (joules). Must satisfy `energy.point ≥ Λ.point`.
    pub energy: Estimate<f64>,
    /// Actual execution duration (seconds). Must satisfy Margolus–Levitin bound.
    pub time: Estimate<f64>,
    /// Actual memory/storage used (bytes, as f64 for SI-unit consistency).
    pub space: Estimate<f64>,
}

impl ResourceTriple {
    /// Validates physical consistency of this triple.
    ///
    /// Returns every violation found; an empty `Vec` means the record is clean.
    /// A physically invalid record is still storable (measurement errors happen),
    /// but violations must be flagged for the Landauer auditor to investigate.
    #[must_use]
    pub fn validate_physics(&self) -> Vec<PhysicsViolation> {
        let mut v: Vec<PhysicsViolation> = Vec::new();

        if self.energy.point < 0.0 {
            v.push(PhysicsViolation::NegativeEnergy);
        }
        if self.time.point <= 0.0 {
            v.push(PhysicsViolation::NonPositiveTime);
        }
        if self.space.point < 0.0 {
            v.push(PhysicsViolation::NegativeSpace);
        }

        // Margolus–Levitin: T ≥ π·ℏ / (2·E)
        // Checked for completeness; macroscopically relevant at femtojoule scale
        // and for future sub-quantum extensions.
        if self.energy.point > 0.0 {
            let t_min = std::f64::consts::PI * H_BAR / (2.0 * self.energy.point);
            if self.time.point < t_min {
                v.push(PhysicsViolation::MargolusLevitinViolated {
                    actual_s: self.time.point,
                    minimum_s: t_min,
                });
            }
        }

        v
    }

    /// Thermodynamic waste = E − Λ with conservative uncertainty propagation.
    ///
    /// Uncertainty is propagated as:
    ///   `waste.lower = energy.lower − λ.upper`  (minimum possible waste)
    ///   `waste.upper = energy.upper − λ.lower`  (maximum possible waste)
    #[must_use]
    pub fn thermodynamic_waste(&self, landauer: &LandauerCost) -> Estimate<f64> {
        Estimate {
            point: self.energy.point - landauer.point,
            lower: self.energy.lower - landauer.upper,
            upper: self.energy.upper - landauer.lower,
        }
    }
}

// ── Violation enum ────────────────────────────────────────────────────────────

/// A physical-law violation detected in a [`ResourceTriple`].
#[derive(Debug, Clone, thiserror::Error)]
#[non_exhaustive]
pub enum PhysicsViolation {
    /// Energy is negative — violates conservation of energy.
    #[error("energy is negative — violates conservation of energy")]
    NegativeEnergy,

    /// Time is non-positive — violates causality.
    #[error("time is non-positive — violates causality")]
    NonPositiveTime,

    /// Space is negative — physically impossible.
    #[error("space is negative — physically impossible")]
    NegativeSpace,

    /// Margolus–Levitin theorem violated: T < π·ℏ / (2·E).
    #[error(
        "Margolus–Levitin violated: T={actual_s:.3e} s < T_min={minimum_s:.3e} s"
    )]
    MargolusLevitinViolated {
        /// Measured execution time (seconds).
        actual_s: f64,
        /// Minimum allowed time (seconds) at this energy.
        minimum_s: f64,
    },
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::estimate::Estimate;

    fn valid_triple() -> ResourceTriple {
        ResourceTriple {
            energy: Estimate::exact(1e-19),
            time:   Estimate::exact(1e-9),
            space:  Estimate::exact(128.0),
        }
    }

    #[test]
    fn valid_triple_has_no_violations() {
        assert!(valid_triple().validate_physics().is_empty());
    }

    #[test]
    fn negative_energy_is_flagged() {
        let mut t = valid_triple();
        t.energy = Estimate { point: -1.0, lower: -2.0, upper: 0.0 };
        let v = t.validate_physics();
        assert!(v.iter().any(|e| matches!(e, PhysicsViolation::NegativeEnergy)));
    }

    #[test]
    fn zero_time_is_flagged() {
        let mut t = valid_triple();
        t.time = Estimate::exact(0.0);
        let v = t.validate_physics();
        assert!(v.iter().any(|e| matches!(e, PhysicsViolation::NonPositiveTime)));
    }

    #[test]
    fn negative_space_is_flagged() {
        let mut t = valid_triple();
        t.space = Estimate { point: -1.0, lower: -2.0, upper: 0.0 };
        let v = t.validate_physics();
        assert!(v.iter().any(|e| matches!(e, PhysicsViolation::NegativeSpace)));
    }

    #[test]
    fn thermodynamic_waste_propagates_uncertainty() {
        let triple = ResourceTriple {
            energy: Estimate::new(1e-19, 0.8e-19, 1.2e-19).unwrap(),
            time:   Estimate::exact(1e-9),
            space:  Estimate::exact(0.0),
        };
        let lambda = Estimate::new(1e-20, 0.5e-20, 2.0e-20).unwrap();
        let waste = triple.thermodynamic_waste(&lambda);

        assert!((waste.point - (1e-19 - 1e-20)).abs() < 1e-30);
        // lower = energy.lower - lambda.upper = 0.8e-19 - 2.0e-20
        assert!((waste.lower - (0.8e-19 - 2.0e-20)).abs() < 1e-30);
        // upper = energy.upper - lambda.lower = 1.2e-19 - 0.5e-20
        assert!((waste.upper - (1.2e-19 - 0.5e-20)).abs() < 1e-30);
    }
}
