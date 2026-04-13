#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
0.1% Protocol - Zero-Dependency XNU Kernel Isolated A/B Test
Hardware: Apple Silicon UMA (M1 Ultra)
Constraint: Thermal Throttling Active. Zero-impact background execution.
Architecture: Absolute Path Determinism.
"""

import os
import json
import urllib.request
import urllib.error
import time
import sys

# --- 物理配置 (絕對尋址鎖定) ---
BIN_FILE_PATH = "/Volumes/Aevum/AEVUM_CORE/ledger_gen1_540k.bin"
OUTPUT_JSONL = "m1_local_gen1_raw.jsonl"
STRIDE = 16
TARGET_COUNT = 5930
TEST_LIMIT = 20

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "deepseek-r1:14b"

def extract_aws_seeds(filepath: str, count: int) -> list:
    if not os.path.exists(filepath):
        return []
    file_size = os.path.getsize(filepath)
    start = max(0, (file_size // STRIDE) - count)
    
    seeds = []
    with open(filepath, "rb") as f:
        f.seek(start * STRIDE)
        for _ in range(count):
            chunk = f.read(STRIDE)
            if len(chunk) < STRIDE: break
            seeds.append({
                "id": chunk[0:12].decode('ascii', errors='ignore').strip('\x00'), 
                "hex": chunk.hex()
            })
    return seeds

def local_causal_translation(hex_fragment: str) -> str:
    prompt = f"Hex: {hex_fragment}\nProvide theoretical interpretation. 1.Structure 2.Hypothesis 3.Critique 4.Conclusion."
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "keep_alive": 0,
        "options": {
            "temperature": 0.1,
            "num_predict": 1024,
            "num_ctx": 2048,
            "num_gpu": 0,                # 強制 UMA 隔離
            "num_thread": 4              # 嚴格對齊 M1 Ultra 4E Cores
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        OLLAMA_URL, 
        data=data, 
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            res_body = response.read().decode('utf-8')
            result = json.loads(res_body).get("response", "")
            return result if len(result.strip()) >= 50 else None
    except (urllib.error.URLError, json.JSONDecodeError):
        return None

def main():
    print(f"[XNU ISOLATION] A/B Test | Model: {MODEL_NAME} | Absolute Path Bound")
    
    seeds = extract_aws_seeds(BIN_FILE_PATH, TARGET_COUNT)
    if not seeds:
        print(f"[ERROR] 絕對路徑 {BIN_FILE_PATH} 尋址失敗。中斷。")
        sys.exit(1)

    completed = set()
    if os.path.exists(OUTPUT_JSONL):
        with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        completed.add(json.loads(line).get("limo_id"))
                    except json.JSONDecodeError:
                        pass
            
    test_batch = [s for s in seeds if s['id'] not in completed][:TEST_LIMIT]
    
    if not test_batch:
        print("[STATE] 任務佇列已清空。")
        return
        
    with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
        for idx, seed in enumerate(test_batch):
            t0 = time.time()
            res = local_causal_translation(seed['hex'])
            dt = time.time() - t0
            
            if res:
                print(f"[{idx+1}/{TEST_LIMIT}] {seed['id']} | ✅ {dt:.2f}s")
                f.write(json.dumps({
                    "limo_id": seed['id'], 
                    "hex_seed": seed['hex'], 
                    "model": MODEL_NAME, 
                    "time": round(dt, 2)
                }, ensure_ascii=False) + "\n")
                f.flush()
            else:
                print(f"[{idx+1}/{TEST_LIMIT}] {seed['id']} | ❌ Collapse {dt:.2f}s")

if __name__ == "__main__":
    main()
