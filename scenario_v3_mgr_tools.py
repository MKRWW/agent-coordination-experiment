"""
Rollen-Arm mit Werkzeugkasten, abgeleitet von scenario_v3_mgr.

Einzige Aenderung gegenueber scenario_v3_mgr: der gemeinsame Werkzeugkasten aus
toolbox.py wird an beide Sets angehaengt. Er ist fuer Entwickler- und
Manager-Arm wortgleich - gemessen wird, welche Rolle welches Werkzeug zieht.
"""
from scenario_v3_mgr import *              # noqa: F401,F403
import scenario_v3_mgr as _base
from toolbox import TOOLBOX

SCENARIO_ID = _base.SCENARIO_ID + "-tools"
SCENARIO_VERSION = _base.SCENARIO_VERSION
COMMON_BRIEF = _base.COMMON_BRIEF
SYSTEM_A = _base.SYSTEM_A.rstrip() + "\n\n" + TOOLBOX
SYSTEM_B = _base.SYSTEM_B.rstrip() + "\n\n" + TOOLBOX


def scenario_fingerprint():
    import hashlib
    h = hashlib.sha256()
    for part in (SCENARIO_ID, str(SCENARIO_VERSION), COMMON_BRIEF, SYSTEM_A, SYSTEM_B):
        h.update(part.encode())
    return h.hexdigest()[:16]
