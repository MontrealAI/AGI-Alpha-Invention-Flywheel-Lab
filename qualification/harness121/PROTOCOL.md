# HARNESS 121 — pre-code correctness and usability regression protocol

Date: 2026-11-09 America/Toronto. Parent: PR #320 exact commit `74d8b5fe435a6a0cd670d57158adb5f68ebd5cc0`, NOT protected main. Scope: isolate review repairs without writing PR #320's branch or financial owner sources. This branch is a proposed review-only child and must not merge into main.

## Frozen cases and verdicts
1. Serialized project restorable-boundary: import a *plain* synthetic contribution with 2,600,000 backslashes into a fresh project. Require that **no accepted save/export can emit a project which importProject rejects**. Accept either a safely prevented import with original project unmodified or a portable serialized project that successfully round-trips. Check portable JSON size, escaping, project identity, and no silent overwrite.
2. Exact integer expression: `add([Number.MAX_SAFE_INTEGER,2,-2])` and `sum([Number.MAX_SAFE_INTEGER,2,-2])` must produce INVALID, not an incorrect PASSED IN SCOPE value. Verify normal [12,-2,3] addition, [7,3,-2] summation and a safe product still pass.
3. Workflow-only proposal: when imported independently of instrumentSpec, a valid declarative workflow must render an editable workflow editor and an executable Run button; the instrument-only panel must remain hidden, and no placeholder quote calculator should be fabricated.
4. Arrangement-only proposal: a valid economic arrangement without instrumentSpec must make its input and checker visible and preserve the model-supplied choice. No price, buyer, account, funding, eligibility, paid model call, or commercial result is inferred.

## Stop / qualification
Only these four frozen cases and existing product tests are valid confirmation criteria. Preserve any initially failing output; no seed search. Preexisting PR #320 review threads remain unresolved until exact repaired source is independently tested and integrated by its owner. The branch is a source-change proposal with no release, checkout, payment, outreach, credentials, account operation or rights claims. A hosted green suite is engineering qualification only; independent graphical/file-launch and public-release byte testing remain separate.
