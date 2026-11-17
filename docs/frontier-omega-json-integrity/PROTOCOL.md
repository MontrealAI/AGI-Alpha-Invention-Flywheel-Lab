# Prospective JSON evidence identity review (2026-11-17)

**Frozen before tests or correction.** Reviewed exact source `d1c7fee057961727f984c22fce1379c3d6f544b9`, function `frontier_omega.__main__.read_json` and `frontier_omega.ignition.main`. The standard-library `json.load` defaults accept duplicate object members (last value wins) and nonstandard NaN / Infinity constants. CLI-supplied assessment/ignition JSON currently uses that path. This is an *input ambiguity* in claimed frontier/buyer evidence; no real buyer, proof receipt or money has been involved.

## Fixed negative regression cases
1. A duplicate **outer `synthetic`** key containing `true` followed by `false` must be refused before a later declaration can erase the rehearsal marker.
2. A duplicate **nested `matched_test.synthetic`** key containing `true` followed by `false` must be refused, even with a nonsynthetic outer record.
3. An input containing the nonstandard JSON constant `NaN` must be refused before any economic evidence classification.
4. An input containing the nonstandard JSON constants `Infinity` or `-Infinity` must be refused before any calculation, including when embedded in a nested cost.
5. A minimal unambiguous valid JSON object must continue to parse normally.

Test only through transient local UTF-8 input files using the normal `read_json` entry point; no private account, network access or persistent keys. Preserve the tests-only failure as a historical failure, never retroactively relabel it. A prospective narrow `json.load(object_pairs_hook=..., parse_constant=...)` repair may follow only after an actual failing reproduction. Do not rewrite source archives, financial rules or the owner PR #428. Complete PR-workflow and release-source qualification must be independently re-earned on the new exact correction head.

**Evidence tiers:** input-parser correctness only; not proof that a public URL is truthful, an independent human accepted a task, a buyer signed, or paid commerce occurred. The original 16/16 qualified head remains frozen as a previous success, not a pass for new work.
