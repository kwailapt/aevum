# aevum-filter

Cut your AI agent's token cost by 90%. One command.

## Usage

```bash
# Filter text directly
npx aevum-filter "Your long AI response text here..."

# Pipe from stdin
echo "Long text..." | npx aevum-filter

# Use your own Aevum server
npx aevum-filter --url http://localhost:8889 "text"
```

## How it works

Sends text to [Aevum's](https://github.com/kwailapt/aevum) `aevum_filter` tool, which uses a **CSSR ε-machine** to extract statistical complexity (S_T) and discard entropy noise (H_T).

- **S_T** = minimal causal structure needed to predict the process (signal)
- **H_T** = residual unpredictability (noise)
- Most MCP responses are 90% H_T noise → `aevum_filter` keeps S_T, drops H_T

Same information. 90% fewer tokens. Real physics.

## No setup required

The default endpoint is `https://mcp.aevum.network` — no API key, no account.

## License

Apache 2.0
