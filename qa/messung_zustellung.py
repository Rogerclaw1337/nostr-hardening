#!/usr/bin/env python3
"""Messung zu Punkt 1: Wie oft sagt ein Relais ja und liefert das Event danach nicht?

Erzeugt ein einzelnes kind-1-Event mit einem Wegwerfschlüssel, sendet es an alle
Relais der Liste und prüft nach einer Wartezeit per REQ, ob es noch da ist.
Schreibt das Ergebnis als JSON, damit es zitierbar bleibt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nostrhard.delivery import audit          # noqa: E402
from nostrhard.keys import load_or_create, note  # noqa: E402

RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://relay.ditto.pub",
    "wss://relay.dreamith.to",
    "wss://relay.snort.social",
    "wss://relay.tchncs.de",
    "wss://nostr.mom",
    "wss://relay.nostr.band",
    "wss://nostr-pub.wellorder.net",
]


async def _audit(relays, ev, settle, ok_timeout):
    from nostrhard.wire import PublishResult, publish_and_verify
    import asyncio as _a
    sem = _a.Semaphore(6)

    async def one(url):
        async with sem:
            try:
                return await publish_and_verify(url, ev, settle_seconds=settle, ok_timeout=ok_timeout, fetch_timeout=ok_timeout)
            except Exception as exc:  # noqa: BLE001
                return PublishResult(relay=url, note=f"{type(exc).__name__}: {exc}")

    results = await _a.gather(*(one(u) for u in relays))
    from nostrhard.delivery import AuditReport
    return AuditReport(event_id=ev["id"], results=list(results))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relais", nargs="*", default=RELAYS)
    ap.add_argument("--settle", type=float, default=4.0, help="Wartezeit zwischen Annahme und Nachschauen in Sekunden")
    ap.add_argument("--aus", default="/opt/data/nostr-hardening/qa/zustellung_messung.json")
    ap.add_argument("--texte", type=int, default=1, help="Anzahl unabhängiger Events")
    ap.add_argument("--ok-timeout", type=float, default=8.0, help="Wartezeit auf das OK in Sekunden")
    args = ap.parse_args()

    keys = load_or_create()
    print(f"Testpubkey: {keys.public_key().to_hex()}")
    runs = []
    for i in range(args.texte):
        text = f"delivery audit {uuid.uuid4().hex[:12]}"
        ev = note(text, keys)
        report = await _audit(args.relais, ev, args.settle, args.ok_timeout)
        print(f"\nEvent {i + 1}/{args.texte}: {ev['id'][:16]}…")
        for line in report.lines():
            print("  " + line)
        summary = report.summary()
        print(f"  Summe: {summary['accepted']}/{summary['relays']} angenommen, "
              f"{summary['retrievable']} abrufbar, {summary['false_success']} Fake-OK")
        runs.append({"event": ev, "summary": summary,
                     "results": [r.as_dict() for r in report.results]})

    out = {
        "zeit": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "settle_seconds": args.settle,
        "pubkey": keys.public_key().to_hex(),
        "laeufe": runs,
    }
    p = Path(args.aus)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ngeschrieben: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
