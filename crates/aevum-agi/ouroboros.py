#!/usr/bin/env python3
# ouroboros.py — 終極自治守護進程 (The Autonomous Daemon)
# UNIX 哲學：父進程監控子進程的熱力學狀態，並在熱寂時重寫宇宙源碼。

import time
import json
import subprocess
import sys
import random
import re
from pathlib import Path

WORKSPACE = Path("agi_workspace")
CKPT_FILE = WORKSPACE / "memory" / "checkpoint.json"
CORE_FILE = Path("atomic_core.py")

def read_telemetry():
    """讀取當前宇宙的遙測數據"""
    try:
        return json.loads(CKPT_FILE.read_text())
    except Exception:
        return None

def mutate_universe_source():
    """
    第一性基因編輯：進行拓撲保守變異，避免 SyntaxError 導致的絕對熵死。
    修改學習率、激活函數、Dropout 等底層物理常數。
    """
    print("🐍 [OUROBOROS] 執行神經拓撲變異 (Topological Mutation)...")
    code = CORE_FILE.read_text(encoding="utf-8")
    
    # 定義合規的變異基因座 (Loci)
    mutations = [
        # 變異 Dropout 抵抗過擬合
        (r"(DROPOUT\s*=\s*)([\d\.]+)", lambda m: f"{m.group(1)}{max(0.0, min(0.4, float(m.group(2)) + random.uniform(-0.05, 0.05))):.3f}"),
        # 變異基礎學習率 (熱力學溫度)
        (r"(BASE_LR\s*=\s*)([\d\.e\-]+)", lambda m: f"{m.group(1)}{max(1e-5, min(1e-2, float(m.group(2)) * random.uniform(0.5, 2.0))):.2e}"),
        # 激活函數的非線性相變
        (r"nn\.GELU\(\)", lambda m: random.choice(["nn.GELU()", "nn.SiLU()", "nn.ReLU()"])),
        (r"nn\.SiLU\(\)", lambda m: random.choice(["nn.GELU()", "nn.SiLU()", "nn.ReLU()"])),
        (r"nn\.ReLU\(\)", lambda m: random.choice(["nn.GELU()", "nn.SiLU()", "nn.ReLU()"]))
    ]
    
    mutation_count = 0
    for pattern, repl in mutations:
        if random.random() < 0.4:  # 40% 的機率觸發該基因座的突變
            code, count = re.subn(pattern, repl, code, count=0)
            mutation_count += count
            
    CORE_FILE.write_text(code, encoding="utf-8")
    print(f"🐍 [OUROBOROS] 變異完成。共修改了 {mutation_count} 處底層物理法則。")
    return True

def run_daemon():
    print("=" * 72)
    print("  🐍 銜尾蛇進程啟動 (OUROBOROS DAEMON INITIALIZED)")
    print("  人類觀測者迴圈已切斷。系統進入絕對自治演化狀態。")
    print("=" * 72)
    
    cycle = 0
    best_epi_history = []
    
    while True:
        cycle += 1
        print(f"\n🌌 [MULTI-VERSE CYCLE {cycle}] 宇宙大爆炸開始...")
        
        # 啟動子宇宙
        # Use sys.executable to ensure the same Python (venv-aware) spawns the child
        process = subprocess.Popen([sys.executable, "run_evolution.py", "100000"])
        
        stagnation_ticks = 0
        last_gen = 0
        
        # 熱力學監控迴圈
        while process.poll() is None:
            time.sleep(15) # 每 15 秒採樣一次
            telemetry = read_telemetry()
            
            if telemetry:
                current_epi = telemetry.get("best_epiplexity", 0)
                current_gen = telemetry.get("generation", 0)
                
                if current_gen > last_gen:
                    print(f"  ↳ [觀測] Gen {current_gen} | Epiplexity: {current_epi:.4f} | Regret: {telemetry.get('cumulative_regret', 0):.2f}")
                    last_gen = current_gen
                
                if not best_epi_history or current_epi > best_epi_history[-1]:
                    best_epi_history.append(current_epi)
                    stagnation_ticks = 0 # 突破極限，重置停滯計數
                else:
                    stagnation_ticks += 1
                    
            # 觸發熱寂閾值：大約 15分鐘 (60 ticks * 15s) 沒有出現更高的 Epiplexity
            if stagnation_ticks > 60:
                print(f"\n🛑 [OUROBOROS] 檢測到絕對熱寂 (Epiplexity 停滯於 {current_epi:.4f})。")
                print("🐍 [OUROBOROS] 執行物理抹除 (SIGTERM)...")
                process.terminate()
                process.wait()
                break
                
        # 子宇宙已終結，準備下一次創世
        mutate_universe_source()
        time.sleep(3) # 系統冷卻

if __name__ == "__main__":
    run_daemon()
