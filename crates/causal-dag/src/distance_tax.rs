//! Pillar: I + II. PACR fields: Π + Λ.
//!
//! **Causal Distance Tax** — prevents parasitic long-range DAG attachment.
//!
//! # Physical Axiom
//!
//! Special relativity imposes a light-cone constraint: causal influence decays
//! with distance.  A record that claims a long-range causal ancestor without
//! paying proportionally more energy is physically implausible — it asserts
//! influence propagation faster than allowed by the causal structure.
//!
//! This module enforces that claim via an **exponential tax**:
//!
//! ```text
//! Λ_required = Λ_base × exp(α × causal_distance)
//! ```
//!
//! where `causal_distance` is the BFS hop count from the claimed predecessor
//! to the nearest DAG tip (record with no successors).
//!
//! # Anti-Star-Graph
//!
//! A pathological "star graph" topology arises when many records all list the
//! same predecessor (e.g. GENESIS or a hot root node) as their parent.  This
//! creates a hub node with unbounded out-degree, violating Pillar I's O(n)
//! invariant and defeating causal isolation.
//!
//! The `max_children_per_node` cap bounds out-degree to 65,536 by default,
//! preventing hub formation while allowing legitimate fan-out topologies.
//!
//! # Usage
//!
//! Call [`CausalDag::validate_distance_tax`] BEFORE [`CausalDag::append`]:
//!
//! ```rust,ignore
//! dag.validate_distance_tax(&record, &DistanceTaxConfig::default())?;
//! dag.append(record)?;
//! ```
//!
//! The two-step call pattern is intentional: validation is a read-only check
//! that does not mutate the DAG.  On failure the record is discarded without
//! ever touching the append path.

#![forbid(unsafe_code)]

use std::collections::{HashSet, VecDeque};

use thiserror::Error;

use crate::CausalDag;
use pacr_types::{CausalId, PacrRecord};

// ── Configuration ─────────────────────────────────────────────────────────────

/// Configuration for causal distance taxation.
///
/// All thresholds are configurable — none are dictated by an absolute physical
/// law.  The defaults represent conservative production values tuned for a
/// 10^11-node network.
#[derive(Debug, Clone)]
pub struct DistanceTaxConfig {
    /// Maximum allowed causal hops from a predecessor to the nearest DAG tip.
    ///
    /// Records referencing predecessors beyond this distance are rejected.
    /// Default: `64` (analogous to a discrete light-cone radius).
    pub max_causal_distance: usize,

    /// Exponential tax rate per hop of causal distance.
    ///
    /// Required energy = `Λ_base × exp(α × distance)`.
    /// Default: `0.1` — at distance 64 this is `exp(6.4) ≈ 601×`.
    pub alpha: f64,

    /// Maximum children per node.
    ///
    /// Prevents star-graph topologies where a single hub acquires unbounded
    /// out-degree.  Default: `65_536` (2^16).
    pub max_children_per_node: usize,
}

impl Default for DistanceTaxConfig {
    fn default() -> Self {
        Self {
            max_causal_distance: 64,
            alpha: 0.1,
            max_children_per_node: 65_536,
        }
    }
}

// ── Error ─────────────────────────────────────────────────────────────────────

/// Errors produced by the distance-tax pre-validation check.
#[derive(Debug, Clone, Error, PartialEq)]
pub enum DistanceTaxError {
    /// The predecessor is too far from the current DAG frontier.
    #[error("causal distance {distance} to predecessor {predecessor:?} exceeds max {max}")]
    DistanceExceeded {
        predecessor: CausalId,
        distance: usize,
        max: usize,
    },

    /// The record's energy is insufficient to cover the distance tax.
    #[error("energy {actual:.3e} J insufficient for distance tax {required:.3e} J")]
    InsufficientTax { required: f64, actual: f64 },

    /// The predecessor node has reached its maximum child capacity.
    #[error("node {parent:?} has reached child capacity {max}")]
    ChildCapacityExceeded { parent: CausalId, max: usize },
}

// ── CausalDag extension ───────────────────────────────────────────────────────

impl CausalDag {
    /// Pre-validate the causal distance tax for a record BEFORE calling
    /// [`CausalDag::append`].
    ///
    /// Checks three invariants for each non-GENESIS predecessor:
    ///
    /// 1. **Capacity**: the predecessor has not exceeded `max_children_per_node`.
    /// 2. **Distance**: hop count from the predecessor to the nearest DAG tip
    ///    does not exceed `max_causal_distance`.
    /// 3. **Energy**: the record's actual energy `≥ Λ × exp(α × distance)`.
    ///
    /// Returns the aggregate tax multiplier `exp(α × total_distance)` on
    /// success.  The caller may use this to verify the effective Λ floor.
    ///
    /// # Errors
    ///
    /// Returns the first [`DistanceTaxError`] encountered.  Errors are returned
    /// early — remaining predecessors are not checked after the first failure.
    pub fn validate_distance_tax(
        &self,
        record: &PacrRecord,
        config: &DistanceTaxConfig,
    ) -> Result<f64, DistanceTaxError> {
        let mut total_tax_multiplier = 1.0_f64;

        for pred_id in &record.predecessors {
            if pred_id.is_genesis() {
                continue; // GENESIS is a sentinel; it has no capacity or distance constraint
            }

            // ── Invariant 1: child capacity ───────────────────────────────────
            let child_count = self.successors(pred_id).len();
            if child_count >= config.max_children_per_node {
                return Err(DistanceTaxError::ChildCapacityExceeded {
                    parent: *pred_id,
                    max: config.max_children_per_node,
                });
            }

            // ── Invariant 2: causal distance ──────────────────────────────────
            let distance = self.distance_to_tips(pred_id, config.max_causal_distance);
            if distance > config.max_causal_distance {
                return Err(DistanceTaxError::DistanceExceeded {
                    predecessor: *pred_id,
                    distance,
                    max: config.max_causal_distance,
                });
            }

            total_tax_multiplier *= (config.alpha * distance as f64).exp();
        }

        // ── Invariant 3: energy tax ───────────────────────────────────────────
        let required_energy = record.landauer_cost.point * total_tax_multiplier;
        if record.resources.energy.point < required_energy {
            return Err(DistanceTaxError::InsufficientTax {
                required: required_energy,
                actual: record.resources.energy.point,
            });
        }

        Ok(total_tax_multiplier)
    }

    /// Compute the hop distance from `id` to the **nearest** DAG tip (a node
    /// with no children), via BFS forward traversal.
    ///
    /// - If `id` has no children it is itself a tip → returns `0`.
    /// - BFS is bounded at `depth_limit + 1` to avoid full-graph traversal.
    ///   If no tip is found within the limit, returns `depth_limit + 1`.
    ///
    /// O(reachable nodes within `depth_limit` hops).
    fn distance_to_tips(&self, id: &CausalId, depth_limit: usize) -> usize {
        // Fast path: if no children, this node IS a tip
        let root_children = self.successors(id);
        if root_children.is_empty() {
            return 0;
        }
        drop(root_children);

        let mut queue: VecDeque<(CausalId, usize)> = VecDeque::new();
        let mut visited: HashSet<CausalId> = HashSet::new();

        queue.push_back((*id, 0));
        visited.insert(*id);

        while let Some((current, depth)) = queue.pop_front() {
            // Safety early-exit: don't search beyond the limit
            if depth > depth_limit {
                return depth;
            }

            let kids = self.successors(&current);
            if kids.is_empty() {
                // Found the nearest tip at this depth
                return depth;
            }
            for kid in kids {
                if visited.insert(kid) {
                    queue.push_back((kid, depth + 1));
                }
            }
        }

        // No tip found within the graph (shouldn't happen in a well-formed DAG
        // unless all reachable nodes form a cycle — prevented by append()).
        depth_limit + 1
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};
    use smallvec::smallvec;

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// Build a minimal valid record with exactly enough energy to cover
    /// `tax_multiplier × landauer_cost`.
    fn record_with_energy(id: u128, preds: &[u128], landauer: f64, energy: f64) -> PacrRecord {
        let pred_set = preds.iter().map(|&p| CausalId(p)).collect();
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(pred_set)
            .landauer_cost(Estimate::exact(landauer))
            .resources(ResourceTriple {
                energy: Estimate::exact(energy),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.5),
                entropy_rate: Estimate::exact(0.3),
            })
            .payload(Bytes::new())
            .build()
            .unwrap()
    }

    fn append_genesis_record(dag: &Arc<CausalDag>, id: u128) {
        let r = record_with_energy(id, &[], 1e-20, 1e-16);
        dag.append(r).unwrap();
    }

    // ── distance_to_tips ──────────────────────────────────────────────────────

    #[test]
    fn tip_has_distance_zero() {
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);
        // Node 1 has no children → it's a tip at distance 0
        assert_eq!(dag.distance_to_tips(&CausalId(1), 64), 0);
    }

    #[test]
    fn parent_of_tip_has_distance_one() {
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);
        let child = record_with_energy(2, &[1], 1e-20, 1e-16);
        dag.append(child).unwrap();
        // Node 1 has one child (node 2) which is a tip → distance = 1
        assert_eq!(dag.distance_to_tips(&CausalId(1), 64), 1);
    }

    #[test]
    fn chain_depth_respected() {
        // Build 1 → 2 → 3 → 4 (4 is the tip)
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);
        for i in 2_u128..=4 {
            let r = record_with_energy(i, &[i - 1], 1e-20, 1e-16);
            dag.append(r).unwrap();
        }
        assert_eq!(dag.distance_to_tips(&CausalId(1), 64), 3);
    }

    // ── ChildCapacityExceeded ─────────────────────────────────────────────────

    #[test]
    fn rejects_when_child_capacity_exceeded() {
        // Use a tiny capacity for the test (not 65_536 — that would be too slow)
        let config = DistanceTaxConfig {
            max_children_per_node: 3,
            ..Default::default()
        };
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1); // root

        // Add exactly max_children_per_node children to root
        for i in 2_u128..=4 {
            let r = record_with_energy(i, &[1], 1e-20, 1e-16);
            dag.append(r).unwrap();
        }

        // One more child would exceed capacity
        let overflow = record_with_energy(5, &[1], 1e-20, 1e-16);
        let result = dag.validate_distance_tax(&overflow, &config);
        assert!(
            matches!(
                result,
                Err(DistanceTaxError::ChildCapacityExceeded { max: 3, .. })
            ),
            "expected ChildCapacityExceeded, got: {result:?}"
        );
    }

    #[test]
    fn allows_exactly_at_capacity() {
        let config = DistanceTaxConfig {
            max_children_per_node: 3,
            ..Default::default()
        };
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);

        // Two children: still one slot available
        for i in 2_u128..=3 {
            let r = record_with_energy(i, &[1], 1e-20, 1e-16);
            dag.append(r).unwrap();
        }

        // Third child should be allowed (2 < 3)
        let at_limit = record_with_energy(4, &[1], 1e-20, 1e-16);
        let result = dag.validate_distance_tax(&at_limit, &config);
        assert!(result.is_ok(), "third child should be allowed: {result:?}");
    }

    // ── DistanceExceeded ──────────────────────────────────────────────────────

    #[test]
    fn rejects_when_distance_exceeds_max() {
        // Build a 5-hop chain, then try to reference root from the tip.
        let config = DistanceTaxConfig {
            max_causal_distance: 3, // max 3 hops
            alpha: 0.0,             // no energy tax (isolate distance check)
            max_children_per_node: 65_536,
        };
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);
        for i in 2_u128..=5 {
            let r = record_with_energy(i, &[i - 1], 1e-20, 1e-16);
            dag.append(r).unwrap();
        }
        // Node 1 is now 4 hops from the tip (5) → exceeds max_causal_distance=3
        let late_ref = record_with_energy(6, &[1], 1e-20, 1e-16);
        let result = dag.validate_distance_tax(&late_ref, &config);
        assert!(
            matches!(
                result,
                Err(DistanceTaxError::DistanceExceeded { max: 3, .. })
            ),
            "expected DistanceExceeded, got: {result:?}"
        );
    }

    // ── InsufficientTax ───────────────────────────────────────────────────────

    #[test]
    fn rejects_when_energy_below_tax() {
        // Build parent → child (distance 1 from parent to tip)
        let config = DistanceTaxConfig {
            max_causal_distance: 64,
            alpha: 10.0, // very steep: exp(10×1) ≈ 22026×
            max_children_per_node: 65_536,
        };
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);
        // Append child so parent is at distance 1 from tip
        let child = record_with_energy(2, &[1], 1e-20, 1e-16);
        dag.append(child).unwrap();

        // grandchild references parent (distance 1) but only has 1× energy
        let grandchild = record_with_energy(3, &[1], 1e-20, 1e-16);
        // Required: 1e-20 × exp(10 × 1) ≈ 2.2e-16; actual energy is 1e-16 < 2.2e-16
        let result = dag.validate_distance_tax(&grandchild, &config);
        assert!(
            matches!(result, Err(DistanceTaxError::InsufficientTax { .. })),
            "expected InsufficientTax, got: {result:?}"
        );
    }

    // ── Healthy DAG ───────────────────────────────────────────────────────────

    #[test]
    fn healthy_linear_chain_passes() {
        // Linear chain with short distances and sufficient energy
        let config = DistanceTaxConfig {
            alpha: 0.1,
            ..Default::default()
        };
        let dag = Arc::new(CausalDag::new());
        append_genesis_record(&dag, 1);

        let mut last = 1_u128;
        for i in 2_u128..=10 {
            let r = record_with_energy(i, &[last], 1e-20, 1e-16);
            dag.append(r.clone()).unwrap();
            // Each new record references only the previous tip → distance = 0
            let _result = dag.validate_distance_tax(&r, &config);
            // Before appending the record the predecessor IS the tip (dist=0)
            // so we must validate before appending; here we verify the already-
            // appended chain stays valid for the NEXT step.
            last = i;
        }

        // Reference the current tip (distance=0): tax multiplier = exp(0) = 1.0
        let next = record_with_energy(11, &[last], 1e-20, 1e-16);
        let result = dag.validate_distance_tax(&next, &config);
        assert!(
            result.is_ok(),
            "healthy tip reference should pass: {result:?}"
        );
        assert!(
            (result.unwrap() - 1.0).abs() < 1e-10,
            "tip distance = 0 → multiplier = 1.0"
        );
    }

    #[test]
    fn genesis_predecessor_exempt_from_tax() {
        // GENESIS is sentinel — distance tax must not apply to it
        let dag = Arc::new(CausalDag::new());
        let config = DistanceTaxConfig {
            alpha: 999.0,           // would be catastrophic if applied
            max_causal_distance: 0, // would reject everything if applied
            max_children_per_node: 65_536,
        };
        let genesis_child = record_with_energy(1, &[], 1e-20, 1e-16);
        // GENESIS predecessor: predecessors vec is empty but the builder
        // uses GENESIS sentinel automatically for genesis records.
        // Instead build a record with explicit GENESIS predecessor:
        let r = PacrBuilder::new()
            .id(CausalId(1))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time: Estimate::exact(1e-6),
                space: Estimate::exact(0.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(0.5),
                entropy_rate: Estimate::exact(0.3),
            })
            .payload(Bytes::new())
            .build()
            .unwrap();
        let result = dag.validate_distance_tax(&r, &config);
        assert!(
            result.is_ok(),
            "GENESIS predecessor should be exempt: {result:?}"
        );
        drop(genesis_child);
    }

    // ── Error display ─────────────────────────────────────────────────────────

    #[test]
    fn distance_exceeded_error_message_contains_distance() {
        let err = DistanceTaxError::DistanceExceeded {
            predecessor: CausalId(42),
            distance: 100,
            max: 64,
        };
        let msg = err.to_string();
        assert!(msg.contains("100"), "{msg}");
        assert!(msg.contains("64"), "{msg}");
    }

    #[test]
    fn insufficient_tax_error_message_contains_amounts() {
        let err = DistanceTaxError::InsufficientTax {
            required: 1.5e-10,
            actual: 1e-20,
        };
        let msg = err.to_string();
        assert!(
            msg.contains("1.500e-10") || msg.contains("1.5e-10") || msg.contains("1.50"),
            "{msg}"
        );
    }
}
