# Accessibility127 — source-first public procurement evidence (research only)

**Verdict: HOLD / NO BID / NO DEPLOY.** This is a small, independently checkable, local semantic-HTML *research fact sheet*, **not** an accessibility-remediation service, an issuer-authenticated tender extract, WCAG certificate, contract, earned business or Blue Sky flagship. Its finding: evidence-grading and provenance are achievable technically without inventing tender budgets, but real PDF content, buyer rights, complete specialist comparison and actual demand remain absent. Source-first publication is one candidate productive means; commercial value is unproven.

## Why this problem exists, and strong alternatives

The **official City of Vaughan RFP26-214** page reports a 60-month accessibility-remediation procurement, awarded 2026-09-15. The displayed **CAD $40** is for **downloading documents**, not contract value. A **third-party Toronto** notice posted 2026-11-04 describes document accessibility remediation; its estimated $25k–$100k is **not an issuer-confirmed contract budget** and the original SAP Ariba specs/deadline are unverified here. A historical **secondary OSFI award report** lists CAD $39,312.89, which is not a per-document rate, an offer to us or revenue. All three sources and their evidence grades are pinned in `PUBLIC_FACTS.json` and the preregistered [protocol](PROTOCOL.md).

Four arrangements were screened before implementation: (A) one-off specialist PDF remediation; (B) authoring approved structured content then publishing semantic HTML to prevent some retrofit needs; (C) continuing release-integrated accessibility assurance with competent manual review/repair; (D) **no bid/no deployment**. Our minimal B instrument is not a replacement for A. An unrestricted competent specialist with conventional tools, existing providers, automated checkers, and no purchase remain allowed. Cost parity, unmet need, reachable buyers, eligibility, consent, source rights, correction/support capacity and receipts all remain unknown; D therefore wins the **current entry decision**.

## Run an offline research reproduction

No extra dependencies, keys, network or paid compute are needed. From the repository root:

```sh
python -m unittest discover -s tests -p 'test_accessibility127.py' -v
python -m research.accessibility127 --input campaign/accessibility127/PUBLIC_FACTS.json --output /tmp/accessibility127-new
python -m research.verify_accessibility127 --input campaign/accessibility127/PUBLIC_FACTS.json --html /tmp/accessibility127-new/fact_sheet.html --manifest /tmp/accessibility127-new/MANIFEST.json
```

The generator refuses malformed/duplicated source records, unsupported provenance grades, unsafe URLs and invented tender budgets. It HTML-escapes source text and writes `fact_sheet.html` with an input/output SHA-256 manifest. A separately authored offline parser independently verifies field-for-field source data, table structure, source links, manifest identities and overt false statements. Rehashing a tampered HTML byte stream alone does not bypass the field-by-field checks. This checks **semantic markup properties**, NOT actual assistive-technology user acceptance, WCAG 2.1 AA, accessibility of original PDFs or official issuer authenticity. This is manually transcribed public data.

## Execution and immutable failures

Before code, protocol freeze commit: `09f8e7049912a64f8b4b7c34eb6759a669603b9d`. Local first targeted attempt on prototype: 9 pass/1 fail (**test fixture tried to mutate a nonexistent substring, so it did not test tampering**). The first corrected mutation selection also failed 9 pass/1 fail because its replacement substring was still absent. Both are **failed attempts**, not retrospectively passes. The corrected explicit `assertNotEqual(original, modified)` makes the negative tampering case effective. Final local Python standard-library suite: **10/10 passed**; generator and independent verifier both returned exit 0, `accepted: true`, 3 records. The original local failures are not source-product failure evidence or success claims. **Hosted exact-head qualification and PR review are separate gates**.

Frozen input SHA-256: `51831e6fbe86019d018ce4e8b21a66be4b225961e276fc56a2ff38c0674d8fdf`. Local HTML payload SHA-256: `e18d396ba849ad8676dcf3c39bcc6790817012231af3a3364b9bb255c3d8885a`. These are **local reproducibility receipts**, not yet an independent hosted/actual-release byte qualification.

## Financial and commercial boundary

This work does **not** touch `Account`, `JournalAccount`, an original native account, financial signer, lease, writer, queue, private data, existing P0/PR40 source, release guards, historical failures, purchases, bids or production. No test is a buyer, sale, collected revenue, complete-cost profit, recurring subscription or earned reinvestment. The US$3B trailing-365 complete-cost profit objective is **unqualified**. Do not merge wholesale as a financial runtime or declare a new Blue Sky invention. The next meaningful acceptance requires rights-cleared *real* tender/PDF inputs and independently verified output with full specialist/human+software competitive quality, cost and capacity; current account custody and no-bid policy remain binding.
