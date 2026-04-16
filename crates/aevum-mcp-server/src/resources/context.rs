// crates/aevum-mcp-server/src/resources/context.rs
//
// Pillar: I/II/III. PACR field: ALL.
// aevum_context: MCP Resource exposing current causal state summary.
//
// HTTP mode: SSE endpoint /events pushes StateChange notifications when
//   S_T trend shifts (3 consecutive records with H_T rising > threshold).
// stdio mode: static resource only (MCP stdio does not support server-initiated messages).
//
// Week 2 stub: types are defined but broadcast channel integration is not yet wired.
// The #[allow(dead_code)] attributes are intentional — these will be activated in
// transport/http.rs when the SSE endpoint is implemented.

#![forbid(unsafe_code)]

/// A causal state change event broadcast to connected clients.
#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct StateChange {
    pub record_count: u64,
    pub s_t: f64,
    pub h_t: f64,
    pub trend: StateTrend,
}

#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq)]
pub enum StateTrend {
    StructureDiscovery, // S_T rising, H_T stable
    EntropyIncrease,    // H_T rising, S_T stable — investigate
    PhaseTransition,    // both rising — new regime
    Stable,
}

/// Returns the current causal context summary as a JSON string (~200 tokens).
/// Called by the MCP Resource handler for `aevum://context/current`.
#[allow(dead_code)]
pub fn current_context_summary(record_count: u64, s_t: f64, h_t: f64, trend: &StateTrend) -> String {
    let trend_str = match trend {
        StateTrend::StructureDiscovery => "StructureDiscovery",
        StateTrend::EntropyIncrease    => "EntropyIncrease",
        StateTrend::PhaseTransition    => "PhaseTransition",
        StateTrend::Stable             => "Stable",
    };
    format!(
        "Current causal state: {record_count} records, S_T: {s_t:.4}, H_T: {h_t:.4}, trend: {trend_str}"
    )
}

// TODO(week-2): add tokio::sync::broadcast channel + SSE endpoint integration
