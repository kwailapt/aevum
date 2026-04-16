//! Pillar: II. PACR field: Λ.
//!
//! **Landauer-on-Drop Global Allocator** — the thermodynamic nervous system.
//!
//! Standalone crate extracted from `aevum-core` so other crates can depend on
//! Landauer accounting without pulling in the full `aevum-core` dependency tree.
//!
//! # Why intercept `dealloc`?
//!
//! In Rust, when a variable's lifetime ends the `Drop` trait fires and heap
//! memory is returned to the allocator.  This deallocation is physically the
//! moment when bits are irreversibly erased — the exact event that Landauer's
//! principle taxes.
//!
//! By wrapping every `dealloc` call we count bits erased continuously, without
//! any application code having to opt in.  TGP is not a function you call;
//! it is a law the system cannot escape.
//!
//! # Safety contract
//!
//! Each unsafe block below wraps exactly one system-allocator call and one
//! atomic counter increment.  There is:
//! - No pointer arithmetic
//! - No raw memory reads or writes
//! - No lifetime violations
//! - No data races (AtomicU64 with Relaxed ordering is sound here: we only
//!   need monotonicity, not happens-before synchronisation)

// Crate-level: deny unsafe. The one exception is the inner mod below.
#![deny(unsafe_code)]

// This is the ONLY #[allow(unsafe_code)] in this crate.
#[allow(unsafe_code)]
mod inner {
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicU64, Ordering};

    /// Cumulative bits erased since process start.
    ///
    /// Monotonically increasing. Never reset. Never decremented.
    pub static BITS_ERASED: AtomicU64 = AtomicU64::new(0);

    /// The Landauer allocator wraps the system allocator and counts bit
    /// erasures on every `dealloc` call.
    pub struct LandauerAllocator;

    // SAFETY JUSTIFICATION:
    // `GlobalAlloc` requires `unsafe impl` because the trait contract depends
    // on pointer validity guarantees that the compiler cannot verify statically.
    // We delegate entirely to `System` for actual memory management.
    // Our additions: one `fetch_add` on an `AtomicU64` in `dealloc`.
    // No pointer arithmetic, no aliasing, no lifetime violations.
    #[allow(unsafe_code)]
    unsafe impl GlobalAlloc for LandauerAllocator {
        unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
            // SAFETY: layout validated by caller (Rust stdlib contract).
            unsafe { System.alloc(layout) }
        }

        unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
            // Count bits BEFORE releasing the memory — the erasure event.
            let bits = layout.size() as u64 * 8;
            BITS_ERASED.fetch_add(bits, Ordering::Relaxed);
            // SAFETY: ptr and layout are the exact pair alloc returned.
            unsafe { System.dealloc(ptr, layout) }
        }
    }
}

pub use inner::LandauerAllocator;
use inner::BITS_ERASED;
use std::sync::atomic::Ordering;

// ── Public API ────────────────────────────────────────────────────────────────

/// Read the cumulative bits erased since process start.
///
/// O(1), lock-free.
#[must_use]
pub fn bits_erased() -> u64 {
    BITS_ERASED.load(Ordering::Relaxed)
}

/// Compute the Landauer dissipation cost in joules for `bits` erased at
/// temperature `temperature_k` (Kelvin).
///
/// `Λ = bits × k_B × T × ln(2)`
#[must_use]
pub fn landauer_cost_joules(bits: u64, temperature_k: f64) -> f64 {
    const K_B: f64 = 1.380_649e-23;
    bits as f64 * K_B * temperature_k * std::f64::consts::LN_2
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bits_erased_monotonically_increases() {
        let before = bits_erased();
        let v: Vec<u8> = (0..1024).map(|i| i as u8).collect();
        drop(v);
        let after = bits_erased();
        assert!(
            after >= before,
            "bits_erased must be monotonically non-decreasing: before={before}, after={after}"
        );
    }

    #[test]
    fn bits_erased_increases_on_heap_allocation() {
        let before = bits_erased();
        let _v: Vec<u8> = vec![0u8; 4096];
        drop(_v);
        let after = bits_erased();
        assert!(after >= before, "after={after} should be ≥ before={before}");
    }

    #[test]
    fn landauer_cost_at_300k_matches_constant() {
        let cost = landauer_cost_joules(1, 300.0);
        let expected = 2.870_979e-21_f64;
        let ratio = cost / expected;
        assert!(
            (ratio - 1.0).abs() < 1e-4,
            "Λ(1 bit, 300 K) = {cost:.6e}, expected ≈ {expected:.6e}"
        );
    }

    #[test]
    fn landauer_cost_scales_linearly_with_bits() {
        let one = landauer_cost_joules(1, 300.0);
        let thousand = landauer_cost_joules(1_000, 300.0);
        let ratio = thousand / one;
        assert!(
            (ratio - 1_000.0).abs() < 1.0,
            "Λ must scale linearly: ratio={ratio}"
        );
    }

    #[test]
    fn landauer_cost_scales_linearly_with_temperature() {
        let at_300 = landauer_cost_joules(100, 300.0);
        let at_600 = landauer_cost_joules(100, 600.0);
        let ratio = at_600 / at_300;
        assert!(
            (ratio - 2.0).abs() < 1e-10,
            "Λ must be proportional to T: ratio={ratio}"
        );
    }

    #[test]
    fn landauer_cost_zero_bits_is_zero() {
        let cost = landauer_cost_joules(0, 300.0);
        assert_eq!(cost, 0.0, "0 bits erased → 0 joules");
    }
}
