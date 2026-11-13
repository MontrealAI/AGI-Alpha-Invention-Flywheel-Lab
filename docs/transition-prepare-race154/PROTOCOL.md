# Transition154 — preregistered adversarial conflicting-writer review

**Parent source (immutable baseline):** PR #40, `ced6c1cb004887dcdafaea59a2976020be649f8e`. **Owner:** independent test-only reviewer. **Target:** `connected_enterprise.operations.prepare_upgrade` and the public OPERATOR descriptor handoff. **Integration:** NONE.

## Safety property

Given one signed prior STATE/checkpoint in one business output and two distinct prospective upgrade requests with that *same* expected checkpoint, at most **one** concurrent caller may return successful acceptance. Competing source-selection writers must either serialize and reject the stale competing request or fail closed with explicit evidence. Success must not depend on a last-writer-wins descriptor. No change to old account, signing key, journal, queue, money, liabilities or historical evidence is permitted.

## Fixed adversarial protocol before code

A single test uses two threads and distinct IDs `writer-A` and `writer-B`; both have one common synthetic prior checkpoint. Source identity and historical manifest are fixed. The actual `operations.prepare_upgrade` control flow and descriptor file writes execute. **Only the signer, ticket validator and source-copy operations are mocked**, and the fixture intentionally has a non-authentic synthetic signature. A timed rendezvous in the mocked authorizer forces concurrent eligibility where the implementation permits it; the timeout avoids deadlocking future serializing fixes. The acceptance oracle counts returned successful prepare calls; it does **not** count mocking as real signed-account proof.

**One preregistered attempt**, no changing seeds, parameters or acceptance after seeing the result. If both callers succeed, report `CONFLICTING_PREPARES_BOTH_ACCEPTED_SAME_CHECKPOINT` as a **test failure** with narrow scope. A mere absence of process crashes is not sufficient to pass. If an incidental I/O error rejects one request, independently inspect that error before treating it as a concurrency protection. This fixture establishes only the descriptor arbitration issue: an actual authenticated account/transition run, cross-process `RunLock` enforcement, crash idempotence, forged-key rejection and full financial history are *not* qualified here.

## Ownership and limitations

PR #40 retains its own financial-authority writer. This test-only sibling branch must never force-update PR #40, merge owner finance sources into main, replace an original signed STATE, or acquire the owner's key. If failed, owner must make a separate reviewed repair on its own source and qualify the *exact new* source, followed by normal current-main semantic composition and published-release operation. Historical failed tests stay failed. No customer, real transaction, new paid services, outreach or production deployment.

**Commercial result:** neither this test nor its repair provides buyer demand, earnings or a US$3 billion profit claim.
