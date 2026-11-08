# Cost ledger — Learning to Build 1.1.0

**Complete economic cost and savings are not established.** This ledger records measured work, including failures and verification, with explicit boundaries. There is no accepted whole-cell outcome for an equivalent-outcome cost comparison and no demonstrated primary candidate-evaluation saving. The source nucleus result of the fixed pretrained specialist is separately qualified; it does not establish a completed construction-and-transfer cycle.

[COST_LEDGER.json](COST_LEDGER.json) contains exact values, source SHA-256 hashes, JSON pointers, event identities, nested relationships and the exact additional internal-review receipts. The decimal values below are rounded only for readability. The ledger deliberately has no grand total.

## How to read the costs

A CPU second is measured process consumption. A wall second is elapsed time within a particular observation. Neither is a billed dollar amount. Concurrent work can overlap; adding wall intervals does not establish project duration. An instrument timer inside a process and an enclosing command receipt describe overlapping work. Use one boundary for that physical execution, not their sum. A later replay is a new execution and is additional work; a repeated summary or copied receipt is not.

The archive and per-file hashes in the JSON bind every value. Original observations are members of [REPRODUCTION.tar.gz](construction/evidence/REPRODUCTION.tar.gz); `sources` gives each exact member name. The [evidence manifest](construction/evidence/EVIDENCE_MANIFEST.json) retains the package inventory. Setup repair observations are members of [setup-boundary-evidence.tar.gz](qualification/setup-boundary-evidence.tar.gz). Reviewer source receipts are embedded byte-for-byte as UTF-8 strings in the JSON with their original names and hashes, so this ledger remains independently inspectable even apart from a companion review packet.

## Original classical construction and specialist comparison

| Observation | CPU s | Wall s | Accounting boundary |
| --- | ---: | ---: | --- |
| Classical run invocation 1 | 545.537421 | 544.043742 | `classical-invocation-1`; additional observed work |
| Classical donor stage | 542.976103 | 543.098095 | `classical-stage-donor`; nested attribution |
| Classical run invocation 2 | 156.129276 | 154.124109 | `classical-invocation-2`; additional observed work |
| Classical source stage | 28.601031 | 28.187764 | `classical-stage-source`; nested attribution |
| Classical successor stage | 125.358125 | 125.417224 | `classical-stage-successor`; nested attribution |
| Specialist 116-field command | 4970.459513 | 4970.989785 | `specialist-116`; additional observed work |
| Inner 116-field specialist session | 4969.506586 | 4970.035403 | `specialist-116-session`; nested attribution |
| Specialist idempotent resume | 1.914530 | 1.917543 | `specialist-resume`; additional observed work |
| Original raw nucleus-image operation | 49.609667 | 49.620102 | `specialist-raw-operation`; additional observed work |
| Inner raw nucleus operation | 48.696984 | 48.706637 | `specialist-raw-operation-inner`; nested attribution |

The three classical stage intervals total **696.935259 CPU seconds and 696.703084 wall seconds**. Those totals are nested inside the two recorded invocations; they are not extra work. The donor consumes 542.976103 CPU seconds. Its retained history is upstream work attributable to the inherited-history and matched same-content comparisons; it was not re-executed once per arm. The no-history arm did not receive donor history. Exact construction and held-out intervals for all six arms are retained under `six_arm_nested_costs`, within the successor stage. All six exhausted 24 candidates and failed complete qualification.

The specialist command covers 116 fields: 50 source validation, 50 source test, four successor calibration and 12 successor test. Its 4,970.459513 command CPU seconds enclose the 4,969.506586 session CPU seconds. Setup, separate checks and later raw-image operation are additional observations. The fixed specialist has different learned stock from the finite constructor, with unknown upstream training cost and pretraining overlap.

Sources: `classical/RUN_STATE.json`, `classical/RESULTS.json`, `incumbent/RESULTS.json`, `incumbent-command-001.json`, `incumbent-resume-001.json`, `incumbent-operator-command-001.json` and `incumbent-operator/OPERATION.json` in the original archive.

## Preserve the cost of rejected checks

| Observation | CPU s | Wall s | Accounting boundary |
| --- | ---: | ---: | --- |
| CLASSICAL_INDEPENDENT_CHECK | 606.770208 | 606.624696 | `original-raw-check-rejected`; additional observed work |
| PROJECTED_CLASSICAL_INDEPENDENT_CHECK | 605.296403 | 604.937472 | `projection-full-replay-001`; additional observed work |
| PROJECTED_CLASSICAL_INDEPENDENT_CHECK-002 | 589.958294 | 590.038176 | `projection-full-replay-002`; additional observed work |
| INCUMBENT_INDEPENDENT_CHECK.REJECTED-001 | 17.652201 | 16.002155 | `saved-specialist-audit-rejected`; additional observed work |
| INCUMBENT_INDEPENDENT_CHECK | 16.288997 | 16.291746 | `saved-specialist-audit-corrected`; additional observed work |
| Projected-tree idempotent resume | 1.864356 | 0.603360 | `projection-resume`; additional observed work |

These are distinct executions. The original strict raw-tree check remains rejected. The two projected-tree replays are not duplicates of the same cost receipt: the second reran the checker after a separately documented loading-schema correction. The first saved-neural audit also rejected on that schema issue, then a new corrected pass completed. Saved-neural audits rescore masks; they do not repeat neural inference. The ledger also retains focused schema-regression tests, two historical input-failure replays, an optimized integrity check, observation-stability checking and finite-illustration reproduction commands.

Two recorded failures lack retained CPU/wall telemetry: a failed recheck launcher before checker execution, and a receipt-writing failure after an idempotent resume operation. They remain **UNKNOWN**, not zero. The later successful resume does not replace their cost.

## Setup and acquisition

| Observation | CPU s | Wall s | Accounting boundary |
| --- | ---: | ---: | --- |
| setup-001-failed | 0.056826 | 14.916356 | `setup-001-failed`; additional observed work |
| Separate corrected DINOv3 archive acquisition diagnosis | 0.057072 | 5.582091 | `upstream-targz-diagnosis`; additional observed work |
| setup-002 | 37.124096 | 97.490826 | `setup-002`; additional observed work |
| setup-003 | 6.831196 | 6.837839 | `setup-003`; additional observed work |
| setup-004-standalone | 41.192047 | 61.679980 | `setup-004-standalone`; additional observed work |

Each setup CPU value is the recorded installer parent CPU plus explicitly reaped child-command CPU. The wall value is the enclosing setup interval. Individual downloads, preflight and model-load times are nested within those observations. The corrected archive acquisition diagnosis is a separate recorded attempt. The failed first installer attempt remains included.

Five successful public-data downloads have recorded transfer wall intervals and byte hashes in `input-acquisition/FETCH.json`; their CPU is unavailable. A 59,768,832-byte partial data-download file was observed, with unknown origin and additional cost. Verified input-byte totals are not total network traffic. Initial environment creation and source probes were not completely metered. Cached setup does not make the prior acquisition, installation or model-training cost zero.

## New diagnostics and single stopped repair

| Observation | CPU s | Wall s | Accounting boundary |
| --- | ---: | ---: | --- |
| diagnostics-initial | 8.465148 | 7.058458 | `diagnostics-initial`; additional observed work |
| diagnostics-author-verification | 8.895572 | 7.277900 | `diagnostics-author-verification`; additional observed work |
| repair-initial | 3.262927 | 1.755030 | `repair-initial`; additional observed work |
| repair-author-verification | 3.407852 | 1.756553 | `repair-author-verification`; additional observed work |

These rows use the producer's instrumented interval. The JSON also preserves slightly wider process CPU including startup; it is an overlapping measurement of the same run. The author did not retain a full enclosing command receipt for these runs. Script wall timing excludes interpreter startup and final receipt serialization. Authoring, engineering preflight and reasoning are not included.

Each diagnostic run executed 33 cached-score order interventions through the unchanged constructor, plus 24 actual classical segmentations including controls. The 792 cached evaluator calls in each order replay are not 792 new image-inference calls. Each repair run executed four actual classical compositions and scoring passes, stopped at the failed calibration gate, and scored no test fields. There was no new neural inference in these four author runs. The [diagnostic receipts](construction/diagnostics/PROCESS_COST.json), [diagnostic replay receipt](construction/diagnostics/REPLAY_VERIFICATION.json), [repair receipt](construction/repair/PROCESS_COST.json) and [repair replay receipt](construction/repair/REPLAY_VERIFICATION.json) preserve their separate costs and outcomes.

### Cached specialist masks carry prior cost

The repair consumed four existing specialist calibration predictions. Their original field CPU totals **122.637093 seconds** and field wall totals **122.650064 seconds**. Within field CPU, segmentation accounts for **122.036695 seconds** and scoring for **0.314104 seconds**. These amounts are already inside the original 116-field session and command. They are lineage attribution, not additional execution, and must not be added again. A fresh standalone deployment of this composition would need its own actual inference and setup costs; the cached repair runtime is not an estimate of that full cost.

The repair failed the frozen whole-cell boundary gate. Its standalone raw-input neural-composition operation was consequently not run. It establishes neither an accepted useful whole-cell result nor savings. Reference-assisted diagnostic passes also do not satisfy raw-input acceptance.

## Additional internal review and setup-boundary qualification

| Observation | CPU s | Wall s | Accounting boundary |
| --- | ---: | ---: | --- |
| LIMITED_SAVED_OUTPUT_AUDIT.stdout | 449.190954 | 448.861647 | `review-limited-saved-audit`; additional observed work |
| RAW_RECONSTRUCTION_INDEPENDENT_CHECK | 2.088304 | 0.433945 | `review-raw-inventory`; additional observed work |
| MECHANISM_AND_REPAIR_REVIEW | 3.213029 | 1.560201 | `review-mechanism-mask-rescore`; additional observed work |
| diagnostic-independent-replay | 8.665957 | 7.025907 | `review-diagnostic-independent-replay`; additional observed work |
| repair-independent-replay | 3.379151 | 1.805589 | `review-repair-independent-replay`; additional observed work |
| Original extracted installer failure | UNKNOWN | 0.048050 | `setup-boundary-failed`; additional observed work |
| Exact cached setup after installer-boundary repair | 7.362655 | 7.425014 | `setup-boundary-repaired`; additional observed work |
| Copied repaired edition raw nucleus operation | 52.247691 | 52.277315 | `setup-boundary-raw-operation`; additional observed work |

The reviewer limited audit rescored 312 saved fields and regenerated 136 unique classical predictions. It did not repeat donor/calibration prediction generation or neural inference. Its time is checker-reported inner time, not a captured outer command. The mechanism review independently decoded references and rescored 20 archived masks. The diagnostic and repair replay rows use captured child-command boundaries; their inner instrumented times are retained as nested rows in the JSON and must not be added. Additional extraction, projection reconstruction, projection tests and setup-review test commands are also retained there.

The setup-boundary raw operation records 52.247691 CPU seconds and 52.277315 wall seconds inside a **53.123837-second enclosing operation**. Wrapper CPU is unavailable. This copied repaired candidate operated an already exposed nucleus field and reproduced its retained prediction. The preceding extracted installer failure and seven focused tests in normal and optimized modes are preserved. The earlier failed package-gate timing observations remain separately indexed in the JSON; its failed installer interval is the same event shown above, not another charge.

Review independence is limited to separate assistant roles in the same session. Same-author numerical replays are labeled separately. None of these operations makes an exposed field fresh, and none is an external audit.

## Material unknowns and cost of an accepted outcome

- **Residual-origin work:** every raw residual is preserved and mapped, but provenance and any additional execution cost remain unresolved. Byte identity and successful projected replay do not prove a zero-cost origin. The producer's false interrupted-work flag only describes its recorded attempts.
- **Unrecovered history and preparation:** original unavailable full runs, unmetered interruption/acquisition work, initial environment exploration and engineering preflight are not reconstructed from later timings.
- **Human and assistant work:** research design, source analysis, failed approaches, authoring, review, correction, manuscript production and human intervention lack complete time and billing measurements. Transferring work to a human is not demonstrated elimination of that work.
- **Money and upstream resources:** included assistant/model/host billing, network/storage cost and specialist pretraining are unknown. No new purchase or paid model API call does not mean zero economic cost.
- **Subsequent publication work:** final sealed/extracted source-package gates, hosted CI, integration, publication and operation from downloaded release artifacts are additional work. Their later workflow and operation receipts supplement this snapshot; no invented estimate is included here.

An equivalent verified whole-cell outcome was not reached. A ratio of the failed candidate's runtime to a specialist's runtime therefore cannot establish the cost of an equivalent accepted result. The demonstrated primary candidate-evaluation saving remains **zero**. Complete lifecycle savings, monetary savings and fresh retained-method learning advantage remain **not established**.

## Check the accounting

Read `sources` and verify each file/member hash before resolving an event's JSON pointers. For embedded reviewer sources, hash the UTF-8 bytes of `embedded_utf8`; the original bytes are retained without reserialization. For installer CPU, recompute the explicitly stated parent-plus-child formula. Resolve `contained_by` and `accounting_relation` before aggregation. Do not add rows labeled nested attribution, aliases of a receipt, inner/wrapper alternatives, or the cached constituent attribution as separate work. This is a receipt index and qualified cost analysis, not an estimate of missing bills or a complete economic total.
