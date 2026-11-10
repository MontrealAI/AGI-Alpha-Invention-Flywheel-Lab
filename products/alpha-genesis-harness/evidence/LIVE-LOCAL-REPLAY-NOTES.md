# Local model replay: demonstrated operation, variable construction quality

The final source completed a real **local actor–critic workflow** using llama.cpp
b12242 and Qwen3-1.7B Q4_K_M on Linux CPU. Customer HTTP onboarding discovered
and connected the model, the builder constructed a bounded calculator, and a
separate critic invocation completed. Frozen acceptance cases passed; the
exported evaluator returned **34 for x=17** outside the HARNESS, and retained
reuse returned **82 for x=41**. Ordinary arithmetic and equal-content reuse
produce the same result. This does not establish an inventive advantage or a
genuinely different successor capability.

**The complete final two-policy replay is FAIL.** Its single-builder arm
exhausted all three registered iterations. The model repeatedly represented
the numeric constant `2` as the input reference `{"field":"2"}` and briefly
wrote the wrong filename. The unchanged evaluator rejected the undeclared
input; no invalid artifact was accepted. A prior successful run does not erase
this failure or establish reliable repeatability.

## Preserved attempts

All timestamps below are UTC on 10 November 2026. Each linked receipt records
the exact executed source hashes, pinned model/runtime hashes, outputs and
limits. The two qualifying source observations had unchanged source throughout
their own executions; they are separate observations of different server
integration snapshots.

| Start | Observation | Outcome | Actual inference calls | Wall / child CPU seconds |
|---|---|---|---:|---:|
| 05:37 | Initial context setup, preserved in the primary receipt | Both requests stopped at the conservative 8192-token context preflight; no inference dispatched | 0 | 2.65 / 1.77 |
| 05:38 | [Before final integration](live-local-workflows-v0.3-before-final-integration.json), actual and declared context 16384 | Single builder PASS; actor–critic PASS; both exported and reused | 1 + 2 | 28.59 / 53.80 |
| 05:54 | [Final integration](live-local-workflows-v0.3.json), context 16384 | Single builder FAIL after three iterations; actor–critic PASS, exported and reused | 3 + 2 | 73.67 / 143.76 |
| 05:57 | [Withdrawn exploratory grammar clarification](live-local-workflows-v0.3-exploratory-unqualified.json) | **FAIL_SOURCE_CHANGED; unqualified** | 1 + 2 | 32.02 / 60.36 |

The last exploratory attempt briefly added two general expression-format
sentences to the builder prompt. The change was withdrawn to preserve the
already frozen source. A stop request raced with completion: both model arms
had run, but the source changed during execution and the probe correctly
refused qualification. Its consumed calls and resource use remain recorded;
its generated outputs are not final-source evidence. Only the two added
sentences were removed. The restored `bridge/workflows.py` SHA-256 is
`05203df3906e44be13e4ed51e4b9766f9e260fd3ee8560bfd99ec3ed4a75cfd9`,
matching the final integration receipt. All eight executed-source identities
in that primary receipt matched the current files when this note was written.

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
