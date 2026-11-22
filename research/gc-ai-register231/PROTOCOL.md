# GC-AI-REGISTER231 — frozen public-source transparency experiment

**Preregistered November 21, 2026 before implementation**; base main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. No native-finance/runtime mutations, customer contact, bidding, spending, transactions or production use.

## Public need and consequential possibility

Canada published its AI Register consultation *What We Heard* on **November 18, 2026**. Respondents report that ambiguous blank cells, inconsistent terminology, weak CSV navigation and lack of a data dictionary obstruct sound public interpretation. Test a reproducible, small **public-disclosure boundary receipt** that distinguishes what a public register actually discloses from what it cannot substantiate. This is a proposed useful result, not a demonstrated beneficiary or legal-compliance advantage.

Primary sources:
- https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/advancing-ai/progress/consultations-government-canada-ai-register-what-we-heard.html
- https://open.canada.ca/data/dataset/fcbc0200-79ba-4fa4-94a6-00e32facea6b
- https://open.canada.ca/data/dataset/fcbc0200-79ba-4fa4-94a6-00e32facea6b/resource/369f6f34-148a-42ed-b581-8c164e941a89/download/gc-ai-register-mvp-registre-de-lia-du-gc-pmv-04-26.csv

## Four arrangements and strongest executable control

A: a fully capable spreadsheet or competent standard-library CSV/pandas script, freely filtering, searching and exporting (strong local control, can tie/win).
B: a commercial governance suite/human analytical service (no purchasing; actual price/integration unknown).
C: the proposed reproducible disclosure-boundary receipt with independent ordinary-script parity.
D: no construction; await the Canadian government's updated register.

## Frozen experiment and stopping rule

**One** attempted HTTP GET of the exact official CSV (no favorable-source switch, no retries) and **one** full-dataset pass. On 403 or other refusal preserve failure unchanged: fixture success is not official-register success. Do not weaken this rule to obtain a pass.

Produce raw-byte SHA-256, byte count, exact header and complete data-row counts, per-column nonblank/blank/declared literal `unknown`/`N/A` counts, duplicate exact-row signals, and a compact output with source identity. Never publish the original bulk data or infer official missingness from incomplete transfer.

Blank is `BLANK_OR_UNSPECIFIED`, not inapplicable, low-risk, no harm or compliant. A missing field is `SCHEMA_FIELD_ABSENT` globally, not an inference about any system. Literal unknown/NA are *source tokens* and not proven semantics. Unknown codebook means no inference about actual impact, legality, disclosure duties, non-compliance, scope, entities, duplicate real systems or data quality outside structural observables. Do not reclassify system names or estimate risk.

The parser must reject malformed records, duplicate headers, invalid UTF-8 and expected-source digest mismatches. Duplicate rows are flagged, not erased. Source CSV reader and **independent** plain `csv.reader` complete-denominator counts must agree. Test at least twelve frozen adversarial cases including BOM, Unicode, multiline quoted cell, duplicate headings, empty and missing cells, exact duplicates, literal NA, bad row widths, digest mismatch, no invented risk, and deterministic repeated execution. Receipt files are create-only; no private data.

Register CPU and wall time where supported; real enterprise/host/model costs remain unknown. No buyer/payment claims. A distinct successor test would reuse this mechanism on another authorized public dataset with matched strongest conventional tools and independently useful decisions, counting transfer costs. That causal successor and improved inventor remain unestablished. The US$3B complete-cost trailing-365 profit target remains unachieved. **HOLD / NO BID / NO DEPLOY.**
