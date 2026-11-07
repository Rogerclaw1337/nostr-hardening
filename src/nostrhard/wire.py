"""Rohe WebSocket-Ebene.

Bewusst ohne Client-Bibliothek: genostr und nostr-sdk abstrahieren genau die
Nachrichten weg, um die es hier geht (OK-Prefix, PROOF, EOSE, NOTICE). Wer
Zustellung messen will, muss die Drähte sehen.

Nur zum Signieren wird nostr_sdk benutzt.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TIMEOUT = 8.0


class RelayError(RuntimeError):
    """Verbindung nicht möglich oder Relais antwortet nicht protokollgerecht."""


@dataclass
class PublishResult:
    relay: str
    accepted: bool | None = None          # Inhalt des OK-Feldes, None = keine Antwort
    message: str = ""                     # Prefix/Text aus OK
    latency_ms: int | None = None
    retrievable: bool | None = None       # nach Wartezeit per REQ wiedergefunden
    roundtrip_ms: int | None = None
    note: str = ""

    @property
    def prefix(self) -> str:
        """Führender Prefix einer OK-Nachricht, etwa 'persisted' oder 'blocked'."""
        if ":" in self.message:
            return self.message.split(":", 1)[0].strip().lower()
        return ""

    @property
    def is_false_success(self) -> bool:
        """Relais sagt ja, liefert das Event danach aber nicht zurück."""
        return self.accepted is True and self.retrievable is False

    def as_dict(self) -> dict[str, Any]:
        return {
            "relay": self.relay,
            "accepted": self.accepted,
            "message": self.message,
            "prefix": self.prefix,
            "latency_ms": self.latency_ms,
            "retrievable": self.retrievable,
            "roundtrip_ms": self.roundtrip_ms,
            "false_success": self.is_false_success,
            "note": self.note,
        }


async def _connect(url: str, timeout: float = 10.0):
    import websockets

    try:
        return await asyncio.wait_for(websockets.connect(url, open_timeout=timeout), timeout)
    except Exception as exc:  # noqa: BLE001 - jede Ursache ist hier ein Befund
        raise RelayError(f"{url}: {type(exc).__name__}: {exc}") from exc


async def publish_and_verify(
    url: str,
    event_json: dict[str, Any],
    *,
    settle_seconds: float = 3.0,
    ok_timeout: float = DEFAULT_TIMEOUT,
    fetch_timeout: float = DEFAULT_TIMEOUT,
) -> PublishResult:
    """Event senden, OK lesen, warten, per REQ nachsehen ob es noch da ist.

    Das ist der ganze Punkt 1 in einer Funktion: `OK ... true` ist eine Quittung
    über die Annahme, kein Nachweis über den Bestand.
    """
    res = PublishResult(relay=url)
    eid = event_json["id"]
    t0 = time.monotonic()
    try:
        ws = await _connect(url)
    except RelayError as exc:
        res.note = str(exc)
        return res

    try:
        await ws.send(json.dumps(["EVENT", event_json]))
        deadline = time.monotonic() + ok_timeout
        while True:
            rest = deadline - time.monotonic()
            if rest <= 0:
                res.note = "kein OK innerhalb des Zeitlimits"
                return res
            try:
                raw = await asyncio.wait_for(ws.recv(), rest)
            except asyncio.TimeoutError:
                res.note = "kein OK innerhalb des Zeitlimits"
                return res
            except Exception as exc:  # noqa: BLE001
                res.note = f"Verbindung beim Warten auf OK: {exc}"
                return res
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, list) or len(msg) < 3:
                continue
            if msg[0] == "OK" and msg[1] == eid:
                res.accepted = bool(msg[2])
                res.message = str(msg[3]) if len(msg) > 3 else ""
                res.latency_ms = int((time.monotonic() - t0) * 1000)
                break
            if msg[0] in ("NOTICE", "CLOSED"):
                res.note = f"{msg[0]}: {msg[1] if len(msg) > 1 else ''}"
        if not res.accepted:
            return res

        if settle_seconds:
            await asyncio.sleep(settle_seconds)

        t1 = time.monotonic()
        sub = f"proof-{eid[:8]}"
        await ws.send(json.dumps(["REQ", sub, {"ids": [eid]}]))
        deadline = time.monotonic() + fetch_timeout
        found = False
        while True:
            rest = deadline - time.monotonic()
            if rest <= 0:
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), rest)
            except asyncio.TimeoutError:
                break
            except Exception as exc:  # noqa: BLE001
                res.note = (res.note + " " if res.note else "") + f"Verbindung beim Lesen: {exc}"
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, list):
                continue
            if msg[0] == "EVENT" and len(msg) > 2 and isinstance(msg[2], dict) and msg[2].get("id") == eid:
                found = True
            if msg[0] == "EOSE":
                break
        res.retrievable = found
        res.roundtrip_ms = int((time.monotonic() - t1) * 1000)
        return res
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


async def fetch_events(
    url: str,
    filters: list[dict[str, Any]],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    limit_events: int | None = None,
) -> list[dict[str, Any]]:
    """Einfacher REQ über einen Filter; sammelt bis EOSE."""
    out: list[dict[str, Any]] = []
    sub = f"req-{int(time.time() * 1000) % 100000}"
    try:
        ws = await _connect(url)
    except RelayError:
        return out
    try:
        await ws.send(json.dumps(["REQ", sub, *filters]))
        deadline = time.monotonic() + timeout
        while True:
            rest = deadline - time.monotonic()
            if rest <= 0:
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), rest)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, list):
                continue
            if msg[0] == "EVENT" and len(msg) > 2:
                out.append(msg[2])
                if limit_events and len(out) >= limit_events:
                    break
            elif msg[0] == "EOSE":
                break
        try:
            await ws.send(json.dumps(["CLOSE", sub]))
        except Exception:  # noqa: BLE001
            pass
        return out
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


async def relay_info(url: str, timeout: float = 6.0) -> dict[str, Any]:
    """NIP-11-Dokument holen (HTTP GET mit Accept: application/nostr+json)."""
    import urllib.request

    http = url.replace("wss://", "https://").replace("ws://", "http://")
    req = urllib.request.Request(http, headers={"Accept": "application/nostr+json", "User-Agent": "nostrhard"})
    loop = asyncio.get_running_loop()

    def _do() -> dict[str, Any]:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - feste, geprüfte Ziele
            return json.loads(resp.read().decode("utf-8", "replace"))

    try:
        return await loop.run_in_executor(None, _do)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}
