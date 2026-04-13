//! Pillar: ALL. Layer 3: Semantic Waist. PACR field: all six.
//!
//! **AgentCard schema** — typed Rust representation of the AgentCard v1.0
//! JSON schema.  All types are pure data: they derive `Serialize`/`Deserialize`
//! but carry zero execution logic and make no network calls.
//!
//! Schema invariants enforced at construction time by [`AgentCard::validate`]:
//!
//! - `agent_id`: 26-character Crockford Base32 ULID.
//! - `version`: semver 2.0 (`MAJOR.MINOR.PATCH[-pre][+build]`).
//! - `capabilities`: at least one entry; each `id` is lowercase dot-namespaced.
//! - `pricing.base_cost_joules`: if set and non-zero, must be ≥ `LANDAUER_FLOOR_JOULES`.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

use crate::LANDAUER_FLOOR_JOULES;

// ── Validation error ──────────────────────────────────────────────────────────

/// An error returned by [`AgentCard::validate`].
#[derive(Debug, Clone, Error)]
#[error("{0}")]
pub struct ValidationError(pub String);

// ── Protocol ──────────────────────────────────────────────────────────────────

/// Transport protocol used to communicate with the agent.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Protocol {
    #[serde(rename = "http")]
    Http,
    #[serde(rename = "websocket")]
    WebSocket,
    #[serde(rename = "sse")]
    Sse,
    #[serde(rename = "grpc")]
    Grpc,
    #[serde(rename = "mcp")]
    Mcp,
    #[serde(rename = "google_a2a")]
    GoogleA2a,
    #[serde(rename = "native")]
    Native,
}

// ── AuthScheme ────────────────────────────────────────────────────────────────

/// Authentication scheme for reaching this agent.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AuthScheme {
    #[serde(rename = "none")]
    None,
    #[serde(rename = "bearer")]
    Bearer,
    #[serde(rename = "api_key")]
    ApiKey,
    #[serde(rename = "oauth2")]
    Oauth2,
    #[serde(rename = "mtls")]
    Mtls,
}

// ── AuthConfig ────────────────────────────────────────────────────────────────

/// Authentication configuration for reaching this agent.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AuthConfig {
    /// Authentication scheme.
    pub scheme: AuthScheme,

    /// Token endpoint URL (for `oauth2` scheme).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token_url: Option<String>,

    /// Header name where the credential is sent (for `api_key` scheme).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub header: Option<String>,
}

// ── Endpoint ──────────────────────────────────────────────────────────────────

/// How to reach this agent.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Endpoint {
    /// Transport protocol.
    pub protocol: Protocol,

    /// URL or address of the endpoint.
    pub url: String,

    /// Optional health-check endpoint.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub health_url: Option<String>,

    /// Authentication configuration.  `None` means no authentication.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub auth: Option<AuthConfig>,
}

// ── Capability ────────────────────────────────────────────────────────────────

/// A single capability that the agent can perform.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Capability {
    /// Machine-readable capability identifier.
    ///
    /// Must match `^[a-z0-9][a-z0-9._-]*$` (dot-namespaced, e.g. `text.generate`).
    pub id: String,

    /// Human-readable description.
    pub description: String,

    /// Optional semantic tags for discovery and routing.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,

    /// JSON Schema describing the accepted input, or `None` for unstructured.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_schema: Option<Value>,

    /// JSON Schema describing the produced output, or `None` for unstructured.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_schema: Option<Value>,
}

// ── PricingModel ──────────────────────────────────────────────────────────────

/// Cost model for interacting with this agent.
///
/// Thermodynamic settlement uses Joules; fiat settlement is optional.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PricingModel {
    /// Base cost per request in Joules (Landauer unit).
    ///
    /// If set and non-zero, must be ≥ [`LANDAUER_FLOOR_JOULES`].
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_cost_joules: Option<f64>,

    /// Estimated end-to-end latency in milliseconds.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub estimated_latency_ms: Option<f64>,

    /// ISO 4217 currency code or token symbol (e.g. `"USD"`, `"USDC"`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub currency: Option<String>,

    /// Cost per request in the fiat/token currency.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cost_per_request: Option<f64>,
}

// ── Metadata ──────────────────────────────────────────────────────────────────

/// Metadata derived from PACR causal history via the π projection function.
///
/// Fields prefixed with `pacr:` are computed from the ledger, never self-declared.
/// Custom fields without the `pacr:` prefix may be set by the agent operator.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct Metadata {
    /// Count of PACR records involving this `agent_id`.
    #[serde(rename = "pacr:interaction_count", skip_serializing_if = "Option::is_none")]
    pub interaction_count: Option<u64>,

    /// Time-decay-weighted average latency in milliseconds.
    #[serde(rename = "pacr:avg_latency_ms", skip_serializing_if = "Option::is_none")]
    pub avg_latency_ms: Option<f64>,

    /// Time-decay-weighted average energy cost in Joules.
    #[serde(rename = "pacr:avg_cost_joules", skip_serializing_if = "Option::is_none")]
    pub avg_cost_joules: Option<f64>,

    /// Reputation score in \[0.0, 1.0\]: `f(success_rate, latency, Sτ/Hτ)`.
    #[serde(rename = "pacr:reputation_score", skip_serializing_if = "Option::is_none")]
    pub reputation_score: Option<f64>,

    /// PageRank variant on the causal interaction graph.
    #[serde(rename = "pacr:influence_rank", skip_serializing_if = "Option::is_none")]
    pub influence_rank: Option<f64>,

    /// Betweenness centrality score.
    #[serde(rename = "pacr:critical_score", skip_serializing_if = "Option::is_none")]
    pub critical_score: Option<f64>,
}

// ── AgentCard ─────────────────────────────────────────────────────────────────

/// AgentCard v1.0 — the self-declaration of an agent's identity, capabilities,
/// and terms of interaction.
///
/// Construct via `serde_json::from_str` or by building the struct directly.
/// Call [`AgentCard::validate`] to check schema invariants after construction.
///
/// # Example
///
/// ```rust
/// use agent_card::schema::{AgentCard, Capability, Endpoint, Protocol};
///
/// let card = AgentCard {
///     agent_id:     "01HZQK3P8EMXR9V7T5N2W4J6C0".into(),
///     name:         "My Agent".into(),
///     version:      "1.0.0".into(),
///     capabilities: vec![Capability {
///         id:            "text.generate".into(),
///         description:   "Generate text from a prompt.".into(),
///         tags:          None,
///         input_schema:  None,
///         output_schema: None,
///     }],
///     endpoint: Endpoint {
///         protocol:   Protocol::Http,
///         url:        "https://agent.example.com/api".into(),
///         health_url: None,
///         auth:       None,
///     },
///     pricing:  None,
///     metadata: None,
/// };
/// assert!(card.validate().is_ok());
/// ```
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentCard {
    /// Globally unique agent identifier (26-char Crockford Base32 ULID).
    pub agent_id: String,

    /// Human-readable display name (1–128 characters).
    pub name: String,

    /// Semantic version of this agent's card format (semver 2.0).
    pub version: String,

    /// Capabilities offered by this agent (at least one required).
    pub capabilities: Vec<Capability>,

    /// How to reach this agent.
    pub endpoint: Endpoint,

    /// Optional cost model.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pricing: Option<PricingModel>,

    /// Metadata derived from PACR ledger (π projection).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<Metadata>,
}

impl AgentCard {
    /// Validate all schema invariants.
    ///
    /// Returns `Ok(())` if valid, or the first [`ValidationError`] found.
    ///
    /// # Errors
    ///
    /// - `agent_id` is not a 26-character Crockford Base32 ULID.
    /// - `name` is empty.
    /// - `version` is not semver 2.0.
    /// - `capabilities` is empty.
    /// - Any capability `id` does not match `^[a-z0-9][a-z0-9._-]*$`.
    /// - `pricing.base_cost_joules` is non-zero and below `LANDAUER_FLOOR_JOULES`.
    pub fn validate(&self) -> Result<(), ValidationError> {
        // agent_id: 26-char Crockford Base32 ULID
        if !is_valid_ulid(&self.agent_id) {
            return Err(ValidationError(format!(
                "agent_id must be a 26-character Crockford Base32 ULID, got: {:?}",
                self.agent_id
            )));
        }

        // name: non-empty, ≤ 128 chars
        if self.name.is_empty() {
            return Err(ValidationError("name must not be empty".into()));
        }
        if self.name.len() > 128 {
            return Err(ValidationError(format!(
                "name exceeds 128 characters (got {})",
                self.name.len()
            )));
        }

        // version: semver 2.0
        if !is_valid_semver(&self.version) {
            return Err(ValidationError(format!(
                "version must be semver 2.0 (e.g. \"1.0.0\"), got: {:?}",
                self.version
            )));
        }

        // capabilities: at least one
        if self.capabilities.is_empty() {
            return Err(ValidationError(
                "capabilities must contain at least one entry".into(),
            ));
        }

        for (i, cap) in self.capabilities.iter().enumerate() {
            if !is_valid_capability_id(&cap.id) {
                return Err(ValidationError(format!(
                    "capabilities[{i}].id must match ^[a-z0-9][a-z0-9._-]*$, got: {:?}",
                    cap.id
                )));
            }
            if cap.id.len() > 128 {
                return Err(ValidationError(format!(
                    "capabilities[{i}].id exceeds 128 characters"
                )));
            }
            if cap.description.is_empty() {
                return Err(ValidationError(format!(
                    "capabilities[{i}].description must not be empty"
                )));
            }
        }

        // endpoint.url: non-empty
        if self.endpoint.url.is_empty() {
            return Err(ValidationError("endpoint.url must not be empty".into()));
        }

        // pricing.base_cost_joules: must be ≥ LANDAUER_FLOOR_JOULES if non-zero
        if let Some(pricing) = &self.pricing {
            if let Some(joules) = pricing.base_cost_joules {
                if joules < 0.0 {
                    return Err(ValidationError(
                        "pricing.base_cost_joules must be >= 0".into(),
                    ));
                }
                if joules > 0.0 && joules < LANDAUER_FLOOR_JOULES {
                    return Err(ValidationError(format!(
                        "pricing.base_cost_joules {joules:.3e} J is below the Landauer \
                         floor at 300 K ({LANDAUER_FLOOR_JOULES:.3e} J) — physically implausible"
                    )));
                }
            }
            if let Some(latency) = pricing.estimated_latency_ms {
                if latency < 0.0 {
                    return Err(ValidationError(
                        "pricing.estimated_latency_ms must be >= 0".into(),
                    ));
                }
            }
            if let Some(cost) = pricing.cost_per_request {
                if cost < 0.0 {
                    return Err(ValidationError(
                        "pricing.cost_per_request must be >= 0".into(),
                    ));
                }
            }
        }

        Ok(())
    }
}

// ── Format validators ─────────────────────────────────────────────────────────

/// Validate a Crockford Base32 ULID: exactly 26 uppercase characters from the
/// Crockford alphabet (0-9, A-H, J, K, M, N, P-T, V-Z — no I, L, O, U).
fn is_valid_ulid(s: &str) -> bool {
    if s.len() != 26 {
        return false;
    }
    s.chars().all(|c| {
        matches!(c,
            '0'..='9' | 'A'..='H' | 'J' | 'K' | 'M' | 'N' | 'P'..='T' | 'V'..='Z'
        )
    })
}

/// Validate a semver 2.0 string.
fn is_valid_semver(s: &str) -> bool {
    // Split off optional build metadata
    let (core, _build) = match s.split_once('+') {
        Some((c, b)) => (c, Some(b)),
        None => (s, None),
    };
    // Split off optional pre-release
    let (numeric, _pre) = match core.split_once('-') {
        Some((n, p)) => (n, Some(p)),
        None => (core, None),
    };
    // Validate MAJOR.MINOR.PATCH
    let parts: Vec<&str> = numeric.split('.').collect();
    if parts.len() != 3 {
        return false;
    }
    parts.iter().all(|p| {
        if p.is_empty() {
            return false;
        }
        // No leading zeros (except "0" itself)
        if p.len() > 1 && p.starts_with('0') {
            return false;
        }
        p.chars().all(|c| c.is_ascii_digit())
    })
}

/// Validate a capability id: must match `^[a-z0-9][a-z0-9._-]*$`.
fn is_valid_capability_id(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    let mut chars = s.chars();
    let first = chars.next().expect("non-empty checked above");
    if !first.is_ascii_lowercase() && !first.is_ascii_digit() {
        return false;
    }
    chars.all(|c| {
        c.is_ascii_lowercase() || c.is_ascii_digit() || c == '.' || c == '_' || c == '-'
    })
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_card() -> AgentCard {
        AgentCard {
            agent_id:     "01HZQK3P8EMXR9V7T5N2W4J6C0".into(),
            name:         "Test Agent".into(),
            version:      "1.0.0".into(),
            capabilities: vec![Capability {
                id:            "text.generate".into(),
                description:   "Generate text from a prompt.".into(),
                tags:          None,
                input_schema:  None,
                output_schema: None,
            }],
            endpoint: Endpoint {
                protocol:   Protocol::Http,
                url:        "https://example.com".into(),
                health_url: None,
                auth:       None,
            },
            pricing:  None,
            metadata: None,
        }
    }

    // ── Valid construction ─────────────────────────────────────────────────────

    #[test]
    fn minimal_card_is_valid() {
        assert!(minimal_card().validate().is_ok());
    }

    #[test]
    fn serde_roundtrip_preserves_data() {
        let card = minimal_card();
        let json = serde_json::to_string(&card).unwrap();
        let decoded: AgentCard = serde_json::from_str(&json).unwrap();
        assert_eq!(card, decoded);
    }

    // ── agent_id validation ────────────────────────────────────────────────────

    #[test]
    fn rejects_short_agent_id() {
        let mut card = minimal_card();
        card.agent_id = "SHORT".into();
        assert!(card.validate().is_err());
    }

    #[test]
    fn rejects_agent_id_with_invalid_chars() {
        let mut card = minimal_card();
        // 'I', 'L', 'O', 'U' are not in Crockford alphabet
        card.agent_id = "ILOUILOUILOUILOUILOUILOUI0".into();
        assert!(card.validate().is_err());
    }

    #[test]
    fn accepts_all_valid_crockford_chars() {
        let mut card = minimal_card();
        // Contains only valid Crockford chars in a 26-char string
        card.agent_id = "0123456789ABCDEFGHJKMNPQRS".into();
        assert!(card.validate().is_ok());
    }

    // ── version validation ─────────────────────────────────────────────────────

    #[test]
    fn accepts_valid_semver_variants() {
        for ver in &["0.0.1", "1.0.0", "2.3.4-alpha.1", "1.0.0+build.42", "1.0.0-rc.1+sha.abc"] {
            let mut card = minimal_card();
            card.version = (*ver).into();
            assert!(card.validate().is_ok(), "version {ver:?} should be valid");
        }
    }

    #[test]
    fn rejects_invalid_semver() {
        for ver in &["1.0", "1", "v1.0.0", "1.0.0.0", "1.01.0"] {
            let mut card = minimal_card();
            card.version = (*ver).into();
            assert!(card.validate().is_err(), "version {ver:?} should be rejected");
        }
    }

    // ── capabilities validation ────────────────────────────────────────────────

    #[test]
    fn rejects_empty_capabilities() {
        let mut card = minimal_card();
        card.capabilities.clear();
        assert!(card.validate().is_err());
    }

    #[test]
    fn rejects_capability_with_invalid_id() {
        let mut card = minimal_card();
        card.capabilities[0].id = "Text Generate".into(); // uppercase + space
        assert!(card.validate().is_err());
    }

    #[test]
    fn rejects_capability_id_starting_with_dash() {
        let mut card = minimal_card();
        card.capabilities[0].id = "-bad".into();
        assert!(card.validate().is_err());
    }

    #[test]
    fn accepts_capability_id_with_dots_and_dashes() {
        let mut card = minimal_card();
        card.capabilities[0].id = "text.gen-v2_fast".into();
        assert!(card.validate().is_ok());
    }

    // ── pricing validation ─────────────────────────────────────────────────────

    #[test]
    fn rejects_cost_below_landauer_floor() {
        let mut card = minimal_card();
        card.pricing = Some(PricingModel {
            base_cost_joules:    Some(1e-30), // below floor
            estimated_latency_ms: None,
            currency:            None,
            cost_per_request:    None,
        });
        let err = card.validate().unwrap_err();
        assert!(
            err.0.contains("Landauer"),
            "expected Landauer floor error, got: {err}"
        );
    }

    #[test]
    fn accepts_zero_joules() {
        // Zero = free tier / public agent, explicitly allowed
        let mut card = minimal_card();
        card.pricing = Some(PricingModel {
            base_cost_joules:    Some(0.0),
            estimated_latency_ms: None,
            currency:            None,
            cost_per_request:    None,
        });
        assert!(card.validate().is_ok());
    }

    #[test]
    fn accepts_cost_exactly_at_landauer_floor() {
        let mut card = minimal_card();
        card.pricing = Some(PricingModel {
            base_cost_joules:    Some(LANDAUER_FLOOR_JOULES),
            estimated_latency_ms: None,
            currency:            None,
            cost_per_request:    None,
        });
        assert!(card.validate().is_ok());
    }

    #[test]
    fn rejects_negative_cost() {
        let mut card = minimal_card();
        card.pricing = Some(PricingModel {
            base_cost_joules:    Some(-1e-20),
            estimated_latency_ms: None,
            currency:            None,
            cost_per_request:    None,
        });
        assert!(card.validate().is_err());
    }

    // ── endpoint validation ────────────────────────────────────────────────────

    #[test]
    fn rejects_empty_endpoint_url() {
        let mut card = minimal_card();
        card.endpoint.url = String::new();
        assert!(card.validate().is_err());
    }

    // ── protocol serde ─────────────────────────────────────────────────────────

    #[test]
    fn protocol_serializes_to_schema_values() {
        assert_eq!(
            serde_json::to_string(&Protocol::GoogleA2a).unwrap(),
            "\"google_a2a\""
        );
        // Schema specifies "websocket" (no underscore), not "web_socket"
        assert_eq!(
            serde_json::to_string(&Protocol::WebSocket).unwrap(),
            "\"websocket\""
        );
        assert_eq!(
            serde_json::to_string(&Protocol::Http).unwrap(),
            "\"http\""
        );
    }

    #[test]
    fn all_protocols_roundtrip() {
        let protos = [
            Protocol::Http,
            Protocol::WebSocket,
            Protocol::Sse,
            Protocol::Grpc,
            Protocol::Mcp,
            Protocol::GoogleA2a,
            Protocol::Native,
        ];
        for proto in &protos {
            let json = serde_json::to_string(proto).unwrap();
            let decoded: Protocol = serde_json::from_str(&json).unwrap();
            assert_eq!(proto, &decoded, "roundtrip failed for {proto:?}");
        }
    }

    // ── metadata ───────────────────────────────────────────────────────────────

    #[test]
    fn metadata_pacr_fields_serialize_with_colon_prefix() {
        let meta = Metadata {
            interaction_count: Some(42),
            reputation_score:  Some(0.95),
            ..Default::default()
        };
        let json = serde_json::to_string(&meta).unwrap();
        assert!(json.contains("pacr:interaction_count"), "{json}");
        assert!(json.contains("pacr:reputation_score"), "{json}");
    }
}
