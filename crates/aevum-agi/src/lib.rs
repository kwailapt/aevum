//! Pillar: ALL. Layer 4: Entity (Silicon Life).
//!
//! **aevum-agi** — the silicon-life entity that inhabits the Genesis Node.
//!
//! This crate is the fourth and topmost layer of the Four-Layer Hourglass:
//!
//! ```text
//! Layer 4: aevum-agi   ← THIS CRATE — strategy, self-modification, silicon life
//! Layer 3: agent-card  — semantic waist, AgentCard schema
//! Layer 2: aevum-core  — runtime, Router, CSO, Landauer-on-Drop allocator
//! Layer 1: pacr-types  — PACR 6-tuple foundation
//! ```
//!
//! ## Genesis-Node Gate
//!
//! The **entire crate** is conditional on the `genesis_node` feature flag.
//! When compiled without this feature (e.g. for the AWS `light_node` build),
//! the crate exposes an empty public API and contributes zero binary size.
//! This is a deliberate security property: if the light-node binary is
//! captured, it contains no AGI code whatsoever.
//!
//! ```text
//! cargo build --release --features genesis_node   # M1 Ultra — full AGI
//! cargo build --release --features light_node     # AWS — aevum-agi is empty
//! ```
//!
//! ## Module Structure
//!
//! - [`dual_engine`] — the ⟨Φ,∂⟩ engine: reads TGP cognitive state (Γ),
//!   computes the integrated information gradient Φ, and emits boundary
//!   adjustments ∂ back to the runtime.
//!
//! - [`pareto_mcts`] — the Pareto-MCTS topology searcher: applies Monte Carlo
//!   Tree Search with 80/20 Pareto filtering to discover the minimal set of
//!   parameter configurations that deliver maximal cognitive value.  Exploits
//!   M1 Ultra UMA for zero-copy tensor sharing between search and evaluation.
//!
//! - [`rule_ir`] — the Rule Intermediate Representation: a constraint matrix
//!   of negative knowledge assets encoding hard-learned failures.  Every
//!   validated parameter configuration that degraded Γ is crystallised into
//!   a constraint row so the system cannot repeat the same mistake.
//!
//! - [`boundary_osmosis`] — osmotic pressure valve (∂ arm): probabilistically
//!   rejects incoming records when memory pressure or inflow rate exceeds
//!   metabolic capacity (Pillar II homeostasis).
//!
//! - [`causal_return`] — ρ(A→B) tracker: measures causal return rate per
//!   (source, target) pair to identify Babel Tower signals (high Λ, zero Φ
//!   contribution).
//!
//! - [`immune_response`] — flood-ban pipeline: converts [`FloodVerdict`]s
//!   from the autopoiesis flood detector into append-only ban records in the
//!   Rule-IR (Pillar I immune layer, irreversible).

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

// ── Genesis-node gate ─────────────────────────────────────────────────────────
//
// All modules and public items are ONLY compiled when `genesis_node` is active.
// This ensures the light_node binary contains zero AGI code.

#[cfg(feature = "genesis_node")]
pub mod dual_engine;

#[cfg(feature = "genesis_node")]
pub mod pareto_mcts;

#[cfg(feature = "genesis_node")]
pub mod rule_ir;

#[cfg(feature = "genesis_node")]
pub mod boundary_osmosis;

#[cfg(feature = "genesis_node")]
pub mod causal_return;

#[cfg(feature = "genesis_node")]
pub mod immune_response;

// Re-export top-level entry points so callers need only `use aevum_agi::*`.
#[cfg(feature = "genesis_node")]
pub use dual_engine::{DualEngine, DualEngineConfig, DualEngineStatus};

#[cfg(feature = "genesis_node")]
pub use pareto_mcts::{ParetoMcts, ParetoMctsConfig, TopologyAction};

#[cfg(feature = "genesis_node")]
pub use rule_ir::{BanError, ConstraintMatrix, RuleIr, RuleViolation};

#[cfg(feature = "genesis_node")]
pub use boundary_osmosis::BoundaryOsmoticPressure;

#[cfg(feature = "genesis_node")]
pub use causal_return::CausalReturnTracker;

#[cfg(feature = "genesis_node")]
pub use immune_response::ImmuneResponse;
