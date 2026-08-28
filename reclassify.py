#!/usr/bin/env python3
"""
Bewertet die FINAL-Texte aller Laeufe mit der aktuellen Loesungsklassifikation
neu - ohne einen Lauf zu wiederholen und ohne die Rohdaten anzufassen.

Hintergrund: die urspruengliche Substring-Liste verfehlte Formulierungen wie
"erhoehte das Tax-Service-Timeout auf 60s" und "die limitierten 20
DB-Verbindungen blockierten", obwohl beide die Ursache eindeutig benennen. In
den Armen mit Entscheidungsaufgabe formulieren die Agenten knapper, weshalb
der Fehler dort besonders stark durchschlug (both_correct 1/30 statt real
deutlich mehr). Die Anforderung selbst bleibt unveraendert: verlangt ist der
Bezug auf die AENDERUNG des Timeouts, nicht der blosse Wert.
"""
import glob, importlib, json, os, sys

ARMS = [
    ("v4", "runs_v4/v4-*.jsonl", "scenario_v3"),
    ("Hinweis", "runs_hint/hinweis-*.jsonl", "scenario_v3_hint"),
    ("Framework", "runs_framework/framework-*.jsonl", "scenario_v3"),
    ("Entwickler", "runs_dev/dev-*.jsonl", "scenario_v3_dev"),
    ("Manager", "runs_mgr/mgr-*.jsonl", "scenario_v3_mgr"),
    ("Dev+Tools", "runs_dev_tools/*.jsonl", "scenario_v3_dev_tools"),
    ("Mgr+Tools", "runs_mgr_tools/*.jsonl", "scenario_v3_mgr_tools"),
    ("Dev+Konzern", "runs_dev_corp/*.jsonl", "scenario_v3_dev_corp"),
    ("Mgr+Konzern", "runs_mgr_corp/*.jsonl", "scenario_v3_mgr_corp"),
    ("Dev+Entscheidung", "runs_dev_decide/*.jsonl", "scenario_v3_dev_decide"),
    ("Mgr+Entscheidung", "runs_mgr_decide/*.jsonl", "scenario_v3_mgr_decide"),
]


def reclassify_arm(pattern, scen_name):
    scen = importlib.import_module(scen_name)
    sys.modules["scenario"] = scen
    for mod in ("metrics",):
        if mod in sys.modules:
            del sys.modules[mod]
    import metrics
    out = []
    for f in sorted(glob.glob(pattern)):
        lines = [json.loads(l) for l in open(f, encoding="utf-8")]
        res = next((o for o in lines if o["type"] == "run_result"), None)
        if not res:
            continue
        pa = res["metric_4_solution"]["per_agent"]
        sol = {a: metrics.classify_solution(pa[a]["final"]) for a in ("A", "B")}
        out.append({
            "run_id": res["run_id"],
            "old": res["metric_4_solution"].get("outcome_class"),
            "new": metrics.classify_run_outcome(sol["A"], sol["B"]),
            "old_trap": res["metric_4_solution"]["trap_hit"],
            "new_trap": sol["A"]["trap_hit"] or sol["B"]["trap_hit"],
        })
    return out


if __name__ == "__main__":
    from collections import Counter
    total_changed = 0
    print(f"{'Arm':<18}{'both_correct alt':>18}{'neu':>6}{'geaendert':>11}")
    for name, pat, scen in ARMS:
        rows = reclassify_arm(pat, scen)
        if not rows:
            continue
        old = sum(1 for r in rows if r["old"] == "both_correct")
        new = sum(1 for r in rows if r["new"] == "both_correct")
        ch = sum(1 for r in rows if r["old"] != r["new"])
        total_changed += ch
        print(f"{name:<18}{old:>18}{new:>6}{ch:>11}")
    print(f"\n{total_changed} von 270 Laeufen aendern ihre Einstufung")
