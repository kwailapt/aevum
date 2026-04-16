//! Pillar: II. PACR field: Ω (space axis).
//!
//! Linux perf probe for the space (S) axis of the resource triple.
//!
//! # Physical basis
//!
//! On Linux, `/proc/self/statm` exposes the kernel's page-granular
//! accounting of this process's resident set size (RSS) — the number of
//! physical RAM pages currently mapped.  Multiplied by the system page size
//! (4 096 bytes on x86-64 and ARM64 / AWS c7g), this gives the process's
//! current physical memory footprint.
//!
//! RSS is the "space" axis because it measures actual physical memory
//! consumed, not virtual address space (which can be arbitrarily large).
//!
//! # Precision and uncertainty
//!
//! `/proc/self/statm` has page granularity (4 096 B).  We model the
//! uncertainty as ±1 page (the measurement could be one page off due to
//! concurrent allocations during the read syscall).
//!
//! If the file is unavailable (container restrictions, non-Linux kernel),
//! returns `None` → parent module applies the wide-CI fallback.

const PAGE_BYTES: f64 = 4_096.0; // 4 KiB page, Linux ARM64 / x86-64

/// Reads process RSS (bytes) from `/proc/self/statm`.
///
/// Returns `None` if the file is unavailable or unparseable.
///
/// # Format
///
/// `/proc/self/statm`: space-separated integers representing page counts.
/// Column layout: `total_vm rss shared text lib data dt`
/// We read only column 1 (index 0 = total_vm, index 1 = rss).
#[must_use]
#[cfg(feature = "light_node")]
pub fn sample_rss_bytes() -> Option<f64> {
    let contents = std::fs::read_to_string("/proc/self/statm").ok()?;
    let rss_pages: u64 = contents
        .split_whitespace()
        .nth(1)? // column index 1 = RSS pages
        .parse()
        .ok()?;
    Some(rss_pages as f64 * PAGE_BYTES)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(all(test, feature = "light_node"))]
mod tests {
    use super::*;

    #[test]
    fn sample_rss_bytes_returns_positive_on_linux() {
        // On a real Linux host this should always succeed and return > 0.
        if let Some(rss) = sample_rss_bytes() {
            assert!(rss > 0.0, "RSS must be > 0 for a live process");
        }
        // On non-Linux or restricted environments: None is acceptable.
    }
}
