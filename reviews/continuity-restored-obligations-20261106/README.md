# Independent CONTINUITY Ω restored-obligation provenance review

**Scope:** isolated review of owner PR #279, pinned source `6cd7e1bb7197cabdf8f3d093eead662cde5351f4`. This branch adds only tests and this short finding; it does **not** alter the owner branch, the canonical enterprise, any financial account, historical evidence, or the published runtime.

**Flagship dependency:** a post-disruption business commitment must be independently reconciled without reissuing fulfilled work or inventing missing orders. An ambiguous restored view cannot certify that outcome. These cases test an acceptance prerequisite, not an invented market or new business.

## Two independently specified counterexamples

1. **Correctly absent cancellation.** A historical order for 600 units is `CANCELLED`; the restored **outstanding** view contains no entry. There is no missing active obligation. Existing `restored_anomalies` reports `MISSING_FROM_RESTORED_SNAPSHOT`, a false positive that could trigger unneeded work.
2. **Unobservable fulfillment progress.** The source events accept 1,000 and 800 units, amend the first to 1,100, then fulfill 100. The true outstanding requirement is **1,800** units. A restored snapshot containing only gross quantities 1,100 and 800 (total **1,900**) has no fulfillment state/IDs. The prototype constructs the correct 1,800-unit handoff from the separate source history, but the snapshot comparison returns an empty diagnostic, so this *restoration check* cannot establish that completed work is preserved. This is a **missing proof boundary**, not evidence of a real duplicate delivery or false native account balance.

## Executed red-run receipt (retained, not revised into a pass)

The first exact-head review workflow [42296081697](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42296081697) completed **FAILURE** on review head `60a796dd4d716614215edf168f016b0e4212998f`. It ran 48 tests (46 pre-existing plus two new), with **one** failed assertion: the correctly absent cancellation was reported `MISSING_FROM_RESTORED_SNAPSHOT`. The gross-only fulfillment test unexpectedly passed because its condition also accepted an unspecified independent-audit failure. That was an insufficient *test oracle*, not evidence that restoration provenance was established. The second assertion has now been tightened prospectively on `0fd3c1d613333f052a81912515b0d5ad5240ae8f` to require an actual restoration-comparator finding; the first failed run stays failed. A new exact-head workflow outcome, if any, must be reported separately.

## Frozen acceptance / expected initial outcome

Run on the exact stacked source:

```sh
python3 -m unittest discover -s tests -p 'test_continuity_restore_provenance_review.py' -v
```

The two new checks are **expected to fail on the owner baseline**. This is deliberate: a red source-matched test is a preserved finding, not a failed historical run to erase or a passing CI to manufacture. The constructor may instead fail closed, or the new restoration evidence must distinguish completed from outstanding obligations; a passing synthetic audit with no finding for unverifiable fulfillment progress is not sufficient. Preserve original 29+17 baseline tests and independently implemented replay. Fix both constructor and verifier consistently, not by suppressing the finding or rewriting old synthetic source events.

**Compatible repair criteria:** define the recovered snapshot's meaning and provenance explicitly; keep inactive/canceled/fully fulfilled records from being counted as outstanding; bind shipment/fulfillment identifiers and source sequences to a caller-controlled authenticated reference where available; reject or label missing provenance unverified. Version the schema if semantics change. Maintain source-pin checks, duplicate-JSON/type guards, capacity/rights checks, and platform workflow contract from main PR #280. Test tampering, replay, cancellation, partial fulfillment, full fulfillment, reinstatement if supported, and crash/resume separately. No signature or caller-held hash alone proves real-world data custody.

**Commercial verdict:** NO DEPLOY. There is no outside paying customer, valid supplier consent, measured real delivery, complete actual cost bill, new revenue, or verified stronger-than-conventional recovery advantage. Neither a new test nor later green CI can establish those. Signed native-capital handoff and exclusive account ownership remain independent blocked questions.

**Review ownership:** the original #279 owner retains their implementation and integration rights. This is an additive research/challenge branch to merge or decline after source-specific review. It is *not* authorized to replace the published main source, the independent verifier, or a financial authority.
