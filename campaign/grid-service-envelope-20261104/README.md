# A grid connection that promises completed work, not annual energy

**Status: construction and prospective qualification, no live service or Blue Sky admission.**

The missing-means hypothesis is a site-specific operating envelope that joins utility-protected network operation to deadline-bound compute work, backup, storage and funded downside. The consequence could be earlier productive load connection, but an existing flexible connection with the same ordinary equipment and scheduling is a strong complete alternative. This experiment gives it exactly the same information, construction and financing permissions. A tie rejects the alleged residual, not the value of ordinary engineering.

The finite registration was published at `0d9d20258b19dd11b3d2599201d9c445ab067f72` before confirmation. January development revealed that an all-thermal-on assumption makes the *existing* RTS system infeasible. `DEVELOPMENT_FAILURE.json` preserves this loss; `AMENDMENT_01.json` prospectively replaces it with one common fixed 24-hour binary commitment per thermal unit. This is a restricted unit-commitment policy, not a proof of physical feasibility or impossibility. No July/December outcome was used for the correction.

## Actual construction

Known HiGHS mixed-integer optimization joins 73-bus, 120-branch DC power flow, pinned generator and hourly profile bounds, thermal ramps, two released work batches with 12-hour deadlines, equipment sizing, fuel/SOC constraints, and seven fault cases. Grid service disconnects on the declared feeder-trip intervals. All plans are identical until the fault is observed at hour8; workload timing is common to all plans. The battery cannot be counted both as available work energy and its terminal reserve. Equipment commitments are chosen before fault identity is known. An independent checker reconstructs the constraints from source CSV and witness data without importing the producer model.

This produces a **modeled completed-work contract** in MWh-equivalent IT work, not measured FLOPs or a real workload acceptance guarantee. The guarantee is limited to the exact registered deterministic cases and assumed observations. Unmodeled events fail closed at the connection boundary; completion then has no guarantee. A financial reserve does not repair missed work. No real customer, utility, supplier, insurer or funder has consented.

## Data and applicability

Pinned [RTS-GMLC](https://github.com/GridMod/RTS-GMLC/tree/3ece0d3725c844056132393ee252b3083dd4eab4) data are credited to **DOE/NREL/ALLIANCE**, without endorsement. The `data/` directory retains a compact three-day slice, exact topology, manifest, full upstream README and the entire Data Use Disclaimer Agreement present at the pin. That upstream notice itself ends abruptly at “OR IN”; its bytes are preserved, not repaired by invented terms. Data are provided AS IS and the notice includes an indemnity obligation. SHA256 identities and Git blob IDs distinguish whole upstream files from selected rows.

DAY_AHEAD profiles are forecasts, not realized operation. Hydro/RTPV output is fixed, wind/PV curtailable, CSP and existing storage disabled rather than inventing their energy state. DC flow includes transformer taps and continuous line limits, but omits AC voltage, stability, protection, reserve markets, subhourly startup/UPS behavior, forecast errors and real network rights. The benchmark is not an actual grid application.

[Johnson, Blanford and Bistline](https://arxiv.org/abs/2611.00462) motivate checking severe individual curtailments, not just annual totals. Their national model does not calibrate this test network. [Electricity North West](https://www.enwl.co.uk/get-connected/apply-for-a-new-connection/flexible-connections/curtailment-information/) already supplies flexible-connection forecasts/indices and conditional curtailed offers. Its index triggers investigation and intervention, not an unconditional delivered-energy cap. Its regional eligibility and compensation terms are not assumed to apply here.

## Comparison, costs and rights

The primary ordinary flexible route is exactly the same feasible construction and equipment, without an artificial control handicap. Fixed-work and no-equipment controls expose which ordinary components are required. Relocation compares the tested buses but retains unknown relocation costs and site-specific acceptance. Firm connection and reinforcement remain legitimate outside options with unresolved quotes, timelines and qualifications; missing data are never labeled infeasibility. They are not artificially excluded to manufacture advantage.

All monetary coefficients are explicit uncalibrated scenario assumptions. Results report asset, contingency, operating, working-capital and performance-reserve requirements plus **unknown additive complete cost U**. Break-even is conditional cost recovery, not willingness to pay or profit. Financing requirements and debt-service cash flows are separate from economic annuities to avoid double counting. $100,000 and $1billion are funding references, neither available funds nor universal limits. No native account is opened and no real expense is incurred by this model. Actual host/model billing remains unknown.

The finite game is an equipment/work planner facing one of seven observed stress regimes, minimizing declared equipment-plus-worst-case operating subtotal. The solver bound applies only to that restricted mixed-integer program. There is no strategic buyer/supplier equilibrium, truthful-revelation proof, market-optimal enterprise or complete-system cost optimum; utility redispatch/startup/no-load costs remain in U.

## Mechanism dependency and continuation

OUT-STRATEGISE pp.3–8 and12–14 motivates one executable continuation per observed leaf rather than clairvoyant action; `construct.py` enforces pre-observation equality and `verify.py` rechecks it. OUT-DESIGN pp.7–13 motivates usable local capacity with intermediate-state obligations; every hourly power and SOC state is checked. These are applications of standard robust optimization, not reproductions of a manuscript's general theorem. The dependency is the joined network/work/failure contract, not another framework or paper. Its retained value is a small independently testable construction. Changed workloads, networks, failure sets, rights or costs require requalification; no funded successor is claimed.
