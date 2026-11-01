# Selective prepaid refusal recourse

This opt-in policy uses the canonical `run_world`, `JournalAccount`, complete-offer allocator and independent native auditor. It does not change default or existing v1 fixed paid recourse.

```json
{"schema":"connected-selective-refusal-recourse/v2","daily_planning_cost":100000,"daily_evaluation_cost":10000}
```

Set this as `refusal_recourse_policy` in an otherwise valid complete-offer configuration. Values are positive integer microUSD. Daily evaluation is paid before evaluating public alternatives, including on hold days. The allowance is paid before any private buyer response only when its disclosed conditional benefit exceeds its fee. Current cash, obligations, operating bills, full capacity units and source-bound already-admitted offers constrain the allocator. Forecast value never becomes available funding.

The deliberately conservative heuristic examines the first planned quote's refusal branch. It admits only unique alternatives from customers outside the original selected basket and requires preservation of every other exact selected quote. Scenario-by-scenario rational weights multiply public refusal probability by the additional alternatives' costed net contributions. This avoids multiplying unrelated averages when uncertainty is correlated. Independence of separate buyer hypotheses remains an authored market-model assumption. A hold is possible even when a later refusal branch might be valuable; this is not a globally optimal retry policy.

The possible allowance fee is reserved in the planning envelope before purchase. On purchase the actual prepaid charge replaces that envelope deduction. On hold the conservative deduction expires with the planning event; it is neither an expense nor a permanent native reservation. The evaluator does not consult private buyer atoms or future responses. Already accepted deliveries and selected investments remain mandatory through the existing recourse allocator, which enforces work uniqueness, cash locks and weighted capacity. Unsupported authored allocation interactions remain rejected.

Named evaluation/allowance native costs are idempotent. If interrupted after allowance charging, recovery reconstructs the public prepayment snapshot from that same account's charged evaluation prefix and continues without reseeding or a duplicate charge. Independent auditing rederives the public choice, current native prefix, purchase or hold, all cost semantics, every response and the selected native effects. A policy label or certificate alone is not financial authority.

Run the finite comparison from the repository root:

```sh
python3 scripts/run_selective_recourse048.py --output /absolute/new/selective048
```

The driver freezes source, its own bytes and the preregistration before executing from that frozen copy. It runs the nine fixed worlds in `campaign/selective-recourse-048/PREREGISTRATION.json`: no recourse, fixed paid recourse and selective paid recourse, each in uncertain-demand, no-demand and no-alternative conditions. Each separate account starts with exactly US$100,000, runs 14 simulated days and drains its scheduled events. Repeating the command on the same output continues those original accounts under the frozen source and re-audits their saved histories. Keep the whole output private for recovery; only `SUMMARY.json` and compact source/protocol summaries are public evidence.

The cost envelope includes failed/unused evaluations, acquisition, production, maintenance, support, settlement fees, tax and startup development. Actual host/model/engineering billing remains unknown. Results are developer-authored synthetic engineering comparisons, not calibrated demand, actual commerce, a discovery advantage or an annual-profit result. Neither losing arms nor failed runs justify changing the preregistered seed or horizon.

Focused checks:

```sh
python3 -m unittest tests.test_refusal_recourse tests.test_connected_refusal_recourse tests.test_connected_finance tests.test_connected_temporal_boundaries -v
```

Retained lesson: separately averaged refusal and profit overvalued a correlated two-scenario alternative; scenario-wise multiplication fixes that counterexample. New claims still require the corresponding source-matched qualification and downloaded-release operation. Existing account/writer protection remains mandatory; no competing ledger or financial interface was introduced.


## Inspected fixed result

All nine registered worlds and a separate-process full native/operating re-audit accepted. Repeating the frozen driver preserved the native ledger and financial summary digest in each original account.

| Case | No recourse profit | Fixed paid profit | Selective paid profit | Paid deliveries per arm |
| --- | ---: | ---: | ---: | ---: |
| Uncertain demand | $51.000 | $49.800 | $49.680 | 4 / 4 / 4 |
| No demand | -$117.800 | -$119.200 | -$117.940 | 0 / 0 / 0 |
| No alternative | -$92.600 | -$94.000 | -$92.740 | 0 / 0 / 0 |

Selective bought all 14 allowances in uncertain demand and held on every day in the other two cases. Every selective account paid $0.14 evaluation. Avoiding the fixed fee helps in the hold cases, but no recourse wins all three comparisons after costs; no default promotion is justified. The no-alternative fixture's first considered buyer did not purchase; its negative result remains.

`RESULTS.json` binds these exposed authored results to the earlier exact 228-member comparison source `d0981cc06cb96682aadede96106f1391e452806add82cc4eedceb6df3759bee4`. The subsequent source adds explicit release inventory members and consumes authenticated exact win-probability fractions when supplied, falling back to the historical decimal display interpretation otherwise. A tiny positive refusal probability must survive a rounded display of 1. These later changes have focused regression evidence; they do not rename the earlier worlds as execution of the final integrated source. Full integration/release qualification is separate.
# Future sequence-window cash bounds

The sequence forecast includes known recourse fees for native planning events
strictly after its already prepaid current prefix, through the future decision
inclusive and before the terminal operating horizon. V1 reserves its mandatory
daily planning fee. V2 reserves its mandatory daily evaluation plus a declared
conservative upper bound for every optional future allowance; that bound does
not purchase allowances or charge native fees when the selective policy holds.

This fixed amount is deducted once per route from the full future cash bound,
alongside existing maintenance and contact costs. It is not multiplied by buyers,
profiles or public channel seeds. Mandatory fees are common costs before the
baseline comparison, so they can cancel from the incremental objective when
liquidity is ample. They still reduce actual prefunded delivery feasibility.
Metadata distinguishes mandatory expense from optional allowance cash protection.
No-policy forecast bytes are unchanged. Native funding, accounting, retry choice
and future reauthorization remain independent guards; this repairs a forecast
cash-bound omission, not an observed native overdraft.

`python3 -m unittest discover -s tests -p test_connected_sequence_recourse050.py -v`
checks clock boundaries, absent/invalid policies, the known-fee cash counterexample,
shared-cost cancellation and V1/V2 native audit, interruption, unchanged resume
and rejection of forged future-fee metadata.
