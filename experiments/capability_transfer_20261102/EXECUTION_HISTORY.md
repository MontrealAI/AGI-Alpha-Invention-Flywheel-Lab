# Numerical execution history

The prospective source freeze `1d400d7ac4a0f21fc7faf5892f3161b713ce16390ce439fad38de10df99dc86e`, published at source `6b3e7f290c44aae4666295bcfad9229623ff47b7`, ran the registered numerical evaluation. The process failed while serializing the result because a NumPy boolean in the probe menu was not JSON serializable. No scientific result file or accepted verdict was produced. The original empty output directory and public source history are retained; no score was silently accepted.

The correction converts the already computed voltage separation to a Python float, so its comparison produces a serializable boolean. It changes no model, seed, acceptance threshold, probe action, comparator or numerical outcome calculation. A regression checks JSON serialization. The next freeze `FROZEN_STAGE_B_SERIALIZATION_FIX.json` binds this corrected source before the same registered evaluation is rerun into a different output directory.

The corrected source was published in commit `f920b361ebb140ab08758afe7d0fb6a5f43ee800` before the rerun. Its freeze SHA256 is `05bb81b18d96b1e4a6ab1110a26974dfe5cef2002bf8ac33e6141c160ceb408b`. The run produced original result SHA256 `4c36506559fb88cdcfde81f76a12daf0af3ed369a67b0306499b0ecea2d39a8c`: numerical checks passed; the anticipated impossibility criterion did not. Recorded CPU 71.8549 s and wall 71.8591 s cover the instrumented evaluation interval, not all exports, construction, included assistant use or the complete session.

A separately labeled post-result midpoint diagnostic then found a common prediction accepted in both original worlds. No frozen source, model, horizon, threshold or original receipt was changed. The diagnostic supersedes the old unconditional abstention recommendation only for this finite task; see `CLAIM_CORRECTIONS.md` and `INDEPENDENT_NUMERICAL_REVIEW.md`.

The frozen numerical experiment was replayed successfully by the numerical job in hosted workflow run `41487782250` at source `34b56f4052c7defaab4c18327f8051d60d4abe6b`. This is an implementation replay, not physical validation or a business outcome.
