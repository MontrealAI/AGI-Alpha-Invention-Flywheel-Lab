# Investment cancellation retirement

Review: [PR #22 discussion_r4427015349](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/22#discussion_r4427015349).

The original defect is reproduced on source `b60eb7018fc7090ff3d7876c7b4e6b87a5e86922` in `COUNTEREXAMPLE.before.json`. A delivery advanced through native `prepare`, with a $13.70 reservation covering $10.00 production and $3.70 later costs. `Account.execute('cancel_investment', ...)` released the entire $13.70 reservation. Expenses remained at the earlier unrelated $10.00, and `account.audit()` accepted the history. These are development counterexample receipts, not a commercial result.

The adaptive account now retires `cancel_investment` completely. Execution, direct public account audit, public export and account reopen reject such histories. This covers cancellation before work as well as cancellation after costs or native preparation; the facade cannot infer that an external production commitment is costless. Pending safe work retains its reservation and can resume through source-bound obligation reconciliation and `finish`. Previously cancelled histories must be quarantined for explicit reconciliation; they cannot silently resume as qualified accounts. The lower-level generic exchange remains available for preserved non-adaptive historical experiments and for constructing adversarial legacy input to tests; it cannot qualify an adopted adaptive account.

Regression coverage includes before-work cancellation; funded partial and prepared work; duplicate, unknown and stale requests; requests after finish; restart and abrupt process exit with prepared obligations; and syntactically valid legacy native cancellation histories supplied directly to the auditor or reopened as accounts. The prior counterexample remains in the test through a deliberate private lower-level bypass, which the public adaptive facade refuses.

Validation:

```sh
python3 -m unittest tests.test_adaptive_cancellation tests.test_adaptive_account -v
python3 verification/scan_adaptive_cancellation_history.py --output /tmp/cancellation-history.json
```

`REGRESSIONS.log` records the 26 passing focused tests. `HISTORICAL_SCAN.json` checks all 20 original archive parts and the exact archive SHA-256 `29aaa1e6ec81b145753550b3394c1684f503f804e8bc565af404d13e8d92be34`, then records every inspected world's original compressed hash and action digest. The 160 completed confirmation002 worlds contain 57,948 actions and **zero** investment cancellations. The 13 completed worlds in the preserved incomplete confirmation001 contain 5,159 actions and **zero** investment cancellations. This specific defect therefore did not affect those published trajectories; their original bytes and verdicts remain preserved. The scan is not a new operating replay and does not complete confirmation001 or qualify new growth results.

For exact reproduction of the original counterexample, create an isolated checkout at the original source above, copy `probe_before.py` into it, and run `PYTHONPATH=. python3 probe_before.py`. The repaired current source is expected to reject that probe at cancellation.
