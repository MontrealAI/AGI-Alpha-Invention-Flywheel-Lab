# Transition162 — preregistered cross-operation source-epoch race

**Owner:** independent, test-only P0 reviewer. **Parent:** separately owned PR #40 exact source `ced6c1cb004887dcdafaea59a2976020be649f8e`. **Date:** 2026-11-14. **Integration:** NONE. This research branch must not be merged into main or rewritten into a passing result while an authentic safety failure remains.

## Distinct falsifiable question

Transitions154 and155 already report conflicts between *two prepare calls*. This test instead interleaves the canonical `operations.operate` and `operations.prepare_upgrade` on one prior OPERATOR descriptor and the **same** old checkpoint. Can an operating caller select the old source and start `run_world`, then a distinct caller successfully prepare and publish the new source descriptor while the first old-source operation remains active?

**Fixed schedule (one case, no seed search):**
1. Start from a synthetic old-source operator with `business_dir='.'`, no pending request, matching manifest and one synthetic STATE.
2. Let `operate` read and accept the old descriptor; stop it immediately before its mocked `run_world` body.
3. Invoke the actual public `prepare_upgrade` flow for a distinct new source and policy against that unchanged prior checkpoint; capture whether it returns a newly prepared descriptor.
4. Let the prior `operate` caller return from its mocked run. Require that the two incompatible successes **cannot both** occur; the accepted alternative is a source-bound exclusive-writer refusal or a documented reconciliation before both claims can be made.

## Preserved evidence / limits

This is a **source-control-plane** schedule only. Synthetic STATE is deliberately not HMAC-authenticated. Signer, ticket checking, source identity/source copy and actual `run_world` work are mocked; `read_operator`, old-source descriptor selection, public `operate` source selection, `prepare_upgrade` sequencing, history/descriptor writing and pending-upgrade validation are real owner code. An observed double acceptance does **not** prove real account corruption, money loss or a live signer takeover. It does prove that these two public control paths do not visibly enforce a shared operation/prepare exclusion for this registered schedule. Conversely, a pass would not qualify genuine HMAC, JournalAccount, crash recovery, maturation, nonempty operating queue migration or original private-account ownership.

No financial implementation, original account, key, queue, historical evidence, release guard or owner branch is modified. The test writes only into a transient synthetic fixture. Running the regression on the frozen owner source is independent review, not acquisition of owner authority.

**Required owner-side repair if red:** one canonical account/source writer lease across operate, prepare, upgrade, native mutations and terminal resume, with revalidation of the signed checkpoint/counter and pending authorization under that lease. Keep already failed T154/T155 red evidence immutable. Source-matched HMAC, queue, crash/replay/fork and current-main composition qualification remain mandatory.

**Commercial status:** No real buyer, collection, producer output or profit; US$3B T365 target unqualified. No spending, paid models, outreach, external transaction, deployment or credential activity.
