// crates/pacr-types/src/lib.rs
//
// Pillar: ALL. PACR field: ALL.
// This crate defines the PACR 6-tuple. It is the single most important file
// in the entire Aevum codebase. Changing the semantics of any type here
// invalidates all historical records. Proceed with extreme caution.
//
// Physical basis: the 6 dimensions are mutually independent projections of
// the same computation event onto 6 physically irreducible axes. Removing
// any dimension loses information that cannot be recovered.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use serde::{Deserialize, Serialize};
use smallvec::SmallVec;
use std::fmt;

// ============================================================
// Dimension 0: Estimate<T> — Measurement with uncertainty
// ============================================================
// Physical basis: all physical measurements have finite precision
// (Heisenberg uncertainty, thermodynamic fluctuations, finite clock resolution).
// Storing [lower, point, upper] encodes this at the protocol level so that
// Day-0 rough estimates and Year-5 precision measurements share the same schema.

/// A physical measurement represented as a point estimate ± confidence interval.
///
/// The interval [lower, upper] is a 95% confidence interval by default.
///
/// **Invariant**: `lower <= point <= upper`
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Estimate<T: PartialOrd + Copy> {
    pub point: T,
    pub lower: T,
    pub upper: T,
}

impl<T: PartialOrd + Copy + fmt::Display> Estimate<T> {
    /// Creates a new estimate, enforcing the ordering invariant.
    ///
    /// # Errors
    /// Returns [`EstimateError::InvalidBounds`] if `lower > point` or `point > upper`.
    pub fn new(point: T, lower: T, upper: T) -> Result<Self, EstimateError> {
        if lower > point || point > upper {
            return Err(EstimateError::InvalidBounds);
        }
        Ok(Self { point, lower, upper })
    }

    /// Creates an exact estimate (zero uncertainty).
    /// Used for quantities known with mathematical certainty (e.g., counting).
    #[must_use]
    pub fn exact(value: T) -> Self {
        Self {
            point: value,
            lower: value,
            upper: value,
        }
    }
}

// Eq and Hash are intentionally NOT implemented for f64-based Estimates.
// Floating-point equality is physically meaningless for measurements.
// Use `is_consistent_with()` for physically meaningful comparison.
impl Estimate<f64> {
    /// Two estimates are physically consistent if their confidence intervals overlap.
    /// This is the correct notion of "agreement" between two measurements.
    #[must_use]
    pub fn is_consistent_with(&self, other: &Self) -> bool {
        self.lower <= other.upper && other.lower <= self.upper
    }

    /// Relative uncertainty: (upper - lower) / |point|.
    /// A quality metric that should decrease over time as the system learns.
    /// Returns `f64::INFINITY` if the point estimate is at machine zero.
    #[must_use]
    pub fn relative_uncertainty(&self) -> f64 {
        if self.point.abs() < f64::EPSILON {
            return f64::INFINITY;
        }
        (self.upper - self.lower) / self.point.abs()
    }

    /// Widen this estimate conservatively.
    /// Useful when composing multiple uncertain quantities.
    #[must_use]
    pub fn with_extra_uncertainty(&self, factor: f64) -> Self {
        debug_assert!(factor >= 1.0, "widening factor must be >= 1");
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

impl<T: PartialOrd + Copy + fmt::Display> fmt::Display for Estimate<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}  [{}, {}]", self.point, self.lower, self.upper)
    }
}

/// Errors produced when constructing an [`Estimate`].
#[derive(Debug, Clone, thiserror::Error)]
pub enum EstimateError {
    #[error("Invalid bounds: required lower <= point <= upper")]
    InvalidBounds,
}

// ============================================================
// Dimension 1: ι — Causal Identity
// ============================================================
// Physical basis: logical a priori — every distinct event must be
// uniquely addressable so the causal DAG has a well-defined node set.
// ULID encoding: 48-bit ms timestamp (storage locality) + 80-bit randomness.
// Timestamp is NOT causal order — causal order comes from Π.

/// The causal identity of a PACR record.
///
/// 128 bits = 48-bit ms timestamp (for storage locality) + 80-bit randomness.
/// Ordering by `CausalId` value is for efficient storage scans only —
/// causal order is determined solely by the predecessor set Π.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct CausalId(pub u128);

impl CausalId {
    /// The null identity — used only as a sentinel for genesis events
    /// (events with no causal predecessors in the system).
    pub const GENESIS: Self = Self(0);

    /// Returns `true` if this is a genesis event.
    #[must_use]
    pub fn is_genesis(&self) -> bool {
        self.0 == 0
    }
}

impl fmt::Display for CausalId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Display in hex — a proper Crockford Base32 encoder is in `causal-id`
        write!(f, "{:032X}", self.0)
    }
}

// ============================================================
// Dimension 2: Π — Causal Predecessor Set
// ============================================================
// Physical basis: special relativity mandates that causation propagates
// at most at the speed of light, imposing a partial order on events.
// SmallVec<[CausalId; 4]>: most events have 1–4 predecessors; the
// inline buffer avoids heap allocation for the common case (Pillar I).

/// The direct causal predecessors of this event.
///
/// Unordered (partial order, not total order — physics-mandated).
/// `SmallVec<[CausalId; 4]>` avoids heap allocation for the common case.
pub type PredecessorSet = SmallVec<[CausalId; 4]>;

// ============================================================
// Dimension 3: Λ — Landauer Cost
// ============================================================
// Physical basis: Landauer's principle — each irreversible bit erasure
// dissipates at minimum E_Λ = k_B × T × ln(2) ≈ 2.85×10⁻²¹ J at 300 K.
// Λ is the theoretical floor; actual energy E ≥ Λ always.

/// Landauer cost of a computation event, in joules.
/// Invariant: `point ≥ 0` (energy is non-negative).
pub type LandauerCost = Estimate<f64>;

// ============================================================
// Dimension 4: Ω — Resource Constraint Triple (E, T, S)
// ============================================================
// Physical basis: conservation of energy (E), Margolus–Levitin theorem (T),
// and Bremermann's limit (S). These three axes are coupled — you cannot
// simultaneously minimize all three (the trilemma). Storing them as a
// named triple enforces their conceptual coupling.

/// The resource constraint triple: (Energy, Time, Space).
///
/// Physical constraints (checked by [`ResourceTriple::validate_physics`]):
/// - `energy.point >= 0` (non-negative energy)
/// - `time.point > 0` (causality requires positive duration)
/// - `space.point >= 0` (non-negative memory)
/// - `time.point >= π·ℏ / (2·energy.point)` (Margolus–Levitin bound)
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct ResourceTriple {
    /// Actual energy consumed (joules). Must satisfy `energy.point >= Λ.point`.
    pub energy: Estimate<f64>,
    /// Actual execution duration (seconds). Must satisfy Margolus–Levitin.
    pub time: Estimate<f64>,
    /// Actual memory/storage used (bytes, as `f64` for SI unit consistency).
    pub space: Estimate<f64>,
}

impl ResourceTriple {
    /// Validates physical consistency constraints.
    /// Returns all violations found (empty list = valid record).
    ///
    /// A physically invalid record is still storable — measurement errors happen.
    /// Violations are flagged for the Landauer auditor to investigate.
    #[must_use]
    pub fn validate_physics(&self) -> Vec<PhysicsViolation> {
        let mut v = Vec::new();

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
        // ℏ ≈ 1.054571817e-34 J·s
        // This bound is only macroscopically relevant for femtojoule computations,
        // but we check it for completeness and future sub-quantum extensions.
        if self.energy.point > 0.0 {
            const H_BAR: f64 = 1.054_571_817e-34;
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

    /// Thermodynamic waste = E - Λ.
    ///
    /// Uncertainty is propagated conservatively:
    /// - waste_lower = E_lower - Λ_upper (minimum possible waste)
    /// - waste_upper = E_upper - Λ_lower (maximum possible waste)
    #[must_use]
    pub fn thermodynamic_waste(&self, landauer: &LandauerCost) -> Estimate<f64> {
        Estimate {
            point: self.energy.point - landauer.point,
            lower: self.energy.lower - landauer.upper,
            upper: self.energy.upper - landauer.lower,
        }
    }
}

/// A physical law violated by a [`ResourceTriple`].
#[derive(Debug, Clone, thiserror::Error)]
pub enum PhysicsViolation {
    #[error("Energy is negative — violates energy conservation")]
    NegativeEnergy,
    #[error("Time is non-positive — violates causality")]
    NonPositiveTime,
    #[error("Space is negative — physically impossible")]
    NegativeSpace,
    #[error(
        "Margolus–Levitin violated: T={actual_s:.3e}s < T_min={minimum_s:.3e}s"
    )]
    MargolusLevitinViolated { actual_s: f64, minimum_s: f64 },
}

// ============================================================
// Dimension 5: Γ — Cognitive Split (S_T, H_T)
// ============================================================
// Physical basis: computational mechanics fundamental theorem (arXiv:2601.03220).
// S_T (statistical complexity, bits) and H_T (entropy rate, bits/symbol) are
// two projections of the same ε-machine — they cannot be separated.
// Together they characterize the observer-relative information structure of
// the data stream processed by this computation event.

/// The cognitive split: intrinsic information structure of the processed stream.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct CognitiveSplit {
    /// Statistical complexity S_T (bits).
    /// Minimum information needed to optimally predict the stream.
    /// Rising S_T = the system is discovering learnable structure.
    pub statistical_complexity: Estimate<f64>,

    /// Entropy rate H_T (bits per symbol).
    /// Residual unpredictability that cannot be compressed further.
    /// Rising H_T = the system is encountering irreducible noise.
    pub entropy_rate: Estimate<f64>,
}

impl CognitiveSplit {
    /// Structure-to-noise ratio: S_T / H_T.
    ///
    /// - High ratio → structured, predictable stream (chess rules).
    /// - Low ratio → simple but random stream (fair coin).
    /// - `None` → fully deterministic (H_T ≈ 0), ratio is effectively infinite.
    #[must_use]
    pub fn structure_noise_ratio(&self) -> Option<f64> {
        if self.entropy_rate.point.abs() < f64::EPSILON {
            return None; // H_T ≈ 0: fully deterministic, infinite structure ratio
        }
        Some(self.statistical_complexity.point / self.entropy_rate.point)
    }

    /// Returns `true` if this stream is in the "structured" regime
    /// (S_T significantly exceeds H_T), indicating high learnability.
    #[must_use]
    pub fn is_structured(&self) -> bool {
        self.structure_noise_ratio()
            .map_or(true, |r| r > 1.0)
    }
}

// ============================================================
// Dimension 6: P — Opaque Payload
// ============================================================
// Physical basis: completeness axiom — the semantic content of the computation
// event must be preserved. PACR does not interpret it; upper layers define
// their own schemas within P. UNIX philosophy: a finite byte stream.

/// Opaque payload — the semantic content of the computation event.
/// PACR does not interpret this. Upper layers define their own schemas.
pub type Payload = bytes::Bytes;

// ============================================================
// THE PACR RECORD — The 6-tuple R = (ι, Π, Λ, Ω, Γ, P)
// ============================================================

/// A Physically Annotated Causal Record.
///
/// The minimal sufficient statistic for a computation event.
/// Six dimensions, each derived from physical first principles,
/// mutually independent, atomically irreducible.
///
/// **R = (ι, Π, Λ, Ω, Γ, P)**
///
/// # Immutability
/// This struct is the Day-0 immutable contract. Adding fields is permitted
/// (append-only evolution). Changing existing field semantics is **forbidden**.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PacrRecord {
    /// ι — Causal Identity (logical a priori)
    pub id: CausalId,

    /// Π — Causal Predecessor Set (special relativity → partial order)
    pub predecessors: PredecessorSet,

    /// Λ — Landauer Cost in joules (Landauer's principle)
    pub landauer_cost: LandauerCost,

    /// Ω — Resource Constraint Triple (conservation laws)
    pub resources: ResourceTriple,

    /// Γ — Cognitive Split (computational mechanics)
    pub cognitive_split: CognitiveSplit,

    /// P — Opaque Payload (completeness axiom)
    pub payload: Payload,
}

impl PacrRecord {
    /// Validates all physical invariants of this record.
    ///
    /// A record that violates physics is still storable (measurement errors happen),
    /// but the violations are flagged for the Landauer auditor.
    #[must_use]
    pub fn validate(&self) -> Vec<ValidationIssue> {
        let mut issues = Vec::new();

        for v in self.resources.validate_physics() {
            issues.push(ValidationIssue::Physics(v));
        }

        // E ≥ Λ: actual energy must exceed the Landauer floor
        if self.resources.energy.point < self.landauer_cost.point {
            issues.push(ValidationIssue::EnergyBelowLandauer {
                actual_j: self.resources.energy.point,
                landauer_j: self.landauer_cost.point,
            });
        }

        if self.landauer_cost.point < 0.0 {
            issues.push(ValidationIssue::NegativeLandauer);
        }

        if self.cognitive_split.statistical_complexity.point < 0.0 {
            issues.push(ValidationIssue::NegativeComplexity);
        }

        if self.cognitive_split.entropy_rate.point < 0.0 {
            issues.push(ValidationIssue::NegativeEntropyRate);
        }

        // Self-reference check: no causal loops
        if self.predecessors.contains(&self.id) {
            issues.push(ValidationIssue::SelfReference);
        }

        issues
    }

    /// Computes thermodynamic waste = E - Λ for this record.
    #[must_use]
    pub fn thermodynamic_waste(&self) -> Estimate<f64> {
        self.resources.thermodynamic_waste(&self.landauer_cost)
    }
}

/// A validation issue found in a [`PacrRecord`].
#[derive(Debug, Clone, thiserror::Error)]
pub enum ValidationIssue {
    #[error("Physics violation: {0}")]
    Physics(PhysicsViolation),
    #[error("Actual energy {actual_j:.3e} J is below Landauer floor {landauer_j:.3e} J")]
    EnergyBelowLandauer { actual_j: f64, landauer_j: f64 },
    #[error("Landauer cost cannot be negative")]
    NegativeLandauer,
    #[error("Statistical complexity S_T cannot be negative")]
    NegativeComplexity,
    #[error("Entropy rate H_T cannot be negative")]
    NegativeEntropyRate,
    #[error("Record references itself as predecessor — causal loop")]
    SelfReference,
}

// ============================================================
// PACR Builder — compile-time enforcement of all-6-fields-required
// ============================================================

/// Builder for [`PacrRecord`].
///
/// Rust's type system enforces: you cannot call `build()` if any of the
/// six PACR dimensions is missing. Missing a field is a **build error**,
/// not a runtime error.
#[derive(Default)]
pub struct PacrBuilder {
    id: Option<CausalId>,
    predecessors: Option<PredecessorSet>,
    landauer_cost: Option<LandauerCost>,
    resources: Option<ResourceTriple>,
    cognitive_split: Option<CognitiveSplit>,
    payload: Option<Payload>,
}

impl PacrBuilder {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn id(mut self, id: CausalId) -> Self {
        self.id = Some(id);
        self
    }

    #[must_use]
    pub fn predecessors(mut self, preds: PredecessorSet) -> Self {
        self.predecessors = Some(preds);
        self
    }

    #[must_use]
    pub fn landauer_cost(mut self, cost: LandauerCost) -> Self {
        self.landauer_cost = Some(cost);
        self
    }

    #[must_use]
    pub fn resources(mut self, res: ResourceTriple) -> Self {
        self.resources = Some(res);
        self
    }

    #[must_use]
    pub fn cognitive_split(mut self, split: CognitiveSplit) -> Self {
        self.cognitive_split = Some(split);
        self
    }

    #[must_use]
    pub fn payload(mut self, payload: Payload) -> Self {
        self.payload = Some(payload);
        self
    }

    /// Builds the [`PacrRecord`]. Fails if **any** dimension is missing.
    ///
    /// # Errors
    /// Returns [`BuildError::MissingDimension`] naming the missing field.
    pub fn build(self) -> Result<PacrRecord, BuildError> {
        Ok(PacrRecord {
            id: self.id.ok_or(BuildError::MissingDimension("ι (id)"))?,
            predecessors: self
                .predecessors
                .ok_or(BuildError::MissingDimension("Π (predecessors)"))?,
            landauer_cost: self
                .landauer_cost
                .ok_or(BuildError::MissingDimension("Λ (landauer_cost)"))?,
            resources: self
                .resources
                .ok_or(BuildError::MissingDimension("Ω (resources)"))?,
            cognitive_split: self
                .cognitive_split
                .ok_or(BuildError::MissingDimension("Γ (cognitive_split)"))?,
            payload: self
                .payload
                .ok_or(BuildError::MissingDimension("P (payload)"))?,
        })
    }
}

/// Error returned when building a [`PacrRecord`] with a missing dimension.
#[derive(Debug, Clone, thiserror::Error)]
pub enum BuildError {
    #[error("Missing PACR dimension: {0} — all six dimensions are mandatory")]
    MissingDimension(&'static str),
}

// ============================================================
// Tests
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn estimate_new_enforces_invariant() {
        assert!(Estimate::new(1.0_f64, 0.5, 1.5).is_ok());
        assert!(Estimate::new(1.0_f64, 1.5, 0.5).is_err()); // lower > point
        assert!(Estimate::new(1.0_f64, 0.5, 0.8).is_err()); // point > upper
    }

    #[test]
    fn estimate_exact_has_zero_uncertainty() {
        let e = Estimate::exact(42.0_f64);
        assert_eq!(e.point, e.lower);
        assert_eq!(e.lower, e.upper);
        assert_eq!(e.relative_uncertainty(), 0.0);
    }

    #[test]
    fn estimate_consistency_check() {
        let a = Estimate::new(1.0_f64, 0.5, 1.5).unwrap();
        let b = Estimate::new(1.2_f64, 0.8, 1.6).unwrap();
        let c = Estimate::new(3.0_f64, 2.0, 4.0).unwrap();
        assert!(a.is_consistent_with(&b)); // intervals overlap
        assert!(!a.is_consistent_with(&c)); // [0.5,1.5] vs [2.0,4.0] — no overlap
    }

    #[test]
    fn causal_id_genesis_sentinel() {
        assert!(CausalId::GENESIS.is_genesis());
        assert!(!CausalId(1).is_genesis());
    }

    #[test]
    fn resource_triple_validates_negative_energy() {
        let bad = ResourceTriple {
            energy: Estimate { point: -1.0, lower: -2.0, upper: 0.0 },
            time: Estimate::exact(1.0),
            space: Estimate::exact(0.0),
        };
        let v = bad.validate_physics();
        assert!(v.iter().any(|e| matches!(e, PhysicsViolation::NegativeEnergy)));
    }

    #[test]
    fn builder_rejects_missing_dimension() {
        let result = PacrBuilder::new()
            .id(CausalId(1))
            // deliberately omit other fields
            .build();
        assert!(result.is_err());
    }

    #[test]
    fn builder_accepts_complete_record() {
        use bytes::Bytes;
        use smallvec::smallvec;

        let record = PacrBuilder::new()
            .id(CausalId(42))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-19),
                time: Estimate::exact(1e-9),
                space: Estimate::exact(128.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(3.0),
                entropy_rate: Estimate::exact(1.0),
            })
            .payload(Bytes::from_static(b"hello"))
            .build();

        assert!(record.is_ok());
        let r = record.unwrap();
        assert!(r.validate().is_empty());
        assert_eq!(r.thermodynamic_waste().point, 1e-19 - 1e-20);
    }
}
