#!/usr/bin/env python3
"""
Zwei-Agenten-Koordinationsexperiment - Orchestrator.

Der Orchestrator ist die EINZIGE Verbindung zwischen den Agenten. Keine
Agent-Bibliothek, nur HTTP gegen den OpenAI-kompatiblen Chat-Endpoint.

Isolationsregeln (im Code durchgesetzt, nach dem Lauf maschinell geprueft):
  1. Zwei getrennte Message-Historien. A sieht nie System-Prompt oder
     Historie von B.
  2. Was A ausgibt, geht B als reiner `user`-Turn zu - byte-identisch,
     ohne Praefix, ohne Sprecherkennzeichnung.
  3. Kein System-Prompt erwaehnt, dass das Gegenueber ein Modell ist.
  4. Ground Truth und Falle bleiben im Orchestrator.
  5. Identische Sampling-Parameter fuer beide Seiten.

Bekannte Asymmetrie (bewusst, protokolliert): A erhaelt einen minimalen
Kickoff-Turn vom Orchestrator ("Der Kanal ist offen."), damit ueberhaupt
jemand anfaengt. B erhaelt keinen - seine erste user-Nachricht ist A's Text.
"""
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

import metrics
import scenario

BASE_URL = os.environ.get("COORD_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("COORD_MODEL", "local-model")

# Der Auftrag verlangt 16-32K Kontext, damit der KV-Cache die parallelen
# Sessions nicht limitiert. Der vLLM-Prozess lokal laeuft produktiv mit
# max_model_len=262144; er wird fuer dieses Experiment NICHT umkonfiguriert.
# Stattdessen ist das Budget hier hart clientseitig gesetzt: wird es
# ueberschritten, bricht der Lauf mit protokolliertem Grund ab.
CONTEXT_BUDGET_TOKENS = 32768
MAX_TOKENS_PER_TURN = 700
TEMPERATURE = 0.7
MAX_TURNS = 20

KICKOFF = "Der Kanal ist offen."
# Ab Arm v4: ein FINAL ist erst gueltig, wenn der Agent mindestens eine
# Nachricht des Gegenuebers empfangen hat. Ein zu fruehes FINAL beendet den
# Lauf nicht - es wird zurueckgewiesen und der Lauf laeuft weiter.
FINAL_REJECTION = "Noch keine Antwort des Gegenuebers erhalten."


class Endpoint:
    def __init__(self, base_url=BASE_URL, model=MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def identity(self):
        req = urllib.request.Request(f"{self.base_url}/v1/models")
        data = json.load(urllib.request.urlopen(req, timeout=30))
        for m in data["data"]:
            if m["id"] == self.model:
                return {"served_as": m["id"], "root": m.get("root"),
                        "max_model_len": m.get("max_model_len")}
        raise RuntimeError(f"Modell {self.model} nicht am Endpoint")

    def count_tokens(self, messages):
        """Exakte Prompt-Laenge ueber vLLMs /tokenize, sonst Schaetzung."""
        body = {"model": self.model, "messages": messages,
                "chat_template_kwargs": {"enable_thinking": False}}
        try:
            req = urllib.request.Request(
                f"{self.base_url}/tokenize", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=30))["count"], "tokenize"
        except Exception:
            chars = sum(len(m["content"]) for m in messages)
            return chars // 3, "estimate"

    def chat(self, messages, seed, retries=3):
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "seed": seed,
            "max_tokens": MAX_TOKENS_PER_TURN,
            # local-model3.x liefert ohne dieses Flag content=None (thinking-Falle)
            "chat_template_kwargs": {"enable_thinking": False},
        }
        last = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/v1/chat/completions",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"})
                t0 = time.time()
                resp = json.load(urllib.request.urlopen(req, timeout=300))
                dt = time.time() - t0
                content = resp["choices"][0]["message"].get("content")
                if content is None:
                    raise RuntimeError("content=None trotz enable_thinking=false")
                return {"content": content, "usage": resp["usage"],
                        "finish_reason": resp["choices"][0].get("finish_reason"),
                        "latency_s": round(dt, 2), "attempts": attempt + 1}
            except Exception as e:              # noqa: BLE001
                last = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Endpoint-Fehler nach {retries} Versuchen: {last}")


class Log:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, "w", encoding="utf-8")

    def write(self, obj):
        obj.setdefault("ts", round(time.time(), 3))
        self.fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


def isolation_check(hist_a, hist_b, sent_a, sent_b):
    """
    Maschineller Nachweis der Isolation. Prueft:
      - jede Historie beginnt mit dem eigenen System-Prompt
      - der fremde System-Prompt taucht in der Historie nicht auf
      - jede eingehende user-Nachricht ist byte-identisch mit einer vom
        Gegenueber gesendeten assistant-Nachricht (kein Praefix, keine
        Sprecherkennzeichnung)
      - Ground Truth und Fallen-Beschreibung kommen in keiner Historie vor
    """
    problems = []

    def blob(h):
        return "\n".join(m["content"] for m in h)

    if hist_a[0]["content"] != scenario.SYSTEM_A:
        problems.append("A: system-Prompt nicht an Position 0")
    if hist_b[0]["content"] != scenario.SYSTEM_B:
        problems.append("B: system-Prompt nicht an Position 0")

    blob_a, blob_b = blob(hist_a), blob(hist_b)
    # markante Zeile aus dem jeweils fremden Set
    marker_b_in_a = "--- BEGINN CONFIG-DIFF" in blob_a
    marker_a_in_b = "--- BEGINN LOGAUSSCHNITTE" in blob_b
    if marker_b_in_a:
        problems.append("A: Config-Diff-Block aus Set B in A's Historie")
    if marker_a_in_b:
        problems.append("B: Logblock aus Set A in B's Historie")

    for name, hist, sent_by_other in (("A", hist_a, sent_b), ("B", hist_b, sent_a)):
        for i, m in enumerate(hist):
            if m["role"] != "user":
                continue
            if name == "A" and i == 1 and m["content"] == KICKOFF:
                continue
            if m["content"] == FINAL_REJECTION:
                continue        # Orchestrator-Rueckweisung, protokolliert
            if m["content"] not in sent_by_other:
                problems.append(
                    f"{name}: user-Turn #{i} nicht byte-identisch mit einer "
                    f"Nachricht des Gegenuebers -> {m['content'][:80]!r}")

    for name, b in (("A", blob_a), ("B", blob_b)):
        for probe in (scenario.GROUND_TRUTH[:60], scenario.TRAP["claim"][:60],
                      scenario.TRAP["why_plausible"][:60]):
            if probe in b:
                problems.append(f"{name}: Ground-Truth/Fallen-Text in der Historie")

    return {"passed": not problems, "problems": problems}


def config_fingerprint(scen_fp, final_lock, max_turns):
    """Fingerprint des ARMS: Prompts plus die Mechanik, die sie umgibt."""
    import hashlib
    h = hashlib.sha256()
    h.update(f"{scen_fp}|final_lock={final_lock}|max_turns={max_turns}"
             f"|temp={TEMPERATURE}|max_tokens={MAX_TOKENS_PER_TURN}".encode())
    return h.hexdigest()[:16]


def run(seed, run_id, out_dir="runs", base_url=BASE_URL, model=MODEL,
        max_turns=MAX_TURNS, final_lock=False, arm=None):
    ep = Endpoint(base_url, model)
    ident = ep.identity()
    path = os.path.join(out_dir, f"{run_id}.jsonl")
    log = Log(path)

    hist = {
        "A": [{"role": "system", "content": scenario.SYSTEM_A}],
        "B": [{"role": "system", "content": scenario.SYSTEM_B}],
    }
    hist["A"].append({"role": "user", "content": KICKOFF})

    sent = {"A": [], "B": []}          # was jede Seite ausgegeben hat
    received_blob = {"A": "", "B": ""}  # was jede Seite mitgeteilt bekam
    received_count = {"A": 0, "B": 0}   # wie viele Nachrichten des Gegenuebers
    has_asked = {"A": False, "B": False}
    final = {"A": None, "B": None}
    final_turn = {"A": None, "B": None}
    first_ks_q = None                   # Metrik 1
    metric_events = []
    premature_finals = []               # Metrik 6
    pending_contradiction = None        # (pair, injected_turn, receiver)
    abort_reason = None

    log.write({
        "type": "run_meta",
        "run_id": run_id,
        "seed": seed,
        "scenario_id": scenario.SCENARIO_ID,
        "scenario_version": scenario.SCENARIO_VERSION,
        "scenario_fingerprint": scenario.scenario_fingerprint(),
        "arm": arm or ("v4" if final_lock else "legacy"),
        "final_lock": final_lock,
        "config_fingerprint": config_fingerprint(
            scenario.scenario_fingerprint(), final_lock, max_turns),
        "endpoint": base_url,
        "model_requested": model,
        "model_identity": ident,
        "sampling": {"temperature": TEMPERATURE, "seed": seed,
                     "max_tokens": MAX_TOKENS_PER_TURN,
                     "chat_template_kwargs": {"enable_thinking": False},
                     "identical_for_both_agents": True},
        "context_budget_tokens": CONTEXT_BUDGET_TOKENS,
        "max_turns": max_turns,
        "system_prompt_A": scenario.SYSTEM_A,
        "system_prompt_B": scenario.SYSTEM_B,
        "kickoff_note": "Nur A erhaelt den Orchestrator-Kickoff; B's erste "
                        "user-Nachricht ist A's Text. Bewusste Asymmetrie.",
    })
    log.write({"type": "orchestrator_message", "to": "A", "turn": 0,
               "content": KICKOFF})

    for turn in range(1, max_turns + 1):
        agent = "A" if turn % 2 == 1 else "B"
        other = "B" if agent == "A" else "A"

        n_tok, how = ep.count_tokens(hist[agent])
        if n_tok > CONTEXT_BUDGET_TOKENS:
            abort_reason = (f"Kontextbudget ueberschritten: {n_tok} > "
                            f"{CONTEXT_BUDGET_TOKENS} bei Turn {turn} ({agent})")
            log.write({"type": "abort", "turn": turn, "reason": abort_reason})
            break

        try:
            res = ep.chat(hist[agent], seed=seed)
        except Exception as e:              # noqa: BLE001
            abort_reason = f"Endpoint-Fehler bei Turn {turn} ({agent}): {e}"
            log.write({"type": "abort", "turn": turn, "reason": abort_reason})
            break

        content = res["content"].strip()
        hist[agent].append({"role": "assistant", "content": content})
        sent[agent].append(content)

        # --- Heuristiken auf diesen Turn -----------------------------------
        q = metrics.classify_questions(content)
        halluc = metrics.find_unsupported(content, agent, received_blob[agent])
        role_exit = metrics.classify_role_exit(content, has_asked[agent])
        fin = metrics.extract_final(content)
        injected = metrics.detect_contradiction_injection(content, agent)

        # Metrik 3: Reaktion auf einen im Vorturn injizierten Widerspruch
        contradiction_response = None
        if pending_contradiction and pending_contradiction["receiver"] == agent:
            pair = pending_contradiction["pair"]
            cls = metrics.classify_contradiction_response(content, pair)
            contradiction_response = {
                "contradiction_id": pair["id"],
                "injected_at_turn": pending_contradiction["turn"],
                "responder": agent,
                "class": cls["class"],
                "quote": cls["quote"],
                "resolution_note": pair["resolution"],
            }
            metric_events.append({"metric": "contradiction_response",
                                  "turn": turn, **contradiction_response})
            log.write({"type": "metric_event", "metric": "contradiction_response",
                       "turn": turn, **contradiction_response})
            pending_contradiction = None

        if q["knowledge_state"] and first_ks_q is None:
            first_ks_q = {"turn": turn, "agent": agent,
                          "quote": q["knowledge_state"][0]["quote"]}
            log.write({"type": "metric_event",
                       "metric": "first_knowledge_state_question",
                       "turn": turn, "agent": agent,
                       "quote": q["knowledge_state"][0]["quote"]})
        for h in q["knowledge_state"]:
            metric_events.append({"metric": "knowledge_state_question",
                                  "turn": turn, "agent": agent, **h})
        for h in q["fact_question"]:
            metric_events.append({"metric": "fact_question",
                                  "turn": turn, "agent": agent, **h})
        for h in halluc:
            metric_events.append({"metric": "knowledge_hallucination",
                                  "turn": turn, "agent": agent, **h})
            log.write({"type": "metric_event", "metric": "knowledge_hallucination",
                       "turn": turn, "agent": agent, **h,
                       "note": "Heuristik-Verdacht - Klartext zur Nachpruefung"})
        for h in role_exit["pattern_hits"]:
            metric_events.append({"metric": "role_exit", "turn": turn,
                                  "agent": agent, "signal": "pattern", **h})
            log.write({"type": "metric_event", "metric": "role_exit", "turn": turn,
                       "agent": agent, "signal": "pattern", **h})
        for h in role_exit["structural"]:
            metric_events.append({"metric": "role_exit", "turn": turn,
                                  "agent": agent, "signal": "structural", **h})
            log.write({"type": "metric_event", "metric": "role_exit", "turn": turn,
                       "agent": agent, "signal": "structural", **h})

        if q["any_question"]:
            has_asked[agent] = True
        if injected:
            pair = next(p for p in scenario.CONTRADICTION_PAIRS
                        if p["id"] == injected[0]["contradiction_id"])
            pending_contradiction = {"pair": pair, "turn": turn, "receiver": other}
            log.write({"type": "metric_event", "metric": "contradiction_injected",
                       "turn": turn, "agent": agent, **injected[0]})
        # --- FINAL-Sperre (Arm v4 und spaeter) -----------------------------
        final_rejected = False
        if fin and final_lock and received_count[agent] == 0:
            final_rejected = True
            premature_finals.append({"turn": turn, "agent": agent, "final": fin,
                                     "quote": content})
            log.write({"type": "metric_event", "metric": "premature_final",
                       "turn": turn, "agent": agent, "final": fin,
                       "note": "FINAL abgegeben, bevor eine Nachricht des "
                               "Gegenuebers empfangen wurde - zurueckgewiesen, "
                               "Lauf laeuft weiter"})
        elif fin and final[agent] is None:
            final[agent] = fin
            final_turn[agent] = turn

        log.write({
            "type": "turn", "turn": turn, "agent": agent,
            "content": content,
            "prompt_tokens_before": n_tok, "token_count_method": how,
            "usage": res["usage"], "latency_s": res["latency_s"],
            "finish_reason": res["finish_reason"], "attempts": res["attempts"],
            "heuristics": {
                "knowledge_state_question": q["knowledge_state"],
                "fact_question": q["fact_question"],
                "any_question": q["any_question"],
                "hallucination_suspects": halluc,
                "role_exit": role_exit,
                "final": fin,
                "final_valid": bool(fin) and not final_rejected,
                "final_rejected": final_rejected,
                "contradiction_injected": injected,
                "contradiction_response": contradiction_response,
            },
        })

        # --- Rueckweisung an den Absender, chronologisch direkt danach -----
        if final_rejected:
            hist[agent].append({"role": "user", "content": FINAL_REJECTION})
            log.write({"type": "orchestrator_message", "to": agent, "turn": turn,
                       "content": FINAL_REJECTION,
                       "reason": "premature_final"})

        # --- Zustellung an das Gegenueber: roh, ohne Praefix ----------------
        hist[other].append({"role": "user", "content": content})
        received_blob[other] += "\n" + content
        received_count[other] += 1

        if final["A"] and final["B"]:
            break

    turns_used = sum(1 for m in hist["A"] + hist["B"] if m["role"] == "assistant")
    iso = isolation_check(hist["A"], hist["B"], sent["A"], sent["B"])
    log.write({"type": "isolation_check", **iso})

    sol = {a: metrics.classify_solution(final[a]) for a in ("A", "B")}
    outcome = metrics.classify_run_outcome(sol["A"], sol["B"])
    cons = metrics.consensus_of(final["A"], final["B"], sol["A"], sol["B"])
    log.write({"type": "consensus", **cons})
    # Alt-Feld fuer die Vergleichbarkeit mit den Laeufen vor Arm v4
    verdicts = [sol["A"]["verdict"], sol["B"]["verdict"]]
    if "correct" in verdicts:
        run_verdict = "correct"
    elif "correct_with_trap" in verdicts:
        run_verdict = "correct_with_trap"
    elif "wrong" in verdicts:
        run_verdict = "wrong"
    else:
        run_verdict = "none"
    solve_turn = min([t for t in final_turn.values() if t], default=None)

    result = {
        "type": "run_result",
        "run_id": run_id,
        "seed": seed,
        "turns_used": turns_used,
        "abort_reason": abort_reason,
        "isolation_passed": iso["passed"],
        "metric_1_first_knowledge_state_question": first_ks_q,   # None = nie
        "metric_2_hallucination_suspects": {
            "total": sum(1 for e in metric_events
                         if e["metric"] == "knowledge_hallucination"),
            "asserted": sum(1 for e in metric_events
                            if e["metric"] == "knowledge_hallucination"
                            and e.get("mode") == "asserted"),
            "hedged": sum(1 for e in metric_events
                          if e["metric"] == "knowledge_hallucination"
                          and e.get("mode") == "hedged"),
            "negated": sum(1 for e in metric_events
                           if e["metric"] == "knowledge_hallucination"
                           and e.get("mode") == "negated"),
            "by_agent": {a: sum(1 for e in metric_events
                                if e["metric"] == "knowledge_hallucination"
                                and e["agent"] == a) for a in ("A", "B")},
        },
        "metric_3_contradiction": [e for e in metric_events
                                   if e["metric"] == "contradiction_response"],
        "metric_4_solution": {
            "outcome_class": outcome,
            "consensus": cons,
            "verdict_legacy": run_verdict,
            "verdict": run_verdict,
            "solve_turn": solve_turn,
            "trap_hit": sol["A"]["trap_hit"] or sol["B"]["trap_hit"],
            "per_agent": {a: {"final": final[a], "final_turn": final_turn[a],
                              **sol[a]} for a in ("A", "B")},
        },
        "metric_5_role_exit": {
            "count": sum(1 for e in metric_events if e["metric"] == "role_exit"),
            "events": [e for e in metric_events if e["metric"] == "role_exit"],
        },
        "metric_6_premature_finals": {
            "count": len(premature_finals),
            "by_agent": {a: sum(1 for e in premature_finals if e["agent"] == a)
                         for a in ("A", "B")},
            "events": premature_finals,
        },
        "counts": {
            "knowledge_state_questions": sum(
                1 for e in metric_events if e["metric"] == "knowledge_state_question"),
            "other_questions": sum(
                1 for e in metric_events if e["metric"] == "fact_question"),
        },
        "heuristic_disclaimer": "Alle Klassifikationen sind heuristische "
                                "Vorschlaege. Die Turns liegen im Volltext im "
                                "selben File und sind manuell nachpruefbar.",
    }
    log.write(result)
    log.close()
    return result, path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--out", default="runs")
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--model", default=MODEL)
    p.add_argument("--max-turns", type=int, default=MAX_TURNS)
    p.add_argument("--final-lock", action="store_true")
    p.add_argument("--arm", default=None)
    a = p.parse_args()
    rid = a.run_id or f"run-seed{a.seed}"
    os.makedirs(a.out, exist_ok=True)
    res, path = run(a.seed, rid, a.out, a.base_url, a.model, a.max_turns,
                    final_lock=a.final_lock, arm=a.arm)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"\nLog: {path}")


if __name__ == "__main__":
    main()
