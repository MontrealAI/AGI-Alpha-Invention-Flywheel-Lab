# Durable selected public evidence

This directory retains **one** already-public, key-free selected control case. It is not a new simulation, the whole 63-case campaign, or authority to resume a private account.

- File: `growth067-dev-100000-distribution_first.zip`
- Bytes: `2257538`
- SHA-256: `f7415b3200eb0984961b6c17e7a90bf8ce1559559ebf3ec425bb025a43480c95`
- Original Actions artifact: `13157389058`, run `41467872078`
- Executed source: `8d615b1e850f81838b7ff77f87fee8964bf1f280`

The original Actions artifact expires on 9 November 2026. This copy preserves the exact same bytes in repository history; its contents and economics are unchanged.

## Content and privacy boundary

Independent inspection found exactly 125 regular JSON members: four package files, 61 decision records, and 60 delivery records. Paths match the executed `growth067.ci.pack` whitelist and manifest. There are no private account/recovery files, private signing keys, API secrets, symlinks, path traversal, or extra members. Public action proofs and commitments remain present. The generic journal field named `key` is an operation identity, not a private cryptographic key.

This is public replay evidence only. It cannot grant private account custody or permission to transact. Do not substitute its bulk-modeled quantities for observed customer work.

## Verify and replay

Verify the downloaded archive:

```sh
sha256sum growth067-dev-100000-distribution_first.zip
```

Use the public source at the exact executed commit. From any location, provide its checkout path to the standalone replay script:

```sh
python3 replay_selected.py --source-checkout /path/to/executed-source --archive growth067-dev-100000-distribution_first.zip --output /tmp/growth067-public-replay.json
```

The script verifies the archive identity, member whitelist, 68 source hashes, the legacy engine's two additional pinned package bootstrap files, and result digest before replaying the public native, operating and full-modeled-cost audit in a fresh temporary directory. It does not reopen, copy, or resume a private account, perform economic production again, make model calls, or contact any service.
