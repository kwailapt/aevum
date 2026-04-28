// crates/causal-dag/src/lib.rs
//
// Pillar: I (causal partial order). PACR fields: ι, Π.
// A lock-free, append-only directed acyclic graph.
// Nodes = CausalId, Edges = Predecessor relationships.
// This is the backbone of all causal reasoning in Aevum.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(clippy::cast_precision_loss, clippy::cast_possible_truncation, clippy::cast_sign_loss, clippy::cast_possible_wrap, clippy::similar_names, clippy::doc_markdown, clippy::unreadable_literal, clippy::redundant_closure, clippy::unwrap_or_default, clippy::doc_overindented_list_items, clippy::cloned_instead_of_copied, clippy::needless_pass_by_value, clippy::cast_lossless, clippy::module_name_repetitions, clippy::into_iter_without_iter, clippy::unnested_or_patterns, clippy::let_underscore_untyped, clippy::manual_let_else, clippy::suspicious_open_options, clippy::iter_not_returning_iterator, clippy::must_use_candidate, clippy::ptr_arg, clippy::manual_midpoint, clippy::map_unwrap_or, clippy::bool_to_int_with_if, clippy::missing_panics_doc)]

use dashmap::DashMap;
use pacr_types::{CausalId, PacrRecord};
use smallvec::SmallVec;
use std::sync::Arc;
use thiserror::Error;

/// A lock-free, append-only causal DAG.
///
/// Design decisions:
/// - `DashMap` provides lock-free concurrent reads and sharded-lock writes.
///   At 10^11 scale, this is preferable to a single RwLock.
/// - Append-only: once a node is inserted, it is never modified or removed.
///   This mirrors the physical irreversibility of causal events.
/// - No global ordering: nodes are accessed by CausalId or traversed via Π edges.
///   There is NO `iter()` that returns nodes in any total order — because
///   total order doesn't exist in a distributed causal system (Axiom I).
pub struct CausalDag {
    /// Map from event ID to its record (or at minimum, its predecessor set).
    /// Using Arc<PacrRecord> for zero-copy sharing across readers.
    nodes: DashMap<CausalId, Arc<PacrRecord>>,

    /// Reverse index: for each event, which events cite it as a predecessor?
    /// Needed for forward traversal (from cause to effect).
    children: DashMap<CausalId, SmallVec<[CausalId; 8]>>,
}

#[derive(Debug, Error)]
pub enum DagError {
    #[error("Duplicate causal ID: {0}")]
    DuplicateId(CausalId),

    #[error("Missing predecessor: event {child} references unknown predecessor {parent}")]
    MissingPredecessor {
        child: CausalId,
        parent: CausalId,
    },

    #[error("Causal cycle detected: event {0} would create a cycle")]
    CycleDetected(CausalId),
}

impl CausalDag {
    /// Creates a new empty DAG.
    #[must_use]
    pub fn new() -> Self {
        Self {
            nodes: DashMap::new(),
            children: DashMap::new(),
        }
    }

    /// Creates a DAG with pre-allocated capacity (for known-scale deployments).
    #[must_use]
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            nodes: DashMap::with_capacity(capacity),
            children: DashMap::with_capacity(capacity),
        }
    }

    /// Appends a PACR record to the DAG.
    ///
    /// Validates:
    /// 1. No duplicate ID (append-only, no overwrites)
    /// 2. All predecessors exist (or are GENESIS)
    /// 3. No self-reference (checked by PacrRecord::validate, re-checked here)
    ///
    /// # Errors
    /// Returns `DagError` if any validation fails.
    ///
    /// Complexity: O(|Π|) — linear in the number of predecessors.
    pub fn append(&self, record: PacrRecord) -> Result<Arc<PacrRecord>, DagError> {
        let id = record.id;

        // Check for duplicate
        if self.nodes.contains_key(&id) {
            return Err(DagError::DuplicateId(id));
        }

        // Validate all predecessors exist
        for pred_id in &record.predecessors {
            if !pred_id.is_genesis() && !self.nodes.contains_key(pred_id) {
                return Err(DagError::MissingPredecessor {
                    child: id,
                    parent: *pred_id,
                });
            }
        }

        // Self-reference check
        if record.predecessors.contains(&id) {
            return Err(DagError::CycleDetected(id));
        }

        let record = Arc::new(record);

        // Insert node
        self.nodes.insert(id, Arc::clone(&record));

        // Update reverse index (children)
        for pred_id in &record.predecessors {
            self.children
                .entry(*pred_id)
                .or_insert_with(SmallVec::new)
                .push(id);
        }

        Ok(record)
    }

    /// Retrieves a record by its causal ID.
    /// O(1) expected time.
    #[must_use]
    pub fn get(&self, id: &CausalId) -> Option<Arc<PacrRecord>> {
        self.nodes.get(id).map(|r| Arc::clone(r.value()))
    }

    /// Returns the direct causal predecessors of an event.
    /// O(1) — just reads the stored predecessor set.
    #[must_use]
    pub fn predecessors(&self, id: &CausalId) -> Option<SmallVec<[CausalId; 4]>> {
        self.nodes.get(id).map(|r| r.predecessors.clone())
    }

    /// Returns the direct causal successors (children) of an event.
    /// O(1) expected time via the reverse index.
    #[must_use]
    pub fn successors(&self, id: &CausalId) -> SmallVec<[CausalId; 8]> {
        self.children
            .get(id)
            .map(|entry| entry.value().clone())
            .unwrap_or_default()
    }

    /// Returns the causal ancestry of an event (all transitive predecessors).
    /// Implements BFS over the Π edges.
    ///
    /// Complexity: O(|ancestors|) — linear in the number of ancestors found.
    /// This can be very large for deep DAGs. Consider depth-limiting in production.
    pub fn ancestry(&self, id: &CausalId, max_depth: usize) -> Vec<CausalId> {
        let mut visited = Vec::new();
        let mut queue = std::collections::VecDeque::new();

        if let Some(record) = self.get(id) {
            for pred in &record.predecessors {
                if !pred.is_genesis() {
                    queue.push_back((*pred, 1_usize));
                }
            }
        }

        while let Some((current, depth)) = queue.pop_front() {
            if depth > max_depth || visited.contains(&current) {
                continue;
            }
            visited.push(current);
            if let Some(record) = self.get(&current) {
                for pred in &record.predecessors {
                    if !pred.is_genesis() {
                        queue.push_back((*pred, depth + 1));
                    }
                }
            }
        }

        visited
    }

    /// Number of events in the DAG.
    #[must_use]
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Returns true if the DAG is empty.
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

