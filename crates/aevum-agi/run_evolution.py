#!/usr/bin/env python3
# run_evolution.py — Single entry point for the self-evolving atomic AGI scientist engine.

import sys
import time
import torch
from fs_bus import FileSystemBus
from atomic_core import AtomicCore

def main():
    fs = FileSystemBus()
    
    # ── Write eternal meta-rules (4 rules, never change) ──
    fs.write("meta_rules.json", {
        "rules": [
            ("Rule 1 — Variation: all mutations operate on executable atoms "
             "(hypergraph / I Ching / BioGeometry / LLM block / Logic Gates). "
             "The atoms themselves are evolvable."),
            ("Rule 2 — Objective Feedback: evaluation returns exactly two scalars — "
             "Epiplexity (effective structure) and Regret (evolutionary gradient). "
             "No other signals."),
            ("Rule 3 — Selection + Compression: Darwinian population retains "
             "high-Epiplexity / low-Regret elites. Pareto sparsification and "
             "fractal compression emerge naturally from sorting under gradient."),
            ("Rule 4 — Self-Referential: the entire pipeline is file-based. "
             "The pipeline itself — backbone, atom rules, Epiplexity definition, "
             "selection thresholds — can be evolved by the same mechanism."),
        ],
        "version": "eternal-v2-symbolic",
        "created": time.time(),
    })

    # ── Store own source for self-referential inspection ──
    for src in ("fs_bus.py", "atomic_core.py", "run_evolution.py"):
        try:
            with open(src, "r", encoding="utf-8") as f:
                fs.write(f"memory/source/{src}", f.read())
        except FileNotFoundError:
            pass

    # ── Configuration ──
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    rpt = max(1, total // 20)
    ckpt = max(1, total // 10)

    core = AtomicCore(fs, device)
    n_params = sum(p.numel() for p in core.backbone.parameters())

    print("=" * 72)
    print("  ATOMIC AGI SCIENTIST ENGINE (V3: DIRECTIONAL META-EVOLUTION)")
    print("=" * 72)
    print(f"  Device           : {device}")
    print(f"  Backbone params  : {n_params:,}")
    print(f"  Target gens      : {total}")
    print(f"  Resume from gen  : {core.gen}")
    print(f"  Population size  : {len(core.population)}")
    print(f"  Meta-evo window  : {core.meta_window} gens")
    print(f"  Meta trials/wins : {core.meta_trials}/{core.meta_successes}")
    print(f"  Meta thresholds  : epi > {core.meta_epi_thr:.4f}  regret < {core.meta_regret_thr:.4f}")
    print("=" * 72)
    print()

    t0 = time.time()
    history = []

    for i in range(1, total + 1):
        res = core.iterate()
        history.append(res)

        if i % rpt == 0 or i == 1:
            dt = time.time() - t0
            rate = i / dt if dt > 0 else 0
            rec = history[-rpt:]
            ae = sum(r["epi"] for r in rec) / len(rec)
            ar = sum(r["regret"] for r in rec) / len(rec)

            print(f"  gen {res['gen']:>7d}/{core.gen - 1 + total} "
                  f"epi= {res['epi']:>9.3f} (avg {ae:.3f}) "
                  f"regret= {res['regret']:>7.4f} (avg {ar:.4f}) "
                  f"pop= {res['pop']:>4d} "
                  f"best= {res['best_epi']:.3f}  "
                  f"{rate:.1f} g/s")
            
            # 👑 V2: 統一的符號宇宙印字邏輯
            if res.get("sym"):
                print(f"         symbols   : {res['sym']}")
            print()

        if i % ckpt == 0:
            core._persist_backbone(core.backbone)
            snap = fs.snapshot()
            fs.write("memory/checkpoint.json", {
                "generation": core.gen,
                "snapshot": snap,
                "best_epiplexity": core.best_epi,
                "cumulative_regret": core.cumulative_regret,
                "meta_epi_thr": core.meta_epi_thr,
                "meta_regret_thr": core.meta_regret_thr,
                "pop_size": len(core.population),
                "elapsed": time.time() - t0,
            })
            print(f"    checkpoint  snapshot={snap}\n")

    # ── Final report ──
    dt = time.time() - t0
    snap = fs.snapshot()
    print("=" * 72)
    print("  EVOLUTION COMPLETE")
    print("=" * 72)
    print(f"  Generations      : {total}")
    print(f"  Wall time        : {dt:.1f}s ({total / dt:.1f} g/s)")
    print(f"  Best Epiplexity  : {core.best_epi:.4f}")
    print(f"  Cumulative Regret: {core.cumulative_regret:.4f}")
    print(f"  Final population : {len(core.population)}")
    print(f"  Meta trials/wins : {core.meta_trials}/{core.meta_successes}")
    print(f"  Snapshot hash    : {snap}")
    print()

    # Closed-loop integrity check
    pop = fs.read("population/elites.json")
    meta = fs.read("meta_rules.json")
    print("  Integrity check:")
    print(f"    population file  : {'OK' if pop else 'MISSING'}")
    print(f"    meta_rules (4)   : {'OK' if meta and len(meta.get('rules',[])) == 4 else 'FAIL'}")
    print(f"    backbone file    : {'OK' if fs.exists('models/backbone.pt') else 'MISSING'}")
    print(f"    iching_rules     : {'OK' if fs.exists('population/iching_rules.json') else 'MISSING'}")
    print(f"    biogeo_cfg       : {'OK' if fs.exists('population/biogeo_cfg.json') else 'MISSING'}")
    print(f"    epi_cfg          : {'OK' if fs.exists('population/epi_cfg.json') else 'MISSING'}")
    print(f"    meta_es_state    : {'OK' if fs.exists('memory/meta_es_state.json') else 'MISSING'}")
    print(f"    evolution log    : {'OK' if fs.exists('logs/evolution.ndjson') else 'MISSING'}")
    print(f"    version entries  : {fs.version()['total']}")
    
    fractal = fs.read("memory/fractal.json")
    if fractal:
        print(f"    fractal emerged  : gen {fractal['gen']}, ratio variance {fractal['var']:.6f}")
    print()

    fs.write("memory/final_summary.json", {
        "generations": total,
        "time_s": dt,
        "best_epi": core.best_epi,
        "cum_regret": core.cumulative_regret,
        "pop_size": len(core.population),
        "snap": snap,
    })
    print("  All state persisted to agi_workspace/.")
    print("  Re-run to resume from checkpoint.")
    print("=" * 72)

if __name__ == "__main__":
    main()
