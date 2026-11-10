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
