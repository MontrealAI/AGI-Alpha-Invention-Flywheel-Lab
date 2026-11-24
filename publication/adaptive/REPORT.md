# FRONTIER Ω · Learning from MONTREAL.AI release work

**Release scope.** The local learning runner, public release verifier, trained-model replay and read-only experimental runtime are independently releasable. The timing model missed its confirmation threshold. Retain the conventional forecast and the existing exact-source release verification.

## Actual operation

The local worker fetched [MONTREAL.AI Pages run 45438435432](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45438435432). It matched the live release receipt to the run ID and commit `53101fd1af33b2dec8335db0a7ae566adb94c0d7`, verified the two supplied public asset digests, and queued a training job. The workspace retained 265 observations, reserved four public reads, and trained a local candidate. The audit took 10.64 seconds and the training job including preparation took 0.13 seconds. This was a live check of an already released commit, with persistent state and subsequent learning. The operator supplied the scope, historical seed and acceptance clauses. Workflow authority stayed with the established Pages verifier.

## Specialist model and conventional controls

The [registration](REGISTRATION.md) specified temporal splits by Actions run number before training. It committed the cohort identity, exact weights and preselected comparator before opening confirmation. The model learned nine coefficients for a timing residual, eight of which changed. Training used 205 eligible public examples, 360 CPU passes, roughly 0.170 seconds wall time and 0.160 seconds process CPU time. No API charges were incurred. Data acquisition, setup, engineering, maintenance and human attention were outside those recorded CPU timings. The third event type had no fit examples, so its confirmation results are an out-of-distribution challenge.

| Confirmation scope | Cases | Trained MAE | Trailing-21 MAE | Trained P90 error | Trailing-21 P90 error |
| --- | ---: | ---: | ---: | ---: | ---: |
| All eligible | 56 | 89.00 s | 88.04 s | 202 s | 179 s |
| Main pushes | 14 | 218.79 s | 226.71 s | 619 s | 619 s |
| Pull requests | 28 | 51.86 s | 56.71 s | 93 s | 111 s |
| Scheduled runs | 14 | 33.50 s | 12.00 s | 62 s | 18 s |

The pooled model missed the registered 10% improvement and tail conditions. Trailing-60 was the strongest observed pooled retrospective control at 76.82 seconds MAE and 124 seconds P90. Trailing-21 was the prospectively selected comparator. All competitors, measured inference timings and group scores remain in `verification.json`. The ordinary local worker offers trained estimates in shadow only where its fit has support for that event family. Verified admission requires a separately signed decision.

## Tool construction and transfer

Open WebAssembly text requests reached their output ceiling or were interrupted. The 8B trial also hit a CPU timeout. A second 4B route returned compact stack programs, but their stack checks failed. After [registering the representation change](REPRESENTATION-FOLLOWUP.md), the same 4B model generated portable integer expressions that compiled into isolated Wasm. The operator supplied the compiler and operating contract. The expressions, ranking rule and constants came from model responses. The release retains the malformed, cancelled and rejected run records.

On 14 held production pushes the best generated candidate used 102 modeled reads versus 243 for the eligible 20-second policy. Its P95 detection delay was 53 seconds versus 18. The limit was 20 seconds. The candidate did not qualify. The empirical survival alternative also missed the tail limit. These are scheduled-read calculations against actual completion records, with no retrospective authorization to replace live monitoring.

The model then wrote a case-ranking rule following this failure. It preferred late cases, large timing discrepancies and high conventional detection delay. In the fresh PR task, the executable rule replaced three of the four development cases. The fixed ordinary order changed the ordering of the coverage set. The removal control returned to coverage while retaining the same prior. The original arm's submitted expression exceeded the complexity bound.

| Held PR task · 28 cases | Reads | P95 delay | Maximum delay | Verdict |
| --- | ---: | ---: | ---: | --- |
| Original inventor | — | — | — | Refused before execution |
| Ordinary reuse | 84 | 57 s | 58 s | Rejected |
| Executable ranking | 95 | 45 s | 46 s | Rejected |
| Ranking withdrawn | 84 | 57 s | 58 s | Rejected |
| Empirical survival | 155 | 32 s | 48 s | Ineligible |
| Periodic 20 seconds | 168 | 18 s | 18 s | Eligible |

The changed examples accompanied a 12-second lower tail and 11 more modeled reads versus withdrawal. No model-generated policy met the productive acceptance limits. Scheduled runs had no eligible development cohort for another matched construction comparison. Retain the conventional monitoring policy. The [full receipt](verification.json) recomputes the ranking, exact selected cases and each score. The constructor used Qwen3-4B-Instruct-2507 Q4_K_M with llama.cpp build 12242, four CPU threads and a 3,072-token server context. There were seven expression requests, with 4,498 input tokens, 528 output tokens and 172.26 seconds of observed request time. Across all routes, 23 settled attempts recorded 964.61 seconds. Earlier refusals without reported token counts reserved 4,096 output tokens. An interrupted request retained a separate 256-token reservation. None incurred a paid inference charge.

## Next measurement

Observe phase transitions prospectively and forecast remaining time from the actual build, deploy and verification phase. Compare against a phase-aware empirical control, with enough fit support in each event family. The timing loss on the scheduled cohort and the late-read tail on push and PR cohorts identify concrete conditions that a new design must handle. Continue comparing executable case ranking against coverage and removal on fresh objectives. A verified productive win is still required before testing the next inventor generation.

## Reproduce and challenge

Use `python3 reproduce.py` from the distributed companion to re-fit the model and recompute confirmation. Install the hash-pinned Wasmtime dependency and use `python3 reproduce.py --full` to challenge the generated monitoring programs. `python3 self_test.py` exercises the portable execution and authority boundaries with test keys. The normalized records in `cohort/` retain each case's public run ID and source commit. The raw page digests and acquisition endpoints are recorded in `cohort/inputs.json`.

### Résumé en français

L’utilitaire local a vérifié la publication réelle de MONTREAL.AI, puis a entraîné un modèle spécialisé à partir de l’historique public. Huit paramètres ont changé. Sur 56 cas de confirmation, l’erreur absolue moyenne était de 89,00 secondes pour le modèle contre 88,04 secondes pour la référence préétablie. Les erreurs sur les exécutions planifiées ont fortement augmenté. La prévision conventionnelle demeure la référence. La chaîne d’apprentissage et ses échecs sont reproductibles. Toute adoption exige une évaluation et une autorisation distinctes.

La méthode apprise a remplacé trois des quatre cas de développement pour les demandes d’intégration. Elle a ramené le 95e centile du retard de détection de 57 à 45 secondes par rapport au retrait de la méthode. Elle a exigé des lectures supplémentaires. Le seuil de 20 secondes n’a pas été atteint. Les instruments conventionnels demeurent en service.
