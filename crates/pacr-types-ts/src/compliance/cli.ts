#!/usr/bin/env node
// src/compliance/cli.ts
// PACR Compliance Suite v1.0 — CLI entry point
//
// Usage:
//   npx @aevum/pacr-compliance --target ./my-adapter.ts
//   npx @aevum/pacr-compliance --target ./my-adapter.ts --json
//   npx @aevum/pacr-compliance --help
//
// Exit codes:
//   0  COMPLIANT or PACR_LITE
//   1  NON_COMPLIANT
//   2  Usage / loading error

import { runCompliance } from './v1.js';
import type { ComplianceReport, ComplianceStatus, ComplianceVerdict } from './v1.js';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import process from 'node:process';

// ─────────────────────────────────────────────────────────────────────────────
// Argument parsing (zero external dependencies)
// ─────────────────────────────────────────────────────────────────────────────

interface CliArgs {
  target: string | null;
  json: boolean;
  help: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args = argv.slice(2);
  let target: string | null = null;
  let json = false;
  let help = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      help = true;
    } else if (arg === '--json') {
      json = true;
    } else if (arg === '--target' || arg === '-t') {
      target = args[++i] ?? null;
    } else if (arg?.startsWith('--target=')) {
      target = arg.slice('--target='.length);
    }
  }

  return { target, json, help };
}

// ─────────────────────────────────────────────────────────────────────────────
// Human-readable report renderer
// ─────────────────────────────────────────────────────────────────────────────

const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const DIM = '\x1b[2m';

function statusColor(status: ComplianceStatus): string {
  switch (status) {
    case 'PASS': return GREEN;
    case 'FAIL': return RED;
    case 'WARN': return YELLOW;
    case 'SKIP': return DIM;
  }
}

function verdictColor(verdict: ComplianceVerdict): string {
  switch (verdict) {
    case 'COMPLIANT': return GREEN;
    case 'PACR_LITE': return YELLOW;
    case 'NON_COMPLIANT': return RED;
  }
}

function renderReport(report: ComplianceReport): string {
  const lines: string[] = [];

  lines.push('');
  lines.push(`${BOLD}PACR Compliance Suite v${report.version}${RESET}`);
  lines.push(`${DIM}Target : ${report.target}${RESET}`);
  lines.push(`${DIM}Date   : ${report.timestamp}${RESET}`);
  lines.push('');
  lines.push(`${'─'.repeat(72)}`);

  let currentLevel = '';
  for (const result of report.results) {
    if (result.level !== currentLevel) {
      currentLevel = result.level;
      const levelLabel = currentLevel === 'MUST'
        ? 'MUST — 不合規即禁用商標'
        : currentLevel === 'SHOULD'
        ? 'SHOULD — 不通過則降級為 PACR-Lite'
        : 'MAY — 進階合規（成熟度指標）';
      lines.push('');
      lines.push(`${CYAN}${BOLD}[ ${currentLevel} ]${RESET}  ${DIM}${levelLabel}${RESET}`);
    }

    const color = statusColor(result.status);
    const statusTag = `${color}${BOLD}${result.status.padEnd(4)}${RESET}`;
    const durationTag = `${DIM}(${result.durationMs}ms)${RESET}`;
    lines.push(`  ${statusTag}  ${result.id}  ${result.message}  ${durationTag}`);

    if (result.evidence !== undefined && (result.status === 'FAIL' || result.status === 'WARN')) {
      const evidenceStr = JSON.stringify(result.evidence, replacer, 2)
        .split('\n')
        .map((l) => `        ${DIM}${l}${RESET}`)
        .join('\n');
      lines.push(`${DIM}       evidence:${RESET}`);
      lines.push(evidenceStr);
    }
  }

  lines.push('');
  lines.push(`${'─'.repeat(72)}`);
  lines.push('');

  const { summary } = report;
  const vColor = verdictColor(summary.verdict);
  lines.push(`${BOLD}Verdict : ${vColor}${summary.verdict}${RESET}`);
  lines.push('');
  lines.push(`  MUST  : ${GREEN}${summary.mustPass} PASS${RESET}  ${RED}${summary.mustFail} FAIL${RESET}`);
  lines.push(`  SHOULD: ${GREEN}${summary.shouldPass} PASS${RESET}  ${YELLOW}${summary.shouldWarn} WARN${RESET}`);
  lines.push(`  MAY   : ${GREEN}${summary.mayPass} PASS${RESET}`);
  lines.push('');

  if (summary.verdict === 'COMPLIANT') {
    lines.push(`${GREEN}${BOLD}✓ System is fully PACR-COMPLIANT.${RESET}`);
  } else if (summary.verdict === 'PACR_LITE') {
    lines.push(`${YELLOW}${BOLD}~ System qualifies as PACR-Lite (SHOULD tests did not all pass).${RESET}`);
  } else {
    lines.push(`${RED}${BOLD}✗ System is NON-COMPLIANT — ${summary.mustFail} MUST test(s) failed.${RESET}`);
    lines.push(`${RED}  PACR trademark usage is not permitted.${RESET}`);
  }
  lines.push('');

  return lines.join('\n');
}

/** JSON.stringify replacer: encode Infinity as strings for portability */
function replacer(_key: string, value: unknown): unknown {
  if (typeof value === 'number' && !isFinite(value)) {
    return value > 0 ? '__PACR_INF__' : '__PACR_NEG_INF__';
  }
  return value;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

const HELP = `
PACR Compliance Suite v1.0
Usage: pacr-compliance --target <adapter-file> [--json]

Options:
  --target <file>   Path to the adapter module (JS/TS).
                    Must export a default PACRComplianceTarget implementation.
  --json            Output raw JSON report instead of human-readable text.
  --help, -h        Show this help message.

Exit codes:
  0   COMPLIANT or PACR_LITE
  1   NON_COMPLIANT (one or more MUST tests failed)
  2   Usage error or adapter load failure

Example:
  pacr-compliance --target ./my-adapter.js
  pacr-compliance --target ./my-adapter.ts --json | jq .summary
`.trim();

async function main(): Promise<void> {
  const args = parseArgs(process.argv);

  if (args.help || args.target === null) {
    console.log(HELP);
    process.exit(args.help ? 0 : 2);
  }

  // Resolve the target path relative to cwd
  const targetPath = resolve(process.cwd(), args.target);
  const targetUrl = pathToFileURL(targetPath).href;

  // Dynamically import the adapter module
  let targetModule: unknown;
  try {
    targetModule = await import(targetUrl);
  } catch (err) {
    console.error(`Error loading adapter from "${args.target}": ${String(err)}`);
    process.exit(2);
  }

  // Expect a default export that is the compliance target
  const mod = targetModule as Record<string, unknown>;
  const adapter = mod['default'] ?? mod;

  if (
    adapter === null ||
    typeof adapter !== 'object' ||
    typeof (adapter as Record<string, unknown>)['triggerEvent'] !== 'function' ||
    typeof (adapter as Record<string, unknown>)['triggerCausalChain'] !== 'function' ||
    typeof (adapter as Record<string, unknown>)['getAgentCard'] !== 'function' ||
    typeof (adapter as Record<string, unknown>)['retrieveRecord'] !== 'function'
  ) {
    console.error(
      `Error: adapter module at "${args.target}" does not export a valid PACRComplianceTarget.\n` +
      'The default export (or module itself) must implement:\n' +
      '  { name, triggerEvent, triggerCausalChain, getAgentCard, retrieveRecord }',
    );
    process.exit(2);
  }

  // Run the compliance suite
  let report: ComplianceReport;
  try {
    report = await runCompliance(adapter as Parameters<typeof runCompliance>[0]);
  } catch (err) {
    console.error(`Compliance suite encountered a fatal error: ${String(err)}`);
    process.exit(2);
  }

  // Output
  if (args.json) {
    process.stdout.write(JSON.stringify(report, replacer, 2) + '\n');
  } else {
    process.stdout.write(renderReport(report));
  }

  // Exit code
  process.exit(report.summary.verdict === 'NON_COMPLIANT' ? 1 : 0);
}

// Prevent top-level await errors in older Node by using .catch
main().catch((err: unknown) => {
  console.error(`Fatal: ${String(err)}`);
  process.exit(2);
});
