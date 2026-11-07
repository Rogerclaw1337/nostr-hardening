"""Punkt 2: Aufbewahrung deklarieren und messen.

Ein Relais ist kein Archiv. Die Frage "wie lange hält dieses Relais meine Daten?"
lässt sich heute nur beantworten, indem man nachsieht — und auch das nur
näherungsweise. Dieses Modul tut beides:

    declared(info)             was das NIP-11-Dokument behauptet
    measure_horizon(relay)     was tatsächlich noch abrufbar ist

Der Horizont wird über Stichproben in die Vergangenheit geschätzt: für jede
Altersstufe wird gefragt, ob es überhaupt Events gibt (limit 1). Das ist billiger
als Zählen und beantwortet genau die Frage, die einen Autor interessiert.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .wire import fetch_events, relay_info

STUFEN_TAGE = [7, 30, 90, 180, 365, 730, 1825]


@dataclass
class Horizon:
    relay: str
    oldest_found_days: int | None = None   # gröbste Stufe, auf der noch etwas kam
    steps: dict[int, bool] | None = None
    declared: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "relay": self.relay,
            "oldest_found_days": self.oldest_found_days,
            "steps": self.steps,
            "declared": self.declared,
        }


def declared(info: dict[str, Any]) -> dict[str, Any]:
    """Relevante Felder aus dem NIP-11-Dokument, ohne Interpretation."""
    if not info or "_error" in info:
        return {"error": (info or {}).get("_error", "kein NIP-11")}
    out: dict[str, Any] = {
        "name": info.get("name"),
        "software": info.get("software"),
        "version": info.get("version"),
    }
    lim = info.get("limitation") or {}
    for key in ("max_message_length", "max_subscriptions", "max_filters",
                "max_limit", "max_subid_length", "min_prefix", "payment_required",
                "auth_required", "restricted_writes", "created_at_lower_limit"):
        if key in lim:
            out[key] = lim[key]
    # Nicht standardisiert, aber in freier Wildbahn vorhanden: eigene Retention-Felder
    for key in ("retention", "retention_days", "retention_policy", "archive"):
        if key in info:
            out[key] = info[key]
        if key in lim:
            out[key] = lim[key]
    return out


async def measure_horizon(relay: str, *, kind: int = 1, timeout: float = 8.0) -> Horizon:
    now = int(time.time())
    steps: dict[int, bool] = {}
    oldest: int | None = None
    for days in STUFEN_TAGE:
        until = now - days * 86400
        since = until - 86400  # ein Tag Fenster
        events = await fetch_events(
            relay,
            [{"kinds": [kind], "since": since, "until": until, "limit": 1}],
            timeout=timeout,
            limit_events=1,
        )
        hit = bool(events)
        steps[days] = hit
        if hit:
            oldest = days
        else:
            # erste Stufe ohne Treffer beendet die Suche (nicht streng monoton,
            # aber in der Praxis stabil und billig)
            break
    info = await relay_info(relay)
    return Horizon(relay=relay, oldest_found_days=oldest, steps=steps, declared=declared(info))


async def survey(relays: list[str], *, kind: int = 1) -> list[Horizon]:
    return list(await asyncio.gather(*(measure_horizon(r, kind=kind) for r in relays)))
