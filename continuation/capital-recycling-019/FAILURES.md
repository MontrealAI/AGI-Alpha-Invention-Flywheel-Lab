# Preserved continuation failures

Every attempt remains in the resource ledger and its named log.

- `prepare`: the script directory, rather than repository root, was on Python's import path. No service artifacts were created.
- `prepare-retry`: service generation completed, then report construction failed because the catalogue does not encode per-job `segment` or `tier` fields. Generated artifacts were retained; the retry became idempotent. The mandate's four-segment/two-tier counts are labeled as assertions, not re-derived from those JSON files.
- `matched-experiment`: `vendor/__init__.py` was absent from the selectively retrieved pinned closure.
- `matched-experiment-retry`: an empty Git blob had been materialized with one newline, so the pinned exchange correctly rejected it.
- `matched-experiment-retry2`: the first cover record lacked the native event clock; the native exchange rejected later consent before money/state could be misinterpreted.
- `matched-experiment-retry3`: the experiment and audits completed, but the post-run assertion used the Account snapshot shape rather than the underlying native snapshot shape.

No cap was increased, no failed log was replaced, and no failure was called a pass.
