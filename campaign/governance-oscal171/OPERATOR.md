# OSCAL171 — scoped interoperable control impact, not a compliance product

**Outcome:** import a deliberately narrow OSCAL-shaped JSON control catalog, including nested groups and child controls, into the **unchanged** `governance_impact140` engine. Explicit before/after scope assignments bind controls to registered AI-system tags; revision identities come from entire control content and ancestor context, not publisher version strings alone. No evidence becomes automatically approved. The CLI creates a read-only engineering report and independently anchored hashes can detect changed source.

**Public sources:** [NIST OSCAL Catalog v1.2.1](https://pages.nist.gov/OSCAL-Reference/models/v1.2.1/catalog/json-reference/) and [Shared Services Canada's October 30, 2026 AI governance challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance), closing December 22, 2026 at 14:00 ET. The challenge calls for standards-based exchange, change impact, ongoing risk assessment and authorized human review. It offers potential Phase 2 contracts capped at CAD2m each, **not** supplier revenue. TRL5–9 and Canadian business eligibility remain unverified.

From the repository root run:

```sh
python3 -B -m unittest tests.test_governance_oscal171 -v
python3 -B -m unittest tests.test_governance_impact140 -v
python3 -O -B -m unittest tests.test_governance_oscal171 -v
python3 -B -m research.governance_oscal171 --input /absolute/synthetic-input.json --output /absolute/new-report.json
```

Input keys: `schema`, `before_catalog`, `after_catalog`, `systems`, `before_scope`, `after_scope`, `evidence`; schema `agi-alpha/oscal-interop171/input-v1`. Each catalog has one `catalog` with canonical `uuid`, `metadata.title`, `metadata.version`, and `controls` and/or `groups`. Each control ID must be explicitly assigned its own scope mapping `{"applies_to":["registered-tag"]}` in both periods. An empty array explicitly means out of scope. Missing and unknown control assignments fail. Inputs and outputs are synthetic/public only.

**Limits:** This is a *subset converter*, not a conformant full OSCAL validator or verified standards-compliant enterprise API. Unrecognized OSCAL control fields are hashed but not semantically interpreted. It does not authenticate publisher, legal policy meaning, reviewer identity, scope assignment, access controls or privacy/data residency. SHA256 alone is not a signature. The unchanged impact140 engine always marks actual compliance pending or indeterminate, not satisfied. No native account, signed transition, live dataset, buyer relationship, deployment, paid API, real contract or actual commercial earnings are involved. Model/host billing and full delivery costs remain unknown.

**Strong comparators:** competent governance specialist with conventional scripts, an established full GRC provider/integrator, this limited adapter atop existing impact140, and NO BID / NO DEPLOY. No established cost, functionality or buyer-acceptance advantage over the complete alternatives. Source-bound fixed tests, original engine regressions and exact-head hosted CI can qualify engineering correctness only. Preserve genuine failures. Do not merge as a flagship, claim a public release or submit an offer absent independent source, commercial, security and eligibility qualifications.

**P0 boundary:** Owner PR #40 retains original Account/JournalAccount and signing/writer authority. No other owner files, historical failures, accounts or financial liabilities are modified. The US$3B trailing-365-day complete-cost profit objective remains unachieved.
