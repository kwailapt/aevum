# SPEC-AGENTCARD.md — AgentCard Schema Specification

> This defines the AgentCard semantic waist (Layer 3).
> AgentCard is a PURE DATA SCHEMA. Zero execution logic. Zero network calls.
> It compiles and works independently of Aevum Core.

---

## §1 Design Principle

AgentCard is to A2A what HTTP headers are to the web:
a standardized, human-readable, machine-parseable declaration of identity and capability.

It is the UNIX "file descriptor" of the agent economy:
every agent interaction begins by exchanging AgentCards.

### Non-Negotiable Rules:
1. AgentCard contains NO execution logic (no RPC, no network, no state)
2. AgentCard does NOT depend on Aevum Core internals
3. AgentCard CAN be parsed by ANY framework (not just Aevum)
4. AgentCard is the Payload (P) inside a PACR record — PACR treats it as opaque bytes

---

## §2 AgentCard Schema (v1.0)

```rust
/// An agent's self-declaration of identity, capabilities, and terms.
/// This is the "business card" of the A2A economy.
///
/// Layer: 3 (Semantic Waist). Not tied to any physical pillar.
pub struct AgentCard {
    // ═══ Identity (bound to PACR ι) ═══
    /// Globally unique agent identifier (same ULID space as CausalId)
    pub agent_id: String,           // 128-bit ULID as Crockford Base32
    
    /// Human-readable display name
    pub name: String,
    
    /// Semantic version of this agent's card format
    pub version: String,            // semver, e.g. "1.0.0"

    // ═══ Capability Declaration ═══
    /// List of capabilities this agent offers
    pub capabilities: Vec<Capability>,

    // ═══ Endpoint ═══
    /// How to reach this agent
    pub endpoint: Endpoint,

    // ═══ Pricing & Terms ═══
    /// Cost model for interacting with this agent
    pub pricing: Option<PricingModel>,

    // ═══ PACR-Derived Metadata (populated by π projection from history) ═══
    /// Interaction statistics derived from PACR causal history
    /// These fields are NOT self-declared — they are COMPUTED from the ledger
    pub metadata: HashMap<String, serde_json::Value>,
}

pub struct Capability {
    /// Machine-readable capability identifier
    pub id: String,                 // e.g. "text-generation", "code-review"
    
    /// Human-readable description
    pub description: String,
    
    /// Input schema (JSON Schema or equivalent)
    pub input_schema: Option<serde_json::Value>,
    
    /// Output schema
    pub output_schema: Option<serde_json::Value>,
}

pub struct Endpoint {
    /// Protocol type
    pub protocol: Protocol,
    
    /// URL or address
    pub url: String,
}

pub enum Protocol {
    Http,
    WebSocket,
    Sse,
    Grpc,
    Mcp,           // Model Context Protocol
    GoogleA2A,     // Google's A2A protocol
}

pub struct PricingModel {
    /// Base cost per request (in Joules — thermodynamic settlement)
    pub base_cost_joules: Option<f64>,
    
    /// Estimated latency (derived from PACR Ω history)
    pub estimated_latency_ms: Option<f64>,
    
    /// Currency (if fiat/token settlement also supported)
    pub currency: Option<String>,
    pub cost_per_request: Option<f64>,
}
```

---

## §3 PACR ↔ AgentCard Projection Functions

### π Projection: PACR History → AgentCard Metadata

```
π: [PacrRecord] → AgentCard.metadata
```

The π function projects dynamic PACR causal history into static AgentCard metadata:
- `pacr:interaction_count` ← count of PACR records involving this agent_id
- `pacr:avg_latency` ← Σ(Ω.time) / N with time-decay weighting
- `pacr:avg_cost` ← Σ(Ω.energy) / N with time-decay weighting  
- `pacr:reputation_score` ← f(success_rate, latency, Sₜ/Hₜ ratio)
- `pacr:influence_rank` ← PageRank variant on causal interaction graph
- `pacr:critical_score` ← betweenness centrality

### Σ Aggregation: Must Include Time Decay

Old PACR records contribute LESS to current AgentCard metadata.
Decay function: `weight(record) = exp(-λ × (now - record.Ω.time))`

This forces agents to CONTINUOUSLY interact to maintain their capability claims.
Stale agents naturally lose reputation — no manual intervention needed.

---

## §4 agentcard-spec (Open Source Deliverable)

The `agentcard-spec` repository on GitHub should contain:
1. `schema.json` — JSON Schema definition of AgentCard v1.0
2. `README.md` — <300 lines explaining how ANY agent can create an AgentCard
3. `examples/` — Sample AgentCards for common agent types
4. `validators/` — Lightweight validation library (Rust + TypeScript + Python)
5. `LICENSE` — Apache 2.0

This is the FIRST open-source artifact to publish.
It is the protocol virus seed — zero cost to create, infinite compound interest.
