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
        "aevum_filter"   => crate::tools::filter::handle(req.id, args).await,
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
