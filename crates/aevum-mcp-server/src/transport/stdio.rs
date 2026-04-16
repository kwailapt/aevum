// crates/aevum-mcp-server/src/transport/stdio.rs
//
// Pillar: I. PACR field: ι.
// JSON-RPC over stdin/stdout — MCP standard transport for Claude Desktop.

#![forbid(unsafe_code)]

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
            Ok(0) => break, // EOF
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

        let response = match serde_json::from_str::<McpRequest>(trimmed) {
            Ok(req) => dispatch(req, Arc::clone(&state)).await,
            Err(e) => McpResponse::err(
                Value::Null,
                -32700,
                format!("parse error: {e}"),
            ),
        };

        let mut out = serde_json::to_string(&response).unwrap_or_default();
        out.push('\n');
        if let Err(e) = writer.write_all(out.as_bytes()).await {
            eprintln!("stdout write error: {e}");
            break;
        }
        let _ = writer.flush().await;
    }
}
