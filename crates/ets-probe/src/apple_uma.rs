//! Pillar: II. PACR field: Ω (space axis).
//!
//! M1 Ultra hardware probe for the space (S) axis of the resource triple.
//!
//! # Physical basis
//!
//! macOS does not expose `/proc/self/statm`.  Precise process RSS requires
//! the Mach `task_info()` kernel call, which involves unsafe FFI to the Mach
//! microkernel.  Because this crate carries `#![forbid(unsafe_code)]`, we
//! cannot call `task_info()` directly in this phase.
//!
//! # Current implementation
//!
//! Returns `None`, triggering the wide-CI fallback in the parent module.
//!
//! # Future work (Phase 2+)
//!
//! A separate `ets-probe-ffi` crate (with `#[deny(unsafe_code)]` and an
//! explicit per-block safety justification) will wrap `task_info()` to
//! provide a tight RSS measurement.  That crate will be compiled only when
//! `genesis_node` is active and will be a non-trust-root dependency.
//!
//! # Wide CI is acceptable; fabricated precision is not
//!
//! Per RULES-ARCHITECTURE.md §2: "Wide CI is OK; dishonest CI is FORBIDDEN."
//! Returning `None` here causes the parent to use a `[0.0, 1e12]` interval —
//! this is honest and correct.

/// Attempts to read process RSS (bytes) from the M1 Ultra (macOS) kernel.
///
/// Always returns `None` in this phase (see module-level documentation).
/// The parent module will apply the honest wide-CI fallback.
#[must_use]
#[cfg(feature = "genesis_node")]
pub fn sample_rss_bytes() -> Option<f64> {
    // TODO (Phase 2+): call mach_task_self() / task_info() via ets-probe-ffi.
    None
}
