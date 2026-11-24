# P0-271 adjudication — November 24, 2026

**Diagnostic PASS; native historical cache recovery-equivalence FAIL. Do not adopt this cache for native integration.**

Exact owner source `ced6c1cb004887dcdafaea59a2976020be649f8e` (PR40 draft); exact executing workflow head `c11f37f785dceb25d3d5f93fcc53c714acea2f36`, attempt 1, [run 45499508927](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45499508927), job 138818717677. The workflow's green conclusion denotes execution/artifact retention, not equivalence. Frozen [protocol](PROTOCOL.md) and [probe](probe.py) unchanged.

The independently downloaded [artifact 14970677551](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45499508927/artifacts/14970677551) has SHA256 `3d6711a5ec41b0d195d559a33523d54adc886ced2afcd85547e3853725d02594` (matches hosted metadata); ZIP integrity passed. Its sole member P0_271.json (2092 bytes) has SHA256 `6f04060136da2d6b2981cbb7903700109ac385a3dc66ba8111b2041047043ddf`. Public [RESULT.json](RESULT.json) at `897094fdb563a790af95d417c0eac92bacf448ca` has identical Git blob SHA1 `7ec3ef0cada6aadccfe1cdc379853ededfa38862`, independently computed from downloaded member bytes. Probe SHA256 reported by actual run: `28d281c17785c0f2f8a8348f3b54a1bd818991dddffc4f4d64c046fb9e300808`.

| Registered arm | Accepted | Receipt equals baseline | Direct launches | Pending alias removed |
|---|---|---|---:|---|
| Cold baseline | yes | yes | 1 | n/a |
| Warm clean | yes | yes | 0 | n/a |
| Warm valid pending alias | yes | yes | 0 | no |
| Cold valid pending alias | yes | yes | 1 | yes |
| Warm invalid unreferenced alias | yes | yes | 0 | no |
| Cold invalid unreferenced alias | no | no | 1 | no |
| Restored cold | yes | yes | 1 | n/a |

All four registered invariants passed: state and native history unchanged after authorization, source inventory unchanged, signer inode unchanged, referenced published blob unchanged. Authentic second authorization obtained, but the second transition was never committed. No original account accessed. No timeout in this comparison. Measured self CPU 8.843529 s, waited-child CPU 8.085396 s, wall 17.120018902 s; actual billing unknown. No paid model calls, purchases, outreach, external revenue, production deployment or new credentials.

## Source diagnosis and next decision

At the pinned owner source, `connected_enterprise/upgrades.py:55–102` resolves ticket, validates source inventory and jobs, then returns cached receipt at lines 75–76 before constructing the subprocess's evidence-directory scope at 77–86. The cache key does not contain that directory or its current recovery state. `connected_enterprise/transition_evidence.py:237–271` recovers same-inode staging aliases under exclusive directory lock when entering the scope, and rejects invalid content before unlink. Parent scope entry before the alias appears cannot substitute for the later canonical subprocess entry. This explains the observed difference without claiming original-account corruption, exploitability outside this disposable fixture, or complete causal explanation for prior native timeouts.

**Do not optimize around this failure.** The conservative alternative is fresh replay. Next registered development comparison should retain the unchanged historical verifier, perform the same canonical recovery and rejection at each use, and test exact receipt, effects, evidence-route identity and race/crash semantics. An entry-only preflight or an immutable snapshot alone is not enough; establish dependency completeness and isolation before caching, including nested verifier closures. Prefer disabling reuse for cases whose effect equivalence cannot be established. Compare against fresh replay rather than only the known non-equivalent incumbent. No owner-source edits while custody is unknown.

## Acceptance matrix / owner boundary

| Stage | Status |
|---|---|
| P0-271 diagnostic | achieved |
| Existing cache equivalence | failed (two discriminating pairs) |
| Native successive migration qualification | failed in prior P0-262/263/267/268; unchanged |
| Effect-preserving alternative | unqualified |
| Original financial owner account/source custody | blocked, actual separate task checkpoint unavailable |
| Protected composition, normal merge, released native maturity/reinvestment | blocked/unqualified |
| P1/P2, real commerce, recursive improvement, $3B T365 | not established |

Main refreshed at `96bf376e90acb2ae291a6317e72284a266389d27`, AGENTS.md, developer/operator/resource guides, Blue Sky guidance, six durable overnight022 handoff records and 92-record proof bundle manifest reviewed. Release workflow 45502402219 for current main in progress; corresponding release tag not found at inspection. Earlier release workflow 45485175678 completed successfully. PR40 head unchanged, PR77 remains draft at cd5281b0ae7b484572bfb35ccb7e51ef5b3be4b3. No inference about original task inactivity; no owner branch, native account, ledger, source guard, history or liability modified. Research branch only; do not merge wholesale. No changes to other owners' work or schedules.
