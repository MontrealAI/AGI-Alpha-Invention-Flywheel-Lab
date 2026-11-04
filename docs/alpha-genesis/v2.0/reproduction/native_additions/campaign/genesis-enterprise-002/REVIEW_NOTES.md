# Release review

The previous download link failed because the requested ZIP was never created. This edition rebuilds the package directly from available staged source and a fresh source-bound native run on 2026-11-04. A validation bug (the string-valued `continuation_funding_policy` was passed through an integer validator) was corrected in `genesis002/decision.py`.

**Current verified checks:** 38 decision and frontier-observer tests pass. A fresh six-delivery run using the published native source succeeded, its separate local audit returned `accepted: true`, and resume returned the identical final result. The full 62-test suite did not finish within the current recheck window; do not treat it as freshly certified. The earlier 62-pass narrative belongs to prior work, not a currently verified full-suite run.

**Source and scope:** New additive files only. No customer data, account databases, private keys, private action tapes or credentials are included. Native reference is historical commit `4a87b455...`, not current `main`; this is not current-main CI/release qualification.

**Economics:** Buyer values, costs and orders are authored hypothetical simulation values. Modeled results do not evidence observed commercial success, real earned money, general autonomy or superior opportunity discovery.

**What to do next:** Apply the patch to the repository, run exact-head CI against current `main` after reviewing compatibility, then produce separately registered evidence for real demand and new capabilities within authorized limits.
