# Verification-only continuation

The authorized checks completed on candidate `fff440f64087ae1daa088e329f980c4827729b05`.
No candidate runtime or prepared test was changed. This directory adds evidence
and verification tools only. The [source verification](SOURCE_VERIFICATION.json)
binds the original and isolated copies before and after execution.

| Check | Recorded outcome |
| --- | --- |
| Corrected launcher, same six compatibility modules | 70 tests passed; no NUL corruption or recursive rerun |
| Prepared maturity-to-successor case | Passed once, with its original script and protocol |
| Prepared ordinary Account/Journal portable source upgrade | Passed on current financial source after correcting Git lookup environment |
| Default 12-arrival matched comparison | 12 enabled versus 4 disabled settled orders; both completed and audited |
| Provider-default and outside-choice cases | Both completed and audited; losses and unpaid liability retained |
| Extracted public operating records | All three canonical audits passed without private account keys |
| Aggregate CPU control | Controlled two-child process group was detected and stopped; final controller probe passed |

The [machine-readable results](RESULTS.json), [comparison](COMPARISON.json),
[resource receipts](RESOURCES.json), [per-job logs](jobs/),
[proof records](proofs/) and [allocation](ALLOCATION.json) contain the details.
The 22 native tests that passed in the preceding checkpoint were not rerun or
counted as new tests.

All dollar figures below are simulated USD under authored complete-resource
prices, buyer behavior and provider terms. Actual host/model billing is unknown.
Production executed deterministic synthetic reconciliation jobs and their checker;
there were no paid frontier-model calls, real customers or real collections.

| Retained operating case | Settled orders | Modeled profit | Unpaid claims |
| --- | ---: | ---: | ---: |
| Recycling enabled | 12 | $1,367.84 | $0 |
| Recycling disabled | 4 | $453.28 | $0 |
| Provider default | 1 | -$139.68 | $250 |
| Outside choice | 0 | -$5.00 | $0 |

The enabled arm recorded 11 profitable earned-funded continuations. The control
disables receipt financing and retains unused cash; it is an ablation, not the
strongest conventional financing policy. This comparison does not isolate the
effect of prospective terms or prove market superiority.

In the prepared causal mechanism case, $149 of available cash could not fund a
$150 successor production commitment. Maturity released exactly $501 of reserve,
leaving cash and the $250 profit unchanged. The same owned account and private
key then funded, executed and collected a distinct successor service using earned
funds. Final modeled profit was $300, cash $800, and $200.20 of successor exposure
remained protected. Maturity itself was not income.

## Preserved failures and limits

The original recursive-launcher failure and resource breach remain in
[the original checkpoint](../native-capital-020/CLOSEOUT.json). Its 435.256672077
CPU seconds exceeded that job's 300-second cap. The earlier cycle remains
resource-unqualified; this distinct allocation does not reset that history.
Original failed logs, launcher and resource ledger are byte-checked unchanged.

Two orchestration failures in this continuation are also retained. The first
portable proof attempt inherited Git's nested-directory prefix and could not
archive its historical fixture. Setting `GIT_DIR` and `GIT_WORK_TREE` corrected
the execution environment while preserving the test and candidate. An early
comparison-completion precondition rejected the still-pending final maturity
event after 36 events; continuation processed that event on the same account/key
before the successful canonical completion and audits. No outcome, seed, price,
service cohort, assertion or financial rule was retuned.

The first controller receipts were corrected before candidate verification to
include final disk-scan CPU. Corrections are explicit in the resource ledger.
The controller's disk traversal was subsequently optimized without changing
process-group accounting; the final controller was separately exercised. CPU
charges include children, waited descendants, controller work and a conservative
30-second setup/publication allowance. RSS and disk growth are sampled; per-process
kernel limits supplement aggregate monitoring. These are local engineering
receipts, not independent certification or host/model billing measurements.

Financial Account/Journal source transition is verified. Full legacy operating
queue/STATE migration remains unimplemented and guarded. Observed commercial
revenue, capability-compounding benefit, Blue Sky enablement, annual profit,
merge and release remain unestablished. No hosted CI, new runtime changes,
external spending, merge, release or automatic renewal was authorized or done.

## Public raw records

The [byte-bound index](RAW_OPERATING_INDEX.json) lists every archive member and
transport part. After obtaining this directory from the candidate branch:

```sh
python3 verification-tools/restore_raw_records.py --output /absolute/new/RAW_OPERATING_RECORDS.zip
python3 -m zipfile -e /absolute/new/RAW_OPERATING_RECORDS.zip /absolute/new/public-records
cd /absolute/new/public-records/central-comparison/source
python3 -m connected_enterprise audit --output /absolute/new/public-records/central-comparison
```

The same audit command works for `provider_default` and `outside_choice` from
their respective `source` directories. Each export retains the exact frozen
source, configuration, service inputs/artifacts, native record and operating
result. SQLite accounts, private simulation keys and private resumable state are
excluded. Public records support audit rather than owned-account takeover.
The [export audit receipt](PUBLIC_EXPORT_AUDIT.json) records actual execution of
these audits on extracted copies.
