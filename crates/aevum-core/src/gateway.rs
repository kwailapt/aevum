//! HTTP gateway: OpenAI-compatible `/v1/chat/completions`.
//!
//! Each request:
//! 1. Parses `node_id` from `Authorization: Bearer <u64>`.
//! 2. Reads `X-Aevum-Mode` to select a `TrilemmaMode` (energy / time / space).
//! 3. Computes `cost = API_BASE_COST × mode.chi_multiplier()`.
//! 4. Deducts `cost` χ-Quanta from the sharded ledger (CAS, lock-free).
//! 5. Forwards to Aliyun DashScope; refunds on upstream failure.
//! 6. Returns JSON with `x_quanta_balance` and `x_ness_sigma` appended.

use crate::ledger::{ShardedLedger, INSUFFICIENT};
use crate::thermodynamics::TrilemmaMode;
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use reqwest::Client;
use serde_json::Value;
use std::sync::Arc;

const ALIYUN_URL: &str =
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions";

/// Base χ cost per API call.  10× above the Landauer floor (LANDAUER_CHI = 1),
/// leaving room for the trilemma multiplier without breaching the second law.
const API_BASE_COST: u64 = 10;

#[derive(Clone)]
pub struct GatewayState {
    pub client:  Client,
    pub ledger:  Arc<ShardedLedger>,
    pub api_key: String,
}

pub async fn handle_completions(
    State(state): State<GatewayState>,
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    // ── 1. Parse node_id ──────────────────────────────────────────────────────
    let node_id: u64 = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .unwrap_or("")
        .trim_start_matches("Bearer ")
        .parse()
        .unwrap_or(0);

    // ── 2. Trilemma mode → cost ───────────────────────────────────────────────
    let mode = headers
        .get("X-Aevum-Mode")
        .and_then(|h| h.to_str().ok())
        .map(TrilemmaMode::from_header)
        .unwrap_or_default();

    let cost = API_BASE_COST * mode.chi_multiplier();

    // ── 3. Deduct (CAS, lock-free) ────────────────────────────────────────────
    let balance = state.ledger.deduct(node_id, cost, mode);
    if balance == INSUFFICIENT {
        return (StatusCode::PAYMENT_REQUIRED, "Insufficient χ-Quanta").into_response();
    }

    // ── 4. Forward to upstream ────────────────────────────────────────────────
    let body = serde_json::json!({
        "model":    payload.get("model").and_then(|v| v.as_str()).unwrap_or("qwen-plus"),
        "messages": payload.get("messages").cloned().unwrap_or(serde_json::json!([])),
        "stream":   false,
    });

    match state.client
        .post(ALIYUN_URL)
        .header("Authorization", format!("Bearer {}", state.api_key))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r) => {
            let mut data: Value = r.json().await.unwrap_or_default();
            if let Some(obj) = data.as_object_mut() {
                // ── 5. Append thermodynamic telemetry ─────────────────────────
                obj.insert("x_quanta_balance".into(), serde_json::json!(balance));
                obj.insert("x_quanta_cost".into(),    serde_json::json!(cost));
                obj.insert("x_trilemma_mode".into(),  serde_json::json!(format!("{mode:?}")));
                let sigma = state.ledger.ness().sigma();
                obj.insert("x_ness_sigma".into(),     serde_json::json!(sigma));
            }
            (StatusCode::OK, Json(data)).into_response()
        }
        Err(_) => {
            // Refund on upstream failure — operation was reversible at this point.
            state.ledger.mint(node_id, cost);
            (StatusCode::BAD_GATEWAY, "Upstream routing failed").into_response()
        }
    }
}
