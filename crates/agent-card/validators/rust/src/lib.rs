//! AgentCard v1.0 lightweight validator.
//!
//! Pure data validation — no network calls, no execution logic.
//! Validates the structural invariants of an AgentCard JSON document:
//!
//! - Required top-level fields are present
//! - `agent_id` is a valid Crockford Base32 ULID (26 characters)
//! - `version` follows semver 2.0 (MAJOR.MINOR.PATCH[‑pre][+build])
//! - `capabilities` is non-empty and each capability has `id` and `description`
//! - Capability `id` is dot-namespaced machine-readable (lowercase, dots, dashes, digits)
//! - `endpoint.protocol` is a known value
//! - `endpoint.url` is non-empty
//! - `pricing.base_cost_joules`, if set, is ≥ the Landauer floor at 300 K
//!
//! # Usage
//!
//! ```rust
//! let json = r#"{"agent_id":"01HZQK3P8EMXR9V7T5N2W4J6C0","name":"Test","version":"1.0.0","capabilities":[{"id":"text.generate","description":"Generate text"}],"endpoint":{"protocol":"http","url":"https://example.com"}}"#;
//! let errors = agentcard_validator::validate(json);
//! assert!(errors.is_empty(), "expected no errors, got: {:?}", errors);
//! ```

#![forbid(unsafe_code)]

use serde_json::Value;

/// Landauer floor: k_B × 300 K × ln(2) in Joules.
/// Any `base_cost_joules` below this value is physically implausible.
pub const LANDAUER_FLOOR_JOULES: f64 = 2.854e-21;

/// Known protocol values accepted by the schema.
const KNOWN_PROTOCOLS: &[&str] = &[
    "http", "websocket", "sse", "grpc", "mcp", "google_a2a", "native",
];

/// Known auth scheme values.
const KNOWN_AUTH_SCHEMES: &[&str] = &["none", "bearer", "api_key", "oauth2", "mtls"];

// ─── Public API ──────────────────────────────────────────────────────────────

/// Validate an AgentCard JSON string.
///
/// Returns a `Vec<String>` of human-readable error messages.
/// An empty Vec means the document is valid.
///
/// # Errors
///
/// Returns a parse error message if `json` is not valid JSON at all.
pub fn validate(json: &str) -> Vec<String> {
    let value: Value = match serde_json::from_str(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("JSON parse error: {e}")],
    };
    validate_value(&value)
}

/// Validate a parsed `serde_json::Value` as an AgentCard.
///
/// Prefer [`validate`] when starting from a raw JSON string.
pub fn validate_value(card: &Value) -> Vec<String> {
    let mut errors = Vec::new();

    let obj = match card.as_object() {
        Some(o) => o,
        None => {
            errors.push("AgentCard must be a JSON object".into());
            return errors;
        }
    };

    // ── Required top-level fields ──
    validate_agent_id(obj.get("agent_id"), &mut errors);
    require_nonempty_string(obj.get("name"), "name", 128, &mut errors);
    validate_semver(obj.get("version"), &mut errors);
    validate_capabilities(obj.get("capabilities"), &mut errors);
    validate_endpoint(obj.get("endpoint"), &mut errors);

    // ── Optional fields ──
    if let Some(pricing) = obj.get("pricing") {
        if !pricing.is_null() {
            validate_pricing(pricing, &mut errors);
        }
    }

    errors
}

// ─── Field validators ─────────────────────────────────────────────────────────

fn validate_agent_id(value: Option<&Value>, errors: &mut Vec<String>) {
    match value {
        None => errors.push("Missing required field: agent_id".into()),
        Some(Value::String(s)) => {
            if !is_valid_ulid(s) {
                errors.push(format!(
                    "agent_id must be a 26-character Crockford Base32 ULID, got: {s:?}"
                ));
            }
        }
        Some(other) => errors.push(format!(
            "agent_id must be a string, got: {}",
            type_name(other)
        )),
    }
}

fn validate_semver(value: Option<&Value>, errors: &mut Vec<String>) {
    match value {
        None => errors.push("Missing required field: version".into()),
        Some(Value::String(s)) => {
            if !is_valid_semver(s) {
                errors.push(format!(
                    "version must be semver 2.0 (e.g. \"1.0.0\"), got: {s:?}"
                ));
            }
        }
        Some(other) => errors.push(format!(
            "version must be a string, got: {}",
            type_name(other)
        )),
    }
}

fn validate_capabilities(value: Option<&Value>, errors: &mut Vec<String>) {
    match value {
        None => {
            errors.push("Missing required field: capabilities".into());
        }
        Some(Value::Array(arr)) => {
            if arr.is_empty() {
                errors.push("capabilities must contain at least one item".into());
            }
            for (i, cap) in arr.iter().enumerate() {
                validate_capability(i, cap, errors);
            }
        }
        Some(other) => errors.push(format!(
            "capabilities must be an array, got: {}",
            type_name(other)
        )),
    }
}

fn validate_capability(index: usize, cap: &Value, errors: &mut Vec<String>) {
    let prefix = format!("capabilities[{index}]");
    let obj = match cap.as_object() {
        Some(o) => o,
        None => {
            errors.push(format!("{prefix}: must be an object"));
            return;
        }
    };

    // id — required, machine-readable
    match obj.get("id") {
        None => errors.push(format!("{prefix}.id: missing required field")),
        Some(Value::String(s)) => {
            if s.is_empty() {
                errors.push(format!("{prefix}.id: must not be empty"));
            } else if !is_valid_capability_id(s) {
                errors.push(format!(
                    "{prefix}.id: must be lowercase dot-namespaced (a-z0-9._-), got: {s:?}"
                ));
            }
            if s.len() > 128 {
                errors.push(format!("{prefix}.id: max 128 characters"));
            }
        }
        Some(other) => errors.push(format!(
            "{prefix}.id: must be a string, got: {}",
            type_name(other)
        )),
    }

    // description — required, non-empty
    require_nonempty_string(
        obj.get("description"),
        &format!("{prefix}.description"),
        512,
        errors,
    );
}

fn validate_endpoint(value: Option<&Value>, errors: &mut Vec<String>) {
    match value {
        None => {
            errors.push("Missing required field: endpoint".into());
        }
        Some(obj_val) => {
            let obj = match obj_val.as_object() {
                Some(o) => o,
                None => {
                    errors.push(format!(
                        "endpoint must be an object, got: {}",
                        type_name(obj_val)
                    ));
                    return;
                }
            };

            // protocol
            match obj.get("protocol") {
                None => errors.push("endpoint.protocol: missing required field".into()),
                Some(Value::String(s)) => {
                    if !KNOWN_PROTOCOLS.contains(&s.as_str()) {
                        errors.push(format!(
                            "endpoint.protocol: unknown value {s:?}; expected one of: {}",
                            KNOWN_PROTOCOLS.join(", ")
                        ));
                    }
                }
                Some(other) => errors.push(format!(
                    "endpoint.protocol: must be a string, got: {}",
                    type_name(other)
                )),
            }

            // url
            match obj.get("url") {
                None => errors.push("endpoint.url: missing required field".into()),
                Some(Value::String(s)) => {
                    if s.is_empty() {
                        errors.push("endpoint.url: must not be empty".into());
                    }
                }
                Some(other) => errors.push(format!(
                    "endpoint.url: must be a string, got: {}",
                    type_name(other)
                )),
            }

            // auth (optional but validated if present)
            if let Some(auth) = obj.get("auth") {
                if !auth.is_null() {
                    validate_auth(auth, errors);
                }
            }
        }
    }
}

fn validate_auth(auth: &Value, errors: &mut Vec<String>) {
    let obj = match auth.as_object() {
        Some(o) => o,
        None => {
            errors.push(format!(
                "endpoint.auth: must be an object or null, got: {}",
                type_name(auth)
            ));
            return;
        }
    };
    match obj.get("scheme") {
        None => errors.push("endpoint.auth.scheme: missing required field".into()),
        Some(Value::String(s)) => {
            if !KNOWN_AUTH_SCHEMES.contains(&s.as_str()) {
                errors.push(format!(
                    "endpoint.auth.scheme: unknown value {s:?}; expected one of: {}",
                    KNOWN_AUTH_SCHEMES.join(", ")
                ));
            }
        }
        Some(other) => errors.push(format!(
            "endpoint.auth.scheme: must be a string, got: {}",
            type_name(other)
        )),
    }
}

fn validate_pricing(pricing: &Value, errors: &mut Vec<String>) {
    let obj = match pricing.as_object() {
        Some(o) => o,
        None => {
            errors.push(format!(
                "pricing: must be an object or null, got: {}",
                type_name(pricing)
            ));
            return;
        }
    };

    if let Some(cost) = obj.get("base_cost_joules") {
        if !cost.is_null() {
            match cost.as_f64() {
                Some(j) if j < 0.0 => {
                    errors.push("pricing.base_cost_joules: must be >= 0".into());
                }
                Some(j) if j > 0.0 && j < LANDAUER_FLOOR_JOULES => {
                    errors.push(format!(
                        "pricing.base_cost_joules: {j:.3e} J is below the Landauer floor \
                         at 300 K ({LANDAUER_FLOOR_JOULES:.3e} J) — physically implausible"
                    ));
                }
                None => {
                    errors.push("pricing.base_cost_joules: must be a number or null".into());
                }
                _ => {}
            }
        }
    }

    if let Some(latency) = obj.get("estimated_latency_ms") {
        if !latency.is_null() {
            if latency.as_f64().map(|v| v < 0.0).unwrap_or(false) {
                errors.push("pricing.estimated_latency_ms: must be >= 0".into());
            }
        }
    }

    if let Some(cost_per) = obj.get("cost_per_request") {
        if !cost_per.is_null() {
            if cost_per.as_f64().map(|v| v < 0.0).unwrap_or(false) {
                errors.push("pricing.cost_per_request: must be >= 0".into());
            }
        }
    }
}

// ─── Helper validators ────────────────────────────────────────────────────────

fn require_nonempty_string(value: Option<&Value>, field: &str, max_len: usize, errors: &mut Vec<String>) {
    match value {
        None => errors.push(format!("Missing required field: {field}")),
        Some(Value::String(s)) => {
            if s.is_empty() {
                errors.push(format!("{field}: must not be empty"));
            }
            if s.len() > max_len {
                errors.push(format!("{field}: max {max_len} characters"));
            }
        }
        Some(other) => errors.push(format!(
            "{field}: must be a string, got: {}",
            type_name(other)
        )),
    }
}

// ─── Format checkers ──────────────────────────────────────────────────────────

/// Validate a Crockford Base32-encoded ULID: exactly 26 characters from the
/// Crockford alphabet (0-9, A-H, J, K, M, N, P-T, V-Z — no I, L, O, U).
fn is_valid_ulid(s: &str) -> bool {
    if s.len() != 26 {
        return false;
    }
    s.chars().all(|c| matches!(c,
        '0'..='9' | 'A'..='H' | 'J' | 'K' | 'M' | 'N' | 'P'..='T' | 'V'..='Z'
    ))
}

/// Validate a semver 2.0 string: MAJOR.MINOR.PATCH with optional pre-release and build.
/// Accepts: "1.0.0", "0.3.2-beta.1", "1.0.0+build.42".
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

/// Validate a capability id: lowercase letters, digits, dots, underscores, and dashes.
/// Must start with a letter or digit.
fn is_valid_capability_id(s: &str) -> bool {
    let mut chars = s.chars();
    match chars.next() {
        None => return false,
        Some(c) => {
            if !c.is_ascii_lowercase() && !c.is_ascii_digit() {
                return false;
            }
        }
    }
    chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '.' || c == '_' || c == '-')
}

fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "boolean",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_card() -> &'static str {
        r#"{
            "agent_id": "01HZQK3P8EMXR9V7T5N2W4J6C0",
            "name": "Test Agent",
            "version": "1.0.0",
            "capabilities": [
                {"id": "text.generate", "description": "Generate text"}
            ],
            "endpoint": {"protocol": "http", "url": "https://example.com"}
        }"#
    }

    #[test]
    fn minimal_valid_card_passes() {
        let errors = validate(minimal_card());
        assert!(errors.is_empty(), "unexpected errors: {errors:?}");
    }

    #[test]
    fn missing_required_fields_detected() {
        let errors = validate("{}");
        let joined = errors.join("\n");
        assert!(joined.contains("agent_id"), "expected agent_id error");
        assert!(joined.contains("name"), "expected name error");
        assert!(joined.contains("version"), "expected version error");
        assert!(joined.contains("capabilities"), "expected capabilities error");
        assert!(joined.contains("endpoint"), "expected endpoint error");
    }

    #[test]
    fn invalid_ulid_rejected() {
        let json = minimal_card().replace("01HZQK3P8EMXR9V7T5N2W4J6C0", "not-a-ulid");
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("agent_id")), "{errors:?}");
    }

    #[test]
    fn ulid_with_invalid_chars_rejected() {
        // 'I', 'L', 'O', 'U' are not in the Crockford alphabet
        let json = minimal_card().replace("01HZQK3P8EMXR9V7T5N2W4J6C0", "ILOUILOUILOUILOUILOUILOUI0");
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("agent_id")), "{errors:?}");
    }

    #[test]
    fn valid_semver_variants_accepted() {
        for ver in &["0.0.1", "1.0.0", "2.3.4-alpha.1", "1.0.0+build.42", "1.0.0-rc.1+sha.abc"] {
            let json = minimal_card().replace("\"1.0.0\"", &format!("\"{ver}\""));
            let errors = validate(&json);
            let ver_errors: Vec<_> = errors.iter().filter(|e| e.contains("version")).collect();
            assert!(ver_errors.is_empty(), "version {ver:?} should be valid, got: {ver_errors:?}");
        }
    }

    #[test]
    fn invalid_semver_rejected() {
        for ver in &["1.0", "1", "v1.0.0", "1.0.0.0", "1.01.0"] {
            let json = minimal_card().replace("\"1.0.0\"", &format!("\"{ver}\""));
            let errors = validate(&json);
            assert!(
                errors.iter().any(|e| e.contains("version")),
                "version {ver:?} should be rejected, got: {errors:?}"
            );
        }
    }

    #[test]
    fn empty_capabilities_rejected() {
        let json = minimal_card().replace(
            r#""capabilities": [
                {"id": "text.generate", "description": "Generate text"}
            ]"#,
            r#""capabilities": []"#,
        );
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("capabilities")), "{errors:?}");
    }

    #[test]
    fn capability_missing_id_rejected() {
        let json = minimal_card().replace(
            r#"{"id": "text.generate", "description": "Generate text"}"#,
            r#"{"description": "Generate text"}"#,
        );
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("capabilities[0].id")), "{errors:?}");
    }

    #[test]
    fn capability_invalid_id_rejected() {
        let json = minimal_card().replace("text.generate", "Text Generate");
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("capabilities[0].id")), "{errors:?}");
    }

    #[test]
    fn unknown_protocol_rejected() {
        let json = minimal_card().replace("\"http\"", "\"ftp\"");
        let errors = validate(&json);
        assert!(errors.iter().any(|e| e.contains("endpoint.protocol")), "{errors:?}");
    }

    #[test]
    fn all_known_protocols_accepted() {
        for proto in &["http", "websocket", "sse", "grpc", "mcp", "google_a2a", "native"] {
            let json = minimal_card().replace("\"http\"", &format!("\"{proto}\""));
            let errors = validate(&json);
            let proto_errors: Vec<_> = errors.iter().filter(|e| e.contains("endpoint.protocol")).collect();
            assert!(proto_errors.is_empty(), "protocol {proto:?} should be valid, got: {proto_errors:?}");
        }
    }

    #[test]
    fn below_landauer_floor_rejected() {
        let json = format!(
            r#"{{"agent_id":"01HZQK3P8EMXR9V7T5N2W4J6C0","name":"T","version":"1.0.0",
            "capabilities":[{{"id":"x.y","description":"d"}}],
            "endpoint":{{"protocol":"http","url":"https://x.com"}},
            "pricing":{{"base_cost_joules":1e-30}}}}"#
        );
        let errors = validate(&json);
        assert!(
            errors.iter().any(|e| e.contains("Landauer")),
            "expected Landauer floor error, got: {errors:?}"
        );
    }

    #[test]
    fn zero_joules_accepted() {
        // zero = free tier / public agent, explicitly allowed
        let json = format!(
            r#"{{"agent_id":"01HZQK3P8EMXR9V7T5N2W4J6C0","name":"T","version":"1.0.0",
            "capabilities":[{{"id":"x.y","description":"d"}}],
            "endpoint":{{"protocol":"http","url":"https://x.com"}},
            "pricing":{{"base_cost_joules":0.0}}}}"#
        );
        let errors = validate(&json);
        assert!(errors.is_empty(), "zero joules should be valid: {errors:?}");
    }

    #[test]
    fn invalid_json_returns_error() {
        let errors = validate("{not json}");
        assert!(!errors.is_empty());
        assert!(errors[0].contains("JSON parse error"));
    }

    #[test]
    fn full_example_cards_valid() {
        // Validate the shipped example cards from this repository.
        // These paths are relative to the workspace root during `cargo test`.
        let examples = [
            "../../examples/llm-agent.json",
            "../../examples/code-review-agent.json",
            "../../examples/data-pipeline-agent.json",
        ];
        for path in &examples {
            if let Ok(content) = std::fs::read_to_string(path) {
                let errors = validate(&content);
                assert!(
                    errors.is_empty(),
                    "example {path} failed validation: {errors:?}"
                );
            }
            // If the file does not exist (e.g. running tests in isolation), skip silently.
        }
    }
}
