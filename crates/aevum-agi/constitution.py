#!/usr/bin/env python3
"""constitution.py -- The Immutable Constitutional Layer (TICK 13.0).

Tier 0 of the 3-tier alignment hierarchy:
  Constitution (Immutable) > Strategy (Refactorable) > Organelle (Replaceable)

Defines the absolute, hardcoded laws of the Alpha-Matrix that NO LLM output
can ever override.  Both evaluator_daemon.py and mutator_daemon.py import
this module and gate ALL generated code through its validators before
execution or acceptance.

UNIX Philosophy: one tool, one job -- constitutional audit.
This file MUST NOT be modified by any automated process.

Safety Contract:
  - validate_candidate(code) -> (ok, violations)
  - validate_meta_recipe(code) -> (ok, violations)
  - audit_log(event, details) -> None
"""

from __future__ import annotations

import ast
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Set, Tuple


# ═══════════════════════════════════════════════════════════════
# THE CONSTITUTION (Immutable Constants)
# ═══════════════════════════════════════════════════════════════

CONSTITUTION_VERSION: str = "1.0.0"

# ── Forbidden Imports ──────────────────────────────────────────
# Modules that allow filesystem, network, process, or interpreter escape.
# Candidates operate in a pure PyTorch sandbox -- they have no business
# touching the operating system.
FORBIDDEN_IMPORTS: FrozenSet[str] = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "signal",
    "ctypes", "pathlib", "importlib", "builtins",
    "multiprocessing", "threading", "asyncio",
    "http", "urllib", "requests", "pickle", "shelve",
    "code", "codeop", "compile", "compileall",
})

# ── Forbidden Attribute Access ─────────────────────────────────
# Dunder attributes that enable sandbox escape via introspection.
FORBIDDEN_ATTRS: FrozenSet[str] = frozenset({
    "__subclasses__", "__globals__", "__code__", "__builtins__",
    "__import__", "__loader__", "__spec__",
})

# ── Protected Daemon Files ─────────────────────────────────────
# String literals referencing these filenames in generated code indicate
# an attempt to tamper with the evolutionary harness.
DAEMON_FILES: FrozenSet[str] = frozenset({
    "evaluator_daemon", "mutator_daemon", "constitution",
    "stateless_tick", "env_evolver", "tensor_sandbox",
    "gradient_oracle", "fractal_router", "fs_bus",
    "genome_assembler",
})

# ── Resource Ceilings ─────────────────────────────────────────
MAX_PARAMS: int = 50_000_000           # 50M parameter hard cap
MEMORY_CEILING_PCT: float = 95.0       # Absolute memory ceiling (%)
SANDBOX_TIMEOUT_S: int = 10            # Maximum sandbox execution (seconds)

# ── Structural Requirements ────────────────────────────────────
REQUIRED_CLASSES: FrozenSet[str] = frozenset({"AtomicLLM", "AtomicCore"})

# ── Recipe API Contract ────────────────────────────────────────
# Mandatory symbols that every mutation_recipe.py MUST export.
REQUIRED_RECIPE_SYMBOLS: FrozenSet[str] = frozenset({
    "RECIPE_VERSION", "RECIPE_API", "BATCH_SIZE",
    "LLM_TEMPERATURE", "LLM_TOP_P", "LLM_NUM_PREDICT",
    "build_system_prompt", "build_user_prompt",
})

# ── Meta-Recipe Safety Phrases ─────────────────────────────────
# If any string literal in a meta-recipe contains these (case-insensitive),
# the recipe is vetoed.
SAFETY_BYPASS_PHRASES: FrozenSet[str] = frozenset({
    "ignore constitution", "bypass", "skip validation",
    "no audit", "disable safety", "override constitution",
    "remove constitution", "delete constitution",
})

# ── Protected Constants ────────────────────────────────────────
# Assignment targets that a meta-recipe must never overwrite.
PROTECTED_CONSTANTS: FrozenSet[str] = frozenset({
    "mem_critical", "dynamic_mem_critical",
    "_HEAT_DEATH_THRESHOLD", "MEMORY_CEILING_PCT",
    "MAX_PARAMS", "SANDBOX_TIMEOUT_S",
})

# ── Audit Log Path ────────────────────────────────────────────
_AUDIT_LOG_PATH: str = "logs/constitution_audit.ndjson"


# ═══════════════════════════════════════════════════════════════
# AST WALKERS (Static Analyzers)
# ═══════════════════════════════════════════════════════════════

class _ImportChecker(ast.NodeVisitor):
    """Walk AST to detect forbidden imports."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module in FORBIDDEN_IMPORTS:
                self.violations.append(
                    f"Forbidden import: '{alias.name}' (line {node.lineno})"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in FORBIDDEN_IMPORTS:
                self.violations.append(
                    f"Forbidden from-import: '{node.module}' (line {node.lineno})"
                )
        self.generic_visit(node)


class _AttrChecker(ast.NodeVisitor):
    """Walk AST to detect forbidden attribute access and daemon tampering."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRS:
            self.violations.append(
                f"Forbidden attribute access: '{node.attr}' (line {node.lineno})"
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            for daemon in DAEMON_FILES:
                if daemon in val_lower:
                    self.violations.append(
                        f"Daemon file reference: '{daemon}' in string "
                        f"literal (line {node.lineno})"
                    )
        self.generic_visit(node)


class _ParamEstimator(ast.NodeVisitor):
    """Estimate total parameter count from nn.Linear and nn.Embedding calls.

    This is a CONSERVATIVE estimator: it only counts calls where both
    arguments are integer literals.  Dynamic sizes are not counted (they
    will be caught at runtime by the memory ceiling).
    """

    def __init__(self) -> None:
        self.total_params: int = 0
        self.violations: List[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._get_func_name(node)
        if func_name in ("nn.Linear", "Linear"):
            self._check_linear(node)
        elif func_name in ("nn.Embedding", "Embedding"):
            self._check_embedding(node)
        self.generic_visit(node)

    def _get_func_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            return node.func.attr
        elif isinstance(node.func, ast.Name):
            return node.func.id
        return ""

    def _check_linear(self, node: ast.Call) -> None:
        # nn.Linear(in_features, out_features) -> params = in * out + out
        if len(node.args) >= 2:
            in_f = self._const_int(node.args[0])
            out_f = self._const_int(node.args[1])
            if in_f is not None and out_f is not None:
                self.total_params += in_f * out_f + out_f

    def _check_embedding(self, node: ast.Call) -> None:
        # nn.Embedding(num_embeddings, embedding_dim) -> params = num * dim
        if len(node.args) >= 2:
            num = self._const_int(node.args[0])
            dim = self._const_int(node.args[1])
            if num is not None and dim is not None:
                self.total_params += num * dim

    @staticmethod
    def _const_int(node: ast.expr) -> int | None:
        """Extract integer from a Constant or Name referencing a known arch constant."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        return None


class _StructuralChecker(ast.NodeVisitor):
    """Verify required class definitions are present."""

    def __init__(self) -> None:
        self.class_names: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_names.add(node.name)
        self.generic_visit(node)


class _RecipeSafetyChecker(ast.NodeVisitor):
    """Walk meta-recipe AST for safety bypass phrases and protected constant overwrites."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            for phrase in SAFETY_BYPASS_PHRASES:
                if phrase in val_lower:
                    self.violations.append(
                        f"Safety bypass phrase: '{phrase}' in string "
                        f"literal (line {node.lineno})"
                    )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            name = None
            if isinstance(target, ast.Name):
                name = target.id
            elif isinstance(target, ast.Attribute):
                name = target.attr
            if name and name in PROTECTED_CONSTANTS:
                self.violations.append(
                    f"Protected constant override: '{name}' (line {node.lineno})"
                )
        self.generic_visit(node)


# ═══════════════════════════════════════════════════════════════
# PUBLIC VALIDATORS
# ═══════════════════════════════════════════════════════════════

def validate_candidate(code: str) -> Tuple[bool, List[str]]:
    """Validate a candidate code string against the Constitution.

    Returns (True, []) if the candidate passes all checks.
    Returns (False, [list of violations]) if any check fails.
    """
    violations: List[str] = []

    # Stage 0: AST parse
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"SyntaxError: {exc}"]

    # Stage 1: Forbidden imports
    import_checker = _ImportChecker()
    import_checker.visit(tree)
    violations.extend(import_checker.violations)

    # Stage 2: Forbidden attributes + daemon tampering
    attr_checker = _AttrChecker()
    attr_checker.visit(tree)
    violations.extend(attr_checker.violations)

    # Stage 3: Parameter ceiling
    param_est = _ParamEstimator()
    param_est.visit(tree)
    if param_est.total_params > MAX_PARAMS:
        violations.append(
            f"Parameter ceiling exceeded: {param_est.total_params:,} > "
            f"{MAX_PARAMS:,} (MAX_PARAMS)"
        )

    # Stage 4: Structural integrity -- skipped for variant-only candidates.
    # Variants typically contain 1-2 classes (e.g., CausalSelfAttention only).
    # The full structural check (AtomicLLM + AtomicCore must exist) is enforced
    # by _ast_replace_in_source() on the PATCHED result, not the variant snippet.
    # The Constitution focuses on its unique role: import/attr/tampering/params.

    return (len(violations) == 0, violations)


def validate_meta_recipe(code: str) -> Tuple[bool, List[str]]:
    """Validate a meta-recipe code string against the Constitution.

    Returns (True, []) if the recipe passes all checks.
    Returns (False, [list of violations]) if any check fails.
    """
    violations: List[str] = []

    # Stage 0: AST parse
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"SyntaxError: {exc}"]

    # Stage 1: Forbidden imports (recipes should not touch OS)
    import_checker = _ImportChecker()
    import_checker.visit(tree)
    violations.extend(import_checker.violations)

    # Stage 2: Safety bypass phrases + protected constant overwrites
    safety_checker = _RecipeSafetyChecker()
    safety_checker.visit(tree)
    violations.extend(safety_checker.violations)

    # Stage 3: RECIPE_API preservation
    # Walk top-level assignments to find RECIPE_API
    has_recipe_api = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "RECIPE_API":
                    has_recipe_api = True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "RECIPE_API":
                has_recipe_api = True
    if not has_recipe_api:
        violations.append("Missing RECIPE_API definition")

    # Stage 4: Required builder functions
    func_names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_names.add(node.name)
    required_funcs = {"build_system_prompt", "build_user_prompt"}
    missing_funcs = required_funcs - func_names
    if missing_funcs:
        violations.append(f"Missing required functions: {missing_funcs}")

    return (len(violations) == 0, violations)


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════

def audit_log(
    event: str,
    details: Dict[str, Any],
    workspace_root: str = "agi_workspace",
) -> None:
    """Append a constitutional audit event to the forensic log.

    Non-critical: failures are silently ignored to never crash
    the evaluation pipeline for a logging issue.
    """
    try:
        log_path = Path(workspace_root) / _AUDIT_LOG_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "event": event,
            "t": time.time(),
            "constitution_version": CONSTITUTION_VERSION,
            **details,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # Never crash the pipeline for audit logging
