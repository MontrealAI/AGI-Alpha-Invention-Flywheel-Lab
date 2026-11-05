# PhysicalBattery100: forecasting is not yet failure discrimination

**Post-hoc review of an already exposed historical cohort. The original primary experiment failed its frozen interval-coverage condition. No new physical test, forecast, fitted model or fresh scientific confirmation is reported here.**

This supporting review connects the battery work to the GENESIS question of which missing measurement could enable a consequential decision. It identifies an evaluation gap, not a qualified instrument or a new flagship. The original protocol, code, models, predictions and result remain unchanged in [PR #238](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/238).

## What was independently checked

[Run 41931850452](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41931850452) completed successfully at source `67644b8519d510188ab7f64e1679f78e3266371c`. Successful execution is separate from scientific acceptance. Its artifact `battery100-results`, ID `13370954244`, was downloaded again and matched GitHub's SHA-256 digest:

`e347f626c423a620e937e49405d5483d15413f33a2c1f65c9af989a518a89095`

The review verified the prediction seal, all 54 unique method-cell rows and 18 target endpoints. Each target was independently recomputed from the artifact's accepted-capacity CSV: endpoint capacity divided by the median of that cell's first ten accepted cycle capacities. The original evaluator was neither imported nor rerun. The calculation is independent code on the same evidence and execution environment, not independent metrology or external certification.

The unit is **nine cells across nine represented groups**, each observed at two endpoints. Eighteen endpoints are not eighteen independent experiments. The same-model laboratory protocol and group restrictions of the [original frozen protocol](../battery_physical100/PROTOCOL.md) still apply.

| Existing method | Mean absolute error (percentage points) | Maximum absolute error (pp) | Covered endpoints | Mean interval width (pp) | Cycle-1000 pass / abstain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adjusted peer, frozen primary | 0.182131 | 0.883389 | 16/18 | 1.081404 | 9 / 0 |
| Unadjusted peer | 0.164464 | 0.613974 | 14/18 | 0.725352 | 9 / 0 |
| Persistence | 5.586836 | 8.696838 | 18/18 | 13.410369 | 9 / 0 |
| Recent linear | 7.646483 | 14.266449 | 18/18 | 20.738099 | 0 / 9 |
| Sqrt plus linear | 5.058324 | 9.537988 | 18/18 | 14.066778 | 0 / 9 |
| Curve-feature ridge | 0.648983 | 1.518339 | 18/18 | 2.380522 | 9 / 0 |

Both primary interval misses are cell **A1003**, at cycles 500 and 1000. The other four original acceptance conditions pass; the combined original verdict remains **false**. The unadjusted peer's smaller observed point error does not prove a population-wide advantage. The ridge control covers all endpoints with wider intervals, but promoting it after observing the test cohort would be post-hoc selection, not fresh confirmation.

## The decision-relevant limit

All nine cycle-1000 outcomes exceed the registered 80% capacity-ratio threshold. They range from **89.223509% to 92.278447%**. Thus an uninformative always-pass diagnostic is correct on all nine cells. It is not a deployable screening policy. With no below-threshold failures in the cohort, this result cannot estimate the ability to detect such failures or justify terminating required testing.

The early-data adjustment has not demonstrated incremental point-error benefit in this observed comparison. Same-group forecast accuracy does not establish a better battery candidate, safely avoided laboratory testing, customer acceptance, paid demand or complete-cost advantage. No laboratory cycles, elapsed laboratory time, money or sales were actually saved.

## Reproduce without new data acquisition

Python 3 standard library only, from the repository root:

```sh
python -B -m unittest research.battery_physical100_review.test_review -v
python -B -m research.battery_physical100_review.review \
  --check research/battery_physical100_review/result.json
```

`evidence.json` retains the original sealed prediction object plus only the 108 capacity values needed for this calculation: ten reference and two endpoint capacities for each of nine cells. These are compact derived results from the public artifact, not the raw measurement streams. It records the original ZIP and member digests. `result.json` is recomputed by `review.py`; input/schema inconsistencies fail explicitly even under optimized Python. No producer imports, network calls, fitting, new model runs or equipment control occur.

The Actions artifact is scheduled to expire on 2027-02-02. The compact evidence keeps the arithmetic review usable afterward. Source provenance was verified at extraction time; the compact projection cannot reconstruct or independently reauthenticate the entire original archive after its expiry. Preserve the original artifact identifiers and hashes when comparing other copies.

## Consequential next test, not a retrospective repair

Tried: historical same-group forecasts and empirical calibration ranges. Outcome: accurate primary point predictions but failed coverage, with no failure-class examples. Lesson: a small mean error does not answer the important discrimination question.

A future, separately registered study would first establish a valuable unresolved decision under competent same-peer, published early-life and strong conventional alternatives. It would need suitably independent measurements covering the outcomes that matter, frozen error/abstention rules and complete acquisition, development, verification and deployment costs. If existing observations suffice, use them. If a different excitation, sensor or experimental procedure is required, validate it on measurements obtained under that procedure; old fixed-protocol traces cannot validate an intervention never performed. Choosing a new threshold or method after this cohort is exposed does not repair its original verdict.

This review neither selects a globally best opportunity nor authorizes new measurements, physical operation, purchases, outreach, deployment or termination of required tests.
