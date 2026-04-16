# landauer-allocator

**Landauer-on-Drop global allocator — counts bit erasures on every `dealloc`.**

Part of the [Aevum](https://github.com/kwailapt/aevum) physics kernel.

[![Crates.io](https://img.shields.io/crates/v/landauer-allocator)](https://crates.io/crates/landauer-allocator)
[![docs.rs](https://img.shields.io/docsrs/landauer-allocator)](https://docs.rs/landauer-allocator)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](../../LICENSE)

## What It Is

A Rust [global allocator](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html) that intercepts every `dealloc` call and counts the bits erased, then exposes the cumulative total via a lock-free atomic counter.

From this count you can compute the **Landauer dissipation cost** — the minimum energy required to erase those bits, grounded in the second law of thermodynamics:

```
Λ = bits_erased × k_B × T × ln(2)
```

where `k_B = 1.380649 × 10⁻²³ J/K` (SI 2019 exact) and `T` is temperature in Kelvin.

## Why Intercept `dealloc`?

In Rust, when a variable's lifetime ends the `Drop` trait fires and heap memory is returned to the allocator. This deallocation **is physically the moment when bits are irreversibly erased** — the exact event that Landauer's principle taxes.

By wrapping every `dealloc`, the allocator counts bit erasures **automatically and continuously**. No application code needs to opt in. No code path can bypass Λ accounting, because no code path bypasses `Drop`.

This answers the question: *"How far is my program from the Landauer limit?"*

## Usage

```rust
use landauer_allocator::LandauerAllocator;

#[global_allocator]
static A: LandauerAllocator = LandauerAllocator;

fn main() {
    let before = landauer_allocator::bits_erased();

    let v: Vec<u8> = (0..1024).collect();
    drop(v);

    let after = landauer_allocator::bits_erased();
    let delta = after - before;

    let cost_joules = landauer_allocator::landauer_cost_joules(delta, 300.0);
    println!("bits erased: {delta}");
    println!("Λ = {cost_joules:.3e} joules  (at 300 K)");
}
```

## API

| Function | Description |
|----------|-------------|
| `bits_erased() → u64` | Cumulative bits erased since process start. O(1), lock-free. Monotonically non-decreasing. |
| `landauer_cost_joules(bits, temp_k) → f64` | Λ = bits × k_B × T × ln(2). Returns cost in joules. |

## Safety Contract

The crate uses `#![deny(unsafe_code)]` at the crate level. The single `#[allow(unsafe_code)]` block is isolated in an inner module and wraps exactly:

1. One delegation to `System.alloc(layout)`
2. One delegation to `System.dealloc(ptr, layout)` — preceded by one `AtomicU64::fetch_add`

There is no pointer arithmetic, no raw memory reads, no lifetime violations. Each unsafe block carries a justification comment.

## Physics Constant

```rust
const K_B: f64 = 1.380_649e-23;  // Boltzmann constant (SI 2019 exact)

// Λ per bit at 300 K:  k_B × 300 × ln(2) ≈ 2.87 × 10⁻²¹ joules
```

## License

Apache-2.0 — see [LICENSE](../../LICENSE).
