# Public-demand 140 — frozen construction and qualification protocol

**Freeze:** 2026-11-12 UTC, before implementation. **Base:** `b0435293d767304b836e4d16624a27b138ecb52f`. **Owner:** isolated synthetic, offline commercial-prototype workstream; not financial PR #40, HARNESS PR #344, or design search PR #77. **Permissions:** code/tests/metadata only; no proposals, submissions, customer contact, spending, payments, live data, new credentials or deployment.

## Real public opportunity, carefully scoped

Primary government statement: https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance

Shared Services Canada's challenge opened **30 Oct 2026**, closes **22 Dec 2026 at 14:00 ET**, and asks for continuous AI-governance requirement alignment, impacted-system reassessment, traceable controls/evidence, interoperable exchange and independent authorized review. The challenge says **one or two possible** Phase 2 prototype contracts, **CAD 2M maximum each** over up to 20 months. It expressly does **not** promise a contract. Phase 2 entry requires **TRL 5–9 and eligibility**. This repository does not establish that its product satisfies either condition. Any third-party estimate is not accepted as an actual award or price.

This is an **observable public statement of procurement need**, not actual buyer assent to this supplier, actual revenue, a partner agreement, eligible TRL, a winning offer, market size, or a positive net margin. CanadaBuys solicitation controls if it conflicts with this program page; no actual submission is permitted.

## Joint complete-arrangement choices; no outcome manufactured

1. **Human specialist + spreadsheet/rules:** conventional software and expert judgment, explicit labor, change monitoring, review, security and maintenance; potentially strongest for a small system inventory.
2. **Established enterprise GRC software + integrator:** credible incumbent automation/interoperability and professional governance assurance; licensing and integration prices not yet sourced, never set to zero.
3. **Offline content-addressed change-impact instrument + authorized reviewer:** construct the *missing coupling* from new/modified/retired requirements to system-control evidence impact and an exportable unresolved decision list. Human approval remains external and explicit. No assumption of cheaper end-to-end fulfillment.
4. **No-deploy:** zero new sale, conserves resources; preferred if no qualified TRL, rights, funding, acceptance or superior complete-cost case.

The purpose of this finite step is a **working, falsifiable subsystem**, not selection of a commercial winning arm. Full-offer eligibility, interoperability, audit authority, privacy and complete-cost costed comparators remain outstanding. One public tender cannot scale to the US$3B T365 milestone by itself.

## Frozen synthetic test contract (all cases, no cherry-picking)

The candidate is a standard-library, no-key, offline Python CLI taking JSON for registered systems, requirements and evidence. Its output must deterministically distinguish impacted and unaffected systems with policy-version provenance. It must:
- T1: fail closed on duplicate identifiers, invalid structure, invalid evidence status and unknown requirement references;
- T2: on a newly added applicable requirement, emit `unable_to_determine` until valid independently approved evidence is supplied;
- T3: on changing a requirement version, invalidate prior-version evidence rather than silently treating it as current;
- T4: retain pre-change requirement/evidence identities in a transparent `change`/provenance receipt and mark retirement `not_applicable`, never pretend to erase historical obligations;
- T5: leave unrelated system/control results unaffected by an inapplicable change;
- T6: treat supplied self-asserted `passed` and `approved` fields as *unverified claims*; require explicit signed external reviewer verification in a future authority integration (not constructed here). Present a status of `pending_review`, never self-approve or issue a compliance certificate;
- T7: independent, exact-input deterministic output/hash and tamper-detection by recomputed hash only; never call this a cryptographic signature or trust anchor;
- T8: modifications to one system's evidence cannot silently satisfy another system, and unknown rule IDs reject;
- T9: adversarial empty/invalid input and case-mismatched versions fail closed without claiming success.

**Fixed stopping rule:** run all T1–T9 once on the frozen authored samples and a competent direct conventional inspection of each expected finding. Preserve every failure. If any test fails, correct source only without changing this contract; do not pretend synthetic correctness establishes commercial differentiation. Zero authenticated account actions; no transfers/investments. Measure local resource telemetry and retain unknown actual model/host billing as unknown.

## Required proof tiers

- **Engineering:** source-bound deterministic tests, negative cases and CLI output; exact commit/hash and explicit coverage gaps.
- **Independent product acceptance:** not achieved until externally authorized reviewers validate real system requirements, privacy/security/data residency, official change feeds, permissions and the complete tender outcomes.
- **Commercial:** no supplier qualification, proposal, buyer consent, recurring demand, awards, paid receipts, revenue, T365 profit or causal successor claim from this pilot.
- **Financial:** no new operating/native account or capital authorization; original canonical JournalAccount, its signer and liabilities remain the sole authoritative financial boundary.

Do not merge into native finance or HARNESS without scoped owner review and complete release qualification. Reassess adverse costs, conventional GRC capability, failure regions and no-deploy before any expansion.