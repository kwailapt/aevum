# AgentCard

> AgentCard is to A2A what HTTP headers are to the web.

A standardized, human-readable, machine-parseable declaration of agent identity and capability. Every agent-to-agent interaction begins by exchanging AgentCards.

**Schema version:** 1.0
**License:** Apache 2.0

---

## What is AgentCard?

When HTTP was designed, headers solved a critical bootstrapping problem: how does a server know what format a client accepts before any negotiation happens? The `Content-Type`, `Accept`, and `Authorization` headers let two endpoints understand each other before a single byte of payload is exchanged.

AgentCard solves the same problem for agent-to-agent (A2A) communication:

| HTTP Headers | AgentCard |
|---|---|
| `Content-Type` | `capabilities[].id` |
| `Accept` | input/output schemas |
| `Authorization` | `endpoint.auth` |
| `Server` / `User-Agent` | `name` + `version` |
| Cache headers | `metadata.pacr:*` |

An AgentCard is a **pure data document** — no network calls, no execution logic. Any framework can parse it. It is transported as the Payload (P) inside a PACR record; PACR treats it as opaque bytes.

---

## Quick Start

### Minimal valid AgentCard

```json
{
  "agent_id": "01HZQK3P8EMXR9V7T5N2W4J6C0",
  "name": "My Agent",
  "version": "1.0.0",
  "capabilities": [
    {
      "id": "text.generate",
      "description": "Generate text given a prompt"
    }
  ],
  "endpoint": {
    "protocol": "http",
    "url": "https://agent.example.com/api"
  }
}
```

### Generate an `agent_id`

`agent_id` is a [ULID](https://github.com/ulid/spec) encoded as Crockford Base32 (26 characters). Use any ULID library:

```bash
# Python
python3 -c "import uuid; print(str(uuid.uuid4()).replace('-','').upper()[:26])"

# Rust
ulid = "1.0"  # in Cargo.toml
let id = ulid::Ulid::new().to_string();

# Node.js
npm install ulid && node -e "const {ulid} = require('ulid'); console.log(ulid())"
```

Alternatively, any 26-character Crockford Base32 string is valid.

---

## Schema Reference

Full JSON Schema: [`schema.json`](./schema.json)

### Top-level fields

| Field | Required | Type | Description |
|---|---|---|---|
| `agent_id` | ✓ | string | ULID in Crockford Base32 (26 chars) |
| `name` | ✓ | string | Human-readable display name (max 128 chars) |
| `version` | ✓ | string | Semver 2.0 of this card |
| `capabilities` | ✓ | array | One or more capabilities (see below) |
| `endpoint` | ✓ | object | How to reach this agent |
| `pricing` | — | object\|null | Cost model (optional) |
| `metadata` | — | object | π-projected PACR stats (optional) |

### Capability

```json
{
  "id": "code.review",
  "description": "Review source code and return structured feedback",
  "tags": ["code", "review", "quality"],
  "input_schema": {
    "type": "object",
    "required": ["source", "language"],
    "properties": {
      "source": { "type": "string" },
      "language": { "type": "string" }
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["issues"],
    "properties": {
      "issues": { "type": "array" },
      "summary": { "type": "string" }
    }
  }
}
```

| Field | Required | Type | Description |
|---|---|---|---|
| `id` | ✓ | string | Machine-readable identifier, dot-namespaced (e.g. `text.generate`) |
| `description` | ✓ | string | Human-readable description (max 512 chars) |
| `tags` | — | string[] | Semantic tags for discovery |
| `input_schema` | — | JSON Schema\|null | Accepted input structure |
| `output_schema` | — | JSON Schema\|null | Produced output structure |

### Endpoint

```json
{
  "protocol": "http",
  "url": "https://agent.example.com/api",
  "health_url": "https://agent.example.com/health",
  "auth": {
    "scheme": "bearer",
    "token_url": "https://auth.example.com/token"
  }
}
```

| Field | Required | Type | Description |
|---|---|---|---|
| `protocol` | ✓ | enum | `http`, `websocket`, `sse`, `grpc`, `mcp`, `google_a2a`, `native` |
| `url` | ✓ | string | URI where the agent accepts requests |
| `health_url` | — | string | Optional health-check URI |
| `auth` | — | object\|null | Authentication config |

**Auth schemes:** `none`, `bearer`, `api_key`, `oauth2`, `mtls`

### PricingModel

Pricing uses **Joules** as the canonical unit of account — thermodynamic settlement that is protocol-independent and cannot be inflated.

```json
{
  "base_cost_joules": 2.854e-21,
  "estimated_latency_ms": 120.0,
  "currency": "USD",
  "cost_per_request": 0.001
}
```

| Field | Type | Description |
|---|---|---|
| `base_cost_joules` | number\|null | Cost per request in Joules (Landauer floor at 300K: 2.854×10⁻²¹ J) |
| `estimated_latency_ms` | number\|null | Estimated end-to-end latency in ms |
| `currency` | string\|null | ISO 4217 or token symbol for fiat/token settlement |
| `cost_per_request` | number\|null | Cost in the specified fiat/token currency |

The **Landauer floor** (2.854×10⁻²¹ J at 300 K) is the minimum thermodynamic cost of erasing one bit. `base_cost_joules` must be ≥ this value.

---

## PACR-Derived Metadata (π projection)

Fields prefixed `pacr:` in `metadata` are **computed from the causal ledger**, not self-declared. A validator or router that has access to the PACR ledger populates them. An agent operator MUST NOT forge these fields.

| Key | Description |
|---|---|
| `pacr:interaction_count` | Count of PACR records involving this agent |
| `pacr:avg_latency_ms` | Time-decay-weighted average latency |
| `pacr:avg_cost_joules` | Time-decay-weighted average energy cost |
| `pacr:reputation_score` | Score in [0, 1]: f(success_rate, latency, Sτ/Hτ) |
| `pacr:influence_rank` | PageRank on causal interaction graph |
| `pacr:critical_score` | Betweenness centrality |

**Decay formula:** `weight(record) = exp(−λ × (now − record.Ω.time))`

Old interactions contribute less. Agents that stop interacting naturally lose reputation without manual intervention.

Non-`pacr:` metadata fields may be freely set by the operator.

---

## Validation

### Rust

```toml
# Cargo.toml
[dependencies]
agentcard-validator = { path = "validators/rust" }
```

```rust
use agentcard_validator::validate;

let json = std::fs::read_to_string("my-agent.json")?;
let errors = validate(&json);
if errors.is_empty() {
    println!("Valid AgentCard");
} else {
    for e in &errors { eprintln!("Error: {e}"); }
}
```

### Python (jsonschema)

```python
import json, jsonschema

schema = json.load(open("schema.json"))
card   = json.load(open("my-agent.json"))
jsonschema.validate(card, schema)  # raises ValidationError on failure
```

### Node.js (ajv)

```js
const Ajv = require("ajv/dist/2020");
const schema = require("./schema.json");
const card   = require("./my-agent.json");

const ajv = new Ajv();
const valid = ajv.validate(schema, card);
if (!valid) console.error(ajv.errors);
```

---

## Examples

| File | Agent type |
|---|---|
| [`examples/llm-agent.json`](./examples/llm-agent.json) | Language model agent |
| [`examples/code-review-agent.json`](./examples/code-review-agent.json) | Code review agent |
| [`examples/data-pipeline-agent.json`](./examples/data-pipeline-agent.json) | Data pipeline / ETL agent |

---

## Serve your AgentCard

Place your AgentCard at `.well-known/agent.json` on your domain for automatic discovery:

```
https://your-agent.example.com/.well-known/agent.json
```

This follows the [Well-Known URIs RFC 8615](https://www.rfc-editor.org/rfc/rfc8615) convention.

---

## Design Invariants

1. **Pure data** — AgentCard contains no execution logic, no RPC, no network calls.
2. **Zero core dependency** — can be parsed by any framework without Aevum Core.
3. **Append-only schema** — existing fields never change semantics; new fields may be added.
4. **Metadata is derived** — `pacr:*` fields come from the ledger, not the agent's self-report.

---

## Contributing

1. Fork the repository
2. Add your validator or example to the appropriate directory
3. Ensure `validators/rust/` passes `cargo test`
4. Open a pull request

Issues and RFCs welcome.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE)
