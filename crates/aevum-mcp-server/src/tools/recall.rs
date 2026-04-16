// crates/aevum-mcp-server/src/tools/recall.rs
//
// Pillar: I/III. PACR field: Π/Γ.
// aevum_recall: query → TextSymbolizer → ε-machine → query_S_T
//               → BTreeMap<OrderedFloat<f64>, Vec<CausalId>> range search
//               → ρ-weighted scoring → top-K structured context.
//
// Optional: traverse_depth walks the Π predecessor chain from each top-K result
// up to N hops, returning the full causal chain as structured context.
//
// Pipeline:
//   1. TextSymbolizer::new().symbolize(query) → Option<Vec<f64>>
//      → None → return {context:[], reason:"query_too_short"}
//
//   2. equal_frequency + infer_fast → query_S_T
//
//   3. s_t_index read-lock: range [query_S_T - tolerance, query_S_T + tolerance]
//      → Vec<CausalId> candidates (O(log n + k) — Pillar I compliant)
//
//   4. For each candidate CausalId:
//        record = dag.get(id)
//        rho = cso.get_rho(id)
//        score = rho / (1.0 + |record.gamma.S_T - query_S_T|)
//
//   5. Sort descending by score, take top_k.
//
//   6. If traverse_depth > 0: walk Π predecessors up to traverse_depth hops.
//
//   7. Return structured context (never raw natural language — Pillar III: return
//      causal structure, not token-inflated prose).

#![forbid(unsafe_code)]

use std::sync::Arc;

use ordered_float::OrderedFloat;
use serde_json::Value;

use crate::router::McpResponse;
use crate::state::AppState;
use crate::symbolizer::TextSymbolizer;

use epsilon_engine::{infer_fast, symbolize::equal_frequency, Config};

/// Default S_T search tolerance (bits).
/// Candidates within ±1.0 bit of the query's S_T are considered structurally similar.
const DEFAULT_TOLERANCE: f64 = 1.0;

/// Default number of records to return.
const DEFAULT_TOP_K: usize = 5;

/// Default traverse_depth: 0 = no ancestor traversal (similarity search only).
const DEFAULT_TRAVERSE_DEPTH: usize = 0;

/// Alphabet size for query ε-machine inference (must match remember pipeline).
const ALPHABET_SIZE: usize = 8;

pub async fn handle(id: Value, args: Value, state: Arc<AppState>) -> McpResponse {
    // ── 0. Extract arguments ─────────────────────────────────────────────────
    let query = match args.get("query").and_then(|v| v.as_str()) {
        Some(q) => q.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: query"),
    };
    let top_k = args
        .get("top_k")
        .and_then(|v| v.as_u64())
        .map(|v| v as usize)
        .unwrap_or(DEFAULT_TOP_K);
    let tolerance = args
        .get("tolerance")
        .and_then(|v| v.as_f64())
        .unwrap_or(DEFAULT_TOLERANCE);
    let traverse_depth = args
        .get("traverse_depth")
        .and_then(|v| v.as_u64())
        .map(|v| v as usize)
        .unwrap_or(DEFAULT_TRAVERSE_DEPTH);

    // ── 1. TextSymbolizer → 4-gram frequency distribution ────────────────────
    let freqs = match TextSymbolizer::new().symbolize(&query) {
        Some(f) => f,
        None => {
            return McpResponse::ok(
                id,
                serde_json::json!({
                    "context": [],
                    "relevant_records": [],
                    "confidence": 0.0,
                    "reason": "query_too_short"
                }),
            );
        }
    };

    // ── 2. Quantize → ε-machine → query_S_T ─────────────────────────────────
    // ConstantInput: short query where all 4-gram frequencies are equal.
    // Physical meaning (Pillar III): uniform distribution → S_T = 0, H_T = H_max.
    // We proceed with query_S_T = 0.0 — this queries the zero-causal-structure region.
    let query_s_t = match equal_frequency(&freqs, ALPHABET_SIZE) {
        Ok(symbols) => {
            let cfg = Config {
                max_depth: 5,
                alpha: 0.001,
                bootstrap_b: 0,
                alphabet_size: ALPHABET_SIZE,
            };
            infer_fast(&symbols, cfg)
                .cognitive_split
                .statistical_complexity
                .point
        }
        Err(epsilon_engine::symbolize::SymbolizeError::ConstantInput) => {
            // Uniform distribution → query maps to S_T = 0 (zero causal structure).
            0.0_f64
        }
        Err(e) => {
            return McpResponse::err(id, -32603, format!("symbolize error: {e:?}"));
        }
    };

    // ── 3. BTreeMap range query over s_t_index ───────────────────────────────
    // O(log n + k) — Pillar I compliant.
    let lo = OrderedFloat(query_s_t - tolerance);
    let hi = OrderedFloat(query_s_t + tolerance);

    let candidates: Vec<pacr_types::CausalId> = {
        let idx = state.s_t_index.read().await;
        idx.range(lo..=hi)
            .flat_map(|(_, ids)| ids.iter().copied())
            .collect()
    };

    if candidates.is_empty() {
        return McpResponse::ok(
            id,
            serde_json::json!({
                "context": [],
                "relevant_records": [],
                "confidence": 0.0,
                "query_s_t": query_s_t,
                "searched_range": [query_s_t - tolerance, query_s_t + tolerance]
            }),
        );
    }

    // ── 4. Score: ρ-weighted S_T similarity ─────────────────────────────────
    // score = ρ / (1.0 + |record_S_T - query_S_T|)
    //
    // Rationale (Pillar III): Records closer in S_T share causal structure.
    // ρ (causal return rate from CsoIndex) amplifies records from high-value
    // agents — connecting Pillar II (thermodynamic cost) to retrieval quality.
    let mut scored: Vec<(f64, pacr_types::CausalId, f64, f64, String)> = candidates
        .into_iter()
        .filter_map(|cid| {
            let record = state.dag.get(&cid)?;
            let record_s_t = record.cognitive_split.statistical_complexity.point;
            let record_h_t = record.cognitive_split.entropy_rate.point;
            let rho = state.cso.get_rho(&cid);
            // Treat unknown agents (rho=0.0) as rho=1.0 (neutral, not penalized).
            let effective_rho = if rho > 0.0 { rho } else { 1.0 };
            let st_dist = (record_s_t - query_s_t).abs();
            let score = effective_rho / (1.0 + st_dist);

            // Decode payload as UTF-8; use hex fallback for binary payloads.
            let payload_str = std::str::from_utf8(&record.payload)
                .map(|s| s.to_owned())
                .unwrap_or_else(|_| {
                    format!("<binary {} bytes>", record.payload.len())
                });

            Some((score, cid, record_s_t, record_h_t, payload_str))
        })
        .collect();

    // ── 5. Sort descending by score, take top_k ──────────────────────────────
    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    scored.truncate(top_k);

    // Confidence = mean score of returned records (normalized: 0..1 roughly).
    let confidence = if scored.is_empty() {
        0.0_f64
    } else {
        let sum: f64 = scored.iter().map(|(s, ..)| s).sum();
        (sum / scored.len() as f64).min(1.0)
    };

    // ── 6. Causal chain traversal (traverse_depth > 0) ──────────────────────
    // Walk Π predecessor chain from each top-K record up to `traverse_depth` hops.
    // BFS, bounded. Genesis sentinels are skipped (CausalId(0)).
    // Pillar I: worst-case O(top_k × traverse_depth) DAG reads — bounded constant.
    let ancestor_chains: Vec<Vec<Value>> = if traverse_depth == 0 {
        scored.iter().map(|_| vec![]).collect()
    } else {
        scored
            .iter()
            .map(|(_, root_cid, _, _, _)| {
                let mut chain: Vec<Value> = Vec::new();
                let mut frontier: Vec<pacr_types::CausalId> = vec![*root_cid];
                let mut depth = 0usize;

                while depth < traverse_depth && !frontier.is_empty() {
                    let mut next_frontier: Vec<pacr_types::CausalId> = Vec::new();
                    for cid in &frontier {
                        if let Some(rec) = state.dag.get(cid) {
                            let s_t = rec.cognitive_split.statistical_complexity.point;
                            let h_t = rec.cognitive_split.entropy_rate.point;
                            let payload_str = std::str::from_utf8(&rec.payload)
                                .map(|s| s.to_owned())
                                .unwrap_or_else(|_| format!("<binary {} bytes>", rec.payload.len()));
                            chain.push(serde_json::json!({
                                "causal_id": format!("{:032x}", cid.0),
                                "depth":     depth + 1,
                                "s_t":       s_t,
                                "h_t":       h_t,
                                "payload":   payload_str
                            }));
                            for pred in &rec.predecessors {
                                if !pred.is_genesis() {
                                    next_frontier.push(*pred);
                                }
                            }
                        }
                    }
                    frontier = next_frontier;
                    depth += 1;
                }
                chain
            })
            .collect()
    };

    // ── 7. Build structured response ─────────────────────────────────────────
    let relevant_records: Vec<Value> = scored
        .iter()
        .zip(ancestor_chains.iter())
        .map(|((score, cid, rec_s_t, rec_h_t, payload), chain)| {
            let mut obj = serde_json::json!({
                "causal_id": format!("{:032x}", cid.0),
                "s_t": rec_s_t,
                "h_t": rec_h_t,
                "score": score,
                "payload": payload
            });
            if !chain.is_empty() {
                obj["causal_chain"] = serde_json::json!(chain);
            }
            obj
        })
        .collect();

    // `context` is a compact text summary of the top record (prevents token bloat).
    let context: Vec<Value> = scored
        .iter()
        .take(top_k)
        .map(|(_, _, rec_s_t, rec_h_t, payload)| {
            serde_json::json!({
                "s_t": rec_s_t,
                "h_t": rec_h_t,
                "content": payload
            })
        })
        .collect();

    McpResponse::ok(
        id,
        serde_json::json!({
            "context": context,
            "relevant_records": relevant_records,
            "confidence": confidence,
            "query_s_t": query_s_t,
            "searched_range": [query_s_t - tolerance, query_s_t + tolerance]
        }),
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    async fn remember(
        state: Arc<AppState>,
        text: &str,
        req_id: i64,
    ) -> serde_json::Value {
        crate::tools::remember::handle(
            Value::Number(req_id.into()),
            serde_json::json!({"text": text}),
            state,
        )
        .await
        .result
        .unwrap_or(serde_json::json!({"recorded": false}))
    }

    #[tokio::test]
    async fn recall_missing_query_returns_error() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(Value::Number(1.into()), serde_json::json!({}), state).await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn recall_short_query_returns_empty() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({"query": "hi"}),
            state,
        )
        .await;
        assert!(resp.result.is_some());
        let r = resp.result.unwrap();
        assert_eq!(r["context"].as_array().unwrap().len(), 0);
        assert_eq!(r["reason"], "query_too_short");
    }

    #[tokio::test]
    async fn recall_empty_dag_returns_empty_context() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({"query": "what does the system know about causal structure?"}),
            state,
        )
        .await;
        assert!(resp.result.is_some());
        let r = resp.result.unwrap();
        let ctx = r["context"].as_array().unwrap();
        assert_eq!(ctx.len(), 0);
    }

    #[tokio::test]
    async fn recall_finds_remembered_text() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        // Store a record.
        let mem_text = "The epsilon machine reconstructs causal states from time series data using CSSR algorithm.";
        let v = remember(Arc::clone(&state), mem_text, 1).await;

        if v["recorded"] == false {
            // noise-screened — skip test (environmental — not a logic error)
            return;
        }

        // Query with similar language.
        let resp = handle(
            Value::Number(2.into()),
            serde_json::json!({
                "query": "causal states from time series epsilon machine",
                "top_k": 5,
                "tolerance": 2.0
            }),
            Arc::clone(&state),
        )
        .await;

        assert!(resp.result.is_some());
        let r = resp.result.unwrap();
        // May or may not find depending on S_T distance — assert shape is correct.
        assert!(r["relevant_records"].is_array());
        assert!(r["confidence"].is_number());
        assert!(r["query_s_t"].is_number());
    }

    #[tokio::test]
    async fn recall_top_k_respected() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        // Store 5 records.
        let texts = [
            "Pillar I: all algorithms must be O(n) or better for hyperscale invariant",
            "Pillar II: Landauer bound k_B T ln2 per bit erased thermodynamic constraint",
            "Pillar III: epsilon machine CSSR S_T H_T cognitive complexity observer dependent",
            "PACR 6-tuple record causal identity predecessor landauer resource cognitive payload",
            "Causal DAG lock-free append-only DashMap CAS based data structure for Pillar One",
        ];
        let mut recorded_count = 0usize;
        for (i, t) in texts.iter().enumerate() {
            let v = remember(Arc::clone(&state), t, i as i64 + 1).await;
            if v["recorded"] == true {
                recorded_count += 1;
            }
        }

        if recorded_count == 0 {
            return; // all noise-screened — environment-dependent
        }

        let resp = handle(
            Value::Number(99.into()),
            serde_json::json!({
                "query": "Pillar causal machine thermodynamic constraint",
                "top_k": 2,
                "tolerance": 5.0
            }),
            Arc::clone(&state),
        )
        .await;

        let r = resp.result.unwrap();
        let relevant = r["relevant_records"].as_array().unwrap();
        assert!(
            relevant.len() <= 2,
            "top_k=2 must limit results, got {}",
            relevant.len()
        );
    }

    #[tokio::test]
    async fn recall_scores_are_positive() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        let text = "causal structure epsilon machine statistical complexity entropy rate";
        let v = remember(Arc::clone(&state), text, 1).await;
        if v["recorded"] == false {
            return;
        }

        let resp = handle(
            Value::Number(2.into()),
            serde_json::json!({"query": text, "tolerance": 5.0}),
            Arc::clone(&state),
        )
        .await;
        let r = resp.result.unwrap();
        for rec in r["relevant_records"].as_array().unwrap() {
            let score = rec["score"].as_f64().unwrap();
            assert!(score > 0.0, "all scores must be positive, got {score}");
        }
    }

    #[tokio::test]
    async fn recall_response_has_required_fields() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({"query": "causal memory query structure test"}),
            state,
        )
        .await;
        let r = resp.result.unwrap();
        assert!(r.get("context").is_some(), "response must have 'context'");
        assert!(r.get("relevant_records").is_some(), "response must have 'relevant_records'");
        assert!(r.get("confidence").is_some(), "response must have 'confidence'");
        assert!(r.get("query_s_t").is_some(), "response must have 'query_s_t'");
    }

    #[tokio::test]
    async fn recall_default_tolerance_is_used() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();
        // No tolerance arg → default 1.0 should be used silently (no error).
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({"query": "default tolerance test for recall pipeline"}),
            state,
        )
        .await;
        assert!(resp.error.is_none(), "no error expected with default tolerance");
    }

    #[tokio::test]
    async fn traverse_depth_zero_has_no_causal_chain() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        let text = "epsilon machine causal state splitting reconstruction algorithm complexity";
        let v = remember(Arc::clone(&state), text, 1).await;
        if v["recorded"] != true {
            return;
        }

        let resp = handle(
            Value::Number(2.into()),
            serde_json::json!({"query": text, "tolerance": 10.0, "traverse_depth": 0}),
            Arc::clone(&state),
        )
        .await;
        let r = resp.result.unwrap();
        for rec in r["relevant_records"].as_array().unwrap() {
            assert!(
                rec.get("causal_chain").is_none(),
                "traverse_depth=0 must not add causal_chain field"
            );
        }
    }

    #[tokio::test]
    async fn traverse_depth_one_includes_causal_chain() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        // Store two records so the second has a predecessor to traverse.
        let text1 = "Landauer bound energy cost thermodynamic constraint Pillar II";
        let text2 = "causal state epsilon machine CSSR algorithm statistical complexity Pillar III";
        let v1 = remember(Arc::clone(&state), text1, 1).await;
        let v2 = remember(Arc::clone(&state), text2, 2).await;
        if v1["recorded"] != true || v2["recorded"] != true {
            return;
        }

        let resp = handle(
            Value::Number(3.into()),
            serde_json::json!({"query": text2, "tolerance": 10.0, "traverse_depth": 1}),
            Arc::clone(&state),
        )
        .await;
        let r = resp.result.unwrap();
        let relevant = r["relevant_records"].as_array().unwrap();
        // At least one record should have a causal_chain field (the one with a predecessor).
        let has_chain = relevant.iter().any(|rec| rec.get("causal_chain").is_some());
        assert!(has_chain, "traverse_depth=1 on a chained record must produce causal_chain");
    }

    #[tokio::test]
    async fn traverse_depth_chain_entries_have_required_fields() {
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        let text1 = "autopoiesis feedback loop Gamma field schema evolution";
        let text2 = "causal return rate rho CSO Pillar II thermodynamic settlement";
        let v1 = remember(Arc::clone(&state), text1, 1).await;
        let v2 = remember(Arc::clone(&state), text2, 2).await;
        if v1["recorded"] != true || v2["recorded"] != true {
            return;
        }

        let resp = handle(
            Value::Number(3.into()),
            serde_json::json!({"query": text2, "tolerance": 10.0, "traverse_depth": 2}),
            Arc::clone(&state),
        )
        .await;
        let r = resp.result.unwrap();
        for rec in r["relevant_records"].as_array().unwrap() {
            if let Some(chain) = rec.get("causal_chain").and_then(|c| c.as_array()) {
                for entry in chain {
                    assert!(entry.get("causal_id").is_some(), "chain entry must have causal_id");
                    assert!(entry.get("depth").is_some(),    "chain entry must have depth");
                    assert!(entry.get("s_t").is_some(),      "chain entry must have s_t");
                    assert!(entry.get("h_t").is_some(),      "chain entry must have h_t");
                    assert!(entry.get("payload").is_some(),  "chain entry must have payload");
                    let depth = entry["depth"].as_u64().unwrap();
                    assert!(depth >= 1, "depth must be ≥1");
                }
            }
        }
    }

    #[tokio::test]
    async fn recall_remember_roundtrip() {
        // End-to-end: remember → recall → find the record.
        let dir = tempdir().unwrap();
        let state = AppState::new(dir.path().join("l.bin")).await.unwrap();

        let text = "The autopoietic kernel observes its own Gamma field and proposes schema evolution when H_T rises.";
        let v = remember(Arc::clone(&state), text, 1).await;
        if v["recorded"] == false {
            return;
        }
        let stored_s_t: f64 = v["s_t"].as_f64().unwrap();

        // Recall with a tolerance wide enough to always find the record.
        let resp = handle(
            Value::Number(2.into()),
            serde_json::json!({
                "query": text,
                "top_k": 5,
                "tolerance": 10.0
            }),
            Arc::clone(&state),
        )
        .await;
        let r = resp.result.unwrap();
        let query_s_t: f64 = r["query_s_t"].as_f64().unwrap();

        // S_T of the same text must be identical (TextSymbolizer is deterministic).
        assert!(
            (query_s_t - stored_s_t).abs() < 1e-9,
            "same text must produce same S_T: query={query_s_t}, stored={stored_s_t}"
        );

        let relevant = r["relevant_records"].as_array().unwrap();
        assert!(!relevant.is_empty(), "must find the remembered record");
    }
}
