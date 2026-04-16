# Contributing to Aevum

Thank you for your interest in Aevum! We welcome contributions from anyone who respects the physical laws that ground this project.

## Ground Rules

Every contribution must pass three checks before review:

### 1. Pillar Check
Does it respect the [Three Inviolable Pillars](RULES-ARCHITECTURE.md)?

| Pillar | Constraint |
|--------|-----------|
| **I — Hyperscale** | All algorithms O(n) or better. Lock-free data structures. No Mutex. |
| **II — Thermodynamics** | Landauer cost (Λ) recorded for every computation. E ≥ Λ always. |
| **III — Cognitive Complexity** | S_T (statistical complexity) ≠ Shannon entropy. ε-machine required. |

### 2. PACR Check
Does the change produce or consume valid [PACR 6-tuples](RULES-PACR.md)?

```
R = (ι, Π, Λ, Ω, Γ, P)
     │   │   │   │   │   └── Payload (bytes)
     │   │   │   │   └────── Cognitive split: S_T, H_T
     │   │   │   └────────── Resource triple: energy, time, space
     │   │   └────────────── Landauer cost (joules)
     │   └────────────────── Predecessor set (causal DAG edges)
     └────────────────────── Causal identity (128-bit ULID)
```

### 3. CI Gate
```bash
cargo fmt --all --check
cargo clippy --workspace --all-features -- -D warnings
cargo test --workspace
```

All three must pass. No exceptions.

## Commit Format

```
[phase N] module: brief description

Pillar: I/II/III/ALL
PACR field: ι/Π/Λ/Ω/Γ/P
Breaking: yes/no
```

## What to Contribute

### High-impact areas (most wanted):
- **New MCP tools** — extend `crates/aevum-mcp-server/src/tools/` with tools that produce PACR records
- **Hardware probes** — add energy measurement for your platform in `crates/ets-probe/`
- **ε-machine improvements** — higher-order CSSR, GPU-accelerated bootstrap in `crates/epsilon-engine/`
- **Client integrations** — connect Aevum to other MCP clients, AI frameworks, or agent platforms

### Good first issues:
- Add benchmarks with `criterion.rs` for any crate
- Improve error messages in `pacr-types` validation
- Add examples for `agent-card` schema

## Design Decision Process

When uncertain, ask:

> "Which physical law forces this choice?"

If no physical law forces it → make it configurable, not hardcoded.

## Code of Conduct

Be precise. Be honest about uncertainty (that's why `Estimate<T>` has `lower` and `upper` bounds). Respect thermodynamics — every computation has a cost, including code review.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
