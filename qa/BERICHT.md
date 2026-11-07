# QA-Bericht — fünf Punkte, gemessen am 7. November 2026

Alles hier ist mit den Skripten in diesem Ordner reproduzierbar. Rohdaten liegen
daneben als JSON. Wo eine Messung unsicher ist, steht das dabei — nicht als
Fußnote, sondern im Satz.

---

## 1 · Zustellung

**Frage:** Sagt ein Relais „ja" und hat das Event danach trotzdem nicht?

**Aufbau:** ein kind-1-Event pro Lauf, Wegwerfschlüssel
(`dbe5a4ea…a414d3`), zehn öffentliche Relais, `OK` mit 15 s Frist, 6 s Wartezeit,
danach `REQ {"ids":[…]}`. Drei unabhängige Events.

| Relais | angenommen | abrufbar |
|---|---|---|
| relay.primal.net | ja | ja |
| nos.lol | ja | ja |
| relay.ditto.pub | ja (`duplicate:`) | ja |
| relay.snort.social | ja | ja |
| nostr.mom | ja | **nein** (1 von 3 Läufen; Minuten später erneut geprüft: weiterhin weg) |
| relay.damus.io | keine Antwort (1 von 3: Antwort und Auslieferung) |
| relay.dreamith.to | keine Antwort |
| relay.nostr.band | keine Antwort |
| nostr-pub.wellorder.net | keine Antwort |
| relay.tchncs.de | `false` — keine Schreibrechte für diesen Schlüssel |

**Ergebnis:** 5–6 von 10 angenommen, 4–5 antworten gar nicht, **1 Fake-OK**
nachgewiesen. Wer auf fünf Relais veröffentlicht und „success" liest, hat real
zwei bis vier Kopien.

**Grenze der Messung:** „keine Antwort" ist kein Beweis für Ablehnung — es kann
auch an Cloudflare, Rate-Limits oder einem langsamen Relais liegen. Deshalb steht
in der Tabelle „keine Antwort" und nicht „abgelehnt".

---

## 2 · Aufbewahrung

**Frage:** Wie lange hält ein Relais meine Daten — und sagt es das?

| Relais | Retention-Feld in NIP-11 | älteste Stichprobe |
|---|---|---|
| relay.primal.net | keins | 730 Tage (bei 5 Jahren nichts) |
| nos.lol | keins | 730 Tage |
| relay.ditto.pub | keins | 1825 Tage |
| nostr.wine | keins | 730–1825 Tage (zwei Läufe, schwankend) |
| nostr.mom | keins | 90 Tage |
| relay.damus.io | keins | widersprüchlich: Treffer bei 7 Tagen, nichts im 30-Tage-Fenster |
| relay.snort.social | keins | nichts älter als ~7 Tage |
| relay.nostr.band | keins | gar keine kind-1-Antwort |

**Ergebnis:** **Kein einziges der acht Relais deklariert eine Aufbewahrungsfrist.**
Und die Messung selbst ist unzuverlässig: Damus liefert je nach Filterform
unterschiedliche Antworten, weil `since`/`until` Implementierungssache sind.

**Konsequenz:** Ein Autor kann heute nicht wissen, ob sein Artikel in zwei Jahren
noch existiert. Der einzige belastbare Weg ist, das Ereignis selbst zu verwahren
und die Relais als Fundstelle zu behandeln.

---

## 3 · Zap-Belege

**Frage:** Wie viele öffentliche Zap-Belege beweisen tatsächlich eine Zahlung?

**Aufbau:** je 50 kind-9735 von vier Relais, entdoppelt auf **112** Belege. Jede
Rechnung wurde mit einem eigenen BOLT11-Leser dekodiert (Prüfsumme verifiziert),
dann `sha256(preimage)` gegen `payment_hash` geprüft und `sha256(description)`
gegen `description_hash`.

| Befund | Anzahl | Anteil |
|---|---|---|
| Zahlung kryptografisch belegt | 63 | 56 % |
| nicht belegbar | 49 | 44 % |
| Zweck gebunden | 70 | 63 % |
| keine `bolt11` im Beleg | 10 | 9 % |
| kein `description`-Tag | 9 | 8 % |

Belegte Summe: **15.215 Sats**, Median **21 Sats**, größter Einzelbeleg
**10.000 Sats**.

**Selbstkontrolle des Lesers:** Wäre die Dekodierung falsch, würde das `preimage`
nie auf den gelesenen `payment_hash` passen. Bei 63 von 112 passt es — und weil
derselbe Code die übrigen 49 als „kein preimage" ausweist, ist das kein
Parserfehler, sondern ein Merkmal der Belege.

**Fehler, der dabei auffiel (und behoben wurde):** Die erste Fassung des Lesers
rechnete mit falschen Einheiten (`u` = 100.000 msat, nicht 100.000.000), wodurch
alle Beträge um Faktor 1000 zu hoch waren — Median 21.000 statt 21 Sats. Aufgefallen
ist es am Median, nicht am Code. Die Zahlen oben stammen aus der korrigierten
Fassung.

---

## 4 · Löschen

**Frage:** Ist ein gelöschtes Event danach weg?

**Aufbau:** Ziel posten (kind 1 und kind 30023), Abrufbarkeit bestätigen,
NIP-09-Löschung mit `e`, `a` und `k` posten, warten, erneut prüfen.

| Fall | vorher abrufbar | nachher abrufbar |
|---|---|---|
| Notiz (kind 1) | 2 von 4 Relais | **1** — relay.primal.net lieferte sie weiter |
| Longform (kind 30023) | 3 von 4 Relais | **1** — relay.primal.net lieferte es weiter |

Minuten später erneut geprüft: nos.lol und nostr.mom hatten gelöscht,
primal.net lieferte beide Ziele weiterhin per ID aus.

**Ergebnis:** Löschen funktioniert dort, wo das Event lag — außer auf einem von
drei Relais. Der Autor erfährt davon nichts.

---

## 5 · Medien

**Frage:** Warum erscheint ein Video im Artikel nicht, in der Notiz aber schon?

*Diese Messung stammt vom 5. Oktober 2026 (DOM-geprüft in Primal) und wurde für
diesen Bericht nicht wiederholt. Alles andere hier ist vom 7. November.*

**Aufbau:** sechs Longform-Varianten mit derselben MP4 — nackte URL,
Markdown-Bild, `imeta` (NIP-92), `image`-Tag als Cover, HTML `<video>`,
`/a/<naddr>`-Route. Dieselbe URL zusätzlich in einer Notiz (kind 1).

**Ergebnis:** In kind 30023 erzeugte **keine** Variante einen Player; die Notiz
zeigte sofort einen. Die Darstellung hängt am Event-Typ, nicht an den Tags.

**Konsequenz im Code:** `media.for_article()` verweigert die Illusion — für Video
gibt es einen Link plus Warnung, dass kein Player entsteht, und den Hinweis, eine
Begleitnotiz zu veröffentlichen. `media.for_note()` legt die URL in den Text *und*
in `imeta`, weil Clients unterschiedlich lesen.

---

## Selbsttests

`tests/test_hardening.py` — 23 Prüfungen, alle bestanden: `a`-Tag-Logik,
`deletion_covers`, Medien-Tags (inklusive der Regel „Video nie als `image`"),
Zap-Prüfung ohne `preimage`, falscher Empfänger, BOLT11-Prüfsumme.

## Was hier nicht steht

* Keine Aussage über Relais, die geschwiegen haben — außer dass sie schwiegen.
* Keine Verallgemeinerung der Stichprobe: 112 Belege sind eine Momentaufnahme,
  keine Erhebung über das Netz.
* Keine Behauptung, ein Vorschlag sei „richtig". Die Vorschläge sind begründete
  Entwürfe; die Entscheidung liegt bei den Maintainern.
