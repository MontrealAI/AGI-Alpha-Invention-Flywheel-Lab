# Agent cache ceiling 259 — execution checkpoint, 24 November 2026 UTC

## Decision and scope

Retain the source-bound workload instrument for qualification, not a new serving product or commercial offer. The [frozen protocol](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a6c3e6f936d800345f03e297f95f0eaffe1fb995/research/agent_cache_ceiling259/PROTOCOL.md) compares established cross-model shadow warming, cache-aware admission, ordinary serving and non-entry. The actual missing incremental outcome over strong incumbents remains unestablished. No buyer, funding, GPU, accepted task-quality improvement, or actual savings assumed.

Primary evidence: [ShadowPrefill, November 9](https://arxiv.org/abs/2611.13176), [persistent degradation in prefix-cached agent serving, November 10](https://arxiv.org/abs/2611.13412), and [Azure public metadata release](https://github.com/Azure/AzurePublicDataset/releases/tag/ghcp-coding-agent-2026). The first already warms alternate models under serving slack; the second documents persistence of cache collapse and evaluates cache-residency budget controls. Combining their labels is not invention. Dataset [description](https://github.com/Azure/AzurePublicDataset/blob/master/GitHubCopilotCodingAgentDataset2026.md), Git blob d6eba28fe735833eb5cfe06114881237ff980635, CC-BY; Liu et al., *Agentic Coding in the Wild: Characterizing GitHub Copilot Traces at Production Scale*, [arXiv:2608.00101](https://arxiv.org/abs/2608.00101). Source aggregates are rounded, raw bytes not yet accessed.

## Executed source-matched qualification

[Implementation](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/807eace809f2dba1c7f71ee1cd3e13113dded7d3/research/agent_cache_ceiling259/replay.py) and [workflow head](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/8ef2cc44c7d29ce431d8ead48405e523a7ef6dd2). Local copy matched the fetched Git blob exactly: df8c5b5be9022d43b0139b9daa6787bbaa594d65 (11,726 bytes), SHA256 34d611003227673c0c29bb67ecf2ccb67c5674041154ff4fa69e9bec648b2b03.

- Seven registered local Python unit tests passed on first execution (accounting, missing end, schema, sequence, tokens, unknown timestamp, zero). Outer /usr/bin/time user 0.97s, system 0.40s, wall 0.97s, max RSS 97552 KiB, test-reported elapsed 0.002s. No model invocation.
- Separate positive archive-path check passed on the same script: three authored gzipped JSONL members written in reverse lexicographic order; selected a and b, excluded z (which had an intentionally distinct 1000-token prompt). Four calls, two sessions, 40 prompt, 16 cached, 24 misses, 8 output; one first-class same-model call and one switched-model call, six switch misses. At q=0.1,r=4, exact selected-switch bound 3/32, all-call bound 3/8. User 0.95s, system 0.24s, wall 0.79s, max RSS 97176 KiB. This is authored archive/selection correctness only, not raw workload or commercial evidence.
- A standard public read-only GitHub Actions push workflow was published at exact head 8ef2cc44. No workflow run ID or conclusion verified: available commit-workflow connector returns only PR-triggered runs, empty on this push; combined status empty and direct web workflow fetch failed. No claim of job admission, raw downloads or test execution on hosted runner. The local container cannot resolve github.com (git ls-remote DNS failure). Do not repeat or change the registered date arms without inspecting their actual first hosted results. If the push was not admitted, diagnose that separately. The self-test step pipes through tee; require actual test log and exit evidence, not merely a green step (default shell pipeline semantics can obscure a failing upstream command). No retries.

## New source-backed necessary-condition result (not raw replay)

The Azure release description reports P=631.4B prompt, C=540.95B cached, O=4.91B completion tokens, M=P-C=90.45B. A separately executed integer-rational calculation used million-token units to avoid floating-point arithmetic in the numerator and denominator. It yields the optimistic upper bound (1-q)M/(M+qC+rO) for converting **all** observed misses into cached input, even if conversion costs nothing. Fixed accepted call trace and common normalized token prices only. No evidence all misses are convertible, no cross-model subset size from summary totals, and no actual model prices. This is not a limit on other optimizations or other markets.

| Cached/uncached unit price q | Output/input price r=1 | r=4 | r=10 |
|---|---:|---:|---:|
| 0 | 94.851% | 82.160% | 64.815% |
| 0.1 | 54.468% | 49.581% | 42.038% |
| 0.5 | 12.362% | 11.884% | 11.030% |
| 1 | 0% | 0% | 0% |

For q=0.5,r=4, even a costless oracle that converts every observed miss could reduce this modeled bill by only 11.884% on the rounded source totals; a proposal requiring a 20% reduction from cache warming alone would therefore fail under those specified pricing assumptions. For q=0.1,r=4, the analogous all-call envelope is 49.581%; it is not the switch-only result. Neither ratio is an observed price, physical workload reduction or savings. For the exact defined nonoverlap switch subset the bound can only be narrower; no inference for ambiguous/overlapping calls. Actual source-registered per-shard replay remains pending. Unknown full costs and actual bills remain unknown.

## Acceptance and ownership

| Gate | Verdict |
|---|---|
| Current main and release baseline refreshed | ACHIEVED main 3cc6bc95a13f991b5158e5bd5064b766b21632a4; existing workflow 45296234913 inspected, historical release qualification and publication success; no new release replay. |
| Durable overnight022 records | ACHIEVED read of handoff, completion matrix, final report, two download proofs and independent review; source identities unchanged. |
| Source-bound instrument and authored correctness | ACHIEVED locally, exact blob and seven tests plus positive fixture as above. |
| Two registered real public metadata arms | PARTIAL implementation and workflow committed; actual hosted execution unobserved. |
| Actual serving constraint and incremental accepted benefit vs strongest alternatives | UNQUALIFIED. No physical serving, task acceptance or complete costs measured. |
| Original native-capital checkpoint/exclusive writer | BLOCKED: PR40 still owner-dependent; latest inspected comment is prior P0-255 handoff, no new owner custody receipt. No inference of task inactivity or transfer. |
| P0 protected integration, native profit, actual commerce, recursive improvement, USD3B trailing365 | UNQUALIFIED; no new accounts, liabilities, spending, paid APIs, credentials, transactions, outreach or deployment. |

All prior failures and isolated P0-255/P0-258 evidence retained. This branch is additive research, not canonical runtime. Do not merge or adopt as financial authority. Next decision: inspect hosted receipts; if usable, determine exact source-supported switch subset economics and reject unsupported claims, then only design a measured serving test for a residual over actual strong incumbents. No claim of zero whole-episode cost.
