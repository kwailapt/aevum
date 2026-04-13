# Power-Law Primacy Axiom

> **Any long-lived adaptive system operating under finite resources shall assume that utility, risk, and compounding potential are heavy-tailed. Allocation and governance must prioritize tail-critical nodes over average-case coverage.**

## Rationale

Under Gaussian assumptions, the mean governs. Under power-law assumptions — which hold for code fitness landscapes, organelle reuse frequency, and evolutionary benefit distributions — the **tail governs**. A single elite organelle with leverage_score ≥ 5.0 may yield more cumulative Φ than the entire bottom 80% of the candidate pool combined.

Optimizing for the average is thermodynamic waste: it dissipates finite Φ budget across candidates whose marginal contribution is statistically negligible.

## The Leverage Score

The system evaluates every organelle and mutation event with the `ComputeLeverage` operator (TICK 40.0 Phase 0, `autopoietic_core.py`):

```
Leverage_Score = (Impact × Reuse_Potential × Transferability) / Thermodynamic_Cost
```

| Dimension          | Definition                                                         |
|--------------------|--------------------------------------------------------------------|
| Impact             | Expected delta-Φ if this candidate is adopted                      |
| Reuse_Potential    | Estimated future reuse count without structural modification        |
| Transferability    | Cross-niche portability ∈ [0, 1]; 1 = universally composable       |
| Thermodynamic_Cost | Σ (cpu_fraction + ram_fraction + latency_norm) from sandbox        |

The score is **multiplicative**: a zero in any numerator dimension collapses the score regardless of the others. There is no additive averaging.

## The Tail Discovery Loop

`tail_discovery_loop()` in `autopoietic_core.py` partitions any candidate list into:

- **ELITE** (top 20% by leverage_score): receive 80% of available Φ budget
- **DEFERRED** (bottom 80%): zero direct resource allocation; retained for diversity bookkeeping only

This is the computational formalization of the 80/20 rule applied to evolutionary pressure.

## The 3 Irreversible Topological Dimensions

Every sealed structure in the system carries three provenance anchors (established TICK 28.0 in `rule_ir.py`, locked by TICK 40.0 Phase 0's `ConstitutionalViolationError(BaseException)` upgrade):

| Field             | Purpose                                                                              |
|-------------------|--------------------------------------------------------------------------------------|
| `substrate_deps`  | Hardware/framework provenance at mint time — prevents cross-substrate semantic drift |
| `seed`            | PRNG anchor for deterministic rollback and replay across lineage splits               |
| `content_hash`    | SHA-256 tamper seal of content + deps + seed — mismatch raises `ConstitutionalViolationError` (BaseException, uncatchable) |

## Integration Points

| Component              | How Leverage Governs It                                                      |
|------------------------|------------------------------------------------------------------------------|
| `kelly_bet_size()`     | Takes `leverage_score` as input; returns Φ fraction to allocate              |
| `pareto_filter()`      | 80/20 Pareto rank filter on 3D survival vector (pre-TICK 40 complement)      |
| `tail_discovery_loop()`| Primary TICK 40.0 allocation gate; supersedes local heuristics               |
| `mutator_daemon.py`    | Should route targeted mutations to ELITE pool organelles first               |
| `island_good/`         | Leverage-scored elites are the primary seeding source for cross-pollination  |

## Constitutional Lock

`ConstitutionalViolationError` inherits from `BaseException` since TICK 40.0 Phase 0. A tampered or corrupted sealed structure is an **extinction-class event** — not a recoverable runtime error. The daemons will halt, not log-and-continue.
