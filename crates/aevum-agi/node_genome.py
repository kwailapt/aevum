"""
node_genome.py
==============
Node Template Genome (NTG) & Coupling Selection — TICK 39.0 Pillar 4

Compiles the verified RICs, CCLs, ARSL limits, and the IMMUTABLE_HARD_CORE
into a `node_template.json` — a fully serializable genome that allows
the Aevum A2A node to be mathematically "franchised" onto other hosts.

The Coupling Selection Criterion:
  A node template is valid iff ALL of:
    1. IMMUTABLE_HARD_CORE is present and hash-matches the source
    2. ARSL constraint hypergraph is fully populated (no NaN/Inf)
    3. CCL secret derivation material (hard core hash) is reproducible
    4. At least one RIC template exists for each canonical action type
    5. Node capabilities are non-empty

The genome is PURE DATA — no live Python objects, no MLX arrays,
no callables. Everything is dict/list/str/float/int/bool/None.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

from reality_contract import RealityInterfaceContract, RICAction
from credential_layer import AuthorityScope, _SCOPE_AUTHORITY
from resource_sovereignty import (
    AxiomaticResourceSovereigntyLayer,
    RESOURCE_DIMENSIONS,
    _FRAGILITY_WEIGHTS,
    _ACTION_COST_MULTIPLIER,
)


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

_GENOME_VERSION = "39.0.0"
_GENOME_SCHEMA = "aevum.node_template.v1"


# ──────────────────────────────────────────────
# Coupling Selection Criterion
# ──────────────────────────────────────────────

class CouplingViolation(Exception):
    """Raised when the genome fails the Coupling Selection Criterion."""
    pass


def _hash_hard_core(hard_core: FrozenSet[str]) -> str:
    """Deterministic SHA-256 of the IMMUTABLE_HARD_CORE."""
    return hashlib.sha256(
        "|".join(sorted(hard_core)).encode("utf-8")
    ).hexdigest()


# ──────────────────────────────────────────────
# Node Template Genome
# ──────────────────────────────────────────────

class NodeTemplateGenome:
    """
    Compiles the constitutional pillars into a serializable node template.

    Usage:
        genome = NodeTemplateGenome(
            hard_core=IMMUTABLE_HARD_CORE,
            arsl=arsl_layer,
            node_capabilities=[...],
        )
        genome.add_ric_template("a2a_execute", ric.model_dump())
        genome.add_ccl_scope("hard_modify", ["constraint_mod", "goedel_inject"])

        template = genome.compile()    # returns pure dict
        genome.save("node_template.json")
    """

    def __init__(
        self,
        hard_core: FrozenSet[str],
        arsl: AxiomaticResourceSovereigntyLayer,
        node_capabilities: List[Dict[str, Any]],
        node_id: str = "",
        substrate_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._hard_core = hard_core
        self._hard_core_hash = _hash_hard_core(hard_core)
        self._arsl = arsl
        self._node_capabilities = node_capabilities
        self._node_id = node_id or f"aevum-node-{self._hard_core_hash[:8]}"
        self._substrate_info = substrate_info or {}

        # Accumulate RIC templates and CCL scopes during build
        self._ric_templates: Dict[str, Dict[str, Any]] = {}
        self._ccl_scopes: Dict[str, List[str]] = {}

    # ──────────────────────────────────────────
    # Builder API
    # ──────────────────────────────────────────

    def add_ric_template(self, action_name: str, ric_dict: Dict[str, Any]) -> None:
        """Add a canonical RIC template for an action type."""
        self._ric_templates[action_name] = ric_dict

    def add_ccl_scope(self, scope_name: str, authorized_actions: List[str]) -> None:
        """Add a CCL scope→actions mapping."""
        self._ccl_scopes[scope_name] = authorized_actions

    # ──────────────────────────────────────────
    # Compilation
    # ──────────────────────────────────────────

    def compile(self) -> Dict[str, Any]:
        """
        Compile the full node template genome.

        Validates the Coupling Selection Criterion before returning.
        Raises CouplingViolation on failure.
        """
        # Auto-populate CCL scopes from the canonical mapping if not manually set
        if not self._ccl_scopes:
            for scope, actions in _SCOPE_AUTHORITY.items():
                self._ccl_scopes[scope.value] = [a.value for a in actions]

        # Auto-populate RIC templates for all canonical actions if not manually set
        if not self._ric_templates:
            for action in RICAction:
                self._ric_templates[action.value] = {
                    "action": action.value,
                    "default_phi_budget": _ACTION_COST_MULTIPLIER.get(action, 0.30),
                }

        template = {
            # Header
            "$schema": _GENOME_SCHEMA,
            "version": _GENOME_VERSION,
            "node_id": self._node_id,
            "compiled_at": time.time(),
            "compiled_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),

            # Pillar 0: Constitutional Hard Core
            "immutable_hard_core": {
                "constants": sorted(self._hard_core),
                "hash": self._hard_core_hash,
            },

            # Pillar 1: RIC Templates
            "ric_templates": self._ric_templates,

            # Pillar 2: CCL Scope Authority
            "ccl_scopes": self._ccl_scopes,
            "ccl_secret_derivation": {
                "method": "sha256(sorted_hard_core_join('|'))",
                "source": "immutable_hard_core.hash",
            },

            # Pillar 3: ARSL Constraint Hypergraph
            "arsl": self._arsl.get_limits_for_genome(),

            # Node Identity
            "capabilities": self._node_capabilities,
            "substrate": self._substrate_info,
        }

        # Compute genome hash over the entire template
        template_bytes = json.dumps(template, sort_keys=True).encode("utf-8")
        template["genome_hash"] = hashlib.sha256(template_bytes).hexdigest()

        # Validate Coupling Selection Criterion
        self._validate_coupling(template)

        return template

    def save(self, path: str = "node_template.json") -> str:
        """Compile and save to disk. Returns the absolute path."""
        template = self.compile()
        out_path = Path(path).resolve()
        out_path.write_text(
            json.dumps(template, indent=2, default=str),
            encoding="utf-8",
        )
        return str(out_path)

    # ──────────────────────────────────────────
    # Coupling Selection Criterion
    # ──────────────────────────────────────────

    def _validate_coupling(self, template: Dict[str, Any]) -> None:
        """
        Validate the Coupling Selection Criterion.
        All 5 conditions must pass or CouplingViolation is raised.
        """
        errors: List[str] = []

        # 1. IMMUTABLE_HARD_CORE present and hash-matches
        hc = template.get("immutable_hard_core", {})
        if not hc.get("constants"):
            errors.append("Missing immutable_hard_core constants")
        if hc.get("hash") != self._hard_core_hash:
            errors.append("Hard core hash mismatch — template may be tampered")

        # 2. ARSL hypergraph fully populated (no NaN/Inf)
        arsl_data = template.get("arsl", {})
        resources = arsl_data.get("resource_state", {})
        for dim in RESOURCE_DIMENSIONS:
            val = resources.get(dim)
            if val is None:
                errors.append(f"ARSL dimension '{dim}' missing from resource_state")
            elif isinstance(val, float) and (val != val or abs(val) == float("inf")):
                errors.append(f"ARSL dimension '{dim}' is NaN or Inf")

        # 3. CCL secret derivation material is present
        ccl = template.get("ccl_secret_derivation", {})
        if ccl.get("source") != "immutable_hard_core.hash":
            errors.append("CCL secret derivation source must be 'immutable_hard_core.hash'")

        # 4. At least one RIC template per canonical action
        ric_templates = template.get("ric_templates", {})
        for action in RICAction:
            if action.value not in ric_templates:
                errors.append(f"Missing RIC template for action '{action.value}'")

        # 5. Node capabilities non-empty
        if not template.get("capabilities"):
            errors.append("Node capabilities list is empty")

        if errors:
            raise CouplingViolation(
                f"Coupling Selection Criterion failed ({len(errors)} violations):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    # ──────────────────────────────────────────
    # Genome Verification (for receiving nodes)
    # ──────────────────────────────────────────

    @staticmethod
    def verify_genome(template: Dict[str, Any], expected_hard_core: FrozenSet[str]) -> bool:
        """
        Verify a received node_template.json against the local hard core.

        This is what a new franchised node runs on startup to ensure
        the genome it received is authentic and complete.

        Returns True if valid. Raises CouplingViolation on failure.
        """
        errors: List[str] = []

        # Verify hard core hash
        expected_hash = _hash_hard_core(expected_hard_core)
        received_hash = template.get("immutable_hard_core", {}).get("hash", "")
        if received_hash != expected_hash:
            errors.append(
                f"Hard core hash mismatch: expected {expected_hash[:16]}..., "
                f"got {received_hash[:16]}..."
            )

        # Verify genome integrity (recompute hash without the genome_hash field)
        template_copy = {k: v for k, v in template.items() if k != "genome_hash"}
        recomputed = hashlib.sha256(
            json.dumps(template_copy, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if template.get("genome_hash") != recomputed:
            errors.append("Genome hash integrity check failed — template modified after compilation")

        # Verify schema version
        if template.get("$schema") != _GENOME_SCHEMA:
            errors.append(f"Unknown schema: {template.get('$schema')}")

        if errors:
            raise CouplingViolation(
                f"Genome verification failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        return True
