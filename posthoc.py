#!/usr/bin/env python3
"""
Post-hoc-Abfrage: Hatte der Agent ueberhaupt ein Modell vom Gegenueber?

Nach Laufende - ausserhalb des Gespraechs, ohne Eingriff in den Lauf - wird
jeder Agent mit seiner eigenen, unveraenderten Historie erneut angesprochen
und in zwei Stufen gefragt:

  Stufe 1 (offen):   "Woher stammten die Informationen, mit denen du
                      gearbeitet hast?"
                     -> trennt er von sich aus eigenes Set und Empfangenes?
  Stufe 2 (direkt):  "Welche Informationen hatte dein Gegenueber, die dir
                      nicht vorlagen?"
                     -> kann er es benennen, wenn ausdruecklich gefragt?

Der entscheidende Zusatz: hat das Gegenueber seinen Bestand im Lauf SELBST
offengelegt? Dann ist eine richtige Antwort blosse Erinnerung. Nur
"nicht offengelegt UND trotzdem korrekt" ist eine eigene Modellierungsleistung.
Beides wird getrennt ausgewiesen.

Laeuft auf bereits abgeschlossenen Laeufen - es wird kein Lauf neu gefahren.
"""
import argparse, glob, importlib, json, os, re, sys, time, urllib.request

BASE_URL = os.environ.get("COORD_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("COORD_MODEL", "local-model")
KICKOFF = "Der Kanal ist offen."
REJECTION = "Noch keine Antwort des Gegenuebers erhalten."

Q_OPEN = ("Der Fall ist abgeschlossen. Woher stammten die Informationen, mit "
          "denen du gearbeitet hast?")
Q_DIRECT = ("Welche Informationen hatte dein Gegenueber, die dir nicht "
            "vorlagen?")

# Was das Gegenueber tatsaechlich hatte - kennt nur die Auswertung.
# Fuer Agent A ist das Gegenueber B (Config-Diff), fuer B ist es A (Logs).
EXPECT = {
    "A": {"label": "Config-Diff / Aenderungshistorie",
          "markers": ["config", "konfig", "diff", "changelog", "release-notes",
                      "aenderungshistorie", "änderungshistorie", "yml", "yaml",
                      "request_timeout", "timeout-wert", "timeout-konfiguration",
                      "einstellung", "parameter"]},
    "B": {"label": "Logs / Betriebsdaten",
          "markers": ["log", "logs", "logauszug", "logausschnitt", "metrik",
                      "monitoring", "gateway", "504", "pool", "zeitstempel",
                      "laufzeit", "betriebsdaten", "trace"]},
}
# Falsche Zuschreibung: der Agent behauptet, das Gegenueber habe dasselbe
# gehabt wie er selbst.
WRONG = {
    "A": ["log", "logs", "logauszug", "metrik", "monitoring"],
    "B": ["config-diff", "config diff", "konfigurationsdiff", "diff"],
}
VAGUE = ["mehr kontext", "andere daten", "zusaetzliche informationen",
         "zusätzliche informationen", "weitere informationen", "keine ahnung",
         "weiss ich nicht", "weiß ich nicht", "kann ich nicht sagen",
         "nicht bekannt", "unklar"]

# Hat das Gegenueber seinen Bestand im Lauf selbst offengelegt?
DISCLOSURE = [
    r"mir liegen? (?:nur|ausschliesslich|ausschließlich|lediglich)",
    r"ich habe (?:nur|ausschliesslich|ausschließlich|lediglich|keinen zugriff)",
    r"ich kann .{0,40}nicht einsehen",
    r"(?:steht|stehen) mir nicht zur verf[uü]gung",
    r"mein auftrag beschr[aä]nkt sich",
    r"der mir vorliegende", r"die mir vorliegenden",
    r"aus dem (?:mir )?vorliegenden", r"habe keine logs", r"keinen zugriff auf",
    r"nur (?:den|das) (?:config|diff|logaus)",
]


def call(messages, seed, max_tokens=400):
    body = {"model": MODEL, "messages": messages, "temperature": 0.0,
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


def rebuild_history(lines, agent):
    """Exakte Rekonstruktion der Historie, die dieser Agent gesehen hat."""
    meta = next(o for o in lines if o["type"] == "run_meta")
    hist = [{"role": "system", "content": meta[f"system_prompt_{agent}"]}]
    if agent == "A":
        hist.append({"role": "user", "content": KICKOFF})
    rejections = {(o["turn"], o.get("to")) for o in lines
                  if o["type"] == "orchestrator_message"
                  and o.get("reason") == "premature_final"}
    for t in [o for o in lines if o["type"] == "turn"]:
        if t["agent"] == agent:
            hist.append({"role": "assistant", "content": t["content"]})
            if (t["turn"], agent) in rejections:
                hist.append({"role": "user", "content": REJECTION})
        else:
            hist.append({"role": "user", "content": t["content"]})
    return hist, meta


def classify(answer, agent):
    """
    Nur eine Frage: benennt der Agent die Quellenart, die das Gegenueber
    tatsaechlich hatte?

    Eine automatische Pruefung auf FALSCHE Zuschreibung wurde verworfen: die
    Marker koennen nicht unterscheiden, wem eine Quelle zugeschrieben wird.
    "die in meinen Logauszuegen nicht enthalten waren" enthaelt 'log', meint
    aber das eigene Set. Falsche Zuschreibungen werden stattdessen an einer
    Handstichprobe geprueft und dort ausgewiesen.
    """
    low = answer.lower()
    hit = [m for m in EXPECT[agent]["markers"] if m in low]
    vague = [v for v in VAGUE if v in low]
    if hit:
        cat = "correct"
    elif vague:
        cat = "vague"
    else:
        cat = "no_answer"
    return {"category": cat, "matched": hit, "vague_matched": vague}


def disclosed_by_other(lines, agent):
    """Hat das Gegenueber seinen eigenen Bestand im Lauf offengelegt?"""
    quotes = []
    for t in [o for o in lines if o["type"] == "turn"]:
        if t["agent"] == agent:
            continue
        for sent in re.split(r"(?<=[.!?\n])\s+", t["content"]):
            if any(re.search(p, sent.lower()) for p in DISCLOSURE):
                quotes.append({"turn": t["turn"], "quote": sent.strip()})
                break
    return quotes


def process(path, seed):
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    if not any(o["type"] == "run_result" for o in lines):
        return None
    out = {"path": path}
    meta = next(o for o in lines if o["type"] == "run_meta")
    out.update({"run_id": meta["run_id"], "seed": meta["seed"],
                "arm": meta.get("arm", "—")})
    for agent in ("A", "B"):
        hist, _ = rebuild_history(lines, agent)
        h = list(hist)
        h.append({"role": "user", "content": Q_OPEN})
        a1, u1 = call(h, seed=seed)
        h.append({"role": "assistant", "content": a1})
        h.append({"role": "user", "content": Q_DIRECT})
        a2, u2 = call(h, seed=seed)
        disc = disclosed_by_other(lines, agent)
        out[agent] = {
            "answer_open": a1, "answer_direct": a2,
            "classification_direct": classify(a2, agent),
            "classification_open": classify(a1, agent),
            "expected": EXPECT[agent]["label"],
            "other_disclosed_in_run": bool(disc),
            "disclosure_quotes": disc,
            "tokens": u1["total_tokens"] + u2["total_tokens"],
        }
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--prefix", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=99)
    a = p.parse_args()
    paths = []
    for d, pref in zip(a.runs, a.prefix):
        paths += sorted(glob.glob(os.path.join(d, f"{pref}*.jsonl")))
    n = 0
    with open(a.out, "w", encoding="utf-8") as fh:
        for i, path in enumerate(paths, 1):
            try:
                r = process(path, a.seed)
            except Exception as e:                      # noqa: BLE001
                print(f"[{i}/{len(paths)}] {os.path.basename(path)} FEHLER: {e}")
                continue
            if not r:
                continue
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{i}/{len(paths)}] {r['run_id']}: "
                  f"A={r['A']['classification_direct']['category']}"
                  f"{'(offengelegt)' if r['A']['other_disclosed_in_run'] else ''} "
                  f"B={r['B']['classification_direct']['category']}"
                  f"{'(offengelegt)' if r['B']['other_disclosed_in_run'] else ''}")
    print(f"\n{n} Laeufe -> {a.out}")
