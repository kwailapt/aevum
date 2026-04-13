#!/usr/bin/env python3
# git_msa_daemon.py — Git-MSA Evolutionary Conservation Daemon
# AlphaGenome mapping: treats Git history as a Multiple Sequence Alignment (MSA)
# library. Rules surviving 10,000+ ticks are hardened into meta_rules.json.

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fs_bus import FileSystemBus

# Conservation threshold: rules must survive this many generations
# before being promoted to eternal status in meta_rules.json.
CONSERVATION_THRESHOLD = 10_000

# Scan interval in seconds (daemon polling rate)
SCAN_INTERVAL = 60.0


class GitMSADaemon:
    """Background conservation lock daemon.

    Scans the evolution log and meta-evolution state to identify rules
    (I Ching weights, BioGeometry configs, Epiplexity parameters) that
    have persisted without rollback for CONSERVATION_THRESHOLD generations.

    When a rule crosses the threshold, it is:
    1. Hardened: written into meta_rules.json as an eternal axiom.
    2. Locked: excluded from future meta-evolution perturbations.
    3. Logged: appended to logs/conservation.ndjson for audit trail.
    """

    def __init__(self, fs: FileSystemBus):
        self.fs = fs
        self._load_state()

    def _load_state(self):
        """Load daemon state from filesystem."""
        state = self.fs.read("memory/msa_daemon_state.json") or {}
        self.rule_birth: Dict[str, int] = state.get("rule_birth", {})
        self.hardened_rules: List[str] = state.get("hardened_rules", [])
        self.last_scan_gen: int = state.get("last_scan_gen", 0)

    def _save_state(self):
        """Persist daemon state."""
        self.fs.write("memory/msa_daemon_state.json", {
            "rule_birth": self.rule_birth,
            "hardened_rules": self.hardened_rules,
            "last_scan_gen": self.last_scan_gen,
        })

    def scan(self) -> List[str]:
        """Scan current rules and check for conservation threshold crossing.

        Returns list of newly hardened rule keys.
        """
        # Read current generation from checkpoint
        ckpt = self.fs.read("memory/checkpoint.json") or {}
        current_gen = ckpt.get("generation", 0)

        if current_gen <= self.last_scan_gen:
            return []

        # Read meta-evolution state to check for rollbacks
        meta_state = self.fs.read("memory/meta_es_state.json") or {}

        # Read current rule files
        iching = self.fs.read("population/iching_rules.json") or {}
        biogeo = self.fs.read("population/biogeo_cfg.json") or {}
        epi_cfg = self.fs.read("population/epi_cfg.json") or {}

        # Build current rule fingerprints
        current_rules: Dict[str, float] = {}
        for k, v in iching.items():
            current_rules[f"ic_{k}_w"] = v.get("w", 1.0)
            current_rules[f"ic_{k}_mr"] = v.get("mr", 0.3)
        for i, w in enumerate(biogeo.get("rw", [])):
            current_rules[f"bg_rw_{i}"] = w
        current_rules["epi_div_w"] = epi_cfg.get("div_w", 1.0)
        current_rules["epi_scale"] = epi_cfg.get("scale", 1.0)

        # Track rule births (first appearance without rollback)
        for key, val in current_rules.items():
            if key not in self.rule_birth:
                self.rule_birth[key] = current_gen

        # Check for rules crossing conservation threshold
        newly_hardened: List[str] = []
        for key, birth_gen in list(self.rule_birth.items()):
            if key in self.hardened_rules:
                continue
            age = current_gen - birth_gen
            if age >= CONSERVATION_THRESHOLD:
                self.hardened_rules.append(key)
                newly_hardened.append(key)

                # Log conservation event
                event = {
                    "gen": current_gen,
                    "rule": key,
                    "value": current_rules.get(key),
                    "age": age,
                    "t": time.time(),
                }
                self.fs.append("logs/conservation.ndjson", event)
                print(f"  [git-msa] HARDENED: {key} = {current_rules.get(key)} "
                      f"(survived {age} generations)")

        # Promote hardened rules to meta_rules.json
        if newly_hardened:
            self._promote_to_meta_rules(newly_hardened, current_rules)

        self.last_scan_gen = current_gen
        self._save_state()
        return newly_hardened

    def _promote_to_meta_rules(self, keys: List[str], values: Dict[str, float]):
        """Write hardened rules into meta_rules.json as eternal conservation laws."""
        meta = self.fs.read("meta_rules.json") or {"rules": [], "version": "eternal-v2-symbolic"}

        if "conserved" not in meta:
            meta["conserved"] = {}

        for key in keys:
            meta["conserved"][key] = {
                "value": values.get(key),
                "hardened_at": time.time(),
                "status": "eternal",
            }

        meta["conservation_count"] = len(meta["conserved"])
        self.fs.write("meta_rules.json", meta)
        self.fs.commit(f"Git-MSA: hardened {len(keys)} rules into meta_rules.json")

    def reset_rule(self, key: str):
        """Called on meta-evolution rollback — resets the birth counter for a rule."""
        if key in self.rule_birth and key not in self.hardened_rules:
            del self.rule_birth[key]


def run_daemon():
    """Run the daemon in a polling loop."""
    fs = FileSystemBus()
    daemon = GitMSADaemon(fs)

    print("=" * 72)
    print("  GIT-MSA CONSERVATION DAEMON")
    print("=" * 72)
    print(f"  Conservation threshold : {CONSERVATION_THRESHOLD} generations")
    print(f"  Scan interval          : {SCAN_INTERVAL}s")
    print(f"  Already hardened       : {len(daemon.hardened_rules)} rules")
    print(f"  Last scanned gen       : {daemon.last_scan_gen}")
    print("=" * 72)

    while True:
        try:
            newly = daemon.scan()
            if newly:
                print(f"  [git-msa] Cycle complete: {len(newly)} new conserved rules")
        except Exception as e:
            print(f"  [git-msa] Scan error: {e}")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run_daemon()
