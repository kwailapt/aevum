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
//! See `cssr.rs` module documentation for the full algorithm description.
//! Briefly: suffix-tree statistics → KS homogeneity tests → state splitting →
//! merge pass → compact → stationary π → (C_μ, h_μ) with bootstrap CIs.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

pub mod complexity;
pub mod cssr;
pub mod symbolize;

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
            max_depth: 4,
            alpha: 0.001,
            bootstrap_b: 200,
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
/// # Returns
///
/// [`InferResult`] with the inferred [`CognitiveSplit`] and state count.
///
/// # Panics
///
/// Does not panic; degrades gracefully on empty input (returns zero metrics).
#[must_use]
pub fn infer(symbols: &[u8], cfg: Config) -> InferResult {
    if symbols.is_empty() {
        return InferResult {
            cognitive_split: zero_split(),
            num_states: 1,
        };
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

/// Infer without bootstrap CI (faster; returns only point estimates).
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

// ── Minimal test RNG (no external deps) ──────────────────────────────────────

/// Xorshift64 used only in tests/KATs — not part of the public API.
struct TestRng(u64);

impl TestRng {
    fn new(seed: u64) -> Self {
        Self(if seed == 0 { 0xdeadbeef_cafebabe } else { seed })
    }

    fn next_u64(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }

    fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
}

// ── Test sequence generators ──────────────────────────────────────────────────

/// Generate an Even Process sequence of length `n`.
///
/// State-machine:
/// ```text
/// S0 --[0, p=2/3]--> S0
/// S0 --[1, p=1/3]--> S1
/// S1 --[0, p=1/3]--> S0
/// S1 --[1, p=2/3]--> S1
/// ```
/// Theoretical values: C_μ = 1.0 bit, h_μ ≈ 0.9183 bits/sym, 2 states.
///
/// The transition probabilities are chosen so that the stationary distribution
/// is exactly [0.5, 0.5] → C_μ = H([0.5, 0.5]) = 1.0 bit.
fn gen_even_process(n: usize, seed: u64) -> Vec<u8> {
    let mut rng = TestRng::new(seed);
    let mut symbols = Vec::with_capacity(n);
    let mut state = 0u8; // 0 or 1
    for _ in 0..n {
        let u = rng.next_f64();
        let (sym, next_state) = if state == 0 {
            // From S0: emit 0 (p=2/3) → S0, emit 1 (p=1/3) → S1
            if u < 2.0 / 3.0 { (0u8, 0u8) } else { (1u8, 1u8) }
        } else {
            // From S1: emit 0 (p=1/3) → S0, emit 1 (p=2/3) → S1
            if u < 1.0 / 3.0 { (0u8, 0u8) } else { (1u8, 1u8) }
        };
        symbols.push(sym);
        state = next_state;
    }
    symbols
}

/// Generate a Golden Mean Process sequence of length `n`.
///
/// State-machine (forbids consecutive 0s):
/// ```text
/// S0 (last was 0): must emit 1 → S1
/// S1 (last was 1): emit 0 (p=1/2) → S0, emit 1 (p=1/2) → S1
/// ```
/// Stationary: π_S0 = 1/3, π_S1 = 2/3.
/// Theoretical: C_μ = H([1/3, 2/3]) ≈ 0.9183 bits, h_μ ≈ 0.6667 bits/sym, 2 states.
fn gen_golden_mean(n: usize, seed: u64) -> Vec<u8> {
    let mut rng = TestRng::new(seed);
    let mut symbols = Vec::with_capacity(n);
    let mut state = 1u8; // start in S1 (last emitted 1)
    for _ in 0..n {
        let u = rng.next_f64();
        let (sym, next_state) = if state == 0 {
            // Must emit 1
            (1u8, 1u8)
        } else {
            // Emit 0 (p=1/2) → S0, or 1 (p=1/2) → S1
            if u < 0.5 { (0u8, 0u8) } else { (1u8, 1u8) }
        };
        symbols.push(sym);
        state = next_state;
    }
    symbols
}

// ── Unit & KAT tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

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
        // Deterministic stream → 1 state, h_μ ≈ 0
        assert_eq!(result.num_states, 1, "constant stream → 1 state");
        assert!(result.cognitive_split.entropy_rate.point < 0.05);
    }

    #[test]
    fn infer_alternating_stream_two_states() {
        // Perfectly alternating 010101... → 2 states.
        let symbols: Vec<u8> = (0..2000).map(|i| (i % 2) as u8).collect();
        let cfg = Config { max_depth: 2, alpha: 0.001, ..Config::default() };
        let result = infer_fast(&symbols, cfg);
        assert_eq!(result.num_states, 2, "alternating → 2 states");
    }

    // ── KAT: Even Process ─────────────────────────────────────────────────────
    //
    // Theoretical: C_μ = 1.0 bit (exact), h_μ ≈ 0.9183 bits/sym, 2 states.

    #[test]
    fn kat_even_process_state_count() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer_fast(&seq, cfg);
        assert_eq!(
            result.num_states, 2,
            "Even Process must infer exactly 2 states, got {}",
            result.num_states
        );
    }

    #[test]
    fn kat_even_process_complexity() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer(&seq, cfg);
        let c = result.cognitive_split.statistical_complexity;
        // True C_μ = 1.0 bit; allow ±0.08 for N=10 000 sampling noise.
        assert!(
            (c.point - 1.0).abs() < 0.08,
            "Even Process C_μ point estimate {:.4} not close to 1.0",
            c.point
        );
        // CI must be well-formed (lower ≤ point ≤ upper).
        assert!(c.lower <= c.point + 1e-9, "C_μ: lower > point");
        assert!(c.point <= c.upper + 1e-9, "C_μ: point > upper");
    }

    #[test]
    fn kat_even_process_entropy_rate() {
        let seq = gen_even_process(10_000, 42);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer(&seq, cfg);
        let h = result.cognitive_split.entropy_rate;
        // True h_μ ≈ 0.9183; allow ±0.08.
        assert!(
            (h.point - 0.9183).abs() < 0.08,
            "Even Process h_μ {:.4} not close to 0.9183",
            h.point
        );
        assert!(h.lower <= h.point + 1e-9, "h_μ: lower > point");
        assert!(h.point <= h.upper + 1e-9, "h_μ: point > upper");
    }

    // ── KAT: Golden Mean Process ──────────────────────────────────────────────
    //
    // Theoretical: C_μ = H([1/3,2/3]) ≈ 0.9183 bits, h_μ ≈ 0.6667 bits/sym, 2 states.

    #[test]
    fn kat_golden_mean_state_count() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer_fast(&seq, cfg);
        assert_eq!(
            result.num_states, 2,
            "Golden Mean must infer exactly 2 states, got {}",
            result.num_states
        );
    }

    #[test]
    fn kat_golden_mean_complexity() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer(&seq, cfg);
        let c = result.cognitive_split.statistical_complexity;
        let expected = 0.9183_f64;
        assert!(
            (c.point - expected).abs() < 0.08,
            "Golden Mean C_μ {:.4} not close to {expected:.4}",
            c.point
        );
        assert!(c.lower <= c.point + 1e-9, "C_μ: lower > point");
        assert!(c.point <= c.upper + 1e-9, "C_μ: point > upper");
    }

    #[test]
    fn kat_golden_mean_entropy_rate() {
        let seq = gen_golden_mean(10_000, 99);
        let cfg = Config {
            max_depth:   2,
            alpha:       0.001,
            bootstrap_b: 200,
            alphabet_size: 2,
        };
        let result = infer(&seq, cfg);
        let h = result.cognitive_split.entropy_rate;
        let expected = 0.6667_f64;
        assert!(
            (h.point - expected).abs() < 0.08,
            "Golden Mean h_μ {:.4} not close to {expected:.4}",
            h.point
        );
        assert!(h.lower <= h.point + 1e-9, "h_μ: lower > point");
        assert!(h.point <= h.upper + 1e-9, "h_μ: point > upper");
    }

    // ── Memory bound (structural check, not a heap profiler) ─────────────────

    #[test]
    fn large_sequence_does_not_oom() {
        // N=50_000, max_depth=4, |A|=4 — exercises the memory path.
        // This test does not measure heap; it just verifies no allocation panic.
        let seq: Vec<u8> = (0..50_000u64)
            .map(|i| (i.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407) % 4) as u8)
            .collect();
        let cfg = Config {
            max_depth:    4,
            alpha:        0.001,
            bootstrap_b:  10, // reduced B for speed
            alphabet_size: 4,
        };
        let result = infer_fast(&seq, cfg);
        assert!(result.num_states >= 1);
        assert!(result.cognitive_split.statistical_complexity.point >= 0.0);
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        /// C_μ is always ≥ 0.
        #[test]
        fn complexity_always_non_negative(
            seed in 0u64..u64::MAX,
            n    in 200usize..1000usize,
        ) {
            let seq = gen_even_process(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.cognitive_split.statistical_complexity.point >= 0.0);
        }

        /// h_μ is always ≥ 0.
        #[test]
        fn entropy_rate_always_non_negative(
            seed in 0u64..u64::MAX,
            n    in 200usize..1000usize,
        ) {
            let seq = gen_even_process(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.cognitive_split.entropy_rate.point >= 0.0);
        }

        /// At least 1 state is always returned.
        #[test]
        fn at_least_one_state(
            seed in 0u64..u64::MAX,
            n    in 50usize..500usize,
        ) {
            let seq = gen_golden_mean(n, seed);
            let cfg = Config { max_depth: 2, bootstrap_b: 5, ..Config::default() };
            let r = infer_fast(&seq, cfg);
            prop_assert!(r.num_states >= 1);
        }

        /// CI bounds are ordered: lower ≤ point ≤ upper.
        #[test]
        fn ci_bounds_ordered(
            seed in 0u64..u64::MAX,
            n    in 500usize..2000usize,
        ) {
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
