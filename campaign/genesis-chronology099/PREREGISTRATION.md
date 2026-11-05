# GENESIS099 — prospective canonical cost-chronology regression

Frozen source: `3507d556387649008698c354e57917fd3fd1d1f6` (PR #233), before writing test code.
Historical falsifier: PR #235 at `fadfe8f40f9149b30be9859999391aff4d2bf2ea`; its original C1 **passed an incorrect hour** under its earlier parent `895166b...`. Preserve that observation and its full hosted results. GENESIS099 is *repair qualification*, not new independent economic evidence or a replacement of historical trials.

Test source under existing canonical JournalAccount/BusinessAccount, on wholly disposable temporary local simulated accounts. Never touch the active P0 account, operator signer, private recovery material or already frozen histories.

Fixed tests, exact source and stopping rule:
- A: unmodified protocol; all overhead amounts/days/cardinality and canonical native audit must accept.
- B: first acquisition amount unchanged, posted hour 23 instead of registered hour 24 through genuine `BusinessAccount.cost`; injection must occur once; canonical native audit must reject with `REGISTERED_FIXED_COST_CHANGED`.
- C: first maintenance entry omitted through producer-call interception, with other native actions unchanged; canonical native audit must reject `REGISTERED_FIXED_COST_CHANGED`.
- D: buyer declines under the original protocol except `offer.value = 0`; zero collections, full acquisition/maintenance incurred at registered hours, canonical native audit must accept.

Run exactly once per fixed case. Do not resample, mutate amounts to win or accept sidecar witness as authority. `python -m unittest tests.test_genesis_cost_chronology099 -v`. This test-only branch is based on the **owner's prospective fix**; the owning PR #233 is not modified or merged by this work. If any fails, preserve failure and diagnose separately. Evidence from exact-head CI may count as software qualification only, not public release/download, actual commerce, P0 migration or US$3 billion T365 profit.

Owner of canonical finance changes: PR #233; this branch adds only the regression test and this preregistration, with no competing financial writer. Do not merge the research branch wholesale to main.
