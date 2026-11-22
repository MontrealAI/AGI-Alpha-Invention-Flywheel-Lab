# Qualification119 — producer SHA/CSV snapshot consistency (frozen BEFORE witness)
 
Frozen baseline: protected main `3ccf23595c65f8a85b1e69391820463a2d72d5e8`.
Target: owner PR #316 at immutable `9e9b501c84ffe7b7969027c43eb465aff81f8499`. Source files: `campaign/public-need117/interpret.py` and `verify.py`. No write to owner branch or account. This is independent support for a public expressed methodology-validation need, not a government transaction, population claim or flagship.

## Fixed two-case diagnostic
- Positive control: run original `interpret.build` on two-row synthetic CSV A; require SHA256(A), sample-level counts from A and successful unchanged `verify`.
- Single adverse schedule: in the producer's own `interpret.load`, replace CSV A with synthetic CSV B **after `Path.read_bytes` returns A but before `Path.open` obtains the input for the CSV parser**. A and B have distinct row identities and opposite scored results, but identical shape and record count. Do not adjust cases or select schedules after observing outcomes.
- Security acceptance requires the report to correspond to one and the same immutable CSV byte stream, or reject the mutation. If `input_sha256 == SHA256(A)` but reported group counts match B rather than A, **FAIL_PRODUCER_MISMATCH_ACCEPTED** even when command exits zero. If a source swap is not exercised, verdict INCONCLUSIVE. Independently run `verify` on the altered current B to distinguish producer race from the already separately demonstrated verifier race in PR #317.
- Record source SHAs, observed A/B digests, counts, verdict and process resource measurements. Preserve negative result, even if CI green. No new buyer, paid commerce, genuine economic advantage, supplier eligibility or 3B progress is inferred.

## Decision and bounds
If the producer misbinds bytes, owner should make **producer `load` and independent `verify` hash and parse their respective same bounded immutable byte buffer**. Preserve CSV strictness, UTF-8 validation, 4MB and 20,000-record constraints; refuse impossible/oversized inputs. Add both deterministic swap regressions. Any genuine correction is reviewed and integrated by **PR #316's implementation owner** after independent tests. No source registry, financial key, protected main, release, historical allocation failure, public-bid action or production state changes.

This protocol predates code implementation on the qualification branch; exact case contents are fixed: header `case_id,period,group,label,model_output`; A has `SYN-A1,2026-11,alpha,0,0` and `SYN-A2,2026-11,alpha,1,1`; B has `SYN-B1,2026-11,alpha,0,1` and `SYN-B2,2026-11,alpha,1,0`. One baseline, one swap.