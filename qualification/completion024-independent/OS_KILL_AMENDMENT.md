# Nonrelaxing amendment — fix v2-CAS fixture eligibility, preserve first failure

Frozen original protocol: `OS_KILL_AFTER_NATIVE_COMMIT_PROTOCOL.md` at `76b729da56ef2b29c4b4dd800515e25ef595b4b8`.

**Actual first run:** [#42424919995](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42424919995), exact source `8754a5f50ef7aaf074c1aac7e4c428e939f0b21d`, **FAILED** before launching the crash subprocess. Four unintentionally imported existing fixture tests passed; the one new test failed asserting that `validate_ticket` returns the external v2-CAS schema. In fact, `validate_ticket` correctly resolves either wire format to the historical inner `agi-alpha/native-source-transition/v1` body, and the borrowed `_prepare` helper *defaults to a v1 ticket*. Therefore the first run supplied no evidence whatsoever about hard-kill recovery or v2-CAS behavior. It must remain FAILED; no retroactive pass.

**Prospective repair only (before editing executable test):**

1. Retain the unchanged originally registered claim, outstanding payable, same native account, HMAC verification, fatal SIGKILL immediately after real `Account.source_transition`, canonical retry/reopen/audit, exact one-transition and original-liability invariants, downgrade rejection, and non-disclosure boundaries.
2. Use the borrowed claim fixture only to create its original signed account and prior state. Ignore its default v1 authorization; create a **separate explicit owner-generated** ticket with `authorize_upgrade(..., transition_format='v2-cas', evidence_root=the same local store, expected_state_digest=the exact prior snapshot)`. Require external `ticket['body']['schema'] == 'agi-alpha/native-source-transition/v2-cas'`, while its independently validated *resolved historical inner body* must retain `schema == 'agi-alpha/native-source-transition/v1'`. The ticket must be verified by canonical `validate_ticket` with the same ephemeral owner key/path/current target before use.
3. Import the fixture module under its module name (not importing its `unittest.TestCase` class into the test namespace) so this dedicated run executes exactly one fixed new case rather than four unrelated inherited tests.
4. Keep first failed workflow and this amendment in immutable Git history; do not rewrite code/source guards or old evidence. Any new run is a separate exact-head test; a failure at the intended OS-kill/restart boundary remains a new failure, not an excuse to relax the safety test.

**Claims unchanged:** A passing repair would qualify only one ephemeral signed financial-claim crash schedule. It is not an operating-queue continuation, original account handoff, full current-main composition, release, or observed commerce.
