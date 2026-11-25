# Replay the frozen battery decisions

The archived JSON includes the investigator-written factual source notes, original document locators and SHA-256 values, supplied scope annotations, frozen predictions and independent reference dispositions. It contains no original manufacturer PDFs or private inputs. Primary and confirmation use public product documentation with test declarations. Adverse cases are fictional.

From the repository root, run:

```sh
node publication/prove-advantage/dpp-replay/replay.mjs
cd publication/prove-advantage/dpp-replay
sha256sum --check SHA256SUMS --quiet
python replay-scores.py
```

The original typed inputs and predictions remain frozen. On the installed checker, 25 of those 27 decisions and source IDs reproduce with the original bytes. Two FENECON reference inputs are withheld because the source note describes short series labels without naming the model in each column. `PRIMARY-COLUMN-LABELS.json` records the reviewed expansion of the original three labels from Table 17. The replay makes that change in memory, then reproduces all 27 decisions and evidence sets. Run `node publication/prove-advantage/dpp-replay/replay.mjs --reviewed-primary` from the repository root to produce the revised packet for the application. Source files remain available at their original links and the input hashes remain unchanged.

The Node replay also shows five primary and one adverse change when declared scope is withdrawn from the checked inputs under the current column-binding code. Both original withdrawal files remain archived. Their scores describe the original experiment.

The scoring replay uses the independent evaluator's registered disposition, source attribution and rationale-presence rules. Competent direct and FRONTIER Ω both score 14/16 and 6/6 on the two battery cohorts. Adequate interpretation of the source labels, scope and rationale still needs independent review. The frozen primary result also records the two shared ambiguities and early disclosure. [Matched report](../DPP.md)
