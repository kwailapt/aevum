//! Pillar: II. PACR field: Ω (Resource Triple).
//!
//! Physical axiom: three inescapable resource constraints couple energy (E),
//! time (T), and space (S) onto a **2-D constraint surface** — they cannot be
//! independently minimised (the Energy-Time-Space trilemma).
//!
//! This crate measures all three axes and returns a [`ResourceTriple`] with
//! **honest confidence intervals**.  Wide CI is acceptable; fabricated
//! precision is forbidden (RULES-ARCHITECTURE.md §2).
//!
//! # Axis measurement strategy
//!
//! | Axis   | Source                          | Precision          |
//! |--------|---------------------------------|--------------------|
//! | E      | Λ × efficiency\_factor          | wide CI (userspace)|
//! | T      | `std::time::Instant`            | ±1 µs jitter       |
//! | S      | platform probe (see below)      | varies by platform |
//!
//! ## Space (S) platform dispatch
//!
//! | Feature         | Platform  | Implementation      | Precision   |
//! |-----------------|-----------|---------------------|-------------|
//! | `genesis_node`  | macOS M1  | `apple_uma.rs`      | wide CI*    |
//! | `light_node`    | Linux     | `linux_perf.rs`     | ±1 page     |
//! | _(default)_     | any       | wide CI fallback    | wide CI     |
//!
//! *M1 precise RSS requires Mach `task_info()` (unsafe FFI); deferred to a
//! future `ets-probe-ffi` crate.  See `apple_uma.rs` for full rationale.
//!
//! ## Energy (E)
//!
//! Actual energy cannot be measured from userspace without privileged hardware
//! counters (Intel RAPL, Apple PMU).  We derive E conservatively:
//!
//! ```text
//! E.point = Λ.point × EFFICIENCY_POINT   (10⁴ × Landauer — modern CMOS)
//! E.lower = Λ.lower × EFFICIENCY_LOWER   (10³ × Landauer — best case)
//! E.upper = Λ.upper × EFFICIENCY_UPPER   (10⁶ × Landauer — legacy CMOS)
//! ```
//!
//! This guarantees **E.point ≥ Λ.point** by construction (PACR invariant).

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

#[cfg(feature = "genesis_node")]
mod apple_uma;

#[cfg(feature = "light_node")]
mod linux_perf;

#[cfg(feature = "genesis_node")]
pub mod thermal_monitor;

use pacr_types::{Estimate, LandauerCost, ResourceTriple};
use std::time::Instant;

// ── Efficiency model ──────────────────────────────────────────────────────────
// Typical ratio of actual energy to Landauer floor for modern CMOS:
//   Pentium 4-era:  ~10⁶ × Landauer
//   Modern server:  ~10³ × Landauer
//   Point estimate: 10⁴ × Landauer (geometric mean of the range)
//
// DESIGN CHOICE (configurable): these factors are not physics-mandated.
// They represent empirical knowledge about CMOS efficiency.  Future phases
// may replace them with direct RAPL / PMU measurements.

const EFFICIENCY_POINT: f64 = 1.0e4;
const EFFICIENCY_LOWER: f64 = 1.0e3;
const EFFICIENCY_UPPER: f64 = 1.0e6;

// ── Time uncertainty model ────────────────────────────────────────────────────
// `std::time::Instant` on Linux: clock_gettime(MONOTONIC) ≈ 1 ns resolution.
// We model ±1 µs uncertainty to account for OS jitter and context switching.
// DESIGN CHOICE (configurable): not physics-mandated.

const TIME_UNCERTAINTY_S: f64 = 1.0e-6; // ±1 µs

// ── EtsProbe ──────────────────────────────────────────────────────────────────

/// A timer that measures the Ω resource triple for a computation.
///
/// # Usage
///
/// ```
/// use ets_probe::EtsProbe;
/// use pacr_types::Estimate;
///
/// // Λ from landauer-probe (or any other source)
/// let lambda = Estimate::exact(2.871e-18); // 1000 bits at 300 K
///
/// let probe = EtsProbe::start();
/// let _ = (0u64..100_000).sum::<u64>();
/// let triple = probe.finish(&lambda);
///
/// assert!(triple.energy.point >= lambda.point);
/// assert!(triple.time.point   >= 0.0);
/// assert!(triple.space.point  >= 0.0);
/// ```
pub struct EtsProbe {
    start: Instant,
}

impl EtsProbe {
    /// Starts the probe immediately before the measured computation.
    #[must_use]
    pub fn start() -> Self {
        Self { start: Instant::now() }
    }

    /// Stops the probe and returns the [`ResourceTriple`] for this computation.
    ///
    /// # Arguments
    ///
    /// * `landauer` — the Λ estimate for this computation (from
    ///   `landauer-probe`).  E is derived from Λ to guarantee E ≥ Λ.
    ///
    /// # Complexity
    ///
    /// O(1).  One syscall for space on Linux (`/proc/self/statm`).
    #[must_use]
    pub fn finish(self, landauer: &LandauerCost) -> ResourceTriple {
        let elapsed_s = self.start.elapsed().as_secs_f64();
        ResourceTriple {
            energy: energy_from_landauer(landauer),
            time:   time_estimate(elapsed_s),
            space:  space_estimate(),
        }
    }
}

/// Measures a closure and returns its [`ResourceTriple`] alongside its output.
///
/// `landauer` must be pre-computed (e.g. via `landauer_probe::compute()`).
///
/// # Example
///
/// ```
/// use ets_probe::measure;
/// use pacr_types::Estimate;
///
/// let lambda = Estimate::exact(2.871e-18);
/// let (triple, sum) = measure(&lambda, || (0u64..1_000).sum::<u64>());
/// assert!(triple.energy.point >= lambda.point);
/// ```
pub fn measure<F, R>(landauer: &LandauerCost, f: F) -> (ResourceTriple, R)
where
    F: FnOnce() -> R,
{
    let probe  = EtsProbe::start();
    let output = f();
    let triple = probe.finish(landauer);
    (triple, output)
}

// ── Internal helpers ──────────────────────────────────────────────────────────

/// Derives the energy estimate from the Landauer cost.
///
/// Guarantees `energy.point ≥ landauer.point` by construction:
/// `EFFICIENCY_POINT = 1e4 ≥ 1`, so `energy.point = landauer.point × 1e4 ≥ landauer.point`.
#[must_use]
pub(crate) fn energy_from_landauer(landauer: &LandauerCost) -> Estimate<f64> {
    Estimate {
        point: landauer.point * EFFICIENCY_POINT,
        lower: landauer.lower * EFFICIENCY_LOWER,
        upper: landauer.upper * EFFICIENCY_UPPER,
    }
}

/// Wraps the wall-clock duration with ±1 µs uncertainty.
#[must_use]
pub(crate) fn time_estimate(elapsed_s: f64) -> Estimate<f64> {
    Estimate {
        point: elapsed_s,
        lower: (elapsed_s - TIME_UNCERTAINTY_S).max(0.0),
        upper: elapsed_s + TIME_UNCERTAINTY_S,
    }
}

/// Returns the space estimate via platform-specific dispatch.
///
/// Falls back to a wide CI `[0, 1e12]` when no precise measurement
/// is available.  This is honest — we know the process uses some memory
/// but cannot state how much without platform-specific probes.
#[must_use]
fn space_estimate() -> Estimate<f64> {
    let rss = sample_rss_bytes();
    rss.map_or_else(
        || wide_space_ci(),
        |bytes| {
            let page = 4_096.0_f64;
            Estimate {
                point: bytes,
                lower: (bytes - page).max(0.0),
                upper: bytes + page,
            }
        },
    )
}

/// Platform-specific RSS sampling.  Returns `None` when unavailable.
fn sample_rss_bytes() -> Option<f64> {
    // Each cfg block has an early return; unreachable code is dead-code
    // eliminated by the compiler for the active feature set.
    #[cfg(feature = "genesis_node")]
    {
        let v = apple_uma::sample_rss_bytes();
        if v.is_some() {
            return v;
        }
    }
    #[cfg(feature = "light_node")]
    {
        let v = linux_perf::sample_rss_bytes();
        if v.is_some() {
            return v;
        }
    }
    None
}

/// Honest wide CI for space when no measurement is available.
///
/// `point = 0.0` means "no measurement obtained", NOT "zero memory used".
/// `upper = 1.0e12` (1 TiB) is a conservative physical upper bound.
#[must_use]
fn wide_space_ci() -> Estimate<f64> {
    Estimate { point: 0.0, lower: 0.0, upper: 1.0e12 }
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use pacr_types::Estimate;

    fn test_lambda() -> LandauerCost {
        // 1 000 bits at 300 K: Λ ≈ 2.871e-18 J
        Estimate {
            point: 2.871e-18,
            lower: 2.774e-18,
            upper: 2.968e-18,
        }
    }

    // ── energy_from_landauer ──────────────────────────────────────────────────

    #[test]
    fn energy_point_exceeds_landauer_point() {
        let lambda = test_lambda();
        let energy = energy_from_landauer(&lambda);
        assert!(
            energy.point >= lambda.point,
            "E.point={} < Λ.point={}", energy.point, lambda.point
        );
    }

    #[test]
    fn energy_bounds_ordered() {
        let lambda = test_lambda();
        let e = energy_from_landauer(&lambda);
        assert!(e.lower <= e.point, "E.lower={} > E.point={}", e.lower, e.point);
        assert!(e.point <= e.upper, "E.point={} > E.upper={}", e.point, e.upper);
    }

    #[test]
    fn energy_lower_from_lower_lambda() {
        let lambda = test_lambda();
        let e = energy_from_landauer(&lambda);
        // lower = lambda.lower × EFFICIENCY_LOWER
        let expected_lower = lambda.lower * EFFICIENCY_LOWER;
        assert!((e.lower - expected_lower).abs() < 1e-40);
    }

    // ── time_estimate ─────────────────────────────────────────────────────────

    #[test]
    fn time_bounds_ordered() {
        let t = time_estimate(1.5e-3); // 1.5 ms
        assert!(t.lower <= t.point);
        assert!(t.point <= t.upper);
    }

    #[test]
    fn time_lower_not_negative() {
        // Elapsed ≈ 0 → lower would go negative without the .max(0.0) floor
        let t = time_estimate(0.0);
        assert!(t.lower >= 0.0);
    }

    // ── EtsProbe ──────────────────────────────────────────────────────────────

    #[test]
    fn probe_finish_energy_exceeds_landauer() {
        let lambda = test_lambda();
        let probe  = EtsProbe::start();
        let _      = (0u64..100_000).sum::<u64>();
        let triple = probe.finish(&lambda);
        assert!(
            triple.energy.point >= lambda.point,
            "E.point={} < Λ.point={}", triple.energy.point, lambda.point
        );
    }

    #[test]
    fn probe_finish_time_positive() {
        let lambda = test_lambda();
        let probe  = EtsProbe::start();
        let _      = (0u64..100_000).sum::<u64>();
        let triple = probe.finish(&lambda);
        assert!(triple.time.point >= 0.0);
        assert!(triple.time.lower >= 0.0);
    }

    #[test]
    fn probe_finish_space_non_negative() {
        let lambda = test_lambda();
        let probe  = EtsProbe::start();
        let triple = probe.finish(&lambda);
        assert!(triple.space.point >= 0.0);
        assert!(triple.space.lower >= 0.0);
    }

    #[test]
    fn probe_finish_passes_physics_check() {
        let lambda = test_lambda();
        let probe  = EtsProbe::start();
        let _      = (0u64..1_000).sum::<u64>();
        let triple = probe.finish(&lambda);
        let violations = triple.validate_physics();
        assert!(
            violations.is_empty(),
            "Unexpected physics violations: {violations:?}"
        );
    }

    // ── measure() ────────────────────────────────────────────────────────────

    #[test]
    fn measure_returns_correct_output() {
        let lambda    = test_lambda();
        let (_, sum)  = measure(&lambda, || (0u64..1_000).sum::<u64>());
        assert_eq!(sum, 499_500);
    }

    #[test]
    fn measure_triple_is_valid() {
        let lambda        = test_lambda();
        let (triple, _)   = measure(&lambda, || 42_u32);
        assert!(triple.energy.point >= lambda.point);
        assert!(triple.time.lower   >= 0.0);
        assert!(triple.space.lower  >= 0.0);
    }

    // ── wide_space_ci ─────────────────────────────────────────────────────────

    #[test]
    fn wide_ci_is_bounded_and_ordered() {
        let ci = wide_space_ci();
        assert!(ci.lower <= ci.point);
        assert!(ci.point <= ci.upper);
        assert!(ci.upper > 0.0);
    }
}

// ── Property-based tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod prop_tests {
    use super::*;
    use pacr_types::Estimate;
    use proptest::prelude::*;

    /// Generate a valid LandauerCost (lower ≤ point ≤ upper, all positive).
    fn arb_lambda() -> impl Strategy<Value = LandauerCost> {
        (1e-25_f64..1e-10_f64).prop_flat_map(|point| {
            let lower = point * 0.97; // −3 % (290 K / 300 K ratio ≈ 0.967)
            let upper = point * 1.03; // +3 %
            Just(Estimate { point, lower, upper })
        })
    }

    proptest! {
        /// E.point ≥ Λ.point for all valid Λ values.
        #[test]
        fn energy_always_exceeds_landauer(lambda in arb_lambda()) {
            let energy = energy_from_landauer(&lambda);
            prop_assert!(
                energy.point >= lambda.point,
                "E.point={} < Λ.point={}", energy.point, lambda.point
            );
        }

        /// E bounds are always ordered: lower ≤ point ≤ upper.
        #[test]
        fn energy_bounds_always_ordered(lambda in arb_lambda()) {
            let e = energy_from_landauer(&lambda);
            prop_assert!(e.lower <= e.point,
                "E.lower > E.point: {} > {}", e.lower, e.point);
            prop_assert!(e.point <= e.upper,
                "E.point > E.upper: {} > {}", e.point, e.upper);
        }

        /// time_estimate bounds are always ordered, lower ≥ 0.
        #[test]
        fn time_bounds_always_valid(elapsed_s in 0.0_f64..1_000.0_f64) {
            let t = time_estimate(elapsed_s);
            prop_assert!(t.lower >= 0.0,       "lower < 0: {}", t.lower);
            prop_assert!(t.lower <= t.point,   "lower > point");
            prop_assert!(t.point <= t.upper,   "point > upper");
        }

        /// ResourceTriple derived from valid Λ always passes physics check.
        #[test]
        fn derived_triple_always_passes_physics(
            lambda in arb_lambda(),
            elapsed_s in 1e-9_f64..1.0_f64,
        ) {
            let triple = ResourceTriple {
                energy: energy_from_landauer(&lambda),
                time:   time_estimate(elapsed_s),
                space:  wide_space_ci(),
            };
            let violations = triple.validate_physics();
            prop_assert!(
                violations.is_empty(),
                "physics violations: {violations:?}"
            );
        }

        /// E.point ≥ Λ.point holds for the full triple.
        #[test]
        fn triple_energy_exceeds_landauer(lambda in arb_lambda()) {
            let energy = energy_from_landauer(&lambda);
            prop_assert!(energy.point >= lambda.point);
        }
    }
}
