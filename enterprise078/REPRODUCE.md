# Reproduce Enterprise078

Run Python 3.12+ with the repository's pinned `requirements-commercial010.txt` installed. Use a clean checkout of the scientific freeze commit and a new absolute output directory. No API, credential, live buyer or physical instrument is used.

```sh
python -m unittest enterprise078.test_enterprise078 -v
python -m enterprise078.campaign run --output /tmp/enterprise078-reproduction
python -m enterprise078.campaign audit --output /tmp/enterprise078-reproduction
```

The producer freezes its source before creating separate original accounts. Keep the private directory locally for recovery; never publish it. Public replay verifies exact manifests, registered capital, contracts, request namespaces, accepted output bytes and complete native journal arithmetic. It cannot authenticate an owner's HMAC without private authority. Opening the same original accounts is tested without changing their financial history.

`gateway` runs the separately labeled 128-by-eight development gateway. Its original source and outcome are pinned to `df8197d27266687b9971afa13143d38d0a310af6`; do not use later code to rewrite that development record.

This is an authored finite comparison, not blinded physical experimentation. Each recorded accepted output is qualified to the stated digital model. Source and hypothesis authors share a host; separate implementation and real local SQLite checks provide bounded corroboration, not an external scientific validation. Real instruments need independently supported operation identity, readback, timing and physical calibration contracts.

## Public evidence replay, including the tested funding revision

From the published PR head, run:

```sh
python -m enterprise078.replay --output /tmp/enterprise078-public-replay
```

This verifies the two archive hashes, restores only public evidence, copies exact original scientific source by digest, applies the preregistered revision patch in a separate directory, checks every registered case and independently invokes the canonical native audit from each matching source. It does not open original private recovery directories or manufacture new native collections. A fresh directory is required. The public-only native replay is the qualified portable evidence path; campaign authoring and actual physical deployment remain different operations.
