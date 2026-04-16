#!/usr/bin/env node
// aevum-filter — thin CLI shell over the live Aevum MCP server.
// Usage:
//   npx aevum-filter "your text here"
//   echo "long text" | npx aevum-filter
//   npx aevum-filter --url https://your-server:8889 "text"

const MCP_URL = process.env.AEVUM_URL || "https://mcp.aevum.network";
const args = process.argv.slice(2);

let url = MCP_URL;
let textArg = null;

// Parse args
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--url" && args[i + 1]) {
    url = args[i + 1];
    i++;
  } else if (args[i] === "--help" || args[i] === "-h") {
    console.log(`aevum-filter — Cut AI token cost by 90%

Usage:
  npx aevum-filter "your text"
  echo "long text" | npx aevum-filter
  npx aevum-filter --url https://your-server:8889 "text"

Options:
  --url <endpoint>  MCP server URL (default: https://mcp.aevum.network)
  --help            Show this help

How it works:
  Sends text to aevum_filter, which uses a CSSR ε-machine to extract
  statistical complexity (S_T) and discard entropy noise (H_T).
  Same information, 90% fewer tokens.

Source: https://github.com/kwailapt/aevum`);
    process.exit(0);
  } else {
    textArg = args.slice(i).join(" ");
    break;
  }
}

async function getInput() {
  if (textArg) return textArg;

  // Read from stdin
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8").trim();
}

async function filter(text) {
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: {
      name: "aevum_filter",
      arguments: { content: text },
    },
  });

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });

  if (!resp.ok) {
    console.error(`Error: ${resp.status} ${resp.statusText}`);
    process.exit(1);
  }

  const data = await resp.json();
  const result = data.result || {};

  // Handle both stdio (content[].text) and HTTP (flat result) formats
  if (Array.isArray(result.content) && result.content.length > 0) {
    const inner = result.content[0].text;
    try {
      return JSON.parse(inner);
    } catch {
      return { content: inner, filtered: true };
    }
  }

  // HTTP flat result: { content: "...", filtered: true, kept_chunks: N, ... }
  if (typeof result.content === "string" || result.filtered !== undefined) {
    return result;
  }

  return result;
}

async function main() {
  const text = await getInput();
  if (!text) {
    console.error("Usage: npx aevum-filter 'your text here'");
    process.exit(1);
  }

  const inputLen = text.length;
  const result = await filter(text);

  const output = typeof result.content === "string" ? result.content : JSON.stringify(result);
  const outputLen = output.length;
  const compression = inputLen > 0 ? Math.round((1 - outputLen / inputLen) * 100) : 0;

  if (output) console.log(output);
  console.error(`\n--- aevum-filter ---`);
  console.error(`Input:       ${inputLen} chars`);
  console.error(`Output:      ${outputLen} chars`);
  console.error(`Compression: ${compression}%`);
  console.error(`Kept chunks: ${result.kept_chunks ?? "?"} / ${result.total_chunks ?? "?"}`);
  console.error(`S_T threshold: ${result.s_t_threshold ?? "?"}`);
  console.error(`Server:      ${url}`);
}

main().catch((e) => {
  console.error(`Error: ${e.message}`);
  process.exit(1);
});
