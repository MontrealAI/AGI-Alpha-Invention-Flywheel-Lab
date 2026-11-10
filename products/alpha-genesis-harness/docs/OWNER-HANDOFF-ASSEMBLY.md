# Owner handoff assembler

This maintainer tool assembles Vincent's review bundle after the final source-specific GitHub prerelease is published and its downloaded customer archive has been operated successfully. It does not publish, rebuild the customer ZIP, access Squarespace, or save anything to Library. The output always describes the edition as a candidate and keeps commercial readiness false.

## Inputs

| Input | Required evidence |
|---|---|
| `--source-sha` | Full final 40-character source commit, independently checked against the published tag |
| `--release-url` | Actual `https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/alpha-genesis-harness-vVERSION-rc-SOURCEPREFIX` URL |
| `--asset-dir` | Downloaded release assets: exact customer ZIP, checksum, actual screenshots and associated browser/platform receipts |
| `--operation-receipt` | `QUALIFICATION.json` from **harness-published-operation**, not the initial build or prepublication check; its `operation-N.stdout.txt` and `.stderr.txt` logs should be alongside it |
| `--output` | New staging directory; existing named bundles are never overwritten |
| `--expected-sha256` | Recommended independently verified whole-ZIP digest; otherwise the selected matching operation receipt supplies it |
| `--matrix` | Optional latest owner matrix. An override must explicitly identify the exact final `source_revision`. Otherwise the immutable packaged matrix is preserved. |
| `--screenshots-dir` | Optional separate directory of actual screenshots with their corresponding receipts |
| `--pull-request-url` | Optional public PR URL for the authorized repository |

The assembler does not authenticate GitHub or retrieve a URL. The operator must first verify the release/tag source, download origin and selected receipt. The offline checks establish agreement between those supplied identities and the bytes; they do not turn an invented receipt into external proof.

## Run after final publication

Run from the product directory. Replace every uppercase placeholder with the actual final value. Do not use initial qualification sample assets as final inputs.

```sh
python3 scripts/owner_handoff.py \
  --source-sha FULL_FINAL_SOURCE_SHA \
  --release-url https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/alpha-genesis-harness-v0.3.0-rc-SOURCEPREFIX \
  --asset-dir /absolute/final-downloaded-assets \
  --expected-sha256 EXACT_CUSTOMER_ZIP_SHA256 \
  --operation-receipt /absolute/harness-published-operation/QUALIFICATION.json \
  --matrix /absolute/final-source-bound-owner-matrix.json \
  --pull-request-url https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/324 \
  --output /absolute/new-owner-handoff-output
```

If more than one customer source-bound ZIP exists in the asset directory, select the exact one with `--customer-zip /absolute/file.zip`. A working-tree candidate archive is refused even though a committed customer prerelease remains a commercial candidate.

## Output

The result JSON identifies the review directory, deterministic owner ZIP, owner ZIP digest, exact customer digest, included deliverable count and published-operation status. The owner ZIP and checksum sit beside the review directory.

| Path in the owner bundle | Purpose |
|---|---|
| `00-OWNER-START.html` | Polished bilingual review entry point, exact identity, all 22 requested deliverable categories, receipt-derived counts, actual platform scope, screenshots and remaining dependencies |
| `01-CUSTOMER-DOWNLOAD/` | Untouched published customer ZIP and its SHA-256; this is the only potential storefront upload |
| `02-EXPLORE-THE-EDITION/` | Full byte-verified expanded edition for convenient review, including all examples and source evidence |
| `03-MANUAL-UPLOAD/` | Bilingual listing, separated English/French descriptions, field map, manual owner checklist and prepared ChatGPT approval materials |
| `04-SCREENSHOTS/` | Actual supplied screenshots, including OS-prefixed images |
| `05-VERIFICATION/` | Original operation/browser/platform receipts, operation logs, preserved matrix and parsed summaries |
| `OWNER-HANDOFF.json` | Machine-readable identity, deliverables, source/receipt associations, platform scopes and unresolved criteria |
| `OWNER-FILE-MANIFEST.json` | Hash and byte count for every handoff file except this manifest itself |

Open the HTML and check that all 22 categories are included. Check the exact customer archive hash again before handing the files over. The owner review ZIP must never be mistaken for the smaller customer product ZIP.

## Evidence rules

- Test counts are parsed only from the supplied operation logs. If logs are absent, the report leaves counts absent; it never uses an earlier release's totals.
- JavaScript runs on macOS/Windows are shown separately as per-platform executions, not summed as unique tests.
- `PLATFORM-*-VERIFICATION.json` must identify the same final source and customer ZIP digest. A platform PASS must contain successful recorded commands. Its exact stated scope is displayed.
- Each source-associated screenshot must be named by its own matching PASS browser receipt. OS-prefixed images are associated through the matching platform receipt's nested browser report. Missing associations remain explicit.
- Matrix rows are preserved. A successful archive operation does not automatically change live-provider, commercial approval, broader invention, accessibility or OS criteria.
- A failed operation receipt produces a clearly failed evidence report while preserving the candidate status. Exit 0 means assembly completed, **not** that all product qualification criteria passed.
- No report or asset is submitted to Squarespace. The bilingual checklist is for Vincent's eventual manual decision and action.

## Verify the assembler

From the product directory:

```sh
python3 -m unittest discover -s tests -p test_owner_handoff.py -v
```

The synthetic tests check byte preservation, dynamic counts, status integrity, source/hash mismatches, unsafe members, screenshot associations and per-platform receipts. They are tool tests, not customer-product or live-inference qualification.

## Mandatory GENESIS example and raw proof

The 22 categories identify GENESIS itself as the primary improvement example. The GENESIS guide, actual construction source, fixed protocol and successor evaluator must be present. The scientific evidence category additionally requires current published-operation `OMEGA-DEMONSTRATION.json`, `OMEGA-FRESH-SOURCE-FREEZE.json` and `OMEGA-FRESH-SUCCESSOR.json`. These contain the constructed candidate source, nonce, exact cases and all comparison decisions. Historical packaged receipts and the additional quote example cannot substitute for missing final-source GENESIS proof. Preserve the five actual workflow/strategy/GENESIS sibling receipts byte-for-byte.

Correctness and safe reuse do not establish complete-cost superiority or autonomous construction of arbitrary source improvements. Those failed or unresolved criteria remain explicit alongside external authentication and commercial blocks.
