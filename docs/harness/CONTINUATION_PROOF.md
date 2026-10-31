# Lean same-runner continuation proof

Run `python scripts/prove_harness_continuation.py --receipt /tmp/continuation-receipt.json`,
or the **🌌♾️ AGI ALPHA Flywheel Harness: isolated continuation proof** GitHub Actions workflow.
The workflow is manual/PR-triggered, not a recurring commercial operator.

This small development campaign creates new disposable synthetic accounts only.
It registers one fixed seed, a 14-day planning horizon plus settlement drain, and
two existing baseline/growth arms. Each business has separate modeled capital.
The continuation and reference copies share source, seed, configuration and the exact prepared public service
manifest/inputs, not private keys. Preparation is executed once and its measured
CPU receipt is preserved, not zeroed or regenerated per arm. No incumbent account, historical operating directory, or live
customer information is accepted as input to the public campaign entrypoint.

The proof uses canonical registration, `operate --max-events 1`, then a separate
`operate --max-events 2` process. These event bounds are **per business**, not
aggregate CPU or spending limits. Owner-only partial validation checks frozen
source/configuration, the native HMAC checkpoint and native action prefix, and
native accounting under the existing ownership lease. It explicitly reports
`CHECKPOINTED_PENDING_FULL_AUDIT`; it does not fabricate REPORT or COMPLETE.

Only in the new marked test fixture, the child exits abruptly after production
but before advancing the operating checkpoint. Native recovery replays that
pending event. Separate tests reject a concurrent RunLock writer and a direct
native account writer. Final native/operating audits must pass; complete
financial/operating semantics must match uninterrupted operation. A duplicate
**completed** resume must not advance finance or events. Comparisons exclude only
canonical independent-owner signatures/filesystem witnesses and timing metadata;
all source, native actions, obligations, money, orders and event timestamps remain.

## Scope and open gates

- This proves **same-runner, cross-process** persistence, not cross-workflow state custody.
- A private durable backend and distributed writer fencing are **not implemented** here.
- A durable inbox making **partial** workflow-trigger requests exactly-once is **not implemented**.
- The synthetic fixture is engineering evidence, not a profit improvement or scale claim.
- Host/model billing is unavailable, never treated as zero. Subprocess CPU/wall
  observations and unchanged modeled business costs are reported separately.
- Only a compact receipt is uploaded. Private keys, raw account directories,
  large logs, source ZIPs and recovery authority are never uploaded. Disposable
  account state is removed when the campaign exits.

An initial 3-day/4-buyer development probe did not reach production and failed
`REGISTERED_FAULT_NOT_REACHED`; it is not counted as a continuation pass. The
14-day/8-buyer configuration is a prospective correction based on the existing
recovery test fixture, not a fresh commercial confirmation cohort.

A subsequent diagnostic correctly rejected independently prepared service manifests:
preparation CPU is embedded in manifest and native contract identity. The corrected
proof shares the exact public workload before creating reference accounts; it does
not normalize financial digests or copy private account authority.
