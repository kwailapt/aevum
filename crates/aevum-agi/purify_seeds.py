import json
import struct
import os
import sys

BASE_DIR = os.getcwd()
LOG_DIR = os.path.join(BASE_DIR, "agi_workspace", "logs")
OUTPUT_SEED = os.path.join(BASE_DIR, "agi_seeds.bin")

print(f"[AEVUM purify] Target: evolution.ndjson log extraction")
print(f"[scan] Directory: {LOG_DIR}")

if not os.path.exists(LOG_DIR):
    print(f"[ERROR] Log directory not found: {LOG_DIR}")
    sys.exit(1)

# Primary source: evolution.ndjson (NDJSON format, one JSON per line)
ndjson_path = os.path.join(LOG_DIR, "evolution.ndjson")

with open(OUTPUT_SEED, "wb") as bin_out:
    count = 0

    if os.path.exists(ndjson_path):
        with open(ndjson_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                gen = data.get("gen", 0)
                weight = data.get("epi", data.get("epiplexity", 0.0))

                # 16-Byte Stride: 12(Label) + 4(Float32)
                label = f"LIMO_{gen:07d}".encode('ascii')[:12]
                packed = struct.pack("<12sf", label, float(weight))
                bin_out.write(packed)
                count += 1

                if count % 50000 == 0:
                    print(f"  progress: {count} seeds extracted...")
    else:
        # Fallback: individual .json log files
        log_files = [f for f in os.listdir(LOG_DIR) if f.endswith(".json")]
        log_files.sort()
        for filename in log_files:
            path = os.path.join(LOG_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError, OSError):
                continue

            gen = data.get("gen", 0)
            weight = data.get("epi", data.get("epiplexity", 0.0))

            label = f"LIMO_{gen:07d}".encode('ascii')[:12]
            packed = struct.pack("<12sf", label, float(weight))
            bin_out.write(packed)
            count += 1

            if count % 50000 == 0:
                print(f"  progress: {count} seeds extracted...")

print("-" * 60)
print(f"[DONE] Total seeds extracted: {count}")
print(f"[FILE] {OUTPUT_SEED}")
print(f"[SIZE] {os.path.getsize(OUTPUT_SEED)} Bytes")
print("-" * 60)
