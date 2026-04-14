//! Pillar: III. PACR field: Γ.
//!
//! O(1) Shannon entropy pre-filter for ε-machine inference.
//!
//! Before running the full CSSR pipeline (which is O(N × L)) this screen
//! computes H(X) from a 256-bucket byte frequency table in a single pass.
//! If H(X) is below a configurable threshold the data is near-deterministic
//! and CSSR would return a trivial single-state machine — skip it.
//!
//! # Why O(1)?
//!
//! The frequency table has exactly 256 buckets regardless of input length N.
//! One pass over the data fills the table; entropy is computed from the 256
//! non-zero buckets.  Both operations are O(N) in data length but O(1) in
//! alphabet size (bounded constant 256).  The "O(1)" claim in the spec refers
//! to the constant-bounded alphabet work, not to skipping the data pass.
//!
//! # Usage
//!
//! ```
//! use epsilon_engine::quick_screen::{quick_screen, ScreenResult};
//!
//! let data = vec![0u8; 1000]; // constant → H(X) = 0 → Skip
//! let result = quick_screen(&data, 0.5);
//! assert!(matches!(result, ScreenResult::Skip { .. }));
//!
//! let mixed: Vec<u8> = (0u8..=255).cycle().take(1024).collect();
//! let result2 = quick_screen(&mixed, 0.5);
//! assert!(matches!(result2, ScreenResult::Proceed { .. }));
//! ```

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

// ── ScreenResult ──────────────────────────────────────────────────────────────

/// Result of the quick-screen entropy pre-filter.
#[derive(Debug, Clone, PartialEq)]
pub enum ScreenResult {
    /// H(X) is below `threshold` — data is near-deterministic.
    /// CSSR would return a trivial 1-state machine; skip it.
    Skip {
        /// Human-readable reason.
        reason: &'static str,
        /// Measured H(X) in bits.
        entropy_bits: f64,
    },
    /// H(X) is at or above `threshold` — proceed to full CSSR inference.
    Proceed {
        /// Measured H(X) in bits.
        entropy_bits: f64,
    },
}

impl ScreenResult {
    /// Returns `true` when this result is [`Skip`](ScreenResult::Skip).
    #[must_use]
    pub fn is_skip(&self) -> bool {
        matches!(self, Self::Skip { .. })
    }

    /// Returns the measured entropy in bits regardless of variant.
    #[must_use]
    pub fn entropy_bits(&self) -> f64 {
        match *self {
            Self::Skip { entropy_bits, .. } | Self::Proceed { entropy_bits } => entropy_bits,
        }
    }
}

// ── quick_screen ──────────────────────────────────────────────────────────────

/// Run the Shannon entropy pre-filter on `data`.
///
/// Builds a 256-bucket byte frequency table in one pass, computes H(X), and
/// compares against `threshold` (bits).
///
/// # Arguments
///
/// * `data`      — raw byte slice.  Empty input yields H(X) = 0.0 → Skip.
/// * `threshold` — entropy threshold in bits.  Values below this trigger Skip.
///   A threshold of `0.0` means only completely constant streams are skipped.
///
/// # Complexity
///
/// O(N) in input length; O(1) in alphabet size (fixed 256 buckets).
#[must_use]
pub fn quick_screen(data: &[u8], threshold: f64) -> ScreenResult {
    let entropy_bits = byte_entropy(data);
    if entropy_bits < threshold {
        ScreenResult::Skip { reason: "near-deterministic", entropy_bits }
    } else {
        ScreenResult::Proceed { entropy_bits }
    }
}

// ── Internal ──────────────────────────────────────────────────────────────────

/// Compute Shannon entropy H(X) of the byte distribution in `data`, in bits.
///
/// Uses a 256-entry frequency table.  Returns 0.0 for empty input.
#[must_use]
pub(crate) fn byte_entropy(data: &[u8]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    let mut freq = [0u64; 256];
    for &b in data {
        freq[b as usize] += 1;
    }
    let n = data.len() as f64;
    freq.iter()
        .filter(|&&c| c > 0)
        .map(|&c| {
            let p = c as f64 / n;
            -p * p.log2()
        })
        .sum()
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_stream_is_skipped() {
        let data = vec![42u8; 1000];
        let r = quick_screen(&data, 0.5);
        assert!(r.is_skip(), "constant stream must be skipped");
        assert!((r.entropy_bits() - 0.0).abs() < 1e-10);
    }

    #[test]
    fn uniform_byte_stream_proceeds() {
        // All 256 values equally frequent → H(X) = 8 bits.
        let data: Vec<u8> = (0u8..=255).cycle().take(2048).collect();
        let r = quick_screen(&data, 0.5);
        assert!(!r.is_skip(), "uniform stream must proceed");
        assert!((r.entropy_bits() - 8.0).abs() < 0.01);
    }

    #[test]
    fn empty_input_is_skipped() {
        let r = quick_screen(&[], 0.5);
        assert!(r.is_skip());
        assert_eq!(r.entropy_bits(), 0.0);
    }

    #[test]
    fn zero_threshold_only_skips_constant() {
        let data = vec![0u8; 100];
        assert!(quick_screen(&data, 0.0).is_skip());

        // Any non-trivial data should proceed at threshold=0.0.
        let data2 = vec![0u8, 1u8, 0u8, 1u8];
        assert!(!quick_screen(&data2, 0.0).is_skip());
    }

    #[test]
    fn binary_alternating_entropy_is_one_bit() {
        let data: Vec<u8> = (0u8..2).cycle().take(1000).collect();
        let h = byte_entropy(&data);
        assert!((h - 1.0).abs() < 0.01, "H([0,1]) = 1 bit, got {h}");
    }

    #[test]
    fn entropy_bits_accessor_consistent() {
        let data: Vec<u8> = (0u8..=255).cycle().take(512).collect();
        let r = quick_screen(&data, 4.0);
        let h = byte_entropy(&data);
        assert!((r.entropy_bits() - h).abs() < 1e-10);
    }

    #[test]
    fn screen_result_is_skip_helper() {
        let skip = ScreenResult::Skip { reason: "near-deterministic", entropy_bits: 0.1 };
        let proceed = ScreenResult::Proceed { entropy_bits: 5.0 };
        assert!(skip.is_skip());
        assert!(!proceed.is_skip());
    }
}
