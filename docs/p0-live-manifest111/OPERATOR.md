# P0 live-source manifest qualification111 — operator and interpretation

This is an additive **read-only, key-free** composition-contract test of the *current released main-side financial source*, not a native account operation and not owner-source integration. Registered protocol: [PROTOCOL.md](../../campaign/p0-live-manifest111/PROTOCOL.md), immutable initial registration commit `5640ec69e3faedd39886707abf368c9fb7192012`.

On a Python 3.12 clean checkout with standard dependencies:

```sh
python3 -m pip install --only-binary=:all: -r requirements-commercial010.txt -r requirements-cycle004.txt numpy==2.3.5 scipy==1.17.0
python3 -B -m unittest tests.test_p0_live_manifest_closure111 -v
```

The tests import and execute **the actual** `connected_enterprise.finance.source_paths_for_manifest` and `source_identity` functions for five presently live manifest schemas, verify full file-byte SHA-256 inventories and distinct identities, then make private *source-only* temporary copies to exercise mutation, deletion and symlink refusal. They assert critical current caller interfaces exist. They **do not** open, modify, initialize, sign or recover Account/JournalAccount, claim any money, mutate customer state, or transfer source authority. The temporary clones contain no keys or account/recovery files and are discarded at test end.

Fixed expected outcomes: five well-formed current-main source closures bind to exact on-disk file bytes, and adversarial changes trigger a new source identity or refusal. A failed test is a real engineering failure and must not be reclassified; the current main source serves as **baseline for a prospective composed P0 runtime**, not as proof an older owner branch already supports these routes. If any source closure expands legitimately, this test must evaluate the **new current** declarations prospectively rather than retrospectively weakening the existing financial/identity guard.

For original P0 integration, the **exclusive financial owner** must still provide the latest authenticated original signed nonempty-queue checkpoint and safe writer transition; preserve old account/ledger identity, historical claims and permanent tails, implement authenticated source-version transition and exact source semantics, qualify crash/race/replay/fork behavior, and test actual due financial events. This compatibility test is only one prerequisite. P0 requires full source-matched test qualification, normal protected merge/release, actual public release download and resumed native audit. The source branch and this research/qualification PR are *not a substitute for those boundaries*.

No customer has been approached, no buyer consent or paid work was inferred, no external/model/API services were purchased, no credentials were created, no new simulated money or financing was attributed, and no US$3B profit or recursive capability claim results from green tests.
