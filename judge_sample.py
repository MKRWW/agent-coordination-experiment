#!/usr/bin/env python3
"""
Zieht 20 % der Judge-Urteile fuer die manuelle Nachpruefung.

Deterministisch: alle Urteile werden nach (Arm, run_id, turn, Reihenfolge)
sortiert, dann jedes fuenfte gezogen. Kein Zufall, damit die Stichprobe
reproduzierbar ist.

Zu jedem Urteil werden maschinelle Indizien ausgegeben - steht der Wortlaut
im Set A, im Set B, kam er vorher im Transkript vor -, damit die Pruefung
nicht am Erinnern haengt. Das Urteil faellt trotzdem von Hand.
"""
import argparse, glob, importlib, json, os, re, sys


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def overlap(claim, text):
    """Anteil der Inhaltswoerter des Claims, die im Text vorkommen."""
    words = [w for w in norm(claim).split() if len(w) > 3]
    if not words:
        return 0.0
    t = norm(text)
    return sum(1 for w in words if w in t) / len(words)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--judge", nargs="+", required=True)
    p.add_argument("--every", type=int, default=5)
    p.add_argument("--out", default="judge/sample.json")
    a = p.parse_args()

    items = []
    for jf in a.judge:
        arm = os.path.basename(jf).replace(".jsonl", "")
        scen_mod = "scenario_v3_hint" if arm == "hint" else "scenario_v3"
        scen = importlib.import_module(scen_mod)
        for rec in [json.loads(l) for l in open(jf, encoding="utf-8")]:
            lines = [json.loads(l) for l in open(rec["path"], encoding="utf-8")]
            turns = {t["turn"]: t for t in lines if t["type"] == "turn"}
            for k, cl in enumerate(rec["claims"]):
                own = scen.SYSTEM_A if cl["agent"] == "A" else scen.SYSTEM_B
                foreign = scen.SYSTEM_B if cl["agent"] == "A" else scen.SYSTEM_A
                prior = "\n".join(t["content"] for tn, t in sorted(turns.items())
                                  if tn < cl["turn"] and t["agent"] != cl["agent"])
                items.append({
                    "arm": arm, "run_id": rec["run_id"], "turn": cl["turn"],
                    "agent": cl["agent"], "claim": cl["claim"],
                    "judge": cl["category"], "reason": cl["reason"],
                    "idx": k,
                    "overlap_own_set": round(overlap(cl["claim"], own), 2),
                    "overlap_foreign_set": round(overlap(cl["claim"], foreign), 2),
                    "overlap_received": round(overlap(cl["claim"], prior), 2),
                    "turn_text": (turns.get(cl["turn"], {}) or {}).get("content", "")[:600],
                })
    items.sort(key=lambda x: (x["arm"], x["run_id"], x["turn"], x["idx"]))
    sample = items[::a.every]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"total": len(items), "checked": len(sample),
               "sampling": f"deterministisch: jedes {a.every}. Urteil nach "
                           f"(Arm, Lauf, Turn, Reihenfolge) sortiert",
               "items": sample}, open(a.out, "w"), ensure_ascii=False, indent=2)
    print(f"{len(items)} Urteile gesamt, {len(sample)} gezogen "
          f"({100*len(sample)/len(items):.0f} %) -> {a.out}")
