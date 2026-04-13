# fs_bus.py — Unified file-system bus. Everything is a file.
# Single responsibility: all I/O, serialization, and content-hash versioning.

import json
import hashlib
import time
import os
import subprocess
from pathlib import Path
from typing import Any, Optional


class FileSystemBus:
    """UNIX-philosophy file-system bus.

    All state — population, memory, models, logs, meta-rules — flows through
    this single interface as plain files.  Content-hash versioning provides
    git-like integrity without an external dependency.
    """

    def __init__(self, root: str = "agi_workspace"):
        self.root = Path(root)
        self._versions = self.root / ".versions"
        for d in ("population", "memory", "models", "logs", ".versions"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self._git_available = self._init_git()

    # ── write ──────────────────────────────────────────────

    def write(self, path: str, data: Any) -> str:
        fp = self.root / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (dict, list)):
            content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            fp.write_text(content, encoding="utf-8")
        elif isinstance(data, bytes):
            fp.write_bytes(data)
        else:
            fp.write_text(str(data), encoding="utf-8")
        h = hashlib.sha256(fp.read_bytes()).hexdigest()[:12]
        entry = {"path": path, "hash": h, "t": time.time()}
        (self._versions / f"{h}.json").write_text(
            json.dumps(entry), encoding="utf-8"
        )
        self._bump_version_counter(entry)
        return h

    def write_bytes(self, path: str, data: bytes) -> str:
        fp = self.root / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(data)
        h = hashlib.sha256(data).hexdigest()[:12]
        entry = {"path": path, "hash": h, "t": time.time()}
        (self._versions / f"{h}.json").write_text(
            json.dumps(entry), encoding="utf-8"
        )
        self._bump_version_counter(entry)
        return h

    # ── read ───────────────────────────────────────────────

    def read(self, path: str) -> Optional[Any]:
        fp = self.root / path
        if not fp.exists():
            return None
        text = fp.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    def read_bytes(self, path: str) -> Optional[bytes]:
        fp = self.root / path
        return fp.read_bytes() if fp.exists() else None

    # ── queries ────────────────────────────────────────────

    def exists(self, path: str) -> bool:
        return (self.root / path).exists()

    def list_dir(self, path: str) -> list:
        fp = self.root / path
        return [p.name for p in fp.iterdir()] if fp.exists() else []

    def version(self) -> dict:
        """Return version count and latest entry (O(1) — no directory scan)."""
        counter_file = self._versions / "_counter.json"
        if counter_file.exists():
            try:
                return json.loads(counter_file.read_text())
            except (json.JSONDecodeError, ValueError):
                pass
        return {"total": 0}

    def _bump_version_counter(self, entry: dict) -> None:
        """Increment the version counter (O(1) append, not O(n) scan)."""
        counter_file = self._versions / "_counter.json"
        try:
            state = json.loads(counter_file.read_text()) if counter_file.exists() else {"total": 0}
        except (json.JSONDecodeError, ValueError):
            state = {"total": 0}
        state["total"] = state.get("total", 0) + 1
        state["latest"] = entry
        counter_file.write_text(json.dumps(state), encoding="utf-8")

    def snapshot(self) -> str:
        """Fast content hash of critical state files only (population + memory)."""
        h = hashlib.sha256()
        for subdir in ("population", "memory"):
            d = self.root / subdir
            if d.exists():
                for f in sorted(d.rglob("*")):
                    if f.is_file():
                        h.update(f.read_bytes())
        # Include meta_rules.json at root
        mr = self.root / "meta_rules.json"
        if mr.exists():
            h.update(mr.read_bytes())
        return h.hexdigest()[:16]

    # ── git integration ───────────────────────────────────

    def _init_git(self) -> bool:
        if not (self.root / ".git").exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=self.root, capture_output=True, check=True,
                )
                gitignore = self.root / ".gitignore"
                if not gitignore.exists():
                    gitignore.write_text(".DS_Store\n*.pt\n.versions/\n")
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                return False
        return True

    def commit(self, message: str) -> bool:
        if not self._git_available:
            return False
        try:
            # Stage only critical state dirs (skip logs/.versions for speed)
            for subdir in ("population", "memory", "meta_rules.json"):
                target = self.root / subdir
                if target.exists():
                    subprocess.run(
                        ["git", "add", str(target)],
                        cwd=self.root, capture_output=True, check=False,
                    )
            result = subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty=false"],
                cwd=self.root, capture_output=True,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    # ── append (NDJSON) ───────────────────────────────────

    def append(self, path: str, data: Any) -> None:
        fp = self.root / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(data, ensure_ascii=False, default=str)
        with open(fp, "a", encoding="utf-8") as f:
            f.write(line + "\n")

