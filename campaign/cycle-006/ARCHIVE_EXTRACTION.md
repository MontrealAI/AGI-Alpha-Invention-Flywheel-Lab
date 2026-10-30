# Supported source extraction and repackaging

The original mechanism-completion release remains unchanged at SHA-256
`9e80e3708f430b0a5ac18c8580eb2320febb213cbda63cc7eaa00be81b78e95d`.
Its ordinary extraction retains `ARCHIVE_MANIFEST.json`; its original full suite
then fails one of 94 tests with `ARCHIVE_RESERVED_MANIFEST`. The source and
failure receipt are preserved under `evidence/cycle-006/extraction006/`.
The earlier validated-extractor success remains a distinct, valid result.

New archives can use either procedure after checking the published ZIP digest:

```sh
python -m zipfile -e DOWNLOAD.zip /tmp/alpha-ordinary-NEW
cd /tmp/alpha-ordinary-NEW/AGI_ALPHA_Mechanism_Completion
python -m unittest discover -s tests -v
```

Ordinary extraction is intended only for a trusted digest-checked release, since
standard unzip is not the laboratory's path or identity validator. The laboratory
extractor validates every path, manifest entry and payload hash before creating a
new destination and consumes the archive's packaging metadata:

```sh
python -I /path/to/trusted/flywheel/archive_v2.py extract DOWNLOAD.zip /tmp/alpha-validated-NEW
cd /tmp/alpha-validated-NEW
python -m unittest discover -s tests -v
```

When the packaging manifest remains in an ordinary extraction, `build` now
requires its exact payload set and hashes to match before creating output. It
omits only this successfully validated packaging record, preserves its original
bytes, and writes a fresh packaging manifest. Missing, added, changed, ambiguous
or malformed inputs refuse; an existing output is never overwritten. Normal
Python cache and Git directories remain excluded under the original policy.
This verifies identity, not scientific or commercial truth.

For authorized development edits, first use the validated extractor to obtain
the checked payload tree without a stale packaging record, then construct a new
source identity. Do not remove or rewrite historical manifests to make a modified
old snapshot appear unchanged. The new `archive_v2.py` requires its own cycle-006
source freeze; cycle-005 frozen identities and receipts are not recertified.
