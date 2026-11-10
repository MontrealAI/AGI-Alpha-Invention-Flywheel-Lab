# Integrated engineering qualification

This file records the initial local integration before hosted publication. Later hosted and browser receipts must identify their exact source separately. The product is a release candidate; this is not a declaration that the complete commercial mandate has been met.

## Executed checks

- Final local integration: 51 Node tests passed (23 engine development tests and 28 independently prepared acceptance regressions).
- 45 Python tests passed: 23 provider/HTTP/canonical-adapter checks, 16 adversarial archive checks and six independently written archive-execution/public-preview checks.
- Existing repository platform checks passed (16); canonical mechanism suites passed (46); existing research-site checks passed (22).
- `evidence/UI_REPLAY.cjs` passed nine application flows in jsdom 26.1.0: editing a mission then saving/exporting without Continue; importing and executing a custom instrument; save/reopen; demo verification; retention; equal-content successor comparison; artifact/dossier export; French switching; and downgrading a reopened capability's current verification. This emulates DOM behavior. It does not render pixels or establish a native browser/OS pass.

The additional `evidence/UI_PARALLEL_REPLAY.cjs` passed nine mocked bridge checks: concurrent independent requests, frozen prompt, partial failure/cost preservation, explicit artifact selection, cancellation of all requests, post-cancel result suppression, active-workspace replacement protection, deferred file-read protection and cancellation ownership. These are in-memory fixture responses, not vendor authentication.

The UI test's initial harness mistakenly targeted the mission heading instead of the name input. Correcting that test selector resolved its failed assertion; no product behavior was changed to satisfy it.

Reproduce the DOM test using a separate temporary development dependency directory (no dependencies are bundled with the application):

```bash
npm install --prefix /tmp/harness-dom-test --no-audit --no-fund jsdom@26.1.0
NODE_PATH=/tmp/harness-dom-test/node_modules node products/alpha-genesis-harness/evidence/UI_REPLAY.cjs
NODE_PATH=/tmp/harness-dom-test/node_modules node products/alpha-genesis-harness/evidence/UI_PARALLEL_REPLAY.cjs
```

The remaining dependency inventory is in `THIRD-PARTY.json`. Main automated test commands and exact archive verification are documented in `docs/RELEASE.md`.

## Independent review corrections

In addition to the preserved independent findings, review of the release integration found and repaired four issues before publication:

1. The Pages sparse checkout lacked a customer example consumed by its tests. The exact file is now included.
2. Archive hashing, verification and extraction could observe different path contents. All three now consume the same bounded immutable byte snapshot; a path-replacement regression executes only the originally verified bytes.
3. An archive test child could inherit publication credentials. Download and operation are separate workflow steps, and child processes receive only an explicit environment allowlist.
4. The preview manifest named a source revision while reading mutable working files. Publication now reads the four allowed assets directly from the selected Git commit. A dirty/deleted-worktree regression verifies source identity.

## Product and research limits

The two synthetic missions demonstrate executable instruments, conditional economics, falsification and an honest conventional tie/winner. They establish neither physical capability nor real demand, new-market superiority, general transformational discovery or improved inventive intelligence. API adapters have protocol and loopback tests; no live authenticated vendor call was made. No API keys, paid services or real transactions were used. Actual assistant/host economic costs are unmeasured.

The available cloud browser refused local-file URLs and could not reach the workspace's loopback HTTP server. Initial rendered-browser review therefore awaits the allowlisted public candidate preview. Windows/macOS launch tests, signing/notarization and real provider qualification remain unexecuted. The browser application has no native installer and requires no installation for its manual workflow.

Squarespace administration presented its login screen. No store draft, uploaded customer archive, checkout test, sale or publication has occurred. Final listing copy and configuration instructions are prepared in `commercial/`; a draft is not a deployment.

## PR 320 review correction and final local regression

GitHub review of source `74d8b5fe435a6a0cd670d57158adb5f68ebd5cc0` exposed three additional issues, independently reproduced before correction:

1. JSON escaping and pretty printing could make an accepted project export larger than the old serialized import bound. Decoded processing limits and a conservative 64 MiB UTF-8 transport envelope are now distinct. Export preflights actual reopening semantics, and response installation remains transactional. Escaped and Unicode roundtrips, oversized encoded documents and aggregate growth are independently covered.
2. Integer add/sum could overflow and later return to a seemingly safe but wrong result. Every numeric integer input and intermediate is now checked, including multiplication followed by zero; invalid arithmetic cannot earn a successful execution verdict.
3. Workflow-only and arrangement-only proposals were hidden behind an unrelated instrument requirement. The three artifact panels are now independent. Replacement clears stale active workflow aliases while retaining historical contributions and results; malformed saved workflows remain inspectable and fail on compilation.

After these corrections, root integration executed **60 Node tests** (26 development, 34 independent), **45 Python tests**, **12 DOM application flows** and **9 mocked parallel-model checks**; all passed. DOM emulation still does not establish graphical or cross-OS launch qualification. The original failures and source identities remain in the independent review evidence.

A separate single live public-source attempt reached the real loopback source route, but public-address validation refused the request before TLS. No remote content, hash, freshness or changed-source result was observed. `live-source-qualification.json` preserves the exact result and unchanged bridge-source identities. Protocol fixtures and this refused live attempt do not establish working Internet retrieval in this execution environment. No alternate routing, API credentials or paid requests were used.

## Connected-mode review and hosted interface coverage

Review of source `04fa5adffb60d6611a8b4f9da7bcf337d664a766` independently reproduced an incorrect comma expression: direct and transformational connected imports were always taking the parallel-candidate branch. The condition now tests only the declared mode, preserving the captured project owner. The new tests execute each supported artifact kind in both non-parallel modes and retain explicit selection for parallel alternatives.

Further independent checking found that comparing workflow object references after the engine cloned a project could discard user-edited workflow settings even for commentary. Cleanup now follows an actual accepted replacement workflow field. Commentary and unrelated artifact imports preserve edited workflows, including their executable inputs and save/reopen behavior. Original failing receipts and corrected source hashes are retained by the independent reviewer.

The maintained DOM replays now cover 12 general application flows and 14 connected-mode checks. A separate, independently authored `UI_CONNECTED_ACCEPTANCE.cjs` covers 15 controller scenarios. All three remain mock-provider DOM emulation, not graphical or authenticated vendor qualification. The hosted product workflow now executes these replays using the exact `tests/dom/package-lock.json` dependency graph with installation scripts disabled. No external modules are bundled in the customer runtime.

For the locked DOM checks, copy `tests/dom/package*.json` to an empty development directory, run `npm ci --prefix /absolute/development-directory --ignore-scripts --no-audit --no-fund`, then set `NODE_PATH=/absolute/development-directory/node_modules` when invoking each evidence replay. The ordinary 60 Node and 45 Python product regressions remain passing.
