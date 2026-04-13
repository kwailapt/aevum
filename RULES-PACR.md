# RULES-PACR.md — PACR Formal Definition & Physical Axioms

> Subordinate to CLAUDE.local.md. This file is the mathematical specification
> of PACR. Claude Code should reference this when implementing pacr-types crate.

---

## §1 The Problem PACR Solves (Precise Statement)

In a universe obeying known physical laws, for any computation event,
what is the MINIMUM information set that must be preserved to ensure
NO future analysis capability is irreversibly lost?

This is a MINIMAX problem: minimize dimensions (storage cost),
maximize future analytical completeness (never close an analysis path).

---

## §2 Four Physical Axioms (Derivation Starting Points)

### Axiom I — Causality
In any universe obeying special relativity, the only physically meaningful
partial order between events is CAUSAL ORDER. Total order (global clocks)
does not exist in distributed systems — this is a physics constraint,
not an engineering limitation. Simultaneity is observer-dependent.

### Axiom II — Landauer's Principle
Any computational system at temperature T, erasing 1 bit of information,
must dissipate at least k_B × T × ln(2) energy to the environment.
This is NOT an engineering limit — it is a direct corollary of the
Second Law of Thermodynamics.

### Axiom III — Conservation & Constraint Laws
Three inescapable resource constraints:
- Energy conservation (E cannot exceed supply)
- Causal time lower bound (T ≥ πℏ/2E, Margolus-Levitin)
- Space lower bound (S has physical minimum per Holevo-von Neumann)
These form a constraint triple (E, T, S) on a 2D manifold.

### Axiom IV — Computational Mechanics Fundamental Theorem
Any data stream has intrinsic causal structure decomposable into:
- S_T (statistical complexity): minimum causal-state information to predict
- H_T (entropy rate): residual unpredictability given causal states
This decomposition is UNIQUE (asymptotically) and observer-independent.
S_T and H_T are inseparable projections of the same ε-machine.

---

## §3 Six Atomic Dimensions (Derived from Axioms)

Each dimension passes three tests:
(a) Which axiom mandates its existence?
(b) Can it be derived from other dimensions? (Must be NO)
(c) Can it be decomposed further? (Must be NO)

### Dimension 1: ι ∈ I — Causal Identity
- **Origin**: Logical a priori (referential necessity) + Axiom I
- **Nature**: Scalar identifier. Zero-dimensional, cannot decompose further.
- **Rust**: `CausalId(u128)` — 128-bit ULID

### Dimension 2: Π ⊆ I — Causal Predecessor Set
- **Origin**: Axiom I (causal partial order → DAG edges)
- **Nature**: Unordered set (partial order, NOT total order — physics-mandated)
- **Independence**: ι tells "which event", Π tells "caused by what" — neither derives the other
- **Rust**: `SmallVec<[CausalId; 4]>`

### Dimension 3: Λ = (λ̂, λ⁻, λ⁺) — Landauer Cost
- **Origin**: Axiom II
- **Nature**: Scalar energy value (joules) with confidence interval
- **Independence**: Ω.E gives UPPER bound; Λ gives LOWER bound. Gap = waste. Neither derives the other.
- **Rust**: `Estimate<f64>`

### Dimension 4: Ω = ((ê,e⁻,e⁺), (t̂,t⁻,t⁺), (ŝ,s⁻,s⁺)) — Resource Triple
- **Origin**: Axiom III
- **Nature**: Three physically coupled quantities on a 2D constraint surface
- **Why triple not three separate**: Provides consistency check (Margolus-Levitin: T ≥ πℏ/2E)
- **Rust**: `ResourceTriple { energy: Estimate<f64>, time: Estimate<f64>, space: Estimate<f64> }`

### Dimension 5: Γ = ((ŝ_T, s_T⁻, s_T⁺), (ĥ_T, h_T⁻, h_T⁺)) — Cognitive Split
- **Origin**: Axiom IV
- **Nature**: Two inseparable projections of the same ε-machine
- **Why not derive from P**: S_T/H_T are DISTRIBUTIONAL properties, not single-instance.
  Re-computing from scattered Payloads across nodes is intractable. Record once, use forever.
- **Rust**: `CognitiveSplit { statistical_complexity: Estimate<f64>, entropy_rate: Estimate<f64> }`

### Dimension 6: P ∈ {0,1}* — Opaque Payload
- **Origin**: Completeness axiom (semantic content must be preserved)
- **Nature**: Finite byte sequence, opaque to PACR layer (UNIX byte-stream spirit)
- **Rust**: `bytes::Bytes`

---

## §4 Proofs

### Completeness (no 7th dimension needed)
- Thermodynamic 0th law → covered by Λ (temperature is environment parameter)
- Thermodynamic 1st law → covered by Ω.E
- Thermodynamic 2nd law → covered by Λ
- Special relativity → covered by (ι, Π)
- Quantum mechanics → covered by Ω constraint (Margolus-Levitin, Bremermann)
- Information theory → covered by Γ.H_T
- Computational complexity → NOT a physics constraint; does not generate new dimension
- General relativity → negligible at Earth surface; append via meta-rule 1 if needed

### Independence (cannot reduce to 5)
| Dimension | Removable? | Counterexample |
|-----------|------------|----------------|
| ι | No | Two identical-property events at different DAG positions indistinguishable |
| Π | No | Known identity but unknown predecessors → isolated point in DAG |
| Λ | No | Ω.E gives only upper bound, not lower bound |
| Ω | No | Λ gives only lower bound, not actual consumption |
| Γ | No | Cannot reliably estimate distributional properties from single Payload |
| P | No | First 5 dimensions contain no semantic content |

---

## §5 Five Meta-Properties (derived from definition)

1. **Physical Completeness**: 6 dimensions cover all known physical constraints on computation events.
2. **Mutual Independence**: No dimension derivable from any combination of the other 5.
3. **Atomic Irreducibility**: Each dimension at minimum physical granularity.
4. **Measurement Tolerance**: Every physical quantity = (point, lower, upper). Day 0 rough estimates and Year-5 precision use the SAME format.
5. **Temporal Immutability**: PACR definition derived from physics, not technology. Only changes if physics changes. New dimensions APPEND-ONLY.

---

## §6 Ontological Status (One-Liner)

**PACR is the minimal sufficient statistic that physics imposes on computation events.**

Sufficient = all physically extractable information recoverable from R.
Minimal = removing any dimension permanently loses some analysis capability.

PACR is to computation events what the Action is to mechanical trajectories:
the minimal complete starting point from which everything can be derived.
