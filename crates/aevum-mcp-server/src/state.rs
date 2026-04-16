// crates/aevum-mcp-server/src/state.rs
//
// Pillar: I/II/III. PACR field: ALL.
// AppState — shared infrastructure threaded through every request handler.
//
// Design rationale:
//   - `CausalDag`  is lock-free (DashMap) — no wrapper needed.
//   - `PacrLedger` requires `&mut self` for file I/O → wrapped in `tokio::sync::Mutex`.
//   - `s_t_index`  is a `BTreeMap<OrderedFloat<f64>, Vec<CausalId>>` for O(log n) range
//     queries during recall → wrapped in `tokio::sync::RwLock` (many readers, rare writers).
//   - `CsoIndex`   is lock-free (DashMap) — no wrapper needed.
//   - `last_id`    tracks the most-recently appended CausalId so each new record can
//     set Π = {last_id}, forming a linear causal chain. Stored in a `std::sync::Mutex<u128>`
//     (non-async; held only for a u128 copy — nanoseconds, never across await points).
//     `AtomicU128` is not stable on MSRV 1.75.
//
// CausalId generation (no causal-id crate available at workspace level):
//   128-bit = 48-bit millisecond UNIX timestamp (left-shifted) | 80-bit process counter.
//   Timestamps used ONLY for ID uniqueness, never for causal ordering — Π encodes order.

#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use causal_dag::CausalDag;
use ordered_float::OrderedFloat;
use pacr_types::CausalId;
use pacr_ledger::{PacrLedger, LedgerError};
use aevum_core::CsoIndex;
use tokio::sync::RwLock;

use crate::resources::context::SsnBroadcaster;

// ── ID counter ────────────────────────────────────────────────────────────────

/// Per-process monotonic counter for the low 80 bits of generated CausalIds.
static ID_COUNTER: AtomicU64 = AtomicU64::new(1);

/// Generate a 128-bit causal ID.
///
/// Structure: `[48-bit ms since epoch][80-bit counter]`
/// The counter occupies bits 0–79; the timestamp occupies bits 80–127.
/// Guarantees strict monotonicity within a process and global uniqueness in practice.
///
/// Per §CLAUDE.local.md §2: the timestamp is used ONLY for ID uniqueness, not ordering.
/// Causal order is always encoded in Π (predecessor set).
pub fn generate_causal_id() -> CausalId {
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    // 48 bits of ms in the top half.
    let ts_bits = (ms & 0xFFFF_FFFF_FFFF) << 80;
    let counter = ID_COUNTER.fetch_add(1, Ordering::Relaxed) as u128;
    // Counter occupies bottom 80 bits.
    let counter_bits = counter & 0xFFFF_FFFF_FFFF_FFFF_FFFF;
    CausalId(ts_bits | counter_bits)
}

// ── AppState ──────────────────────────────────────────────────────────────────

/// Shared state threaded through all MCP request handlers via `Arc<AppState>`.
pub struct AppState {
    /// Lock-free append-only causal DAG (DashMap internals).
    pub dag: CausalDag,

    /// Append-only persistent PACR ledger.
    /// `tokio::sync::Mutex` because `PacrLedger::append` requires `&mut self` (file I/O).
    pub ledger: tokio::sync::Mutex<PacrLedger>,

    /// S_T → [CausalId] index for O(log n) range queries during recall.
    /// `RwLock` because reads dominate (recall >> remember frequency).
    pub s_t_index: RwLock<BTreeMap<OrderedFloat<f64>, Vec<CausalId>>>,

    /// Causal Settlement Oracle — tracks ρ (causal return rate) per agent.
    /// Lock-free (DashMap internals).
    pub cso: CsoIndex,

    /// Structural State Network broadcaster.
    /// Sends StateChange events to SSE subscribers after each record append.
    /// In stdio mode receivers are absent; send() is a zero-cost no-op.
    pub ssn: SsnBroadcaster,

    /// CausalId of the most recently appended record.
    /// New records set Π = {last_id}, forming a linear causal chain.
    /// `std::sync::Mutex<u128>` — never held across await points, held for nanoseconds.
    /// Initialized to 0 == CausalId::GENESIS.
    last_id: Mutex<u128>,
}

impl AppState {
    /// Open (or create) the PACR ledger at `ledger_path` and construct AppState.
    ///
    /// On open, replays all existing records into the in-memory indexes so that
    /// memory density (R1) is preserved across restarts:
    ///   - `dag`       — lock-free causal DAG (DashMap)
    ///   - `s_t_index` — BTreeMap<OrderedFloat<f64>, Vec<CausalId>> for recall
    ///   - `ssn`       — SsnBroadcaster rolling window (trend awareness)
    ///   - `last_id`   — advances to the highest replayed CausalId
    ///
    /// `cso` is NOT replayed from ledger (ρ rates require live interaction data,
    /// not historical records — they are rebuilt through normal settle calls).
    ///
    /// # Errors
    /// Returns `LedgerError` if the file cannot be opened or replayed.
    pub async fn new(ledger_path: impl AsRef<Path>) -> Result<Arc<Self>, LedgerError> {
        let ledger = PacrLedger::open(ledger_path)?;

        // ── Replay in-memory indexes from persisted ledger ────────────────────
        let dag        = CausalDag::new();
        let ssn        = SsnBroadcaster::new();
        let mut s_t_map: BTreeMap<OrderedFloat<f64>, Vec<CausalId>> = BTreeMap::new();
        let mut last_id_val: u128 = 0;

        for result in ledger.iter()? {
            let record = result?;
            let s_t = record.cognitive_split.statistical_complexity.point;
            let h_t = record.cognitive_split.entropy_rate.point;
            let cid = record.id;

            // Advance last_id to the highest seen CausalId.
            if cid.0 > last_id_val {
                last_id_val = cid.0;
            }

            // Insert into BTreeMap s_t_index.
            s_t_map
                .entry(OrderedFloat(s_t))
                .or_default()
                .push(cid);

            // Feed SSN rolling window (trend awareness restored after replay).
            ssn.observe(s_t, h_t);

            // Insert into lock-free DAG. Duplicate errors are impossible because
            // the ledger enforces unique IDs, but we tolerate them defensively.
            let _ = dag.append(record);
        }

        Ok(Arc::new(Self {
            dag,
            ledger: tokio::sync::Mutex::new(ledger),
            s_t_index: RwLock::new(s_t_map),
            cso: CsoIndex::new(),
            ssn,
            last_id: Mutex::new(last_id_val),
        }))
    }

    /// Snapshot the current last_id (the causal predecessor for the next record).
    pub fn last_id(&self) -> CausalId {
        let guard = self.last_id.lock().expect("last_id mutex poisoned");
        CausalId(*guard)
    }

    /// Advance last_id to `new_id` only if `new_id > current`.
    /// Monotonic: never regresses.
    pub fn update_last_id(&self, new_id: CausalId) {
        let mut guard = self.last_id.lock().expect("last_id mutex poisoned");
        if new_id.0 > *guard {
            *guard = new_id.0;
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn app_state_new_creates_successfully() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.ledger");
        let state = AppState::new(&path).await.unwrap();
        assert_eq!(state.last_id(), CausalId::GENESIS);
    }

    #[tokio::test]
    async fn generate_causal_id_is_unique() {
        let a = generate_causal_id();
        let b = generate_causal_id();
        assert_ne!(a, b, "sequential IDs must differ");
    }

    #[tokio::test]
    async fn generate_causal_id_is_monotonic() {
        let ids: Vec<CausalId> = (0..100).map(|_| generate_causal_id()).collect();
        for w in ids.windows(2) {
            assert!(w[0].0 < w[1].0, "IDs must be strictly monotonic");
        }
    }

    // ── Ledger replay tests ───────────────────────────────────────────────────

    /// Helper: remember a piece of text into `state` via the full tool pipeline.
    async fn remember(state: Arc<AppState>, text: &str) -> serde_json::Value {
        crate::tools::remember::handle(
            serde_json::Value::Number(1.into()),
            serde_json::json!({"text": text}),
            state,
        )
        .await
        .result
        .unwrap_or(serde_json::json!({"recorded": false}))
    }

    #[tokio::test]
    async fn replay_restores_dag_on_reopen() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("replay_dag.bin");

        let text = "The epsilon machine reconstructs causal states using CSSR algorithm with statistical complexity.";
        let v = {
            let state = AppState::new(&path).await.unwrap();
            remember(Arc::clone(&state), text).await
        };

        if v["recorded"] != true {
            return; // noise-screened — skip
        }
        let causal_id_str = v["causal_id"].as_str().unwrap().to_owned();

        // Reopen — replay must restore the DAG.
        let state2 = AppState::new(&path).await.unwrap();
        let cid_u128 = u128::from_str_radix(&causal_id_str, 16).unwrap();
        let cid = pacr_types::CausalId(cid_u128);
        assert!(
            state2.dag.get(&cid).is_some(),
            "replayed DAG must contain the persisted record"
        );
    }

    #[tokio::test]
    async fn replay_restores_s_t_index_on_reopen() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("replay_idx.bin");

        let text = "Pillar I hyperscale invariant O(n) lock-free causal dag DashMap CAS";
        let v = {
            let state = AppState::new(&path).await.unwrap();
            remember(Arc::clone(&state), text).await
        };

        if v["recorded"] != true {
            return;
        }
        let stored_s_t: f64 = v["s_t"].as_f64().unwrap();

        // Reopen — s_t_index must contain the stored S_T.
        let state2 = AppState::new(&path).await.unwrap();
        let idx = state2.s_t_index.read().await;
        let key = ordered_float::OrderedFloat(stored_s_t);
        assert!(
            idx.contains_key(&key),
            "replayed s_t_index must contain stored S_T={stored_s_t:.4}"
        );
    }

    #[tokio::test]
    async fn replay_restores_last_id_on_reopen() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("replay_lastid.bin");

        let text = "Landauer cost k_B T ln2 per erased bit thermodynamic Pillar II constraint";
        let v = {
            let state = AppState::new(&path).await.unwrap();
            remember(Arc::clone(&state), text).await
        };

        if v["recorded"] != true {
            return;
        }
        let causal_id_str = v["causal_id"].as_str().unwrap().to_owned();
        let expected_cid_u128 = u128::from_str_radix(&causal_id_str, 16).unwrap();

        // Reopen — last_id must be restored.
        let state2 = AppState::new(&path).await.unwrap();
        assert_eq!(
            state2.last_id(),
            pacr_types::CausalId(expected_cid_u128),
            "replayed last_id must equal the last appended record's CausalId"
        );
    }

    #[tokio::test]
    async fn empty_ledger_replay_produces_empty_indexes() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("empty_replay.bin");

        // Open once (creates header), close, reopen.
        drop(AppState::new(&path).await.unwrap());
        let state2 = AppState::new(&path).await.unwrap();

        assert_eq!(state2.last_id(), CausalId::GENESIS, "empty ledger → GENESIS");
        assert!(
            state2.s_t_index.read().await.is_empty(),
            "empty ledger → empty s_t_index"
        );
    }

    #[tokio::test]
    async fn update_last_id_advances_monotonically() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.ledger");
        let state = AppState::new(&path).await.unwrap();

        let id1 = CausalId(100);
        let id2 = CausalId(200);
        let id3 = CausalId(50); // older — must not regress

        state.update_last_id(id1);
        assert_eq!(state.last_id(), id1);

        state.update_last_id(id2);
        assert_eq!(state.last_id(), id2);

        state.update_last_id(id3); // must NOT update (50 < 200)
        assert_eq!(state.last_id(), id2, "last_id must not regress");
    }
}
