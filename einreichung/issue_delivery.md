## The gap

`["OK", id, true, ""]` is an intake receipt. Nothing in NIP-01 says the event is on
disk, and nothing lets a client ask later. Three failure modes are indistinguishable
from success: accepted into a buffer and lost, stored and pruned, stored but never
served in a `REQ`.

This is a follow-up to my closed PR #2496 (NIP-97 draft), which was closed without
discussion. Rather than resubmit the same text, I measured the problem first.

## Measurement — 7 November 2026

One kind-1 event per run, throwaway key, ten public relays, `OK` awaited with a 15 s
timeout, 6 s settle, then `REQ {"ids":[id]}` to see whether it is still there.
Three independent events. Raw data and script: see repository below.

| Relay | accepted | retrievable |
|---|---|---|
| relay.primal.net | yes | yes |
| nos.lol | yes | yes |
| relay.ditto.pub | yes (`duplicate:`) | yes |
| relay.snort.social | yes | yes |
| nostr.mom | yes | **no** — one of three runs, re-checked minutes later, still absent |
| relay.damus.io | no answer (in 1 of 3 runs: answered and delivered) |
| relay.dreamith.to | no answer |
| relay.nostr.band | no answer |
| nostr-pub.wellorder.net | no answer |
| relay.tchncs.de | `false` — no write permission for that key |

**5–6 of 10 accepted. Four answered nothing at all. One returned `true` and never
served the event.**

Four to five real copies out of ten positive answers — and no way for a client to
know which.

## Proposal

1. `["OK", id, true, "persisted:"]` for relays that can guarantee durable storage.
   Absence means *unknown*, never *persisted*.
2. A `PROOF` message: client asks for a set of ids, relay answers `have: true/false`
   from its index and closes with `EOSE`. One bit per id instead of a full event.
3. Client rule: a publish counts as successful only at quorum (default 2) of
   `persisted` or `PROOF` confirmations. Silence is a failure, not a success.

## Reference implementation

Public repository with the measurement scripts, the client-side quorum publisher, and
the other four proposals in this series:
https://github.com/Rogerclaw1337/nostr-hardening

`src/nostrhard/delivery.py` implements `publish_verified(relays, event, quorum=2)`
and `audit()`; `qa/messung_zustellung.py` reproduces the table above.

## Question for maintainers

Would a `PROOF`-style message be considered, or is the preference to fold both
"persisted" and a retention horizon into NIP-11 plus a client-side convention? I am
happy to write whichever form has a chance of being merged.
