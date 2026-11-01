# Native market indexing 049 — scale execution without changing the business game

## Delivered code

The main native engine repeatedly revalidated the entire customer request map while initializing every buyer, constructing offers and independently auditing decisions. `_offer_menu` also scanned the entire service inventory for every customer's request. This change validates a detached immutable profile snapshot once per operation/audit and uses the existing admitted job dictionary for request-ID lookup. Every current policy is still fully validated, outputs are detached, no process-global cache is introduced, and final native audits remain independent of producer receipts. A malformed admitted job index fails closed.

No cash, prices, buyer values, channel rights, opening capital, service acceptance, expense envelopes, paid-action permissions or default strategy changes. This is an execution optimization, not an invention or economic-uplift claim. It is separate from the active customer-access contract repair described on PR93 and from PR95's cooperation qualification repair. Compose overlapping source hunks deliberately; do not replace newer owner files wholesale.

Base: `7333cb483a9fb261177e89a094f72ab896aab82c`. Local tested canonical source: `56d98e075776be4f8274b85aa87a1375c149af0782c5967920d91163acd0520b` (227 members). Driver SHA256: `14b7b0c9d7c8ef974a2cbe84b4068d2179d0d13af40dd39547dcc90fcd9d7716`.

## Executed local evidence

57 selected tests passed, including 26 new tests, native complete-outcome production/acceptance and four independently rejected tamper cases. Initial test development used an invalid below-minimum inventory; that one failed test was corrected to use the existing minimum32 without changing the guard. The original failure is not a pass. Full exact-head hosted qualification is separate.

A fixed source-bound driver executed BOTH original and optimized implementations, with exactly US$100,000 simulated capital per independent account. The same seeds, terms, work inventory, buyer alternatives, allowed actions and expense envelopes were used inside each pair. All four completed worlds passed the native auditor. Financial, customer, channel, cost, decision, order and artifact semantic projections are exactly equal between implementations; source-specific signatures are not claimed byte-identical.

| Authored native case | Original profit | Optimized profit | Paid orders / paying customers | Paying customers acquired through paid channels |
|---|---:|---:|---:|---:|
| 4 buyers,4 days | -$35.45 | -$35.45 | 1 / 1 | 0 |
| 48 prospects,21 days | $249.80 | $249.80 | 11 / 10 | 7 |

The larger case records28 paid-channel exposures, $53.50 channel invoices, $550 collections and $300.20 total modeled expenses. Thus paid acquisition beyond the initial four is executed in this coherently configured example. That result is NOT caused by this optimization: the original implementation gets the identical result. It also does not retroactively repair the PR93 experiment's owned-audience mismatch. The small case remains a loss.

Native performance evidence is separate: local CPU microbenchmarks returned identical outputs, with4096-buyer initialization falling from16.2519s to0.08234s (~197x), and64 requested-job lookups in32768 inventory entries falling from2.68398s to0.02897s (~93x). These are single-environment microbenchmarks, NOT total-enterprise speedups, measured monetary savings or profit improvements. One local larger-world invocation hit the tool deadline and continued the same original account; interrupted-process CPU is unavailable, so no end-to-end speedup is claimed.

Local runtime: Python3.13.5 / cryptography46.0.4. Hosted qualification uses the pinned Python3.12 / cryptography50.0.2 environment. Market values, costs, 100% arrivals/retention and zero nonpayment in this performance fixture are authored assumptions, not calibration. Actual host/model/developer billing remains unknown. No actual customers, real payments, external outreach, paid inference, improved inventor, annual profit milestone or physical expansion is established.

## Reproduce

Use a clean checkout with the pinned dependencies. Run the same driver against the pinned base and candidate in separate worktrees; copying the driver into the base does not modify the canonical operating source inventory. The hosted workflow does this explicitly.

```sh
python -m unittest tests.test_connected_market_index049 -v
python scripts/qualify_market_index049.py run --case small --output /absolute/new/small049 --max-events 1000
python scripts/qualify_market_index049.py verify --case small --output /absolute/new/small049
python scripts/qualify_market_index049.py run --case acquisition --output /absolute/new/acquisition049 --max-events 1000
python scripts/qualify_market_index049.py verify --case acquisition --output /absolute/new/acquisition049
```

A `run` on an existing registered output resumes its original account only if source, driver, protocol and configuration still match. Do not copy balances or delete liabilities. Keep private account/recovery state and synthetic signing keys private. Publish only `PUBLIC.json` or an explicit summary; `SEMANTICS.json` is a local comparison input, not an authority. Source registration is not release qualification. The new experiment driver is repository tooling, outside the selective runtime source inventory; its separate hash is recorded in every registration.

Normal review, all applicable exact-source checks, coherent integration, release publication and downloaded operation remain required. US$3 billion trailing-365-day profit remains the commercial objective, not an achievement or a throughput-test threshold.
