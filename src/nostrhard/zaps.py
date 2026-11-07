"""Punkt 3: Zap-Belege prüfen, nicht Zaps zählen.

Ein Zap ist erst dann ein Beleg, wenn drei Dinge zusammenpassen:

1. Der Beleg (kind 9735) ist vom Lightning-Knoten des Empfängers signiert.
2. Die Rechnung im Beleg (bolt11) enthält einen `description_hash`, der zu dem
   Zap-Request passt, den der Absender signiert hat.
3. Das `preimage` im Beleg hasht auf den `payment_hash` der Rechnung.

Ohne 2 und 3 ist ein Beleg eine Behauptung. Die Praxis zeigt Belege, bei denen
Punkt 3 fehlt (der Knoten veröffentlicht dann keine Vorlage) — solche Zaps sind
gezahlt, aber nicht öffentlich nachweisbar.

Dieses Modul prüft, was prüfbar ist, und benennt, was fehlt.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

try:  # vollständiges Paket, wenn vorhanden
    import bolt11 as bolt11lib  # type: ignore
except Exception:  # noqa: BLE001
    bolt11lib = None

from . import bolt11mini


@dataclass
class ReceiptCheck:
    ok: bool
    amount_msat: int | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "amount_msat": self.amount_msat,
                "checks": self.checks, "problems": self.problems}


def _tags(event: dict[str, Any]) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    for t in event.get("tags", []):
        if not t:
            continue
        out.setdefault(t[0], []).append(t)
    return out


def _first(tags: dict[str, list[list[str]]], name: str) -> str | None:
    got = tags.get(name)
    if not got:
        return None
    vals = got[0]
    return vals[1] if len(vals) > 1 else None


def verify_receipt(event: dict[str, Any], expected_recipient: str | None = None) -> ReceiptCheck:
    """Prüft ein kind-9735-Event gegen die Regeln aus NIP-57."""
    res = ReceiptCheck(ok=False)
    problems = res.problems
    checks = res.checks

    checks["kind_9735"] = event.get("kind") == 9735
    if not checks["kind_9735"]:
        problems.append("kein kind-9735-Event")

    tags = _tags(event)
    bolt11 = _first(tags, "bolt11")
    desc = _first(tags, "description")
    desc_hash_tag = _first(tags, "description_hash")
    preimage = _first(tags, "preimage")
    p_tag = _first(tags, "p")

    inv_desc_hash = None
    checks["has_bolt11"] = bool(bolt11)
    checks["has_p_tag"] = bool(p_tag)
    if expected_recipient:
        checks["recipient_matches"] = (p_tag or "").lower() == expected_recipient.lower()
        if not checks["recipient_matches"]:
            problems.append("p-Tag nennt einen anderen Empfänger")
    if not bolt11:
        problems.append("keine bolt11-Rechnung im Beleg")

    if bolt11:
        try:
            if bolt11lib is not None:
                decoded = bolt11lib.decode(bolt11)
                ph = getattr(decoded, "payment_hash", None) or ""
                res.amount_msat = getattr(decoded, "amount_msat", None)
                inv_desc_hash = getattr(decoded, "description_hash", None)
            else:
                decoded = bolt11mini.decode(bolt11)
                ph = decoded.payment_hash or ""
                res.amount_msat = decoded.amount_msat
                inv_desc_hash = decoded.description_hash
            checks["bolt11_decodes"] = True
            checks["has_amount"] = bool(res.amount_msat)
            if inv_desc_hash:
                checks["invoice_carries_description_hash"] = True
        except Exception as exc:  # noqa: BLE001
            checks["bolt11_decodes"] = False
            problems.append(f"Rechnung nicht lesbar: {exc}")
            ph = ""
    else:
        ph = ""

    # Zweckbindung: SHA256(description) müsste dem description_hash der Rechnung
    # entsprechen. In der Praxis scheitert das häufig, weil Clients den Zap-Request
    # beim Speichern neu serialisieren. Dann ist die Zahlung belegt, der Zweck nicht.
    if desc:
        computed = hashlib.sha256(desc.encode("utf-8")).hexdigest()
        target = (inv_desc_hash or desc_hash_tag or "").lower()
        checks["purpose_bound"] = bool(target) and computed == target
        if target and not checks["purpose_bound"]:
            problems.append("Zweck nicht kryptografisch gebunden (description neu serialisiert)")
        if not target:
            problems.append("keine description_hash in der Rechnung")
    else:
        checks["has_description"] = False
        problems.append("kein description-Tag (Zap-Request fehlt)")

    if preimage and ph:
        checks["preimage_matches_invoice"] = hashlib.sha256(bytes.fromhex(preimage)).hexdigest() == ph.lower()
        if not checks["preimage_matches_invoice"]:
            problems.append("preimage hasht nicht auf payment_hash")
    elif not preimage:
        checks["preimage_matches_invoice"] = False
        problems.append("kein preimage — Zahlung öffentlich nicht nachweisbar")

    # "ok" heißt: die Zahlung ist kryptografisch belegt (preimage -> payment_hash
    # der Rechnung). Der Zweck ist eine eigene, schwächere Aussage (purpose_bound).
    res.ok = bool(checks.get("kind_9735") and checks.get("has_bolt11")
                  and checks.get("has_p_tag") and checks.get("preimage_matches_invoice"))
    return res


def tally(events: list[dict[str, Any]], expected_recipient: str | None = None) -> dict[str, Any]:
    """Sammelauswertung über viele Belege: wie viele sind wirklich nachweisbar?"""
    details = [verify_receipt(e, expected_recipient).as_dict() for e in events]
    ok = [d for d in details if d["ok"]]
    purpose = [d for d in details if d["checks"].get("purpose_bound")]
    total_msat = sum(d["amount_msat"] or 0 for d in ok)
    return {
        "belege": len(details),
        "zahlung_belegt": len(ok),
        "zahlung_nicht_belegt": len(details) - len(ok),
        "zweck_gebunden": len(purpose),
        "sats_belegt": total_msat // 1000 if total_msat else 0,
        "details": details,
    }
