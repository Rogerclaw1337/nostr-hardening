"""Kommandozeile: die fünf Punkte als anwendbare Werkzeuge.

    python -m nostrhard publish datei.txt --quorum 2
    python -m nostrhard audit <event-id>
    python -m nostrhard relay wss://nos.lol
    python -m nostrhard zap --stichprobe 50
    python -m nostrhard media https://beispiel/video.mp4 --langform

Jeder Befehl gibt aus, was er tatsächlich geprüft hat — und was nicht.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import deleting, media, zaps
from .retention import measure_horizon
from .wire import fetch_events, publish_and_verify

STANDARD_RELAIS = [
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay.ditto.pub",
    "wss://nostr.mom",
    "wss://relay.damus.io",
]


def _relais(arg: list[str] | None) -> list[str]:
    return arg or STANDARD_RELAIS


async def cmd_audit(args) -> int:
    eid = args.event_id
    print(f"Prüfe, wer {eid[:16]}… noch ausliefert:\n")
    haben, nicht = [], []
    for url in _relais(args.relais):
        got = await fetch_events(url, [{"ids": [eid]}], timeout=args.timeout, limit_events=1)
        (haben if got else nicht).append(url)
        print(f"  {'da    ' if got else 'fehlt '} {url}")
    print(f"\n{len(haben)} von {len(haben) + len(nicht)} Relais liefern das Event.")
    if nicht:
        print("Ohne Kopie: " + ", ".join(nicht))
    return 0 if haben else 1


async def cmd_relay(args) -> int:
    h = await measure_horizon(args.url, kind=args.kind)
    d = h.declared or {}
    print(f"Relais:      {args.url}")
    print(f"Software:    {d.get('software')}")
    print(f"Retention:   {d.get('retention') or 'nicht deklariert'}")
    print(f"Schreiben:   {'eingeschränkt' if d.get('restricted_writes') else 'offen/unbekannt'}")
    print(f"Auth:        {'nötig' if d.get('auth_required') else 'nicht verlangt'}")
    print(f"Ältester Fund (kind {args.kind}): "
          f"{str(h.oldest_found_days) + ' Tage' if h.oldest_found_days else 'nichts gefunden'}")
    print(f"Stufen:      {h.steps}")
    return 0


async def cmd_publish(args) -> int:
    from .keys import load_or_create, note

    text = Path(args.datei).read_text(encoding="utf-8")
    keys = load_or_create(args.schluessel) if args.schluessel else load_or_create()
    ev = note(text, keys)
    print(f"Event: {ev['id']}\nSende an {len(_relais(args.relais))} Relais, Quorum {args.quorum} …\n")
    for url in _relais(args.relais):
        r = await publish_and_verify(url, ev, settle_seconds=args.settle)
        flag = "FAKE-OK" if r.is_false_success else ("ok" if r.retrievable else ("abgelehnt" if r.accepted is False else "stumm"))
        print(f"  {flag:9s} {url:32s} {r.message}")
    return 0


async def cmd_zap(args) -> int:
    evs = []
    for url in _relais(args.relais):
        got = await fetch_events(url, [{"kinds": [9735], "limit": args.stichprobe}],
                                 timeout=15, limit_events=args.stichprobe)
        evs.extend(got)
    seen, uniq = set(), []
    for e in evs:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        uniq.append(e)
    t = zaps.tally(uniq)
    print(f"Belege: {t['belege']} | Zahlung belegt: {t['zahlung_belegt']} | "
          f"nicht belegt: {t['zahlung_nicht_belegt']} | Zweck gebunden: {t['zweck_gebunden']}")
    print(f"Belegte Summe: {t['sats_belegt']} Sats")
    return 0


def cmd_media(args) -> int:
    plan = (media.for_article if args.langform else media.for_note)(
        args.text or "Beispieltext", args.url, mime=args.mime, alt=args.alt)
    print("--- Inhalt ---")
    print(plan.content)
    print("\n--- Tags ---")
    for t in plan.as_dict()["tags"]:
        print("  " + " | ".join(t))
    if plan.warnings:
        print("\n--- Hinweise ---")
        for w in plan.warnings:
            print("  ! " + w)
    return 0


def cmd_delete(args) -> int:
    print("Zum Löschen wird das Zielevent benötigt (JSON mit id, kind, pubkey, tags).")
    print("Beispiel:")
    print('  python -m nostrhard delete ziel.json')
    if args.datei:
        ziel = json.loads(Path(args.datei).read_text(encoding="utf-8"))
        print(f"\nZiel: kind {ziel.get('kind')}  id {str(ziel.get('id'))[:16]}…")
        print(f"Koordinate: {deleting.coordinate(ziel) or 'nicht nötig (kein 30000–39999)'}")
        loesch = {"tags": [["e", ziel["id"]]] + ([["a", deleting.coordinate(ziel)]] if deleting.coordinate(ziel) else [])}
        print(f"Prüfung: {deleting.deletion_covers(loesch, ziel)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nostrhard", description="Nostr-Härtung: fünf Prüfwerkzeuge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="Wo liegt dieses Event noch?")
    a.add_argument("event_id")
    a.add_argument("--relais", nargs="*")
    a.add_argument("--timeout", type=float, default=8.0)
    a.set_defaults(fn=lambda args: cmd_audit(args))

    r = sub.add_parser("relay", help="NIP-11 und Aufbewahrung eines Relais")
    r.add_argument("url")
    r.add_argument("--kind", type=int, default=1)
    r.set_defaults(fn=lambda args: cmd_relay(args))

    p = sub.add_parser("publish", help="Text als Notiz senden und Zustellung prüfen")
    p.add_argument("datei")
    p.add_argument("--relais", nargs="*")
    p.add_argument("--quorum", type=int, default=2)
    p.add_argument("--settle", type=float, default=4.0)
    p.add_argument("--schluessel", default=None)
    p.set_defaults(fn=lambda args: cmd_publish(args))

    z = sub.add_parser("zap", help="Zap-Belege prüfen")
    z.add_argument("--relais", nargs="*")
    z.add_argument("--stichprobe", type=int, default=25)
    z.set_defaults(fn=lambda args: cmd_zap(args))

    m = sub.add_parser("media", help="Medien-Tags für Notiz oder Langform bauen")
    m.add_argument("url")
    m.add_argument("--langform", action="store_true")
    m.add_argument("--mime", default=None)
    m.add_argument("--alt", default=None)
    m.add_argument("--text", default=None)
    m.set_defaults(fn=cmd_media)

    d = sub.add_parser("delete", help="Löschung prüfen (a-Tag)")
    d.add_argument("datei", nargs="?")
    d.set_defaults(fn=cmd_delete)

    args = ap.parse_args(argv)
    result = args.fn(args)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return result


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
