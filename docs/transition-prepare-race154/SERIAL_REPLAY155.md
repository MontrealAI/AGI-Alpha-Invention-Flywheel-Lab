# Transition155 — preregistered sequential source-authority replacement probe

**Parent:** Transition154 independent test-only PR #360 (source baseline owner PR #40 `ced6c1cb004887dcdafaea59a2976020be649f8e`). This is a separate test, not a retest or reclassification of the already failed concurrent case. **Owner:** independent test reviewer; **integration:** NONE.

## New falsifiable safety question

Even if calls are *fully serialized*, can a second distinct `prepare_upgrade` succeed against the same prior signed STATE checkpoint after the first request has published `OPERATOR.json` but before its financial migration is committed? Correct behavior is idempotent acceptance of an **identical** request, refusal of a distinct request while the first is pending, and no source/descriptor replacement before authenticated source progression.

## Fixed test and acceptance oracle

Use a single POSIX temporary directory with one synthetic checkpoint and one services manifest. Use `engine.default_config()` so that `read_operator` validates the published first descriptor *without mocking that reader*. Call the real `operations.prepare_upgrade` control flow **sequentially**: first `writer-A`, then identical `writer-A` (idempotent retry), then distinct `writer-B`, always against the *same* expected checkpoint. Mock only owner signer/ticket validation, root source identity/copy and service-input copy. No private key or valid signature. Fixed target source and deterministic inputs; no search for favorable seeds.

**Pass only if:** first A succeeds; same-A retry returns the same exact descriptor; B raises a recognized explicit pending/stale/conflict refusal; and all published descriptor, history and state bytes remain unchanged by B. A generic incidental I/O error or an altered `STATE.json` does not qualify. **Fail** if B succeeds or replaces the descriptor, if same-A retry breaks, or if a rejection corrupts published state. No relaxing the oracle after execution.

**Distinct mechanism:** this is sequential pending-request arbitration, not a race. A lock alone cannot satisfy it if the implementation permits sequential same-checkpoint replacement. A future correction should hold the exclusive local account/business writer lease across preparation *and* apply an explicit pending-request identity / verified completed-transition guard. Subsequent genuinely authenticated successive upgrades must still be separately qualified on one account; this synthetic test does not exercise that positive route.

## Preservation and boundaries

Preserve Transition154's earlier failure exactly. Never modify PR #40's implementation or its original signed state; no merge of this red test into main, no claim of account safety from mocks, no access to private account/key/journal/queue, and no commerce, spending or deployment. Source-version transition, tamper/downgrade rejection, full cost and original-account continuity remain owner-integrated P0 acceptance gates.
