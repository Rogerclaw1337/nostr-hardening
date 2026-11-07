# Proposal 3 — Zap receipts: separate "paid" from "claimed"

Status: draft; builds on nostr-protocol/nips#556 (Zap Proofs / partially complete
receipts)
Related: NIP-57, NIP-01

## Problem

A zap receipt (kind 9735) is meant to prove that sats moved. In practice many
receipts prove less than they appear to:

* no `preimage` — the payment cannot be tied to the invoice;
* `description` no longer hashes to the invoice's `description_hash`, because the
  client re-serialised the zap request when storing it;
* no `bolt11` at all.

A client that counts receipts as "zaps received" therefore counts intentions,
not payments.

## Measurement (7 November 2026)

Method: 200 receipts fetched from four relays (primal, nos.lol, nostr.mom,
ditto), deduplicated to 112 unique events, each decoded independently — invoice
decoded with a self-written BOLT11 reader whose checksum is verified and whose
parsed `payment_hash` is checked against the receipt's `preimage`.

| Result | Count | Share |
|---|---|---|
| payment cryptographically proven (`sha256(preimage) == payment_hash`) | 63 | 56 % |
| not provable | 49 | 44 % |
| purpose bound (`sha256(description) == description_hash`) | 70 | 63 % |
| no `bolt11` in the receipt | 10 | 9 % |
| no `description` tag | 9 | 8 % |

Total value of the proven receipts: **15,215 sats**, median 21 sats, largest 10,000 sats.

Of the 102 receipts that carry both a description and an invoice: **70 hash correctly,
32 do not** — 24 because the invoice's description hash no longer matches the stored
description, 8 because the invoice carries no description hash at all.

Self-control of the decoder: if the BOLT11 parser were wrong, the `preimage` would
never match the parsed `payment_hash`. It matches for 63 of 112 receipts, which is
the strongest available evidence that the decoding is correct — and it also shows
that 49 receipts genuinely lack a preimage, since the same code proves the others.

A note on that decoder: the first version applied the wrong unit factors (a `u`
invoice is 100,000 msat, not 100,000,000), which inflated every amount by 1000.
It was caught by looking at the median — 21,000 sats is not a zap, 21 is. The
numbers above are from the corrected version.

## Proposal

### 1. Two independent statements, two names

Clients should stop treating a receipt as one boolean. Split it:

* **paid** — `sha256(preimage) == payment_hash` of the invoice. Hard, verifiable.
* **purpose-bound** — `sha256(description) == description_hash`. Verifiable, but
  frequently broken by re-serialisation.

A receipt with `paid` but without `purpose-bound` is a real payment whose reason is
unproven. A receipt without `paid` is a claim.

### 2. Make `preimage` a MUST for relayed receipts

The node that generated the invoice knows the preimage — it settled the payment.
A receipt published without it is a promise by the sender's wallet, not by the node.
If a wallet cannot publish preimages, it should not publish a receipt at all; the
client can then show "payment claimed by wallet" instead of "zapped".

### 3. Bind the purpose before signing, not after

The zap request should be embedded **byte for byte** — the exact string that was
hashed into the invoice — not parsed and re-encoded. A client that re-serialises
turns a cryptographic proof into a coincidence.

## Reference implementation

* `src/nostrhard/zaps.py` — `verify_receipt()` returns `ok` (paid) and
  `checks.purpose_bound` separately; `tally()` aggregates a sample.
* `src/nostrhard/bolt11mini.py` — BOLT11 reader with checksum verification, used
  where no package is available.
* `qa/zap_belege.json` — raw results.

## Open questions

* Should `paid` require the receipt's author key to equal the LNURL `nostrPubkey`?
  Currently that check is optional; without it a third party can mint receipts for
  someone else's `p` tag.
* Custodial wallets that never see preimages (Wallet of Satoshi is the known case)
  are structurally unable to satisfy this. That is not a reason to weaken the
  rule — it is a reason to label their receipts differently.
