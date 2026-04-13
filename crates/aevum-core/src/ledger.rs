//! Sharded, memory-mapped, lock-free ledger with causal DAG integration.
//!
//! # Layer-2 recap (scale + thermodynamics)
//!
//! * 16 mmap shards × 1 M slots = 16 M physical slots (128 MB).
//! * `splitmix64`: deterministic routing, stable across processes.
//! * `NessMonitor`: tracks σ = dS/dt for NESS reporting.
//!
//! # Layer-3 additions (Epiplexity + causal DAG)
//!
//! Every `deduct()` call now:
//! 1. Measures the CAS loop latency (`trilemma_t`).
//! 2. Calls `EpiplexityEstimator::observe()` and `compute()`.
//! 3. Builds a `CausalRecord` carrying the three physics-native fields:
//!    (a) Landauer bit-erasure count  (b) trilemma (E, T, S) vector  (c) H_T / S_T / ε.
//! 4. Appends to the lock-free G-Set CRDT `CausalDag`.

use crate::causal_dag::{CausalDag, CausalRecord};
use crate::epiplexity::EpiplexityEstimator;
use crate::thermodynamics::{NessMonitor, TrilemmaMode};
use memmap2::MmapMut;
use std::fs::OpenOptions;
use std::io::Write;
use std::slice;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{mpsc, Arc};
use std::thread;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

// ── Constants ─────────────────────────────────────────────────────────────────

pub const N_SHARDS: usize = 16;           // must be power of 2
pub const SLOTS_PER_SHARD: usize = 1_000_000;

const SHARD_BYTES: u64 = (SLOTS_PER_SHARD * 8) as u64;

/// Sentinel returned by `deduct` when balance < cost.
pub const INSUFFICIENT: u64 = u64::MAX;

const AUDIT_PATH: &str = "ledger_audit.jsonl";
const FLUSH_EVERY: u64 = 100;

// ── splitmix64 + route ────────────────────────────────────────────────────────

/// Deterministic bijection u64 → u64 (no external deps, stable cross-process).
#[inline(always)]
pub fn splitmix64(x: u64) -> u64 {
    let x = x.wrapping_add(0x9e3779b97f4a7c15);
    let x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    let x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

/// Map `node_id` → `(shard_index, slot_index)` in O(1).
#[inline(always)]
pub fn route(node_id: u64) -> (usize, usize) {
    let h     = splitmix64(node_id);
    let shard = (h as usize) & (N_SHARDS - 1);
    let slot  = ((h >> 4) as usize) % SLOTS_PER_SHARD;
    (shard, slot)
}

// ── Internal shard ────────────────────────────────────────────────────────────

struct Shard {
    slots: &'static [AtomicU64],
    mmap:  *mut MmapMut,
}

unsafe impl Send for Shard {}
unsafe impl Sync for Shard {}

// ── ShardedLedger ─────────────────────────────────────────────────────────────

pub struct ShardedLedger {
    shards:   Vec<Shard>,
    tx_count: AtomicU64,
    log_tx:   mpsc::SyncSender<String>,

    // Layer-2
    ness: Arc<NessMonitor>,

    // Layer-3
    epi: EpiplexityEstimator,
    dag: Arc<CausalDag>,
}

unsafe impl Send for ShardedLedger {}
unsafe impl Sync for ShardedLedger {}

impl ShardedLedger {
    /// Open sharded ledger.  Also opens the causal DAG at `{dir}/dag.bin`.
    pub fn open(dir: &str, ness: Arc<NessMonitor>) -> std::io::Result<Self> {
        std::fs::create_dir_all(dir)?;

        let mut shards = Vec::with_capacity(N_SHARDS);
        for i in 0..N_SHARDS {
            let path = format!("{dir}/shard_{i:02}.bin");
            let file = OpenOptions::new()
                .read(true).write(true).create(true)
                .open(&path)?;
            if file.metadata()?.len() < SHARD_BYTES {
                file.set_len(SHARD_BYTES)?;
            }
            let mmap: *mut MmapMut =
                Box::into_raw(Box::new(unsafe { MmapMut::map_mut(&file)? }));
            let slots: &'static [AtomicU64] = unsafe {
                slice::from_raw_parts(
                    (*mmap).as_mut_ptr() as *const AtomicU64,
                    SLOTS_PER_SHARD,
                )
            };
            shards.push(Shard { slots, mmap });
        }

        let (log_tx, log_rx) = mpsc::sync_channel::<String>(8_192);
        thread::spawn(move || {
            if let Ok(mut f) =
                OpenOptions::new().create(true).append(true).open(AUDIT_PATH)
            {
                for msg in log_rx { let _ = f.write_all(msg.as_bytes()); }
            }
        });

        let dag_path = format!("{dir}/dag.bin");
        let dag = CausalDag::open(&dag_path)?;

        Ok(Self {
            shards,
            tx_count: AtomicU64::new(0),
            log_tx,
            ness,
            epi: EpiplexityEstimator::new(),
            dag,
        })
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /// CAS deduction loop with Epiplexity recording.
    ///
    /// Returns new balance on success, or `INSUFFICIENT` (u64::MAX) when
    /// `balance < cost`.  The `mode` parameter encodes the declared
    /// `TrilemmaMode`; it is written into the `CausalRecord` but does **not**
    /// change which balance slot is accessed — cost multipliers are applied
    /// by the caller before invoking `deduct`.
    pub fn deduct(&self, node_id: u64, cost: u64, mode: TrilemmaMode) -> u64 {
        let t0 = Instant::now();

        let (si, slot_i) = route(node_id);
        let slot = &self.shards[si].slots[slot_i];
        let mut cur = slot.load(Ordering::Acquire);
        let result = loop {
            if cur < cost { break INSUFFICIENT; }
            match slot.compare_exchange_weak(
                cur, cur - cost,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_)  => break cur - cost,
                Err(v) => cur = v,
            }
        };

        let elapsed_us = t0.elapsed().as_micros() as u64;

        if result != INSUFFICIENT {
            self.ness.record_deduct(cost);
            self.record_full(node_id, cost, result, si, elapsed_us, mode);
        }
        result
    }

    /// Atomic credit: minting or refund.
    pub fn mint(&self, node_id: u64, amount: u64) {
        let (si, slot_i) = route(node_id);
        self.shards[si].slots[slot_i].fetch_add(amount, Ordering::AcqRel);
        self.ness.record_mint(amount);
    }

    /// Non-destructive balance read.
    pub fn balance(&self, node_id: u64) -> u64 {
        let (si, slot_i) = route(node_id);
        self.shards[si].slots[slot_i].load(Ordering::Acquire)
    }

    /// Expose NESS monitor for the background reporter in `main`.
    pub fn ness(&self) -> Arc<NessMonitor> { self.ness.clone() }

    /// Expose the causal DAG (e.g., for query endpoints).
    pub fn dag(&self) -> Arc<CausalDag> { self.dag.clone() }

    // ── Internal ──────────────────────────────────────────────────────────────

    fn record_full(
        &self,
        node_id:    u64,
        cost:       u64,
        balance:    u64,
        shard:      usize,
        elapsed_us: u64,
        mode:       TrilemmaMode,
    ) {
        let n = self.tx_count.fetch_add(1, Ordering::Relaxed);
        if n % FLUSH_EVERY == 0 {
            unsafe { (*self.shards[shard].mmap).flush_async().ok(); }
        }

        // ── Epiplexity computation ─────────────────────────────────────────
        self.epi.observe(cost);
        let epi_vals = self.epi.compute();

        // ── Build CausalRecord ─────────────────────────────────────────────
        let ts_us = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_micros() as u64;

        let parent_hash = self.dag.parent_hash_for(node_id);

        let rec = CausalRecord {
            node_id,
            ts_us,
            cost,
            balance,
            // (a) Landauer: one χ = one k_B T ln2 erasure quantum
            bit_erasures: cost,
            parent_hash,
            shard:        shard as u32,
            mode_bits:    mode as u32,
            self_hash:    0, // filled by CausalDag::append

            // (b) Trilemma vector — measured actuals
            trilemma_e:   cost,          // E: χ consumed
            trilemma_t:   elapsed_us,    // T: wall-clock μs
            trilemma_s:   shard as u32,  // S: shard (space locality)
            _pad1:        0,

            // (c) Epiplexity
            h_t:          epi_vals.h_t,
            s_t:          epi_vals.s_t,
            epiplexity:   epi_vals.epiplexity,
            _pad2:        [0u8; 16],
        };

        self.dag.append(rec);

        // ── Lightweight JSON audit (hot-path: try_send, never blocks) ──────
        let _ = self.log_tx.try_send(format!(
            "{{\"ts\":{ts_us},\"node\":{node_id},\"shard\":{shard},\
              \"cost\":{cost},\"bal\":{balance},\
              \"bit_er\":{cost},\
              \"E\":{cost},\"T\":{elapsed_us},\"S\":{shard},\
              \"h_t\":{:.4},\"s_t\":{:.4},\"epi\":{:.4}}}\n",
            epi_vals.h_t, epi_vals.s_t, epi_vals.epiplexity,
        ));
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::thermodynamics::NessMonitor;
    use std::collections::HashSet;

    fn open_tmp(suffix: &str) -> ShardedLedger {
        let dir = format!("/tmp/aevum_test_{suffix}");
        let _ = std::fs::remove_dir_all(&dir);
        ShardedLedger::open(&dir, NessMonitor::new()).unwrap()
    }

    #[test]
    fn splitmix64_no_collision_small_range() {
        let hashes: HashSet<u64> = (0u64..10_000).map(splitmix64).collect();
        assert_eq!(hashes.len(), 10_000);
    }

    #[test]
    fn route_within_bounds() {
        for id in [0u64, 1, u64::MAX, 12345678, 99_999_999_999] {
            let (s, slot) = route(id);
            assert!(s < N_SHARDS);
            assert!(slot < SLOTS_PER_SHARD);
        }
    }

    #[test]
    fn deduct_insufficient() {
        let l = open_tmp("insuf3");
        assert_eq!(l.deduct(42, 1, TrilemmaMode::Balanced), INSUFFICIENT);
    }

    #[test]
    fn mint_then_deduct_records_to_dag() {
        let l = open_tmp("dag3");
        l.mint(7, 100);
        let bal = l.deduct(7, 30, TrilemmaMode::Balanced);
        assert_eq!(bal, 70);

        // DAG must contain exactly one record.
        let records: Vec<_> = l.dag.iter_committed().collect();
        assert_eq!(records.len(), 1);

        let r = &records[0];
        assert_eq!(r.node_id,      7);
        assert_eq!(r.cost,         30);
        assert_eq!(r.balance,      70);
        assert_eq!(r.bit_erasures, 30);  // (a) Landauer
        assert_eq!(r.trilemma_e,   30);  // (b) E axis
        assert!(r.trilemma_t < 1_000_000); // (b) T axis: < 1s
        assert!(r.epiplexity >= 0.0 && r.epiplexity <= 1.0); // (c)
        assert_ne!(r.self_hash, 0);
    }

    #[test]
    fn causal_chain_links_records() {
        let l = open_tmp("chain3");
        l.mint(5, 1000);

        let b1 = l.deduct(5, 10, TrilemmaMode::Balanced);
        let b2 = l.deduct(5, 10, TrilemmaMode::TimeOptimal);

        assert_eq!(b1, 990);
        assert_eq!(b2, 980);

        let records: Vec<_> = l.dag.iter_committed().collect();
        assert_eq!(records.len(), 2);

        // Second record's parent_hash == first record's self_hash.
        assert_eq!(records[1].parent_hash, records[0].self_hash);
    }

    #[test]
    fn trilemma_mode_stored_in_record() {
        let l = open_tmp("trilemma3");
        l.mint(1, 100);
        l.deduct(1, 10, TrilemmaMode::TimeOptimal);

        let r = l.dag.iter_committed().next().unwrap();
        assert_eq!(r.mode_bits, TrilemmaMode::TimeOptimal as u32);
    }

    #[test]
    fn concurrent_no_overdraft() {
        use std::sync::Arc;
        use std::thread;

        let l = Arc::new(open_tmp("concurrent3"));
        l.mint(0, 100);

        let handles: Vec<_> = (0..20).map(|_| {
            let l2 = l.clone();
            thread::spawn(move || { l2.deduct(0, 10, TrilemmaMode::Balanced); })
        }).collect();
        for h in handles { h.join().unwrap(); }

        assert_eq!(l.balance(0), 0);

        // Exactly 10 successful deductions → 10 DAG records.
        let n = l.dag.iter_committed().count();
        assert_eq!(n, 10);
    }
}
