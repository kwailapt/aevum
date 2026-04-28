//! Pillar: I + II. PACR field: Π.
//!
//! **Partition Recovery Merge** — integrates a remote DAG fragment into the
//! local DAG after a network partition heals.
//!
//! # Physical Axiom
//!
//! A network partition is a violation of causal connectivity: nodes on either
//! side evolve independently, creating two diverging causal lineages.  When
//! the partition heals, the system must reconstruct causal order from the
//! union of both record sets without duplicating any record or violating the
//! predecessor-existence invariant.
//!
//! # Algorithm
//!
//! 1. **Filter**: skip records already present in the local DAG (duplicates).
//! 2. **Sort**: apply Kahn's topological sort to the filtered remote records
//!    so predecessors are always inserted before their descendants.
//!    Complexity: O(V + E) where V = |filtered records|, E = |edges within set|.
//! 3. **Merge**: attempt `dag.append()` on each sorted record in order.
//!    Records whose predecessors are missing from BOTH the remote set AND the
//!    local DAG are collected as `orphans_deferred`.
//! 4. **Tips**: identify the remote tips — records in the merged set that are
//!    not predecessors of any other record in the remote batch.  These form
//!    the causal frontier to which a reunion record will link.

#![forbid(unsafe_code)]

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::Arc;

use pacr_types::{CausalId, PacrRecord};

use crate::{CausalDag, DagError};

// ── Public types ──────────────────────────────────────────────────────────────

/// Result of a partition-recovery merge operation.
#[derive(Debug, Clone)]
pub struct MergeResult {
    /// Number of remote records successfully appended to the local DAG.
    pub records_merged: usize,
    /// Number of remote records skipped (already present in local DAG).
    pub records_skipped: usize,
    /// Records that could not be appended because their predecessors are
    /// absent from both the remote batch and the local DAG (true orphans).
    /// Caller may retry after receiving additional remote records.
    pub orphans_deferred: Vec<Arc<PacrRecord>>,
    /// CausalIds of the remote tips after merging: records that are not
    /// predecessors of any other record in the remote batch.
    /// These are the correct predecessor set for a reunion PACR record.
    pub remote_tips: Vec<CausalId>,
}

// ── Public functions ──────────────────────────────────────────────────────────

/// Merge a remote DAG fragment into `dag`.
///
/// # Arguments
///
/// * `dag`    — the local (mutable) causal DAG.
/// * `remote` — slice of remote PACR records to integrate.
///
/// # Returns
///
/// A [`MergeResult`] summarising what was merged, skipped, deferred, and
/// which CausalIds form the remote tip set.
///
/// # Complexity
///
/// O(|remote| + E_remote) where E_remote is the total predecessor-edge count
/// within the remote record set.  The topological sort is Kahn's algorithm.
pub fn merge_remote(dag: &CausalDag, remote: &[Arc<PacrRecord>]) -> MergeResult {
    if remote.is_empty() {
        return MergeResult {
            records_merged: 0,
            records_skipped: 0,
            orphans_deferred: vec![],
            remote_tips: vec![],
        };
    }

    // Step 1: Filter out records already present in the local DAG.
    let mut records_skipped = 0usize;
    let mut to_merge: Vec<Arc<PacrRecord>> = Vec::with_capacity(remote.len());

    for rec in remote {
        if dag.contains(&rec.id) {
            records_skipped += 1;
        } else {
            to_merge.push(Arc::clone(rec));
        }
    }

    // Step 2: Topologically sort the filtered records.
    let sorted = topological_sort(&to_merge);

    // Step 3: Attempt to append each record in topological order.
    let mut records_merged = 0usize;
    let mut orphans_deferred: Vec<Arc<PacrRecord>> = Vec::new();
    // Track which IDs we have successfully merged (for tip computation).
    let mut merged_ids: HashSet<CausalId> = HashSet::new();

    for rec in &sorted {
        match dag.append((*rec).as_ref().clone()) {
            Ok(_) => {
                records_merged += 1;
                merged_ids.insert(rec.id);
            }
            Err(DagError::DuplicateId(_)) => {
                // Another goroutine may have inserted it between filter and sort.
                records_skipped += 1;
            }
            Err(DagError::MissingPredecessor { .. }) | Err(DagError::SelfReference(_)) => {
                orphans_deferred.push(Arc::clone(rec));
            }
        }
    }

    // Step 4: Compute remote tips.
    // A tip is a merged record whose ID does not appear in the predecessor set
    // of any other record in the remote batch (merged or deferred).
    let all_remote_ids: HashSet<CausalId> = remote.iter().map(|r| r.id).collect();

    // Build the set of IDs that ARE referenced as predecessors within the remote batch.
    let mut referenced_as_predecessor: HashSet<CausalId> = HashSet::new();
    for rec in remote {
        for pred in &rec.predecessors {
            if all_remote_ids.contains(pred) {
                referenced_as_predecessor.insert(*pred);
            }
        }
    }

    // Tips = merged records whose IDs are not referenced as a predecessor within
    // the remote batch.
    let remote_tips: Vec<CausalId> = merged_ids
        .iter()
        .filter(|id| !referenced_as_predecessor.contains(id))
        .copied()
        .collect();

    MergeResult {
        records_merged,
        records_skipped,
        orphans_deferred,
        remote_tips,
    }
}

/// Topologically sort `records` using Kahn's algorithm.
///
/// Only edges WITHIN the `records` slice are considered.  Predecessors that
/// exist in the local DAG (or are GENESIS) are treated as already-satisfied
/// and do not affect ordering.
///
/// Records with no unsatisfied predecessors (within the slice) come first.
/// Records that form a cycle (shouldn't happen in a valid PACR DAG) are
/// appended at the end in input order.
///
/// # Returns
///
/// A new `Vec` containing all input records in topological order.
pub fn topological_sort(records: &[Arc<PacrRecord>]) -> Vec<Arc<PacrRecord>> {
    if records.is_empty() {
        return vec![];
    }

    // Step 1: Build id_set — the set of all IDs in this batch.
    let id_set: HashSet<CausalId> = records.iter().map(|r| r.id).collect();

    // Step 2: Build in_degree — count predecessors that are within id_set.
    // Also build adjacency: for each ID, which records have it as a predecessor?
    let mut in_degree: HashMap<CausalId, usize> = HashMap::with_capacity(records.len());
    // reverse_adj: pred_id → list of record IDs that have pred_id as a predecessor
    let mut reverse_adj: HashMap<CausalId, Vec<CausalId>> = HashMap::with_capacity(records.len());

    // Initialize all records with in_degree 0.
    for rec in records {
        in_degree.entry(rec.id).or_insert(0);
    }

    for rec in records {
        for pred in &rec.predecessors {
            if pred.is_genesis() || !id_set.contains(pred) {
                // Predecessor is external (already in DAG or GENESIS) — skip.
                continue;
            }
            // pred is within our batch → it must come before rec.
            *in_degree.entry(rec.id).or_insert(0) += 1;
            reverse_adj.entry(*pred).or_default().push(rec.id);
        }
    }

    // Build a lookup map: CausalId → Arc<PacrRecord>
    let record_map: HashMap<CausalId, Arc<PacrRecord>> =
        records.iter().map(|r| (r.id, Arc::clone(r))).collect();

    // Step 3: Initialize queue with all records whose in_degree == 0.
    let mut queue: VecDeque<CausalId> = in_degree
        .iter()
        .filter(|(_, &deg)| deg == 0)
        .map(|(&id, _)| id)
        .collect();

    // For determinism, sort the initial queue by CausalId value.
    // (CausalId is Ord — sorted ascending for reproducible output.)
    let mut queue_vec: Vec<CausalId> = queue.drain(..).collect();
    queue_vec.sort_unstable();
    queue.extend(queue_vec);

    let mut sorted: Vec<Arc<PacrRecord>> = Vec::with_capacity(records.len());
    let mut visited: HashSet<CausalId> = HashSet::new();

    // Step 4: Process queue (Kahn's BFS).
    while let Some(id) = queue.pop_front() {
        if visited.contains(&id) {
            continue;
        }
        visited.insert(id);

        if let Some(rec) = record_map.get(&id) {
            sorted.push(Arc::clone(rec));
        }

        // Decrement in_degree for all records that depend on `id`.
        if let Some(dependents) = reverse_adj.get(&id) {
            let mut newly_ready: Vec<CausalId> = Vec::new();
            for &dep_id in dependents {
                if visited.contains(&dep_id) {
                    continue;
                }
                let deg = in_degree.entry(dep_id).or_insert(0);
                if *deg > 0 {
                    *deg -= 1;
                }
                if *deg == 0 {
                    newly_ready.push(dep_id);
                }
            }
            // Sort for determinism before pushing.
            newly_ready.sort_unstable();
            for id in newly_ready {
                queue.push_back(id);
            }
        }
    }

    // Step 5: Append any remaining records that were not reached (cycle members
    // or isolated — in a valid PACR DAG this should not happen, but we handle
    // it gracefully by appending in input order).
    for rec in records {
        if !visited.contains(&rec.id) {
            sorted.push(Arc::clone(rec));
        }
    }

    sorted
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};

    fn make_record(id: u128, preds: &[u128]) -> Arc<PacrRecord> {
        let preds_sv: smallvec::SmallVec<[CausalId; 4]> =
            preds.iter().map(|&p| CausalId(p)).collect();
        Arc::new(
            PacrBuilder::new()
                .id(CausalId(id))
                .predecessors(preds_sv)
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
                .unwrap(),
        )
    }

    // ── Test 1: empty remote ──────────────────────────────────────────────────

    #[test]
    fn empty_remote_returns_empty_result() {
        let dag = CausalDag::new();
        let result = merge_remote(&dag, &[]);
        assert_eq!(result.records_merged, 0);
        assert_eq!(result.records_skipped, 0);
        assert!(result.orphans_deferred.is_empty());
        assert!(result.remote_tips.is_empty());
    }

    // ── Test 2: normal merge ──────────────────────────────────────────────────

    #[test]
    fn normal_merge_inserts_records() {
        // Chain: R1 (genesis) → R2 → R3
        // GENESIS = CausalId(0)
        let r1 = make_record(1, &[0]); // predecessor = GENESIS
        let r2 = make_record(2, &[1]);
        let r3 = make_record(3, &[2]);

        let dag = CausalDag::new();
        let result = merge_remote(&dag, &[r1, r2, r3]);

        assert_eq!(result.records_merged, 3);
        assert_eq!(result.records_skipped, 0);
        assert!(result.orphans_deferred.is_empty());
        assert!(dag.contains(&CausalId(1)));
        assert!(dag.contains(&CausalId(2)));
        assert!(dag.contains(&CausalId(3)));
    }

    // ── Test 3: deferred orphan ───────────────────────────────────────────────

    #[test]
    fn deferred_chain_handles_missing_predecessor() {
        // R2 has predecessor 999, which is neither in the remote batch nor in
        // the local DAG → must go to orphans_deferred.
        let r2 = make_record(2, &[999]); // 999 is unknown

        let dag = CausalDag::new();
        let result = merge_remote(&dag, &[r2]);

        assert_eq!(result.records_merged, 0);
        assert_eq!(result.records_skipped, 0);
        assert_eq!(result.orphans_deferred.len(), 1);
        assert_eq!(result.orphans_deferred[0].id, CausalId(2));
    }

    // ── Test 4: duplicate records skipped ─────────────────────────────────────

    #[test]
    fn duplicate_records_skipped() {
        let dag = CausalDag::new();
        // Pre-insert R1 into the local DAG.
        let r1_local = make_record(1, &[0]);
        dag.append((*r1_local).clone()).unwrap();

        // Now attempt to merge R1 again alongside R2.
        let r1_remote = make_record(1, &[0]);
        let r2 = make_record(2, &[1]);
        let result = merge_remote(&dag, &[r1_remote, r2]);

        assert_eq!(
            result.records_skipped, 1,
            "R1 should be skipped (already in DAG)"
        );
        assert_eq!(result.records_merged, 1, "R2 should be merged");
    }

    // ── Test 5: topological sort orders parents before children ───────────────

    #[test]
    fn topological_sort_orders_dependents_after_parents() {
        // Chain R1→R2→R3, given in reverse order.
        let r3 = make_record(3, &[2]);
        let r2 = make_record(2, &[1]);
        let r1 = make_record(1, &[0]); // GENESIS predecessor

        let sorted = topological_sort(&[r3, r2, r1]);

        assert_eq!(sorted.len(), 3);
        // R1 must come before R2, R2 before R3.
        let pos = |id: u128| {
            sorted
                .iter()
                .position(|r| r.id == CausalId(id))
                .expect("record must be present")
        };
        assert!(pos(1) < pos(2), "R1 must precede R2");
        assert!(pos(2) < pos(3), "R2 must precede R3");
    }

    // ── Test 6: remote tips identified correctly ──────────────────────────────

    #[test]
    fn remote_tips_identified_correctly() {
        // DAG shape: R1 (genesis) → R2, R1 → R3 (two branches, no convergence).
        // Tips should be R2 and R3 (neither is a predecessor of the other).
        let r1 = make_record(1, &[0]);
        let r2 = make_record(2, &[1]);
        let r3 = make_record(3, &[1]);

        let dag = CausalDag::new();
        let result = merge_remote(&dag, &[r1, r2, r3]);

        assert_eq!(result.records_merged, 3);
        // R2 and R3 are tips; R1 is not (it is a predecessor of both R2 and R3).
        assert!(
            result.remote_tips.contains(&CausalId(2)),
            "R2 should be a tip"
        );
        assert!(
            result.remote_tips.contains(&CausalId(3)),
            "R3 should be a tip"
        );
        assert!(
            !result.remote_tips.contains(&CausalId(1)),
            "R1 is not a tip (it is referenced as predecessor)"
        );
    }

    // ── Test 7: tips contain only remote-batch records ────────────────────────

    #[test]
    fn reunion_candidate_tips_do_not_include_non_remote() {
        // Pre-insert L1 into the local DAG. Merge R1 (which cites L1 as
        // predecessor) and R2 (which cites R1). Only R2 should be a tip.
        let dag = CausalDag::new();
        let l1 = make_record(10, &[0]);
        dag.append((*l1).clone()).unwrap();

        let r1 = make_record(20, &[10]); // predecessor = L1 (local)
        let r2 = make_record(30, &[20]); // predecessor = R1 (remote)
        let result = merge_remote(&dag, &[r1, r2]);

        assert_eq!(result.records_merged, 2);
        // R2 is the tip; R1 is not (it's a predecessor of R2).
        // L1 must NOT appear in tips (it's not in the remote batch).
        assert!(
            result.remote_tips.contains(&CausalId(30)),
            "R2 should be a tip"
        );
        assert!(
            !result.remote_tips.contains(&CausalId(20)),
            "R1 should not be a tip (it is a predecessor of R2)"
        );
        assert!(
            !result.remote_tips.contains(&CausalId(10)),
            "L1 must not appear in remote_tips (not in remote batch)"
        );
    }
}
