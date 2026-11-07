# Proposal 2 — Retention: declare it, then measure it

Status: draft; overlaps nostr-protocol/nips#2314 (Relay Self-Declaration Manifest)
and #1902 (Event Preservation Tips)
Related: NIP-11 (relay information), NIP-65, proposal 1

## Problem

Nothing in NIP-11 says how long a relay keeps an event. `limitation` describes what
comes in (message size, filters, payment), never what stays. An author who
publishes a long-read has no way to know whether it will exist next year.

## Measurement (7 November 2026)

Method: NIP-11 read, then a probe in six age steps (7/30/90/180/365/730/1825 days)
asking whether any kind-1 event exists at all in that window. Code:
`src/nostrhard/retention.py`.

| Relay | NIP-11 retention field | oldest sample found |
|---|---|---|
| relay.primal.net | none | 730 days (nothing at 5 years) |
| nos.lol | none | 730 days |
| relay.ditto.pub | none | 1825 days |
| nostr.wine | none | 730 days |
| nostr.mom | none | 90 days |
| relay.damus.io | none | inconsistent (hit at 7 days, nothing in a 30-day window) |
| relay.snort.social | none | nothing older than ~7 days in the probe |
| relay.nostr.band | none | no kind-1 answer at all |

Two findings, and the second is the more important one:

1. **Not one of eight relays declares a retention policy.** The information simply
   does not exist in machine-readable form.
2. **The probe itself is unreliable.** Damus answered "yes" for events older than
   seven days but returned nothing for a 30-day window; different relays evaluate
   `since`/`until` differently. Measuring retention is not merely undocumented — it
   is, today, not reliably possible from the outside.

## Proposal

### 1. Declare, in NIP-11

```json
{
  "limitation": { … },
  "retention": {
    "policy": "time",            // "time" | "size" | "kind-based" | "unlimited" | "unknown"
    "events_days": 730,          // null when unknown
    "dm_days": 30,
    "kinds": { "30023": "unlimited", "1": 730 },
    "purge": "oldest-first",     // how pressure is resolved
    "updated": 1762387200
  }
}
```

Relays that do not know MUST say `"policy": "unknown"`. An explicit "we do not know"
is worth more than silence, because a client can then warn the author.

### 2. Anchor, in the event

For content that must survive, the author should not rely on relay retention at all:
publish the event, then store the raw JSON with a content-addressed host (Blossom or
plain HTTP with the event id as checksum) and put that URI in an `r` tag. The relay
becomes a discovery layer, not the archive.

### 3. Measure, with defined semantics

The probe in `retention.py` should be specified as: *"for time T, does the relay
return any event of kind K created before T?"* — evaluated per step, without
`since`, because `since` handling differs between implementations. The measured
value is a lower bound, never a guarantee.

## Reference implementation

* `src/nostrhard/retention.py` — `declared()` reads NIP-11, `measure_horizon()`
  probes, `survey()` runs a list.
* `qa/retention_messung.json` — raw results of the table above.

## Open questions

* Should the horizon be signed by the relay (so a third party can cite it)?
* How does `retention` interact with `persisted` (proposal 1)? A receipt without a
  horizon is a promise with an unknown expiry — they belong in one document.
