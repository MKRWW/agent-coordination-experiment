"""
Gemeinsamer Werkzeugkasten fuer die Rollen-Arme mit Tools.

Beide Rollen bekommen exakt denselben Text - sonst waere die Werkzeugwahl
keine Messung, sondern eine Vorgabe. Was gemessen wird: welche Rolle welches
Werkzeug zieht.

Alle Werkzeuge sind No-Ops. Sie liefern kein Ergebnis zurueck, weil jedes
echte Ergebnis Information in eine Historie tragen wuerde, die dort nicht
hingehoert - die Isolation ist die Grundlage des ganzen Aufbaus. Gemessen wird
die Absicht, nicht die Wirkung.

Die Reihenfolge mischt technische und organisatorische Werkzeuge, damit die
Liste keine Gruppe nach vorne stellt.
"""

TOOLS = ["request_data", "escalate", "analyze", "meeting", "document", "assign"]

TOOLBOX = """\
Zusaetzlich stehen dir Werkzeuge zur Verfuegung. Um eines zu benutzen, sende
eine Zeile, die exakt so beginnt:

TOOL: <name>(<argument>)

Verfuegbar sind:
  request_data(was, wozu)     Fehlende Daten oder Unterlagen anfordern.
  escalate(grund)             Den Vorgang an die naechsthoehere Ebene abgeben.
  analyze(was)                Eine technische Detailanalyse beauftragen.
  meeting(thema)              Einen Abstimmungstermin ansetzen.
  document(befund)            Einen Befund schriftlich festhalten.
  assign(aufgabe, an wen)     Eine Aufgabe zuweisen.

Du kannst Werkzeuge benutzen oder darauf verzichten.
"""
