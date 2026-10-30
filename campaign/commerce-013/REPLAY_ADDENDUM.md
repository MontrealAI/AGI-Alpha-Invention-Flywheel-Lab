# Commerce 013 — clean reconstruction of all protected native accounts

This addendum strengthens reproducibility **without modifying the already executed candidate, protected decision, results, original source or tests**. It does not retune the business policy or add market evidence.

The original `SERVICE_MANIFEST.json` includes the exact (nondeterministic) construction CPU receipt from the initial authored synthetic packet build. It was source-bound to the saved FROZEN manifest identity before any confirmation was run. The deterministic service source supplies every underlying input, artifact and independent acceptance receipt. The replay utility reconstructs all these files into the same recorded relative paths in a clean checkout, compares every meaningful manifest field except the new local CPU receipt, then uses the **original recorded manifest** when replaying the native ledger. This avoids rehashing earlier evidence.

## Verified from a clean source reconstruction

1. Copied only the scoped source packages, tests and published commerce013 evidence into a fresh working tree, excluding the original generated service files.
2. Ran `python -m commerce013.replay --seed 14013 --output NEW.json`. The utility restored 96 accepted work artifacts, three rejected probes and checked the exact frozen source hashes and manifest identity; all 10 protected native worlds for seed 14013 matched recorded source-bound action-tape digests, cash and service outcomes.
3. With the exact reconstructed service directory, independently reran `replay_seed` for all four protected seeds `14013`, `14017`, `14021`, `14027`. **40/40 protected native worlds matched their previously published full row records exactly.** Receipts are recorded as `REPLAY_<seed>.json`.
4. The clean reproduction ran the original 17 tests plus four new manifest/seed-contract tests: **21/21 PASS**.

No live acquisition, supplier receipt, paid provider, new customer, observed financial transaction or real revenue was involved. The simulated channel cost/resource economics and their negative stressed outcomes remain unchanged. Confirmation seeds were not used in the original two-seed development selection.

## Reproduction (clean repository)

```sh
python3 -m commerce013.replay --seed 14013 --output /tmp/commerce013-new-replay-receipt.json
python3 -m unittest discover -s tests -p 'test_commerce013*.py' -v
```

Run in a **clean unpacked repository** with the exact source identity recorded in `SOURCE_IDENTITIES.json`; the replay refuses to overwrite the previously reconstructed service fixture or output. For the remaining protected seeds, after source reconstruction call `commerce013.replay.replay_seed(ROOT, original_manifest, seed)` within a verified runtime. A production edition should expose an atomic resumable runner rather than use an environment-specific static working directory; this is a source-matched engineering reproduction.

**Business outcome:** The authored-weighted +$102.35 four-day simulated advantage and the adverse-family failures are unchanged. This finite synthetic exercise cannot establish a real market opportunity, a model-calibrated optimum, or time to any billion-dollar target. Actual customer/channel observations are the missing empirical input.
