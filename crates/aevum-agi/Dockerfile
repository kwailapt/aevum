# ──────────────────────────────────────────────────────────────────────────────
# A2A Protocol Layer — Dockerfile
# Packages the Aevum causal-bridge router (port 8420) for Linux deployment.
#
# SUBSTRATE NOTE:
#   autopoietic_core.py depends on Apple MLX (Apple Silicon / macOS only) and
#   cannot run in a standard Linux container.  The router itself (FastAPI +
#   uvicorn) is fully portable.  Run autopoietic_core.py natively on macOS and
#   connect it to the containerised router via http://host.docker.internal:8420.
#
# causal_timechain.py is included and can be invoked as a one-shot command
# via `docker compose run timechain` (see docker-compose.yml).
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# git is required by causal_timechain.py for --allow-empty anchor commits
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy governance modules (imported from project root by server.py) ─────────
COPY reality_contract.py     ./
COPY credential_layer.py     ./
COPY resource_sovereignty.py ./
COPY rule_ir.py              ./
COPY node_genome.py          ./
COPY constitution.py         ./

# ── Copy the A2A router package ───────────────────────────────────────────────
COPY ai2ai/ ./ai2ai/

# ── Copy the causal timechain utility ────────────────────────────────────────
COPY causal_timechain.py ./

# ── Python path: allow imports from /app root (governance modules) ───────────
# server.py imports reality_contract, credential_layer, resource_sovereignty,
# and node_genome directly.  WORKDIR is /app/ai2ai, so without this override
# Python would only search /app/ai2ai and the stdlib — not /app.
ENV PYTHONPATH=/app

# ── Install Python dependencies ───────────────────────────────────────────────
# mlx is NOT listed here — it is macOS/Apple Silicon only and will fail on
# Linux.  The economics engine has a pure-Python fallback when mlx is absent.
RUN pip install --no-cache-dir \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "pydantic>=2.5.0" \
    "httpx>=0.25.0" \
    "numpy>=1.26.0"

# ── Runtime configuration ─────────────────────────────────────────────────────
EXPOSE 8420

WORKDIR /app/ai2ai

# Default command: start the A2A router
CMD ["python", "main.py"]
