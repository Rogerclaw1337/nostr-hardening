# Nostr-Härtung — fünf Punkte, gemessen und angefasst

Dieses Verzeichnis ist keine Meinungssammlung. Es sind fünf Schwachstellen des
Protokolls, jeweils mit einer Messung, einem Vorschlag, lauffähigem Code und
Selbsttests. Alles hier läuft ohne Fremdpakete (kein pip, kein uv in dieser
Umgebung) — nur `websockets` und `nostr_sdk` aus dem vorhandenen Venv.

## Die fünf Punkte

| # | Problem | Messung | Vorschlag | Code |
|---|---|---|---|---|
| 1 | `OK … true` heißt angenommen, nicht gespeichert | 10 Relais, 3 Läufe: 1 Fake-OK, 4–5 stumm | `persisted:` Prefix + `PROOF` + Quorum | `delivery.py` |
| 2 | Relais deklarieren keine Aufbewahrung | 0 von 8 Relais nennen eine Frist | `retention`-Block in NIP-11 + Messverfahren | `retention.py` |
| 3 | Zap-Belege belegen oft nichts | 112 Belege: 42 % nicht nachweisbar | „bezahlt" und „zweckgebunden" trennen | `zaps.py`, `bolt11mini.py` |
| 4 | Löschen wirkt nicht überall | Notiz + Artikel: je 1 Relais behält sie | `a`-Tag Pflicht + Nachprüfung | `deleting.py` |
| 5 | Medien hängen am Event-Typ | Longform: 6 Varianten, kein Player | ein Medienobjekt, `content-type`, Warnung | `media.py` |

Die ausführlichen Vorschläge liegen in `proposals/`, jede Datei nennt die
bestehenden GitHub-Threads, an die sie anschließt (nicht Duplikate, sondern
Fortsetzungen: #2496, #2314, #1902, #556, #2099, #938, primal#233).

## Benutzung als Werkzeug

Die fünf Punkte sind auch als Kommandozeile nutzbar — das ist der Teil, der im Alltag
zählt:

```bash
export PYTHONPATH=/opt/data/nostr-hardening/src
PY=/opt/data/nd2/bin/python

# Wo liegt dieses Event noch? (beantwortet den Fake-OK-Fall)
$PY -m nostrhard audit <event-id>

# Was deklariert ein Relais, wie weit zurück liefert es?
$PY -m nostrhard relay wss://nos.lol

# Text senden und Zustellung prüfen
$PY -m nostrhard publish text.txt --quorum 2

# Zap-Belege prüfen
$PY -m nostrhard zap --stichprobe 50

# Medien-Tags bauen (Notiz oder Langform)
$PY -m nostrhard media https://beispiel/video.mp4 --langform
```

Beispielausgabe von `audit` zu einem Event, bei dem ein Relais `OK true` gab und es
danach nie auslieferte:

```
fehlt  wss://nostr.mom
da     wss://nos.lol
da     wss://relay.primal.net
2 von 3 Relais liefern das Event.
```

## Benutzung als Bibliothek

```bash
export PYTHONPATH=/opt/data/nostr-hardening/src
PY=/opt/data/nd2/bin/python

# Selbsttests (23 Prüfungen)
$PY tests/test_hardening.py

# Zustellung messen (schreibt qa/zustellung_messung2.json)
$PY qa/messung_zustellung.py --settle 6 --ok-timeout 15 --texte 3

# Aufbewahrungshorizont stichprobenartig bestimmen
$PY qa/messung_retention.py

# Zap-Belege prüfen
$PY qa/messung_zaps.py

# Löschen testen (postet echte Test-Events mit Wegwerfschlüssel)
$PY qa/messung_loeschen.py
```

Als Bibliothek:

```python
from nostrhard.delivery import publish_verified
res = await publish_verified(relays, event, quorum=2)
if not res.ok:
    print("nicht bestätigt auf:", res.failed)
```

## Was hier bewusst fehlt

* **Keine NIP-Nummern vergeben.** Das machen die Maintainer. Die Entwürfe nennen
  sich „Proposal", nicht „NIP-100".
* **Kein PR gegen fremde Repos.** Das Einreichen ist eine Entscheidung für den
  Nutzer, nicht für den Agenten.
* **Keine Aussage über Relais, die schweigen.** „Keine Antwort" wird als solches
  berichtet und nicht als Ablehnung gedeutet.

## Struktur

```
proposals/        fünf Entwürfe, englisch (einreichbar)
src/nostrhard/    Bibliothek: wire, delivery, retention, zaps, deleting, media, bolt11mini
qa/               Messskripte + Rohdaten der Messungen
tests/            Selbsttests ohne pytest
qa/BERICHT.md     Zusammenfassung aller Messungen mit Grenzen
```
