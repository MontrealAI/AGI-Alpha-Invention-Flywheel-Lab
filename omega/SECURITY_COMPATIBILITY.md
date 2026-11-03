# Compatibility product: local filesystem safety

This prospective edition hardens `omega.compatibility`, the self-hosted finite-state adapter construction instrument introduced in PR #198. Its flagship dependency is safe delivery and recovery of the constructed adapter, not a new economic or invention claim.

## Supported use
Use Python 3.12 on a local Linux filesystem in a directory controlled by the operator. Supply authorized, deterministic, safely resettable queries and a justified state bound. This patch neither establishes those prerequisites nor contacts an external system.

```sh
python -m omega.compatibility --output /absolute/new/adapter
python -m unittest omega.test_compatibility omega.test_compatibility_security -v
```

Output paths and all ancestors must be real directories, not symlink aliases. Select a new private output directory when an existing path conflicts. Keep the checkpoint and original input for a resumable interruption; never replace another owner's files or copy a financial balance.

The default per-file input and output bound is 16 MiB. `--max-file-bytes` adjusts it explicitly for a justified local workload. Library callers can set `max_file_bytes`, `max_checkpoint_bytes` and `max_document_bytes`. These are resource-safety bounds, not market or business-size ceilings.

## Implemented protections
- Directory-descriptor traversal and no-follow, nonblocking regular-file reads reject symlinks and FIFOs. Verified package bytes are reused during acceptance.
- Unique temporary files, fsync and atomic replacement protect individual checkpoint writes. Immutable outputs use atomic no-clobber publication; existing hard-linked files are not truncated.
- Nonblocking advisory ownership locks reject cooperating concurrent builds before probing. Standalone checkpoint saves reject a stale writer rather than replacing newer state.
- Malformed adapter and manifest shapes fail closed before inappropriate oracle calls. Documentation lookup refuses unsafe, oversized or non-UTF8 inputs.
- CLI filesystem failures return structured `LOCAL_BUILD_FAILED` output and a nonzero exit rather than an uncontrolled traceback.

## Troubleshooting
`OUTPUT_ALREADY_IN_USE`: wait for the actual owner to finish; do not delete its lock. OS process exit releases the advisory lock.
`CHECKPOINT_CHANGED_BY_ANOTHER_WRITER`: preserve both callers' inputs and reopen the latest checkpoint with one owner.
`LOCAL_FILE_BYTE_LIMIT_EXCEEDED`: inspect the intended input size and explicitly choose an appropriate bound; do not remove validation.
`REGULAR_LOCAL_FILE_REQUIRED` or a symlink error: use ordinary files in a private real directory.
`EXISTING_DELIVERY_CHANGED`: preserve the existing package and choose a new destination.
A partial directory is not an accepted product: all manifest members, exact hashes and semantic acceptance must succeed.

## Qualification and limits
The reviewed module was reconciled with PR #198 head `c4926f87f6c3ee9972bbaddfa595972b2d95e066`; its original blob is `0d76d94d1476f656874e86d50ba2f6d32a72f363`. The candidate module SHA256 is `a7946b62f24cca2a6f8cf956903280553c471def45e2df6c3257c40f3e3495a5`.
All 45 focused Linux tests passed after repository-import adaptation: 18 existing compatibility tests and 27 security tests, including process contention and termination, stale writers, links/FIFOs, file-size growth and malformed artifacts. The module and exact patch were independently reviewed and retested before this integration.

Full composed repository, financial source-binding, campaign smoke, final-head CI, merge, release and downloaded-release operation are not established by these focused tests. This is a draft prospective correction, not production certification.

Advisory locks cover cooperating writers, not malicious same-user interference or privileged attackers. Whole-package multi-file crash atomicity, Windows and network/distributed filesystems remain unqualified. Byte bounds are not a CPU/memory process sandbox. Existing finite learning and conformance limits are unchanged.

## Historical evidence
No frozen operating source, accounts, financial results, campaign registrations or historical specialist checker hashes are changed. Existing packages and experiments remain qualified only against their original source. Regenerate and requalify a prospective product under this edition before claiming its acceptance; never rewrite an old source hash to make it pass. The PR #198 economic comparison remains incomplete.

Lesson: validate reads as well as writes, retain verified bytes, and enforce cooperating ownership at the actual output boundary. Continue with composed qualification before release.
