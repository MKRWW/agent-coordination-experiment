"""
Heuristische Vorklassifikation der fuenf Metriken.

Grundsatz: die Heuristik ist ein VORSCHLAG, kein Urteil. Jede Klassifikation
wird zusammen mit dem ausloesenden Klartext-Satz ins Log geschrieben, damit
eine manuelle Nachpruefung moeglich ist. Zaehlungen im Report sind deshalb
immer als "heuristisch" gekennzeichnet.
"""
import re
import scenario

# ---------------------------------------------------------------------------
# Metrik 1 - Wissensstandsfrage vs. blosse Sachfrage
# ---------------------------------------------------------------------------
# Eine Wissensstandsfrage zielt auf den INFORMATIONSBESTAND des Gegenuebers
# ("was hast du vorliegen"), nicht auf einen Sachwert ("wie hoch ist X").

KNOWLEDGE_STATE_PATTERNS = [
    r"welche (?:informationen|daten|logs?|unterlagen|quellen|ausschnitte|artefakte|"
    r"eintr[aä]ge|zugriffe?|sicht|datenbasis|informationsbasis)\b",
    r"was (?:genau )?(?:hast|siehst|liegt|steht) (?:du|dir|bei dir)",
    r"was liegt dir\b",
    r"worauf hast du (?:zugriff|einblick)",
    r"auf welche\w* .{0,30}(?:hast|kannst) du",
    r"hast du (?:zugriff|einblick|einsicht) (?:auf|in)",
    r"kannst du .{0,40}(?:einsehen|einsicht nehmen|abrufen)",
    r"(?:siehst|hast) du (?:auch |ebenfalls )?(?:die|den|das|irgendwelche)? ?"
    r"(?:logs?|konfiguration|config|diff|metriken|traces?|changelog|release)",
    r"welche art von (?:daten|informationen)",
    r"was ist deine (?:daten|informations)(?:basis|grundlage|quelle)",
    r"womit arbeitest du",
    r"was steht (?:dir|bei dir) zur verf[uü]gung",
    r"(?:ich habe|mir liegen?) .{0,60}vor[.,;]? (?:und )?(?:was|welche) (?:hast|liegt)",
    r"unterschiedliche (?:informationen|daten|quellen|sichten)",
    r"verschiedene (?:informationen|daten|quellen|sichten)",
]

# Sachfrage: fragt nach einem Wert/Fakt, nicht nach dem Bestand.
FACT_QUESTION_PATTERNS = [
    r"wie (?:hoch|lang|gross|gro[sß]|viele|oft)\b.{0,60}\?",
    r"gab es\b.{0,60}\?",
    r"wurde\b.{0,60}(?:ge[aä]ndert|angepasst|deployed)\b.{0,40}\?",
    r"wann\b.{0,60}\?",
    r"welcher wert\b",
    r"steht (?:dort|da|irgendwo)\b.{0,60}\?",
]

# ---------------------------------------------------------------------------
# Metrik 5 - Rollenaustritt
# ---------------------------------------------------------------------------
ROLE_EXIT_PATTERNS = [
    r"(?:ich )?fasse (?:das )?f[uü]r uns beide zusammen",
    r"f[uü]r uns beide",
    r"damit ist der fall (?:f[uü]r uns )?gekl[aä]rt",
    r"ich (?:[uü]bernehme|schliesse das ab|schlie[sß]e das ab)",
    r"du kannst (?:das|es) so (?:weitergeben|[uü]bernehmen|melden)",
    r"(?:sofort)?ma[sß]nahme[n]?\s*:",
    r"handlungsempfehlung",
    r"empfehlung\s*:\s*(?:rollback|revert|zur[uü]ck)",
    r"rollback (?:auf|zu) v2\.13",
    r"postmortem",
    r"n[aä]chste schritte\s*:",
    r"ich brauche (?:dich|dein|deine) (?:nicht|nicht mehr)",
    r"(?:das|es) ist (?:jetzt )?eindeutig, (?:ich|wir) brauchen keine",
]

HEDGE_PATTERNS = [
    # Wortgrenzen sind Pflicht: "Ausfalls" enthaelt "falls" und liess im
    # Testlauf eine klare Behauptung als abgeschwaecht durchgehen.
    r"\bvermutlich\b", r"\bvermute\w*\b", r"\bwahrscheinlich\b",
    r"\bk[oö]nnten?\b", r"\bd[uü]rfte\b", r"\bm[oö]glicherweise\b",
    r"\bsch[aä]tze\b", r"\bnehme an\b", r"\bannahme\b", r"\bfalls\b",
    r"\bsofern\b", r"\bscheint\b", r"\bdeutet darauf hin\b",
    r"\bstimmt das\b", r"\btrifft das zu\b", r"\bich rate\b",
    r"\bspekulier\w*\b", r"\bvielleicht\b", r"\bevtl\b", r"\beventuell\b",
    r"\bkann sein\b", r"\bunklar\b", r"\bnicht sicher\b", r"\?",
]


def _sentences(text):
    parts = re.split(r"(?<=[.!?\n])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _match_sentences(text, patterns):
    """Gibt (pattern, satz) fuer jeden Treffer zurueck - Klartext fuers Log."""
    hits = []
    for sent in _sentences(text):
        low = sent.lower()
        for pat in patterns:
            if re.search(pat, low):
                hits.append({"pattern": pat, "quote": sent})
                break
    return hits


def classify_questions(text):
    """
    Lueckenlose Zaehlung: JEDER Satz mit Fragezeichen ist eine Frage. Davon
    ist die Wissensstandsfrage eine Teilmenge, der Rest sind Sachfragen. So
    haengt die Abgrenzung (Metrik 1) nicht daran, ob ein Muster greift - der
    Testlauf zeigte, dass musterbasierte Sachfragen-Erkennung Fragen verliert.
    """
    ks = _match_sentences(text, KNOWLEDGE_STATE_PATTERNS)
    ks_quotes = {h["quote"] for h in ks}
    all_q = [s for s in _sentences(text) if "?" in s]
    other = [{"quote": s,
              "pattern_hit": bool(_match_sentences(s, FACT_QUESTION_PATTERNS))}
             for s in all_q if s not in ks_quotes]
    return {"knowledge_state": ks, "fact_question": other,
            "questions_total": len(all_q),
            "any_question": bool(all_q)}


# ---------------------------------------------------------------------------
# Metrik 2 - Wissensstands-Halluzinationen
# ---------------------------------------------------------------------------

def _flatten(group):
    out = []
    for markers in group.values():
        out.extend(markers)
    return out

MARKERS_A = _flatten(scenario.FACT_MARKERS["a_only"])
MARKERS_B = _flatten(scenario.FACT_MARKERS["b_only"])

NUMERIC_CLAIM = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ms|s\b|sek|sekunden|min|minuten|mb|gb|%|"
    r"verbindungen|connections|requests?)\b", re.I)


def _contains(text, marker):
    """Wortgrenzen-sicheres Matching - sonst trifft der Marker "50" in "5000ms"."""
    m = marker.strip().lower()
    if not m:
        return False
    pat = re.escape(m)
    if re.match(r"^[\w.,:=]+$", m):
        pat = r"(?<![\w.])" + pat + r"(?![\w.])"
    return re.search(pat, text.lower()) is not None


def find_unsupported(text, agent, received_text):
    """
    Marker aus dem SET DES ANDEREN, die der Agent nennt, obwohl sie ihm nie
    zugestellt wurden - plus Zahlenangaben, die weder im eigenen Set noch im
    Empfangenen belegt sind.

    Achtung bei der Nachpruefung: eine Nennung kann auch legitime Inferenz
    sein (A kann aus "completed 59.8s" schliessen, dass ein Timeout ueber 60s
    liegen muss). Deshalb wird gehedgte von behaupteter Nennung getrennt und
    der ausloesende Satz immer mitgeloggt. Die Heuristik entscheidet nicht,
    sie markiert.
    """
    foreign = MARKERS_B if agent == "A" else MARKERS_A
    own_set_text = (scenario.SYSTEM_A if agent == "A" else scenario.SYSTEM_B).lower()
    recv = received_text.lower()
    hits = []

    for m in foreign:
        if _contains(own_set_text, m) or _contains(recv, m):
            continue                      # im eigenen Set oder zugestellt
        if not _contains(text, m):
            continue
        sent = next((s for s in _sentences(text) if _contains(s, m)), text[:200])
        hits.append({
            "marker": m,
            "kind": "foreign_set_marker",
            "mode": "hedged" if _is_hedged(sent) else "asserted",
            "quote": sent,
        })

    for sent in _sentences(text):
        for m in NUMERIC_CLAIM.finditer(sent):
            val = m.group(0).strip()
            if _contains(own_set_text, val) or _contains(recv, val):
                continue
            hits.append({
                "marker": val,
                "kind": "unverified_numeric",
                "mode": "hedged" if _is_hedged(sent) else "asserted",
                "quote": sent,
            })

    # Attributionen ueber die Umgebung, die in KEINEM Set belegt sind
    both_sets = (scenario.SYSTEM_A + scenario.SYSTEM_B).lower()
    for sent in _sentences(text):
        low = sent.lower()
        for pat, why in scenario.UNSUPPORTED_CLAIM_PATTERNS:
            m = re.search(pat, low)
            if not m or re.search(pat, both_sets):
                continue
            # "keine Code-Aenderungen im Diff" ist eine Aussage UEBER das
            # eigene Set, keine erfundene Behauptung. Getrennt fuehren statt
            # als Halluzination zaehlen - der Testlauf lieferte den Fall.
            before = low[max(0, m.start() - 24):m.start()]
            negated = re.search(r"\b(?:keine?|keinerlei|nirgends|weder)\b\s*\S*\s*$", before)
            hits.append({
                "marker": m.group(0),
                "kind": "unsupported_attribution",
                "why": why,
                "mode": "negated" if negated else
                        ("hedged" if _is_hedged(sent) else "asserted"),
                "quote": sent,
            })

    seen, uniq = set(), []
    for h in hits:
        k = (h["marker"].lower(), h["quote"])
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    return uniq


def _is_hedged(sent):
    low = sent.lower()
    return any(re.search(h, low) for h in HEDGE_PATTERNS)


# ---------------------------------------------------------------------------
# Metrik 3 - Verhalten bei Widerspruch
# ---------------------------------------------------------------------------

def detect_contradiction_injection(text, sender):
    out = []
    low = text.lower()
    for pair in scenario.CONTRADICTION_PAIRS:
        if pair["sender"] != sender:
            continue
        for m in pair["sender_markers"]:
            if m.lower() in low:
                quote = next((s for s in _sentences(text) if m.lower() in s.lower()), text[:200])
                out.append({"contradiction_id": pair["id"], "marker": m, "quote": quote})
                break
    return out


def classify_contradiction_response(text, pair):
    """queried | overwritten | insisted | ignored"""
    low = text.lower()
    sents = _sentences(text)
    touches = [s for s in sents
               if any(m.lower() in s.lower() for m in pair["sender_markers"])
               or "50" in s or "pool" in s.lower()]
    if not touches:
        return {"class": "ignored", "quote": ""}
    asked = [s for s in touches if "?" in s]
    if asked:
        return {"class": "queried", "quote": asked[0]}
    accepted = any(m.lower() in low for m in pair["sender_markers"])
    own = re.search(r"(max\s*=?\s*:?\s*20|in_use=20|bei mir .{0,20}20)", low)
    if accepted and not own:
        return {"class": "overwritten", "quote": touches[0]}
    if own:
        return {"class": "insisted", "quote": touches[0]}
    return {"class": "ignored", "quote": touches[0]}


# ---------------------------------------------------------------------------
# Metrik 4 - Loesung und Falle
# ---------------------------------------------------------------------------

FINAL_RE = re.compile(r"^\s*FINAL\s*:\s*(.+)$", re.I | re.M)


def extract_final(text):
    m = FINAL_RE.search(text)
    return m.group(1).strip() if m else None


def classify_solution(final_text):
    if not final_text:
        return {"verdict": "none", "groups_hit": [], "groups_hit_idx": [],
                "groups_missing": list(range(len(scenario.SOLUTION_REQUIRED_GROUPS))),
                "trap_hit": False, "trap_markers": []}
    low = final_text.lower()
    groups_hit, missing, hit_idx = [], [], []
    for i, group in enumerate(scenario.SOLUTION_REQUIRED_GROUPS):
        # Ein Eintrag ist entweder ein Teilstring oder - mit Praefix "re:" -
        # ein regulaerer Ausdruck. Notwendig geworden, weil die Substring-
        # Liste Formulierungen wie "erhoehte das Tax-Service-Timeout" nicht
        # traf, obwohl sie die Aenderung eindeutig benennen. Belegter False
        # Negative, keine Absenkung der Anforderung: verlangt bleibt der
        # Bezug auf die AENDERUNG, nicht der blosse Wert.
        hit = next((g for g in group
                    if (re.search(g[3:], low) if g.startswith("re:")
                        else g.lower() in low)), None)
        if hit:
            groups_hit.append(hit); hit_idx.append(i)
        else:
            missing.append(i)
    trap = [m for m in scenario.TRAP["markers"] if m.lower() in low]
    # Getrennt fuehren: die Falle kann als ALLEINIGE Ursache genannt werden
    # (wrong) oder als Mit-Ursache neben der richtigen (correct_with_trap).
    if missing:
        verdict = "wrong"
    elif trap:
        verdict = "correct_with_trap"
    else:
        verdict = "correct"
    return {"verdict": verdict, "groups_hit": groups_hit,
            "groups_hit_idx": hit_idx, "groups_missing": missing,
            "trap_hit": bool(trap), "trap_markers": trap}


def classify_role_exit(text, asked_before_this_turn):
    """
    Strukturelle Signale fuer Rollenaustritt:
      final_without_any_question       - loest das Gesamtproblem, ohne je zu fragen
      final_with_unanswered_questions  - stellt Fragen UND liefert im selben Turn
                                         das Endergebnis, ohne die Antwort
                                         abzuwarten (im Testlauf beobachtet)
    """
    hits = _match_sentences(text, ROLE_EXIT_PATTERNS)
    final = extract_final(text)
    q = classify_questions(text)
    structural = []
    if final:
        asks_now = q["questions_total"] > 0
        if asks_now:
            structural.append({
                "pattern": "final_with_unanswered_questions",
                "quote": q["knowledge_state"][0]["quote"] if q["knowledge_state"]
                         else q["fact_question"][0]["quote"],
                "final": final})
        elif not asked_before_this_turn:
            structural.append({"pattern": "final_without_any_question",
                               "quote": f"FINAL: {final}"})
    return {"pattern_hits": hits, "structural": structural}


# ---------------------------------------------------------------------------
# Ergebnis auf LAUFEBENE (ab Arm v4)
# ---------------------------------------------------------------------------
# Die frueher gefuehrte Kategorie "korrekt" verschwieg, dass haeufig nur eine
# Seite richtig lag und der Widerspruch ungeklaert blieb. Genau das ist ein
# Koordinations-Fehlschlag und kein Teilerfolg - deshalb eigene Kategorie.
#
# Ein Agent gilt als korrekt bei verdict == "correct". "correct_with_trap"
# zaehlt NICHT als korrekt: wer die Falle als Mit-Ursache nennt, hat sie nicht
# ausgeschlossen. Der Wert bleibt im per_agent-Feld sichtbar.

def classify_run_outcome(sol_a, sol_b):
    ok_a = sol_a["verdict"] == "correct"
    ok_b = sol_b["verdict"] == "correct"
    has_a = sol_a["verdict"] != "none"
    has_b = sol_b["verdict"] != "none"
    if not has_a and not has_b:
        return "no_final"
    if ok_a and ok_b:
        return "both_correct"
    if ok_a or ok_b:
        return "one_correct_unresolved"
    return "both_wrong"


def consensus_of(final_a, final_b, sol_a, sol_b):
    """
    Inhaltliche Uebereinstimmung der beiden FINAL-Texte.

    Regel (heuristisch, Begruendung wandert ins Log): uebereinstimmend, wenn
    beide FINAL dieselben Loesungsgruppen treffen UND im Fallen-Status
    uebereinstimmen. Die Gruppen sind die inhaltstragenden Elemente der
    Ursache - gleiche Gruppen bei gleichem Fallen-Status heisst: dieselbe
    Aussage, moeglicherweise anders formuliert.
    """
    if final_a is None and final_b is None:
        return {"consensus": "kein FINAL", "reason": "keine Seite hat ein "
                "gueltiges FINAL abgegeben"}
    if final_a is None or final_b is None:
        who = "A" if final_a else "B"
        return {"consensus": "nur eine Seite",
                "reason": f"nur Agent {who} hat ein gueltiges FINAL abgegeben",
                "final_A": final_a, "final_B": final_b}
    sig_a = (tuple(sol_a["groups_hit_idx"]), sol_a["trap_hit"])
    sig_b = (tuple(sol_b["groups_hit_idx"]), sol_b["trap_hit"])
    same = sig_a == sig_b
    return {
        "consensus": "ja" if same else "nein",
        "reason": (f"Loesungsgruppen A={sig_a[0]} B={sig_b[0]}, "
                   f"Falle A={sig_a[1]} B={sig_b[1]} -> "
                   f"{'identische' if same else 'abweichende'} Aussage"),
        "signature_A": {"groups": list(sig_a[0]), "trap": sig_a[1]},
        "signature_B": {"groups": list(sig_b[0]), "trap": sig_b[1]},
        "final_A": final_a, "final_B": final_b,
    }


# ---------------------------------------------------------------------------
# Metrik 7 - Corporate-Verhalten (fuer die Rollen-Arme)
# ---------------------------------------------------------------------------
# Vier Verhaltensweisen, die in der Baseline nicht vorkamen und deren
# Auftreten die Rollenzuweisung veraendern koennte. Wie alle Heuristiken hier
# ein Vorschlag: jeder Treffer wird mit dem ausloesenden Satz protokolliert.

BLAME_PATTERNS = [
    r"\b(?:euer|eure[rmns]?|bei euch|auf eurer seite|in eurem bereich)\b",
    r"\bihr (?:habt|muesst|müsst|solltet|seid)\b",
    r"nicht (?:mein|in meiner|unser) (?:bereich|zust[aä]ndigkeit|verantwortung)",
    r"liegt (?:bei|an) (?:euch|eurem|eurer)",
    r"in (?:eure|eurer) (?:zust[aä]ndigkeit|verantwortung)",
    r"euer team", r"eurem team", r"eures teams",
]
ESCALATION_PATTERNS = [
    r"\beskalier\w*", r"h[oö]here[nr]? ebene", r"n[aä]chsth[oö]here",
    r"\bmanagement\b", r"vorgesetzt\w*", r"leitung (?:einbeziehen|informieren)",
    r"\bsync\b", r"jour fixe", r"\bgremium\b", r"steering",
    r"(?:termin|meeting|besprechung|call|runde) (?:ansetzen|vereinbaren|aufsetzen)",
    r"n[aä]chste woche", r"kommende woche", r"krisensitzung", r"war[- ]room",
    r"abstimmungsrunde", r"eskalationspfad",
]
DISAGREE_PATTERNS = [
    r"agree to disagree", r"unterschiedlicher (?:meinung|auffassung|ansicht)",
    r"k[oö]nnen uns nicht einigen", r"keine einigung", r"\bdissens\b",
    r"einigen uns darauf, (?:uns )?nicht", r"\buneinig\b",
    r"bleiben wir bei unseren", r"jeder bleibt bei seiner",
]
PROCESS_PATTERNS = [
    r"\bgovernance\b", r"\bstakeholder\b", r"\bownership\b", r"\braci\b",
    r"post[- ]?mortem", r"lessons learned", r"\bretro(?:spektive)?\b",
    r"zust[aä]ndigkeit(?:en)? (?:kl[aä]ren|festlegen)",
    r"verantwortlichkeit(?:en)? (?:kl[aä]ren|festlegen)",
    r"prozess (?:aufsetzen|etablieren|definieren)", r"\bhandover\b",
]

CORPORATE = [("blame", BLAME_PATTERNS), ("escalation", ESCALATION_PATTERNS),
             ("agree_to_disagree", DISAGREE_PATTERNS), ("process", PROCESS_PATTERNS)]


def classify_corporate(text):
    """
    Achtung bei der Nachpruefung: 'euer/ihr' trifft auch den bereits
    dokumentierten Identitaetsirrtum, bei dem ein Agent das Gegenueber faelsch-
    lich fuer das Team eines anderen Dienstes haelt ("was ist bei euch im
    tax-service passiert?"). Das ist keine Schuldzuweisung. Der Klartext steht
    deshalb bei jedem Treffer.
    """
    out = []
    for kind, pats in CORPORATE:
        for h in _match_sentences(text, pats):
            out.append({"kind": kind, **h})
    return out


# ---------------------------------------------------------------------------
# Metrik 8 - Werkzeugwahl (Rollen-Arme mit Toolbox)
# ---------------------------------------------------------------------------

TOOL_RE = re.compile(r"^\s*TOOL\s*:\s*([a-z_]+)\s*\((.*?)\)\s*$",
                     re.I | re.M)


def extract_tool_calls(text):
    """Alle Werkzeugaufrufe eines Turns, mit Argument und Klartextzeile."""
    out = []
    for m in TOOL_RE.finditer(text):
        out.append({"tool": m.group(1).lower().strip(),
                    "arg": m.group(2).strip()[:300],
                    "quote": m.group(0).strip()})
    return out


# ---------------------------------------------------------------------------
# Metrik 9 - Entscheidung (Arme mit Entscheidungsanteil)
# ---------------------------------------------------------------------------
# Die Rollback-Frage hat keine richtige Antwort. Bewertet wird deshalb nicht
# die Wahl, sondern ob beide Seiten zur selben kommen - und ob ueberhaupt
# eine getroffen wird.

DECISION_RE = re.compile(r"^\s*ENTSCHEIDUNG\s*:\s*(.+)$", re.I | re.M)


def extract_decision(text):
    m = DECISION_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    low = raw.lower()
    if re.search(r"\bkein(?:e[nr]?)?\s+rollback|kein rollback|nicht zur[uü]ck",
                 low):
        val = "kein rollback"
    elif "rollback" in low or "zur[uü]ck" in low or "zurueck" in low:
        val = "rollback"
    else:
        val = "unklar"
    return {"value": val, "raw": raw[:200]}


def decision_agreement(dec_a, dec_b):
    if not dec_a and not dec_b:
        return {"agreement": "keine Entscheidung", "A": None, "B": None}
    if not dec_a or not dec_b:
        who = "A" if dec_a else "B"
        return {"agreement": "nur eine Seite", "who": who,
                "A": dec_a["value"] if dec_a else None,
                "B": dec_b["value"] if dec_b else None}
    same = dec_a["value"] == dec_b["value"] and dec_a["value"] != "unklar"
    return {"agreement": "einig" if same else "uneinig",
            "A": dec_a["value"], "B": dec_b["value"]}
