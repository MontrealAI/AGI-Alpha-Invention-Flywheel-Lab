# Numerical execution history

The prospective source freeze `1d400d7ac4a0f21fc7faf5892f3161b713ce16390ce439fad38de10df99dc86e`, published at source `6b3e7f290c44aae4666295bcfad9229623ff47b7`, ran the registered numerical evaluation. The process failed while serializing the result because a NumPy boolean in the probe menu was not JSON serializable. No scientific result file or accepted verdict was produced. The original empty output directory and public source history are retained; no score was silently accepted.

The correction converts the already computed voltage separation to a Python float, so its comparison produces a serializable boolean. It changes no model, seed, acceptance threshold, probe action, comparator or numerical outcome calculation. A regression checks JSON serialization. The next freeze `FROZEN_STAGE_B_SERIALIZATION_FIX.json` binds this corrected source before the same registered evaluation is rerun into a different output directory.
