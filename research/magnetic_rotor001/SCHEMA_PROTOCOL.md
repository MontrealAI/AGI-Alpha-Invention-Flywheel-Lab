# Preregistered semantic-source gate 002 — no force data read

**Registered 2026-11-08 UTC, after successful source-access gate 001 and before reading MATLAB variable metadata or scientific values.** This is a separate necessary observation dependency, not a physical experiment, flagship, new scientific result, commercial service or change to gate 001's original success and source.

## Frozen known inputs

The independent source gate 001, PR #298 exact head `469bd67e8d63a16a0411526d5be52517eb342f86`, completed in Actions #42441981073, public artifact #13601253864, confirming original Zenodo file `Experiments_force_sensor.zip`: **SHA256 a5a536b9f279604a3aee1a9caaec134b8586d8b5972cbd9733f465cdbb3d3bc8**, 3,746,165 bytes; remote metadata MD5 `28897fb33b1915a0c9317629b9951759`. All ten safe MATLAB `.mat` members (names from public report, no scientific values read) have prefix `Experiments_force_sensor/data_incre_00_height_`, extension `.mat`, with exactly **0.5 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0 / 3.5 / 4.0 / 5.0 / 6.0** height labels. Actual physical meaning and units are not yet established by those labels.

## One fixed *schema-only* check

- One independent HTTPS retrieval (one attempt, no retries or substitutes), reapply the original 8MiB transfer cap, 64MiB expanded cap, source MD5 and exact **source SHA256**, safe ten-member manifest, ZIP CRC checks. Do not copy downloaded source into repo, artifacts or durable files.
- Use Python 3.12, NumPy 2.3.5, SciPy 1.17.0; apply `scipy.io.whosmat` **only**, to obtain top-level MATLAB variable names, array shapes and MATLAB classes **without materializing numeric arrays**. No `loadmat`, array value reduction, force-curve smoothing, fitting, plots or semantic guesses. Catch unsupported v7.3/HDF5 and malformed headers fail-closed.
- Require exactly ten members matching the listed names, each with at least one top-level variable, no duplicate top-level variable name, finite nonnegative dimensions <=10^7 in each variable and at least one variable name shared across **all ten** files. All ten heights are included; nothing is selected by outcome. If any rule fails, record `SCHEMA_GATE_FAILED` with reason, preserve the failure. Successful metadata reporting is `SCHEMA_GATE_PASS_PHYSICAL_MEASUREMENT_HOLD`, not source science or physical function acceptance.
- Public JSON contains only source hashes, pinned software versions, member names/labels, variable names/shapes/types, shared-variable names, counts, HOLD/NO DEPLOY, `mat_numeric_values_read=false`, `commercial_rights=UNVERIFIED`, no raw observations or account keys. No standalone transformed dataset is published.
- Adversarial synthetic `.mat` fixtures test schema changes, missing/extra file, tamper, data read boundary, wrong source, name collisions and scoping. A dedicated GitHub Actions workflow uses standard public runner, literal head, frozen ancestry and 360min platform cap; first step declares `AGI_JOB_START_EPOCH`. Its result must be independently downloaded and checked before promotion.
- There is **no** pass criterion for nonmonotonic friction, operational hold/slide, proof of new physical capability, industrial value, rights or profit at this stage. No repair/repeat after a failed registered run without separately frozen causal hypothesis.

## Next decisive experiment if schema qualifies

Only after examining the actual **schema** and original authors' unit definitions, separately preregister the full ten-height force extraction, phase/velocity window, sign conventions, noise and drift controls, session identity, held-out calibration, completely specified error tolerances and strong independent conventional alternatives. If the files cannot support independent replicates, retain that limitation. A real beneficiary's load/velocity/endurance requirement, manufacturer constraints, field effects, friction control, wear, full lifecycle cost and rights would remain unobserved.

This gate does not open/migrate any native account, authorize spending/financing, invent buyers or confer commercial use rights. No new external credentials, paid model APIs, private data, outreach, physical actuation or deployment. Objective US$3 billion trailing-365-day complete-cost native profit remains UNQUALIFIED.
