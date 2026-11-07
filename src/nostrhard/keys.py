"""Schlüssel und Eventbau über nostr_sdk.

Für Messungen wird bewusst ein eigener Wegwerf-Schlüssel benutzt: Ein Audit, das
Test-Events in die Timeline eines echten Kontos schreibt, ist kein Audit, sondern
Müll. Der Schlüssel wird aus einer Datei geladen, damit Messreihen über Tage
vergleichbar bleiben (und die Events nachvollziehbar sind).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nostr_sdk import Event, EventBuilder, Keys, Kind, Tag

KEYFILE_DEFAULT = Path(os.environ.get("NOSTRHARD_KEY", "/opt/data/secrets/nostrhard_test_key.txt"))


def load_or_create(path: Path | str = KEYFILE_DEFAULT) -> Keys:
    p = Path(path)
    if p.exists():
        secret = p.read_text(encoding="utf-8").strip()
        if secret:
            return Keys.parse(secret)
    keys = Keys.generate()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(keys.secret_key().to_hex(), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return keys


def note(text: str, keys: Keys, tags: list[Tag] | None = None) -> dict[str, Any]:
    """Unsigniertes/ signiertes kind-1-Event als JSON-Dict für die Drahtebene."""
    builder = EventBuilder.text_note(text) if hasattr(EventBuilder, "text_note") else EventBuilder(Kind(1), text)
    if tags:
        for t in tags:
            builder = builder.tags([t])
    event: Event = builder.sign_with_keys(keys)
    return json.loads(event.as_json())


def custom(kind: int, content: str, tags: list[Tag], keys: Keys) -> dict[str, Any]:
    builder = EventBuilder(Kind(kind), content)
    if tags:
        builder = builder.tags(tags)
    event: Event = builder.sign_with_keys(keys)
    return json.loads(event.as_json())


def tag(name: str, *values: str) -> Tag:
    return Tag.parse([name, *values])
