# Proposal 5 — Media: let the event type decide, and say so

Status: draft; relates to NIP-92 (`imeta`), NIP-71 (video), NIP-94 (file metadata),
nostr-protocol/nips#521, and the Primal issue "Video is not embedded in long-form
reads (kind 30023)" (primal-web-app#233)

## Problem

Whether a medium renders is decided by the event *type*, not by the tags:

* in a note (kind 1) a plain video URL becomes a player;
* in a long-form event (kind 30023) the same URL becomes a link, `![…](…mp4)`
  becomes raw text, `imeta` is ignored, an `<video>` tag is shown as text;
* images behave the other way round: they render in articles, but only if the URL
  is also in the content, not just in a tag.

The result: an author writes one document, and each client shows a different
subset, without error messages. My own article lost a video this way; the same
file played fine as a note.

## Evidence

Manual test series on Primal (October 2026), one long-form event per variant, all
with the same mp4: bare URL, markdown image syntax, `imeta` (NIP-92), `image` tag
as cover, HTML `<video>`, and the `/a/<naddr>` route. **No variant produced a
player.** The same URL in a kind-1 note produced one immediately. The difference is
the event kind, not the markup.

## Proposal

### 1. One media object, two renderers

Define the media description once — `url`, `m`, `dim`, `x` (sha256), `alt`,
`blurhash` — and require clients to read it from `imeta` in *every* text-ish event
(1, 30023, 1111). "It is in the tags but I do not render it" is the bug.

### 2. Explicit capability declaration

The long-form event should be able to say what its content contains:

```json
["content-type", "text/markdown", "image/jpeg", "video/mp4"]
```

A client that cannot render `video/mp4` inside 30023 must then display a labelled
placeholder with a link, not silently drop it. A visible "this article contains
video" is acceptable; invisible omission is not.

### 3. Author-side rule (implemented here)

`media.for_article()` refuses to pretend: for a video it emits a link plus a
warning that the medium will not appear as a player, and recommends publishing a
companion note. `media.for_note()` puts the URL in the content *and* in `imeta`,
because clients disagree about which one they read.

## Reference implementation

* `src/nostrhard/media.py` — `for_note()`, `for_article()`, `audit_tags()`.
* `tests/test_hardening.py` — checks that a video in an article produces a warning
  and never a fake `image` tag.

## Open questions

* Should video in long-form be a separate event referenced by `e`, with the client
  composing the page? That is the only design that works across clients without
  changing every renderer.
* NIP-71 uses its own kinds for video; a long-read with an embedded video therefore
  needs a cross-kind reference anyway. The `content-type` tag is the smallest step.
