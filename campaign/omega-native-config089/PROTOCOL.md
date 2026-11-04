# Ω native registered-configuration fault test 089

Source pinned for this independent, test-only experiment: **PR #206 commit `68eef714f62fab64b04131377afd6ae2047358f9`**.
This is **not** the original P0 migration, an alternate financial owner, a release, or a registered market experiment.
No protected native account, historical evidence or private key is used.

## Frozen question and cases (before testing)

Can a self-consistent, genuinely signed and independently auditable JournalAccount be accepted as the registered V4 $100,000 / zero-working-capital / `omega-private-mechanisms-v4-fresh-synthetic` contract when its **actual native account configuration** differs? A summary label or a self-consistent native replay is insufficient. Verify the canonical exported `ledger.config` against the V4 registration, separately from any report display field.

Use *three* separate disposable normal JournalAccounts, each running the same fixed small source-equivalent engineering market `((1337, "substitute"),)` (two types), with the existing accepted services, source hashes, no-demand stress, tariffs, native ledger and public audit. The exact native variants are fixed before execution:

1. **Opening mismatch:** run with USD200,000 opening, then correct only the recorded *display* `opening_microUSD` field to the registered USD100,000. The correct live ledger still has the USD200,000 native opening.
2. **Working reserve mismatch:** normal USD100,000 opening and contract, but use a legitimate USD1 native working reserve rather than registered zero.
3. **Contract mismatch:** normal USD100,000 opening and zero working reserve, but a distinct native contract `omega-private-mechanisms-v4-fresh-synthetic-alternate-fixture`.

All three underlying ledgers must independently pass `audit_journal`, and the registered report/source metadata must remain normal except the explicit case-1 correction. **Expected decision: reject at public V4 audit without operating, re-signing or rewriting the account.** No input selection or favorable-retry rule. Preserve a red CI failure if the current implementation accepts any mismatch; do not weaken source guards or rewrite the expected configuration to get a pass.

## Cost/permissions and stop

Exactly three source-bound disposable simulations, three independent native-replay checks, three public V4 audit attempts; no new market confirmation, no prospective capital claim, no spending/API/customer outreach/deployment. Standard public GitHub Actions only; existing pinned requirements and six-hour platform hard limit. Stop after the three registered checks (or an actual platform limit); report achieved/failed/blocked per arm and hand off to the sole PR #206 financial owner. Implement any eventual canonical repair in the owner's protected integration path, not in this independent verification PR.

## Acceptance matrix (unexecuted protocol)

- Baseline registered terms and source, same-account legitimate journals: **to verify**.
- Native signed journal independently audited for each alternative: **to verify**.
- Opening/working/contract drift rejected by V4's independent public audit: **to verify**.
- Original P0 migration, prior account liabilities, actual paid commerce, complete human alternatives, US$3B trailing profit: **NOT CLAIMED**.
