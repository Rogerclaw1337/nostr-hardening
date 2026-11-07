Supporting data for making the `a` tag explicit, from an end-to-end test rather than from
reading clients (7 November 2026).

Method: post a target on four public relays, confirm it is retrievable, publish a NIP-09
deletion built with `e`, `a` and `k` tags, wait, then re-check every relay by id.

| Case | retrievable before | retrievable after |
|---|---|---|
| kind 1 (note) | 2 of 4 | **1** — primal.net kept serving it |
| kind 30023 (long-form) | 3 of 4 | **1** — primal.net kept serving it |

Re-checked minutes later: every relay that had held a copy dropped it — ditto.pub in both
cases, nos.lol for the article — **except primal.net**, which still returned both
targets when queried by id. (nos.lol and nostr.mom had never held a copy of the note to
begin with.)

Two observations that might be worth a MUST:

1. **Clients should build the coordinate even when they also send `e`.** The `e` tag alone
   does nothing to a 30023. `deleting.coordinate()` in the reference implementation derives
   `<kind>:<pubkey>:<d>` from the target; `deletion_covers()` checks an existing deletion
   event for completeness before it is sent.
2. **A deletion is a request, and clients should verify it.** After sending, ask the relays
   whether the event is gone and report the truth, e.g. "removed from two of the three relays that had it (the note
   case: one of two); primal.net still serves it". Today the user gets a success message and no such
   sentence.

Reference implementation and raw results:
https://github.com/Rogerclaw1337/nostr-hardening — `src/nostrhard/deleting.py`,
`qa/loeschen_messung.json`.
