# causal-dag

**Lock-free append-only causal DAG (G-Set CRDT) for AI agent memory.**

Part of the [Aevum](https://github.com/kwailapt/aevum) physics kernel.

[![Crates.io](https://img.shields.io/crates/v/causal-dag)](https://crates.io/crates/causal-dag)
[![docs.rs](https://img.shields.io/docsrs/causal-dag)](https://docs.rs/causal-dag)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](../../LICENSE)

## What It Is

A lock-free, append-only DAG for storing [`PacrRecord`] nodes linked by causal edges (Π). Backed by `DashMap` for O(1) lookup and O(|Π|) append. No `Mutex`, no `RwLock` in any hot path.

This is the memory substrate for Aevum: every `aevum_remember` call appends a node; every `aevum_recall` traverses the Π edges.

## Properties

| Property | Value |
|----------|-------|
| Append | O(|Π|) — validates predecessor existence |
| Lookup | O(1) — `DashMap` shard |
| Concurrency | Lock-free (sharded CAS) |
| CRDT | G-Set: monotone grow-only, merge = union |
| Ordering | Causal (Π edges), never timestamps |

## Usage

```rust
use causal_dag::CausalDag;
use pacr_types::{PacrRecord, /* ... */};

let dag = CausalDag::new();

// Append a genesis record (no predecessors)
let id = dag.append(record_with_no_predecessors)?;

// Append a causally dependent record
let id2 = dag.append(record_pointing_to(id))?;

// O(1) lookup
let node = dag.get(&id2).expect("just inserted");
```

## Causal Distance Tax

`causal_dag::distance_tax` enforces a **light-cone analog**: records whose causal predecessor is far away (many hops) pay a higher Λ surcharge. This prevents star-graph topologies (hub-and-spoke bottlenecks) from forming — Pillar I requires O(n) routing.

## License

Apache-2.0 — see [LICENSE](../../LICENSE).
