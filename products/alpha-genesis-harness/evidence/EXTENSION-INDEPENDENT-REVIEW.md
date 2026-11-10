# Foundry, frontier monitor and authorization review

Review date: 2026-11-10. Scope: `bridge/upgrade_foundry.py`,
`bridge/frontier_monitor.py`, their HTTP routes, and the existing ChatGPT/Codex
authorization boundaries. Foundry and monitor review was performed separately
from their implementation. This is substantive engineering evidence, not a
GitHub approving review or a general security certification.

## Result

**115 combined tests passed in 11.224 seconds**, with no failures or skips.
The five additional adversarial foundry tests are in
[`test_extension_security.py`](../tests/test_extension_security.py).
The monitor suite contains 22 tests, including its scheduled-stop regression.

Run from the product directory:

```sh
PYTHONPATH=tests python3 -m unittest \
  test_upgrade_foundry test_extension_security test_frontier_monitor \
  test_chatgpt test_chatgpt_hardening test_codex test_codex_messages test_codex_permissions \
  test_independent_codex_resume test_server_integrations test_genesis_http -v
```

## Findings corrected and checked

| Finding | Implemented correction | Regression evidence |
|---|---|---|
| Cancellation could arrive between the final qualification check and its state commit. | Recheck cancellation inside the final locked transaction. | `test_cancellation_between_final_check_and_commit_prevents_qualification` |
| Retained candidate evaluation held the service lock during external execution, preventing timely cancellation. | Execute outside the state lock; track the active cancellation token and recheck candidate selection and source before accepting output. | `test_retained_candidate_execution_can_be_cancelled_before_result_acceptance` |
| Untracked FIFOs, sockets and devices were omitted from the candidate inventory check. | Require ordinary files/directories, bounded inventory, and descriptor-relative no-follow source reads. | `test_untracked_special_file_cannot_enter_candidate_manifest` |
| Only the foundry module itself was bound to qualification authority. | Freeze imported verifier/security-module identities, loaded-source checks, Python runtime identity and the configured Codex executable hash. Recheck before qualification and retained use. | `test_changed_loaded_verifier_dependency_prevents_candidate_qualification` |
| Restart could leave an attempt permanently marked constructing or qualifying. | Recover orphaned attempts as interrupted, retain unknown costs and evidence, permit inspection/export, and never retry or promote automatically. A shared active registry distinguishes genuinely active operations. | `test_restarted_orphaned_attempt_becomes_inspectable_without_promotion` |
| A monitor worker could fetch a previously selected job after the operator stopped it. | Scheduled dispatch checks enabled state under the dispatch lock; explicit manual polling remains separate. | `test_paused_scheduled_request_cannot_dispatch_after_due_list_snapshot` in `test_frontier_monitor.py` |
| Codex commentary and final answer deltas were concatenated, corrupting builder JSON. | Track message IDs, lifecycle phases and authoritative completed text; choose the latest terminal message. Commentary and partial answers remain progress-only. Nullable legacy phases select one completed terminal-position message. Interleaved completion and unfinished-message ordering remain explicit. | 13 tests in `test_codex_messages.py`, including commentary/final JSON separation, completion-only output, legacy phases, interleaving, no nonterminal fallback, and wrong-scope refusal. |

The combined suites also check unchanged/prohibited source edits, modified
protocols and candidate bytes, candidate-supplied fake verdicts, explicit
activation and rollback, sandbox-probe failure without fallback, credential-free
evaluation environments, withheld expected answers, authenticated HTTP routes,
cross-origin refusal, local-only refusal, saved restart consent, and late
stop/remove/close responses. Monitor observations remain **reported** evidence;
they cannot promote a capability to verified status.

The first ten Codex message regressions failed against the prior collector
(14 assertion failures and three errors, including subtests). The corrected
collector and its subsequent ordering regression were reviewed separately by
the foundry implementation reviewer. This patch changes neither workflow
acceptance nor the frozen evaluator implementation.

The message contract was checked against JSON Schema generated locally by the
installed official `codex-cli 0.167.0-alpha.4`, using an empty temporary
`HOME`/`CODEX_HOME`, no credentials, and no inference:

```sh
codex app-server generate-json-schema --experimental --out "$SCHEMA_DIR"
```

`AgentMessageDeltaNotification` identifies `itemId`; `ThreadItem.agentMessage`
contains optional/nullable `phase` (`commentary`, `partial_answer`,
`final_answer`) and complete `text`. The generated schema explicitly requires
legacy compatibility for unknown phases. `item/completed` and completed-turn
item snapshots provide the complete message used for the result. Schema hashes:

| Generated schema | SHA-256 |
|---|---|
| `AgentMessageDeltaNotification.json` | `996e6c0ea65e57bed5a00f410b94381fe5ebf804333e5d00c2b6e6d47e5c55f6` |
| `ItemCompletedNotification.json` | `0bbb11679b32e39a58546d3b532ccae2c1f8f9051a20ce2b4947edb84fc35f08` |
| `TurnCompletedNotification.json` | `00b691508bb0187ecc5f080bb1608add7137672698daed6922967ad90bcb16e1` |

## Fixture and native boundaries

Foundry construction and command/exec tests use explicitly injected protocol
fixtures. Their evaluator fixture computes answers with the existing trusted
interpreter; it does **not** import or execute the proposed candidate Python in
the test host. Passing these tests establishes control-flow and validation
behavior, not a live model-built upgrade or native sandbox enforcement.

The separate actual, credential-free native probe for the preceding source
returned **BLOCKED / CODEX_SANDBOX_UNAVAILABLE** because the host rejected
sandbox setup with `Operation not permitted`. It recorded
`generated_code_executed: false` and `live_model_construction: NOT_TESTED`.
No OAuth-backed process or candidate execution was used to bypass that result.
Reproduce on a compatible machine with `scripts/probe_upgrade_foundry.py`.
ChatGPT Pro inference and commercial authorization remain separate external
qualification requirements.

Frontier tests use injected public-source observations and local HTTP boundary
tests. They do not establish freshness or truth of a live external development.
Replay and monitor persistence use separate authenticated stores: a crash after
replay but before its monitor receipt can deliver a duplicate **reported** event.
Delivery is therefore at least once across that interruption, not exactly once;
duplicates grant no qualification authority.

## Reviewed source identities

SHA-256 values recorded after the combined test run:

| Source | SHA-256 |
|---|---|
| `bridge/upgrade_foundry.py` | `4704c9c9a32d440313182df9098030a4a1f8175ea4d4fedd8807bcbc1f5bee95` |
| `bridge/frontier_monitor.py` | `5c2802c349c012325be5a97fb00d17d9256f004ced3790c44e6022fd2a3fe71d` |
| `bridge/server.py` | `ba63d38377eb5f66f07cda785a080b25034c4909c1e9806826c355de36e8e5ed` |
| `bridge/codex.py` | `c05a689a3fcb417ae3a04a689532928beebca65b3cdd5f4d6262ea6e6ca3a0b2` |
| `bridge/codex_permissions.py` | `ec1dbc1e20b9ca3ae6f4ea5a7c15256e63a4a50413a40321a0281552ee130f66` |
| `bridge/chatgpt.py` | `2a2a69d4327e13b4773fceb559b8029e34e377b409e8221619af1287204c3aea` |
| `bridge/workflows.py` | `05203df3906e44be13e4ed51e4b9766f9e260fd3ee8560bfd99ec3ed4a75cfd9` |
| `bridge/adapters.py` | `9df37397ab9931d0738f0148ca15703f0ecbfa6c88149987684cf8f9f05ac22e` |

The native probe preceded the Codex message collector repair and a later
HTTP-server update. Its foundry module matches the entry above, but its Codex
dependency and full product snapshot differ. It must not be treated as a native
qualification receipt for this final source or archive; rerun the probe on the
released bytes and a compatible host.
