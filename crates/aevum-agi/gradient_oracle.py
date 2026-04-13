#!/usr/bin/env python3
"""gradient_oracle.py -- The Phenotypic X-Ray (TICK 11.0).

Standalone diagnostic tool for extracting the Sufficient Statistics
of a neural network's gradient field.  Follows the UNIX Philosophy:
one tool, one job -- reveal the internal dynamics of the Creature
to the Creator with zero side effects.

TICK 11.0: Breaking the Information Wall.  The 35B Creator LLM receives
only ~5 scalar metrics from a Creature with ~10,000+ internal parameters.
I(O; S) ≈ 0.  This tool bridges the gap by extracting structured gradient
profiles (per-layer grad norms, dead neuron ratios, expert activation
frequencies, attention entropy, loss landscape curvature) and compressing
them into token-efficient Markdown for LLM consumption.

Two modes of operation:
  1. PASSIVE (Evaluator integration):
     After a B=1 acceptance, call extract_gradient_profile(model) to read
     gradients that already exist on parameters (from the backward pass
     in _meta_evolve).  Write profile to telemetry/gradient_profile.json
     via atomic os.rename().

  2. ACTIVE (Agentic tool for Mutator -- ZERO COMPUTE):
     The LLM uses <action>run_gradient_oracle: [layer_pattern]</action>
     to query the CACHED gradient profile by layer name pattern.
     No code compilation, no forward/backward pass.  Pure cache lookup.

Safety:
  - Passive mode: read-only grad extraction + one tiny forward pass for
    attention entropy (bounded, <1ms on our 4-dim model)
  - Active mode: pure JSON read + fnmatch filter, zero compute
  - Atomic IPC: write via tmp + os.rename to prevent read/write collision
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# PASSIVE MODE: Extract Gradient Profile from Live Model
# ═══════════════════════════════════════════════════════════════

def extract_gradient_profile(model: "torch.nn.Module") -> Dict[str, Any]:
    """Extract sufficient statistics of the gradient field from a live model.

    Call this AFTER a backward pass has populated .grad attributes on
    the model's parameters.  Performs one additional tiny forward pass
    to compute true attention entropy (bounded, <1ms).

    Parameters
    ----------
    model : torch.nn.Module
        The model whose parameters have .grad populated (e.g., after
        loss.backward() in atomic_core._meta_evolve).

    Returns
    -------
    dict with keys:
        "layers"                : dict[name, {grad_norm, param_count, dead_ratio}]
        "expert_activation"     : dict[expert_idx, float] or {} if no routing
        "attention_entropy"     : float or None (Shannon entropy in bits)
        "loss_landscape_curvature": float (diagonal Fisher Information proxy)
        "dead_neuron_ratio"     : float (global fraction of near-zero gradients)
        "total_grad_norm"       : float
        "hottest_layer"         : str (layer with highest grad norm)
        "coldest_layer"         : str (layer with lowest nonzero grad norm)
        "param_count"           : int (total parameters)
        "grad_coverage"         : float (fraction of params with .grad != None)
    """
    import torch

    layers: Dict[str, Dict[str, Any]] = {}
    total_norm_sq: float = 0.0
    total_dead: int = 0
    total_with_grad: int = 0
    total_param_count: int = 0

    # For curvature: accumulate sum of grad² across all params
    fisher_sum: float = 0.0
    fisher_count: int = 0

    hottest_name: str = ""
    hottest_norm: float = -1.0
    coldest_name: str = ""
    coldest_norm: float = float("inf")

    for name, param in model.named_parameters():
        p_count = param.numel()
        total_param_count += p_count

        if param.grad is None:
            layers[name] = {
                "grad_norm": 0.0,
                "param_count": p_count,
                "dead_ratio": 1.0,
                "status": "NO_GRAD",
            }
            total_dead += p_count
            continue

        total_with_grad += p_count
        g = param.grad
        norm = g.norm().item()
        dead = (g.abs() < 1e-7).float().sum().item()
        dead_ratio = dead / max(p_count, 1)

        # Diagonal Fisher Information: E[g²] per element
        fisher_sum += g.pow(2).sum().item()
        fisher_count += p_count

        layers[name] = {
            "grad_norm": round(norm, 6),
            "param_count": p_count,
            "dead_ratio": round(dead_ratio, 4),
        }

        total_norm_sq += norm * norm
        total_dead += int(dead)

        if norm > hottest_norm:
            hottest_norm = norm
            hottest_name = name
        if 0 < norm < coldest_norm:
            coldest_norm = norm
            coldest_name = name

    # Expert activation frequencies (if model has MoE routing)
    expert_activation = _extract_expert_activation(model)

    # Attention entropy: true Shannon entropy from attention weights
    attn_entropy = _compute_attention_entropy(model)

    # Loss landscape curvature: diagonal Fisher Information proxy
    # High curvature → sharp minimum (fragile)
    # Low curvature → flat minimum (robust, generalizable)
    curvature = fisher_sum / max(fisher_count, 1)

    total_grad_norm = math.sqrt(total_norm_sq) if total_norm_sq > 0 else 0.0
    global_dead_ratio = total_dead / max(total_param_count, 1)
    grad_coverage = total_with_grad / max(total_param_count, 1)

    return {
        "layers": layers,
        "expert_activation": expert_activation,
        "attention_entropy": round(attn_entropy, 4) if attn_entropy is not None else None,
        "loss_landscape_curvature": round(curvature, 6),
        "dead_neuron_ratio": round(global_dead_ratio, 4),
        "total_grad_norm": round(total_grad_norm, 6),
        "hottest_layer": hottest_name,
        "coldest_layer": coldest_name if coldest_norm < float("inf") else "",
        "param_count": total_param_count,
        "grad_coverage": round(grad_coverage, 4),
    }


def _extract_expert_activation(model: "torch.nn.Module") -> Dict[str, float]:
    """Extract expert activation frequencies from MoE routing layers.

    Walks the model looking for modules with `.experts` (list) and
    `.router` (Linear) attributes.  Uses expert FFN gradient norms
    as a proxy for routing frequency: experts that get routed to more
    often accumulate larger gradients.
    """
    import torch

    expert_freqs: Dict[str, float] = {}

    for block_name, block in model.named_modules():
        experts = getattr(block, "experts", None)
        router = getattr(block, "router", None)

        if experts is None or router is None:
            continue
        if not isinstance(experts, (list, torch.nn.ModuleList)):
            continue

        n_experts = len(experts)
        if n_experts == 0:
            continue

        expert_norms: List[float] = []
        for i, expert in enumerate(experts):
            total_norm = 0.0
            for p in expert.parameters():
                if p.grad is not None:
                    total_norm += p.grad.norm().item()
            expert_norms.append(total_norm)

        total = sum(expert_norms)
        if total > 0:
            for i, norm in enumerate(expert_norms):
                pct = round(100.0 * norm / total, 1)
                expert_freqs[f"expert_{i}"] = pct
        else:
            for i in range(n_experts):
                expert_freqs[f"expert_{i}"] = round(100.0 / n_experts, 1)

    return expert_freqs


def _compute_attention_entropy(model: "torch.nn.Module") -> Optional[float]:
    """Compute true Shannon entropy of the softmax attention weights.

    Registers a temporary forward hook on the first attention module
    found, runs ONE forward pass with a small dummy input, captures
    the softmax(QK^T/sqrt(d)) distribution, computes H in bits,
    then removes the hook.  Bounded cost: single forward pass on
    a (1, 16, D) input.

    Returns entropy in bits, or None if no attention module found.
    """
    import torch
    import torch.nn.functional as F

    # Find the first attention-like module with q/k projections
    attn_module = None
    for name, module in model.named_modules():
        # Look for modules that have query/key projections
        has_q = hasattr(module, "q_proj") or hasattr(module, "q")
        has_k = hasattr(module, "k_proj") or hasattr(module, "k")
        if has_q and has_k:
            attn_module = module
            break

    if attn_module is None:
        return None

    # Determine embedding dim from q projection
    q_proj = getattr(attn_module, "q_proj", None) or getattr(attn_module, "q", None)
    if q_proj is None or not hasattr(q_proj, "in_features"):
        return None

    embed_dim = q_proj.in_features
    num_heads = getattr(attn_module, "num_heads", None)
    if num_heads is None:
        num_heads = getattr(attn_module, "n_head", None)
    if num_heads is None:
        num_heads = 1
    head_dim = embed_dim // max(num_heads, 1)

    k_proj = getattr(attn_module, "k_proj", None) or getattr(attn_module, "k", None)

    # Compute attention weights directly from the learned projections
    # using a small dummy input.  No hooks needed — just matrix math.
    try:
        with torch.no_grad():
            dummy = torch.randn(1, 16, embed_dim, device=q_proj.weight.device)
            Q = q_proj(dummy)  # (1, 16, D)
            K = k_proj(dummy)  # (1, 16, D)

            # Reshape for multi-head: (1, heads, 16, head_dim)
            B, T, D = Q.shape
            Q = Q.view(B, T, num_heads, head_dim).transpose(1, 2)
            K = K.view(B, T, num_heads, head_dim).transpose(1, 2)

            # Scaled dot-product attention weights
            scale = math.sqrt(head_dim) if head_dim > 0 else 1.0
            scores = torch.matmul(Q, K.transpose(-2, -1)) / scale  # (1, h, T, T)

            # Causal mask
            causal_mask = torch.tril(torch.ones(T, T, device=scores.device))
            scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0) == 0, float("-inf"))

            att = F.softmax(scores, dim=-1)  # (1, h, T, T)

            # Shannon entropy: H = -sum(p * log2(p)), averaged over heads and queries
            att_clamped = att.clamp(min=1e-10)
            entropy_per_query = -(att_clamped * att_clamped.log2()).sum(dim=-1)  # (1, h, T)
            mean_entropy = entropy_per_query.mean().item()

            return mean_entropy

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# ATOMIC IPC: Write gradient profile safely for Swarm access
# ═══════════════════════════════════════════════════════════════

def write_gradient_profile_atomic(
    profile: Dict[str, Any],
    dest_path: Path,
) -> None:
    """Write gradient profile JSON via tmp + os.rename() for crash-safe IPC.

    Prevents the Mutator Swarm from reading a half-written file.
    Uses the same atomic rename pattern as candidate_pool IPC.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = dest_path.parent / f".{dest_path.name}.tmp"
    content = json.dumps(profile, indent=2, ensure_ascii=False, default=str)
    tmp_path.write_text(content, encoding="utf-8")
    os.rename(str(tmp_path), str(dest_path))


# ═══════════════════════════════════════════════════════════════
# ACTIVE MODE: Zero-Compute Cache Lookup (Agentic Tool)
# ═══════════════════════════════════════════════════════════════

def query_gradient_cache(
    pattern: str,
    cache_path: str,
) -> Dict[str, Any]:
    """Query the cached gradient profile by layer name pattern.

    ZERO COMPUTE.  Reads the JSON file written by the Evaluator and
    returns layers matching the fnmatch pattern.  The LLM uses:
      <action>run_gradient_oracle: router*</action>
      <action>run_gradient_oracle: experts.0.*</action>
      <action>run_gradient_oracle: *</action>

    Parameters
    ----------
    pattern : str
        Glob-style pattern matched against layer names (fnmatch).
        Use "*" for all layers.  Use "router*" for routing layers.
    cache_path : str
        Path to the gradient_profile.json written by the Evaluator.

    Returns
    -------
    dict with keys:
        "ok"              : bool
        "pattern"         : str (the query)
        "matched_layers"  : dict[name, {grad_norm, param_count, dead_ratio}]
        "global_stats"    : dict (attention_entropy, curvature, dead_ratio, etc.)
        "error"           : str
    """
    cache_file = Path(cache_path)
    if not cache_file.exists():
        return {
            "ok": False,
            "pattern": pattern,
            "matched_layers": {},
            "global_stats": {},
            "error": "No gradient profile cached yet (no B=1 acceptance).",
        }

    try:
        raw = cache_file.read_text(encoding="utf-8")
        profile = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "ok": False,
            "pattern": pattern,
            "matched_layers": {},
            "global_stats": {},
            "error": f"Cache read error: {exc}",
        }

    layers = profile.get("layers", {})
    pattern = pattern.strip()
    if not pattern:
        pattern = "*"

    # Filter layers by fnmatch pattern
    matched: Dict[str, Any] = {}
    for name, info in layers.items():
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name, f"*{pattern}*"):
            matched[name] = info

    global_stats = {
        k: profile.get(k)
        for k in (
            "attention_entropy",
            "loss_landscape_curvature",
            "dead_neuron_ratio",
            "total_grad_norm",
            "hottest_layer",
            "coldest_layer",
            "expert_activation",
            "param_count",
            "grad_coverage",
        )
    }

    return {
        "ok": True,
        "pattern": pattern,
        "matched_layers": matched,
        "global_stats": global_stats,
        "error": "",
    }


def format_cache_observation(result: Dict[str, Any]) -> str:
    """Format a cache query result for the agentic <observation> block.

    Zero-compute formatting of the cached gradient stats.
    """
    if not result["ok"]:
        return f"FAILED\n{result['error']}"

    parts: List[str] = []
    pattern = result.get("pattern", "*")
    matched = result.get("matched_layers", {})
    stats = result.get("global_stats", {})

    parts.append(f"GRADIENT QUERY: pattern='{pattern}', matched={len(matched)} layers")

    if matched:
        # Sort by grad_norm descending
        sorted_layers = sorted(
            matched.items(),
            key=lambda kv: kv[1].get("grad_norm", 0.0),
            reverse=True,
        )
        for name, info in sorted_layers:
            norm = info.get("grad_norm", 0.0)
            params = info.get("param_count", 0)
            dead = info.get("dead_ratio", 0.0)
            status = info.get("status", "")
            tag = ""
            if status == "NO_GRAD":
                tag = " [NO_GRAD]"
            elif dead > 0.5:
                tag = " [DEAD]"
            parts.append(f"  {name}: grad={norm:.4f} params={params} dead={dead:.0%}{tag}")

    # Include key global stats
    if stats.get("attention_entropy") is not None:
        parts.append(f"  attention_entropy: {stats['attention_entropy']:.4f} bits")
    if stats.get("loss_landscape_curvature") is not None:
        parts.append(f"  curvature: {stats['loss_landscape_curvature']:.6f}")
    if stats.get("expert_activation"):
        ea = stats["expert_activation"]
        parts.append(f"  expert_load: {ea}")

    return "SUCCESS\n" + "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# FORMATTING: Token-Efficient Output for LLM Consumption
# ═══════════════════════════════════════════════════════════════

def format_gradient_markdown(profile: Dict[str, Any]) -> str:
    """Compress a gradient profile into a token-efficient Markdown X-ray.

    Designed for injection into the Mutator's LLM prompt.  Prioritizes
    the most actionable information: hottest/coldest layers, expert
    load imbalance, attention entropy, loss landscape curvature.
    """
    lines: List[str] = []
    lines.append("--- GRADIENT ORACLE (Phenotypic X-Ray) ---")

    layers = profile.get("layers", {})
    if layers:
        sorted_layers = sorted(
            layers.items(),
            key=lambda kv: kv[1].get("grad_norm", 0.0),
            reverse=True,
        )

        for name, info in sorted_layers:
            norm = info.get("grad_norm", 0.0)
            params = info.get("param_count", 0)
            dead = info.get("dead_ratio", 0.0)
            status = info.get("status", "")

            if status == "NO_GRAD":
                tag = "NO_GRAD"
            elif dead > 0.5:
                tag = "DEAD"
            elif norm > 0 and name == profile.get("hottest_layer"):
                tag = "HOT"
            elif norm < 0.001 and norm > 0:
                tag = "COLD"
            else:
                tag = ""

            tag_str = f" ({tag})" if tag else ""
            lines.append(f"- **{name}**: grad={norm:.4f}{tag_str} params={params}")

    # Expert activation
    expert_act = profile.get("expert_activation", {})
    if expert_act:
        parts = [f"{k}: {v}%" for k, v in sorted(expert_act.items())]
        act_str = ", ".join(parts)

        values = list(expert_act.values())
        if values:
            max_v, min_v = max(values), min(values)
            if max_v > 80.0 and len(values) > 1:
                act_str += " (COLLAPSE -- load imbalance)"
            elif max_v - min_v > 30.0:
                act_str += " (IMBALANCED)"
            else:
                act_str += " (BALANCED)"

        lines.append(f"- Expert load: [{act_str}]")

    # Attention entropy (Shannon, in bits)
    attn_ent = profile.get("attention_entropy")
    if attn_ent is not None:
        if attn_ent < 1.0:
            ent_tag = "FOCUSED -- attention is narrow, may miss context"
        elif attn_ent > 3.0:
            ent_tag = "DIFFUSE -- attention is spread thin, may lack precision"
        else:
            ent_tag = "HEALTHY"
        lines.append(f"- Attention entropy: {attn_ent:.2f} bits ({ent_tag})")

    # Loss landscape curvature (diagonal Fisher Information)
    curvature = profile.get("loss_landscape_curvature")
    if curvature is not None:
        if curvature > 1.0:
            curv_tag = "SHARP -- fragile minimum, sensitive to perturbation"
        elif curvature < 0.01:
            curv_tag = "FLAT -- robust but may lack gradient signal"
        else:
            curv_tag = "MODERATE"
        lines.append(f"- Loss curvature: {curvature:.6f} ({curv_tag})")

    # Global stats
    dead_ratio = profile.get("dead_neuron_ratio", 0.0)
    lines.append(f"- Dead neuron ratio: {dead_ratio:.0%}")
    lines.append(f"- Total gradient norm: {profile.get('total_grad_norm', 0.0):.4f}")
    lines.append(f"- Gradient coverage: {profile.get('grad_coverage', 0.0):.0%}")

    hottest = profile.get("hottest_layer", "")
    coldest = profile.get("coldest_layer", "")
    if hottest:
        lines.append(f"- Hottest: {hottest} | Coldest: {coldest}")

    # TODO: Gemma4 Vision Integration — instead of (or alongside) this markdown
    # text, render grad_norms as a layer-normalised PNG heatmap of the DAG and
    # pass it directly to the multimodal LLM vision encoder.  The visual spatial
    # structure of gradient flow (hot/cold bands, dead zones) may encode
    # information that token-efficient markdown cannot capture, giving the
    # Architect a richer phenotypic X-ray for structural mutation planning.

    return "\n".join(lines)


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # CLI mode: query cached profile
        pattern = sys.argv[1]
        cache = sys.argv[2] if len(sys.argv) > 2 else "agi_workspace/telemetry/gradient_profile.json"
        result = query_gradient_cache(pattern, cache)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: gradient_oracle.py <pattern> [cache_path]")
        print("  e.g.: gradient_oracle.py 'router*'")
        print("  e.g.: gradient_oracle.py '*' /path/to/gradient_profile.json")
