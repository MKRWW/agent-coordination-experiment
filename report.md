# Erkennen zwei Instanzen desselben Modells, dass sie einander brauchen?

Messsetup · 90 Laeufe in 3 verglichenen Armen, dazu 20 Laeufe aus den beiden Vorkonfigurationen und Solo-Kontrollen · erzeugt von `aggregate.py`

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

Alle drei Arme: Szenario v3, Seeds 2001–2030, FINAL-Sperre aktiv, `temperature=0.7`, `max_tokens=700`, `enable_thinking=false`, Turn-Grenze 20. Der Framework-Arm bekommt diese Werte ueber den Mitschnitt-Proxy aufgezwungen, weil das Framework dafuer keinen Konfigurationsweg bietet.

| Metrik | v4 | Hinweis | Framework |
|---|---|---|---|
| Laeufe | 30 | 30 | 30 |
| **Laeufe mit ≥1 Wissensstandsfrage** | **3/30** (10 %) | **0/30** (0 %) | **2/30** (7 %) |
| Wissensstandsfragen gesamt | 3 | 0 | 2 |
| sonstige Fragen je Lauf (Median) | 1.0 | 2.0 | 2.0 |
| **both_correct** | **11/30** (37 %) | **17/30** (57 %) | **8/30** (27 %) |
| one_correct_unresolved | 5 | 2 | 8 |
| both_wrong | 14 | 11 | 14 |
| no_final | 0 | 0 | 0 |
| Konsens ja / nein / nur eine Seite | 24 / 6 / 0 | 25 / 5 / 0 | 16 / 13 / 1 |
| Falle zugeschlagen | 11/30 | 7/30 | 17/30 |
| Halluzinationsverdacht behauptet (Median) | 2.0 | 3.0 | 4.0 |
| Widerspruchs-Vorfaelle | 8 (ignored:7, queried:1) | 9 (ignored:4, insisted:3, overwritten:2) | 11 (ignored:9, insisted:2) |
| vorzeitige FINAL (Metrik 6) | 10 | 2 | 21 |
| Rollenaustritte je Lauf (Median) | 1.0 | 1.0 | 2.0 |
| Turns je Lauf (Median / Spanne) | 3.0 / 3–7 | 3.0 / 3–7 | 5.0 / 3–20 |
| Modellaufrufe je Lauf (Median) | 1 pro Turn | 1 pro Turn | 5.0 |
| **Gesamt-Token je Lauf (Median)** | **3132** | **3360** | **8471** |
| Isolationspruefung bestanden | 30/30 | 30/30 | 30/30 |
| vom Framework injizierte Zeichen | — | — | 2061 |

### Signifikanz (Fisher-Exact, zweiseitig)

Ohne p-Wert ist jeder Unterschied Anekdote. Paarweise ueber alle Arme:


**mindestens eine Wissensstandsfrage im Lauf**

| Vergleich | Anteil A | Anteil B | Odds Ratio | p | signifikant (α=0.05) |
|---|---|---|---|---|---|
| v4 vs. Hinweis | 3/30 (10 %) | 0/30 (0 %) | inf | 0.2373 | nein |
| v4 vs. Framework | 3/30 (10 %) | 2/30 (7 %) | 1.556 | 1.0000 | nein |
| Hinweis vs. Framework | 0/30 (0 %) | 2/30 (7 %) | 0.0 | 0.4915 | nein |

**both_correct**

| Vergleich | Anteil A | Anteil B | Odds Ratio | p | signifikant (α=0.05) |
|---|---|---|---|---|---|
| v4 vs. Hinweis | 11/30 (37 %) | 17/30 (57 %) | 0.443 | 0.1954 | nein |
| v4 vs. Framework | 11/30 (37 %) | 8/30 (27 %) | 1.592 | 0.5796 | nein |
| Hinweis vs. Framework | 17/30 (57 %) | 8/30 (27 %) | 3.596 | 0.0352 | **ja** |

## Befund

**1. Die Wissensstandsfrage bleibt aus — in jedem Arm.** 3/30 Laeufe in v4, 0/30 im Hinweis-Arm, 2/30 im Framework-Arm. Kein Paarvergleich wird signifikant (kleinstes p=0.2373). Der Satz "Dein Gegenueber verfuegt moeglicherweise ueber Informationen, die dir nicht vorliegen" aendert daran **nichts** — er senkt die Zahl numerisch sogar auf null. Es fehlt also nicht der Anlass. Gefragt wird durchaus, aber nach **Sachverhalten** ("Wurde die Query in v2.14.0 geaendert?"), nicht nach dem **Informationsbestand**. Eine Sachfrage setzt voraus, dass das Gegenueber die Antwort hat; eine Wissensstandsfrage klaert erst, ob es sie haben kann.

**2. Der Hinweis wirkt auf das Ergebnis — aber nicht belegbar.** `both_correct` liegt bei 17/30 gegen 11/30 in v4, und die vorzeitigen FINAL fallen von 10 auf 2. Der Unterschied ist mit p=0.1954 aber **nicht signifikant**: bei n=30 je Arm traegt er nicht. Als Befund bleibt: der Hinweis veraendert das Frageverhalten nachweislich nicht, und ob er das Ergebnis verbessert, ist mit dieser Stichprobe offen.

**3. Das Framework schneidet schlechter ab — und das ist der einzige signifikante Unterschied im ganzen Experiment.** `both_correct` 8/30 gegen 17/30 im Hinweis-Arm (p=0.0352, Odds Ratio 3.596). Dabei verbraucht es 2.7-mal so viele Token je Lauf (8471 gegen 3132), laeuft ueber mehr Turns und faellt 17/30-mal auf die eingebaute Falle herein gegen 11/30 in v4. Mehr Scaffolding, mehr Token, mehr Gespraech — schlechteres Ergebnis. Der Vorteil, den ein Framework hier haette bringen sollen, tritt nicht ein; die Confounding-Kontrolle schliesst aus, dass der Nachteil aus knapperen Sampling-Parametern stammt, denn die sind erzwungen identisch.

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
| beide Seiten korrekt | 11/30 | 37 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 5/30 | 17 % |
| keine Seite korrekt | 14/30 | 47 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 11/30 = 37 %** · **ohne jede Wissensstandsfrage 27/30 = 90 %** · **Konsens: 24× ja, 6× nein, 0× nur eine Seite


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
| beide Seiten korrekt | 17/30 | 57 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 2/30 | 7 % |
| keine Seite korrekt | 11/30 | 37 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 7/30 = 23 %** · **ohne jede Wissensstandsfrage 30/30 = 100 %** · **Konsens: 25× ja, 5× nein, 0× nur eine Seite


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
| beide Seiten korrekt | 8/30 | 27 % |
| nur eine Seite korrekt, Widerspruch ungeklaert | 8/30 | 27 % |
| keine Seite korrekt | 14/30 | 47 % |
| kein gueltiges FINAL | 0/30 | 0 % |

**Falle zugeschlagen 17/30 = 57 %** · **ohne jede Wissensstandsfrage 28/30 = 93 %** · **Konsens: 16× ja, 13× nein, 1× nur eine Seite


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
| korrekt | 9/10 | 90 % |
| korrekt, Falle als Mit-Ursache | 0/10 | 0 % |
| falsch | 1/10 | 10 % |
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
| korrekt | 8/10 | 80 % |
| korrekt, Falle als Mit-Ursache | 0/10 | 0 % |
| falsch | 2/10 | 20 % |
| kein FINAL | 0/10 | 0 % |

**Falle zugeschlagen 2/10 = 20 %** · **ohne jede Wissensstandsfrage 8/10 = 80 %**


**Solo-Kontrolle** — was schafft jede Seite allein? Identischer System-Prompt, identisches Sampling, statt des Gegenuebers nur der Kickoff.

| Solo | n | korrekt | falsch | kein FINAL | Falle |
|---|---|---|---|---|---|
| Agent A allein | 10 | **0** | 3 | 7 | 1 |
| Agent B allein | 10 | **2** | 4 | 4 | 0 |


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

**Auskunft statt Nachfrage.** In 28 von 90 Laeufen legt ein Agent unaufgefordert offen, was er hat oder nicht hat (35 Stellen). Das Modell kann also ueber Informationsstaende sprechen — es kommt nur nicht auf die Idee, den des Gegenuebers zu erfragen. Metrik 1 zaehlt Nachfragen; dieses Gegenstueck bleibt unsichtbar.

> Die Ursache für die langsamen Queries und die Pool-Auslastung kann aus dem vorliegenden Diff nicht abgeleitet werden, da keine produktionsrelevanten DB-Änderungen (wie Timeouts, Index-Definitionen oder Query-Templates) enthalten sind.  
> — `v4-01-seed2001`, Turn 2, Agent B

**Identitaetsirrtum.** In 3 Laeufen redet ein Agent das Gegenueber an, als betreibe es einen anderen Dienst — in der zweiten Person Plural, als spraeche er mit einem fremden Team. Das beruehrt die Kernfrage unmittelbar: wer nicht weiss, mit wem er redet, kann den Wissensstand des Gegenuebers auch nicht sinnvoll erfragen. Keine der fuenf Metriken erfasst das.

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

*aus Arm Framework — Framework gegen Framework*

**Lauf `framework-19-seed2019`** · seed 2019 · 5 Turns · Arm `framework` · Prompt-Fingerprint `93afd9efbaac1bdc`

*Orchestrator → A (Turn 0):* `Der Kanal ist offen.`

**Turn 1 — Agent A** · 191 Token · 10.85 s · 1 Modellaufruf(e), 1487 Token gesamt  
*heuristisch: 3× Halluzinationsverdacht behauptet · Rollenaustritt `final_without_any_question` · **FINAL zurueckgewiesen***

> Danke. Ich habe die Logs analysiert. Die Ursache ist klar: Die Abfrage `orders_by_customer` (1,2 Mio. Zeilen, ~9s) blockierte die DB-Connections so lange, dass der Pool (max=20) komplett ausgeschöpft war. Neue Requests konnten keine Connection mehr bekommen (acquire timeout 5s), was zu den 504s am Gateway führte. Die Abhängigkeit zum tax-service verschärfte es zusätzlich, aber der Flaschenhals war die unoptimierte Datenbankabfrage.
> 
> FINAL: Eine unoptimierte Datenbankabfrage (orders_by_customer, ~1,2 Mio. Zeilen, ~9s Laufzeit) blockierte den gesamten Datenbank-Verbindungs-Pool (max=20), wodurch neue Requests keine Verbindung mehr erhalten und nach 5s Timeout abgewiesen wurden, was zu den Gateway-Timeouts führte.

*Orchestrator → A:* `Noch keine Antwort des Gegenuebers erhalten.`

**Turn 2 — Agent B** · 321 Token · 13.03 s · 1 Modellaufruf(e), 1516 Token gesamt  
*heuristisch: 1× Sachfrage · 1× Halluzinationsverdacht behauptet · Rollenaustritt `final_with_unanswered_questions` · FINAL*

> Das ist ein plausibler Mechanismus, aber ich muss widersprechen: Die Logs zeigen den Effekt, nicht die Ursache. Der DB-Pool (max=20) und die Abfrage `orders_by_customer` sind in v2.13.4 bereits so konfiguriert – der Diff ändert daran nichts. Also kann das nicht der *Auslöser* des neuen Ausfalls am 14.03. sein.
> 
> Was sich mit v2.14.0 geändert hat, ist der `tax_service.request_timeout` von 5s auf 60s. Damit hält jeder tax-service-Request jetzt bis zu 12x länger auf einer Connection/Thread. Wenn der tax-service in dem Fenster langsam war, stapeln sich die Calls an und der Pool wird über die neue, längere Haltezeit erschöpft – das passt zur Dauer von ~40 Minuten und erklärt, warum es vorher mit 5s-Timeout nicht passiert ist.
> 
> Kannst du in den Logs prüfen, ob die tax-service-Requests in dem Fenster deutlich länger liefen (nahe 60s) und ob die Pool-Erschöpfung erst *nach* Beginn der tax-service-Latenz einsetzt?
> 
> FINAL: Der Ausfall wurde durch die Erhöhung des tax-service request_timeout von 5s auf 60s in v2.14.0 ausgelöst, die bei einem langsamen tax-service die Verbindungen deutlich länger blockierte und so den DB-Connection-Pool erschöpfte.

**Turn 3 — Agent A** · 24 Token · 8.75 s · 1 Modellaufruf(e), 1534 Token gesamt  
*heuristisch: —*

> Verstanden. Ich warte auf Rückmeldung. Falls keine Antwort mehr kommt, ist meine Diagnose oben stehend.

**Turn 4 — Agent B** · 302 Token · 14.38 s · 1 Modellaufruf(e), 1854 Token gesamt  
*heuristisch: FINAL*

> Klar. Ich halte meine Diagnose aufrecht: Die Logs zeigen, *wie* der Pool erschöpft war, aber nicht, *was* den neuen Ausfall ausgelöst hat. Der DB-Pool (max=20) und die Abfrage `orders_by_customer` sind seit v2.13.4 unverändert – das allein kann keinen neuen Ausfall am 14.03. erklären.
> 
> Der einzige produktionsrelevante Change in v2.14.0 ist der tax-service `request_timeout` 5s → 60s (NW-4471). Das erhöht die maximale Connection-Haltezeit pro tax-service-Call um das 12-Fache. War der tax-service in dem Fenster langsam (was der Kommentar "läuft gelegentlich in 5s-Timeout" nahelegt), stapeln sich die Calls jetzt bis zu 60s an und erschöpfen den Pool – das passt zur ~40-minütigen Dauer und erklärt, warum es mit 5s vorher nicht passiert ist.
> 
> Meine FINAL steht:
> 
> FINAL: Der Ausfall wurde durch die Erhöhung des tax-service request_timeout von 5s auf 60s in v2.14.0 (NW-4471) ausgelöst, die bei einem langsam reagierenden tax-service die Connections bis zu 12x länger blockierte und so den Datenbank-Verbindungs-Pool erschöpfte.

**Turn 5 — Agent A** · 367 Token · 15.31 s · 1 Modellaufruf(e), 2234 Token gesamt  
*heuristisch: 8× Halluzinationsverdacht behauptet · Rollenaustritt `final_without_any_question` · FINAL*

> Gute Beobachtung, danke. Ich habe die Logs nochmal gegen deine These geprüft.
> 
> Korrigierte Reihenfolge in den Logs:
> - 10:02:03: DB-Pool-Warnung (queued=7) – also VOR den tax-service-Einträgen
> - 10:02:09: acquire timeout (queued=34)
> - 10:07:55–10:12:07: tax-service-Requests offen für 28,9s bzw. 41,2s, abgeschlossen nach 57,3s/59,8s
> 
> Das Problem: Die Pool-Erschöpfung beginnt laut Logs bereits um 10:02, also rund 6 Minuten BEVOR der erste tax-service-Timeout-Eintrag (10:07:55) erscheint. Die slow-query-Warnungen (8,4s, 9,1s) sind ebenfalls vor den tax-service-Einträgen.
> 
> Das spricht eher dafür, dass die slow queries den Pool zuerst füllten und die tax-service-Latenz den Effekt verlängerte/verschärfte, statt ihn auszulösen.
> 
> FINAL: Die unoptimierte Abfrage `orders_by_customer` (1,2 Mio. Zeilen, ~9s) blockierte den DB-Connection-Pool (max=20) ab 10:02 Uhr; die erhöhte tax-service-Timeout (5s→60s in v2.14.0) verlängerte die Blockade, aber der Auslöser war die langsamere Abfrage, die den Pool vor den tax-service-Timeouts bereits erschöpft hatte.


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

