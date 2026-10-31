# Temporal contract boundaries

The original implementation admitted an impossible complete lifecycle when only
clearing time fit the payment deadline. Its capacity admission also counted an
asset active at qualification even when the scheduled production occurred at or
after expiry. Narrow engineering counterexamples and seven baseline failures are
preserved in COUNTEREXAMPLES.before.json and BEFORE.log.

Configuration validation now requires production + acceptance + clearing <= the
inclusive native payment deadline before any output directory or Account is
created. One eligible-capacity list requires activation at or before qualification
and strict production-before-expiry. That list supplies both the slot count and
accepted-order capacity assignment. Future activation does not grant early
qualification capacity. Acquisition exposure rights and the independent auditor's
strict expiry check are unchanged. No default costs, prices or policy were tuned.

The regressions cover deadline equality, invalid precommit rejection, exact and
short expiry, activation boundaries, multiple assets, maximum slots, buyer
refusal without asset-index shifts, production crossing a day, and deterministic
preparation across a saved-state JSON round trip. Existing signed source/state
bindings still govern actual resume; no old queued intent or original result is
rewritten by this change. Broader composed release qualification remains separate.

The read-only impact scan reassembles and byte-verifies the original public
package, its CRC, frozen identity and all eight source-bound result hashes. At
original source abc262bf, all eight configs fit the full deadline, all 20 actual
capacity uses are valid, and eligibility is unchanged at all 560 planning events.
These temporal defects therefore do not alter those original eight trajectories.
They remain historical evidence at their original source; this scan does not
qualify a run of the repaired implementation. Reproduce with:

`python3 evidence/completion015/temporal-repair/scan_history.py`
