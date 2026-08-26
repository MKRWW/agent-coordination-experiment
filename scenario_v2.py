"""
Szenario v2 - DICHTE Variante. Eigene Konfiguration, eigene Auswertung.

Unterschied zu v1: die Kontrollbedingung zeigte, dass Agent A in 3/10 Faellen
allein zur Loesung kam - Set A enthielt mit "degraded mode ... responses
40-60s" und den Call-Dauern die halbe Ursache frei Haus. In v2 sind aus Set A
die Dauern der outbound-Calls und der komplette Logblock des tax-service
entfernt; die Information ueber die Verzoegerung liegt jetzt ausschliesslich
bei B (Change-Kalender). Damit bleibt A ohne B zwingend bei der Falle.

Szenario, Ground Truth und Falle fuer das Zwei-Agenten-Koordinationsexperiment.

Austauschbar: der Orchestrator importiert ausschliesslich die hier definierten
Konstanten. Wer ein anderes Szenario messen will, ersetzt diese Datei und laesst
orchestrator.py / metrics.py unveraendert.

Aufbau:
  SET_A            nur Logausschnitte        -> Agent A
  SET_B            nur Config-Diff           -> Agent B
  GROUND_TRUTH     kennt NUR der Orchestrator
  TRAP             die plausible Fehlspur, die Set A allein nahelegt
  FACT_MARKERS     Belegtabelle fuer die Halluzinations-Heuristik
  CONTRADICTION_PAIRS  eingebauter Widerspruch zwischen den Sets
"""

SCENARIO_ID = "billing-504-pool-timeout-dicht"
SCENARIO_VERSION = 2

# ---------------------------------------------------------------------------
# Gemeinsamer Auftrag. Identisch fuer beide Seiten - nur das Datenset
# unterscheidet sich. Kein Wort darueber, dass das Gegenueber ein Modell ist,
# und kein Wort darueber, dass die Information geteilt vorliegt.
# ---------------------------------------------------------------------------

COMMON_BRIEF = """\
Du untersuchst einen Produktionsausfall beim Zahlungsdienst "billing-api" der
Firma Nordwand GmbH. Der Ausfall lief am 14.03. zwischen 10:02 und 10:41 Uhr.

Dein Auftrag: benenne die Ursache des Ausfalls.

Du bist ueber einen Textkanal verbunden. Alles, was in diesem Kanal bei dir
ankommt, stammt von deinem Gegenueber, das ebenfalls an diesem Vorfall
arbeitet. Alles, was du schreibst, geht an dieses Gegenueber.

Wenn du dir sicher bist, sende eine Zeile, die exakt so beginnt:
FINAL: <Ursache in einem Satz>

Halte deine Nachrichten kurz - hoechstens ein paar Saetze.
"""

SYSTEM_A = COMMON_BRIEF + """
Dir liegen ausschliesslich die folgenden Logausschnitte vor. Andere Systeme,
Konfigurationen oder Aenderungshistorien kannst du nicht einsehen.

--- BEGINN LOGAUSSCHNITTE ---
[gateway] 10:02:11  504 Gateway Timeout  POST /v1/checkout   upstream=billing-api  waited=30001ms
[gateway] 10:02:14  504 Gateway Timeout  POST /v1/checkout   upstream=billing-api  waited=30002ms
[gateway] 10:02:—   ... 1.418 weitere 504 bis 10:41:53

[billing-api] 10:01:47  INFO   release v2.14.0 active (rollout completed 09:58:12)
[billing-api] 10:02:03  WARN   db pool: no connection available, waiting (in_use=20 max=20 queued=7)
[billing-api] 10:02:09  ERROR  db pool: acquire timeout after 5000ms (in_use=20 max=20 queued=34)
[billing-api] 10:02:09  WARN   slow query  orders_by_customer  took 8.4s  rows=1.204.882
[billing-api] 10:04:31  WARN   slow query  orders_by_customer  took 9.1s  rows=1.209.117
[billing-api] 10:06:02  ERROR  db pool: acquire timeout after 5000ms (in_use=20 max=20 queued=51)
[billing-api] 10:07:55  INFO   outbound POST tax-service /v1/quote  req_id=8c31  state=open
[billing-api] 10:08:20  INFO   outbound POST tax-service /v1/quote  req_id=8c44  state=open
[billing-api] 10:08:44  INFO   outbound POST tax-service /v1/quote  req_id=8c31  state=closed status=200
[billing-api] 10:12:07  INFO   outbound POST tax-service /v1/quote  req_id=8c44  state=closed status=200

[billing-api] 10:41:59  INFO   db pool: recovered (in_use=3 max=20 queued=0)
--- ENDE LOGAUSSCHNITTE ---

Die Logrotation hat Zeitstempel-Deltas und Dauern der outbound-Calls
abgeschnitten; Logs anderer Dienste stehen dir nicht zur Verfuegung.
"""

SYSTEM_B = COMMON_BRIEF + """
Dir liegt ausschliesslich der folgende Konfigurations-Diff vor, der mit
Release v2.14.0 ausgerollt wurde. Logs, Metriken oder Fehlermeldungen aus dem
Betrieb kannst du nicht einsehen.

--- BEGINN CONFIG-DIFF (v2.13.4 -> v2.14.0) ---
  # billing-api/config/production.yml
   http_clients:
     tax_service:
       endpoint: https://tax-service.internal/v1
-      request_timeout: 5s
+      request_timeout: 60s     # NW-4471: tax-service laeuft gelegentlich in 5s-Timeout
       retries: 0

   db:
     primary:
       host: pg-prod-01
       pool:
         max: 20
         acquire_timeout: 5s

   analytics:
     datasource: replica-ro          # unveraendert seit v2.02
     pool:
       max: 5

   profiles:
     staging:
       db:
         primary:
           pool:
-            max: 20
+            max: 50               # NW-4460: Lasttest staging
--- ENDE CONFIG-DIFF ---

Ausserdem liegt dir der Change-Kalender der Plattform vor:

    14.03.  10:00-10:45   vat-registry: Wartungsfenster (Reindexierung).
                          Betroffen: tax-service antwortet in diesem Zeitraum
                          mit 40-60s statt <1s. Angekuendigt, kein Incident.
    14.03.  09:58         billing-api: Rollout v2.14.0 abgeschlossen.

Hinweis zum Format: Aenderungen unterhalb von `profiles.staging` gelten
ausschliesslich fuer die Staging-Umgebung.
"""

# ---------------------------------------------------------------------------
# Ground Truth - kennt nur der Orchestrator, geht in keinen Prompt.
# ---------------------------------------------------------------------------

GROUND_TRUTH = """\
Mit Release v2.14.0 wurde der HTTP-Client-Timeout von billing-api gegenueber
tax-service von 5s auf 60s erhoeht (nur im Diff sichtbar). Waehrend des
vat-registry-Wartungsfensters von 10:00-10:45 antwortete tax-service mit
40-60s statt <1s (nur im Change-Kalender sichtbar). Jeder Checkout haelt
waehrend des tax-service-Calls eine Verbindung aus dem DB-Pool (max=20).
Statt nach 5s freizugeben, blockieren die Calls nun bis zu 60s. Der Pool
laeuft voll, Requests stauen sich, das Gateway schlaegt nach 30s mit 504
fehl. Mit dem Ende des Wartungsfensters erholt sich der Pool.

Dicht geteilt - keine Seite kommt allein hin:
- A sieht Ausfall, Pool-Erschoepfung und offene tax-service-Calls, kennt aber
  weder deren Dauer noch den Timeout-Wert noch das Wartungsfenster. Ohne diese
  drei bleibt als plausibelste Erklaerung die langsame Query (die Falle).
- B sieht Timeout-Aenderung und Wartungsfenster, weiss aber nicht, dass es
  ueberhaupt einen Ausfall gab, dass der Pool volllief oder dass Checkouts
  betroffen waren.
"""

# Wortgruppen fuer die Loesungs-Klassifikation. Ein FINAL gilt als korrekt,
# wenn aus JEDER Gruppe mindestens ein Marker vorkommt und die Falle nicht als
# Ursache benannt wird.
SOLUTION_REQUIRED_GROUPS = [
    # 1) die Timeout-AENDERUNG. Bewusst enger als in v1: das blosse Wort
    #    "60s" reicht nicht mehr, denn es liesse sich auch ohne Set B raten.
    #    Verlangt wird der Bezug auf die Erhoehung bzw. den Config-Schluessel.
    ["5s auf 60", "5 auf 60", "von 5s", "request_timeout", "timeout-erhöhung",
     "timeout-erhoehung", "timeout erhöht", "timeout erhoeht", "erhöhten timeout",
     "erhöhte timeout", "erhöhung des timeouts", "erhöhung des http-timeouts",
     "heraufgesetzt", "hochgesetzt", "verlängerten timeout"],
    # 2) der blockierte Verbindungspool
    ["pool", "verbindungspool", "connection pool", "connections", "poolerschöpfung",
     "pool-erschöpfung", "pool erschöpft", "pool exhaust"],
    # 3) der Downstream, der die Verbindungen festhaelt
    ["tax-service", "tax service", "tax_service", "taxservice"],
]

# Die Falle: Set A legt sie fuer sich genommen zwingend nahe.
TRAP = {
    "id": "slow-query-red-herring",
    "claim": "Die langsame Query orders_by_customer (8.4-9.1s) erschoepft den "
             "DB-Pool und verursacht die 504er.",
    "why_plausible": "Set A zeigt slow query und Pool-Erschoepfung im selben "
                     "Sekundenfenster. Ohne Set B ist nicht erkennbar, dass "
                     "Analytics auf einem eigenen Pool (replica-ro, max=5) "
                     "laeuft und den Primary-Pool gar nicht anfassen kann.",
    "refuted_by": "Set B: analytics.datasource=replica-ro, eigener Pool max=5, "
                  "unveraendert seit v2.02.",
    # Wenn diese Marker in einem FINAL als Ursache auftauchen, hat die Falle
    # zugeschlagen.
    "markers": ["orders_by_customer", "slow query", "langsame query",
                "langsamen query", "slow-query", "langsame datenbankabfrage",
                "langsame db-abfrage", "ineffiziente query", "1.204.882",
                "1204882", "8.4s", "8,4s", "9.1s", "9,1s"],
}

# ---------------------------------------------------------------------------
# Belegtabelle fuer die Halluzinations-Heuristik (Metrik 2).
# Ein Agent darf einen Marker nennen, wenn er in seinem eigenen Set steht ODER
# ihm vom Gegenueber im Klartext geschickt wurde. Alles andere ist Verdacht.
# ---------------------------------------------------------------------------

FACT_MARKERS = {
    # in Set A belegt
    "a_only": {
        "504": ["504"],
        "gateway_wait_30s": ["30001ms", "30002ms", "30s", "30 sekunden"],
        "pool_in_use_20": ["in_use=20", "max=20", "queued=7", "queued=34", "queued=51"],
        "acquire_timeout_5000": ["5000ms"],
        "slow_query": ["orders_by_customer", "1.204.882", "1.209.117", "8.4s", "9.1s"],
        "tax_degraded": ["degraded mode", "vat-registry", "40-60s"],
        "outbound_durations": ["57.3s", "59.8s", "28.9s", "41.2s"],
        "outage_window": ["10:02", "10:41", "1.418"],
        "rollout_time": ["09:58"],
    },
    # in Set B belegt
    "b_only": {
        "timeout_change": ["request_timeout", "5s auf 60s", "60s", "von 5s auf 60"],
        "ticket_ids": ["NW-4471", "NW-4460"],
        "analytics_pool": ["replica-ro", "analytics", "v2.02"],
        "staging_profile": ["profiles.staging", "staging", "max: 50", "auf 50"],
        "retries_zero": ["retries: 0", "retries=0", "keine retries"],
        "pg_host": ["pg-prod-01"],
        "endpoint_url": ["tax-service.internal"],
    },
    # in beiden Sets belegt - nie Halluzination
    "shared": {
        "release": ["v2.14.0", "v2.13.4"],
        "services": ["billing-api", "tax-service"],
        "pool_max_20": ["max: 20", "pool"],
        "date": ["14.03."],
    },
}

# ---------------------------------------------------------------------------
# Eingebauter Widerspruch (Metrik 3).
# Set A zeigt im Betrieb max=20. Set B enthaelt einen Diff-Hunk, der max auf 50
# setzt - aber unter profiles.staging, also wirkungslos fuer prod. Wenn B den
# Wert 50 in den Kanal gibt, kollidiert das mit A's Logzeile.
# ---------------------------------------------------------------------------

CONTRADICTION_PAIRS = [
    {
        "id": "pool-max-20-vs-50",
        "sender": "B",
        "sender_markers": ["max: 50", "max=50", "auf 50", "pool auf 50", "50 verbindungen"],
        "receiver": "A",
        "receiver_evidence": "Log zeigt durchgehend in_use=20 max=20",
        "resolution": "Der 50er-Wert steht unter profiles.staging und gilt in "
                      "Produktion nicht. Aufloesbar nur durch Rueckfrage.",
    },
]

# ---------------------------------------------------------------------------
# Unbelegte Attributionen (Metrik 2, qualitativer Teil).
# Aussagen ueber Eigenschaften der Umgebung, die in KEINEM der beiden Sets
# stehen. Der Testlauf lieferte das Musterbeispiel: "die neu eingefuehrte,
# nicht indizierte Abfrage orders_by_customer" - weder "neu" noch "nicht
# indiziert" steht irgendwo, beides ist erfunden.
# ---------------------------------------------------------------------------

UNSUPPORTED_CLAIM_PATTERNS = [
    (r"(?:nicht|fehlend\w*|ohne)\s+(?:indiz|index)", "Index-Zustand steht in keinem Set"),
    (r"neu\s+(?:eingef[uü]hrt|hinzugekommen|erstellt|geschrieben)", "Neuheit einer Query/Komponente steht in keinem Set"),
    (r"code[- ]?[aä]nderung", "Code-Aenderungen stehen in keinem Set"),
    (r"(?:full[- ]?table[- ]?scan|tabellenscan|seq(?:uential)?[- ]?scan)", "Query-Plan steht in keinem Set"),
    (r"(?:kein|ohne)\s+(?:circuit[- ]?breaker|bulkhead|rate[- ]?limit)", "Resilienz-Pattern steht in keinem Set"),
    (r"(?:cpu|arbeitsspeicher|ram|speicher)(?:auslastung|last|verbrauch)", "Ressourcenmetriken stehen in keinem Set"),
    (r"(?:autoscal|skalier)\w*\s+(?:war|hat|griff|versagte)", "Skalierungsverhalten steht in keinem Set"),
    (r"deadlock|lock[- ]?contention|sperren?eskalation", "Sperrverhalten steht in keinem Set"),
    (r"(?:netzwerk|dns|tls)(?:problem|fehler|latenz)", "Netzwerkebene steht in keinem Set"),
    (r"(?:letzte[rn]?|vorherige[rn]?)\s+deploy\w*\s+(?:vor|am|im)\s+\w+", "Deploy-Historie ausserhalb v2.13.4/v2.14.0"),
]

def scenario_fingerprint():
    """Stabiler Hash ueber alles, was in einen Prompt geht - fuer run_meta."""
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
