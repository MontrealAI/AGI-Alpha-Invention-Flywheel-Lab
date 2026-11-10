# HARNESS 68 publication recovery

This workflow repairs the release transport for the already qualified source
`68c2c1a00c78579b76788955a87f74dace8cc404`. It does not change the customer archive,
rerun live models, rerun macOS or Windows qualification, or promote the candidate's
scientific or commercial status.

The original release job
[129751761654](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42786474290/job/129751761654)
failed while uploading `Darwin-CODEX-HOST-VERIFICATION.stderr.txt` with HTTP 400
“Bad Content-Length”. Published-archive operation and owner assembly were not
reached. The failed attempt's evidence remains part of the recovery inventory.

## Activation and source separation

Only a push changing one of the four listed recovery files on
`recovery/harness-68-publication-20261110` triggers this dedicated workflow.
Creating Git blobs or reviewing the draft does not activate it. The workflow
checks out recovery controls at the triggering commit and the product separately
at the exact qualified commit. Both checkouts disable persisted credentials.

It uses a standard public Ubuntu runner and the qualified source's locked DOM
and browser test dependencies. Model weights and live inference are not needed.
The GH_TOKEN environment variable is set only for acquisition, base publication,
published-asset download and final publication. The checkout actions authenticate
without persisting credentials. Product verification and owner assembly run
without publication credentials; the helper also sanitizes product subprocess
environments.

## Evidence and publication rules

The transport helper pins the original source, artifact IDs and digests. The
customer ZIP must remain byte-for-byte unchanged, with SHA-256:

```text
2b7d979d84290f57d8865102f782b3571e2b42d9354080dced003e4a326b757a
```

The phases are sequential: acquire, prepare, operate received bytes, publish base
assets, download published bytes, restore represented empty diagnostics, operate
published bytes, assemble and visually verify the owner handoff, and publish the
final owner assets. Tests run before acquisition.

The credential-free prepare and owner-assembly steps hash their completed base
and final state inventories into fixed Actions step outputs. Later credentialed
phases require these independently captured hashes before publication or download;
the helper also revalidates the pinned inputs, inventory bytes and relevant
receipts. Product execution cannot silently substitute a revised inventory.

A zero-byte auxiliary diagnostic is represented in a nonempty transport inventory
with its original name, byte count and SHA-256, then restored as an exact empty
file before downstream reconciliation. It is not deleted from the evidence,
padded, substituted, or counted as a successful test. Customer archives and
nonempty evidence retain their exact bytes. Existing release assets are accepted
only when their identities match; mismatches fail instead of being overwritten.

Matching, already uploaded original assets are reused. Repeatability is bounded:
a fresh recovery after partial recovery publication can observe a different
prior-release snapshot or auxiliary ZIP hash and safely refuse. This workflow
does not promise arbitrary automatic retries or general resume behavior.

One narrowly authorized exception applies to a zero-byte starter diagnostic in
an authenticated, matching, unpublished draft release. The helper must verify
its empty content against the independent original artifact, preserve its asset
metadata and exact empty bytes in the auxiliary ZIP, and recheck the draft and
asset immediately before deleting that failed starter. It must never delete an
uploaded, nonempty or public release asset. This exception does not replace or
alter the customer ZIP or other evidence.

The workflow preserves the complete public recovery directory on success or
failure, including original artifact ZIPs and the failed publication receipt.
It does not use a replacement source build or discard failed model results.

## What a successful recovery establishes

Success requires operating the received and redownloaded customer ZIP, reconciling
the original results, and rendering the assembled owner page with its 22 delivery
categories, contained local links, exact source identity and 390-pixel viewport
check. These checks establish package and handoff operation within their recorded
scope; they are not a full accessibility audit or proof of general invention.

The model evidence's overall FAIL and the optional quote checkpoint or result
remain visible as recorded even when its mandatory core checks pass. Incomplete
quote evidence remains incomplete; it is not presented as a completed outcome. Live provider access, commercial approval,
market validation and scientific superiority remain separate qualifications.
The owner handoff retains candidate status and `commercially_ready: false`.

Final links belong to the source-specific
[candidate release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/alpha-genesis-harness-v0.3.0-rc-68c2c1a00c78).
Do not claim that an owner bundle exists or that a phase passed until its actual
receipt and published asset are available. The owner ZIP is for review; only the
untouched customer ZIP is the potential storefront upload. All Squarespace
actions remain with the owner.

## Recovery transport attempt 1

The recovery-control commit `669136de5a47251dffdd78433f555ced46324ea4`
passed all 39 synthetic tests in 0.213 seconds on 10 November 2026, then
[run 42800283531, job 129775709257](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42800283531/job/129775709257)
refused the first artifact download with HTTP 415 at 10:34:47 UTC. No release
publication step ran. Acquisition had not written any files, so the always-run
artifact upload reported no files; the Actions log is the original evidence.

The Actions artifact archive endpoint requires the GitHub JSON Accept header
for its download redirect; release asset binary downloads use octet-stream.
The correction separates response-byte handling from the request Accept header,
keeps redirected storage requests unauthenticated, and adds direct/redirected
transport and actual acquisition-call regressions. The 42-test suite must pass
before the corrected acquisition runs. The five original artifact identities,
customer ZIP, model evidence and product source remain unchanged.
