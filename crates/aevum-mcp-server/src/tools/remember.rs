// crates/aevum-mcp-server/src/tools/remember.rs
//
// Pillar: II/III. PACR field: Λ/Γ/P.
// aevum_remember: text → TextSymbolizer → quick_screen → ε-engine → PACR record → DAG + ledger.

#![forbid(unsafe_code)]

use crate::router::{McpResponse};
use serde_json::Value;

pub async fn handle(id: Value, args: Value) -> McpResponse {
    let text = match args.get("text").and_then(|v| v.as_str()) {
        Some(t) => t.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: text"),
    };

    // TODO(week-1): implement full pipeline:
    //   TextSymbolizer → quick_screen → infer_fast → PacrBuilder → CausalDag + PacrLedger
    let _ = text;

    McpResponse::err(id, -32603, "aevum_remember: not yet implemented")
}
