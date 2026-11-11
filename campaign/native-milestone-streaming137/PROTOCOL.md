# Native milestone streaming137 — frozen prospective engineering protocol

**Scope:** additive, independently owned scale-observation performance correction on public main `7287ed23aee97e52cc822bbb2c22688cc0dc71b7`. **Not** a commercial invention, not a native operating-account migration, and not a new revenue, demand or financing result. Protected original accounts and PR #40 are out of scope.

## Decisive obstruction and stronger ordinary control

`connected_enterprise.scale._milestones` currently scans **every collection for every collection for every target** when computing rolling 365-day amounts. At `m` collections and fixed five thresholds this is O(5m²), even though the existing ordinary rolling-window/deque algorithm in the same module can compute each historical prefix in O(m). It threatens the ability to audit a large observed native event stream without changing a single monetary rule. Use the competent ordinary deque/prefix method as the control, not an alleged novel algorithm.

## Frozen invariants and acceptance (registered before source modification)

1. Preserve five original threshold values, strict rolling-time membership `hour - 8760 < collection_hour <= hour`, within-hour **action-index** prefix ordering, and exact signed integer corrections. Keep the first observed collection crossing and first **profitable and obligation-covered** crossing distinct, even if a later correction reverses attainment.
2. Preserve `_calendar`, `_point`, `_receivables`, `_covered`, every output field, null nonattainment, final terminal status, original inputs and full native financial audit requirements. No relaxation of any source, account, archive, or resource guard.
3. Match the original nested-sum implementation as an independently retained oracle on *bounded fixtures* covering a year rollover, same-hour positive/negative corrections, protected and unprotected states, and no crossing. Compare the full structured milestone records, not merely the amounts.
4. On a separately constructed 10,000-entry ordered collection stream, instrument source-array visits with a fail-fast counting iterable: **at most 6 × input entries**. This tests linear traversal of source records without a timing-dependent CPU assertion. No modeled customer, artifact or bill is created by this synthetic observer stress.
5. Run the specific regression and the pre-existing connected-scale / trailing-profit tests on **the exact corrected head**; hosted repository CI and normal protected merge/release are separate gates. A failing original run stays failed.
6. The correction must not claim million-order empirical operation, future demand, calibrated buyers, novel economic mechanism, native scale projection, or US$3B attained. Whole-campaign/model host billing remains unknown.

**Decision:** Ship only if exact-result equivalence and bounded traversal pass. If not, preserve failure and reject or correct the mechanism. Keep this work isolated from the native-capital writer and the commercial Blue Sky experiment owners.

**Registered external source:** `connected_enterprise/scale.py` Git blob `a18c8c1bf9f8baf795e9c78d1a56ffe5b501afdd`, `tests/test_connected_scale.py` current main. Original baseline _milestones scan remains immutable at `7287ed23aee97e52cc822bbb2c22688cc0dc71b7`. No performance result exists at protocol freeze.
