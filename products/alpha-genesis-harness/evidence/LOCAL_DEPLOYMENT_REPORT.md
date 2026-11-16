# Local deployment lifecycle engineering receipt

Base source: `11f72c9411bb8b51b1a2b1890c9d52b74a4c40b4`. Candidate source is the containing PR head, not a released system.

Implemented an owner-authorized local deployment/support lifecycle using the existing bounded instrument evaluator and optional live `WorkflowService` admission. No external deployment, customer contact, spend, new credentials or financial account changes occurred.

Executed commands from `products/alpha-genesis-harness`:

- `python3 -m unittest discover -s tests -p test_deployment.py -v`: 17 passed.
- `python3 -m unittest discover -s tests -p 'test_workshop*.py' -v`: 12 passed.
- `python3 -m unittest discover -s tests -p 'test_instrument*.py' -v`: 19 passed.

The new tests execute install, run, reopen, upgrade, explicit rollback, failed acceptance without replacing current state, tamper-triggered blocked health, recovery, stale evaluator, invalid input, duplicate JSON, type distinctions, path/symlink refusal, private file modes and lock refusal. An actual existing-workshop integration test registers and constructs via an explicitly authored transport, admits, installs, executes and then revokes; subsequent use refuses. It is not live inference.

An authored parts-dispatch workshop export was also installed through the explicitly low-level local path with its five existing acceptance cases. Actual new input `arrived=17,reserved=8` returned `ready=8,remaining=9,shortage=0`; reopening retained the same content-addressed release. Its receipt states `executed_local` and `runtime_acceptance_established:false`, not business acceptance. This arithmetic example is an engineering exercise, not a claimed novel commercial outcome.

Independent review of the initial candidate found (1) a misleading fresh-input `accepted_local` status, (2) ancestor-symlink bypass and permissive file modes, and (3) no inherited workshop admission/revocation. These were corrected, with regression coverage. A later independent finding showed that the bound workshop operation limit was not retained; the exact `max_operations` is now carried into the release and used for acceptance and new-input execution, with propagation and exhaustion regressions. The original existing workshop tests remain unchanged.

No test establishes arbitrary enterprise autonomy, real customer support, signed multi-tenant authorization, power-loss durability or general correctness on unseen inputs. Live model/Pro runtime qualification, target-specific external connectors and full enterprise delivery remain separate barriers. Full candidate CI, public release and operation from a released artifact are not inferred from local scoped tests.

No dependency was added: Python standard library and existing HARNESS modules only. `THIRD-PARTY.json` dependency inventory remains accurate. Acceptance scope is detailed in `docs/LOCAL_DEPLOYMENT.md`.
