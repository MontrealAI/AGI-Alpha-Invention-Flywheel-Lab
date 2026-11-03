# Omega guarded-prefix successor: unadopted engineering result

**The semantic gate passed; the preregistered performance gate failed.** All 50
qualification tests passed on the final attempt and every measured audit result
matched full replay. The one-job CPU median increased, so the verdict remains
`QUALIFIED_SEMANTICS_TIMING_TIE_OR_REGRESSION`. Do not describe this as a general
speedup, adopt it into the market experiment, or reinterpret earlier accounts.

## Candidate and scope

Base: `77cbb9f78390c67da6fd00f81d79c19bd5014e2a`. The isolated branch was
`experiment/omega-prefix-engineering-20261103`; the worktree was
`/workspace/scratch/e8834006b462/omega-prefix-engineering`.

`candidate.patch` contains one production change, admitting
`omega/native-product/v1` to the existing `JournalAccount._audit_incremental`
allowlist, and the new regression test. It adds no ledger or replay framework.
The main experiment and its registered accounts were untouched. The candidate
remains enabled only in its isolated engineering checkout; this package is a
reviewable research result, not adoption, merge, release, or released operation.

Existing owner/source/manifest guards, exact prior-action comparison, current
contract checks and historical delivered-output rebinding remain in force.
Public and reopen audits remain full. The final suite includes the existing
prefix and production suites, the complete existing market-product suite, and
eight new Omega tests. These exercise every-entry equivalence, tampered prior
actions and derived state, request/source/delivery changes, a delivery change
during auditing, outer-journal failure, independent public audits, cold reopen,
claim boundaries and earned-capacity limits. Inherited tests cover actual
artifact checking, consent, nonpayment, bundle refunds and interrupted release.
Independent read-only reviews found no additional blocking authority gap.

## Predeclared matched measurement

The protocol was hashed before execution. Each trace constructs real water-kit
artifacts, independently checks them, pays declared native fixture costs,
releases accepted orders, matures obligations and performs one earned-funded
engineering action. Both arms audit exactly the same exported prefixes, source,
manifest and delivered files. Each guarded pass starts cold. Two repetitions
use full/guarded then guarded/full order. Timing includes session construction
and final teardown. No measurements were collected before the final test gate.

| Useful jobs | Native actions / audited prefixes | Replay calls, full → guarded | Median wall seconds, full → guarded | Median own CPU seconds, full → guarded |
| --- | --- | --- | --- | --- |
| 1 | 15 / 15 | 106 → 15 | 0.524184 → 0.369188 | 0.294250 → 0.333817 |
| 3 | 41 / 41 | 821 → 41 | 2.838195 → 1.852977 | 2.482352 → 1.617609 |

The one-job CPU median increased **13.45%**. The three-job medians decreased
**34.71% wall** and **34.84% CPU**. The protocol required lower CPU and wall
medians at both sizes, so its performance condition failed. All paired
per-prefix audit outputs matched exactly. Raw repetitions and result digests
are in `RESULT_FINAL.json`.

This is a two-repeat, single-host, instrumented connected-audit comparison.
Other work shared the host; there was no exclusive CPU allocation. It does not
measure full business throughput, human effort, customer demand, or profit,
and it does not establish performance on the completed 500-plus-action runs.
Full-prefix hashing, source checks, job rebinding, journal checks and proof
validation still run. Trace construction was measured separately: 1.438 seconds
wall / 0.636 CPU for one job, and 3.905 wall / 3.292 CPU for three jobs. Benchmark
waited-child CPU was zero. Actual host/model billing remains unknown.

## Preserved failures and lessons

1. `RESULT_INITIAL.json`: 49/50 tests passed; the new test incorrectly expected
   a USD1 earned spend to be unavailable before maturity. Seed cash can cover
   reserves while leaving some earnings unrestricted. The corrected test uses
   actual unrestricted capacity, asserts positive accounting profit, rejects
   an unfunded action and verifies no postings. Native rules were unchanged.
2. `RESULT_CLAIM_FIXTURE_FAILURE.json`: 49/50 passed; the new fixture attempted
   to deny an ordinary claim. The native contract correctly permits that denial
   only for an unpaid disputed claim. The corrected fixture declares a disputed
   claim and retains the boundary/maturity/full-replay checks.

Both receipts retain `UNQUALIFIED_NO_PERFORMANCE_CLAIM` and an empty
`measurements` array. Neither attempt ran a benchmark. Before any measurement,
review also corrected a timer that excluded final guarded-session teardown.
No prior timing is presented or silently replaced. The three qualification
attempts together measured 185.002 seconds wall and 140.381 seconds own CPU;
these are engineering telemetry, not complete development cost or business
expenses. Disposable fixture accounts were closed. Private fixture sidecars are
excluded from this research package; copy only the files listed in `HASHES.json`.
No private keys or account recovery material belong in a public package.

## Reproduce in a separate checkout

Keep the package's reference receipts unchanged. From a checkout containing
this package, use a new absolute destination:

```bash
git worktree add --detach /absolute/new-omega-prefix 77cbb9f78390c67da6fd00f81d79c19bd5014e2a
cp -R campaign/omega-prefix-engineering-20261103 /absolute/new-omega-prefix/campaign/
cd /absolute/new-omega-prefix
git apply campaign/omega-prefix-engineering-20261103/candidate.patch
python3 -u campaign/omega-prefix-engineering-20261103/run.py --output /absolute/new-omega-prefix/campaign/omega-prefix-engineering-20261103/REPRODUCTION.json
```

The measured runtime was Python 3.12.14 on Linux x86_64. Use existing repository
dependencies and supported local POSIX storage. The runner creates fresh
explicitly synthetic fixtures, never opens an existing business account, and
refuses to overwrite its chosen output receipt. Source, protocol, runner and
test hashes are retained in `HASHES.json` and the result. New timings can differ;
reproduction should preserve semantic equivalence and report its actual result.

**Next action:** retain the failed performance verdict and reviewable candidate.
Keep full replay in the main experiment. A future longer-trace comparison is
justified only by a concrete operating workload and a new preregistered gate;
do not tune a crossover threshold or retest selectively to manufacture a win.
