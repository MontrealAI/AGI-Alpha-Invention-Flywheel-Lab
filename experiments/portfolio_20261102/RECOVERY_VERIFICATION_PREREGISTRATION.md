# Independent acceptance gates for interrupted native campaign recovery

## Registration and scope

This document registers the independent verifier's acceptance conditions before
any recovery writer reopens an interrupted canonical account. Development may
use newly created synthetic accounts. The verifier reads public exports and
receipts; it does not open the canonical SQLite accounts or read their private
authentication material. The account owner must use the unchanged native owner
and authentication mechanisms for any reopening.

The financial implementation remains the public freeze
`9d4b2a2efb0289d6493d24e2e6c9493720596971`. Its freeze-document SHA-256 is
`3cfe1304592430bdea1329c42d4c4e5122dd7c90107302ada5fcff89ffbfd389`.
The first parallel orchestration freeze remains public commit
`418440e4587165488ccbf5a9d6bc04ba375a4675`, with freeze-document SHA-256
`95c0913b6f1e931d83e8cfde705ea844bd4626157890442fb42d77be017f2c4d`.
Recovery code, its tests, this document, and its execution plan require a new
public source binding. Existing financial, scientific, and native audit source
must retain its original hashes. A separately disclosed CI-only repair must
not be represented as a financial-source change or silently replace an older
orchestration receipt.

At the observed interruption, the fixed denominator is:

| Original indices | Status before recovery | Required treatment |
| --- | --- | --- |
| 00–07 | Eight complete, independently accepted accounts | Retain their original public output bytes and independent receipts. |
| 08–11 | Four opened accounts with incomplete controller execution | Preserve the existing account and durable prefix; any continuation uses that same account. |
| 12–23 | Twelve accounts not yet opened | Open each registered account at most once under its original recipe. |

The stopped process handles are unavailable, no owned driver or watcher process
is present, and the four interrupted public journals stopped advancing around
2026-11-02 19:39:40 UTC. The interruption's platform cause is unestablished.
The absence of a final campaign result is an execution interruption, not a
financial success or failure observation for the unfinished horizon. Earlier
completed outcomes have already been seen and must be disclosed. Recovery is
post-interruption execution of the same registered conditional models, not a
new blinded campaign.

## Preservation and admission gates

1. **Fixed recipes and denominator.** Recover only the four interrupted
   indices and run only the twelve unopened indices. Preserve all eight
   completed accounts, all interruption records, all failures, and every
   attempted index. World parameters, capital, policy, earned-only choice,
   1,825-day horizon, and final `[35040, 43800)` profit interval are unchanged.
   There is no favorable-outcome selection or replacement arm.
2. **Immutable evidence before reopening.** Before an account owner reopens
   an interrupted account, record the complete public durable action prefix,
   journal envelope, public source/manifest identity, and available public
   proof/resolution files with byte counts and SHA-256 hashes. Record the
   latest action sequence and time, all journal statuses, and whether a final
   pending intent exists. Preserve the original bytes in a separate evidence
   directory; never rewrite that preserved evidence. Private keys and private
   database files are not published or read by the independent verifier.
3. **Same native authority.** Reopening must retain the original account
   path, contract identifier, opening amount, working-capital configuration,
   manifest, source closure, durable action sequence, and native authentication
   authority. The original single-writer lock remains mandatory. No account
   deletion, reseeding, replacement, capital top-up, wallet-to-company transfer,
   debt draw, or cross-account pooling is permitted.
4. **Native recovery only.** If the original native owner discovers a final
   `PENDING` intent, only the existing native recovery routine may resolve it.
   Preserve its pre-open and post-recovery public states and identify any
   appended native action or completed/rejected journal entry. Existing
   completed entries and durable actions must remain exact. An incompatible
   pending tail, failed authentication, source mismatch, unexplained mutation,
   or divergent journal must refuse recovery and remain a reported failure.
5. **No acceptance bypass.** Full native audits, service-artifact checks,
   source checks, financial reservations, tax commitments, owner checks,
   rejection handling, and stop conditions stay active. Recovery must not
   modify native financial code, manufacture an accepted audit flag, or grant
   this service a new fast-audit exception.

## Reconstruction and append gates

6. **Historical state before current decisions.** Reconstruct the unchanged
   frozen controller using historical native states, not the current account
   balance substituted at past dates. Match every existing journal request,
   argument, timestamp, disposition, and deterministic receipt in order.
   Non-journaled observations and refusals must arise from the corresponding
   historical state. Reconstruction includes the complete daily record,
   pending obligations, tax memo and paid tax, collected-prior-year renewal
   eligibility, earned-resource plans, K1/K2 funding, prepaid capacity,
   operating stops, and future maturity/collection event days.
7. **Exact cutover.** Before the first new policy action is appended, require
   exact exhaustion of the recovered historical prefix and equality of the
   reconstructed current native export/state with the authenticated reopened
   account. No request may be skipped, executed twice, reordered, or remapped
   to a different account. A disagreement refuses append. Disposable native
   replay state is validation machinery; it is never a second company account
   or additional received capital in the campaign.
8. **Checkpoint identity.** Any newly added durable controller checkpoint
   must bind the exact controller/recovery source, recipe, manifest, account
   contract, complete controller state, native sequence, and native-prefix
   digest. Use the existing native checkpoint sealing/verification authority
   if a checkpoint authorizes future appends. An unsealed public summary is
   evidence only. Refuse wrong-source, wrong-account, altered-state, advanced,
   or non-prefix checkpoints. A stale valid checkpoint may authorize only
   exact reconstruction of the intervening native prefix, never omission of
   already executed actions or restored spending power.
9. **Durable interruption handling.** Record each recovery opening and its
   outcome. If recovery is itself interrupted, preserve that attempt and
   require the same admission and prefix checks at the next opening. There
   are no hidden automatic retries. Mark completed output only after the
   original operating horizon, required tail drain, native audits, and
   trajectory export all complete. Create-only outputs and idempotent exact
   existing-file checks may not overwrite a divergent result.

## Required development checks before canonical continuation

The recovery implementation must demonstrate the following on new synthetic
accounts before the canonical writer is authorized by the prospective source
freeze. Their expected behavior is fixed here; failure is retained and repaired
with a new source identity before canonical use.

- A matched uninterrupted run and interrupted/recovered run must produce the
  same complete native operating and post-drain ledgers, every daily financial
  value, decisions, cost receipts, tax settlements, rolling profit, K2 funding,
  license counts, stop status, and final reserves. Only explicitly measured
  runtime/provenance metadata and per-run private authentication bytes may
  differ. Differences in public financial state are not allowable noise.
- Exercise both seed-funded and earned-funded expenditure; cash-constrained
  refusal; delayed collection; cancellation/refund; tax due on collection;
  collection after the operating horizon; renewal eligibility; and maturity.
  A short horizon is acceptable for semantic development tests, while every
  canonical account retains the full registered five-year horizon.
- Interrupt between completed native requests and inside a durable pending
  operation; recover using the existing native pending-intent protocol.
  Include a second interruption of the same synthetic account and establish
  that no action, expense, release, refund, or tax is duplicated.
- Refuse an altered prefix request, action, receipt, checkpoint state, account
  identity, source hash, world/capital recipe, or manifest. Refuse unexpected
  extra or missing history and an incomplete account presented as completed.
  Demonstrate that refusing a reconstruction mismatch appends no policy action.
- Demonstrate exact retention of a previously complete account and absence of
  its reopening for commercial work. Demonstrate that all four interrupted
  and twelve unopened indices remain in the final denominator, including any
  recovery infrastructure failures.

## Final independent acceptance

The unchanged frozen per-account auditor must accept every completed account.
The independent assembly review must bind all 24 ordered registered recipes,
unique contracts, shared frozen source closure and two-artifact catalog, native
opening amounts, public exports, and compact campaign rows. It must preserve
the earlier eight receipts, verify all recovered-prefix relations, and count
all interruption/recovery attempts separately from the 24 economic arms.
The original incomplete orchestration history must remain visible; a new
recovery receipt must not falsely assert that the original process completed
without interruption.

Final qualification requires 24 completed and independently accepted arms.
Any refused or unresolved account remains in the denominator and prevents that
qualification. Resource reporting includes the additional reconstruction and
audit work; unavailable pre-interruption process CPU or model/human billing is
reported as unmeasured rather than zero. A resumed read-only audit watcher may
retain existing receipts and add newly closed arms, but it cannot create a
completed financial trajectory or alter an earlier finding.

These gates concern computational provenance and accounting. They do not turn
authored market worlds into observed customers, cash, financing, physical
deployments, or a demonstrated billion-dollar enterprise.
