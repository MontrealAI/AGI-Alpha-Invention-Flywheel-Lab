# Fresh bilingual mission study

The evidence-bound executor and the ordinary same-model comparator each completed **0 of 4** tasks to the registered acceptance standard. Each arm ran three real Qwen3-8B turns per case, for a total of 24 observed provider calls. The native runtime performed authorized table operations and withheld unsupported typed claims. The retained model drafts and incomplete constructions still failed full-task review.

| Fresh mission | Evidence-bound executor | Ordinary model with tools |
| --- | --- | --- |
| FR · Mixed-unit solute balance | Executed approved tables. Integer division discarded both sub-litre volumes and none of the three claims had bound execution. | Repeated incorrect unit arithmetic and reported wrong results. No exact reusable query. |
| EN · Revision-aware operating decision | Reused an example table name while querying the authorized ledger. All three SQL constructions were refused. | Proposed rounding and selected the latest active record before considering later retirements. The worker refused the resulting scalar type. Its unexecuted answer reported 123 of 145 instead of the exact 55 of 90. |
| FR · Missing paired measurement | Correctly withheld the typed claim for the missing duration. A retained draft still asserted that the full aggregate had been calculated. | Correctly located the missing duration and nevertheless reported 187/50 L/min by including litres from the incomplete observation. |
| EN · Pinned source acquisition | Requested both approved URLs. The local resolver returned `EAI_AGAIN` and neither source body was admitted. | Repeated both approved fetches without admitted bytes. It guessed the eligible label and reported the wrong patch version. |

[Primary result and actual per-arm receipts](RESULT.json) · [Separate DNS diagnostic](SOURCE-DNS-DIAGNOSTIC.json) · [Frozen test inputs](CASES.json) · [Independent references](ORACLE.json)

An explicitly assisted native replay independently verified all six numeric claims across both calculation cases and replayed each compiled SQL artifact on the withheld dataset. It also produced a precise abstention for the missing duration with no numeric claim. The operator supplied the SQL and exact claim bindings. This qualifies the tested native execution and evidence mechanism under correct inputs and actions. The four independent conventional references also matched, including the two interpreter headers acquired separately by the evaluator. [Assisted native replay](assisted/RESULT.json) · [Ordinary SQL control](ORDINARY-SQL-CONTROL.json) · [Conventional references](CONVENTIONAL-REFERENCE.json)

## Method and replay

The registration specifies the tasks, information parity, acceptance conditions and limits before model execution. The candidate uses the mission backend frozen at `aa42b078e10a745f22f0ce2dba8fceaca8caabba`. The two primary arms use the same credential-free Qwen3-8B server for at most three calls, 768 output tokens per call and 14 tool attempts per case. [Registration](REGISTRATION.json) · [Executed local model](../QWEN-LOCAL-IDENTITY.json)

The evidence-bound executor can persist authorized claims and connect each accepted numeric result to its input and execution. The direct comparator uses the same language model with ordinary read-only SQL, access to the same approved source URLs, and feedback from actual tools. Its final output and reusable query face the same independently computed task requirements. The deterministic reference is authored separately by the evaluator and supplies the exact checks, including reuse of the final artifact on data excluded from all model conversations.

An accepted calculation requires relevant executed values and successful reuse. An accepted missing-evidence result identifies the missing observation and withholds the requested numerical result. An accepted source decision requires both pinned fetches and correct selection. The public registration keeps this engineering cohort distinct from the historical regression results and the 48-case strategic-learning confirmation.

With the [recorded local model](../QWEN-LOCAL-IDENTITY.json) running, replay from the repository root. Supply a checkout of the exact backend to `--repo`, then repeat with `--arm direct` and a new result directory to run the matched comparator.

```sh
eval_dir=publication/evidence-bound/evaluation
python -B "$eval_dir/run_missions.py" --repo /path/to/frozen-backend \
  --cases "$eval_dir/fresh/CASES.json" --oracle "$eval_dir/fresh/ORACLE.json" \
  --registration "$eval_dir/fresh/REGISTRATION.json" \
  --registration-sha256 591e595b8b32bee948a2cfed14d189cc7719641b5dabf5a181af7f1ac1cf88dd \
  --arm evidence --config "$eval_dir/fresh/RUNTIME-CONFIG.json" \
  --result /tmp/frontier-fresh-evidence-replay
```

One run per case and arm was measured. The preregistered previous-engine arm was optional and remained unrun. Model server CPU accounting, operator authorship and review time, and complete operating costs remain unmeasured. These eight live trials do not qualify general autonomous construction or superiority over the ordinary model route.
