# Outcome-driven mission comparison

This study measures whether approved schema delivery and deterministic outcome assembly improve whole-mission completion. The three newly authored synthetic missions cover English transport occupancy with a join, French cargo mass-distance with unit conversions, and a French measurement with one missing cell. All numerical answers require reproduction on held input rows using the same retained query. The missing measurement requires a localized, precise abstention.

The exact panel, held reuse rows, separate Python `Fraction` references, materiality threshold and stopping rules were sealed before model exposure. The release supplies the SHA-256 commitments in [REGISTRATION.json](REGISTRATION.json). The evaluator and implementation authors operated under shared workspace administration. Separate authoring provides an independent reference calculation and task selection with no claim of protected external custody.

| Arm | Scope |
| --- | --- |
| Previous executor | Exact `297a51c25c48031e1e6f964835f4dfae3ddb8023` source |
| Schema delivery | Candidate with direct approved schema context and constructor binding |
| Outcome assembly | Candidate with deterministic verified conclusions and explicit abstention |
| Combined | Candidate with both changes enabled |
| Direct intelligence | Same local model with ordinary read-only SQLite and Boolean exact reference feedback |
| Conventional | Separate exact Python workflow over the same authorized observations |

The native and direct models receive equivalent authorized initial data and task semantics. Native arms use the executor's bounded construction and evidence protocol. The schema treatment automatically delivers structured metadata and binds the portable constructor to an approved dataset. This panel grants the same four native tools to every native arm. The direct arm can immediately run ordinary queries on the supplied schema, with exact Boolean agreement feedback unavailable in the native constructor prompt. Instructions vary with interfaces. The current candidate shares exact-arithmetic advice across its treatment options, while the previous arm preserves the original source and instructions. A contrast with the previous release can therefore measure the combined operational change. Attribution to one isolated prompt change would require an additional candidate-version control.

Positive materiality requires at least one more whole-mission completion on the three-case panel for the combined arm than the previous executor, with zero false accepted combined-arm outcomes. The strict comparison tracks contradictions in proposed work as a member-facing quality failure. It separately records errors in verified outcome projection. The deterministic reference is intentionally capable on these small, supplied-data tasks. Public source acquisition needs a separate authorized evaluation. Complete economic cost, private operator preparation time and hardware costs were outside the instrumentation. This study records dispatches, received replies, usable provider token counters, tool actions, elapsed execution and explicit missing observations. Timeouts remain in the denominator and carry no inferred token counts.

## Observed outcomes

| Arm | Whole outcomes | Numerical outcomes | Model dispatches / replies | Reported input / output tokens | Tool attempts | Total case seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous executor | 0/3 | 0/2 | 4 / 2 | 2,912 / 937 | 10 | 529.1 |
| Schema delivery | 1/3 | 0/2 | 6 / 6 | 11,045 / 1,395 | 17 | 383.9 |
| Outcome assembly | 1/3 | 0/2 | 4 / 4 | 4,611 / 1,694 | 6 | 296.2 |
| Combined | 1/3 | 0/2 | 5 / 5 | 8,689 / 963 | 13 | 272.8 |
| Same-model direct | 1/3 | 0/2 | 3 / 2 | 1,024 / 583 | 2 | 338.7 |
| Conventional exact | 3/3 | 2/2 | 0 / 0 | 0 / 0 | 0 | <0.001 |

All 18 registered cells were adjudicated. The combined arm meets the finite-panel threshold with zero false verified conclusions. Every accepted local-model mission was the same precise French power abstention. The combined arm identified `mesures[1].duree_s`. The schema-only arm identified `piquet-5` and `duree_s` in its French draft. The complete-data model missions produced zero accepted numerical outcomes. The full records include real replies and refusals, tool artifacts, run checks, usage, elapsed times and outcome messages. [Observed results](RESULT.json)

The English direct run constructed and executed a query that produced `53/90` from the primary observations and `452/789` on held rows. The model nevertheless answered `ABSTAIN` and cited `371/630` in prose. The whole mission failed. The schema-only executor constructed a query with the correct table names and join, but its retained integer division yielded `0` during a separate retrospective SQL replay. This replay leaves the original mission grade and live execution count unchanged.

In the combined French cargo mission, the model asserted exact conversion in its work draft. The witnessed SQL returned raw fields and then separately multiplied heterogeneous units without normalization. There was no qualifying bound execution for the requested aggregate. The outcome assembler withheld all conclusions as `UNVERIFIED`. The failure and the original model text remain in the observation archive.

The included-Codex control solved both numerical missions with ordinary SQL. Independent replay preserved the same exact receipts on held rows, and the French missing-data case was correctly withheld. The author froze the three answers in 56 seconds and recorded approximately 1.17 ms of SQLite execution. Included model tokens and infrastructure cost were unobserved. [Included comparison](INCLUDED-ASSESSMENT.json)

The previous-executor and same-model direct phase overlapped with other CPU research during several early trials. Those three transport timeouts lack reported token usage and remain recorded as failures. There were 22 local dispatches, 19 replies, 28,281 reported input tokens, 5,572 reported output tokens and zero paid requests. There was no operator intervention during the measured runs. The panel supports a scoped missing-evidence result and explains two numerical execution failures. General completion, relative superiority and a causal latency gain remain unestablished. Autonomous numerical completion in the combined configuration remains **NO-GO** on this model and setup.

## Reproduce

The model is Qwen3-8B Q4_K_M served by llama.cpp build `b12242` on loopback. The published [runtime configuration](RUNTIME-CONFIG.json) has no credentials and permits zero paid requests. Use the archived model-file and launch-script commitments in [MODEL-FILES.sha256](MODEL-FILES.sha256). The registered run used eight CPU threads, one slot, `--ctx-size 16384`, `--batch-size 128`, `--ubatch-size 64`, `--cache-ram 0`, `--ctx-checkpoints 0`, `--jinja`, `--reasoning off` and `--reasoning-budget 0`. Hardware scheduling affects elapsed times. A replay may produce different timings and does not overwrite an observation.

From the checkout containing this document, with a compatible model server on the configured loopback port, use the following runs. Set `previous` to a separately archived checkout at the registered ancestor. Set `candidate` to `f61020768e0a1e18da46e6c1a3426bef63c9a925`. All 34 consumed files match that commit and the subsequent test-only commit `5955c08d36d31b77a310720ae2ba17142fca9794` byte for byte. The source map and commit comparison are in [CANDIDATE-FREEZE.json](CANDIDATE-FREEZE.json) and [CANDIDATE-REVISION.json](CANDIDATE-REVISION.json).

The later release candidate `2dcf1f252e7bb6eff528a2ef60e3314cab477e88` rejects contradictory explicit schema declarations before SQLite execution and claim verification. Approved data remain available to the authorized local constructor. The candidate matches 32 of the 34 study source files. The registered missions had consistent schema declarations. Recorded model behavior and elapsed times belong to the preregistered experimental source.

```bash
evaluation=$PWD/publication/outcome-driven/evaluation
run_root=$(mktemp -d)
registered_sha=cfb88bf4441a8ffb950054c8eabd5c53e480e6c749f7085e9f08d180af022485
registered_inputs=(
  --cases "$evaluation/CASES.json"
  --reuse "$evaluation/REUSE.json"
  --oracle "$evaluation/ORACLE.json"
  --registration "$evaluation/REGISTRATION.json"
  --registration-sha256 "$registered_sha"
  --config "$evaluation/RUNTIME-CONFIG.json"
)
python -B "$evaluation/run.py" --repo "$previous" --phase conventional \
  --result "$run_root/conventional" "${registered_inputs[@]}"
python -B "$evaluation/run.py" --repo "$previous" --phase initial \
  --result "$run_root/initial" "${registered_inputs[@]}"
python -B "$evaluation/run.py" --repo "$candidate" --phase candidate \
  --result "$run_root/candidate" "${registered_inputs[@]}"
python -B "$evaluation/summarize.py" --registration "$evaluation/REGISTRATION.json" \
  --conventional "$run_root/conventional" --phases "$run_root/initial" "$run_root/candidate" \
  --output "$run_root/RESULT.json"
```

The evidence-only [historical replay](HISTORICAL-REPLAY.json) uses already published archives and performs zero model calls. It keeps previously failed numerical claims unresolved and projects the French missing observation as an exact abstention. A separately archived assisted calculation still resolves three verified values. Changing input bytes, using a stale revision, and substituting fixtures each blocks promotion.
