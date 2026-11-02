# Registered stage result

Frozen source: portfolio commit `34f0319d520fcab78796e4ee10d5401e7afd433d`; `PREREGISTRATION.json` SHA-256 `8c420598312fa2818aa140bff68c58fba3348e693dc2f45d5e3f150c06ffe0ee`. The finite run executed once. Source, acceptance and scenario inputs were unchanged after freeze.

| Outcome | K1 process heat | K2 water-recovery heat duty |
| --- | ---: | ---: |
| Unchanged electrical heating | Infeasible | Infeasible |
| Heat pump A alone | Infeasible | Infeasible |
| Storage B alone | Infeasible | Infeasible |
| Heat pump plus storage | Feasible | Feasible |
| Electrical input over 48 h | 12,360.280845 kWh | 6,716.160174 kWh |
| Unrestricted conventional design | Exact energy tie | Exact energy tie |
| Equal-content ordinary reuse | Exact energy tie | Exact energy tie |
| Separate fresh LP formulation | Exact energy tie | Exact energy tie |

All eight feasible schedules pass the producer's heat, storage, power and source-bound checker at the registered absolute tolerance. Independent verification is a separate portfolio receipt; the producer's pass is not independent acceptance. Four registered adverse cases—lost heat source, 50 kW electrical cap, lower heat-pump efficiency and heavy storage losses—are infeasible. All negative cases remain in `evidence/RESULTS.json`.

K1 consumes 12,360.280845, 12,360.220871 and 12,360.213340 kWh at time steps of 1, 0.5 and 0.25 hours. The largest relative difference from the quarter-hour result is about 0.00000546, below the registered 0.01 threshold. This verifies this discretized screening task; it is not a compressor or transient-plant convergence study.

The successor's salt/water balance models 3,250 kg/h of product water, 1,750 kg/h of concentrate and 350 kg/h of conserved salt from a 5,000 kg/h feed. The heat duty is 424.005787 kW under the declared six-effect and 75% sensible-recovery assumptions. No physical water was produced and no purity was measured. The pure-water latent-heat approximation differs from three pinned NIST values by 0.0208%, 0.1157% and 0.3767%, respectively. That reference check does not validate boiling-point elevation or fouling in concentrated brine.

| Claim | Verdict | Why |
| --- | --- | --- |
| Actual executable design and schedules constructed | Supported | Sparse dispatch source, separate formulation and replayable schedules exist. |
| Complementarity inside the stated model | Supported | Both individual changes fail; their combination serves the original duty. |
| Thermodynamic and conservation code checks | Supported within model | All accepted schedules obey recorded balances and bounded inputs. |
| Physical industrial capability | Unresolved | No calibrated compressor map, brine pilot, output-quality test or equipment commissioning. |
| Advantage over a competent complete conventional route | Failed | Same-outcome, equal-permission conventional route ties exactly. |
| Retained algorithm or discovery advantage | Failed for this stage | Ordinary reuse and a fresh formulation tie; same-constructor fresh source cannot establish independent discovery. |
| Different successor function | Supported as a constructed model | Water-recovery duty differs from process-heat delivery. |
| More consequential successor | Unresolved | No independently specified site/beneficiary outcome compares consequence across heat and water. |
| Blue Sky industry creation | Unresolved and not admitted | Existing complete integration and missing physical/economic evidence leave no established residual. |
| Actual commerce or revenue | Absent | No buyers, contracts, orders, payments or real transactions. |
| USD 3 billion annual profit | Not established | The science run makes no financial projection; all physical and financial qualifications remain separate. |

Decision: retain the bounded thermodynamic/dispatch constructor and failure rules; do not offer it as a physically qualified plant or grant a novelty premium. The strongest complete route remains viable. The next discriminating evidence would be a public measured compressor/storage/brine pilot trace with separately specified purity, fouling and duty acceptance. Extra synthetic site identifiers would not resolve that gap. The current finite prerequisite stage is closed; further physical confirmation requires a separately registered, available evidence source or authorized qualified experiment.

No tests were rerun until favorable. No failed case was dropped. No paid APIs, extra spending, outreach or physical operations occurred. The saved schedules are computational artifacts, not measured industrial deployment. Root canonical economics may price a nonexclusive computational package only as an explicitly conditional scenario with refusal and complete alternatives.
