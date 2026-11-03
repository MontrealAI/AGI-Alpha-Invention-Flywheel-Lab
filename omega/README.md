# FLYWHEEL Ω: local buyer pathway and coupled seller probe

A runnable, deliberately narrow self-service research edition. It constructs a
synthetic non-potable industrial water-sharing blueprint, independently verifies
its declared constraints, and compares fresh successor work with ordinary reuse.
It reuses the lab's mechanism planner and canonical native accounting.

**No Super Alpha result is claimed.** Existing water optimization is prior art.
Mathematical acceptance is not physical safety, an installed plant, a customer
outcome, actual commerce or a license to use water. See the [protocol](../campaign/omega-water-20261103/PROTOCOL.md)
and [complete alternatives](../campaign/omega-water-20261103/PRIOR_ART.md).

## Try it locally

Python 3.12. In an existing authorized environment with dependencies installed:

```sh
python -m pip install -r omega/requirements.txt
python -m omega solve --request omega/request.json --output /tmp/my-water-certificate.json
python -m omega serve --port 8879
```

Open http://127.0.0.1:8879 in your local browser. Edit the request, construct/check
and download a certificate. The server binds only to loopback, makes no model or
other network call and has no checkout or external action. Stop with Ctrl-C.
The synthetic unit is an integer volume unit; all contamination units are a
consistent authored mass/volume scale. Prices are modeled USD cents per volume
unit. Real calibration, treatment/transport, infrastructure and applicable
requirements are not established. Never use this as a water safety instrument.

The default path is entirely local deterministic computation. Alternatively,
change `model_route` to `buyer_owned_account_external`, use your own model account
**yourself** to produce a proposal matching the JSON plan schema, and import it:

```sh
python -m omega solve --request my-request.json --proposal my-plan.json --output /tmp/checked.json
```

This is a user-controlled file handoff, not an integrated paid-model adapter.
The request hash must match the exact request. No model key is requested, stored
or used. An imported model plan gets the same independent checks and no inherited
authority. We did not execute or benchmark an external paid-model arm.

## Reproduce the finite experiment

```sh
python -m unittest omega.test_buyer omega.test_seller omega.test_http omega.test_product omega.test_strategy omega.test_operate -v
python -m omega experiment --output /tmp/omega-buyer-result.json
python -m omega.operate --output /tmp/omega-private-seller-NEW
```

Every output destination must be fresh. Do not delete another owner's account,
reset a balance or copy signing/recovery keys into public artifacts. The seller
source snapshot and native account are private continuation state. Its explicit
`native-public-export.json` is key-free audit data, not spending authority.
The corrected seller runs distinct hypothetical accounts for the declared policy
and market-world comparisons. It makes time-causal build, research, offer, stop
and pivot decisions, with voluntary buyers, native acceptance, modeled payments,
refunds, settlement and residual liabilities. See [cost assumptions](../campaign/omega-water-20261103/COSTS.md).
The fixed endpoint is hour 8760. No hidden-world identity selects an action;
only revealed public observations select the policy's common continuation.

`omega.seller` is preserved as the **historical failed cost-only design**, not the
current seller policy. Its US$24,800 loss was an authored budget, not actual
spending, an optimized decision or a demand finding. Non-entry would dominate
that closed zero-sales schedule. Never interpret either simulation as continued
authority over an existing owner account or as evidence of actual commerce.

## Packages are optional, not orders

- Free/core package: intended open-source release, **license/IP review unresolved**.
  The repository has no verified root open-source license; public source is not
  itself permission to redistribute. This PR does not invent or grant rights.
- US$299 self-hosted download: modeled convenience offer, not required for research.
- US$99 group webinar: at most 500 seats/session, optional and not scheduled.
- US$20,000 private founder session: 30 minutes, optional and not scheduled.

USD is an authored modeling convention pending commercial currency confirmation.
Self-service incumbents, ordinary providers, human-plus-AI and no purchase remain
available. Hypothetical choices feed explicitly simulated consent and native revenue only
inside the fictional account. They are not actual demand, consent, contracts,
revenue or proof of a viable enterprise.
Founder sessions consume human time and cannot support a fully autonomous claim.
Actual bills, taxes, demand, deployment costs and human/AI productivity are unknown.

## Exact controls and interpretation

24 authored fixtures, including infeasibility, withdrawal and changed quality.
Candidate dynamic programming versus independently written conventional MILP;
both use exact integer acceptance, and a separate exhaustive integer oracle
checks these small fixtures’ optima without floating-point tolerance. No hidden holdout or measured workforce is
claimed. Reusing equal-content ordinary code on a fresh request is permitted and
must win ties. A stale plan is rejected, while compatible code may be reused.
Construction time, paid-model cost and full site delivery costs are unmeasured,
so this code cannot substantiate economic superiority even if runtime differs.
The US$3B trailing-year complete-cost profit objective remains unachieved.
