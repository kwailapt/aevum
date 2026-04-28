//! Pillar: I + II. PACR field: ι, Π, Λ, Ω, Γ.
//!
//! **Three-Layer Envelope Defense** — physics-first rejection.
//!
//! Incoming PACR records are validated in three layers before being accepted:
//!
//! ```text
//! ┌─────────────────────────────────────────┐
//! │ Layer 1 — TGP Physical Frame            │  ← physics plausibility
//! │   E ≥ Λ, T > 0, S ≥ 0, Λ > 0          │
//! │   Γ: S_T ≥ 0, H_T ≥ 0                 │
//! ├─────────────────────────────────────────┤
//! │ Layer 2 — CTP Causal Frame              │  ← DAG consistency
//! │   No self-reference in Π               │
//! │   All non-GENESIS predecessors exist   │
//! ├─────────────────────────────────────────┤
//! │ Layer 3 — Payload Accepted              │  ← semantic routing (future)
//! └─────────────────────────────────────────┘
//! ```
//!
//! A forged record with zero computational backing is rejected at Layer 1
//! before the router allocates memory to inspect the causal frame or payload.
//! The physics layer is the bouncer; the causal layer is the inner check.

#![forbid(unsafe_code)]

use std::sync::Arc;

use causal_dag::CausalDag;
use pacr_types::{CausalId, PacrRecord};
use thiserror::Error;

use crate::pressure_gauge::ThermodynamicPressureGauge;

// ── Rejection reasons ─────────────────────────────────────────────────────────

/// Why a record was rejected by the router.
#[derive(Debug, Clone, Error)]
#[non_exhaustive]
pub enum RejectionReason {
    // ── Layer 1: TGP Physical Frame ───────────────────────────────────────────
    /// Actual energy is below the Landauer floor — physics violation.
    #[error("TGP: actual energy {actual_j:.3e} J < Landauer floor {landauer_j:.3e} J")]
    EnergyBelowLandauer { actual_j: f64, landauer_j: f64 },

    /// Landauer cost is negative — energy is non-negative by definition.
    #[error("TGP: Landauer cost is negative ({value:.3e} J)")]
    NegativeLandauer { value: f64 },

    /// Accumulated Λ throughput exceeds the thermodynamic pressure budget.
    #[error("TGP: thermodynamic pressure budget exceeded (throttled)")]
    ThrottleExceeded,

    /// Elapsed time is negative — time is non-negative by definition.
    #[error("TGP: elapsed time is negative ({value:.3e} s)")]
    NegativeTime { value: f64 },

    /// Space usage is negative — memory is non-negative by definition.
    #[error("TGP: space usage is negative ({value:.3e} bytes)")]
    NegativeSpace { value: f64 },

    /// Statistical complexity S_T is negative — information is non-negative.
    #[error("TGP: statistical complexity S_T is negative ({value:.3e})")]
    NegativeStatisticalComplexity { value: f64 },

    /// Entropy rate H_T is negative — entropy is non-negative.
    #[error("TGP: entropy rate H_T is negative ({value:.3e})")]
    NegativeEntropyRate { value: f64 },

    // ── Layer 2: CTP Causal Frame ─────────────────────────────────────────────
    /// Record lists itself as a causal predecessor — creates a causal loop.
    #[error("CTP: record {id:?} references itself as predecessor")]
    SelfReference { id: CausalId },

    /// A non-GENESIS predecessor does not exist in the local DAG.
    #[error("CTP: predecessor {missing:?} not found in DAG (child {child:?})")]
    MissingPredecessor { child: CausalId, missing: CausalId },
}

// ── Routing decision ──────────────────────────────────────────────────────────

/// The router's verdict on a single PACR record.
#[derive(Debug)]
pub enum RouterDecision {
    /// Record passed all three layers; ready for DAG append and downstream.
    Accepted,
    /// Record was rejected; contains the first violation found.
    Rejected(RejectionReason),
}

impl RouterDecision {
    /// Returns `true` if the record was accepted.
    #[must_use]
    pub fn is_accepted(&self) -> bool {
        matches!(self, Self::Accepted)
    }
}

// ── Router ────────────────────────────────────────────────────────────────────

/// Three-layer envelope defense router.
///
/// Holds a shared reference to the causal DAG for Layer 2 predecessor checks.
/// Layer 1.5: thermodynamic pressure gauge — rejects envelopes when aggregate
/// Λ throughput exceeds the configured power budget.
pub struct Router {
    dag: Arc<CausalDag>,
    pressure_gauge: ThermodynamicPressureGauge,
}

impl Router {
    /// Creates a new router backed by the given causal DAG.
    ///
    /// Pressure gauge defaults to `max_watts = f64::MAX` (no throttling),
    /// preserving backward compatibility with existing call sites.
    #[must_use]
    pub fn new(dag: Arc<CausalDag>) -> Self {
        Self {
            dag,
            pressure_gauge: ThermodynamicPressureGauge::new(f64::MAX, 1.0),
        }
    }

    /// Creates a router with an explicit thermodynamic pressure gauge.
    #[must_use]
    pub fn with_pressure_gauge(dag: Arc<CausalDag>, gauge: ThermodynamicPressureGauge) -> Self {
        Self {
            dag,
            pressure_gauge: gauge,
        }
    }

    /// Validate a PACR record through all three layers.
    ///
    /// Returns the first violation found; layers are checked in order so that
    /// cheap physics checks always run before DAG lookups.
    #[must_use]
    pub fn validate(&self, record: &PacrRecord) -> RouterDecision {
        // ── Layer 1: TGP Physical Frame ───────────────────────────────────────
        if let Some(reason) = check_tgp(record) {
            return RouterDecision::Rejected(reason);
        }

        // ── Layer 1.5: Thermodynamic Pressure ────────────────────────────────
        if self
            .pressure_gauge
            .should_throttle(record.landauer_cost.point)
        {
            return RouterDecision::Rejected(RejectionReason::ThrottleExceeded);
        }

        // ── Layer 2: CTP Causal Frame ─────────────────────────────────────────
        if let Some(reason) = check_ctp(record, &self.dag) {
            return RouterDecision::Rejected(reason);
        }

        // ── Layer 3: Payload Accepted ─────────────────────────────────────────
        // Future: parse AgentCard for semantic routing.
        // For now, any record reaching Layer 3 is unconditionally accepted.
        RouterDecision::Accepted
    }
}

// ── Layer 1: TGP Physical Frame ───────────────────────────────────────────────

/// Check the TGP physical frame invariants.
///
/// Returns `Some(reason)` on the first violation, `None` if the record is
/// physically plausible.
fn check_tgp(r: &PacrRecord) -> Option<RejectionReason> {
    // Λ ≥ 0
    if r.landauer_cost.point < 0.0 {
        return Some(RejectionReason::NegativeLandauer {
            value: r.landauer_cost.point,
        });
    }

    // E ≥ Λ (Landauer's principle)
    if r.resources.energy.point < r.landauer_cost.point {
        return Some(RejectionReason::EnergyBelowLandauer {
            actual_j: r.resources.energy.point,
            landauer_j: r.landauer_cost.point,
        });
    }

    // T ≥ 0
    if r.resources.time.point < 0.0 {
        return Some(RejectionReason::NegativeTime {
            value: r.resources.time.point,
        });
    }

    // S ≥ 0
    if r.resources.space.point < 0.0 {
        return Some(RejectionReason::NegativeSpace {
            value: r.resources.space.point,
        });
    }

    // S_T ≥ 0
    if r.cognitive_split.statistical_complexity.point < 0.0 {
        return Some(RejectionReason::NegativeStatisticalComplexity {
            value: r.cognitive_split.statistical_complexity.point,
        });
    }

    // H_T ≥ 0
    if r.cognitive_split.entropy_rate.point < 0.0 {
        return Some(RejectionReason::NegativeEntropyRate {
            value: r.cognitive_split.entropy_rate.point,
        });
    }

    None
}

// ── Layer 2: CTP Causal Frame ─────────────────────────────────────────────────

/// Check the CTP causal frame invariants against the live DAG.
fn check_ctp(r: &PacrRecord, dag: &CausalDag) -> Option<RejectionReason> {
    // No self-reference
    if r.predecessors.contains(&r.id) {
        return Some(RejectionReason::SelfReference { id: r.id });
    }

    // All non-GENESIS predecessors must exist in the DAG.
    for &pred in &r.predecessors {
        if pred.is_genesis() {
            continue; // GENESIS is a sentinel; it never needs to be in the DAG
        }
        if !dag.contains(&pred) {
            return Some(RejectionReason::MissingPredecessor {
                child: r.id,
                missing: pred,
            });
        }
    }

    None
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};
    use smallvec::smallvec;

    fn valid_record(id: u128) -> PacrRecord {
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(4096.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate: Estimate::exact(0.9),
            })
            .payload(Bytes::from_static(b"test"))
            .build()
            .expect("all fields provided")
    }

    fn make_dag_with(record: PacrRecord) -> Arc<CausalDag> {
        let dag = Arc::new(CausalDag::new());
        dag.append(record).expect("valid record");
        dag
    }

    // ── Layer 1: TGP ─────────────────────────────────────────────────────────

    #[test]
    fn valid_record_is_accepted() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let r = valid_record(1);
        assert!(router.validate(&r).is_accepted());
    }

    #[test]
    fn rejects_energy_below_landauer() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let r = PacrBuilder::new()
            .id(CausalId(2))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-10)) // huge floor
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-20), // energy < floor
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(matches!(
            router.validate(&r),
            RouterDecision::Rejected(RejectionReason::EnergyBelowLandauer { .. })
        ));
    }

    #[test]
    fn rejects_negative_landauer() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let r = PacrBuilder::new()
            .id(CausalId(3))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(-1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(matches!(
            router.validate(&r),
            RouterDecision::Rejected(RejectionReason::NegativeLandauer { .. })
        ));
    }

    #[test]
    fn rejects_negative_time() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let r = PacrBuilder::new()
            .id(CausalId(4))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(-1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(matches!(
            router.validate(&r),
            RouterDecision::Rejected(RejectionReason::NegativeTime { .. })
        ));
    }

    // ── Layer 2: CTP ──────────────────────────────────────────────────────────

    #[test]
    fn rejects_self_reference() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let id = CausalId(10);
        let r = PacrBuilder::new()
            .id(id)
            .predecessors(smallvec![id]) // self-reference
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(matches!(
            router.validate(&r),
            RouterDecision::Rejected(RejectionReason::SelfReference { .. })
        ));
    }

    #[test]
    fn rejects_missing_predecessor() {
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        // Predecessor CausalId(999) does not exist in the empty DAG.
        let r = PacrBuilder::new()
            .id(CausalId(20))
            .predecessors(smallvec![CausalId(999)])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(matches!(
            router.validate(&r),
            RouterDecision::Rejected(RejectionReason::MissingPredecessor { .. })
        ));
    }

    #[test]
    fn accepts_genesis_predecessor_without_dag_entry() {
        // GENESIS is a sentinel — it must NOT be required to exist in the DAG.
        let dag = Arc::new(CausalDag::new());
        let router = Router::new(dag);
        let r = valid_record(30);
        // valid_record uses GENESIS as predecessor; DAG is empty.
        assert!(router.validate(&r).is_accepted());
    }

    #[test]
    fn accepts_record_with_existing_predecessor() {
        let parent = valid_record(40);
        let dag = make_dag_with(parent);
        let router = Router::new(Arc::clone(&dag));
        // Child references parent (CausalId(40)), which exists in the DAG.
        let child = PacrBuilder::new()
            .id(CausalId(41))
            .predecessors(smallvec![CausalId(40)])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate: Estimate::exact(0.0),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        assert!(router.validate(&child).is_accepted());
    }
}
