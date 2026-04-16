//! Epiplexity estimator (arXiv:2601.03220).
//!
//! For a computationally bounded observer with time budget T:
//!
//! * `H_T` — time-bounded entropy: the Shannon entropy of the empirical cost
//!   distribution over a rolling window.  Represents randomness that the
//!   observer **cannot** reduce within the time budget.
//!
//! * `S_T` = H_max − H_T — learnable structure: the information the observer
//!   **can** compress using a frequency model within T.
//!
//! * `ε`   = S_T / H_max — epiplexity ∈ [0, 1]:
//!   - ε → 1: costs are highly concentrated / predictable (structured).
//!   - ε → 0: costs are uniformly distributed (pure noise).
//!
//! # Lock-free design
//!
//! A circular ring of `WINDOW` `AtomicU64` slots is written with
//! `fetch_add` on the head counter.  `observe()` is O(1); `compute()` is
//! O(WINDOW) = O(1024) — called only when building a `CausalRecord`, not
//! on every hot-path operation.

use std::sync::atomic::{AtomicU64, Ordering};

const WINDOW: usize = 1024;
const WINDOW_MASK: usize = WINDOW - 1;

/// Upper bound for cost values tracked in the frequency table.
/// All χ costs fit comfortably (base=10, max trilemma×=3 → 30 per call).
const MAX_COST_SLOT: usize = 255;

pub struct EpiplexityEstimator {
    ring: Box<[AtomicU64]>,   // circular buffer; 0 = empty slot
    head: AtomicU64,
}

// Safety: AtomicU64 is Sync; Box is unique owner.
unsafe impl Sync for EpiplexityEstimator {}
unsafe impl Send for EpiplexityEstimator {}

impl EpiplexityEstimator {
    pub fn new() -> Self {
        let ring = (0..WINDOW)
            .map(|_| AtomicU64::new(0))
            .collect::<Vec<_>>()
            .into_boxed_slice();
        Self { ring, head: AtomicU64::new(0) }
    }

    /// Record one cost observation.  O(1), never blocks.
    #[inline]
    pub fn observe(&self, cost: u64) {
        let cost = cost.clamp(1, MAX_COST_SLOT as u64); // 0 reserved as "empty"
        let idx  = self.head.fetch_add(1, Ordering::Relaxed) as usize & WINDOW_MASK;
        self.ring[idx].store(cost, Ordering::Release);
    }

    /// Compute H_T, S_T, and ε from the current window.  O(WINDOW).
    pub fn compute(&self) -> EpiplexityValues {
        let mut freq   = [0u32; MAX_COST_SLOT + 1];
        let mut total  = 0u32;

        for slot in self.ring.iter() {
            let v = slot.load(Ordering::Acquire) as usize;
            if v > 0 && v <= MAX_COST_SLOT {
                freq[v] += 1;
                total   += 1;
            }
        }

        if total == 0 {
            return EpiplexityValues::zero();
        }

        let n = total as f64;

        // Shannon entropy of the empirical distribution.
        let h_t: f64 = freq.iter()
            .filter(|&&c| c > 0)
            .map(|&c| { let p = c as f64 / n; -p * p.log2() })
            .sum();

        // Maximum entropy: log2 of the number of distinct cost values seen.
        let distinct = freq.iter().filter(|&&c| c > 0).count().max(1) as f64;
        let h_max = distinct.log2().max(f64::EPSILON); // avoid /0

        let s_t        = (h_max - h_t).max(0.0);
        let epiplexity = (s_t / h_max).clamp(0.0, 1.0);

        EpiplexityValues { h_t, s_t, epiplexity }
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct EpiplexityValues {
    /// Time-bounded entropy H_T (bits).
    pub h_t:        f64,
    /// Learnable structure S_T (bits).
    pub s_t:        f64,
    /// Epiplexity ε = S_T / H_max ∈ [0, 1].
    pub epiplexity: f64,
}

impl EpiplexityValues {
    fn zero() -> Self { Self { h_t: 0.0, s_t: 0.0, epiplexity: 0.0 } }
}
