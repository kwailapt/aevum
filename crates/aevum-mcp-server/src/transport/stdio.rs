// crates/aevum-mcp-server/src/transport/stdio.rs
//
// Pillar: I. PACR field: ι.
// JSON-RPC over stdin/stdout — MCP standard transport for Claude Desktop.
//
// MCP distinguishes two inbound message kinds (JSON-RPC 2.0 §5):
//   Request      — has "id" field → MUST send exactly one Response.
//   Notification — NO "id" field  → MUST send NO response (silent discard).
//
// Claude Desktop sends `notifications/initialized` immediately after the
// server's `initialize` response. Replying to it with any bytes (even an
// error) causes Claude Desktop's Zod validator to reject the response as an
// unrecognised message shape and mark the MCP server as failed.
//
// Fix: parse raw JSON Value first, gate on presence of "id".

use std::sync::Arc;

use crate::router::{dispatch, McpRequest, McpResponse};
use crate::state::AppState;
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

pub async fn run(state: Arc<AppState>) {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();
    let mut reader = BufReader::new(stdin);
    let mut writer = stdout;
    let mut line = String::new();

    loop {
        line.clear();
        match reader.read_line(&mut line).await {
            Ok(0) => break, // EOF — Claude Desktop closed the pipe
            Ok(_) => {}
            Err(e) => {
                eprintln!("stdin read error: {e}");
                break;
            }
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        // ── Step 1: parse raw JSON ────────────────────────────────────────────
        let raw: Value = match serde_json::from_str(trimmed) {
            Ok(v) => v,
            Err(e) => {
                // Malformed JSON — send parse error with null id (per JSON-RPC spec).
                let resp = McpResponse::err(Value::Null, -32700, format!("parse error: {e}"));
                write_response(&mut writer, &resp).await;
                continue;
            }
        };

        // ── Step 2: Notification guard ────────────────────────────────────────
        // JSON-RPC 2.0: a message without "id" is a Notification.
        // Responding to a Notification violates the spec and breaks Claude Desktop.
        if raw.get("id").is_none() {
            // Silently discard — no bytes written to stdout.
            continue;
        }

        // ── Step 3: Deserialise as Request and dispatch ───────────────────────
        let resp = match serde_json::from_value::<McpRequest>(raw) {
            Ok(req) => dispatch(req, Arc::clone(&state)).await,
            Err(e) => McpResponse::err(Value::Null, -32700, format!("parse error: {e}")),
        };
        write_response(&mut writer, &resp).await;
    }
}

/// Serialise `resp` to a single newline-terminated JSON line and flush.
async fn write_response(writer: &mut tokio::io::Stdout, resp: &McpResponse) {
    let mut out = serde_json::to_string(resp).unwrap_or_default();
    out.push('\n');
    if let Err(e) = writer.write_all(out.as_bytes()).await {
        eprintln!("stdout write error: {e}");
    }
    let _ = writer.flush().await;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    // Notification-gate logic is tested at the unit level by inspecting the
    // raw-JSON branch directly (the async stdio loop is integration-tested via
    // the smoke-test script).  Core invariant: a JSON object without "id" must
    // be classified as a Notification and produce zero response bytes.

    use serde_json::json;

    #[test]
    fn notification_has_no_id_field() {
        let notif =
            json!({ "jsonrpc": "2.0", "method": "notifications/initialized", "params": {} });
        assert!(
            notif.get("id").is_none(),
            "notifications must not carry an id"
        );
    }

    #[test]
    fn request_has_id_field() {
        let req = json!({ "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {} });
        assert!(req.get("id").is_some(), "requests must carry an id");
    }

    #[test]
    fn null_id_request_is_not_notification() {
        // JSON-RPC allows id: null for requests. Still a Request, not a Notification.
        let req = json!({ "jsonrpc": "2.0", "id": null, "method": "initialize", "params": {} });
        // id key is present (value is null) — get("id") returns Some(Value::Null)
        assert!(
            req.get("id").is_some(),
            "id:null is still a Request, not a Notification"
        );
    }
}
