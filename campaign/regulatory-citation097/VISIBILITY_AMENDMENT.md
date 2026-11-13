# Visibility097 — prospective adversarial correction protocol (8 November 2026)

## Frozen source, before implementation
Parent is draft PR #300 head `927c4d7f1578b9b6abfb415ebbcff54792046caa` from unchanged main `de9546ef9083f64a25186f1c5163e3a3a4eaeae5`. This is an additive correction of an **independently demonstrated failing claim**: the exact current `VisibleHTML` accepts a quote between the registered anchors even when the *only* occurrence is inside `<div hidden>`, `<div aria-hidden="true">` or `<div style="display:none">`. Current C7 tests only script/style tags; original passed results cannot be upgraded to generic browser-visibility proof. See PR #300 issuecomment-6719196086. Original A0–A2 first strict-window run FAILED and its later A3–A5 prospective official-page test PASSED *only under the previous extractor*; preserve both verdicts unchanged.

## Test-first H-series, fixed before changes
New synthetic fixtures, same fixed public-document id/URL and anchored quote, no new seed/source/buyer:
- H0: only occurrence in `hidden` Boolean attribute => quote refused.
- H1: only occurrence in `aria-hidden="true"`, with whitespace/case variation => refused. `aria-hidden` is accessibility metadata, **not** a full rendered-visibility determination.
- H2: only occurrence in inline `display:none` with varied case/spacing/`!important` => refused.
- H3: only occurrence in `visibility:hidden` or `visibility:collapse` => refused.
- H4: nested descendants of suppressed container, including interleaved benign descendants, => refused; correctly closed container followed by genuinely exposed same quote => accepted.
- H5: benign visible siblings, `aria-hidden="false"`, normal inline `display:block`, void tags/self-closing tags do not suppress unrelated quotes.
- H6: unsupported or ambiguous inline values for `display` / `visibility` (including `var(...)` and CSS comments) fail **closed for that element**, not silently treated as shown.
- H7: C0–C13 replay identically, including script/style/noscript/template SVG suppression, source swap, anchor ambiguity, deterministic packet replay.
- H8: all original two live URLs and three exact public excerpts may be replayed only as clearly labeled *engineering reproduction* under a different extractor, never as first preregistered public-source confirmation; no changed source texts, quotes, boundaries or selection.
- H9: no false claim of full browser visibility, external stylesheet/class/JavaScript-rendered visibility, issuer signature, legal compliance, paid buyer, comparison superiority or source-to-commerce readiness.

## Implementation/qualification and limits
Implement stack-aware ancestor suppression using only standard-library HTMLParser; handle HTML void/self-closing tags and nested suppression. Prefer conservative rejection of unsupported inline visibility expressions to permissive extraction. Maintain exact raw-byte SHA256, allowlisted HTTPS, fetch budget and C0–C13 unchanged. Record negative fixtures and existing failure receipts. Synthetic H-series + full C-series pass required before claiming *limited explicit-attribute/inline-style filtering*. Hosted exact-head CI, official source reproduction and applicable repository workflows must be reviewed separately. A browser HTML/CSS cascade implementation is **out of scope**; external CSS, dynamic DOM, layout and accessibility are not generally verified. A competent browser/specialist remains a stronger complete baseline. If actual source stops matching, preserve failure and do not sample until favorable.

Nothing here authorizes changes to financial Account/JournalAccount, signer, liabilities, signed operating queues, P0 owner, existing release, payment, real customers, outreach or production. Draft/no bid/no deploy. US$3B trailing365 profit unqualified.
