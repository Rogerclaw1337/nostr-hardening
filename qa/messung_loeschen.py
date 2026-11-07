#!/usr/bin/env python3
"""QA zu Punkt 4: löscht NIP-09 wirklich — und was ändert das `a`-Tag?

Ablauf je Fall:
  1. Ziel posten und bestätigen, dass es abrufbar ist.
  2. Lösch-Event posten (kind 5): einmal ohne `a`, einmal mit `a`.
  3. Warten, dann auf allen Relais nachsehen, ob das Ziel noch kommt.

Ergebnis wird als JSON geschrieben, damit die Aussage zitierbar bleibt.
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

from nostrhard.deleting import build_deletion, verify_deleted  # noqa: E402
from nostrhard.keys import custom, load_or_create, note, tag  # noqa: E402
from nostrhard.wire import publish_and_verify  # noqa: E402

RELAYS = ["wss://relay.primal.net", "wss://nos.lol", "wss://nostr.mom", "wss://relay.ditto.pub"]


async def post(relays, ev):
    done = []
    for r in relays:
        res = await publish_and_verify(r, ev, settle_seconds=2.0)
        done.append({"relay": r, "accepted": res.accepted, "retrievable": res.retrievable})
    return done


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relais", nargs="*", default=RELAYS)
    ap.add_argument("--aus", default="/opt/data/nostr-hardening/qa/loeschen_messung.json")
    args = ap.parse_args()

    keys = load_or_create()
    out = {"zeit": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "faelle": []}

    for fall in ("notiz", "longform"):
        tagger = uuid.uuid4().hex[:8]
        if fall == "notiz":
            ev = note(f"deletion test {tagger}", keys)
        else:
            ev = custom(30023, f"# deletion test {tagger}\n\nProbeartikel für NIP-09-Verhalten.",
                        [tag("d", f"delete-test-{tagger}"), tag("title", f"Deletion test {tagger}")], keys)
        posted = await post(args.relais, ev)
        alive_before = await verify_deleted(args.relais, ev["id"])
        deletion = build_deletion([ev], keys, reason="qa")
        del_posted = await post(args.relais, deletion)
        await asyncio.sleep(4)
        alive_after = await verify_deleted(args.relais, ev["id"])
        out["faelle"].append({
            "fall": fall,
            "ziel_id": ev["id"],
            "kind": ev["kind"],
            "gepostet": posted,
            "vorher_abrufbar": alive_before.reachable_after,
            "loesch_event": deletion["id"],
            "loesch_tags": [[t[0], t[1]] for t in deletion["tags"]],
            "loesch_gepostet": del_posted,
            "nachher_abrufbar": alive_after.reachable_after,
            "wirksam": alive_after.effective,
        })
        print(f"\n{fall}: {ev['id'][:12]}…  vorher abrufbar auf {len(alive_before.reachable_after)}/"
              f"{len(args.relais)} · nachher noch auf {len(alive_after.reachable_after)}")
        for r in alive_after.reachable_after:
            print(f"   noch da: {r}")

    p = Path(args.aus)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ngeschrieben: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
