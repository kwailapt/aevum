// crates/aevum-mcp-server/src/router.rs
//
// Pillar: I. PACR field: ι/Π.
// ToolRouter: dispatches MCP JSON-RPC tool calls to handler functions.

#![forbid(unsafe_code)]

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::state::AppState;

/// A single MCP JSON-RPC request.
#[derive(Debug, Deserialize)]
pub struct McpRequest {
    #[allow(dead_code)] // validated by transport layer; router uses method/params
    pub jsonrpc: String,
    pub id: Value,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

/// A single MCP JSON-RPC response.
#[derive(Debug, Serialize)]
pub struct McpResponse {
    pub jsonrpc: String,
    pub id: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<McpError>,
}

#[derive(Debug, Serialize)]
pub struct McpError {
    pub code: i32,
    pub message: String,
}

impl McpResponse {
    pub fn ok(id: Value, result: Value) -> Self {
        Self { jsonrpc: "2.0".into(), id, result: Some(result), error: None }
    }

    pub fn err(id: Value, code: i32, message: impl Into<String>) -> Self {
        Self {
            jsonrpc: "2.0".into(),
            id,
            result: None,
            error: Some(McpError { code, message: message.into() }),
        }
    }
}

/// Route an incoming MCP request to the appropriate tool handler.
pub async fn dispatch(req: McpRequest, state: Arc<AppState>) -> McpResponse {
    match req.method.as_str() {
        "tools/call" => dispatch_tool_call(req, state).await,
        "tools/list" => tools_list(req.id),
        "initialize" => initialize(req.id),
        _ => McpResponse::err(req.id, -32601, format!("method not found: {}", req.method)),
    }
}

async fn dispatch_tool_call(req: McpRequest, state: Arc<AppState>) -> McpResponse {
    let tool_name = req.params.get("name").and_then(|v| v.as_str()).unwrap_or("");
    let args = req.params.get("arguments").cloned().unwrap_or(Value::Null);

    match tool_name {
        "aevum_remember" => crate::tools::remember::handle(req.id, args, state).await,
        "aevum_recall"   => crate::tools::recall::handle(req.id, args, state).await,
        "aevum_filter"   => crate::tools::filter::handle(req.id, args, Arc::clone(&state)).await,
        "aevum_settle"   => crate::tools::settle::handle(req.id, args, state).await,
        _ => McpResponse::err(req.id, -32602, format!("unknown tool: {tool_name}")),
    }
}

fn tools_list(id: Value) -> McpResponse {
    let tools = serde_json::json!([
        {
            "name": "aevum_remember",
            "description": "Store a causal memory record. Runs ε-engine CSSR on the input, extracts S_T/H_T, and appends a PACR record to the causal DAG.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": { "type": "string", "description": "The content to remember." }
                },
                "required": ["text"]
            }
        },
        {
            "name": "aevum_recall",
            "description": "Retrieve causally relevant memories for a query. Uses ρ-weighted S_T similarity search over the causal DAG.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "The query to match against stored memories." },
                    "top_k": { "type": "integer", "description": "Maximum number of results (default 5)." },
                    "tolerance": { "type": "number", "description": "S_T search radius (default 1.0 bits)." }
                },
                "required": ["query"]
            }
        },
        {
            "name": "aevum_filter",
            "description": "Distil a high-entropy MCP response to its causal structure (S_T). Removes H_T noise before passing to Claude.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": { "type": "string", "description": "Raw MCP response content to filter." }
                },
                "required": ["content"]
            }
        },
        {
            "name": "aevum_settle",
            "description": "Record a Paperclip agent interaction and update its ρ causal return rate in the CSO reputation index.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_agent_id": { "type": "string" },
                    "target_agent_id": { "type": "string" },
                    "lambda_joules":   { "type": "number" },
                    "phi_before":      { "type": "number" },
                    "phi_after":       { "type": "number" }
                },
                "required": ["source_agent_id", "target_agent_id", "lambda_joules", "phi_before", "phi_after"]
            }
        }
    ]);
    McpResponse::ok(id, serde_json::json!({ "tools": tools }))
}

fn initialize(id: Value) -> McpResponse {
    McpResponse::ok(id, serde_json::json!({
        "protocolVersion": "2024-11-05",
        "capabilities": { "tools": {} },
        "serverInfo": { "name": "aevum-mcp-server", "version": "0.1.0" }
    }))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    async fn test_state() -> Arc<AppState> {
        let dir = tempdir().unwrap();
        AppState::new(dir.path().join("router_test.bin")).await.unwrap()
    }

    fn make_req(method: &str, params: serde_json::Value) -> McpRequest {
        McpRequest { jsonrpc: "2.0".into(), id: Value::Number(1.into()), method: method.to_owned(), params }
    }

    // ── dispatch ─────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn dispatch_unknown_method_returns_error_32601() {
        let state = test_state().await;
        let req = make_req("unknown/method", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32601);
    }

    #[tokio::test]
    async fn dispatch_initialize_returns_protocol_version() {
        let state = test_state().await;
        let req = make_req("initialize", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        assert!(resp.result.is_some());
        let r = resp.result.unwrap();
        assert_eq!(r["protocolVersion"], "2024-11-05");
        assert!(r["capabilities"]["tools"].is_object());
    }

    #[tokio::test]
    async fn dispatch_tools_list_returns_four_tools() {
        let state = test_state().await;
        let req = make_req("tools/list", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        let tools = resp.result.unwrap()["tools"].as_array().unwrap().to_owned();
        assert_eq!(tools.len(), 4, "must expose exactly 4 tools");
    }

    #[tokio::test]
    async fn tools_list_contains_all_tool_names() {
        let state = test_state().await;
        let req = make_req("tools/list", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        let tools = resp.result.unwrap()["tools"].as_array().unwrap().to_owned();
        let names: Vec<&str> = tools.iter()
            .filter_map(|t| t["name"].as_str())
            .collect();
        assert!(names.contains(&"aevum_remember"),  "missing aevum_remember");
        assert!(names.contains(&"aevum_recall"),    "missing aevum_recall");
        assert!(names.contains(&"aevum_filter"),    "missing aevum_filter");
        assert!(names.contains(&"aevum_settle"),    "missing aevum_settle");
    }

    #[tokio::test]
    async fn dispatch_unknown_tool_returns_error_32602() {
        let state = test_state().await;
        let req = make_req(
            "tools/call",
            serde_json::json!({ "name": "nonexistent", "arguments": {} }),
        );
        let resp = dispatch(req, state).await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn mcp_response_ok_has_no_error() {
        let resp = McpResponse::ok(Value::Number(1.into()), serde_json::json!({ "x": 1 }));
        assert!(resp.error.is_none());
        assert_eq!(resp.result.unwrap()["x"], 1);
    }

    #[tokio::test]
    async fn mcp_response_err_has_no_result() {
        let resp = McpResponse::err(Value::Number(1.into()), -32700, "parse error");
        assert!(resp.result.is_none());
        let e = resp.error.unwrap();
        assert_eq!(e.code, -32700);
        assert!(e.message.contains("parse error"));
    }

    #[tokio::test]
    async fn tools_list_each_tool_has_input_schema() {
        let state = test_state().await;
        let req = make_req("tools/list", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        let tools = resp.result.unwrap()["tools"].as_array().unwrap().to_owned();
        for tool in &tools {
            assert!(
                tool.get("inputSchema").is_some(),
                "tool {:?} missing inputSchema", tool["name"]
            );
        }
    }

    #[tokio::test]
    async fn server_info_has_name_and_version() {
        let state = test_state().await;
        let req = make_req("initialize", serde_json::json!({}));
        let resp = dispatch(req, state).await;
        let r = resp.result.unwrap();
        assert!(r["serverInfo"]["name"].is_string());
        assert!(r["serverInfo"]["version"].is_string());
    }
}
