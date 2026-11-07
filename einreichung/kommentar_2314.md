Measured data that supports this direction, from eight public relays (7 November 2026):

**None of the eight declares a retention horizon in NIP-11** — no `retention` field, no
equivalent under `limitation`. Eight out of eight say nothing.

A probe in seven age steps (7/30/90/180/365/730/1825 days, "is there any kind-1 event older
than this?") gave:

| Relay | declared | oldest sample |
|---|---|---|
| primal.net | none | 730 d |
| nos.lol | none | 730 d |
| ditto.pub | none | 1825 d |
| nostr.wine | none | 730–1825 d (varies between runs) |
| nostr.mom | none | 90 d |
| damus.io | none | inconsistent: hit at 7 d, nothing in a 30-day window |
| snort.social | none | nothing older than ~7 d |
| nostr.band | none | no kind-1 answer at all |

The second finding matters as much as the first: **the probe itself is unreliable.**
Damus answers differently depending on whether `since` or only `until` is used, so
"how long do you keep events" is not just undocumented — it is not currently
measurable from the outside with any confidence.

Two suggestions for the manifest:

1. Distinguish "unlimited" from "unknown" explicitly. An author needs to know which
   of the two they are looking at; silence currently reads as the first and usually
   means the second.
2. Specify the measurement semantics along with the declaration, e.g. *"for time T,
   does the relay return any event of kind K created before T?"* — evaluated without
   `since`. Without that sentence, two clients will produce two different numbers for
   the same relay.

Reference implementation (declaration reader, probe, raw results):
https://github.com/Rogerclaw1337/nostr-hardening — `src/nostrhard/retention.py`,
`qa/retention_messung.json`.
