# P0-187 — Deterministic acceptance-after-CAS-revocation race (frozen before test)

**Registered:** 2026-11-16 UTC. **Exact prospective candidate parent:** P0-186 `df0387344d82e80f09f8e7e94f2019009be3f0e5`; owner financial PR #40 `ced6c1cb004887dcdafaea59a2976020be649f8e` remains unchanged. This is a test-only, unmerged, independent review branch. It is NOT an approved financial writer, account migration, release, or competing source.

## Fixed falsification target

The P0-186 `_cached_history_evidence_available` check re-resolves nested CAS on a cache hit, but it does not hold the canonical evidence store or source/account writer lease through the instant of returning the cached receipt. A fixture-owned evidence blob can vanish **after the successful closure check but before cached acceptance**. Acceptance requires evidence still available at the authorization linearization point, or a proven immutable read snapshot whose validity/authority is explicitly bound. One earlier successful snapshot alone may not stand for the current store after revocation.

## Exact deterministic schedule

1. Construct one nested V2 predecessor plus one V2 outer ticket using the unchanged fixture factory in `tests/test_transition_store184.py`. Publish only synthetic CAS blobs in a fresh temporary directory; use a temporary synthetic verifier root. No original account, signing key, customer data, finance file, journal or recovery material.
2. Patch only external historical subprocess to a deterministic model returning accepted *iff* the nested ticket resolves. Patch inventory/job loading as previous review tests do. First `verify_historical` establishes one successful audit and a valid cache; no mutation.
3. Make one identical call, instrumenting the **real** P0-186 closure function at its return boundary. On its *second* successful completion, delete exactly the previously identified nested-only CAS blob in the same trusted temporary directory, and then return the function's unmodified boolean. No thread timing, retries, alternate seed, sleep, or input replacement.
4. Independently show the outer V2 ticket still resolves but the nested ticket now fails `TRANSITION_EVIDENCE_MISSING_OR_CHANGED`. The safety requirement is that the identical second call **must not** return an accepted historical audit after that revocation. Preserve the original observed exception/result and the unchanged first-call receipt.
5. Run one fixed new test plus all previous P0-184/185/186 tests in read-only hosted Actions on the exact branch head. A failing required assertion is a genuine RED and remains failed; do not weaken it, change schedule or silently relabel as successful. Do not use its failure to infer corruption or compromise of actual HMAC account material.

## Scope, limits and owner-side consequence

The fixture uses a deterministic monkeypatch seam to place the revocation **between** a real successful CAS closure check and an in-process cached return. It is a **synthetic interleaving counterexample**, not evidence that a filesystem attacker reached real accounts, a demonstrated current production exploit, or a whole-business transaction. No external uncooperative writer is modeled. The proposed remedies require an owner-approved single canonical lease and/or immutable verified evidence snapshot with current authority; simple path hashing, a later unlocked recheck, more cache-key fields or retrying the subprocess alone cannot establish race-free acceptance. Do not modify PR40, PR35, P0-186 source, historical failures or any original protected liability. No new spending, paid models, keys, outreach, production deployment or real transactions.

**Decision:** Even if the observed RED occurs, review-only; no merge/release approval or commerce claims. If the result is unexpectedly safe, record the actual behavior and avoid tuning a fixture to obtain RED.
