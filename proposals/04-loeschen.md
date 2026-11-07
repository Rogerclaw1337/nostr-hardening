# Proposal 4 — Deletion: the `a` tag is not optional, and deletion is not done

Status: draft; builds on nostr-protocol/nips#2099 (+ #938, #1731)
Related: NIP-09, NIP-01 (replaceable events)

## Problem

NIP-09 addresses ordinary events with `e`. Parameterised replaceable events
(30000–39999, e.g. long-form 30023) are addressed by *coordinate* — and a deletion
without the matching `a` tag does nothing to them. Clients set `e` and stop.

The second half is social, not technical: even a correct deletion is a request.
Relays may ignore it, and nobody measures whether they did.

## Measurement (7 November 2026)

Method: post a target on four public relays, confirm it is retrievable, publish a
NIP-09 deletion built by `deleting.build_deletion()` (with `e`, `a` and `k` tags),
wait, then re-check every relay. Code: `qa/messung_loeschen.py`.

| Case | retrievable before | still retrievable afterwards |
|---|---|---|
| kind 1 (note) | 2 of 4 | **1** — relay.primal.net kept serving it |
| kind 30023 (long-form) | 3 of 4 | **1** — relay.primal.net kept serving it |

Re-checked several minutes later: every relay that had held a copy dropped it —
ditto.pub in both cases, nos.lol for the article — except primal.net, which still
returned both targets by id. (nos.lol and nostr.mom had never held a copy of the note.)

So: **deletion worked on the relays that had it, except one** — and the author has
no way to know which. A deletion event that is accepted is not a deletion that is
executed.

## Proposal

### 1. Clients: build the coordinate, always

For any event with kind ≥ 30000, the deletion MUST carry `a = <kind>:<pubkey>:<d>`.
Recommended, and cheap: also add `k` tags so a relay can route without parsing ids.
`deleting.deletion_covers()` exists to test this on the client side before sending.

### 2. A way to ask "is it gone?"

Reuse the `PROOF` message from proposal 1 — the same primitive answers both
"do you have it" and "do you still have it". After a deletion, a client SHOULD
verify and tell the user the truth: *"removed from 3 of 4 relays; primal.net still
serves it."*

That sentence is the product. Today the user gets a green checkmark and a lie.

### 3. Tombstone with a retention argument

For content that must not resurface, a signed tombstone (`kind 5` with the
`a` coordinate and no `e`) placed into the same relays should survive longer than
the thing it deletes. Without a retention declaration (proposal 2) even that is
guesswork.

## Reference implementation

* `src/nostrhard/deleting.py` — `coordinate()`, `build_deletion()`,
  `deletion_covers()`, `verify_deleted()`.
* `qa/loeschen_messung.json` — raw results.

## Open questions

* Should a relay that ignores a deletion be allowed to keep the *content* while
  dropping it from indexes? (Primal appears to do this: the event is still served
  by id.)
* The "restore" case: if a later event with the same `d` tag arrives, is the
  deletion still valid? NIP-09 is silent, which is why #1731 keeps coming back.
