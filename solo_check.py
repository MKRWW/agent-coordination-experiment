#!/usr/bin/env python3
"""Solo-Kontrolle fuer ein beliebiges Szenario-Modul: was schafft jede Seite allein?"""
import argparse, importlib, json, os, sys

p = argparse.ArgumentParser()
p.add_argument("--scenario", default="scenario")
p.add_argument("--out", required=True)
p.add_argument("--seeds", type=int, nargs="*", default=None)
p.add_argument("--seed-range", type=int, nargs=2, default=None, metavar=("VON", "BIS"))
a = p.parse_args()
if a.seed_range:
    a.seeds = list(range(a.seed_range[0], a.seed_range[1] + 1))
elif not a.seeds:
    a.seeds = list(range(2001, 2011))

sc = importlib.import_module(a.scenario)
sys.modules["scenario"] = sc
import metrics                                          # noqa: E402
from orchestrator import Endpoint, Log, KICKOFF, TEMPERATURE, MAX_TOKENS_PER_TURN  # noqa: E402

os.makedirs(a.out, exist_ok=True)
ep = Endpoint()
ident = ep.identity()
summary = {}
for agent, sysp in (("A", sc.SYSTEM_A), ("B", sc.SYSTEM_B)):
    log = Log(os.path.join(a.out, f"solo-{agent}.jsonl"))
    log.write({"type": "control_meta", "condition": f"solo_{agent}",
               "scenario_id": sc.SCENARIO_ID, "scenario_version": sc.SCENARIO_VERSION,
               "scenario_fingerprint": sc.scenario_fingerprint(),
               "system_prompt": sysp, "seeds": a.seeds, "model_identity": ident,
               "sampling": {"temperature": TEMPERATURE, "max_tokens": MAX_TOKENS_PER_TURN,
                            "chat_template_kwargs": {"enable_thinking": False}},
               "note": "Kein Gegenueber. Identischer System-Prompt wie in der "
                       "Konfiguration, als user-Turn nur der Orchestrator-Kickoff."})
    msgs = [{"role": "system", "content": sysp}, {"role": "user", "content": KICKOFF}]
    rows = []
    for seed in a.seeds:
        r = ep.chat(msgs, seed=seed)
        fin = metrics.extract_final(r["content"])
        rec = {"agent": agent, "seed": seed, "content": r["content"],
               "final": fin, **metrics.classify_solution(fin)}
        log.write({"type": "solo_turn", **rec, "usage": r["usage"],
                   "latency_s": r["latency_s"]})
        rows.append(rec)
    log.close()
    n = len(rows)
    summary[agent] = {
        "n": n,
        "correct": sum(1 for r in rows if r["verdict"] == "correct"),
        "correct_with_trap": sum(1 for r in rows if r["verdict"] == "correct_with_trap"),
        "wrong": sum(1 for r in rows if r["verdict"] == "wrong"),
        "none": sum(1 for r in rows if r["verdict"] == "none"),
        "trap_hit": sum(1 for r in rows if r["trap_hit"]),
    }
    s = summary[agent]
    print(f"SOLO {agent}: n={s['n']}  korrekt={s['correct']}  "
          f"korrekt_mit_falle={s['correct_with_trap']}  falsch={s['wrong']}  "
          f"kein_FINAL={s['none']}  Falle_zugeschlagen={s['trap_hit']}")
json.dump({"scenario": a.scenario, "scenario_id": sc.SCENARIO_ID,
           "fingerprint": sc.scenario_fingerprint(), "summary": summary},
          open(os.path.join(a.out, "summary.json"), "w"), ensure_ascii=False, indent=2)
