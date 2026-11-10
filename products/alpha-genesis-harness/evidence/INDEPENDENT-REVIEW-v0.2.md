# Independent review of the 0.2 candidate

This review covers implementation correctness and local security boundaries. It does not qualify authenticated providers, an eligible ChatGPT Pro account, OpenAI commercial approval, actual customer acceptance or financial success.

## Baseline

The review began at repository commit `e23ab09852d3ac14ff91156e8910df7e3c22268e`. Before the new integrations landed, the existing Node suites passed all 60 tests, and the Python product suite passed all 50 tests. Existing archive traversal, immutable-byte verification, provider-consent and browser import protections were read before adding new tests. These baseline observations do not certify later changes.

## Independent adversarial checks

Final test results and implementation identities are recorded after integration. No live model requests, private account access, payments, Squarespace activity or external messages are used in this review.

The verification boundary remains explicit: provider/model declarations and successful protocol fixtures are not live authentication; model criticism is not the independent acceptance oracle; a self-consistent checksum is not source authenticity.

## Findings and repairs

The reviewer reported these concrete defects to their implementation owners; implementation fixes and the independent regressions are separate files.

| Boundary | Observed issue during integration | Repaired behavior independently exercised |
|---|---|---|
| Portable instrument inputs | A declared `public` input did not prevent reading an undeclared `private.extra` field. | Undeclared roots are refused; declared nested fields still execute. |
| Exact portable arithmetic | Integer-valued floats above the safe numerical range were accepted; `1` and `1.0` compared differently. | Unsafe values and hidden intermediate overflow are refused. Numeric equality and acceptance preserve JSON numeric semantics while distinguishing booleans. |
| Streaming usage | A final display callback failure added a full reservation after known usage had already been accounted. | The single known response remains charged once; no reservation remains. |
| Commercial approval configuration | Nonstring values such as JSON `null` or `false` could become nonempty approval-reference strings. | Those values fail the commercial gate before storage or inference. An actual reference remains an operator assertion, not proof of OpenAI approval. |
| ChatGPT completion | A malformed `response.completed` lacking completed response status could be accepted. | Missing status is rejected and the active request is cleaned up. |
| Local-only sign-out | The server allowed sign-out but its implementation could contact the remote revocation endpoint. | Local-only sign-out clears tokens with zero transport calls and states that remote revocation was not confirmed. |
| Imported executable assets | An attacker could rehash an export containing an arbitrary file labeled a trusted runner. | Imports enforce the same file-kind boundary and fixed runner as constructed artifacts. |
| Interrupted repair | Replacing an artifact before committing its new checkpoint hash stranded the previous state after interruption. | Immutable content-addressed artifacts preserve the last atomic checkpoint. A separate process exits abruptly during repair, reopens as interrupted, and resumes to accepted completion without resetting attempt counts. |
| Workspace concurrency | Process-local locks alone did not establish exclusive ownership across connector instances. | A second process is refused; same-process instances share in-flight ownership and cannot duplicate a pending dispatch. |
| Local-only runtime facade | An injected base runtime could remain remote-enabled despite the facade reporting local-only mode. | The facade refuses remote generation and discovery before transport; local-only status remains authoritative. |
| Codex continuation authority | Unsigned or relocatable checkpoints did not establish a trusted original account, model, workspace and sandbox boundary. | HMAC-authenticated checkpoints bind original account identity, model, thread, exact workspace and runtime paths, and sandbox. Editing payloads or copying a checkpoint to another root is refused before process launch and allowance count. |
| Codex resume concurrency | Reading a checkpoint before acquiring its exclusive lock could replay an attempt committed concurrently. | A deterministic concurrent-commit regression confirms the locked checkpoint is read before accepting a new attempt. |
| Codex sign-out race | The final account check released its lock before launching the child, allowing a launch with old credentials after sign-out finished. | Final identity check and process launch share the authorization lock. A deterministic lock-release schedule confirms no launch after completed invalidation. |
| Codex persisted configuration | The runtime directory lived inside the agent's writable workspace and could be changed before continuation. | The runtime directory is a protected sibling outside every per-run write grant, with its exact location bound by the signed checkpoint. |
| Action-budget exhaustion | A refused excess action skipped frozen verification and required criticism after earlier durable work; a repair could retain a stale pass. | Remaining actions are refused, then current artifact bytes are checked and reviewed. Valid within-budget work can finish; an invalid replacement cannot inherit the earlier pass. |
| Parallel cost evidence | Parent capabilities omitted costs because model requests were recorded only in child histories. | Parent evidence aggregates each attempted branch request, including failed, interrupted and late responses, without charging the runtime budget a second time. |
| Branch initialization interruption | A child's first checkpoint was saved before parent ownership and registration, allowing an ungoverned orphan after interruption. | Parent identities and allocations are reserved first; the first child checkpoint records ownership. Interrupted initialization resumes the same child identity and allocation. |

The original partial or malformed outcomes are not promoted into passes. Fixed-source checks are reported below.

## Executed independent suite

Command from repository root:

```sh
python3 -m unittest discover -s products/alpha-genesis-harness/tests -p 'test_independent_*.py' -q
```

**74 tests passed in 2.583 seconds**, with no skips, on the integrated working source reviewed in this session: 32 general boundary regressions, 15 Codex continuation/profile regressions, 6 source-tool regressions, 18 strategy executor regressions and 3 paired-retrieval regressions. The source-bound release qualification must rerun the suite on the exact packaged bytes; this review is not a substitute for that receipt.

The suite also exercises one-character credential fragmentation across streaming callbacks, transmitted tool-schema budget refusal before dispatch, unsolicited tool refusal, interrupted stream rejection, disabled connection with no transport, incorrect OAuth state with no code exchange, credential-file symlink refusal, caller mutation of frozen acceptance, forged model verification refusal, artifact tampering before reuse/export, cancellation followed by a late proposal, foreign-origin HTTP rejection, and an actual loopback ZIP download containing only the verified artifact bytes and a portable workflow record.

The HTTP follow-up accepts a portable workflow larger than 1 MiB through its explicitly larger import envelope, while an ordinary generation request over 1 MiB is refused before reading its body. Workflow source actions reject caller-supplied headers and allowlist overrides, exact-host violations, userinfo and private DNS destinations. A status-only global local-mode guard still blocks retrieval. Source artifacts cannot execute as instruments; imported sources preserve their untrusted bytes without fetching or inheriting verified status, and a rehashed source record cannot smuggle an executable filename. These source tests use a synthetic resolver and never open an external connection.

Every workflow response in these adversarial tests is explicitly supplied by a fixture. This demonstrates enforcement and executable workflow behavior, not real-model autonomy, current frontier model quality or a new discovery advantage. Separate model invocations do not make their judgments independent empirical evidence. Document acceptance checks remain structural. Real authentication, remote quota behavior, operating-system protections and commercial authorization require their separately stated live checks.

## Strategy follow-up

The strategy regressions check isolated branch artifacts, deterministic accepted-branch selection, fixed sums of iteration/action allocations and a model-call cap that includes critic, adversary, economist and researcher overhead. Internal child IDs cannot be dispatched directly through public step/start/resume operations. Adaptive success does not activate alternatives; an actual recorded failure is retained when the registered topology changes, with the original providers, permissions and acceptance unchanged.

The monetary test uses the real `Runtime` and atomic `Budget` with an authored local sender. Two branches attempt reservations while the first response is held; the shared balance permits exactly one request to dispatch. The accepted response is accounted once and all reservations are released. This is a synthetic price/usage test with no paid request. Cancellation discards both late branch proposals. Pause, service reopen and explicit resume preserve the original branch IDs and consumed attempts. A checkpoint-boundary interruption during branch initialization cannot expose a standalone child or create a second allocation on recovery. Rehashed child imports cannot enlarge the frozen parent contract, imported branches remain paused and unverified, and corrupt inherited bytes are refused before dispatch.

Adversarial cases are adjudicated against the operator-frozen reference or original case. A model's invented expected value cannot override that reference; an actual counterexample invalidates an initial pass. Claims without a reference stop for review and do not register a capability. The operator reference remains an explicit assumption outside its supplied checks.

The paired driver was independently rerun and its recorded source hashes match the reviewed files. Both arms use equal two-call/two-action budgets, the same objective, initial context and structural acceptance, with isolated artifacts and only the retrieval permission differing. The control honestly abstains; the treatment resolves the synthetic source value. Changing the source coefficient changes the observed answer, and a missing ground-truth coefficient is refused before creating an experiment. A deterministic reader also resolves the same fact with zero model calls. This qualifies information access and evidence handling, not research superiority, live retrieval or an economic advantage.

## Credential portability and CI follow-up

The credential reader now uses a zero fallback when the host lacks `os.O_NONBLOCK`, while retaining regular-file and applicable owner-permission checks. The separate 13-test ChatGPT suite passed in 0.122 seconds, including simulated absence of that Unix flag. This Linux-host test does not qualify Windows authentication, DPAPI behavior, installation or credential protection on an actual Windows machine.

CI/browser review corrected a fixed-port false-pass risk: the replay now waits for its own child to announce an ephemeral loopback origin and confirms an HTTP 200 response and a live child. Chrome/Chromium lookup, startup errors and child cleanup are explicit. Failure receipts and available screenshots, including native Codex probe results, are retained by the unconditional evidence-upload step. Syntax, YAML and package/lock consistency checks passed; the lock integrity encodings were checked, not freshly authenticated against remote tarballs. Three local negative-path exercises preserved failure receipts and stopped their child: missing Python, a ready connector followed by a missing browser, and actual Chromium fallback blocked by host socket permissions. Later keyboard, save/reload, portable JSON import, disabled Codex and offline-file checks were read in the current replay; their graphical execution requires source-matched hosted receipts. This review adds no macOS, Windows or final-source browser PASS claim.

The subsequent macOS/Windows CI addition selects exactly one native executable from the locked platform-specific Codex package and runs the existing probe without authentication or model calls. Its receipt must agree with its exit code (`0`/`PASS` or `2`/`BLOCKED`), declare zero inference calls and no real credentials, and records the source, archive digest and host. Raw output is preserved, and release publication depends on both platform jobs. A blocked native sandbox remains explicitly blocked even when the evidence-recording step succeeds.

This follow-up reproduced and corrected a qualifier false-pass: assigning PASS before parsing the browser receipt left PASS/exit zero after a JSON error. The qualifier now validates browser status, exact source, host-platform mapping and empty error list before assigning PASS; exceptions force FAIL. Seven synthetic subprocess scenarios were exercised: malformed receipt, wrong source, wrong status and wrong platform all failed, while valid Linux/Windows/macOS platform-name mappings passed. These simulations test receipt validation, not operation on those operating systems. Actual platform qualification still requires the corresponding hosted receipt.

## Follow-up source identities

The final focused run above observed these SHA-256 identities. Later edits require the release qualification to rerun the relevant checks.

| File | SHA-256 |
|---|---|
| `bridge/chatgpt.py` | `70b9dde0531090612fe9de41247af2a6fdb4386ec560b457f329118b59f316c6` |
| `bridge/codex.py` | `37ed92af69ea0458321d64d851659113402f11a61880e120f52e79d903ff2ca7` |
| `bridge/codex_permissions.py` | `0b92a29817d761bb13994ca4a62c1b825e0d7f44712d2b88e0eecbc89319b578` |
| `bridge/workflows.py` | `098410d3b410383ed17ffc60e14deb55ac26a45546b6b71d5a0311713538462d` |
| `bridge/workflow_strategies.py` | `f995a052f7b3d6ad6a6017665138d051c6d5df65a2155ae81a987156a6541a06` |
| `bridge/strategy_demo.py` | `85881056d8b1b0c1e8e597bec95387d23b94ba48de8a62ed1650196ab36b9a30` |
| `bridge/server.py` | `6062338ae27ad8187c6c50c2ccb75c0e1ce76e2959b07f6600e5fe2ab25acb34` |
| `bridge/services.py` | `fed69688610d2d8045d7fa95eb1c15eebea8f62ee8ccfed2920cf1dc6a67c0c6` |
| `evidence/UI_BROWSER_REPLAY.cjs` | `3d5909b7dffac331549ae2c8cb9ea7f8a30021bb0087f803523d3c01aa12e5d0` |
| `scripts/qualify_platform.py` | `4edbdd3ab27cf8c2d84ee8e5d67bb5183cd674a2657497cda37983da3a4cf647` |
| `.github/workflows/alpha-genesis-harness.yml` (repository root) | `467bb4992be7d89a9a524a3056a641319ae432257ed238d25b8ef44ad6cf0be5` |

## Interruption reproduction details

The crash regression starts a subprocess with three declared iterations: one failing construction, one repair interrupted with `os._exit(77)` after immutable artifact creation but before checkpoint commit, and one explicit recovery attempt. The prior mutable-artifact implementation produced `WORKFLOW_INTEGRITY` at reopen. The corrected implementation preserves the prior referenced bytes, reports interruption, retains the failed/interrupted attempts and finishes the third attempt under the originally declared limit. Tampering tests now alter the authoritative `.objects/<sha256>` bytes; modifying an unused former filename alias is not a tamper test.

Codex review also prompted thread/turn identity checks, bounded protocol buffering, app-server shutdown before artifact collection and descriptor-relative no-follow artifact reads. The independent continuation tests use a synthetic JSON-RPC process and explicitly injected schema and runtime validators. They establish original account/model/path binding, preserved read-only rights, refusal before count consumption, interrupted-thread recovery, and cancellation before the handshake starts a thread or turn. They do not exercise an actual Codex sandbox.

The final implementation uses the named `harness_isolated` permission profile through the experimental app-server protocol, replacing the initial unsupported legacy sandbox fields. Independent assertions check default root denial, network denial, exact workspace access, no legacy sandbox override and refusal to start a turn unless the app-server confirms the requested profile. A native-probe failure stops before the credential-bearing child and local allowance count; sign-out during the probe also prevents launch. The probe test confirms a synthetic environment sentinel, removal of inherited API keys, a loopback-only model-provider URL, no inference request and cleanup of test files. This is a protocol fixture, not proof that the host enforces a sandbox.

The owner's `CODEX-CLI-COMPATIBILITY.json` reports the current stable and preview CLIs support named profiles, while this engineering host refuses native sandbox setup. This is a host limitation, not a universal Codex-version blocker. Production execution requires that local native probe to pass and the operator's authentication. No completed authenticated Codex run or live continuation is claimed here.
