// crates/epsilon-machine/src/lib.rs
//
// Pillar: III (cognitive complexity). PACR field: Γ = (S_T, H_T).
//
// Computes S_T and H_T from a data stream using a first-order ε-machine
// approximation (bigram Markov chain over a quantized alphabet).
//
// # ε-Machine theory (arXiv:2601.03220)
//
// An ε-machine is the minimal sufficient statistic for predicting a process.
// Its causal states partition the history of the process such that states
// with identical predictive distributions are merged.
//
// Two key quantities emerge:
//
//   S_T = H(causal state distribution)        [statistical complexity, bits]
//         The Shannon entropy of the stationary distribution over causal states.
//         Represents learnable structure: information the observer CAN exploit.
//
//   H_T = H(next symbol | current causal state) [entropy rate, bits/symbol]
//         The residual unpredictability after exploiting all causal structure.
//         Represents irreducible noise: information the observer CANNOT reduce.
//
// # First-order approximation
//
// Exact ε-machine construction requires finding the unique minimal causal-state
// partition of the process, which is generally intractable for unknown processes.
//
// We use a first-order Markov approximation:
//   - Causal states ≡ current symbol values (quantized to ALPHABET buckets)
//   - Transition probabilities estimated from bigram frequencies
//
// This approximation is exact for first-order Markov processes and provides
// a lower bound on S_T and an upper bound on H_T for higher-order processes.
//
// # Alphabet quantization
//
// Raw f64 values are mapped to [0, ALPHABET) using log-scale bins appropriate
// for cost distributions (which are typically power-law or log-normal).
// The quantization is monotone: larger values map to larger bins.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use pacr_types::{CognitiveSplit, Estimate};

// ── Constants ──────────────────────────────────────────────────────────────────

/// Number of quantization levels.
///
/// 64 levels × 64 levels = 4096 bigram cells × 8 bytes = 32 KB on the heap.
/// Chosen to capture the dynamic range of typical cost distributions (10^0 to
/// 10^9 χ-quanta) while keeping memory bounded (Pillar I: zero-copy / arena).
const ALPHABET: usize = 64;

/// Minimum number of observations before `compute()` returns non-zero estimates.
/// Below this threshold the bigram table is too sparse for reliable regression.
const MIN_OBSERVATIONS: u64 = 32;

// ── Quantizer ──────────────────────────────────────────────────────────────────

/// Maps a non-negative f64 to a symbol in [0, ALPHABET).
///
/// Uses a log-scale mapping: bin i contains values in [base^i, base^(i+1)).
/// Values ≤ 0 map to bin 0 (the "zero or negative" sentinel bin).
/// Monotone: larger values → larger bins. This preserves ordinal structure.
#[must_use]
fn quantize(value: f64) -> usize {
    if value <= 0.0 || !value.is_finite() {
        return 0;
    }
    // log2(value) maps [1, 2^63] → [0, 63].
    // Clamp to [0, ALPHABET-1].
    let log = value.log2().max(0.0) as usize;
    log.min(ALPHABET - 1)
}

/// Maps a u64 cost value (χ-quanta) to a symbol in [0, ALPHABET).
#[must_use]
fn quantize_u64(value: u64) -> usize {
    if value == 0 {
        return 0;
    }
    let log = (64 - value.leading_zeros() - 1) as usize;
    log.min(ALPHABET - 1)
}

// ── EpsilonMachine ─────────────────────────────────────────────────────────────

/// First-order ε-machine estimator.
///
/// Maintains a bigram frequency table over a quantized alphabet.
/// Call [`observe`] or [`observe_u64`] for each incoming data point,
/// then [`compute`] to get the current [`CognitiveSplit`].
///
/// # Thread safety
/// Not thread-safe. Use one instance per thread, or wrap in `Mutex` / `Arc`.
pub struct EpsilonMachine {
    /// Unigram counts: how many times each symbol was observed.
    unigram: Box<[u64; ALPHABET]>,

    /// Bigram counts: `bigram[i][j]` = number of times symbol `j` followed `i`.
    bigram: Box<[[u64; ALPHABET]; ALPHABET]>,

    /// Total number of observations (= sum of unigram counts).
    total: u64,

    /// Previous observed symbol (for bigram tracking). `None` until ≥ 1 call.
    prev: Option<usize>,
}

impl EpsilonMachine {
    /// Creates a new, empty estimator.
    #[must_use]
    pub fn new() -> Self {
        Self {
            unigram: Box::new([0; ALPHABET]),
            bigram: Box::new([[0; ALPHABET]; ALPHABET]),
            total: 0,
            prev: None,
        }
    }

    /// Records one observation of a f64 value.
    ///
    /// Complexity: O(1).
    pub fn observe(&mut self, value: f64) {
        self.observe_symbol(quantize(value));
    }

    /// Records one observation of a u64 value (cost in χ-quanta).
    ///
    /// Complexity: O(1).
    pub fn observe_u64(&mut self, value: u64) {
        self.observe_symbol(quantize_u64(value));
    }

    /// Records one observation of a raw symbol in [0, ALPHABET).
    pub fn observe_symbol(&mut self, sym: usize) {
        let sym = sym.min(ALPHABET - 1);
        self.unigram[sym] += 1;
        if let Some(p) = self.prev {
            self.bigram[p][sym] += 1;
        }
        self.prev = Some(sym);
        self.total += 1;
    }

    /// Resets all observations. Useful when switching to a new data regime.
    pub fn reset(&mut self) {
        *self.unigram = [0; ALPHABET];
        *self.bigram = [[0; ALPHABET]; ALPHABET];
        self.total = 0;
        self.prev = None;
    }

    /// Returns the number of observations recorded so far.
    #[must_use]
    pub fn total_observations(&self) -> u64 {
        self.total
    }

    /// Computes the current cognitive split (S_T, H_T).
    ///
    /// # Algorithm
    ///
    /// 1. Estimate the stationary distribution π from unigram frequencies.
    /// 2. S_T = H(π) = -Σᵢ πᵢ log₂ πᵢ   (Shannon entropy of state distribution)
    /// 3. For each state i: H(next | i) = -Σⱼ P(j|i) log₂ P(j|i)
    /// 4. H_T = Σᵢ πᵢ × H(next | i)     (expected conditional entropy)
    ///
    /// # Uncertainty
    ///
    /// Both estimates carry uncertainty bounds derived from the standard error
    /// of sample entropy: σ_H ≈ sqrt(k / N) where k = alphabet size, N = count.
    /// This is a first-order approximation; exact bounds require bootstrap.
    ///
    /// # Complexity
    /// O(ALPHABET²) = O(4096) — constant in data size.
    #[must_use]
    pub fn compute(&self) -> CognitiveSplit {
        if self.total < MIN_OBSERVATIONS {
            // Not enough data: return zero with wide uncertainty.
            return CognitiveSplit {
                statistical_complexity: Estimate {
                    point: 0.0,
                    lower: 0.0,
                    upper: (ALPHABET as f64).log2(), // maximum possible S_T
                },
                entropy_rate: Estimate {
                    point: 0.0,
                    lower: 0.0,
                    upper: (ALPHABET as f64).log2(), // maximum possible H_T
                },
            };
        }

        let n = self.total as f64;

        // ── Step 1: stationary distribution π ────────────────────────────────
        let pi: Vec<f64> = self.unigram.iter().map(|&c| c as f64 / n).collect();

        // ── Step 2: S_T = H(π) ───────────────────────────────────────────────
        let s_t: f64 = pi
            .iter()
            .filter(|&&p| p > 0.0)
            .map(|&p| -p * p.log2())
            .sum();

        // ── Step 3: H(next | state=i) for each active state ──────────────────
        // ── Step 4: H_T = Σᵢ πᵢ × H(next | i) ──────────────────────────────
        let h_t: f64 = pi
            .iter()
            .enumerate()
            .filter(|(_, &p)| p > 0.0)
            .map(|(i, &pi_i)| {
                let row = &self.bigram[i];
                let row_total: u64 = row.iter().sum();
                if row_total == 0 {
                    return 0.0;
                }
                let row_n = row_total as f64;
                let h_row: f64 = row
                    .iter()
                    .filter(|&&c| c > 0)
                    .map(|&c| {
                        let p = c as f64 / row_n;
                        -p * p.log2()
                    })
                    .sum();
                pi_i * h_row
            })
            .sum();

        // ── Uncertainty ───────────────────────────────────────────────────────
        // Sample entropy standard error ≈ sqrt(k / N) × log₂(e) bits.
        // This is the Miller-Madow correction — a practical first-order bound.
        let sigma = ((ALPHABET as f64) / n).sqrt();
        let st_half = sigma * std::f64::consts::LOG2_E;
        let ht_half = sigma * std::f64::consts::LOG2_E;

        CognitiveSplit {
            statistical_complexity: Estimate {
                point: s_t,
                lower: (s_t - st_half).max(0.0),
                upper: (s_t + st_half).min((ALPHABET as f64).log2()),
            },
            entropy_rate: Estimate {
                point: h_t,
                lower: (h_t - ht_half).max(0.0),
                upper: (h_t + ht_half).min((ALPHABET as f64).log2()),
            },
        }
    }
}

impl Default for EpsilonMachine {
    fn default() -> Self {
        Self::new()
    }
}

// ── Utility: diagnose regime from two snapshots ────────────────────────────────

/// The trend of a single metric between two snapshots.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Trend {
    Rising,
    Falling,
    Stable,
}

/// Classifies the trend of a value between two snapshots.
///
/// `threshold`: minimum absolute change (in the same units as `before`/`after`)
/// to be considered a trend rather than noise.
#[must_use]
pub fn classify_trend(before: f64, after: f64, threshold: f64) -> Trend {
    let delta = after - before;
    if delta > threshold {
        Trend::Rising
    } else if delta < -threshold {
        Trend::Falling
    } else {
        Trend::Stable
    }
}

/// Cognitive regime diagnosed from two consecutive [`CognitiveSplit`] snapshots.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CognitiveRegime {
    /// S_T rising, H_T stable: discovering learnable structure.
    StructureDiscovery,
    /// S_T stable, H_T rising: encountering noise.
    NoiseIntrusion,
    /// Both rising: new regime, old ε-machine model is inadequate.
    RegimeShift,
    /// Both falling: converging / simplifying.
    Convergence,
    /// Both stable: non-equilibrium steady state reached.
    SteadyState,
    /// Any other combination — not enough signal.
    Undetermined,
}

/// Diagnoses the cognitive regime from two consecutive snapshots.
#[must_use]
pub fn diagnose_regime(
    before: &CognitiveSplit,
    after: &CognitiveSplit,
    threshold: f64,
) -> CognitiveRegime {
    let st_trend = classify_trend(
        before.statistical_complexity.point,
        after.statistical_complexity.point,
        threshold,
    );
    let ht_trend = classify_trend(
        before.entropy_rate.point,
        after.entropy_rate.point,
        threshold,
    );

    match (st_trend, ht_trend) {
        (Trend::Rising, Trend::Stable) => CognitiveRegime::StructureDiscovery,
        (Trend::Stable, Trend::Rising) => CognitiveRegime::NoiseIntrusion,
        (Trend::Rising, Trend::Rising) => CognitiveRegime::RegimeShift,
        (Trend::Falling, Trend::Falling) => CognitiveRegime::Convergence,
        (Trend::Stable, Trend::Stable) => CognitiveRegime::SteadyState,
        _ => CognitiveRegime::Undetermined,
    }
}

// ── Tests ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Feed N identical symbols → fully deterministic stream → H_T → 0.
    #[test]
    fn deterministic_stream_has_zero_entropy_rate() {
        let mut em = EpsilonMachine::new();
        for _ in 0..1000 {
            em.observe_u64(42); // single cost value, repeated
        }
        let split = em.compute();
        // H_T should be exactly 0 (one state, no uncertainty in next symbol).
        assert_eq!(
            split.entropy_rate.point, 0.0,
            "H_T should be 0 for a deterministic stream"
        );
        // S_T should be 0 (one state, no distribution uncertainty).
        assert_eq!(
            split.statistical_complexity.point, 0.0,
            "S_T should be 0 for a single-state process"
        );
    }

    /// Feed alternating symbols → periodic stream → low H_T, non-zero S_T.
    #[test]
    fn alternating_stream_has_low_entropy_rate() {
        let mut em = EpsilonMachine::new();
        for i in 0..1000_u64 {
            em.observe_u64(if i % 2 == 0 { 1 } else { 128 });
        }
        let split = em.compute();
        // Alternating sequence: given state=1, next is always 128 → H(next|1) = 0.
        // H_T should be 0 (perfectly predictable given the current state).
        assert!(
            split.entropy_rate.point < 0.1,
            "H_T for alternating stream should be near 0, got {}",
            split.entropy_rate.point
        );
        // S_T should be > 0 (two states with equal probability → H(π) = 1 bit).
        assert!(
            split.statistical_complexity.point > 0.5,
            "S_T for alternating stream should be ~1 bit, got {}",
            split.statistical_complexity.point
        );
    }

    /// Feed uniformly random symbols → high H_T, high S_T.
    #[test]
    fn uniform_random_has_high_entropy_rate() {
        let mut em = EpsilonMachine::new();
        // Simulate uniform distribution over 32 distinct values
        for rep in 0..50_u64 {
            for v in 0..32_u64 {
                em.observe_u64(1_u64 << v + rep % 3);
            }
        }
        let split = em.compute();
        // H_T should be high (near log2(32) = 5 bits) for a uniform i.i.d. process.
        assert!(
            split.entropy_rate.point > 2.0,
            "H_T for near-uniform stream should be high, got {}",
            split.entropy_rate.point
        );
    }

    #[test]
    fn underpopulated_returns_zero_with_wide_bounds() {
        let mut em = EpsilonMachine::new();
        em.observe_u64(5); // only 1 observation < MIN_OBSERVATIONS
        let split = em.compute();
        assert_eq!(split.statistical_complexity.point, 0.0);
        assert!(split.statistical_complexity.upper > 0.0);
    }

    #[test]
    fn quantize_is_monotone() {
        let values = [0.0_f64, 1.0, 2.0, 4.0, 8.0, 100.0, 1e6, 1e9, 1e18];
        for w in values.windows(2) {
            assert!(quantize(w[0]) <= quantize(w[1]));
        }
    }

    #[test]
    fn regime_diagnosis_steady_state() {
        let same = pacr_types::CognitiveSplit {
            statistical_complexity: Estimate::exact(2.0),
            entropy_rate: Estimate::exact(1.0),
        };
        assert_eq!(
            diagnose_regime(&same, &same, 0.1),
            CognitiveRegime::SteadyState
        );
    }

    #[test]
    fn regime_diagnosis_structure_discovery() {
        let before = pacr_types::CognitiveSplit {
            statistical_complexity: Estimate::exact(1.0),
            entropy_rate: Estimate::exact(1.0),
        };
        let after = pacr_types::CognitiveSplit {
            statistical_complexity: Estimate::exact(2.0),
            entropy_rate: Estimate::exact(1.0),
        };
        assert_eq!(
            diagnose_regime(&before, &after, 0.1),
            CognitiveRegime::StructureDiscovery
        );
    }

    #[test]
    fn reset_clears_state() {
        let mut em = EpsilonMachine::new();
        for _ in 0..100 {
            em.observe_u64(42);
        }
        em.reset();
        assert_eq!(em.total_observations(), 0);
        let split = em.compute();
        assert_eq!(split.statistical_complexity.point, 0.0);
    }
}
