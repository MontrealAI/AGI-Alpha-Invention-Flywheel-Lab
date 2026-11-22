# OSCAL172 — source-anchored applicability-continuity trial (frozen before code)

Registered 2026-11-15 against exact released Git main `75f8f722c923e448d8f1fb44aa762b6ba0cd5a46`. Standalone, additive engineering research. No edit to original financial Account/JournalAccount, transition PR40, keys, queues, release manifest or live customer policy. No new API, spending, outreach, procurement bid, production deployment or compliance authorization.

## Problem and productive means
The merged OSCAL171 adapter parses the official NIST AI RMF catalog but demands explicit applicability for *every* control at each assessment. Re-entering unchanged, independently anchored prior assignments can be avoidable operator effort, while blindly propagating them would risk wrong scope or silent compliance assertions. Construct a **conservative, read-only continuity proposal** that reuses exact prior mappings only when the old/new semantic content and registered system inventory are unchanged, and otherwise refuses automatic scope continuity. This is an ordinary content-addressed data-reuse mechanism, not a new algorithm, a buyer win or a Blue Sky flagship.

## Alternative and falsification contract
Compare (A) competent human + conventional script that rechecks all scope entries, (B) existing GRC/provider scope management, (C) a content-addressed provisional carry-forward proposal with explicit exception queue, and (D) no-deploy. Strong existing software may match C exactly: if so record tie, not advantage. Never invent wages, intervention hours, real adoption or market size. Only explicit synthetic scope assignments are permitted in test fixtures; NIST does not authorize those assignments.

### Exact interface and security boundary
Implement `research/governance_scope172.py` using merged `research.governance_oscal171.extract_catalog`, `explicit_requirements`, and `products.governance_impact140.engine.sha256` without modifying them. Input: original OSCAL catalog, candidate successor OSCAL catalog, exact original and successor registered systems, complete original explicit scope, and **four externally supplied exact SHA-256 anchors** (old catalog, new catalog, old scope and original system inventory). All source anchors must be lower-case 64-hex and recompute exactly. They are integrity checks against externally pinned expectations, not digital signatures or proof of issuer/reviewer identity.

Validate originals through the existing strict importer. Carry a prior mapping as a **provisional proposal** only for the exact same control ID and semantic_sha256 if original systems equal successor systems canonically. Otherwise emit a distinct mandatory review exception for changed, new, or inventory-changed controls. Retired controls are recorded, not silently discarded. Never infer applicability from title, catalog or official source. No output should be treated as an authenticated approval, legal finding, money or real contract. Reject unknown keys, duplicate IDs, malformed/ambiguous/unknown scope tags, changed expected digests, malformed systems, unsupported source structure, or unsupported partial catalogs.

## Frozen T1–T10 acceptance, one finite experiment
1. Two-control synthetic identical catalog/inventory and explicit source-anchored prior scope yield exactly two provisional carries, zero exceptions, zero approval.
2. Same declared publisher version but changed control semantic content causes one review exception and exactly one unchanged provisional carry.
3. Added control requires review, retired control remains listed, never auto-applied.
4. Group-ancestor content change invalidates descendants but leaves unrelated controls eligible.
5. A changed system inventory/tags invalidates **all** scope carries; never reuse across an unregistered target.
6. Altered old/new catalog, scope or inventory against a frozen independent anchor fails closed; an anchor computed from the untrusted report itself is not independent authorization.
7. Missing, unknown, duplicate or malformed explicit scope and noncanonical hashes fail closed; unchanged native impact140 remains the authority for findings.
8. Multiple calls deterministic with unmutated inputs; reports include explicit separate `provisional`, `review_required`, `retired`, source hashes, and no compliance or commercial authorization.
9. Official, independently pinned NIST v1.6.0 AI RMF OSCAL v1.2.3 **91-control** catalog: on a *synthetic tagged system*, identical source yields 91 provisional proposals, while a precisely synthetic single-control content revision yields 90 provisional and 1 review exception. Real official controls and publisher bytes remain unchanged; no real system applicability is asserted.
10. All original OSCAL171 and impact140 regressions pass unchanged on exact head. No native financial or release source modifications.

Freeze inputs, acceptance and the official source: `usnistgov/oscal-content` tag `v1.6.0`, `nist.gov/AI100-1/ver1/json/NIST_AI-RMF_v1_catalog-min.json`, Git blob `1f625a618448cec41f8f7fa8ea50bbaf7751bb82`. Use the same source authenticity limitations as OSCAL171 T9. Full source-matched workflow must upload a compact receipt even on failure. Preserve failed runs and repair without weakening tests. Record source commits, executed work and unknown actual host/model costs.

## Decision
If exact continuity and conservative exceptions pass, retain as a research **proposal generator**, not an automatic approver or a financial operating integration. Procurement eligibility, genuine buyer acceptance, scale, official legal source interpretations, rival advantage, privacy/identity, actual billing and US$3B trailing-365 complete-cost profit remain unqualified. If the ordinary comparator ties, no novelty credit. Future adoption requires accepted full outcome and independent review, normal protected merge/release and independently downloaded bytes.
