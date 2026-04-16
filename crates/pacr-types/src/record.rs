//! Pillar: ALL. PACR field: ALL (integrates ι, Π, Λ, Ω, Γ, P into one record).
//!
//! This module defines the **PACR 6-tuple** — the immutable Day-0 contract.
//!
//! **R = (ι, Π, Λ, Ω, Γ, P)**
//!
//! Physical axiom for each dimension:
//!   ι — logical a priori (every distinct event needs a unique address)
//!   Π — special relativity (causal partial order, never total order)
//!   Λ — Landauer's principle (see landauer.rs)
//!   Ω — conservation + Margolus–Levitin (see ets.rs)
//!   Γ — computational mechanics (see complexity.rs)
//!   P — completeness axiom (semantic content must be preserved)
//!
//! SCHEMA IS APPEND-ONLY.  New optional fields may be added.
//! Existing field semantics MUST NEVER change.

use crate::complexity::CognitiveSplit;
use crate::estimate::Estimate;
use crate::ets::{PhysicsViolation, ResourceTriple};
use crate::landauer::LandauerCost;

use serde::{Deserialize, Serialize};
use smallvec::SmallVec;
use std::fmt;

// ── Dimension ι: Causal Identity ──────────────────────────────────────────────

/// The causal identity of a PACR record.
///
/// 128 bits = 48-bit millisecond timestamp (storage locality) + 80-bit randomness.
///
/// **Important**: ordering by `CausalId` value is for efficient storage scans
/// only.  Causal order is determined solely by the predecessor set Π.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct CausalId(pub u128);

impl CausalId {
    /// Sentinel for genesis events — events with no causal predecessors.
    pub const GENESIS: Self = Self(0);

    /// Returns `true` if this is a genesis event (no causal predecessors).
    #[must_use]
    pub fn is_genesis(&self) -> bool {
        self.0 == 0
    }
}

impl fmt::Display for CausalId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Hex display; Crockford Base32 encoder lives in the `causal-id` crate.
        write!(f, "{:032X}", self.0)
    }
}

// ── Dimension Π: Causal Predecessor Set ──────────────────────────────────────

/// Direct causal predecessors of this event.
///
/// Unordered set (partial order, not total order — physics-mandated).
/// `SmallVec<[CausalId; 4]>` avoids heap allocation for the common case of
/// 1–4 predecessors (Pillar I: zero-copy on the hot path).
pub type PredecessorSet = SmallVec<[CausalId; 4]>;

// ── Dimension P: Opaque Payload ───────────────────────────────────────────────

/// Opaque payload — the semantic content of the computation event.
///
/// PACR does not interpret this field.  Upper layers (`AgentCard`, etc.) define
/// their own schemas within P.  Zero-copy via `bytes::Bytes`.
pub type Payload = bytes::Bytes;

// ── THE PACR RECORD ───────────────────────────────────────────────────────────

/// A Physically Annotated Causal Record — the minimal sufficient statistic
/// for a computation event.
///
/// ```text
/// R = (ι,  Π,  Λ,   Ω,          Γ,              P)
///      id  preds  cost  resources  cognitive_split  payload
/// ```
///
/// Six dimensions, each derived from physical first principles,
/// mutually independent and atomically irreducible.
///
/// # Immutability
/// This is the Day-0 contract.  Adding fields is permitted (append-only
/// schema evolution).  Changing existing field semantics is **forbidden**.
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
    /// Returns every issue found; an empty `Vec` means the record is clean.
    /// A physically invalid record is still storable (measurement errors happen),
    /// but violations must be flagged for the Landauer auditor to investigate.
    #[must_use]
    pub fn validate(&self) -> Vec<ValidationIssue> {
        let mut issues: Vec<ValidationIssue> = Vec::new();

        // Ω: physics constraints on the resource triple
        for v in self.resources.validate_physics() {
            issues.push(ValidationIssue::Physics(v));
        }

        // E ≥ Λ: actual energy must exceed the Landauer theoretical floor
        if self.resources.energy.point < self.landauer_cost.point {
            issues.push(ValidationIssue::EnergyBelowLandauer {
                actual_j: self.resources.energy.point,
                landauer_j: self.landauer_cost.point,
            });
        }

        // Λ ≥ 0
        if self.landauer_cost.point < 0.0 {
            issues.push(ValidationIssue::NegativeLandauer);
        }

        // S_T ≥ 0
        if self.cognitive_split.statistical_complexity.point < 0.0 {
            issues.push(ValidationIssue::NegativeComplexity);
        }

        // H_T ≥ 0
        if self.cognitive_split.entropy_rate.point < 0.0 {
            issues.push(ValidationIssue::NegativeEntropyRate);
        }

        // No self-reference in Π (causal loops are acausal)
        if self.predecessors.contains(&self.id) {
            issues.push(ValidationIssue::SelfReference);
        }

        issues
    }

    /// Thermodynamic waste for this record: E − Λ with uncertainty propagation.
    #[must_use]
    pub fn thermodynamic_waste(&self) -> Estimate<f64> {
        self.resources.thermodynamic_waste(&self.landauer_cost)
    }
}

// ── Validation issue enum ─────────────────────────────────────────────────────

/// A validation issue found in a [`PacrRecord`].
#[derive(Debug, Clone, thiserror::Error)]
#[non_exhaustive]
pub enum ValidationIssue {
    /// A physical-law violation in the resource triple.
    #[error("physics violation: {0}")]
    Physics(PhysicsViolation),

    /// Actual energy is below the Landauer floor — violates Landauer's principle.
    #[error("actual energy {actual_j:.3e} J is below Landauer floor {landauer_j:.3e} J")]
    EnergyBelowLandauer { actual_j: f64, landauer_j: f64 },

    /// Landauer cost is negative — energy is non-negative by definition.
    #[error("Landauer cost cannot be negative")]
    NegativeLandauer,

    /// Statistical complexity `S_T` is negative — information is non-negative.
    #[error("statistical complexity `S_T` cannot be negative")]
    NegativeComplexity,

    /// Entropy rate `H_T` is negative — entropy is non-negative.
    #[error("entropy rate `H_T` cannot be negative")]
    NegativeEntropyRate,

    /// Record lists itself as a causal predecessor — creates a causal loop.
    #[error("record references itself as predecessor — causal loop")]
    SelfReference,
}

// ── Builder ───────────────────────────────────────────────────────────────────

/// Builder for [`PacrRecord`].
///
/// `build()` returns `Err` if **any** of the six PACR dimensions is missing.
/// Partial records are a protocol violation — the error names the missing field.
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
    /// Creates a new empty builder.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Sets the causal identity ι.
    #[must_use]
    pub fn id(mut self, id: CausalId) -> Self {
        self.id = Some(id);
        self
    }

    /// Sets the predecessor set Π.
    #[must_use]
    pub fn predecessors(mut self, preds: PredecessorSet) -> Self {
        self.predecessors = Some(preds);
        self
    }

    /// Sets the Landauer cost Λ.
    #[must_use]
    pub fn landauer_cost(mut self, cost: LandauerCost) -> Self {
        self.landauer_cost = Some(cost);
        self
    }

    /// Sets the resource triple Ω.
    #[must_use]
    pub fn resources(mut self, res: ResourceTriple) -> Self {
        self.resources = Some(res);
        self
    }

    /// Sets the cognitive split Γ.
    #[must_use]
    pub fn cognitive_split(mut self, split: CognitiveSplit) -> Self {
        self.cognitive_split = Some(split);
        self
    }

    /// Sets the opaque payload P.
    #[must_use]
    pub fn payload(mut self, payload: Payload) -> Self {
        self.payload = Some(payload);
        self
    }

    /// Builds the [`PacrRecord`].
    ///
    /// # Errors
    /// Returns [`BuildError::MissingDimension`] naming the first missing field.
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

/// Error returned by [`PacrBuilder::build`] when a required dimension is absent.
#[derive(Debug, Clone, thiserror::Error)]
#[non_exhaustive]
pub enum BuildError {
    /// A named PACR dimension was not supplied to the builder.
    #[error("missing PACR dimension: {0} — all six dimensions are mandatory")]
    MissingDimension(&'static str),
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::complexity::CognitiveSplit;
    use crate::ets::ResourceTriple;
    use bytes::Bytes;
    use smallvec::smallvec;

    fn complete_record() -> PacrRecord {
        PacrBuilder::new()
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
            .payload(Bytes::from_static(b"hello aevum"))
            .build()
            .expect("all fields provided")
    }

    // ── CausalId ─────────────────────────────────────────────────────────────

    #[test]
    fn genesis_sentinel_is_genesis() {
        assert!(CausalId::GENESIS.is_genesis());
    }

    #[test]
    fn non_zero_id_is_not_genesis() {
        assert!(!CausalId(1).is_genesis());
    }

    // ── Builder ───────────────────────────────────────────────────────────────

    #[test]
    fn builder_rejects_missing_id() {
        let r = PacrBuilder::new()
            .predecessors(smallvec![])
            .landauer_cost(Estimate::exact(0.0))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-19),
                time: Estimate::exact(1e-9),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build();
        assert!(r.is_err());
        let msg = r.unwrap_err().to_string();
        assert!(msg.contains('\u{03B9}') || msg.contains("id"), "msg={msg}");
    }

    #[test]
    fn builder_rejects_empty_partially_filled() {
        let r = PacrBuilder::new().id(CausalId(1)).build();
        assert!(r.is_err());
    }

    #[test]
    fn builder_accepts_fully_filled() {
        let r = complete_record();
        assert!(r.validate().is_empty());
    }

    // ── PacrRecord::validate ──────────────────────────────────────────────────

    #[test]
    fn validate_clean_record_is_empty() {
        assert!(complete_record().validate().is_empty());
    }

    #[test]
    fn validate_self_reference_in_predecessors() {
        let id = CausalId(99);
        let r = PacrBuilder::new()
            .id(id)
            .predecessors(smallvec![id]) // self-reference
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-19),
                time: Estimate::exact(1e-9),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        let issues = r.validate();
        assert!(issues
            .iter()
            .any(|i| matches!(i, ValidationIssue::SelfReference)));
    }

    #[test]
    fn validate_energy_below_landauer_floor() {
        let r = PacrBuilder::new()
            .id(CausalId(1))
            .predecessors(smallvec![])
            .landauer_cost(Estimate::exact(1e-10)) // huge floor
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-20), // energy < floor
                time: Estimate::exact(1e-9),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        let issues = r.validate();
        assert!(issues
            .iter()
            .any(|i| matches!(i, ValidationIssue::EnergyBelowLandauer { .. })));
    }

    // ── thermodynamic_waste ───────────────────────────────────────────────────

    #[test]
    fn waste_equals_energy_minus_landauer() {
        let r = complete_record(); // energy=1e-19, landauer=1e-20
        let waste = r.thermodynamic_waste();
        let expected = 1e-19 - 1e-20;
        assert!(
            (waste.point - expected).abs() < 1e-30,
            "waste={}",
            waste.point
        );
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use crate::complexity::CognitiveSplit;
    use crate::ets::ResourceTriple;
    use bytes::Bytes;
    use proptest::prelude::*;
    use smallvec::smallvec;

    /// Any complete record with valid physics must pass validate() cleanly.
    proptest! {
        #[test]
        fn complete_valid_record_has_no_issues(
            id_raw      in 1_u128..u128::MAX,
            energy      in 1e-25_f64..1e-10_f64,
            time        in 1e-12_f64..1.0_f64,
            space       in 0.0_f64..1e9_f64,
            s_t         in 0.0_f64..100.0_f64,
            h_t         in 0.0_f64..100.0_f64,
        ) {
            // Λ ≤ E: pick Λ as half of E
            let landauer = Estimate::exact(energy * 0.5);
            let r = PacrBuilder::new()
                .id(CausalId(id_raw))
                .predecessors(smallvec![CausalId::GENESIS])
                .landauer_cost(landauer)
                .resources(ResourceTriple {
                    energy: Estimate::exact(energy),
                    time:   Estimate::exact(time),
                    space:  Estimate::exact(space),
                })
                .cognitive_split(CognitiveSplit {
                    statistical_complexity: Estimate::exact(s_t),
                    entropy_rate:           Estimate::exact(h_t),
                })
                .payload(Bytes::new())
                .build()
                .unwrap();
            let issues = r.validate();
            prop_assert!(
                issues.is_empty(),
                "unexpected issues: {:?}", issues
            );
        }
    }
}
