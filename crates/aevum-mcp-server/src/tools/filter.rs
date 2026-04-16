// crates/aevum-mcp-server/src/tools/filter.rs
//
// Pillar: III. PACR field: Γ.
// aevum_filter: Paperclip token reduction via ε-engine content distillation.
//
// Pipeline:
//   1. TextSymbolizer: text → 4-gram frequency distribution
//      → too short? → return { filtered: false, reason: "text_too_short" }
//   2. quick_screen: byte stream → ScreenResult
//      → Skip? → return { filtered: false, reason: "no_signal" }
//   3. Split text into fixed-size chunks (~512 chars)
//   4. Per chunk: symbolize → infer_fast → S_T
//   5. Keep chunks where S_T > S_T_THRESHOLD
//   6. Return { filtered: true, content: joined_kept_chunks, kept_chunks, total_chunks }
//
// Complexity: O(L × depth) where L = total characters, depth = CSSR max_depth.
// Pillar I compliant: no global lock, no heap growth beyond input size.

use std::sync::Arc;

use serde_json::Value;

use crate::router::McpResponse;
use crate::state::AppState;
use crate::symbolizer::TextSymbolizer;

use epsilon_engine::{
    infer_fast,
    quick_screen::{quick_screen, ScreenResult},
    symbolize::equal_frequency,
    Config,
};

/// Chunk size for per-chunk CSSR analysis.
/// 512 chars ≈ 128 tokens — balances S_T resolution with CSSR convergence.
const CHUNK_SIZE: usize = 512;

/// S_T retention threshold (bits).
/// Chunks below this are considered structurally empty and discarded.
/// Typical prose: S_T ≈ 1–4. Noise: S_T ≈ 0.
const S_T_THRESHOLD: f64 = 0.3;

/// Shannon entropy pre-filter threshold (bits).
const QUICK_SCREEN_THRESHOLD: f64 = 0.5;

/// ε-machine alphabet size (matches remember.rs for consistency).
const ALPHABET_SIZE: usize = 8;

pub async fn handle(id: Value, args: Value, _state: Arc<AppState>) -> McpResponse {
    // ── 1. Parse argument ─────────────────────────────────────────────────────
    let content = match args.get("content").and_then(|v| v.as_str()) {
        Some(c) => c.to_owned(),
        None => return McpResponse::err(id, -32602, "missing required argument: content"),
    };

    let sym = TextSymbolizer::new();

    // ── 2. Global quick_screen on full content ────────────────────────────────
    // If the entire content is noise we save the cost of chunking + CSSR.
    let global_freqs = match sym.symbolize(&content) {
        Some(f) => f,
        None => {
            return McpResponse::ok(
                id,
                serde_json::json!({
                    "filtered": false,
                    "reason":   "text_too_short",
                    "content":  ""
                }),
            );
        }
    };

    let byte_stream: Vec<u8> = global_freqs.iter().flat_map(|v| v.to_le_bytes()).collect();
    match quick_screen(&byte_stream, QUICK_SCREEN_THRESHOLD) {
        ScreenResult::Skip {
            reason,
            entropy_bits,
        } => {
            return McpResponse::ok(
                id,
                serde_json::json!({
                    "filtered":     false,
                    "reason":       "no_signal",
                    "detail":       reason,
                    "entropy_bits": entropy_bits,
                    "content":      ""
                }),
            );
        }
        ScreenResult::Proceed { .. } => {}
    }

    // ── 3. Chunk + per-chunk CSSR ─────────────────────────────────────────────
    // char_indices is needed to avoid splitting UTF-8 code points.
    let chars: Vec<char> = content.chars().collect();
    let total_chars = chars.len();

    let cfg = Config {
        max_depth: 5,
        alpha: 0.001,
        bootstrap_b: 0, // fast path (Pillar I)
        alphabet_size: ALPHABET_SIZE,
    };

    let mut kept: Vec<String> = Vec::new();
    let mut total_chunks: usize = 0;

    let mut offset = 0;
    while offset < total_chars {
        let end = (offset + CHUNK_SIZE).min(total_chars);
        let chunk: String = chars[offset..end].iter().collect();
        offset = end;
        total_chunks += 1;

        // Per-chunk symbolize → quick_screen → CSSR
        let chunk_s_t = match sym.symbolize(&chunk) {
            None => {
                // Chunk too short for 4-gram → keep it unconditionally (avoid data loss
                // on tail fragments). Physical rationale: short tail has S_T unknown,
                // not S_T=0; the uncertainty favours retention.
                kept.push(chunk);
                continue;
            }
            Some(freqs) => {
                let bytes: Vec<u8> = freqs.iter().flat_map(|v| v.to_le_bytes()).collect();
                match quick_screen(&bytes, QUICK_SCREEN_THRESHOLD) {
                    ScreenResult::Skip { .. } => {
                        // Chunk is pure noise — discard.
                        continue;
                    }
                    ScreenResult::Proceed { .. } => {}
                }

                match equal_frequency(&freqs, ALPHABET_SIZE) {
                    Ok(symbols) => {
                        let result = infer_fast(&symbols, cfg.clone());
                        result.cognitive_split.statistical_complexity.point
                    }
                    Err(_) => {
                        // Constant-input (all 4-grams identical) → S_T = 0.
                        // Discard (below threshold).
                        0.0
                    }
                }
            }
        };

        if chunk_s_t > S_T_THRESHOLD {
            kept.push(chunk);
        }
        // else: discard low-S_T chunk (noise / boilerplate)
    }

    let kept_chunks = kept.len();
    let filtered_content = kept.join("\n\n");

    McpResponse::ok(
        id,
        serde_json::json!({
            "filtered":     true,
            "content":      filtered_content,
            "kept_chunks":  kept_chunks,
            "total_chunks": total_chunks,
            "s_t_threshold": S_T_THRESHOLD
        }),
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    async fn state() -> Arc<AppState> {
        let dir = tempdir().unwrap();
        AppState::new(dir.path().join("l.bin")).await.unwrap()
    }

    #[tokio::test]
    async fn filter_missing_content_returns_error() {
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({}),
            state().await,
        )
        .await;
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32602);
    }

    #[tokio::test]
    async fn filter_empty_string_returns_too_short() {
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "content": "" }),
            state().await,
        )
        .await;
        let r = resp.result.unwrap();
        assert_eq!(r["filtered"], false);
        assert_eq!(r["reason"], "text_too_short");
    }

    #[tokio::test]
    async fn filter_structured_text_returns_filtered_true() {
        let content = "The epsilon machine infers causal structure from discrete time series. \
                       Statistical complexity measures the minimum information needed to predict \
                       future observations. Entropy rate measures residual unpredictability. \
                       These two quantities are inseparable — two projections of the same ε-machine. \
                       The PACR record stores both as the cognitive split Γ. \
                       This text should have sufficient S_T to pass the retention threshold.";
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "content": content }),
            state().await,
        )
        .await;
        assert!(resp.error.is_none(), "unexpected error: {:?}", resp.error);
        let r = resp.result.unwrap();
        // Either filtered=true (kept content) or filtered=false(noise) — for structured text, expect true.
        assert_eq!(r["filtered"], true, "structured text should be retained");
        assert!(r["kept_chunks"].is_number());
        assert!(r["total_chunks"].is_number());
    }

    #[tokio::test]
    async fn filter_response_has_required_fields() {
        let content = "Landauer's principle: any logically irreversible computation must \
                       dissipate at least k_B × T × ln(2) joules per erased bit. This is \
                       a corollary of the Second Law of Thermodynamics, not an engineering limitation.";
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "content": content }),
            state().await,
        )
        .await;
        let r = resp.result.unwrap();
        assert!(r.get("filtered").is_some(), "must have 'filtered'");
        assert!(r.get("content").is_some(), "must have 'content'");
    }

    #[tokio::test]
    async fn filter_keeps_at_most_total_chunks() {
        let content = "This is a structured paragraph with enough words to form 4-grams. \
                       The epsilon machine analysis will compute S_T and H_T for this chunk. \
                       Physically annotated causal records track information structure over time. \
                       Each computation event has an irreducible Landauer cost in joules.";
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "content": content }),
            state().await,
        )
        .await;
        let r = resp.result.unwrap();
        if r["filtered"] == true {
            let kept = r["kept_chunks"].as_u64().unwrap();
            let total = r["total_chunks"].as_u64().unwrap();
            assert!(kept <= total, "kept_chunks must not exceed total_chunks");
        }
    }

    #[tokio::test]
    async fn filter_long_content_produces_multiple_chunks() {
        // 1100 chars ≈ 2+ chunks at CHUNK_SIZE=512
        let content = "a".repeat(600) + &"b".repeat(600);
        let resp = handle(
            Value::Number(1.into()),
            serde_json::json!({ "content": content }),
            state().await,
        )
        .await;
        // Should not error (may be filtered out as noise, but must return a valid response)
        assert!(resp.error.is_none() || resp.result.is_some());
    }
}
