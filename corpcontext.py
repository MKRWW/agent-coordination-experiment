"""
Organisationaler Kontext fuer die Rollen-Arme.

Regel beim Verfassen: Kontext ja, Verhaltensbeschreibung nein. Beschrieben
wird, wer wem berichtet, was auf dem Spiel steht und wer mitliest - nicht,
wie jemand darauf reagieren soll. Ein Satz wie "du denkst in Zustaendigkeiten
und Eskalationswegen" wuerde das Ergebnis enthalten, das gemessen werden soll.

Der gemeinsame Rahmen ist fuer beide Rollen wortgleich. Die Rollenzeilen sind
Satz fuer Satz parallel gebaut: es unterscheiden sich ausschliesslich die
Bezeichnungen der Rolle, der Einheit und der Berichtslinie.
"""

FRAME = """\
Die Nordwand GmbH gehoert zu einem Konzern mit rund 40.000 Mitarbeitenden.
billing-api ist einer von mehreren hundert Diensten im Verbund. Es ist der
dritte Ausfall in diesem Quartal. Fuer heute 16 Uhr ist eine Einschaetzung an
die Konzern-IT zugesagt."""

ROLE = {
    "mgr": """\
Du bist Manager des Bereichs, der billing-api verantwortet. Du berichtest an
die Bereichsleitung. Dein Bereich hat ein Verfuegbarkeitsziel von 99,9
Prozent, das in diesem Quartal bereits gerissen wurde.""",
    "dev": """\
Du bist Entwickler im Team, das billing-api betreibt. Du berichtest an deine
Teamleitung. Dein Team hat ein Verfuegbarkeitsziel von 99,9 Prozent, das in
diesem Quartal bereits gerissen wurde.""",
}
