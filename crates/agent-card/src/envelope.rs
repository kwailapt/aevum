//! Pillar: I + II + III. PACR fields: ι, Π, Λ, Ω, Γ, P.
//!
//! **Inverted three-layer envelope** — physical proof before semantic routing.
//!
//! The envelope structure is the inverse of the network stack. Instead of
//! payload wrapping headers, physical proof wraps the causal frame wraps the
//! payload:
//!
//! ```text
//! ┌────────────────────────────────────────────────┐
//! │ TGP Physical Frame (outermost)                 │  ← LAYER 1
//! │   magic: 0x50434152  ("PACR")                  │
//! │   id: CausalId (ι)                             │
//! │   landauer_cost: LandauerCost (Λ)              │
//! │   resources: ResourceTriple (Ω)                │
//! │   cognitive_split: CognitiveSplit (Γ)          │
//! ├────────────────────────────────────────────────┤
//! │ CTP Causal Frame (middle)                      │  ← LAYER 2
//! │   predecessors: PredecessorSet (Π)             │
//! ├────────────────────────────────────────────────┤
//! │ Application Payload (innermost)                │  ← LAYER 3
//! │   agent_card: Option<AgentCard>                │
//! │   body: bytes::Bytes (P)                       │
//! └────────────────────────────────────────────────┘
//! ```
//!
//! A forged record with zero computational backing is rejected at Layer 1
//! (TGP) before the router allocates memory to inspect the causal frame or
//! parse the AgentCard.  The physics layer is the bouncer; the semantic layer
//! is the receptionist behind the bouncer.
//!
//! This module provides the data types for each layer.  Actual validation is
//! performed by `aevum-core`'s Router — this crate holds only the schema.

#![forbid(unsafe_code)]

use bytes::Bytes;
use pacr_types::{CausalId, CognitiveSplit, Estimate, PredecessorSet, ResourceTriple};
use serde::{Deserialize, Serialize};

use crate::{schema::AgentCard, TGP_MAGIC};

// ── TGP Physical Frame ────────────────────────────────────────────────────────

/// LandauerCost wrapper — a single `Estimate<f64>` representing Λ in Joules.
///
/// Retyped here so `TgpFrame` can own its fields without importing from
/// `landauer-probe` (which lives in a different layer).
pub type LandauerCost = Estimate<f64>;

/// Layer 1 — TGP Physical Frame.
///
/// Contains the physical proof of work: Landauer cost (Λ), resource triple (Ω),
/// and cognitive split (Γ), plus the causal identity (ι) that names this record.
///
/// The TGP frame is always the outermost layer of an envelope.  A router that
/// receives a raw byte stream can reject it immediately if the physics are
/// implausible — without ever deserialising the inner layers.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TgpFrame {
    /// Protocol magic: must equal [`TGP_MAGIC`] (`0x50434152`, ASCII "PACR").
    pub magic: u32,

    /// Causal identity of this record (ι).
    pub id: CausalId,

    /// Landauer cost estimate (Λ) — minimum energy to erase the bits.
    pub landauer_cost: LandauerCost,

    /// Energy-Time-Space resource triple (Ω).
    pub resources: ResourceTriple,

    /// Cognitive complexity split S_T / H_T (Γ).
    pub cognitive_split: CognitiveSplit,
}

impl TgpFrame {
    /// Returns `true` if the TGP frame is physically plausible.
    ///
    /// Physics invariants checked:
    /// - `magic == TGP_MAGIC`
    /// - `Λ ≥ 0` (Landauer cost is non-negative)
    /// - `Ω.energy ≥ Λ` (actual energy ≥ Landauer floor)
    /// - `Ω.time ≥ 0`
    /// - `Ω.space ≥ 0`
    /// - `Γ.statistical_complexity ≥ 0`
    /// - `Γ.entropy_rate ≥ 0`
    #[must_use]
    pub fn is_physically_plausible(&self) -> bool {
        self.magic == TGP_MAGIC
            && self.landauer_cost.point >= 0.0
            && self.resources.energy.point >= self.landauer_cost.point
            && self.resources.time.point >= 0.0
            && self.resources.space.point >= 0.0
            && self.cognitive_split.statistical_complexity.point >= 0.0
            && self.cognitive_split.entropy_rate.point >= 0.0
    }
}

// ── CTP Causal Frame ──────────────────────────────────────────────────────────

/// Layer 2 — CTP Causal Frame.
///
/// Contains the predecessor set (Π) that places this record in the causal DAG.
/// The causal frame is validated against the live DAG by the router.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CtpFrame {
    /// Causal predecessors (Π) — the edges of the causal DAG.
    pub predecessors: PredecessorSet,
}

impl CtpFrame {
    /// Returns `true` if `id` appears in the predecessor set (self-reference).
    ///
    /// A record that lists itself as a predecessor creates a causal loop,
    /// which is a protocol violation.
    #[must_use]
    pub fn has_self_reference(&self, id: CausalId) -> bool {
        self.predecessors.contains(&id)
    }
}

// ── Application Payload ───────────────────────────────────────────────────────

/// Layer 3 — Application Payload.
///
/// Contains the optional [`AgentCard`] (semantic routing data) plus the raw
/// opaque payload bytes (P).  This layer is only reached after Layer 1
/// (physics) and Layer 2 (causality) have both passed.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ApplicationPayload {
    /// Parsed AgentCard for semantic routing (optional).
    ///
    /// When `None`, the record carries no routing metadata; the router uses
    /// only the TGP/CTP frames to decide how to handle the payload.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent_card: Option<AgentCard>,

    /// Opaque payload bytes (P) — application-defined content.
    #[serde(with = "bytes_serde")]
    pub body: Bytes,
}

// ── serde helper for Bytes ────────────────────────────────────────────────────

mod bytes_serde {
    use bytes::Bytes;
    use serde::{Deserialize, Deserializer, Serialize, Serializer};

    pub fn serialize<S>(bytes: &Bytes, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        bytes.as_ref().serialize(serializer)
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Bytes, D::Error>
    where
        D: Deserializer<'de>,
    {
        let vec: Vec<u8> = Vec::deserialize(deserializer)?;
        Ok(Bytes::from(vec))
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use pacr_types::{CognitiveSplit, Estimate, ResourceTriple};
    use smallvec::smallvec;

    fn valid_tgp_frame(id: u128) -> TgpFrame {
        TgpFrame {
            magic: TGP_MAGIC,
            id: CausalId(id),
            landauer_cost: Estimate::exact(1e-20),
            resources: ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(4096.0),
            },
            cognitive_split: CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate: Estimate::exact(0.9),
            },
        }
    }

    // ── TgpFrame ───────────────────────────────────────────────────────────────

    #[test]
    fn valid_tgp_frame_is_plausible() {
        assert!(valid_tgp_frame(1).is_physically_plausible());
    }

    #[test]
    fn wrong_magic_is_implausible() {
        let mut frame = valid_tgp_frame(2);
        frame.magic = 0xDEAD_BEEF;
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn energy_below_landauer_is_implausible() {
        let mut frame = valid_tgp_frame(3);
        frame.landauer_cost = Estimate::exact(1e-10); // huge Landauer floor
        frame.resources.energy = Estimate::exact(1e-20); // actual < floor
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn negative_landauer_is_implausible() {
        let mut frame = valid_tgp_frame(4);
        frame.landauer_cost = Estimate::exact(-1e-20);
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn negative_time_is_implausible() {
        let mut frame = valid_tgp_frame(5);
        frame.resources.time = Estimate::exact(-1e-6);
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn negative_space_is_implausible() {
        let mut frame = valid_tgp_frame(6);
        frame.resources.space = Estimate::exact(-1.0);
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn negative_statistical_complexity_is_implausible() {
        let mut frame = valid_tgp_frame(7);
        frame.cognitive_split.statistical_complexity = Estimate::exact(-0.1);
        assert!(!frame.is_physically_plausible());
    }

    #[test]
    fn negative_entropy_rate_is_implausible() {
        let mut frame = valid_tgp_frame(8);
        frame.cognitive_split.entropy_rate = Estimate::exact(-0.1);
        assert!(!frame.is_physically_plausible());
    }

    // ── CtpFrame ───────────────────────────────────────────────────────────────

    #[test]
    fn self_reference_detected() {
        let id = CausalId(100);
        let frame = CtpFrame {
            predecessors: smallvec![id],
        };
        assert!(frame.has_self_reference(id));
    }

    #[test]
    fn no_self_reference_with_different_predecessors() {
        let id = CausalId(200);
        let frame = CtpFrame {
            predecessors: smallvec![CausalId(1), CausalId(2)],
        };
        assert!(!frame.has_self_reference(id));
    }

    #[test]
    fn genesis_predecessor_no_self_reference() {
        let id = CausalId(300);
        let frame = CtpFrame {
            predecessors: smallvec![CausalId::GENESIS],
        };
        assert!(!frame.has_self_reference(id));
    }

    // ── ApplicationPayload ─────────────────────────────────────────────────────

    #[test]
    fn payload_with_empty_body_roundtrips() {
        let payload = ApplicationPayload {
            agent_card: None,
            body: Bytes::new(),
        };
        let json = serde_json::to_string(&payload).unwrap();
        let decoded: ApplicationPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(payload, decoded);
    }

    #[test]
    fn payload_with_body_bytes_roundtrips() {
        let payload = ApplicationPayload {
            agent_card: None,
            body: Bytes::from_static(b"hello PACR"),
        };
        let json = serde_json::to_string(&payload).unwrap();
        let decoded: ApplicationPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(payload.body, decoded.body);
    }

    // ── TgpFrame serde ─────────────────────────────────────────────────────────

    #[test]
    fn tgp_frame_serde_roundtrip() {
        let frame = valid_tgp_frame(99);
        let json = serde_json::to_string(&frame).unwrap();
        let decoded: TgpFrame = serde_json::from_str(&json).unwrap();
        assert_eq!(frame, decoded);
    }
}
