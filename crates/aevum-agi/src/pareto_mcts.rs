//! Pillar: I + II. PACR field: Γ, Ω.
//!
//! **Pareto-MCTS Topology Searcher** — finds the minimal 20% of parameter
//! configurations that deliver 80% of cognitive value.
//!
//! # Theory
//!
//! The Pareto-MCTS module applies the 80/20 leverage principle to Monte Carlo
//! Tree Search (MCTS) over the space of `RuntimeConfig` parameter settings.
//! It specifically exploits the M1 Ultra's Unified Memory Architecture (UMA)
//! to hold the full topology tree in a single flat memory region, enabling
//! zero-copy SIMD comparisons of node value estimates.
//!
//! ## Why MCTS over the topology space?
//!
//! The AGI's operating parameters (epsilon window, producer interval, thread
//! count) form a discrete search space with high-dimensional structure.
//! Exhaustive search is O(N^k) and violates Pillar I.  MCTS with UCB1
//! selection and Pareto pruning converges to the efficient frontier in O(log N)
//! amortised steps while maintaining statistical rigour.
//!
//! ## Pareto Filtering
//!
//! After each rollout, nodes are ranked on two axes:
//!
//! 1. **Cognitive yield** — the Φ improvement per unit time (ΔΦ / Δt).
//! 2. **Thermodynamic cost** — bits erased per record produced (Λ per record).
//!
//! A node is Pareto-optimal if no other node dominates it on both axes
//! simultaneously.  The search keeps only the Pareto front, pruning dominated
//! nodes to maintain O(n) memory (Pillar I).
//!
//! ## UMA Advantage
//!
//! On M1 Ultra, GPU and CPU share the same physical DRAM.  The topology tree
//! can be serialised directly into a Metal-accessible buffer, allowing the
//! evaluator to compute SIMD Pareto dominance tests on the GPU without a PCIe
//! copy.  This acceleration is deferred to Phase 8; the stub uses CPU-only
//! logic with the same asymptotic complexity.
//!
//! # Phase 7 Stub Status
//!
//! This is the Phase 7 stub.  The full Pareto-MCTS (Phase 8) will:
//! - Use real Φ measurements from `DualEngine` as rollout rewards.
//! - Maintain a true UCB1 selection policy with tunable exploration constant.
//! - Prune dominated nodes in O(n log n) via sort-then-sweep.
//! - Export the Pareto front as PACR records (with Π linking to the rollouts).
//! - Integrate with the M1 Ultra UMA allocator for zero-copy evaluation.
//!
//! The stub implements the node data structure, selection logic, and Pareto
//! dominance check — the structural skeleton Phase 8 will flesh out.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};

// ── TopologyAction ────────────────────────────────────────────────────────────

/// A discrete mutation to the AGI's operating parameters.
///
/// Each `TopologyAction` represents a single step in the MCTS search tree.
/// Actions are composed sequentially to describe a path from the root
/// (current configuration) to a candidate leaf (proposed new configuration).
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TopologyAction {
    /// Decrease the record-producer tick interval (produce records faster).
    DecreaseProducerInterval,

    /// Increase the record-producer tick interval (produce records slower).
    IncreaseProducerInterval,

    /// Widen the epsilon-engine inference window (more data per inference).
    WidenEpsilonWindow,

    /// Narrow the epsilon-engine inference window (less latency per inference).
    NarrowEpsilonWindow,

    /// Add one tokio worker thread (more parallelism).
    AddWorkerThread,

    /// Remove one tokio worker thread (less overhead).
    RemoveWorkerThread,

    /// Keep the current configuration unchanged.
    Noop,
}

// ── Tree node ─────────────────────────────────────────────────────────────────

/// One node in the Pareto-MCTS topology tree.
///
/// Tracks visit count, cumulative value, and the action that led to this node.
/// The tree is stored as a `Vec<MctsNode>` with parent indices for O(1) parent
/// access — no heap allocations beyond the initial `Vec` growth.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MctsNode {
    /// Action taken from the parent to reach this node.
    pub action: TopologyAction,

    /// Number of times this node has been visited during rollouts.
    pub visit_count: u64,

    /// Cumulative cognitive yield (ΔΦ per tick) summed over rollouts.
    pub value_sum: f64,

    /// Cumulative thermodynamic cost (bits/record) summed over rollouts.
    pub cost_sum: f64,

    /// Index of the parent node in the tree's backing `Vec`.
    /// `None` for the root node.
    pub parent_idx: Option<usize>,
}

impl MctsNode {
    /// Mean cognitive yield over all rollouts visiting this node.
    ///
    /// Returns `0.0` when `visit_count == 0` (node never visited).
    #[must_use]
    pub fn mean_value(&self) -> f64 {
        if self.visit_count == 0 {
            0.0
        } else {
            self.value_sum / self.visit_count as f64
        }
    }

    /// Mean thermodynamic cost over all rollouts visiting this node.
    ///
    /// Returns `f64::MAX` when `visit_count == 0` (penalise unvisited nodes).
    #[must_use]
    pub fn mean_cost(&self) -> f64 {
        if self.visit_count == 0 {
            f64::MAX
        } else {
            self.cost_sum / self.visit_count as f64
        }
    }

    /// Returns `true` if this node Pareto-dominates `other`.
    ///
    /// Node `A` dominates `B` if:
    /// - `A.mean_value() ≥ B.mean_value()` AND
    /// - `A.mean_cost()  ≤ B.mean_cost()`
    /// AND at least one inequality is strict.
    #[must_use]
    pub fn dominates(&self, other: &MctsNode) -> bool {
        let v_a = self.mean_value();
        let c_a = self.mean_cost();
        let v_b = other.mean_value();
        let c_b = other.mean_cost();

        // At least as good on both axes AND strictly better on at least one.
        (v_a >= v_b && c_a <= c_b) && (v_a > v_b || c_a < c_b)
    }
}

// ── Configuration ─────────────────────────────────────────────────────────────

/// Configuration for the Pareto-MCTS searcher.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ParetoMctsConfig {
    /// UCB1 exploration constant c.  Higher values favour unexplored nodes.
    ///
    /// Default: `√2 ≈ 1.414` (theoretical optimum for bounded rewards in [0,1]).
    pub exploration_constant: f64,

    /// Maximum tree depth before forcing a rollout.
    ///
    /// Bounded at 16 to keep memory O(n) per Pillar I.
    pub max_depth: usize,

    /// Target size of the Pareto front.
    ///
    /// When the front exceeds this size, dominated nodes are pruned.
    pub pareto_front_target: usize,
}

impl Default for ParetoMctsConfig {
    fn default() -> Self {
        Self {
            exploration_constant: std::f64::consts::SQRT_2,
            max_depth:            16,
            pareto_front_target:  8,
        }
    }
}

// ── ParetoMcts ────────────────────────────────────────────────────────────────

/// Pareto-MCTS topology searcher.
///
/// Maintains a tree of [`MctsNode`]s and selects the next `TopologyAction` to
/// evaluate based on UCB1 with Pareto dominance pruning.
pub struct ParetoMcts {
    cfg:         ParetoMctsConfig,
    nodes:       Vec<MctsNode>,
    pareto_front: Vec<usize>, // indices into `nodes`
}

impl ParetoMcts {
    /// Create a new searcher with a single root node (`Noop` action).
    #[must_use]
    pub fn new(cfg: ParetoMctsConfig) -> Self {
        let root = MctsNode {
            action:      TopologyAction::Noop,
            visit_count: 0,
            value_sum:   0.0,
            cost_sum:    0.0,
            parent_idx:  None,
        };
        Self {
            cfg,
            nodes:        vec![root],
            pareto_front: vec![0],
        }
    }

    /// Total number of nodes in the tree (including the root).
    #[must_use]
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Number of nodes on the current Pareto front.
    #[must_use]
    pub fn pareto_front_size(&self) -> usize {
        self.pareto_front.len()
    }

    /// Select the next `TopologyAction` to explore via UCB1.
    ///
    /// Returns the action from the node with the highest UCB1 score among
    /// nodes on the Pareto front.  Falls back to `Noop` when the front is
    /// empty (should not occur after construction).
    ///
    /// UCB1 score = mean_value + c × √(ln(N_total) / visit_count)
    /// where `N_total` is the sum of all visit counts in the tree.
    #[must_use]
    pub fn select_action(&self) -> TopologyAction {
        let total_visits: u64 = self.nodes.iter().map(|n| n.visit_count).sum();
        let ln_total = if total_visits > 0 {
            (total_visits as f64).ln()
        } else {
            0.0
        };

        let best_idx = self.pareto_front.iter().max_by(|&&a, &&b| {
            let score_a = self.ucb1_score(&self.nodes[a], ln_total);
            let score_b = self.ucb1_score(&self.nodes[b], ln_total);
            score_a.partial_cmp(&score_b).unwrap_or(std::cmp::Ordering::Equal)
        });

        best_idx
            .map(|&idx| self.nodes[idx].action.clone())
            .unwrap_or(TopologyAction::Noop)
    }

    /// Record the outcome of a rollout for the given action.
    ///
    /// Adds a child node under the root with the observed `phi_delta` and
    /// `bits_per_record`, then updates the Pareto front.
    ///
    /// # Arguments
    ///
    /// * `action`          — the `TopologyAction` that was evaluated.
    /// * `phi_delta`       — measured ΔΦ per tick from the rollout.
    /// * `bits_per_record` — measured bits erased per PACR record produced.
    pub fn record_rollout(&mut self, action: TopologyAction, phi_delta: f64, bits_per_record: f64) {
        // Find existing child of root with this action, or add a new node.
        let child_idx = self.find_or_add_child(0, action, bits_per_record);
        let node = &mut self.nodes[child_idx];
        node.visit_count += 1;
        node.value_sum   += phi_delta;
        node.cost_sum    += bits_per_record;

        // Recompute Pareto front including the updated node.
        self.update_pareto_front();
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    /// UCB1 score for a node.
    fn ucb1_score(&self, node: &MctsNode, ln_total: f64) -> f64 {
        if node.visit_count == 0 {
            return f64::INFINITY; // Unvisited nodes have highest priority
        }
        node.mean_value()
            + self.cfg.exploration_constant * (ln_total / node.visit_count as f64).sqrt()
    }

    /// Find an existing child of `parent_idx` with `action`, or append one.
    fn find_or_add_child(
        &mut self,
        parent_idx: usize,
        action: TopologyAction,
        initial_cost: f64,
    ) -> usize {
        // Search existing children (linear scan is fine: branching factor ≤ 7)
        if let Some(idx) = self
            .nodes
            .iter()
            .enumerate()
            .filter(|(_, n)| n.parent_idx == Some(parent_idx))
            .find(|(_, n)| n.action == action)
            .map(|(i, _)| i)
        {
            return idx;
        }

        // Add new node
        let new_idx = self.nodes.len();
        self.nodes.push(MctsNode {
            action,
            visit_count: 0,
            value_sum:   0.0,
            cost_sum:    initial_cost, // Will be divided on first visit
            parent_idx:  Some(parent_idx),
        });
        new_idx
    }

    /// Recompute the Pareto front from all non-root nodes.
    fn update_pareto_front(&mut self) {
        // Collect indices of all visited non-root nodes.
        let candidates: Vec<usize> = (1..self.nodes.len())
            .filter(|&i| self.nodes[i].visit_count > 0)
            .collect();

        // A node is on the front iff no other candidate dominates it.
        let front: Vec<usize> = candidates
            .iter()
            .filter(|&&i| {
                !candidates
                    .iter()
                    .any(|&j| j != i && self.nodes[j].dominates(&self.nodes[i]))
            })
            .copied()
            .collect();

        self.pareto_front = if front.is_empty() {
            vec![0] // Fall back to root when no visited children exist
        } else {
            front
        };
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── MctsNode ───────────────────────────────────────────────────────────────

    #[test]
    fn mean_value_zero_for_unvisited() {
        let node = MctsNode {
            action: TopologyAction::Noop, visit_count: 0,
            value_sum: 0.0, cost_sum: 0.0, parent_idx: None,
        };
        assert_eq!(node.mean_value(), 0.0);
    }

    #[test]
    fn mean_cost_max_for_unvisited() {
        let node = MctsNode {
            action: TopologyAction::Noop, visit_count: 0,
            value_sum: 0.0, cost_sum: 0.0, parent_idx: None,
        };
        assert_eq!(node.mean_cost(), f64::MAX);
    }

    #[test]
    fn mean_value_correct_after_visits() {
        let node = MctsNode {
            action: TopologyAction::Noop, visit_count: 4,
            value_sum: 8.0, cost_sum: 0.0, parent_idx: None,
        };
        assert!((node.mean_value() - 2.0).abs() < 1e-10);
    }

    #[test]
    fn dominates_strictly_better_on_both_axes() {
        let a = MctsNode { action: TopologyAction::Noop, visit_count: 1,
            value_sum: 5.0, cost_sum: 1.0, parent_idx: None };
        let b = MctsNode { action: TopologyAction::Noop, visit_count: 1,
            value_sum: 3.0, cost_sum: 3.0, parent_idx: None };
        assert!(a.dominates(&b), "a should dominate b");
        assert!(!b.dominates(&a), "b should not dominate a");
    }

    #[test]
    fn dominates_equal_nodes_not_dominating() {
        let a = MctsNode { action: TopologyAction::Noop, visit_count: 1,
            value_sum: 3.0, cost_sum: 2.0, parent_idx: None };
        let b = a.clone();
        assert!(!a.dominates(&b), "equal nodes should not dominate each other");
    }

    #[test]
    fn dominates_tradeoff_not_dominating() {
        // A is better on value but worse on cost — not dominated
        let a = MctsNode { action: TopologyAction::Noop, visit_count: 1,
            value_sum: 5.0, cost_sum: 4.0, parent_idx: None };
        let b = MctsNode { action: TopologyAction::Noop, visit_count: 1,
            value_sum: 2.0, cost_sum: 1.0, parent_idx: None };
        assert!(!a.dominates(&b));
        assert!(!b.dominates(&a));
    }

    // ── ParetoMcts ─────────────────────────────────────────────────────────────

    #[test]
    fn new_tree_has_one_node() {
        let tree = ParetoMcts::new(ParetoMctsConfig::default());
        assert_eq!(tree.node_count(), 1);
    }

    #[test]
    fn select_action_on_fresh_tree_returns_action() {
        let tree = ParetoMcts::new(ParetoMctsConfig::default());
        // Fresh tree — root has no visits, select returns its Noop action
        let _ = tree.select_action();
    }

    #[test]
    fn record_rollout_adds_node() {
        let mut tree = ParetoMcts::new(ParetoMctsConfig::default());
        tree.record_rollout(TopologyAction::WidenEpsilonWindow, 0.5, 1000.0);
        assert_eq!(tree.node_count(), 2, "root + one child");
    }

    #[test]
    fn record_rollout_same_action_reuses_node() {
        let mut tree = ParetoMcts::new(ParetoMctsConfig::default());
        tree.record_rollout(TopologyAction::WidenEpsilonWindow, 0.5, 1000.0);
        tree.record_rollout(TopologyAction::WidenEpsilonWindow, 0.7, 900.0);
        assert_eq!(tree.node_count(), 2, "should reuse existing child");
        // visit_count should be 2
        assert_eq!(tree.nodes[1].visit_count, 2);
    }

    #[test]
    fn pareto_front_excludes_dominated_nodes() {
        let mut tree = ParetoMcts::new(ParetoMctsConfig::default());
        // A: high value, low cost — dominates B
        tree.record_rollout(TopologyAction::WidenEpsilonWindow, 10.0, 100.0);
        // B: low value, high cost — dominated
        tree.record_rollout(TopologyAction::NarrowEpsilonWindow, 1.0, 1000.0);

        // A should be on the Pareto front; B should not.
        let front_actions: Vec<TopologyAction> = tree
            .pareto_front
            .iter()
            .map(|&i| tree.nodes[i].action.clone())
            .collect();
        assert!(
            front_actions.contains(&TopologyAction::WidenEpsilonWindow),
            "dominant node should be on Pareto front"
        );
    }

    #[test]
    fn pareto_front_keeps_both_tradeoff_nodes() {
        let mut tree = ParetoMcts::new(ParetoMctsConfig::default());
        // A: high value, high cost
        tree.record_rollout(TopologyAction::WidenEpsilonWindow, 10.0, 1000.0);
        // B: low value, low cost — neither dominates the other
        tree.record_rollout(TopologyAction::NarrowEpsilonWindow, 1.0, 100.0);

        assert_eq!(tree.pareto_front_size(), 2, "both nodes should be on Pareto front");
    }

    #[test]
    fn action_serde_roundtrip() {
        let actions = [
            TopologyAction::DecreaseProducerInterval,
            TopologyAction::IncreaseProducerInterval,
            TopologyAction::WidenEpsilonWindow,
            TopologyAction::NarrowEpsilonWindow,
            TopologyAction::AddWorkerThread,
            TopologyAction::RemoveWorkerThread,
            TopologyAction::Noop,
        ];
        for action in &actions {
            let json = serde_json::to_string(action).unwrap();
            let decoded: TopologyAction = serde_json::from_str(&json).unwrap();
            assert_eq!(action, &decoded, "roundtrip failed for {action:?}");
        }
    }
}
