# Reproduce Enterprise078

Use Python3.12+ and the repository's pinned `requirements-commercial010.txt`. The current repository retains the unmodified main financial runtime. Historical Enterprise078 science runs from its exact, separately staged source.

```sh
python -m enterprise078.runtime --output /tmp/enterprise078-science
cd /tmp/enterprise078-science
python -m unittest enterprise078.test_enterprise078 -v
python -m enterprise078.campaign run --output /tmp/enterprise078-reproduction
python -m enterprise078.campaign audit --output /tmp/enterprise078-reproduction
```

The `run` command creates explicitly fresh reproduction accounts, never a continuation of an existing enterprise. A new absolute output directory is required. Keep original private authority locally. Historical original-account continuation requires that original private state and the corresponding original source; public exports cannot recreate it. Do not invoke `enterprise078.campaign` directly from the current repository root, whose financial runtime is intentionally different.

From the published PR checkout, replay the actual public evidence without creating new accounts:

```sh
python -m enterprise078.replay --output /tmp/enterprise078-public-replay
```

This verifies both archive hashes, stages the pinned306-file original science, applies only the preregistered revision patch in a separate directory, checks every registered case and runs canonical native semantic audits in matching subprocesses. The original12 and revised3 exports remain distinct. Public replay cannot authenticate ownership HMACs or confer authority over the original accounts.

Scientific source:825cabc0edf2e6bf677a5b80ade274ae8dee38bb. Original full inventory digest:c13a7411587736a18f1adc6422a15e026b6c934524eba745b344da82befff570. Initial1,024-operation gateway uses its own earlier source/outcome df8197d27266687b9971afa13143d38d0a310af6; do not rewrite it with later code.

All laboratory outputs remain qualified to authored finite digital models. Real SQLite tests give bounded computational corroboration. Physical instruments, market demand and external scientific validation are not established.
