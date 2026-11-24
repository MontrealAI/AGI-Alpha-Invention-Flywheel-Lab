# P0-268 adjudication — 2026-11-24

**Diagnostic PASS; native successive-transition qualification FAIL.** One registered invocation, no rerun. [Exact-head job](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45457293982/job/138670075698) executed frozen workflow f08684538818f9ddc76d9810f5b9b37083f33da1. The actual downloaded artifact 14949969757 (1763 bytes) has SHA256 7c083ea8c81bf087c8e2797c4d5bc974c493dc7458e2e6b62986b0c3e0d796e1; ZIP CRC checks passed. Its sole member P0_268.json (4785 bytes) has SHA256 66ce4e95e0d0361c31b82d01bdc4d71a9a2596504a9d9ec0db6b2b4ec8ad4f9b and Git blob 3bd25c5176e24f4fc6885435d8c6859c754a587b, matching the public copy at a981673cf947cfc4fce2f47a17b10369e2aed4a7. Neither signing material nor raw private trace was downloaded or published.

## Acceptance matrix

| Condition | Verdict | Evidence |
|---|---|---|
| Frozen workflow, unchanged test and instrumented source | Achieved | Job and receipt; probe blob c7e3b0a9d7333521a84be2b698c6ff7d4695d02d |
| Six original static gates / seven context checks | Achieved | 6/6 and 7/7 |
| Diagnostic usability | Achieved | 4020 complete spans, no invalid pairs, malformed rows or orphan ends |
| Unchanged successive same-business native test | Failed | Exit 1, TimeoutExpired |
| Safe cross-process audit reuse | Blocked/unestablished | Exact serialized input repetition does not bind execution closure |
| Native financial lifecycle and P0 release | Blocked | No qualified composition or signer custody |
| Paid commerce, $3B trailing-365 complete-cost native profit, recursive improvement | Unestablished | No new commercial operation, native profit not measured |

## What the diagnostic changes

109 audit launches, 113 isolated boots, 54 patched descendant requests, 200 leaf-cache hits. Of 109 boots correlated with audit input, 106 repeated one of just three exact serialized inputs. There were 163 audit-input wait spans, also with three distinct inputs; 54 parent-wait correlations were ambiguous because of nesting. Do not treat the 160 repeated wait spans as distinct physical launches. This is evidence of redundancy, not a demonstration of cache eligibility or an exclusive cost decomposition. Inclusive child waits totaled 219.464 s; service loads 61.579 s, inventory 46.225 s, leaf context 35.400 s, historical verification 345.842 s. These sums overlap and must not be added. Measured waited-child CPU 94.309581 s; wall 256.25624670900004 s; actual model/host/whole-episode billing unknown. The timed-out fixture remains failed even if tracing is useful.

At owner source ced6c1cb004887dcdafaea59a2976020be649f8e, upgrades.py:55–102 selects a pinned historical source, loads jobs, checks process-local _HISTORICAL_AUDITS, launches audit_journal and checks source/service again. finance.py:137 and :213 call verify_historical during historical lineage and signed source upgrade respectively. The digest used by the trace binds serialized payload, not the verifier implementation, launcher, dependencies, mutable evidence or caller authority. The result supports examining a request-scoped dependency graph instead of increasing timeouts or repeating the same optimization.

## Decision and boundary

Retain P0-268 and P0-262/263/267 failure verdicts. Compare (1) original fresh replay; (2) immutable per-audit closure/materialization with no receipt reuse; (3) scoped dependency-graph reuse of independently verified pure audit results only. Prefer a fresh-vs-reuse equivalence test on the same frozen two-transition fixture with exact descendant closures, explicit request binding, no authorization/ticket reuse, distinct accounts/contexts rejected, mutation during replay/reuse and cycles failing closed. A result must not be self-approved or used to skip mandatory native ledger/queue/authority checks. No nested-cache adoption until these obligations are established. Do not infer projected speedup from the span counts. No new workflow launched in this adjudication.

Main refreshed at 4509ef9ec2756427107dcf155228dac9f5617a2e; current release workflow 45456595620 qualification and publication jobs succeeded, downloaded-operation job still in progress at inspection. Historical release and six overnight022 handoff records refreshed, instructions and operator/resource guide inspected. PR40 is a draft on integration/transition-recovery-025; its described source is not proof of actual separate task checkpoint or original-account custody. Original owner status remains unknown; no overlapping writes, account/key access, spending, outreach, real transactions or deployment. This receipt lives only on the research branch. The broader mission remains open.
