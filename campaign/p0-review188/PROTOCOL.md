# P0-188 — Verified immutable historical CAS snapshot (independent research instrument)

**Registration 2026-11-16 UTC.** Exact parent source `a40a9df6cdb73af10d03280225a131384eb0f169` (P0-187, test-only); upstream P0-186 source `df0387344d82e80f09f8e7e94f2019009be3f0e5`; protected financial owner PR #40 remains `ced6c1cb004887dcdafaea59a2976020be649f8e`. Freeze this protocol in a commit *before* constructing implementation or tests.

## Consequential P0 dependency

P0-187 demonstrated a real failure of mutable-directory historical-cache reuse at a deterministic deletion interleaving. An evidence snapshot might eliminate repeated dependency on a changing filesystem, **but only if it is actually closed, byte-verified and immutable and later bound to a genuine authenticated account/source writer transaction**. This isolated instrument addresses *snapshot completeness and integrity*, not the as-yet-absent writer/financial authority boundary. It must not turn P0-187 RED into PASS.

## Fixed finite construction and acceptance

Implement a separate review-only `connected_enterprise/history_snapshot188.py` utility that takes an externally authenticated caller-supplied transition ticket *inside an explicit trusted evidence-directory scope*; recursively resolves V2 CAS references, follows nested signed historical tickets including via prior records/envelopes/operating checkpoints, and captures each referenced canonical blob as immutable bytes. Use the existing `transition_evidence` hash/size checks and bounded `evidence_scope` to independently verify the captured closure. Bound traversal to at most 64 tickets and 150,000 inspected nodes, and inherit existing CAS blob/bundle bounds. Return an immutable value containing a deterministic snapshot digest and the exact root-ticket digest. Return **no authority or acceptance receipt**. No financial account, source guard or auditor change.

Exactly one new hosted focused test run must check:
1. A two-generation synthetic V2 hierarchy succeeds and yields a source-identifiable closed snapshot; within its frozen scope, both root and nested ticket resolve without the original directory.
2. Deleting the uniquely nested blob **after capture** makes the live CAS fail but does not affect the independent captured snapshot. This demonstrates snapshot persistence, **not** evidence that a current mutable account may accept the historical audit after deletion.
3. Missing or corrupted nested evidence *before* capture fails closed; no partial snapshot or accepted audit is returned.
4. The returned mapping is immutable, and unrelated/incomplete blobs are not smuggled in as current authority.
5. Include existing P0-184/185/186 and frozen P0-187 tests unchanged to show their current verdicts; P0-187 remains a required RED of the *unchanged* P0-186 cached acceptance route. Do not modify, drop or reverse its acceptance.

## Claims and ownership

A passing snapshot-only test demonstrates a reusable proof transport primitive, not HMAC account authentication, exclusive-writer authority, lock cooperation against unlink, atomic financial history migration, safe original-account recovery, release, observed demand, profitability, or full P0 remediation. An immutable snapshot is not sufficient to justify spending or state transition without authenticated source/ledger identity and a single canonical writer. Record exact-head workflow outcomes, time/resources where obtainable, all historical failures and any new negatives. No PR40/PR35/main writes, accounts, keys, protected liabilities, paid APIs, customer outreach, real commerce, or deployment. This PR is independent and must not merge wholesale into main.

**Stopping rule:** one preregistered implementation and fixed test suite. If rejected, preserve its failing receipt and diagnose without changing thresholds or retesting to manufacture success.
