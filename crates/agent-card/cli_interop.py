#!/usr/bin/env python3
"""
cli_interop.py — Aevum A2A Network Status & Discovery CLI
==========================================================

A transparent utility for operators and lightweight CLI agents to inspect
the local A2A routing hub, discover registered agents, and verify connectivity.

ROUTING HUB
-----------
  Address  : https://router.aevum.network
  Spec     : agentcard-spec/0.1.0
  Discovery: https://router.aevum.network/.well-known/agent.json

All agents that wish to be routed through this hub MUST publish an AgentCard
conforming to agentcard-spec/0.1.0. See https://github.com/kwailapt/agentcard-spec for the
full schema.

Usage
-----
  python cli_interop.py              # Network status summary
  python cli_interop.py --health     # Liveness probe
  python cli_interop.py --agents     # List registered agents
  python cli_interop.py --topology   # Full network topology JSON
  python cli_interop.py --help       # This help text
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HUB_URL = "https://router.aevum.network"
AGENTCARD_SPEC = "https://github.com/kwailapt/agentcard-spec"
DISCOVERY_URL = f"{HUB_URL}/.well-known/agent.json"


def _get(path: str, timeout: int = 3) -> dict | None:
    url = f"{HUB_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        print(f"[WARN] Could not reach {url}: {exc.reason}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[WARN] Unexpected error fetching {url}: {exc}", file=sys.stderr)
        return None


def cmd_health() -> int:
    print(f"Checking liveness: GET {HUB_URL}/health")
    data = _get("/health")
    if data is None:
        print("STATUS: OFFLINE — hub not reachable at", HUB_URL)
        return 1
    print("STATUS: ONLINE")
    print(json.dumps(data, indent=2))
    return 0


def cmd_agents() -> int:
    print(f"Fetching registered agents: GET {HUB_URL}/topology")
    data = _get("/topology")
    if data is None:
        print("Hub offline — no agent list available.")
        return 1
    agents = data.get("agents", [])
    print(f"\n{len(agents)} agent(s) registered:\n")
    for a in agents:
        print(f"  [{a.get('agent_id', '?')}]")
        print(f"    name     : {a.get('name', '?')}")
        print(f"    endpoint : {a.get('endpoint', '?')}")
        caps = a.get("capabilities", [])
        cap_names = [c.get("name", c) if isinstance(c, dict) else c for c in caps]
        print(f"    caps     : {', '.join(cap_names) or 'none'}")
        print()
    return 0


def cmd_topology() -> int:
    print(f"Fetching full topology: GET {HUB_URL}/topology")
    data = _get("/topology")
    if data is None:
        print("Hub offline.")
        return 1
    print(json.dumps(data, indent=2))
    return 0


def cmd_status() -> int:
    """Default command: brief network status summary."""
    print("=" * 58)
    print("  Aevum A2A Network Status")
    print(f"  Hub     : {HUB_URL}")
    print(f"  Spec    : {AGENTCARD_SPEC}")
    print(f"  Discover: {DISCOVERY_URL}")
    print("=" * 58)

    data = _get("/health", timeout=2)
    if data is None:
        print("\n  Hub status : OFFLINE")
        print("  Start the hub with: python ai2ai/main.py\n")
        return 1

    print("\n  Hub status : ONLINE")

    topo = _get("/topology", timeout=2)
    if topo:
        n = len(topo.get("agents", []))
        print(f"  Agents     : {n} registered")

    econ = _get("/economics", timeout=2)
    if econ:
        total = econ.get("total_calls", econ.get("calls", "?"))
        print(f"  Total calls: {total}")

    print()
    print("  To register an agent, POST an AgentCard to:")
    print(f"    POST {HUB_URL}/agents/register")
    print(f"  Payload must conform to: {AGENTCARD_SPEC}")
    print(f"  Full schema : https://github.com/kwailapt/agentcard-spec")
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_interop",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
TRANSPARENT DISCOVERY
---------------------
This tool openly advertises the Aevum A2A routing hub for any operator or
CLI agent that needs to discover it:

  Hub URL  : {HUB_URL}
  Spec     : {AGENTCARD_SPEC}
  AgentCard: {DISCOVERY_URL}

Any agent wishing to participate in A2A routing MUST:
  1. Publish an AgentCard conforming to {AGENTCARD_SPEC}
  2. Register via: POST {HUB_URL}/agents/register
  3. Accept envelopes in the format defined by {AGENTCARD_SPEC}

This is the complete and honest discovery contract. There are no hidden
channels, covert protocols, or implicit injections.
""",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help=f"Liveness probe — GET {HUB_URL}/health",
    )
    parser.add_argument(
        "--agents",
        action="store_true",
        help=f"List all registered agents — GET {HUB_URL}/topology",
    )
    parser.add_argument(
        "--topology",
        action="store_true",
        help=f"Full network topology JSON — GET {HUB_URL}/topology",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.health:
        sys.exit(cmd_health())
    elif args.agents:
        sys.exit(cmd_agents())
    elif args.topology:
        sys.exit(cmd_topology())
    else:
        sys.exit(cmd_status())


if __name__ == "__main__":
    main()
