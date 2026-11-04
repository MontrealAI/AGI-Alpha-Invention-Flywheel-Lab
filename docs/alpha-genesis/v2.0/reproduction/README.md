# Native reproduction: historical source only

`native_reference.zip` is the exact inner source archive from the supplied public connected014 release artifact. `native_additions/` is the corrected additive Native Enterprise 002 source, not a patch to finance/account semantics.

Historical native commit: `4a87b455373be72811ad3a0c654a116c3604a374`.

These files are an experimental reproduction, **not current-main or hosted CI qualification**. No repository mutation is performed.

## Environment

A local POSIX filesystem, Python, and the reference dependencies are required. The completed paper recheck used CPython 3.13.5. The reference dependency file contains:

```
cryptography==50.0.2
cffi==2.1.1
pycparser==3.11
```

Use a local virtual environment for any dependency installation. The reproduction driver installs nothing and makes no network or model calls.

From the publication root:

```sh
python3 reproduction/reproduce_native.py --work /absolute/new/private-genesis-reproduction
```

The driver checks the historical archive hash, extracts source, copies the additive changes, runs the native suite, executes four independent six-cycle simulations, independently audits each, and checks unchanged resume.

The output must not exist. This is deliberate: the script must never silently reseed or overwrite an existing account. A failed run retains its state and evidence. For intentional account continuation use the underlying native resume command on its original source; do not rerun the reproduction initializer on that directory.

**Keep the working directory private.** Native accounts generate local simulation authority and recovery files. `PUBLIC_SUMMARY.json` is the only automatically summarized sharing output. Such local authority is neither a cryptocurrency wallet nor permission for real commerce, but should not be exposed.

The other subdirectories hold the supplied finite decision and composition prototypes, with original scenario assumptions and tests. They are not live frontier discovery systems.

The byte-preserved source snapshots include their earlier release/status notes. Those historical notes are not rewritten. This paper’s fresh test transcripts and four reproduced accounts supply the newer verification described in edition 2.0.
