//! Pillar: I + II + III. PACR field: ι, Π, Λ, Γ.
//!
//! **Causal Settlement Oracle (CSO)** — resolves disputes between competing
//! PACR record proposals and maintains the global reputation index.
//!
//! # Settlement
//!
//! When two records `A` and `B` claim to be the canonical next event in a
//! causal chain, the CSO uses the following deterministic algorithm:
//!
//! 1. Compute the causal ancestry depth of each record in the live DAG.
//!    Deeper ancestry → more physical work performed → wins.
//! 2. If depths are equal, use lexicographic ordering of `CausalId` as a
//!    deterministic tiebreaker (no clocks, no randomness — Pillar I).
//!
//! # Reputation Index (`CsoIndex`)
//!
//! The CSO maintains a lock-free reputation index keyed by agent ID.
//! Reputation is a weighted composite of three sub-scores:
//!
//! ```text
//! reputation_score = 0.4 × normalized_rho
//!                  + 0.3 × success_rate
//!                  + 0.3 × latency_score
//! ```
//!
//! where:
//! - `normalized_rho`  = clamp(ρ_ema, 0, 1)  — causal return rate EMA.
//! - `success_rate`    = successful_interactions / total_interactions.
//! - `latency_score`   = EMA of per-interaction quality (1.0 when ρ > 0, else 0.0).
//!
//! # Usage
//!
//! ```rust
//! use aevum_core::cso::CsoIndex;
//! use pacr_types::CausalId;
//!
//! let idx = CsoIndex::new();
//! for _ in 0..50 {
//!     idx.record_interaction(CausalId(1), CausalId(2), 1e-20, 0.0, 1.0);
//! }
//! assert!(idx.reputation_score(&CausalId(1)) > 0.8);
//! ```

#![forbid(unsafe_code)]

use std::sync::Arc;

use causal_dag::CausalDag;
use dashmap::DashMap;
use pacr_types::{CausalId, PacrRecord};
use serde::{Deserialize, Serialize};

// ── AgentId ───────────────────────────────────────────────────────────────────

/// Agent identifier — a `CausalId` used as a reputation key.
pub type AgentId = CausalId;

// ── AgentStats (private) ──────────────────────────────────────────────────────

/// Per-agent statistics tracked by the CSO index.
///
/// All fields are plain `f64` / `u64`; the `DashMap` entry holds the lock for
/// concurrent updates (one shard lock per agent, not a global lock).
#[derive(Debug, Clone)]
struct AgentStats {
    /// EMA of the causal return rate ρ.
    rho_ema:              f64,
    /// Total number of interactions observed.
    total_interactions:   u64,
    /// Number of interactions with ρ > 0 (positive causal impact).
    success_interactions: u64,
    /// EMA of the per-interaction quality signal (1.0 on success, 0.0 on failure).
    latency_ema:          f64,
}

impl AgentStats {
    fn new() -> Self {
        Self {
            rho_ema:              0.0,
            total_interactions:   0,
            success_interactions: 0,
            latency_ema:          0.0,
        }
    }

    fn update_ema(current: f64, new_value: f64) -> f64 {
        const ALPHA: f64 = 0.1;
        ALPHA * new_value + (1.0 - ALPHA) * current
    }

    /// Ingest a new ρ observation and update all derived metrics.
    fn ingest(&mut self, rho: f64) {
        self.rho_ema = Self::update_ema(self.rho_ema, rho);
        self.total_interactions += 1;

        let quality = if rho > 0.0 {
            self.success_interactions += 1;
            1.0_f64
        } else {
            0.0_f64
        };

        self.latency_ema = Self::update_ema(self.latency_ema, quality);
    }

    /// Normalized ρ ∈ [0, 1]: clamp the EMA to the non-negative unit interval.
    fn normalized_rho(&self) -> f64 {
        self.rho_ema.clamp(0.0, 1.0)
    }

    /// Fraction of interactions that produced a positive causal return.
    fn success_rate(&self) -> f64 {
        if self.total_interactions == 0 {
            return 0.0;
        }
        self.success_interactions as f64 / self.total_interactions as f64
    }

    /// Latency score ∈ [0, 1] — EMA of per-interaction quality signal.
    fn latency_score(&self) -> f64 {
        self.latency_ema.clamp(0.0, 1.0)
    }

    /// Weighted reputation composite.
    fn reputation_score(&self) -> f64 {
        0.4 * self.normalized_rho()
            + 0.3 * self.success_rate()
            + 0.3 * self.latency_score()
    }
}

// ── CsoIndex ──────────────────────────────────────────────────────────────────

/// Lock-free CSO reputation index.
///
/// Maintains per-agent EMA statistics and serves O(1) reputation queries.
/// The index is backed by a `DashMap` with fine-grained shard locking —
/// concurrent reads and writes from different agents do not contend.
pub struct CsoIndex {
    /// Per-agent statistics, keyed by `AgentId`.
    rho_index: DashMap<AgentId, AgentStats>,
}

impl CsoIndex {
    /// Create a new, empty CSO index.
    #[must_use]
    pub fn new() -> Self {
        Self { rho_index: DashMap::new() }
    }

    /// Update the ρ EMA for `agent` with a new raw ρ value.
    ///
    /// Called externally by `CausalReturnTracker::agent_return_rate()` to
    /// feed aggregate return rates into the reputation index.
    pub fn update_rho(&self, agent: AgentId, new_rho: f64) {
        self.rho_index
            .entry(agent)
            .or_insert_with(AgentStats::new)
            .ingest(new_rho);
    }

    /// Record one complete interaction from `source` → `target`.
    ///
    /// Computes ρ = (phi_after − phi_before) / source_lambda and updates the
    /// source agent's stats.  Silently ignores calls where `source_lambda ≤ 0`.
    pub fn record_interaction(
        &self,
        source:        AgentId,
        target:        AgentId,
        source_lambda: f64,
        phi_before:    f64,
        phi_after:     f64,
    ) {
        if source_lambda <= 0.0 {
            return;
        }
        let rho = (phi_after - phi_before) / source_lambda;
        self.rho_index
            .entry(source)
            .or_insert_with(AgentStats::new)
            .ingest(rho);
        // Ensure target exists in the index (appears in leaderboard).
        self.rho_index.entry(target).or_insert_with(AgentStats::new);
    }

    /// Get the current ρ EMA for `agent`, returning 0.0 if unknown.
    ///
    /// O(1) amortised DashMap lookup.
    #[must_use]
    pub fn get_rho(&self, agent: &AgentId) -> f64 {
        self.rho_index.get(agent).map(|s| s.rho_ema).unwrap_or(0.0)
    }

    /// Compute the weighted reputation score for `agent`.
    ///
    /// Returns 0.0 for unknown agents.
    #[must_use]
    pub fn reputation_score(&self, agent: &AgentId) -> f64 {
        self.rho_index
            .get(agent)
            .map(|s| s.reputation_score())
            .unwrap_or(0.0)
    }

    /// Rank of `agent` in the global leaderboard (1-indexed, lower = better).
    ///
    /// O(n) where n is the number of agents in the index.
    #[must_use]
    pub fn rank(&self, agent: &AgentId) -> usize {
        let target_score = self.reputation_score(agent);
        let above = self
            .rho_index
            .iter()
            .filter(|entry| entry.value().reputation_score() > target_score)
            .count();
        above + 1
    }

    /// Return the top-`n` agents by reputation score.
    ///
    /// Ties broken by `AgentId` descending (deterministic, no clock).
    /// O(n log n) — acceptable for leaderboard queries (not hot path).
    #[must_use]
    pub fn leaderboard(&self, n: usize) -> Vec<(AgentId, f64)> {
        let mut entries: Vec<(AgentId, f64)> = self
            .rho_index
            .iter()
            .map(|entry| (*entry.key(), entry.value().reputation_score()))
            .collect();

        entries.sort_unstable_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| b.0.cmp(&a.0))
        });

        entries.truncate(n);
        entries
    }

    /// Total number of agents tracked by the index.
    #[must_use]
    pub fn agent_count(&self) -> usize {
        self.rho_index.len()
    }
}

impl Default for CsoIndex {
    fn default() -> Self {
        Self::new()
    }
}

// ── HTTP response / request types ─────────────────────────────────────────────

/// Response body for `GET /cso/reputation/{agent_id}`.
#[derive(Debug, Serialize)]
pub struct ReputationResponse {
    pub agent_id:         u128,
    pub rho:              f64,
    pub reputation_score: f64,
    pub rank:             usize,
}

/// Response body for `GET /cso/leaderboard`.
#[derive(Debug, Serialize)]
pub struct LeaderboardResponse {
    pub agents: Vec<LeaderboardEntry>,
}

/// One row in the leaderboard response.
#[derive(Debug, Serialize)]
pub struct LeaderboardEntry {
    pub agent_id:         u128,
    pub reputation_score: f64,
}

/// Request body for `POST /cso/record_interaction`.
#[derive(Debug, Deserialize)]
pub struct RecordInteractionRequest {
    pub source:        u128,
    pub target:        u128,
    pub source_lambda: f64,
    pub phi_before:    f64,
    pub phi_after:     f64,
}

// ── Axum HTTP handlers ────────────────────────────────────────────────────────

use axum::{
    Json,
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
};

/// `GET /cso/reputation/:agent_id`
///
/// Returns `{ agent_id, rho, reputation_score, rank }`.
/// Returns 404 if the agent has not yet been observed.
pub async fn handle_get_reputation(
    State(idx): State<Arc<CsoIndex>>,
    Path(agent_id): Path<u128>,
) -> impl IntoResponse {
    let agent = CausalId(agent_id);
    if idx.rho_index.get(&agent).is_none() {
        return (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({ "error": "agent not found" })),
        )
            .into_response();
    }
    let resp = ReputationResponse {
        agent_id,
        rho:              idx.get_rho(&agent),
        reputation_score: idx.reputation_score(&agent),
        rank:             idx.rank(&agent),
    };
    (StatusCode::OK, Json(resp)).into_response()
}

/// `GET /cso/leaderboard`
///
/// Returns the top-10 agents by reputation score.
pub async fn handle_get_leaderboard(
    State(idx): State<Arc<CsoIndex>>,
) -> impl IntoResponse {
    let agents: Vec<LeaderboardEntry> = idx
        .leaderboard(10)
        .into_iter()
        .map(|(id, score)| LeaderboardEntry {
            agent_id:         id.0,
            reputation_score: score,
        })
        .collect();
    Json(LeaderboardResponse { agents })
}

/// `POST /cso/record_interaction`
///
/// Accepts `{ source, target, source_lambda, phi_before, phi_after }`.
/// Returns 204 No Content on success.
pub async fn handle_record_interaction(
    State(idx): State<Arc<CsoIndex>>,
    Json(body): Json<RecordInteractionRequest>,
) -> impl IntoResponse {
    idx.record_interaction(
        CausalId(body.source),
        CausalId(body.target),
        body.source_lambda,
        body.phi_before,
        body.phi_after,
    );
    StatusCode::NO_CONTENT
}

// ── Settlement outcome ────────────────────────────────────────────────────────

/// The CSO's verdict when settling two competing proposals.
#[derive(Debug, Clone)]
pub struct SettlementOutcome {
    pub winner:       CausalId,
    pub loser:        CausalId,
    pub winner_depth: usize,
    pub loser_depth:  usize,
}

// ── CausalSettlementOracle ────────────────────────────────────────────────────

/// Causal Settlement Oracle — resolves disputes between competing PACR records.
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
    /// before being submitted to the CSO.
    ///
    /// # Special cases
    ///
    /// - If both IDs are identical, `winner == loser` and both depths are equal.
    /// - If a record is not in the DAG, its depth is 0 (no ancestry evidence).
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

    /// Compute the causal ancestry depth of a record (BFS, O(V+E)).
    #[must_use]
    fn ancestry_depth(&self, id: CausalId) -> usize {
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

    // Convenience: AgentId-style shorthand for tests only.
    fn aid(v: u128) -> CausalId { CausalId(v) }

    // ── CsoIndex: reputation thresholds ──────────────────────────────────────

    #[test]
    fn high_rho_interactions_produce_high_reputation() {
        let idx = CsoIndex::new();
        // phi advances from 0 → 1 each call, lambda = 1e-20 → ρ = 1e20 → clamped 1.0
        for _ in 0..50 {
            idx.record_interaction(aid(1), aid(2), 1e-20, 0.0, 1.0);
        }
        let score = idx.reputation_score(&aid(1));
        assert!(
            score > 0.8,
            "expected reputation > 0.8 after 50 high-ρ interactions, got {score:.4}"
        );
    }

    #[test]
    fn zero_rho_interactions_produce_low_reputation() {
        let idx = CsoIndex::new();
        // phi does not change → ρ = 0
        for _ in 0..50 {
            idx.record_interaction(aid(3), aid(4), 1e-20, 0.5, 0.5);
        }
        let score = idx.reputation_score(&aid(3));
        assert!(
            score < 0.2,
            "expected reputation < 0.2 after 50 zero-ρ interactions, got {score:.4}"
        );
    }

    // ── CsoIndex: update_rho path ─────────────────────────────────────────────

    #[test]
    fn update_rho_high_values_produce_high_reputation() {
        let idx = CsoIndex::new();
        for _ in 0..50 {
            idx.update_rho(aid(10), 1.0);
        }
        let score = idx.reputation_score(&aid(10));
        assert!(score > 0.8, "update_rho(1.0)×50 → {score:.4} should exceed 0.8");
    }

    #[test]
    fn update_rho_zero_produces_low_reputation() {
        let idx = CsoIndex::new();
        for _ in 0..50 {
            idx.update_rho(aid(11), 0.0);
        }
        let score = idx.reputation_score(&aid(11));
        assert!(score < 0.2, "update_rho(0.0)×50 → {score:.4} should be below 0.2");
    }

    // ── CsoIndex: leaderboard ─────────────────────────────────────────────────

    #[test]
    fn leaderboard_sorted_descending_by_score() {
        let idx = CsoIndex::new();

        // Agent 100: high ρ
        for _ in 0..50 {
            idx.record_interaction(aid(100), aid(999), 1e-20, 0.0, 1.0);
        }
        // Agent 200: medium ρ (ρ = 0.5 → clamped 0.5)
        for _ in 0..50 {
            idx.record_interaction(aid(200), aid(999), 2.0, 0.0, 1.0);
        }
        // Agent 300: zero ρ
        for _ in 0..50 {
            idx.record_interaction(aid(300), aid(999), 1e-20, 0.5, 0.5);
        }

        let board = idx.leaderboard(10);
        assert!(!board.is_empty());

        // Scores must be non-increasing.
        for w in board.windows(2) {
            assert!(
                w[0].1 >= w[1].1,
                "leaderboard not sorted: {:.4} before {:.4}",
                w[0].1,
                w[1].1
            );
        }

        // Agent 100 must outrank agent 300.
        let s100 = idx.reputation_score(&aid(100));
        let s300 = idx.reputation_score(&aid(300));
        assert!(s100 > s300, "high-ρ agent ({s100:.4}) must beat zero-ρ agent ({s300:.4})");
    }

    // ── CsoIndex: edge cases ──────────────────────────────────────────────────

    #[test]
    fn get_rho_unknown_agent_returns_zero() {
        let idx = CsoIndex::new();
        assert_eq!(idx.get_rho(&aid(999)), 0.0);
    }

    #[test]
    fn reputation_score_unknown_agent_returns_zero() {
        let idx = CsoIndex::new();
        assert_eq!(idx.reputation_score(&aid(999)), 0.0);
    }

    #[test]
    fn rank_one_is_highest_score() {
        let idx = CsoIndex::new();
        for _ in 0..50 {
            idx.update_rho(aid(1), 1.0);
        }
        for _ in 0..50 {
            idx.update_rho(aid(2), 0.0);
        }
        assert_eq!(idx.rank(&aid(1)), 1, "high-score agent must be rank 1");
        assert_eq!(idx.rank(&aid(2)), 2, "low-score agent must be rank 2");
    }

    // ── CausalSettlementOracle ────────────────────────────────────────────────

    #[test]
    fn settle_identical_ids_returns_same_winner_and_loser() {
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let r = minimal_record(1, &[]);
        dag.append(r.clone()).unwrap();
        let outcome = cso.settle(&r, &r);
        assert_eq!(outcome.winner, outcome.loser);
    }

    #[test]
    fn settle_deeper_ancestry_wins() {
        let dag = Arc::new(CausalDag::new());
        let root    = minimal_record(1, &[]);
        let child_a = minimal_record(2, &[1]);
        dag.append(root).unwrap();
        dag.append(child_a.clone()).unwrap();

        let child_b = minimal_record(3, &[]);
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let outcome = cso.settle(&child_a, &child_b);
        assert_eq!(outcome.winner, child_a.id);
        assert_eq!(outcome.loser,  child_b.id);
    }

    #[test]
    fn settle_equal_depth_uses_lexicographic_tiebreak() {
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));

        let low_id  = minimal_record(10, &[]);
        let high_id = minimal_record(20, &[]);

        let outcome = cso.settle(&low_id, &high_id);
        assert_eq!(outcome.winner, high_id.id);
    }

    #[test]
    fn settle_records_not_in_dag_both_depth_zero() {
        let dag = Arc::new(CausalDag::new());
        let cso = CausalSettlementOracle::new(Arc::clone(&dag));
        let a = minimal_record(100, &[]);
        let b = minimal_record(200, &[]);
        let outcome = cso.settle(&a, &b);
        assert_eq!(outcome.winner_depth, 0);
        assert_eq!(outcome.loser_depth,  0);
    }
}
