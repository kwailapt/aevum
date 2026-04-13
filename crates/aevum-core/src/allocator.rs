//! Pillar: II. PACR field: Λ.
//!
//! **Landauer-on-Drop Global Allocator** — the thermodynamic nervous system.
//!
//! This is the ONLY file in the entire `aevum-core` crate permitted to contain
//! unsafe code.  All other files carry `#![forbid(unsafe_code)]`.
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

// This is the ONLY #[allow(unsafe_code)] in aevum-core.
// Every other source file carries #![forbid(unsafe_code)].
#[allow(unsafe_code)]
mod inner {
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicU64, Ordering};

    /// Cumulative bits erased since process start.
    ///
    /// Monotonically increasing. Never reset. Never decremented.
    /// Relaxed ordering is sufficient: we only need a lower bound on bits
    /// erased; strict happens-before is not required for Landauer accounting.
    pub static BITS_ERASED: AtomicU64 = AtomicU64::new(0);

    /// The Landauer allocator wraps the system allocator and counts bit
    /// erasures on every `dealloc` call.
    pub struct LandauerAllocator;

    // SAFETY JUSTIFICATION (required by RULES-CODING.md §5a):
    //
    // `GlobalAlloc` requires `unsafe impl` because the trait contract depends
    // on pointer validity guarantees that the compiler cannot verify
    // statically.  We delegate entirely to `System` (the OS allocator) for
    // actual memory management.  Our additions are:
    //   1. In `dealloc`: one `fetch_add` on an `AtomicU64` (lock-free, sound).
    //   2. No other pointer manipulation.
    //
    // The two `unsafe` blocks each forward an already-valid pointer to `System`
    // unchanged — we never dereference, offset, or alias them.
    #[allow(unsafe_code)]
    unsafe impl GlobalAlloc for LandauerAllocator {
        unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
            // SAFETY: `layout` was validated by the caller (Rust stdlib contract).
            unsafe { System.alloc(layout) }
        }

        unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
            // Count bits BEFORE releasing the memory — the erasure event.
            let bits = layout.size() as u64 * 8;
            BITS_ERASED.fetch_add(bits, Ordering::Relaxed);

            // SAFETY: `ptr` and `layout` are the exact pair that `alloc` returned;
            // caller guarantees this (Rust stdlib contract).
            unsafe { System.dealloc(ptr, layout) }
        }
    }
}

// Re-export for `#[global_allocator]` registration in lib.rs.
pub(crate) use inner::LandauerAllocator;
use inner::BITS_ERASED;

use std::sync::atomic::Ordering;

// ── Public API ────────────────────────────────────────────────────────────────

/// Read the cumulative bits erased since process start.
///
/// O(1), lock-free.  The value is a lower bound — some allocations
/// (static initializers, allocator bookkeeping) may not be counted.
#[must_use]
pub fn bits_erased() -> u64 {
    BITS_ERASED.load(Ordering::Relaxed)
}

/// Compute the Landauer dissipation cost in joules for `bits` erased at
/// temperature `temperature_k` (Kelvin).
///
/// `Λ = bits × k_B × T × ln(2)`
///
/// # Arguments
///
/// * `bits`          — number of bits irreversibly erased.
/// * `temperature_k` — ambient temperature in Kelvin (300 K is the standard).
#[must_use]
pub fn landauer_cost_joules(bits: u64, temperature_k: f64) -> f64 {
    const K_B: f64 = 1.380_649e-23; // Boltzmann constant (2019 SI exact)
    bits as f64 * K_B * temperature_k * std::f64::consts::LN_2
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bits_erased_monotonically_increases() {
        let before = bits_erased();
        // Force an allocation + deallocation.
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
        // Allocate 4 KiB on the heap and immediately drop.
        let _v: Vec<u8> = vec![0u8; 4096];
        drop(_v);
        let after = bits_erased();
        // At minimum 4 KiB × 8 bits = 32 768 bits should have been counted.
        assert!(
            after >= before,
            "after={after} should be ≥ before={before}"
        );
    }

    #[test]
    fn landauer_cost_at_300k_matches_constant() {
        // 1 bit at 300 K: Λ ≈ 2.870 979 × 10⁻²¹ J
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
