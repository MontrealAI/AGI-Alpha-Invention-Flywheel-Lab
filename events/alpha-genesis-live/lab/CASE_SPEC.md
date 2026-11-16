# Synthetic case: Sable Supply catalog reconciliation

**Business objective:** identify the precise discrepancies between an internal catalog and supplier feed, so an operations owner can investigate before acting.

**Input contract:** comma-separated UTF-8, exact `sku` identifier, shared fields compared as exact strings (`product`, `unit_price`, `stock`, `status`); no inference of business truth. `X-007` and `X-7` are different identifiers. Source A and B are equally untrusted here. No real suppliers, customers or transactions are represented.

**Deterministic expected results:**

| SKU | Disagreement | A | B | Why it matters |
|---|---|---|---|---|
| X-101 | stock | 20 | 18 | Inventory change needs owner investigation |
| X-102 | unit_price | 9.95 | 11.95 | Price conflict needs contract check |
| X-104 | status | active | paused | Catalog status requires authoritative confirmation |

Unmatched A-only: `X-007` and `X-105`; B-only `X-107`. **Matched unique identifiers = 5**. The sample contains **7 A rows** and **6 B rows**. No authorization or financial effect follows directly.

**Challenge input:** `supply_b_challenge.csv` reduces the three conflicts to zero, adds `X-007` to B, preserves A-only `X-105` and B-only `X-107`. **6 matched identifiers; 1 A-only and 1 B-only**. Changing input bytes requires a fresh comparison; prior receipt must not be silently reused.

**Designed failure examples:** `claim_wrong.json` intentionally omits two unmatched IDs and alleges an incorrect X-101 price conflict; `claim_reference.json` contains the correct structured result. These are **authored** and are not model output.

**Human review duty:** identify the authoritative source(s), confirm contract terms and effective dates, investigate data quality and duplicate keys, approve any operational changes under normal organizational controls. One completed data check does not establish process or economic value.
