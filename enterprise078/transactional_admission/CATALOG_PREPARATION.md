# Inactive catalog preparation

The missing native upgrade has three distinct parts: bind the candidate to the
original authority/history, activate explicit new catalog semantics without
rewriting the old tape, and independently replay the combined old/new history.
This increment implements only the first part. There is no activation API.

`catalog.prepare` uses existing `BusinessAccount.seal_checkpoint`; recovery uses
its existing `verify_checkpoint`. The canonical native signer remains private.
The signed state binds the exact typed request, accepted DB/CSV byte hashes,
candidate source file hashes, prior proposal digest and sequence. The native
checkpoint binds original source/manifest, contract and financial-history prefix.
The old manifest, financial journal and tape are not edited. A lab job name cannot
stand in for a transactional output.

Private proposal files use exclusive creation, canonical bytes, file/directory
fsync and the existing native account's POSIX owner lock. Torn records fail closed
on reopen; no automatic overwrite, re-signing or reseeding repairs them. Keep the
returned expected-head receipt in the caller's durable recovery state. Supplying
that expected head is mandatory to detect removed tails; without an external
anchor, rollback of all local files cannot be detected. This is local POSIX
custody, not distributed consensus or protection from a malicious filesystem.

Original account operation is **not enabled** by these records. They are marked
`PREPARED_NOT_ACTIVE`, and `native_catalog_admitted` is always false. Native
activation must revalidate available delivery bytes and complete offer economics;
a past acceptance receipt alone does not prove current artifact availability.
Candidate source changes require a new reviewed proposal, never changing an old
proposal's bound digest. Keep proposal envelopes private with recovery state;
publish only key-free summaries.

## Executed scope

Protocol published before implementation at
`2bbbb607a3cad3036d3571dd9d56f274ad754fc4`. Eight controls execute in a separately
identified fresh test account through the exact staged original native runtime.
Two proposals survive authenticated reopen, a subsequent zero-value native event
preserves their prefix binding, and the fixture's once-incurred100USD loss remains.
Tampered activation, changed candidate source, stale expected head, missing tail
and lab relabeling are refused. The existing no-reseed controls run first.

```sh
python -m unittest enterprise078.transactional_admission.test_admission.NativeBoundaryTests -v
python -m unittest enterprise078.transactional_admission.test_catalog -v
```

These are exposed development controls, not independently approved migration or
fresh commercial confirmation. No proposal was written to original authority.
See [key-free fixture evidence](../evidence/CATALOG_PREPARATION.json). Full
construction/model/host costs remain unknown; no commercial profit is attributed.

Next implement and independently qualify the activation/replay portion on fresh
fixtures before touching the original account: a new catalog event must preserve
the old financial prefix and liabilities and route historical events through the
exact old sources. A copied balance, changed original manifest/source pin, dynamic
monkeypatch bypass or false positive expected_net is not a transition.
