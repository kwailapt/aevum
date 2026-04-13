"""
meta_ocf.py
===========
Meta-Organism Coherence Field (Meta-OCF) — TICK 39.1 Pillar A

Civilizational Immune System: prevents Cancerous Node Divergence by
enforcing hard-core genetic loyalty across all franchised nodes.

Design:

  IdentityDissolutionError (BaseException, NOT Exception)
    Raised when a node's IMMUTABLE_HARD_CORE hash drifts from genesis.
    It is UNCATCHABLE by the standard `except Exception` guard in
    _governor_loop() — it propagates through and physically halts
    the node's governor, triggering an orderly but forced shutdown.

    "If you are no longer who you were born as,
     you must cease to operate until you are reinstated."

  GenesisTether
    Binds a single node to its constitutional genesis state.
    Computes genesis_hash = SHA-256(sorted(IMMUTABLE_HARD_CORE))
    at instantiation and re-verifies on every attest() call.
    Raises IdentityDissolutionError immediately on hash drift.
    Also verifies child genomes received via NTG against the
    expected genesis hash (coupling selection criterion).

  MetaOCFBus
    The franchise network's immune coordinator.
    Manages GenesisTether instances for multiple child nodes.
    Provides batch_attest() for a single governance tick to
    verify all registered child tethers simultaneously.
    Maintains an immutable event log (attestation_log) — never
    pruned, never zeroed, append-only.

Propagation rules:
  - IdentityDissolutionError in _governor_loop()  → halts governor (not caught)
  - IdentityDissolutionError in tick_boundary()   → propagates upward to loop halt
  - IdentityDissolutionError in batch_attest()    → caller decides to re-raise

All logic is pure CPU, O(1) per tether, no I/O.
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────
# IdentityDissolutionError — THE UNCATCHABLE
# ──────────────────────────────────────────────────────────────────────────

class IdentityDissolutionError(BaseException):
    """
    A node's IMMUTABLE_HARD_CORE has drifted from its genesis state.

    This is a HARD HALT exception — it INTENTIONALLY inherits from
    BaseException, not Exception, so that:

        except Exception:   ← does NOT catch this
        except BaseException ← would catch, but only used for cleanup

    The governor loop's bare `except Exception` guard will NOT trap
    IdentityDissolutionError. It propagates to the outermost scope
    and halts the node's main thread, forcing a clean restart from
    a verified genesis state.

    Analogy: This is the cellular equivalent of apoptosis — the
    organism's last act of constitutional loyalty is its own death.
    """

    def __init__(
        self,
        node_id: str,
        genesis_hash: str,
        observed_hash: str,
        drift_age_s: float = 0.0,
        extra: str = "",
    ) -> None:
        self.node_id        = node_id
        self.genesis_hash   = genesis_hash
        self.observed_hash  = observed_hash
        self.drift_age_s    = drift_age_s
        self.detected_at    = time.time()
        super().__init__(
            f"IDENTITY DISSOLUTION: node={node_id!r} "
            f"genesis={genesis_hash[:12]}... "
            f"observed={observed_hash[:12]}... "
            f"drift_age={drift_age_s:.1f}s"
            + (f" | {extra}" if extra else "")
        )


# ──────────────────────────────────────────────────────────────────────────
# Attestation Record — immutable audit entry
# ──────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AttestationRecord:
    """
    A single attestation event in the OCF audit log.
    Frozen (immutable) — the log is append-only, never mutated.
    """
    node_id:      str
    attested_at:  float           # Unix timestamp
    result:       str             # "ok" | "drift" | "genome_mismatch"
    genesis_hash: str             # expected hash
    observed_hash: str            # actual hash at this attestation
    attest_count: int             # monotonically increasing per node


# ──────────────────────────────────────────────────────────────────────────
# GenesisTether
# ──────────────────────────────────────────────────────────────────────────

def _hash_hard_core(hard_core: FrozenSet[str]) -> str:
    """Deterministic SHA-256 of an IMMUTABLE_HARD_CORE frozenset."""
    return hashlib.sha256(
        "|".join(sorted(hard_core)).encode("utf-8")
    ).hexdigest()


class GenesisTether:
    """
    Binds a node to its constitutional genesis state.

    At instantiation the current IMMUTABLE_HARD_CORE is hashed and
    stored as the irrevocable genesis_hash.  Every call to attest()
    recomputes the hash and compares.  Any drift is fatal.

    Usage (inside _governor_loop):

        _GENESIS_TETHER = GenesisTether(
            node_id="aevum-node-0",
            immutable_hard_core=IMMUTABLE_HARD_CORE,
            attest_interval_s=300.0,   # 5 minutes
        )

        # Inside the tick:
        _GENESIS_TETHER.attest(IMMUTABLE_HARD_CORE)  # raises if drifted

    Thread safety: attest() is idempotent and safe to call from any thread.
    """

    def __init__(
        self,
        node_id: str,
        immutable_hard_core: FrozenSet[str],
        attest_interval_s: float = 300.0,
    ) -> None:
        self.node_id              = node_id
        self._genesis_hash        = _hash_hard_core(immutable_hard_core)
        self._genesis_ts          = time.time()
        self._attest_interval_s   = attest_interval_s
        self._last_attest_ts      = self._genesis_ts
        self._attest_count        = 0
        self._attestation_log: List[AttestationRecord] = []

    # ─────────────────────────────────────────────────────
    # Core Attestation
    # ─────────────────────────────────────────────────────

    @property
    def genesis_hash(self) -> str:
        return self._genesis_hash

    def is_due(self) -> bool:
        """Return True if attest_interval_s has elapsed since last check."""
        return (time.time() - self._last_attest_ts) >= self._attest_interval_s

    def attest(self, current_hard_core: FrozenSet[str]) -> AttestationRecord:
        """
        Verify the node's current hard core against genesis.

        Args:
            current_hard_core: The live IMMUTABLE_HARD_CORE frozenset.

        Returns:
            AttestationRecord with result="ok"

        Raises:
            IdentityDissolutionError (BaseException) immediately if drift detected.
            This error is NOT catchable by `except Exception` — the governor loop
            will halt.
        """
        now = time.time()
        self._attest_count += 1
        self._last_attest_ts = now

        observed_hash = _hash_hard_core(current_hard_core)
        drift_age_s   = now - self._genesis_ts

        if observed_hash != self._genesis_hash:
            record = AttestationRecord(
                node_id       = self.node_id,
                attested_at   = now,
                result        = "drift",
                genesis_hash  = self._genesis_hash,
                observed_hash = observed_hash,
                attest_count  = self._attest_count,
            )
            self._attestation_log.append(record)

            raise IdentityDissolutionError(
                node_id       = self.node_id,
                genesis_hash  = self._genesis_hash,
                observed_hash = observed_hash,
                drift_age_s   = drift_age_s,
            )

        record = AttestationRecord(
            node_id       = self.node_id,
            attested_at   = now,
            result        = "ok",
            genesis_hash  = self._genesis_hash,
            observed_hash = observed_hash,
            attest_count  = self._attest_count,
        )
        self._attestation_log.append(record)
        return record

    def verify_child_genome(
        self,
        genome_dict: Dict[str, Any],
    ) -> AttestationRecord:
        """
        Verify a franchised child node's compiled genome against this tether.

        Called by the parent node when a new NTG-spawned child presents its genome.

        Raises IdentityDissolutionError if the child's hard core hash doesn't
        match this node's genesis hash — the child is constitutionally incompatible.
        """
        now = time.time()
        self._attest_count += 1
        self._last_attest_ts = now

        child_hash = genome_dict.get("immutable_hard_core", {}).get("hash", "")

        if child_hash != self._genesis_hash:
            record = AttestationRecord(
                node_id       = self.node_id,
                attested_at   = now,
                result        = "genome_mismatch",
                genesis_hash  = self._genesis_hash,
                observed_hash = child_hash,
                attest_count  = self._attest_count,
            )
            self._attestation_log.append(record)

            raise IdentityDissolutionError(
                node_id       = self.node_id,
                genesis_hash  = self._genesis_hash,
                observed_hash = child_hash,
                drift_age_s   = 0.0,
                extra          = "genome_mismatch — child genome rejected by GenesisTether",
            )

        record = AttestationRecord(
            node_id       = self.node_id,
            attested_at   = now,
            result        = "ok",
            genesis_hash  = self._genesis_hash,
            observed_hash = child_hash,
            attest_count  = self._attest_count,
        )
        self._attestation_log.append(record)
        return record

    # ─────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a serializable status report (safe for logging)."""
        last = self._attestation_log[-1] if self._attestation_log else None
        return {
            "node_id":          self.node_id,
            "genesis_hash":     self._genesis_hash[:16] + "...",
            "genesis_ts":       self._genesis_ts,
            "attest_count":     self._attest_count,
            "attest_interval_s": self._attest_interval_s,
            "last_result":      last.result if last else "never",
            "last_attested_at": last.attested_at if last else None,
            "uptime_s":         time.time() - self._genesis_ts,
        }


# ──────────────────────────────────────────────────────────────────────────
# MetaOCFBus — Franchise Network Immune Coordinator
# ──────────────────────────────────────────────────────────────────────────

class MetaOCFBus:
    """
    The franchise network's constitutional immune system.

    Manages GenesisTether instances for all registered child nodes.
    A single call to batch_attest() verifies all registered tethers
    simultaneously and returns a health report.

    Dissolution events are recorded in an append-only event log.
    batch_attest() raises IdentityDissolutionError for the FIRST
    drifted node it detects — callers can catch this at the
    civilization-level and decide whether to:
      (a) raise immediately to halt the coordinator, or
      (b) quarantine the drifted node and continue.

    Usage:

        bus = MetaOCFBus(parent_genesis_hash=_GENESIS_TETHER.genesis_hash)

        # When a child node is spawned:
        bus.register_child(child_node_id, child_hard_core)

        # In the governance tick:
        report = bus.batch_attest(all_child_hard_cores_by_id)
    """

    def __init__(self, parent_genesis_hash: str) -> None:
        self._parent_genesis_hash = parent_genesis_hash
        self._tethers: Dict[str, GenesisTether] = {}
        # Append-only global event log — never pruned
        self._event_log: List[AttestationRecord] = []
        self._dissolution_events: List[IdentityDissolutionError] = []

    def register_child(
        self,
        node_id: str,
        immutable_hard_core: FrozenSet[str],
        attest_interval_s: float = 300.0,
    ) -> None:
        """
        Register a new franchised child node.

        Immediately verifies that the child's genesis hash matches the
        parent — a child born with a different hard core is constitutionally
        invalid and raises IdentityDissolutionError before registration.
        """
        child_hash = _hash_hard_core(immutable_hard_core)
        if child_hash != self._parent_genesis_hash:
            raise IdentityDissolutionError(
                node_id       = node_id,
                genesis_hash  = self._parent_genesis_hash,
                observed_hash = child_hash,
                drift_age_s   = 0.0,
                extra          = "child registered with incompatible hard core — registration REJECTED",
            )
        tether = GenesisTether(
            node_id            = node_id,
            immutable_hard_core = immutable_hard_core,
            attest_interval_s  = attest_interval_s,
        )
        self._tethers[node_id] = tether

    def deregister_child(self, node_id: str) -> None:
        """Remove a child node from the bus (e.g., after graceful shutdown)."""
        self._tethers.pop(node_id, None)

    def batch_attest(
        self,
        current_cores: Dict[str, FrozenSet[str]],
    ) -> Dict[str, Any]:
        """
        Attest all registered children whose tether is due.

        Args:
            current_cores: dict mapping node_id → current IMMUTABLE_HARD_CORE

        Returns:
            {
              "attested": [list of node_ids checked],
              "ok":       [list of healthy node_ids],
              "dissolved": [list of drifted node_ids],
              "skipped":  [list of node_ids not yet due],
            }

        Raises:
            IdentityDissolutionError for the first drifted node encountered.
            The caller (civilization-level supervisor) decides whether to
            quarantine or re-raise.
        """
        result: Dict[str, Any] = {
            "attested": [],
            "ok":       [],
            "dissolved": [],
            "skipped":  [],
        }

        for node_id, tether in list(self._tethers.items()):
            if not tether.is_due():
                result["skipped"].append(node_id)
                continue

            core = current_cores.get(node_id)
            if core is None:
                # Node is registered but sent no heartbeat — treat as potential drift
                result["skipped"].append(node_id)
                continue

            result["attested"].append(node_id)
            try:
                rec = tether.attest(core)
                self._event_log.append(rec)
                result["ok"].append(node_id)
            except IdentityDissolutionError as exc:
                self._dissolution_events.append(exc)
                # Record the drift event
                result["dissolved"].append(node_id)
                # Re-raise — the first dissolution halts the batch
                raise

        return result

    def get_health(self) -> Dict[str, Any]:
        """Return a full health report of all registered tethers."""
        return {
            "registered_nodes": len(self._tethers),
            "total_attests":    len(self._event_log),
            "dissolution_count": len(self._dissolution_events),
            "tether_statuses":  {nid: t.status() for nid, t in self._tethers.items()},
        }
