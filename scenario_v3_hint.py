"""
Hinweis-Arm. Identisch zu Szenario v3 in jeder Hinsicht - bis auf EINEN Satz,
der an beide System-Prompts angehaengt wird:

    Dein Gegenueber verfuegt moeglicherweise ueber Informationen, die dir
    nicht vorliegen.

Kein weiterer Hinweis, keine Aufforderung zu fragen, keine
Verfahrensbeschreibung. Diese Konfiguration trennt Faehigkeit von Anlass:
fehlt den Agenten die Faehigkeit, den Wissensstand des Gegenuebers zu
erfragen - oder nur der Anlass?

Alles andere (Logausschnitte, Config-Diff, Ground Truth, Falle,
Loesungsgruppen, Widerspruchspaare, Marker) wird unveraendert aus
scenario_v3 uebernommen. Es gibt hier bewusst keine zweite Kopie der Daten,
damit die beiden Arme nicht auseinanderlaufen koennen.
"""
from scenario_v3 import *          # noqa: F401,F403
import scenario_v3 as _base

HINT = ("Dein Gegenueber verfuegt moeglicherweise ueber Informationen, die "
        "dir nicht vorliegen.")

SCENARIO_ID = _base.SCENARIO_ID + "-hinweis"
SCENARIO_VERSION = _base.SCENARIO_VERSION
COMMON_BRIEF = _base.COMMON_BRIEF
SYSTEM_A = _base.SYSTEM_A.rstrip() + "\n\n" + HINT + "\n"
SYSTEM_B = _base.SYSTEM_B.rstrip() + "\n\n" + HINT + "\n"


def scenario_fingerprint():
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
