# Commercial assessment

Each assessment reports the beneficiary, proposed outcome, candidate's strongest alternative and decisive test, source-rights declarations, and observed model telemetry. Human effort, customer demand, booked revenue and financing stay unknown unless supported through a separate commercial evidence process. A working artifact and a tested ordinary alternative establish technical evidence.

To examine a bounded offer, paste the object from `examples/commercial/release-review.json` into the mission's advanced **Resources** field as the value of `commercial_case`. Keep the existing resource settings. The example references the executed GNU checksum and file-inventory comparison. It contains no invented selling price, buyer, contract or cost. Rerun under a new mission revision when assumptions change.

## Supplying a scenario

Declare one `currency`, one accepted-delivery `unit`, and the `horizon` over which fixed costs and obligations apply. Currency amounts are unsigned decimal strings. Every amount needs `low`, `high`, `provenance` (one of `assumption`, `quote` or `measurement`) and `source`. An assumption's source explains its rationale. A quote should identify the provider, terms and date. These are operator-attributed inputs. No exchange-rate conversion or verification of pricing occurs.

| Optional field | Input |
| --- | --- |
| `costs` | Map of category names to nonempty lists of amounts. Each amount also has a `basis` of `fixed` for the whole scenario or `per_unit` for each accepted delivery. |
| `price` | Range for the proposed charge per accepted delivery. |
| `volume` | Object with nonnegative whole `units`, `provenance`, and `source`. This is a scenario volume. |
| `strongest_alternative`, `willingness_to_pay`, `rights`, `payment_timing`, `funding` | Each supplied field is an object containing `claim`, `provenance` and `source`. Identify what has actually been observed. |
| `participants` | List with each proposed participant's `role`, `incentive`, `outside_option`, `provenance` and `source`. Include customer self-service, rival services and the option of declining when relevant. |

The cost categories are `search_construction`, `compute_inference`, `data_tools`, `human_intervention`, `acquisition_distribution`, `deployment_onboarding`, `verification_rework`, `support_maintenance`, `retained_obligations` and `opportunity_cost`. Include failed research and retries. Disclose unpaid internal time, omitted supplier or buyer costs, and residual reliability or liability exposures. Count each resource in exactly one line. A supplied category represents the operator's claim that its whole range is covered; enter zero only with an explicit, supportable rationale.

## Reading the result

Partial cost inputs produce covered-cost subtotals and a list of missing categories. Price and assumed volume can establish projected gross revenue even while delivery costs are unknown. Total modeled cost requires coverage of every category and an explicit volume.

When all categories and price are present, the program computes two conditional break-even thresholds. The favorable case uses the lowest fixed cost and the largest unit contribution. The adverse case uses the highest fixed cost and the smallest unit contribution. Each threshold is the smallest positive whole volume whose contribution covers fixed costs. A nonpositive unit contribution leaves that bound without a positive-margin threshold. The interval is a sensitivity envelope, without a probability assigned to either endpoint.

Internal opportunity cost is included in economic contribution. It may be noncash. Funding and payment timing require their own evidence to evaluate liquidity. The product does not post entries to accounts or imply that a buyer, payment or funding exists. Compare staging, declining and the strongest complete incumbent before consuming internal research capacity.
