# Retroactive Sensor Lab · first construction and qualification protocol

**Status:** executable, developer-authored local browser research prototype. Not proof of autonomous discovery, historical physical measurement, buyer demand, profitability, or uniquely new technology.

## The consequence worth opening

A buyer has a consequential historical question for which no single existing measurement series matches the precise definition. Separate archives may contain sufficient underlying observations to construct a *new derived indicator*, with missing evidence kept explicit. The immediate technical object is not another dashboard: it is an on-demand, question-defined **measurement contract** that includes a derivation, source lineage, disagreement policy, uncertainty accounting, and reproducible artifact.

Example: “At which archived timestamps did temperature ≥ 32 °C coincide with relative humidity ≥ 70%?” Existing sensors collected those inputs independently. The result is **not** a reconstructed unrecorded observation, a physiological heat-exposure index, an indoor climate claim, or an independently authenticated archive.

This first result addresses only exact-UTC co-occurrence for user-provided CSVs and synthetic fixture records. Automated discovery of external sources, instrument design, real buyer negotiation, scientifically valid spatial joins, historical calibration, full catalog search, and commercial settlement are *not* implemented. Where archival records are inadequate, the defensible output is UNKNOWN, not a fabricated time series.

## Three materially different enterprise candidates

| Candidate | Outcome and beneficiary | Binding constraint | Strongest practical alternative | Decisive next test |
| --- | --- | --- | --- | --- |
| **A · Question-defined historical sensors** | Audit-ready bespoke historical event, property or operational indicators for authorized diligence, underwriting or research | Observations fragmented across datasets; custom alignment, provenance, semantic validation and uncertainty costly | Existing geospatial data platforms, specialists and analytics suppliers; self-service archive processing | Real archived datasets plus independent expert comparison; determine whether production and complete verification costs undercut best offered equivalent outcome |
| **B · Evidence-native outcome contracts** | Buyers pay for independently verified, previously uneconomic assurance rather than opaque generated work | Ex-post validation, adjudication, and asymmetric information make small deals uneconomic | Conventional managed service and existing assurance platforms | Complete proof-bound production, adverse claims, adjudication and an actual voluntary purchase at positive complete-cost return |
| **C · Autonomous coordination markets** | Enable mutually advantageous productive transactions across multiple firms, suppliers and specialized operators | Search, multi-party matching, contracting, trust and contingent capital need bespoke negotiation | Existing brokers, procurement exchanges, partners or direct contracting | Independent participant consent and outside-option checks, qualified order and obligation-safe settlement |

**Initial selection: A, for the construction experiment**, because a useful artifact and an independently inspectable failure mode can be built with no external authority or paid services. This is a selection for a small first *experiment*, not a finding that A has the highest expected long-term profit or even that a new market exists. Opportunity selection must be reopened with independently sourced demand, complete costs, strength of alternatives and strategic responses. Do not lock the firm to historical sensors.

## Market evidence and existing alternatives

This is not a claim to have invented historical analytics as a category. [Google Earth Engine](https://earthengine.google.com/) already supports large historical archives and commercial analysis; [Planet Analytics](https://account.planet.com/products/satellite-imagery-analysis/) already offers on-demand and retrospective geospatial analytics; [NASA Harmonized Landsat/Sentinel-2](https://hls.gsfc.nasa.gov/data-access-and-tools/) offers established archived analytical products. Those are serious incumbent alternatives, not assumed deficient competitors. The differentiator to test is low-cost **question-specific, source-inspectable and uncertainty-preserving measurement contracts** with complete outcome assurance and voluntary commercial participation. Independent buyer demand and complete cost advantage remain unknown.

## Playable technical experiment

Public site: [Retroactive Sensor Lab](../research/sensor-lab.html). Pure local calculation: [sensor-engine.mjs](../research/sensor-engine.mjs). Tests: [sensor-engine Node tests](../../tests/test_sensor_engine.mjs).

1. Read two UTC timestamp/value CSV archives supplied by the user. The embedded fixture is deliberately fabricated and clearly labeled.
2. Define a question by setting two independent thresholds.
3. Perform exact timestamp joins, without invented interpolation or unsafe source conflation. Reject malformed inputs; mark gaps, duplicates and invalid values UNKNOWN.
4. Reconstruct per-day counts of satisfied, not-satisfied and unknown observations, not an unsupported causal or physical metric.
5. Export the derived series and evidence JSON with original row references and SHA-256 input fingerprints. Cryptographic hashing links bytes; it **does not authenticate source truth**.
6. Challenge with missing values, conflicting duplicates, changed thresholds and no-common-observation cases. Retain the failed/unknown distinctions.
7. Next: evaluate on independently sourced public archives with timestamp/cadence/unit/timezone, spatial and sensor-quality checks; compare with best existing tool and domain expert under identical acceptance criteria. Acquire external rights and data only with proper authorization.

The browser prototype is deterministic and local-only. Do not misrepresent it as an autonomous data-hunting agent, independent physical sensor, measured research novelty, or real commercial transaction.

Run focused tests from the repository root:

```sh
node --test tests/test_sensor_engine.mjs
python3 -m unittest discover -s tests -p 'test_research_site.py' -v
python3 scripts/build_research_site.py --output /tmp/agi-alpha-sensor-site-FRESH
```

The GitHub Pages build must remain explicitly allowlisted: no repository export, no private archives, no credentials, no user files or uncontrolled third-party scripts. Updating the page means building, checking and releasing from exact current source with the established CI and deployment boundary. Other repository owners retain their branches and account authority.

## Co-invent the commercial mechanism, not just the algorithm

A viable enterprise may need data licensors, source owners, metric designers, independent checkers, underwriting users, financing partners and distribution. Each can refuse. Define clear rights and valid use, buyer acceptance, calibrated dispute resolution, payment and refund terms, provenance, assurance cost and liability before pretending there is a transaction. Non-discriminatory consent, no fraudulent source provenance, and verifiable value matter more than arbitrarily winning orders.

**Conditional game-theoretic decision:** Let \(x=(q,p,c,d)\) choose a measurement definition and coverage \(q\), price \(p\), contract/assurance \(c\) and distribution \(d\). Optimize, within a declared feasible strategy set and current evidence,

\[
x^* \in \operatorname*{argmax}_{x}\;\mathbb E[\text{accepted, collected 365-day profit net of ALL costs and obligations}\mid x,\text{buyer options, rival responses, data rights}]
\]

subject to each participant's voluntary participation relative to its outside option, permissions, acceptance obligations, liquidity, capacity and risk limits. Allow no-bid, simpler competitor, and holding cash as options. A strategic best response is model-dependent, **not a universal Nash-optimal price or proof of demand**. Validate buyer choice with independently sourced offers and calibrated evidence before increasing allocation; never infer sales from a synthetic customer response.

The complete productive arrangement should be revisable: if buyer value is low, choose a different use case; if archival evidence is weak, invent a better sensor or stop; if source rights or checking dominate, change procurement or verification architecture. Do not optimize a small, fixed buyer calendar indefinitely.

## Recursive invention, evidence and the $3B objective

The first derived sensor is only a **capability candidate**. The true successor test asks whether its validated source-join/proof/uncertainty procedure reduces complete construction cost or enables a *different* useful indicator (e.g., an independent machine-performance archive with disparate signals) against an equally informed strong ordinary baseline. Report cost of finding, building, checking, maintaining and transferring the mechanism. Separately test whether an improved generator discovers better sensor constructors on fresh tasks; a developer-written reuse template is not autonomous discovery.

Keep the two flywheels distinct. A commercial system can deliver accepted, collected profitable outcomes with fixed AI capability. An inventive system earns its recursive claim only through actual fresh successor benefit. The research pilot neither operates nor modifies the native commercial ledger.

**Primary simulation objective is unchanged:** exactly **US$100,000** starting simulated capital; **US$3 billion in profit over a registered trailing 365-day window** net of complete modeled costs at the fixed native observer, with full obligation protection, source-frozen accounting, rival response and no capital resets or annualization shortcuts. US$3B is a target, not an achieved profit or universal ceiling. At a hypothetical 50% complete-cost profit margin, it mathematically requires US$6B in *accepted collected* annual sales; actual demand, coverage, pricing, competition, delivery capacity, finance and margins remain unknown. Real-world commercial evidence requires real independently accepted and collected transactions under separate authorization.

The first experiment can be small. The industry ambition cannot be assumed from it.
