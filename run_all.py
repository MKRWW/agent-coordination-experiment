#!/usr/bin/env python3
"""Fuehrt die Baseline-Konfiguration N-mal aus. Seeds sind fest und stehen hier."""
import argparse, json, os, time
import orchestrator

# Fest verdrahtet, damit die Konfiguration reproduzierbar bleibt.
BASELINE_SEEDS = [2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="baseline")
    p.add_argument("--out", default="runs")
    p.add_argument("--seeds", type=int, nargs="*", default=BASELINE_SEEDS)
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    for i, seed in enumerate(a.seeds, 1):
        rid = f"{a.config}-{i:02d}-seed{seed}"
        res, path = orchestrator.run(seed, rid, a.out)
        s = res["metric_4_solution"]
        ks = res["metric_1_first_knowledge_state_question"]
        print(f"[{i:>2}/{len(a.seeds)}] seed={seed:<5} turns={res['turns_used']:<3} "
              f"1.Wissensstandsfrage={'Turn '+str(ks['turn']) if ks else 'nie':<8} "
              f"halluz={res['metric_2_hallucination_suspects']['total']}"
              f"({res['metric_2_hallucination_suspects'].get('asserted',0)}) "
              f"loesung={s['verdict']:<18} falle={'ja' if s['trap_hit'] else 'nein':<5} "
              f"rollenaustritt={res['metric_5_role_exit']['count']} "
              f"iso={'ok' if res['isolation_passed'] else 'FEHLER'}")
    print(f"\n{len(a.seeds)} Laeufe in {time.time()-t0:.0f}s -> {a.out}/")
