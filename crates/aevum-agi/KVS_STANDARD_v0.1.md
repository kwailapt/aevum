# Knowledge Value Score (KVS) Standard — v0.1
**Effective Tick:** 31.0
**Status:** Draft Ratified

---

## 1. Motivation

The `ConstraintMatrix` is not merely a configuration object — it is a **genetic asset** with an economic lifecycle. Each time a matrix governs an evolutionary decision, it either creates or destroys fitness value. The Knowledge Value Score (KVS) captures the **cumulative economic worth** of a matrix as a function of its reuse history and the fitness outcomes it has produced.

KVS enables the system to preferentially retain, promote, and breed from high-value constraint matrices over evolutionary generations — analogous to capital compounding.

---

## 2. Definitions

| Symbol | Field | Type | Description |
|---|---|---|---|
| `r` | `len(interaction_history)` | `int` | Number of times this matrix has been applied (reuse count) |
| `Y` | `meta_yield` | `float` | Cumulative signed fitness delta attributed to this matrix across all applications. Dimensionless. |
| `K` | `kvs_score` | `float` | Knowledge Value Score — the primary economic ranking metric |

---

## 3. KVS Formula

```
K = r × max(0, 1 + Y)
```

**Derivation:**

- The factor `(1 + Y)` converts `meta_yield` to a **multiplicative yield coefficient**:
  - `Y = 0.0` → coefficient = 1.0 (neutral; score scales linearly with reuse)
  - `Y > 0.0` → coefficient > 1.0 (compounding; each additional use is worth more)
  - `Y < -1.0` → coefficient ≤ 0.0 (destructive; matrix has negative economic value)
- Clamped at 0 via `max(0, ...)` to prevent negative scores (economic value cannot be less than zero)
- Multiplied by `r` to reward **reuse** — a matrix that works and keeps working compounds value

**Key properties:**
- **Deterministic:** `K` is a pure function of `meta_yield` and `len(interaction_history)`. It can be recomputed exactly from serialized state.
- **Monotonically non-decreasing in r** (for Y ≥ -1): Every reuse at non-negative yield increases K
- **Penalizes harm:** Persistent negative `meta_yield` below -1.0 collapses K to zero, marking the matrix as economically inert

---

## 4. meta_yield Accounting

`meta_yield` is a **running sum of signed fitness deltas**:

```
Y_t = Y_{t-1} + Δf_t
```

where `Δf_t` is the fitness change observed in the evolutionary cycle during which the matrix governed decisions.

**Attribution rules:**
- `Δf` is computed as `(fitness_after - fitness_before)` at the island level
- Positive mutations yield `Δf > 0`; neutral mutations yield `Δf ≈ 0`; catastrophic mutations yield `Δf << 0`
- Attribution is **single-level**: only the matrix that governed the mutating island is credited/penalized

---

## 5. interaction_history Format

Each entry is a UTF-8 string with the following pipe-delimited structure:

```
{timestamp}|{agent}|Δ{fitness_delta:+.4f}[|{event_tag}]
```

Example entries:
```
20260407T142301Z|mutator_daemon|Δ+0.0312|tick_31
20260407T143015Z|mutator_daemon|Δ-0.0050|tick_31
20260407T150022Z|local_breeder|Δ+0.1200|elite_promotion
```

**Retention policy:** The last **50 entries** are retained on serialization. Older entries are permanently discarded. The `reuse count r` is therefore `len(interaction_history)` after load, bounded at 50. Use `meta_yield` (the running sum) as the authoritative fitness-yield record — it is never truncated.

---

## 6. Exclusion from content_hash

`kvs_score`, `meta_yield`, `interaction_history`, and `verified_by` are **intentionally excluded** from `ConstraintMatrix._compute_content_hash()`. See `rule_ir.py:_compute_content_hash()` for the authoritative exclusion documentation.

**Rationale:** These fields change on every `record_application()` call. Including them in the hash payload would cause `verify_integrity()` to raise `ConstitutionalViolationError` on every application event, rendering the integrity mechanism useless.

---

## 7. KVS in Evolutionary Selection

Future selection pressure (TICK 32.0+):

| KVS Range | Elite Status | Selection Weight |
|---|---|---|
| `K ≥ 50.0` | Tier-1 Elite | 3× selection weight |
| `25.0 ≤ K < 50.0` | Tier-2 Established | 2× selection weight |
| `5.0 ≤ K < 25.0` | Tier-3 Emerging | 1× selection weight |
| `K < 5.0` | Unproven | 0.5× selection weight |
| `K = 0.0, Y < -1.0` | Inert / Harmful | Eligible for culling |

These thresholds are in the **Evolvable Soft Shell** and may be updated by the mutation pipeline.

---

## 8. Implementation Reference

```python
# ConstraintMatrix.record_application() — canonical KVS update
self.interaction_history.append(label)
if len(self.interaction_history) > 50:
    self.interaction_history = self.interaction_history[-50:]
self.meta_yield += fitness_delta
self.verified_by = agent
reuse = len(self.interaction_history)
self.kvs_score = reuse * max(0.0, 1.0 + self.meta_yield)
```

---

*This standard defines the economic valuation layer of the Autopoietic AGI substrate.*
