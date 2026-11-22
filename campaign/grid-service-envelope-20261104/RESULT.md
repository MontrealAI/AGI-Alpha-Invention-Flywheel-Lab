# Constructed, independently checked, and not a new enabling advantage

**All 24 registered runs completed. Eight of eight primary constructions pass the independent hourly-model checker; all eight are equally available to the ordinary complete flexible-connection route. The alleged new enabling residual is rejected in this finite comparison. No Blue Sky admission or commercial qualification is earned.**

Source was published before confirmation at `c41003078379e97a048b5dbf87e7676a0ca2b7a8`. Computational closure is `a58c8699af2bec2c4e6978fa5984ddc1fa1c449d9b645633ec1307050f178d0b`; workflow-only correction `416e320` leaves it unchanged. The original registration, prospective development amendment and both development failures remain intact.

## What actually ran

Two fixed historical day-ahead profiles (1 July and 1 December 2020) × two RTS buses (101 and313) × two IT capacity scales (10 and100MW) × three policies = **24 runs**. Each primary run jointly constructs 168 hourly fault-contingent plans with common pre-observation decisions, two released 12-hour work batches, source network/generation constraints and sized storage/backup. The mixed-integer model has39,841variables and112,795constraints. Every accepted primary witness passes1,939 independent checks and168 command replays. The reported solver gap is zero; its bound is solver-reported, not an independently proved optimality certificate.

- Primary integrated plan: **8/8 accepted** in the registered hourly approximation.
- Ordinary flexible connection + same storage/backup/workload shifting: **8/8 exact available-plan ties**, analytically because feasible sets, information and complete modeled cost permissions are identical. This is not a benchmark of two independent discovery algorithms.
- No-equipment control: **0/8**, solver-reported infeasible.
- Fixed half-capacity work each hour: **0/8**, solver-reported infeasible within the registered equipment bounds.

The last16 outcomes are not physical impossibility proofs, and no separate infeasibility certificate is claimed. A larger fixed-work battery or a different operating/connection arrangement could change them. The equal-permission ordinary complete route already defeats the claimed residual, so weaker controls cannot earn invention admission.

All sites/days select the same equipment at a given scale. Thus these cases establish no economically meaningful siting advantage; authored deadline/outage constraints, rather than a newly removed grid bottleneck, drive this portfolio. Annual cost is a conditional repetition formula, not a year of operational simulation.

## Declared cost subtotal, not market price

| Quantity |10MW IT case|100MW IT case|
|---|---:|---:|
| Modeled daily work, MWh-equivalent IT units|120|1,200|
| Battery energy, MWh|50.5263|505.2632|
| Battery power, MW|3.3241|33.2410|
| Backup power, MW|0.3241|3.2410|
| Asset funding including20% contingency|$223.88m|$2,230.67m|
| Restricted performance reserve|$18.66m|$185.89m|
| Working capital|$0.51m|$5.13m|
| Initial all-cash requirement|$243.05m|$2,421.69m|
| Conditional annual economic subtotal|$67.16m|$669.42m|
| Break-even subtotal per modeled work unit|$1,533.38|$1,528.35|

Every monetary coefficient is an explicit **uncalibrated scenario assumption**, not an installed-equipment quote or a measured compute delivery cost. Full delivery price is **(modeled annual subtotal + unknown complete cost U) / annual work**. U includes utility redispatch/startup/no-load, tax, permits, true interconnection and rights, equipment repair/replacement after faults, fuel logistics and emissions permissions, outage liabilities, annual working-capital carry/opportunity cost and other jurisdiction-specific residuals. Its value is unresolved and need not be small. There is no verified conversion to real FLOPs, GPU hours or accepted customer work.

The performance reserve is restricted capital, not an expense, revenue or proof of sufficient liability coverage. Its opportunity charge is counted separately. Hypothetical60% debt at8%, five years and2% fees implies initial equity/reserves of about$111.41m/$1,110.05m and annual debt service$33.64m/$335.21m. Debt principal is not revenue. Debt service is a cash-flow obligation, not added again to capital-recovery annuity costs. No finance is known available, none is secured, and this experiment opens no ledger or native account. The $100,000 and$1billion figures are reference funding envelopes, not grants, universal caps or profit.

## Complete alternatives and participation

The ordinary flexible route has the same accepted outcome at the same modeled budget, so the candidate cannot charge an invented novelty premium. Relocation to either tested bus gives no numerical improvement before relocation cost; actual site acceptability and relocation cost remain unknown. Firm connection, reinforcement and independently protected feeds remain legitimate complete alternatives, but real quotes, energization dates, protections and acceptance are unavailable. They are **unresolved**, not shown inferior or impossible. For any such alternative to dominate, its accepted complete-cost offer must undercut the modeled subtotal plus the respective unknown residuals; no numeric tariff threshold can be claimed without its service scope and quote.

Non-entry incurs no modeled operating commitment and delivers no work. No buyer value, acceptance preference, signed participation or available funding has been supplied, so nothing here rationally selects market entry. The finite minimax planner handles seven authored nature regimes, not strategic buyers, suppliers, competition or a truthful market mechanism. This is not game-theoretically optimal enterprise commerce.

## Exact limits and fail-safe behavior

The registered model is hourly, lossless DC with fixed whole-day thermal commitment. It omits AC voltage/stability/protection, source reserve requirements, forecast error, actual backup startup and UPS transitions. Some non-worst-case schedules contain simultaneous *hourly average* charge/discharge. The shared-power bound accounts for both, but no within-hour physical switching feasibility has been demonstrated. No physical device command is issued. The largest-nameplate-unit outage is vacuous in3/8 primary cases because the common commitment leaves that unit off; this is not an all-unit N-1 study.

An observation outside the declared set causes the offline policy to return zero grid import and withdraw its completion guarantee. The funded-reserve arithmetic cannot make missed work complete. End-of-day SOC is checked, but annual repetition after an equipment fault would require restored equipment and separately costed repair; no uncharged perpetual post-fault availability is asserted.

## Reproduce and inspect

Install `requirements-grid-envelope.txt` in an isolated environment, then:

```sh
python -m grid_service_envelope.construct --data campaign/grid-service-envelope-20261104/data --day 2020-01-01 --output development.json
GRID_ENVELOPE_WITNESS=development.json GRID_ENVELOPE_REQUIRE_WITNESS=1 python -m unittest discover -s tests -p test_grid_service_envelope.py -v
python -m grid_service_envelope.run --role reproduction --output /absolute/new/grid-envelope-output
```

The existing public registration/amendment and unchanged computational source bind this experiment. The [successful hosted reproduction](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41845523339) records all24 outcomes and the matching source closure in its logs. Exactly eight compressed primary witnesses accompany this compact report; ancillary local review and row files are not part of this publication. To check a stored primary witness without rerunning optimization, decompress it with Python gzip, parse JSON and call `grid_service_envelope.verify.verify(witness, data_directory)`. The independent checker pins the source manifest and reconstructs all registered constraints. It does not certify utility permissions or physical operation.

**Tried → outcome → lesson → next:** construct an integrated network/work/failure service envelope → computationally feasible in8cases but matched by the strong ordinary route → the unproven missing means was already ordinary complete engineering in this tested scope → retain the small checker and honest boundary; do not promote this as a new flagship or write a success paper. Any further grid claim first needs a genuinely unmet, externally specified service constraint and actual physical/rights/cost qualification, not another favorable optimization run.

## Published witness identities

Each path is relative to this report's `evidence/` directory. SHA256 values bind compressed bytes; independent verification accepts the decompressed JSON.

|Witness|Compressed bytes|SHA256|
|---|---:|---|
|2020-07-01-101-10-primary.json.gz|150840|`07c57dbdd6b08cfacffbabe93b82c476b06b8965f2dc79783f5cee957df4c621`|
|2020-07-01-101-100-primary.json.gz|151377|`d91c0c6d48b840b57ec5f0e255f9622852747b31d8b2bc54a2c5fac3ff5f0e5f`|
|2020-07-01-313-10-primary.json.gz|150475|`ec60e3945b7c167517183b4deb69d95cbff362c3f10156247a67648d3a1873ac`|
|2020-07-01-313-100-primary.json.gz|150525|`8100cad066d0cdf9955c0e2c75a4079fc1c8f28116212d9c978a03509fec1cad`|
|2020-12-01-101-10-primary.json.gz|148967|`b8f25ba7805f455a2ed6b771f6edc0b2dcee75b324830f975522790b5b4d5a88`|
|2020-12-01-101-100-primary.json.gz|150080|`6cb622a9928efaa2c9aa521066f6a7f95e5e9ed812d401f3b27b981e6bc40e8c`|
|2020-12-01-313-10-primary.json.gz|148630|`388cae003cb352905857e7169bbbe0c258f37a8fb8b706f88b845c036f0f904f`|
|2020-12-01-313-100-primary.json.gz|148192|`3052e10e1192c07a59a9fda2491e69a72b1a5d1e71b613578d473e0383144a07`|

