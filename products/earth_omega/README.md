# EARTH Ω
## Discover which charging-site opportunities deserve due diligence, and which do not

**Executable pre-feasibility prototype for EV charging operators and commercial-property portfolios.** Give it authorized candidate locations, evidenced development constraints and explicit economic scenarios. It produces a ranked decision dossier, break-even utilization, downside/upside NPV, a budget-constrained shortlist, and the missing evidence that prevents a defensible decision. It does not declare land commercially viable from a map.

This is a supporting instrument for the flagship's site-discovery ambition, not a demonstrated new frontier breakthrough. Its consequential next test is whether evidence-seeking agents can find economically valuable feasible sites that the strongest conventional site-selection workflow misses at equal total cost. That test has not run.

### Run now (Python 3.11+, no dependency installation, no paid service)

From repository root:

```sh
python -m unittest discover -s products/earth_omega/tests -v
python -m products.earth_omega.earth screen products/earth_omega/examples/mission.json --out /tmp/earth-dossier
python -m products.earth_omega.earth verify products/earth_omega/examples/mission.json /tmp/earth-dossier/report.json
python -m products.earth_omega.earth investigate products/earth_omega/examples/mission.json --out /tmp/earth-investigation.json
```

Open `/tmp/earth-dossier/index.html` locally. Output paths must be new: existing deliverables are not silently overwritten. The example is **entirely synthetic**, not a recommendation about any actual property. It demonstrates a profitable scenario excluded for unknown grid access, exclusion of overlapping catchments, a negative-NPV no-build option, and selection of the better qualifying scenario under capital limits. CAD/EUR are supported as separate input units, never implicitly converted.

### Discover actual candidate facilities without supplying a site list

```sh
python -m products.earth_omega.earth discover --out /tmp/earth-discovery --min-spaces 100 --max-age-days 90
```

The automated discovery path retrieves the official Paris parking and Belib metadata, checks ODbL licenses, downloads full bounded exports, checks counts, identifies candidate facilities, joins nearby public charging stations, assesses row freshness, and produces `discovery.json`, GIS-ready `leads.geojson`, and an offline `index.html`. It gathers source evidence and generates leads **without an operator-provided candidate list**. This is genuine rule-based automated discovery, not demonstrated frontier-model reasoning or commercial qualification.

A live November 16 run fetched **125 parking facilities and 1,969 charging records**, generated **120 leads** meeting the requested capacity threshold, and qualified **zero commercially viable sites**. All120 parking rows were older than the90-day freshness rule, and all120 lacked the reported EV-space count. Three charging records with missing station/point IDs are quarantined, not treated as a station named `None`. [Live receipt](evidence/discovery-live.json).

The source's EV-space field excludes accessible/PMR EV spaces. Its complement is not proven uncharged capacity. Unknown counts are never zero. Leads are ordered for evidence gathering by freshness, known reported EV-space fraction and facility capacity, **not by profit or demand**. Existing municipal concessions do not imply private property availability or operator willingness. This first discovery geography is Paris; it is not a worldwide property search. Use source-derived leads to investigate permissions, demand, connection terms and costs before creating an economic mission.

Derived discovery databases are ODbL1.0 with attribution and share-alike; code retains repository license. The output includes attribution. Check license obligations before combining with proprietary databases or distributing derived outputs. Raw transient downloads are not committed.

### Collect actual public evidence

```sh
python -m products.earth_omega.earth collect paris --out /tmp/earth-public
python -m products.earth_omega.earth normalize paris /tmp/earth-public --out /tmp/earth-observations.json
```

This downloads **only 100 Paris Belib charging-point records**, not the entire city or all competitors. A real retrieval and normalization passed on November 16, 2026: [receipt](evidence/public-retrieval.json). Import retains producer `date_maj`, not retrieval date, and includes only `En service` records. Charger points are not distinct stations. The snapshot's SHA256 is checked before import; that proves byte consistency, not truth, provenance authentication or completeness.

Montreal collectors are implemented but live downloads returned HTTP403 here. No circumvention or invented data was used:

```sh
python -m products.earth_omega.earth collect chargers --out /tmp/earth-mtl
python -m products.earth_omega.earth normalize chargers /tmp/earth-mtl --observed-at 2026-11-01T00:03:00Z --out /tmp/earth-mtl-observations.json
python -m products.earth_omega.earth collect utilization --out /tmp/earth-use
python -m products.earth_omega.earth normalize utilization /tmp/earth-use --out /tmp/earth-use-observations.json
```

Verify current official metadata before choosing `--observed-at`. The timestamp above is the metadata observed during this build, not a perpetual freshness assertion. Monthly historical utilization is normalized to daily kWh using actual days in the reported month. It remains **historical neighboring utilization**, never a new site's demand forecast. The importer is implemented but live Montreal schema compatibility is unqualified until the endpoint is accessible.

Copy normalized `observations` into a **new** mission JSON. Preserve source/hash/date. Do not replace synthetic economics or constraints with the label “public-snapshot.” Use `operator-supplied` for missions whose location, permissions or economics are supplied by an operator. The evidence-mode label is a disclosure, not a certification.

### Buyer intake and acceptance

Use the example as schema. Every candidate needs:
- Unique ID, longitude/latitude, location source and observation time.
- Evidence-backed `yes`, `no` or `unknown` for site control, permitted use, grid connection and accessibility. Missing/stale facts block eligibility; `no` rejects.
- Declared `demand_group`: potentially cannibalizing sites share a group and cannot both be selected. Cross-group interaction still requires external validation.
- Capital cost, fixed annual cost, unit selling price/variable cost, residual value, discount rate, horizon and **explicit daily-kWh range**. Amounts use the mission currency. Include all applicable tax, lease, grid, maintenance, insurance, finance, failure, decommissioning and customer-acquisition costs. Explicit unpriced costs block eligibility. A required `cost_coverage` object records `included` or `not_applicable` and a nonempty `basis` for installation, grid, land, energy, maintenance, network, insurance, tax, financing, decommissioning and acquisition. Missing declarations block eligibility. These declarations are auditable assertions, not independent proof of completeness.
- Budget means **installation capital allocation**, not full operating liquidity. No borrowing or spending occurs.

The economic screen ranks its supplied candidate set. The separate discovery command generates leads from public municipal facility inventory; neither obtains property rights nor enumerates all available parcels. An operator-provided scenario is not independently verified demand. Source references can be forged; the verifier does not authenticate documents or substitute for legal/engineering due diligence. No sensitive customer records are necessary for the public example. Keep private data and generated customer reports out of Git.

### Economics and reproducibility

`NPV = -capex + sum((365 × daily_kWh × unit_margin - annual_fixed_cost)/(1+r)^year) + residual/(1+r)^years`.

Downside/upside scenarios are evaluated, not probability-weighted forecasts. Negative unit margins reverse the range correctly. Break-even utilization is calculated only for positive unit margin. Real profit, actual inference/tool/compute billing, investment financing, working-capital timing and correlated demand are not inferred. Unknown costs stay unknown.

An exact finite enumeration chooses the largest sum of positive downside NPVs under the installation budget and one-site-per-demand-group constraint. **No-build is always allowed.** Maximum 20 candidates is this solver's computational safety bound, not a market-size claim. For a larger authorized parcel inventory, replace the exact solver with a qualified integer optimizer and preserve the same constraints; partitioning portfolios naively is not globally optimal.

`verify` regenerates the complete report from the mission and compares canonical JSON. This catches changed results but shares the screening implementation; it is **not an independently implemented verifier or independent reproduction of factual claims**. A separate unit calculation checks the cash-flow formula. Tampered input with a matching newly generated report will pass recomputation; source truth requires separate assurance.

### Is it agentic?

`agent.py` exposes a constrained multi-step investigation controller: inspect candidates, compare a portfolio, then finish with verifier-produced facts. Invalid tools, unknown sites, early completion and model-supplied execution are rejected. The runnable `investigate` CLI uses a clearly labelled deterministic policy, **not AI**.

`HarnessCodexPlanner(service, model)` accepts an existing authenticated repository `bridge.codex.CodexService`. `run(mission, HarnessCodexPlanner(service, selected_account_model))` delegates sequential tool decisions to that service. The service preserves the existing account-selection, model-discovery, consent and sandbox checks; there is no new authentication path, API-key fallback, paid call or automatic Pro entitlement. Its final strict JSON is untrusted and validated by the controller. The model cannot change economic facts or authorize investment.

**Live model-backed operation is not qualified here.** The existing native sandbox preflight returned `CODEX_SANDBOX_UNAVAILABLE` before any inference or real credential use. Repair/qualify that shared dependency, connect the authorized account using the existing HARNESS workflow, select an actually available model, then run a fresh end-to-end rehearsal. Contract tests with a fake service are not live model tests. This draft is useful screening software, not yet the promised fully autonomous commercially validated discovery business.

### Public data and licensing

- [Paris Belib static data](https://opendata.paris.fr/explore/dataset/belib-points-de-recharge-pour-vehicules-electriques-donnees-statiques/): Ville de Paris / Belib. Official API metadata verified Open Database License (ODbL). No complete raw dataset is redistributed by this draft.
- [Montreal charger metadata](https://donnees.artm.quebec/catalogue/dataset/bornes-recharge-publiques): Ville de Montréal, CC BY 4.0. Approximate public municipal locations, incomplete market coverage.
- [Montreal utilization metadata](https://donnees.artm.quebec/catalogue/dataset/utilisation-bornes-recharge-publique-voiture-electrique): Ville de Montréal, CC BY 4.0. Monthly aggregate public charger use, potentially stale.

Fixed reviewed HTTPS endpoints, redirect refusal and a 32MiB response bound prevent arbitrary URL execution/SSRF in this collector. No model-provided URLs are fetched. Public endpoint reliability/rate limits remain external dependencies. No demand claim, price recommendation, sale, lease, planning application or customer outreach is authorized by a run.

### Next decisive product test

Preregister a consenting operator's candidate cohort and strongest existing GIS/engineering selection baseline. Blind evaluation should measure accepted feasible site discoveries, due-diligence hours saved, false positives, grid/lease accuracy, full acquisition/data/inference/support cost and eventual actual project outcomes. Equal information, total resources and non-entry options for both arms. Stop promotion when claimed gains fail. No benchmark or customer sales are presently established.
