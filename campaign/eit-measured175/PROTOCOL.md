# EIT175 — frozen public physical-data byte and replicate preflight

Registration time: 2026-11-15 UTC, before any source archive download, content inspection, test implementation or hosted execution.
Parent source (EIT174): `faa0584083c4969d35f8789ec8e0941d18db3e26`. EIT174 freeze `36029fc722a8431a6ad8a044e224f5791db1810b` and recorded exact official metadata `69f31a43c2dbea8457cafcc4ed7a4250238495acf0df41339e030b5fe502c82c`, DOI `10.5281/zenodo.24120439`. EIT175 is a distinct test, not a retrospective upgrade of EIT174.

## Fixed source and reproducibility

Download *one and only one* public official archive, `AgarCylinderPhantom.zip`, from
`https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content`.
Expected exact byte length **12,482,688**, publisher-declared MD5 **658694f69f64075b6fefec2e2c597131**. No alternate mirror/version, seed, candidate selection, purchased service, key, physical operation, patient data, manual repair, or retroactive adjustment. Standard read-only HTTP(S), only a confirmed Zenodo host redirect, connect/read timeout <=60 seconds, cap at 20MiB. Independently hash actual bytes SHA256 and MD5; MD5 check is a publisher checksum witness, not independent scientific validation. If network/bytes differ, preserve FAILED; no retry to find a pass.

Validate standard ZIP archive: no encrypted members, symlinks, absolute/traversing/non-ASCII-dangerous member paths, duplicate casefold names, >2,000 entries, >500MiB declared total uncompressed bytes, >64MiB for a selected MAT member, or corrupted compressed streams. Read only tiny selected measurement members; do not extract to persistent folders.

## Fixed simple experimental check

The paper says agar MAT v7.3 data contain `currents_matrix`, `voltages_matrix`, `units_info` and that suffixes `_1` and `_2` mark separate repeats when present. Among case-insensitive `Data/` paths ending in `.mat`, find pairs sharing the same filename stem after the literal trailing `_1`/`_2` (before extension). Take **only the lexicographically smallest common stem** (no searching for attractive outcomes). If no such pair exists, fail this registered repeat check without reinterpreting two different setups as repeats.

Using pinned wheel h5py and numpy, read exact `currents_matrix` and `voltages_matrix` HDF5 numeric datasets from each of the two MAT files. Require rank 2, nonempty, finite real numbers, <=2 million values per array, matched current/voltage dimensions across the pair; check `units_info` exists. No undocumented transposition/unit conversion or engineered noise correction. Record four member names/hashes, two numeric array shapes, RMS and max-absolute direct differences, mean absolute voltages, and self CPU/wall. **Do not assign an inferential threshold, calibrate a reconstruction, claim a physical breakthrough, or declare repeat stability based on numbers alone.**

If file structure uses different but legitimate MATLAB object references, or no repeated pair exists, record the exact failure rather than weakening tests. This preflight only proves one archive's bytes and an applicable actual repeated-measurement structure; the paper's full measurements and acquisition still have independent uncertainties.

## Offline regression protocol and hosted execution

Add source and one tests file with fixed cases: valid synthetic paired HDF5 archive, wrong publisher MD5, wrong size, corrupt ZIP, encrypted ZIP/member symlink/traversal, duplicate casefold member, uncompressed-size guard, no repeat pair, missing HDF5 fields, nonfinite values, wrong dimensions, and arbitrary exact-stem tie ordering. At least 12 independently named tests; do not weaken failures.

GitHub CI must use `ubuntu-latest` with the first mandatory job-start marker, max 360-minute actual platform window, minimal contents-read, no secrets, no custom services, no paid model, pinned setup action, only-binary wheels and fixed dependency versions. Upload compact receipt even on failure (no bulk archive or raw measurements published).

**Verdict gates:** actual source archive bytes authenticated or FAILED; repeated-measurement numeric accessibility or FAILED; new interior-property capability NOT TESTED; acceptance against strongest authors' linear inversion, GN/TV, human and AI alternatives NOT TESTED; native account/earning/reinvestment NOT TESTED; revenue, real buyer, and US$3B trailing-365 target NOT ACHIEVED. The separate financial owner PR40, original account, all liabilities, prior test failures and release remain untouched. No deployment or commercial action.
