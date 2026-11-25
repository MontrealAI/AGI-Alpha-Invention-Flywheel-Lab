# Independent strategic-learning confirmation

**NO-GO for specialist admission.** The frozen adapter answered SKIP on every direct case, matching the constant-SKIP control at 28 out of 48. With retrieved training examples it made the same decision as the unmodified model on all 48 cases, scoring 40 out of 48. The exact deterministic solver accepted all 48 cases by matching rational primal and dual values.

| Model | Direct | Method prompt | Verified training examples | Exact tool advice |
| --- | ---: | ---: | ---: | ---: |
| SmolLM2-135M-Instruct | 26/48 | 20/48 | 40/48 | 21/48 |
| Frozen low-rank adapter | 28/48 | 27/48 | 40/48 | 27/48 |

Every model arm was run locally and scored a forced BUY or SKIP decision. In the exact tool advice arm, the same model still selected the final answer after seeing the tool's output. Where the required payoff and signal structure is available, route straight to the exact solver. Both retrieval configurations made five false purchases among eight exact ties and had the same total worst-case regret. The Brier score, exact regret and all strata are in [RESULT.json](RESULT.json).

The evaluator authored the synthetic cases independently and withheld the case and oracle bytes from model construction until the adapter and prediction source were frozen. Registration preceded training. Cases include asymmetric signal quality, decisions with extra actions, payoff-translation pairs, exact ties, and near-boundary pairs. Cases and predictions became public after scoring. This was separate evaluation work on one administrative setup. The study does not establish externally separated custody, transferable improvement, general strategic ability, or an end-to-end cost advantage.

## Replay

The eight-arm [PREDICTIONS.json](PREDICTIONS.json) contains the observed token probabilities, actions, input commitments and source/model identity. The [registration](REGISTRATION.json) binds the exact [inputs](CASES.jsonl), [oracle](ORACLE.json), and [independent verifier](../strategic_reference.py). The case author's script and original seed are available for audit. The immutable registered inputs are the replay entry point.

From the repository root, replay the independent verifier and every observed decision with the standard library:

```sh
eval_dir=publication/evidence-bound/evaluation
python -B "$eval_dir/grade_strategic.py" \
  --registration "$eval_dir/strategic/REGISTRATION.json" \
  --cases "$eval_dir/strategic/CASES.jsonl" \
  --oracle "$eval_dir/strategic/ORACLE.json" \
  --predictions "$eval_dir/strategic/PREDICTIONS.json" \
  --output /tmp/frontier-strategic-independent-replay.json
```

See the [training and checkpoint receipt](../../strategic/README.md) for an actual inference replay. The predictor ran all arms in 146.73 seconds, reaching 674,746,368 bytes of process memory on the shared host. The independent CPU solver took about 0.18 seconds for all 48 cases. These observed timings have different footprints and omit full host cost.
