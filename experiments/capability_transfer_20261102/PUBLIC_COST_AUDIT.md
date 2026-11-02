# Public research cost audit

## Verdict and scope

The five separately seeded cost-only research cases pass native financial replay and a separate reconstruction of the registered expense decisions. The review used the public export, its registration, the declared cost envelope and pinned public source. It rebuilt the 313 safe fixture files in a clean temporary source directory and replayed all 19 native expense actions. No original private account files or signing keys were accessed.

The reviewer was separate from the operator who executed these five accounts, but also authored `economics.py`. This provides separate execution and arithmetic review, not full constructor-independent or external financial certification. The underlying native ledger verifier is reused unchanged.

A second reviewer, who did not author the accounting wrapper, separately read the wrapper, tests, named public receipts, registration, envelope and README. That review found no blocking issue in the actual result and verified all 42 native source hashes, artifact/export commitments, 19 expense actions and 20 decision prefixes/receipts. It did not repeat the complete native replay. Automated `audit_public` does not compare every duplicated `decision.before_state_digest`, `decision.receipt` or stored `native_audit` field; the second reviewer checked that the current copies match. Do not claim universal metadata tamper resistance or external certification.

## Reconciled results

All dollar amounts below are simulated. Each row is an independent equity hypothesis; balances are never pooled.

| Opening equity USD | Research expense USD | Closing cash USD | Protected working reserve USD | Available cash USD | Final action |
| ---: | ---: | ---: | ---: | ---: | --- |
| 10,999 | 750 | 10,249 | 10,000 | 249 | Fourth 250 expense refused |
| 11,000 | 1,000 | 10,000 | 10,000 | 0 | All four expenses funded |
| 100,000 | 1,000 | 99,000 | 10,000 | 89,000 | All four expenses funded |
| 1,000,000 | 1,000 | 999,000 | 10,000 | 989,000 | All four expenses funded |
| 1,000,000,000 | 1,000 | 999,999,000 | 10,000 | 999,989,000 | All four expenses funded |

Every case has zero revenue, zero collections, zero payables, no sales orders and no earned-funded investment. Profit is minus the incurred expense. The reserve remains cash and is not counted as an additional expense. All recorded spending is labeled SEED. The 20 decision-state commitments, including the refused action, match the independently reconstructed native prefixes; each funded decision receipt matches its journal receipt.

The registered observation is **24 hours**, from 2026-11-02 17:00 UTC to 2026-11-03 17:00 UTC. `completed_365_day_window` is false in every case. The existing receipt field named `trailing365_profit_microUSD` contains the available partial-window loss here; its name does not establish a completed year. No annualized profit or US$1 billion or US$3 billion profit milestone is supported.

## What was measured and what remains assumed

The native actions, refusal, protected balances, event hashes and replay receipts were actually executed. The four USD250 resource items are explicit authored sensitivity inputs, totaling USD1,000 when affordable. They are not measured model billing, actual purchases, human wages or a verified complete cost of the scientific project. The accounts attach those hypothetical expenses to an existing artifact commitment; this does not establish that they financed real laboratory work.

The producer recorded about 4.595 process CPU seconds and 4.683 wall seconds for its accounting stage. This excludes scientific construction and included assistant work; the reviewer did not independently measure that earlier execution. Actual model tokens and inference cost remain null. Session-wide compute, orchestration, oversight, physical qualification, insurance, certification, deployment and customer acquisition remain unmeasured or unpriced. Upfront capital availability is a scenario condition, not secured financing. No debt, staged funding, capitalization, depreciation or tax benefit was introduced.

The artifact commitment is checked consistently across the registration and native work records. The scientific artifact bytes were outside this review's read scope, so their independent content verification and scientific acceptance remain separate.

## Exact evidence and portable delivery

- Public export SHA256: `d4f0e9f200a47079eb7dd68461a2b98c93bd4527f0f6941575bfe4d0d0af3091`
- Registration SHA256: `e94112d4784abbd81af4ee277e5a12fe354d3237c79e887b90f379da3506bb5c`
- Economics source SHA256: `04f75c5570de6467a9e6998afbd3e148a5439c1700ae370ed7aa02d80b9b3a21`
- Native source identity SHA256: `be0a101be84b3b98b4a68308cd7cf37f99a47e8809657a8cd5a75df714d933f1`
- Artifact commitment SHA256: `4c36506559fb88cdcfde81f76a12daf0af3ed369a67b0306499b0ecea2d39a8c`
- Native base commit: `88ddcfa3745dd5ae3022b9224d151943c9489b10`

Retain the complete key-free public export rather than inventing a reduced ledger. Its 1,181,792 bytes compress to **97,296 bytes** using `gzip.compress(raw, compresslevel=9, mtime=0)` in the current runtime. That is approximately 91.8 percent smaller, without omitting any replay inputs. The resulting gzip bytes have SHA256 `017cf928a94dd57fd8ab4faabf4cd7a0b58a65b3eb8bd4d2c1b2e6fe682c3d20`; verify the uncompressed export hash even if another compressor version produces different gzip bytes.

A portable publication should contain the compressed full export, the exact registration, this audit and the producer audit receipt, with pinned source and artifact references. The public export already contains the safe fixture bytes and native action history. Its existing `audit` command also requires the committed scientific artifact bytes. Publish no private recovery directory, key, redundant development runs or duplicate unpacked fixture tree.
