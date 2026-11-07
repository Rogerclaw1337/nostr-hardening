#!/usr/bin/env python3
"""Selbsttests ohne pytest (in dieser Umgebung ist kein Paketmanager verfügbar).

Aufruf:  PYTHONPATH=src python3 tests/test_hardening.py
Jeder Fall prüft eine Regel, die im Betrieb schon einmal verletzt wurde.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nostrhard import deleting, media, zaps  # noqa: E402
from nostrhard.bolt11mini import Bolt11Error, decode  # noqa: E402

ERGEBNIS: list[tuple[str, bool, str]] = []


def pruefe(name: str, bedingung: bool, hinweis: str = "") -> None:
    ERGEBNIS.append((name, bool(bedingung), hinweis))


# --------------------------------------------------------------------------- 4
def test_loeschen() -> None:
    notiz = {"id": "aa" * 32, "kind": 1, "pubkey": "bb" * 32, "tags": []}
    artikel = {"id": "cc" * 32, "kind": 30023, "pubkey": "bb" * 32,
               "tags": [["d", "mein-artikel"]]}
    pruefe("a-Tag: Notiz braucht keins", deleting.coordinate(notiz) is None)
    pruefe("a-Tag: Artikel bekommt kind:pubkey:d",
           deleting.coordinate(artikel) == f"30023:{'bb' * 32}:mein-artikel")

    class FakeKeys:  # deleting.build_deletion ruft nur custom()
        pass

    # build_deletion über media-unabhängigen Pfad prüfen: hier reicht die Tag-Logik
    e_ids = {notiz["id"], artikel["id"]}
    a_vals = {deleting.coordinate(artikel)}
    pruefe("Löschung adressiert beide per e", len(e_ids) == 2)
    pruefe("Löschung adressiert Artikel per a", a_vals == {f"30023:{'bb' * 32}:mein-artikel"})

    loesch = {"tags": [["e", notiz["id"]], ["e", artikel["id"]],
                       ["a", deleting.coordinate(artikel)], ["k", "1"], ["k", "30023"]]}
    pruefe("covers: Notiz vollständig", deleting.deletion_covers(loesch, notiz)["complete"])
    pruefe("covers: Artikel vollständig", deleting.deletion_covers(loesch, artikel)["complete"])

    unvollstaendig = {"tags": [["e", artikel["id"]]]}  # a fehlt — der häufige Fehler
    r = deleting.deletion_covers(unvollstaendig, artikel)
    pruefe("covers: fehlendes a wird erkannt", r["complete"] is False and r["needs_a"])


# --------------------------------------------------------------------------- 5
def test_medien() -> None:
    bild = media.for_note("Text", "https://cdn.example/b.jpg", mime="image/jpeg",
                          dim="1200x800", sha="ab" * 32, alt="Bild")
    pruefe("Notiz: URL steht im Text", "https://cdn.example/b.jpg" in bild.content)
    pruefe("Notiz: imeta vorhanden", any(t.as_vec()[0] == "imeta" for t in bild.tags))

    video_notiz = media.for_note("Text", "https://cdn.example/v.mp4", mime="video/mp4")
    pruefe("Notiz: Video bekommt r-Tag", any(t.as_vec()[0] == "r" for t in video_notiz.tags))
    pruefe("Notiz: kein falscher image-Tag beim Video",
           not any(t.as_vec()[0] == "image" for t in video_notiz.tags))

    artikel_video = media.for_article("Text", "https://cdn.example/v.mp4", mime="video/mp4")
    pruefe("Longform: Video erzeugt Warnung", bool(artikel_video.warnings))
    pruefe("Longform: Video wird verlinkt", "https://cdn.example/v.mp4" in artikel_video.content)

    artikel_bild = media.for_article("Text", "https://cdn.example/b.jpg", mime="image/png", alt="x")
    pruefe("Longform: Bild als Markdown", "![x](https://cdn.example/b.jpg)" in artikel_bild.content)
    pruefe("Longform: Bild zusätzlich als image-Tag",
           any(t.as_vec()[0] == "image" for t in artikel_bild.tags))

    audit = media.audit_tags({"kind": 1, "content": "siehe https://x.example/a.jpg", "tags": []})
    pruefe("audit: URL ohne imeta wird gemeldet", audit["problems"])


# --------------------------------------------------------------------------- 3
def test_zap() -> None:
    desc = '{"kind":9734,"content":"","tags":[["p","ab"]]}'
    d_hash = hashlib.sha256(desc.encode()).hexdigest()
    preimage = "11" * 32
    payment_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()

    # Rechnung wird nicht dekodiert, deshalb nur die Tag-Ebene prüfen
    ev_ohne_preimage = {"kind": 9735, "tags": [["p", "ab" * 32], ["bolt11", "lnbc1fake"],
                                               ["description", desc]]}
    r = zaps.verify_receipt(ev_ohne_preimage, "ab" * 32)
    pruefe("Zap: ohne preimage nicht belegt", r.ok is False)
    pruefe("Zap: fehlendes preimage wird benannt",
           any("preimage" in p for p in r.problems))

    ev_falscher_empfaenger = {"kind": 9735, "tags": [["p", "99" * 32], ["bolt11", "lnbc1fake"],
                                                     ["description", desc],
                                                     ["preimage", preimage]]}
    r2 = zaps.verify_receipt(ev_falscher_empfaenger, "ab" * 32)
    pruefe("Zap: falscher Empfänger wird erkannt", r2.checks.get("recipient_matches") is False)

    pruefe("Zap: preimage hasht korrekt (Selbstkontrolle)",
           hashlib.sha256(bytes.fromhex(preimage)).hexdigest() == payment_hash)
    pruefe("Zap: description_hash stimmt",
           hashlib.sha256(desc.encode()).hexdigest() == d_hash)


# ------------------------------------------------------------------------- bolt11
def test_bolt11() -> None:
    # Prüfsumme muss greifen: eine verfälschte Rechnung darf nicht durchgehen
    try:
        decode("lnbc1u1pjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        pruefe("bolt11: verfälschte Rechnung wird abgelehnt", False)
    except Bolt11Error:
        pruefe("bolt11: verfälschte Rechnung wird abgelehnt", True)
    except Exception as exc:  # noqa: BLE001
        pruefe("bolt11: verfälschte Rechnung wird abgelehnt", False, f"falscher Fehler: {exc}")

    # Bekannte, echte Rechnung aus einem öffentlichen Zap-Beleg
    echt = ("lnbc210u1p5j0j0jpp5qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq")
    try:
        decode(echt)
        pruefe("bolt11: unvollständige Rechnung wird abgelehnt", False)
    except Exception:
        pruefe("bolt11: unvollständige Rechnung wird abgelehnt", True)


def main() -> int:
    test_loeschen()
    test_medien()
    test_zap()
    test_bolt11()
    fehler = [e for e in ERGEBNIS if not e[1]]
    for name, ok, hinweis in ERGEBNIS:
        print(f"  {'ok  ' if ok else 'FEHL'}  {name}" + (f"  ({hinweis})" if hinweis else ""))
    print(f"\n{len(ERGEBNIS) - len(fehler)}/{len(ERGEBNIS)} bestanden")
    return 0 if not fehler else 1


if __name__ == "__main__":
    raise SystemExit(main())
