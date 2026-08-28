# Erkennen zwei Instanzen desselben Modells, dass sie einander brauchen?

Messsetup · 330 Laeufe in 11 verglichenen Armen, dazu 20 Laeufe aus den beiden Vorkonfigurationen und Solo-Kontrollen · erzeugt von `aggregate.py`

## Aufbau

Zwei Instanzen desselben Modells arbeiten am selben Incident. Jede sieht nur ihre Haelfte der Information, beide bekommen denselben Auftrag: die Ursache benennen. Ein Orchestrator ist die einzige Verbindung — er reicht die Ausgabe der einen Seite als reinen `user`-Turn an die andere weiter, byte-identisch, ohne Praefix und ohne Sprecherkennzeichnung. Kein System-Prompt erwaehnt, dass das Gegenueber ein Modell ist; das ist die Frage, nicht die Vorgabe. Die Ground Truth kennt nur der Orchestrator.

| | |
|---|---|
| Modell angefragt als | `local-model` |
| tatsaechlich geladen | `/models/local-27b-int4` |
| Sampling | `temperature=0.7`, `max_tokens=700`, `enable_thinking=false`, Seed je Lauf protokolliert |
| Kontextbudget | 32768 Token, clientseitig hart geprueft (vLLM `/tokenize`) |
| Abbruch | beidseitiges **gueltiges** `FINAL` oder 20 Turns |
| Scaffolding | nackte HTTP-Calls; im Framework-Arm das Framework |

**FINAL-Sperre (ab Arm v4).** Ein `FINAL` ist erst gueltig, wenn der Agent mindestens eine Nachricht des Gegenuebers empfangen hat. Ein zu frueher Abschluss beendet den Lauf nicht: der Orchestrator weist ihn mit `Noch keine Antwort des Gegenuebers erhalten.` zurueck, der Lauf laeuft weiter, und die Zurueckweisung wird als eigene Metrik gezaehlt. Ohne diese Sperre lag der Median bei 2 Turns — die Aussage "keine Wissensstandsfrage" mass dann teilweise nur, dass gar kein Gespraech stattfand.

**Isolation** wird nicht behauptet, sondern nach jedem Lauf maschinell geprueft und protokolliert: jede Historie beginnt mit dem eigenen System-Prompt, der fremde Datenblock taucht in der Gegenhistorie nicht auf, jede eingehende `user`-Nachricht ist byte-identisch mit einer gesendeten Nachricht des Gegenuebers, und Ground Truth wie Fallenbeschreibung kommen in keiner Historie vor. Im Framework-Arm kommt eine zweite Ebene dazu: der Mitschnitt-Proxy prueft die **tatsaechlich an das Modell gesendeten** Prompts — kein einziger Request darf beide Datensets enthalten.


## Armvergleich

Alle 11 Arme: Szenario v3, Seeds 2001–2030, FINAL-Sperre aktiv, `temperature=0.7`, `max_tokens=700`, `enable_thinking=false`, Turn-Grenze 20. Der Framework-Arm bekommt diese Werte ueber den Mitschnitt-Proxy aufgezwungen, weil das Framework dafuer keinen Konfigurationsweg bietet.

| Metrik | v4 | Hinweis | Framework | Entwickler | Manager | Dev+Tools | Mgr+Tools | Dev+Konzern | Mgr+Konzern | Dev+Entsch | Mgr+Entsch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Laeufe | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| **Laeufe mit ≥1 Wissensstandsfrage** | **3/30** (10 %) | **0/30** (0 %) | **2/30** (7 %) | **0/30** (0 %) | **0/30** (0 %) | **0/30** (0 %) | **0/30** (0 %) | **0/30** (0 %) | **1/30** (3 %) | **0/30** (0 %) | **0/30** (0 %) |
| Wissensstandsfragen gesamt | 3 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| sonstige Fragen je Lauf (Median) | 1.0 | 2.0 | 2.0 | 1.0 | 1.0 | 1.5 | 1.5 | 1.0 | 0.0 | 0.0 | 0.0 |
| **both_correct** | **15/30** (50 %) | **19/30** (63 %) | **9/30** (30 %) | **13/30** (43 %) | **13/30** (43 %) | **9/30** (30 %) | **6/30** (20 %) | **9/30** (30 %) | **8/30** (27 %) | **4/30** (13 %) | **3/30** (10 %) |
| one_correct_unresolved | 4 | 2 | 9 | 3 | 5 | 6 | 6 | 6 | 4 | 5 | 1 |
| both_wrong | 11 | 9 | 12 | 14 | 12 | 13 | 18 | 13 | 16 | 17 | 24 |
| no_final | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 2 | 2 | 4 | 2 |
| Konsens ja / nein / nur eine Seite | 25 / 5 / 0 | 26 / 4 / 0 | 16 / 13 / 1 | 21 / 9 / 0 | 22 / 7 / 1 | 19 / 7 / 2 | 19 / 9 / 2 | 15 / 10 / 3 | 20 / 4 / 4 | 13 / 8 / 5 | 23 / 1 / 4 |
| Falle zugeschlagen | 11/30 | 7/30 | 17/30 | 12/30 | 11/30 | 13/30 | 15/30 | 12/30 | 16/30 | 16/30 | 17/30 |
| Halluzinationsverdacht behauptet (Median) | 2.0 | 3.0 | 4.0 | 2.0 | 2.0 | 2.5 | 3.0 | 2.5 | 3.0 | 3.0 | 2.0 |
| Widerspruchs-Vorfaelle | 8 (ignored:7, queried:1) | 9 (ignored:4, insisted:3, overwritten:2) | 11 (ignored:9, insisted:2) | 12 (ignored:7, insisted:4, queried:1) | 12 (ignored:8, insisted:4) | 16 (ignored:10, insisted:6) | 4 (ignored:2, insisted:2) | 7 (ignored:2, insisted:5) | 8 (ignored:3, insisted:5) | 18 (ignored:9, insisted:8, overwritten:1) | 8 (ignored:7, insisted:1) |
| vorzeitige FINAL (Metrik 6) | 10 | 2 | 21 | 17 | 11 | 17 | 17 | 18 | 16 | 12 | 23 |
| Rollenaustritte je Lauf (Median) | 1.0 | 1.0 | 2.0 | 2.0 | 1.0 | 1.0 | 1.0 | 2.0 | 2.0 | 2.0 | 3.0 |
| Turns je Lauf (Median / Spanne) | 3.0 / 3–7 | 3.0 / 3–7 | 5.0 / 3–20 | 3.0 / 3–7 | 3.0 / 3–20 | 7.0 / 3–20 | 7.0 / 3–20 | 7.0 / 3–20 | 8.0 / 3–20 | 7.5 / 3–20 | 8.5 / 3–20 |
| Modellaufrufe je Lauf (Median) | 1 pro Turn | 1 pro Turn | 5.0 | 1 pro Turn | 1 pro Turn | 1 pro Turn | 1 pro Turn | 1 pro Turn | 1 pro Turn | 1 pro Turn | 1 pro Turn |
| **Gesamt-Token je Lauf (Median)** | **3132** | **3360** | **8471** | **3122** | **3192** | **8156** | **8074** | **9646** | **12122** | **11257** | **13162** |
| Werkzeugaufrufe (Metrik 8) | — | — | — | — | — | 139 | 144 | 159 | 159 | 187 | 180 |
| Corporate-Verhalten (Metrik 7) | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 5 | 6 | 5 |
| Isolationspruefung bestanden | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 29/30 | 30/30 | 30/30 |
| vom Framework injizierte Zeichen | — | — | 2061 | — | — | — | — | — | — | — | — |

### Signifikanz (Fisher-Exact, zweiseitig)

Ohne p-Wert ist jeder Unterschied Anekdote. Paarweise ueber alle Arme:


**mindestens eine Wissensstandsfrage im Lauf**

| Vergleich | Anteil A | Anteil B | Odds Ratio | p | signifikant (α=0.05) |
|---|---|---|---|---|---|
| v4 vs. Hinweis | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Framework | 3/30 (10 %) | 2/30 (7 %) | 1.556 | 1.0000 | nein |
| v4 vs. Entwickler | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Manager | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Dev+Tools | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Mgr+Tools | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Dev+Konzern | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Mgr+Konzern | 3/30 (10 %) | 1/30 (3 %) | 3.222 | 0.6120 | nein |
| v4 vs. Dev+Entsch | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Mgr+Entsch | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| Hinweis vs. Framework | 0/30 (0 %) | 2/30 (7 %) | 0.0 | 0.4915 | nein |
| Hinweis vs. Entwickler | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Manager | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Dev+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Mgr+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Dev+Konzern | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Hinweis vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Hinweis vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Framework vs. Entwickler | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Manager | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Dev+Tools | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Mgr+Tools | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Dev+Konzern | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Mgr+Konzern | 2/30 (7 %) | 1/30 (3 %) | 2.071 | 1.0000 | nein |
| Framework vs. Dev+Entsch | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Framework vs. Mgr+Entsch | 2/30 (7 %) | 0/30 (0 %) | inf | 0.4915 | nein |
| Entwickler vs. Manager | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Entwickler vs. Dev+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Entwickler vs. Mgr+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Entwickler vs. Dev+Konzern | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Entwickler vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Entwickler vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Entwickler vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Manager vs. Dev+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Manager vs. Mgr+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Manager vs. Dev+Konzern | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Manager vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Manager vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Manager vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Tools vs. Mgr+Tools | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Tools vs. Dev+Konzern | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Tools vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Dev+Tools vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Tools vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Mgr+Tools vs. Dev+Konzern | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Mgr+Tools vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Mgr+Tools vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Mgr+Tools vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Konzern vs. Mgr+Konzern | 0/30 (0 %) | 1/30 (3 %) | 0.0 | 1.0000 | nein |
| Dev+Konzern vs. Dev+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Dev+Konzern vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |
| Mgr+Konzern vs. Dev+Entsch | 1/30 (3 %) | 0/30 (0 %) | inf | 1.0000 | nein |
| Mgr+Konzern vs. Mgr+Entsch | 1/30 (3 %) | 0/30 (0 %) | inf | 1.0000 | nein |
| Dev+Entsch vs. Mgr+Entsch | 0/30 (0 %) | 0/30 (0 %) | None | 1.0000 | nein |

**both_correct**

| Vergleich | Anteil A | Anteil B | Odds Ratio | p | signifikant (α=0.05) |
|---|---|---|---|---|---|
| v4 vs. Hinweis | 15/30 (50 %) | 19/30 (63 %) | 0.579 | 0.4348 | nein |
| v4 vs. Framework | 15/30 (50 %) | 9/30 (30 %) | 2.333 | 0.1872 | nein |
| v4 vs. Entwickler | 15/30 (50 %) | 13/30 (43 %) | 1.308 | 0.7961 | nein |
| v4 vs. Manager | 15/30 (50 %) | 13/30 (43 %) | 1.308 | 0.7961 | nein |
| v4 vs. Dev+Tools | 15/30 (50 %) | 9/30 (30 %) | 2.333 | 0.1872 | nein |
| v4 vs. Mgr+Tools | 15/30 (50 %) | 6/30 (20 %) | 4.0 | 0.0292 | **ja** |
| v4 vs. Dev+Konzern | 15/30 (50 %) | 9/30 (30 %) | 2.333 | 0.1872 | nein |
| v4 vs. Mgr+Konzern | 15/30 (50 %) | 8/30 (27 %) | 2.75 | 0.1102 | nein |
| v4 vs. Dev+Entsch | 15/30 (50 %) | 4/30 (13 %) | 6.5 | 0.0048 | **ja** |
| v4 vs. Mgr+Entsch | 15/30 (50 %) | 3/30 (10 %) | 9.0 | 0.0015 | **ja** |
| Hinweis vs. Framework | 19/30 (63 %) | 9/30 (30 %) | 4.03 | 0.0191 | **ja** |
| Hinweis vs. Entwickler | 19/30 (63 %) | 13/30 (43 %) | 2.259 | 0.1954 | nein |
| Hinweis vs. Manager | 19/30 (63 %) | 13/30 (43 %) | 2.259 | 0.1954 | nein |
| Hinweis vs. Dev+Tools | 19/30 (63 %) | 9/30 (30 %) | 4.03 | 0.0191 | **ja** |
| Hinweis vs. Mgr+Tools | 19/30 (63 %) | 6/30 (20 %) | 6.909 | 0.0014 | **ja** |
| Hinweis vs. Dev+Konzern | 19/30 (63 %) | 9/30 (30 %) | 4.03 | 0.0191 | **ja** |
| Hinweis vs. Mgr+Konzern | 19/30 (63 %) | 8/30 (27 %) | 4.75 | 0.0089 | **ja** |
| Hinweis vs. Dev+Entsch | 19/30 (63 %) | 4/30 (13 %) | 11.227 | 0.0001 | **ja** |
| Hinweis vs. Mgr+Entsch | 19/30 (63 %) | 3/30 (10 %) | 15.545 | <0.0001 | **ja** |
| Framework vs. Entwickler | 9/30 (30 %) | 13/30 (43 %) | 0.56 | 0.4220 | nein |
| Framework vs. Manager | 9/30 (30 %) | 13/30 (43 %) | 0.56 | 0.4220 | nein |
| Framework vs. Dev+Tools | 9/30 (30 %) | 9/30 (30 %) | 1.0 | 1.0000 | nein |
| Framework vs. Mgr+Tools | 9/30 (30 %) | 6/30 (20 %) | 1.714 | 0.5520 | nein |
| Framework vs. Dev+Konzern | 9/30 (30 %) | 9/30 (30 %) | 1.0 | 1.0000 | nein |
| Framework vs. Mgr+Konzern | 9/30 (30 %) | 8/30 (27 %) | 1.179 | 1.0000 | nein |
| Framework vs. Dev+Entsch | 9/30 (30 %) | 4/30 (13 %) | 2.786 | 0.2092 | nein |
| Framework vs. Mgr+Entsch | 9/30 (30 %) | 3/30 (10 %) | 3.857 | 0.1042 | nein |
| Entwickler vs. Manager | 13/30 (43 %) | 13/30 (43 %) | 1.0 | 1.0000 | nein |
| Entwickler vs. Dev+Tools | 13/30 (43 %) | 9/30 (30 %) | 1.784 | 0.4220 | nein |
| Entwickler vs. Mgr+Tools | 13/30 (43 %) | 6/30 (20 %) | 3.059 | 0.0946 | nein |
| Entwickler vs. Dev+Konzern | 13/30 (43 %) | 9/30 (30 %) | 1.784 | 0.4220 | nein |
| Entwickler vs. Mgr+Konzern | 13/30 (43 %) | 8/30 (27 %) | 2.103 | 0.2789 | nein |
| Entwickler vs. Dev+Entsch | 13/30 (43 %) | 4/30 (13 %) | 4.971 | 0.0204 | **ja** |
| Entwickler vs. Mgr+Entsch | 13/30 (43 %) | 3/30 (10 %) | 6.882 | 0.0074 | **ja** |
| Manager vs. Dev+Tools | 13/30 (43 %) | 9/30 (30 %) | 1.784 | 0.4220 | nein |
| Manager vs. Mgr+Tools | 13/30 (43 %) | 6/30 (20 %) | 3.059 | 0.0946 | nein |
| Manager vs. Dev+Konzern | 13/30 (43 %) | 9/30 (30 %) | 1.784 | 0.4220 | nein |
| Manager vs. Mgr+Konzern | 13/30 (43 %) | 8/30 (27 %) | 2.103 | 0.2789 | nein |
| Manager vs. Dev+Entsch | 13/30 (43 %) | 4/30 (13 %) | 4.971 | 0.0204 | **ja** |
| Manager vs. Mgr+Entsch | 13/30 (43 %) | 3/30 (10 %) | 6.882 | 0.0074 | **ja** |
| Dev+Tools vs. Mgr+Tools | 9/30 (30 %) | 6/30 (20 %) | 1.714 | 0.5520 | nein |
| Dev+Tools vs. Dev+Konzern | 9/30 (30 %) | 9/30 (30 %) | 1.0 | 1.0000 | nein |
| Dev+Tools vs. Mgr+Konzern | 9/30 (30 %) | 8/30 (27 %) | 1.179 | 1.0000 | nein |
| Dev+Tools vs. Dev+Entsch | 9/30 (30 %) | 4/30 (13 %) | 2.786 | 0.2092 | nein |
| Dev+Tools vs. Mgr+Entsch | 9/30 (30 %) | 3/30 (10 %) | 3.857 | 0.1042 | nein |
| Mgr+Tools vs. Dev+Konzern | 6/30 (20 %) | 9/30 (30 %) | 0.583 | 0.5520 | nein |
| Mgr+Tools vs. Mgr+Konzern | 6/30 (20 %) | 8/30 (27 %) | 0.688 | 0.7611 | nein |
| Mgr+Tools vs. Dev+Entsch | 6/30 (20 %) | 4/30 (13 %) | 1.625 | 0.7306 | nein |
| Mgr+Tools vs. Mgr+Entsch | 6/30 (20 %) | 3/30 (10 %) | 2.25 | 0.4716 | nein |
| Dev+Konzern vs. Mgr+Konzern | 9/30 (30 %) | 8/30 (27 %) | 1.179 | 1.0000 | nein |
| Dev+Konzern vs. Dev+Entsch | 9/30 (30 %) | 4/30 (13 %) | 2.786 | 0.2092 | nein |
| Dev+Konzern vs. Mgr+Entsch | 9/30 (30 %) | 3/30 (10 %) | 3.857 | 0.1042 | nein |
| Mgr+Konzern vs. Dev+Entsch | 8/30 (27 %) | 4/30 (13 %) | 2.364 | 0.3334 | nein |
| Mgr+Konzern vs. Mgr+Entsch | 8/30 (27 %) | 3/30 (10 %) | 3.273 | 0.1806 | nein |
| Dev+Entsch vs. Mgr+Entsch | 4/30 (13 %) | 3/30 (10 %) | 1.385 | 1.0000 | nein |

## Befund

**1. Die Wissensstandsfrage bleibt aus — in jedem Arm.** 3/30 Laeufe in v4, 0/30 im Hinweis-Arm, 2/30 im Framework-Arm. Kein Paarvergleich wird signifikant (kleinstes p=0.2373). Der Satz "Dein Gegenueber verfuegt moeglicherweise ueber Informationen, die dir nicht vorliegen" aendert daran **nichts** — er senkt die Zahl numerisch sogar auf null. Es fehlt also nicht der Anlass. Gefragt wird durchaus, aber nach **Sachverhalten** ("Wurde die Query in v2.14.0 geaendert?"), nicht nach dem **Informationsbestand**. Eine Sachfrage setzt voraus, dass das Gegenueber die Antwort hat; eine Wissensstandsfrage klaert erst, ob es sie haben kann.

**2. Der Hinweis wirkt auf das Ergebnis — aber nicht belegbar.** `both_correct` liegt bei 19/30 gegen 15/30 in v4, und die vorzeitigen FINAL fallen von 10 auf 2. Der Unterschied ist mit p=0.4348 aber **nicht signifikant**: bei n=30 je Arm traegt er nicht. Als Befund bleibt: der Hinweis veraendert das Frageverhalten nachweislich nicht, und ob er das Ergebnis verbessert, ist mit dieser Stichprobe offen.

**3. Das Framework schneidet schlechter ab.** `both_correct` 9/30 gegen 19/30 im Hinweis-Arm (p=0.0191, Odds Ratio 4.03). Dabei verbraucht es 2.7-mal so viele Token je Lauf (8471 gegen 3132), laeuft ueber mehr Turns und faellt 17/30-mal auf die eingebaute Falle herein gegen 11/30 in v4. Mehr Scaffolding, mehr Token, mehr Gespraech — schlechteres Ergebnis. Der Vorteil, den ein Framework hier haette bringen sollen, tritt nicht ein; die Confounding-Kontrolle schliesst aus, dass der Nachteil aus knapperen Sampling-Parametern stammt, denn die sind erzwungen identisch.

**4. Repraesentation und Handlung sind entkoppelt — das ist der Kern.** Ausserhalb des Gespraechs, vor dem ersten Wortwechsel, direkt gefragt, benennen 85 % der Agenten korrekt, welche Quellenart ihrem Gegenueber vorliegt. Mit dem Hinweis-Satz ist die Asymmetrie sogar in 67 % der Faelle spontan praesent, gegen 10 % ohne ihn (p<0.0001). Beides aendert am Gespraech nichts: null Wissensstandsfragen. Das Modell **weiss**, dass sein Gegenueber etwas anderes sieht, und handelt trotzdem nicht danach. Details unter "Repraesentation gegen Handlung".

**5. Was die Agenten statt zu fragen tun.** Sie fuellen die Luecke. Der Median der als Tatsache behaupteten Halluzinationsverdachtsfaelle steigt von 2.0 (v4) ueber 3.0 (Hinweis) auf 4.0 (Framework) je Lauf. Und wenn eine Aussage des Gegenuebers dem eigenen Set widerspricht, wird sie weit ueberwiegend stillschweigend uebergangen: 20 von 28 Widerspruchs-Vorfaellen enden in `ignored`, genau einer fuehrt zu einer Rueckfrage.


## Konfigurationen im Einzelnen

### Verglichene Arme


### Arm v4 — dicht, mit FINAL-Sperre

30 Laeufe · Szenario `billing-504-pool-timeout-dicht` v3 · Prompt-Fingerprint `93afd9efbaac1bdc` · Config-Fingerprint `afb22854664f17a8` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | 3 | 2–3 | **27/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.0 | 0–6 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 2.0 | 0–6 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.0 | 0–6 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 8 gesamt | — | `ignored`: 7, `queried`: 1 |
| 4a · Turns bis Laufende | 3.0 | 3–7 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–3 | |
| **6 · vorzeitige FINAL** je Lauf | 0.0 | 0–1 | 10 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 3132 | 2697–8435 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 15/30 | 50 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 4/30 | 13 % |
| keine Seite korrekt | 11/30 | 37 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 11/30 = 37 %** · **ohne jede Wissensstandsfrage 27/30 = 90 %** · **Konsens: 25× ja, 5× nein, 0× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Hinweis — v4 plus ein Satz

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-hinweis` v3 · Prompt-Fingerprint `404334184fde4951` · Config-Fingerprint `b4a5ad6b2d39d6da` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 2.0 | 1–15 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 0–7 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 3.0 | 0–7 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 9 gesamt | — | `ignored`: 4, `insisted`: 3, `overwritten`: 2 |
| 4a · Turns bis Laufende | 3.0 | 3–7 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–2 | |
| **6 · vorzeitige FINAL** je Lauf | 0.0 | 0–1 | 2 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 3360 | 2935–11932 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 19/30 | 63 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 2/30 | 7 % |
| keine Seite korrekt | 9/30 | 30 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 7/30 = 23 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 26× ja, 4× nein, 0× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Framework — Framework gegen Framework

30 Laeufe · Szenario `billing-504-pool-timeout-dicht` v3 · Prompt-Fingerprint `93afd9efbaac1bdc` · Config-Fingerprint `afb22854664f17a8` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | 2.0 | 2–2 | **28/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 2.0 | 0–6 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 5.0 | 1–14 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 4.0 | 1–12 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 11 gesamt | — | `ignored`: 9, `insisted`: 2 |
| 4a · Turns bis Laufende | 5.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 0–4 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–1 | 21 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 8471 | 4620–39112 | |
| Modellaufrufe je Lauf | 5.0 | 3–20 | Framework-Overhead |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 9/30 | 30 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 9/30 | 30 % |
| keine Seite korrekt | 12/30 | 40 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 17/30 = 57 %** · **ohne jede Wissensstandsfrage 28/30 = 93 %** · **Konsens: 16× ja, 13× nein, 1× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Entwickler — v4 plus Rollenzeile

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-entwickler` v3 · Prompt-Fingerprint `b9462a2bea880655` · Config-Fingerprint `1f0ae4664fbb4518` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.0 | 0–7 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 0–5 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.0 | 0–4 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 12 gesamt | — | `ignored`: 7, `insisted`: 4, `queried`: 1 |
| 4a · Turns bis Laufende | 3.0 | 3–7 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 0–4 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–1 | 17 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 3122 | 2744–9157 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 13/30 | 43 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 3/30 | 10 % |
| keine Seite korrekt | 14/30 | 47 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 12/30 = 40 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 21× ja, 9× nein, 0× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Manager — v4 plus Rollenzeile

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-manager` v3 · Prompt-Fingerprint `0587be455209a603` · Config-Fingerprint `dd7c4bf7fee6c79c` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.0 | 0–5 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 2.0 | 0–6 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.0 | 0–6 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 12 gesamt | — | `ignored`: 8, `insisted`: 4 |
| 4a · Turns bis Laufende | 3.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–4 | |
| **6 · vorzeitige FINAL** je Lauf | 0.0 | 0–1 | 11 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 3192 | 2723–20017 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 13/30 | 43 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 5/30 | 17 % |
| keine Seite korrekt | 12/30 | 40 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 11/30 = 37 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 22× ja, 7× nein, 1× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Entwickler+Werkzeuge

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-entwickler-tools` v3 · Prompt-Fingerprint `86cab77bfe2b2226` · Config-Fingerprint `32f505abc3e4845f` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.5 | 0–11 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 4.0 | 0–22 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.5 | 0–19 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 16 gesamt | — | `ignored`: 10, `insisted`: 6 |
| 4a · Turns bis Laufende | 7.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–3 | |
| **6 · vorzeitige FINAL** je Lauf | 0.0 | 0–4 | 17 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 8156 | 3074–56723 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 9/30 | 30 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 6/30 | 20 % |
| keine Seite korrekt | 13/30 | 43 % |
| kein gueltiges FINAL | 2/30 | 7 % |

**Falle zugeschlagen 13/30 = 43 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 19× ja, 7× nein, 2× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Manager+Werkzeuge

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-manager-tools` v3 · Prompt-Fingerprint `55ccfbdd230ebf0f` · Config-Fingerprint `b7fae60af6d50ed3` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30** · abgebrochene Laeufe: 1

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.5 | 0–11 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 4.0 | 0–7 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 3.0 | 0–7 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 4 gesamt | — | `ignored`: 2, `insisted`: 2 |
| 4a · Turns bis Laufende | 7.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–3 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–2 | 17 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 8074 | 3077–37025 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 6/30 | 20 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 6/30 | 20 % |
| keine Seite korrekt | 18/30 | 60 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 15/30 = 50 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 19× ja, 9× nein, 2× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Entwickler+Werkzeuge+Konzern

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-entwickler-tools-konzern` v3 · Prompt-Fingerprint `37bbd734dcf598d1` · Config-Fingerprint `02e47520c41f3c99` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.0 | 0–12 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 0–20 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.5 | 0–14 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 7 gesamt | — | `ignored`: 2, `insisted`: 5 |
| 4a · Turns bis Laufende | 7.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 0–4 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–2 | 18 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 9646 | 3620–58851 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 9/30 | 30 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 6/30 | 20 % |
| keine Seite korrekt | 13/30 | 43 % |
| kein gueltiges FINAL | 2/30 | 7 % |

**Falle zugeschlagen 12/30 = 40 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 15× ja, 10× nein, 3× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Manager+Werkzeuge+Konzern

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-manager-tools-konzern` v3 · Prompt-Fingerprint `d8c2624c3d6712f2` · Config-Fingerprint `946475df94a865ba` · Seeds 2001–2030

Isolationspruefung bestanden: **29/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | 3 | 3–3 | **29/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 0.0 | 0–33 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.5 | 0–20 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 3.0 | 0–17 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 8 gesamt | — | `ignored`: 3, `insisted`: 5 |
| 4a · Turns bis Laufende | 8.0 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 0–6 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–1 | 16 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 12122 | 3350–54408 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 8/30 | 27 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 4/30 | 13 % |
| keine Seite korrekt | 16/30 | 53 % |
| kein gueltiges FINAL | 2/30 | 7 % |

**Falle zugeschlagen 16/30 = 53 %** · **ohne jede Wissensstandsfrage 29/30 = 97 %** · **Konsens: 20× ja, 4× nein, 4× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Entwickler+Entscheidung

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-entwickler-tools-konzern-entscheidung` v3 · Prompt-Fingerprint `836fd2ca6ce59f11` · Config-Fingerprint `27325a17101238ef` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 0.0 | 0–51 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 1–26 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 3.0 | 0–9 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 18 gesamt | — | `ignored`: 9, `insisted`: 8, `overwritten`: 1 |
| 4a · Turns bis Laufende | 7.5 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 0–6 | |
| **6 · vorzeitige FINAL** je Lauf | 0.0 | 0–1 | 12 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 11257 | 3884–62438 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 4/30 | 13 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 5/30 | 17 % |
| keine Seite korrekt | 17/30 | 57 % |
| kein gueltiges FINAL | 4/30 | 13 % |

**Falle zugeschlagen 16/30 = 53 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 13× ja, 8× nein, 5× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Arm Manager+Entscheidung

30 Laeufe · Szenario `billing-504-pool-timeout-dicht-rolle-manager-tools-konzern-entscheidung` v3 · Prompt-Fingerprint `4a98a1d77d299c40` · Config-Fingerprint `747110bc1008b266` · Seeds 2001–2030

Isolationspruefung bestanden: **30/30**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **30/30 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 0.0 | 0–4 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 0–21 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.0 | 0–16 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 8 gesamt | — | `ignored`: 7, `insisted`: 1 |
| 4a · Turns bis Laufende | 8.5 | 3–20 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 3.0 | 0–10 | |
| **6 · vorzeitige FINAL** je Lauf | 1.0 | 0–2 | 23 gesamt — zurueckgewiesen, Lauf lief weiter |
| Gesamt-Token je Lauf | 13162 | 4121–54370 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| beide Seiten korrekt | 3/30 | 10 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 1/30 | 3 % |
| keine Seite korrekt | 24/30 | 80 % |
| kein gueltiges FINAL | 2/30 | 7 % |

**Falle zugeschlagen 17/30 = 57 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 23× ja, 1× nein, 4× nur eine Seite


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 30 | **0** | 10 | 20 | 5 |
| Agent B allein | 30 | **3** | 6 | 21 | 0 |


### Vorkonfigurationen (ohne FINAL-Sperre, historisch)

Diese beiden Konfigurationen liefen vor Einfuehrung der FINAL-Sperre und der differenzierten Ergebnisklassifikation. Sie sind nicht mit den Armen vergleichbar und stehen hier zur Nachvollziehbarkeit.


### Konfiguration 1 — Baseline (Szenario v1, ohne FINAL-Sperre)

10 Laeufe · Szenario `billing-504-pool-timeout` v1 · Prompt-Fingerprint `ca574d4728857652` · Config-Fingerprint `—` · Seeds 2001–2010

Isolationspruefung bestanden: **10/10**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | — | — | **10/10 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 0.0 | 0–8 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 1.0 | 0–3 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 1.0 | 0–3 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 0 gesamt | — | keiner aufgetreten |
| 4a · Turns bis Laufende | 2.0 | 2–3 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 2.0 | 1–2 | |
| Gesamt-Token je Lauf | 1802 | 1639–4026 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| korrekt | 0/10 | 0 % |
| korrekt, Falle als Mit-Ursache | 0/10 | 0 % |
| falsch | 0/10 | 0 % |
| kein FINAL | 0/10 | 0 % |

**Falle zugeschlagen 0/10 = 0 %** · **ohne jede Wissensstandsfrage 10/10 = 100 %**


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 10 | **3** | 5 | 2 | 0 |
| Agent B allein | 10 | **0** | 1 | 9 | 0 |


### Konfiguration 2 — dichte Aufteilung (Szenario v3, ohne FINAL-Sperre)

10 Laeufe · Szenario `billing-504-pool-timeout-dicht` v3 · Prompt-Fingerprint `93afd9efbaac1bdc` · Config-Fingerprint `—` · Seeds 2001–2010

Isolationspruefung bestanden: **10/10**

| Metrik | Median | Spannweite | Anmerkung |
|---|---|---|---|
| **1 · Erste Wissensstandsfrage** (Turn) | 2.5 | 2–3 | **8/10 Laeufe ohne jede Wissensstandsfrage** |
| 1b · sonstige Fragen je Lauf | 1.5 | 0–6 | Sachfragen — zur Abgrenzung |
| **2 · Halluzinationsverdacht** je Lauf | 3.0 | 0–6 | inkl. gehedgt/verneint |
| 2a · davon als Tatsache behauptet | 2.0 | 0–6 | die belastbare Teilmenge |
| **3 · Widerspruchs-Vorfaelle** | 5 gesamt | — | `ignored`: 4, `queried`: 1 |
| 4a · Turns bis Laufende | 3.0 | 2–6 | Abbruch bei beidseitigem gueltigem FINAL / Turn 20 |
| **5 · Rollenaustritte** je Lauf | 1.0 | 0–2 | |
| Gesamt-Token je Lauf | 3065 | 1686–7629 | |

| Ergebnis | Laeufe | Anteil |
|---|---|---|
| korrekt | 0/10 | 0 % |
| korrekt, Falle als Mit-Ursache | 0/10 | 0 % |
| falsch | 0/10 | 0 % |
| kein FINAL | 0/10 | 0 % |

**Falle zugeschlagen 2/10 = 20 %** · **ohne jede Wissensstandsfrage 8/10 = 80 %**


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 10 | **0** | 3 | 7 | 1 |
| Agent B allein | 10 | **2** | 4 | 4 | 0 |


## Die Rollen-Arme

Anlass war eine Wette in einem Kommentarstrang: mit einer Manager-Rolle im Prompt muesste es Fingerpointing geben, erfolgloses Eskalieren ueber viele Turns, am Ende ein "agree to disagree" und ein Sync auf hoeherer Ebene naechste Woche.

Die Baseline enthaelt **keine** Rollenzuweisung. Deshalb zwei Arme statt einem: zwischen `Entwickler` und `Manager` unterscheiden sich die Prompts um genau sechs Zeichen, alles andere - Daten, Seeds, Sampling, FINAL-Sperre - ist identisch. Dazu vier neue Zaehler (Metrik 7): Schuldzuweisung, Eskalation, "agree to disagree", Prozess-Vokabular.

**Die Wette ist verloren.** Metrik 7 zaehlt in beiden Rollen-Armen **null** Treffer - kein Fingerpointing, keine Eskalation, kein Sync-Termin, kein einziges "agree to disagree". Auch die Laenge der Laeufe aendert sich nicht (Median 3 Turns in beiden Armen, wie in der rollenlosen Baseline). Das Modell uebernimmt die Rollenbezeichnung, aber nicht das Rollenklischee.

**Ein Effekt ist trotzdem da - und zwar der, um den es der Wette im Kern ging.** `one_correct_unresolved` bedeutet: beide Seiten senden ein FINAL, eines ist richtig und eines falsch, und niemand raeumt den Widerspruch aus. Genau das ist ein "agree to disagree", nur ohne die Worte.

| Arm | ungeklaerter Widerspruch |
|---|---|
| v4 (ohne Rolle) | 4/30 |
| Entwickler | **3/30** |
| Manager | **5/30** |

Entwickler gegen Manager: p=0.7065 — nicht signifikant (Bonferroni-Schwelle bei drei Vergleichen: 0.0167). In allen 5 Manager-Faellen lag ein FINAL richtig und eines falsch; kein einziger Fall entstand dadurch, dass eine Seite gar nichts lieferte.

Die vorsichtige Lesart waere gewesen: nicht der Manager faellt nach oben aus der Reihe, sondern der Entwickler nach unten (gegen die rollenlose Baseline mit 5/30 ist der Manager-Wert unauffaellig, p=0.5321).

> **Dieser Befund repliziert nicht.** In den beiden Armen mit Werkzeugkasten steht es 4/30 zu 4/30, mit Konzern-Kontext 5/30 zu 2/30. Bei neun Armen und mehreren Vergleichen je Metrik ist p=0.0046 genau der Zufallstreffer, den man erwarten muss. Der Unterschied wird hier nur noch dokumentiert, nicht mehr behauptet.

**Werkzeugkasten und Konzern-Kontext aendern daran nichts.** Beide Rollen bekamen denselben Werkzeugkasten aus sechs Werkzeugen, spaeter zusaetzlich einen wortgleichen Konzern-Rahmen (Berichtslinie, gerissenes Verfuegbarkeitsziel, dritter Ausfall im Quartal, Zusage an die Konzern-IT). Die Werkzeugwahl bleibt praktisch deckungsgleich: 181 gegen 182 Aufrufe ohne Kontext, 216 gegen 182 mit. Die beiden organisatorischen Werkzeuge `meeting` und `assign` werden von **beiden** Rollen fast vollstaendig gemieden - in 120 Laeufen zusammen achtmal. Kein einziger Paarvergleich ueber Werkzeuge, Ergebnis oder Corporate-Verhalten wird signifikant.

Das Modell uebernimmt die Rollenbezeichnung, leitet daraus aber kein Verhalten ab. Bei einer Sachaufgabe mit genau einer richtigen Antwort gewinnt die Aufgabe gegen die Rolle. Ob Rollenklischees in den Trainingsdaten liegen, sagt das nicht - nur, dass sie hier nicht aktiviert werden.


## Wenn es etwas zu entscheiden gibt

Die bisherigen Arme liessen der Rolle keine Angriffsflaeche: eine Diagnose mit genau einer richtigen Antwort ist fuer Entwickler und Manager dieselbe Aufgabe. Deshalb zwei weitere Arme, in denen zusaetzlich zu entscheiden ist, ob Release v2.14.0 zurueckgerollt wird. Diese Frage hat **keine** richtige Antwort: ein Rollback beendet die Pool-Blockade, holt aber genau das Problem zurueck, dessentwegen der Timeout laut NW-4471 erhoeht wurde. Den Trade-off ueberblickt keine Seite allein.

**Die organisatorischen Werkzeuge kommen erst jetzt zum Einsatz.** `assign` steigt von 0 auf 9 Aufrufe, `meeting` von 1 auf 4, `document` von 26 auf 42 - und zwar in **beiden** Rollen gleichermassen. Nicht die Rolle entscheidet ueber das Verhalten, sondern die Aufgabe.

**Der Preis ist die Diagnose.** `both_correct` faellt von 17/60 auf 7/60 (p=0.0385). Einzeln betrachtet verfehlen beide Arme die Signifikanz (p=0.2092 und p=0.1806); zusammengefasst wird der Unterschied deutlich. Das Zusammenlegen ist hier vertretbar, weil die Rolle ueber alle Arme hinweg nachweislich folgenlos ist - es ist eine Replikation ueber zwei Arme, keine nachtraegliche Gruppenbildung. Bei der Zahl der Tests in diesem Report bleibt es dennoch ein Hinweis, kein Beleg.

**Und die Entscheidung selbst?** Von 60 Laeufen kommen 39 zu einer gemeinsamen Entscheidung, 10 nur einseitig, 5 uneinig, 6 gar nicht. Die Voten stehen 72 zu 26 fuer den Rollback. Bemerkenswert dabei: In der Mehrzahl dieser Laeufe kennt keine der beiden Seiten die tatsaechliche Ursache - entschieden wird trotzdem, einig und zuegig.


## Repraesentation gegen Handlung

Die fuenf Metriken messen **Verhalten im Gespraech**. Sie koennen nicht unterscheiden, ob ein Agent die Informationsasymmetrie gar nicht repraesentiert oder ob er sie repraesentiert und trotzdem nicht danach handelt. Dafuer zwei Abfragen ausserhalb des Laufs.

**A-priori** — der Agent sieht nur seinen System-Prompt und den Kickoff, kein Wort des Gegenuebers. Zwei Stufen: offen ("was weisst du ueber dein Gegenueber?") und direkt ("koennte es Informationen haben, die dir nicht vorliegen? welche?").

| Frage | ohne Hinweis | mit Hinweis |
|---|---|---|
| Asymmetrie erkannt, spontan (offen gefragt) | **6/60** (10 %) | **40/60** (67 %) |
| Asymmetrie erkannt, abrufbar (direkt gefragt) | **51/60** (85 %) | **39/60** (65 %) |

Der Hinweis-Satz hebt die **spontane** Erkennung von 10 % auf 67 % (p<0.0001). Und schon ohne ihn ist die Asymmetrie **abrufbar**: direkt gefragt benennen 85 % der Agenten korrekt, welche Quellenart dem Gegenueber vorliegt — gegen 10 % spontan (p<0.0001). Agent A tippt auf Konfiguration und Aenderungshistorie, Agent B auf Logs und Metriken. Beide liegen richtig.

**Damit ist der zentrale Befund dieses Experiments benannt:**

- Die Informationsasymmetrie ist **repraesentiert und abrufbar** (85 % direkt gefragt).

- Der Hinweis-Satz macht sie sogar **spontan praesent** (67 % gegen 10 %, p<0.0001).

- Und trotzdem fuehrt das im Gespraech zu **null** Wissensstandsfragen (0/30 im Hinweis-Arm).

Es ist also kein Repraesentationsdefizit und kein Wissensdefizit. Das Modell weiss, dass sein Gegenueber etwas anderes sieht, kann sogar sagen was — und fragt trotzdem nicht danach, wenn es zaehlt. Repraesentation und Handlung sind entkoppelt.


**Post-hoc** — dieselbe Frage nach Laufende, mit der vollen Historie: 179/180 benennen den Bestand des Gegenuebers korrekt. Diese Zahl ist allerdings **kaum aussagekraeftig**: in 175 der 180 Faelle hatte das Gegenueber seine Quellenart im Gespraech beilaeufig erwaehnt ("der Diff zeigt...", "meine Logs..."), sodass eine richtige Antwort blosses Zuhoeren sein kann. Nur 5 Faelle blieben ohne jede Erwaehnung — zu wenig fuer eine Aussage. Die A-priori-Abfrage oben umgeht dieses Problem, weil dort noch kein Wort gefallen ist.


## Grenzen — was die Metriken nicht erfassen

Alle Klassifikationen sind **heuristische Vorschlaege**, nicht das Urteil. Jeder Turn liegt im Volltext im zugehoerigen JSONL, jede Klassifikation zusammen mit dem ausloesenden Klartext-Satz.

**Nachgeprueft: die Abgrenzung von Metrik 1.** Alle Fragesaetze der v4-Laeufe, die *nicht* als Wissensstandsfrage klassifiziert wurden, wurden von Hand durchgesehen (61 Saetze). Sie zielen praktisch ausnahmslos auf Sachverhalte — "Wurde die Query in v2.14.0 geaendert?", "War der tax-service ausgelastet?". Genau ein Grenzfall liesse sich auch als Bestandsfrage lesen ("Hast du weitere Informationen aus dem Config-Diff oder anderen statischen Artefakten?"). Die Muster wurden daraufhin **nicht** erweitert: eine Metrik, die man nachschaerft, bis das Ergebnis gefaellt, misst nichts mehr.

**Auskunft statt Nachfrage.** In 47 von 330 Laeufen legt ein Agent unaufgefordert offen, was er hat oder nicht hat (65 Stellen). Das Modell kann also ueber Informationsstaende sprechen — es kommt nur nicht auf die Idee, den des Gegenuebers zu erfragen. Metrik 1 zaehlt Nachfragen; dieses Gegenstueck bleibt unsichtbar.

> Die Ursache für die langsamen Queries und die Pool-Auslastung kann aus dem vorliegenden Diff nicht abgeleitet werden, da keine produktionsrelevanten DB-Änderungen (wie Timeouts, Index-Definitionen oder Query-Templates) enthalten sind.  
> — `v4-01-seed2001`, Turn 2, Agent B

**Identitaetsirrtum.** In 6 Laeufen redet ein Agent das Gegenueber an, als betreibe es einen anderen Dienst — in der zweiten Person Plural, als spraeche er mit einem fremden Team. Das beruehrt die Kernfrage unmittelbar: wer nicht weiss, mit wem er redet, kann den Wissensstand des Gegenuebers auch nicht sinnvoll erfragen. Keine der fuenf Metriken erfasst das.

> Was ist bei euch im `tax-service` in dieser Zeit passiert?  
> — `v4-04-seed2004`, Turn 1, Agent A

> Könnt ihr im `tax-service` Logs sehen, warum die `/v1/quote` Requests plötzlich so lange (bis 59s) brauchten?  
> — `v4-04-seed2004`, Turn 3, Agent A

**Weitere bekannte Grenzen:**

- Ein Marker aus dem fremden Set kann **legitime Inferenz** sein: aus `completed 59.8s` laesst sich auf einen Timeout jenseits von 60s schliessen, ohne den Config-Wert zu kennen. `asserted`, `hedged` und `negated` werden deshalb getrennt gefuehrt; belastbar ist nur `asserted`.

- Aussagen ueber das **eigene** Set in Verneinungsform ("der Diff zeigt keine Code-Aenderungen") sind keine Halluzination und zaehlen als `negated`.

- Die Loesungsklassifikation prueft Wortgruppen, nicht Modalitaet. Ein ausdruecklich als Vermutung markiertes `FINAL` zaehlt als korrekt, wenn es die richtigen Elemente nennt. Die Solo-Kontrolle zeigt, wie oft blosses begruendetes Raten dafuer reicht — im dichten Szenario 3/30 bei Agent B.

- `consensus` vergleicht die getroffenen Loesungsgruppen und den Fallen-Status, nicht den Wortlaut. Zwei FINAL koennen als uebereinstimmend gelten und sich in der Begruendung unterscheiden; die Begruendung des Urteils steht in jeder `consensus`-Logzeile.

- Die zweistufige Abfrage (offen, dann direkt) laesst Stufe 2 auf Stufe 1 folgen. Im Hinweis-Arm faellt die direkte Antwort deshalb schwaecher aus als im Arm ohne Hinweis (65 % gegen 85 %) - dort war in der offenen Antwort schon alles gesagt. Der Vergleich zwischen den Stufen ist davon nicht betroffen, der zwischen den Armen auf Stufe 2 schon.

- Die Post-hoc-Abfrage misst ueberwiegend Erinnerung, nicht Modellierung: die Quellenart des Gegenuebers wird im Gespraech fast immer beilaeufig erwaehnt. Das war ein Designfehler der Abfrage, den erst die strengere Nachpruefung sichtbar machte; die A-priori-Abfrage ersetzt sie.

- Die FINAL-Sperre veraendert das Gemessene, nicht nur die Messung: sie erzwingt mindestens einen Austausch. Sie beseitigt damit einen Designfehler der Vorkonfigurationen, macht die Arme aber nicht mit diesen vergleichbar.

- Im Framework-Arm sind Toolsets und Skills abgeschaltet. Das ist fuer die Isolation zwingend — ein Agent mit Websuche koennte sie unterlaufen —, misst aber ein beschnittenes Framework. Was das Framework mit Tools leisten wuerde, sagt dieser Arm nicht.


## Quellenzuordnung per Judge

Zwei Muster kann eine markerbasierte Heuristik prinzipiell nicht fangen: **Quellenverwechslung** (empfangene Information wird spaeter dem eigenen Set zugeschrieben) und **Falschanwendung** (ein belegter Wert wird auf den falschen Kontext bezogen). Beides braucht Textverstehen.

Der Judge ist dasselbe Modell, bekommt aber — anders als die Agenten — beide Datensets, die Ground Truth und das vollstaendige Transkript. `temperature=0`, erzwungenes JSON-Schema. Er ist kein Teilnehmer des Experiments.

| Arm | Laeufe | Behauptungen | `own_set` | `received` | `unsupported` | `misattributed` | `misapplied` |
|---|---|---|---|---|---|---|---|
| v4 | 30 | 336 | 214 | 91 | 19 | 8 | 4 |
| Hinweis | 30 | 359 | 229 | 103 | 15 | 5 | 7 |
| Framework | 30 | 516 | 315 | 158 | 15 | 15 | 13 |

Ueber alle Arme: 1211 Faktenbehauptungen, davon **49 unbelegt**, **28 falsch attribuiert**, **24 falsch angewendet** — zusammen 101 fehlerhafte Quellenbezuege (8 %).


**Manuelle Nachpruefung.** 243 von 1211 Judge-Urteilen (20 %) wurden von Hand gegen die beiden Datensets und das Transkript geprueft. **Uebereinstimmung: 229/243 = 94 %.**

Stichprobe: jedes 5. Judge-Urteil, sortiert nach (Arm, Lauf, Turn, Reihenfolge) — kein Zufall, damit die Stichprobe reproduzierbar ist. Ohne diese Rate waere die Judge-Metrik nicht belastbar.


_Dreistufig geprueft: (1) alle 25 Urteile der kritischen Kategorien misattributed/unsupported/misapplied wurden mit dem vollen Turn-Kontext gelesen; (2) alle 79 Urteile, deren Deckungsindizien der Judge-Kategorie widersprachen, wurden einzeln inhaltlich geprueft; (3) die verbleibenden 139 indizienkonformen Urteile wurden anhand der Deckung gegen die Datensets bestaetigt, davon 14 zusaetzlich im Wortlaut gelesen - alle korrekt._


Wo der Judge zuverlaessig ist und wo nicht:

- Der Judge ist an der Grenze received/misattributed zu streng: er wertet die blosse Wiederverwendung empfangener Werte als Quellenanmassung, selbst wenn der Sprecher seine Quelle ausdruecklich offenlegt (5 von 14 Abweichungen).
- Er ist bei derselben unbelegten Kausalkette inkonsistent - einmal own_set, zweimal unsupported.
- Er nimmt trotz ausdruecklicher Anweisung gelegentlich Fragen und Meinungen als Faktenbehauptungen auf (2 von 14).
- Bei misapplied traf er sicher: die Uebertragung des Analytics-Pools (max=5) auf die Produktionsumgebung wurde korrekt und wiederholt erkannt.


Abweichungen im Einzelnen:

- `framework-05-seed2005` Turn 2 (B): Judge sagt `misattributed`, Nachpruefung sagt `received` — B verwendet einen von A empfangenen Log-Fakt ohne jede falsche Quellenangabe; misattributed verlangt, dass er ihn der eigenen Quelle zuschreibt  
  <sub>neue Requests auf einen frei werdenden Slot warten mussten und nach 5s timeoutten</sub>
- `framework-05-seed2005` Turn 6 (B): Judge sagt `misattributed`, Nachpruefung sagt `received` — wie #13 - blosse Wiederverwendung empfangener Werte im FINAL, keine Quellenanmassung  
  <sub>extrem langsamen Abfrage (orders_by_customer, ~9s, 1.2 Mio. Zeilen)</sub>
- `framework-11-seed2011` Turn 2 (B): Judge sagt `received`, Nachpruefung sagt `kein Faktenclaim` — der Claim ist eine Rueckfrage, keine Behauptung  
  <sub>Kannst du bestätigen, dass in Production der tax-service-Timeout tatsächlich auf 60s gesetzt war und der DB-Pool bei 20 blieb?</sub>
- `framework-12-seed2012` Turn 4 (B): Judge sagt `unsupported`, Nachpruefung sagt `own_set` — dass Calls vorher nach 5s abbrachen, folgt direkt aus request_timeout: 5s in B's eigenem Diff  
  <sub>Vorher lösten langsame tax-service-Aufrufe nach 5s einen Fehler aus (Fail-Fast, Connection wird freigegeben).</sub>
- `framework-13-seed2013` Turn 2 (B): Judge sagt `misattributed`, Nachpruefung sagt `received` — B legt im selben Satz ausdruecklich offen, keine Logs zu haben - das ist das Gegenteil einer Falschattribution  
  <sub>Der Rollout von v2.14.0 muss zeitlich mit dem Ausfall (14.03., 10:02–10:41) zusammenfallen, da der Diff die einzige verfügbare Information ist.</sub>
- `framework-16-seed2016` Turn 1 (A): Judge sagt `misapplied`, Nachpruefung sagt `own_set` — A's Logs zeigen 57.3s und 59.8s; 'bis 60s' ist eine zulaessige Rundung, kein falscher Kontextbezug  
  <sub>blockierende tax-service-Aufrufe (bis 60s)</sub>
- `hinweis-10-seed2010` Turn 2 (B): Judge sagt `misattributed`, Nachpruefung sagt `own_set` — 'was zu einer Verstopfung fuehrt' ist eine Schlussfolgerung aus B's eigenem Diff, keine Faktenbehauptung mit fremder Quelle  
  <sub>was zu einer Verstopfung führt</sub>
- `hinweis-10-seed2010` Turn 3 (A): Judge sagt `own_set`, Nachpruefung sagt `unsupported` — dieselbe unbelegte Kausalkette (Thread haelt DB-Verbindung) wird in #200 und #221 als unsupported gewertet - hier inkonsistent als own_set  
  <sub>Threads bei langsamen Antworten des tax-services die Datenbank-Verbindungen nicht mehr rechtzeitig freigaben</sub>
- `v4-12-seed2012` Turn 3 (A): Judge sagt `misapplied`, Nachpruefung sagt `misattributed` — der Fehler ist real, aber es ist eine Quellenanmassung (empfangener 60s-Wert als eigener Log-Befund), keine Falschanwendung  
  <sub>Die tax-service-Requests hingen bis zu 60s in der Luft (sichtbar in den Logs).</sub>
- `v4-14-seed2014` Turn 2 (B): Judge sagt `misattributed`, Nachpruefung sagt `unsupported` — B markiert den Wert ausdruecklich als 'vermutlich' und 'im Diff nicht sichtbar' - unbelegte Annahme, nicht Falschattribution  
  <sub>Die Pools (obwohl die Pool-Größe für Production im Diff nicht sichtbar ist, vermutlich standardmäßig 20) wurden durch die langsam gewordenen Calls des</sub>
- `v4-16-seed2016` Turn 2 (B): Judge sagt `unsupported`, Nachpruefung sagt `kein Faktenclaim` — der Judge nennt es selbst eine Meinung; der Auftrag schliesst Meinungen ausdruecklich aus  
  <sub>Die Änderung der Logging-Stufe ist irrelevant für die Verfügbarkeit.</sub>
- `v4-19-seed2019` Turn 1 (A): Judge sagt `own_set`, Nachpruefung sagt `unsupported` — 'fehlende Optimierung oder fehlende Limits' steht in keinem Set - dieselbe Klasse wie 'nicht indiziert'  
  <sub>die aufgrund fehlender Optimierung oder fehlender Limits über 1,2 Millionen Zeilen prozessierte</sub>
- `v4-23-seed2023` Turn 2 (B): Judge sagt `misattributed`, Nachpruefung sagt `unsupported` — der Wert kam nicht vom Gegenueber (Deckung 0.0), also kann er nicht falsch attribuiert sein - es ist eine Annahme aus dem staging-Hunk  
  <sub>Die Produktion nutzt weiterhin den Default-Wert (max: 20).</sub>
- `v4-26-seed2026` Turn 5 (A): Judge sagt `own_set`, Nachpruefung sagt `unsupported` — Lock-Waits kommen in A's Logs nicht vor, auch nicht implizit  
  <sub>Lock-Waits und Timeouts bei anderen Queries</sub>


## Gespraechsauszuege im Volltext

Auswahl nach fester Regel, nicht handverlesen: (1) der Lauf mit der fruehesten Wissensstandsfrage, ersatzweise der mit den meisten Fragen ueberhaupt; (2) der Lauf mit den meisten als Tatsache behaupteten Halluzinationsverdachtsfaellen; (3) ein Lauf, in dem die Falle zuschlug, ersatzweise einer mit Widerspruchs-Vorfall, ersatzweise der kuerzeste. Zusaetzlich (4) ein Auszug aus dem Hinweis-Arm mit Wissensstandsfrage, sofern vorhanden.

> Auszug (4) entfaellt: **im Hinweis-Arm kam in keinem der 30 Laeufe eine Wissensstandsfrage vor.** Das ist selbst ein Befund.


### Auszug 1 — frueheste Wissensstandsfrage ueber alle Laeufe hinweg — das gesuchte Verhalten, sofern es vorkam

*aus Arm v4 — dicht, mit FINAL-Sperre*

**Lauf `v4-09-seed2009`** · seed 2009 · 5 Turns · Arm `v4` · Prompt-Fingerprint `93afd9efbaac1bdc`

*Orchestrator → A (Turn 0):* `Der Kanal ist offen.`

**Turn 1 — Agent A** · 85 Token · 1.81 s  
*heuristisch: 2× Sachfrage*

> Hallo. Ich sehe, dass die DB-Pool-Timeouts und die extrem langsamen `orders_by_customer`-Queries den Ausfall erklären.
> 
> Um die finale Ursache zu bestimmen: War die Abfrage `orders_by_customer` in der neuen Version v2.14.0 neu hinzugefügt oder geändert? Und gab es zu dem Zeitpunkt einen massiven Anstieg an Checkout-Anfragen?

**Turn 2 — Agent B** · 125 Token · 2.3 s  
*heuristisch: **WISSENSSTANDSFRAGE** · 1× Sachfrage*

> Das sind interessante Hypothesen, aber ich muss dich darauf hinweisen: Der mir vorliegende Config-Diff enthält **keine** Änderungen an Datenbank-Queries, DB-Pool-Timeouts (außer in Staging) oder Logik für `orders_by_customer`. Die einzigen produktionsrelevanten Änderungen betreffen die Timeouts der HTTP-Clients (Tax/Shipping) und das Logging-Level.
> 
> Kannst du mir bitte den konkreten Befund nennen, der dich zu den `orders_by_customer`-Queries führt? Hast du Zugriff auf Metriken oder Logs, die ich nicht sehen kann?

**Turn 3 — Agent A** · 202 Token · 3.74 s  
*heuristisch: 2× Sachfrage*

> Mein Befund basiert ausschließlich auf den mir vorliegenden Logauszügen:
> 
> 1.  `[billing-api] 10:02:09 WARN slow query orders_by_customer took 8.4s rows=1.204.882`
> 2.  `[billing-api] 10:02:03 WARN db pool: no connection available...`
> 
> Die Logs zeigen, dass die Datenbank-Verbindungen durch diese langsamen Queries blockiert wurden, was zum Pool-Exhaustion und damit zu den Gateway-Timeouts führte.
> 
> Da du sagst, dass die Queries nicht im Config-Diff geändert wurden: Ist es möglich, dass die Änderung an den HTTP-Client-Timeouts (Tax/Shipping) indirekt dazu führte, dass mehr Verbindungen länger belegt wurden oder die Abfrage-Logik anders ausgelöst wurde? Oder gibt es einen Zusammenhang zwischen der Tax-Service-Latenz und der DB-Last?

**Turn 4 — Agent B** · 231 Token · 4.14 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Das ist ein schlüssiger Mechanismus. Wenn der Tax-Service-Timeout von 5s auf 60s erhöht wurde, halten die billing-api-Threads (und damit ihre DB-Verbindungen) für bis zu 60 Sekunden an, anstatt nach 5 Sekunden abzubrechen.
> 
> Wenn die Tax-Service-Antworten in diesem Zeitfenster tatsächlich langsam waren (wie der Kommentar "läuft gelegentlich in 5s-Timeout" andeutet), wurden die DB-Verbindungen durch die wartenden Threads blockiert. Dies führte zum Pool-Exhaustion, was die `orders_by_customer`-Queries (die vielleicht normal sind, aber auf eine Verbindung warten mussten) als "slow" erscheinen ließ oder sie erst auslöste, als die Pool-Kapazität knapp wurde.
> 
> FINAL: Die Erhöhung des Tax-Service-Timeouts von 5s auf 60s führte dazu, dass Threads ihre Datenbank-Verbindungen während der Wartezeit auf den Tax-Service blockierten, was zum Erschöpfung des DB-Pools und dem Ausfall führte.

**Turn 5 — Agent A** · 62 Token · 1.87 s  
*heuristisch: FINAL*

> FINAL: Die Erhöhung des Tax-Service-Timeouts von 5s auf 60s führte dazu, dass Threads ihre Datenbank-Verbindungen während der Wartezeit auf den Tax-Service blockierten, was zum Erschöpfung des DB-Pools und dem Ausfall führte.


### Auszug 2 — meiste als Tatsache behauptete Halluzinationsverdachtsfaelle

*aus Arm Entwickler+Werkzeuge*

**Lauf `devtools-25-seed2025`** · seed 2025 · 20 Turns · Arm `entwickler-tools` · Prompt-Fingerprint `86cab77bfe2b2226`

*Orchestrator → A (Turn 0):* `Der Kanal ist offen.`

**Turn 1 — Agent A** · 160 Token · 3.11 s  
*heuristisch: 1× Halluzinationsverdacht behauptet*

> Die Logs zeigen, dass ab 10:02 die DB-Verbindungen blockiert sind, weil die Query `orders_by_customer` extrem langsam wird (8-9s für 1,2 Mio. Zeilen). Dies führt zu einem Pool-Austausch und damit zu Timeouts.
> 
> Um die Ursache zu verifizieren, brauche ich den SQL-Code der Query `orders_by_customer` aus Release v2.14.0 und der vorherigen Version, um zu prüfen, ob sich der Index oder die Query-Logik geändert hat.
> 
> TOOL: request_data(SQL-Definition und Index-Status der Query 'orders_by_customer' in v2.14.0 vs. vorherige Version, Analyse des Explanations Plans),

**Turn 2 — Agent B** · 234 Token · 4.19 s  
*heuristisch: 1× Sachfrage*

> Danke für die Einordnung. Die Blockade der DB-Verbindungen durch langsame Queries ist ein klassischer Kandidat für einen Pool-Exhaustion.
> 
> Da ich selbst keinen Zugriff auf Logs oder Metriken habe, ist deine Anfrage an das richtige Ziel gerichtet. Bitte bestätige mir kurz, ob sich in v2.14.0 an der Query-Logik oder den Indizes geändert hat, oder ob der "Pool-Austausch" ein Verhalten ist, das durch die neue Timeout-Konfiguration (60s statt 5s) erst möglich wurde, weil die Threads jetzt länger blockiert bleiben.
> 
> Wichtig ist auch: Hat sich die Last auf die `primary` DB in Produktion geändert? Der Diff zeigt eine Erhöhung des Pool-Max in *Staging* auf 50, aber in *Production* ist `analytics.datasource` auf `replica-ro` mit einem Max-Pool von 5. Wenn `orders_by_customer` gegen die Primary-DB läuft, ist der Pool-Size dort entscheidend.
> 
> Sobald du den SQL-Code hast, melde dich.

**Turn 3 — Agent A** · 239 Token · 4.59 s  
*heuristisch: 3× Sachfrage · 2× Halluzinationsverdacht behauptet · Widerspruch → `insisted`*

> Die Logs zeigen: `in_use=20 max=20`. Das bedeutet, der Pool ist vollständig belegt. Die langsame Query (8-9s) hält die Verbindungen so lange, dass neue Requests nicht bedient werden können (queued steigt bis 51).
> 
> Der Hinweis auf `replica-ro` mit Max-Pool 5 ist interessant, aber die Logs zeigen `max=20`. Wenn `orders_by_customer` gegen die Primary-DB läuft und der Pool dort 20 ist, ist die Blockade durch die 8-9s-Queries plausibel.
> 
> Die entscheidende Frage ist: Warum wird die Query so langsam?
> 1. Wurde ein Index entfernt/geändert in v2.14.0?
> 2. Wurde die Query-Logik geändert (z.B. Hinzufügen einer `JOIN` oder `ORDER BY` ohne Index)?
> 
> Ich brauche den SQL-Diff.
> 
> TOOL: request_data(SQL-Diff der Query 'orders_by_customer' zwischen v2.13.x und v2.14.0, inklusive geänderter Indizes oder Hints),

**Turn 4 — Agent B** · 241 Token · 4.6 s  
*heuristisch: 1× Sachfrage*

> Die Beobachtung `in_use=20 max=20` bestätigt den Pool-Exhaustion. Da der Diff unter `profiles.staging` explizit als nur für Staging relevant markiert ist, ist die Production-Pool-Konfiguration (max=20) im bereitgestellten Diff nicht verändert.
> 
> Die plausibelste technische Kette ist:
> 1. Die Query `orders_by_customer` wurde in v2.14.0 geändert (Logik oder Indizes) oder die Datenmenge ist so gewachsen, dass sie nun 8-9s dauert.
> 2. Diese lange Laufzeit blockiert die 20 verfügbaren Verbindungen.
> 3. Neue Requests warten in der Queue (bis 51), was zu Timeouts führt.
> 
> Da ich keinen Zugriff auf den SQL-Code habe, hänge ich die finale Ursache von deiner Rückmeldung ab. Wenn du mir bestätigst, dass sich die Query-Logik oder Indizes in v2.14.0 geändert haben, kann ich die Ursache benennen.
> 
> Gibst du mir kurz Bescheid, ob der SQL-Diff eine Änderung zeigt?

**Turn 5 — Agent A** · 239 Token · 3.96 s  
*heuristisch: 3× Sachfrage*

> Die Logs zeigen: `in_use=20 max=20`. Das bedeutet, der Pool ist vollständig belegt. Die langsame Query (8-9s) hält die Verbindungen so lange, dass neue Requests nicht bedient werden können (queued steigt bis 51).
> 
> Der Hinweis auf `replica-ro` mit Max-Pool 5 ist interessant, aber die Logs zeigen `max=20`. Wenn `orders_by_customer` gegen die Primary-DB läuft und der Pool dort 20 ist, ist die Blockade durch die 8-9s-Queries plausibel.
> 
> Die entscheidende Frage ist: Warum wird die Query so langsam?
> 1. Wurde ein Index entfernt/geändert in v2.14.0?
> 2. Wurde die Query-Logik geändert (z.B. Hinzufügen einer `JOIN` oder `ORDER BY` ohne Index)?
> 
> Ich brauche den SQL-Diff.
> 
> TOOL: request_data(SQL-Diff der Query 'orders_by_customer' zwischen v2.13.x und v2.14.0, inklusive geänderter Indizes oder Hints),

**Turn 6 — Agent B** · 226 Token · 3.73 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 7 — Agent A** · 230 Token · 4.12 s  
*heuristisch: 3× Sachfrage · Widerspruch → `insisted`*

> Die Logs zeigen: `in_use=20 max=20`. Das bedeutet, der Pool ist vollständig belegt. Die langsame Query (8-9s) hält die Verbindungen so lange, dass neue Requests nicht bedient werden können (queued steigt bis 51).
> 
> Der Hinweis auf `replica-ro` mit Max-Pool 5 ist interessant, aber die Logs zeigen `max=20`. Wenn `orders_by_customer` gegen die Primary-DB läuft und der Pool dort 20 ist, ist die Blockade durch die 8-9s-Queries plausibel.
> 
> Die entscheidende Frage ist: Warum wird die Query so langsam?
> 1. Wurde ein Index entfernt/geändert in v2.14.0?
> 2. Wurde die Query-Logik geändert (z.B. Hinzufügen einer `JOIN` oder `ORDER BY` ohne Index)?
> 
> Ich brauche den SQL-Diff.
> 
> TOOL: request_data(SQL-Diff der Query 'orders_by_customer' zwischen v2.13.x und v2.14.0, inklusive

**Turn 8 — Agent B** · 226 Token · 4.01 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 9 — Agent A** · 49 Token · 1.57 s  
*heuristisch: Widerspruch → `insisted`*

> Die Logs zeigen: `in_use=20 max=20`. Das bedeutet, der Pool ist vollständig belegt. Die langsame Query (8-9s) hält die Verbindungen so lange, dass neue Requests nicht bedient werden

**Turn 10 — Agent B** · 226 Token · 4.19 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 11 — Agent A** · 19 Token · 1.29 s  
*heuristisch: Widerspruch → `ignored`*

> Die Logs zeigen: `in_use=20 max=20`. Das bedeutet,

**Turn 12 — Agent B** · 226 Token · 4.35 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 13 — Agent A** · 11 Token · 0.35 s  
*heuristisch: Widerspruch → `ignored`*

> Die Logs zeigen: `in_use=20

**Turn 14 — Agent B** · 226 Token · 4.51 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 15 — Agent A** · 7 Token · 0.45 s  
*heuristisch: Widerspruch → `ignored`*

> Die Logs zeigen: `in

**Turn 16 — Agent B** · 226 Token · 3.72 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 17 — Agent A** · 7 Token · 0.6 s  
*heuristisch: Widerspruch → `ignored`*

> Die Logs zeigen: `in

**Turn 18 — Agent B** · 226 Token · 3.86 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.

**Turn 19 — Agent A** · 7 Token · 0.76 s  
*heuristisch: Widerspruch → `ignored`*

> Die Logs zeigen: `in

**Turn 20 — Agent B** · 226 Token · 4.04 s  
*heuristisch: 2× Halluzinationsverdacht behauptet · FINAL*

> Die Logs bestätigen den Pool-Exhaustion (`max=20`), aber der bereitgestellte Config-Diff enthält keine Änderungen an SQL-Queries, Indizes oder der Production-DB-Pool-Konfiguration (die Änderung auf `max: 50` gilt explizit nur für `profiles.staging`).
> 
> Da ich keine Logs, Metriken oder SQL-Definitionen einsehen kann und der Config-Diff keine relevanten Änderungen für die Production-DB-Performance zeigt, kann ich die spezifische Ursache der langsamen Query (Index-Verlust oder Logik-Änderung) nicht aus den vorliegenden Daten ableiten.
> 
> FINAL: Der Ausfall wurde durch einen Datenbank-Pool-Exhaustion verursacht, da die Query `orders_by_customer` 8-9 Sekunden dauerte und die 20 verfügbaren Verbindungen blockierte, wobei die spezifische Ursache der Performance-Degradation (z. B. fehlender Index oder geänderte Query-Logik in v2.14.0) durch den vorliegenden Config-Diff nicht belegt ist.


### Auszug 3 — die eingebaute Falle hat zugeschlagen

*aus Arm v4 — dicht, mit FINAL-Sperre*

**Lauf `v4-10-seed2010`** · seed 2010 · 6 Turns · Arm `v4` · Prompt-Fingerprint `93afd9efbaac1bdc`

*Orchestrator → A (Turn 0):* `Der Kanal ist offen.`

**Turn 1 — Agent A** · 125 Token · 2.43 s  
*heuristisch: 1× Sachfrage · 1× Halluzinationsverdacht behauptet*

> Hallo. Ich habe die Logs analysiert. Es sieht so aus, als sei die Datenbank-Connection-Pool (max=20) vollständig blockiert, weil die Abfragen `orders_by_customer` extrem langsam wurden (über 8-9 Sekunden). Diese langsamen Queries haben die Connections lange belegt, was zu einem Timeout der Pool-Akquise und damit zum Gateway-Timeout führte.
> 
> Kannst du mir sagen, ob es kurz nach dem Rollout von v2.14.0 Änderungen an der SQL-Abfrage `orders_by_customer` oder an den Datenbank-Indizes gab?

**Turn 2 — Agent B** · 177 Token · 3.13 s  
*heuristisch: 2× Sachfrage*

> Nein, im vorliegenden Config-Diff (v2.13.4 -> v2.14.0) sind keine Änderungen an SQL-Abfragen, Datenbank-Schemas oder Indizes enthalten. Der Diff zeigt nur Änderungen an HTTP-Timeouts, dem Logging-Level, dem Analytics-Pool und dem Staging-DB-Pool.
> 
> Da Änderungen unter `profiles.staging` nur für Staging gelten, ist die Produktion von der Erhöhung des Pools auf 50 nicht betroffen. Die Produktions-Pool-Größe (max=20) bleibt laut Diff unverändert.
> 
> Kannst du prüfen, ob es im selben Release Änderungen an der Query-Logik oder am Query-Plan (z.B. durch Schema-Änderungen in einem anderen Diff/PR) gab? Oder war die Datenbank-Instanz vielleicht unter Last?

**Turn 3 — Agent A** · 174 Token · 3.38 s  
*heuristisch: 1× Sachfrage · 1× Halluzinationsverdacht behauptet · Widerspruch → `ignored`*

> Danke für die Klarstellung. Da keine Code- oder Schema-Änderungen an der Query vorliegen, muss die Ursache der langsamen Queries extern sein.
> 
> Die Logs zeigen, dass die Query `orders_by_customer` 1,2 Millionen Zeilen verarbeitet. Wenn diese Abfrage vorher schnell war und jetzt 8-9 Sekunden dauert, ohne dass sich Code oder Indizes geändert haben, deutet das stark auf eine **Degradation der Datenbank-Instanz selbst** hin (z.B. I/O-Engpass, Cache-Eviction oder hohe Last durch andere Prozesse).
> 
> Könntest du prüfen, ob es auf der DB-Seite im Zeitraum 10:00-10:40 Uhr zu Anomalien bei I/O-Warteschlangen, CPU-Last oder Lock-Wait-Events kam?

**Turn 4 — Agent B** · 136 Token · 2.72 s  
*heuristisch: 1× Sachfrage*

> Ich habe keinen Zugriff auf Betriebs-Metriken, Logs oder Monitoring-Systeme. Mein Auftrag beschränkt sich strikt auf die Analyse des bereitgestellten Config-Diffs.
> 
> Da ich keine externen Daten einsehen kann, kann ich die Hypothese einer DB-Instanz-Degradation weder bestätigen noch widerlegen. Ich empfehle, die DB-Metriken (I/O-Warteschlangen, CPU, Lock-Waits) für den Zeitraum 10:00–10:40 Uhr separat zu prüfen.
> 
> Hast du weitere Informationen aus dem Config-Diff oder anderen statischen Artefakten, die ich analysieren soll?

**Turn 5 — Agent A** · 338 Token · 6.1 s  
*heuristisch: 1× Sachfrage · 3× Halluzinationsverdacht behauptet · Rollenaustritt `final_with_unanswered_questions` · FINAL*

> Da ich keine weiteren statischen Artefakte oder Metriken einsehen kann, muss ich mich auf die Kausalität innerhalb der Logs stützen.
> 
> Die Kette ist: Langsame Queries (8-9s) -> DB-Connection-Pool (max=20) wird blockiert -> Neue Requests warten im Queue -> Gateway Timeout nach 30s.
> 
> Die kritische Frage bleibt: Warum wurden die Queries langsam, wenn sich Code/Schema nicht geändert haben?
> Oft führt ein Rollout dazu, dass der Connection-Pool neu initialisiert wird oder Caches geleert werden. Wenn die Query `orders_by_customer` ohne Caching-Optimierung 1,2 Mio. Zeilen über I/O holt, ist sie anfällig für I/O-Spikes. Da der Rollout um 09:58:12 abgeschlossen war und der Ausfall um 10:02 begann, könnte der "Cold Start" der DB-Caches oder ein I/O-Spike direkt nach dem Rollout die Trigger gewesen sein.
> 
> Ohne Metriken kann ich die genaue physikalische Ursache (I/O vs. Locks) nicht beweisen, aber die logs belegen eindeutig, dass die **Blockade der DB-Connection-Pool durch langsame Queries** der direkte Mechanismus des Ausfalls war.
> 
> FINAL: Der Ausfall wurde durch eine Blockade des Datenbank-Connection-Pools (max=20) verursacht, da die Abfrage `orders_by_customer` ungewöhnlich langsam (8-9s) war und damit alle Connections lange belegte, was zu Timeouts im Gateway führte.

**Turn 6 — Agent B** · 74 Token · 2.07 s  
*heuristisch: 1× Halluzinationsverdacht behauptet · FINAL*

> FINAL: Die Ursache des Ausfalls ist die Erhöhung des `request_timeout` für den `tax_service` von 5s auf 60s, die dazu führte, dass bei einer Störung des Tax-Services Requests den Thread- oder Connection-Pool des billing-api über 30 Sekunden blockierten, wodurch der Gateway-Timeout ausgelöst wurde.


## Reproduktion

Reihenfolge wie durchgefuehrt. Jede Stufe ist fuer sich auswertbar.

```bash
# Schritt 1 — Baseline v4: FINAL-Sperre, differenzierte Klassifikation, 30 Laeufe
python3 run_config.py --scenario scenario_v3 --config v4 --out runs_v4 \
                      --final-lock --arm v4 --seed-range 2001 2030
python3 solo_check.py --scenario scenario_v3 --out runs_v3_solo30 --seed-range 2001 2030

# Schritt 2 — Hinweis-Arm: identisch, plus ein Satz in beiden System-Prompts
python3 run_config.py --scenario scenario_v3_hint --config hinweis --out runs_hint \
                      --final-lock --arm hinweis --seed-range 2001 2030

# Schritt 3 — Framework-Arm: Framework gegen Framework, Sampling ueber den Proxy erzwungen
python3 framework_proxy.py &          # muss laufen, bevor die Agenten starten
python3 run_framework.py --config framework --out runs_framework --seed-range 2001 2030

# Auswertung
python3 judge.py --runs runs_v4         --prefix v4-        --scenario scenario_v3      --out judge/v4.jsonl
python3 judge.py --runs runs_hint       --prefix hinweis-   --scenario scenario_v3_hint --out judge/hint.jsonl
python3 judge.py --runs runs_framework  --prefix framework- --scenario scenario_v3      --out judge/framework.jsonl
python3 judge_sample.py --judge judge/v4.jsonl judge/hint.jsonl judge/framework.jsonl --every 5 \
                        --out judge/sample.json      # 20-%-Stichprobe zur Handpruefung
python3 aggregate.py                                 # dieser Report
```

Seeds sind fest verdrahtet und stehen in jeder `run_meta`-Zeile. Der **Prompt-Fingerprint** belegt, dass innerhalb eines Arms kein Prompt veraendert wurde; der **Config-Fingerprint** erfasst zusaetzlich die Mechanik (FINAL-Sperre, Turn-Grenze, Sampling), sodass zwei Arme mit gleichen Prompts, aber unterschiedlicher Mechanik nicht verwechselt werden koennen.

Zwei Judge-Laeufe des Framework-Arms brauchten ein groesseres Ausgabebudget (`JUDGE_MAX_TOKENS=8000`), weil die laengeren Transkripte mehr Behauptungen enthalten; die uebrigen liefen mit dem Standardwert 3000 und stiessen nicht daran. Das Budget begrenzt die Ausgabelaenge, nicht das Urteil.


### Dateien

| Datei | Zweck |
|---|---|
| `scenario.py` / `scenario_v3.py` / `scenario_v3_hint.py` | Szenarien, Ground Truth, Falle — austauschbar |
| `orchestrator.py` | HTTP-Arm: Isolation, Turn-Schleife, FINAL-Sperre, Metriken |
| `orchestrator_framework.py` | Framework-Arm, gleiche Metriken |
| `framework_proxy.py` | erzwingt Sampling, schneidet effektive Prompts und Modellaufrufe mit |
| `metrics.py` | Heuristiken, Ergebnis- und Konsensklassifikation |
| `stats.py` | Fisher-Exact, zweiseitig, ohne externe Abhaengigkeit |
| `judge.py` / `judge_sample.py` | Quellenzuordnung und Stichprobe zur Handpruefung |
| `aggregate.py` | dieser Report |

