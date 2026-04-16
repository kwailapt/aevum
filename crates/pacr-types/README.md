# pacr-types

**The PACR 6-tuple — physically annotated causal records for AI agents.**

Part of the [Aevum](https://github.com/kwailapt/aevum) physics kernel.

[![Crates.io](https://img.shields.io/crates/v/pacr-types)](https://crates.io/crates/pacr-types)
[![docs.rs](https://img.shields.io/docsrs/pacr-types)](https://docs.rs/pacr-types)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](../../LICENSE)

## What It Is

`pacr-types` defines the **PACR 6-tuple** — the immutable schema that every Aevum record must satisfy:

```
R = (ι, Π, Λ, Ω, Γ, P)
```

| Symbol | Name | Type | Physical Origin |
|--------|------|------|----------------|
| ι | Causal Identity | `CausalId` (128-bit ULID) | Logical identity |
| Π | Predecessor Set | `SmallVec<[CausalId; 4]>` | Special relativity causal order |
| Λ | Landauer Cost | `Estimate<f64>` (joules) | Landauer's principle |
| Ω | Resource Triple | `ResourceTriple` (E, T, S) | Conservation + Margolus-Levitin |
| Γ | Cognitive Split | `CognitiveSplit` (S_T, H_T) | CSSR ε-machine |
| P | Opaque Payload | `bytes::Bytes` | Completeness axiom |

## Key Properties

- **Zero dependencies on non-std crates** except `serde`, `smallvec`, `bytes`, `thiserror`
- **`#![forbid(unsafe_code)]`** — trust root; zero tolerance
- **`Estimate<T>`** wraps every physical measurement with `{ point, lower, upper }` — uncertainty at the protocol level
- **`Ω.energy ≥ Λ`** always enforced — actual cost cannot be less than Landauer floor
- **No self-reference** in Π — a record cannot be its own causal predecessor

## Usage

```rust
use pacr_types::{PacrRecord, PacrBuilder, Estimate, ResourceTriple, CognitiveSplit};
use bytes::Bytes;

let record = PacrBuilder::new()
    .landauer(Estimate::exact(2.854e-21))
    .resources(ResourceTriple {
        energy: Estimate::exact(1e-18),
        time:   Estimate::exact(1e-9),
        space:  Estimate::exact(512.0),
    })
    .cognitive(CognitiveSplit {
        statistical_complexity: Estimate::exact(3.2),
        entropy_rate:           Estimate::exact(0.8),
    })
    .payload(Bytes::from("hello causal world"))
    .build()?;

assert!(record.validate().is_ok());
```

## Invariants

1. `Estimate<T>`: `lower ≤ point ≤ upper` always. `Estimate::new()` is fallible; `Estimate::exact()` sets all three to the same value.
2. `Ω.energy ≥ Λ` — actual energy cost ≥ Landauer floor (validated by `PacrRecord::validate()`).
3. Schema is **append-only** — existing fields never change semantics.

## License

Apache-2.0 — see [LICENSE](../../LICENSE).
