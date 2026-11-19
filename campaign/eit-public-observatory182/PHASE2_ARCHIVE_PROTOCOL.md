# EIT182 prospective phase 2: exact public archive bytes and measured-voltage inventory

**Frozen before downloading measurement archives and before implementation**. The initial source-metadata-only trial on push commit `14f28ab5b0d3b9d2126dfe918181c9438ac5d337` succeeded in both hosted jobs; artifact 14492486724 (outer SHA-256 `5dab4a58e280a86319b1646446fbd06d8c8f1c78e4bac8256ece9d67d391e874`) lists all 10 public record files, reported CC-BY-4.0 rights, and source **declared** hashes. Neither archive data bytes nor HDF5 readings were downloaded in that stage.

## Fixed physical source and method

Only fetch the exact `AgarCylinderPhantom.zip` URL in the frozen metadata receipt:
`https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content`.
The source reports size **12,482,688 bytes** and MD5 **658694f69f64075b6fefec2e2c597131**. This is an *expected-source declaration*, not yet independent byte verification. Do not fetch any other archive in this trial. Use read-only standard GitHub-hosted public network, no private credential or paid service. Stream the archive into an ephemeral file; reject changed final host, size, MD5, unsafe ZIP names, duplicate names, symlinks, encrypted entries or CRC failures. Independently hash entire archived bytes using SHA-256 and individual selected HDF5 member bytes; retain only small public metadata receipts, never copy entire dataset into this Git tree.

Enumerate **all** `.mat` members whose normalized path contains a `Data` directory and whose basename does not begin `mesh_` or `J_`; sort case-sensitively, include every eligible member, and **do not select a favorable subset**. For every member, open the MATLAB 7.3 HDF5 file using pinned standard `h5py` + `numpy`; require top-level numeric `currents_matrix` and `voltages_matrix`, finite nonempty values and a documented sample slice. Record exact shapes, dtypes, global finite norm/mean and minimum/maximum, deterministic SHA-256 of original member bytes and a finite source-value summary. If required fields/units are absent, an eligible member is invalid and the trial fails, not discarded. An internal non-numeric object or calibrated-sensor provenance cannot be manufactured.

### Registered acceptance and stopping

- **Byte-verified source acquisition** only if observed compressed size, MD5, safe contents and all relevant member hashes validate.
- **Measured-array inventory** only if at least two eligible independently recorded cases pass for complete data (current and voltage); source filenames are not clinical labels.
- A successful inventory is a real-public-phantom **data-processing result**, not a reconstruction, causal observability gain, uncertainty-validated sensing, patient diagnosis, commercially accepted outcome or frontier novelty.
- Strict worst-case disk/memory safeguards are finite engineering limits for this declared trial, not general business ceilings; fail with a diagnosis if unhandled source expansion exceeds available resources. Record measured process CPU/wall/RSS and source bytes. No retry on failure without diagnosis and a new prospective amendment.
- Physical property estimation, pairing saline vs targets, cross-instrument reconstruction, threshold calibration and strongest ordinary TV/CGO/specialist control are **not selected or performed** in this phase; they require a separately frozen physical case/outcome contract after structure and original source data are verified.
- **HOLD/NO DEPLOY/NO BID** regardless of stage success. No native financial or payer impact. Prior P0 original account/queue, immutable failures and other Blue Sky owners remain untouched.
