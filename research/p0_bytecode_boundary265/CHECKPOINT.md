# P0-265 development checkpoint — 2026-11-24

Protocol frozen at 848dcecec18abf16984a46ad6f90b4a991b0d769; first local execution, exit 0. The actual executed probe matched Git blob effe5872578e1e84e8d2979de71690ea41940b34, SHA256 188c94c0d214e4b7174d3308d6f84b30de7322521405ff5cad44a803058a86ad. No rerun. Exact owner source_inventory was reproduced from upgrades.py at owner head ced6c1cb004887dcdafaea59a2976020be649f8e (blob 9866d004c412fc05c9f6292cf898307f177359df).

```json
{"accepted": true, "actual_billing_usd": null, "checks": {"clean_source": true, "fresh_cache_prefix": true, "fresh_prefix_stays_empty": true, "isolated_no_write": true, "nested_prefix_not_inherited": true, "no_write": true, "ordinary": true, "owner_inventory_equal": true}, "observed": {"clean_source": "NEW", "fresh_cache_prefix": "NEW", "isolated_no_write": "OLD", "nested_prefix_not_inherited": "OLD", "no_write": "OLD", "ordinary": "OLD"}, "python": "3.13.5", "scope": "synthetic CPython timestamp-cache development probe", "waited_child_cpu_seconds": 12.693823, "wall_seconds": 11.468624035999994}
```

All eight fixed checks passed. A timestamp-matching stale synthetic bytecode file can change the executed module result while the actual owner source_inventory remains equal after removal of that bytecode. Ordinary startup, -B, and -I -S -B each loaded OLD even though the source contained NEW. Explicit fresh empty pycache_prefix plus -B loaded NEW, and did not write to the prefix. The nested ordinary subprocess did not inherit this prefix and loaded OLD. Clean source loaded NEW. No malicious payload, real audit bypass, financial key or account involved.

## Native applicability

Exact owner upgrades.py lines 40–53 inventory only .py and exclude __pycache__; lines 55–103 select historical root, validate jobs and launch audit with PYTHONPATH and PYTHONDONTWRITEBYTECODE. Lines 163–164 launch historical authorization similarly. Exact unchanged successive-transition test in tests/test_connected_operating_upgrade.py (blob fc4917ae2ef6ff90ac0c8df9606dbfdd181d428b), lines 225–238, creates a forward source by copying the first successor and edits its engine file. This is a relevant source-closure boundary, not evidence that stale bytecode exists in that fixture. P0-263 stages a fresh source tree for its outer invocation; this result does not contradict that protection. The actual descendant selected historical roots and interpreter flags remain to be observed. Fresh cache-prefix isolation is only a tested component; it does not qualify arbitrary native code, native extensions, startup hooks, source-only modules or mutable dependency directories.

Decision: retain the regression, do not enable recursive memoization merely on source hashes. Next decisive native test should use a controlled execution boundary covering every historical subprocess (including descendants), verify actual interpreter startup policy, bytecode/import paths and full selected source/dependency/service/evidence closure, refuse unbound descendants, then test cold-versus-reuse equivalence under the unchanged native assertions and 60s subprocess limits. Instrumentation must not change historical verifier bytes or silently discard obligations, and must not publish raw command payloads or private paths. Do not claim that bytecode caused the prior timeout.

| Acceptance | Verdict |
|---|---|
| P0-265 fixed synthetic platform | Development pass 8/8 |
| P0-264 original venv arm | Historical failed 3/4; preserved |
| P0-263 full native composition | Historical failed 2/3; preserved |
| Descendant native launch receipts and cache equivalence | Unqualified |
| Original account/source custody | Unknown; no integration |
| P0 release, P1/P2 complete-cost profit, recursive improvement, actual commerce | Not established |

Repository refresh: main 39e76570c851b3527d78a526053a9ea2a611a993; AGENTS.md, guide/resource/operator and charter sources retrieved, six handoff records retrieved, connected014-release.yml blob 6aedd5edbbd59ee585589634b8346276880c214d. Published matching connected014 release dated 2026-11-24 05:26:17 UTC; workflow 45327425758 all three jobs report success. PR40 remains open at ced6c1cb004887dcdafaea59a2976020be649f8e; no original owner handoff inferred. Local git network resolution failed; connector source reads and isolated new research branch publication succeeded. No actual native execution attempted here, no protected code or main changed, no spending, no new external credentials, no outreach or transactions. Actual whole-episode billing unknown. US$3B trailing-365 complete-cost profit remains open and unachieved.
