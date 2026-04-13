//! Lock-free CRDT causal DAG for Aevum ledger records.
//!
//! # CRDT semantics (Grow-Only Set / G-Set)
//!
//! * Records are **content-addressed** by `self_hash` (splitmix64 chain over
//!   identity fields).  `self_hash` is never part of its own input.
//! * **Append** is the only mutation.  Records are immutable once committed.
//! * **Merge**(A, B) = union of record sets — idempotent, commutative,
//!   associative.  Two replicas converge by exchanging unseen records.
//! * **Causal ordering** is encoded in `parent_hash` chains per `node_id`.
//!
//! # Lock-free implementation
//!
//! * `write_head: AtomicUsize` is incremented with `fetch_add`, giving each
//!   writer a unique slot without any mutex.
//! * After writing all fields, the writer sets `filled[idx] = 1` behind a
//!   `Release` fence.  Readers check `filled[idx]` with `Acquire` before
//!   trusting the record.
//! * `heads[node_slot]: AtomicU64` stores the `self_hash` of the most recent
//!   record for each `node_id` group (65 536 buckets), enabling O(1) parent
//!   lookup.  Last-writer-wins is safe: all records are in the DAG regardless.
//!
//! # Storage
//!
//! An mmap-backed flat file (`ledger/dag.bin`) of `DAG_CAPACITY` fixed-size
//! `CausalRecord` slots (128 B each → 32 MB at 256 K capacity).

use crate::ledger::splitmix64;
use memmap2::MmapMut;
use std::fs::OpenOptions;
use std::sync::atomic::{fence, AtomicU8, AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;

// ── Record layout ─────────────────────────────────────────────────────────────

/// 128-byte record (two 64-byte cache lines) carrying all physics-native fields.
///
/// Compile-time size assertion below enforces this.
#[repr(C, align(64))]
#[derive(Clone, Copy)]
pub struct CausalRecord {
    // ── Cache line 0 (64 bytes): identity + transaction + Landauer ────────────

    /// Node identifier.
    pub node_id:      u64,   //  0..8

    /// Wall-clock timestamp of the operation (µs since UNIX epoch).
    pub ts_us:        u64,   //  8..16

    /// χ-Quanta deducted in this operation.
    pub cost:         u64,   // 16..24

    /// Remaining balance after deduction.
    pub balance:      u64,   // 24..32

    /// **(a) Landauer bit-erasure count.**
    ///
    /// Each χ-Quanta corresponds to one Landauer erasure event
    /// (E_min = k_B T ln 2 ≈ 2.85×10⁻²¹ J at 300 K).
    /// `bit_erasures = cost` by construction.
    pub bit_erasures: u64,   // 32..40

    /// Hash of the preceding record for this `node_id` (0 = genesis).
    pub parent_hash:  u64,   // 40..48

    /// Shard index where the balance slot resides (space locality proxy).
    pub shard:        u32,   // 48..52

    /// `TrilemmaMode` encoding: 0=Balanced, 1=EnergyOptimal, 2=SpaceOptimal, 3=TimeOptimal.
    pub mode_bits:    u32,   // 52..56

    /// Content hash for CRDT deduplication (splitmix64 over identity fields).
    pub self_hash:    u64,   // 56..64

    // ── Cache line 1 (64 bytes): trilemma measurements + epiplexity ──────────

    /// **(b-E) Energy axis** — χ-Quanta actually consumed (= cost × mode_multiplier).
    pub trilemma_e:   u64,   // 64..72

    /// **(b-T) Time axis** — wall-clock microseconds for the CAS deduction loop.
    pub trilemma_t:   u64,   // 72..80

    /// **(b-S) Space axis** — shard index (physical memory locality, 0-based).
    pub trilemma_s:   u32,   // 80..84

    pub _pad1:        u32,   // 84..88

    /// **(c) H_T** — time-bounded entropy estimate (bits) over the rolling window.
    pub h_t:          f64,   // 88..96

    /// **(c) S_T** — learnable structure estimate (bits) = H_max − H_T.
    pub s_t:          f64,   // 96..104

    /// **(c) ε** = S_T / H_max ∈ [0, 1].  1 = perfectly structured, 0 = pure noise.
    pub epiplexity:   f64,   // 104..112

    pub _pad2:        [u8; 16], // 112..128
}

// Enforce 128-byte layout at compile time.
const _: () = assert!(
    core::mem::size_of::<CausalRecord>() == 128,
    "CausalRecord must be exactly 128 bytes"
);

impl CausalRecord {
    /// Compute the content hash (does NOT include `self_hash` to avoid circularity).
    pub fn compute_hash(&self) -> u64 {
        let mut h = splitmix64(self.node_id);
        h = splitmix64(h ^ self.ts_us);
        h = splitmix64(h ^ self.cost);
        h = splitmix64(h ^ self.balance);
        h = splitmix64(h ^ self.parent_hash);
        // Ensure hash is never 0 (0 is used as "no record" sentinel).
        if h == 0 { 1 } else { h }
    }
}

// ── CausalDag ─────────────────────────────────────────────────────────────────

pub const DAG_CAPACITY: usize = 262_144;    // 256 K records
const DAG_BYTES: u64 = (DAG_CAPACITY * 128) as u64; // 32 MB

/// Buckets for causal chain head tracking (must be power of 2).
const HEAD_SLOTS: usize = 65_536;

pub struct CausalDag {
    records:    *mut CausalRecord,   // mmap base pointer
    mmap:       *mut MmapMut,
    write_head: AtomicUsize,
    /// Per-slot write-completion sentinel (0 = empty, 1 = committed).
    filled:     Vec<AtomicU8>,
    /// `heads[node_slot]` = `self_hash` of the latest record for this bucket.
    heads:      Vec<AtomicU64>,
}

// Safety:
//   records — each slot is written by exactly one thread (unique via fetch_add).
//   mmap    — touched only in flush_async, never aliased as &mut during reads.
unsafe impl Send for CausalDag {}
unsafe impl Sync for CausalDag {}

impl CausalDag {
    pub fn open(path: &str) -> std::io::Result<Arc<Self>> {
        let file = OpenOptions::new()
            .read(true).write(true).create(true)
            .open(path)?;
        if file.metadata()?.len() < DAG_BYTES {
            file.set_len(DAG_BYTES)?;
        }
        let mmap: *mut MmapMut =
            Box::into_raw(Box::new(unsafe { MmapMut::map_mut(&file)? }));
        let records = unsafe { (*mmap).as_mut_ptr() as *mut CausalRecord };

        let filled = (0..DAG_CAPACITY).map(|_| AtomicU8::new(0)).collect();
        let heads  = (0..HEAD_SLOTS).map(|_| AtomicU64::new(0)).collect();

        Ok(Arc::new(Self {
            records, mmap,
            write_head: AtomicUsize::new(0),
            filled, heads,
        }))
    }

    /// Look up the `self_hash` of the most recent committed record for `node_id`.
    /// Returns 0 (genesis) if no prior record exists for this bucket.
    pub fn parent_hash_for(&self, node_id: u64) -> u64 {
        let slot = splitmix64(node_id) as usize & (HEAD_SLOTS - 1);
        self.heads[slot].load(Ordering::Acquire)
    }

    /// Append one record to the DAG.  Lock-free; returns the slot index.
    ///
    /// Returns `None` when the mmap buffer is full (capacity exhausted).
    pub fn append(&self, mut rec: CausalRecord) -> Option<usize> {
        let idx = self.write_head.fetch_add(1, Ordering::Relaxed);
        if idx >= DAG_CAPACITY {
            // Saturate: do not wrap — wrapping would overwrite existing records
            // and break the G-Set CRDT invariant.
            return None;
        }

        // Seal the record with its content hash.
        rec.self_hash = rec.compute_hash();

        // Write all 128 bytes to the reserved slot.
        // Safety: idx is unique per thread; ptr arithmetic stays in bounds.
        unsafe { self.records.add(idx).write(rec); }

        // Release fence: all field writes above are visible before filled[idx] = 1.
        fence(Ordering::Release);
        self.filled[idx].store(1, Ordering::Relaxed);

        // Update causal chain head.  Last-writer-wins is CRDT-safe:
        // every record is in the DAG; only the "current tip" pointer races.
        let head_slot = splitmix64(rec.node_id) as usize & (HEAD_SLOTS - 1);
        self.heads[head_slot].store(rec.self_hash, Ordering::Release);

        // Async flush every 256 appends (power of 2, no division).
        if idx & 0xFF == 0 {
            unsafe { (*self.mmap).flush_async().ok(); }
        }

        Some(idx)
    }

    /// Number of records appended so far (capped at DAG_CAPACITY).
    pub fn len(&self) -> usize {
        self.write_head.load(Ordering::Relaxed).min(DAG_CAPACITY)
    }

    /// Iterate all **committed** records (Acquire-loads `filled[i]`).
    /// Yields records in append order; skips in-flight slots.
    pub fn iter_committed(&self) -> impl Iterator<Item = CausalRecord> + '_ {
        let head = self.len();
        (0..head).filter_map(move |i| {
            if self.filled[i].load(Ordering::Acquire) == 1 {
                // Safety: filled[i]==1 means the writer completed the Release fence.
                Some(unsafe { self.records.add(i).read() })
            } else {
                None
            }
        })
    }

    /// G-Set CRDT merge stub.
    ///
    /// Full distributed merge = union of two `iter_committed()` streams,
    /// deduplicated by `self_hash`.  This returns the local DAG size for now;
    /// the interface exists for the distributed extension in layer 4+.
    pub fn crdt_merge_count(&self) -> usize {
        self.len()
    }
}
