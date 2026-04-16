//! Pillar: ALL. Layer 3: Semantic Waist.
//!
//! **AgentCard** — the self-declaration of an agent's identity, capabilities,
//! and terms of interaction.
//!
//! AgentCard is the semantic waist of the Four-Layer Hourglass:
//!
//! ```text
//! Layer 4: aevum-agi   — reads AgentCard to make strategic decisions
//! Layer 3: agent-card  ← THIS CRATE (pure schema, zero execution)
//! Layer 2: aevum-core  — routes PACR records using AgentCard capabilities
//! Layer 1: pacr-types  — foundation types (CausalId, Estimate<T>)
//! ```
//!
//! ## Structural Asymmetric Coupling
//!
//! - AgentCard depends on **nothing** below Layer 3 except `CausalId` (ι).
//! - `aevum-core` unilaterally reads AgentCard for routing decisions.
//! - AgentCard **never** imports from `aevum-core` or `epsilon-engine`.
//!
//! ## Physics Invariants
//!
//! - `pricing.base_cost_joules`, when set and non-zero, must be ≥ the
//!   Landauer floor at 300 K: `LANDAUER_FLOOR_JOULES = 2.854e-21 J`.
//!   A price below this is physically impossible.
//! - The envelope (TGP → CTP → Payload) mirrors the Router's three-layer
//!   defence: physical plausibility before causal consistency before semantics.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(clippy::module_name_repetitions)]

pub mod envelope;
pub mod schema;

pub use envelope::{ApplicationPayload, CtpFrame, TgpFrame};
pub use schema::{
    AgentCard, AuthConfig, AuthScheme, Capability, Endpoint, Metadata, PricingModel, Protocol,
};

/// Landauer floor at 300 K: k_B × 300 × ln(2) ≈ 2.854 × 10⁻²¹ J.
///
/// Any `base_cost_joules` value strictly between 0 and this constant is
/// physically impossible — it would imply erasing less than one bit of entropy.
pub const LANDAUER_FLOOR_JOULES: f64 = 2.854e-21;

/// TGP envelope magic bytes: ASCII "PACR" encoded as a little-endian u32.
pub const TGP_MAGIC: u32 = 0x5043_4152; // 'P','A','C','R'
