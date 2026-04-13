//! Pillar: I. PACR field: ι, Π.
//!
//! **Causal Settlement Oracle (CSO)** — resolves disputes between competing
//! PACR record proposals.
//!
//! When two records `A` and `B` claim to be the canonical next event in a
//! causal chain, the CSO uses the following deterministic algorithm:
//!
//! 1. Compute the causal ancestry depth of each record in the live DAG.
//!    Deeper ancestry → more physical work performed → wins.
//! 2. If depths are equal, use lexicographic ordering of `CausalId` as a
//!    deterministic tiebreaker (no clocks, no randomness — Pillar I).
//!
//! # Stub status
//!
//! This is the Phase 5 stub.  The full CSO (Phase 6) will implement
//! economic settlement via PACR `Λ`-weighted voting.

#![forbid(unsafe_code)]

use std::sync::Arc;

use causal_dag::CausalDag;
use pacr_types::{CausalId, PacrRecord};

// ── Settlement outcome ────────────────────────────────────────────────────────

/// The CSO's verdict when settling two competing proposals.
#[derive(Debug, Clone)]
pub struct SettlementOutcome {
    /// The winning record.
    pub winner: CausalId,
    /// The losing record (will be discarded or archived).
    pub loser: CausalId,
    /// Causal ancestry depth of the winner.
    pub winner_depth: usize,
    /// Causal ancestry depth of the loser.
    pub loser_depth: usize,
}

// ── CSO ───────────────────────────────────────────────────────────────────────

/// Causal Settlement Oracle.
pub struct CausalSettlementOracle {
    dag: Arc<CausalDag>,
}

impl CausalSettlementOracle {
    /// Create a new CSO backed by the given causal DAG.
    #[must_use]
    pub fn new(dag: Arc<CausalDag>) -> Self {
        Self { dag }
    }

    /// Settle a dispute between two competing PACR records.
    ///
    /// Both records must have been validated by the [`Router`][crate::router::Router]
    /// before being submitted to the CSO.  Undefined behaviour for unvalidated records
    /// is not possible (no unsafe code), but results may be semantically incorrect.
    ///
    /// # Special cases
    ///
    /// - If both IDs are identical, `winner == loser` and both depths are equal.
    /// - If a record is not in the DAG, its depth is 0 (no ancestry evidence).
    ///
    /// [`Router`]: crate::router::Router
    #[must_use]
    pub fn settle(&self, a: &PacrRecord, b: &PacrRecord) -> SettlementOutcome {
        if a.id == b.id {
            let depth = self.ancestry_depth(a.id);
            return SettlementOutcome {
                winner: a.id,
                loser:  b.id,
                winner_depth: depth,
                loser_depth:  depth,
            };
        }

        let depth_a = self.ancestry_depth(a.id);
        let depth_b = self.ancestry_depth(b.id);

        // Deeper ancestry wins (more physical work proven).
        // Lexicographic CausalId breaks ties deterministically.
        let a_wins = depth_a > depth_b || (depth_a == depth_b && a.id > b.id);

        if a_wins {
            SettlementOutcome {
                winner: a.id,
                loser:  b.id,
                winner_depth: depth_a,
                loser_depth:  depth_b,
            }
        } else {
            SettlementOutcome {
                winner: b.id,
                loser:  a.id,
                winner_depth: depth_b,
                loser_depth:  depth_a,
            }
        }
    }

    /// Compute the causal ancestry depth of a record.
    ///
    /// Depth = number of unique ancestors reachable via Π edges (BFS).
    /// Returns 0 if the record is not in the DAG.
    ///
    /// O(V + E) worst case, bounded by DAG size.
    #[must_use]
    fn ancestry_depth(&self, id: CausalId) -> usize {
        // Use the DAG's ancestry traversal with an effectively unbounded depth.
        self.dag.ancestry(&id, usize::MAX).len()
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, PredecessorSet, ResourceTriple};

    fn minimal_record(id: u128, preds: &[u128]) -> PacrRecord {
        let pred_set: PredecessorSet = preds.iter().map(|&p| CausalId(p)).collect();
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(pred_set)
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time:   Estimate::exact(1e-6),
                space:  Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.5),
                entropy_rate:           Estimate::exact(0.3),
            })
            .payload(Bytes::new())
            .build()
            .unwrap()
    }

    #[test]
    fn settle_identical_ids_returns_same_winner_and_loser() {
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let r = minimal_record(1, &[]);
        dag.append(r.clone()).unwrap();
        let outcome = cso.settle(&r, &r);
        assert_eq!(outcome.winner, outcome.loser, "identical records: winner = loser");
    }

    #[test]
    fn settle_deeper_ancestry_wins() {
        // Build a chain: root → child_a.  child_b has no ancestors in the DAG.
        let dag = Arc::new(CausalDag::new());
        let root = minimal_record(1, &[]);
        let child_a = minimal_record(2, &[1]);
        dag.append(root).unwrap();
        dag.append(child_a.clone()).unwrap();

        let child_b = minimal_record(3, &[]); // not in DAG
        // Don't append child_b to DAG — it has zero ancestry depth.

        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let outcome = cso.settle(&child_a, &child_b);
        // child_a has depth ≥ 1 (has root as ancestor), child_b has depth 0.
        assert_eq!(outcome.winner, child_a.id, "deeper ancestry must win");
        assert_eq!(outcome.loser,  child_b.id);
    }

    #[test]
    fn settle_equal_depth_uses_lexicographic_tiebreak() {
        // Both records have no ancestors in the DAG → depth 0 each.
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));

        let low_id  = minimal_record(10, &[]);
        let high_id = minimal_record(20, &[]);

        // higher CausalId should win when depths are equal
        let outcome = cso.settle(&low_id, &high_id);
        assert_eq!(
            outcome.winner, high_id.id,
            "higher CausalId wins tiebreak: winner={:?}", outcome.winner
        );
    }

    #[test]
    fn settle_records_not_in_dag_both_depth_zero() {
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let a = minimal_record(100, &[]);
        let b = minimal_record(200, &[]);
        let outcome = cso.settle(&a, &b);
        assert_eq!(outcome.winner_depth, 0, "not-in-DAG record has depth 0");
        assert_eq!(outcome.loser_depth,  0);
    }
}
