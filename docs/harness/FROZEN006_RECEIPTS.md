# Frozen cycle006 prospective wrapper receipts

This is a narrow follow-up to PR #264's prospective v4 monitor compatibility
repair. It improves cancellation evidence for the same authenticated historical
worker; it is not a new scientific or economic result. The existing v4 monitor,
frozen source, accounts and historical failures remain unchanged.

## Output ownership and completion

The inline wrapper in `.github/workflows/campaign.yml` claims a new exclusive
output under blocked SIGINT/SIGTERM and atomically writes `PENDING.json` before
source authentication. Existing outputs and symlinked paths are refused without
overwriting their evidence. Source errors or handled pre-completion cancellation
attempt an atomic `INTERRUPTED.json` with state `INCOMPLETE` and the failing phase.
Recovery requires a new exclusive output, not overwriting a prior run.

Final JSON and report files are written to same-directory temporary files,
flushed and fsynced, atomically replaced, then directory-fsynced. The first
wrapper cancellation fails the run; later wrapper-handler signals cannot abandon
its failure cleanup before masking begins. The v4 monitor retains its own worker
signal handling and process-group cleanup. COMPLETE promotion/rollback is masked
against catchable signals to protect the rename/fsync transaction.

`COMPLETE.json` is written only after the v4 receipt is complete and the original
worker's completion state and report digest match. It proves artifact completion,
**not successful process or CI exit**: cancellation after durable completion can
still fail the shell while leaving the valid marker. Qualification must require
the successful process/workflow result as well as source-bound output checks.

The original 6,363-source authentication and five limits remain binding: wall
360 seconds, CPU 240 seconds, memory 4 GiB, per-file output 64 MiB and aggregate
bounded storage 512 MiB. Prior v3 run `42083204982` remains failed. A fresh
successful reproduction does not rewrite that result.

## Focused verification

From repository root:

```sh
python3 -B tests/test_frozen006_receipt_interruptions.py
python3 -B -m unittest -v \
  tests.test_frozen006_boundary.Frozen006BoundaryTests.test_hosted_replay_uses_materialized_original_runtime \
  tests.test_frozen006_boundary.Frozen006BoundaryTests.test_prospective_supervision_retains_bounds_receipts_and_failed_history \
  tests.test_resource006_v4_scan
```

The new suite executes the exact workflow inline code, real OS signals and the
unchanged v4 monitor against a small synthetic authenticated source fixture.
It covers initialization, ownership refusal, partial writes and fsync errors,
source/report mismatches, completion promotion, two signals before cleanup,
actual running-worker SIGINT/SIGTERM and child reaping, and explicit failure
limits. Its synthetic 6,363-entry fixture is **not** the historical source closure.
The two existing boundary checks plus five scan checks test preserved constraints.

This focused local verification is not full repository qualification, historical
worker replay, a new release or downloaded-release operation. Those require the
normal exact-source hosted gates and review before integration. No terminal
receipt is guaranteed for SIGKILL, host loss, power failure, arbitrary I/O errors
or malicious concurrent filesystem replacement. The monitor's documented trusted-
command and CPU/descendant-accounting limits remain; this is not a sandbox or a
proof over every possible instruction-boundary interruption.
