"""Minimaler BOLT11-Leser (bech32), ohne Fremdpaket.

Warum selbst: In dieser Umgebung gibt es weder pip noch uv, und die Prüfung von
Zap-Belegen braucht den `payment_hash` aus der Rechnung. Ohne ihn lässt sich
`preimage` nicht gegenprüfen, und ohne Gegenprobe ist ein Beleg eine Behauptung.

Sicherheitsnetz statt Vertrauen:
* die bech32-Prüfsumme wird geprüft (falsche Rechnung -> Ausnahme, kein Raten),
* die 5-zu-8-Bit-Umwandlung wird mit Restbits geprüft (kein stilles Verschieben),
* jede Ausgabe trägt die Länge des gelesenen Feldes, damit Aufrufer validieren.

Das ersetzt kein vollständiges BOLT11-Paket, deckt aber die Felder ab, die für
Belege zählen: Betrag, Zeitstempel, payment_hash, description(_hash), Ablauf.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
# Millisatoshi je Einheit: 1 BTC = 1e11 msat, 1 mBTC = 1e8, 1 uBTC = 1e5,
# 1 nBTC = 1e2, 1 pBTC = 0,1. Falsche Faktoren hier verzerren jeden Betrag um
# Zehnerpotenzen - der klassische Fehler beim Selbstbau eines BOLT11-Lesers.
MULT = {"m": 10 ** 8, "u": 10 ** 5, "n": 10 ** 2, "p": 0.1, "": 10 ** 11}


class Bolt11Error(ValueError):
    """Rechnung nicht lesbar; die Meldung nennt den Grund."""


def _polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= gen[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _check_checksum(data: str) -> None:
    hrp, _, rest = data.rpartition("1")
    if not hrp or len(rest) < 6:
        raise Bolt11Error("kein gültiger bech32-Aufbau")
    vals = [CHARSET.find(c) for c in rest]
    if any(v < 0 for v in vals):
        raise Bolt11Error("ungültiges Zeichen im Datenteil")
    if _polymod(_hrp_expand(hrp) + vals) != 1:
        raise Bolt11Error("bech32-Prüfsumme stimmt nicht")


def _five_to_eight(groups: list[int], *, strict: bool = True) -> bytes:
    acc = 0
    bits = 0
    out = bytearray()
    for g in groups:
        acc = (acc << 5) | g
        bits += 5
        while bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    if strict and bits >= 5:
        raise Bolt11Error("Restbits länger als ein Zeichen")
    if strict and acc & ((1 << bits) - 1):
        raise Bolt11Error("Restbits nicht null")
    return bytes(out)


@dataclass
class Invoice:
    amount_msat: int | None = None
    timestamp: int | None = None
    payment_hash: str | None = None
    description: str | None = None
    description_hash: str | None = None
    payee: str | None = None
    expiry: int | None = None
    network: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "amount_msat": self.amount_msat,
            "timestamp": self.timestamp,
            "payment_hash": self.payment_hash,
            "description": self.description,
            "description_hash": self.description_hash,
            "payee": self.payee,
            "expiry": self.expiry,
            "network": self.network,
        }


def decode(invoice: str) -> Invoice:
    inv = invoice.strip().lower()
    _check_checksum(inv)
    hrp, _, rest = inv.rpartition("1")
    m = re.match(r"^ln([a-z]+?)(\d+)?([munp])?$", hrp)
    if not m:
        raise Bolt11Error(f"unbekannter Präfix: {hrp}")
    network = {"bc": "mainnet", "tb": "testnet", "bcrt": "regtest"}.get(m.group(1), m.group(1))
    amount_msat = None
    if m.group(2):
        amount_msat = int(round(int(m.group(2)) * MULT[m.group(3) or ""]))

    allgroups = [CHARSET.find(c) for c in rest[:-6]]
    if any(v < 0 for v in allgroups):
        raise Bolt11Error("ungültiges Zeichen im Datenteil")
    # Nach den Feldern folgt die Signatur: 65 Byte = 520 Bit = 104 Fünfgruppen.
    if len(allgroups) <= 104 + 7:
        raise Bolt11Error("zu kurz für Felder und Signatur")
    data = allgroups[:-104]

    out = Invoice(amount_msat=amount_msat, network=network)

    # Zeitstempel: erste 35 Bit = 7 Gruppen
    if len(data) < 7:
        raise Bolt11Error("zu kurz")
    ts = 0
    for g in data[:7]:
        ts = (ts << 5) | g
    out.timestamp = ts

    i = 7
    while i + 3 <= len(data):
        tag = data[i]
        ln = (data[i + 1] << 5) | data[i + 2]
        i += 3
        if i + ln > len(data):
            raise Bolt11Error("Feldlänge überschreitet die Rechnung")
        payload = data[i:i + ln]
        i += ln
        if tag == 1:  # p: payment_hash, 52 Zeichen = 32 Byte
            raw = _five_to_eight(payload)
            out.payment_hash = raw.hex()
            if len(raw) != 32:
                raise Bolt11Error(f"payment_hash hat {len(raw)} statt 32 Byte")
        elif tag == 13:  # d: description, utf-8
            out.description = _five_to_eight(payload).decode("utf-8", "replace")
        elif tag == 23:  # h: description_hash
            raw = _five_to_eight(payload)
            out.description_hash = raw.hex()
            if len(raw) != 32:
                raise Bolt11Error(f"description_hash hat {len(raw)} statt 32 Byte")
        elif tag == 19:  # n: payee
            out.payee = _five_to_eight(payload).hex()
        elif tag == 6:  # x: expiry
            val = 0
            for g in payload:
                val = (val << 5) | g
            out.expiry = val
        out.fields[str(tag)] = len(payload)
    return out
