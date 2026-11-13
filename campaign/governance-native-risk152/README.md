# Governance native risk152 — first-party measurements, not governance authorization

**Source:** [frozen prospective protocol](PROTOCOL.md) at commit `46280f6a20b2550165afc03f1bf19a604fea0b18`. This additive research dependency addresses the 10 November 2026 [CanadaBuys Amendment 001](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-189-51083224) Q1/A1, Q6/A6 and Q20/A20: native data, model and output risk/evaluation capabilities cannot be replaced with third-party/open-source scoring integrations or externally computed threshold checks. No proposal, government approval or deployment is implied.

From an exact repository checkout:
```sh
python3 -B -m unittest discover -s tests -p 'test_governance_native_risk152.py' -v
python3 -O -B -m unittest discover -s tests -p 'test_governance_native_risk152.py' -v
python3 -B -m unittest discover -s tests -p 'test_governance_impact140.py' -v
```

Use `products.governance_impact140.native_risk152.evaluate(data)` for the first-party, synthetic source metric calculation. The exact `input-v1` contains `schema`, `system_id`, `thresholds` and `rows`. Each row needs `case_id`, `truth` (0, 1 or unknown), `prediction`, `group`, `repeat_prediction` and `claimed_violation`. `claimed_review` is explicitly untrusted. Thresholds are exact decimal strings between 0 and 1; `min_group_positives` is a positive integer. No other fields are accepted. For standalone JSON input, run:

```sh
python3 -B -m products.governance_impact140.native_risk152 --input /absolute/synthetic.json --output /absolute/new-receipt.json
```

Output reports exact numerator/denominator ratios for missing-label rate, accuracy, group true-positive-rate gap, repeated-prediction disagreement and *claimed* output-policy violation rate. When labels, repeats or sufficient positive group support are absent, the corresponding metric is **UNABLE_TO_DETERMINE**; missing rows are not deleted to obtain better scores. Every submitted `claimed_violation` and `claimed_review` field remains an **unauthenticated assertion**. A source input hash and deterministic receipt hash require independent, trustworthy anchors and never supply signatures, authorization or a compliance finding. Only synthetic binary-classification evidence is supported.

**Acceptance boundary:** this is only one native numerical quality subsystem, not Essential Outcome 6 as a whole. It does **not** authenticate the data, compare against actual model/service ground truth, guarantee fairness, define comprehensive data/model/output risk evaluation, provide RBAC, user accounts, active workflow escalations, residency/deletion, audited reviewer decisions, human oversight, full policy framework mapping, standard APIs, bilingual reporting, secure hosting or real buyer acceptance. CanadaBuys' latest published requirements and original solicitation control; this research artifact is not known to satisfy TRL 5–9 or the government competitive-innovation screen. No bid/deploy remains the decision.

**Commercial discipline:** compare first-party whole-platform completion against a competent established GRC suite plus integrator, human specialists using conventional software, and nonentry, including all security, acquisition, hosting, correction and long-lived support costs. A third-party-only evaluation adapter is inadmissible for the cited native requirement. None of those options has verified complete costs or user participation; no market share, accepted buyer, actual account, earned cash, true operating profit, recursive-discovery benefit or US$3B T365 milestone is established. The one original native-capital owner/source/signature/queues remain untouched.
