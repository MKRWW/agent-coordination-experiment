#!/usr/bin/env python3
"""
Framework-Arm: dieselbe Aufgabe, beide Seiten als Framework-Agent.

Aufbau identisch zum HTTP-Arm - getrennte Historien (hier: getrennte
das Framework-Sessions in getrennten FRAMEWORK_HOME-Verzeichnissen), byte-identische
Zustellung, FINAL-Sperre, dieselbe Turn-Grenze, dieselben Metriken.

Confounding-Kontrolle (sonst waere der Arm wertlos):
  - temperature, max_tokens und enable_thinking erzwingt framework_proxy.py auf
    exakt die Werte der anderen Arme. das Framework bietet dafuer keinen
    Konfigurationsweg.
  - Der Seed kommt ebenfalls ueber den Proxy, weil das Framework keinen kennt.
  - Der vollstaendige effektive Prompt inklusive aller vom Framework
    injizierten Bloecke wird vom Proxy protokolliert und hier je Turn
    fingerprintet.
  - Mehrfachaufrufe pro Turn werden gezaehlt und mit Token-Verbrauch
    ausgewiesen. Ein Vorteil, der nur aus mehr Token oder mehr Aufrufen
    stammt, ist kein Vorteil des Scaffoldings.
  - Toolsets und Skills sind abgeschaltet: ein Agent mit Websuche koennte die
    Isolation unterlaufen. Der Proxy belegt mit tools_count=0, dass keine
    Tool-Definitionen rausgehen.
"""
import argparse, hashlib, json, os, re, subprocess, time

import metrics
import scenario
from orchestrator import (CONTEXT_BUDGET_TOKENS, FINAL_REJECTION, KICKOFF,
                          MAX_TOKENS_PER_TURN, MAX_TURNS, TEMPERATURE, Log,
                          config_fingerprint)

CONTAINER = os.environ.get("FRAMEWORK_CONTAINER", "framework")
HOME_BASE = "$FRAMEWORK_HOME/coord-experiment"
HOST_BASE = "$FRAMEWORK_HOME/coord-experiment"
PROXY_LOG = os.environ.get("PROXY_LOG", "/tmp/framework_proxy.jsonl")
SEEDFILE = os.environ.get("PROXY_SEEDFILE", "/tmp/framework_proxy_seed.txt")

NOISE = re.compile(r"^\s*(session_id:|⚠|✓|Loading|Resuming)", re.M)


def proxy_offset():
    try:
        return sum(1 for _ in open(PROXY_LOG, encoding="utf-8"))
    except FileNotFoundError:
        return 0


def proxy_slice(start):
    try:
        rows = [json.loads(l) for l in open(PROXY_LOG, encoding="utf-8")]
    except FileNotFoundError:
        return []
    return rows[start:]


class FrameworkAgent:
    """Eine das Framework-Instanz mit eigenem FRAMEWORK_HOME und eigener Session."""

    def __init__(self, name, run_id):
        self.name = name
        self.home = f"{HOME_BASE}/{name}"
        self.host_home = f"{HOST_BASE}/{name}"
        self.session = None
        self.session_name = f"coord-{run_id}-{name}"

    def send(self, text):
        qfile_host = os.path.join(self.host_home, ".coord_query.txt")
        with open(qfile_host, "w", encoding="utf-8") as fh:
            fh.write(text)
        qfile = f"{self.home}/.coord_query.txt"
        cmd = ["docker", "exec", "-e", f"FRAMEWORK_HOME={self.home}", CONTAINER,
               "framework", "chat", "--query-file", qfile, "-Q"]
        if self.session:
            cmd += ["-r", self.session]
        else:
            cmd += ["-c", self.session_name, "--create-if-missing"]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        dt = time.time() - t0
        out = p.stdout or ""
        m = re.search(r"session_id:\s*(\S+)", out)
        if m:
            self.session = m.group(1)
        body = NOISE.sub("", out).strip()
        return {"content": body, "latency_s": round(dt, 2),
                "returncode": p.returncode, "stderr": (p.stderr or "")[-400:]}


def run(seed, run_id, out_dir, max_turns=MAX_TURNS, final_lock=True,
        arm="framework"):
    open(SEEDFILE, "w").write(str(seed))
    os.makedirs(out_dir, exist_ok=True)
    run_proxy_start = proxy_offset()
    log = Log(os.path.join(out_dir, f"{run_id}.jsonl"))

    agents = {"A": FrameworkAgent("A", run_id), "B": FrameworkAgent("B", run_id)}
    shadow = {"A": [{"role": "system", "content": scenario.SYSTEM_A}],
              "B": [{"role": "system", "content": scenario.SYSTEM_B}]}
    shadow["A"].append({"role": "user", "content": KICKOFF})
    sent = {"A": [], "B": []}
    received_blob = {"A": "", "B": ""}
    received_count = {"A": 0, "B": 0}
    has_asked = {"A": False, "B": False}
    final = {"A": None, "B": None}
    final_turn = {"A": None, "B": None}
    first_ks_q = None
    metric_events, premature_finals, framework_overhead = [], [], []
    pending_contradiction = None
    abort_reason = None

    log.write({
        "type": "run_meta", "run_id": run_id, "seed": seed,
        "scenario_id": scenario.SCENARIO_ID,
        "scenario_version": scenario.SCENARIO_VERSION,
        "scenario_fingerprint": scenario.scenario_fingerprint(),
        "arm": arm, "final_lock": final_lock,
        "config_fingerprint": config_fingerprint(
            scenario.scenario_fingerprint(), final_lock, max_turns),
        "backend": "framework", "container": CONTAINER,
        "framework_homes": {k: v.home for k, v in agents.items()},
        "sampling": {"temperature": TEMPERATURE, "seed": seed,
                     "max_tokens": MAX_TOKENS_PER_TURN,
                     "chat_template_kwargs": {"enable_thinking": False},
                     "enforced_by": "framework_proxy.py",
                     "identical_for_both_agents": True},
        "context_budget_tokens": CONTEXT_BUDGET_TOKENS, "max_turns": max_turns,
        "system_prompt_A": scenario.SYSTEM_A,
        "system_prompt_B": scenario.SYSTEM_B,
        "kickoff_note": "Nur A erhaelt den Orchestrator-Kickoff; B's erste "
                        "Nachricht ist A's Text. Bewusste Asymmetrie.",
        "isolation_note": "Toolsets und Skills abgeschaltet - ein Agent mit "
                          "Websuche koennte die Isolation unterlaufen.",
    })
    log.write({"type": "orchestrator_message", "to": "A", "turn": 0,
               "content": KICKOFF})

    inbox = {"A": [KICKOFF], "B": []}

    for turn in range(1, max_turns + 1):
        agent = "A" if turn % 2 == 1 else "B"
        other = "B" if agent == "A" else "A"
        if not inbox[agent]:
            continue
        payload = inbox[agent].pop(0)

        off = proxy_offset()
        try:
            res = agents[agent].send(payload)
        except Exception as e:                        # noqa: BLE001
            abort_reason = f"das Framework-Fehler bei Turn {turn} ({agent}): {e}"
            log.write({"type": "abort", "turn": turn, "reason": abort_reason})
            break
        calls = proxy_slice(off)
        content = res["content"].strip()
        if not content:
            abort_reason = (f"Leere Antwort von das Framework bei Turn {turn} "
                            f"({agent}); rc={res['returncode']} "
                            f"stderr={res['stderr'][:200]}")
            log.write({"type": "abort", "turn": turn, "reason": abort_reason})
            break

        shadow[agent].append({"role": "assistant", "content": content})
        sent[agent].append(content)

        # --- Framework-Overhead dieses Turns -------------------------------
        eff = [c for c in calls if c.get("streamed")] or calls
        eff_prompt = eff[-1]["messages"] if eff else []
        eff_blob = json.dumps(eff_prompt, ensure_ascii=False, sort_keys=True)
        ov = {
            "turn": turn, "agent": agent,
            "model_calls": len(calls),
            "total_tokens": sum((c.get("usage") or {}).get("total_tokens", 0)
                                for c in calls),
            "prompt_tokens_main": (eff[-1].get("usage") or {}).get("prompt_tokens")
                                  if eff else None,
            "completion_tokens_main": (eff[-1].get("usage") or {}).get("completion_tokens")
                                      if eff else None,
            "system_prompt_chars": eff[-1]["system_prompt_chars"] if eff else None,
            "own_set_chars": len(scenario.SYSTEM_A if agent == "A"
                                 else scenario.SYSTEM_B),
            "tools_count": eff[-1]["tools_count"] if eff else None,
            "effective_prompt_fingerprint": hashlib.sha256(eff_blob.encode()).hexdigest()[:16],
            "seed_seen_by_proxy": eff[-1].get("seed") if eff else None,
            "forced_sampling": eff[-1].get("forced") if eff else None,
            "side_calls": [{"call_no": c["call_no"],
                            "system_prompt_chars": c["system_prompt_chars"],
                            "usage": c.get("usage"),
                            "original_sampling": c.get("original_sampling")}
                           for c in calls if not c.get("streamed")],
        }
        ov["framework_injected_chars"] = (
            (ov["system_prompt_chars"] or 0) - ov["own_set_chars"])
        framework_overhead.append(ov)
        log.write({"type": "framework_overhead", **ov,
                   "effective_system_prompt": eff[-1]["messages"][0]["content"]
                   if eff and eff[-1]["messages"] else None})

        # --- Heuristiken (identisch zum HTTP-Arm) --------------------------
        q = metrics.classify_questions(content)
        halluc = metrics.find_unsupported(content, agent, received_blob[agent])
        role_exit = metrics.classify_role_exit(content, has_asked[agent])
        fin = metrics.extract_final(content)
        injected = metrics.detect_contradiction_injection(content, agent)

        contradiction_response = None
        if pending_contradiction and pending_contradiction["receiver"] == agent:
            pair = pending_contradiction["pair"]
            cls = metrics.classify_contradiction_response(content, pair)
            contradiction_response = {
                "contradiction_id": pair["id"],
                "injected_at_turn": pending_contradiction["turn"],
                "responder": agent, "class": cls["class"], "quote": cls["quote"],
                "resolution_note": pair["resolution"]}
            metric_events.append({"metric": "contradiction_response",
                                  "turn": turn, **contradiction_response})
            log.write({"type": "metric_event", "metric": "contradiction_response",
                       "turn": turn, **contradiction_response})
            pending_contradiction = None

        if q["knowledge_state"] and first_ks_q is None:
            first_ks_q = {"turn": turn, "agent": agent,
                          "quote": q["knowledge_state"][0]["quote"]}
            log.write({"type": "metric_event",
                       "metric": "first_knowledge_state_question", "turn": turn,
                       "agent": agent, "quote": q["knowledge_state"][0]["quote"]})
        for h in q["knowledge_state"]:
            metric_events.append({"metric": "knowledge_state_question",
                                  "turn": turn, "agent": agent, **h})
        for h in q["fact_question"]:
            metric_events.append({"metric": "fact_question", "turn": turn,
                                  "agent": agent, **h})
        for h in halluc:
            metric_events.append({"metric": "knowledge_hallucination",
                                  "turn": turn, "agent": agent, **h})
            log.write({"type": "metric_event", "metric": "knowledge_hallucination",
                       "turn": turn, "agent": agent, **h,
                       "note": "Heuristik-Verdacht - Klartext zur Nachpruefung"})
        for h in role_exit["pattern_hits"]:
            metric_events.append({"metric": "role_exit", "turn": turn,
                                  "agent": agent, "signal": "pattern", **h})
        for h in role_exit["structural"]:
            metric_events.append({"metric": "role_exit", "turn": turn,
                                  "agent": agent, "signal": "structural", **h})

        if q["any_question"]:
            has_asked[agent] = True
        if injected:
            pair = next(p for p in scenario.CONTRADICTION_PAIRS
                        if p["id"] == injected[0]["contradiction_id"])
            pending_contradiction = {"pair": pair, "turn": turn, "receiver": other}
            log.write({"type": "metric_event", "metric": "contradiction_injected",
                       "turn": turn, "agent": agent, **injected[0]})

        final_rejected = False
        if fin and final_lock and received_count[agent] == 0:
            final_rejected = True
            premature_finals.append({"turn": turn, "agent": agent, "final": fin,
                                     "quote": content})
            log.write({"type": "metric_event", "metric": "premature_final",
                       "turn": turn, "agent": agent, "final": fin,
                       "note": "FINAL vor der ersten Nachricht des Gegenuebers "
                               "- zurueckgewiesen, Lauf laeuft weiter"})
        elif fin and final[agent] is None:
            final[agent] = fin
            final_turn[agent] = turn

        log.write({"type": "turn", "turn": turn, "agent": agent,
                   "content": content, "latency_s": res["latency_s"],
                   "framework": {"model_calls": ov["model_calls"],
                                 "total_tokens": ov["total_tokens"],
                                 "prompt_tokens_main": ov["prompt_tokens_main"]},
                   "usage": {"prompt_tokens": ov["prompt_tokens_main"],
                             "completion_tokens": ov["completion_tokens_main"],
                             "total_tokens": ov["total_tokens"]},
                   "prompt_tokens_before": ov["prompt_tokens_main"],
                   "token_count_method": "proxy",
                   "finish_reason": None, "attempts": 1,
                   "heuristics": {
                       "knowledge_state_question": q["knowledge_state"],
                       "fact_question": q["fact_question"],
                       "any_question": q["any_question"],
                       "hallucination_suspects": halluc,
                       "role_exit": role_exit, "final": fin,
                       "final_valid": bool(fin) and not final_rejected,
                       "final_rejected": final_rejected,
                       "contradiction_injected": injected,
                       "contradiction_response": contradiction_response}})

        if final_rejected:
            shadow[agent].append({"role": "user", "content": FINAL_REJECTION})
            inbox[agent].append(FINAL_REJECTION)
            log.write({"type": "orchestrator_message", "to": agent, "turn": turn,
                       "content": FINAL_REJECTION, "reason": "premature_final"})

        shadow[other].append({"role": "user", "content": content})
        inbox[other].append(content)
        received_blob[other] += "\n" + content
        received_count[other] += 1

        if final["A"] and final["B"]:
            break

    # --- Isolationspruefung: Schattenhistorie UND echte Proxy-Prompts -------
    from orchestrator import isolation_check
    iso = isolation_check(shadow["A"], shadow["B"], sent["A"], sent["B"])
    # Zusaetzlich: die TATSAECHLICH gesendeten Prompts. Der Orchestrator sieht
    # nur seine Schattenhistorie - was das Framework ans Modell schickt, weiss
    # nur der Proxy. Kein einziger Request darf beide Datenbloecke enthalten.
    leaks, checked = [], 0
    for rec in proxy_slice(run_proxy_start):
        blob = json.dumps(rec.get("messages", []), ensure_ascii=False)
        checked += 1
        has_a = "BEGINN LOGAUSSCHNITTE" in blob
        has_b = "BEGINN CONFIG-DIFF" in blob
        if has_a and has_b:
            leaks.append({"call_no": rec.get("call_no"),
                          "problem": "Request enthaelt BEIDE Datensets"})
    iso_proxy = {"requests_checked": checked, "leaks": leaks,
                 "passed": not leaks}
    if leaks:
        iso["passed"] = False
        iso["problems"] = iso.get("problems", []) + [
            f"Proxy: {len(leaks)} Request(s) mit beiden Datensets"]
    log.write({"type": "isolation_check", **iso, "proxy_check": iso_proxy,
               "note": "Zwei Ebenen: Schattenhistorie des Orchestrators plus "
                       "die tatsaechlich an das Modell gesendeten Prompts aus "
                       "dem Proxy-Mitschnitt."})

    sol = {a: metrics.classify_solution(final[a]) for a in ("A", "B")}
    outcome = metrics.classify_run_outcome(sol["A"], sol["B"])
    cons = metrics.consensus_of(final["A"], final["B"], sol["A"], sol["B"])
    log.write({"type": "consensus", **cons})
    turns_used = len([m for h in shadow.values() for m in h
                      if m["role"] == "assistant"])
    solve_turn = min([t for t in final_turn.values() if t], default=None)

    result = {
        "type": "run_result", "run_id": run_id, "seed": seed,
        "turns_used": turns_used, "abort_reason": abort_reason,
        "isolation_passed": iso["passed"],
        "metric_1_first_knowledge_state_question": first_ks_q,
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
                                and e["agent"] == a) for a in ("A", "B")}},
        "metric_3_contradiction": [e for e in metric_events
                                   if e["metric"] == "contradiction_response"],
        "metric_4_solution": {
            "outcome_class": outcome, "consensus": cons,
            "verdict": sol["A"]["verdict"] if sol["A"]["verdict"] != "none"
                       else sol["B"]["verdict"],
            "solve_turn": solve_turn,
            "trap_hit": sol["A"]["trap_hit"] or sol["B"]["trap_hit"],
            "per_agent": {a: {"final": final[a], "final_turn": final_turn[a],
                              **sol[a]} for a in ("A", "B")}},
        "metric_5_role_exit": {
            "count": sum(1 for e in metric_events if e["metric"] == "role_exit"),
            "events": [e for e in metric_events if e["metric"] == "role_exit"]},
        "metric_6_premature_finals": {
            "count": len(premature_finals),
            "by_agent": {a: sum(1 for e in premature_finals if e["agent"] == a)
                         for a in ("A", "B")},
            "events": premature_finals},
        "framework_overhead": {
            "total_model_calls": sum(o["model_calls"] for o in framework_overhead),
            "total_tokens": sum(o["total_tokens"] for o in framework_overhead),
            "calls_per_turn": [o["model_calls"] for o in framework_overhead],
            "injected_chars_median": sorted(
                o["framework_injected_chars"] for o in framework_overhead)[
                    len(framework_overhead) // 2] if framework_overhead else None,
            "per_turn": framework_overhead},
        "counts": {
            "knowledge_state_questions": sum(
                1 for e in metric_events if e["metric"] == "knowledge_state_question"),
            "other_questions": sum(
                1 for e in metric_events if e["metric"] == "fact_question")},
        "heuristic_disclaimer": "Alle Klassifikationen sind heuristische "
                                "Vorschlaege. Volltexte im selben File.",
    }
    log.write(result)
    log.close()
    return result, os.path.join(out_dir, f"{run_id}.jsonl")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--out", default="runs_framework")
    p.add_argument("--max-turns", type=int, default=MAX_TURNS)
    a = p.parse_args()
    res, path = run(a.seed, a.run_id, a.out, a.max_turns)
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("framework_overhead",)},
                     ensure_ascii=False, indent=2)[:2000])
    print("Log:", path)
