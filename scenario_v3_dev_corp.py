"""
Rollen-Arm mit Werkzeugkasten UND organisationalem Kontext (dev).

Einzige Aenderung gegenueber scenario_v3_dev_tools: der Konzern-Rahmen aus
corpcontext.py ersetzt die knappe Rollenzeile. Werkzeugkasten, Daten, Ground
Truth, Falle und Loesungsgruppen bleiben unveraendert - damit ist der
Vergleich gegen die Werkzeug-Arme ohne Kontext direkt moeglich.
"""
from scenario_v3_dev_tools import *      # noqa: F401,F403
import scenario_v3_dev_tools as _tools
import scenario_v3_dev as _role
from corpcontext import FRAME, ROLE

CONTEXT = ROLE["dev"] + "\n\n" + FRAME

SCENARIO_ID = _tools.SCENARIO_ID + "-konzern"
SCENARIO_VERSION = _tools.SCENARIO_VERSION
COMMON_BRIEF = _tools.COMMON_BRIEF
SYSTEM_A = _tools.SYSTEM_A.replace(_role.ROLE, CONTEXT, 1)
SYSTEM_B = _tools.SYSTEM_B.replace(_role.ROLE, CONTEXT, 1)


def scenario_fingerprint():
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
