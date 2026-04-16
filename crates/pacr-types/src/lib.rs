//! # pacr-types
//!
//! Pillar: ALL. PACR field: ALL.
//!
//! The **trust root** of the entire Aevum codebase.
//! Defines the PACR 6-tuple and all shared physical measurement types.
//!
//! ```text
//! R = (ι,  Π,              Λ,            Ω,               Γ,               P)
//!      id  predecessors    landauer_cost  resources         cognitive_split   payload
//! ```
//!
//! | Field | Module     | Physical axiom                                    |
//! |-------|------------|---------------------------------------------------|
//! | ι     | record     | Logical a priori (referential necessity)           |
//! | Π     | record     | Special relativity → causal partial order          |
//! | Λ     | landauer   | Landauer's principle (Second Law)                 |
//! | Ω     | ets        | Conservation laws + Margolus–Levitin              |
//! | Γ     | complexity | Computational mechanics (arXiv:2601.03220)         |
//! | P     | record     | Completeness axiom                                |
//!
//! ## Rules
//! - Schema is **append-only**: existing field semantics NEVER change.
//! - This crate has **zero dependencies** beyond serde, smallvec, bytes, thiserror.
//! - `#![forbid(unsafe_code)]` is unconditional: no exceptions.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

pub mod complexity;
pub mod estimate;
pub mod ets;
pub mod landauer;
pub mod record;

// ── Top-level re-exports (the public API of this crate) ──────────────────────

pub use complexity::CognitiveSplit;
pub use estimate::{Estimate, EstimateError};
pub use ets::{PhysicsViolation, ResourceTriple};
pub use landauer::{landauer_floor_joules, LandauerCost, H_BAR, K_B, LANDAUER_JOULES_300K};
pub use record::{
    BuildError, CausalId, Payload, PacrBuilder, PacrRecord, PredecessorSet, ValidationIssue,
};
