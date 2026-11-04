# ActiveTender096 fixed-failure source diagnostic — prospective protocol

**Frozen before diagnostic implementation.** This is an independent source-only review stacked on PR #225 head `110fdbf8d8c171cca394f431e725690ff05bb1b6`. Do not modify its registered first live experiment, exact denominator (5 selected, 4 parsed, 1 failed), all historical CI failures, financial accounts, operators, keys, historical source or tender classification. The historical `ocds-h6vhtk-0692e8` failure remains `MALFORMED_SOURCE_JSON` with no retained raw source. A new response cannot establish what the historical bytes contained.

## Narrow diagnostic and stop

Make **exactly one** fresh, read-only official HTTPS GET to `https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/ocds-h6vhtk-0692e8`. This is the *same previously failed process*, not another selected lead. No query search, no substitution, no retries, no other record. Maximum 3 MiB, read timeout 25 seconds, strict expected URL, no cross-host redirects. Use a standard public GitHub Actions runner, pinned existing actions, recorded start, 360-minute platform window; actual code should finish quickly.

Retain only a compact JSON diagnostic receipt, including capture timestamp, HTTP status/content type if observed, returned byte count, SHA256, JSON first nonwhitespace token class, strict UTF-8 and JSON parsing diagnostic (error line/column/reason), duplicate-key and nonfinite checking, licence/schema status if possible. Do **not** retain or publish the raw body, contact details, notice attachments, private data, credentials or recovery material. A hash is not a retained-byte witness. Do not infer the historical response's cause or retroactively repair its failure. Declare response retrieval failure as diagnostic failure.

## Acceptance and competing explanations

Precommit a local synthetic test matrix for valid licensed record, invalid JSON, HTML body, duplicate key, invalid UTF-8, oversize, unexpected redirect/host, no replay/substitution, and no bid/financial action. The live source may now differ from the historical source: distinguish malformed upstream body, client/parser compatibility issue, malformed/oversized/redirected transport and unknown from the new observation only. Diagnostic completion is not original experiment completion; no retesting to find a favorable prospect.

Commercial decision stays **NO BID / NO DEPLOY**. Strong procurement platforms/human research/no entry remain valid; buyer willingness, deliverability, competitive price, financing, full costs, native T365 profit, real commerce and invention advantage remain unestablished. Never write canonical financial source/accounts or other owners' PR branches. All original failures remain failed. After the one source diagnostic, either devise a source-compatible prospective correction with independent review or stop this failed generic-tender route. No outreach, purchases, paid APIs, bids or deployment.
