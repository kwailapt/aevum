//! Pillar: I + III. PACR field: Γ, Π.
//!
//! **Rule Intermediate Representation (Rule-IR)** — constraint matrix of
//! negative knowledge assets.
//!
//! # Theory
//!
//! Negative knowledge is the set of things the system has learned NOT to do.
//! Each validated failure is more valuable than an equivalent success because
//! it permanently prunes a region of the search space that would otherwise
//! be re-explored.
//!
//! The Rule-IR encodes each observed failure as a **constraint row** in a
//! matrix `R`:
//!
//! ```text
//! R ∈ ℝ^{m × d}   where m = number of rules, d = feature dimension
//! ```
//!
//! A candidate configuration `x ∈ ℝ^d` is **violated** by rule `i` if:
//!
//! ```text
//! R[i] · x + b[i] > 0
//! ```
//!
//! where `b[i]` is the rule's bias term derived from the threshold that
//! triggered the constraint.  Candidate configurations are screened by the
//! `ParetoMcts` before rollout: any configuration that activates any rule is
//! rejected before being evaluated.
//!
//! # Physical Interpretation
//!
//! Each constraint row corresponds to a PACR record in the causal ledger —
//! specifically an autopoiesis record from the `PROPOSE` step that was
//! subsequently rejected at `VALIDATE`.  The rule's Π predecessor set links
//! it back to the observations that triggered the failure, forming an
//! immutable causal trace.
//!
//! This is the "negative knowledge as asset" principle: failures do not
//! disappear from the ledger; they crystallise into permanent constraints
//! that make all future decisions globally smarter at O(1) marginal cost.
//!
//! # Phase 7 Stub Status
//!
//! This is the Phase 7 stub.  The full Rule-IR (Phase 8) will:
//! - Encode constraints as dense f32 vectors for SIMD screening.
//! - Support rule generalisation via DBSCAN clustering of nearby failures.
//! - Persist the constraint matrix as a PACR record (append-only, content-
//!   addressed by the hash of R + b).
//! - Implement O(m) batch screening using dot-product operations.
//!
//! The stub implements the rule storage structure, single-rule evaluation,
//! and batch screening API — the structural skeleton Phase 8 will flesh out.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

// ── Constraint Rule ───────────────────────────────────────────────────────────

/// One row of the constraint matrix — a learned negative knowledge asset.
///
/// A rule encodes a region of the parameter space that caused a Γ degradation.
/// The constraint is: `weights · x + bias > 0` → violation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ConstraintRule {
    /// Human-readable label for this rule (e.g. `"epsilon_window_too_wide"`).
    pub label: String,

    /// Weight vector `w ∈ ℝ^d`.  Length must equal `d` for the matrix.
    pub weights: Vec<f64>,

    /// Bias term `b`.
    pub bias: f64,

    /// The Γ degradation magnitude that triggered this rule.
    ///
    /// Larger magnitudes indicate more severe failures; used to prioritise
    /// which rules to apply first during batch screening.
    pub severity: f64,
}

impl ConstraintRule {
    /// Evaluate the rule against a feature vector `x`.
    ///
    /// Returns `true` (violated) if `w · x + b > 0`.
    ///
    /// # Panics
    ///
    /// Panics if `x.len() != self.weights.len()`.
    #[must_use]
    pub fn evaluate(&self, x: &[f64]) -> bool {
        assert_eq!(
            x.len(),
            self.weights.len(),
            "feature vector length {} does not match rule weight length {}",
            x.len(),
            self.weights.len()
        );
        let dot: f64 = self.weights.iter().zip(x.iter()).map(|(w, xi)| w * xi).sum();
        dot + self.bias > 0.0
    }
}

// ── Violation ─────────────────────────────────────────────────────────────────

/// A rule violation reported by [`ConstraintMatrix::screen`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Error)]
#[error("rule violation: {label} (severity {severity:.3})")]
pub struct RuleViolation {
    /// Index of the violated rule in the constraint matrix.
    pub rule_index: usize,
    /// Label of the violated rule.
    pub label: String,
    /// Severity of the violated rule.
    pub severity: f64,
}

// ── ConstraintMatrix ──────────────────────────────────────────────────────────

/// The full constraint matrix of negative knowledge assets.
///
/// Stores `m` [`ConstraintRule`]s.  Candidate configurations are screened
/// against all rules via [`ConstraintMatrix::screen`] before being evaluated.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConstraintMatrix {
    /// Ordered list of constraint rules.  New rules are appended; none removed
    /// (append-only, mirroring the PACR ledger invariant).
    rules: Vec<ConstraintRule>,

    /// Feature dimension `d`.  Set on the first call to `add_rule`.
    /// All subsequent rules must have the same weight vector length.
    dimension: Option<usize>,
}

impl ConstraintMatrix {
    /// Create an empty constraint matrix.
    #[must_use]
    pub fn new() -> Self {
        Self { rules: Vec::new(), dimension: None }
    }

    /// Number of rules in the matrix.
    #[must_use]
    pub fn rule_count(&self) -> usize {
        self.rules.len()
    }

    /// Feature dimension `d` (derived from the first rule added).
    ///
    /// Returns `None` when the matrix is empty.
    #[must_use]
    pub fn dimension(&self) -> Option<usize> {
        self.dimension
    }

    /// Append a new constraint rule to the matrix.
    ///
    /// # Errors
    ///
    /// Returns [`RuleIrError::DimensionMismatch`] if the rule's weight vector
    /// length differs from the established dimension `d`.
    pub fn add_rule(&mut self, rule: ConstraintRule) -> Result<(), RuleIrError> {
        match self.dimension {
            None => {
                self.dimension = Some(rule.weights.len());
            }
            Some(d) if rule.weights.len() != d => {
                return Err(RuleIrError::DimensionMismatch {
                    expected: d,
                    got:      rule.weights.len(),
                });
            }
            _ => {}
        }
        self.rules.push(rule);
        Ok(())
    }

    /// Screen a candidate configuration `x` against all rules.
    ///
    /// Returns a `Vec` of all rules violated by `x`.  An empty `Vec` means
    /// the candidate passes all constraints and may be evaluated.
    ///
    /// Rules are sorted by descending severity before screening, so the
    /// most severe violation is always first in the returned `Vec`.
    ///
    /// # Errors
    ///
    /// Returns [`RuleIrError::DimensionMismatch`] if `x.len() ≠ d`.
    /// Returns [`RuleIrError::EmptyMatrix`] if no rules have been added.
    pub fn screen(&self, x: &[f64]) -> Result<Vec<RuleViolation>, RuleIrError> {
        if self.rules.is_empty() {
            return Err(RuleIrError::EmptyMatrix);
        }
        let d = self.dimension.unwrap_or(0);
        if x.len() != d {
            return Err(RuleIrError::DimensionMismatch {
                expected: d,
                got:      x.len(),
            });
        }

        // Sort indices by descending severity so the worst violations appear first.
        let mut indices: Vec<usize> = (0..self.rules.len()).collect();
        indices.sort_by(|&a, &b| {
            self.rules[b]
                .severity
                .partial_cmp(&self.rules[a].severity)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let violations = indices
            .into_iter()
            .filter(|&i| self.rules[i].evaluate(x))
            .map(|i| RuleViolation {
                rule_index: i,
                label:      self.rules[i].label.clone(),
                severity:   self.rules[i].severity,
            })
            .collect();

        Ok(violations)
    }
}

impl Default for ConstraintMatrix {
    fn default() -> Self {
        Self::new()
    }
}

// ── RuleIr wrapper ────────────────────────────────────────────────────────────

/// Top-level Rule-IR wrapper with statistics tracking.
///
/// Wraps a [`ConstraintMatrix`] and counts how many candidates were screened
/// and how many were blocked.  These statistics are fed back to the
/// `GammaCalculator` as part of the autopoiesis OBSERVE step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleIr {
    matrix:           ConstraintMatrix,
    /// Total candidates screened since construction.
    pub candidates_screened: u64,
    /// Total candidates blocked (at least one rule violated).
    pub candidates_blocked:  u64,
}

impl RuleIr {
    /// Create a new Rule-IR with an empty constraint matrix.
    #[must_use]
    pub fn new() -> Self {
        Self {
            matrix:              ConstraintMatrix::new(),
            candidates_screened: 0,
            candidates_blocked:  0,
        }
    }

    /// Add a new constraint rule derived from an observed failure.
    ///
    /// # Errors
    ///
    /// Propagates [`RuleIrError::DimensionMismatch`] from [`ConstraintMatrix::add_rule`].
    pub fn add_rule(&mut self, rule: ConstraintRule) -> Result<(), RuleIrError> {
        self.matrix.add_rule(rule)
    }

    /// Number of rules in the constraint matrix.
    #[must_use]
    pub fn rule_count(&self) -> usize {
        self.matrix.rule_count()
    }

    /// Screen a candidate configuration, updating block statistics.
    ///
    /// Returns `Ok(true)` if the candidate is **allowed** (no rules violated).
    /// Returns `Ok(false)` if the candidate is **blocked** (at least one violated).
    ///
    /// # Errors
    ///
    /// Propagates errors from [`ConstraintMatrix::screen`].
    pub fn is_allowed(&mut self, x: &[f64]) -> Result<bool, RuleIrError> {
        self.candidates_screened += 1;
        match self.matrix.screen(x) {
            Ok(violations) => {
                if violations.is_empty() {
                    Ok(true)
                } else {
                    self.candidates_blocked += 1;
                    Ok(false)
                }
            }
            Err(RuleIrError::EmptyMatrix) => Ok(true), // No rules → always allowed
            Err(e) => Err(e),
        }
    }

    /// Blocking rate: fraction of screened candidates that were blocked.
    ///
    /// Returns `0.0` when no candidates have been screened.
    #[must_use]
    pub fn blocking_rate(&self) -> f64 {
        if self.candidates_screened == 0 {
            0.0
        } else {
            self.candidates_blocked as f64 / self.candidates_screened as f64
        }
    }
}

impl Default for RuleIr {
    fn default() -> Self {
        Self::new()
    }
}

// ── Error ─────────────────────────────────────────────────────────────────────

/// Errors produced by the Rule-IR module.
#[derive(Debug, Clone, Error, PartialEq)]
pub enum RuleIrError {
    /// Feature vector length does not match the matrix dimension.
    #[error("dimension mismatch: expected {expected}, got {got}")]
    DimensionMismatch { expected: usize, got: usize },

    /// The constraint matrix contains no rules.
    #[error("constraint matrix is empty")]
    EmptyMatrix,
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn rule(label: &str, weights: Vec<f64>, bias: f64, severity: f64) -> ConstraintRule {
        ConstraintRule { label: label.into(), weights, bias, severity }
    }

    // ── ConstraintRule ─────────────────────────────────────────────────────────

    #[test]
    fn rule_violated_when_dot_plus_bias_positive() {
        let r = rule("test", vec![1.0, 0.0], -0.5, 1.0);
        // w · x + b = 1.0 × 1.0 + 0.0 × 0.0 − 0.5 = 0.5 > 0 → violated
        assert!(r.evaluate(&[1.0, 0.0]));
    }

    #[test]
    fn rule_not_violated_when_dot_plus_bias_non_positive() {
        let r = rule("test", vec![1.0, 0.0], -2.0, 1.0);
        // w · x + b = 1.0 × 1.0 − 2.0 = −1.0 ≤ 0 → not violated
        assert!(!r.evaluate(&[1.0, 0.0]));
    }

    #[test]
    fn rule_not_violated_when_exactly_zero() {
        let r = rule("test", vec![1.0], -1.0, 1.0);
        // w · x + b = 1.0 × 1.0 − 1.0 = 0.0 → NOT violated (strict >)
        assert!(!r.evaluate(&[1.0]));
    }

    // ── ConstraintMatrix ───────────────────────────────────────────────────────

    #[test]
    fn empty_matrix_returns_error_on_screen() {
        let matrix = ConstraintMatrix::new();
        let result = matrix.screen(&[1.0, 2.0]);
        assert_eq!(result, Err(RuleIrError::EmptyMatrix));
    }

    #[test]
    fn add_rule_sets_dimension() {
        let mut matrix = ConstraintMatrix::new();
        matrix.add_rule(rule("r1", vec![1.0, 2.0], 0.0, 1.0)).unwrap();
        assert_eq!(matrix.dimension(), Some(2));
    }

    #[test]
    fn add_rule_dimension_mismatch_rejected() {
        let mut matrix = ConstraintMatrix::new();
        matrix.add_rule(rule("r1", vec![1.0, 2.0], 0.0, 1.0)).unwrap();
        let result = matrix.add_rule(rule("r2", vec![1.0], 0.0, 1.0));
        assert_eq!(result, Err(RuleIrError::DimensionMismatch { expected: 2, got: 1 }));
    }

    #[test]
    fn screen_returns_empty_when_no_violations() {
        let mut matrix = ConstraintMatrix::new();
        matrix.add_rule(rule("r1", vec![1.0, 0.0], -10.0, 1.0)).unwrap();
        let violations = matrix.screen(&[1.0, 0.0]).unwrap();
        assert!(violations.is_empty());
    }

    #[test]
    fn screen_returns_violated_rules() {
        let mut matrix = ConstraintMatrix::new();
        matrix.add_rule(rule("r1", vec![1.0], -0.5, 2.0)).unwrap(); // violated by x=[1.0]
        let violations = matrix.screen(&[1.0]).unwrap();
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].label, "r1");
    }

    #[test]
    fn screen_violations_sorted_by_severity_descending() {
        let mut matrix = ConstraintMatrix::new();
        // Both rules will be violated; r2 has higher severity
        matrix.add_rule(rule("r1", vec![1.0], -0.5, 1.0)).unwrap();
        matrix.add_rule(rule("r2", vec![1.0], -0.5, 5.0)).unwrap();
        let violations = matrix.screen(&[1.0]).unwrap();
        assert_eq!(violations.len(), 2);
        assert_eq!(violations[0].label, "r2", "higher severity should be first");
    }

    // ── RuleIr ─────────────────────────────────────────────────────────────────

    #[test]
    fn empty_rule_ir_allows_everything() {
        let mut ir = RuleIr::new();
        assert!(ir.is_allowed(&[1.0, 2.0]).unwrap());
        assert_eq!(ir.candidates_screened, 1);
        assert_eq!(ir.candidates_blocked, 0);
    }

    #[test]
    fn blocking_rate_zero_when_no_blocks() {
        let mut ir = RuleIr::new();
        let _ = ir.is_allowed(&[1.0]);
        assert_eq!(ir.blocking_rate(), 0.0);
    }

    #[test]
    fn blocking_rate_zero_before_any_screens() {
        let ir = RuleIr::new();
        assert_eq!(ir.blocking_rate(), 0.0);
    }

    #[test]
    fn is_allowed_false_when_rule_violated() {
        let mut ir = RuleIr::new();
        ir.add_rule(rule("bad_config", vec![1.0, 0.0], -0.5, 3.0)).unwrap();
        let allowed = ir.is_allowed(&[1.0, 0.0]).unwrap();
        assert!(!allowed, "should be blocked by rule");
        assert_eq!(ir.candidates_blocked, 1);
    }

    #[test]
    fn is_allowed_true_when_rule_not_violated() {
        let mut ir = RuleIr::new();
        ir.add_rule(rule("safe_config", vec![1.0, 0.0], -10.0, 1.0)).unwrap();
        let allowed = ir.is_allowed(&[1.0, 0.0]).unwrap();
        assert!(allowed, "should pass rule");
        assert_eq!(ir.candidates_blocked, 0);
    }

    #[test]
    fn blocking_rate_increases_with_blocks() {
        let mut ir = RuleIr::new();
        ir.add_rule(rule("r", vec![1.0], -0.5, 1.0)).unwrap();
        ir.is_allowed(&[1.0]).unwrap();  // blocked
        ir.is_allowed(&[-1.0]).unwrap(); // allowed
        assert!((ir.blocking_rate() - 0.5).abs() < 1e-10);
    }

    #[test]
    fn rule_violation_display() {
        let v = RuleViolation {
            rule_index: 0,
            label:      "epsilon_too_wide".into(),
            severity:   4.2,
        };
        let s = v.to_string();
        assert!(s.contains("epsilon_too_wide"), "{s}");
        assert!(s.contains("4.2"), "{s}");
    }

    #[test]
    fn rule_ir_rule_count_tracks_adds() {
        let mut ir = RuleIr::new();
        assert_eq!(ir.rule_count(), 0);
        ir.add_rule(rule("r1", vec![1.0], 0.0, 1.0)).unwrap();
        assert_eq!(ir.rule_count(), 1);
        ir.add_rule(rule("r2", vec![2.0], 0.0, 2.0)).unwrap();
        assert_eq!(ir.rule_count(), 2);
    }
}
