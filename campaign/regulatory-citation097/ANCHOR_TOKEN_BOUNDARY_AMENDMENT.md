# Anchor token-boundary correction — prospective source-integrity protocol, 8 November 2026

## Fixed prior evidence and failure

Source before this prospective change: draft PR #300 head `a27aa5d39590098935a565bb207e270b80cf9791`, current main `de9546ef9083f64a25186f1c5163e3a3a4eaeae5`. Preserve original failed global-uniqueness official-source run #42458780446, separately amended A3–A5 and all successful C0–C13/H0–H9 results as historical engineering evidence. Do not relabel, replace public sources, select alternative quotes, change registration, or infer buyer acceptance.

## Problem, independently specified before changing code

The current `bounded_quote` finds section-start and section-stop with unbounded `str.find`, and searches the quotation as a substring. Consequently the registered `SEC-A` may be matched inside `XSEC-A`, `SEC-B` inside `SEC-BETA`, `6.1.1` inside `16.1.1` or `6.1.1.1`, and a registered `Signed control assertion.` inside `preSigned control assertion.`. This can mislabel a quote as located in a registered section even though no complete anchor/quote token exists. This is a new prospective adversarial case; all original passes remain limited to their original criteria.

## Fixed N-series tests (synthetic only; no new official page, seed, account or market)

- N0: start anchor only as `XSEC-A` => refuse.
- N1: stop anchor only as `SEC-BETA` => refuse.
- N2: registered numeric `6.1.1` cannot match `16.1.1` or `6.1.1.1`; a genuine `6.1.1` with ordinary punctuation remains eligible.
- N3: quoted sentence only inside longer adjoining word => refuse.
- N4: intact `SEC-A ... SEC-B`, legitimate earlier cross-reference, and two independent real sections retain original respective accept/accept/refuse semantics.
- N5: quoted passage/registered anchors may have surrounding normal punctuation and whitespace; section starts and stops are token-bounded not global-unique.
- N6: C0–C13 and H0–H9 must still pass unchanged.

Implementation: change only token-window matching in `research/regulatory_citation097.py`, add an isolated N-series test module, update the dedicated workflow to run it. A token begins/ends at a lexical boundary: no immediately adjacent letter, digit, underscore, or continuation consisting of dot/hyphen followed by a letter/digit (in either direction). Preserve the original local-window uniqueness rule and rejection of nested or competing real anchors. Do not weaken other tests, financial authority, source guard, official fetch allowlist or fail-closed source hash.

Stop after one source-matched qualification. Preserve any test/workflow failure; never rerun to select a favorable outcome. An official-source reproduction, if run, is on exposed fixtures, not fresh confirmation. This component remains a source-anchored substring witness, not semantic/legal correctness, complete rendering, digital issuer authenticity, paid demand, qualified release or a commercial service. Financial P0 owner/source/account and existing releases remain untouched. Decision remains NO BID / NO DEPLOY.