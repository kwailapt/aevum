// crates/aevum-mcp-server/src/resources/context.rs
//
// Pillar: I/II/III. PACR field: ALL.
// aevum_context: MCP Resource exposing current causal state summary.
//
// SsnBroadcaster — Structural State Network broadcaster.
// Observes (S_T, H_T) pairs from remember.rs after each record append,
// maintains a rolling window, classifies trend, and broadcasts non-Stable
// events to any connected SSE subscribers.
//
// HTTP mode: SSE endpoint /events subscribes to this channel.
// stdio mode: broadcast fires silently (zero overhead — no receivers).

#![forbid(unsafe_code)]

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use tokio::sync::broadcast;

// ── Constants ─────────────────────────────────────────────────────────────────

/// Broadcast channel capacity. Lagging receivers are dropped (bounded memory).
const CHANNEL_CAP: usize = 64;

/// How many (S_T, H_T) observations constitute a trend window.
const TREND_WINDOW: usize = 3;

/// Minimum per-step delta required to count as a rising trend.
const TREND_DELTA: f64 = 0.05;

// ── Types ─────────────────────────────────────────────────────────────────────

/// A causal state change event broadcast to connected clients.
///
/// Fields are read by the HTTP SSE handler (`transport/http.rs`) under the
/// `transport-http` feature. In the default (stdio-only) build no SSE consumer
/// exists, hence the `allow(dead_code)` below.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct StateChange {
    pub record_count: u64,
    pub s_t: f64,
    pub h_t: f64,
    pub trend: StateTrend,
}

/// Pillar III classification of the current information-theoretic regime.
#[derive(Debug, Clone, PartialEq)]
pub enum StateTrend {
    /// S_T rising, H_T stable — system is discovering learnable structure.
    StructureDiscovery,
    /// H_T rising, S_T stable — encountering irreducible noise; investigate.
    EntropyIncrease,
    /// Both rising — new dynamical regime; possible phase transition.
    PhaseTransition,
    /// Neither rising above threshold — steady state.
    Stable,
}

// ── SsnBroadcaster ────────────────────────────────────────────────────────────

/// Structural State Network broadcaster.
///
/// Thread-safe: the window is protected by `std::sync::Mutex` (held for
/// nanoseconds, never across await points). The broadcast channel is
/// `tokio::sync::broadcast` (lock-free MPMC ring buffer).
pub struct SsnBroadcaster {
    tx: broadcast::Sender<StateChange>,
    /// Rolling window of (S_T, H_T) pairs, capped at TREND_WINDOW.
    window: Mutex<Vec<(f64, f64)>>,
    record_count: AtomicU64,
}

impl SsnBroadcaster {
    /// Create a new broadcaster. Zero cost until `subscribe()` is called.
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(CHANNEL_CAP);
        Self {
            tx,
            window: Mutex::new(Vec::with_capacity(TREND_WINDOW + 1)),
            record_count: AtomicU64::new(0),
        }
    }

    /// Subscribe to state change events. Returns a `Receiver` for SSE.
    /// Each subscriber gets their own receive handle; lagging receivers are
    /// silently dropped (bounded memory — Pillar I).
    ///
    /// Used by `transport/http.rs` under the `transport-http` feature.
    #[cfg_attr(not(feature = "transport-http"), allow(dead_code))]
    pub fn subscribe(&self) -> broadcast::Receiver<StateChange> {
        self.tx.subscribe()
    }

    /// Called after every `remember.rs` record append.
    /// Updates the rolling window and broadcasts if trend is non-Stable.
    pub fn observe(&self, s_t: f64, h_t: f64) {
        let count = self.record_count.fetch_add(1, Ordering::Relaxed) + 1;

        let trend = {
            let mut w = self.window.lock().expect("SSN window mutex poisoned");
            w.push((s_t, h_t));
            if w.len() > TREND_WINDOW {
                let excess = w.len() - TREND_WINDOW;
                w.drain(..excess);
            }
            classify_trend(&w)
        };

        // Only broadcast non-Stable events (SSN is a phase-transition detector,
        // not a heartbeat). stdio callers have no receivers so send() is a no-op.
        if trend != StateTrend::Stable {
            let _ = self.tx.send(StateChange {
                record_count: count,
                s_t,
                h_t,
                trend,
            });
        }
    }

    /// Current record count (lock-free read).
    ///
    /// Used in tests and by the HTTP transport resource handler.
    #[allow(dead_code)]
    pub fn record_count(&self) -> u64 {
        self.record_count.load(Ordering::Relaxed)
    }
}

impl Default for SsnBroadcaster {
    fn default() -> Self {
        Self::new()
    }
}

// ── Trend classifier ──────────────────────────────────────────────────────────

/// Classify the current trend from the rolling window.
///
/// "Rising" means every consecutive step increases by at least `TREND_DELTA`.
/// Window must have at least 2 observations; otherwise returns `Stable`.
fn classify_trend(window: &[(f64, f64)]) -> StateTrend {
    if window.len() < 2 {
        return StateTrend::Stable;
    }

    let s_t_rising = window.windows(2).all(|w| w[1].0 - w[0].0 >= TREND_DELTA);
    let h_t_rising = window.windows(2).all(|w| w[1].1 - w[0].1 >= TREND_DELTA);

    match (s_t_rising, h_t_rising) {
        (true, true) => StateTrend::PhaseTransition,
        (true, false) => StateTrend::StructureDiscovery,
        (false, true) => StateTrend::EntropyIncrease,
        (false, false) => StateTrend::Stable,
    }
}

// ── Context summary ───────────────────────────────────────────────────────────

/// Returns the current causal context summary (~200 tokens).
/// Called by the MCP Resource handler for `aevum://context/current`.
///
/// Used by the HTTP transport and tested in the test suite.
#[allow(dead_code)]
pub fn current_context_summary(
    record_count: u64,
    s_t: f64,
    h_t: f64,
    trend: &StateTrend,
) -> String {
    let trend_str = match trend {
        StateTrend::StructureDiscovery => "StructureDiscovery",
        StateTrend::EntropyIncrease => "EntropyIncrease",
        StateTrend::PhaseTransition => "PhaseTransition",
        StateTrend::Stable => "Stable",
    };
    format!(
        "Current causal state: {record_count} records, S_T: {s_t:.4}, H_T: {h_t:.4}, trend: {trend_str}"
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── classify_trend ────────────────────────────────────────────────────────

    #[test]
    fn classify_empty_window_is_stable() {
        assert_eq!(classify_trend(&[]), StateTrend::Stable);
    }

    #[test]
    fn classify_single_observation_is_stable() {
        assert_eq!(classify_trend(&[(1.0, 1.0)]), StateTrend::Stable);
    }

    #[test]
    fn classify_both_rising_is_phase_transition() {
        let w = vec![(0.0, 0.0), (0.1, 0.1), (0.2, 0.2)];
        assert_eq!(classify_trend(&w), StateTrend::PhaseTransition);
    }

    #[test]
    fn classify_only_s_t_rising_is_structure_discovery() {
        let w = vec![(0.0, 1.0), (0.1, 1.0), (0.2, 1.0)];
        assert_eq!(classify_trend(&w), StateTrend::StructureDiscovery);
    }

    #[test]
    fn classify_only_h_t_rising_is_entropy_increase() {
        let w = vec![(1.0, 0.0), (1.0, 0.1), (1.0, 0.2)];
        assert_eq!(classify_trend(&w), StateTrend::EntropyIncrease);
    }

    #[test]
    fn classify_below_threshold_is_stable() {
        // Delta = 0.01 < TREND_DELTA (0.05) → Stable
        let w = vec![(0.0, 0.0), (0.01, 0.01), (0.02, 0.02)];
        assert_eq!(classify_trend(&w), StateTrend::Stable);
    }

    // ── SsnBroadcaster ────────────────────────────────────────────────────────

    #[tokio::test]
    async fn observer_increments_record_count() {
        let ssn = SsnBroadcaster::new();
        assert_eq!(ssn.record_count(), 0);
        ssn.observe(0.0, 0.0);
        assert_eq!(ssn.record_count(), 1);
        ssn.observe(0.0, 0.0);
        assert_eq!(ssn.record_count(), 2);
    }

    #[tokio::test]
    async fn observer_broadcasts_phase_transition() {
        let ssn = SsnBroadcaster::new();
        let mut rx = ssn.subscribe();

        // Three observations with delta > 0.05 on both axes.
        // After the second observe, window = [(0.0,0.0),(0.1,0.1)] → both rising → broadcast.
        ssn.observe(0.0, 0.0);
        ssn.observe(0.1, 0.1);
        ssn.observe(0.2, 0.2);

        // First broadcast fires at the second observe (window len=2 ≥ 2, both deltas=0.1≥0.05).
        let event = rx
            .try_recv()
            .expect("should have received a PhaseTransition event");
        assert_eq!(event.trend, StateTrend::PhaseTransition);
        // The first non-Stable broadcast is at observe(0.1,0.1) — s_t=0.1, h_t=0.1
        assert_eq!(event.s_t, 0.1);
        assert_eq!(event.h_t, 0.1);
    }

    #[tokio::test]
    async fn stable_observations_do_not_broadcast() {
        let ssn = SsnBroadcaster::new();
        let mut rx = ssn.subscribe();

        // Flat observations — no trend
        ssn.observe(1.0, 1.0);
        ssn.observe(1.0, 1.0);
        ssn.observe(1.0, 1.0);

        assert!(
            rx.try_recv().is_err(),
            "stable state must not trigger a broadcast"
        );
    }

    // ── current_context_summary ───────────────────────────────────────────────

    #[test]
    fn context_summary_contains_all_fields() {
        let s = current_context_summary(42, 3.14, 1.59, &StateTrend::StructureDiscovery);
        assert!(s.contains("42"), "must contain record count");
        assert!(s.contains("3.1400"), "must contain S_T");
        assert!(s.contains("1.5900"), "must contain H_T");
        assert!(s.contains("StructureDiscovery"), "must contain trend");
    }
}
