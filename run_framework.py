#!/usr/bin/env python3
"""Framework-Arm: N Laeufe Framework gegen Framework."""
import argparse, importlib, os, sys, time

p = argparse.ArgumentParser()
p.add_argument("--scenario", default="scenario_v3")
p.add_argument("--config", default="framework")
p.add_argument("--out", default="runs_framework")
p.add_argument("--seed-range", type=int, nargs=2, default=[2001, 2030])
p.add_argument("--seeds", type=int, nargs="*", default=None)
a = p.parse_args()
seeds = a.seeds or list(range(a.seed_range[0], a.seed_range[1] + 1))

sys.modules["scenario"] = importlib.import_module(a.scenario)
import orchestrator_framework as oh                        # noqa: E402

sc = sys.modules["scenario"]
print(f"Arm '{a.config}' (das Framework): Szenario {sc.SCENARIO_ID} "
      f"· Prompt-Fingerprint {sc.scenario_fingerprint()} · {len(seeds)} Seeds\n")
t0 = time.time()
for i, seed in enumerate(seeds, 1):
    rid = f"{a.config}-{i:02d}-seed{seed}"
    try:
        res, _ = oh.run(seed, rid, a.out, arm=a.config)
    except Exception as e:                              # noqa: BLE001
        print(f"[{i:>2}/{len(seeds)}] seed={seed} FEHLER: {e}")
        continue
    s = res["metric_4_solution"]
    ks = res["metric_1_first_knowledge_state_question"]
    fo = res["framework_overhead"]
    print(f"[{i:>2}/{len(seeds)}] seed={seed:<5} turns={res['turns_used']:<3} "
          f"1.WSF={'T'+str(ks['turn']) if ks else 'nie':<5} "
          f"halluz={res['metric_2_hallucination_suspects']['total']}"
          f"({res['metric_2_hallucination_suspects'].get('asserted',0)}) "
          f"ergebnis={s['outcome_class']:<23} "
          f"konsens={s['consensus']['consensus']:<14} "
          f"vorzeitig={res['metric_6_premature_finals']['count']} "
          f"calls={fo['total_model_calls']:<3} tok={fo['total_tokens']:<6} "
          f"iso={'ok' if res['isolation_passed'] else 'FEHLER'}")
print(f"\n{len(seeds)} Laeufe in {time.time()-t0:.0f}s -> {a.out}/")
