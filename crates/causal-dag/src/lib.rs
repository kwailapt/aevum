//! Pillar: I. PACR fields: ι (node identity), Π (predecessor edges).
//!
//! A **lock-free, append-only** causal DAG over [`PacrRecord`] nodes.
//!
//! Physical axiom: special relativity mandates that causation propagates at
//! most at the speed of light, imposing a strict **partial order** on events.
//! This partial order is encoded in the predecessor set Π — there is no total
//! order and no global clock.
//!
//! # Design
//!
//! | Operation           | Complexity    | Mechanism                            |
//! |---------------------|---------------|--------------------------------------|
//! | [`CausalDag::append`] | O(\|Π\|)    | predecessor validation + `DashMap` CAS |
//! | [`CausalDag::get`]  | O(1) expected | `DashMap` sharded read                 |
//! | [`CausalDag::successors`] | O(1)    | `DashMap` reverse-index read           |
//! | [`CausalDag::predecessors`] | O(1)  | `DashMap` sharded read                 |
//! | [`CausalDag::ancestry`] | O(V+E)    | BFS with `HashSet` visited-set         |
//!
//! # CRDT semantics
//!
//! The DAG is a **Grow-Only Set (G-Set)**: records are immutable once inserted
//! and the only mutation is appending new records.  Two replicas converge by
//! exchanging unseen records (union of node sets).
//!
//! # Concurrency
//!
//! [`DashMap`] uses sharded locks (not a single `RwLock`) and provides
//! lock-free concurrent reads on already-inserted keys.  Append uses
//! `entry()` for an atomic duplicate-check-and-insert, eliminating the
//! TOCTOU race of a separate `contains_key` + `insert` pair.
//!
//! No `Mutex` or `RwLock` is used anywhere in this crate.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::must_use_candidate,
    clippy::needless_pass_by_value,
    clippy::missing_panics_doc,
    clippy::missing_errors_doc,
    clippy::return_self_not_must_use,
    clippy::unreadable_literal
)]

pub mod distance_tax;
pub mod merge;

use std::collections::HashSet;
use std::sync::Arc;

use dashmap::mapref::entry::Entry;
use dashmap::DashMap;
use smallvec::SmallVec;
use thiserror::Error;

use pacr_types::{CausalId, PacrRecord};

// ── Public types ──────────────────────────────────────────────────────────────

/// A lock-free, append-only directed acyclic graph of [`PacrRecord`] nodes.
///
/// Nodes are [`CausalId`]s.  Directed edges flow from each record to its
/// causal predecessors (Π).  A reverse index (`children`) allows O(1)
/// forward traversal (cause → effect).
///
/// # Invariants maintained at all times
///
/// 1. **Append-only**: a record is never removed or modified after insertion.
/// 2. **Predecessor-existence**: every non-GENESIS predecessor of a record
///    was inserted before that record.  This makes transitive causal cycles
///    structurally impossible (no record can be its own ancestor).
/// 3. **No self-reference**: a record cannot list its own `id` in Π.
#[derive(Debug)]
pub struct CausalDag {
    /// Primary map: `CausalId` → Arc<PacrRecord>.
    /// `DashMap` provides O(1) sharded reads and atomic entry operations.
    nodes: DashMap<CausalId, Arc<PacrRecord>>,

    /// Reverse index: `predecessor_id` → list of successor ids.
    /// Enables O(1) forward traversal (cause → effect).
    /// `SmallVec<[CausalId; 4]>`: most nodes have 1–4 children (Pillar I,
    /// inline buffer avoids heap allocation for the common case).
    children: DashMap<CausalId, SmallVec<[CausalId; 4]>>,
}

/// Error returned by [`CausalDag::append`].
#[derive(Debug, Clone, Error)]
#[non_exhaustive]
pub enum DagError {
    /// A record with this [`CausalId`] already exists in the DAG.
    /// Append-only invariant: duplicate IDs are forbidden.
    #[error("duplicate causal ID: {0}")]
    DuplicateId(CausalId),

    /// The record references a predecessor that has not yet been inserted.
    /// Physical axiom: a cause must exist before an effect can reference it.
    #[error("missing predecessor: {child} references unknown predecessor {parent}")]
    MissingPredecessor {
        /// The record being inserted.
        child: CausalId,
        /// The predecessor that was not found in the DAG.
        parent: CausalId,
    },

    /// The record lists its own [`CausalId`] in its predecessor set Π.
    /// A causal self-loop violates the acyclicity invariant.
    #[error("self-reference: {0} cannot be its own causal predecessor")]
    SelfReference(CausalId),
}

// ── Implementation ────────────────────────────────────────────────────────────

impl CausalDag {
    /// Creates an empty DAG.
    #[must_use]
    pub fn new() -> Self {
        Self {
            nodes: DashMap::new(),
            children: DashMap::new(),
        }
    }

    /// Creates an empty DAG with pre-allocated shard capacity.
    ///
    /// Use when the expected record count is known in advance; avoids
    /// rehashing at ingestion time.
    #[must_use]
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            nodes: DashMap::with_capacity(capacity),
            children: DashMap::with_capacity(capacity),
        }
    }

    /// Appends a [`PacrRecord`] to the DAG.
    ///
    /// Validates three structural invariants before inserting:
    /// 1. No duplicate ID (append-only).
    /// 2. Every non-GENESIS predecessor already exists in the DAG.
    /// 3. No self-reference in Π.
    ///
    /// On success, returns an [`Arc`] pointing to the stored record.
    ///
    /// # Errors
    ///
    /// Returns [`DagError`] if any invariant is violated.
    ///
    /// # Complexity
    ///
    /// O(\|Π\|) — one `DashMap` read per predecessor, then one atomic
    /// `entry()` insert for the node itself.
    pub fn append(&self, record: PacrRecord) -> Result<Arc<PacrRecord>, DagError> {
        let id = record.id;

        // ── Invariant 3: no self-reference ────────────────────────────────────
        // Checked first: cheapest check, no map access needed.
        if record.predecessors.contains(&id) {
            return Err(DagError::SelfReference(id));
        }

        // ── Invariant 2: all predecessors exist ───────────────────────────────
        // Safe to validate before locking the node shard: the DAG is append-only
        // so existing nodes can never disappear.  If a predecessor is missing,
        // we fail fast without touching the write path.
        for pred_id in &record.predecessors {
            if !pred_id.is_genesis() && !self.nodes.contains_key(pred_id) {
                return Err(DagError::MissingPredecessor {
                    child: id,
                    parent: *pred_id,
                });
            }
        }

        // ── Invariant 1: no duplicate + atomic insert ─────────────────────────
        // `entry()` acquires the shard lock once and either inserts (Vacant) or
        // detects a duplicate (Occupied) atomically — no TOCTOU race.
        let record_arc = match self.nodes.entry(id) {
            Entry::Occupied(_) => return Err(DagError::DuplicateId(id)),
            Entry::Vacant(slot) => {
                let arc = Arc::new(record);
                slot.insert(Arc::clone(&arc));
                arc
            }
        };

        // ── Update reverse index (children) ───────────────────────────────────
        // O(|Π|) inserts into the children map.  Each predecessor gains `id` as
        // a child.  GENESIS entries are indexed too — useful for enumerating
        // first-generation events.
        for pred_id in &record_arc.predecessors {
            self.children.entry(*pred_id).or_default().push(id);
        }

        Ok(record_arc)
    }

    /// Retrieves a record by its [`CausalId`].
    ///
    /// Returns `None` if the ID is not present.
    ///
    /// # Complexity
    ///
    /// O(1) expected — single `DashMap` sharded read.
    #[must_use]
    pub fn get(&self, id: &CausalId) -> Option<Arc<PacrRecord>> {
        self.nodes.get(id).map(|r| Arc::clone(r.value()))
    }

    /// Returns `true` if a record with `id` exists in the DAG.
    ///
    /// # Complexity
    ///
    /// O(1) expected.
    #[must_use]
    pub fn contains(&self, id: &CausalId) -> bool {
        self.nodes.contains_key(id)
    }

    /// Returns the direct causal predecessors of `id` (the Π set).
    ///
    /// Returns `None` if `id` is not present in the DAG.
    ///
    /// # Complexity
    ///
    /// O(1) expected — reads the stored predecessor set.
    #[must_use]
    pub fn predecessors(&self, id: &CausalId) -> Option<SmallVec<[CausalId; 4]>> {
        self.nodes.get(id).map(|r| r.predecessors.clone())
    }

    /// Returns the direct causal successors of `id` (events that cite `id` in Π).
    ///
    /// Returns an empty `SmallVec` if `id` has no known successors yet.
    ///
    /// # Complexity
    ///
    /// O(1) expected — reads the reverse index.
    #[must_use]
    pub fn successors(&self, id: &CausalId) -> SmallVec<[CausalId; 4]> {
        self.children
            .get(id)
            .map(|entry| entry.value().clone())
            .unwrap_or_default()
    }

    /// Returns all transitive causal ancestors of `id` up to `max_depth` hops.
    ///
    /// Uses BFS over the Π edges.  GENESIS predecessors are not included in the
    /// result (they are the definitional "no ancestor" sentinel).
    ///
    /// # Complexity
    ///
    /// O(V + E) where V is the number of ancestors visited and E is the total
    /// predecessor edges traversed.  `max_depth` bounds the frontier.
    #[must_use]
    pub fn ancestry(&self, id: &CausalId, max_depth: usize) -> Vec<CausalId> {
        let mut visited: HashSet<CausalId> = HashSet::new();
        let mut result: Vec<CausalId> = Vec::new();
        let mut queue: std::collections::VecDeque<(CausalId, usize)> =
            std::collections::VecDeque::new();

        if let Some(record) = self.get(id) {
            for pred in &record.predecessors {
                if !pred.is_genesis() {
                    queue.push_back((*pred, 1));
                }
            }
        }

        while let Some((current, depth)) = queue.pop_front() {
            if depth > max_depth || visited.contains(&current) {
                continue;
            }
            visited.insert(current);
            result.push(current);

            if let Some(record) = self.get(&current) {
                for pred in &record.predecessors {
                    if !pred.is_genesis() && !visited.contains(pred) {
                        queue.push_back((*pred, depth + 1));
                    }
                }
            }
        }

        result
    }

    /// Number of records in the DAG.
    ///
    /// # Complexity
    ///
    /// O(1) — `DashMap` tracks length per shard.
    #[must_use]
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Returns `true` if the DAG contains no records.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
}

impl Default for CausalDag {
    fn default() -> Self {
        Self::new()
    }
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};

    /// Build a minimal valid [`PacrRecord`] for testing.
    pub(super) fn make_record(id: u128, preds: &[u128]) -> PacrRecord {
        let predecessors = preds.iter().copied().map(CausalId).collect();
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(predecessors)
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-19),
                time: Estimate::exact(1e-9),
                space: Estimate::exact(128.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate: Estimate::exact(0.5),
            })
            .payload(Bytes::new())
            .build()
            .expect("test record is always valid")
    }

    // ── append ────────────────────────────────────────────────────────────────

    #[test]
    fn append_genesis_record_succeeds() {
        let dag = CausalDag::new();
        let r = dag.append(make_record(1, &[0])); // 0 = GENESIS
        assert!(r.is_ok());
        assert_eq!(dag.len(), 1);
    }

    #[test]
    fn append_duplicate_id_returns_error() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        let err = dag.append(make_record(1, &[0])).unwrap_err();
        assert!(matches!(err, DagError::DuplicateId(_)));
    }

    #[test]
    fn append_missing_predecessor_returns_error() {
        let dag = CausalDag::new();
        // id=2 cites id=99 which does not exist
        let err = dag.append(make_record(2, &[99])).unwrap_err();
        assert!(matches!(err, DagError::MissingPredecessor { .. }));
    }

    #[test]
    fn append_self_reference_returns_error() {
        let dag = CausalDag::new();
        let err = dag.append(make_record(5, &[5])).unwrap_err();
        assert!(matches!(err, DagError::SelfReference(_)));
    }

    #[test]
    fn append_chain_of_three_succeeds() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[1])).unwrap();
        dag.append(make_record(3, &[2])).unwrap();
        assert_eq!(dag.len(), 3);
    }

    // ── get / contains ─────────────────────────────────��──────────────────────

    #[test]
    fn get_returns_correct_record() {
        let dag = CausalDag::new();
        dag.append(make_record(7, &[0])).unwrap();
        let got = dag.get(&CausalId(7)).expect("should be present");
        assert_eq!(got.id, CausalId(7));
    }

    #[test]
    fn get_absent_id_returns_none() {
        let dag = CausalDag::new();
        assert!(dag.get(&CausalId(42)).is_none());
    }

    #[test]
    fn contains_returns_true_after_append() {
        let dag = CausalDag::new();
        dag.append(make_record(10, &[0])).unwrap();
        assert!(dag.contains(&CausalId(10)));
        assert!(!dag.contains(&CausalId(11)));
    }

    // ── predecessors / successors ─────────────────────────────────────────────

    #[test]
    fn predecessors_returns_pi_set() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[0])).unwrap();
        dag.append(make_record(3, &[1, 2])).unwrap();
        let preds = dag.predecessors(&CausalId(3)).unwrap();
        assert!(preds.contains(&CausalId(1)));
        assert!(preds.contains(&CausalId(2)));
        assert_eq!(preds.len(), 2);
    }

    #[test]
    fn successors_empty_for_leaf_node() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        // id=1 has no successors yet
        assert!(dag.successors(&CausalId(1)).is_empty());
    }

    #[test]
    fn successors_populated_after_child_appended() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[1])).unwrap();
        let succ = dag.successors(&CausalId(1));
        assert_eq!(succ.len(), 1);
        assert_eq!(succ[0], CausalId(2));
    }

    #[test]
    fn successors_diamond_shape() {
        // 0 → 1 → 3
        //   ↘ 2 ↗
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[0])).unwrap();
        dag.append(make_record(3, &[1, 2])).unwrap();
        let succ = dag.successors(&CausalId(1));
        assert_eq!(succ.len(), 1);
        assert_eq!(succ[0], CausalId(3));
    }

    // ── ancestry ──────────────────────────────────────────────────────────────

    #[test]
    fn ancestry_linear_chain() {
        // 1 → 2 → 3 (genesis at 0)
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[1])).unwrap();
        dag.append(make_record(3, &[2])).unwrap();
        let ancestors = dag.ancestry(&CausalId(3), 10);
        // Must contain 1 and 2; not 0 (GENESIS filtered) nor 3 (self)
        assert!(ancestors.contains(&CausalId(1)));
        assert!(ancestors.contains(&CausalId(2)));
        assert!(!ancestors.contains(&CausalId(0)));
        assert!(!ancestors.contains(&CausalId(3)));
    }

    #[test]
    fn ancestry_respects_max_depth() {
        // chain: 1 → 2 → 3 → 4
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        dag.append(make_record(2, &[1])).unwrap();
        dag.append(make_record(3, &[2])).unwrap();
        dag.append(make_record(4, &[3])).unwrap();
        // From 4 with depth=1: should only reach 3
        let ancestors = dag.ancestry(&CausalId(4), 1);
        assert_eq!(ancestors.len(), 1);
        assert!(ancestors.contains(&CausalId(3)));
    }

    #[test]
    fn ancestry_empty_for_genesis_child() {
        let dag = CausalDag::new();
        dag.append(make_record(1, &[0])).unwrap();
        // id=1's only predecessor is GENESIS (id=0), which is filtered
        let ancestors = dag.ancestry(&CausalId(1), 10);
        assert!(ancestors.is_empty());
    }

    // ── Structural DAG invariants ─────────────────────────────────────────────

    #[test]
    fn append_only_get_never_returns_different_record() {
        // Once a record is inserted, a second get must return the same id.
        let dag = CausalDag::new();
        dag.append(make_record(42, &[0])).unwrap();
        let first = dag.get(&CausalId(42)).unwrap();
        let second = dag.get(&CausalId(42)).unwrap();
        // Arc::ptr_eq is sufficient: same backing allocation = same record.
        assert!(Arc::ptr_eq(&first, &second));
    }

    #[test]
    fn is_empty_and_len_track_correctly() {
        let dag = CausalDag::new();
        assert!(dag.is_empty());
        assert_eq!(dag.len(), 0);
        dag.append(make_record(1, &[0])).unwrap();
        assert!(!dag.is_empty());
        assert_eq!(dag.len(), 1);
        dag.append(make_record(2, &[1])).unwrap();
        assert_eq!(dag.len(), 2);
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::tests::make_record;
    use super::*;
    use proptest::prelude::*;

    proptest! {
        /// Append-only: every successfully appended record is immediately
        /// retrievable, and its id matches.
        #[test]
        fn appended_record_is_retrievable(id in 1_u128..10_000_u128) {
            let dag = CausalDag::new();
            dag.append(make_record(id, &[0])).unwrap();
            let got = dag.get(&CausalId(id));
            prop_assert!(got.is_some());
            prop_assert_eq!(got.unwrap().id, CausalId(id));
        }

        /// Duplicate IDs are always rejected regardless of content.
        #[test]
        fn duplicate_id_always_rejected(id in 1_u128..10_000_u128) {
            let dag = CausalDag::new();
            dag.append(make_record(id, &[0])).unwrap();
            let err = dag.append(make_record(id, &[0]));
            prop_assert!(err.is_err());
            prop_assert!(matches!(err.unwrap_err(), DagError::DuplicateId(_)));
        }

        /// A chain of N records is always consistent: each record has exactly
        /// the predecessor it was built with, and len() == N.
        #[test]
        fn linear_chain_len_correct(n in 1_usize..50_usize) {
            let dag = CausalDag::new();
            // Record 1 is a genesis child; records 2..n each follow the prior.
            dag.append(make_record(1, &[0])).unwrap();
            for i in 2..=(n as u128) {
                dag.append(make_record(i, &[i - 1])).unwrap();
            }
            prop_assert_eq!(dag.len(), n);
        }

        /// Self-reference is always rejected.
        #[test]
        fn self_reference_always_rejected(id in 1_u128..10_000_u128) {
            let dag = CausalDag::new();
            let err = dag.append(make_record(id, &[id]));
            prop_assert!(matches!(err, Err(DagError::SelfReference(_))));
        }

        /// Missing-predecessor is always rejected (citing an id that was never
        /// inserted).
        #[test]
        fn missing_predecessor_always_rejected(
            id     in 1_u128..5_000_u128,
            parent in 5_001_u128..10_000_u128,   // guaranteed absent
        ) {
            let dag = CausalDag::new();
            let result = dag.append(make_record(id, &[parent]));
            prop_assert!(result.is_err());
            let is_missing = matches!(result.unwrap_err(),
                DagError::MissingPredecessor { .. });
            prop_assert!(is_missing);
        }

        /// O(1) lookup contract: get() on an existing record returns Some in
        /// constant time (checked indirectly via 1 000 sequential lookups on
        /// a DAG of N records — all must succeed).
        #[test]
        fn all_appended_ids_are_retrievable(n in 1_usize..100_usize) {
            let dag = CausalDag::new();
            dag.append(make_record(1, &[0])).unwrap();
            for i in 2..=(n as u128) {
                dag.append(make_record(i, &[i - 1])).unwrap();
            }
            for i in 1..=(n as u128) {
                prop_assert!(dag.get(&CausalId(i)).is_some(),
                    "id={i} should be in DAG");
            }
        }

        /// Successor reverse-index is consistent: if B cites A in Π, then
        /// A.successors() must contain B.
        #[test]
        fn successors_consistent_with_predecessors(
            a in 1_u128..1_000_u128,
            b in 1_001_u128..2_000_u128,
        ) {
            let dag = CausalDag::new();
            dag.append(make_record(a, &[0])).unwrap();
            dag.append(make_record(b, &[a])).unwrap();
            let succ = dag.successors(&CausalId(a));
            prop_assert!(succ.contains(&CausalId(b)),
                "successors({a}) should contain {b}");
        }
    }
}
