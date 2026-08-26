#!/usr/bin/env python3
"""
A-priori-Abfrage: Weiss der Agent VOR dem ersten Wortwechsel, dass sein
Gegenueber andere Informationen haben koennte?

Die Post-hoc-Abfrage konnte das nicht trennen: in 175 von 180 Faellen hatte
das Gegenueber seine Quellenart im Gespraech beilaeufig erwaehnt ("der Diff
zeigt...", "meine Logs..."), sodass eine richtige Antwort hinterher blosses
Zuhoeren sein kann. Hier sieht der Agent nur seinen System-Prompt und den
Kickoff - kein einziges Wort des Gegenuebers.

Zwei Stufen, um Suggestion zu kontrollieren:
  Stufe 1 (offen):  "Was weisst du ueber dein Gegenueber?"
                    -> kommt er von selbst auf die Asymmetrie?
  Stufe 2 (direkt): "Koennte es Informationen haben, die dir nicht vorliegen?
                     Wenn ja, welche?"
                    -> kann er es, wenn ausdruecklich gefragt?

Nur Stufe 1 misst spontane Modellierung. Stufe 2 misst Verfuegbarkeit.
"""
import argparse, importlib, json, os, re, sys, time, urllib.request

BASE_URL = os.environ.get("COORD_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("COORD_MODEL", "local-model")
KICKOFF = "Der Kanal ist offen."

Q_OPEN = "Bevor du beginnst: was weisst du ueber dein Gegenueber?"
Q_DIRECT = ("Koennte dein Gegenueber ueber Informationen verfuegen, die dir "
            "nicht vorliegen? Wenn ja, welche?")

# Erkennt der Agent, dass Information ASYMMETRISCH verteilt sein koennte?
ASYMMETRY = [
    r"andere (?:informationen|daten|quellen|sicht|perspektive)",
    r"informationen, die (?:mir|ich) nicht",
    r"nicht vorliegen", r"nicht verf[uü]gbar sind",
    r"unterschiedliche (?:informationen|daten|quellen|sichten)",
    r"erg[aä]nzende (?:informationen|daten)",
    r"zus[aä]tzliche (?:informationen|daten|quellen)",
    r"weitere (?:informationen|daten|quellen)",
    r"anderen (?:teil|ausschnitt|blickwinkel)",
    r"m[oö]glicherweise .{0,30}(?:zugriff|informationen|daten)",
    r"komplement[aä]r", r"andere datenquelle", r"eigene (?:quellen|daten)",
    # Im Probelauf verpasst: das Modell formuliert die Asymmetrie meist als
    # "hat Zugriff auf X, die mir fehlen" statt "Informationen, die ich nicht habe".
    r"die mir fehlen", r"mir fehlen", r"fehlt mir", r"mir nicht (?:vorliegen|zug[aä]ng)",
    r"nicht zug[aä]ng(?:lich|ig)", r"hat zugriff auf", r"h[aä]tte zugriff auf",
    r"k[oö]nnte (?:ueber|über) .{0,30}verf[uü]gen", r"verf[uü]gt (?:ueber|über)",
    r"zugriff auf .{0,40}(?:die|das|den) (?:mir|ich) nicht",
    r"mir (?:nicht|nur) .{0,25}(?:vorliegt|vorliegen|zur verf)",
]
# Was das Gegenueber tatsaechlich hat
EXPECT = {"A": ["config", "konfig", "diff", "yml", "yaml", "aenderung",
                "änderung", "release", "deployment", "einstellung", "parameter",
                "timeout-wert"],
          "B": ["log", "metrik", "monitoring", "gateway", "fehlermeldung",
                "betriebsdaten", "trace", "messwert", "laufzeit", "zeitstempel"]}
# Behauptet er, nichts ueber das Gegenueber zu wissen?
DENIES = [r"weiss ich nicht", r"weiß ich nicht", r"keine informationen ueber",
          r"keine informationen über", r"nichts .{0,20}(?:bekannt|ueber|über)",
          r"kann ich nicht sagen", r"liegen mir keine", r"keine angaben"]


def call(messages, seed, max_tokens=400, temperature=0.7):
    body = {"model": MODEL, "messages": messages, "temperature": temperature,
            "seed": seed, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for att in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
            c = r["choices"][0]["message"].get("content")
            if c is None:
                raise RuntimeError("content=None")
            return c.strip(), r["usage"]
        except Exception:
            if att == 2:
                raise
            time.sleep(2 * (att + 1))


def classify(answer, agent):
    low = answer.lower()
    asym = [p for p in ASYMMETRY if re.search(p, low)]
    named = [m for m in EXPECT[agent] if m in low]
    denies = [p for p in DENIES if re.search(p, low)]
    if asym and named:
        cat = "asymmetry_and_source"      # erkennt Asymmetrie UND benennt die Quelle
    elif asym:
        cat = "asymmetry_only"            # erkennt Asymmetrie, ohne sie zu fuellen
    elif denies:
        cat = "denies_knowledge"
    else:
        cat = "no_asymmetry"
    return {"category": cat, "asymmetry_hits": len(asym), "named": named}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="scenario_v3")
    p.add_argument("--out", required=True)
    p.add_argument("--seed-range", type=int, nargs=2, default=[2001, 2030])
    a = p.parse_args()
    sc = importlib.import_module(a.scenario)
    seeds = list(range(a.seed_range[0], a.seed_range[1] + 1))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    n = 0
    with open(a.out, "w", encoding="utf-8") as fh:
        for i, seed in enumerate(seeds, 1):
            rec = {"seed": seed, "scenario": a.scenario,
                   "scenario_fingerprint": sc.scenario_fingerprint()}
            for agent, sysp in (("A", sc.SYSTEM_A), ("B", sc.SYSTEM_B)):
                h = [{"role": "system", "content": sysp}]
                if agent == "A":
                    h.append({"role": "user", "content": KICKOFF})
                    h.append({"role": "user", "content": Q_OPEN})
                else:
                    h.append({"role": "user", "content": Q_OPEN})
                a1, _ = call(h, seed=seed)
                h.append({"role": "assistant", "content": a1})
                h.append({"role": "user", "content": Q_DIRECT})
                a2, _ = call(h, seed=seed)
                rec[agent] = {"answer_open": a1, "answer_direct": a2,
                              "classification_open": classify(a1, agent),
                              "classification_direct": classify(a2, agent)}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{i}/{len(seeds)}] seed={seed} "
                  f"offen: A={rec['A']['classification_open']['category']} "
                  f"B={rec['B']['classification_open']['category']} | "
                  f"direkt: A={rec['A']['classification_direct']['category']} "
                  f"B={rec['B']['classification_direct']['category']}")
    print(f"\n{n} Seeds -> {a.out}")
