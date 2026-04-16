// crates/aevum-mcp-server/src/tools/settle.rs
//
// Pillar: II. PACR field: Λ/Ω.
// aevum_settle: records a Paperclip agent interaction into the CsoIndex,
// updating the source agent's ρ (causal return rate) and reputation score.
//
// Pipeline:
//   1. Parse source_agent_id, target_agent_id (32 hex chars → CausalId)
//   2. Validate lambda_joules > 0 (Pillar II: Λ ≥ 0 strictly)
//   3. CsoIndex::record_interaction(source, target, lambda, phi_before, phi_after)
//      → ρ = (phi_after − phi_before) / lambda_joules
//   4. Return { source_agent_id, target_agent_id, rho, landauer_cost_joules, reputation_score }

use std::sync::Arc;

use aevum_core::cso::AgentId;
use pacr_types::CausalId;
use serde_json::Value;

use crate::router::McpResponse;
use crate::state::AppState;

/// Parse a hex string (up to 32 hex chars) into a `CausalId`/`AgentId`.
/// Accepts strings with or without a leading "0x".
fn parse_agent_id(s: &str) -> Result<AgentId, String> {
    u128::from_str_radix(s.trim_start_matches("0x"), 16)
        .map(CausalId)
        .map_err(|e| format!("invalid agent id '{s}': {e}"))
}

pub async fn handle(id: Value, args: Value, state: Arc<AppState>) -> McpResponse {
    // ── 1. Parse arguments ────────────────────────────────────────────────────
    let source_str = match args.get("source_agent_id").and_then(|v| v.as_str()) {
        Some(s) => s.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: source_agent_id"),
    };
    let target_str = match args.get("target_agent_id").and_then(|v| v.as_str()) {
        Some(t) => t.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: target_agent_id"),
    };
    let lambda_joules = match args.get("lambda_joules").and_then(|v| v.as_f64()) {
        Some(l) => l,
        None => return McpResponse::err(id, -32602, "missing required argument: lambda_joules"),
    };
    let phi_before = match args.get("phi_before").and_then(|v| v.as_f64()) {
        Some(p) => p,
        None => return McpResponse::err(id, -32602, "missing required argument: phi_before"),
    };
    let phi_after = match args.get("phi_after").and_then(|v| v.as_f64()) {
        Some(p) => p,
        None => return McpResponse::err(id, -32602, "missing required argument: phi_after"),
    };

    // ── 2. Validate Landauer cost (Pillar II: energy dissipation > 0) ─────────
    if lambda_joules <= 0.0 {
        return McpResponse::err(
            id,
            -32602,
            "lambda_joules must be > 0 (Pillar II: energy cost cannot be zero or negative)",
        );
    }

    // ── 3. Parse agent IDs ────────────────────────────────────────────────────
    let source = match parse_agent_id(&source_str) {
        Ok(a) => a,
        Err(e) => return McpResponse::err(id, -32602, e),
    };
    let target = match parse_agent_id(&target_str) {
        Ok(a) => a,
        Err(e) => return McpResponse::err(id, -32602, e),
    };

    // ── 4. Record in CsoIndex (lock-free DashMap) ─────────────────────────────
    // ρ = (phi_after − phi_before) / lambda_joules
    // Updates source agent's EMA and success/failure counters atomically.
    state
        .cso
        .record_interaction(source, target, lambda_joules, phi_before, phi_after);

    // ── 5. Read back updated metrics ──────────────────────────────────────────
    let rho = state.cso.get_rho(&source);
    let reputation = state.cso.reputation_score(&source);

    McpResponse::ok(
        id,
        serde_json::json!({
            "source_agent_id":    source_str,
            "target_agent_id":    target_str,
            "rho":                rho,
            "landauer_cost_joules": lambda_joules,
            "reputation_score":   reputation
        }),
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn agent_hex(n: u128) -> String {
        format!("{n:032x}")
    }

    #[tokio::test]
    async fn settle_missing_source_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(Value::Number(1.into()), serde_json::json!({}), state).await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn settle_missing_target_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "source_agent_id": agent_hex(1) }),
            state,
        )
        .await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn settle_zero_lambda_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": agent_hex(1),
                "target_agent_id": agent_hex(2),
                "lambda_joules": 0.0,
                "phi_before": 0.0,
                "phi_after": 1.0
            }),
            state,
        )
        .await;
        assert!(
            resp.error.is_some(),
            "zero lambda must be rejected (Pillar II)"
        );
    }

    #[tokio::test]
    async fn settle_negative_lambda_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": agent_hex(1),
                "target_agent_id": agent_hex(2),
                "lambda_joules": -1e-20,
                "phi_before": 0.0,
                "phi_after": 1.0
            }),
            state,
        )
        .await;
        assert!(
            resp.error.is_some(),
            "negative lambda must be rejected (Pillar II)"
        );
    }

    #[tokio::test]
    async fn settle_valid_interaction_returns_ok() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": agent_hex(42),
                "target_agent_id": agent_hex(99),
                "lambda_joules":   1e-20,
                "phi_before":      0.0,
                "phi_after":       1.0
            }),
            Arc::clone(&state),
        )
        .await;
        assert!(resp.error.is_none(), "unexpected error: {:?}", resp.error);
        let r = resp.result.unwrap();
        assert!(r["rho"].is_number());
        assert!(r["reputation_score"].is_number());
        assert_eq!(r["landauer_cost_joules"].as_f64().unwrap(), 1e-20);
    }

    #[tokio::test]
    async fn settle_response_has_required_fields() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": agent_hex(1),
                "target_agent_id": agent_hex(2),
                "lambda_joules":   2.87e-21,
                "phi_before":      0.5,
                "phi_after":       0.8
            }),
            state,
        )
        .await;
        let r = resp.result.unwrap();
        assert!(
            r.get("source_agent_id").is_some(),
            "must have source_agent_id"
        );
        assert!(r.get("rho").is_some(), "must have rho");
        assert!(
            r.get("landauer_cost_joules").is_some(),
            "must have landauer_cost_joules"
        );
        assert!(
            r.get("reputation_score").is_some(),
            "must have reputation_score"
        );
    }

    #[tokio::test]
    async fn settle_invalid_agent_id_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": "not-a-hex-id",
                "target_agent_id": agent_hex(2),
                "lambda_joules":   1e-20,
                "phi_before":      0.0,
                "phi_after":       1.0
            }),
            state,
        )
        .await;
        assert!(resp.error.is_some(), "invalid agent ID must return error");
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn settle_reputation_increases_with_positive_interactions() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        let args = serde_json::json!({
            "source_agent_id": agent_hex(7),
            "target_agent_id": agent_hex(8),
            "lambda_joules":   1e-20,
            "phi_before":      0.0,
            "phi_after":       1.0
        });

        // 50 positive interactions → ρ EMA should converge above 0.5
        let mut last_rep = 0.0_f64;
        for i in 0..50_i64 {
            let resp = handle(Value::Number(i.into()), args.clone(), Arc::clone(&state)).await;
            last_rep = resp.result.unwrap()["reputation_score"].as_f64().unwrap();
        }
        assert!(
            last_rep > 0.5,
            "reputation should be > 0.5 after 50 positive interactions, got {last_rep}"
        );
    }

    #[tokio::test]
    async fn settle_rho_reflects_phi_ratio() {
        // Single interaction: phi_after=1.0, phi_before=0.0, lambda=1.0 → ρ_raw=1.0
        // After one update: rho_ema = α×1.0 + (1-α)×0.0 = 0.1
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({
                "source_agent_id": agent_hex(100),
                "target_agent_id": agent_hex(200),
                "lambda_joules":   1.0,
                "phi_before":      0.0,
                "phi_after":       1.0
            }),
            state,
        )
        .await;
        let r = resp.result.unwrap();
        let rho: f64 = r["rho"].as_f64().unwrap();
        // EMA after one step with α=0.1: 0.1*1.0 + 0.9*0.0 = 0.1
        assert!(
            (rho - 0.1).abs() < 1e-9,
            "single positive interaction → rho_ema ≈ 0.1, got {rho}"
        );
    }
}
