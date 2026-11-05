# Connected014 released-wheel → GENESIS source-integrity repair 087

## Prospective protocol frozen before changing tests or implementation (5 November 2026)

**Base:** main `8c833ac2f1f164d7f2b0f021113ed0d1bca46e61`. This is a *new corrective branch*, not a modification of the released tag or its immutable records.

**Immutable motivating failure:** GitHub Actions run [42025891338](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42025891338), job `127257346385`, actually downloaded and operated the newly published `connected014-8c833ac2...` release. The release and publish phases succeeded, along with the six-command native connected operation, wheel utility and V4, but **downloaded GENESIS failed**: `ValueError: EXACT_EXTRACTED_SOURCE_REQUIRED` at `scripts/qualify_genesis_release.py:71`. All subsequent downloaded-source probes were skipped. This *remains a failed overall release operation*. The previous release and its source hashes are never rewritten.

**Causal hypothesis, not an observed file listing yet:** the wheel's nested interpreter uses `python -I` while relying on `PYTHONDONTWRITEBYTECODE`; isolated mode ignores `PYTHON*` environment variables, so importing `flywheel_wheel` can leave extraneous `__pycache__/*.pyc` under the *shared extracted release directory*. The wheel's source identity hashes only declared files and would not catch these extras, whereas GENESIS rightly demands an exact complete source tree. The failure may also have another cause: retain the original failure and reject a repair that merely bypasses source-integrity verification.

## Frozen C0–C4 criteria

- **C0 (clean original):** the canonical wheel release test starts with exact selected source-path inventory in a newly extracted directory, not a checkout or an alternate account.
- **C1 (no extras):** execute the actual released wheel utility with a Python interpreter that explicitly disables bytecode generation even in isolated mode; after 48-stage precision operation, recursively compare the exact *complete file inventory* against C0. No ignored extra files, not merely unchanged hashes of selected files.
- **C2 (tampering):** the existing source-file tamper test must still fail closed and retain only a compact, key-free rejection receipt.
- **C3 (composed downloaded boundary):** source-matched clean-package tests and actual new public-release download must execute wheel, V4 and GENESIS sequentially on actual released bytes with six zero-exit GENESIS commands, independent original-account audit and key-free output; exact source-tree enforcement remains unchanged. Do **not** substitute a clean second extraction just to mask leaked files.
- **C4 (compatibility and resource):** existing native, financial, source/archive, old tests and platform clock/timeout guards remain unchanged; follow normal exact-head CI, independent review, protected PR merge, release and downloaded-byte audit.

**Permitted change:** smallest subprocess launch fix in `scripts/qualify_released_wheel035.py`, plus a regression in the existing `tests/test_flywheel_release_035.py`; no financial implementation, account, signed operating state, old experimental allocation, source guard or archive-size guard changes. Tests are preregistered before code. Historical failure remains failed. Fresh code/release is a *new* engineering result, not external commerce, economic confirmation, financing, new profit or recursive invention.

**Acceptance:** technical evidence only, never automatic publication/commercial adoption; original and new release must be named separately. If the precise fault is not reproduced or another source writer emerges, preserve failure and investigate rather than weakening `EXACT_EXTRACTED_SOURCE_REQUIRED`.
