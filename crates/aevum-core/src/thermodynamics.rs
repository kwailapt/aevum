//! Thermodynamic constraints for Aevum Core.
//!
//! Three physical laws are enforced at the code level:
//!
//! 1. **Landauer's Principle** — every irreversible bit operation dissipates
//!    at minimum E_min = k_B × T × ln(2) ≈ 2.85×10⁻²¹ J at 300 K.
//!    Mapped to χ-Quanta: `LANDAUER_CHI = 1`. No operation may cost less.
//!
//! 2. **Second Law (NESS)** — the system maintains a Non-Equilibrium Steady
//!    State by ensuring entropy production σ = dS/dt > 0. If minting exceeds
//!    consumption the system drifts toward equilibrium and collapses.
//!
//! 3. **Energy–Time–Space Trilemma** — a node cannot simultaneously minimise
//!    all three. Declaring a `TrilemmaMode` shifts cost to the non-optimised axes.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ── Physical constants ────────────────────────────────────────────────────────

/// k_B × 300 K × ln(2)  (Joules per irreversible bit operation at room temp)
pub const LANDAUER_JOULES: f64 = 2.854e-21;

/// χ-Quanta floor per operation.  Costs below this violate the second law.
pub const LANDAUER_CHI: u64 = 1;

// ── NESS monitor ─────────────────────────────────────────────────────────────

/// Tracks global entropy production rate σ (χ / s).
///
/// σ = (deducted − minted) / Δt
///
/// * σ > 0 → `Dissipative`: system consumes more than it mints — NESS maintained.
/// * σ = 0 → `Equilibrium`: no net flow — system stagnant.
/// * σ < 0 → `Inflating`: minting exceeds consumption — unsustainable.
pub struct NessMonitor {
    minted:      AtomicU64,
    deducted:    AtomicU64,
    epoch_start: AtomicU64,   // epoch milliseconds
}

impl NessMonitor {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            minted:      AtomicU64::new(0),
            deducted:    AtomicU64::new(0),
            epoch_start: AtomicU64::new(now_ms()),
        })
    }

    #[inline]
    pub fn record_mint(&self, amount: u64) {
        self.minted.fetch_add(amount, Ordering::Relaxed);
    }

    #[inline]
    pub fn record_deduct(&self, amount: u64) {
        self.deducted.fetch_add(amount, Ordering::Relaxed);
    }

    /// Entropy production rate σ (χ / s).
    pub fn sigma(&self) -> f64 {
        let elapsed_s = now_ms()
            .saturating_sub(self.epoch_start.load(Ordering::Relaxed)) as f64
            / 1_000.0;
        if elapsed_s < 1e-9 { return 0.0; }
        let d = self.deducted.load(Ordering::Relaxed) as f64;
        let m = self.minted.load(Ordering::Relaxed) as f64;
        (d - m) / elapsed_s
    }

    pub fn state(&self) -> NessState {
        match self.sigma() {
            s if s > 0.0 => NessState::Dissipative,
            s if s < 0.0 => NessState::Inflating,
            _            => NessState::Equilibrium,
        }
    }

    /// Equivalent physical power dissipation via Landauer (Watts).
    pub fn power_watts(&self) -> f64 {
        self.sigma().max(0.0) * LANDAUER_JOULES
    }

    /// Snapshot current stats then reset counters for the next epoch.
    pub fn snapshot_and_reset(&self) -> NessSnapshot {
        let snap = NessSnapshot {
            sigma:    self.sigma(),
            state:    self.state(),
            power_w:  self.power_watts(),
            minted:   self.minted.load(Ordering::Relaxed),
            deducted: self.deducted.load(Ordering::Relaxed),
        };
        self.minted.store(0, Ordering::Relaxed);
        self.deducted.store(0, Ordering::Relaxed);
        self.epoch_start.store(now_ms(), Ordering::Relaxed);
        snap
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum NessState {
    Dissipative,
    Equilibrium,
    Inflating,
}

impl std::fmt::Display for NessState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Dissipative => write!(f, "DISSIPATIVE"),
            Self::Equilibrium => write!(f, "EQUILIBRIUM"),
            Self::Inflating   => write!(f, "INFLATING"),
        }
    }
}

pub struct NessSnapshot {
    pub sigma:    f64,
    pub state:    NessState,
    pub power_w:  f64,
    pub minted:   u64,
    pub deducted: u64,
}

// ── Energy–Time–Space Trilemma ────────────────────────────────────────────────

/// A node declares which axis it optimises.  The system enforces the
/// corresponding χ multiplier — the other two axes bear the cost.
///
/// Trilemma: minimising energy ↔ latency ↔ space are mutually exclusive.
/// Only one can be minimised at a time; the others must increase.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub enum TrilemmaMode {
    #[default]
    /// 1× base cost.  Standard routing, no axis optimised.
    Balanced,
    /// 1× χ  — minimum Landauer cost. Accepts higher latency (no priority).
    EnergyOptimal,
    /// 3× χ  — pays extra energy to buy latency (priority routing hint).
    TimeOptimal,
    /// 2× χ  — pays extra energy to reduce shard space overhead
    ///          (compact fold, higher collision tolerance).
    SpaceOptimal,
}

impl TrilemmaMode {
    /// χ multiplier enforced by the thermodynamic constraint.
    pub fn chi_multiplier(self) -> u64 {
        match self {
            Self::Balanced | Self::EnergyOptimal => 1,
            Self::SpaceOptimal                   => 2,
            Self::TimeOptimal                    => 3,
        }
    }

    /// Parse from the `X-Aevum-Mode` request header value.
    pub fn from_header(s: &str) -> Self {
        match s.to_ascii_lowercase().as_str() {
            "energy" => Self::EnergyOptimal,
            "time"   => Self::TimeOptimal,
            "space"  => Self::SpaceOptimal,
            _        => Self::Balanced,
        }
    }
}

// ── Internal ──────────────────────────────────────────────────────────────────

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
