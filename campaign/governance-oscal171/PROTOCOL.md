# Governance OSCAL interoperability 171 — prospective engineering protocol

**Source baseline:** qualified main `98202ad3b3ef6bd43d76ed3d056b0cf820c800a0`. Freeze this protocol in Git **before** implementing adapters or tests. Independent additive product-research owner; no edits to canonical Account, financial PR40, release code, original accounts, keys, or live governance systems. No spending, partner contact, applications, new external credentials, paid APIs, private data or deployment.

## Actual problem, existing mechanisms and alternatives

Shared Services Canada's public AI governance challenge (opened 2026-10-30; closes 2026-12-22 14:00 ET) requires standards-based interoperable exchange and continuous reassessment of registered AI systems. The source is https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance . The existing merged `products/governance_impact140/engine.py` already computes conservative pending impact and external-anchor integrity, with risk152/reassessment153/drift159 supplementary synthetic components; **do not duplicate or replace them**. NIST OSCAL control catalogs document `catalog`, `metadata`, recursive `groups` and `controls`: https://pages.nist.gov/OSCAL-Reference/models/v1.2.1/catalog/json-reference/ . This prototype is a **narrow explicit-subset adapter**, not full OSCAL schema validation or federal legal interpretation.

Compare (A) incumbent human specialist plus conventional inventory/script, (B) established governance platform/integrator capable of OSCAL and full lifecycle, (C) scoped content-addressed import to unchanged impact140 with explicit target scope and human verification, and (D) NO BID / NO DEPLOY. C may show engineering interoperability, not an advantage over A/B, buyer commitment, TRL5-9, compliant federal system, supplier eligibility or profit.

## Precommitted contract

Add `research/governance_oscal171.py`, fixed tests `tests/test_governance_oscal171.py`, this protocol, operator note and standard GitHub-hosted CI. The input is two OSCAL-shaped catalogs (before/after), explicit registered systems and separately assigned control scopes per stage, plus untrusted evidence. Every catalog control must be accounted for explicitly in the corresponding scope map; no auto-generated applicability from title, group or assumed law. Accept nested groups and child controls. Capture complete source-control canonical digest (including unrecognized OSCAL fields) and contextual ancestor group content; distinguish changed, added and retired controls. Keep original control IDs and catalog version/UUID as source metadata. Pass **only** a fresh, source-bound native input to unchanged `impact140.assess` and return its unchanged findings, never mint approvals. Strict reject of duplicate control IDs, unknown or missing scope, malformed catalogs, duplicate JSON keys and nonfinite values. No source-side mutation or identity reset.

### Fixed adversarial cases (one development/confirmation, no seed selection)

1. A two-control nested catalog with two explicit system tags produces identical native findings to direct competent conversion; every control ID is accounted for; nonapplicable system remains unaffected.
2. A control statement changes **without changing declared OSCAL metadata version**; its content-addressed control revision changes and old evidence never authorizes it.
3. Adding and retiring a control affects precisely scoped systems, preserving retired history and quarantine of cross-scope evidence.
4. Unknown/unassigned scope, duplicate IDs across nested groups, ambiguous/applicability assignments and unknown systems fail closed, not silently skipped.
5. A nested group's changed semantic context changes a descendant control revision; unrelated control remains stable.
6. The result is deterministic for identical ordered source; original inputs not mutated; independent SHA256 source anchors are required and altered catalog content is rejected.
7. Strict CLI JSON refuses duplicate keys, nonfinite numbers, same input/output, existing output; emits create-only, bounded public synthetic report.
8. Source-bound unchanged impact140 regressions and no review authorization; no account/payment/revenue action.

**Stop rule:** one fixed synthetic engineering comparison and bounded local plus source-matched hosted runs. Record original failures immutably, repair source rather than relaxing preregistered criteria. If C ties competent direct conversion, report a tie and leave NO BID. New integration/release only after normal reviewed qualification; current work does not move actual source/account custody. Commercial full costs, real buyer evidence, eligibility, verified enterprise adapters, RBAC, on-prem residency, model/host billing and US$3B T365 remain unknown/unachieved.
