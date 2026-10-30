# Capital recycling continuation 019

## Decision

**Do not adopt this mechanism as operational current-Account recycling.**

The small matched positive-demand experiment shows a large conditional benefit
inside a PR24-derived native-ledger extension. It also finds the decisive
integration failure: the extension is rejected when given the current adaptive
manifest because it does not enter through the mandatory owned `Account`
facade, and its audit is not `audit_account`. Treating it as operational would
therefore create the parallel, unauthenticated operating path the mandate
forbids.

The code is a prospective support candidate, not a release gate or merge
request. It preserves the permanent-contract baseline and old histories.
It makes no claim of legal finality, a real insurer, provider solvency, actual
buyer demand, actual commerce, or paid frontier-model execution.

## Exact source and ownership

- Parent support commit: `ee6742725c68bf7bea5bb3cb2ed91c4fd5a1164e`.
- PR24 input: `97c790ae681779deca53e8ddc8c6dc3b6841bfc6`;
  exact `enterprise/contract012.py` Git blob
  `204d443f06757220b739438f813b7ca48fe5a3e7`.
- Observed PR28 head at the execution boundary:
  `d1a7b41779ae4ee2f00402bef11e5ae931200ba6`.
- The canonical integration owner remains task
  `01a18e41-da6b-764d-8a13-d6e9a0b5c0f5`. No checkout, account, key, proof,
  budget, or release authority was inherited.
- This checkpoint is isolated to new files and fresh temporary simulation
  accounts. It launches no hosted CI and changes no release candidate.

At 22:57 UTC PR28 was open/unmerged, merge state `unstable`, with ten unresolved
review threads. Eight exact-head checks had succeeded, one
(`adaptive-current`) remained in progress, and publication jobs were skipped.
No qualified completion015 release existed. A green subset is not a release.

## Treatment and model

All matched arms have $500 simulated opening cash, $100 working capital, the
same 20 authored opportunities, the same $200 offer, and the same accepted
synthetic `reconciliation-000` output. No top-up occurs. The permanent arm
retains price plus $0.20 forever. The prospective central arm charges:

- $5 arrangement cost and $1 premium per attempted covered order;
- $40 production/full modeled delivery cost;
- two-hour finite primary claim window and three-hour residual window;
- 80% modeled cover;
- 5% deductible, 2.5% exclusion, 2.5% payout-gap, 5% modeled provider-default
  severity on covered exposure, and 5% correlated-dispute exposure.

At maturity, the full permanent tail and a computed residual reservation change
in one native SQLite transaction. If current unrestricted earned cash cannot
fund the residual, the transaction rolls back and the permanent tail remains.
Subsequent delivery commitments reserve native `unrestrictedEarned` before
expense. One central late claim consumes half its reserved gap; unused gaps
release only after the residual window.

The 160-job/20-family catalogue and 12 reference bundles are read from the
existing repository files. No catalogue job is represented as executed: the
actual executed fixture is the accepted deterministic service output above.
The four-segment/two-tier counts supplied in the mandate are not fields in these
two JSON manifests and remain an explicitly labeled mandate assertion.

## Results

Amounts below are simulated USD, converted from exact integer microUSD.

| Arm | Settled | Refunds | No purchase | Nonpayment | Prior-earned commitments | Profit | Available | Tail/residual outstanding | Stop |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| permanent | 4 | 0 | 0 | 0 | 3 | $600.000 | $199.200 | $800.800 | buyer collateral unavailable on next attempt |
| prospective central | 17 | 1 | 0 | 2 | 17 | $2,637.981 | $3,037.981 | $0 | none |
| high premium ($80/order) | 1 | 0 | 0 | 0 | 0 | $75.000 | $475.000 | $0 | no audited earned cash for next commitment |
| high friction ($30) | 0 | 0 | 20 | 0 | 0 | -$5.000 | $395.000 | $0 | none; buyers decline |
| full provider default severity | 0 | 0 | 0 | 0 | 0 | $154.000 | $353.800 | $200.200 | residual reserve unavailable; permanent tail preserved |
| fully correlated dispute | 0 | 0 | 0 | 0 | 0 | $154.000 | $353.800 | $200.200 | residual reserve unavailable; permanent tail preserved |

Central conditional difference: **+13 settled outcomes and +$2,037.981 modeled
profit** versus the permanent arm. This is causal only for the authored matched
opportunities and treatment bundle. It is not measured external demand or an
Account-qualified enterprise result.

The central capital identity is:

`cash = $500 seed + $3,400 collections - $762.019 paid complete costs = $3,137.981`

`available = $3,137.981 cash - $100 working - $0 payables - $0 custody - $0 tail - $0 active residual = $3,037.981`

The permanent identity is:

`available = $1,100 cash - $100 working - $800.800 permanent tail = $199.200`

The independent compact verifier checked six arms, 23 funding-lineage records,
profit/cash/available identities, reservation-before-spend witnesses, claim
bounds, failure-region tail preservation, restart equality, competing-writer
refusal, and replay audit. It is separate code by the same author/model/host,
not external certification.

## Reproduce

From this exact source:

```sh
python3 continuation/capital-recycling-019/run_bounded.py \\
  --name prepare-reproduction --cwd "$PWD" \\
  env PYTHONPATH=. python3 continuation/capital-recycling-019/prepare.py

python3 continuation/capital-recycling-019/run_bounded.py \\
  --name matched-reproduction --cwd "$PWD" \\
  env PYTHONPATH=. python3 continuation/capital-recycling-019/run_experiment.py

python3 continuation/capital-recycling-019/run_bounded.py \\
  --name verify-reproduction --cwd "$PWD" \\
  env PYTHONPATH=. python3 continuation/capital-recycling-019/verify.py
```

Use a fresh allocation and fresh output names; the published allocation is not
reusable authority.

## Resource reconciliation

The prospective cap was 180 total waited-child CPU seconds, 1,800 wall seconds,
768 MiB task memory, 64 MiB added disk, 12 MiB decoded retrieval, one active
job, per-job 60 CPU/60 wall seconds on one processor, and $0 external cost.

Metered jobs used **6.885532 CPU seconds**. Maximum waited-child RSS was
34,044 KiB; maximum observed workspace bytes were 1,848,013. Decoded source
retrieval remained below 12 MiB. All attempts were serialized by the
prelaunch lock. Preparation, connector, orchestration, and host billing are
unmetered and not inferred to be zero. The preserved failures are in
`FAILURES.md`, their logs, and `RESOURCES.jsonl`.

## Four separate completion states

1. **Safe qualified release — open.** PR28 remains open/unmerged; ten threads
   unresolved and one exact-head check running at the boundary. No release or
   downloaded-release operation was performed here.
2. **Operational earned-capital recycling — open; candidate declined.** The
   PR24-derived economics are favorable centrally, but the current mandatory
   Account/authenticated-audit boundary rejects this extension. It is not
   adopted.
3. **Joint C/K policy — open.** This is not C0K0/C1K0/C0K1/C1K1 and changes no
   joint-policy decision.
4. **Scale horizon/failure region — prior reconciliation retained.** The
   exposed PR23 replay remains 480 worlds, 21,952 annual intervals, and zero
   $3B trailing-year modeled-profit crossings by month 60. It was not rerun.

## Smallest next discriminating action

Under a new explicit allocation, integrate the finite/risk transition as an
opt-in operation of the existing adaptive `Account`, including HMAC
authorization, obligation-aware finish/claim resolution, `audit_account`
reconstruction, idempotent crash recovery, and native competing-writer tests.
Then rerun this frozen matched cohort. If that Account-native candidate cannot
preserve the same identities and rollback behavior, retain the permanent
baseline.
