# Temporal risk159 operator — synthetic two-period source-bound evidence

This is an **additive, key-free research dependency** on existing `products.governance_impact140.native_risk152`. It compares two distinct authored first-party observation sets **under exactly the same policy**. The prior Governance158 demonstration instead compares a changed requirement under one common observation set; both are useful but neither alone implements the required government platform. Never transform a synthetic risk signal into compliance approval.

## Reproduce and qualify

From the exact branch checkout:

```sh
python3 -B -m unittest discover -s tests -p 'test_governance_temporal_drift159.py' -v
python3 -B -m unittest discover -s tests -p 'test_governance_native_risk152.py' -v
python3 -B -m unittest discover -s tests -p 'test_governance_native_reassessment153.py' -v
```

The [dedicated workflow](../../.github/workflows/governance-temporal-drift159.yml) runs all original 140/152/153/158 tests, the twelve new frozen checks, and separately downloads exact allowlisted source. Its second job checks a previous-job source manifest hash and reproduces the real `native_drift159` CLI. Local success cannot replace actual completed GitHub-hosted checks.

Prepare an input JSON with the exact seven registered fields shown in [the preregistration](PROTOCOL.md) and direct raw rows accepted by the existing native risk152 evaluator. Choose a **new** output path:

```sh
python3 -B -m products.governance_impact140.native_drift159 --input /absolute/input.json --output /absolute/new/report.json
```

To verify a receipt, obtain three expected SHA-256 anchors **separately from the output** (receipt and prior/current raw-observation digests), then call `verify_receipt(report, expected_receipt=..., expected_prior_raw=..., expected_current_raw=...)`. A receipt's own printed hashes do **not** authenticate people, observations or the original source; no signing keys or accounts are used.

## Boundaries and next admission

Output reports numerical directions for five original risk152 metrics and whether a fresh authorized human review is required. The two authorship dates and disjoint case IDs do not prove dataset authenticity, independence, consent, population comparability, statistical significance or a causal change. The instrument cannot by itself authenticate reviewers, enforce data residency or retention, integrate with enterprise identity/API systems, or demonstrate TRL 5–9.

Compare this research route against competent human monitoring with ordinary software, existing GRC/AI-risk vendors and no purchase. Full engineering, onboarding, verification, support, tax, procurement and capital costs are **not observed**. The actual federal challenge's CAD2M Phase-2 cap and estimated 1–2 awards are neither our customers nor our profit. Commercial verdict: **NO BID / NO DEPLOY**. No canonical native account, cash or ledger is created or altered; original financial owner and historical failure traces remain untouched. The US$3B trailing-365-day complete-cost profit milestone is not qualified.
