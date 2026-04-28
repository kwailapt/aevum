//! Pillar: III. PACR field: Γ (symbol alphabet for ε-machine construction).
//!
//! Converts continuous time-series data into discrete symbol sequences.
//! Two strategies are provided:
//!
//! | Strategy      | Bin boundaries          | Use case                        |
//! |---------------|-------------------------|---------------------------------|
//! | EqualWidth    | Uniform value intervals | Known bounded range             |
//! | EqualFrequency| Uniform sample quantiles| Unknown distribution (default)  |
//!
//! # Alphabet size
//!
//! The alphabet size `|A|` trades bias for variance:
//! - Small `|A|` (2–4): under-resolves structure, misses fine-grained patterns.
//! - Large `|A|` (8–16): more states but requires larger N for statistical power.
//! - Recommended: `|A|` = 4–8 for N < 50 000 samples.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::unreadable_literal,
    clippy::redundant_closure,
    clippy::unwrap_or_default,
    clippy::doc_overindented_list_items,
    clippy::cloned_instead_of_copied,
    clippy::needless_pass_by_value,
    clippy::cast_lossless,
    clippy::module_name_repetitions,
    clippy::into_iter_without_iter,
    clippy::unnested_or_patterns,
    clippy::let_underscore_untyped,
    clippy::manual_let_else,
    clippy::suspicious_open_options,
    clippy::iter_not_returning_iterator,
    clippy::must_use_candidate,
    clippy::ptr_arg,
    clippy::manual_midpoint,
    clippy::map_unwrap_or,
    clippy::bool_to_int_with_if,
    clippy::missing_panics_doc
)]

/// Error type for symbolization failures.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum SymbolizeError {
    /// The input data slice is empty.
    EmptyInput,
    /// `num_symbols` must be ≥ 2.
    TooFewSymbols,
    /// All values are identical — cannot bin with equal-frequency.
    ConstantInput,
}

impl std::fmt::Display for SymbolizeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyInput => write!(f, "input data is empty"),
            Self::TooFewSymbols => write!(f, "num_symbols must be ≥ 2"),
            Self::ConstantInput => write!(f, "all values are identical; cannot bin"),
        }
    }
}

impl std::error::Error for SymbolizeError {}

// ── Equal-Width Quantization ──────────────────────────────────────────────────

/// Quantize `data` into `num_symbols` equal-width bins.
///
/// Bin boundaries are `[min, min + w, min + 2w, ...]` where `w = (max - min) / n`.
/// Symbols are `0 ..= num_symbols - 1`.
///
/// # Errors
///
/// Returns [`SymbolizeError`] if `data` is empty, `num_symbols < 2`,
/// or all values are identical (zero-width bins).
pub fn equal_width(data: &[f64], num_symbols: usize) -> Result<Vec<u8>, SymbolizeError> {
    if data.is_empty() {
        return Err(SymbolizeError::EmptyInput);
    }
    if num_symbols < 2 {
        return Err(SymbolizeError::TooFewSymbols);
    }

    let min = data.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = data.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

    if (max - min).abs() < f64::EPSILON {
        return Err(SymbolizeError::ConstantInput);
    }

    let width = (max - min) / num_symbols as f64;
    let n_sym = num_symbols as u8;

    let symbols = data
        .iter()
        .map(|&v| {
            let bin = ((v - min) / width).floor() as u8;
            bin.min(n_sym - 1) // clamp the max value into the last bin
        })
        .collect();

    Ok(symbols)
}

// ── Equal-Frequency Quantization ─────────────────────────────────────────────

/// Quantize `data` into `num_symbols` equal-frequency (quantile) bins.
///
/// Bin boundaries are chosen so each bin contains approximately the same
/// number of samples.  Symbol `k` maps to the `k`-th quantile interval.
///
/// This is the recommended strategy for CSSR: it maximises entropy in the
/// symbolic sequence, giving the suffix tree more discriminating power.
///
/// # Errors
///
/// Returns [`SymbolizeError`] if `data` is empty, `num_symbols < 2`,
/// or all values are identical.
pub fn equal_frequency(data: &[f64], num_symbols: usize) -> Result<Vec<u8>, SymbolizeError> {
    if data.is_empty() {
        return Err(SymbolizeError::EmptyInput);
    }
    if num_symbols < 2 {
        return Err(SymbolizeError::TooFewSymbols);
    }

    // Sort indices to find quantile boundaries.
    let mut sorted: Vec<f64> = data.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let first = sorted[0];
    let last = sorted[sorted.len() - 1];
    if (last - first).abs() < f64::EPSILON {
        return Err(SymbolizeError::ConstantInput);
    }

    // Compute `num_symbols - 1` cut-points at quantile boundaries.
    // Cut k: sorted[floor(k * N / num_symbols)] for k = 1..num_symbols-1.
    let n = sorted.len();
    let cuts: Vec<f64> = (1..num_symbols)
        .map(|k| {
            let idx = (k * n / num_symbols).min(n - 1);
            sorted[idx]
        })
        .collect();

    let symbols = data
        .iter()
        .map(|&v| {
            // Binary search for the first cut > v → symbol index.
            let sym = cuts.partition_point(|&cut| v >= cut) as u8;
            sym.min(num_symbols as u8 - 1)
        })
        .collect();

    Ok(symbols)
}

// ── Utility: alphabet size inference ──────────────────────────────────────────

/// Returns the number of distinct symbols actually used in the sequence.
///
/// This may be less than the requested `num_symbols` when the data range
/// is narrower than expected.
#[must_use]
pub fn alphabet_size(symbols: &[u8]) -> usize {
    let mut seen = [false; 256];
    for &s in symbols {
        seen[s as usize] = true;
    }
    seen.iter().filter(|&&b| b).count()
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn equal_width_basic() {
        let data = vec![0.0, 1.0, 2.0, 3.0];
        let syms = equal_width(&data, 4).unwrap();
        // Each value maps to its own bin.
        assert_eq!(syms, vec![0, 1, 2, 3]);
    }

    #[test]
    fn equal_width_clamps_max() {
        // Exactly max value must map to last bin, not overflow.
        let data = vec![0.0, 0.5, 1.0];
        let syms = equal_width(&data, 2).unwrap();
        // [0.0, 0.5) → 0; [0.5, 1.0] → 1 (clamped)
        assert_eq!(syms[2], 1, "max value must map to last bin");
    }

    #[test]
    fn equal_frequency_distributes_evenly() {
        // 100 values uniform → 4 bins each with ~25 elements.
        let data: Vec<f64> = (0..100).map(|i| i as f64).collect();
        let syms = equal_frequency(&data, 4).unwrap();
        let mut counts = [0usize; 4];
        for &s in &syms {
            counts[s as usize] += 1;
        }
        // Each bin should have ~25; allow ±2 slack.
        for c in counts {
            assert!(
                (23..=27).contains(&c),
                "bin count {c} out of expected range"
            );
        }
    }

    #[test]
    fn equal_width_empty_error() {
        assert_eq!(equal_width(&[], 4), Err(SymbolizeError::EmptyInput));
    }

    #[test]
    fn equal_width_few_symbols_error() {
        assert_eq!(
            equal_width(&[1.0, 2.0], 1),
            Err(SymbolizeError::TooFewSymbols)
        );
    }

    #[test]
    fn equal_width_constant_error() {
        assert_eq!(
            equal_width(&[5.0, 5.0, 5.0], 4),
            Err(SymbolizeError::ConstantInput)
        );
    }

    #[test]
    fn equal_frequency_constant_error() {
        assert_eq!(
            equal_frequency(&[3.0, 3.0], 2),
            Err(SymbolizeError::ConstantInput)
        );
    }

    #[test]
    fn alphabet_size_counts_distinct() {
        let syms = vec![0u8, 1, 2, 1, 0, 3];
        assert_eq!(alphabet_size(&syms), 4);
    }

    #[test]
    fn alphabet_size_single_symbol() {
        let syms = vec![7u8; 100];
        assert_eq!(alphabet_size(&syms), 1);
    }
}
