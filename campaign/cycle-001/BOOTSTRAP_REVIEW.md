# Bootstrap reconciliation review

Reviewer: separate bootstrap-review agent; 29 October 2026. Shared model family, tools and host with the integration lead. Procedural source review, not external certification. No candidate edits, PR approvals or remote mutations were made.

## Decision

Use PR #2 commit `3f6afb85cbda324913aac8316e6f3e54dfa2e93c` as the useful policy/screen baseline, while preserving current owner main `aa5f47d47e2c76ce501e5d68b0b232f364bb893e`. It is not a completed campaign: every supplied hypothesis remains NOT_ADMITTED. PR #1's scheduling example is an optional regression fixture, not the flagship and not a replacement for stronger recovered strategy-invention work.

Both drafts independently pass their published tests at exact source bytes. This qualifies the narrow local software behavior below, not scientific or commercial success.

## Source and instruction inspection

- PR #2 has AGENTS.md blob `4e77c7acb12650ef306ae7b9f133748db3e5ccad` and CHARTER.md blob `d77cff1199e7b583d7a2fbf9d6b39867fcc3b9d4`. Both were read in full.
- PR #1 has no AGENTS.md or CHARTER.md at its inspected tree. Its PROTOCOL.md blob `42ffe807089acb1b7e0550beb6c4b092f2940db9`, README.md, SCHEMAS.md, code, tests, example and workflow were read.
- PR #2 preserves owner FIRST_CAMPAIGN.md blob `8dd0fb3cbec10ffe69dc8424a72f2a809dc2399e` and README.md blob `abcd6e2fcc561967f72f393003fee1590ac6e826`. Preserve FIRST_CAMPAIGN verbatim.
- Relevant AGENTS requirements: compare three materially distinct possibilities; record actual resources and inherited exposure/error history; source-bound selective reuse; retain stronger alternatives and failures; separate protected confirmation from development; verifier may not modify candidate; do not infer costs/demand; measure lifecycle costs; preserve owner README absent explicit direction; do not claim background activity.
- Initial package restrictions are not new user approval requirements: the latest execution brief explicitly authorizes campaign execution, recorded bounded allocation and GitHub publication within existing permissions. No new spending, paid calls, outreach or real commerce is authorized.

## Collision and integration plan

| Path | Collision | Recommended treatment |
| --- | --- | --- |
| lab.py | Entirely different CLIs and schemas | Keep PR #2 screener; if needed, retain PR #1 as `infrastructure/queue_demo.py` with an explicit import/CLI. Never combine by overwriting. |
| tests/test_lab.py | Both use the same filename/module | Preserve PR #2 tests; namespace PR #1 tests with their own imports. |
| README.md | PR #1 replaces owner README | Preserve owner README. Use a separate campaign reading entry point; any later explicit update should be focused and reviewed. |
| .gitignore | Different generated-output patterns | Merge only needed patterns while preserving history. |
| PROTOCOL.md, SCHEMAS.md | PR #1-only queue contracts | If retained, name/scope as fixture documentation rather than new campaign-wide implementation claims. |
| AGENTS.md, CHARTER.md, templates, examples/possibilities.json | PR #2-only | Retain as useful instructions/scaffolding. |
| .github/workflows/tests.yml | PR #1-only | The existing pinned checkout and read-only, 3-minute stdlib job can support meaningful verification, subject to final tests/source matching. |

Neither PR requires a wholesale merge to reuse a small useful part; preserve exact source provenance and avoid marking overlapping PR work merged if it was only selectively imported.

## Executed verification

Local review snapshots live under `research-work/bootstrap-snapshots`; they are temporary copies of fetched public files, not a repository checkout.

| Snapshot | Source Git blob | Test Git blob | Result |
| --- | --- | --- | --- |
| PR #1 | `7c9c9304e853037011378192bb00946f0ce170fd` | `b03a88712a8680ee657ac8275cfce06b1d3f2838` | 10/10 unittest tests passed; 0.009 s reported |
| PR #2 | `1baea4fab96cda5cc9059267985a66386ba7c63c` | `6ec94f30271212e915bd93cc1281434bcc7808a9` | 13/13 unittest tests passed; 0.009 s reported |

The local `git hash-object` values matched GitHub file blob identities for code, tests and both examples. Runs used Python 3.12.14 in the shared host.

PR #1 demo reproduction returned WORKS_IN_FIXTURE_SCOPE, UNKNOWN economics, NOT_ESTABLISHED successor benefit and NOT_ADMITTED Blue Sky admission. Protocol SHA-256: `babf29cefa4d0080da39ca93170b65a2eda41451806f280706efa01e8f9c7486`. It retained the rejected longest-first policy and valid shortest-first policy. Strongest competent controls tie the inherited policy.

PR #2 screen reproduction returned three candidates, zero admitted, commercial success UNESTABLISHED. Its tests reject missing fields, duplicates, unsupported extra claims, malformed sources and malformed JSON; supplied favorable cost records never admit a cohort. Output directories are exclusive.

## Limits and concrete issues

1. PR #1 enumerates developer-registered policies and supplies the structural mapping manually. Its exhaustive checker is a separate implementation in the same module; this is not a separately controlled verifier. No autonomous discovery, unrestricted invention, meaningful economic transformation or causal learning follows.
2. PR #2 is a strict shape/evidence-gap tool. URL/date strings and cost records are not verified. It explicitly reports source entries unverified and declared domain distinctness unverified. It does not research or rank opportunities.
3. Neither contribution executes generated code. The absence of a generated-code sandbox is acceptable for these trusted declarative fixtures; it cannot qualify a later generated-program path.
4. PR #2's cost-validation error calls the record “signed” although it verifies only field shape; do not describe a cryptographic signature mechanism as implemented.
5. PR #2 source files carry Apache-2.0 SPDX headers, while PR #1 explicitly says no project-wide license was selected. Preserve existing notices; do not infer a blanket repository license or introduce one silently.
6. No remote Actions CI or release qualification was asserted by this review. Final integration needs tests against final published source and actual job results.

## Acceptance for integration

Accept the bootstrap only as narrow engineering infrastructure. A substantive campaign closeout still requires sourced opportunity decision, executed discriminating probe when justified, unchanged independent specification, preserved criticism/repair trace, cost/unknown ledger, honest economic and successor verdicts, and final source-matched publication.

