//! Pillar: ALL. PACR field: ALL.
//!
//! **Aevum Core** — Layer 1 (Substrate) + Layer 2 (Physical).
//!
//! This crate integrates the Phase 0–4 building blocks into a running
//! system:
//!
//! - [`allocator`] — Landauer-on-Drop global allocator (only `unsafe` in crate).
//! - [`router`]    — Three-layer TGP → CTP → payload envelope defense.
//! - [`cso`]       — Causal Settlement Oracle stub.
//! - [`runtime`]   — tokio 3-task runtime + JSONL ledger persistence.
//!
//! # Global allocator
//!
//! This crate registers [`allocator::LandauerAllocator`] as the process-wide
//! global allocator.  Every `dealloc` call increments `BITS_ERASED`, making
//! Landauer accounting automatic and non-bypassable.

// All modules except `allocator` carry #![forbid(unsafe_code)].
// `allocator` carries #![allow(unsafe_code)] scoped to its inner module.
#![deny(unsafe_code)]
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

pub mod allocator;
pub mod cso;
pub mod forwarder;
pub mod pressure_gauge;
pub mod router;
pub mod runtime;

// ── Global Allocator ──────────────────────────────────────────────────────────
//
// Setting the global allocator in a library crate is intentional:
// every binary that links aevum-core (including the CLI and tests)
// uses LandauerAllocator, making Λ accounting mandatory and non-bypassable.
//
// This attribute is not `unsafe` — it only registers the type; the actual
// unsafe implementation is isolated in `allocator::inner`.

#[global_allocator]
static ALLOCATOR: allocator::LandauerAllocator = allocator::LandauerAllocator;

// ── Re-exports ────────────────────────────────────────────────────────────────

pub use allocator::{bits_erased, landauer_cost_joules};
pub use cso::{CausalSettlementOracle, CsoIndex};
pub use forwarder::TailscaleForwarder;
pub use router::Router;
pub use runtime::{
    export_ledger, merge_ledgers, read_status, start, verify_ledger, RuntimeConfig, RuntimeState,
    RuntimeStatus,
};
