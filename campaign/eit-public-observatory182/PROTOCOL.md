# Blue Sky EIT: pre-implementation physical-data intake protocol (2026-11-19 UTC)

## Selection and distinction from existing work

This is a separate **research-only, read-only** branch based on main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. It does not change the canonical Account, JournalAccount, PR40 source, queues, existing businesses or other Blue Sky owners. It is **not** the financial P0 integration and **not** a commercial launch.

Compare three materially different possibilities from `campaign/blue-sky-064/CANDIDATES.md` plus no-deploy:
1. Passive mixed-contact: possible load-dependent passive sliding/holding; existing mixed-assembly observations and qualified complete device comparison absent; the independent measurement instrument is already research-owned in PR465–469. **Hold**, no overlapping implementation.
2. Interior-property observatory: measured moderate-contrast EIT tank datasets could enable a proper same-instrument, held-out observability experiment without buying a device. Compared with competent human/specialist inverse methods, established regularized and CGO reconstruction, alternative instrumentation and no use. **Select for a finite independent evidence-acquisition test**, not as a proven new or commercially superior capability.
3. Resource-to-capital: possible qualified feedstock conversion with complete costs but no admissible actual conversion/impurity/kinetics measurement in available source. **Hold**.
4. **No-deploy/no-bid** is the standing economic decision without accepted outcome, voluntary demand, complete economics and authorized funding.

## Independently published physical source

Hamilton et al., *Data Archive for 2D and 3D Electrical Impedance Tomography with moderate conductivity contrast phantoms*, arXiv:2611.17225v1, submitted **2026-11-12**, https://arxiv.org/abs/2611.17225. DOI of the archived dataset claimed by the authors: https://doi.org/10.5281/zenodo.24120439 (Zenodo record ID 24120439, v1). The article reports KIT4/KIT5 physical measurements for `AgarCylinderPhantom`, `AgarChestPhantom`, `HeadPhantom`, with separate .mat HDF5 measurements, computational meshes, and Jacobians. The head phantom has 16 injecting and 32 measuring electrodes, and a resistive skull. **Existing published studies have already used related measurements; posting the archive in November 2026 does not establish that the method or physical sensing became newly possible this month.** No patient data is involved in this study. These are phantoms, not clinical evidence.

## Frozen first test / stopping rule (before seeing fetched record)

**Only** query the public Zenodo REST `https://zenodo.org/api/records/24120439` exactly once per hosted trial; use stdlib networking with a finite transport timeout and bounded JSON read. Parse duplicate-key-free JSON. Validate record ID, asserted DOI or exact record identity, three archive filename classes, public source URLs, nonnegative declared sizes, safe unique file basenames, and source-declared checksums. Record the entire original list, not selected favorable items. Produce a canonical JSON manifest, a SHA-256 digest of the received metadata bytes, and a clear pass/fail decision; do not copy or download the whole dataset on this initial run. A declared source checksum is **metadata**, not evidence that any data bytes were independently hashed. Permit public metadata-only access; do not infer license rights if metadata does not disclose a clear license.

This bounded **source-provenance gate** succeeds only if all three declared phantom classes are present and record identity is consistent. If the request, metadata, license, or expected file list is inaccessible or inconsistent, preserve the original failed run and stop this route pending a new prospectively documented decision. Do not silently fall back to a different record or change source after seeing results. No retries until a diagnosed fix. Network and runner cost unknown beyond measured public-hosted execution; no paid APIs or purchases.

### Next conditional causal test (not performed or implied by this intake)

If intake passes, freeze archive-by-archive byte hashes **after actual downloads** before physical analysis. Compare saline-only and prelisted non-saline measurements using a competent original Jacobian/linear-Tikhonov baseline and strong existing TV/CGO or learned reconstructions when reproducible under equal budgets. Use every predeclared eligible case, not cherry-picked cases, with holdouts by independent phantom/geometry where data supports them; account for current patterns, electrode/contact errors, nonidentifiability, multiple testing, missing measurements, and calibration uncertainty. An observable phantom contrast is not proof of inaccessible **new** information, clinical suitability, improved human productivity or a paying buyer. Only subsequently test accepted decision value and complete economic viability. Do not move the evaluator to make a result pass.

## Accounting/authority and acceptance ledger

- New code and CI may only inspect public metadata or perform ephemeral local testing; no actual commerce, licensed physical actuation, model key, financial account or original operation access.
- **Achieved prior to source access:** preregistered protocol, original publication citation, explicit incumbent and no-deploy.
- **Pending:** exact source metadata and declared rights; actual measured bytes; reconstruction; independent acceptance; matched strongest alternatives; complete-cost positive economics; actual payments; earned-funded successor.
- **Failed or blocked:** preserve as FAILED/BLOCKED with original trace, never relabel.
- A successful GitHub workflow establishes only metadata acquisition and format validation. It cannot qualify a new scientific result, financial integration, released native operation, $3B profit or physical/clinical deployment.
