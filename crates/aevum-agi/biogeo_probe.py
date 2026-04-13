#!/usr/bin/env python3
"""biogeo_probe.py -- The Universal Sensor Bus (TICK 8.0).

Lightweight, standalone physical-environment probe following UNIX philosophy:
one tool, one job -- detect and report the host's physical constraints.

Exposes get_physics_schema() -> dict: a schema-free, deeply extensible
dictionary of hardware metrics.  New sensors (GPU VRAM, POD budgets,
network bandwidth) can be added as top-level or nested keys without
breaking existing consumers.

No ML dependencies.  No side effects.  Pure measurement.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any, Dict


def _detect_total_ram_bytes() -> int:
    """Detect total physical RAM in bytes. Cross-platform (macOS/Linux)."""
    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        else:
            with open("/proc/meminfo") as f:
                text = f.read()
            m = re.search(r"MemTotal:\s+(\d+)", text)
            if m:
                return int(m.group(1)) * 1024  # /proc/meminfo reports kB
    except Exception:
        pass
    return 0


def _detect_cpu_cores() -> int:
    """Detect number of logical CPU cores."""
    return os.cpu_count() or 1


def _detect_mem_utilization_pct() -> float:
    """Detect current system-wide memory utilization percentage."""
    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                lines = result.stdout
                page_size = 16384  # default macOS ARM
                m = re.search(r"page size of (\d+)", lines)
                if m:
                    page_size = int(m.group(1))

                def _extract(label: str) -> int:
                    m2 = re.search(rf"{label}:\s+(\d+)", lines)
                    return int(m2.group(1)) if m2 else 0

                free = _extract("Pages free")
                inactive = _extract("Pages inactive")
                total_pages = sum(
                    _extract(lbl) for lbl in (
                        "Pages free", "Pages active", "Pages inactive",
                        "Pages speculative", "Pages wired down",
                    )
                )
                if total_pages > 0:
                    used_pct = (1.0 - (free + inactive) / total_pages) * 100.0
                    return max(0.0, min(100.0, used_pct))
        else:
            with open("/proc/meminfo") as f:
                text = f.read()
            total_m = re.search(r"MemTotal:\s+(\d+)", text)
            avail_m = re.search(r"MemAvailable:\s+(\d+)", text)
            if total_m and avail_m:
                total = float(total_m.group(1))
                avail = float(avail_m.group(1))
                if total > 0:
                    return (1.0 - avail / total) * 100.0
    except Exception:
        pass
    return 0.0


def get_physics_schema() -> dict:
    """Return a schema-free dictionary of the host's physical constraints.

    The returned dict is deeply extensible: consumers MUST handle missing
    keys gracefully (use .get()).  New sensors (GPU VRAM, Kubernetes POD
    budgets, network I/O, disk IOPS) can be added as top-level or nested
    keys without breaking existing callers.

    Current sensors:
      compute.cpu_cores       -- int, logical core count
      memory.total_bytes      -- int, physical RAM in bytes
      memory.total_gb         -- float, physical RAM in GB
      memory.utilization_pct  -- float, current system-wide memory usage %
      platform.os             -- str, sys.platform value
      platform.arch           -- str, CPU architecture (e.g. arm64)
    """
    total_ram = _detect_total_ram_bytes()

    return {
        "compute": {
            "cpu_cores": _detect_cpu_cores(),
        },
        "memory": {
            "total_bytes": total_ram,
            "total_gb": round(total_ram / (1024 ** 3), 1) if total_ram else 0.0,
            "utilization_pct": round(_detect_mem_utilization_pct(), 2),
        },
        "platform": {
            "os": sys.platform,
            "arch": os.uname().machine if hasattr(os, "uname") else "unknown",
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_physics_schema(), indent=2))
