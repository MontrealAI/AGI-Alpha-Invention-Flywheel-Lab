# Connected014 test-source closure 123 — frozen prospective protocol

**Baseline:** main `e23ab09852d3ac14ff91156e8910df7e3c22268e` / public prerelease `connected014-e23ab09852d3ac14ff91156e8910df7e3c22268e`.
**Origin:** [issue #323](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/323), independently preserved 59 attempted / 49 passing / 10 errors on extracted public source under Python 3.13. The documented operating environment is Python 3.12; those failures are not a financial-engine failure and must not be rewritten as passes.

## Hypothesis and minimal repair
The canonical source ZIP intentionally ships `tests/test_connected*.py` but omits two nonprivate transitive developer-test inputs: `tools/p0_source_guard.py` and `evidence/strategic024-publication/COMPOSED_SOURCE_BINDING.json`. Include only these two safe files **when the corresponding included tests are present**, preserving original hashes and the original test/authority expectations. The tests must receive authentic bytes rather than a synthesized binding or a permissive test skip. Do not change `connected_enterprise/runner.py`, `finance.py`, any accounts, signing keys, queues, liabilities, archive guards or historical evidence.

## Frozen acceptance and negative controls
1. New source-distribution manifest contains the two required files and their actual SHA-256, both inside the signed/source-bound package identity when their dependent test modules are included.
2. Both presence and omission cases are tested: absent dependent test means its developer-only dependency is not gratuitously packaged. Missing dependency when needed fails closed.
3. On a clean extracted ZIP under Python **3.12**, repeat exactly the four issue-323 test modules, including all original cases: `tests.test_connected_p0_source_guard`, `tests.test_connected_lifecycle`, `tests.test_connected_recovery_preflight`, `tests.test_connected_release`. **No skips or weakening**; the existing 10 errors remain an immutable negative baseline.
4. Root and connected release regression workflows pass on the exact PR source SHA, with source archive, runtime, dependency and artifact receipts. A normal merge and actual public-release download must be qualified separately.
5. An adulterated or missing file/fixture cannot be silently repaired by fetching a network copy; archive manifest hash/CRC guards remain unchanged. Private keys remain excluded.
6. No change in claimed paying contracts, native profit, original-account custody, future earnings or US$3B attainment; commercial verdict remains **UNQUALIFIED**.

**Decision policy:** If introduced regressions or full closure failures appear, retain failures and diagnose before another source revision; do not repeatedly sample for green. This is release reproducibility support for eventual source-bound enterprise qualification, not a new Blue Sky flagship, commercial success or permission to overwrite the active native-capital implementation owner.