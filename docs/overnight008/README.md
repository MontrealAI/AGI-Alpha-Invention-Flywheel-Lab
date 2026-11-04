# Recovered public research edition

**MISSION NOT COMPLETE.** This package reconstructs the historical checkpoint from public commit `3360acaffa088ca4e9cc595412026210cb4952b2`. It adds a separately attributed recovery supplement. It does not claim a fresh numerical experiment, physical validation, profitable offering or commercial flywheel.

- [PDF](AGI_ALPHA_Overnight_008.pdf): compiled LaTeX, 12 pages, every final page visually inspected.
- [LaTeX](AGI_ALPHA_Overnight_008.tex), [self-contained HTML](index.html), and [GitHub-readable report](REPORT.md).
- [Source manifest](SOURCE_SHA256.json): all 119 original consumed files checked against the exact public commit.
- [Recovery provenance](RECOVERY_PROVENANCE.json): extra public v1 source hashes, prior public comments and recovery wrapper identity.
- [Visual QA](VISUAL_QA.json), [build receipt](BUILD_RECEIPT.json), [render receipt](RENDER_RECEIPT.json), and [iteration/resource record](RECOVERY_ITERATIONS.json).
- [Artifact hashes](ARTIFACT_SHA256.json): final deliverable identity, excluding this hash manifest itself and temporary files.

The main text describes the source checkpoint at 06:13:57 UTC. Appendix A records the subsequent public full120 review as a prior report, not a new proof replay. The missing private arrays and their old hashes cannot establish a recovered witness. Original resource/error budgets remain unchanged; incomplete monetary costs remain UNKNOWN.

From an exact public checkout, regenerate the base with the unchanged public builder:

```sh
python3 scripts/build_overnight008_paper.py --source-ref 3360acaffa088ca4e9cc595412026210cb4952b2
```

Regenerate the recovered edition using the supplied wrapper and its adjacent `PUBLIC_REVIEWS.json`:

```sh
python3 PATH_TO_RECOVERY/build_recovery.py \
  --repo PATH_TO_PUBLIC_CHECKOUT --output NEW_RECOVERY_OUTPUT
```

The wrapper writes only its output directory, checks the frozen public builder identity, and enforces 600 CPU-seconds and 2 GiB address space per process. Its receipt measures the current build only. Render and inspect the newly generated PDF again; an older QA receipt does not qualify new bytes. The final visual QA, artifact hashes and iteration record are intentionally separate from manuscript generation.

No campaign candidate, authority, verifier or frozen builder was changed by paper recovery. Source identity establishes bytes; it does not establish experimental truth. A clone reconstruction is distinct from final downloaded release-package qualification.
