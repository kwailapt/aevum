//! Pillar: III. PACR field: Γ.
//!
//! Causal State Splitting Reconstruction (CSSR) algorithm.
//!
//! Ref: Shalizi & Crutchfield (2001), "Computational Mechanics: Pattern and
//! Prediction, Structure and Simplicity", J. Stat. Phys. 104(3-4):817-879.
//!
//! # Algorithm outline
//!
//! 1. Build suffix statistics: for every observed history `h` of length
//!    `1..=max_depth`, count how often each symbol follows `h`.
//! 2. Process histories depth-first (L=1 first).
//!    For each history `h` of length L:
//!    a. Find parent history `h[1..]` and its assigned causal state S.
//!    b. KS-test: is `h`'s conditional distribution homogeneous with S?
//!       • Yes → assign `h` to S (add `h`'s counts to S's pool).
//!       • No  → search other states for a homogeneous match; else new state.
//! 3. Merge pass: collapse pairs of states that are now indistinguishable.
//! 4. Compact (remove empty states, re-index).

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use std::collections::HashMap;

/// Minimum per-history observations before eligibility for KS testing.
/// Histories with fewer observations are skipped (assigned to parent state).
const MIN_OBSERVATIONS: u32 = 20;

// ── Data structures ───────────────────────────────────────────────────────────

/// A causal state: an equivalence class of histories sharing the same
/// conditional future distribution.
#[derive(Debug, Clone)]
pub struct CausalState {
    pub id: usize,
    /// Pooled next-symbol counts across all histories assigned to this state.
    pub pooled: Vec<u32>,
    /// Histories (as symbol sequences) assigned to this state.
    pub histories: Vec<Vec<u8>>,
}

impl CausalState {
    fn new(id: usize, alphabet_size: usize) -> Self {
        Self { id, pooled: vec![0u32; alphabet_size], histories: Vec::new() }
    }

    fn total(&self) -> u32 {
        self.pooled.iter().sum()
    }

    fn is_empty(&self) -> bool {
        self.total() == 0 && self.histories.is_empty()
    }

    fn absorb(&mut self, history: Vec<u8>, counts: &[u32]) {
        for (i, &c) in counts.iter().enumerate() {
            self.pooled[i] += c;
        }
        self.histories.push(history);
    }
}

/// Output of a single CSSR run.
#[derive(Debug, Clone)]
pub struct CssrResult {
    /// Final causal states (non-empty, re-indexed 0..k).
    pub states: Vec<CausalState>,
    /// Maps every observed history to its state index.
    pub assignment: HashMap<Vec<u8>, usize>,
    pub alphabet_size: usize,
    pub max_depth: usize,
}

// ── Two-sample Kolmogorov–Smirnov test ───────────────────────────────────────

/// Two-sample KS test for discrete distributions.
///
/// Returns `true` (reject homogeneity) when the empirical CDFs differ by more
/// than the `alpha`-level critical value.  Returns `false` when either sample
/// is too small (`< MIN_OBSERVATIONS`) — conservative (assume homogeneous).
pub fn ks_reject_homogeneity(counts_a: &[u32], counts_b: &[u32], alpha: f64) -> bool {
    let n_a: u32 = counts_a.iter().sum();
    let n_b: u32 = counts_b.iter().sum();

    if n_a < MIN_OBSERVATIONS || n_b < MIN_OBSERVATIONS {
        return false; // insufficient data — do not split
    }

    let fa = n_a as f64;
    let fb = n_b as f64;

    // Maximum absolute CDF difference over the discrete alphabet.
    let k = counts_a.len().max(counts_b.len());
    let mut cum_a = 0u32;
    let mut cum_b = 0u32;
    let mut d_max: f64 = 0.0;

    for i in 0..k {
        cum_a += if i < counts_a.len() { counts_a[i] } else { 0 };
        cum_b += if i < counts_b.len() { counts_b[i] } else { 0 };
        let d = (cum_a as f64 / fa - cum_b as f64 / fb).abs();
        if d > d_max {
            d_max = d;
        }
    }

    // Asymptotic critical value: D_crit = c_α × sqrt((n_A + n_B) / (n_A × n_B)).
    // c_α = sqrt(-0.5 × ln α).
    let c_alpha = (-0.5_f64 * alpha.ln()).sqrt();
    let d_crit = c_alpha * ((fa + fb) / (fa * fb)).sqrt();

    d_max > d_crit
}

// ── Suffix statistics ─────────────────────────────────────────────────────────

/// Build per-suffix next-symbol count vectors for all depths `1..=max_depth`.
///
/// Memory: O(N × max_depth) worst-case, but histories with identical byte
/// sequences share one entry.  For typical processes this is
/// O(|A|^max_depth × |A|) entries, capped by N.
pub fn build_suffix_stats(
    symbols: &[u8],
    alphabet_size: usize,
    max_depth: usize,
) -> HashMap<Vec<u8>, Vec<u32>> {
    let mut stats: HashMap<Vec<u8>, Vec<u32>> = HashMap::new();
    let n = symbols.len();

    for depth in 1..=max_depth {
        for i in depth..n {
            let next = symbols[i] as usize;
            if next >= alphabet_size {
                continue;
            }
            let history = symbols[i - depth..i].to_vec();
            let entry = stats
                .entry(history)
                .or_insert_with(|| vec![0u32; alphabet_size]);
            entry[next] += 1;
        }
    }

    stats
}

// ── Core CSSR ─────────────────────────────────────────────────────────────────

/// Run CSSR on a discrete symbol sequence.
///
/// # Arguments
/// * `symbols`       — observed symbol sequence (values `0..alphabet_size`)
/// * `alphabet_size` — `|A|`
/// * `max_depth`     — maximum history length `L`
/// * `alpha`         — KS significance level (e.g. `0.001`)
///
/// # Returns
///
/// [`CssrResult`] with the inferred causal states and history → state map.
pub fn run_cssr(
    symbols: &[u8],
    alphabet_size: usize,
    max_depth: usize,
    alpha: f64,
) -> CssrResult {
    let stats = build_suffix_stats(symbols, alphabet_size, max_depth);
    let mut states: Vec<CausalState> = Vec::new();
    let mut assignment: HashMap<Vec<u8>, usize> = HashMap::new();

    // Process histories depth-by-depth (L=1 first).
    for depth in 1..=max_depth {
        // Collect all observed histories of this depth.
        let mut histories: Vec<Vec<u8>> = stats
            .keys()
            .filter(|h| h.len() == depth)
            .cloned()
            .collect();
        histories.sort(); // deterministic order

        for history in histories {
            let hist_counts = &stats[&history];
            let hist_total: u32 = hist_counts.iter().sum();

            // Parent history: drop the oldest (first) symbol.
            let parent_key: Vec<u8> = if depth > 1 { history[1..].to_vec() } else { vec![] };
            let parent_state = if depth > 1 { assignment.get(&parent_key).copied() } else { None };

            // --- Assign this history to a causal state ---
            let target_state: Option<usize> = if let Some(ps_id) = parent_state {
                // Is this history homogeneous with its parent's state?
                if hist_total < MIN_OBSERVATIONS {
                    Some(ps_id) // too few obs — keep with parent
                } else {
                    let reject = ks_reject_homogeneity(&states[ps_id].pooled, hist_counts, alpha);
                    if reject {
                        // Heterogeneous: find another compatible state.
                        find_compatible(&states, hist_counts, alpha)
                    } else {
                        Some(ps_id)
                    }
                }
            } else {
                // Depth-1 with no parent: find any compatible state.
                if hist_total < MIN_OBSERVATIONS {
                    states.first().map(|s| s.id) // assign to first available
                } else {
                    find_compatible(&states, hist_counts, alpha)
                }
            };

            let sid = target_state.unwrap_or_else(|| {
                let id = states.len();
                states.push(CausalState::new(id, alphabet_size));
                id
            });

            states[sid].absorb(history.clone(), hist_counts);
            assignment.insert(history, sid);
        }
    }

    // Merge pass: collapse any two states that have become indistinguishable.
    merge_pass(&mut states, &mut assignment, alpha);

    // Compact: remove empty states and re-index.
    let remap = compact(&mut states);
    for sid in assignment.values_mut() {
        if let Some(&new_id) = remap.get(sid) {
            *sid = new_id;
        }
    }

    // Ensure at least one state.
    if states.is_empty() {
        let mut s = CausalState::new(0, alphabet_size);
        for (h, counts) in &stats {
            s.absorb(h.clone(), counts);
            assignment.insert(h.clone(), 0);
        }
        states.push(s);
    }

    CssrResult { states, assignment, alphabet_size, max_depth }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Find the first existing state whose pooled distribution is homogeneous with
/// `hist_counts` at significance `alpha`.  Returns `None` if no match found.
fn find_compatible(
    states: &[CausalState],
    hist_counts: &[u32],
    alpha: f64,
) -> Option<usize> {
    states
        .iter()
        .filter(|s| !s.is_empty())
        .find(|s| !ks_reject_homogeneity(&s.pooled, hist_counts, alpha))
        .map(|s| s.id)
}

/// Merge pass: repeatedly scan for pairs of states whose pooled distributions
/// are homogeneous; merge the larger-index into the smaller-index.
fn merge_pass(
    states: &mut Vec<CausalState>,
    assignment: &mut HashMap<Vec<u8>, usize>,
    alpha: f64,
) {
    let mut changed = true;
    while changed {
        changed = false;
        let n = states.len();
        'outer: for i in 0..n {
            for j in (i + 1)..n {
                if states[i].is_empty() || states[j].is_empty() {
                    continue;
                }
                let a = states[i].pooled.clone();
                let b = states[j].pooled.clone();
                if !ks_reject_homogeneity(&a, &b, alpha) {
                    // Merge j → i.
                    let j_hist = states[j].histories.clone();
                    let j_pooled = states[j].pooled.clone();
                    for (k, &c) in j_pooled.iter().enumerate() {
                        states[i].pooled[k] += c;
                    }
                    for h in j_hist {
                        assignment.insert(h.clone(), i);
                        states[i].histories.push(h);
                    }
                    states[j].pooled = vec![0; states[j].pooled.len()];
                    states[j].histories.clear();
                    changed = true;
                    break 'outer;
                }
            }
        }
    }
}

/// Remove empty states and return an old→new index map.
fn compact(states: &mut Vec<CausalState>) -> HashMap<usize, usize> {
    let mut remap: HashMap<usize, usize> = HashMap::new();
    let mut new_states: Vec<CausalState> = Vec::new();
    for s in states.drain(..) {
        if !s.is_empty() {
            let new_id = new_states.len();
            remap.insert(s.id, new_id);
            let mut ns = s;
            ns.id = new_id;
            new_states.push(ns);
        }
    }
    *states = new_states;
    remap
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ks_rejects_clearly_different_distributions() {
        // [1000, 0] vs [0, 1000] — maximally different
        let a = vec![1000u32, 0];
        let b = vec![0u32, 1000];
        assert!(ks_reject_homogeneity(&a, &b, 0.001));
    }

    #[test]
    fn ks_accepts_identical_distributions() {
        let a = vec![667u32, 333];
        let b = vec![670u32, 330];
        assert!(!ks_reject_homogeneity(&a, &b, 0.001));
    }

    #[test]
    fn ks_returns_false_for_small_samples() {
        let a = vec![5u32, 3];
        let b = vec![0u32, 8];
        // n < MIN_OBSERVATIONS → conservative (false)
        assert!(!ks_reject_homogeneity(&a, &b, 0.001));
    }

    #[test]
    fn build_suffix_stats_counts_correctly() {
        // Sequence "01010101" with |A|=2, max_depth=1.
        let seq = vec![0u8, 1, 0, 1, 0, 1, 0, 1];
        let stats = build_suffix_stats(&seq, 2, 1);
        // After "0": always 1 follows (3 times) — except last "0" ends sequence.
        let after_0 = &stats[&vec![0u8]];
        let after_1 = &stats[&vec![1u8]];
        // "0" appears at positions 0,2,4,6 — each followed by "1" → 4 times.
        // "1" appears at positions 1,3,5,7 — positions 1,3,5 followed by "0" (pos 7 is last) → 3 times.
        assert_eq!(after_0[1], 4, "0 → 1 four times in 01010101");
        assert_eq!(after_1[0], 3, "1 → 0 three times in 01010101");
    }
}
