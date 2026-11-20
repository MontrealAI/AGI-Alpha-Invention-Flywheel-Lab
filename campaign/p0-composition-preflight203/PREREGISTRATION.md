# P0-203 — immutable public-source three-way composition preflight

Registered 2026-11-20, BEFORE constructing the probe. This is a one-shot
source-only investigation, not custody transfer, financial migration,
routine release qualification, or approval to merge owner code.

## Immutable inputs

- Qualified target: `main=f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
- Owner-held historical candidate: PR40 `ced6c1cb004887dcdafaea59a2976020be649f8e`.
- Expected common ancestor: `8abfb96d4ef859e30ca344d7933ec2a2f49012c1`.
- PR35 predecessor: `7d75766401adede49afd2427be82eb0302934b80`, closed unmerged.
- Source handoff remains unverified for separate native task `01a18fa7-ffc6-7384-8bb4-ea6012cfb0f7`; no inactivity inference.

## Problem and alternatives

A valid composed financial release requires the existing main operator and
all owner liabilities, signer authority and operating queues. Earlier
independent AST/interface and manifest probes (#495, #496, #502) showed
semantic incompatibilities; GitHub's compare reports a divergent four
owner commits versus 640 target-main commits. A real isolated three-way
merge preflight has not been qualified by those source-only interfaces.

Compare (A) wholesale direct three-way source composition, (B) future
owner-reviewed selective forward-port retaining main's source closure and
owner's valid historical transitions, and (C) retained qualified release /
NO ADOPTION. Here only (A) is executable; (B) requires actual owner
checkpoint and action-specific integration, and (C) remains the default.

## Frozen one-shot test and stopping rule

On a standard public GitHub ubuntu-latest runner, use an isolated temporary
Git repository with **no active account or private credentials**. Fetch
exact immutable public Git commits; verify the common ancestor. Execute
exactly one normal, non-forced, no-commit 3-way merge of PR40 into the
target main. Preserve the return code, unmerged paths and original
source-ref hashes. Do not auto-resolve, cherry-pick, stage, push, retry
with a different base, re-sign any state, change archive guards or
download private account recovery.

- If unresolved paths exist, explicitly report **FAILED_DIRECT_COMPOSITION**
  with exact conflict inventory and keep champion unchanged. A returned
  nonzero must never become a falsely reported successful merge.
- A clean tree would establish only **PARTIAL_SOURCE_COMPOSITION**, not
  semantic compatibility, source-manifest closure, live signer/queue
  migration, financial equivalence, native maturity, release or profit.
- If pinned sources or ancestry cannot be retrieved, label **BLOCKED**
  with the actual transport/ancestry error. Retain that result.
- No sampling or retuning; report measured CPU/wall, unknown host billing,
  source refs, process exit, and only compact public artifacts.
- Fixed attempt count: exactly ONE combination. No later cherry-picking.
- The workflow itself must use the canonical six-hour GitHub job window,
  AGI_JOB_START_EPOCH first-step marker, default public runner and no
  paid services.

## Financial and commercial acceptance boundary

No original native account is opened or created; no model buyer is
synthesized and no actual commerce occurs. Preservation of historical
key, signed cash, obligations, queues and write-ahead logs is a required
subsequent owner-controlled acceptance, not an inference from this test.
Even a clean source merge needs independently qualified CLI operations,
normal protected release, downloaded released-byte audit, complete costs
and genuinely settled revenue. The US$3 billion trailing-365-day target
remains unachieved. Do not merge this review-only branch wholesale.
