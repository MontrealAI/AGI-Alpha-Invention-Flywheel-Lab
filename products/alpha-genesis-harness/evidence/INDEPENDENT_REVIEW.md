# Independent qualification review

This review is by a separate evaluation agent, using the same workspace and execution host. It is procedural separation, not external certification. Independent conceptual arithmetic/economic/adversarial cases were frozen before candidate engine source existed (SHA-256 `822cd80634fa5061f34dafb9f23875f363df7d8662062faa59239262b53029a2`). A separate synthetic affine-calibration set was frozen before its mission artifact existed (`c3c7902ee8a2891e553312d20308466b94d0cba6b7aaa27417ef3b34ff66c776`). Subsequent exposure makes these regression cases, not fresh research confirmation.

## Findings and disposition

| Finding | Reproduction | Disposition |
|---|---|---|
| A release manifest could assert that its own contents matched a source revision without a comparison to that source. | Initial code inspection found `source_matches_commit` copied from manifest to verification receipt. | Packaging owner added externally pinned digest/revision checks and actual Git-source comparison. Standalone manifest consistency now reports source identity as unverified. Independent fabricated-archive regression passes. |
| Retrieval silently dropped the query string when URL path was nonempty. | On adapters.py SHA-256 `7a53cd194f37533ac36df9885970b002a68459c7e17bff92b5e1aac86b3b7b7b`, `https://example.org/paper?version=2` requested `/paper` while retaining full URL in provenance. | Repaired and independently reproduced on adapter snapshot `865b5b748af4ea8cd6ed313f0116c5cf380e31c84b468bc528dcdc4e8f1b687a`: query target includes `/paper?version=2`; malformed usage raises a safe error and retains the complete 0.000017 USD fixture reservation. The corresponding provider regressions pass. |
| Malformed provider usage could make a sent request appear free. | Same adapter snapshot: mocked successful OpenAI text with `usage: []` raised `AttributeError`; spending guard settled to committed `0.0`, reserved `0.0`. | Repaired and independently reproduced on adapter snapshot `865b5b748af4ea8cd6ed313f0116c5cf380e31c84b468bc528dcdc4e8f1b687a`: query target includes `/paper?version=2`; malformed usage raises a safe error and retains the complete 0.000017 USD fixture reservation. The corresponding provider regressions pass. |


| Rival model proposals sharing a local capability name broke discovery. | Two valid contributions each named a capability `converter`; import succeeded, then discovery raised `Duplicate capability id`. | Imported identifiers are now namespaced by contribution, with original IDs, costs and authorship retained. Independent regression confirms both alternatives survive and the cheaper complete path is selected. |
| Imported malformed project rows could fail after replacing the visible workspace. | A project with `sources: [null]` passed engine validation, while UI rendering dereferenced source fields. | Import validation now rejects non-object rows and missing required display fields before UI state replacement. Independent malformed-row cases pass for every required record collection. |
| Imported capability cards displayed a historical pass as current verification. | Static review found the renderer read `verification.verdict` ahead of `currentVerification`, despite import invalidating current authority. | UI owner changed precedence to current verification and labels the historical receipt separately. Browser confirmation is recorded by the UI reviewer, not inferred from this static check. |
| Save/Export could omit visible mission edits before pressing Continue. | Static review showed form fields were copied into the project only on submit. | UI owner bound mission input events to project state. Static inspection confirms the change; browser confirmation belongs to the UI reviewer. |
| Hash checking and ZIP interpretation could read different pathname contents. | Code inspection found separate hash read and ZIP reopen. | Verification now hashes and parses one bounded immutable snapshot. A deterministic path-replacement regression confirms a valid substitute ZIP cannot rebind the externally pinned hash. |

## Test interpretation corrections

The initial independent economic fixture treated `fundingAvailableMinor` as additional outside funding. The engine contract instead defines it as total consortium funds replacing net member payments. The case was corrected from 31 additional to 211 total; expected total resource cost 631, participant payoffs and savings 19 were unchanged. The engine was not changed to manufacture this pass.

A cancellation fixture initially declared too few operations to compile after compilation-cost accounting was strengthened. Its budget was raised to reach the intended cancellation-between-steps boundary; separate zero-budget and overrun rejection tests remain. Capability-ID assertions were updated to check the newly retained original `sourceId` and contribution identity after namespacing, rather than require the obsolete internal ID shape.

An initial candidate-package scan rejected the literal fake PEM marker in this reviewer's malicious-archive test fixture. The marker is now assembled at runtime from split literals, so the strict package scanner remains intact and the test still proves malicious bytes are refused. No actual key was present.

## Executed independent checks

- `node --test products/alpha-genesis-harness/tests/acceptance.test.cjs`: 28 passed, zero failed.
- `python3 -m unittest discover -s products/alpha-genesis-harness/tests -p test_release.py -q`: 16 passed, zero failed.
- Provider developer tests were separately rerun during review; the two reproduced defects are covered by repaired fixture regressions. These are contract/mock/local-wire tests, not authenticated frontier-model calls.
- Five preprepared affine-calibration cases passed, including both endpoints; the deliberately omitted-offset candidate failed all five by 2,500 declared units. Full direct algebra ties the correct instrument. These synthetic cases do not validate any physical sensor or superiority over ordinary software.

## Scope

The official product's ten acceptance requirements are reported individually in `acceptance-results.json`. Correct bounded arithmetic, safe import, provenance handling and ZIP integrity do not establish open-ended invention, authenticated vendor operation, willingness to pay, physical feasibility, recursive discovery advantage, native operating-system validation or a completed storefront deployment.

No paid model calls, API keys, purchases, financial-account actions or outreach were used in this evaluation. Provider responses used for adversarial checking are explicitly fabricated protocol fixtures.

## Supplemental parallel-model review

The later concurrent-provider UI dispatches independent requests with one frozen prompt, waits for every result with `Promise.allSettled`, records failed/cancelled attempts and unknown costs, and retains distinct artifact candidates until the customer selects one. No authenticated vendor request was made in this review.

Static review identified a project-ownership race: replacing the workspace while model requests were pending could attach their responses and costs to the wrong mission. The repaired code captures the originating project for imports, costs, batch and cancellation receipts; checks active work again at the actual workspace-replacement action; and records the frozen prompt and objective. Inspection confirms those repairs. Mock DOM and browser execution are recorded separately by their owners.

The new persisted `providerRuns`, `providerCosts`, `providerCancellations` and `artifactCandidates` collections initially bypassed malformed-row validation. The existing independent malformed-project test was extended to those collections, reproduced a failure for `providerRuns: [null]`, and passed after optional-array validation was added. The updated independent engine suite remains **28 passed / 0 failed** (expanded coverage within the existing test).

## PR #320 review findings: independent reproduction and repair

The three later review findings were independently checked against PR source `74d8b5fe435a6a0cd670d57158adb5f68ebd5cc0`; none is erased by the earlier green checks.

| Finding | Independently observed failure | Repaired qualification |
|---|---|---|
| Escaped response could be saved but not reopened. | Engine SHA-256 `50c38275f2a2af0fa89ddda5d13dd2401f3741ed7fcd1d7b2c644b8d0a303519` accepted 2,600,000 backslashes, exported 5,201,035 encoded characters/bytes, then rejected its own export at the old serialized 5,000,000-character check. | Engine and UI now share a 64 MiB serialized UTF-8 envelope while retaining the separate decoded 5,000,000-text-unit, node and nesting bounds. The encoded allowance covers escaping and bounded pretty-print overhead; it is not a business-scale limit. Escaped and Unicode examples actually reopen; valid JSON one byte above the shared encoded limit is refused. Adding a second 2.6-million-character decoded contribution is rejected transactionally with the first export preserved byte-for-byte. |
| Safe final integer concealed an unsafe intermediate. | Both `add` and `sum` on `[9007199254740991, 2, -2]` returned `PASSED IN SCOPE` with `9007199254740990`; an independent BigInt control gives `9007199254740991`. | Checked intermediate arithmetic rejects unsupported exact-integer evaluation rather than accepting a rounded result. Independent positive and negative reduction cases pass. |
| Workflow-only and arrangement-only proposals had no usable controls. | On the pinned PR head (app SHA-256 `a68f3326f28cb24cbb1a813bf1dda1278fb66d6f5d33e87cf90eb886c6e9cb49`), both valid imports showed `experiment-workspace` hidden because no `instrumentSpec` existed. | The three artifact panels are independently gated. Separate DOM-emulated runs executed a workflow without an instrument and checked an arrangement without an instrument; each saved and reopened correctly. |

Related artifact-selection review exposed one additional failure: after running workflow A, importing workflow B still displayed A because the old `workflowSpec` alias took precedence. The repaired import/selection path clears obsolete active definitions and inputs while retaining historical run records. An independent DOM replay changed from `x × 2` at `x = 5` (10) to `x × 4` at `x = 9` (36); the replacement remained active after save/reopen.

A separate mocked parallel replay selected an arithmetic proposal, ran its default workflow, then selected the competing arrangement-only proposal. The prior active instrument, workflow and workflow inputs were absent afterward; both rival contributions and artifact candidates remained retained, and the selected project exported and reopened successfully. These tests used jsdom 26.1.0 and in-memory responses, with no network, graphical browser or authenticated vendor calls.

The updated independent engine acceptance suite is **34 passed / 0 failed**. The expanded serialized-envelope tests use the shared exported limit rather than the obsolete 5,000,000 encoded-character policy. The earlier failure and scope remain recorded above. Root integration records the final broader suite and publication state separately.
