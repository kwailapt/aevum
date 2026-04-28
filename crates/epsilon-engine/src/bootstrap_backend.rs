//! Pillar: III. PACR field: Γ.
//!
//! Pluggable bootstrap backend abstraction for ε-machine confidence intervals.
//!
//! # Design
//!
//! [`BootstrapBackend`] is a zero-cost trait that decouples the CSSR inference
//! pipeline from the specific resampling engine.  Today only [`CpuBootstrap`]
//! is active.  On genesis_node (M1 Ultra) a [`MetalBootstrap`] stub compiles
//! in; the stub delegates to [`CpuBootstrap`] until the Metal compute pipeline
//! is implemented in `ets-probe-ffi`.
//!
//! # Contract
//!
//! `resample_and_estimate(data, b)` returns a `Vec<f64>` of length `2 × b`
//! laid out as `[c_0, h_0, c_1, h_1, …, c_{b-1}, h_{b-1}]` where `c_i` is
//! the C_μ estimate and `h_i` is the h_μ estimate for bootstrap replicate `i`.
//!
//! This flat layout avoids heap-allocating `b` tuples and maps naturally to
//! SIMD-friendly memory access patterns for future Metal kernels.

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

use crate::complexity::counts_to_probs;
use crate::cssr::{run_cssr, CausalState};

// ── BootstrapBackend trait ────────────────────────────────────────────────────

/// Pluggable backend for parametric bootstrap resampling of ε-machine metrics.
///
/// Implementors must be stateless (or internally synchronised) so that
/// `resample_and_estimate` can be called from multiple async tasks.
pub trait BootstrapBackend {
    /// Run `b` bootstrap replicates on `data` and return interleaved
    /// `[c_0, h_0, c_1, h_1, …]` estimates (length = `2 × b`).
    ///
    /// The caller is responsible for extracting percentiles from the returned
    /// vector.
    fn resample_and_estimate(&self, data: &[u8], b: usize) -> Vec<f64>;
}

// ── CpuBootstrap ──────────────────────────────────────────────────────────────

/// CPU-based parametric bootstrap (the existing B=200 implementation).
///
/// Each replicate resamples each causal state's pooled emission counts from
/// its empirical distribution using an Xorshift64 RNG, then recomputes
/// (C_μ, h_μ).  The implementation mirrors [`complexity::bootstrap_ci`] but
/// exposes the raw sample vector rather than aggregated percentiles.
#[derive(Debug, Clone)]
pub struct CpuBootstrap {
    /// Maximum CSSR history depth L.
    pub max_depth: usize,
    /// KS significance level α.
    pub alpha: f64,
    /// Discrete alphabet size |A|.
    pub alphabet_size: usize,
}

impl CpuBootstrap {
    /// Create with explicit parameters.
    #[must_use]
    pub fn new(max_depth: usize, alpha: f64, alphabet_size: usize) -> Self {
        Self {
            max_depth,
            alpha,
            alphabet_size,
        }
    }
}

impl Default for CpuBootstrap {
    fn default() -> Self {
        Self {
            max_depth: 4,
            alpha: 0.001,
            alphabet_size: 2,
        }
    }
}

impl BootstrapBackend for CpuBootstrap {
    fn resample_and_estimate(&self, data: &[u8], b: usize) -> Vec<f64> {
        if data.is_empty() || b == 0 {
            return Vec::new();
        }
        let result = run_cssr(data, self.alphabet_size, self.max_depth, self.alpha);
        if result.states.is_empty() {
            return Vec::new();
        }

        // Empirical stationary distribution (visit counts per state).
        let pi = empirical_pi(&result.states, data, result.max_depth);

        let mut rng = Xorshift64::new(0xdead_beef_cafe_1234);
        let mut out = Vec::with_capacity(2 * b);

        for _ in 0..b {
            let boot_states = resample_states(&result.states, &mut rng);
            let (c, h) = compute_ch(&boot_states, &pi);
            out.push(c);
            out.push(h);
        }
        out
    }
}

// ── MetalBootstrap (genesis_node stub) ───────────────────────────────────────

/// GPU-accelerated bootstrap stub (M1 Ultra Metal compute pipeline).
///
/// Currently delegates to [`CpuBootstrap`].  When the Metal kernel is
/// implemented in `ets-probe-ffi`, replace the body of
/// `resample_and_estimate` with the Metal dispatch.
#[cfg(feature = "genesis_node")]
#[derive(Debug, Clone)]
pub struct MetalBootstrap {
    inner: CpuBootstrap,
}

#[cfg(feature = "genesis_node")]
impl MetalBootstrap {
    /// Create with explicit parameters.
    #[must_use]
    pub fn new(max_depth: usize, alpha: f64, alphabet_size: usize) -> Self {
        Self {
            inner: CpuBootstrap::new(max_depth, alpha, alphabet_size),
        }
    }
}

#[cfg(feature = "genesis_node")]
impl Default for MetalBootstrap {
    fn default() -> Self {
        Self {
            inner: CpuBootstrap::default(),
        }
    }
}

#[cfg(feature = "genesis_node")]
impl BootstrapBackend for MetalBootstrap {
    fn resample_and_estimate(&self, data: &[u8], b: usize) -> Vec<f64> {
        // TODO: dispatch to Metal compute pipeline once ets-probe-ffi is ready.
        self.inner.resample_and_estimate(data, b)
    }
}

// ── Internal helpers ──────────────────────────────────────────────────────────

/// Empirical stationary distribution: fraction of positions (past `max_depth`)
/// assigned to each causal state.
fn empirical_pi(states: &[CausalState], symbols: &[u8], max_depth: usize) -> Vec<f64> {
    let k = states.len();
    let mut visits = vec![0u64; k];
    let n = symbols.len();

    // Build a lookup: history bytes → state id.
    let mut assignment: std::collections::HashMap<Vec<u8>, usize> =
        std::collections::HashMap::new();
    for s in states {
        for h in &s.histories {
            assignment.insert(h.clone(), s.id);
        }
    }

    for pos in max_depth..n {
        let mut assigned = false;
        for d in (1..=max_depth).rev() {
            let hist = &symbols[pos - d..pos];
            if let Some(&sid) = assignment.get(hist) {
                visits[sid] += 1;
                assigned = true;
                break;
            }
        }
        if !assigned {
            visits[0] += 1;
        }
    }
    let total: u64 = visits.iter().sum();
    if total == 0 {
        return vec![1.0 / k as f64; k];
    }
    visits.iter().map(|&v| v as f64 / total as f64).collect()
}

/// Parametric resample: for each state, draw `total` new counts from its
/// empirical distribution.
fn resample_states(states: &[CausalState], rng: &mut Xorshift64) -> Vec<CausalState> {
    states
        .iter()
        .map(|s| {
            let total: u32 = s.pooled.iter().sum();
            let probs = counts_to_probs(&s.pooled);
            let mut new_counts = vec![0u32; s.pooled.len()];
            for _ in 0..total {
                let sym = rng.sample_categorical(&probs);
                new_counts[sym] += 1;
            }
            CausalState {
                id: s.id,
                pooled: new_counts,
                histories: s.histories.clone(),
            }
        })
        .collect()
}

/// Compute (C_μ, h_μ) from resampled states and a fixed π.
fn compute_ch(states: &[CausalState], pi: &[f64]) -> (f64, f64) {
    // C_μ = H[π] = -Σ π_i log2(π_i)
    let c_mu: f64 = pi
        .iter()
        .filter(|&&p| p > 1e-300)
        .map(|&p| -p * p.log2())
        .sum();
    // h_μ = Σ π_i H[emission dist of state i]
    let h_mu: f64 = states
        .iter()
        .zip(pi.iter())
        .map(|(s, &pi_i)| {
            let probs = counts_to_probs(&s.pooled);
            let h: f64 = probs
                .iter()
                .filter(|&&p| p > 1e-300)
                .map(|&p| -p * p.log2())
                .sum();
            pi_i * h
        })
        .sum();
    (c_mu, h_mu)
}

// ── Minimal RNG ───────────────────────────────────────────────────────────────

struct Xorshift64(u64);

impl Xorshift64 {
    fn new(seed: u64) -> Self {
        Self(if seed == 0 {
            0xcafe_babe_1234_5678
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

    fn sample_categorical(&mut self, probs: &[f64]) -> usize {
        let u = self.next_f64();
        let mut cum = 0.0;
        for (i, &p) in probs.iter().enumerate() {
            cum += p;
            if u < cum {
                return i;
            }
        }
        probs.len() - 1
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::gen_even_process;

    #[test]
    fn cpu_bootstrap_empty_input_returns_empty() {
        let backend = CpuBootstrap::default();
        assert!(backend.resample_and_estimate(&[], 200).is_empty());
    }

    #[test]
    fn cpu_bootstrap_zero_b_returns_empty() {
        let backend = CpuBootstrap::default();
        let data: Vec<u8> = gen_even_process(500, 1);
        assert!(backend.resample_and_estimate(&data, 0).is_empty());
    }

    #[test]
    fn cpu_bootstrap_output_length_is_2b() {
        let backend = CpuBootstrap::default();
        let data = gen_even_process(1000, 42);
        let out = backend.resample_and_estimate(&data, 20);
        assert_eq!(out.len(), 40, "expected 2×b=40 entries");
    }

    #[test]
    fn cpu_bootstrap_c_mu_non_negative() {
        let backend = CpuBootstrap::default();
        let data = gen_even_process(2000, 7);
        let out = backend.resample_and_estimate(&data, 50);
        for i in (0..out.len()).step_by(2) {
            assert!(out[i] >= 0.0, "C_μ[{}]={} < 0", i / 2, out[i]);
        }
    }

    #[test]
    fn cpu_bootstrap_h_mu_non_negative() {
        let backend = CpuBootstrap::default();
        let data = gen_even_process(2000, 13);
        let out = backend.resample_and_estimate(&data, 50);
        for i in (1..out.len()).step_by(2) {
            assert!(out[i] >= 0.0, "h_μ[{}]={} < 0", i / 2, out[i]);
        }
    }

    #[test]
    fn xorshift_output_in_unit_interval() {
        let mut rng = Xorshift64::new(99);
        for _ in 0..1000 {
            let v = rng.next_f64();
            assert!((0.0..1.0).contains(&v));
        }
    }

    #[cfg(feature = "genesis_node")]
    #[test]
    fn metal_bootstrap_delegates_to_cpu() {
        let cpu = CpuBootstrap::default();
        let metal = MetalBootstrap::default();
        let data = gen_even_process(500, 5);
        let cpu_out = cpu.resample_and_estimate(&data, 10);
        let metal_out = metal.resample_and_estimate(&data, 10);
        // Both must produce the same length output (same backend, different RNG seed ok).
        assert_eq!(cpu_out.len(), metal_out.len());
    }
}
