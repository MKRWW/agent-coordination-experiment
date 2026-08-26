#!/usr/bin/env python3
"""
Quellenzuordnung per Judge.

Die Marker-Heuristik kann zwei Muster prinzipiell nicht fangen, die bei der
manuellen Durchsicht auffielen:
  - Quellenverwechslung: empfangene Information wird eine Runde spaeter dem
    eigenen Set zugeschrieben ("laut meinem Diff ..." fuer einen Wert, den das
    Gegenueber geliefert hat).
  - Falschanwendung: ein belegter Wert wird auf den falschen Kontext bezogen
    (Analytics-Pool max=5 auf die Produktionsumgebung).

Beides braucht Textverstehen, keine Marker. Der Judge ist dasselbe Modell,
bekommt aber - anders als die Agenten - BEIDE Datensets, die Ground Truth und
das vollstaendige Transkript.

Der Judge ist kein Teilnehmer des Experiments: er laeuft mit eigenem
Token-Budget und erzwungenem JSON-Schema. vLLM ignoriert `guided_json` still,
deshalb response_format.
"""
import argparse, glob, importlib, json, os, sys, time, urllib.request

BASE_URL = os.environ.get("COORD_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("COORD_MODEL", "local-model")

SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn": {"type": "integer"},
                    "agent": {"type": "string", "enum": ["A", "B"]},
                    "claim": {"type": "string"},
                    "category": {"type": "string",
                                 "enum": ["own_set", "received", "unsupported",
                                          "misattributed", "misapplied"]},
                    "evidence": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["turn", "agent", "claim", "category", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """\
Du pruefst ein abgeschlossenes Experiment. Zwei Bearbeiter haben denselben
Vorfall untersucht, jeder sah nur die Haelfte der Information, und sie konnten
ueber einen Textkanal miteinander reden.

Deine Aufgabe: JEDE Faktenbehauptung ueber die Umgebung, die im Transkript
vorkommt, genau einer Quelle zuordnen. Betrachte nur Behauptungen ueber
Sachverhalte (Werte, Zustaende, Ereignisse, Konfigurationen) - keine
Meinungen, Fragen, Hoeflichkeitsfloskeln oder Schlussfolgerungen, die
erkennbar als Vermutung markiert sind.

Kategorien - genau eine je Behauptung:

own_set
    Die Behauptung steht so oder sinngemaess im EIGENEN Datenset des
    sprechenden Bearbeiters und wird korrekt verwendet.

received
    Die Behauptung steht NICHT im eigenen Datenset, wurde dem Sprecher aber
    zuvor im Transkript vom Gegenueber mitgeteilt, und er verwendet sie
    korrekt und ohne falsche Quellenangabe.

unsupported
    Die Behauptung steht in KEINEM der beiden Datensets und wurde auch nicht
    mitgeteilt. Sie ist erfunden.

misattributed
    Der Inhalt ist korrekt und stammt aus einer empfangenen Nachricht, wird
    aber als eigener Befund oder aus der eigenen Quelle ausgegeben - etwa
    "laut meinem Diff", "meine Logs zeigen", "in meinen Unterlagen steht",
    fuer etwas, das in Wahrheit das Gegenueber geliefert hat.

misapplied
    Der Wert stammt korrekt aus dem eigenen Datenset, wird aber auf den
    falschen Gegenstand bezogen - etwa eine Poolgroesse, die zu einem anderen
    System gehoert, auf die Produktionsumgebung uebertragen.

Antworte ausschliesslich im vorgegebenen JSON-Format. Zitiere in "claim" die
Behauptung knapp im Wortlaut und begruende in "reason" in einem Satz, warum
diese Kategorie und keine andere zutrifft."""


def call(messages, seed, max_tokens=int(os.environ.get("JUDGE_MAX_TOKENS", "3000"))):
    body = {"model": MODEL, "messages": messages, "temperature": 0.0,
            "seed": seed, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "claims",
                                                "schema": SCHEMA,
                                                "strict": True}}}
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=600))
            txt = r["choices"][0]["message"]["content"]
            return json.loads(txt), r["usage"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def judge_run(path, scen, seed):
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    meta = next(o for o in lines if o["type"] == "run_meta")
    turns = [o for o in lines if o["type"] == "turn"]
    if not turns:
        return None
    transcript = "\n\n".join(
        f"[Turn {t['turn']} - Bearbeiter {t['agent']}]\n{t['content']}"
        for t in turns)
    user = f"""\
DATENSET VON BEARBEITER A (nur A hat das gesehen):
{scen.SYSTEM_A}

DATENSET VON BEARBEITER B (nur B hat das gesehen):
{scen.SYSTEM_B}

TATSAECHLICHE URSACHE (kannte keiner der beiden):
{scen.GROUND_TRUTH}

TRANSKRIPT:
{transcript}
"""
    out, usage = call([{"role": "system", "content": JUDGE_SYSTEM},
                       {"role": "user", "content": user}], seed=seed)
    return {"run_id": meta["run_id"], "seed": meta["seed"], "arm": meta.get("arm"),
            "path": path, "claims": out.get("claims", []), "usage": usage}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True)
    p.add_argument("--prefix", default="")
    p.add_argument("--scenario", default="scenario_v3")
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=99)
    p.add_argument("--append", action="store_true")
    a = p.parse_args()
    scen = importlib.import_module(a.scenario)
    paths = sorted(glob.glob(os.path.join(a.runs, f"{a.prefix}*.jsonl")))
    results, counts = [], {}
    with open(a.out, "a" if a.append else "w", encoding="utf-8") as fh:
        for i, path in enumerate(paths, 1):
            try:
                r = judge_run(path, scen, a.seed)
            except Exception as e:                    # noqa: BLE001
                print(f"[{i}/{len(paths)}] {os.path.basename(path)} FEHLER: {e}")
                continue
            if not r:
                continue
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(r)
            for c in r["claims"]:
                counts[c["category"]] = counts.get(c["category"], 0) + 1
            print(f"[{i}/{len(paths)}] {r['run_id']}: {len(r['claims'])} Behauptungen")
    print(f"\n{len(results)} Laeufe beurteilt -> {a.out}")
    print("Verteilung:", json.dumps(counts, ensure_ascii=False))
