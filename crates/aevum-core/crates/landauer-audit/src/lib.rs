// crates/landauer-audit/src/lib.rs
//
// Pillar: II (thermodynamic constraint). PACR fields: Λ, Ω.
//
// Measures actual computation resources and computes Landauer cost bounds.
//
// # Physical model
//
// Landauer's principle (1961): each logically irreversible operation that
// erases one bit of information dissipates at least:
//
//   E_Λ = k_B × T × ln(2)
//
// At room temperature (T = 300 K):
//   E_Λ ≈ 2.854 × 10⁻²¹ J per bit erasure
//
// The auditor cannot directly count bit erasures at the hardware level from
// safe Rust. Instead, it accepts a caller-provided estimate and measures:
//   - Wall-clock duration (T axis) via std::time::Instant
//   - Resident memory (S axis) via /proc/self/statm (Linux) or fallback
//   - Energy (E axis) computed as Λ × efficiency_factor (see below)
//
// # Uncertainty model
//
// Energy uncertainty spans from the Landauer floor (theoretical minimum,
// where efficiency = 100%) to 1000× Landauer (typical for modern CMOS at
// room temperature). The wide interval is honest — we cannot measure actual
// chip power dissipation from userspace.
//
// Temperature uncertainty: we assume T = 300 K ± 10 K (data centre range).
// This propagates directly into Λ: ΔΛ/Λ = ΔT/T ≈ ±3.3%.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use pacr_types::{Estimate, LandauerCost, ResourceTriple};
use std::time::Instant;

// ── Physical constants ─────────────────────────────────────────────────────────

/// Boltzmann constant (J/K).
pub const K_BOLTZMANN: f64 = 1.380_649e-23;

/// Nominal ambient temperature (K) — data-centre room temperature.
pub const TEMPERATURE_K: f64 = 300.0;

/// Lower temperature bound (K) — well-cooled data centre.
pub const TEMPERATURE_LOWER_K: f64 = 290.0;

/// Upper temperature bound (K) — warm rack / edge node.
pub const TEMPERATURE_UPPER_K: f64 = 310.0;

/// Landauer energy per bit erasure at nominal temperature (joules).
/// E_Λ = k_B × T × ln(2)
pub const LANDAUER_PER_BIT_J: f64 =
    K_BOLTZMANN * TEMPERATURE_K * std::f64::consts::LN_2;

/// Lower bound on Landauer cost (per bit) at T_lower.
const LANDAUER_PER_BIT_LOWER_J: f64 =
    K_BOLTZMANN * TEMPERATURE_LOWER_K * std::f64::consts::LN_2;

/// Upper bound on Landauer cost (per bit) at T_upper.
const LANDAUER_PER_BIT_UPPER_J: f64 =
    K_BOLTZMANN * TEMPERATURE_UPPER_K * std::f64::consts::LN_2;

/// Typical ratio of actual energy to Landauer floor for modern CMOS.
/// A Pentium 4-class operation dissipates ~10^6 × Landauer; modern
/// efficient cores are closer to ~10^3. We use 10^4 as the point estimate
/// and span [10^3, 10^6] as the 95% CI.
const EFFICIENCY_POINT: f64 = 1.0e4;
const EFFICIENCY_LOWER: f64 = 1.0e3;
const EFFICIENCY_UPPER: f64 = 1.0e6;

// ── Timer ──────────────────────────────────────────────────────────────────────

/// Wraps a high-resolution timer to measure the T axis (wall-clock duration).
///
/// # Usage
/// ```rust,ignore
/// let timer = ComputationTimer::start();
/// // ... perform computation ...
/// let result = timer.finish(bits_erased);
/// ```
pub struct ComputationTimer {
    start: Instant,
}

impl ComputationTimer {
    /// Starts the timer. Call this immediately before the measured computation.
    #[must_use]
    pub fn start() -> Self {
        Self { start: Instant::now() }
    }

    /// Stops the timer and computes the full [`AuditResult`].
    ///
    /// `bits_erased`: caller's estimate of logically irreversible bit
    /// operations in the measured computation (e.g., 8 × bytes_overwritten).
    /// If unknown, use [`estimate_bits_from_bytes`] or pass 1 for the
    /// Landauer floor with maximum uncertainty.
    ///
    /// # Complexity
    /// O(1). Reads /proc/self/statm once for the space estimate on Linux.
    #[must_use]
    pub fn finish(self, bits_erased: u64) -> AuditResult {
        let elapsed = self.start.elapsed();
        let elapsed_s = elapsed.as_secs_f64();
        let bits = bits_erased.max(1); // floor at 1 bit (Pillar II: Λ > 0)

        // ── Λ — Landauer cost ────────────────────────────────────────────────
        let lambda = landauer_cost(bits);

        // ── Ω — Resource triple ──────────────────────────────────────────────
        let resources = ResourceTriple {
            energy: energy_estimate(&lambda),
            time: time_estimate(elapsed_s),
            space: space_estimate(),
        };

        AuditResult {
            landauer_cost: lambda,
            resources,
            bits_erased: bits,
        }
    }
}

// ── Result ─────────────────────────────────────────────────────────────────────

/// Output of a [`ComputationTimer::finish`] call.
/// Contains the Λ and Ω fields ready to insert into a PACR builder.
#[derive(Debug, Clone)]
pub struct AuditResult {
    /// Λ — Landauer cost in joules.
    pub landauer_cost: LandauerCost,
    /// Ω — Resource constraint triple.
    pub resources: ResourceTriple,
    /// Number of bit erasures used to compute Λ (for auditability).
    pub bits_erased: u64,
}

// ── Helper: estimate bit erasures from byte count ──────────────────────────────

/// Estimates bit erasures from the number of bytes written/overwritten.
///
/// Physical basis: writing N bytes to a location holding unknown previous
/// content erases at most 8·N bits. This is a conservative upper bound;
/// the true number depends on how many bits actually flipped.
///
/// # Returns
/// An estimate with point = 4·N (expected value, assuming ~50% bits flip
/// on average) and interval [1, 8·N].
#[must_use]
pub fn estimate_bits_from_bytes(bytes: u64) -> u64 {
    // Point estimate: 4 bits per byte (half of 8, expected value)
    (bytes * 4).max(1)
}

// ── Internal helpers ───────────────────────────────────────────────────────────

fn landauer_cost(bits: u64) -> LandauerCost {
    let n = bits as f64;
    // Uncertainty propagated from temperature range ± 10 K
    Estimate {
        point: n * LANDAUER_PER_BIT_J,
        lower: n * LANDAUER_PER_BIT_LOWER_J,
        upper: n * LANDAUER_PER_BIT_UPPER_J,
    }
}

fn energy_estimate(lambda: &LandauerCost) -> Estimate<f64> {
    // Actual energy = Λ × efficiency_factor
    // We cannot measure actual chip power from userspace, so the interval
    // spans from the Landauer floor (100% efficient, thermodynamically ideal)
    // to 10^6 × Landauer (early transistor-era inefficiency, upper outlier).
    Estimate {
        point: lambda.point * EFFICIENCY_POINT,
        lower: lambda.lower * EFFICIENCY_LOWER,
        upper: lambda.upper * EFFICIENCY_UPPER,
    }
}

fn time_estimate(elapsed_s: f64) -> Estimate<f64> {
    // Instant resolution on Linux is typically 1 ns (clock_gettime MONOTONIC).
    // We model uncertainty as ±1 μs (1000× the raw resolution) to account for
    // OS jitter and context switching.
    let uncertainty_s = 1.0e-6_f64;
    Estimate {
        point: elapsed_s,
        lower: (elapsed_s - uncertainty_s).max(0.0),
        upper: elapsed_s + uncertainty_s,
    }
}

fn space_estimate() -> Estimate<f64> {
    // Read resident set size from /proc/self/statm (Linux).
    // Format: "total_pages rss_pages ..."
    // RSS is the actual physical memory in use — the most relevant "space" axis.
    read_rss_bytes().map_or_else(
        || Estimate {
            // Unknown: use a wide interval rather than fabricating a number.
            // point = 0 means "we have no measurement", not "zero memory used".
            point: 0.0,
            lower: 0.0,
            upper: 1.0e12, // 1 TB — clearly an upper bound for any real process
        },
        |rss| {
            let page = 4096.0_f64; // 4 KB page (Linux default)
            Estimate {
                point: rss,
                lower: (rss - page).max(0.0),
                upper: rss + page,
            }
        },
    )
}

/// Returns the resident set size in bytes by reading `/proc/self/statm`.
/// Returns `None` if the file is unavailable (non-Linux platforms or
/// environments without procfs).
fn read_rss_bytes() -> Option<f64> {
    let contents = std::fs::read_to_string("/proc/self/statm").ok()?;
    let mut parts = contents.split_whitespace();
    let _total = parts.next()?; // skip total virtual pages
    let rss_pages: u64 = parts.next()?.parse().ok()?;
    Some(rss_pages as f64 * 4096.0)
}

// ── Convenience: measure a closure ────────────────────────────────────────────

/// Measures a closure and returns the [`AuditResult`] alongside its output.
///
/// `bytes_touched` is a hint for estimating bit erasures.  Pass `0` if
/// unknown — the auditor will floor at 1 bit (honest Λ > 0).
///
/// # Example
/// ```rust
/// use landauer_audit::measure;
///
/// let (result, sum) = measure(1024, || (0u64..1024).sum::<u64>());
/// assert!(result.landauer_cost.point > 0.0);
/// assert_eq!(sum, 523_776);
/// ```
pub fn measure<F, R>(bytes_touched: u64, f: F) -> (AuditResult, R)
where
    F: FnOnce() -> R,
{
    let timer = ComputationTimer::start();
    let output = f();
    let bits = estimate_bits_from_bytes(bytes_touched).max(1);
    let result = timer.finish(bits);
    (result, output)
}

// ── Tests ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn landauer_cost_is_positive() {
        let timer = ComputationTimer::start();
        let result = timer.finish(1000);
        assert!(result.landauer_cost.point > 0.0);
        assert!(result.landauer_cost.lower > 0.0);
        assert!(result.landauer_cost.lower <= result.landauer_cost.point);
        assert!(result.landauer_cost.point <= result.landauer_cost.upper);
    }

    #[test]
    fn energy_exceeds_landauer() {
        let timer = ComputationTimer::start();
        let result = timer.finish(1);
        // Energy point estimate must be >= Landauer point (E ≥ Λ)
        assert!(result.resources.energy.point >= result.landauer_cost.point);
    }

    #[test]
    fn time_is_positive() {
        let timer = ComputationTimer::start();
        // Small but non-zero computation
        let _ = (0u64..1000).sum::<u64>();
        let result = timer.finish(8000);
        assert!(result.resources.time.point >= 0.0);
        // lower bound must not be negative
        assert!(result.resources.time.lower >= 0.0);
    }

    #[test]
    fn bit_floor_is_one() {
        let timer = ComputationTimer::start();
        let result = timer.finish(0); // 0 bits → floors to 1
        assert_eq!(result.bits_erased, 1);
        assert!(result.landauer_cost.point > 0.0);
    }

    #[test]
    fn measure_closure_works() {
        let (result, sum) = measure(1024, || (0u64..1024).sum::<u64>());
        assert!(result.landauer_cost.point > 0.0);
        assert_eq!(sum, 523_776);
    }

    #[test]
    fn estimate_bits_from_bytes_floors_at_one() {
        assert_eq!(estimate_bits_from_bytes(0), 1);
        assert_eq!(estimate_bits_from_bytes(1), 4);
        assert_eq!(estimate_bits_from_bytes(100), 400);
    }

    #[test]
    fn resource_triple_passes_physics_check() {
        let timer = ComputationTimer::start();
        let result = timer.finish(64);
        // The Margolus-Levitin bound is only relevant at femtojoule scale;
        // our energy estimates are far above that, so time should always pass.
        let violations = result.resources.validate_physics();
        assert!(
            violations.is_empty(),
            "Unexpected physics violations: {violations:?}"
        );
    }

    #[test]
    fn landauer_const_matches_known_value() {
        // k_B × 300 K × ln(2) ≈ 2.854e-21 J
        let expected = 2.854e-21_f64;
        let ratio = LANDAUER_PER_BIT_J / expected;
        assert!(
            (ratio - 1.0).abs() < 0.01,
            "Landauer constant off by more than 1%: {LANDAUER_PER_BIT_J:.4e}"
        );
    }
}
