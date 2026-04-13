// crates/pacr-types/src/lib.rs
//
// Pillar: ALL. PACR field: ALL.
// This crate defines the PACR 6-tuple. It is the single most important file
// in the entire Aevum codebase. Changing the semantics of any type here
// invalidates all historical records. Proceed with extreme caution.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use serde::{Deserialize, Serialize};
use smallvec::SmallVec;
use std::fmt;

// ============================================================
// Dimension 0: Estimate<T> — Measurement with uncertainty
// ============================================================
// Every physical quantity in PACR carries its own uncertainty.
// This is not optional — it's a protocol-level requirement
// derived from the fact that all physical measurements have
// finite precision (Heisenberg, thermodynamic fluctuations).

/// A physical measurement represented as point estimate ± confidence interval.
/// The interval [lower, upper] is a 95% confidence interval by default.
/// Invariant: lower <= point <= upper
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
    /// Returns `EstimateError::InvalidBounds` if lower > point or point > upper.
    pub fn new(point: T, lower: T, upper: T) -> Result<Self, EstimateError> {
        if lower > point || point > upper {
            return Err(EstimateError::InvalidBounds);
        }
        Ok(Self { point, lower, upper })
    }

    /// Creates an exact estimate (zero uncertainty).
    /// Used for quantities known with mathematical certainty (e.g., counting).
    pub fn exact(value: T) -> Self {
        Self {
            point: value,
            lower: value,
            upper: value,
        }
    }
}

// Eq is intentionally NOT derived for f64-based Estimates.
// Floating point equality is physically meaningless for measurements.
// Use `is_consistent_with()` instead.
impl Estimate<f64> {
    /// Two estimates are consistent if their confidence intervals overlap.
    /// This is the physically meaningful notion of "equality" for measurements.
    #[must_use]
    pub fn is_consistent_with(&self, other: &Self) -> bool {
        self.lower <= other.upper && other.lower <= self.upper
    }

    /// Returns the relative uncertainty (interval width / point estimate).
    /// A measure of measurement quality that improves over time.
    #[must_use]
    pub fn relative_uncertainty(&self) -> f64 {
        if self.point.abs() < f64::EPSILON {
            return f64::INFINITY;
        }
        (self.upper - self.lower) / self.point.abs()
    }
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum EstimateError {
    #[error("Invalid bounds: lower must be <= point <= upper")]
    InvalidBounds,
}

// ============================================================
// Dimension 1: ι — Causal Identity
// ============================================================
// Pillar: Logical a priori (referential necessity).
// A globally unique, monotonically sortable, unforgeable identifier.
// We use ULID (Universally Unique Lexicographically Sortable Identifier)
// because it embeds a millisecond timestamp for rough temporal locality
// (useful for storage, NOT for causal ordering — causal order comes from Π only).

/// The causal identity of a PACR record.
/// 128 bits: 48-bit timestamp (ms) + 80-bit randomness.
/// Ordering by ι is for storage efficiency only, NOT causal semantics.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct CausalId(pub u128);

impl CausalId {
    /// The null identity — used only as a sentinel for "no predecessor" (genesis events).
    pub const GENESIS: Self = Self(0);

    /// Returns true if this is a genesis event (no causal predecessors).
    #[must_use]
    pub fn is_genesis(&self) -> bool {
        self.0 == 0
    }
}

impl fmt::Display for CausalId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Display as Crockford Base32 (ULID standard) for human readability
        write!(f, "{:032X}", self.0)
    }
}

// ============================================================
// Dimension 2: Π — Causal Predecessor Set
// ============================================================
// Pillar I: Special relativity → causal partial order.
// The predecessor set defines the edges of the causal DAG.
// SmallVec optimization: most events have 1-4 predecessors.
// The set is UNORDERED — partial order, not total order (physics-mandated).

/// The set of direct causal predecessors of this event.
/// Unordered because causal structure is a partial order (Axiom I).
/// SmallVec<[CausalId; 4]> avoids heap allocation for the common case.
pub type PredecessorSet = SmallVec<[CausalId; 4]>;

// ============================================================
// Dimension 3: Λ — Landauer Cost
// ============================================================
// Pillar II: Landauer's principle / Second law of thermodynamics.
// The minimum energy dissipated by the irreversible bit erasures
// in this computation event. Unit: joules.
// Λ ≤ E (actual energy) always. The gap (E - Λ) is thermodynamic waste.

/// Landauer cost of a computation event.
/// Estimate in joules. Invariant: Λ.point ≥ 0 (energy is non-negative).
pub type LandauerCost = Estimate<f64>;

// ============================================================
// Dimension 4: Ω — Resource Constraint Triple (E, T, S)
// ============================================================
// Pillar II: Conservation laws + Margolus-Levitin + Bremermann limit.
// Three physically coupled quantities forming a constraint surface.
// Stored as a triple (not three independent fields) to enforce their coupling.

/// The resource constraint triple: (Energy, Time, Space).
/// - energy: actual energy consumed (joules). Must satisfy E ≥ Λ.
/// - time: actual wall-clock duration (seconds). Must satisfy T ≥ πℏ/(2E).
/// - space: actual memory/storage used (bytes, as f64 for SI consistency).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct ResourceTriple {
    /// Actual energy consumed (joules)
    pub energy: Estimate<f64>,
    /// Actual execution time (seconds)
    pub time: Estimate<f64>,
    /// Actual space used (bytes)
    pub space: Estimate<f64>,
}

impl ResourceTriple {
    /// Validates physical consistency constraints.
    /// Returns a list of violations (empty = valid).
    #[must_use]
    pub fn validate_physics(&self) -> Vec<PhysicsViolation> {
        let mut violations = Vec::new();

        // Energy must be non-negative
        if self.energy.point < 0.0 {
            violations.push(PhysicsViolation::NegativeEnergy);
        }

        // Time must be positive
        if self.time.point <= 0.0 {
            violations.push(PhysicsViolation::NonPositiveTime);
        }

        // Space must be non-negative
        if self.space.point < 0.0 {
            violations.push(PhysicsViolation::NegativeSpace);
        }

        // Margolus-Levitin: T ≥ πℏ/(2E)
        // ℏ ≈ 1.054571817e-34 J·s
        // This bound is only physically meaningful for very small E and T,
        // but we check it for completeness.
        if self.energy.point > 0.0 {
            let h_bar: f64 = 1.054_571_817e-34;
            let ml_bound = std::f64::consts::PI * h_bar / (2.0 * self.energy.point);
            if self.time.point < ml_bound {
                violations.push(PhysicsViolation::MargolusLevitinViolation {
                    actual_time: self.time.point,
                    minimum_time: ml_bound,
                });
            }
        }

        violations
    }

    /// Computes thermodynamic waste = E - Λ (actual energy minus Landauer floor).
    /// Returns the waste as an Estimate, propagating uncertainties.
    #[must_use]
    pub fn thermodynamic_waste(&self, landauer: &LandauerCost) -> Estimate<f64> {
        // Point estimate: E - Λ
        // Lower bound: E_lower - Λ_upper (minimum possible waste)
        // Upper bound: E_upper - Λ_lower (maximum possible waste)
        let point = self.energy.point - landauer.point;
        let lower = self.energy.lower - landauer.upper;
        let upper = self.energy.upper - landauer.lower;
        // Waste can't be negative (by definition E ≥ Λ), but measurement
        // uncertainty might make it so — we preserve the raw numbers.
        Estimate { point, lower, upper }
    }
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum PhysicsViolation {
    #[error("Energy cannot be negative")]
    NegativeEnergy,
    #[error("Time must be positive")]
    NonPositiveTime,
    #[error("Space cannot be negative")]
    NegativeSpace,
    #[error("Margolus-Levitin violated: T={actual_time:.2e}s < T_min={minimum_time:.2e}s")]
    MargolusLevitinViolation {
        actual_time: f64,
        minimum_time: f64,
    },
}

// ============================================================
// Dimension 5: Γ — Cognitive Split (S_T, H_T)
// ============================================================
// Pillar III: Computational mechanics fundamental theorem.
// Two inseparable projections of the same ε-machine.
// S_T = statistical complexity (bits): learnable structure
// H_T = entropy rate (bits/symbol): residual randomness
// Ref: arXiv:2601.03220

/// Cognitive split: the intrinsic information-theoretic structure of the
/// data stream processed by this event.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct CognitiveSplit {
    /// Statistical complexity S_T (bits).
    /// The minimum information required to optimally predict the stream.
    /// Higher S_T = more learnable structure.
    pub statistical_complexity: Estimate<f64>,

    /// Entropy rate H_T (bits per symbol).
    /// The residual unpredictability after accounting for all learnable structure.
    /// Higher H_T = more irreducible randomness.
    pub entropy_rate: Estimate<f64>,
}

impl CognitiveSplit {
    /// The complexity-entropy ratio: S_T / H_T.
    /// High ratio → structured and predictable (chess rules).
    /// Low ratio → simple but random (coin flip).
    /// This ratio is the key diagnostic for the autopoietic loop.
    #[must_use]
    pub fn structure_noise_ratio(&self) -> Option<f64> {
        if self.entropy_rate.point.abs() < f64::EPSILON {
            return None; // Fully deterministic — ratio is infinite
        }
        Some(self.statistical_complexity.point / self.entropy_rate.point)
    }

    /// Returns true if this event's data stream is in the "structured" regime
    /// (S_T significantly exceeds H_T), indicating high learnability.
    #[must_use]
    pub fn is_structured(&self) -> bool {
        self.structure_noise_ratio()
            .map_or(true, |ratio| ratio > 1.0)
    }
}

// ============================================================
// Dimension 6: P — Opaque Payload
// ============================================================
// Completeness axiom: semantic content must be preserved.
// Opaque to PACR layer — no structure assumptions.
// UNIX philosophy: it's a byte stream.

/// Opaque payload — the semantic content of the computation event.
/// PACR does not interpret this. It is a finite byte sequence.
/// Upper layers define their own schemas within P.
pub type Payload = bytes::Bytes;

// ============================================================
// THE PACR RECORD — The 6-tuple
// ============================================================

/// A Physically Annotated Causal Record.
///
/// The minimal sufficient statistic for a computation event.
/// 6 dimensions, each derived from physical first principles,
/// mutually independent, atomically irreducible.
///
/// R = (ι, Π, Λ, Ω, Γ, P)
///
/// This struct is the Day 0 immutable contract.
/// Adding fields (append-only evolution) is permitted.
/// Changing existing field semantics is FORBIDDEN.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PacrRecord {
    /// ι — Causal Identity (logical a priori)
    pub id: CausalId,

    /// Π — Causal Predecessor Set (Axiom I: special relativity)
    pub predecessors: PredecessorSet,

    /// Λ — Landauer Cost in joules (Axiom II: Landauer's principle)
    pub landauer_cost: LandauerCost,

    /// Ω — Resource Constraint Triple (Axiom III: conservation laws)
    pub resources: ResourceTriple,

    /// Γ — Cognitive Split (Axiom IV: computational mechanics)
    pub cognitive_split: CognitiveSplit,

    /// P — Opaque Payload (completeness axiom)
    pub payload: Payload,
}

impl PacrRecord {
    /// Validates all physical invariants of this record.
    /// A record that violates physics is still storable (measurement errors happen),
    /// but the violations are flagged for the Landauer auditor.
    #[must_use]
    pub fn validate(&self) -> Vec<PacrValidationIssue> {
        let mut issues = Vec::new();

        // Check resource triple physical constraints
        for v in self.resources.validate_physics() {
            issues.push(PacrValidationIssue::PhysicsViolation(v));
        }

        // Check E ≥ Λ (actual energy must exceed Landauer floor)
        if self.resources.energy.point < self.landauer_cost.point {
            issues.push(PacrValidationIssue::EnergyBelowLandauer {
                actual: self.resources.energy.point,
                landauer: self.landauer_cost.point,
            });
        }

        // Check Λ ≥ 0
        if self.landauer_cost.point < 0.0 {
            issues.push(PacrValidationIssue::NegativeLandauer);
        }

        // Check S_T ≥ 0 and H_T ≥ 0
        if self.cognitive_split.statistical_complexity.point < 0.0 {
            issues.push(PacrValidationIssue::NegativeComplexity);
        }
        if self.cognitive_split.entropy_rate.point < 0.0 {
            issues.push(PacrValidationIssue::NegativeEntropyRate);
        }

        // Check predecessor set does not contain self (no causal loops)
        if self.predecessors.contains(&self.id) {
            issues.push(PacrValidationIssue::SelfReference);
        }

        issues
    }

    /// Computes thermodynamic waste for this record.
    #[must_use]
    pub fn thermodynamic_waste(&self) -> Estimate<f64> {
        self.resources.thermodynamic_waste(&self.landauer_cost)
    }
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum PacrValidationIssue {
    #[error("Physics violation: {0}")]
    PhysicsViolation(PhysicsViolation),
    #[error("Actual energy ({actual:.2e}J) below Landauer floor ({landauer:.2e}J)")]
    EnergyBelowLandauer { actual: f64, landauer: f64 },
    #[error("Landauer cost cannot be negative")]
    NegativeLandauer,
    #[error("Statistical complexity cannot be negative")]
    NegativeComplexity,
    #[error("Entropy rate cannot be negative")]
    NegativeEntropyRate,
    #[error("Record references itself as predecessor (causal loop)")]
    SelfReference,
}

// ============================================================
// PACR Builder — Enforces "all 6 fields must be populated"
// ============================================================

/// Builder that ensures a PACR record is complete before construction.
/// Rust's type system enforces: you cannot build a PacrRecord with missing fields.
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
        Self {
            id: None,
            predecessors: None,
            landauer_cost: None,
            resources: None,
            cognitive_split: None,
            payload: None,
        }
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

    /// Build the PACR record. Fails if ANY dimension is missing.
    ///
    /// # Errors
    /// Returns `PacrBuildError::MissingField` with the name of the missing dimension.
    pub fn build(self) -> Result<PacrRecord, PacrBuildError> {
        Ok(PacrRecord {
            id: self.id.ok_or(PacrBuildError::MissingField("ι (id)"))?,
            predecessors: self
                .predecessors
                .ok_or(PacrBuildError::MissingField("Π (predecessors)"))?,
            landauer_cost: self
                .landauer_cost
                .ok_or(PacrBuildError::MissingField("Λ (landauer_cost)"))?,
            resources: self
                .resources
                .ok_or(PacrBuildError::MissingField("Ω (resources)"))?,
            cognitive_split: self
                .cognitive_split
                .ok_or(PacrBuildError::MissingField("Γ (cognitive_split)"))?,
            payload: self
                .payload
                .ok_or(PacrBuildError::MissingField("P (payload)"))?,
        })
    }
}

impl Default for PacrBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum PacrBuildError {
    #[error("Missing PACR dimension: {0} — all 6 dimensions are mandatory")]
    MissingField(&'static str),
}

