"""Punkt 4: Löschen, das auch löscht.

NIP-09 kennt zwei Fälle, und der zweite wird fast überall falsch gemacht:

* gewöhnliche Events (kind 1, 7, …) werden über `e` adressiert,
* ersetzbare Events (kind 0, 3, 10000–19999) und parameterisierte ersetzbare
  Events (kind 30000–39999, etwa Longform 30023) brauchen zusätzlich den
  `a`-Tag `<kind>:<pubkey>:<d>`.

Ohne `a`-Tag bleibt der Artikel stehen, obwohl der Autor glaubt, gelöscht zu
haben. Dieses Modul baut die Löschung richtig und prüft danach nach.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .keys import custom, tag
from .wire import fetch_events


def coordinate(event: dict[str, Any]) -> str | None:
    """`a`-Wert für parameterisierte ersetzbare Events, sonst None."""
    kind = event.get("kind")
    if not isinstance(kind, int):
        return None
    if 30000 <= kind < 40000:
        d = ""
        for t in event.get("tags", []):
            if t and t[0] == "d":
                d = t[1] if len(t) > 1 else ""
                break
        return f"{kind}:{event['pubkey']}:{d}"
    return None


def build_deletion(
    targets: Iterable[dict[str, Any]],
    keys,
    *,
    reason: str = "",
) -> dict[str, Any]:
    """kind-5-Event, das für jedes Ziel den passenden Tag setzt."""
    tags = []
    for ev in targets:
        tags.append(tag("e", ev["id"]))
        coord = coordinate(ev)
        if coord:
            tags.append(tag("a", coord))
        if isinstance(ev.get("kind"), int):
            tags.append(tag("k", str(ev["kind"])))
    return custom(5, reason, tags, keys)


@dataclass
class DeletionCheck:
    target_id: str
    reachable_after: list[str]
    gone_after: list[str]

    @property
    def effective(self) -> bool:
        return not self.reachable_after

    def as_dict(self) -> dict[str, Any]:
        return {"target": self.target_id, "still_reachable": self.reachable_after,
                "gone": self.gone_after, "effective": self.effective}


async def verify_deleted(relays: list[str], target_id: str, *, timeout: float = 8.0) -> DeletionCheck:
    """Nach dem Löschen: auf welchen Relais ist das Ziel noch abrufbar?"""
    still: list[str] = []
    gone: list[str] = []
    for url in relays:
        events = await fetch_events(url, [{"ids": [target_id]}], timeout=timeout, limit_events=1)
        (still if events else gone).append(url)
    return DeletionCheck(target_id=target_id, reachable_after=still, gone_after=gone)


def deletion_covers(deletion: dict[str, Any], target: dict[str, Any]) -> dict[str, bool]:
    """Prüft, ob ein vorhandenes kind-5-Event das Ziel vollständig adressiert."""
    e_ids = {t[1] for t in deletion.get("tags", []) if t and t[0] == "e" and len(t) > 1}
    a_vals = {t[1] for t in deletion.get("tags", []) if t and t[0] == "a" and len(t) > 1}
    coord = coordinate(target)
    return {
        "has_e": target["id"] in e_ids,
        "needs_a": coord is not None,
        "has_a": (coord in a_vals) if coord else True,
        "complete": (target["id"] in e_ids) and (coord is None or coord in a_vals),
    }
