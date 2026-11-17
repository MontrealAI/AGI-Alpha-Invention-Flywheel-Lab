# Chronology correction — qualification and owner-current composition

## Immutable evidence and witnessed result
- Original owner intake source: PR #423 at `fcbc6961321ee67a72ba69276b4b37bcccaeba8a`.
- Frozen review protocol (before tests): `60e3393fa42630a80ae44d7677f3007186e4e759`, stored in `CHRONOLOGY-REVIEW.md` without rewriting the frozen text.
- Test-first head: `a4777339c0c631aa099c1edb68aa41a6cd6bb2c9`; hosted run [#43993918927](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43993918927) **FAILED** as preregistered: both new negative assertions expected a ValueError and did not receive one; unchanged owner tests passed. This remains a failure.
- First prospective corrected head: `6664587719b37be5a7f8fe3f17da6a25a10bb487`; hosted run [#44002016125](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44002016125) **SUCCEEDED** at the exact head. Logs show 25 conversion tests, including the two registered chronology regressions, and 30 reservoir tests passing, plus the source workflow's unchanged ALPHA economic and native-finance commands. No real payment, buyer, model inference or authoritative treasury was exercised.

## Prospective owner-current composition
- Independently checked that the owner's latest source at `0edbe87d20f5c6496f844059e3575a9181e07901` retained the **exact unchanged** original `frontier_bridge.py` blob `a2c7476b04b66c35eccee83cb716aa66af339bd8`. Its new changes are in the buyer signing, delivery verification, external-test payment protocol, source kit and other integration code, not that chronology gate.
- This reviewer-only merge composes the owner-current tree with **one narrow chronology guard** from the first corrected head and **both original registered tests**, preserving all **23 owner-current conversion tests**, for **25 unique conversion test methods**. It retains the unchanged frozen protocol and this evidence record. It does not rewrite the owner branch, sign an order, move a cash balance, or merge into main.
- The merged reviewer head needs **new exact-head CI**, source-kit extraction and owner review before any integration or release claim. Do not carry over run #44002016125's PASS to the composed head without that evidence.

## Scope and next decision
The guard checks `before.observed_on <= old.run_on <= intake_utc_day` and `after.observed_on <= new.run_on <= intake_utc_day`. It is a **chronology consistency check**, not time attestation, actual replay provenance, independent buyer validation, complete-cost reconciliation, real revenue, historic impossibility or frontier novelty. Fixed-source and scenario results do not establish customer demand. Keep the currently qualified released champion and original financial/signing owner; no transaction, outreach, spending, paid API, key or private account was involved. A failing composed qualification must remain a failure until a separately reviewed repair.
