Data on how often a receipt actually proves a payment, from a sample of public receipts
(7 November 2026).

Method: 200 receipts from four relays (primal, nos.lol, nostr.mom, ditto), deduplicated
to **112 unique events**. Each `bolt11` decoded with a checksum-verified reader, then
`sha256(preimage)` compared against the invoice's `payment_hash`, and `sha256(description)`
against `description_hash`.

| Result | Count | Share |
|---|---|---|
| payment cryptographically proven | 63 | 56 % |
| not provable | 49 | 44 % |
| purpose bound | 70 | 63 % |
| no `bolt11` at all | 10 | 9 % |
| no `description` tag | 9 | 8 % |

Proven value: 15,215 sats, median 21 sats, largest 10,000 sats.

**The dominant reason is a missing `preimage`** — 49 of 112. Those payments may well have
happened; nothing in the receipt proves it. A client that counts receipts as "zaps
received" therefore counts a mix of settled payments and claims.

The second reason is more subtle and worth stating in the NIP: even when the payment is
proven, the *purpose* often is not. `sha256(description)` failed to match the invoice's
`description_hash` in 24 cases, because clients re-serialise the zap request instead of
storing the exact string that was hashed. The proof survives; the "what for" does not.

Suggestion, in the spirit of this thread: treat the two as separate statements —
`paid` (preimage → payment_hash, hard) and `purpose-bound` (description → description_hash,
weaker) — instead of one boolean per receipt.

Reference implementation, including a self-contained BOLT11 reader (no external package,
checksum verified) and the raw sample:
https://github.com/Rogerclaw1337/nostr-hardening — `src/nostrhard/zaps.py`,
`qa/zap_belege.json`.
