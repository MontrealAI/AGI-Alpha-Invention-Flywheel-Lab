# Table Desk

**Recover a reusable CSV from a specific printed table and inspect where each value came from.** A reader provides a transcription. Table Desk renders the registered PDF regions, binds the transcription to those image bytes, and checks the complete matrix against the separately supplied, authorized semantic table. When every cell matches, the researcher gets a CSV carrying both source references. Where a publisher already provides a complete semantic table, the direct export takes only the HTML and registration.

[Open the accepted Cycle 001 CSV](evidence/cycle-001.csv) · [First physical page crop](evidence/page-1.png) · [Second physical page crop](evidence/page-2.png) · [Published PDF](../../../docs/research/cycle-001.pdf) · [Author HTML](../../../docs/research/cycle-001.html)

## What happened on the first published table

This is one table spanning two physical pages. The 12 cells contain prose, with no numerical values. A repeated second-page header was excluded using the registered geometry.

| Route | Measured outcome |
| --- | --- |
| Included ChatGPT/Codex, two images only | 12/12 exact cells on its first frozen transcript. [Transcript](included-vision.json) · [Acceptance receipt](evidence/included-vision-receipt.json) |
| NVIDIA Nemotron-3.5-Parse, local CPU, two full crops | 12/12 exact cells after deterministic extraction of its table markup. The run took 39.1139 seconds of wall time and 111.714 CPU seconds, with 3,079,996 KiB peak resident memory. [Model observation and raw generations](evidence/nemotron/) · [Acceptance receipt](evidence/nemotron/receipt.json) |
| Tesseract 5.5.0, English, registered per-cell rectangles | 12/12 exact cells. Its 12 subprocesses took 1.017 seconds in total, excluding crop preparation and rendering. [All OCR attempts and receipt](evidence/tesseract-receipt.json) |
| Direct author HTML | Complete 4 × 3 table. The direct export, included visual reader, NVIDIA parser and conventional OCR all produced identical 763-byte CSV content. [Direct receipt](evidence/direct-author-receipt.json) |

A separate evaluator parsed the first author table with lxml and the three outputs with Python’s CSV reader. All 12 cells matched in each of the three outputs available to that evaluator (direct, included vision and Tesseract). The separately scored NVIDIA output has the same CSV digest. The evaluator also inspected the two registered crops against the five original pages and confirmed that the second page completes the fourth row.

CSV SHA-256 is `c02f8528f5e3e2b8fd89efdcfdcf015c04fdd97568267d553d0dad333ecc1015`. As prediction targets the two source forms have common authorship. Acceptance establishes complete agreement with the pinned reference. The supplied transcriber could have used other information; the experiment’s first-response commit and presentation conditions carry the provenance claim, beyond the hashes enforced by the program. Both direct HTML access and the strong conventional OCR route succeeded. Source selection, cell-region preparation, complete human labor, provider cost, commercial demand and strict AI-versus-human productivity remain unmeasured. The deterministic controls with a different two-column fixture reject wrong digits, dropped/substituted signs, grid changes and missing authority.

[Protocol and source geometry](REGISTRATION.md) · [Registration commit](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/f958c50baa11ffa9fc0d49bc81d76072a173900c) · [Frozen included transcript before scoring](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/b11a677cd9bcf87d1b5d0ca2963839c936f1aea7) · [NVIDIA execution and replay](NVIDIA-ARM.md)

## Run from the repository root

Use Python 3.11+. Rendering requires Poppler `pdftoppm` and Pillow, and the OCR arm additionally needs Tesseract with English language data. The direct export needs only Python. Choose new output paths for each execution.

```bash
desk=products/frontier-omega-ignition/table_desk
pdf=docs/research/cycle-001.pdf
author=docs/research/cycle-001.html

python3 "$desk/table_desk.py" direct --registration "$desk/cycle-001.json" \
  --author "$author" --output /tmp/td01-direct

python3 "$desk/table_desk.py" crop --registration "$desk/cycle-001.json" \
  --pdf "$pdf" --output /tmp/td01-images

python3 "$desk/table_desk.py" check --registration "$desk/cycle-001.json" \
  --pdf "$pdf" --author "$author" --candidate "$desk/included-vision.json" \
  --witness "$desk/included-witness.json" --output /tmp/td01-included

python3 "$desk/table_desk.py" ocr --registration "$desk/cycle-001.json" \
  --pdf "$pdf" --author "$author" --output /tmp/td01-ocr

cmp /tmp/td01-direct/table.csv "$desk/evidence/cycle-001.csv"
python3 -m unittest discover -s "$desk" -p 'test_table_desk.py' -v
```

The `check` route requires the same actual PNG bytes shown to the visual transcriber. The published rendering used Poppler 26.05.0. Font libraries or renderer versions can change pixels or PNG encoding. An image mismatch leaves `receipt.json` with a withheld verdict and exits 2. Inspect the bundled rendered images to replay the original challenge. Register any new rendering and capture a fresh transcript before viewing the reference. An accepted check returns 0. A mismatch against an authorized reference records every differing cell plus the dimensions and returns 2 without exporting CSV. Operational errors return 1. The fresh-directory delivery prevents a stale accepted CSV surviving a failed attempt.

## Apply to another publication

Prepare a registration with PDF and HTML SHA-256 digests, the physical PDF page numbers, crop rectangles, row bands, column boundaries and the author table’s 1-based ordinal. Positions are measured from the top left of an unrotated PDF page in whole points. For `ocr`, use the same column positions across the registered pages. The HTML route takes a simple rectangular table with explicitly closed rows and cells. Merged cells and nested tables require a separate, unambiguous author representation. Preserve authorization for using and redistributing the documents.

With `crop`, deliver only the registered images to the reader. Before consulting the author table, save a rectangular JSON array of strings and a witness matching [this format](included-witness.json), with hashes of the registration, candidate bytes and rendered PNGs in page order. Keep the witness and transcript in an independent record. Supply them to `check`. Only Unicode NFC and whitespace are normalized. Signs, punctuation, digits, unit spellings and case remain significant. Where no authorized semantic authority exists, the appropriate result of this version is a withheld CSV. For crops with small fonts, meaningful symbols or complex geometry, preserve ambiguous cells and qualify fresh trials.
