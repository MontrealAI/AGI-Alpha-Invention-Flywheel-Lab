# Independent review of the quantum recovery and noise-identification package

## Final verdict

**PASS for the bounded computational research scope. No required code fixes remain.** The reviewed frozen scientific sources implement the stated finite mathematical contracts. The selected recovery and independent conventional recovery each reproduce **824/824 checks**. All seven successor constructions, including the selected pair2 source and the ordinary-reuse control, reproduce **163/163 checks** apiece. Every original source/dependency and qualification provenance chain reconciles exactly.

The packaging owner selected the unchanged **pair2 retained** successor after review identified its smaller measurement frame, lower recorded qualification memory, and stronger recorded response conditioning. Its full source was reviewed, and supplemental independent public-fixture checks passed for its execution and erasure APIs and ideal inference with convexly dependent hypotheses. A final manifest-only relocated replay passed every scientific verdict and the selected operator example. The final report, README, ordinary-reuse provenance, and manifest were reviewed. This is a separate-agent code/evidence review, not formal PR approval, release approval, external scientific certification, or economic validation.

## Material findings and disposition

**R1 — Relative replay output paths: fixed and independently verified.** The original `reproduce.py` created a relative output directory in the caller's working directory but ran the checker with the package directory as its working directory. The checker therefore interpreted the same path differently. The owner fixed this by expanding and resolving the output path before creation or subprocess launch. The independent relocated replay verifies the fix for the complete nine-entry package.

**R2 — Selection among qualified alternatives.** Pair2 retained constructs 484 outcomes on the recorded syndrome-rank-22 cases; pair1 constructs 946. The recorded qualifier RSS is 165,528 KiB versus 249,220 KiB, and pair2 has a larger smallest nonzero response singular value in each of the six recorded cases. These are useful bounded engineering differences, though qualifier resources include checker work and singular values alone do not establish statistical efficiency. Selecting the unchanged pair2 source follows the protocol's performance and conditioning considerations. All original construction outcomes remain unchanged.

**R3 — Preserve source-specific evidence: verified.** The original pair1 dependency-use trace and ambiguity-resolution witness remain labeled as pair1 evidence. Separate pair2 receipts were inspected and match the selected source and unchanged recovery dependency. Both constructions record actual `Recovery.__init__` and `Recovery.kraus` calls. The report correctly states that the original raw-readout rank is specific to the frozen recovery Kraus basis and numerical realization, and does not establish an impossibility for every conventional recovery measurement.

**R4 — Portability scope.** The replay wrapper uses `resource`, `RLIMIT_AS`, and `preexec_fn`, so its supported execution path is POSIX/Linux. The workflow explicitly uses Ubuntu. No Windows portability is established or needed for that declared path.

**R5 — Failed diagnostic cost boundary: corrected.** Failed CLI receipts do not by themselves prove zero backend inference. The report now states that the diagnostics failed without a completed result and that backend work and cost remain unknown.

## Scientific implementation

`recovery.py` constructs the common Knill–Laflamme Gram matrix from sparse physical error columns. Its eigendecomposition produces orthogonal syndrome/logical sectors while discarding numerical zero modes, which is essential for degenerate codes. The exported rows implement the resulting logical recovery map. Their complement is accounted for as a classical erasure outcome. Validation checks orthonormality, the full logical Knill–Laflamme relations, and the resulting isometry without silently normalizing invalid input.

The selected pair2 successor uses the recovery's public operator interface. Its raw syndrome frame has one basis row and two phase-sensitive rows for every coordinate pair, giving `r²` outcomes whose effects span every Hermitian syndrome operator. Whitening the positive frame operator normalizes the measurement while preserving that span. Composing these rows with the recovery operators preserves the arbitrary logical state and makes the observation map injective on the physically available syndrome information. Rank-deficient channel libraries are correctly reported as nonunique.

Its estimator explicitly normalizes classical observations and computes identifiable coordinates by SVD. Exact feasible data are handled through the inverse or linear feasibility on the simplex. For noisy data, it fits in identifiable coordinates. This is an estimator for the declared finite task, with no maximum-likelihood, confidence-interval, optimal-shot, or hardware-circuit claim.

## Independent checker adequacy

The frozen checkers reconstruct physical Pauli action independently, derive the correctable span by pivoted QR, and inspect the exported operators directly. They test support, completeness, logical matrix-unit preservation, and agreement between predicted and physical response. The second checker derives the available noise-information rank from a physical density Gram matrix, rather than accepting the candidate's self-reported rank. The resulting finite tests support arbitrary logical-state nondisturbance through full-span matrix identities, not only a single convenient logical probe.

There are six frozen scientific cohorts per stage. Counts such as 824 and 163 describe checks over those cohorts, not independent scientific replications. The assurance is finite double-precision numerical verification with separated nonzero spectra. It is not a formal proof for every floating-point input, a hostile-code sandbox, external certification, or a hardware experiment. Blinding is procedural on a shared host.

The review also used public fixtures for targeted supplemental checks of code paths that the frozen successor checker does not directly call. Both pair1 and pair2 convenience execution agreed with the exported operators for arbitrary complex physical branches, including off-span and subnormalized mass; the erasure effect completed the channel. Convexly dependent channel hypotheses produced feasible ideal estimates at simplex boundaries. A sparse 20-qubit, four-dimensional product code passed local amplitude-damping checks on all 20 qubits, with a maximum density error of about `1.943e-16`. These remain separate supplemental observations and do not modify original acceptance or source outcomes.

## Successor distinctness and evidence limits

The second objective is substantively different: recovery returns a corrected logical density, while the successor constructs an executable noise-identification instrument, an observation matrix, an identifiable parameter quotient, and an estimator. That is useful computational research functionality. The evidence establishes neither operation of a physical instrument nor downstream economic value.

Every paired construction succeeded. The data therefore do not show that the retained artifact was necessary to reach the successor outcome. The construction intervals were:

| Pair | Retained source available | Without prior source | Without minus retained |
|---|---:|---:|---:|
| 1 | 368.421 s | 479.399 s | +110.978 s |
| 2 | 343.992 s | 386.715 s | +42.724 s |
| 3 | 349.174 s | 347.304 s | −1.870 s |

This is mixed marginal latency evidence: two shorter retained intervals and one essentially tied interval with the without-source construction slightly faster. The mean recorded reduction is 50.611 seconds. These are three repeated constructions of the same successor task, not three different productive inventions. The intervals include model inference, orchestration, and scheduling, not complete compute or economic costs. Three procedurally paired trials do not establish a general causal population effect. The ordinary-reuse control's prior source is functionally comparable independently implemented code, not byte-identical equal content; the preserved clarification states that distinction before its dispatch. That ordinary-reuse construction passed 163/163 checks in a recorded 373.638-second interval, with zero source repairs and verified dependency binding.

The final report retains the first capability's 320.234-second constructor interval and 348.773-second dispatch-to-freeze interval, along with its development and qualification, acquisition/search effort, all seven successor constructions, failures, integration, verification, review, packaging, operation, and unknown model/host and continuing costs. Every measured one-successor interval saving is smaller than the first acquisition interval. The conventional first source also has a 213.211-second elapsed-since-recon record, with different activity boundaries; these first-stage intervals are not a controlled latency comparison. Complete costs are disclosed by category but only partly measured. Overlapping elapsed intervals cannot be summed and renamed end-to-end wall time. Logged numerical CPU cannot be renamed inference compute. Included capability use does not imply zero economic resource cost.

No global algorithmic novelty, quantum speedup, physical fault tolerance, improved inventor, human-only productivity superiority, revenue, profitable funded continuation, or complete economic advantage is established. Functional reuse is supported; causal necessity, general construction superiority, and economic compounding remain separate unproved claims.

## Reproduction and source identity

The independent relocation test copied **only the 29 manifest-bound files and the manifest** into a temporary source path containing a space. It removed inherited `PYTHONPATH`, ran from outside the source directory, and supplied a relative output path. All nine qualifications reproduced their original verdicts; the selected operator demo also passed and emitted the exact selected source hashes. The copied scientific sources stayed unchanged. Temporary case copies were removed; the review retains result receipts and hashes, not duplicated hidden input data.

The complete relocation check took 32.729 seconds wall time and 32.684 seconds measured child CPU, with a maximum child RSS of 250,124 KiB. Those are reviewer process resources, not model-inference cost or historical construction latency. The actual replay runtime was Python 3.12.14, NumPy 2.3.5, and SciPy 1.17.0 on Linux, with one BLAS thread. Third-party and BLAS binaries are version-recorded, not asserted byte-identical across hosts.

The final scientific manifest is `74280c1fc74bc830c5a8c3ce08c0581197f0d82757f64bfbecc399217d1bda3c`. The exact reviewed file hashes, original and new receipt bindings, paired measurements, and scope limits are recorded in `REVIEW.json`.

Key immutable identities:

| Source | SHA-256 |
|---|---|
| Retained recovery | `f8638af7b2532f8c2161fefe2169bb91788c9fc3a5e3321cf7a05ec717f7c134` |
| Selected pair2 successor | `6afa2b999e810e8873ee1ed9de4ca09ddb06b80cfe2c37d269ab798e7c09679b` |
| Valid pair1 successor alternative | `0a1a563879a76bc192936caba3a8ae27987024123d03287dacf5dea80da716db` |
| Conventional recovery | `c2b3ba3fde39b247ea4d81983e5a4bb6de1d5ed62053b205f8aa65138f99e261` |
| First checker and copied physics dependency | `3099493828db0dbfee9a8624d28c64655a36fc8eaa1c140ba361aee391461bdb` |
| Second checker | `7f483d904aacd4ebd2b88da9081030e0de03848a164481952426bf0ebec82a75` |

The final README and report accurately distinguish useful finite mathematical functionality, executed ordinary source reuse, mixed marginal elapsed-time evidence, and unmeasured complete economic benefit. The workflow source follows the declared standard Ubuntu path, one BLAS thread, pinned scientific dependencies, a 360-minute platform window, read-only repository permissions, and retained result artifacts. Its actual hosted completion was not independently observed by this reviewer. Hosted workflow success, publication of the final package, merge, release, and deployment must each be reported only if separately observed.
