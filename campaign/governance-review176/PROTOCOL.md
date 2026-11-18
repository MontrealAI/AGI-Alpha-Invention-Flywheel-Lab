# Governance176 — preregistered independent reviewer-attestation boundary

**Frozen 2026-11-18 before implementation.** Source base: `172ea7a9b96ad123a879dde76101b944aa9cf131`. Separate additive review challenger: do not modify `products/governance_impact140`, the existing OSCAL/risk adapters, native Account/JournalAccount, original capital owner, live credentials or production policy. Simulation-only public engineering; no spending, contact, real customer data, submission, or deployment.

## Why build this missing productive means

[Shared Services Canada's official AI-governance challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance) (opened 2026-10-30, closes 2026-12-22 14:00 ET) explicitly asks that assurance artefacts be attributable to **authorized** individuals and that authorized reviewers validate, reject, modify or annotate findings with retained decisions. The current offline Impact140 findings intentionally remain unauthenticated. This bounded prototype tests whether an independently held, scoped verification key can establish **cryptographic provenance of a reviewer action** on an exact existing finding; it does not establish a person's real identity or legal authority, TRL5–9, actual compliance, tender responsiveness, commercial advantage, or US$3B profit.

## Strong complete alternatives, still eligible

1. Competent governance reviewers with conventional signed PDF, spreadsheet, version control and controlled identity systems.
2. Established enterprise GRC suites with SSO/RBAC, policy/version governance, audit history, controls, reviewer sign-off and accredited integrators.
3. The new offline Ed25519 receipt-bound verifier (a narrow portable component), with an *externally anchored and administrator-controlled* reviewer trust list.
4. No-bid/no-deploy. **Default commercial decision remains NO BID / NO DEPLOY** pending full authorized identity, immutable audit history, data security, native risk, full mandatory functionality, eligibility and complete cost/beneficiary proof.

No price for an incumbent, buyer assent, actual authorization or revenue may be inferred. Signature verification is standard cryptography, not an invention claim.

## Frozen functionality and adversarial cases

Source: the unchanged `products.governance_impact140.engine.verify_receipt` with separately supplied expected input and receipt digests. A review action must bind tenant/organization, system, requirement ID/version, evidence ID, source hashes, decision, unique decision ID and validity period. The key authority comes **only from a separately supplied, explicitly anchored trust record**; no key, role or revocation from the signed record may expand authority. The key is Ed25519 and signature verification must use a real external crypto implementation, not equality to a claimed digest. Review results are provenance-only, **never a compliance certificate or alteration of the source finding**.

All the following must be executed once, preserving failures, with no seed/sample reselection:

- T01: genuine externally scoped signature on an existing current evidence finding verifies and yields an action-provenance receipt, leaving the original finding unchanged;
- T02: changed signature or signed decision, source digest, receipt content or externally anchored trust digest rejects;
- T03: wrong tenant, system, requirement ID/version or evidence identity rejects despite a mathematically valid signature;
- T04: unknown, revoked or wrong-role reviewer and untrusted/replaced public key reject;
- T05: expired, future-issued, reversed or otherwise invalid time windows reject at the trusted evaluation instant;
- T06: duplicate action IDs and signatures, or multiple decisions on one current finding in the same batch, reject; state clearly that cross-run replay requires a separate durable externally governed history;
- T07: retired/out-of-scope/quarantined/unresolved findings and self-asserted 'approved' text cannot become a verified acceptance;
- T08: malformed structures, duplicate JSON keys, invalid base64, non-Ed25519 keys and unsupported decision verbs reject;
- T09: two independent reviewer keys with disjoint scopes do not authorize each other's findings;
- T10: valid negative/reject decision still retains original claim state and has no automated side effect;
- T11: deterministic, independently recomputed output includes full decision IDs, source and trust hashes without secrets; no undisclosed keys/accounts;
- T12: clean standard `ubuntu-latest` hosted run executes unmodified tests and an actual CLI example, no paid APIs/new credentials or larger runners.

**Stop:** Do not claim physical identity, a production RBAC platform, tamper-proof storage, non-repudiation, legally valid approvals, live independent buyers, commercially winning bid, or release completion. The trust record and clock must be supplied by a credible external operator in any eventual real deployment. The prototype does not implement a persistent append-only replay registry, key lifecycle, on-prem deployment, privacy, residency or bid submission. Publish source, tests, scoped CI and source-bound results on a draft PR; normal owner review and protected release qualification remain necessary.
