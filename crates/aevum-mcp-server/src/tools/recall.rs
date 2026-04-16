// crates/aevum-mcp-server/src/tools/recall.rs
//
// Pillar: I/III. PACR field: Π/Γ.
// aevum_recall: query → TextSymbolizer → S_T feature → ρ-weighted BTreeMap search → structured context.

#![forbid(unsafe_code)]

use crate::router::McpResponse;
use serde_json::Value;

pub async fn handle(id: Value, args: Value) -> McpResponse {
    let _query = match args.get("query").and_then(|v| v.as_str()) {
        Some(q) => q.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: query"),
    };
    let _top_k = args.get("top_k").and_then(|v| v.as_u64()).unwrap_or(5) as usize;

    // TODO(week-1): implement full pipeline:
    //   TextSymbolizer → infer_fast → query_S_T
    //   BTreeMap<OrderedFloat<f64>, Vec<CausalId>> range query
    //   score = rho / (1 + |S_T - query_S_T|)
    //   return top_k structured records

    McpResponse::err(id, -32603, "aevum_recall: not yet implemented")
}
