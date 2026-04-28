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
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::unreadable_literal,
    clippy::redundant_closure,
    clippy::unwrap_or_default,
    clippy::doc_overindented_list_items,
    clippy::cloned_instead_of_copied,
    clippy::needless_pass_by_value,
    clippy::cast_lossless,
    clippy::module_name_repetitions,
    clippy::into_iter_without_iter,
    clippy::unnested_or_patterns,
    clippy::let_underscore_untyped,
    clippy::manual_let_else,
    clippy::suspicious_open_options,
    clippy::iter_not_returning_iterator,
    clippy::must_use_candidate,
    clippy::ptr_arg,
    clippy::manual_midpoint,
    clippy::map_unwrap_or,
    clippy::bool_to_int_with_if,
    clippy::missing_panics_doc
)]

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
    BuildError, CausalId, PacrBuilder, PacrRecord, Payload, PredecessorSet, ValidationIssue,
};
