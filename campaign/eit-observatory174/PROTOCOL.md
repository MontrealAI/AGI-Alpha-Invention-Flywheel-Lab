# EIT174: preregistered actual-measurement source preflight (2026-11-15)

**Frozen before implementation or remote test.** Base main: `75f8f722c923e448d8f1fb44aa762b6ba0cd5a46`. This is a nonfinancial, additive Blue Sky 064 interior-observatory research branch. It must not touch the canonical connected enterprise, private accounts, financial owner PR40, governance PR372/373, release manifest, customer data, or keys.

## Opportunity and strong alternatives

The source is Hamilton et al., *Data Archive for 2D and 3D Electrical Impedance Tomography with moderate conductivity contrast phantoms*, arXiv:2611.17225v1, originally submitted 2026-11-12: https://arxiv.org/abs/2611.17225 . Its reported version-1 dataset DOI is https://doi.org/10.5281/zenodo.24120439 . Three claimed tank families: AgarCylinderPhantom (2D), AgarChestPhantom (2D), HeadPhantom (3D). This may support a future experimentally checkable interior-property observatory; publication and archive existence do not establish new observability, permission to run physical devices, patient safety, buyer demand, or a capability gain.

Before constructing a missing measurement, retain these competing complete routes:
1. Authors' conventional linear-difference imaging and native experiment codes, with full acquisition/mesh resources.
2. Competent CEM-based nonlinear/regularized inversion (including GN/TV), additional measurements where authorized, and existing human interpretation.
3. Joint measurement-selection plus separately calibrated inverse model and uncertainty-aware refusal, *only if* it achieves a specified outcome the above cannot deliver under matched resources.
4. No construction/deployment when measurement provenance, uncertainty, standards, practical resources or acceptability are absent.

All four are currently **HOLD/NO DEPLOY**. The manuscript itself describes existing successful reconstructions; inventing their inadequacy would be invalid.

## One fixed first experiment — remote metadata preflight only

A single tool run attempts to retrieve `https://zenodo.org/api/records/24120439` over HTTPS with a hard deadline, maximum 1 MiB response, and no redirects off the Zenodo host. It must parse a UTF-8 JSON object, retain exact downloaded metadata SHA256, record ID, version, DOI, title, license and listed artifact names, byte sizes and provider checksums when present. It must verify the record identifies the specified version DOI and **all three** expected archive families by exact, case-insensitive zip filename stems (no opportunistic alternate data source). Enforce names are plain basenames, nonnegative bounded sizes, and refuse duplicates, missing names, non-zip or unsupported upstream shapes. Do not download any data archive or report its byte hash as independently verified. Metadata checksums are publisher claims only. On any bad response, inaccessible source, missing field or mismatch: exit nonzero and retain the failure.

Implement a deterministic offline fixture test: valid three-archive response; missing family; conflicting duplicate; traversal; mismatched DOI; oversized response; invalid JSON; status/non-200; unexpected redirect; absent provider checksum (preserve as unknown, not fail if checksums optional); and no false "raw data verified" flag.

Measurement-inference, quantitative image quality, withheld phantoms and commercial success are *not* acceptance criteria in this preflight. This stage passes only if official metadata is accessible and structurally source-bound with the listed families; separately label data bytes, actual observations and real accepted physical outcomes as **NOT TESTED**.

Use only Python standard library, no paid API or credentials. Hosted workflow: public-repository standard ubuntu-latest, job timeout <=360 min, initial execution-start marker, no elevated permissions, no secrets, no persistent downloaded assets. Include measured process CPU/wall in the receipt. The workflow must never create a production account, vendor interaction or commercial transaction. Do not rerun or select a new version merely to manufacture success.

## Next acceptance — not authorized as achieved

Only after data bytes and licensing/rights are independently verified should a separate finite protocol freeze a particular end-use: classification/localization with explicit error coverage and false-positive tolerance across held-out original measured phantoms, matched old/additional measurement budget, calibration cost and strongest baseline. Source authors' simulation or reference images do not independently certify a new physical result. Finance, capital and demand require a distinct canonical native-account experiment; at this stage no revenues, supplier agreements, contracts, funding, actual bill values or annual profit can be claimed. Record physical and commercial verdicts independently. If source access fails, retain the failed attempt unchanged and seek a different independently supported source in a newly registered effort.
