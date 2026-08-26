#!/usr/bin/env python3
"""
Mitschnitt-Proxy zwischen das Framework und vLLM.

Zweck (drei Anforderungen des Framework-Arms in einem):
  1. Sampling-Parameter erzwingen. das Framework bietet keinen Konfigurationsweg fuer
     temperature/max_tokens; ohne Angleichung waere ein Vorteil des Frameworks
     nicht von einem Vorteil aus mehr Token zu unterscheiden. Der Proxy
     ueberschreibt genau drei Felder auf die Werte der anderen Arme:
     temperature=0.7, max_tokens=700, chat_template_kwargs.enable_thinking=false.
  2. Den vollstaendigen effektiven Prompt protokollieren, den das Framework
     tatsaechlich schickt - inklusive aller injizierten Bloecke - und
     fingerprinten.
  3. Mehrfachaufrufe pro Turn zaehlen: jeder Request wird mit Zeitstempel,
     Token-Verbrauch und laufender Nummer geloggt.

Alles andere wird unveraendert durchgereicht.
"""
import json, os, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("PROXY_UPSTREAM", "http://localhost:8000")
LOGFILE = os.environ.get("PROXY_LOG", "/tmp/framework_proxy.jsonl")
PORT = int(os.environ.get("PROXY_PORT", "8899"))

FORCED = {"temperature": 0.7, "max_tokens": 700}
SEEDFILE = os.environ.get("PROXY_SEEDFILE", "/tmp/framework_proxy_seed.txt")


def _current_seed():
    """Der Seed des laufenden Durchgangs. das Framework kennt keinen Seed-Parameter;
    ohne ihn waere der Arm nicht seed-gleich zu den anderen. Der Orchestrator
    schreibt vor jedem Lauf den Wert in diese Datei."""
    try:
        return int(open(SEEDFILE).read().strip())
    except Exception:
        return None
FORCED_TEMPLATE = {"enable_thinking": False}

_lock = threading.Lock()
_counter = {"n": 0}


def _log(obj):
    with _lock:
        with open(LOGFILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw)
        except Exception:
            body = None

        original = None
        if isinstance(body, dict):
            original = {k: body.get(k) for k in
                        ("temperature", "max_tokens", "chat_template_kwargs")}
            body.update(FORCED)
            body["chat_template_kwargs"] = dict(FORCED_TEMPLATE)
            _seed = _current_seed()
            if _seed is not None:
                body["seed"] = _seed
            # das Framework erwartet SSE. Streaming bleibt erhalten, der Proxy
            # schneidet den Stream mit statt ihn zu unterdruecken.
            if body.get("stream"):
                body["_stream_wanted"] = True
                body["stream_options"] = {"include_usage": True}
            else:
                body.pop("stream_options", None)
            if body.get("tools") == []:
                body.pop("tools")             # leeres tools-Array lehnt vLLM ab
            if body.get("tool_choice") in (None, "none") and "tools" not in body:
                body.pop("tool_choice", None)
            raw = json.dumps(body).encode()

        with _lock:
            _counter["n"] += 1
            call_no = _counter["n"]

        streaming = bool(isinstance(body, dict) and body.get("_stream_wanted"))
        if isinstance(body, dict):
            body.pop("_stream_wanted", None)
            raw = json.dumps(body).encode()

        t0 = time.time()
        req = urllib.request.Request(UPSTREAM + self.path, data=raw,
                                     headers={"Content-Type": "application/json"})

        rec = {"call_no": call_no, "ts": round(t0, 3), "path": self.path,
               "streamed": streaming,
               "forced": dict(FORCED, chat_template_kwargs=FORCED_TEMPLATE),
               "original_sampling": original, "seed": _current_seed(),
               "request_keys": sorted(body.keys()) if isinstance(body, dict) else None}
        if isinstance(body, dict):
            msgs = body.get("messages", [])
            rec["messages"] = msgs
            rec["n_messages"] = len(msgs)
            rec["system_prompt_chars"] = sum(
                len(m.get("content") or "") for m in msgs if m.get("role") == "system")
            rec["tools_count"] = len(body.get("tools") or [])
            rec["tool_names"] = [t.get("function", {}).get("name")
                                 for t in (body.get("tools") or [])]

        if streaming:
            # SSE durchreichen und dabei mitschneiden: das Framework braucht den
            # Stream, das Experiment braucht Inhalt und Token-Verbrauch.
            try:
                resp = urllib.request.urlopen(req, timeout=600)
            except urllib.error.HTTPError as e:
                out, code = e.read(), e.code
                rec.update({"status": code, "error_body": out.decode()[:600],
                            "latency_s": round(time.time() - t0, 2)})
                _log(rec)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            parts, usage, finish = [], None, None
            for line in resp:
                try:
                    self.wfile.write(b"%X\r\n" % len(line) + line + b"\r\n")
                    self.wfile.flush()
                except Exception:
                    break
                if line.startswith(b"data: "):
                    payload = line[6:].strip()
                    if payload and payload != b"[DONE]":
                        try:
                            j = json.loads(payload)
                            if j.get("usage"):
                                usage = j["usage"]
                            for ch in j.get("choices") or []:
                                d = (ch.get("delta") or {}).get("content")
                                if d:
                                    parts.append(d)
                                if ch.get("finish_reason"):
                                    finish = ch["finish_reason"]
                        except Exception:
                            pass
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass
            rec.update({"status": 200, "latency_s": round(time.time() - t0, 2),
                        "usage": usage, "finish_reason": finish,
                        "response_content": "".join(parts)})
            _log(rec)
            return

        try:
            resp = urllib.request.urlopen(req, timeout=600)
            out, code = resp.read(), resp.status
        except urllib.error.HTTPError as e:
            out, code = e.read(), e.code
        except Exception as e:                        # noqa: BLE001
            out, code = json.dumps({"error": str(e)}).encode(), 500
        rec.update({"status": code, "latency_s": round(time.time() - t0, 2),
                    "error_body": out.decode()[:600] if code >= 400 else None})
        try:
            rj = json.loads(out)
            rec["usage"] = rj.get("usage")
            ch = (rj.get("choices") or [{}])[0]
            rec["response_content"] = (ch.get("message") or {}).get("content")
            rec["finish_reason"] = ch.get("finish_reason")
        except Exception:
            pass
        _log(rec)

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        try:
            resp = urllib.request.urlopen(UPSTREAM + self.path, timeout=60)
            out, code = resp.read(), resp.status
        except Exception as e:                        # noqa: BLE001
            out, code = json.dumps({"error": str(e)}).encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    print(f"Proxy :{PORT} -> {UPSTREAM}, Log {LOGFILE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
