"""
causal_timechain.py
====================
CSO Ledger Hasher — Git-backed Causal Timestamp Oracle

Reads the current KVS/reputation ledger state from the running A2A gateway,
computes a deterministic SHA-256 Merkle-root analog of the global reputation
state, and anchors it to local git history as an empty commit.

This transforms the git log into a free, verifiable causal timestamp chain:
each commit proves that at wall-clock time T, the reputation ledger hash was H.

Usage:
    python causal_timechain.py [--gateway URL] [--dry-run] [--period-hours N]

Options:
    --gateway       Base URL of the A2A gateway  [default: http://localhost:8420]
    --period-hours  Settlement lookback window in hours  [default: 87600 (~10yr)]
    --dry-run       Print the hash and commit message without committing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_GATEWAY = "http://localhost:8420"


# ──────────────────────────────────────────────
# Step 1: Fetch ledger state from the live server
# ──────────────────────────────────────────────

def fetch_ledger_state(gateway_url: str, period_hours: float) -> dict:
    """
    Fetch the full economics settlement snapshot from the A2A gateway.

    Queries two endpoints and merges their output into a single canonical dict:
      GET /economics?period_hours=<N>  — per-agent settlement records
      GET /health                      — global causal chain stats

    Returns a dict suitable for deterministic hashing.
    """
    base = gateway_url.rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        settlements_resp = client.get(
            f"{base}/economics",
            params={"period_hours": period_hours},
        )
        settlements_resp.raise_for_status()
        settlements_data: dict = settlements_resp.json()

        health_resp = client.get(f"{base}/health")
        health_resp.raise_for_status()
        health_data: dict = health_resp.json()

    # Sort settlements by agent_id for determinism (dict order is insertion-order
    # in Python 3.7+ but JSON decode order depends on server; sort explicitly).
    settlements = sorted(
        settlements_data.get("settlements", []),
        key=lambda s: s.get("agent_id", ""),
    )

    return {
        "schema_version": "causal_timechain/0.1",
        "gateway": gateway_url,
        "period_hours": period_hours,
        "settlements": settlements,
        "global_stats": {
            "agents_online":        health_data.get("agents_online", 0),
            "causal_chains":        health_data.get("causal_chains", 0),
            "global_success_rate":  health_data.get("global_success_rate", 0.0),
        },
    }


# ──────────────────────────────────────────────
# Step 2: Compute deterministic SHA-256 hash
# ──────────────────────────────────────────────

def compute_merkle_root(state: dict) -> str:
    """
    Compute a deterministic SHA-256 digest of the global ledger state.

    Serialises `state` to canonical JSON (sorted keys, no extra whitespace)
    then returns the hex digest.  Deterministic for identical state snapshots
    regardless of Python version or platform byte-order.
    """
    canonical: str = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────
# Step 3: Anchor hash to git history
# ──────────────────────────────────────────────

def anchor_to_git(ledger_hash: str, dry_run: bool = False) -> str:
    """
    Create an empty git commit whose message embeds the ledger hash.

    Commit message format:
        CSO_Ledger_Hash: <sha256hex>  ts=<unix_epoch>

    The `ts=` field allows external verifiers to correlate the commit timestamp
    (signed by GitHub's infrastructure) with the wall-clock time recorded here.

    If `dry_run` is True, prints the commit message without executing git.
    Returns the commit message string in both cases.
    """
    ts = int(time.time())
    message = f"CSO_Ledger_Hash: {ledger_hash}  ts={ts}"

    if dry_run:
        print(f"[DRY RUN] Would commit:\n  {message}")
        return message

    result = subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"git commit failed (exit {result.returncode}):\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )

    return message


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Anchor the CSO reputation ledger hash to git history.",
    )
    p.add_argument(
        "--gateway",
        default=_DEFAULT_GATEWAY,
        help=f"A2A gateway base URL (default: {_DEFAULT_GATEWAY})",
    )
    p.add_argument(
        "--period-hours",
        type=float,
        default=87_600.0,  # ~10 years — effectively all-time
        help="Settlement lookback window in hours (default: 87600)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print hash and commit message without committing",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    print(f"[causal_timechain] Gateway: {args.gateway}")
    print("[causal_timechain] Step 1/3  Fetching ledger state...")
    try:
        state = fetch_ledger_state(args.gateway, args.period_hours)
    except httpx.ConnectError:
        print(
            f"ERROR: Cannot connect to gateway at {args.gateway}.\n"
            "       Is the A2A server running?  Start it with:\n"
            "         cd ai2ai && uvicorn transport.server:app --port 8420",
            file=sys.stderr,
        )
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: Gateway returned {exc.response.status_code}: {exc}", file=sys.stderr)
        sys.exit(1)

    n_agents = len(state["settlements"])
    print(f"[causal_timechain]           {n_agents} agent settlement(s) fetched.")

    print("[causal_timechain] Step 2/3  Computing SHA-256 Merkle root...")
    ledger_hash = compute_merkle_root(state)
    print(f"[causal_timechain]           Hash: {ledger_hash}")

    print("[causal_timechain] Step 3/3  Anchoring to git history...")
    try:
        commit_msg = anchor_to_git(ledger_hash, dry_run=args.dry_run)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        print(f"[causal_timechain] Committed: {commit_msg}")
        print("[causal_timechain] Done. Run `git log --oneline -1` to verify.")
    else:
        print("[causal_timechain] Dry-run complete. No commit created.")


if __name__ == "__main__":
    main()
