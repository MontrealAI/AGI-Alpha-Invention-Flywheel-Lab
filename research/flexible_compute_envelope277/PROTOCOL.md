# Flexible compute envelope 277 — registered finite construction

2026-11-25. Source base 297a51c25c48031e1e6f964835f4dfae3ddb8023. Nonconflicting stand-alone research; no native account, financing, grid control or real contracts.

## Selection before execution
1. Distribution interconnection queue-management software: DOE iQMS announced up to $11.2m for utility pilots, with existing recipients and incumbent software. The program budget is not accessible revenue or a large-scale margin. Do not pursue this already competitive complete service without an unmet outcome.
2. Conditional capacity assurance for compute: FERC's June 18 orders identify insufficient flexible-load services; response deadlines were Nov 16/20. GridCARE/PGE announced an 80 MW incremental capacity project in Oct 2025. GridCARE and utility engineers are strong complete alternatives. Select the narrower candidate: a checkable capacity/deadline envelope that a compute operator could use to negotiate a conditional capacity contract. This is not a tariff approval, grid study, or newly established market gap.
3. Energy/carbon-aware batch scheduling: ICP-AI (Aug 29 2026) and SustainCluster demonstrate strong incumbent planning and scheduling. No residual established. Do not sell another energy optimizer.
4. No deploy: default unless real beneficiary acceptance, complete competitive costs, contractual terms and reachable demand support entry.

Sources (read 2026-11-25; page text, not verified raw-byte downloads):
- https://www.energy.gov/cmei/i2x/i2x-innovative-queue-management-solutions-iqms-clean-energy-interconnection-and-0
- https://www.ferc.gov/cost-transparency-customer-protection
- https://www.pjm.com/committees-and-groups/task-forces/camstf
- https://www.gridcare.ai/post/pge-and-gridcare-accelerate-hundreds-of-megawatts
- https://arxiv.org/abs/2608.29359
- https://github.com/HewlettPackard/sustain-cluster
- https://www.dominionenergy.com/virginia/rates-and-tariffs/curtailment-notices

Dominion's public summer notice calendar is a real observed timing sequence: May 16–Sep 30; 14:00–21:00, at most 19 requests. The published 2026 dates are transcribed in the executable. No assertion that these notices are applicable to a new data center, that they are its full contract, or that curtailment depth/energy was measured. All work, capacity and deadline values are authored scenarios. Time is nominal local calendar hours (no DST transitions within this summer). Use every notice, not selected days.

## Frozen experiment
138 days; 24 slots/day; divisible homogeneous work released each hour until its deadline fits the horizon. Work arrival 20 units/h; normal capacity 24 units/h. No real MW conversion is claimed. Relative deadlines D=1,8,24,48 hours. Effective curtailed capacities F=0,8,12,16,20,24. Full firm is F=24; interruptible is lower F; a hypothetical independent backup would need to cover the effective capacity gap, with cost and availability unknown. No deploy earns/spends nothing. No physical actuation or financial events.

For preemptible divisible jobs on one aggregate resource with capacity observed each hour, EDF (earliest deadline first) is a strong exact conventional scheduler; no weaker heuristic comparator. Interval demand is 20*max(0,L-D+1). Maximum curtailment hours in any length L interval among all legal calendars is min(19*7, floor(L/24)*7+min(L%24,7)); aligned consecutive calls attain the envelope. The minimum interval slack supplies a robust certificate, not a probabilistic forecast. Compare against EDF independently on the full observed calendar and a 19-consecutive-day legal stress calendar, plus an exhaustive miniature (5 days, 2 calls, all subsets and all intervals) testing the overlap formula. All 24 arms retained. Fixed one execution; no parameter tuning or repeat to improve result. Require observed interval certificate matches observed EDF, robust result matches stress EDF, robust pass implies observed pass, and miniature overlap equality for every length. If any fails, retain the failure. Output minimum integral firm capacity per deadline from the tested grid only, plus exact integral minimum from all F=0..24 using the analytic certificate (separately labeled). No claim of novel algorithm, causal AI improvement, physical capacity, commercial profit or general grid reliability. Costs of compute, backup, interconnection, customer acquisition, verification, outages, insurance, taxes, support, and actual billing unknown; no price or willingness to pay assumed. No native account created. All economic gates remain unqualified. A successor would need real rights-cleared workload deadline/energy traces and independent utility acceptance of a complete contract and metering rules; no forecast value booked.
