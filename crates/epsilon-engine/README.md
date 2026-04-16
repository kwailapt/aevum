# epsilon-engine

**CSSR ε-machine: statistical complexity S_T and entropy rate H_T from arbitrary data streams.**

Part of the [Aevum](https://github.com/kwailapt/aevum) physics kernel.

[![Crates.io](https://img.shields.io/crates/v/epsilon-engine)](https://crates.io/crates/epsilon-engine)
[![docs.rs](https://img.shields.io/docsrs/epsilon-engine)](https://docs.rs/epsilon-engine)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](../../LICENSE)

## What It Is

An implementation of **Causal State Splitting Reconstruction (CSSR)** — the algorithm that infers a minimal ε-machine from a data stream and computes:

- **S_T** (statistical complexity, C_μ) — the amount of causal structure in the data
- **H_T** (entropy rate, h_μ) — residual unpredictability given the causal states

**S_T ≠ Shannon entropy H(X).** Shannon entropy measures static symbol distributions. S_T measures the minimal memory required to predict future symbols — a fundamentally different quantity.

```
S_T = 0 → pure noise (no structure)
S_T → ∞ → maximal causal structure
H_T = 0 → perfectly predictable given causal states
H_T → log(A) → maximally random
```

## The `aevum_filter` Use Case

Aevum uses `epsilon-engine` to filter AI agent responses: chunks with S_T below a threshold are dropped (repetitive/padded content), chunks above are kept (causal structure). Real benchmark results:

| Input | Compression | Notes |
|-------|-------------|-------|
| Pure repetition | 100% | Correctly: zero causal structure |
| Padded LLM response | 36–68% | Pleasantries dropped, insight kept |
| Dense technical text | 0% | Correctly: every sentence carries structure |

## Usage

```rust
use epsilon_engine::{Cssr, TextSymbolizer, Symbolizer};

// Symbolize raw text into a discrete alphabet (4-gram frequency binning)
let symbols = TextSymbolizer::default().symbolize("your text here");

// Infer ε-machine (depth=3)
let machine = Cssr::new(3).infer(&symbols);

println!("S_T = {:.4}", machine.statistical_complexity());
println!("H_T = {:.4}", machine.entropy_rate());
```

## Limitations

The `TextSymbolizer` uses 4-gram character frequencies. This measures **byte-level repetition**, not **semantic redundancy**. Navigation HTML ("Home About Blog Contact") has high character entropy and is not filtered. Future versions may add word-level or token-level symbolization.

## Algorithm Reference

Cosma Rohilla Shalizi and James P. Crutchfield, "Computational Mechanics: Pattern and Prediction, Structure and Simplicity," *Journal of Statistical Physics* 104 (2001): 817–879.

## License

Apache-2.0 — see [LICENSE](../../LICENSE).
