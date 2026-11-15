# Transition165 — stale cached prepared upgrade on an advanced operating checkpoint

## Fixed research contract, before test implementation

Source under test: owner PR #40 exact `ced6c1cb004887dcdafaea59a2976020be649f8e`, a draft based on unmerged PR #35. This branch is an **independent test-only sibling**. Do not merge it wholesale, change the financial owner's source or signer, use original recovered accounts, or count a synthetic descriptor as signed/native authority. It has **no integration or account writer authority**.

**Question:** Does `connected_enterprise.operations.prepare_upgrade` revalidate the current `STATE.json` checkpoint when it returns a cached identical pending request? A cached successful preparation selected against checkpoint A must not remain successful if the observed checkpoint later changes to B without a committed authenticated transition. Unchanged retry remains idempotent.

**One preregistered finite schedule, no case selection:**
1. In a new disposable directory, build a synthetic, unsigned operator fixture using `engine.default_config()`, `migration.default_policy()`, one manifest, and source identities `a*64` (old) and `b*64` (new). Patch *only* signer, ticket validator, immutable source-copy and input-copy dependencies; exercise the actual public `prepare_upgrade` and `read_operator` control flow. No actual HMAC, Account, JournalAccount or external customer.
2. First call request `writer-A` with `expected_checkpoint_sha256=digest(A)`: require success. Capture exact `OPERATOR.json`, `SERVICES.json`, staged history and signer call count. Second identical call while A is unchanged: require exact same descriptor bytes, no second signer call, no writes.
3. Advance **only the disposable synthetic** `STATE.json` to distinct well-formed B (same source/identity, later event clock), retaining the same `writer-A` request and old expected checkpoint digest. Confirm `digest(B)!=digest(A)`. Require a fail-closed stale/authority/replay rejection **before** any further signer call, source copy, descriptor, manifest or history mutation. Never modify a real account, cash or signing history.
4. Always run the already-existing owner-source authorization-reuse unit suite unchanged as a control. Preserve any failed outcome unchanged.

**Primary test verdict:** The one stale-retry case is **FAILED** if the identical cached request is accepted after B is observed. No later source changes or new seed may convert that historical failure into a pass. A code correction would require a distinct owner-controlled change and new evidence. Checks of synthetic source/control-plane behavior do **not** prove HMAC compromise, financial corruption, loss of obligations or a runnable operating-queue migration.

**Practical owner-side implication if failing:** recheck a genuinely authenticated current account/operating checkpoint and protected pending status inside the shared canonical writer lease before honoring an identical cached request. Reuse must be tied to the exact signed predecessor/counter/source/journal, not merely `OPERATOR.json`'s self-digest. This is in addition to previously preserved T154/T155/T162 failures, not a replacement for them.

Never expose credentials, original recovery files, simulator keys, or make financial writes. No spending, paid APIs, outreach, bid, real transaction or production deployment. Commercial result remains unknown/unqualified; the US$3B trailing-365 profit milestone is not measured by this test.
