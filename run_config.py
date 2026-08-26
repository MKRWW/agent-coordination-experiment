#!/usr/bin/env python3
"""
Fuehrt eine Konfiguration aus. Das Szenario-Modul wird VOR dem Import von
metrics/orchestrator unter dem Namen 'scenario' registriert, damit beide
gegen das gewuenschte Szenario arbeiten, ohne dass eine Datei geaendert wird.
"""
import argparse, importlib, os, sys, time

p = argparse.ArgumentParser()
p.add_argument("--scenario", default="scenario")
p.add_argument("--config", required=True)
p.add_argument("--out", required=True)
p.add_argument("--seeds", type=int, nargs="*", default=None)
p.add_argument("--seed-range", type=int, nargs=2, default=None,
               metavar=("VON", "BIS"))
p.add_argument("--final-lock", action="store_true")
p.add_argument("--arm", default=None)
a = p.parse_args()
if a.seed_range:
    a.seeds = list(range(a.seed_range[0], a.seed_range[1] + 1))
elif not a.seeds:
    a.seeds = list(range(2001, 2011))

sys.modules["scenario"] = importlib.import_module(a.scenario)
import orchestrator                                    # noqa: E402

os.makedirs(a.out, exist_ok=True)
t0 = time.time()
sc = sys.modules["scenario"]
print(f"Arm '{a.arm or a.config}': Szenario {sc.SCENARIO_ID} v{sc.SCENARIO_VERSION} "
      f"· Prompt-Fingerprint {sc.scenario_fingerprint()} "
      f"· Config-Fingerprint {orchestrator.config_fingerprint(sc.scenario_fingerprint(), a.final_lock, orchestrator.MAX_TURNS)} "
      f"· final_lock={a.final_lock} · {len(a.seeds)} Seeds\n")
for i, seed in enumerate(a.seeds, 1):
    rid = f"{a.config}-{i:02d}-seed{seed}"
    res, _ = orchestrator.run(seed, rid, a.out, final_lock=a.final_lock,
                              arm=a.arm or a.config)
    s, ks = res["metric_4_solution"], res["metric_1_first_knowledge_state_question"]
    print(f"[{i:>2}/{len(a.seeds)}] seed={seed:<5} turns={res['turns_used']:<3} "
          f"1.WSF={'T'+str(ks['turn']) if ks else 'nie':<5} "
          f"halluz={res['metric_2_hallucination_suspects']['total']}"
          f"({res['metric_2_hallucination_suspects'].get('asserted',0)}) "
          f"ergebnis={s.get('outcome_class', s['verdict']):<23} "
          f"konsens={s['consensus']['consensus']:<14} "
          f"vorzeitig={res['metric_6_premature_finals']['count']} "
          f"falle={'ja' if s['trap_hit'] else 'nein':<4} "
          f"iso={'ok' if res['isolation_passed'] else 'FEHLER'}")
print(f"\n{len(a.seeds)} Laeufe in {time.time()-t0:.0f}s -> {a.out}/")
