# Independent actual-published download check

PASS in the declared engineering scope. This check downloaded the actual public release asset, verified its GitHub SHA256 and trusted source-B freeze, independently checked all 5,289 manifest payloads, and extracted under a new temporary directory with no Git repository in its ancestry. Source imports came from the extraction, with a clean environment and user site disabled.

Executed from the extracted source: 94 unit tests; 11 verifier tests; documented `run_completion.py`; rerunnable source-A false acceptance and source-B strict refusals/verifier-source binding; original edition 127 checks and replay; all 22 unchanged cycle004 identities and replay. All payloads remained unchanged after execution. The source-matched clean-release workflow separately repeats the owner phase-code execution; this check independently pins its 39 files and v2 protocol/verifier freeze.

`REPORT.json` and individual logs contain exact commands, return codes, durations and identities. `DOWNLOAD_RECEIPT.json` binds the public URL, GitHub digest, qualification digest and report. The release ZIP is not duplicated here. Metadata reports `immutable:false`; this is a published hash-identified prerelease. No release or candidate source was changed.

Reproduce after downloading the linked asset to `DOWNLOADED.zip`:

```sh
python verification/cycle005_published_asset.py --archive DOWNLOADED.zip --sha256 9e80e3708f430b0a5ac18c8580eb2320febb213cbda63cc7eaa00be81b78e95d --metadata evidence/cycle-005/verifier-published-download-metadata.json --output NEW_PATH
```

This independent check used 64.493 seconds wall time. It verifies this exact artifact on the installed Linux/Python/dependency environment, not fresh scientific performance or commercial success.
