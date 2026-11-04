# Which native account and which year qualify?

Generic finance can correctly replay a signed account even when its opening capital, participants or obligations differ from the registered enterprise. These tests generated separate native accounts with the altered terms. Each witness used actual ledger transitions and separately called the portable operator audit.

| Question | Earlier result on `68eef71` | Corrected rule |
| --- | --- | --- |
| Did the enterprise use its registered funding and contract? | Six genuine V1–V4 histories initialized with altered capital, working reserve or contract passed portable audit. Completed live resume rejected each. | Compare the actual native configuration to the operator's registered opening, working reserve and contract before qualifying the year. |
| Did an affordable successor investment occur? | A V1 or V2 operator with $245.210 of unrestricted earnings could omit its required $50 day-325 investment and report $100.168 after tax instead of $60.168. A V3 operator could omit its $5 post-tax investment and report $137.576 instead of $132.576. | Determine eligibility from the ledger at the decision time, including available cash, unrestricted earnings and any applicable stop. Require the correct earned debit and checked productive work whenever eligible. |
| Does the revenue belong to the registered transaction? | On V1, substituting another buyer for the registered buyer on both the wallet and offer still qualified $99 of collections. Altered budgets, deadlines, event identifiers or an extra wallet also passed in the affected legacy versions. | Reconstruct the registered wallet, offers and ordered consent, funding, release or refund events with their exact arguments and dates. |
| Did V4 operate exactly its registered year? | A coherent missing $5 debit raised profit from $22.896 to $27.896. A wallet on day 365 and fabricated audit metadata also passed. | Reconstruct the ordered financial requests, funding source and realized completion. Decide the $5 successor after maintenance and modeled tax. Verify the audit record and detect unconsumed transactions. |

## Reproduce the counterexamples

Use Python 3.12 and the repository's pinned mechanism requirements. From the repository root, choose a new directory. This writes temporary synthetic accounts and compact per-case results.

```sh
set -eu
review=campaign/omega-economy-v4/review/registered-account-policy
python -B "$review/independent_omega_operator_suite.py" "$PWD" /absolute/new/operator-checks --workers 4
python -B -m unittest tests.test_omega_cart_native.RegisteredCartTimetable -v
```

The 19-case replay covers six incorrect configurations, three correctly funded controls, three improper omissions and seven changes to participant or transaction identity. The separate V4 suite covers financial order, the closing decision, funding labels and report identity. The [opening](OMEGA_CONFIG_INDEPENDENT_BEFORE.json), [successor](OMEGA_LEGACY_SUCCESSOR_INDEPENDENT_BEFORE.json) and [participant](OMEGA_MARKET_IDENTITIES_INDEPENDENT_BEFORE.json) witnesses preserve the earlier acceptances. The [configuration-only check](REGISTERED_NATIVE_CONFIG.json) and [V4 timetable-only check](V4_COMPANION_POLICY_REVIEW.json) record the intermediate source identities. The [combined replay](INDEPENDENT_OPERATOR_REPLAY.json) pins the three tested implementation files and all fixture results. Its `source_commit` names the checkout parent, `68eef71`. Its `source_files_sha256` identifies the corrected candidate bytes, which differ from that parent. Exact public-commit and release checks are recorded separately in the [integration history](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/206). The [preceding 332-test pass](RIVAL_HEAD_GATE.json) belongs to the earlier commit whose verifier admitted these cases.

All 19 adversarial and funded-control cases also matched on an intermediate candidate. Four original V2 assertions exposed a change in diagnostic precedence for invalid accounts. The final operator runs the established cost check first, preserving its missing-maintenance, tax and expense diagnoses. [Intermediate failures and corrected runtime identities](DIAGNOSTIC_PRECEDENCE.json).

## Did any published result use the wrong terms?

Read-only checks of the seven original V4, eight later V4 and ten distribution exports bound each actual initial state to its own source revision, $100,000 opening, zero working balance, contract and production manifest. The original primary had $148.048 of unrestricted earnings after its tax charge and $99,856.098 of available cash. It paid the required $5 successor charge. Seven V4 accounts funded a required successor and eight had zero eligible earnings. The ten distribution accounts faced a different dated policy. Their decision histories contained six required purchases and fourteen skips. All 25 closed on day 364 and their canonical audit results matched the archived reports or previously published audit receipts. [Account initialization by source](HISTORICAL_ACCOUNT_INITIALIZATION.json) · [Dated decisions and closing balances](HISTORICAL_DECISIONS_AND_CLOSE.json).

Historical replay requires the archived account exports and their exact source checkouts. The original check scripts are included for account custodians. `historical_cart_account_scope_check.py --help` lists the inputs for verifying public evidence against an existing archive. The decision and portable-audit scripts retain the layout of the original custody workspace. These checks inspect historical exports without acquiring writer authority. Current source belongs to new engineering runs. Preserve every existing account's pinned source and use [the recovery procedure](../../README.md#recovery-and-safe-operation) for authenticated local resume.
