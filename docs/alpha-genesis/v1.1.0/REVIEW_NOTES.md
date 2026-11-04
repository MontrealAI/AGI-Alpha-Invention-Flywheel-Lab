# Release review — edition 1.1.0

**ALPHA GENESIS FLYWHEEL Ω · 4 November 2026**

The original 1.0.0 numerical results were reproduced before revision. This review improves the research release; it is not external peer review, a production security assessment or an empirical validation of the proposed autonomous foundry.

## Substantive corrections

**Conventional replay control.** Edition 1.0.0 placed the selective result directly into the conventional-control field. The theoretical tie was correct, but the reported field was not a separately executed implementation. Edition 1.1.0 computes the conventional schedule independently by first-feasible-event assignment. Tests prevent it from calling the candidate scheduler and verify matching traces over 256 additional four-event sequences. The original 25-versus-5 counts and ordinary tie remain unchanged.

**Generated observer.** The original publication verifier compared the results JSON, but did not regenerate and compare every emitted artifact or execute the emitted observer. The revised verifier regenerates all four files, compares their bytes, and the test suite imports the emitted observer and exercises it on rational inputs.

**Optimized-mode integrity.** Core companion invariants used Python `assert`, which can be disabled with `-O`. They now use explicit checks. The suite runs in normal and optimized modes. This protects the stated computation checks, not arbitrary untrusted code execution.

**Input and manifest handling.** The release rejects malformed observation dimensions, inexact inputs in the exact arithmetic functions, invalid reserves, overwritten or symlinked outputs, empty/duplicate/unsafe manifests, missing required files, unexpected files and broken local links. Hashes remain unsigned identity checks, not an authenticity certificate.

## New scientific discriminators

The replay examples now include announced-but-inaccessible tools, access revocation with history preservation, and a newly possible route omitted from the recorded obstacle index. A conditional full-cost equation exposes when selective replay loses despite fewer evaluations: net savings are +17, −5 and −13 in three authored scenarios. These are abstract units, not observed commercial outcomes.

The paper specifies a frontier conversion contract, clarifies error allocation across multiple comparisons, and adds a release-engineering section distinguishing research publication, computational pilots, reusable capabilities, improved inventors and physical/commercial operation.

## Communication and deployment improvements

The release has a responsive reading page, a labeled interactive observation witness, straightforward reproduction instructions, versioned packaging, a static-site export tool, and a served-byte checker using the local expected manifest. The reader can immediately distinguish the delivered research from the proposed product.

Key frontier claims were rechecked against primary sources. The OpenAI mathematics citation now uses a confirmed immutable repository snapshot. The original private source documents remain excluded from public outputs. The original numerical result and build records are retained under `source/original/`.

## What the review does not establish

No frontier-model discovery campaign, new sensor, physical experiment, installed GENESIS product, actual buyer, transaction, profit, independent external review or public-host deployment was performed by these analytical and publication checks. The target remains exceptional scientific and commercial ambition with specific, testable claims.

## Browser-validation scope

Desktop and mobile layouts and arithmetic interactions passed an offline document-injection test with the exact CSS/JavaScript bytes. The fixture uses matching CSP hashes for those inlined assets. Direct file and loopback-HTTP navigation were blocked by the managed Chromium environment. Those whole-page navigation paths are not claimed as tested; the actual deployment must be checked on its destination host. The publication integrity checker separately tests served bytes, not browser policy or host security.

## Public filename-redaction revision

With author approval, the public publication replaces private input filenames with neutral source labels in the bibliography and provenance register. Attribution, source roles and hashes, analytical code, retained numerical results, and conceptual figures are preserved. The PDF is rebuilt from the revised LaTeX; the publication checksums identify this public revision rather than the originally supplied PDF. Earlier Git history is not claimed to be erased.
