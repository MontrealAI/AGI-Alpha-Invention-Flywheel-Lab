# Correctness amendment 004-A — preregistered after the first failed synthetic run

The first exact-head GitHub Actions workflow **#42453860904** at commit `d23667b56bc67f53d4bccad3c177db564951e752` **FAILED before accessing the original Zenodo archive**. Its 14 frozen synthetic regressions produced 11 passes, two failed assertions and one exception. This result stays FAILED; no actual original science was read.

The three independently observed causes and narrowly bounded prospective corrections are:

1. **MAT v5 compressed tag alignment.** SciPy's ordinary `savemat(..., do_compression=True)` omits padding after a top-level miCOMPRESSED element; the new reader incorrectly required an 8-byte trailing pad. Permit the actual bounded compressed payload length to terminate at the unpadded end, while retaining strict element length, zlib output, nesting and absolute bounds. Do not relax regular miMATRIX alignment.
2. **Empty-array metadata semantics.** The real SciPy synthetic `np.array([[]])` serializes with dimensions `[1, 0]`, not `[0, 0]`. Correct **only the test's expected shape**; preserve the parser's exact file-derived dimensions.
3. **Error-class preservation.** `DirectoryError` inherits from `ValueError`. The zlib exception wrapper was swallowing its deliberate `MAT_COMPRESSED_STREAM_UNBOUNDED_OR_INVALID` code and relabeling it as generic invalid. Preserve the exact boundedness rejection by exempting `DirectoryError` from the wrapper; do not accept overlarge compressed data.

Apply these three corrections without changing the original archive identity, frozen ten-height eligibility, shared-variable rule, binary-safe parsing bounds, all-member denominator, workflow clock, source guard, commercial-rights HOLD or prior schema002 failures. Repeat fixed synthetic suite once prospectively; if it qualifies, **only then** run the one already preregistered original-source attempt for the amended implementation. Preserve both hosted outcomes. No scientific numeric interpretation, additional dataset, keys, finance, spending or deployment.
