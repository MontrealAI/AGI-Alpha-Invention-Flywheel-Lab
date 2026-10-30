# Preserved report-summary counterexamples

COUNTEREXAMPLES.json binds the two forged reports and the original checkers that incorrectly accepted them. REPAIRED_REVIEW.json binds unchanged native reports and the new validators. No incorrect value was found in the native reports.

The forged reference artifact changes summary claims, not raw measurements. Its26raw files are byte-identical to the original first-run reference observations preserved in evidence/consequential009/reference-raw-r1.tar.gz; RAW_DEDUP.json verifies that equality. Restore the original bytes with the standard helper, then copy that raw directory into reference/forged-artifacts/raw to replay the archived old checker. This is restoration of preserved bytes, not generation of a new original.

The normal31 independent regression tests reconstruct their own temporary forged copies from those restored native artifacts. No temporary test receipt overwrites the original counterexample or source. All earlier accepted receipts retain the validation scope of their old checker edition;153/170 new checks are not transferred retrospectively to them.
