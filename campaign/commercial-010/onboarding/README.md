# Executed autonomous onboarding

The workflow actually converts synthetic CSV exports into validated service-order JSON. It does not observe a customer's export, approval, attention or integration burden. The original service cohort in `service/executed-002` is unchanged.

```sh
python scripts/run_onboarding010.py --output runs/onboarding010-replay
python -m unittest discover -s tests -p test_onboarding010.py -v
```

For all 19 source orders, the agent wrote explicit contract metadata, an invoice CSV and a payment CSV. The parser checks exact unique headers, UTF-8, quoted fields, positive integer-cent units, USD currency, bounded rows/bytes, unique identities, customer/reference consistency and the declared completeness obligation. It does not guess currency, amounts, mappings or customer permission. CSV quotes and optional UTF-8 BOM are supported. Malformed headers, unsupported currency, reversals, malformed references and unsafe output reuse are rejected.

The executed result in `executed-001/RESULT.json` records 17 validated imports whose canonical bytes exactly match their frozen source JSON. Two inputs are rejected (CAD and a negative reversal). Rerunning the separate service checker accepts 16; the remaining valid import fails its strict completeness obligation because ambiguity remains. An additional actual duplicate-header probe is retained as a rejection. The five onboarding tests exercise quoted fields, exact identity, BOM support, malformed tables/units, duplicate metadata, mismatched data and overwrite refusal.

The recorded `agent_import_work` timing includes CSV parsing, preparation, deterministic reconciliation and independent service requalification. It totals 2.578753189 CPU seconds and 2.583986086 wall seconds for the 19-order cohort. These are observed machine-work measurements. They exclude broader agent inference, code development and orchestration and are not a monetary bill or human work hours. Exact host inference/tool/storage bills remain unknown and belong in the commercial model's conditional complete-cost envelopes.

| Cost or friction | Payer | Evidence and uncertainty | Timing and recurrence |
| --- | --- | --- | --- |
| Agent preparation, onboarding and checks | Seller/agent operation | Actual code and work timings; exact host billing unknown. No hypothetical staff wage. | First-order setup can be charged once for each genuinely new customer; repeated data imports still consume compute. |
| Buyer approval, export, switching, integration and attention | Buyer | No actual customer attention measured. Low friction is a conditional utility assumption, not a proved zero or seller labor cost. | Model one-time attention separately from recurring actions; do not charge the same initial switch on every repeat. |
| Payment/channel/supplier fees and obligations | Named payer in the commercial policy | No new paid external transaction occurred here. Actual host/platform costs are unmetered; modeled fees remain explicit assumptions. | Charge only when the corresponding event or obligation occurs; preserve refunds, reserves and recurrence. |

The prepared workflow supplies a concrete capability that can support lower agent setup effort and reduce required manual data preparation. It does not establish a customer's willingness to grant access, accept the service, pay a premium, or incur zero friction. Those questions remain strategic-model assumptions or separately authorized future measurements. No outreach, paid provider call, credential change, client data or funds movement was performed.

The original no-sale development run modeled **$25 of customer switching/attention friction**, not $25 of agent onboarding labor or a human wage. At the $132.05 offer versus the $139 human benchmark, the $6.95 discount and modeled assurance difference did not overcome that assumed customer burden. The run's zero collections are a consequence of its specified utility model, not an observed market refusal or proof of an AI labor-cost defect. Changing autonomous CSV preparation does not retroactively measure that customer's attention or justify setting it to zero.

The declared human comparator performs human onboarding and service work at human loaded compensation. A transparent illustrative stage allocation is:

| Human-delivered stage | First order | Repeat order | Treatment |
| --- | --- | --- | --- |
| Initial customer onboarding and setup/preparation | 0.5 hour, $17.375 | Excluded after completed setup | One-time human effort; not added a second time to the $139 total. |
| Recurring preparation, reconciliation, verification, corrections, delivery and support | 3.5 hours, $121.625 | 3.5 hours, $121.625 | Human effort at the same rounded $34.75 loaded hourly rate. |
| Total illustrative loaded labor | 4 hours, $139 | 3.5 hours, $121.625 | Assumed time, not a matched human measurement or observed service quote; sensitivity includes much faster and slower workflows. |

Agent-operated onboarding instead incurs machine inference, tools, computation and infrastructure. A prospective $0.01–$2 first-customer setup budget is an explicitly conditional modeling range, not an exact receipt or empirically established billing bound. Repeated imports still consume resources already included in recurring operation costs. Customer attention can separately vary over the declared $0–$50 utility-friction range without becoming seller staffing expense. External onboarding fees default to zero only in the declared no-paid-provider scenario and require separate stress cases when applicable. No guaranteed future orders are assumed to amortize initial setup.
