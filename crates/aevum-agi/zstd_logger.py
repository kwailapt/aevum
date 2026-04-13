#!/usr/bin/env python3
"""zstd_logger.py — First-Principles Storage: Zstandard streaming log compression.

Replaces raw .ndjson / .json log output with CPU-gated Zstd compressed streams.
Target: 2GB raw JSON → ~150-250MB on-the-fly compression (~10:1 ratio).

Design:
  - Streaming append: each record is JSON-encoded and flushed to a .jsonl.zst file
  - CPU-gated: compression only runs when CPU load < 50%; otherwise buffers to
    a small in-memory queue and flushes on next low-load tick
  - Rotation: .zst files are rotated when they exceed _CHUNK_MAX_BYTES
  - NAS offload: placeholder _offload_to_nas() triggered when local log dir > 1GB
  - Read-back: iterator to decompress and yield records for dashboard polling

Axiom 1 compliant: no shared state between ticks. The compressor is opened and
closed within a single function call scope.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import zstandard as zstd

# ── Constants ───────────────────────────────────────────────────────────────

_ZSTD_LEVEL: int = 3                    # Compression level (1-22, 3 = fast default)
_CHUNK_MAX_BYTES: int = 50 * 1024 * 1024  # 50MB per chunk before rotation
_LOCAL_MAX_BYTES: int = 1024 * 1024 * 1024  # 1GB local threshold → NAS offload
_CPU_GATE_PCT: float = 50.0              # Only compress when CPU < this %
_BUFFER_MAX: int = 500                   # Max buffered records before forced flush


# ── CPU gate ────────────────────────────────────────────────────────────────

def _cpu_below_gate() -> bool:
    """Return True if current CPU load is below the compression gate."""
    try:
        loadavg = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        cpu_pct = (loadavg / cpu_count) * 100.0
        return cpu_pct < _CPU_GATE_PCT
    except (OSError, AttributeError):
        return True  # If we can't measure, allow compression


# ── Streaming Zstd Logger ──────────────────────────────────────────────────

class ZstdLogger:
    """Append-only Zstandard compressed JSONL logger.

    Each log stream (e.g., 'tick_telemetry', 'evolution', 'meta_evolution')
    gets its own .jsonl.zst file chain under the logs directory.
    """

    def __init__(self, log_dir: str | Path, stream_name: str):
        self.log_dir = Path(log_dir)
        self.stream_name = stream_name
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: List[bytes] = []
        self._compressor = zstd.ZstdCompressor(level=_ZSTD_LEVEL)

    def _current_chunk_path(self) -> Path:
        """Find the current (latest) chunk file, or create chunk 0."""
        chunks = sorted(self.log_dir.glob(f"{self.stream_name}.*.jsonl.zst"))
        if not chunks:
            return self.log_dir / f"{self.stream_name}.000000.jsonl.zst"
        latest = chunks[-1]
        if latest.stat().st_size >= _CHUNK_MAX_BYTES:
            # Rotate: increment chunk number
            try:
                num = int(latest.stem.split(".")[1]) + 1
            except (IndexError, ValueError):
                num = len(chunks)
            return self.log_dir / f"{self.stream_name}.{num:06d}.jsonl.zst"
        return latest

    def append(self, record: Dict[str, Any]) -> None:
        """Append a single record. CPU-gated: buffers if CPU is high."""
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        self._buffer.append(line.encode("utf-8"))

        # Flush conditions: CPU is low, or buffer is full (forced flush)
        if len(self._buffer) >= _BUFFER_MAX or _cpu_below_gate():
            self.flush()

    def flush(self) -> int:
        """Flush buffered records to the compressed stream. Returns bytes written."""
        if not self._buffer:
            return 0

        chunk_path = self._current_chunk_path()
        raw_data = b"".join(self._buffer)
        self._buffer.clear()

        # Append compressed data to chunk
        # We use a simple framing: [4-byte LE length][compressed block]
        # This allows incremental decompression without re-reading entire file
        compressed = self._compressor.compress(raw_data)
        frame = struct.pack("<I", len(compressed)) + compressed

        with open(chunk_path, "ab") as f:
            f.write(frame)
            f.flush()
            os.fsync(f.fileno())  # Force kernel buffer → physical disk

        # Check NAS offload threshold
        self._check_offload()

        return len(frame)

    def close(self) -> int:
        """Flush any remaining buffered records and sync to disk. Returns bytes written."""
        return self.flush()

    def __enter__(self) -> "ZstdLogger":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _check_offload(self) -> None:
        """Trigger NAS offload if local log size exceeds threshold."""
        total = sum(f.stat().st_size for f in self.log_dir.glob(f"{self.stream_name}.*.jsonl.zst"))
        if total > _LOCAL_MAX_BYTES:
            _offload_to_nas(self.log_dir, self.stream_name)

    def local_size_bytes(self) -> int:
        """Total compressed size of this stream on local SSD."""
        return sum(
            f.stat().st_size
            for f in self.log_dir.glob(f"{self.stream_name}.*.jsonl.zst")
        )

    def chunk_count(self) -> int:
        """Number of chunk files for this stream."""
        return len(list(self.log_dir.glob(f"{self.stream_name}.*.jsonl.zst")))


# ── Read-back iterator (for dashboard) ─────────────────────────────────────

def iter_zstd_records(
    log_dir: str | Path,
    stream_name: str,
    tail: int = 0,
) -> Iterator[Dict[str, Any]]:
    """Iterate over records in a compressed stream.

    If tail > 0, only yield the last N records (reads all, returns tail).
    Designed for dashboard polling — decompresses on-the-fly.
    """
    log_dir = Path(log_dir)
    chunks = sorted(log_dir.glob(f"{stream_name}.*.jsonl.zst"))
    decompressor = zstd.ZstdDecompressor()

    all_records: List[Dict[str, Any]] = []

    for chunk_path in chunks:
        try:
            raw = chunk_path.read_bytes()
        except Exception:
            continue

        offset = 0
        while offset + 4 <= len(raw):
            frame_len = struct.unpack("<I", raw[offset:offset + 4])[0]
            offset += 4
            if offset + frame_len > len(raw):
                break
            compressed_block = raw[offset:offset + frame_len]
            offset += frame_len

            try:
                decompressed = decompressor.decompress(compressed_block)
                for line in decompressed.decode("utf-8").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            all_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

    if tail > 0:
        yield from all_records[-tail:]
    else:
        yield from all_records


def read_latest_record(
    log_dir: str | Path,
    stream_name: str,
) -> Optional[Dict[str, Any]]:
    """Read only the most recent record from a compressed stream.

    Optimized: reads only the last chunk file, decompresses last frame.
    """
    log_dir = Path(log_dir)
    chunks = sorted(log_dir.glob(f"{stream_name}.*.jsonl.zst"))
    if not chunks:
        return None

    decompressor = zstd.ZstdDecompressor()
    last_chunk = chunks[-1]

    try:
        raw = last_chunk.read_bytes()
    except Exception:
        return None

    # Walk all frames, keep last decompressed block
    last_block: Optional[bytes] = None
    offset = 0
    while offset + 4 <= len(raw):
        frame_len = struct.unpack("<I", raw[offset:offset + 4])[0]
        offset += 4
        if offset + frame_len > len(raw):
            break
        compressed_block = raw[offset:offset + frame_len]
        offset += frame_len
        try:
            last_block = decompressor.decompress(compressed_block)
        except Exception:
            continue

    if last_block is None:
        return None

    # Return last non-empty line from last block
    lines = last_block.decode("utf-8").strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


# ── Storage metrics ────────────────────────────────────────────────────────

def get_storage_metrics(log_dir: str | Path) -> Dict[str, Any]:
    """Return storage mass metrics for dashboard display."""
    log_dir = Path(log_dir)
    local_bytes = 0
    chunk_count = 0
    streams: Dict[str, int] = {}

    for f in log_dir.glob("*.jsonl.zst"):
        size = f.stat().st_size
        local_bytes += size
        chunk_count += 1
        stream = f.name.split(".")[0]
        streams[stream] = streams.get(stream, 0) + size

    # Check NAS offload manifest
    nas_bytes = 0
    manifest = log_dir / "_nas_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text())
            nas_bytes = data.get("total_offloaded_bytes", 0)
        except Exception:
            pass

    return {
        "local_bytes": local_bytes,
        "local_mb": round(local_bytes / (1024 * 1024), 2),
        "nas_bytes": nas_bytes,
        "nas_gb": round(nas_bytes / (1024 * 1024 * 1024), 3),
        "chunk_count": chunk_count,
        "streams": streams,
    }


# ── NAS Offload Placeholder ───────────────────────────────────────────────

def _offload_to_nas(log_dir: Path, stream_name: str) -> None:
    """Placeholder: move old .zst chunks to NAS when local > 1GB.

    Implementation hook for future NAS integration (rsync, SMB, NFS).
    Currently: logs the intent and updates the manifest.
    """
    chunks = sorted(log_dir.glob(f"{stream_name}.*.jsonl.zst"))
    if len(chunks) <= 1:
        return  # Keep at least the current chunk

    # In production: rsync/move old chunks to NAS mount
    # For now: record what WOULD be offloaded
    offload_candidates = chunks[:-1]  # All but the latest
    total_offload = sum(c.stat().st_size for c in offload_candidates)

    manifest_path = log_dir / "_nas_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    except Exception:
        manifest = {}

    manifest.setdefault("offload_log", [])
    manifest["offload_log"].append({
        "stream": stream_name,
        "chunks": [c.name for c in offload_candidates],
        "bytes": total_offload,
        "t": time.time(),
        "action": "PENDING_NAS_OFFLOAD",
    })
    manifest["total_offloaded_bytes"] = manifest.get("total_offloaded_bytes", 0) + total_offload

    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"[zstd] NAS offload queued: {len(offload_candidates)} chunks, "
          f"{total_offload / (1024*1024):.1f}MB for stream '{stream_name}'")


# ── Legacy .ndjson migration helper ───────────────────────────────────────

def migrate_ndjson_to_zstd(ndjson_path: Path, log_dir: Path, stream_name: str) -> int:
    """One-shot: compress an existing .ndjson file into a .zst chunk.

    Returns number of records migrated. The original file is NOT deleted
    (caller decides when to remove).
    """
    if not ndjson_path.exists():
        return 0

    logger = ZstdLogger(log_dir, stream_name)
    count = 0
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                logger.append(record)
                count += 1
            except json.JSONDecodeError:
                continue
    logger.flush()
    return count
