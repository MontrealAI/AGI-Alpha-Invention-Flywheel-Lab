# Independent geometry trust-boundary review — November 18, 2026 UTC

**Review owner:** dependent draft PR #450. **Original integration owner:** draft PR #449, original source `230409b54f4adf8f69bd8d029020bfde7acbcff0`. This document proposes a nonfinancial reviewer change, not a release or permission to operate an instrument.

## Failure retained

The original portable receiver accepted a freshly forged reference altitude (+45 degrees) for a target whose original altitude was below the horizon, after a caller changed its own catalog and catalog hash. The original worklist passed as a positive control. The frozen test-only commit `89d805daf2f3d97f6ee73aef66a8ca43b1391d0b` **FAILED** its adverse assertion (expected exception not raised): [original hosted workflow #44222650763](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44222650763). This is a hypothetical newly fabricated pair of documents, not evidence that original Fink, ZTF, or Astropy data were altered.

The prospective source `c72e90845d93ca0960e4969bb61451fc20543a37` verifies each reported reference altitude and Sun altitude against the existing independently calculated geometry within 0.1 degree, including matching eligibility. The original frozen regression passed under that source. Its first whole-product run **FAILED** because the checked-in bilingual HTML still embedded the previous receiver; [workflow #44222849254](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44222849254) is preserved as failed, not relabeled.

## Corrected portable recipient and generated exhibition

The failed job retained a generated, source-matched artifact for independent inspection: [artifact #14390949361](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44222849254/artifacts/14390949361).

- Generated bilingual `FRONTIER_FIELD.html`: SHA-256 `08e6834a911f7b59954eb025dc75257a93d4f515e837484aebb5dfebfdbf24b9`.
- Generated public instrument ZIP: SHA-256 `570131b25a3e125ad86d2b87ee1233b4cef708fd2b6abbfc62ce30dce7ed4047`.
- Embedded `invention/verify.py`: SHA-256 `9cee9fc00cb5c1f4d15bf141dbb39c8ade1f8ae243d1ae1264700b9a751aa612`, also recorded in the ZIP's `SHA256SUMS`.
- Independently extracted receiver replayed 14 registered worklists and both archival photometry windows; its untouched worklist was accepted and independently forged below-horizon receipt rejected. The standalone verifier must use its documented normal Python CLI, not `python -I` without its module path.

A [one-shot exact-byte generation workflow #44228770987](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44228770987) regenerated both bytes on the dependent review branch, required the two expected hashes, committed only the changed bilingual exhibition, and **removed itself in the same final commit**. It used the existing ephemeral GitHub Actions token solely for a fast-forward push to the unchanged reviewed branch; it did not modify PR #449, main, any account, financial writer, or deployment.

## Limitations and integration gate

The geometric cross-check is a portable approximate independence guard, not a fresh Astropy authority, signed broker provenance, physical observation, available telescope time or proof of a source target's identity. An attacker who controls the entire input source can still invent a different coordinate assignment; provenance, source selection, physical scheduling and real scientific outcomes require separate evidence. The conventional exhaustive schedule control remains a tie. No actual paid demand, labor, infrastructure price, inference billing, native capital reinvestment or annual business profit follows from this review.

Retain the original failed trials and all previous historical qualifications. Requalify the **new exact commit including the synchronized HTML** under normal product and repository workflows; verify the recipient extracted from those bytes before any claim of qualified integration. Original PR #449 owner alone controls composition and any later merge/publication. The original canonical financial Account/JournalAccount, signing authority and outstanding liabilities are outside this review and must not be reset, migrated or written by it.
