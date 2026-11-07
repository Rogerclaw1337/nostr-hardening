#!/usr/bin/env python3
"""Messung zu Punkt 2: was deklarieren Relais, und wie weit zurück liefern sie?

Die zweite Frage ist nur als Untergrenze zu haben: gefragt wird stufenweise
"gibt es überhaupt noch ein Event dieses Alters?" — ohne `since`, weil Relais
`since` unterschiedlich auslegen (siehe Bericht).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nostrhard.retention import measure_horizon  # noqa: E402

RELAYS = [
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay.damus.io",
    "wss://nostr.mom",
    "wss://relay.ditto.pub",
    "wss://relay.nostr.band",
    "wss://nostr.wine",
    "wss://relay.snort.social",
]


async def main() -> int:
    aus = []
    for r in RELAYS:
        h = await measure_horizon(r, kind=1)
        d = h.declared or {}
        print(f"{r:32s} aeltester Treffer: {str(h.oldest_found_days) + ' Tage' if h.oldest_found_days else 'nichts':14s} "
              f"Stufen={h.steps} retention={d.get('retention')} software={str(d.get('software'))[:40]}")
        aus.append(h.summary())
    p = Path(__file__).with_name("retention_messung.json")
    p.write_text(json.dumps({"zeit": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "relais": aus},
                            indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\ngeschrieben: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
