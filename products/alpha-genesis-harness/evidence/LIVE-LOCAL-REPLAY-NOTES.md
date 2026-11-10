# Local model replay: demonstrated operation, variable construction quality

The [current equality-corrected source](live-local-workflows-v0.3-equality-fixed.json)
completed a real **local actor–critic workflow** using llama.cpp b12242 and
Qwen3-1.7B Q4_K_M on Linux CPU. Customer HTTP onboarding discovered and
connected the model. The first builder response contained malformed JSON and
was rejected; a second builder response repaired the construction, followed
by a separate critic call. This arm completed in **three calls and two
iterations**. Frozen acceptance passed; the exported evaluator returned
**34 for x=17** outside the HARNESS, and retained reuse returned **82 for
x=41**. Ordinary arithmetic and equal-content reuse produce the same result.
This demonstrates bounded automatic repair in one run, not general invention
or a compounding advantage.

**The current two-policy replay is FAIL overall.** Its single-builder arm
exhausted all three registered iterations, repeatedly representing the numeric
constant `2` as the input reference `{"field":"2"}`. The evaluator rejected
the undeclared input; no invalid artifact was accepted. The actor–critic
success and a prior successful run do not erase this failure or establish
reliable repeatability across policies.

## Preserved attempts

All timestamps below are UTC on 10 November 2026. Each linked receipt records
the exact executed source hashes, pinned model/runtime hashes, outputs and
limits. Each qualified source observation had unchanged source throughout its own
execution. These are separate observations of different source snapshots;
prior receipts do not become current-source evidence after a code change.

| Start | Observation | Outcome | Actual inference calls | Wall / child CPU seconds |
|---|---|---|---:|---:|
| 05:37 | Initial context setup, preserved in the earlier receipts | Both requests stopped at the conservative 8192-token context preflight; no inference dispatched | 0 | 2.65 / 1.77 |
| 05:38 | [Before final integration](live-local-workflows-v0.3-before-final-integration.json), actual and declared context 16384 | Single builder PASS; actor–critic PASS; both exported and reused | 1 + 2 | 28.59 / 53.80 |
| 05:54 | [Prior integration snapshot](live-local-workflows-v0.3.json), context 16384 | Single builder FAIL after three iterations; actor–critic PASS, exported and reused | 3 + 2 | 73.67 / 143.76 |
| 05:57 | [Withdrawn exploratory grammar clarification](live-local-workflows-v0.3-exploratory-unqualified.json) | **FAIL_SOURCE_CHANGED; unqualified** | 1 + 2 | 32.02 / 60.36 |
| 06:46 | [Equality-corrected source](live-local-workflows-v0.3-equality-fixed.json), context 16384 | Single builder FAIL after three iterations; actor–critic PASS after one malformed response and repair, then export/reuse | 3 + 3 | 79.86 / 154.31 |

The last exploratory attempt briefly added two general expression-format
sentences to the builder prompt. The change was withdrawn to preserve the
already frozen source. A stop request raced with completion: both model arms
had run, but the source changed during execution and the probe correctly
refused qualification. Its consumed calls and resource use remain recorded;
its generated outputs are not final-source evidence. Only the two added
sentences were removed. The restored `bridge/workflows.py` SHA-256 is
`05203df3906e44be13e4ed51e4b9766f9e260fd3ee8560bfd99ec3ed4a75cfd9`,
matching both the prior integration and new equality-corrected receipts. The
older receipt’s eight dependencies matched its own source snapshot. Its old
interpreter identity is historical: the new run records the corrected
`bridge/instruments.py` SHA-256
`0a7fb53f8559f04f8b5d9e49ed91b235651541ec7cca87af8152f23c39b551f8`.
All eight dependencies of the new receipt matched the executed files and
remained unchanged throughout that run. The equality correction justified one
new fixed replay with the same prompts, public cases and registered limits;
there was no extra retry or prompt change.

## Scope and reproduction

Run `scripts/probe_local_onboarding.py` with the exact pinned runtime and model
identified in the receipts. The script performs actual HTTP session bootstrap,
model discovery, explicit local connection, construction, deterministic
acceptance, export and reuse. The cases are public arithmetic regressions,
not hidden research confirmation. Each policy permits three iterations and
ten bounded actions; failed attempts are not retried outside that declaration.

The initial context refusal was resolved by configuring a larger actual server
context and the same declared context, without weakening the guard or changing
acceptance. The later construction failure was model output variability, not
a reason to relax the verifier. No provider credentials, paid APIs or cloud
inference were used. Hardware, electricity, engineering, maintenance and
opportunity costs remain unknown; a zero configured token price does not make
the complete experiment free. These observations qualify the stated Linux
llama.cpp operations only, not every local runtime or model.
