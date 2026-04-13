"""
credential_layer.py — Temporary stub for Credentialed Constraint Layer
"""

from typing import Any, Optional


class AuthorityScope:
    """Stub authority scope."""
    SOFT_MODIFY = "soft_modify"
    HARD_MODIFY = "hard_modify"
    FISSION = "fission"
    META_EVOLVE = "meta_evolve"
    FRANCHISE = "franchise"


class CCLVerificationError(Exception):
    """Stub CCL verification error."""
    pass


class StubCredential:
    """Stub credential."""
    def __init__(self):
        self.credential_id = f"cred-{id(self)}"


class CredentialedConstraintLayer:
    """Stub credentialed constraint layer."""
    
    def __init__(self, hard_core: frozenset):
        self.hard_core = hard_core
    
    def requires_credential(self, ric) -> bool:
        """Stub: never require credentials for now."""
        return False
    
    def issue_credential(self, **kwargs) -> StubCredential:
        """Issue a stub credential."""
        return StubCredential()
    
    def verify(self, ric, credential) -> bool:
        """Stub verification: always pass."""
        return True
