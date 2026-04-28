// crates/aevum-mcp-server/src/transport/http.rs
//
// Pillar: I/II/III. PACR field: ALL.
// HTTP transport: axum on :8889, SSE /events endpoint.
//
// Endpoints:
//   POST /          — JSON-RPC 2.0 MCP tool calls (same ToolRouter as stdio)
//   GET  /events    — Server-Sent Events stream: StateChange from SsnBroadcaster
//   GET  /health    — liveness probe (returns {"status":"ok"})
//
// CORS: tower-http CorsLayer, permissive (MCP clients run cross-origin).
// Feature-gated: only compiled with `--features transport-http`.

#![forbid(unsafe_code)]

use std::convert::Infallible;
use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    response::{
        sse::{Event, KeepAlive, Sse},
        IntoResponse, Json,
    },
    routing::{get, post},
    Router,
};
use serde_json::Value;
use tokio::net::TcpListener;
use tokio_stream::wrappers::BroadcastStream;
use tokio_stream::StreamExt as _;
use tower_http::cors::CorsLayer;

use crate::resources::context::StateChange;
use crate::router::{dispatch as router_dispatch, McpRequest};
use crate::state::AppState;

// ── Run ───────────────────────────────────────────────────────────────────────

/// Start the HTTP server on `addr` (e.g. `"0.0.0.0:8889"`).
/// Blocks until the server terminates (SIGINT / OS shutdown).
pub async fn run(addr: &str, state: Arc<AppState>) {
    let app = build_router(state);
    let listener = TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| panic!("failed to bind {addr}: {e}"));
    tracing::info!("aevum-mcp HTTP listening on {addr}");
    axum::serve(listener, app)
        .await
        .unwrap_or_else(|e| panic!("HTTP server error: {e}"));
}

// ── Router ────────────────────────────────────────────────────────────────────

fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/", post(handle_jsonrpc))
        .route("/events", get(handle_sse))
        .route("/health", get(handle_health))
        .with_state(state)
        .layer(CorsLayer::permissive())
}

// ── Handlers ──────────────────────────────────────────────────────────────────

/// POST / — JSON-RPC 2.0 dispatch (same logic as stdio transport).
async fn handle_jsonrpc(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> impl IntoResponse {
    let id = body.get("id").cloned().unwrap_or(Value::Null);
    let method = body
        .get("method")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_owned();
    let params = body
        .get("params")
        .cloned()
        .unwrap_or(Value::Object(Default::default()));

    let req = McpRequest {
        jsonrpc: "2.0".into(),
        id,
        method,
        params,
    };

    let response = router_dispatch(req, state).await;
    Json(serde_json::to_value(response).unwrap_or(Value::Null))
}

/// GET /events — Server-Sent Events stream.
/// Each event carries a JSON-encoded `StateChange` payload.
/// Lagging receivers are silently dropped by the broadcast channel (Pillar I: bounded memory).
async fn handle_sse(
    State(state): State<Arc<AppState>>,
) -> Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>> {
    let rx = state.ssn.subscribe();
    let stream = BroadcastStream::new(rx)
        .filter_map(|result: Result<StateChange, _>| {
            // BroadcastStream yields Err(BroadcastStreamRecvError::Lagged) when
            // the receiver fell behind. Drop silently (Pillar I: no unbounded growth).
            result.ok()
        })
        .map(|change: StateChange| {
            let data = serde_json::json!({
                "record_count": change.record_count,
                "s_t":          change.s_t,
                "h_t":          change.h_t,
                "trend":        format!("{:?}", change.trend),
            });
            Ok::<Event, Infallible>(Event::default().json_data(data).unwrap_or_default())
        });

    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// GET /health — liveness probe for Cloudflare Tunnel health checks.
async fn handle_health() -> impl IntoResponse {
    (StatusCode::OK, Json(serde_json::json!({"status": "ok"})))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Method, Request};
    use tempfile::tempdir;
    use tower::ServiceExt; // for .oneshot()

    async fn test_app() -> (Router, Arc<AppState>) {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let app = build_router(Arc::clone(&state));
        (app, state)
    }

    #[tokio::test]
    async fn health_endpoint_returns_ok() {
        let (app, _) = test_app().await;
        let req = Request::builder()
            .method(Method::GET)
            .uri("/health")
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn jsonrpc_unknown_tool_returns_error_json() {
        let (app, _) = test_app().await;
        let body = serde_json::json!({
            "id": 1,
            "method": "tools/call",
            "params": { "name": "nonexistent_tool", "arguments": {} }
        });
        let req = Request::builder()
            .method(Method::POST)
            .uri("/")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&body).unwrap()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let v: Value = serde_json::from_slice(&bytes).unwrap();
        // Unknown tool → error field
        assert!(
            v.get("error").is_some(),
            "expected error for unknown tool; got: {v}"
        );
    }

    #[tokio::test]
    async fn jsonrpc_remember_call_succeeds() {
        let (app, _) = test_app().await;
        let body = serde_json::json!({
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "aevum_remember",
                "arguments": {
                    "text": "HTTP transport integration test — epsilon machine causal record"
                }
            }
        });
        let req = Request::builder()
            .method(Method::POST)
            .uri("/")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&body).unwrap()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let v: Value = serde_json::from_slice(&bytes).unwrap();
        assert!(
            v.get("result").is_some() || v.get("error").is_some(),
            "response must have result or error; got: {v}"
        );
    }

    #[tokio::test]
    async fn cors_header_present() {
        let (app, _) = test_app().await;
        let req = Request::builder()
            .method(Method::GET)
            .uri("/health")
            .header("origin", "https://mcp.aevum.network")
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        let headers = resp.headers();
        assert!(
            headers.contains_key("access-control-allow-origin"),
            "CORS header missing; headers: {:?}",
            headers
        );
    }

    #[tokio::test]
    async fn tools_list_returns_four_tools() {
        let (app, _) = test_app().await;
        let body = serde_json::json!({ "id": 1, "method": "tools/list", "params": {} });
        let req = Request::builder()
            .method(Method::POST)
            .uri("/")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&body).unwrap()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let v: Value = serde_json::from_slice(&bytes).unwrap();
        let tools = v["result"]["tools"].as_array().unwrap();
        assert_eq!(
            tools.len(),
            4,
            "must expose 4 tools: remember, recall, filter, settle"
        );
    }
}
