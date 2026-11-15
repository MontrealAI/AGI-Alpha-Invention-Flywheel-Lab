# EIT180 — registered cross-replicate structure challenge (15 November 2026)

**Frozen before implementation and real-source inspection in this branch.** Parent EIT179 exact head `489671154ec3bf1b080195bf8f698edd9cf00dcd`, stacked research only. The original EIT177 INVALID_MAT73_MEMBER run remains FAILED, EIT178 correctly diagnosed Apple metadata, and EIT179 measured only an original source-bound pair without reconstructing conductivity. No parent source/test is to be altered.

## Question and consequential decision

Is the reported voltage difference between two same-setup KIT4 AgarChestPhantom repeats consistent with a systematic *reproducible channel/gain/offset* component rather than entirely irreducible variation? This is a required obstruction check before asserting any new EIT measurement/inverse instrument or economically meaningful clinical/industrial detection. An already competent calibration can win. A scientific difference is not proof of conductivity-ground-truth accuracy.

## Fixed source, population and method

Read **only** original EIT179 official Zenodo record `https://zenodo.org/api/records/24120439/files/AgarChestPhantom.zip/content`, exactly 24,539,080 bytes, publisher MD5 `8514af69c0277f339d5576dd4eb9a598`, independently observed SHA-256 `ad193cd88288e3d6f8ea87f76d8ed2f06382291ab494d55efe08806c65ff994c`; reuse EIT179 one-shot 60-second Zenodo-only HTTP and ZIP guards, original lexicographic first genuine `AgarChestPhantom/Data/*_1.mat`/`*_2.mat` pair (never choose a successful later pair), unchanged original MATLAB7.3 parser and finite real current/voltage fields. No raw scientific archive is retained in Git.

Treat voltage matrix row index as the only split axis, not as a claim about physical time or independent measurements. Even zero-based rows are development (for 79 rows: 40); odd rows are **untouched holdout** (39). Each row includes all columns, keeping channel mappings fixed. Nonmatching current matrices invalidate same-drive interpretation and must be disclosed (and block a calibration interpretation if not bitwise numerically equal). Do not transpose, de-mean holdout inputs, use holdout target values to fit, tune thresholds after inspection, or reinterpret labels or units.

Fit on even rows using ordinary explicit double-precision least squares, then predict odd-row second-repeat voltage from first-repeat voltage. Fixed models:

* O0: identity, y=x (no fitting; raw disagreement).
* O1: global through-origin scalar gain, y=g*x (1 trained parameter).
* O2: global affine, y=g*x+b (2 trained parameters).
* C3: per-column affine, y_j=g_j*x_j+b_j (2 parameters per column), using only that column's even rows.

Use exact sum-of-squares formulas, no SciPy optimizer and no hidden regularization. Fail closed on rank-deficient training variance/denominator or nonfinite predictions; never substitute a different fit. Report heldout RMS and mean absolute error for all arms, development RMS, gain/offset parameter summaries, holdout count, source/member identities, and per-column holdout RMS. Preserve model asymmetry: train on first-to-second only, not both directions. C3 is a **candidate diagnostic** and ordinary per-channel calibration is itself a competent incumbent, not a novel method.

**Preregistered decision:** A meaningful structured-repeat signal requires C3 to reduce heldout RMS by at least 10% relative to the *best* O0/O1/O2 comparator, with no column's heldout RMS more than 2x its O0 RMS when O0 RMS>0. Failing this means REJECT_INCREMENTAL_STRUCTURE; passing means CONDITIONAL_REPEAT_STRUCTURE_ONLY, never reconstruction accuracy, autonomous advantage, a new instrument, physical noise calibration or commercial progress. All actual outcomes and failed arms must be retained. A reverse-order or alternative split may be done only as a separately registered follow-up.

## Fixed controls and resource bounds

At least twelve local synthetic tests: exact O0/O1/O2/C3 holdout arithmetic; gain-only and global-offset cases; a channel-specific gain case; overfit example rejecting C3; zero-variance failure; mismatched-current refusal; nonfinite rejection; shape guard; parent real-data namespace/sidecar rule; no-overwrite create-only receipt; pinned publisher SHA/MD5/size refusal; preserved EIT177 failure label. Source-bound actual one-shot run is required; never retry automatically or change the target to obtain a favorable result. Use one standard public GitHub Actions ubuntu-latest read-only job, first-step AGI_JOB_START_EPOCH, 360min ceiling, pinned binary numpy==2.3.5 and h5py==3.15.1 wheels, no services/custom image/paid API. Publish compact JSON receipt, source/test commit, actual results and complete measured self CPU+wall; whole billed costs UNKNOWN.

## Alternative arrangements and authority

Three productive possibilities remain open: (A) use the authors' published linear difference reconstruction and standard calibrations, (B) independently construct and test a potentially stronger physical measurement/reconstruction instrument with ground-truth phantom acceptance, and (C) a human/conventional specialist or mature CEM Gauss-Newton/TV stack; always include NO DEPLOY. All require provenance, rights and matched prospective costs. This narrow experiment does not compare complete alternatives or prove an accepted new commercial outcome. Existing PR40 account/authority/queue/liabilities, finance releases, other-owner source, EIT175/EIT177 historical outcomes and original key custody remain untouched. No outreach, spending, private data, bids, transactions, paid services or deployment. US$3B trailing-365-day complete-cost profit remains unachieved.
