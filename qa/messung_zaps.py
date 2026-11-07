#!/usr/bin/env python3
"""Messung zu Punkt 3: wie viele öffentliche Zap-Belege sind wirklich belegt?

Zieht eine Stichprobe kind-9735 von mehreren Relais, entdoppelt, prüft jeden
Beleg: Zahlung (preimage -> payment_hash) und Zweck (description -> description_hash).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nostrhard import zaps                              # noqa: E402
from nostrhard.wire import fetch_events                 # noqa: E402

RELAYS = ["wss://relay.primal.net", "wss://nos.lol", "wss://nostr.mom", "wss://relay.ditto.pub"]
JE_RELAIS = 50


async def main() -> int:
    evs = []
    for r in RELAYS:
        got = await fetch_events(r, [{"kinds": [9735], "limit": JE_RELAIS}], timeout=15,
                                 limit_events=JE_RELAIS)
        print(f"  {r}: {len(got)} Belege")
        evs.extend(got)
    seen, uniq = set(), []
    for e in evs:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        uniq.append(e)

    t = zaps.tally(uniq)
    print(f"\neindeutige Belege: {t['belege']}")
    print(f"Zahlung belegt:    {t['zahlung_belegt']}  ({t['zahlung_belegt'] / t['belege']:.0%})")
    print(f"nicht belegt:      {t['zahlung_nicht_belegt']}")
    print(f"Zweck gebunden:    {t['zweck_gebunden']}")
    print(f"Sats belegt:       {t['sats_belegt']}")
    gruende = Counter(p.split(" (")[0] for d in t["details"] for p in d["problems"])
    print("\nHaeufigste Gruende:")
    for k, v in gruende.most_common(6):
        print(f"  {v:4d}  {k}")

    p = Path(__file__).with_name("zap_belege.json")
    p.write_text(json.dumps({"zeit": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **t},
                            indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\ngeschrieben: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
