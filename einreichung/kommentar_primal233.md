Reproduced systematically, and it is not a markup problem — it is the event kind.

Six long-form variants (kind 30023), all with the same MP4:
bare URL, markdown image syntax `![alt](url.mp4)`, `imeta` (NIP-92), `image` tag as cover,
HTML `<video>`, and the `/a/<naddr>` route.

**No variant produced a player.** The same URL in a kind-1 note produced one immediately.

So for kind 30023 the client does not render video at all, regardless of how the reference
is expressed — which makes every "try this tag instead" workaround futile.

Two things that would help authors in the meantime, neither of which requires a player:

1. **Show it as a labelled attachment.** If a long-form event contains a URL with a video
   MIME type, a placeholder with a link is far better than silently dropping the reference.
   Invisible omission is the part that costs authors real content.
2. **Let the event declare it.** A `["content-type", "text/markdown", "video/mp4"]` tag would
   let a client know before parsing that something in there cannot be shown, and the author
   could be warned at publication time instead of days later.

My own workaround, now enforced in code: for long-form I emit a link plus an explicit warning
that no player will appear, and publish a companion note (kind 1) with the same file. That
works everywhere, but it is a workaround for a client behaviour.

Reference: https://github.com/Rogerclaw1337/nostr-hardening — `src/nostrhard/media.py`
(`for_article()` refuses to pretend, `for_note()` puts the URL in content and `imeta`).
