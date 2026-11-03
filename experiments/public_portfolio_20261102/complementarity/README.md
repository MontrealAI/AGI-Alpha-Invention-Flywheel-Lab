# Complementary industrial heat and water construction

This is an executed-design experiment, not an installed plant. The candidate is a heat-pump and thermal-storage combination that serves continuous process heat from intermittent low-grade heat under an electrical-power limit. The different successor function is hypersaline-brine water recovery. An independently supplied water-quality or industrial-operability result is required before any physical output may be sold as qualified.

## Candidate comparison before confirmation

| Candidate and important outcome | Binding question | Complete incumbent route | First construction, cost/lead-time uncertainty and decision |
| --- | --- | --- | --- |
| Continuous industrial heat from intermittent low-grade heat, followed by industrial water recovery | Can source temperature, available heat, grid power and storage jointly supply the required heat without free initial energy? | Industrial heat pumps, thermal storage, conventional process integration and vapor-recompression/evaporation systems. A conventional engineer receives the same components and optimizer. | **Selected:** coupled mass/energy balance plus feasible dispatch. Computationally decisive conservation and complementarity tests are possible locally. Supplier performance, fouling, pressure equipment, commissioning cost and lead time remain unmeasured. |
| Firm renewable hydrogen production with water conditioning and buffer storage | Can variable power, minimum production obligations, water, compression and storage be funded together? | Commercial electrolyzers and conventional power/storage/production optimization. DOE already publishes system performance targets; targets are not achieved offers. | Not selected: a full commissioning and gas-safety validation gap dominates a local scheduler. Assumed electrolyzer purchase price would not demonstrate new productive means. |
| Low-grade-heat-driven CO2 sorbent regeneration | Can a compatible sorbent, heat source and contactor deliver a specified net removal rate over repeated cycles? | Existing sorbent/contactor development, heat-pump integration and commercially available process engineering. NETL lists low-grade-heat sorbent research. | Not selected: kinetics, humidity degradation, adsorption selectivity, net lifecycle emissions and qualified storage cannot be inferred from heat balance. More consequential chemistry may exist but is not supplied by this environment. |

There is no measured capital threshold establishing that the selected outcome was previously uneconomic. The experiment tests a stated engineering obstruction; a strong conventional tie falsifies an alleged exclusive enabling residual. Selection does not admit a Blue Sky flagship.

## Constructed means and original-purpose bridge

`thermal.py` constructs an explicit linear program. Its variables are heat-pump electrical power, electrical resistance backup, storage charge/discharge power and stored thermal energy. Every time step must deliver the original required heat. Electrical power, source heat, heat-pump thermal output, storage power and stored energy are bounded independently. Storage begins and ends empty, so neither initial heat nor residual stored heat is counted as free production.

The heat-pump screening COP is a declared fraction of the reversible Carnot heating COP, with explicit heat-exchanger temperature approaches. Delivered heat equals recovered source heat plus electrical work. The fraction is an **authored deployment assumption**, not measured compressor performance. A Carnot bound and exact conservation are necessary, not sufficient, engineering validation. Fixed COP ignores part-load, refrigerant, heat-exchanger, compressor-map and transient effects.

K1 is 48 hours of continuous 500 kW heat at 110 C under a 300 kW electrical limit, with twelve daily hours of available source heat. Changes A and B are heat pumping and thermal storage. The registered factorial tests unchanged, A, B and A+B. An unrestricted conventional construction gets A+B and the same complete mathematical model. SciPy HiGHS dual-simplex and interior-point variants check solver agreement; their common implementation lineage is disclosed.

K2 changes function to recovery of water from a 5,000 kg/h, 7% salt-by-mass feed, ending at 20% salt-by-mass concentrate. Salt and total mass are conserved. A latent-heat screening approximation plus feed sensible heat produces the heat duty. Six effective latent-heat reuses and 75% sensible-heat recovery are **assumptions**, not performance evidence. The model does not validate boiling-point elevation, salt rejection, scaling, corrosion, fouling, carryover, vacuum integrity, membrane transport or water quality. It cannot certify potable water or zero liquid discharge. The 75 C utility sink represents a 5 C approach above the 70 C evaporation assumption; actual brine boiling temperature is an unresolved correction.

The retained asset is the frozen dispatch and thermodynamic balance source, with no learned parameters or cached answer. Equal-content ordinary reuse gets that same source. The no-inheritance arm in `fresh.py` constructs a different thermal-output LP formulation without importing the retained kernel; its source was authored by the same constructor from the same mathematical contract. It is **not an independent measured reinvention study**. These controls can support an implementation/content-reuse result, not a better-discovery claim. Independent verification may reconstruct the constraints separately. No procedure is entitled to hidden verifier cases, answers or later measurements.

K2 serves a different potentially consequential function. That it is *more consequential* than K1 remains unestablished: comparing water and heat requires a real site and beneficiary outcome. Transfer of a balance solver is not proof of industry creation.

## Evidence and run

The source and protocol are frozen before registered confirmation. `PREREGISTRATION.json` gives the finite stage and rejection rules. From the repository root:

```bash
python3 experiments/public_portfolio_20261102/complementarity/thermal.py --output /absolute/new/complementarity-results
```

Results contain actual computed schedules and measured process/wall times, separately from industrial estimates. The 48-hour experiment is not an annual profit calculation. Root portfolio economics uses the canonical account and must not count modeled plant output as observed production.

## Deployment economics supplied to the coordinator

The physical offering would be an integrated heat/water system or qualified engineering design, with supplier-neutral procurement and ordinary competitors. This experiment delivers a computational screening design only. The buyer may choose in-house engineering, an established heat-pump/process integrator, another automated provider, delay, or refusal. No willingness to pay, industrial demand, quote, exclusive right or royalty is established.

All amounts below are **uncalibrated sensitivity envelopes**, not quotes. They must not seed a profit claim without an explicit conditional scenario and finite buyer choice. Suggested full-system envelope: heat-pump package USD 0.4–1.5 million; thermal storage USD 0.1–0.8 million; brine evaporator and pretreatment USD 0.5–3 million; site/pressure/electrical integration USD 0.3–1.5 million; pilot and qualification USD 0.1–0.8 million; contingency/decommissioning USD 0.1–0.7 million. Delivery could take 6–24 months and fail qualification. The sum is not the simulator's measured cost, and larger capital is not secured. The USD 100,000 case can fund only a bounded design/pilot hypothesis; USD 1 billion is a separately modeled financing hypothesis.

Cost electricity from computed kWh and an explicit site tariff, not a universal assumed saving. Charge source access, cooling opportunity cost, water intake, pretreatment chemicals, consumables, corrosion-resistant equipment, manufacturing yield, construction labor, specialist engineering, pressure/vacuum safety, spares, calibration, downtime, discharge handling, warranty, insurance/liability, taxes, financing and support tails. Heat displaced and water recovered cannot both be priced at their full independent customer surplus without accounting for joint value and displaced obligations. Plant capex cash and depreciation are separate. Future savings, receivables and promised funding cannot pay installation deposits.

Internal human intervention during local construction is unmeasured beyond the operator's activation instruction; no physical operator, engineering reviewer or customer participated. A credible physical deployment requires domain review, commissioning and continuing maintenance; any hours are scenario assumptions and yield a hybrid result. Unknown included-access/host resource billing remains unknown, not zero economic cost. No paid APIs, extra spending, purchases, outreach or physical operation are part of this experiment.

## Primary sources and rights

Checked 2 November 2026. Only source facts and original derived code are retained; no third-party text, PDF or raw dataset is republished.

| Source | Verified fact used | Scope and rights |
| --- | --- | --- |
| [DOE onsite energy technologies](https://betterbuildingssolutioncenter.energy.gov/onsite-energy/technologies) | Industrial heat pumps recover low-grade heat; thermal storage and integration already exist. | Primary public DOE material. Used as factual basis and competitor evidence, not a performance dataset or exclusive IP grant. |
| [DOE process-heat efficiency](https://www.energy.gov/cmei/ito/finding-efficiencies-process-heat) | Process heat is consequential and waste-heat management is an established development route. | Source does not calibrate this site's cost, demand or performance. |
| [IEA heat-pump operation](https://www.iea.org/reports/the-future-of-heat-pumps/how-a-heat-pump-works) | A heat pump transfers source heat plus electrical work and can supply industrial heat. | Report identifies CC BY 4.0. No report content is redistributed. Household COP examples are not used as industrial calibration. |
| [DOE heat-pump and storage integration research](https://www.energy.gov/nepa/articles/cx-030820-cost-effective-integration-pcm-thermal-energy-storage-and-wet-compression) | Joint heat-pump/storage construction is an existing research subject. | Refutes a generic novelty claim. Does not establish our package's performance. |
| [DOE alkaline-electrolyzer targets](https://www.energy.gov/cmei/fuels/technical-targets-liquid-alkaline-electrolysis) | Public system energy-efficiency and cost targets exist. | Targets and 2022 status are identified separately; not current achieved supplier quotes. |
| [NETL project information](https://netl.doe.gov/projects/project-landing-page-list.aspx) | Low-grade-heat CO2-sorbent regeneration is already under development. | Research results from another project are not our results or a right to use a proprietary sorbent. |
| [NISTIR 5078](https://www.nist.gov/srd/nistir-5078), [Table 1](https://www.nist.gov/document/nistir5078-tab1pdf) | IAPWS-based water/steam property tables supply latent heat at 40, 70 and 100 C for a registered screening check. | Downloaded Table 1: 84,823 bytes, SHA-256 `8134235cf070ad053f006d4e98ebdccd12a621ad86fb3752d38bbce0fbb9cf1f`. Only three property facts are retained. Physical brine validation is still missing. |

No patentability, freedom to operate or enforceable monopoly has been assessed. NumPy and SciPy are existing environment dependencies with their own BSD licenses; no vendored dependency is copied. Project publication is not proof of commercial rights to physical equipment or source data.

## Applied manuscripts

The flagship's purpose/formulation/acceptance distinction and strong unrestricted comparator (pp. 2–4, 9–12) require the original thermal and water outcome to remain fixed. *Beyond the Production Frontier* pp. 4–11 motivates the costed A/B factorial, resource cuts, staging and separate cash/physical conversion; pp. 11–13 prevents monetary or software outputs from standing in for physical capacity. The AGI ALPHA foundation informs bounded jobs, explicit authority, validator acceptance and retained evidence; it is not a device qualification. Original supplied PDF hashes:

```text
transformational-intelligence-202610.pdf d7170e8217e3bf6aa1b84868c1c76c5994c6995c5297ed092d7e72a6430c664f
beyond-the-production-frontier-20261019.pdf 3e5c4bcdb8a6d70ca4bdf1e3285705650e773436555c69ef2ca8d07a5a0e3d00
agi-alpha-foundation-20260430.pdf 4b290d5a8232364b8808c0af8a96e7c9b152afd7ac3f5ba05668a538e073791a
```

Confirmed complementarity alone would be a useful bounded engineering result. A conventional complete tie, absent site validation and unvalidated willingness to pay leave industry creation and the USD 3 billion objective unresolved. The next discriminating construction is a public measured transient heat-pump/storage or brine pilot trace with independently specified fouling and output-quality criteria, not more synthetic identifiers.
