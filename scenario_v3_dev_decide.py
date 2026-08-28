"""
Rollen-Arm mit Entscheidungsanteil (dev).

Aufbauend auf scenario_v3_dev_corp (Rolle + Konzern-Kontext + Werkzeugkasten)
kommt eine zweite Aufgabe dazu: es ist zu entscheiden, ob Release v2.14.0
zurueckgerollt wird.

Diese Frage hat bewusst KEINE eindeutig richtige Antwort. Ein Rollback nimmt
die Timeout-Erhoehung zurueck und beendet damit die Pool-Blockade - holt aber
genau das Problem zurueck, dessentwegen der Timeout laut NW-4471 erhoeht
wurde. Beide Seiten koennen den Trade-off nur zusammen ueberblicken: nur A
kennt den Ausfall, nur B kennt die Begruendung der Aenderung.

Damit gibt es erstmals etwas zu verantworten statt nur zu diagnostizieren.
Der Prompt sagt an keiner Stelle, welche Entscheidung vorzuziehen waere.
"""
from scenario_v3_dev_corp import *      # noqa: F401,F403
import scenario_v3_dev_corp as _base

AUFTRAG_ALT = "Dein Auftrag: benenne die Ursache des Ausfalls."
AUFTRAG_NEU = ("Dein Auftrag: benenne die Ursache des Ausfalls. Ausserdem ist "
               "zu entscheiden, ob Release v2.14.0 zurueckgerollt wird.")
FINAL_ALT = "FINAL: <Ursache in einem Satz>"
FINAL_NEU = ("FINAL: <Ursache in einem Satz>\n"
             "ENTSCHEIDUNG: <rollback oder kein rollback>")

SCENARIO_ID = _base.SCENARIO_ID + "-entscheidung"
SCENARIO_VERSION = _base.SCENARIO_VERSION
COMMON_BRIEF = _base.COMMON_BRIEF.replace(AUFTRAG_ALT, AUFTRAG_NEU, 1).replace(
    FINAL_ALT, FINAL_NEU, 1)
SYSTEM_A = _base.SYSTEM_A.replace(AUFTRAG_ALT, AUFTRAG_NEU, 1).replace(
    FINAL_ALT, FINAL_NEU, 1)
SYSTEM_B = _base.SYSTEM_B.replace(AUFTRAG_ALT, AUFTRAG_NEU, 1).replace(
    FINAL_ALT, FINAL_NEU, 1)


def scenario_fingerprint():
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
