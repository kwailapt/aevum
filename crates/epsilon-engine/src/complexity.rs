//! Pillar: III. PACR field: Γ.
//!
//! Statistical complexity (`C_μ`) and entropy rate (`h_μ`) computation from a
//! [`CssrResult`], plus bootstrap confidence intervals.
//!
//! ## Definitions
//!
//! Given the inferred causal states with stationary distribution π:
//!
//! ```text
//! C_μ = H[π]           = -Σ_i π_i log₂ π_i   (statistical complexity, bits)
//! h_μ = Σ_i π_i H[P(·|i)] = Σ_i π_i (-Σ_a P(a|i) log₂ P(a|i))  (entropy rate, bits/sym)
//! ```
//!
//! Bootstrap CIs use B=200 parametric resamples of the state emission counts.

use crate::cssr::{CausalState, CssrResult};
use pacr_types::Estimate;

// ── Information measures ──────────────────────────────────────────────────────

/// Shannon entropy of a probability vector (in bits).  Zeros are skipped.
#[must_use]
pub fn entropy(probs: &[f64]) -> f64 {
    probs
        .iter()
        .filter(|&&p| p > 1e-300)
        .map(|&p| -p * p.log2())
        .sum()
}

/// Convert a count vector to probability vector.  Returns uniform if all zero.
#[must_use]
pub fn counts_to_probs(counts: &[u32]) -> Vec<f64> {
    let total: u32 = counts.iter().sum();
    if total == 0 {
        let n = counts.len() as f64;
        return vec![1.0 / n; counts.len()];
    }
    counts
        .iter()
        .map(|&c| f64::from(c) / f64::from(total))
        .collect()
}

// ── Stationary distribution ───────────────────────────────────────────────────

/// Estimate the stationary distribution of causal states empirically from the
/// symbol sequence.  Each position (past position `max_depth`) is assigned to
/// the state of its longest matching history prefix.
#[must_use]
pub fn stationary_distribution(result: &CssrResult, symbols: &[u8]) -> Vec<f64> {
    let k = result.states.len();
    let mut visits = vec![0u64; k];
    let n = symbols.len();
    let depth = result.max_depth;

    for pos in depth..n {
        // Try longest matching history first, fall back to shorter.
        let mut assigned = false;
        for d in (1..=depth).rev() {
            let hist = &symbols[pos - d..pos];
            if let Some(&sid) = result.assignment.get(hist) {
                visits[sid] += 1;
                assigned = true;
                break;
            }
        }
        if !assigned {
            visits[0] += 1; // fallback to state 0
        }
    }

    let total: u64 = visits.iter().sum();
    if total == 0 {
        return vec![1.0 / k as f64; k];
    }
    visits.iter().map(|&v| v as f64 / total as f64).collect()
}

// ── C_μ and h_μ ───────────────────────────────────────────────────────────────

/// Compute (`C_μ`, `h_μ`) from causal states and their stationary distribution.
#[must_use]
pub fn compute_metrics(states: &[CausalState], pi: &[f64]) -> (f64, f64) {
    let c_mu = entropy(pi);
    let h_mu: f64 = states
        .iter()
        .zip(pi.iter())
        .map(|(s, &pi_i)| {
            let probs = counts_to_probs(&s.pooled);
            pi_i * entropy(&probs)
        })
        .sum();
    (c_mu, h_mu)
}

// ── Minimal LCG RNG (no external deps) ───────────────────────────────────────

/// 64-bit xorshift RNG.  Deterministic, fast, zero-allocation.
struct Xorshift64(u64);

impl Xorshift64 {
    fn new(seed: u64) -> Self {
        Self(if seed == 0 {
            0xcafe_babe_dead_beef
        } else {
            seed
        })
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

    /// Sample multinomial: given `probs` (sum 1.0) return a symbol index.
    fn sample_categorical(&mut self, probs: &[f64]) -> usize {
        let u = self.next_f64();
        let mut cum = 0.0;
        for (i, &p) in probs.iter().enumerate() {
            cum += p;
            if u < cum {
                return i;
            }
        }
        probs.len() - 1 // floating-point rounding guard
    }
}

// ── Bootstrap CI (B = 200) ────────────────────────────────────────────────────

/// Parametric bootstrap confidence intervals for (`C_μ`, `h_μ`).
///
/// Each bootstrap replicate perturbs each state's pooled counts by resampling
/// from its empirical distribution with the same total.  The 2.5th–97.5th
/// percentile of the B=200 replicates forms the 95% CI.
///
/// Returns `(Estimate<f64> for C_μ, Estimate<f64> for h_μ)` where
/// `point` is the empirical estimate and `lower`/`upper` are CI bounds.
#[allow(clippy::cast_precision_loss)]
#[must_use]
pub fn bootstrap_ci(
    result: &CssrResult,
    symbols: &[u8],
    b: usize,
) -> (Estimate<f64>, Estimate<f64>) {
    let pi = stationary_distribution(result, symbols);
    let (c_mu_point, h_mu_point) = compute_metrics(&result.states, &pi);

    let mut rng = Xorshift64::new(0xdeadbeef_12345678);
    let mut c_samples = Vec::with_capacity(b);
    let mut h_samples = Vec::with_capacity(b);

    for _ in 0..b {
        // Resample each state's emission counts.
        let boot_states: Vec<crate::cssr::CausalState> = result
            .states
            .iter()
            .map(|s| {
                let total: u32 = s.pooled.iter().sum();
                let probs = counts_to_probs(&s.pooled);
                let mut new_counts = vec![0u32; s.pooled.len()];
                for _ in 0..total {
                    let sym = rng.sample_categorical(&probs);
                    new_counts[sym] += 1;
                }
                crate::cssr::CausalState {
                    id: s.id,
                    pooled: new_counts,
                    histories: s.histories.clone(),
                }
            })
            .collect();

        let (c, h) = compute_metrics(&boot_states, &pi);
        c_samples.push(c);
        h_samples.push(h);
    }

    c_samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    h_samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let lo_idx = (b as f64 * 0.025) as usize;
    let hi_idx = (b as f64 * 0.975) as usize;
    let hi_idx = hi_idx.min(b - 1);

    (
        Estimate {
            point: c_mu_point,
            lower: c_samples[lo_idx],
            upper: c_samples[hi_idx],
        },
        Estimate {
            point: h_mu_point,
            lower: h_samples[lo_idx],
            upper: h_samples[hi_idx],
        },
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entropy_uniform_two_symbols() {
        let p = vec![0.5, 0.5];
        let h = entropy(&p);
        assert!((h - 1.0).abs() < 1e-10, "H([0.5,0.5]) = 1.0 bit, got {h}");
    }

    #[test]
    fn entropy_deterministic_is_zero() {
        let p = vec![1.0, 0.0];
        let h = entropy(&p);
        assert!(h.abs() < 1e-10, "H([1,0]) = 0, got {h}");
    }

    #[test]
    fn entropy_one_third_two_thirds() {
        let p = vec![1.0 / 3.0, 2.0 / 3.0];
        let h = entropy(&p);
        // H(1/3, 2/3) ≈ 0.9183 bits
        assert!((h - 0.9183).abs() < 0.001, "H([1/3,2/3]) ≈ 0.9183, got {h}");
    }

    #[test]
    fn counts_to_probs_normalises() {
        let counts = vec![3u32, 1];
        let p = counts_to_probs(&counts);
        assert!((p[0] - 0.75).abs() < 1e-10);
        assert!((p[1] - 0.25).abs() < 1e-10);
    }

    #[test]
    fn counts_to_probs_all_zero_uniform() {
        let counts = vec![0u32, 0, 0];
        let p = counts_to_probs(&counts);
        for &pi in &p {
            assert!((pi - 1.0 / 3.0).abs() < 1e-10);
        }
    }

    #[test]
    fn xorshift_produces_values_in_range() {
        let mut rng = Xorshift64::new(42);
        for _ in 0..1000 {
            let v = rng.next_f64();
            assert!((0.0..1.0).contains(&v), "out of [0,1): {v}");
        }
    }
}
