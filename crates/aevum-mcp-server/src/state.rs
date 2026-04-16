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

    /// CausalId of the most recently appended record.
    /// New records set Π = {last_id}, forming a linear causal chain.
    /// `std::sync::Mutex<u128>` — never held across await points, held for nanoseconds.
    /// Initialized to 0 == CausalId::GENESIS.
    last_id: Mutex<u128>,
}

impl AppState {
    /// Open (or create) the PACR ledger at `ledger_path` and construct AppState.
    ///
    /// # Errors
    /// Returns `LedgerError` if the file cannot be opened or replayed.
    pub async fn new(ledger_path: impl AsRef<Path>) -> Result<Arc<Self>, LedgerError> {
        let ledger = PacrLedger::open(ledger_path)?;
        Ok(Arc::new(Self {
            dag: CausalDag::new(),
            ledger: tokio::sync::Mutex::new(ledger),
            s_t_index: RwLock::new(BTreeMap::new()),
            cso: CsoIndex::new(),
            last_id: Mutex::new(0), // CausalId::GENESIS
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
