# Replay the frozen battery decisions

The archived JSON includes the investigator-written factual source notes, original document locators and SHA-256 values, supplied scope annotations, frozen predictions and independent reference dispositions. It contains no original manufacturer PDFs or private inputs. Primary and confirmation use public product documentation with test declarations. Adverse cases are fictional.

From the repository root, run:

```sh
node publication/prove-advantage/dpp-replay/replay.mjs
cd publication/prove-advantage/dpp-replay
sha256sum --check SHA256SUMS --quiet
python replay-scores.py
```

The Node replay checks all 27 frozen dispositions and evidence sets on the installed source code. It also reports the differences when scope is removed. The corrected parser excludes two branded inline weight descriptions in the primary withdrawal and an inverter-output reading in the adverse withdrawal. Both original withdrawal files remain archived. Their scores describe the original experiment.

The scoring replay uses the independent evaluator's registered disposition, source attribution and rationale-presence rules. Competent direct and FRONTIER Ω both score 14/16 and 6/6 on the two battery cohorts. Adequate interpretation of the source labels, scope and rationale still needs independent review. The frozen primary result also records the two shared ambiguities and early disclosure. [Matched report](../DPP.md)
