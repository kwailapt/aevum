//! Pillar: II. PACR field: Ω (thermodynamic back-pressure).
//!
//! Apple M1 Ultra thermal monitor — genesis_node only.
//!
//! Reads the System Management Controller (SMC) temperature and emits a
//! [`ThermalSignal`] that the `aevum-core` runtime consumes to implement
//! thermodynamic back-pressure: when the die approaches its thermal limit the
//! runtime should throttle new PACR record generation, reducing Landauer waste.
//!
//! # Safety note
//!
//! True SMC access requires the `IOKit` framework via unsafe FFI.  This
//! implementation uses a **simulated** read (returning a configurable fixed
//! temperature) so that the crate remains `#![forbid(unsafe_code)]`.  A future
//! `ets-probe-ffi` crate will provide the real SMC binding; the interface
//! (`ThermalSignal`, `ThermalMonitor`) is intentionally identical so the
//! swap is a one-line dependency change.
//!
//! # Throttle threshold
//!
//! 85 °C — leaves a 15 °C margin before the M1 Ultra's documented throttle
//! onset (~100 °C) and provides a safe operating zone under sustained load.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::unreadable_literal,
    clippy::redundant_closure,
    clippy::unwrap_or_default,
    clippy::doc_overindented_list_items,
    clippy::cloned_instead_of_copied,
    clippy::needless_pass_by_value,
    clippy::cast_lossless,
    clippy::module_name_repetitions,
    clippy::into_iter_without_iter,
    clippy::unnested_or_patterns,
    clippy::let_underscore_untyped,
    clippy::manual_let_else,
    clippy::suspicious_open_options,
    clippy::iter_not_returning_iterator,
    clippy::must_use_candidate,
    clippy::ptr_arg,
    clippy::manual_midpoint,
    clippy::map_unwrap_or,
    clippy::bool_to_int_with_if,
    clippy::missing_panics_doc
)]

/// Die temperature above which the runtime should throttle (°C).
pub const THROTTLE_THRESHOLD_C: f64 = 85.0;

// ── ThermalSignal ─────────────────────────────────────────────────────────────

/// The thermal state reported by a single SMC read.
#[derive(Debug, Clone, PartialEq)]
pub enum ThermalSignal {
    /// Die temperature is below the throttle threshold — normal operation.
    Normal {
        /// Measured (or simulated) die temperature in °C.
        temperature_c: f64,
    },
    /// Die temperature is at or above [`THROTTLE_THRESHOLD_C`].
    ///
    /// The runtime MUST reduce the PACR record generation rate until the next
    /// poll returns [`Normal`](ThermalSignal::Normal).
    Throttle {
        /// Measured (or simulated) die temperature in °C.
        temperature_c: f64,
    },
}

impl ThermalSignal {
    /// Returns `true` when this signal indicates throttling is required.
    #[must_use]
    pub fn should_throttle(&self) -> bool {
        matches!(self, Self::Throttle { .. })
    }

    /// Temperature in °C regardless of variant.
    #[must_use]
    pub fn temperature_c(&self) -> f64 {
        match *self {
            Self::Normal { temperature_c } | Self::Throttle { temperature_c } => temperature_c,
        }
    }
}

// ── ThermalMonitor ────────────────────────────────────────────────────────────

/// Polls the SMC (simulated) and classifies the thermal state.
///
/// Construct with [`ThermalMonitor::new`] (uses [`THROTTLE_THRESHOLD_C`]) or
/// [`ThermalMonitor::with_threshold`] for tests.
#[derive(Debug, Clone)]
pub struct ThermalMonitor {
    threshold_c: f64,
    /// Simulated temperature injected in tests (None → use hardware read).
    simulated_temperature_c: Option<f64>,
}

impl ThermalMonitor {
    /// Create a monitor using the default 85 °C throttle threshold.
    #[must_use]
    pub fn new() -> Self {
        Self {
            threshold_c: THROTTLE_THRESHOLD_C,
            simulated_temperature_c: None,
        }
    }

    /// Create a monitor with a custom threshold (useful in unit tests).
    #[must_use]
    pub fn with_threshold(threshold_c: f64) -> Self {
        Self {
            threshold_c,
            simulated_temperature_c: None,
        }
    }

    /// Inject a fixed temperature for deterministic testing.
    #[must_use]
    pub fn with_simulated_temperature(mut self, temperature_c: f64) -> Self {
        self.simulated_temperature_c = Some(temperature_c);
        self
    }

    /// Read the current thermal state.
    ///
    /// Returns [`ThermalSignal::Normal`] or [`ThermalSignal::Throttle`]
    /// depending on whether the measured temperature exceeds `threshold_c`.
    ///
    /// # Implementation note
    ///
    /// The real SMC read is not yet implemented (requires unsafe FFI).  This
    /// method returns the simulated temperature if one was injected via
    /// [`with_simulated_temperature`](Self::with_simulated_temperature);
    /// otherwise it returns a safe default of 45 °C (typical idle M1 Ultra).
    #[must_use]
    pub fn read(&self) -> ThermalSignal {
        let temperature_c = self.simulated_temperature_c.unwrap_or(45.0);
        classify(temperature_c, self.threshold_c)
    }
}

impl Default for ThermalMonitor {
    fn default() -> Self {
        Self::new()
    }
}

// ── Internal ──────────────────────────────────────────────────────────────────

/// Classify `temperature_c` against `threshold_c`.
#[must_use]
fn classify(temperature_c: f64, threshold_c: f64) -> ThermalSignal {
    if temperature_c >= threshold_c {
        ThermalSignal::Throttle { temperature_c }
    } else {
        ThermalSignal::Normal { temperature_c }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn below_threshold_is_normal() {
        let m = ThermalMonitor::new().with_simulated_temperature(60.0);
        let sig = m.read();
        assert!(!sig.should_throttle());
        assert!((sig.temperature_c() - 60.0).abs() < 1e-10);
    }

    #[test]
    fn at_threshold_is_throttle() {
        let m = ThermalMonitor::new().with_simulated_temperature(THROTTLE_THRESHOLD_C);
        assert!(m.read().should_throttle());
    }

    #[test]
    fn above_threshold_is_throttle() {
        let m = ThermalMonitor::new().with_simulated_temperature(95.0);
        let sig = m.read();
        assert!(sig.should_throttle());
        assert!((sig.temperature_c() - 95.0).abs() < 1e-10);
    }

    #[test]
    fn default_idle_temperature_is_normal() {
        // Default simulated temp is 45 °C — well below 85 °C threshold.
        let m = ThermalMonitor::new();
        assert!(!m.read().should_throttle());
    }

    #[test]
    fn custom_threshold_respected() {
        let m = ThermalMonitor::with_threshold(50.0).with_simulated_temperature(55.0);
        assert!(m.read().should_throttle());

        let m2 = ThermalMonitor::with_threshold(60.0).with_simulated_temperature(55.0);
        assert!(!m2.read().should_throttle());
    }

    #[test]
    fn temperature_accessor_consistent_on_throttle() {
        let sig = ThermalSignal::Throttle {
            temperature_c: 90.0,
        };
        assert!((sig.temperature_c() - 90.0).abs() < 1e-10);
        assert!(sig.should_throttle());
    }

    #[test]
    fn temperature_accessor_consistent_on_normal() {
        let sig = ThermalSignal::Normal {
            temperature_c: 40.0,
        };
        assert!((sig.temperature_c() - 40.0).abs() < 1e-10);
        assert!(!sig.should_throttle());
    }
}
