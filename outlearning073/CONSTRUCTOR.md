# Included-agent construction and frozen reuse

The included agent wrote `constructor.py` during actual K1 development. Python
does not contain an autonomous model callable, an open-ended generator, or a
mechanism for editing model weights. Subsequent calls deterministically compile
the public task and charged diagnostic receipts through the frozen code. This is
a narrower engineering construction claim.

The constructor author used only the four permitted development requests passed
to `make_session`, `session.public`, `session.probe`, and development-only calls
to the independent verifier. The author did not read world/verifier/baseline
source, request internals, confirmation definitions, latent families or seeds,
or K2 outcomes. There were no external calls. The initial public contract omitted
the K2 JSON formula; the coordinator supplied the public schema before the code
was frozen. No confirmation instance was supplied for that addition.

## What observations changed the executable procedure

`K1_GENERATION.json` records all 21 exploratory/systematic probe attempts, their
actions and exact public receipts, proposed-action hashes, competing explanations
and decisions. Four further construction checks record their four actual runtime
diagnostics and all 64 development fault schedules. The preliminary same-key
probe was run in a separate session and is counted; it was not silently replaced
by the systematic repeat.

| Attempt | Observation | Resulting code |
| --- | --- | --- |
| Lost ACK, then unkeyed retry | Two counted effects in every development contract | Timeout never means absence; reject blind unkeyed retry |
| Lost ACK, same-key retry | One effect in two contracts, two in the others | Diagnose same-key settlement; keys are not assumed supported |
| One key across two intents | First intent committed, second absent with zero effects after a declared bound | Give each intent a distinct request/intent key |
| Late write, immediate read, delayed read | Absent followed by committed in bounded contracts | Wait the public in-flight plus visibility windows before treating absence as safe to retry |
| Same-key retry during late completion | One eventual effect in key-supporting bounded contracts, two in the unsupported bounded contract | Retain acknowledgment-gated key settlement only for a diagnosed shared contract |
| Unbounded late write and reads | Unknown reads and unresolved pending effects | Keep neither/unknown explanations and refuse unsupported settlement |

The new reusable code primitive, `settle_intent`, emits executable low-level
actions. In its key branch it retries with the same intent-distinct key and
requires a committed acknowledgment. In its bounded-read branch it writes,
waits through both uncertainty windows, reads, and retries only on `absent`.
`unknown` stops execution. The constructor calls this primitive for every
required intent and records every call and its emitted-steps digest separately
from the artifact. It composes predecessor settlement with a dependent write
whose dependency is the actual `$token:reserve`; no token is fabricated.

The artifact has exactly `steps` and `output`. `construct(session, retained=None)`
returns that artifact. `build(session, retained=None)` returns the artifact and a
separate trace; `construction_trace()` exposes the last trace. `retained_content()`
returns the same substantive JSON retained in `K1_GENERATION.json`. The strong
ordinary control receives those facts and access to this primitive source; it
may implement the same best workflow. A tie or treatment loss remains valid.

K1 output is computed from each public object's exact UTF-8 content. K2 output
is independently computed from public integer rows: the reservation contains
the public job id and row count, and publication contains count, sum, sum of
squares and SHA-256 of the canonical compact JSON row list. Unsupported schemas
are refused. A noisy or unaffordable diagnostic cannot prove safe keys; the code
uses finite public settlement bounds if available and otherwise refuses. The
complete compiled worst-case execution must fit the public deadline.

## Development result and full local units

| Development request | Decision | Accepted schedules | Maximum operation units | Maximum avoidable loss |
| --- | --- | ---: | ---: | ---: |
| 0 | Deliver | 16/16 | 4 | 0 |
| 1 | Deliver | 16/16 | 4 | 0 |
| 2 | Deliver | 16/16 | 14 | 0 |
| 3 | Refuse | 0/16 | 0 | 0 |

The refusal preserves uncertainty and is not counted as delivery. All four exact
outputs were correct. Development diagnostics consumed 103 resource units:
91 for exploratory/systematic probes plus 12 for construction checks. Executing
all 64 development verification schedules consumed another 272 operation units.
Those units do not include an invented dollar price for agent development or
inference; actual billing is unknown and requires separately labeled economic
assumptions. The four verification calls ran once after code generation; there
was no failed-delivery correction or repeated tuning against confirmation.

The constructor source was frozen before any K2 execution by this author:

- Constructor SHA-256: `ca71eee81a40cf32b07a6e51d1baa10bb2ed410e0696e6871aed02a8082d6c32`
- Primitive source SHA-256: `27058ad1290888f19692f949eff69f1e46c6f5f6b9d3fa57aacf171ebac3b16a`
- Retained JSON SHA-256: `2763ae1a0fa616ceb709a736846ab28cb24be1d3a8f6c91c37b34b6ae411f6c8`

These finite observations support the authored service-contract compiler. They
do not establish live-service exactly-once guarantees, physical commissioning,
commercial demand, autonomous scientific discovery, or a retained-method
advantage. Changes to the diagnostic instrument, key guarantees, visibility,
subsequent-call acknowledgments, dependency semantics or output schema invalidate
the stated applicability and require fresh validation.
