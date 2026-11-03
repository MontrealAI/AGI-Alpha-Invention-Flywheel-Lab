# Public evidence and key-free replay

This archive preserves the original 96 technical rows and 18 independent native
account exports. The unfavorable treatment comparison, initial execution failure,
and original replay-checker failure remain included. No account signing authority,
database, raw private action tape, or operating checkpoint is included.

## Source identity

- Repository: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab
- Exact pre-confirmation commit: `85c8a3e98f31bac9d3867a022aaa758623335083`
- Frozen protocol digest: `80aec9bd90d6416e531fef3b5d2c49bc3dd62bf48359f350568631c762ad9bb5`
- The 817-file canonical source selection is represented by `SOURCE_INVENTORY.json`,
  with its exact byte hashes; the public repository supplies the source bytes.
- `checks/postfreeze_replay.py` is an additive verification correction for serialized
  Python-versus-JSON representation. It does not replace frozen methods, evaluator,
  protocol, worlds, economics, or outcomes. Its bytes are in `BUNDLE_MANIFEST.json`.

## Restore source into a new extracted public bundle

Extract this archive into a new directory. Obtain a checkout of the exact commit;
an existing clone can be used. For a fresh clone:

```sh
git clone --filter=blob:none --no-checkout https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab.git frozen-checkout
git -C frozen-checkout checkout --detach 85c8a3e98f31bac9d3867a022aaa758623335083
python setup_source.py --checkout /absolute/path/to/frozen-checkout --evidence-root /absolute/path/to/extracted-evidence
```

The setup verifies every allowlisted payload and source byte before copying. It
requires the extracted bundle manifest and refuses conflicting existing files.
It does not modify the original operating directory, create accounts, reseed money,
open account authority, or rerun commerce. Runtime artifacts already present under
`native/source` remain unchanged. The source checkout must retain its Git commit
identity; the source copied into the bundle does not need `.git`.

Use Python 3.12 and the dependencies listed by the frozen source. Where they are
not already installed, the public dependency command is:

```sh
python -m pip install --only-binary=:all: -r /absolute/path/to/extracted-evidence/native/source/requirements-commercial010.txt
```

## Replay original evidence without signing keys

```sh
cd /absolute/path/to/extracted-evidence/native/source
python -m experiments.outlearning_20261102_906c4f4d.postfreeze_replay --output /absolute/path/to/extracted-evidence --expected-freeze 80aec9bd90d6416e531fef3b5d2c49bc3dd62bf48359f350568631c762ad9bb5 --receipt /absolute/path/to/new-public-replay.json
```

Use a new receipt filename. The checker regenerates and compares deterministic
technical constructions and independently replays the exported native journals;
it does not resume their private accounts. Successful replay establishes source
and result reproduction within the authored simulation, not actual provider
semantics, customers, or a discovery advantage.

## Contents and omissions

`BUNDLE_MANIFEST.json` hashes every payload file except itself. The adjacent archive
manifest records this manifest hash and the archive SHA-256. `FAILURE.json`,
`INDEPENDENT_REPLAY_FAILURE.json`, `RESOURCE_SCOPE.json`, and `ADOPTION.json` retain
failure/resource/decision context. Public native `RESULT.json` receipts supplement
the account exports. All actual request-bound delivered artifacts, including
failed attempts, are included at their original relative verification paths.

The archive deliberately omits raw private account files, checkpoints, authority,
duplicate resume stdout, and duplicate construction/delivery copies. The original
96 scientific rows retain their submitted programs and full probe transcripts.
Only a strict public-file allowlist was inspected for secret patterns; no broader
credential search or account-wide privacy audit was performed.
