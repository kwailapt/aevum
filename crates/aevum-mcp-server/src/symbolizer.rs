// crates/aevum-mcp-server/src/symbolizer.rs
//
// Pillar: III. PACR field: Γ.
// TextSymbolizer: bridges natural language → ε-engine numerical pipeline.
//
// Algorithm:
//   1. Extract all char 4-grams (sliding window)
//   2. Count frequency of each unique 4-gram
//   3. Sort by frequency descending, take top-256 (alphabet cap)
//   4. L1-normalise → Vec<f64>
//
// Output feeds directly into epsilon_engine::symbolize::equal_frequency().
//
// Candidate for upstreaming into epsilon-engine::symbolize when stabilized.

use std::collections::HashMap;

/// Converts a natural-language string into a normalised f64 frequency vector
/// suitable for the ε-engine symbolizer pipeline.
pub struct TextSymbolizer {
    /// Maximum number of distinct 4-gram types to retain.
    alphabet_cap: usize,
}

impl TextSymbolizer {
    pub fn new() -> Self {
        Self { alphabet_cap: 256 }
    }

    /// Symbolize `text` into a Vec<f64> probability distribution over 4-grams.
    ///
    /// Returns `None` if the text is too short to produce any 4-gram (< 4 chars).
    pub fn symbolize(&self, text: &str) -> Option<Vec<f64>> {
        let chars: Vec<char> = text.chars().collect();
        if chars.len() < 4 {
            return None;
        }

        // Step 1 & 2: count 4-gram frequencies
        let mut counts: HashMap<[char; 4], u64> = HashMap::new();
        for window in chars.windows(4) {
            let gram = [window[0], window[1], window[2], window[3]];
            *counts.entry(gram).or_insert(0) += 1;
        }

        // Step 3: sort by frequency descending, take top alphabet_cap
        let mut pairs: Vec<([char; 4], u64)> = counts.into_iter().collect();
        pairs.sort_unstable_by_key(|p| std::cmp::Reverse(p.1));
        pairs.truncate(self.alphabet_cap);

        // Step 4: L1-normalise
        let total: u64 = pairs.iter().map(|(_, c)| c).sum();
        if total == 0 {
            return None;
        }
        let freqs: Vec<f64> = pairs
            .iter()
            .map(|(_, c)| *c as f64 / total as f64)
            .collect();

        Some(freqs)
    }
}

impl Default for TextSymbolizer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic_same_input_same_output() {
        let s = TextSymbolizer::new();
        let text = "the quick brown fox jumps over the lazy dog";
        let a = s.symbolize(text).unwrap();
        let b = s.symbolize(text).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn output_sums_to_one() {
        let s = TextSymbolizer::new();
        let freqs = s.symbolize("hello world this is a test string").unwrap();
        let sum: f64 = freqs.iter().sum();
        assert!((sum - 1.0).abs() < 1e-10, "sum={sum}");
    }

    #[test]
    fn short_text_returns_none() {
        let s = TextSymbolizer::new();
        assert!(s.symbolize("abc").is_none());
    }

    #[test]
    fn output_length_bounded_by_alphabet_cap() {
        let s = TextSymbolizer::new();
        let long_text = "abcdefghijklmnopqrstuvwxyz ".repeat(100);
        let freqs = s.symbolize(&long_text).unwrap();
        assert!(freqs.len() <= 256);
    }

    #[test]
    fn all_values_non_negative() {
        let s = TextSymbolizer::new();
        let freqs = s.symbolize("the quick brown fox").unwrap();
        assert!(freqs.iter().all(|&v| v >= 0.0));
    }
}
