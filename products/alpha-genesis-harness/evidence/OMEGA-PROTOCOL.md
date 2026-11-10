# Ω GENESIS NEXT — independent qualification protocol

Protocol version: **omega-evidence-reuse/1**, fixed 2026-11-10 before observing
the new candidate's execution. Base product source:
`8d69f4f84d0b7e64fe7b55bc7a607294ecac08fa` (HARNESS 0.2 candidate, PR #324).
This is a finite, authored engineering comparison, **not a blinded empirical
study, autonomous discovery claim, or commercial release approval**. The
protocol and evaluator belong to the review side; generated candidate code
must never choose or edit them. The parent execution will bind this document
and test code to the final source revision and hashes.

## Repository limitation and useful outcome

`bridge/workflows.py::WorkflowService._verify` evaluates every frozen acceptance
case after construction and inheritance. Existing retention preserves usable
artifacts, but does not provide a dependency-bound verification index for
deciding when evidence can safely be reused. The proposed enabling instrument
is an exact-content, checker-identity and dependency-identity evidence index.
Its immediate useful outcome is correct reuse or revalidation of HARNESS
instrument checks. Its successor is a different internal operation: allocate
the next validation effort to still-unknown or changed capabilities. This
removes repeated evaluations where the declared applicability remains exact;
it does not establish truth outside those declarations.

## Arms and equal permissions

1. **Baseline GENESIS Ω:** evaluate each requested check afresh using the current
   bounded instrument interpreter and independent expected outputs.
2. **GENESIS Ω+1 candidate:** use a constructed isolated copy of the proposed
   evidence mechanism, retaining results only within exact declared conditions.
3. **Strong ordinary reuse:** conventional content-addressed memoization over
   the same full payload, checker identity and dependencies. It receives the
   same information, may build its small index, and may reuse successful work.
4. **Ablation:** disable or withdraw inherited entries on the successor task.

All arms receive identical requested outputs, observation access and acceptance
requirements. No candidate receives free uncounted validation or hidden answers.
The ordinary control must not use weak label-only or input-only caching.
Execution telemetry, evaluator-call counts and known construction work are
reported separately. Unknown engineering, host, maintenance, integration and
economic costs stay unknown; zero paid API calls does not mean zero full cost.

## Fixed correctness and adversarial cases

The following conditions are fixed before seeing candidate results. Tests may
adapt to the public Python API but must preserve these semantic expectations.

| ID | Condition | Required observation |
|---|---|---|
| C01 | Same complete payload, checker and dependencies twice | Same accepted output; second execution may reuse; one evaluator call |
| C02 | Same labels, different source/instrument bytes | Fresh evaluation; no stale success |
| C03 | Changed input or expected acceptance value | Fresh evaluation, including a failing expected value |
| C04 | Checker identity changed | Fresh evaluation |
| C05 | One dependency changed, removed or added | Fresh evaluation |
| C06 | Explicit invalidation of a used dependency | That entry cannot be reused; independent entries may remain |
| C07 | Same content with different JSON object key ordering | Semantic identity remains stable |
| C08 | Mutate caller-owned result/payload after checking | Stored evidence is not silently rewritten |
| C09 | Corrupt persisted/exported result or its identity | Reject it or revalidate; never accept forged success |
| C10 | Cancelled/withdrawn computation | No successful reusable entry is retained |
| C11 | Failed semantic check | Failure remains failure; no promotion to accepted capability |
| C12 | Bad numeric values, oversized or malformed records | Bounded refusal; no unbounded execution or nonfinite ranking |

Self-upgrade construction must produce actual source bytes in an isolated
candidate directory. It must preserve the original evaluator and source files,
exclude credentials and payment/release authority, and produce a source hash
and inspectable diff or candidate source. Qualification can reject a candidate;
promotion requires explicit operator authorization and a fixed passing receipt.
Unqualified promotion and changing the frozen qualification contract must fail.

## Successor task and independence limits

After initial qualification, use a separately identified set of capability
checks and changed-dependency observations to choose the next useful experiment.
The successor compares the inherited index, no inherited index and strong
ordinary reuse under the same finite evaluator-call allowance. Inspect whether
the chosen experiment addresses still-unknown evidence instead of repeatedly
validating unchanged work. This is a new task relative to instrument checking,
but the authored cases and protocol are public: call it an **authored distinct
successor**, not a hidden or genuinely unseen external evaluation.

Acceptance requires correct current outcomes, rejected invalid transfers and
traceable actual contribution of the inherited mechanism. Sequential execution
alone is insufficient. If ordinary reuse matches the candidate, report the tie.
If complete costs remain unknown, no complete-cost superiority may pass. An
advantage in evaluator-call count against repeated recomputation is narrowly
reported and cannot stand in for advantage over the strong control.

## Decision and retention

The independent test program must exit nonzero for a failed invariant. The
receipt records every arm and attempted case, candidate and evaluator hashes,
wall/CPU telemetry where available, measured evaluator calls, unknown costs,
retention/promotion decision, and successor verdict. Failure is a useful result;
do not retune public cases after observing failure or silently replace a failed
candidate receipt. Repairs receive a new source hash and a fresh reproduction.

Passing this protocol qualifies only its bounded implementation behavior.
General self-improving intelligence, a novel invention method, causal benefit
on genuinely unseen external tasks, profitable demand, full customer readiness,
live cloud inference, eligible ChatGPT Pro consent, commercial OpenAI approval
and cross-platform graphical operation remain separate gates.
