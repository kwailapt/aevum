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
    RuntimeConfig, RuntimeState, RuntimeStatus,
    export_ledger, merge_ledgers, read_status, start, verify_ledger,
};
