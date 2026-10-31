# Completion023 operating and handoff notes

This branch recovers the private successor022 handoff and composes its native
prospective lifecycle with operator release `8abfb96d4ef859e30ca344d7933ec2a2f49012c1`.
The released champion remains in service. This candidate is not release-qualified.
The exact entry evidence and recovered byte inventory are in
[`RECOVERED_SOURCE.json`](../../campaign/completion-023/RECOVERED_SOURCE.json).
The backup contains no final Git metadata: its final runtime is pinned by file
hashes, not an inferred commit. Original private source/account files are never
overwritten by this composition.

## Existing batch interface

```sh
python3 -m pip install -r requirements-commercial010.txt
python3 -m connected_enterprise register --config campaign/overnight-022/OPERATOR_INPUT.json --output /absolute/new/batch
python3 -m connected_enterprise operate --output /absolute/new/batch --max-events 4
python3 -m connected_enterprise resume --output /absolute/new/batch
python3 -m connected_enterprise audit --output /absolute/new/batch
python3 -m connected_enterprise comparison --output /absolute/new/batch --control baseline --candidate growth
python3 -m connected_enterprise scoreboard --output /absolute/new/batch
```

Batch registration remains unfunded until operation. The single-business
configuration and fixed-terms financing experiment retain their distinct schemas:

```sh
python3 -m connected_enterprise register --config examples/connected022/continuing-world.json --seed 2610312231 --cohort-seed 2610312231 --arm growth --output /absolute/new/business
python3 -m connected_enterprise operate --output /absolute/new/business --max-events 18
python3 -m connected_enterprise resume --output /absolute/new/business
python3 -m connected_enterprise audit --output /absolute/new/business
python3 -m connected_enterprise scoreboard --output /absolute/new/business
python3 -m connected_enterprise comparison --config examples/native_capital020/central.json --output /absolute/new/financing
```

The single-business example begins with permanent terms. Follow the authenticated
nonempty-queue upgrade procedure in
[`successor022/OPERATOR.md`](../successor022/OPERATOR.md) to select prospective terms.
It preserves the account, old source versions, liabilities and queued work. New
accounts support development; they do not continue or replace the recovered
businesses. No new seed is a recovery method.

## Existing transition boundary

The recovered accounts already contain three authenticated transitions. Their
required prior record and signed journal exceed the existing 16,000,000-byte v1
ticket bound before any other ticket fields. The preflight in `prepare_upgrade`
rejects an impossible transition with
`SOURCE_UPGRADE_EXCEEDS_EXISTING_TICKET_BOUND` before copying a target source or
replacing `OPERATOR.json`. It is only an early rejection: a small payload still
needs all existing HMAC, checkpoint, historical-audit, counter and transition
checks. No bound, signature or authorization rule is weakened.

Continue those accounts only through their retained authenticated frozen source.
Their original absolute paths are signed identity. Restore only through the
approved private handoff after verifying the original manifest and checking
that no newer account or writer occupies those paths. Record new filesystem
inodes, preserve the original key bytes, and retain the original checkpoint.
Do not run the old qualification helper's historical inode-equality assertion
as if it proved identity across filesystem restoration.

## Portable public audit

After a completed independent audit, this export command copies only source and
service files bound by their recorded hashes, plus key-free operating evidence.
It recursively includes each prior version's complete pinned verifier inventory.
With no active writer, the offline option temporarily hides only the owned
historical source directories and restores them in `finally`:

```sh
python3 scripts/export_recovered023.py --business /absolute/owned/business --output /absolute/new/public-evidence --offline-historical-sources
```

The command writes a ZIP, integrity inventory and audit/resource evidence. It
retains the 10,000-file and 512 MiB guards. It never copies the account database,
private simulation keys, unbound extra source files or new credential material.
The public export reconstructs finance and operating semantics; it grants no
authority to reopen the original account. Private recoverability is checked
separately with the original key and full recovery sidecars.

From an extracted key-free export, verify `INTEGRITY.json` and run its exact
frozen verifier:

```sh
cd /absolute/extracted/public-evidence/source
python3 - <<'PY'
import json
from pathlib import Path
from connected_enterprise.verify import audit
p=Path.cwd().parent
print(json.dumps(audit(p/'source',json.load(open(p/'SERVICES.json')),json.load(open(p/'RESULT.json'))),sort_keys=True))
PY
```

This is portable reproduction, not operation of a downloaded published release.
The latter remains a separate mandatory exit for any new release claim.

## Economic and evidence scope

The original finite horizon is 504 planning hours plus its registered settlement
and maturity drain. Continuations keep the original seed, buyer budgets, costs,
terms and account history. They are exposed engineering reproductions, not fresh
held-out economic confirmation. Deterministic service execution is not a paid
frontier-model call. Actual model/host billing and empirical buyer demand remain
unknown; actual external collections are zero and actual profit is null.

The catalogue manifests still contain 160 services in 20 families and 12 proposed
bundles; portfolio pricing defines four segments and two tiers. Catalogue size
does not prove native execution. Reports identify the services actually settled.
The $3 billion trailing-year complete-cost profit target, native-to-aggregate
bridge, strong financing comparison and joint-policy adoption remain separate
open qualifications. No repair here establishes capability or discovery-process
improvement.
