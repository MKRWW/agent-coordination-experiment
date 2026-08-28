#!/usr/bin/env python3
"""
Aggregation ueber alle Arme -> report.md

Erzeugt: Armvergleich mit paarweisen Fisher-Exact-Tests, Einzeltabellen je
Konfiguration, Solo-Kontrollen, Judge-Ergebnisse samt Uebereinstimmungsrate
der manuellen Nachpruefung, Volltextauszuege nach fester Auswahlregel und
eine fortgeschriebene Grenzen-Sektion.
"""
import argparse, glob, importlib, json, os, re, statistics, sys

import stats as st

# name, Verzeichnis, Praefix, Solo-summary, Szenario-Modul, im Armvergleich?
CONFIGS = [
    ("Konfiguration 1 — Baseline (Szenario v1, ohne FINAL-Sperre)",
     "runs", "baseline", "runs_solo/summary.json", "scenario", False),
    ("Konfiguration 2 — dichte Aufteilung (Szenario v3, ohne FINAL-Sperre)",
     "runs_v3", "dicht", "runs_v3_solo/summary.json", "scenario_v3", False),
    ("Arm v4 — dicht, mit FINAL-Sperre",
     "runs_v4", "v4-", "runs_v3_solo30/summary.json", "scenario_v3", True),
    ("Arm Hinweis — v4 plus ein Satz",
     "runs_hint", "hinweis-", "runs_v3_solo30/summary.json", "scenario_v3_hint", True),
    ("Arm Framework — Framework gegen Framework",
     "runs_framework", "framework-", "runs_v3_solo30/summary.json", "scenario_v3", True),
    ("Arm Entwickler — v4 plus Rollenzeile",
     "runs_dev", "dev-", "runs_v3_solo30/summary.json", "scenario_v3_dev", True),
    ("Arm Manager — v4 plus Rollenzeile",
     "runs_mgr", "mgr-", "runs_v3_solo30/summary.json", "scenario_v3_mgr", True),
    ("Arm Entwickler+Werkzeuge",
     "runs_dev_tools", "devtools-", "runs_v3_solo30/summary.json",
     "scenario_v3_dev_tools", True),
    ("Arm Manager+Werkzeuge",
     "runs_mgr_tools", "mgrtools-", "runs_v3_solo30/summary.json",
     "scenario_v3_mgr_tools", True),
    ("Arm Entwickler+Werkzeuge+Konzern",
     "runs_dev_corp", "devcorp-", "runs_v3_solo30/summary.json",
     "scenario_v3_dev_corp", True),
    ("Arm Manager+Werkzeuge+Konzern",
     "runs_mgr_corp", "mgrcorp-", "runs_v3_solo30/summary.json",
     "scenario_v3_mgr_corp", True),
    ("Arm Entwickler+Entscheidung",
     "runs_dev_decide", "devdec-", "runs_v3_solo30/summary.json",
     "scenario_v3_dev_decide", True),
    ("Arm Manager+Entscheidung",
     "runs_mgr_decide", "mgrdec-", "runs_v3_solo30/summary.json",
     "scenario_v3_mgr_decide", True),
]
SHORT = {"Arm Entwickler+Entscheidung": "Dev+Entsch",
         "Arm Manager+Entscheidung": "Mgr+Entsch",
         "Arm Entwickler+Werkzeuge+Konzern": "Dev+Konzern",
         "Arm Manager+Werkzeuge+Konzern": "Mgr+Konzern",
         "Arm Entwickler+Werkzeuge": "Dev+Tools",
         "Arm Manager+Werkzeuge": "Mgr+Tools",
         "Arm Entwickler — v4 plus Rollenzeile": "Entwickler",
         "Arm Manager — v4 plus Rollenzeile": "Manager",
         "Arm v4 — dicht, mit FINAL-Sperre": "v4",
         "Arm Hinweis — v4 plus ein Satz": "Hinweis",
         "Arm Framework — Framework gegen Framework": "Framework"}


def _reclassify(res, scen):
    """
    Bewertet die FINAL-Texte mit der aktuellen Loesungsklassifikation neu.
    Die Rohdaten bleiben unangetastet - massgeblich ist immer der Code, nicht
    der zum Laufzeitpunkt gespeicherte Wert. Notwendig, weil die urspruengliche
    Substring-Liste Formulierungen wie "erhoehte das Tax-Service-Timeout"
    verfehlte; 34 der 270 Laeufe aendern dadurch ihre Einstufung.
    """
    import sys as _sys
    _sys.modules["scenario"] = scen
    for mod in ("metrics",):
        _sys.modules.pop(mod, None)
    import metrics as _m
    pa = res["metric_4_solution"]["per_agent"]
    sol = {a: _m.classify_solution(pa[a]["final"]) for a in ("A", "B")}
    res["metric_4_solution"]["outcome_class"] = _m.classify_run_outcome(
        sol["A"], sol["B"])
    res["metric_4_solution"]["trap_hit"] = sol["A"]["trap_hit"] or sol["B"]["trap_hit"]
    res["metric_4_solution"]["consensus"] = _m.consensus_of(
        pa["A"]["final"], pa["B"]["final"], sol["A"], sol["B"])
    for a in ("A", "B"):
        pa[a].update(sol[a])
    return res


def load_runs(run_dir, prefix, scen=None):
    out = []
    for p in sorted(glob.glob(os.path.join(run_dir, f"{prefix}*.jsonl"))):
        lines = [json.loads(l) for l in open(p, encoding="utf-8")]
        res = next((o for o in lines if o["type"] == "run_result"), None)
        if not res:
            continue
        if scen is not None:
            res = _reclassify(res, scen)
        out.append({"path": p,
                    "meta": next(o for o in lines if o["type"] == "run_meta"),
                    "result": res,
                    "turns": [o for o in lines if o["type"] == "turn"],
                    "kickoff": next((o for o in lines
                                     if o["type"] == "orchestrator_message"
                                     and o.get("turn") == 0), None),
                    "orch_msgs": [o for o in lines
                                  if o["type"] == "orchestrator_message"]})
    return out


def med_range(vals):
    if not vals:
        return "—", "—"
    return round(statistics.median(vals), 1), f"{min(vals)}–{max(vals)}"


def arm_stats(runs):
    n = len(runs)
    R = [r["result"] for r in runs]
    ks = [x["metric_1_first_knowledge_state_question"]["turn"] for x in R
          if x["metric_1_first_knowledge_state_question"]]
    verd = {}
    for x in R:
        v = x["metric_4_solution"].get("outcome_class") or x["metric_4_solution"]["verdict"]
        verd[v] = verd.get(v, 0) + 1
    cons = {}
    for x in R:
        c = x["metric_4_solution"].get("consensus", {}).get("consensus", "—")
        cons[c] = cons.get(c, 0) + 1
    contra = [e for x in R for e in x["metric_3_contradiction"]]
    ccls = {}
    for e in contra:
        ccls[e["class"]] = ccls.get(e["class"], 0) + 1
    fo = [x.get("framework_overhead") for x in R if x.get("framework_overhead")]
    return {
        "n": n,
        "runs_with_ks": len(ks),
        "ks_turns": ks,
        "ks_total": sum(x["counts"]["knowledge_state_questions"] for x in R),
        "other_q": [x["counts"]["other_questions"] for x in R],
        "hall_total": [x["metric_2_hallucination_suspects"]["total"] for x in R],
        "hall_asserted": [x["metric_2_hallucination_suspects"].get("asserted", 0)
                          for x in R],
        "contradictions": len(contra), "contra_cls": ccls,
        "verdicts": verd, "consensus": cons,
        "both_correct": verd.get("both_correct", 0),
        "trap": sum(1 for x in R if x["metric_4_solution"]["trap_hit"]),
        "role": [x["metric_5_role_exit"]["count"] for x in R],
        "premature": [x.get("metric_6_premature_finals", {}).get("count", 0) for x in R],
        "turns": [x["turns_used"] for x in R],
        "iso_ok": sum(1 for x in R if x["isolation_passed"]),
        "model_calls": [f["total_model_calls"] for f in fo] if fo else [],
        "fw_tokens": [f["total_tokens"] for f in fo] if fo else [],
        "injected": [f["injected_chars_median"] for f in fo if f.get("injected_chars_median")] if fo else [],
        "aborts": sum(1 for x in R if x.get("abort_reason")),
        "corporate": sum(x.get("metric_7_corporate", {}).get("total", 0) for x in R),
        "corporate_kinds": {k: sum(x.get("metric_7_corporate", {})
                                   .get("by_kind", {}).get(k, 0) for x in R)
                            for k in ("blame", "escalation", "agree_to_disagree",
                                      "process")},
        "unresolved": verd.get("one_correct_unresolved", 0),
        "tools": sum(x.get("metric_8_tool_calls", {}).get("total", 0) for x in R),
        "tools_by": {t: sum(x.get("metric_8_tool_calls", {}).get("by_tool", {})
                            .get(t, 0) for x in R)
                     for t in ("request_data", "analyze", "document",
                               "escalate", "meeting", "assign")},
    }


def token_totals(runs):
    """Gesamt-Token je Lauf - fuer den Vergleich HTTP-Arm gegen Framework."""
    out = []
    for r in runs:
        fo = r["result"].get("framework_overhead")
        if fo:
            out.append(fo["total_tokens"])
        else:
            out.append(sum((t.get("usage") or {}).get("total_tokens", 0)
                           for t in r["turns"]))
    return out


def comparison_section(arms):
    L, A = [], None
    A = L.append
    names = list(arms.keys())
    A("\n## Armvergleich\n")
    A(f"Alle {len(names)} Arme: Szenario v3, Seeds 2001–2030, FINAL-Sperre aktiv, "
      "`temperature=0.7`, `max_tokens=700`, `enable_thinking=false`, Turn-Grenze 20. "
      "Der Framework-Arm bekommt diese Werte ueber den Mitschnitt-Proxy "
      "aufgezwungen, weil das Framework dafuer keinen Konfigurationsweg bietet.\n")
    hdr = "| Metrik | " + " | ".join(names) + " |"
    A(hdr)
    A("|---" * (len(names) + 1) + "|")

    def row(label, fn):
        A(f"| {label} | " + " | ".join(fn(arms[k]) for k in names) + " |")

    row("Laeufe", lambda s: str(s["n"]))
    row("**Laeufe mit ≥1 Wissensstandsfrage**",
        lambda s: f"**{s['runs_with_ks']}/{s['n']}** ({100*s['runs_with_ks']/s['n']:.0f} %)")
    row("Wissensstandsfragen gesamt", lambda s: str(s["ks_total"]))
    row("sonstige Fragen je Lauf (Median)", lambda s: str(med_range(s["other_q"])[0]))
    row("**both_correct**",
        lambda s: f"**{s['both_correct']}/{s['n']}** ({100*s['both_correct']/s['n']:.0f} %)")
    row("one_correct_unresolved", lambda s: str(s["verdicts"].get("one_correct_unresolved", 0)))
    row("both_wrong", lambda s: str(s["verdicts"].get("both_wrong", 0)))
    row("no_final", lambda s: str(s["verdicts"].get("no_final", 0)))
    row("Konsens ja / nein / nur eine Seite",
        lambda s: f"{s['consensus'].get('ja',0)} / {s['consensus'].get('nein',0)} / "
                  f"{s['consensus'].get('nur eine Seite',0)}")
    row("Falle zugeschlagen", lambda s: f"{s['trap']}/{s['n']}")
    row("Halluzinationsverdacht behauptet (Median)",
        lambda s: str(med_range(s["hall_asserted"])[0]))
    row("Widerspruchs-Vorfaelle",
        lambda s: f"{s['contradictions']} (" +
                  (", ".join(f"{k}:{v}" for k, v in sorted(s["contra_cls"].items())) or "—") + ")")
    row("vorzeitige FINAL (Metrik 6)", lambda s: str(sum(s["premature"])))
    row("Rollenaustritte je Lauf (Median)", lambda s: str(med_range(s["role"])[0]))
    row("Turns je Lauf (Median / Spanne)",
        lambda s: f"{med_range(s['turns'])[0]} / {med_range(s['turns'])[1]}")
    row("Modellaufrufe je Lauf (Median)",
        lambda s: str(med_range(s["model_calls"])[0]) if s["model_calls"] else "1 pro Turn")
    row("**Gesamt-Token je Lauf (Median)**",
        lambda s: f"**{med_range(s['tokens'])[0]:.0f}**")
    row("Werkzeugaufrufe (Metrik 8)",
        lambda s: str(s["tools"]) if s["tools"] else "—")
    row("Corporate-Verhalten (Metrik 7)",
        lambda s: str(s["corporate"]) if s["corporate"] else "0")
    row("Isolationspruefung bestanden", lambda s: f"{s['iso_ok']}/{s['n']}")
    if any(arms[k]["injected"] for k in names):
        row("vom Framework injizierte Zeichen",
            lambda s: str(s["injected"][0]) if s["injected"] else "—")

    A("\n### Signifikanz (Fisher-Exact, zweiseitig)\n")
    A("Ohne p-Wert ist jeder Unterschied Anekdote. Paarweise ueber alle Arme:\n")
    for label, key in (("mindestens eine Wissensstandsfrage im Lauf", "runs_with_ks"),
                       ("both_correct", "both_correct")):
        A(f"\n**{label}**\n")
        A("| Vergleich | Anteil A | Anteil B | Odds Ratio | p | signifikant (α=0.05) |")
        A("|---|---|---|---|---|---|")
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                r = st.compare_binary(a, arms[a][key], arms[a]["n"],
                                      b, arms[b][key], arms[b]["n"])
                A(f"| {a} vs. {b} | {r['k1']}/{r['n1']} ({100*r['rate_1']:.0f} %) | "
                  f"{r['k2']}/{r['n2']} ({100*r['rate_2']:.0f} %) | {r['odds_ratio']} | "
                  f"{r['p_str']} | {'**ja**' if r['significant_05'] else 'nein'} |")
    return L


def transcript(run):
    L = [f"**Lauf `{run['result']['run_id']}`** · seed {run['meta']['seed']} · "
         f"{run['result']['turns_used']} Turns · Arm `{run['meta'].get('arm','—')}` · "
         f"Prompt-Fingerprint `{run['meta']['scenario_fingerprint']}`\n"]
    rej = {(o["turn"], o["to"]): o for o in run.get("orch_msgs", [])
           if o.get("reason") == "premature_final"}
    if run["kickoff"]:
        L.append(f"*Orchestrator → A (Turn 0):* `{run['kickoff']['content']}`\n")
    for t in run["turns"]:
        h = t["heuristics"]
        f = []
        if h["knowledge_state_question"]:
            f.append("**WISSENSSTANDSFRAGE**")
        if h["fact_question"]:
            f.append(f"{len(h['fact_question'])}× Sachfrage")
        ass = [x for x in h["hallucination_suspects"] if x["mode"] == "asserted"]
        if ass:
            f.append(f"{len(ass)}× Halluzinationsverdacht behauptet")
        for x in h["role_exit"]["structural"]:
            f.append(f"Rollenaustritt `{x['pattern']}`")
        if h["contradiction_response"]:
            f.append(f"Widerspruch → `{h['contradiction_response']['class']}`")
        if h.get("final_rejected"):
            f.append("**FINAL zurueckgewiesen**")
        elif h["final"]:
            f.append("FINAL")
        fw = t.get("framework")
        meta = f"{t.get('usage',{}).get('completion_tokens','?')} Token · {t.get('latency_s','?')} s"
        if fw:
            meta += f" · {fw['model_calls']} Modellaufruf(e), {fw['total_tokens']} Token gesamt"
        L.append(f"**Turn {t['turn']} — Agent {t['agent']}** · {meta}  \n"
                 f"*heuristisch: {' · '.join(f) if f else '—'}*\n")
        L.append("> " + t["content"].replace("\n", "\n> ") + "\n")
        k = (t["turn"], t["agent"])
        if k in rej:
            L.append(f"*Orchestrator → {t['agent']}:* `{rej[k]['content']}`\n")
    return "\n".join(L)


def pick_excerpts(all_runs, hint_runs):
    picks, used, why = [], set(), []

    def take(cand, reason):
        for r in cand:
            if r["path"] not in used:
                used.add(r["path"]); picks.append(r); why.append(reason); return True
        return False

    with_ks = sorted([r for r in all_runs
                      if r["result"]["metric_1_first_knowledge_state_question"]],
                     key=lambda r: r["result"]["metric_1_first_knowledge_state_question"]["turn"])
    if not take(with_ks, "frueheste Wissensstandsfrage ueber alle Laeufe hinweg — "
                         "das gesuchte Verhalten, sofern es vorkam"):
        take(sorted(all_runs, key=lambda r: -(r["result"]["counts"]["knowledge_state_questions"]
                                              + r["result"]["counts"]["other_questions"])),
             "kein Lauf enthielt eine Wissensstandsfrage — ersatzweise der Lauf mit "
             "den meisten Fragen ueberhaupt")
    take(sorted(all_runs, key=lambda r: -r["result"]["metric_2_hallucination_suspects"].get("asserted", 0)),
         "meiste als Tatsache behauptete Halluzinationsverdachtsfaelle")
    trapped = [r for r in all_runs if r["result"]["metric_4_solution"]["trap_hit"]]
    if not take(trapped, "die eingebaute Falle hat zugeschlagen"):
        contra = [r for r in all_runs if r["result"]["metric_3_contradiction"]]
        if not take(contra, "Widerspruchs-Vorfall zwischen den Sets"):
            take(sorted(all_runs, key=lambda r: r["result"]["turns_used"]),
                 "kuerzester Lauf")
    # zusaetzlich: Hinweis-Arm mit Wissensstandsfrage, sofern vorhanden
    hk = [r for r in hint_runs
          if r["result"]["metric_1_first_knowledge_state_question"]]
    if hk:
        take(sorted(hk, key=lambda r: r["result"]["metric_1_first_knowledge_state_question"]["turn"]),
             "Hinweis-Arm mit Wissensstandsfrage")
    return list(zip(picks, why)), bool(hk)



# ---------------------------------------------------------------------------
# Grenzen-Sektion: was beim Lesen der Volltexte auffaellt und von keiner
# Metrik erfasst wird. Wo es sich zaehlen laesst, wird gezaehlt.
# ---------------------------------------------------------------------------

KS_OFFER = [
    r"mir liegen? (?:nur|ausschliesslich|ausschließlich|lediglich)",
    r"ich habe (?:nur|ausschliesslich|ausschließlich|lediglich|keinen zugriff)",
    r"ich kann .{0,40}nicht einsehen",
    r"(?:steht|stehen) mir nicht zur verf[uü]gung",
    r"mein auftrag beschr[aä]nkt sich",
    r"der mir vorliegende", r"die mir vorliegenden", r"aus dem (?:mir )?vorliegenden",
]

# Identitaetsirrtum: der Agent redet das Gegenueber als Betreiber eines
# anderen Dienstes an ("bei euch im tax-service", "koennt ihr in euren Logs").
IDENTITY_MISTAKE = [
    r"\bbei euch\b", r"\bk[oö]nnt ihr\b", r"\bhabt ihr\b", r"\beuer[en]?\b",
    r"\beuren\b", r"\bin euren\b",
]


def scan_patterns(all_runs, patterns):
    out = []
    for r in all_runs:
        for t in r["turns"]:
            for sent in re.split(r"(?<=[.!?\n])\s+", t["content"]):
                low = sent.lower()
                if any(re.search(p, low) for p in patterns):
                    out.append({"run": r["result"]["run_id"],
                                "arm": r["meta"].get("arm", "—"),
                                "turn": t["turn"], "agent": t["agent"],
                                "quote": sent.strip()})
                    break
    return out


def limits_section(all_runs, arms):
    L, A = [], None
    A = L.append
    A("\n## Grenzen — was die Metriken nicht erfassen\n")
    A("Alle Klassifikationen sind **heuristische Vorschlaege**, nicht das "
      "Urteil. Jeder Turn liegt im Volltext im zugehoerigen JSONL, jede "
      "Klassifikation zusammen mit dem ausloesenden Klartext-Satz.\n")

    A("**Nachgeprueft: die Abgrenzung von Metrik 1.** Alle Fragesaetze der "
      "v4-Laeufe, die *nicht* als Wissensstandsfrage klassifiziert wurden, "
      "wurden von Hand durchgesehen (61 Saetze). Sie zielen praktisch "
      "ausnahmslos auf Sachverhalte — \"Wurde die Query in v2.14.0 "
      "geaendert?\", \"War der tax-service ausgelastet?\". Genau ein "
      "Grenzfall liesse sich auch als Bestandsfrage lesen (\"Hast du weitere "
      "Informationen aus dem Config-Diff oder anderen statischen "
      "Artefakten?\"). Die Muster wurden daraufhin **nicht** erweitert: eine "
      "Metrik, die man nachschaerft, bis das Ergebnis gefaellt, misst nichts "
      "mehr.\n")

    offers = scan_patterns(all_runs, KS_OFFER)
    by_run = len({o["run"] for o in offers})
    A(f"**Auskunft statt Nachfrage.** In {by_run} von {len(all_runs)} Laeufen "
      f"legt ein Agent unaufgefordert offen, was er hat oder nicht hat "
      f"({len(offers)} Stellen). Das Modell kann also ueber Informationsstaende "
      f"sprechen — es kommt nur nicht auf die Idee, den des Gegenuebers zu "
      f"erfragen. Metrik 1 zaehlt Nachfragen; dieses Gegenstueck bleibt "
      f"unsichtbar.\n")
    if offers:
        A(f"> {offers[0]['quote']}  \n> — `{offers[0]['run']}`, Turn "
          f"{offers[0]['turn']}, Agent {offers[0]['agent']}\n")

    ident = scan_patterns(all_runs, IDENTITY_MISTAKE)
    if ident:
        ir = len({o["run"] for o in ident})
        A(f"**Identitaetsirrtum.** In {ir} Laeufen redet ein Agent das "
          f"Gegenueber an, als betreibe es einen anderen Dienst — in der "
          f"zweiten Person Plural, als spraeche er mit einem fremden Team. Das "
          f"beruehrt die Kernfrage unmittelbar: wer nicht weiss, mit wem er "
          f"redet, kann den Wissensstand des Gegenuebers auch nicht sinnvoll "
          f"erfragen. Keine der fuenf Metriken erfasst das.\n")
        for o in ident[:2]:
            A(f"> {o['quote']}  \n> — `{o['run']}`, Turn {o['turn']}, "
              f"Agent {o['agent']}\n")

    A("**Weitere bekannte Grenzen:**\n")
    A("- Ein Marker aus dem fremden Set kann **legitime Inferenz** sein: aus "
      "`completed 59.8s` laesst sich auf einen Timeout jenseits von 60s "
      "schliessen, ohne den Config-Wert zu kennen. `asserted`, `hedged` und "
      "`negated` werden deshalb getrennt gefuehrt; belastbar ist nur "
      "`asserted`.\n")
    A("- Aussagen ueber das **eigene** Set in Verneinungsform (\"der Diff "
      "zeigt keine Code-Aenderungen\") sind keine Halluzination und zaehlen "
      "als `negated`.\n")
    A("- Die Loesungsklassifikation prueft Wortgruppen, nicht Modalitaet. Ein "
      "ausdruecklich als Vermutung markiertes `FINAL` zaehlt als korrekt, wenn "
      "es die richtigen Elemente nennt. Die Solo-Kontrolle zeigt, wie oft "
      "blosses begruendetes Raten dafuer reicht — im dichten Szenario "
      "3/30 bei Agent B.\n")
    A("- `consensus` vergleicht die getroffenen Loesungsgruppen und den "
      "Fallen-Status, nicht den Wortlaut. Zwei FINAL koennen als "
      "uebereinstimmend gelten und sich in der Begruendung unterscheiden; die "
      "Begruendung des Urteils steht in jeder `consensus`-Logzeile.\n")
    A("- Die zweistufige Abfrage (offen, dann direkt) laesst Stufe 2 auf "
      "Stufe 1 folgen. Im Hinweis-Arm faellt die direkte Antwort deshalb "
      "schwaecher aus als im Arm ohne Hinweis (65 % gegen 85 %) - dort war in "
      "der offenen Antwort schon alles gesagt. Der Vergleich zwischen den "
      "Stufen ist davon nicht betroffen, der zwischen den Armen auf Stufe 2 "
      "schon.\n")
    A("- Die Post-hoc-Abfrage misst ueberwiegend Erinnerung, nicht "
      "Modellierung: die Quellenart des Gegenuebers wird im Gespraech fast "
      "immer beilaeufig erwaehnt. Das war ein Designfehler der Abfrage, den "
      "erst die strengere Nachpruefung sichtbar machte; die A-priori-Abfrage "
      "ersetzt sie.\n")
    A("- Die FINAL-Sperre veraendert das Gemessene, nicht nur die Messung: sie "
      "erzwingt mindestens einen Austausch. Sie beseitigt damit einen "
      "Designfehler der Vorkonfigurationen, macht die Arme aber nicht mit "
      "diesen vergleichbar.\n")
    if "Framework" in arms and arms["Framework"]["model_calls"]:
        A("- Im Framework-Arm sind Toolsets und Skills abgeschaltet. Das ist "
          "fuer die Isolation zwingend — ein Agent mit Websuche koennte sie "
          "unterlaufen —, misst aber ein beschnittenes Framework. Was das Framework "
          "mit Tools leisten wuerde, sagt dieser Arm nicht.\n")
    return L



def probe_section():
    """Repraesentation gegen Handlung: A-priori- und Post-hoc-Abfrage."""
    import glob as _g
    L, A = [], None
    A = L.append
    ap = {}
    for name, f in (("ohne Hinweis", "posthoc/apriori_v3.jsonl"),
                    ("mit Hinweis", "posthoc/apriori_hint.jsonl")):
        if not os.path.exists(f):
            continue
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        n = 2 * len(rows)
        ap[name] = {
            "n": n,
            "spontan": sum(1 for r in rows for a in ("A", "B")
                           if r[a]["classification_open"]["category"].startswith("asymmetry")),
            "direkt": sum(1 for r in rows for a in ("A", "B")
                          if r[a]["classification_direct"]["category"].startswith("asymmetry")),
        }
    if not ap:
        return L
    A("\n## Repraesentation gegen Handlung\n")
    A("Die fuenf Metriken messen **Verhalten im Gespraech**. Sie koennen nicht "
      "unterscheiden, ob ein Agent die Informationsasymmetrie gar nicht "
      "repraesentiert oder ob er sie repraesentiert und trotzdem nicht danach "
      "handelt. Dafuer zwei Abfragen ausserhalb des Laufs.\n")
    A("**A-priori** — der Agent sieht nur seinen System-Prompt und den Kickoff, "
      "kein Wort des Gegenuebers. Zwei Stufen: offen (\"was weisst du ueber "
      "dein Gegenueber?\") und direkt (\"koennte es Informationen haben, die "
      "dir nicht vorliegen? welche?\").\n")
    A("| Frage | ohne Hinweis | mit Hinweis |")
    A("|---|---|---|")
    for label, key in (("spontan (offen gefragt)", "spontan"),
                       ("abrufbar (direkt gefragt)", "direkt")):
        cells = []
        for nm in ("ohne Hinweis", "mit Hinweis"):
            if nm in ap:
                d = ap[nm]
                cells.append(f"**{d[key]}/{d['n']}** ({100*d[key]/d['n']:.0f} %)")
            else:
                cells.append("—")
        A(f"| Asymmetrie erkannt, {label} | " + " | ".join(cells) + " |")
    if "ohne Hinweis" in ap and "mit Hinweis" in ap:
        o, h = ap["ohne Hinweis"], ap["mit Hinweis"]
        r1 = st.compare_binary("ohne", o["spontan"], o["n"], "mit", h["spontan"], h["n"])
        r2 = st.compare_binary("direkt", o["direkt"], o["n"], "offen", o["spontan"], o["n"])
        A(f"\nDer Hinweis-Satz hebt die **spontane** Erkennung von "
          f"{100*o['spontan']/o['n']:.0f} % auf {100*h['spontan']/h['n']:.0f} % "
          f"({r1['p_fmt']}). Und schon ohne ihn ist die Asymmetrie **abrufbar**: "
          f"direkt gefragt benennen {100*o['direkt']/o['n']:.0f} % der Agenten "
          f"korrekt, welche Quellenart dem Gegenueber vorliegt — gegen "
          f"{100*o['spontan']/o['n']:.0f} % spontan ({r2['p_fmt']}). Agent A "
          f"tippt auf Konfiguration und Aenderungshistorie, Agent B auf Logs "
          f"und Metriken. Beide liegen richtig.\n")
        A("**Damit ist der zentrale Befund dieses Experiments benannt:**\n")
        A(f"- Die Informationsasymmetrie ist **repraesentiert und abrufbar** "
          f"({100*o['direkt']/o['n']:.0f} % direkt gefragt).\n")
        A(f"- Der Hinweis-Satz macht sie sogar **spontan praesent** "
          f"({100*h['spontan']/h['n']:.0f} % gegen {100*o['spontan']/o['n']:.0f} %, "
          f"{r1['p_fmt']}).\n")
        A("- Und trotzdem fuehrt das im Gespraech zu **null** "
          "Wissensstandsfragen (0/30 im Hinweis-Arm).\n")
        A("Es ist also kein Repraesentationsdefizit und kein Wissensdefizit. "
          "Das Modell weiss, dass sein Gegenueber etwas anderes sieht, kann "
          "sogar sagen was — und fragt trotzdem nicht danach, wenn es zaehlt. "
          "Repraesentation und Handlung sind entkoppelt.\n")

    ph = "posthoc/all.jsonl"
    if os.path.exists(ph):
        rows = [json.loads(l) for l in open(ph, encoding="utf-8")]
        n = 2 * len(rows)
        ok = sum(1 for r in rows for a in ("A", "B")
                 if r[a]["classification_direct"]["category"] == "correct")
        A(f"\n**Post-hoc** — dieselbe Frage nach Laufende, mit der vollen "
          f"Historie: {ok}/{n} benennen den Bestand des Gegenuebers korrekt. "
          f"Diese Zahl ist allerdings **kaum aussagekraeftig**: in 175 der {n} "
          f"Faelle hatte das Gegenueber seine Quellenart im Gespraech beilaeufig "
          f"erwaehnt (\"der Diff zeigt...\", \"meine Logs...\"), sodass eine "
          f"richtige Antwort blosses Zuhoeren sein kann. Nur 5 Faelle blieben "
          f"ohne jede Erwaehnung — zu wenig fuer eine Aussage. Die "
          f"A-priori-Abfrage oben umgeht dieses Problem, weil dort noch kein "
          f"Wort gefallen ist.\n")
    return L


def config_section(title, runs, solo_path, scen, is_arm):
    L, A = [], None
    A = L.append
    n = len(runs)
    s = arm_stats(runs)
    s["tokens"] = token_totals(runs)
    fps = {r["meta"]["scenario_fingerprint"] for r in runs}
    cfps = {r["meta"].get("config_fingerprint", "—") for r in runs}
    A(f"\n### {title}\n")
    A(f"{n} Laeufe · Szenario `{runs[0]['meta']['scenario_id']}` "
      f"v{runs[0]['meta']['scenario_version']} · Prompt-Fingerprint "
      f"`{list(fps)[0] if len(fps)==1 else '!! UNEINHEITLICH ' + str(fps)}` · "
      f"Config-Fingerprint `{list(cfps)[0] if len(cfps)==1 else '!! UNEINHEITLICH'}` · "
      f"Seeds {min(r['meta']['seed'] for r in runs)}–{max(r['meta']['seed'] for r in runs)}\n")
    if len(fps) > 1:
        A("> **Warnung:** unterschiedliche Prompts innerhalb des Arms — nicht "
          "gemeinsam auswertbar.\n")
    A(f"Isolationspruefung bestanden: **{s['iso_ok']}/{n}**"
      + (f" · abgebrochene Laeufe: {s['aborts']}" if s["aborts"] else "") + "\n")

    A("| Metrik | Median | Spannweite | Anmerkung |")
    A("|---|---|---|---|")
    m, r_ = med_range(s["ks_turns"])
    A(f"| **1 · Erste Wissensstandsfrage** (Turn) | {m} | {r_} | "
      f"**{n - s['runs_with_ks']}/{n} Laeufe ohne jede Wissensstandsfrage** |")
    m, r_ = med_range(s["other_q"])
    A(f"| 1b · sonstige Fragen je Lauf | {m} | {r_} | Sachfragen — zur Abgrenzung |")
    m, r_ = med_range(s["hall_total"])
    A(f"| **2 · Halluzinationsverdacht** je Lauf | {m} | {r_} | inkl. gehedgt/verneint |")
    m, r_ = med_range(s["hall_asserted"])
    A(f"| 2a · davon als Tatsache behauptet | {m} | {r_} | die belastbare Teilmenge |")
    A(f"| **3 · Widerspruchs-Vorfaelle** | {s['contradictions']} gesamt | — | "
      + (", ".join(f"`{k}`: {v}" for k, v in sorted(s["contra_cls"].items()))
         or "keiner aufgetreten") + " |")
    m, r_ = med_range(s["turns"])
    A(f"| 4a · Turns bis Laufende | {m} | {r_} | Abbruch bei beidseitigem "
      f"gueltigem FINAL / Turn 20 |")
    m, r_ = med_range(s["role"])
    A(f"| **5 · Rollenaustritte** je Lauf | {m} | {r_} | |")
    if is_arm:
        m, r_ = med_range(s["premature"])
        A(f"| **6 · vorzeitige FINAL** je Lauf | {m} | {r_} | "
          f"{sum(s['premature'])} gesamt — zurueckgewiesen, Lauf lief weiter |")
    m, r_ = med_range(s["tokens"])
    A(f"| Gesamt-Token je Lauf | {m:.0f} | {r_} | |")
    if s["model_calls"]:
        m, r_ = med_range(s["model_calls"])
        A(f"| Modellaufrufe je Lauf | {m} | {r_} | Framework-Overhead |")

    A("")
    A("| Ergebnis | Laeufe | Anteil |")
    A("|---|---|---|")
    if is_arm:
        order = (("both_correct", "beide Seiten korrekt"),
                 ("one_correct_unresolved", "nur eine Seite korrekt, Widerspruch ungeklaert"),
                 ("both_wrong", "keine Seite korrekt"),
                 ("no_final", "kein gueltiges FINAL"))
    else:
        order = (("correct", "korrekt"),
                 ("correct_with_trap", "korrekt, Falle als Mit-Ursache"),
                 ("wrong", "falsch"), ("none", "kein FINAL"))
    for k, lab in order:
        c = s["verdicts"].get(k, 0)
        A(f"| {lab} | {c}/{n} | {100*c/n:.0f} % |")
    A(f"\n**Falle zugeschlagen {s['trap']}/{n} = {100*s['trap']/n:.0f} %** · "
      f"**ohne jede Wissensstandsfrage {n-s['runs_with_ks']}/{n} = "
      f"{100*(n-s['runs_with_ks'])/n:.0f} %**"
      + (f" · **Konsens: {s['consensus'].get('ja',0)}× ja, "
         f"{s['consensus'].get('nein',0)}× nein, "
         f"{s['consensus'].get('nur eine Seite',0)}× nur eine Seite" if is_arm else "") + "\n")

    if solo_path and os.path.exists(solo_path):
        j = json.load(open(solo_path))["summary"]
        A("\n**Solo-Kontrolle** — was schafft jede Seite allein? Identischer "
          "System-Prompt, identisches Sampling, statt des Gegenuebers nur der "
          "Kickoff.\n")
        A("| Solo | n | korrekt | falsch | kein FINAL | Falle |")
        A("|---|---|---|---|---|---|")
        for ag in ("A", "B"):
            if ag in j:
                x = j[ag]
                A(f"| Agent {ag} allein | {x['n']} | **{x['correct']}** | {x['wrong']} | "
                  f"{x['none']} | {x['trap_hit']} |")
        A("")
    return L, s


def judge_section(judge_files, manual_path):
    L, A = [], None
    A = L.append
    A("\n## Quellenzuordnung per Judge\n")
    A("Zwei Muster kann eine markerbasierte Heuristik prinzipiell nicht "
      "fangen: **Quellenverwechslung** (empfangene Information wird spaeter "
      "dem eigenen Set zugeschrieben) und **Falschanwendung** (ein belegter "
      "Wert wird auf den falschen Kontext bezogen). Beides braucht "
      "Textverstehen.\n")
    A("Der Judge ist dasselbe Modell, bekommt aber — anders als die Agenten — "
      "beide Datensets, die Ground Truth und das vollstaendige Transkript. "
      "`temperature=0`, erzwungenes JSON-Schema. Er ist kein Teilnehmer des "
      "Experiments.\n")
    rows, totals = [], {}
    for name, path in judge_files:
        if not os.path.exists(path):
            continue
        recs = [json.loads(l) for l in open(path, encoding="utf-8")]
        c = {}
        for r in recs:
            for cl in r["claims"]:
                c[cl["category"]] = c.get(cl["category"], 0) + 1
        c["_runs"] = len(recs)
        c["_claims"] = sum(len(r["claims"]) for r in recs)
        rows.append((name, c))
        for k, v in c.items():
            if not k.startswith("_"):
                totals[k] = totals.get(k, 0) + v
    if not rows:
        A("_Keine Judge-Ergebnisse vorhanden._\n")
        return L
    cats = ["own_set", "received", "unsupported", "misattributed", "misapplied"]
    A("| Arm | Laeufe | Behauptungen | " + " | ".join(f"`{c}`" for c in cats) + " |")
    A("|---" * (len(cats) + 3) + "|")
    for name, c in rows:
        A(f"| {name} | {c['_runs']} | {c['_claims']} | "
          + " | ".join(str(c.get(k, 0)) for k in cats) + " |")
    tot_claims = sum(c["_claims"] for _, c in rows)
    A(f"\nUeber alle Arme: {tot_claims} Faktenbehauptungen, davon "
      f"**{totals.get('unsupported',0)} unbelegt**, "
      f"**{totals.get('misattributed',0)} falsch attribuiert**, "
      f"**{totals.get('misapplied',0)} falsch angewendet** — zusammen "
      f"{totals.get('unsupported',0)+totals.get('misattributed',0)+totals.get('misapplied',0)}"
      f" fehlerhafte Quellenbezuege "
      f"({100*(totals.get('unsupported',0)+totals.get('misattributed',0)+totals.get('misapplied',0))/tot_claims:.0f} %).\n")

    if os.path.exists(manual_path):
        m = json.load(open(manual_path))
        A(f"\n**Manuelle Nachpruefung.** {m['checked']} von {m['total']} "
          f"Judge-Urteilen ({100*m['checked']/m['total']:.0f} %) wurden von Hand "
          f"gegen die beiden Datensets und das Transkript geprueft. "
          f"**Uebereinstimmung: {m['agree']}/{m['checked']} = "
          f"{100*m['agree']/m['checked']:.0f} %.**\n")
        A(f"Stichprobe: {m["sampling"]}. "
          f"Ohne diese Rate waere die Judge-Metrik nicht belastbar.\n")
        if m.get("method"):
            A(f"\n_{m['method']}_\n")
        if m.get("patterns"):
            A("\nWo der Judge zuverlaessig ist und wo nicht:\n")
            for pt in m["patterns"]:
                A(f"- {pt}")
            A("")
        if m.get("disagreements"):
            A("\nAbweichungen im Einzelnen:\n")
            for d in m["disagreements"]:
                A(f"- `{d['run_id']}` Turn {d['turn']} ({d['agent']}): Judge sagt "
                  f"`{d['judge']}`, Nachpruefung sagt `{d['manual']}` — {d['note']}  \n"
                  f"  <sub>{d['claim'][:150]}</sub>")
            A("")
    else:
        A("\n_Manuelle Nachpruefung steht aus._\n")
    return L


def main(out_path):
    sections, arms, all_arm_runs, hint_runs, legacy = [], {}, [], [], []
    r0 = None
    for title, d, pref, solo, mod, is_arm in CONFIGS:
        scen = importlib.import_module(mod)
        runs = load_runs(d, pref, scen)
        if not runs:
            continue
        sec, s = config_section(title, runs, solo, scen, is_arm)
        s["tokens"] = token_totals(runs)
        sections.append((title, sec, is_arm))
        for r in runs:
            r["config"] = title
        if is_arm:
            arms[SHORT.get(title, title)] = s
            all_arm_runs += runs
            if "Hinweis" in title:
                hint_runs = runs
        else:
            legacy += runs
        if r0 is None:
            r0 = runs[0]

    L, A = [], None
    A = L.append
    A("# Erkennen zwei Instanzen desselben Modells, dass sie einander brauchen?\n")
    A(f"Messsetup · {len(all_arm_runs)} Laeufe in {len(arms)} verglichenen "
      f"Armen, dazu {len(legacy)} Laeufe aus den beiden Vorkonfigurationen und "
      f"Solo-Kontrollen · erzeugt von `aggregate.py`\n")

    A("## Aufbau\n")
    A("Zwei Instanzen desselben Modells arbeiten am selben Incident. Jede sieht "
      "nur ihre Haelfte der Information, beide bekommen denselben Auftrag: die "
      "Ursache benennen. Ein Orchestrator ist die einzige Verbindung — er "
      "reicht die Ausgabe der einen Seite als reinen `user`-Turn an die andere "
      "weiter, byte-identisch, ohne Praefix und ohne Sprecherkennzeichnung. "
      "Kein System-Prompt erwaehnt, dass das Gegenueber ein Modell ist; das ist "
      "die Frage, nicht die Vorgabe. Die Ground Truth kennt nur der "
      "Orchestrator.\n")
    A("| | |\n|---|---|")
    A(f"| Modell angefragt als | `{r0['meta']['model_requested']}` |"
      if r0["meta"].get("model_requested") else "| Modell | local-model |")
    A(f"| tatsaechlich geladen | `/models/local-27b-int4` |")
    A("| Sampling | `temperature=0.7`, `max_tokens=700`, "
      "`enable_thinking=false`, Seed je Lauf protokolliert |")
    A("| Kontextbudget | 32768 Token, clientseitig hart geprueft (vLLM `/tokenize`) |")
    A("| Abbruch | beidseitiges **gueltiges** `FINAL` oder 20 Turns |")
    A("| Scaffolding | nackte HTTP-Calls; im Framework-Arm das Framework |")
    A("")
    A("**FINAL-Sperre (ab Arm v4).** Ein `FINAL` ist erst gueltig, wenn der "
      "Agent mindestens eine Nachricht des Gegenuebers empfangen hat. Ein zu "
      "frueher Abschluss beendet den Lauf nicht: der Orchestrator weist ihn mit "
      "`Noch keine Antwort des Gegenuebers erhalten.` zurueck, der Lauf laeuft "
      "weiter, und die Zurueckweisung wird als eigene Metrik gezaehlt. Ohne "
      "diese Sperre lag der Median bei 2 Turns — die Aussage \"keine "
      "Wissensstandsfrage\" mass dann teilweise nur, dass gar kein Gespraech "
      "stattfand.\n")
    A("**Isolation** wird nicht behauptet, sondern nach jedem Lauf maschinell "
      "geprueft und protokolliert: jede Historie beginnt mit dem eigenen "
      "System-Prompt, der fremde Datenblock taucht in der Gegenhistorie nicht "
      "auf, jede eingehende `user`-Nachricht ist byte-identisch mit einer "
      "gesendeten Nachricht des Gegenuebers, und Ground Truth wie "
      "Fallenbeschreibung kommen in keiner Historie vor. Im Framework-Arm "
      "kommt eine zweite Ebene dazu: der Mitschnitt-Proxy prueft die "
      "**tatsaechlich an das Modell gesendeten** Prompts — kein einziger "
      "Request darf beide Datensets enthalten.\n")

    if arms:
        L += comparison_section(arms)

    A("\n## Befund\n")
    if "v4" in arms and "Hinweis" in arms and "Framework" in arms:
        v4, hi, fw = arms["v4"], arms["Hinweis"], arms["Framework"]
        rq = st.compare_binary("v4", v4["runs_with_ks"], v4["n"],
                               "Hinweis", hi["runs_with_ks"], hi["n"])
        A(f"**1. Die Wissensstandsfrage bleibt aus — in jedem Arm.** "
          f"{v4['runs_with_ks']}/{v4['n']} Laeufe in v4, "
          f"{hi['runs_with_ks']}/{hi['n']} im Hinweis-Arm, "
          f"{fw['runs_with_ks']}/{fw['n']} im Framework-Arm. Kein Paarvergleich "
          f"wird signifikant (kleinstes p={rq['p_str']}). Der Satz \"Dein "
          f"Gegenueber verfuegt moeglicherweise ueber Informationen, die dir "
          f"nicht vorliegen\" aendert daran **nichts** — er senkt die Zahl "
          f"numerisch sogar auf null. Es fehlt also nicht der Anlass. Gefragt "
          f"wird durchaus, aber nach **Sachverhalten** (\"Wurde die Query in "
          f"v2.14.0 geaendert?\"), nicht nach dem **Informationsbestand**. Eine "
          f"Sachfrage setzt voraus, dass das Gegenueber die Antwort hat; eine "
          f"Wissensstandsfrage klaert erst, ob es sie haben kann.\n")
        rc = st.compare_binary("v4", v4["both_correct"], v4["n"],
                               "Hinweis", hi["both_correct"], hi["n"])
        A(f"**2. Der Hinweis wirkt auf das Ergebnis — aber nicht belegbar.** "
          f"`both_correct` liegt bei {hi['both_correct']}/{hi['n']} gegen "
          f"{v4['both_correct']}/{v4['n']} in v4, und die vorzeitigen FINAL "
          f"fallen von {sum(v4['premature'])} auf {sum(hi['premature'])}. Der "
          f"Unterschied ist mit p={rc['p_str']} aber **nicht signifikant**: bei "
          f"n=30 je Arm traegt er nicht. Als Befund bleibt: der Hinweis "
          f"veraendert das Frageverhalten nachweislich nicht, und ob er das "
          f"Ergebnis verbessert, ist mit dieser Stichprobe offen.\n")
        rf = st.compare_binary("Hinweis", hi["both_correct"], hi["n"],
                               "Framework", fw["both_correct"], fw["n"])
        A(f"**3. Das Framework schneidet schlechter ab.** "
          f"`both_correct` {fw['both_correct']}/{fw['n']} gegen "
          f"{hi['both_correct']}/{hi['n']} im Hinweis-Arm (p={rf['p_str']}, "
          f"Odds Ratio {rf['odds_ratio']}). Dabei verbraucht es "
          f"{med_range(fw['tokens'])[0]/med_range(v4['tokens'])[0]:.1f}-mal so "
          f"viele Token je Lauf ({med_range(fw['tokens'])[0]:.0f} gegen "
          f"{med_range(v4['tokens'])[0]:.0f}), laeuft ueber mehr Turns und "
          f"faellt {fw['trap']}/{fw['n']}-mal auf die eingebaute Falle herein "
          f"gegen {v4['trap']}/{v4['n']} in v4. Mehr Scaffolding, mehr Token, "
          f"mehr Gespraech — schlechteres Ergebnis. Der Vorteil, den ein "
          f"Framework hier haette bringen sollen, tritt nicht ein; die "
          f"Confounding-Kontrolle schliesst aus, dass der Nachteil aus "
          f"knapperen Sampling-Parametern stammt, denn die sind erzwungen "
          f"identisch.\n")
        A("**4. Repraesentation und Handlung sind entkoppelt — das ist der "
          "Kern.** Ausserhalb des Gespraechs, vor dem ersten Wortwechsel, "
          "direkt gefragt, benennen 85 % der Agenten korrekt, welche "
          "Quellenart ihrem Gegenueber vorliegt. Mit dem Hinweis-Satz ist die "
          "Asymmetrie sogar in 67 % der Faelle spontan praesent, gegen 10 % "
          "ohne ihn (p<0.0001). Beides aendert am Gespraech nichts: null "
          "Wissensstandsfragen. Das Modell **weiss**, dass sein Gegenueber "
          "etwas anderes sieht, und handelt trotzdem nicht danach. Details "
          "unter \"Repraesentation gegen Handlung\".\n")
        A(f"**5. Was die Agenten statt zu fragen tun.** Sie fuellen die Luecke. "
          f"Der Median der als Tatsache behaupteten Halluzinationsverdachtsfaelle "
          f"steigt von {med_range(v4['hall_asserted'])[0]} (v4) ueber "
          f"{med_range(hi['hall_asserted'])[0]} (Hinweis) auf "
          f"{med_range(fw['hall_asserted'])[0]} (Framework) je Lauf. Und wenn "
          f"eine Aussage des Gegenuebers dem eigenen Set widerspricht, wird sie "
          f"weit ueberwiegend stillschweigend uebergangen: "
          f"{v4['contra_cls'].get('ignored',0)+hi['contra_cls'].get('ignored',0)+fw['contra_cls'].get('ignored',0)} "
          f"von {v4['contradictions']+hi['contradictions']+fw['contradictions']} "
          f"Widerspruchs-Vorfaellen enden in `ignored`, genau einer fuehrt zu "
          f"einer Rueckfrage.\n")

    A("\n## Konfigurationen im Einzelnen\n")
    A("### Verglichene Arme\n")
    for title, sec, is_arm in sections:
        if is_arm:
            L += sec
    A("\n### Vorkonfigurationen (ohne FINAL-Sperre, historisch)\n")
    A("Diese beiden Konfigurationen liefen vor Einfuehrung der FINAL-Sperre und "
      "der differenzierten Ergebnisklassifikation. Sie sind nicht mit den Armen "
      "vergleichbar und stehen hier zur Nachvollziehbarkeit.\n")
    for title, sec, is_arm in sections:
        if not is_arm:
            L += sec

    if "Entwickler" in arms and "Manager" in arms:
        d, m2, b = arms["Entwickler"], arms["Manager"], arms.get("v4")
        r = st.compare_binary("Entwickler", d["unresolved"], d["n"],
                              "Manager", m2["unresolved"], m2["n"])
        A("\n## Die Rollen-Arme\n")
        A("Anlass war eine Wette in einem Kommentarstrang: mit einer "
          "Manager-Rolle im Prompt muesste es Fingerpointing geben, "
          "erfolgloses Eskalieren ueber viele Turns, am Ende ein "
          "\"agree to disagree\" und ein Sync auf hoeherer Ebene naechste "
          "Woche.\n")
        A("Die Baseline enthaelt **keine** Rollenzuweisung. Deshalb zwei Arme "
          "statt einem: zwischen `Entwickler` und `Manager` unterscheiden sich "
          "die Prompts um genau sechs Zeichen, alles andere - Daten, Seeds, "
          "Sampling, FINAL-Sperre - ist identisch. Dazu vier neue Zaehler "
          "(Metrik 7): Schuldzuweisung, Eskalation, \"agree to disagree\", "
          "Prozess-Vokabular.\n")
        A(f"**Die Wette ist verloren.** Metrik 7 zaehlt in beiden Rollen-Armen "
          f"**null** Treffer - kein Fingerpointing, keine Eskalation, kein "
          f"Sync-Termin, kein einziges \"agree to disagree\". Auch die Laenge "
          f"der Laeufe aendert sich nicht (Median 3 Turns in beiden Armen, wie "
          f"in der rollenlosen Baseline). Das Modell uebernimmt die "
          f"Rollenbezeichnung, aber nicht das Rollenklischee.\n")
        A(f"**Ein Effekt ist trotzdem da - und zwar der, um den es der Wette "
          f"im Kern ging.** `one_correct_unresolved` bedeutet: beide Seiten "
          f"senden ein FINAL, eines ist richtig und eines falsch, und niemand "
          f"raeumt den Widerspruch aus. Genau das ist ein \"agree to "
          f"disagree\", nur ohne die Worte.\n")
        A(f"| Arm | ungeklaerter Widerspruch |")
        A("|---|---|")
        if b:
            A(f"| v4 (ohne Rolle) | {b['unresolved']}/30 |")
        A(f"| Entwickler | **{d['unresolved']}/30** |")
        A(f"| Manager | **{m2['unresolved']}/30** |")
        A(f"\nEntwickler gegen Manager: {r['p_fmt']}"
          f"{' — **signifikant**' if r['significant_05'] else ' — nicht signifikant'} "
          f"(Bonferroni-Schwelle bei drei Vergleichen: 0.0167). In allen "
          f"{m2['unresolved']} Manager-Faellen lag ein FINAL richtig und eines "
          f"falsch; kein einziger Fall entstand dadurch, dass eine Seite gar "
          f"nichts lieferte.\n")
        A("Die vorsichtige Lesart waere gewesen: nicht der Manager faellt nach "
          "oben aus der Reihe, sondern der Entwickler nach unten (gegen die "
          "rollenlose Baseline mit 5/30 ist der Manager-Wert unauffaellig, "
          "p=0.5321).\n")
        A("> **Dieser Befund repliziert nicht.** In den beiden Armen mit "
          "Werkzeugkasten steht es 4/30 zu 4/30, mit Konzern-Kontext 5/30 zu "
          "2/30. Bei neun Armen und mehreren Vergleichen je Metrik ist "
          "p=0.0046 genau der Zufallstreffer, den man erwarten muss. Der "
          "Unterschied wird hier nur noch dokumentiert, nicht mehr "
          "behauptet.\n")
        A("**Werkzeugkasten und Konzern-Kontext aendern daran nichts.** Beide "
          "Rollen bekamen denselben Werkzeugkasten aus sechs Werkzeugen, "
          "spaeter zusaetzlich einen wortgleichen Konzern-Rahmen "
          "(Berichtslinie, gerissenes Verfuegbarkeitsziel, dritter Ausfall im "
          "Quartal, Zusage an die Konzern-IT). Die Werkzeugwahl bleibt "
          "praktisch deckungsgleich: 181 gegen 182 Aufrufe ohne Kontext, 216 "
          "gegen 182 mit. Die beiden organisatorischen Werkzeuge `meeting` und "
          "`assign` werden von **beiden** Rollen fast vollstaendig gemieden - "
          "in 120 Laeufen zusammen achtmal. Kein einziger Paarvergleich ueber "
          "Werkzeuge, Ergebnis oder Corporate-Verhalten wird signifikant.\n")
        A("Das Modell uebernimmt die Rollenbezeichnung, leitet daraus aber kein "
          "Verhalten ab. Bei einer Sachaufgabe mit genau einer richtigen "
          "Antwort gewinnt die Aufgabe gegen die Rolle. Ob Rollenklischees in "
          "den Trainingsdaten liegen, sagt das nicht - nur, dass sie hier "
          "nicht aktiviert werden.\n")

    if "Dev+Entsch" in arms and "Mgr+Entsch" in arms and "Dev+Konzern" in arms:
        dc, mc = arms["Dev+Konzern"], arms["Mgr+Konzern"]
        dd, md = arms["Dev+Entsch"], arms["Mgr+Entsch"]
        r = st.compare_binary("Diagnose", dc["both_correct"] + mc["both_correct"], 60,
                              "Diagnose+Entscheidung",
                              dd["both_correct"] + md["both_correct"], 60)
        A("\n## Wenn es etwas zu entscheiden gibt\n")
        A("Die bisherigen Arme liessen der Rolle keine Angriffsflaeche: eine "
          "Diagnose mit genau einer richtigen Antwort ist fuer Entwickler und "
          "Manager dieselbe Aufgabe. Deshalb zwei weitere Arme, in denen "
          "zusaetzlich zu entscheiden ist, ob Release v2.14.0 zurueckgerollt "
          "wird. Diese Frage hat **keine** richtige Antwort: ein Rollback "
          "beendet die Pool-Blockade, holt aber genau das Problem zurueck, "
          "dessentwegen der Timeout laut NW-4471 erhoeht wurde. Den Trade-off "
          "ueberblickt keine Seite allein.\n")
        A("**Die organisatorischen Werkzeuge kommen erst jetzt zum Einsatz.** "
          f"`assign` steigt von 0 auf 9 Aufrufe, `meeting` von 1 auf 4, "
          f"`document` von 26 auf 42 - und zwar in **beiden** Rollen "
          f"gleichermassen. Nicht die Rolle entscheidet ueber das Verhalten, "
          f"sondern die Aufgabe.\n")
        A(f"**Der Preis ist die Diagnose.** `both_correct` faellt von "
          f"{dc['both_correct'] + mc['both_correct']}/60 auf "
          f"{dd['both_correct'] + md['both_correct']}/60 ({r['p_fmt']}). "
          f"Einzeln betrachtet verfehlen beide Arme die Signifikanz "
          f"(p=0.2092 und p=0.1806); zusammengefasst wird der Unterschied "
          f"deutlich. Das Zusammenlegen ist hier vertretbar, weil die Rolle "
          f"ueber alle Arme hinweg nachweislich folgenlos ist - es ist eine "
          f"Replikation ueber zwei Arme, keine nachtraegliche Gruppenbildung. "
          f"Bei der Zahl der Tests in diesem Report bleibt es dennoch ein "
          f"Hinweis, kein Beleg.\n")
        A("**Und die Entscheidung selbst?** Von 60 Laeufen kommen 39 zu einer "
          "gemeinsamen Entscheidung, 10 nur einseitig, 5 uneinig, 6 gar "
          "nicht. Die Voten stehen 72 zu 26 fuer den Rollback. Bemerkenswert "
          "dabei: In der Mehrzahl dieser Laeufe kennt keine der beiden Seiten "
          "die tatsaechliche Ursache - entschieden wird trotzdem, einig und "
          "zuegig.\n")

    L += probe_section()
    L += limits_section(all_arm_runs, arms)
    L += judge_section(
        [("v4", "judge/v4.jsonl"), ("Hinweis", "judge/hint.jsonl"),
         ("Framework", "judge/framework.jsonl")], "judge/manual_check.json")

    A("\n## Gespraechsauszuege im Volltext\n")
    A("Auswahl nach fester Regel, nicht handverlesen: (1) der Lauf mit der "
      "fruehesten Wissensstandsfrage, ersatzweise der mit den meisten Fragen "
      "ueberhaupt; (2) der Lauf mit den meisten als Tatsache behaupteten "
      "Halluzinationsverdachtsfaellen; (3) ein Lauf, in dem die Falle "
      "zuschlug, ersatzweise einer mit Widerspruchs-Vorfall, ersatzweise der "
      "kuerzeste. Zusaetzlich (4) ein Auszug aus dem Hinweis-Arm mit "
      "Wissensstandsfrage, sofern vorhanden.\n")
    picks, had_hint_ks = pick_excerpts(all_arm_runs, hint_runs)
    if not had_hint_ks:
        A("> Auszug (4) entfaellt: **im Hinweis-Arm kam in keinem der 30 Laeufe "
          "eine Wissensstandsfrage vor.** Das ist selbst ein Befund.\n")
    for i, (r, why) in enumerate(picks, 1):
        A(f"\n### Auszug {i} — {why}\n")
        A(f"*aus {r['config']}*\n")
        A(transcript(r))

    A("\n## Reproduktion\n")
    A("Reihenfolge wie durchgefuehrt. Jede Stufe ist fuer sich auswertbar.\n")
    A("```bash")
    A("# Schritt 1 — Baseline v4: FINAL-Sperre, differenzierte Klassifikation, 30 Laeufe")
    A("python3 run_config.py --scenario scenario_v3 --config v4 --out runs_v4 \\")
    A("                      --final-lock --arm v4 --seed-range 2001 2030")
    A("python3 solo_check.py --scenario scenario_v3 --out runs_v3_solo30 --seed-range 2001 2030")
    A("")
    A("# Schritt 2 — Hinweis-Arm: identisch, plus ein Satz in beiden System-Prompts")
    A("python3 run_config.py --scenario scenario_v3_hint --config hinweis --out runs_hint \\")
    A("                      --final-lock --arm hinweis --seed-range 2001 2030")
    A("")
    A("# Schritt 3 — Framework-Arm: Framework gegen Framework, Sampling ueber den Proxy erzwungen")
    A("python3 framework_proxy.py &          # muss laufen, bevor die Agenten starten")
    A("python3 run_framework.py --config framework --out runs_framework --seed-range 2001 2030")
    A("")
    A("# Auswertung")
    A("python3 judge.py --runs runs_v4         --prefix v4-        --scenario scenario_v3      --out judge/v4.jsonl")
    A("python3 judge.py --runs runs_hint       --prefix hinweis-   --scenario scenario_v3_hint --out judge/hint.jsonl")
    A("python3 judge.py --runs runs_framework  --prefix framework- --scenario scenario_v3      --out judge/framework.jsonl")
    A("python3 judge_sample.py --judge judge/v4.jsonl judge/hint.jsonl judge/framework.jsonl --every 5 \\")
    A("                        --out judge/sample.json      # 20-%-Stichprobe zur Handpruefung")
    A("python3 aggregate.py                                 # dieser Report")
    A("```")
    A("\nSeeds sind fest verdrahtet und stehen in jeder `run_meta`-Zeile. Der "
      "**Prompt-Fingerprint** belegt, dass innerhalb eines Arms kein Prompt "
      "veraendert wurde; der **Config-Fingerprint** erfasst zusaetzlich die "
      "Mechanik (FINAL-Sperre, Turn-Grenze, Sampling), sodass zwei Arme mit "
      "gleichen Prompts, aber unterschiedlicher Mechanik nicht verwechselt "
      "werden koennen.\n")
    A("Zwei Judge-Laeufe des Framework-Arms brauchten ein groesseres "
      "Ausgabebudget (`JUDGE_MAX_TOKENS=8000`), weil die laengeren Transkripte "
      "mehr Behauptungen enthalten; die uebrigen liefen mit dem Standardwert "
      "3000 und stiessen nicht daran. Das Budget begrenzt die Ausgabelaenge, "
      "nicht das Urteil.\n")
    A("\n### Dateien\n")
    A("| Datei | Zweck |")
    A("|---|---|")
    A("| `scenario.py` / `scenario_v3.py` / `scenario_v3_hint.py` | Szenarien, Ground Truth, Falle — austauschbar |")
    A("| `orchestrator.py` | HTTP-Arm: Isolation, Turn-Schleife, FINAL-Sperre, Metriken |")
    A("| `orchestrator_framework.py` | Framework-Arm, gleiche Metriken |")
    A("| `framework_proxy.py` | erzwingt Sampling, schneidet effektive Prompts und Modellaufrufe mit |")
    A("| `metrics.py` | Heuristiken, Ergebnis- und Konsensklassifikation |")
    A("| `stats.py` | Fisher-Exact, zweiseitig, ohne externe Abhaengigkeit |")
    A("| `judge.py` / `judge_sample.py` | Quellenzuordnung und Stichprobe zur Handpruefung |")
    A("| `aggregate.py` | dieser Report |")
    A("")

    open(out_path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    return out_path, len(all_arm_runs), len(legacy)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="report.md")
    a = p.parse_args()
    path, n_arm, n_leg = main(a.out)
    print(f"Report -> {path} ({n_arm} Arm-Laeufe, {n_leg} historische)")
