# Contingent reserve rights 278 — checkpoint

2026-11-25. Independent successor investigation after 277; no native account or production control. Main inspected at 297a51c25c48031e1e6f964835f4dfae3ddb8023; AGENTS.md blob 1313db6444cada8ea981425bd69a854bfa07f081, release workflow blob 6aedd5edbbd59ee585589634b8346276880c214d. All three release jobs of 45551095868 succeeded. Operator/developer/resource guidance and overnight022 handoff + five companion records refreshed. PR40 and PR77 remain open drafts at ced6c1cb004887dcdafaea59a2976020be649f8e and cd5281b0ae7b484572bfb35ccb7e51ef5b3be4b3; PR65/72 remain open drafts, PR74 closed. Actual financial-owner source/custody not established; no ownership transfer inferred. No protected source touched.

## Productive arrangement and external evidence

The question is whether a conditional power customer can replace individually reserved backup compute with a rights-cleared, jointly controlled remote pool. This would change the productive arrangement, not sell another scheduling optimizer. Alternatives are (1) independent on-site power or firm grid service, actual complete price unknown; (2) direct remote reserved compute with sufficient dedicated capacity; (3) rights-cleared joint remote contingency capacity; (4) no deploy. Competent conventional allocation and cloud resource-sharing are strong incumbents. An external buyer/utility need, willingness to pay and live workload are not established. Do not confuse the source's regulatory innovation with ours.

Primary sources read 2026-11-25:
- FERC June 5 2026 order 195 FERC ¶61,196, paras 99–101, https://spp.org/documents/76880/20260605_order%20-%20revisions%20to%20add%20the%20conditional%20high%20impact%20large%20load%20service_er26-1323.pdf . CHILLS is conditional; disconnection is possible, so an assumed maximum interruption duration or noncoincident customer outages are not supported. SPP's docket index https://www.spp.org/spp-documents-filings/?id=576876 lists the October 26 compliance order; its PDF returned 403, so full current tariff terms are not verified. Do not represent this as legal advice or a specific approved operating agreement.
- AWS https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-share.html documents same-organization-only Capacity Block sharing and first-come-first-served occupation, not owner priority or assured cross-customer access. https://docs.aws.amazon.com/en_eu/AWSEC2/latest/UserGuide/ec2-capacity-blocks.html documents advance reservation. No account, sharing permission, actual reservation or transfer exists here. Independent customer pooling cannot simply be assumed from this feature. No attempt to circumvent rights or change organization membership.
- https://aws.amazon.com/ec2/capacityblocks/pricing/ displayed USD 5.970 per p5.4xlarge instance-hour (one H100) for Ohio/Oregon at inspection. This is a transcribed indicative posted price, not a live offer, supplier commitment, measured resource bill or complete cost. Page bytes were not acquired/hashed.
- Published work https://arxiv.org/abs/2609.05406 models duration-dependent flexibility and correlation using real trace-derived data. The associated Zenodo record 22308423 was not accessible; no workload trace was downloaded or verified. No empirical work units or outage distribution imported from it.

## Frozen experiment and failure adjudication

Source frozen at 202d3a3f365206941abed7e7c32f65340afe4f24, blob 7929730037417ec77cddb6da09c0b4545f33e2b5. Executed retrieved JS expression in the included execution environment. Reproduce by evaluating the file as a JS expression and serializing the return value (the bare node command in the header does not print it). All eight cases retained in original result 2f5704970ad96afc1e206d2fc14498757ad31394, blob 5b1602b2e40472de4075fc7aadfaccac4cf230f7. The augmenting matcher and separate exhaustive Hall test agreed on all 13,673 scenario/capacity comparisons. **The registered experiment nevertheless FAILED**: expected minimum six slots in the FCFS arm, actual four. Do not promote this to a pass. Both failed invariant fields are retained. The original occupancy assumption allowed concentrating all reserved slots at one pool and limiting occupied capacity there to two. It therefore did not imply the assumed four-slot total occupancy loss. No implementation error in matching was detected by the independent method; the protocol expectation was wrong.

Eight authored scenarios, no real workloads. Two simultaneous unit slots per affected site, four sites, assumed pre-staged equivalent jobs, 48 booked hours and 47 usable hours (illustrative). No actual continuous availability or latency is proven.

| Stress/rights condition | Minimum total slots | 48h indicative reservation component, USD |
|---|---:|---:|
| At most one site | 2 | 573.12 |
| At most two | 4 | 1,146.24 |
| All sites | 8 | 2,292.48 |
| One site plus one reserve pool unavailable | 4 | 1,146.24 |
| All sites plus one reserve pool unavailable | 16 | 4,584.96 |
| Split same-org rights | 4 | 1,146.24 |
| Fixed per-pool occupancy assumption | 4 | 1,146.24 |
| One external site has no eligible rights | Infeasible | Unknown |

Direct 8-slot remote reservation reference $2,292.48 is not equivalent under reserve failure, restricted rights or occupied capacity. On-site/full firm alternatives and human-plus-conventional-software implementation costs unmeasured. Reservation component only; local capacity costs, rights, data movement, checkpointing, support, outage, availability, taxes, capital, engineering, acquisition and actual billing unknown. Savings are not margin, customer surplus or revenue.

## Separate diagnostic (not a retry)

Frozen 483a2ac80711f53509c29ad07c5d63271c262682, blob 51dbe296f9397d1768b1fae1a1237d0aacf8c5fc; result 5590cf8d0852fb30bc919eb6027339e0d83991a2, blob 2998003f96f05e36898342d16a3b15120c42116c. All five distinct conditions passed: 565 capacity pairs, 7,496 physically feasible occupancy checks, zero discrepancies against closed-form worst-case availability. Two tasks require 4 slots if each pool may have two occupied slots and one pool may be unused; 6 if both pools must have at least two slots; 6 if up to four uncontrolled slots can be concentrated arbitrarily; no feasible finite reserve under unrestricted FCFS; 2 if exclusive admission is genuinely guaranteed. This corrects the interpretation, not the old result or its verdict. No claim that the supplier supplies any of these occupancy bounds.

## Acceptance matrix
| Claim | Verdict |
|---|---|
| Compare three material productive arrangements and no deploy | Achieved as source-grounded conditional screen |
| Original registered 278 engineering gate | Failed; preserved |
| Matching vs Hall comparator | Achieved for all registered comparisons, conventional tie |
| Separate occupancy diagnostic | Achieved, finite authored cases only |
| Actual contracted power, workload, reserve rights and complete economics | Blocked/unestablished |
| Native lifecycle/owner transfer | Not exercised / blocked |
| Causal invention, successor gain or recursive improvement | Unqualified |
| Actual paid commerce, native T365 and US$3B objective | Unqualified; zero contracts/revenue, native profit null |

**Decision: NO DEPLOY.** Retain the counterexample and rights-aware feasibility screen, not a capacity-sharing business claim. Conditional service does not guarantee disjoint failures. Shared capacity with uncontrolled admission cannot guarantee priority even if the optimizer allocates nominal capacity correctly. The missing means for this route are enforceable, rights-cleared admission and independent availability with a real workload and costed complete contract; AWS intra-org sharing alone already exists and is not our invention. Do not pursue a resale scheme or repeat another authored capacity grid. Prefer a different source-grounded consequential construction unless real rights-cleared inputs become available. No new authority needed for independent research.

Measured JS wall 90 ms + 2 ms; CPU and actual host/model billing unknown. Separate algorithms within the same environment, not independent human review or hosted CI. Only this research branch was written. No actual spend, outreach, loans, transaction, new credential, financial action, production deployment or obligation created. Historical failures, protected liabilities and source untouched.
