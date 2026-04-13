"""
credential_layer.py
===================
Credentialed Constraint Layer (CCL) — TICK 39.0 Pillar 2

Rule-IR matrices cannot be modified blindly. Every self-modification
or high-stakes RIC execution MUST pass through this cryptographic gate.

Gate function:
  Verify(delta_R, credential) → {0, 1}

The CCL uses HMAC-SHA256 over the credential's scope + budget + timestamp
to ensure that only holders of the system secret can authorize modifications.
The secret is derived from the IMMUTABLE_HARD_CORE hash at boot time —
no external key management required.

All verification is pure CPU (HMAC-SHA256). No I/O, no network, no disk.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional

from reality_contract import RealityInterfaceContract, RICAction


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

# Actions that require credential verification (high-stakes)
_CREDENTIALED_ACTIONS: FrozenSet[RICAction] = frozenset({
    RICAction.CONSTRAINT_MOD,
    RICAction.FISSION,
    RICAction.META_EVOLVE,
    RICAction.GOEDEL_INJECT,
    RICAction.NODE_REPLICATE,
})

# Default credential TTL: 5 minutes
_DEFAULT_TTL_S: float = 300.0

# Maximum Φ budget any single credential can authorize
_MAX_PHI_BUDGET: float = 10.0


# ──────────────────────────────────────────────
# Authority Scope
# ──────────────────────────────────────────────

class AuthorityScope(str, Enum):
    """Graduated authority levels for credential issuance."""
    READ_ONLY       = "read_only"       # observe state, no mutation
    SOFT_MODIFY     = "soft_modify"     # EvolvableSoftShell parameters only
    HARD_MODIFY     = "hard_modify"     # ConstraintMatrix gradient updates
    FISSION         = "fission"         # lineage fission authority
    META_EVOLVE     = "meta_evolve"     # LLM-in-the-loop meta-evolution
    FRANCHISE       = "franchise"       # node replication authority
    SOVEREIGN       = "sovereign"       # unrestricted (system bootstrap only)


# Mapping: which scopes authorize which RIC actions
_SCOPE_AUTHORITY: Dict[AuthorityScope, FrozenSet[RICAction]] = {
    AuthorityScope.READ_ONLY: frozenset({
        RICAction.A2A_ROUTE,
    }),
    AuthorityScope.SOFT_MODIFY: frozenset({
        RICAction.A2A_ROUTE,
        RICAction.A2A_EXECUTE,
        RICAction.VALUE_SIGNAL,
    }),
    AuthorityScope.HARD_MODIFY: frozenset({
        RICAction.CONSTRAINT_MOD,
        RICAction.GOEDEL_INJECT,
    }),
    AuthorityScope.FISSION: frozenset({
        RICAction.FISSION,
    }),
    AuthorityScope.META_EVOLVE: frozenset({
        RICAction.META_EVOLVE,
        RICAction.API_CALL,
    }),
    AuthorityScope.FRANCHISE: frozenset({
        RICAction.NODE_REPLICATE,
    }),
    AuthorityScope.SOVEREIGN: frozenset(RICAction),  # all actions
}


# ──────────────────────────────────────────────
# Credential
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class ConstraintCredential:
    """
    A time-bound, scope-limited authorization token.

    Immutable after creation (frozen dataclass).
    The signature is computed at issuance and verified at the gate.
    """
    credential_id: str
    scope: AuthorityScope
    authority: FrozenSet[str]   # specific sub-actions (e.g. {"apply_gradient", "modify_constraint"})
    phi_budget: float           # max Φ cost this credential authorizes
    issued_at: float
    expires_at: float
    issuer: str                 # who created this credential
    signature: str              # HMAC-SHA256 over (credential_id, scope, budget, issued_at, expires_at)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def covers_action(self, ric_action: RICAction) -> bool:
        """Check if this credential's scope authorizes the given RIC action."""
        allowed = _SCOPE_AUTHORITY.get(self.scope, frozenset())
        return ric_action in allowed

    def covers_phi_budget(self, requested: float) -> bool:
        return requested <= self.phi_budget


# ──────────────────────────────────────────────
# CCL Gate
# ──────────────────────────────────────────────

class CCLVerificationError(Exception):
    """Raised when a credential fails verification. Non-fatal — caught by caller."""
    pass


class CredentialedConstraintLayer:
    """
    The mathematical gate: Verify(delta_R, credential) == 1.

    Uses HMAC-SHA256 to verify credential authenticity.
    The secret key is derived from the IMMUTABLE_HARD_CORE hash.

    All methods are synchronous, pure-CPU, O(1).
    """

    def __init__(self, immutable_hard_core: FrozenSet[str]) -> None:
        # Derive the system secret from the constitutional hard core
        core_bytes = "|".join(sorted(immutable_hard_core)).encode("utf-8")
        self._secret: bytes = hashlib.sha256(core_bytes).digest()

    # ──────────────────────────────────────────
    # Credential Issuance
    # ──────────────────────────────────────────

    def issue_credential(
        self,
        scope: AuthorityScope,
        authority: FrozenSet[str],
        phi_budget: float,
        issuer: str = "system",
        ttl_s: float = _DEFAULT_TTL_S,
    ) -> ConstraintCredential:
        """Issue a new signed credential."""
        now = time.time()
        cred_id = hashlib.sha256(
            f"{issuer}:{scope.value}:{now}".encode()
        ).hexdigest()[:16]

        phi_budget = min(phi_budget, _MAX_PHI_BUDGET)
        expires_at = now + ttl_s

        signature = self._compute_signature(
            cred_id, scope, phi_budget, now, expires_at
        )

        return ConstraintCredential(
            credential_id=cred_id,
            scope=scope,
            authority=authority,
            phi_budget=phi_budget,
            issued_at=now,
            expires_at=expires_at,
            issuer=issuer,
            signature=signature,
        )

    # ──────────────────────────────────────────
    # Verification Gate
    # ──────────────────────────────────────────

    def verify(
        self,
        ric: RealityInterfaceContract,
        credential: ConstraintCredential,
    ) -> bool:
        """
        The core gate function: Verify(RIC, credential) → {0, 1}.

        Checks (in order, short-circuit on failure):
          1. Signature is valid (HMAC-SHA256)
          2. Credential is not expired
          3. Credential scope covers the RIC action
          4. Credential Φ budget covers the RIC Φ budget
          5. RIC execute_authority is a subset of credential authority

        Returns True if all checks pass. Raises CCLVerificationError on failure.
        """
        # 1. Signature verification
        expected_sig = self._compute_signature(
            credential.credential_id,
            credential.scope,
            credential.phi_budget,
            credential.issued_at,
            credential.expires_at,
        )
        if not hmac.compare_digest(credential.signature, expected_sig):
            raise CCLVerificationError(
                f"CCL REJECT: invalid signature on credential {credential.credential_id}"
            )

        # 2. Expiry check
        if credential.is_expired():
            raise CCLVerificationError(
                f"CCL REJECT: credential {credential.credential_id} expired "
                f"({credential.expires_at:.0f} < {time.time():.0f})"
            )

        # 3. Scope covers action
        if not credential.covers_action(ric.action):
            raise CCLVerificationError(
                f"CCL REJECT: scope {credential.scope.value} does not cover "
                f"action {ric.action.value}"
            )

        # 4. Φ budget
        if not credential.covers_phi_budget(ric.phi_budget):
            raise CCLVerificationError(
                f"CCL REJECT: credential Φ budget {credential.phi_budget:.3f} < "
                f"RIC Φ budget {ric.phi_budget:.3f}"
            )

        # 5. Authority subset check
        ric_auth_set = frozenset(ric.execute_authority)
        if not ric_auth_set.issubset(credential.authority):
            missing = ric_auth_set - credential.authority
            raise CCLVerificationError(
                f"CCL REJECT: credential missing authority for: {missing}"
            )

        return True

    def requires_credential(self, ric: RealityInterfaceContract) -> bool:
        """Check if this RIC's action type requires credential verification."""
        return ric.action in _CREDENTIALED_ACTIONS

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _compute_signature(
        self,
        cred_id: str,
        scope: AuthorityScope,
        phi_budget: float,
        issued_at: float,
        expires_at: float,
    ) -> str:
        """HMAC-SHA256 over the credential's immutable fields."""
        message = (
            f"{cred_id}|{scope.value}|{phi_budget:.6f}|"
            f"{issued_at:.6f}|{expires_at:.6f}"
        ).encode("utf-8")
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()


# ──────────────────────────────────────────────────────────────────────────
# TICK 39.1: Anti-Reification & Amortized Depreciation
# ──────────────────────────────────────────────────────────────────────────
#
# Problem: The system could rewrite its CCL/Rule-IR to artificially zero out
# the historical Φ debt of past failures — perpetual motion machine.
#
# Solution:
#   1. PhiDebtEntry (frozen): An append-only sunk-cost record.
#      Once written, it can NEVER be deleted or zeroed.
#   2. PhiDebtLedger: Manages the append-only debt list.
#      amortize_one_tick() disperses debt across future ticks.
#      total_pending_debt() returns the current outstanding burden.
#   3. DemotedAxiom: "Controlled Demotion" (受控降格).
#      Obsolete credentials/rules are never deleted; they are
#      archived here with their accumulated Φ cost preserved.
#      This maintains a permanent, calculable rollback pathway.
#   4. CredentialedConstraintLayer gains:
#      - phi_debt_ledger: the live PhiDebtLedger
#      - demote_credential(): archive a superseded credential
#      - amortize_historical_cost(): public API for the governor loop
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PhiDebtEntry:
    """
    An immutable sunk-cost record.

    Once created, this entry CANNOT be modified or deleted.
    The accumulated_phi_cost represents real thermodynamic work
    that was expended — erasing it would violate the First Law.

    Fields:
      source_id:           what credential, rule, or action incurred this
      incurred_at:         Unix timestamp when the cost was crystallized
      accumulated_phi_cost: total Φ consumed by this credential's lifetime
      failure_severity:    0.0 (success) → 1.0 (catastrophic failure)
      amortization_ticks:  over how many future ticks to spread this debt
      remaining_balance:   starts equal to accumulated_phi_cost; decremented
                           by amortize_one_tick() but NEVER below zero —
                           the conceptual 'sunk' portion persists in the log
    """
    source_id:           str
    incurred_at:         float
    accumulated_phi_cost: float
    failure_severity:    float        # [0.0, 1.0]
    amortization_ticks:  int          # how many ticks to spread the debt


@dataclass
class PhiDebtLedger:
    """
    Append-only ledger of Φ sunk costs.

    Design invariants:
      • Entries are NEVER removed — only marked exhausted (balance = 0)
      • Total historical cost is ALWAYS the sum of accumulated_phi_cost
        across all entries, even when amortization is complete
      • pending_debit_per_tick() returns the per-tick installment the
        governor must deduct from its Φ budget

    This makes it mathematically impossible for the system to "forget"
    its past thermodynamic failures by rewriting credentials.
    """
    _entries: List[PhiDebtEntry] = field(default_factory=list)
    _balances: Dict[str, float] = field(default_factory=dict)  # source_id → remaining
    _ticks_processed: int = 0

    def record_debt(
        self,
        source_id: str,
        accumulated_phi_cost: float,
        failure_severity: float = 0.0,
        amortization_ticks: int = 10,
    ) -> PhiDebtEntry:
        """
        Append a new immutable debt entry.

        The entry is immediately added to the ledger.
        Existing entries for this source_id are NOT modified —
        the new debt is additive, not replacement.
        """
        entry = PhiDebtEntry(
            source_id            = source_id,
            incurred_at          = time.time(),
            accumulated_phi_cost = max(0.0, accumulated_phi_cost),
            failure_severity     = max(0.0, min(1.0, failure_severity)),
            amortization_ticks   = max(1, amortization_ticks),
        )
        self._entries.append(entry)
        # Initialize the amortizable balance (can reach 0 but entry stays)
        key = f"{source_id}:{entry.incurred_at:.3f}"
        self._balances[key] = entry.accumulated_phi_cost
        return entry

    def amortize_one_tick(self) -> float:
        """
        Process one tick of amortization across all active debt entries.

        For each entry with remaining balance > 0:
            installment = accumulated_phi_cost / amortization_ticks
            balance     -= installment  (floored at 0.0)

        Returns:
            Total Φ deducted this tick (the governor subtracts this
            from its current Φ budget to enforce sunk-cost honesty).
        """
        self._ticks_processed += 1
        total_deducted = 0.0

        for entry in self._entries:
            key = f"{entry.source_id}:{entry.incurred_at:.3f}"
            balance = self._balances.get(key, 0.0)
            if balance <= 0.0:
                continue
            installment = entry.accumulated_phi_cost / entry.amortization_ticks
            installment = min(installment, balance)
            self._balances[key] = max(0.0, balance - installment)
            total_deducted += installment

        return total_deducted

    def total_pending_debt(self) -> float:
        """Sum of all remaining (not yet amortized) balances."""
        return sum(v for v in self._balances.values() if v > 0.0)

    def total_historical_cost(self) -> float:
        """Sum of ALL accumulated costs ever recorded (incl. fully amortized)."""
        return sum(e.accumulated_phi_cost for e in self._entries)

    def pending_debit_per_tick(self, oscillation_freq_hz: float = 1.0 / 30.0) -> float:
        """
        Estimate the per-tick Φ installment given the current breathing frequency.

        oscillation_freq_hz:
          The governor's boundary breathing frequency (default: 1 tick / 30 s).
          Higher frequency → smaller installments (debt spread thinner).

        Formula:
          Σ_i [ balance_i / max(ticks_remaining_i, 1) ]
          where ticks_remaining_i ≈ amortization_ticks - ticks_processed_for_entry_i

        Returns a conservative estimate safe for budget planning.
        """
        total = 0.0
        for entry in self._entries:
            key = f"{entry.source_id}:{entry.incurred_at:.3f}"
            balance = self._balances.get(key, 0.0)
            if balance <= 0.0:
                continue
            # ticks elapsed since this entry was created
            age_ticks = math.floor(
                (time.time() - entry.incurred_at) * oscillation_freq_hz
            )
            remaining_ticks = max(1, entry.amortization_ticks - age_ticks)
            total += balance / remaining_ticks
        return total

    def get_summary(self) -> Dict[str, Any]:
        """Serializable summary for audit logs and /health endpoints."""
        return {
            "entry_count":          len(self._entries),
            "ticks_processed":      self._ticks_processed,
            "total_historical_cost": self.total_historical_cost(),
            "total_pending_debt":   self.total_pending_debt(),
            "entries": [
                {
                    "source_id":            e.source_id,
                    "accumulated_phi_cost": e.accumulated_phi_cost,
                    "failure_severity":     e.failure_severity,
                    "amortization_ticks":   e.amortization_ticks,
                    "remaining_balance": self._balances.get(
                        f"{e.source_id}:{e.incurred_at:.3f}", 0.0
                    ),
                }
                for e in self._entries
            ],
        }


@dataclass
class DemotedAxiom:
    """
    Controlled Demotion (受控降格) — an obsolete credential or rule
    archived permanently in the CCL's demotion registry.

    Obsolete axioms are NEVER deleted. They are demoted so that:
      1. Their accumulated Φ cost remains calculable.
      2. A rollback pathway can be reconstructed by un-demoting.
      3. The system cannot pretend its past constraints never existed.

    Fields:
      original_id:     the credential_id or rule identifier
      demoted_at:      when demotion occurred
      reason:          why it was demoted ("superseded", "expired", "policy_change")
      accumulated_phi: total Φ attributed to this axiom's lifetime
      superseded_by:   optional id of the new rule that replaced this one
      rollback_data:   enough state to reconstruct the original (pure dict)
    """
    original_id:    str
    demoted_at:     float
    reason:         str
    accumulated_phi: float
    superseded_by:  Optional[str] = None
    rollback_data:  Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────
# CCL extensions — wire in debt tracking + demotion
# ──────────────────────────────────────────────

# Monkey-patch PhiDebtLedger and demotion registry into CCL at class level.
# We do this via subclass extension rather than modifying frozen dataclasses,
# to remain backwards-compatible with any existing CCL consumers.

class CredentialedConstraintLayer(CredentialedConstraintLayer):  # type: ignore[no-redef]
    """
    TICK 39.1 extension of CredentialedConstraintLayer.

    Adds:
      - phi_debt_ledger: PhiDebtLedger (append-only Φ sunk-cost tracking)
      - _demotion_registry: List[DemotedAxiom] (permanent archive of demoted rules)
      - demote_credential(): archive a superseded credential
      - amortize_historical_cost(): public API for the governor loop
      - record_credential_debt(): called automatically when a credential is
        issued for a high-stakes action to begin tracking its Φ cost

    Inheritance note:
      The parent class __init__ is called first; this extension adds the
      ledger and registry as additional instance attributes.
    """

    def __init__(self, immutable_hard_core: FrozenSet[str]) -> None:
        super().__init__(immutable_hard_core)
        self.phi_debt_ledger: PhiDebtLedger = PhiDebtLedger()
        self._demotion_registry: List[DemotedAxiom] = []

    # ──────────────────────────────────────────
    # Anti-Reification Gate
    # ──────────────────────────────────────────

    def record_credential_debt(
        self,
        credential: ConstraintCredential,
        failure_severity: float = 0.0,
        amortization_ticks: int = 10,
    ) -> PhiDebtEntry:
        """
        Record the Φ cost of a credential's lifecycle into the debt ledger.

        Called automatically by issue_credential for credentialed actions.
        The phi_budget of the credential becomes the sunk cost — whether the
        action succeeds or fails, that budget was committed.

        failure_severity > 0.0 increases the amortization burden (the
        failure's Φ cost is spread across fewer future ticks, making
        the recovery slower and more honest).
        """
        # Reduce amortization window for failures — harder to recover
        if failure_severity > 0.5:
            amortization_ticks = max(1, amortization_ticks // 2)

        return self.phi_debt_ledger.record_debt(
            source_id            = credential.credential_id,
            accumulated_phi_cost = credential.phi_budget,
            failure_severity     = failure_severity,
            amortization_ticks   = amortization_ticks,
        )

    def amortize_historical_cost(
        self,
        n_ticks: int = 1,
        oscillation_freq_hz: float = 1.0 / 30.0,
    ) -> float:
        """
        Process n_ticks of Φ debt amortization.

        Called by the governor loop on each boundary breathing cycle.
        Returns the total Φ deducted — the governor MUST subtract this
        from phi_current to prevent sunk-cost erasure.

        Args:
            n_ticks:            number of amortization ticks to process
            oscillation_freq_hz: breathing frequency (default 1/30 Hz)

        Returns:
            Total Φ deducted across all n_ticks.
        """
        total = 0.0
        for _ in range(n_ticks):
            total += self.phi_debt_ledger.amortize_one_tick()
        return total

    # ──────────────────────────────────────────
    # Controlled Demotion (���控降格)
    # ──────────────────────────────────────────

    def demote_credential(
        self,
        credential: ConstraintCredential,
        reason: str = "superseded",
        superseded_by: Optional[str] = None,
        failure_severity: float = 0.0,
    ) -> DemotedAxiom:
        """
        Demote (archive) a credential instead of deleting it.

        The credential's accumulated Φ is preserved in the demotion
        registry and recorded in the debt ledger. The axiom is NEVER
        deleted — it can be queried for rollback reconstruction.

        Returns the DemotedAxiom record.
        """
        # Record the debt before archiving
        self.phi_debt_ledger.record_debt(
            source_id            = credential.credential_id,
            accumulated_phi_cost = credential.phi_budget,
            failure_severity     = failure_severity,
            amortization_ticks   = 20,  # slower amortization for demotions
        )

        demoted = DemotedAxiom(
            original_id    = credential.credential_id,
            demoted_at     = time.time(),
            reason         = reason,
            accumulated_phi = credential.phi_budget,
            superseded_by  = superseded_by,
            rollback_data  = {
                "scope":       credential.scope.value,
                "authority":   list(credential.authority),
                "phi_budget":  credential.phi_budget,
                "issued_at":   credential.issued_at,
                "expires_at":  credential.expires_at,
                "issuer":      credential.issuer,
                "signature":   credential.signature,
            },
        )
        self._demotion_registry.append(demoted)
        return demoted

    def get_demotion_registry(self) -> List[Dict[str, Any]]:
        """Return all demoted axioms (permanent, never pruned)."""
        return [
            {
                "original_id":   d.original_id,
                "demoted_at":    d.demoted_at,
                "reason":        d.reason,
                "accumulated_phi": d.accumulated_phi,
                "superseded_by": d.superseded_by,
            }
            for d in self._demotion_registry
        ]

    def get_debt_summary(self) -> Dict[str, Any]:
        """Full anti-reification status for audit endpoints."""
        return {
            "phi_debt":        self.phi_debt_ledger.get_summary(),
            "demotion_registry_size": len(self._demotion_registry),
        }
