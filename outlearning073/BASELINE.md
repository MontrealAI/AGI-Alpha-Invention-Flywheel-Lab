# Ordinary construction control

This control uses conventional black-box qualification, explicit request identities,
and finite-state workflow construction. It is an independently implemented
algorithmic control, not a measured 100%-human productivity experiment or an
execution of a second frontier model. Its implementation must freeze before K2
confirmation. Development may use the same exposed K1 evidence as the retained
constructor; no sealed outcome may determine its procedure.

## Procedure fixed before confirmation

1. Read only the task's public specification and the same substantive retained K1
   content made available to the retained constructor.
2. Prefer robust construction over unnecessary diagnosis. When public maximum
   in-flight delay B and visibility delay V are finite, construct a single-write,
   immediate-read route. If unresolved, wait until B+V has elapsed from submission,
   read again and retry only after the original must have committed or disappeared.
   No sacrificial probe is needed. Stable distinct per-intent keys work under both
   global and intent-specific deduplication, so scope diagnosis adds no useful
   information for this outcome.
3. When that bounded read-back route is unavailable or cannot meet the deadline,
   repeat one sacrificial intent with the same key and payload. One effect for the
   two immediate writes qualifies keyed retries only within the evaluator's
   explicitly stipulated homogeneous finite service family. Missing/noisy counts,
   no deduplication or an unaffordable diagnostic leave the contract unresolved.
   Charge every affordable probe; an observed finite delay is not a new guarantee.
4. Compile an explicit low-level workflow with conditional continuation and
   dependency ordering. Every K2 publication refers to the reservation token
   actually acknowledged in that execution. Both committed, not-committed and
   neither/pending explanations remain possible; choose a robust policy rather
   than guess the hidden fault label.
5. If the public budget or deadline does not permit qualification and safe useful
   completion, return an explicit refusal rather than invent a successful result.

The control may use every primitive and probe available to the treatment. It is
not restricted to the treatment's original two explanations, and it may generate
different probes and observation histories. Both arms have the same access rights
and execution envelope; actual operation counts and costs must be reported rather
than assumed equal. Information-content matching does not imply identical future
observations.

`baseline.build(session, retained=None)` returns `(artifact, construction_record)`;
`baseline.construct` returns the artifact alone. The artifact has exactly the
world interpreter's `steps` and `output` keys. Construction records expose the
two candidate procedures considered, selected branch, diagnostic count/units,
declared worst operation count and reason. Output arithmetic and SHA-256 are
independently implemented from public inputs; neither constructor imports the
verifier or its expected-output helper. The ordinary control receives equal K1
content but need not pretend an established identity rule requires new learning.

## Exposed development, before confirmation

All four exposed K1 development requests were inspected using this control and
the separately authored verifier. The first three accepted all 16 registered
fault schedules, with zero avoidable loss and maximum operation counts 8, 8 and
12. No diagnostics were required for these public bounded-readback contracts.
The fourth request had no sufficient read-back guarantee and its two-write probe
exhibited no deduplication: the control refused, spending two diagnostic units
and causing no production side effects. That refusal is not a delivered outcome.

An initial wait-first implementation also passed those exposed technical checks.
Before confirmation, immediate read-back was added to avoid paying the maximum
delay when an early acknowledgement is already available. Worst operation counts
remained 8, 8 and 12; totals across the 16 explicit fault schedules are 80, 80 and
136. These totals are enumerated schedule sums, not empirical expected costs or
probabilities. No K2 confirmation request was executed during baseline development.

## Basis and limitations

Request identities, server-side deduplication and reconciling ambiguous outcomes
are established techniques: [AWS's idempotency account](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/).
Conventional composition includes [saga orchestration](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html).
Black-box learning and bounded conformance testing are existing capabilities of
[LearnLib](https://learnlib.de/); this small control does not claim to implement
the complete LearnLib algorithms or their guarantees.

[Microsoft Research's September 2026 study](https://www.microsoft.com/en-us/research/publication/where-does-exactly-once-live-model-harness-and-tool-contract-effects-on-duplicate-side-effects-in-llm-agents/)
already studies lost acknowledgements, late commitment and missing/eventually
consistent reads. Its impossibility boundary rules out crediting local retry
logic with guarantees unsupported by the service contract. Finite authored worlds
can test bounded contract-relative correctness; they cannot establish universal
exactly-once execution or genuine external validation.

A tie or cheaper ordinary construction is an admissible result. A baseline loss
does not by itself establish a learned discovery-method effect: differences in
candidate language, substantive information, development, search and observation
costs require inspection.
