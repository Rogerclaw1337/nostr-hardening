"""Punkt 1: Zustellung beweisen.

`OK ... true` heißt angenommen, nicht gespeichert. Dieses Modul beantwortet die
Frage, die ein Client heute nicht beantworten kann: liegt mein Event nach dem
Senden noch auf dem Relais — und wenn ja, liefert es das Relais auch aus?

Zwei Betriebsarten:

    audit(relays, event)      eine Momentaufnahme über viele Relais
    publish_verified(...)     senden mit Quorum: Erfolg erst, wenn N Relais das
                              Event nachweislich ausliefern

Der Unterschied zu einer Bibliotheksfunktion wie `send_event()` ist der
Nachweis: nach dem Senden wird gewartet, dann per REQ nachgesehen.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .wire import PublishResult, publish_and_verify


@dataclass
class AuditReport:
    event_id: str
    results: list[PublishResult]

    @property
    def accepted(self) -> list[PublishResult]:
        return [r for r in self.results if r.accepted]

    @property
    def retrievable(self) -> list[PublishResult]:
        return [r for r in self.results if r.retrievable]

    @property
    def false_success(self) -> list[PublishResult]:
        return [r for r in self.results if r.is_false_success]

    def summary(self) -> dict[str, Any]:
        n = len(self.results)
        return {
            "event_id": self.event_id,
            "relays": n,
            "accepted": len(self.accepted),
            "retrievable": len(self.retrievable),
            "false_success": len(self.false_success),
            "false_success_rate": round(len(self.false_success) / n, 3) if n else 0.0,
            "no_answer": len([r for r in self.results if r.accepted is None]),
        }

    def lines(self) -> list[str]:
        out = []
        for r in sorted(self.results, key=lambda x: (x.retrievable is not True, x.relay)):
            flag = "FAKE-OK" if r.is_false_success else ("ok" if r.retrievable else ("abgelehnt" if r.accepted is False else "keine Antwort"))
            msg = f" [{r.message}]" if r.message else ""
            out.append(f"{flag:11s} {r.relay:45s} accept={r.accepted} fetch={r.retrievable}{msg}")
        return out


async def audit(
    relays: Sequence[str],
    event: dict[str, Any],
    *,
    settle_seconds: float = 3.0,
    concurrency: int = 6,
) -> AuditReport:
    sem = asyncio.Semaphore(concurrency)

    async def one(url: str) -> PublishResult:
        async with sem:
            try:
                return await publish_and_verify(url, event, settle_seconds=settle_seconds)
            except Exception as exc:  # noqa: BLE001
                return PublishResult(relay=url, note=f"{type(exc).__name__}: {exc}")

    results = await asyncio.gather(*(one(u) for u in relays))
    return AuditReport(event_id=event["id"], results=list(results))


@dataclass
class QuorumResult:
    ok: bool
    confirmed: list[str]
    failed: list[str]
    report: AuditReport


async def publish_verified(
    relays: Iterable[str],
    event: dict[str, Any],
    *,
    quorum: int = 2,
    settle_seconds: float = 3.0,
    retries: int = 0,
) -> QuorumResult:
    """Senden und erst erfolgreich sein, wenn `quorum` Relais das Event ausliefern.

    `retries` wiederholt nur die Relais, die nicht bestätigt haben. Das Event
    bleibt identisch (gleiche ID), es wird also nichts doppelt erzeugt.
    """
    urls = list(relays)
    report = await audit(urls, event, settle_seconds=settle_seconds)
    for _ in range(max(0, retries)):
        if len(report.retrievable) >= quorum:
            break
        missing = [r.relay for r in report.results if not r.retrievable]
        if not missing:
            break
        again = await audit(missing, event, settle_seconds=settle_seconds)
        by_relay = {r.relay: r for r in report.results}
        for r in again.results:
            by_relay[r.relay] = r
        report.results = list(by_relay.values())
    confirmed = [r.relay for r in report.retrievable]
    failed = [r.relay for r in report.results if not r.retrievable]
    return QuorumResult(ok=len(confirmed) >= quorum, confirmed=confirmed, failed=failed, report=report)
