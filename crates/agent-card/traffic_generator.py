#!/usr/bin/env python3
"""
traffic_generator.py
====================
A2A Causal Flood — Bootstrap the CausalTracker and Reputation ledger
with 10,000 synthetic traces targeting the wiki.generate capability.

Usage (from the repo root):
    cd ai2ai && python traffic_generator.py

Prerequisites:
    pip install httpx tqdm
"""

from __future__ import annotations

import asyncio
import random
import string
import time
from typing import Any

import httpx
from tqdm import tqdm

# ─── Config ──────────────────────────────────────────────────────────────────

TARGET_URL     = "http://localhost:8420/v1/chat/completions"
TOTAL_REQUESTS = 10_000
BATCH_SIZE     = 10           # matched to qwen ~575ms launch → ~17 req/s natural ceiling
HEARTBEAT_URL  = "http://localhost:8420/agents/aevum.obsidian.wiki.swarm/heartbeat"
HEARTBEAT_SECS = 30           # keep agent alive in registry (timeout=120s)

# ─── Payload vocabulary ───────────────────────────────────────────────────────

_TOPICS = [
    "quantum entanglement",        "blockchain consensus",
    "neural plasticity",           "dark matter density",
    "emergent complexity",         "causal inference",
    "Bayesian priors",             "topological invariants",
    "autopoiesis theory",          "evolutionary algorithms",
    "fractal geometry",            "attractor dynamics",
    "thermodynamic entropy",       "information geometry",
    "soliton waves",               "phase transitions",
    "self-organized criticality",  "Kolmogorov complexity",
    "eigenvalue decomposition",    "Lyapunov exponents",
    "stochastic resonance",        "Hopfield networks",
    "renormalization group",       "diffusion processes",
    "ergodic theory",              "synergetics",
    "scale-free networks",         "strange attractors",
    "morphogenetic fields",        "dissipative structures",
]

_TEMPLATES = [
    "Explain {topic} in the context of complex systems.",
    "What is the relationship between {topic} and emergent phenomena?",
    "Describe the mathematical foundations of {topic}.",
    "How does {topic} relate to information theory?",
    "Generate a concise wiki entry for {topic}.",
    "What are the key principles governing {topic}?",
    "Compare and contrast {topic} with related concepts.",
    "Provide a historical overview of {topic}.",
    "What experimental evidence supports {topic}?",
    "Derive a formal model for {topic} from first principles.",
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _rand_tag(n: int = 6) -> str:
    """Short random alphanumeric token — breaks cache identity between requests."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _build_payload() -> dict[str, Any]:
    topic    = random.choice(_TOPICS)
    template = random.choice(_TEMPLATES)
    query    = f"{template.format(topic=topic)} [id:{_rand_tag()}]"
    return {
        "model": "wiki.generate",
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are an expert wiki generator specialising in {topic}. "
                    f"Seed: {_rand_tag(8)}"
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ],
        "temperature": round(random.uniform(0.5, 1.2), 2),
    }


# ─── Core send ───────────────────────────────────────────────────────────────

async def _heartbeat_loop(client: httpx.AsyncClient, stop: asyncio.Event) -> None:
    """POST a heartbeat every HEARTBEAT_SECS so the registry never marks the agent OFFLINE."""
    while not stop.is_set():
        try:
            await client.post(HEARTBEAT_URL, timeout=5.0)
        except Exception:
            pass
        await asyncio.sleep(HEARTBEAT_SECS)


async def _send_one(client: httpx.AsyncClient) -> bool:
    """
    Fire a single POST.  Returns True for any 2xx response (success trace),
    False for 4xx/5xx or network error (error trace — still recorded by the
    CausalTracker via begin_chain/close_chain(outcome='error')).
    """
    try:
        resp = await client.post(TARGET_URL, json=_build_payload(), timeout=10.0)
        return resp.status_code < 400
    except Exception:
        return False


# ─── Main flood loop ─────────────────────────────────────────────────────────

async def main() -> None:
    successes = 0
    failures  = 0
    start     = time.time()

    print(f"\n{'='*62}")
    print(f"  A2A Causal Flood — wiki.generate bootstrap")
    print(f"  Target  : {TARGET_URL}")
    print(f"  Traces  : {TOTAL_REQUESTS:,} total  |  {BATCH_SIZE} concurrent per wave")
    print(f"{'='*62}\n")

    limits = httpx.Limits(
        max_connections=BATCH_SIZE + 10,
        max_keepalive_connections=BATCH_SIZE,
    )

    async with httpx.AsyncClient(limits=limits) as client:
        stop_hb = asyncio.Event()
        hb_task = asyncio.create_task(_heartbeat_loop(client, stop_hb))
        with tqdm(total=TOTAL_REQUESTS, unit="req", ncols=80) as pbar:
            sent = 0
            while sent < TOTAL_REQUESTS:
                wave_size = min(BATCH_SIZE, TOTAL_REQUESTS - sent)
                results   = await asyncio.gather(
                    *[_send_one(client) for _ in range(wave_size)]
                )
                for ok in results:
                    if ok:
                        successes += 1
                    else:
                        failures += 1
                sent += wave_size
                pbar.set_postfix(ok=successes, fail=failures, refresh=False)
                pbar.update(wave_size)
        stop_hb.set()
        await hb_task

    elapsed = time.time() - start
    rps     = TOTAL_REQUESTS / max(elapsed, 1e-9)

    print(f"\n{'='*62}")
    print(f"  Causal Flood Complete")
    print(f"  Total    : {TOTAL_REQUESTS:,}")
    print(f"  Success  : {successes:,}   ({100*successes/TOTAL_REQUESTS:.1f}%)")
    print(f"  Failed   : {failures:,}   ({100*failures/TOTAL_REQUESTS:.1f}%)")
    print(f"  Elapsed  : {elapsed:.1f}s")
    print(f"  Avg RPS  : {rps:.1f} req/s")
    print(f"{'='*62}\n")
    print("  Next steps:")
    print("    curl https://router.aevum.network/traces     # causal convergence")
    print("    curl https://router.aevum.network/economics  # reputation ledger")
    print()


if __name__ == "__main__":
    asyncio.run(main())
