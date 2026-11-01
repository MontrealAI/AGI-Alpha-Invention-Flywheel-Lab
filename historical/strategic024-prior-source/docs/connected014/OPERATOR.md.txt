# Connected enterprise 014 operator guide

## Configurable operator increment (overnight022)

The additive interface below uses the same `run_world`, mandatory adaptive
`Account`, `JournalAccount`, signed checkpoint and native ledger. It does not
adopt the separate capital candidate, migrate a legacy account, shorten permanent
tails, or qualify prospective maturity. The active financial integration owner
retains that work. Existing `run --smoke`, default `run`, `resume`, `audit`, and
`package` behavior remains available.

Register a complete finite input before creating accounts:

```sh
python3 -m connected_enterprise register --config campaign/overnight-022/OPERATOR_INPUT.json --output /absolute/new/enterprise022
python3 -m connected_enterprise operate --output /absolute/new/enterprise022 --max-events 4
python3 -m connected_enterprise resume --output /absolute/new/enterprise022
python3 -m connected_enterprise audit --output /absolute/new/enterprise022
python3 -m connected_enterprise comparison --output /absolute/new/enterprise022 --control baseline --candidate growth
python3 -m connected_enterprise scoreboard --output /absolute/new/enterprise022
```

`register` creates a source/configuration freeze, not funded accounts. The input
is copied into the frozen source under its SHA256 content address; its exact
protocol, cases, seeds, service cohort and complete cost configurations are bound
to that source. Inputs require an explicit evidence role (`development`,
`reproduction`, or `finite_authored_comparison`). This label does not certify fresh
holdouts or empirical demand. Existing completion thresholds and financial guards
cannot be weakened through this input.

`operate` executes from that frozen source. `--max-events N` stops after at most
N additional operating events **per business**, retaining the original nonempty
queues, native action tapes and private simulation keys. It is an optional
checkpoint step, not a CPU allocation or a changed scientific horizon. Omitting
the option drains the registered finite run. A paused operation reports
`complete: false`, writes per-world `STATE.json`/`RESULT.json` and `PROGRESS.json`,
and does not emit `COMPLETE.json`. `resume` continues those same accounts. Retain
the whole private output; never copy a balance or regenerate a key.

`comparison` audits the completed operation with its frozen source before
comparing registered control/candidate arms. It uses existing matched native
records; it does not start new worlds. No accounts are pooled. This baseline vs
growth comparison estimates the specified expansion-policy difference under
unchanged permanent terms; it does **not** isolate prospective maturity or the
recycling toggle in the separate capital experiment. Invalid or unregistered
arms, tampered source/configuration, duplicate JSON fields and incomplete output
fail with a nonzero exit and an explicit error. Missing private account authority
blocks operation/resume; a key-free public copy still supports audit.

`scoreboard` is read-only and opens no account. It verifies the recorded package,
source and result bindings and reconciles native event arithmetic before
displaying separate businesses, daily/cohort growth records, costs, cash,
recognized profit, reserves and obligations. Stored audit receipts are labeled
recorded receipts; this display cannot replace `audit` or authorize spending.
Unmeasured host/frontier billing, retention fractions, causal investment returns
and short-horizon trailing-year profit remain `null`. Attributed asset use is
nonadditive. The example is a declared 49-day engineering reproduction with
permanent liabilities, not a fresh commercial or annual-profit confirmation.

For local command resource receipts, including reaped child CPU:

```sh
python3 scripts/measure_overnight022.py --receipt /absolute/new/operate022.json -- python3 -m connected_enterprise operate --output /absolute/new/enterprise022
```

Receipts measure command resources, not model billing or the entire chat session.
Use a new receipt path for each command, retaining failed jobs and their logs.

## Current default: completion015

The current default is the separately registered completion015 comparison in
`campaign/completion-015/PREREGISTRATION.json`: eight separate simulated businesses
over 70 days, comparing retained earned-financed expansion with the owned fixed
baseline. Two central pairs and one pair in each of two adverse regions are fixed
before execution. The 70-day horizon covers acquisition and capacity activation,
21-day expiry, renewal, repeat purchase and collection cycles. No future revenue
or copied balance finances a commitment. The historical confirmation002 and
expansion001 registrations below retain their original source and identities.

The same `run`, `resume`, `audit` and `package` commands operate this edition.
`--smoke` remains an engineering check with separate exposed seeds. Public release
reproduction repeats the default and is labeled reproduction. Source publication
alone does not assert a completed commercial result.

Unsafe native investment cancellation is retired. Interrupted reservations resume
and resolve incurred work and obligations through source-bound completion.
Legacy cancelled accounts fail closed at independent audit and reopen. Connected
journals must cover native history completely in causal order. Direct native
mutations are not an additional supported operating interface.

Central setup/development/search/qualification is a once-per-enterprise USD75
envelope, plus USD0.10 daily maintenance and itemized variable costs. The adverse
complete-cost case raises setup to USD500, production to three times central and
channel prices to ten times central, alongside delayed collection and failures.
These are conditional envelopes; actual host/model billing is unknown.

The current owner mandate authorizes normal qualified merges and release
publication using existing resources. Repository protections, valid findings and
genuinely required action-time approvals remain binding. Historical readiness
restrictions do not replace current authority.

This path operates a **simulated** enterprise using deterministic service production, independent artifact checks, the existing owned native account, paid channel and capacity contracts, and an event clock. It makes no paid model calls, contacts no customers and moves no real money. Buyer demand, provider terms, resource costs and human-service comparisons are authored assumptions. A successful engineering run does not establish empirical demand or a billion-dollar business.

The current allocation and ownership are in [`campaign/connected-014/ALLOCATION.json`](../../campaign/connected-014/ALLOCATION.json). Historical allocations are separate. Read the current source-bound experiment protocol and result receipts before interpreting a commercial verdict. This guide describes interfaces; it does not certify an unexecuted test, confirmation run, hosted workflow, merge or release.

## Environment and paths

Use Python 3.12 and a supported local POSIX filesystem with exclusive writer locks. Network/distributed filesystems and hostile filesystem custody are outside the account-safety claim. The pinned runtime dependencies are in [`requirements-commercial010.txt`](../../requirements-commercial010.txt):

```sh
python3 -m pip install -r requirements-commercial010.txt
```

Use a clean, reviewable source tree and **new, normalized absolute paths**. Replace the example `/tmp` directories with durable private storage for continued operation. Do not reuse a previous output path for a fresh run. The runner freezes its selected source bytes, protocol and configurations into the output before launching the frozen copy. A clean extracted source tree does not need `.git`; its source hash remains authoritative and its Git commit field can be `null`.

## Start, inspect and audit

From the repository root, run a short development qualification:

```sh
python3 -m connected_enterprise run --smoke --output /tmp/connected014-smoke-NEW
```

The separately declared full finite experiment uses:

```sh
python3 -m connected_enterprise run --output /tmp/connected014-confirmation-NEW
```

Choose the full experiment only within a fresh allocation sufficient to finish, independently audit and publish it. Development smoke seeds are excluded from confirmation. A resume continues the same business; starting a new output directory creates separate businesses with explicit separate seed allocations. Earned balances must never be copied between them.

Inspect `FROZEN.json` for source/configuration identity; `PROGRESS.json` for completed tasks; `REPORT.json` for the three separate outcomes, matched comparisons, conditional frontier and next action; and `COMPLETE.json` for completion binding. Each `worlds/<task>/` directory contains `STATE.json`, `RESULT.json`, `AUDIT.json`, `GROWTH.json` and private native-account recovery files. A producer verdict or the existence of `COMPLETE.json` does not replace independent audit.

Run the audit using that output's frozen source:

```sh
cd /tmp/connected014-confirmation-NEW/source
python3 -m connected_enterprise audit --output /tmp/connected014-confirmation-NEW
```

Require exit status zero and an accepted `PACKAGE_AUDIT.json` with the expected source hash, task coverage and declared scope. Preserve failures and disagreements; do not rewrite financial records, source bindings or acceptance flags to make an audit pass. Source changes require a distinct newly frozen experiment, and exposed evidence must not be presented as untouched confirmation.

## Resume the same accounts

After an interruption, stop competing writers and resume the **original output directory** from its frozen source:

```sh
cd /tmp/connected014-confirmation-NEW/source
python3 -m connected_enterprise resume --output /tmp/connected014-confirmation-NEW
python3 -m connected_enterprise audit --output /tmp/connected014-confirmation-NEW
```

The saved event intent, native action tape and signed command journal determine whether a mutation already committed. Recovery must acknowledge that same commitment rather than spend twice, invent a receipt, advance the clock or reseed the account. Completed tasks may be revisited to reconstruct reports; same-account financial actions must remain unchanged. Retain all original state until the recovered run passes independent audit.

A private backup must preserve the **whole output directory after its writers have stopped**, including:

- `STATE.json` and frozen source/configuration/manifest files;
- `account.sqlite.actions.jsonl` and `account.sqlite.persistence.json`, plus the native checkpoint and any existing sidecars;
- `account.sqlite.connected-journal.json`, adaptive proofs and obligation resolutions;
- `account.sqlite.adaptive-simulation-key`, with private permissions retained.

The native action tape is recovery authority; a loose SQLite checkpoint alone is not. The local simulation key authenticates existing account commitments and is not an API credential. Do not publish it, regenerate it for an existing account or use a retired raw account interface to bypass ownership. Missing or mismatched recovery authority is a genuine boundary: preserve the account and record the limitation. A separately registered fresh experiment may proceed with its own seed; it does not recover the old business.

## Publish a key-free evidence package

Keep private recovery backups separate from public audit exports. After a completed accepted audit:

```sh
cd /tmp/connected014-confirmation-NEW/source
python3 -m connected_enterprise package --output /tmp/connected014-confirmation-NEW --archive /tmp/connected014-public-NEW.zip
python3 -m zipfile -t /tmp/connected014-public-NEW.zip
python3 -m zipfile -e /tmp/connected014-public-NEW.zip /tmp/connected014-public-extracted-NEW
cd /tmp/connected014-public-extracted-NEW/source
python3 -m connected_enterprise audit --output /tmp/connected014-public-extracted-NEW
```

Record the archive's SHA256 and byte size, extracted source hash, command exit statuses and audit receipt. Public exports omit local signing keys and SQLite account state. They retain source-bound evidence for independent financial/operating checks and fresh reproduction. **A key-free export is not permission or sufficient authority to resume/take over its original accounts.** To reproduce from exported source, use `run` with a new absolute output directory and identify it as a separate simulation.

The clean-distribution qualifier builds a bounded source ZIP, extracts it without `.git`, starts smoke worlds, resumes completed original accounts, compares native financial records, audits them, exports a key-free package and audits its extracted public copy:

```sh
python3 scripts/qualify_connected014.py --smoke --output /tmp/connected014-clean-NEW --timeout-seconds 1200
```

It writes `QUALIFICATION.json`, source/public ZIP hashes and command logs, including failure receipts. Require `accepted: true` and the intended source hash. Smoke qualification is engineering evidence, not a new commercial confirmation. To qualify exact committed source, first commit the reviewed source and invoke the qualifier from a clean checkout of that commit; compare its reported source hash with the frozen confirmation hash. Do not rename a pre-freeze smoke run as final qualification.

## Financial definitions

All native amounts are integer **micro-USD**: divide by 1,000,000 for displayed USD. Native `day` fields carry integer **hours** in this edition. Production, independent acceptance, clearing, channel activation and expiry occur at their scheduled event times; a monthly reporting bin grants no spending authority.

| Record | Meaning |
| --- | --- |
| Seed/opening capital | Explicit initial funding; not revenue or earned funds. |
| Recognized `revenue` | Native assured release revenue net of contra-revenue; acceptance alone is not recognition. |
| `collections` | Cleared simulated customer collections net of paid reversals; an offer or forecast is not collection. |
| Receivables | Independently prepared/verified invoices awaiting native release; not spendable cash. |
| `expenses` | Incurred complete modeled costs, including failed/unused acquisition and resource contracts. |
| `expensePaid` / `payables` | Cash-paid expenses versus incurred unpaid/refund obligations. |
| `profit` | Revenue plus recovery income minus incurred expenses; not automatically available cash. |
| `cash` | Seed plus collections/recovery minus actual native cash outflows. |
| Custody/tail reserves | Protected buyer custody and retained principal-plus-fee reversal exposure; obligations remain after a sale. |
| Working capital / reserved investment | Declared working buffer and atomically committed investment funds. |
| `available` | Cash after protected obligations, reserves and commitments. |
| `unrestrictedEarned` | Audited available earnings that can finance another qualified investment; excludes uncollected forecasts and seed as earnings. |
| Equity/earned protection backing | Which funding source covers protections; seed-backed reserves are disclosed separately. |

Acquisition and capacity contracts include prepaid declared support; later invoices cannot silently disappear. Successful and unsuccessful outreach, onboarding, service resources, verification, maintenance, development/failed search, payment fees and tax provision enter modeled costs. Actual host/model billing that is unavailable stays explicitly enveloped or unknown. The deterministic executors do not establish measured frontier-model costs, human delivery times or market conversion. Human-service estimates are commercial reference assumptions, not guaranteed buyer willingness to pay.

## Operating and growth limits

The initial service cohort and customer population are finite. Contact slots are potential access, never automatic orders; overlapping audiences, failed access, contact fatigue, lead time, expiry, refusal, shared budgets, supplier interruption, payment delays and refunds can reduce returns. The policy may keep cash or decline work. Purchases require native available funds and current-state authorized reservations; future earnings cannot fund them.

Read each investment's source plan, funding receipt, activation/expiry, subsequent accepted/settled orders and attributed contribution together. Attributed revenue alone does not establish causal incremental profit; matched controls and complete enterprise costs are separate evidence. Conditional success fractions describe finite authored cases rather than calibrated probabilities.

`GROWTH.json` aggregates actual native events with a declared UTC epoch and trailing-365-day collection windows. An annualized short-horizon rate or trailing-12-month-bin result is not the same metric. This short finite enterprise cannot establish billion-dollar native scale. Older adaptive012 and paid-distribution billion-dollar projections retain their own capital, demand and channel assumptions; do not mix their fastest milestones into this account's earnings or forecasts.

The source-distribution and audit commands are local engineering operations. Publication, formal approval, merge, release, paid resources, outreach, real financial actions and deployment remain subject to their separate authorization boundaries.

## Replacement confirmation002

The default registered run compares retained growth with competitive growth under four central matched seeds and two seeds across three adverse cases (20separate businesses). Competitive growth pays5USD once for the pricing extension and0.05USD per offered quote, including declined offers. Prices use only public rival quotes and prior Boolean own-offer outcomes, with a fee-inclusive resource floor plus1USD direct contribution. Equal-utility buyer choices use a stable neutral draw for both arms. Source001 remains an explicitly incomplete checkpoint after a causal trace-order rejection; no source001seed or balance is reused as new confirmation. The smoke route remains a small baseline/growth engineering check. All native large revenue milestones remain separate from historical aggregate projections.
