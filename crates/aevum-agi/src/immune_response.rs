//! Pillar: I + III. PACR field: Γ, Π, P.
//!
//! **Immune Response** — converts a flood detection verdict into a permanent
//! ban record in the Rule-IR.
//!
//! # Theory
//!
//! When the [`FloodDetector`] identifies a flood attack (source concentration
//! above threshold), the immune response module:
//!
//! 1. Encodes the attacker's [`CausalId`] into a PACR record's payload.
//! 2. Appends the record to the Rule-IR's ban list (append-only, irreversible).
//! 3. Future calls to `RuleIr::is_banned(source_id)` return `true`, causing
//!    the TGP layer to drop all packets from that source before parsing.
//!
//! The ban record is itself a PACR record, providing an immutable causal trace:
//! ban happened at time T, caused by flood detected at time T−δ.

#![forbid(unsafe_code)]

use bytes::Bytes;
use pacr_types::{CausalId, CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};
use smallvec::smallvec;

#[cfg(feature = "genesis_node")]
use autopoiesis::flood_detector::FloodVerdict;

use crate::rule_ir::{BanError, RuleIr};

/// Immune response handler.
///
/// Holds the Rule-IR and processes flood verdicts to issue permanent bans.
pub struct ImmuneResponse {
    rule_ir: RuleIr,
    /// Monotonic counter for generating unique ban record IDs.
    ban_seq: u64,
}

impl ImmuneResponse {
    /// Create a new immune response handler.
    #[must_use]
    pub fn new() -> Self {
        Self { rule_ir: RuleIr::new(), ban_seq: 0 }
    }

    /// Process a [`FloodVerdict`] and issue a ban if a flood is detected.
    ///
    /// # Returns
    ///
    /// `Some(CausalId)` of the banned source if a ban was issued.
    /// `None` if the verdict was `Normal` or the ban failed validation.
    #[cfg(feature = "genesis_node")]
    pub fn process_verdict(&mut self, verdict: &FloodVerdict) -> Option<CausalId> {
        let FloodVerdict::FloodDetected { dominant_source, .. } = verdict else {
            return None;
        };
        match self.build_and_apply_ban(*dominant_source) {
            Ok(banned) => Some(banned),
            Err(_) => None,
        }
    }

    /// Whether `id` is currently banned.
    #[must_use]
    pub fn is_banned(&self, id: &CausalId) -> bool {
        self.rule_ir.is_banned(id)
    }

    /// Number of active bans.
    #[must_use]
    pub fn ban_count(&self) -> usize {
        self.rule_ir.ban_count()
    }

    /// Access the underlying Rule-IR (for statistics and screening).
    #[must_use]
    pub fn rule_ir(&self) -> &RuleIr {
        &self.rule_ir
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    fn build_and_apply_ban(&mut self, source: CausalId) -> Result<CausalId, BanError> {
        self.ban_seq += 1;
        // Ban record ID: sentinel 0xBAD0... prefix + sequence number (low bits).
        let id_val: u128 =
            0xBAD0_0000_0000_0000_0000_0000_0000_0000_u128 | u128::from(self.ban_seq);
        let ban_id = CausalId(id_val);

        // Payload: first 16 bytes = banned CausalId (big-endian), then reason.
        let mut payload = source.0.to_be_bytes().to_vec();
        payload.extend_from_slice(b"flood-ban");

        let record = PacrBuilder::new()
            .id(ban_id)
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time:   Estimate::exact(1e-6),
                space:  Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.0),
                entropy_rate:           Estimate::exact(0.0),
            })
            .payload(Bytes::from(payload))
            .build()
            .map_err(|_| BanError::PayloadTooShort { got: 0 })?;

        self.rule_ir.add_ban(record)?;
        Ok(source)
    }
}

impl Default for ImmuneResponse {
    fn default() -> Self {
        Self::new()
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(feature = "genesis_node")]
    fn normal_verdict_produces_no_ban() {
        let mut ir = ImmuneResponse::new();
        let result = ir.process_verdict(&FloodVerdict::Normal);
        assert!(result.is_none());
        assert_eq!(ir.ban_count(), 0);
    }

    #[test]
    #[cfg(feature = "genesis_node")]
    fn flood_detected_triggers_ban() {
        let mut ir = ImmuneResponse::new();
        let attacker = CausalId(0x1234_u128);
        let verdict = FloodVerdict::FloodDetected {
            dominant_source: attacker,
            concentration:   90,
        };
        let banned = ir.process_verdict(&verdict);
        assert_eq!(banned, Some(attacker));
        assert!(ir.is_banned(&attacker));
        assert_eq!(ir.ban_count(), 1);
    }

    #[test]
    #[cfg(feature = "genesis_node")]
    fn multiple_flood_verdicts_create_multiple_bans() {
        let mut ir = ImmuneResponse::new();
        for i in 0..3_u128 {
            let verdict = FloodVerdict::FloodDetected {
                dominant_source: CausalId(i + 1),
                concentration:   85,
            };
            ir.process_verdict(&verdict);
        }
        assert_eq!(ir.ban_count(), 3);
    }

    #[test]
    fn is_banned_false_when_no_bans() {
        let ir = ImmuneResponse::new();
        assert!(!ir.is_banned(&CausalId(42)));
    }
}
