"""Punkt 5: Medien so taggen, dass Clients sie auch zeigen.

Der Befund aus der Praxis: In einem Longform-Event (kind 30023) rendert Primal
kein Video, egal in welcher Schreibweise — die nackte URL wird zum Link, das
Markdown-Bild zum Rohtext, `imeta` wird ignoriert. In einer Notiz (kind 1)
funktioniert dasselbe Video. Die Darstellung hängt am Event-Typ, nicht am Tag.

Dieses Modul zieht daraus die Konsequenz: es taggt für beide Fälle getrennt und
sagt dem Aufrufer, wenn ein Medium im gewählten Event-Typ nicht erscheinen kann.

    for_note(...)     kind 1: URL im Text ist Pflicht, Tags sind Zugabe
    for_article(...)  kind 30023: Bilder ja, Video nur als Link, nie als Player
"""
from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .keys import tag

BILD_TYPEN = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
VIDEO_TYPEN = {"video/mp4", "video/webm", "video/quicktime"}


@dataclass
class MediaPlan:
    content: str
    tags: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"content": self.content, "warnings": self.warnings,
                "tags": [[t.as_vec()[0], *[str(x) for x in t.as_vec()[1:]]] for t in self.tags]}


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_mime(path: str | Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _imeta(url: str, mime: str, *, dim: str | None = None, sha: str | None = None,
           alt: str | None = None) -> Any:
    vals = ["imeta", f"url {url}", f"m {mime}"]
    if dim:
        vals.append(f"dim {dim}")
    if sha:
        vals.append(f"x {sha}")
    if alt:
        vals.append(f"alt {alt}")
    return tag(*vals)


def for_note(
    text: str,
    url: str,
    *,
    mime: str | None = None,
    dim: str | None = None,
    sha: str | None = None,
    alt: str | None = None,
) -> MediaPlan:
    """Notiz: die URL gehört zusätzlich in den Text — Clients entfernen sie beim
    Rendern, und ohne sie zeigt der eine Client nichts, der andere nur den Link."""
    mime = mime or guess_mime(url)
    plan = MediaPlan(content=f"{text.rstrip()}\n\n{url}")
    plan.tags.append(_imeta(url, mime, dim=dim, sha=sha, alt=alt))
    if mime in VIDEO_TYPEN:
        plan.tags.append(tag("r", url))
    return plan


def for_article(
    text: str,
    url: str,
    *,
    mime: str | None = None,
    dim: str | None = None,
    sha: str | None = None,
    alt: str | None = None,
) -> MediaPlan:
    """Longform: Bild als Markdown UND als `image`-Tag; Video nur als Link mit
    ausdrücklichem Hinweis, weil es dort nicht als Player erscheint."""
    mime = mime or guess_mime(url)
    plan = MediaPlan(content=text)
    if mime in BILD_TYPEN:
        plan.content = f"{text.rstrip()}\n\n![{alt or ''}]({url})"
        plan.tags.append(tag("image", url))
        plan.tags.append(_imeta(url, mime, dim=dim, sha=sha, alt=alt))
    elif mime in VIDEO_TYPEN:
        plan.content = f"{text.rstrip()}\n\n{url}"
        plan.tags.append(tag("r", url))
        plan.warnings.append(
            "Video erscheint in Longform-Events nicht als Player (kind 30023). "
            "Fuer ein sichtbares Video zusaetzlich eine Notiz (kind 1) veroeffentlichen."
        )
    else:
        plan.content = f"{text.rstrip()}\n\n{url}"
        plan.warnings.append(f"Unbekannter Typ {mime}: als Link eingebunden.")
    return plan


def audit_tags(event: dict[str, Any]) -> dict[str, Any]:
    """Prüft ein bestehendes Event auf vollständige Medienangaben."""
    tags = event.get("tags", [])
    has_imeta = any(t and t[0] == "imeta" for t in tags)
    has_image = any(t and t[0] == "image" for t in tags)
    urls_in_text = [w for w in (event.get("content") or "").split() if w.startswith(("http://", "https://"))]
    problems = []
    if urls_in_text and not has_imeta:
        problems.append("URL im Text ohne imeta-Tag")
    if has_imeta:
        for t in tags:
            if t and t[0] == "imeta":
                fields = {p.split(" ", 1)[0] for p in t[1:] if " " in p}
                if "m" not in fields:
                    problems.append("imeta ohne m (MIME)")
                if "url" not in fields:
                    problems.append("imeta ohne url")
    return {
        "kind": event.get("kind"),
        "has_imeta": has_imeta,
        "has_image": has_image,
        "urls_in_text": len(urls_in_text),
        "problems": problems,
    }
