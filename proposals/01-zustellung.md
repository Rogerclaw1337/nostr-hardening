# Proposal 1 — Delivery confirmation: make `OK` mean something

Status: draft, replaces the closed PR nostr-protocol/nips#2496
Related: NIP-01 (`OK`), NIP-65 (relay lists), NIP-11 (relay information)

## Problem

A relay answers an `EVENT` with `OK ... true` and the client treats that as "it is
there". It is not. `OK` is an intake receipt; nothing in the protocol states what
happens afterwards, and three failure modes are indistinguishable from success:

1. accepted into a buffer, then lost;
2. stored, later pruned;
3. stored, but never returned in a `REQ`.

## Measurement (7 November 2026)

Method: one kind-1 event per run signed with a throwaway key, sent to ten public
relays, `OK` awaited with a 15 s timeout, then a 6 s settle, then `REQ {"ids":[…]}`.
Three independent events. Reproduce with `qa/messung_zustellung.py`.

| Relay | accepted | retrievable |
|---|---|---|
| relay.primal.net | yes | yes |
| nos.lol | yes | yes |
| relay.ditto.pub | yes (also `duplicate:`) | yes |
| relay.snort.social | yes | yes |
| nostr.mom | yes | **no** (one of three runs, re-checked minutes later: still absent) |
| relay.damus.io | no answer in 15 s (one of three runs: answered, delivered) |
| relay.dreamith.to | no answer |
| relay.nostr.band | no answer |
| nostr-pub.wellorder.net | no answer |
| relay.tchncs.de | `false` — `public key does not have permission to write` |

Result: **5–6 of 10 relays accepted, 4 of 10 answered nothing at all** (damus
answered in one of three runs), **1 accepted and never served the event** — a false
success, verified by re-checking after several minutes.

The false success is the whole point: a client that publishes to ten relays and
reads ten positive answers has, in this sample, **four to five real copies** — and
no way to tell which five.

## Proposal

Three pieces, all optional and backwards compatible.

### 1. `persisted` prefix on `OK`

```
["OK", "<id>", true, "persisted:"]
```

A relay that can guarantee the event is on durable storage says so. Absence of the
prefix means *unknown*, never *persisted*. `duplicate:` already implies persistence.

### 2. `PROOF` message

```
client → relay:  ["PROOF", "<sub-id>", "<event-id>", …]
relay → client:  ["PROOF", "<sub-id>", {"<event-id>": {"have": true, "kind": 1, "created_at": 1234}}, …]
relay → client:  ["EOSE", "<sub-id>"]
```

Cheap to answer from an index, and it answers the only question that matters:
*do you still have this?*

### 3. Client rule: quorum, not faith

A client SHOULD consider a publish successful only when at least N relays have
answered `persisted` **or** confirmed via `PROOF`. Default N = 2. Relays that
answer nothing are counted as failures, not as silent successes.

## Reference implementation

`src/nostrhard/delivery.py` — `publish_verified(relays, event, quorum=2)` sends,
waits, re-reads and returns only when the quorum is met; `audit()` produces the
table above for any relay list.

## Open questions

* `PROOF` versus reusing `REQ` with `ids`: a plain `REQ` already answers it, at the
  cost of a full event transfer. `PROOF` exists for the case where the client wants
  one bit per id.
* Retention interplay: see proposal 2. A `persisted` receipt with no retention
  horizon is a promise with an unknown expiry.
