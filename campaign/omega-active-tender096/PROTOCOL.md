# ActiveTender096 — prospective, bounded official buyer-need observation (frozen before implementation)

**Owner/source:** Independent, additive follow-on stacked on PublicNotice095 exact head `5c528a83391e5130d1aa51563ffe08bb5d2dc520`, whose frozen three historical awarded records and all 12 successful CI workflows remain unchanged. No P0 native account, source owner, signer, operating queue, debt, or archive guard is touched. All actions are research-only and may not bid, buy, contact a buyer, or create financial authority.

## Decision and distinguishing test

PublicNotice095's three registered public needs were already awarded, so they are not prospective buyer opportunities. Test whether the **official public Find a Tender OCDS release feed** can provide *currently observable* tender-stage processes, with a genuinely recorded capture timestamp, current-process lifecycle check and explicit uncertainty, without hindsight or purchase. A tender notice is not willingness to buy our service.

Compare (A) competent human procurement team + conventional tools, (B) incumbent automated procurement platforms and their full service, (C) evidence-linked automatic public-need research with human acceptance, (D) no bid/no deployment. Do not invent their prices, expected wins, willingness to pay, or complete costs. Select C only as a technical information experiment; the commercial choice remains D absent eligibility, deliverability, costed advantage and buyer evidence.

## Locked source, denominator, cost and stopping

Official UK Cabinet Office Find a Tender OCDS API under OGL v3:
- Exactly **one** `GET https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?updatedFrom=2026-11-02T00%3A00%3A00&updatedTo=2026-11-04T15%3A00%3A00&stages=tender&limit=20` (fixed UTC filter; one page only, no cursor follow), with a <=3MiB response limit and 25-second read timeout. The publicly documented endpoint is in https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages .
- Parse an OCDS release package with duplicate-key and type rejection. From its <=20 returned releases, extract unique syntactically valid `ocds-h6vhtk-[0-9a-f]{6}` IDs **sorted lexicographically** and choose the first **five**, or all if fewer. No manual selection or substitutions based on favorable opportunities. There is **no promise** of five records or any positive opportunities. Record search-source SHA256, bytes, actual capture time, all observed counts, fixed selection and any errors.
- GET each selected official `/api/1.0/ocdsRecordPackages/{ocid}` **once**, each <=3MiB/25s; record source hash/bytes and retrieval. Stop after at most six GETs. A failure remains a failure, is never replaced by another OCID, and may not be counted as an opportunity. No keys, paid APIs, personal contacts, attachments or raw large archives.
- Source and process timestamps are **not signed**. Only information actually captured by the observation time may be presented; a retrospective publication date cannot prove previous live availability.

## Prospective eligibility is conservative

A public tender release can be a *research signal*, **not** a confirmed active, addressable paying buyer. Require actual capture before decision, at least one dated tender release, a complete public buyer name and title from an eligible tender release, and an explicit correctly parsed `tender.tenderPeriod.endDate` **strictly after** the observation cutoff. Ignore award, supplier/contract, contact-point, notice attachments, detailed estimated value, personal fields and later publication for predecision feature construction. A known award, cancellation, contract, termination, failed expiry, unknown status/deadline, conflicting or incomplete tender amendments, or source inconsistency must yield `NOT_VERIFIED_OPEN` (or fail). Even if all conditions are met, output only `PUBLIC_DEADLINE_IN_FUTURE_UNVERIFIED_ELIGIBILITY`; never `CONFIRMED_BUYER` or bid authority. Supplier eligibility, buyer fit to **our** service, competitors, costs, procurement regime, accessible portal, terms, buyer willingness and signed first-seen evidence remain unknown.

## Prespecified adversarial checks

1. Search selection: deterministic unique sorted first-five process IDs; no preferred-sector filtering/replacements.
2. Duplicate/foreign malformed release, source mutation, unverified licence, nonfinite JSON, invalid dates and oversized inputs fail.
3. Explicit future deadline is only a public notice property; expiration, missing deadline and invalid timezone cannot be promoted.
4. Award/cancellation/termination blocks even when a tender deadline appears future; no award information leaks into predecision features.
5. Conflicting later tender/amendment signals fail closed rather than emitting stale earlier requirements.
6. A later capture cannot support a supposed earlier decision; no backdated buyer signal.
7. No-bid, no-account, no-contact, and no synthetic profit invariants hold for every case.
8. Frozen original PublicNotice095 tests remain passing.

Use only standard public GitHub runner compute, stdlib and existing project dependencies. Charge actual consumed GitHub resources if observable; whole account/host costs unknown. No assumed revenue. Publish compact source/CI hashes, all chosen identifiers, negative cases and the actual verdict.

## Stop and next action

Exactly one fixed search page and up to five record fetches. **Do not resample until a favorable prospect appears.** Failure to find a truly deliverable opportunity is a legitimate registered result and changes this route to REVISE/NO_BID. Neither technical success nor a publicly advertised tender is a voluntary commercial agreement or the US$3 billion trailing-365-day target. To advance further requires a qualified complete offer, verified ability to deliver/serve, competitor parity, actual eligible capital, measurable demand and permissible real market validation (outreach is not authorized).
