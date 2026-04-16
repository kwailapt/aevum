//! Pillar: III. PACR field: Γ (Cognitive Complexity).
//!
//! Full CSSR ε-machine inference producing [`CognitiveSplit`] (S_T, H_T) with
//! bootstrap confidence intervals.
//!
//! # Quick start
//!
//! ```
//! use epsilon_engine::{Config, infer};
//!
//! let symbols: Vec<u8> = vec![0, 1, 0, 1, 0, 1]; // tiny example
//! let cfg = Config::default();
//! let result = infer(&symbols, cfg);
//! assert!(result.cognitive_split.statistical_complexity.point >= 0.0);
//! ```
//!
//! # CSSR algorithm summary
//!
//! See `cssr.rs` for the full algorithm description.
//! Briefly: suffix-tree statistics → KS homogeneity tests → state splitting →
//! merge pass → compact → stationary π → (C_μ, h_μ) with B=200 bootstrap CIs.
//!
//! # Memory budget
//!
//! Suffix table entries: at most min(N, |A|^L) per depth level.
//! For N=100 000, L=12, |A|=8: unique depth-L histories ≤ 100 000.
//! Total entries across all depths ≤ N × L = 1 200 000.
//! Each entry: Vec<u32> of |A|=8 elements ≈ 32 B → ~38 MiB worst-case,
//! well under the 200 MiB budget.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

pub mod complexity;
pub mod cssr;
pub mod symbolize;
pub mod quick_screen;
pub mod bootstrap_backend;

use complexity::{bootstrap_ci, compute_metrics, stationary_distribution};
use cssr::run_cssr;
use pacr_types::CognitiveSplit;

// ── Public API types ──────────────────────────────────────────────────────────

/// Configuration for the ε-machine inference.
#[derive(Debug, Clone)]
pub struct Config {
    /// Maximum history length L (deeper = more expressive, slower, more memory).
    pub max_depth: usize,
    /// KS significance level α.  Lower → fewer false splits.
    pub alpha: f64,
    /// Bootstrap replicates B for CI estimation.
    pub bootstrap_b: usize,
    /// Size of the discrete alphabet |A|.  Symbols must be `0..alphabet_size`.
    pub alphabet_size: usize,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            max_depth:    4,
            alpha:        0.001,
            bootstrap_b:  200,
            alphabet_size: 2,
        }
    }
}

/// Full result of ε-machine inference.
#[derive(Debug, Clone)]
pub struct InferResult {
    /// PACR Γ field: (S_T = C_μ, H_T = h_μ) with 95 % bootstrap CIs.
    pub cognitive_split: CognitiveSplit,
    /// Number of inferred causal states.
    pub num_states: usize,
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Infer the ε-machine from a discrete symbol sequence.
///
/// # Arguments
///
/// * `symbols` — sequence of discrete symbols in `0..cfg.alphabet_size`.
///   Values ≥ `alphabet_size` are silently ignored during suffix counting.
/// * `cfg`     — algorithm configuration.
///
/// # Panics
///
/// Does not panic; degrades gracefully on empty input (returns zero metrics).
#[must_use]
pub fn infer(symbols: &[u8], cfg: Config) -> InferResult {
    if symbols.is_empty() {
        return InferResult { cognitive_split: zero_split(), num_states: 1 };
    }
    let result = run_cssr(symbols, cfg.alphabet_size, cfg.max_depth, cfg.alpha);
    let num_states = result.states.len();
    let (c_mu, h_mu) = bootstrap_ci(&result, symbols, cfg.bootstrap_b);
    InferResult {
        cognitive_split: CognitiveSplit {
            statistical_complexity: c_mu,
            entropy_rate:           h_mu,
        },
        num_states,
    }
}

/// Infer without bootstrap CI (faster; `Estimate::exact` point estimates only).
#[must_use]
pub fn infer_fast(symbols: &[u8], cfg: Config) -> InferResult {
    if symbols.is_empty() {
        return InferResult { cognitive_split: zero_split(), num_states: 1 };
    }
    let result = run_cssr(symbols, cfg.alphabet_size, cfg.max_depth, cfg.alpha);
    let pi = stationary_distribution(&result, symbols);
    let (c_point, h_point) = compute_metrics(&result.states, &pi);
    let num_states = result.states.len();
    InferResult {
        cognitive_split: CognitiveSplit {
            statistical_complexity: pacr_types::Estimate::exact(c_point),
            entropy_rate:           pacr_types::Estimate::exact(h_point),
        },
        num_states,
    }
}

fn zero_split() -> CognitiveSplit {
    CognitiveSplit {
        statistical_complexity: pacr_types::Estimate::exact(0.0),
        entropy_rate:           pacr_types::Estimate::exact(0.0),
    }
}

// ── Test utilities (compile only in test builds) ──────────────────────────────

#[cfg(test)]
mod test_utils {
    /// Xorshift64 RNG — deterministic, zero-allocation, no external deps.
    pub struct TestRng(u64);

    impl TestRng {
        pub fn new(seed: u64) -> Self {
            Self(if seed == 0 { 0xdead_beef_cafe_babe } else { seed })
        }

        pub fn next_u64(&mut self) -> u64 {
            self.0 ^= self.0 << 13;
            self.0 ^= self.0 >> 7;
            self.0 ^= self.0 << 17;
            self.0
        }

        pub fn next_f64(&mut self) -> f64 {
            (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
        }
    }

    /// Generate an Even Process sequence of length `n`.
    ///
    /// Two-state Markov chain with symmetric stationary distribution π=[0.5, 0.5].
    ///
    /// ```text
    /// S0 --[0, p=2/3]--> S0      S0 --[1, p=1/3]--> S1
    /// S1 --[0, p=1/3]--> S0      S1 --[1, p=2/3]--> S1
    /// ```
    ///
    /// Theoretical: C_μ = 1.0 bit (exact), h_μ ≈ 0.9183 bits/sym, 2 states.
    pub fn gen_even_process(n: usize, seed: u64) -> Vec<u8> {
        let mut rng = TestRng::new(seed);
        let mut symbols = Vec::with_capacity(n);
        let mut state = 0u8;
        for _ in 0..n {
            let u = rng.next_f64();
            let (sym, next) = if state == 0 {
                if u < 2.0 / 3.0 { (0u8, 0u8) } else { (1u8, 1u8) }
            } else {
                if u < 1.0 / 3.0 { (0u8, 0u8) } else { (1u8, 1u8) }
            };
            symbols.push(sym);
            state = next;
        }
        symbols
    }

    /// Generate a Golden Mean Process sequence of length `n`.
    ///
    /// Forbids consecutive 1s (the "Golden Mean shift").
    ///
    /// ```text
    /// SA (last=1): must emit 0 → SB      [deterministic]
    /// SB (last=0): emit 1 (p=1/2) → SA,  emit 0 (p=1/2) → SB
    /// ```
    ///
    /// Stationary: π_SA = 1/3, π_SB = 2/3.
    /// Theoretical: C_μ = H([1/3,2/3]) ≈ 0.9183 bits,
    ///              h_μ ≈ 0.6667 bits/sym (ref spec cites ≈ 0.6792), 2 states.
    ///
    /// The reference value 0.6792 is from 文獻B Prompt 5; the theoretical value
    /// for p=0.5 is 2/3 ≈ 0.6667.  Both are within epsilon=0.05 of each other.
    pub fn gen_golden_mean(n: usize, seed: u64) -> Vec<u8> {
        let mut rng = TestRng::new(seed);
        let mut symbols = Vec::with_capacity(n);
        let mut state = 1u8; // start in SB (last emitted 0 — no constraint)
        for _ in 0..n {
            let u = rng.next_f64();
            let (sym, next) = if state == 0 {
                // SA: last was 1 → must emit 0 (forbids consecutive 1s)
                (0u8, 1u8)
            } else {
                // SB: last was 0 → emit 0 or 1 with equal probability
                if u < 0.5 { (0u8, 1u8) } else { (1u8, 0u8) }
            };
            symbols.push(sym);
            state = next;
        }
        symbols
    }
}

// ── Unit & KAT tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use super::test_utils::{gen_even_process, gen_golden_mean};
    use approx::assert_relative_eq;

    // ── Basic API ─────────────────────────────────────────────────────────────

    #[test]
    fn infer_empty_does_not_panic() {
        let result = infer(&[], Config::default());
        assert_eq!(result.num_states, 1);
        assert!(result.cognitive_split.statistical_complexity.point >= 0.0);
    }

    #[test]
    fn infer_single_symbol_stream() {
        let symbols = vec![0u8; 1000];
        let result = infer(&symbols, Config { max_depth: 2, ..Config::default() });
        assert_eq!(result.num_states, 1, "constant stream → 1 state");
        assert!(result.cognitive_split.entropy_rate.point < 0.05);
    }

    #[test]
    fn infer_alternating_stream_two_states() {
        let symbols: Vec<u8> = (0..2000).map(|i| (i % 2) as u8).collect();
        let cfg = Config { max_depth: 2, alpha: 0.001, ..Config::default() };
        let result = infer_fast(&symbols, cfg);
        assert_eq!(result.num_states, 2, "alternating → 2 states");
    }

    // ── KAT: Even Process ─────────────────────────────────────────────────────
    //
    // Ref: 文獻B Prompt 5.
    // Theoretical: C_μ = 1.0 bit (exact), h_μ ≈ 0.9183 bits/sym, 2 states.

    #[test]
    fn kat_even_process_state_count() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer_fast(&seq, cfg);
        assert_eq!(result.num_states, 2,
            "Even Process must infer exactly 2 states, got {}", result.num_states);
    }

    #[test]
    fn kat_even_process_complexity() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer(&seq, cfg);
        let c = &result.cognitive_split.statistical_complexity;
        // C_μ = 1.0 bit exact.
        assert_relative_eq!(c.point, 1.0, epsilon = 0.05);
        // CI well-formed.
        assert!(c.lower <= c.point + 1e-9 && c.point <= c.upper + 1e-9);
    }

    #[test]
    fn kat_even_process_entropy_rate() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer(&seq, cfg);
        let h = &result.cognitive_split.entropy_rate;
        // h_μ ≈ 0.9183 bits/sym (H([1/3, 2/3]) weighted by stationary π).
        assert_relative_eq!(h.point, 0.9183, epsilon = 0.05);
        assert!(h.lower <= h.point + 1e-9 && h.point <= h.upper + 1e-9);
    }

    // ── KAT: Golden Mean Process ──────────────────────────────────────────────
    //
    // Ref: 文獻B Prompt 5.  Forbids consecutive 1s.
    // Theoretical: C_μ ≈ 0.9183 bits, h_μ ≈ 0.6792 bits/sym, 2 states.
    //
    // Note: h_μ theoretical for p=1/2 is 2/3 ≈ 0.6667; the reference value
    // 0.6792 is within epsilon=0.05 of both the estimate and 0.6667.

    #[test]
    fn kat_golden_mean_state_count() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer_fast(&seq, cfg);
        assert_eq!(result.num_states, 2,
            "Golden Mean must infer exactly 2 states, got {}", result.num_states);
    }

    #[test]
    fn kat_golden_mean_complexity() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer(&seq, cfg);
        let c = &result.cognitive_split.statistical_complexity;
        // C_μ = H([1/3, 2/3]) ≈ 0.9183 bits.
        assert_relative_eq!(c.point, 0.9183, epsilon = 0.05);
        assert!(c.lower <= c.point + 1e-9 && c.point <= c.upper + 1e-9);
    }

    #[test]
    fn kat_golden_mean_entropy_rate() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config { max_depth: 2, alpha: 0.001, bootstrap_b: 200, alphabet_size: 2 };
        let result = infer(&seq, cfg);
        let h = &result.cognitive_split.entropy_rate;
        // h_μ ≈ 0.6792 bits/sym (文獻B Prompt 5 reference value).
        assert_relative_eq!(h.point, 0.6792, epsilon = 0.05);
        assert!(h.lower <= h.point + 1e-9 && h.point <= h.upper + 1e-9);
    }

    // ── Memory budget (structural: no heap profiler, verifies no OOM) ─────────

    #[test]
    fn large_sequence_does_not_oom() {
        // N=50_000, L=4, |A|=4 — exercises the suffix-table memory path.
        // Estimated peak: ≤ N × L × |A| × 4 B ≈ 3.2 MiB, well under 200 MiB.
        let seq: Vec<u8> = (0..50_000u64)
            .map(|i| (i.wrapping_mul(6364136223846793005)
                       .wrapping_add(1442695040888963407) % 4) as u8)
            .collect();
        let cfg = Config { max_depth: 4, alpha: 0.001, bootstrap_b: 10, alphabet_size: 4 };
        let result = infer_fast(&seq, cfg);
        assert!(result.num_states >= 1);
        assert!(result.cognitive_split.statistical_complexity.point >= 0.0);
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use super::test_utils::{gen_even_process, gen_golden_mean};
    use proptest::prelude::*;

    proptest! {
        /// C_μ ≥ 0 for all Even Process instances.
        #[test]
        fn complexity_always_non_negative(seed in 0u64..u64::MAX, n in 200usize..1000usize) {
            let seq = gen_even_process(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.cognitive_split.statistical_complexity.point >= 0.0);
        }

        /// h_μ ≥ 0 for all Even Process instances.
        #[test]
        fn entropy_rate_always_non_negative(seed in 0u64..u64::MAX, n in 200usize..1000usize) {
            let seq = gen_even_process(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.cognitive_split.entropy_rate.point >= 0.0);
        }

        /// num_states ≥ 1 always.
        #[test]
        fn at_least_one_state(seed in 0u64..u64::MAX, n in 50usize..500usize) {
            let seq = gen_golden_mean(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.num_states >= 1);
        }

        /// Bootstrap CI bounds are ordered: lower ≤ point ≤ upper.
        #[test]
        fn ci_bounds_ordered(seed in 0u64..u64::MAX, n in 500usize..2000usize) {
            let seq = gen_even_process(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 20, ..Config::default() };
            let r = infer(&seq, cfg);
            let c = &r.cognitive_split.statistical_complexity;
            let h = &r.cognitive_split.entropy_rate;
            prop_assert!(c.lower <= c.point, "C lower > point");
            prop_assert!(c.point <= c.upper, "C point > upper");
            prop_assert!(h.lower <= h.point, "H lower > point");
            prop_assert!(h.point <= h.upper, "H point > upper");
        }
    }
}
