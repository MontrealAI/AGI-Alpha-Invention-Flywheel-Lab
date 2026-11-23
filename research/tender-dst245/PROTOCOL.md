# TENDER-DST245 — frozen timezone negative/control protocol

Registered as a **dependent, isolated correctness repair** to draft PR #551, exact source `dc93edf62927bb0cf0d91745e07265afa6121faa`. No changes to tender prices, source documents, commercial readiness, canonical native accounts, public main or released runtime. This is supporting engineering, **not** a Blue Sky flagship, buyer contract or external payment.

## Reproduced pre-repair negative witnesses

Python `datetime.replace(tzinfo=ZoneInfo("America/Toronto"))` does **not** ensure that a local wall time exists. On spring-forward Sunday **2026-03-08 02:30 EST**, the current parser yields 07:30 UTC although 02:30 does not exist in Toronto; local round-trip becomes 03:30 EDT. On fallback Sunday **2026-11-01 01:30 EST**, the current parser rejects a legitimate second occurrence (the valid instant is 06:30 UTC, `fold=1`). The first occurrence **2026-11-01 01:30 EDT** is 05:30 UTC.

These are synthetic timestamp tests only. The actual DFO 30008508 November 23, 2026 14:00 EST is unambiguous (19:00 UTC) and shall be unchanged.

## Predeclared acceptance

1. Both existing ordinary EST and EDT cases remain accepted with exact UTC offsets. UTC input remains unmodified. The fixed official DFO case remains INDETERMINATE for inventory completeness, known instant 19:00 UTC, external 14:00 UTC conflict, HOLD_NO_BID.
2. Reject the nonexistent 2026-03-08 02:30 local time regardless of whether its supplied label is EST or EDT.
3. Accept both valid folds 2026-11-01 01:30 EDT (05:30 UTC) and EST (06:30 UTC); do not silently choose the wrong fold.
4. Reject mismatched seasonal labels, malformed times, omitted explicit zones, and mismatched apparent authority. Preserve all original fifteen tests without changing registered source readings.
5. Use only standard-library `zoneinfo` and an exact UTC round-trip to determine which fold is valid; no network, paid APIs, credentials, account mutations, outreach or bidding. New tests independently assert these cases. Keep source and test commits separate from this frozen protocol, never rewrite historical failures.

## Economic scope and control

Time conversion correctness avoids one technical failure mode but supplies no independently verified newest amendment list, financial buyer benefit, complete cost, eligibility or contract. The original `final_current_deadline_verified=False` and `HOLD_NO_BID` remain intact. No runtime release or financial adoption from this repair.