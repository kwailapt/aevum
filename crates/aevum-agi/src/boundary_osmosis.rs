//! Pillar: II + I. PACR field: Λ, Ω.
//!
//! **Boundary Osmotic Pressure** — the ∂ (parasympathetic contraction) arm of
//! the ⟨Φ,∂⟩ dual engine.
//!
//! # Physical Axiom
//!
//! A biological cell maintains homeostasis via osmotic pressure: when internal
//! concentration rises above the environment, water flows out (contraction).
//! This module applies the analogue to the AGI boundary: when memory pressure
//! and/or inflow rate exceed metabolic capacity, the system contracts by
//! probabilistically rejecting incoming records.
//!
//! # Contraction Signal
//!
//! The contraction signal `σ ∈ [0, 1]` is a sigmoid function of a composite
//! pressure score `p`:
//!
//! ```text
//! mem_pressure  = mem_used / mem_ceiling          ∈ [0, 1]
//! flow_pressure = max(0, inflow_rate - metabolic_rate) / (metabolic_rate + 1)
//! composite     = 0.6 × mem_pressure + 0.4 × flow_pressure
//! σ             = 1 / (1 + exp(−k × (composite − θ)))
//! ```
//!
//! With `k = 35` and `θ = 0.3`, the signal exceeds 0.95 when
//! `mem_pressure = 0.9` and `flow_pressure = 0` (composite = 0.54 > θ).

#![forbid(unsafe_code)]

use std::sync::atomic::{AtomicU64, Ordering};

// Sigmoid steepness and threshold for the contraction signal.
const K: f64 = 35.0;
const THETA: f64 = 0.3;

/// Lock-free osmotic pressure valve.
///
/// All fields use `AtomicU64` (f64 bits stored via `f64::to_bits()`) so that
/// multiple threads may update state without locking (Pillar I).
pub struct BoundaryOsmoticPressure {
    /// Current bytes in use (updated externally via `update_mem_used`).
    mem_used: AtomicU64,
    /// Hard ceiling in bytes (e.g., 100 GiB = 100 * 1024^3).
    mem_ceiling: u64,
    /// Exponential moving average of records processed per second
    /// (metabolic rate). Stored as f64 bits in AtomicU64.
    pub(crate) metabolic_rate: AtomicU64,
    /// Exponential moving average of records arriving per second
    /// (inflow rate). Stored as f64 bits in AtomicU64.
    inflow_rate: AtomicU64,
}

impl BoundaryOsmoticPressure {
    /// Create a new valve.
    ///
    /// # Arguments
    ///
    /// * `mem_ceiling` — maximum memory in bytes before hard rejection (e.g., 100 GiB).
    #[must_use]
    pub fn new(mem_ceiling: u64) -> Self {
        Self {
            mem_used:       AtomicU64::new(0),               // plain bytes count
            mem_ceiling,
            metabolic_rate: AtomicU64::new(0_f64.to_bits()), // f64 bits
            inflow_rate:    AtomicU64::new(0_f64.to_bits()), // f64 bits
        }
    }

    /// Update the current memory usage. Called by the runtime on each tick.
    pub fn update_mem_used(&self, bytes: u64) {
        self.mem_used.store(bytes, Ordering::Relaxed);
    }

    /// Update the metabolic rate EMA with a new observation (records/sec).
    /// Uses α = 0.1 for the EMA.
    pub fn update_metabolic_rate(&self, rate: f64) {
        update_ema(&self.metabolic_rate, rate, 0.1);
    }

    /// Update the inflow rate EMA with a new observation (records/sec).
    /// Uses α = 0.1 for the EMA.
    pub fn update_inflow_rate(&self, rate: f64) {
        update_ema(&self.inflow_rate, rate, 0.1);
    }

    /// Compute the contraction signal σ ∈ [0, 1].
    ///
    /// Higher values → stronger contraction → more records rejected.
    /// σ > 0.95 when mem_pressure ≥ 0.9.
    #[must_use]
    pub fn contraction_signal(&self) -> f64 {
        let mem_used_bytes = self.mem_used.load(Ordering::Relaxed);
        // mem_used is stored directly as u64 bytes, not as f64 bits
        let mem_pressure = if self.mem_ceiling == 0 {
            1.0_f64
        } else {
            (mem_used_bytes as f64 / self.mem_ceiling as f64).min(1.0)
        };

        let metabolic = f64::from_bits(self.metabolic_rate.load(Ordering::Relaxed));
        let inflow    = f64::from_bits(self.inflow_rate.load(Ordering::Relaxed));

        let flow_pressure = if metabolic > 0.0 {
            ((inflow - metabolic) / (metabolic + 1.0)).max(0.0)
        } else {
            0.0
        };

        let composite = 0.6 * mem_pressure + 0.4 * flow_pressure;
        1.0 / (1.0 + (-K * (composite - THETA)).exp())
    }

    /// Probabilistic rejection gate.
    ///
    /// Returns `true` if the incoming record should be DROPPED.
    /// Uses a fast xorshift64 PRNG seeded from a thread-local state to
    /// decide proportional to `contraction_signal()`.
    ///
    /// O(1), no allocation.
    #[must_use]
    pub fn should_reject(&self) -> bool {
        let sigma = self.contraction_signal();
        PRNG.with(|cell| {
            let s = xorshift64(cell.get());
            cell.set(s);
            let r = (s as f64) / (u64::MAX as f64);
            r < sigma
        })
    }
}

// ── PRNG helpers ──────────────────────────────────────────────────────────────

thread_local! {
    static PRNG: std::cell::Cell<u64> = const { std::cell::Cell::new(0x9e37_79b9_7f4a_7c15) };
}

#[inline]
fn xorshift64(state: u64) -> u64 {
    let x = state ^ (state << 13);
    let x = x ^ (x >> 7);
    x ^ (x << 17)
}

// ── EMA helper ────────────────────────────────────────────────────────────────

fn update_ema(atom: &AtomicU64, new_obs: f64, alpha: f64) {
    loop {
        let old_bits = atom.load(Ordering::Relaxed);
        let old_val  = f64::from_bits(old_bits);
        let new_val  = alpha * new_obs + (1.0 - alpha) * old_val;
        let new_bits = new_val.to_bits();
        if atom
            .compare_exchange(old_bits, new_bits, Ordering::Relaxed, Ordering::Relaxed)
            .is_ok()
        {
            break;
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn contraction_signal_zero_when_no_pressure() {
        // mem_used=0, mem_ceiling=1GiB, no flows → signal near 0
        let v = BoundaryOsmoticPressure::new(1024 * 1024 * 1024);
        let s = v.contraction_signal();
        assert!(s < 0.1, "signal={s} should be near 0 with no pressure");
    }

    #[test]
    fn contraction_signal_exceeds_threshold_at_90pct_memory() {
        let ceiling = 1_000_000_000_u64; // 1 GB
        let v = BoundaryOsmoticPressure::new(ceiling);
        v.update_mem_used(900_000_000); // 90% used
        let s = v.contraction_signal();
        assert!(s > 0.95, "signal={s} should exceed 0.95 at 90% memory usage");
    }

    #[test]
    fn contraction_signal_increases_with_memory() {
        let ceiling = 1_000_000_000_u64;
        let v = BoundaryOsmoticPressure::new(ceiling);
        v.update_mem_used(100_000_000); // 10%
        let s10 = v.contraction_signal();
        v.update_mem_used(500_000_000); // 50%
        let s50 = v.contraction_signal();
        v.update_mem_used(900_000_000); // 90%
        let s90 = v.contraction_signal();
        assert!(s10 < s50, "signal should increase with memory pressure");
        assert!(s50 < s90, "signal should increase with memory pressure");
    }

    #[test]
    fn contraction_signal_flow_pressure_increases_signal() {
        let ceiling = 1_000_000_000_u64;
        let v = BoundaryOsmoticPressure::new(ceiling);
        v.update_mem_used(500_000_000); // 50%
        let s_no_flow = v.contraction_signal();
        v.update_inflow_rate(1000.0);
        v.update_metabolic_rate(10.0); // inflow >> metabolic
        let s_high_flow = v.contraction_signal();
        assert!(s_high_flow > s_no_flow, "high inflow should increase signal");
    }

    #[test]
    fn should_reject_never_triggers_at_zero_pressure() {
        let v = BoundaryOsmoticPressure::new(1_000_000_000);
        // With near-zero signal, should_reject should almost never fire
        let rejections = (0..1000).filter(|_| v.should_reject()).count();
        assert!(rejections < 100, "too many rejections at zero pressure: {rejections}");
    }

    #[test]
    fn ema_updates_converge() {
        let v = BoundaryOsmoticPressure::new(1_000_000_000);
        // Push metabolic rate toward 100.0 with many updates
        for _ in 0..50 {
            v.update_metabolic_rate(100.0);
        }
        let met = f64::from_bits(v.metabolic_rate.load(std::sync::atomic::Ordering::Relaxed));
        assert!(met > 80.0, "EMA should converge toward 100.0, got {met}");
    }
}
