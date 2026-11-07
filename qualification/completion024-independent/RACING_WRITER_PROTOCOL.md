# Independent v2-CAS competing-writer protocol — 7 November 2026

**Status:** prospectively frozen, before test implementation. **Scope:** freshly constructed, ephemeral simulation account only, on the current PR #295 source. This is not the inaccessible completion023 owner checkpoint, current-main composition, or release qualification.

## Missing P0 claim and fixed construction

The previously qualified bounded v2-CAS continuation did not itself prove safety when **two different OS processes concurrently attempt the *same* authenticated forward-source transition against a nonempty, identical original native account**. A single successful transition must not be counted twice, must not create competing signed account histories, and must not permit either process to replace the underlying simulation key. This test targets the inherited owner implementation without editing its financial code, source guard, archive limit, old history or account authority.

Create one account with a prospective order, completed original service, nonempty financial claim, the original signed journal and a v2-CAS ticket generated through the actual owner-facing `authorize_upgrade` entrypoint. Pin identical old/source services, exact old state digest, the owner-supplied evidence directory, key inode and immutable financial action prefix. From two independent Python interpreter processes (not two threads), release a single synchronization barrier and call `JournalAccount.upgrade_source` using the **same** ticket and account path. Preserve the exit and error class of both processes. A second process may successfully observe idempotence or fail closed on an authentic writer contention; it must not create a second transition.

## Predeclared acceptance and failure

1. At least one process completes a valid transition; neither can silently overwrite another version or evade single-account custody. Both must exit in finite time, without secrets in stdout/stderr.
2. On independently reopening the **same account**, there is exactly one `source_transition` financial action, the original action prefix and claim are byte-equivalent, the original signed key inode is unchanged, the current source remains the intended forward version, and `audit()` accepts.
3. A second valid attempt with the same ticket, after the race, remains financially idempotent (success is allowed); an attempted downgrade through the original source must fail closed with no financial or key mutation.
4. A missing/changed CAS blob remains a refusal; nothing re-signs, resets or discards old liabilities.
5. One fixed execution, no seed search, no automatic retries. If the process race reveals a defect, retain the failure and report to the exclusive P0 owner; **do not fix finance/Account/guard files on this research branch**, do not bypass authentication or relabel a failure.

Record exact Git commit, each subprocess status, signed nonsecret financial sequence/actions and audit verdict, resource measurement where available. Only source code, key-free textual test results and small nonsecret metadata may be published. Absolutely no key files, account sqlite/journal/WAL, recovery sidecars, raw historical account data or test-generated credentials in artifacts.

The incumbent is the published current-main operator, which is unaffected. **Acceptance of this test is an engineering safety property, not authorization to migrate the actual owner account, merge, publish, deploy, infer buyers, book recovered money or claim progress toward US$3B trailing-year complete-cost profit.**
