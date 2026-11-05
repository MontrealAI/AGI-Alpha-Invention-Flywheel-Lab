# GENESIS104 — source-bound native order-prefix recovery (prospective)

**Frozen before test or implementation.** Base: GENESIS103 CI candidate `30bd925950471f7d54b7e65bf3d81f02108bedf6`; parent draft PR #256 on #255, financial integration owner PR #229 remains untouched. This is an isolated repair of independently reported [P1 review 4477792752](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/255#discussion_r4477792752); it is neither a change to the original failed review nor evidence of economic success.

## Invariant and frozen tests

The original HMAC-signed checkpoint may record `phase=order` even when the native owner has already committed an **authentic prefix** of `begin_order` operations but the next signed checkpoint has not been durably written. After native audit and registered-choice validation, accept only a byte-for-byte registered contiguous prefix in native action order: wallet, prospective terms, offer, consent, fund. An empty prefix is allowed; missing/out-of-order, duplicate, off-time or mismatched records must fail **before any new native write**. Do not regenerate keys, erase funded custody, or initialize another account. Existing source/authority checks and owner locking are mandatory.

- **C12**: full five-action native order committed on disposable canonical BusinessAccount; original signed `order` checkpoint retained. Resume exactly the same account; no duplicate wallet, terms, offer, consent or fund. Run original audit and subsequent continuation.
- **C13**: separately test valid partial prefixes after wallet, after terms, after offer and after consent. Resume with the **same** canonical ledger and original HMAC checkpoint. Require one copy of each action, correct ordering, original obligations and successful independent audit.
- **C14**: authentic but incorrectly priced/dated/ordered prefix must be rejected before any mutation. Compare native action tape and signed checkpoint bytes before and after the rejected run.
- **C15**: unchanged empty-order prefix must remain admissible. Existing GENESIS103 C0–C11, GENESIS101 completed chronology and GENESIS102 refund closure must still run.

## Stop, source and evidence

Run fixed C12–C15 once after implementing. No seed search or replacement of failures. Require exact-head hosted discovered tests, original native pilot/resume/audit/export, independent review, and repository-wide source-matched checks. The independently reproduced clean public-release download is a separate later integration requirement, not implied by a unit-test pass. If any case fails preserve the failure and repair prospectively. Do not merge this stacked draft into any financial owner source before safe review and qualifications. No new funding, paid service, customer contact, real transaction, credential, or account takeover. No new enterprise or profit claim.
