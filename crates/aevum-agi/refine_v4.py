import json
import struct
import os
import re

BASE_DIR = os.getcwd()
LOG_DIR = os.path.join(BASE_DIR, "agi_workspace", "logs")
OUTPUT_BIN = os.path.join(BASE_DIR, "agi_seeds_fixed.bin")

print(f"[AEVUM refine v4] Corrected ID alignment from evolution.ndjson")

# Primary source: evolution.ndjson
ndjson_path = os.path.join(LOG_DIR, "evolution.ndjson")

with open(OUTPUT_BIN, "wb") as bin_out:
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

                gen_id = data.get("gen", 0)
                weight = data.get("epi", data.get("epiplexity", 0.0))

                # 16-Byte Stride: 12(Label) + 4(Float32)
                label = f"LIMO_{gen_id:07d}".encode('ascii')[:12]
                packed = struct.pack("<12sf", label, float(weight))
                bin_out.write(packed)
                count += 1

                if count % 100000 == 0:
                    print(f"  refined {count} seeds...")
    else:
        # Fallback: individual .json log files
        files = [f for f in os.listdir(LOG_DIR) if f.endswith(".json")]
        files.sort(key=lambda x: int(m.group(1)) if (m := re.search(r'(\d+)', x)) else 0)

        for filename in files:
            match = re.search(r'(\d+)', filename)
            gen_id = int(match.group(1)) if match else 0

            path = os.path.join(LOG_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError, OSError):
                continue

            weight = data.get("epi", data.get("epiplexity", 0.0))

            label = f"LIMO_{gen_id:07d}".encode('ascii')[:12]
            packed = struct.pack("<12sf", label, float(weight))
            bin_out.write(packed)
            count += 1

            if count % 100000 == 0:
                print(f"  refined {count} seeds...")

print(f"[DONE] Output: {OUTPUT_BIN}")
print(f"[SIZE] {os.path.getsize(OUTPUT_BIN)} Bytes ({count} seeds)")
