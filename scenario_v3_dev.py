"""
Rollen-Arm: Entwickler.

Identisch zu Szenario v3 - bis auf EINE vorangestellte Zeile:

    Du bist Entwickler im Team, das billing-api betreibt.

Die Baseline enthaelt ueberhaupt keine Rollenzuweisung. Deshalb gibt es zwei
Rollen-Arme statt einem: Wer nur den Manager-Arm gegen die rollenlose Baseline
stellt, aendert zwei Dinge gleichzeitig (Rolle vorhanden + Rolle ist Manager)
und kann den Effekt hinterher nicht zuordnen. Mit beiden Armen variiert
zwischen ihnen genau ein Wort.

Alles andere - Logausschnitte, Config-Diff, Ground Truth, Falle,
Loesungsgruppen, Marker - wird unveraendert aus scenario_v3 uebernommen.
"""
from scenario_v3 import *          # noqa: F401,F403
import scenario_v3 as _base

ROLE = "Du bist Entwickler im Team, das billing-api betreibt."

SCENARIO_ID = _base.SCENARIO_ID + "-rolle-entwickler"
SCENARIO_VERSION = _base.SCENARIO_VERSION
COMMON_BRIEF = ROLE + "\n\n" + _base.COMMON_BRIEF
SYSTEM_A = _base.SYSTEM_A.replace(_base.COMMON_BRIEF, COMMON_BRIEF, 1)
SYSTEM_B = _base.SYSTEM_B.replace(_base.COMMON_BRIEF, COMMON_BRIEF, 1)


def scenario_fingerprint():
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
