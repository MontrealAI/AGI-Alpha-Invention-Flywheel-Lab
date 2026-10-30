# Reproduce the commercial 010 engineering results

This edition contains executed reconciliation artifacts on disclosed synthetic
inputs, strategic simulated buyers and competing providers, and the native
protected exchange's simulated cash ledger. Every order, payment and earned
balance in the market model remains **SIMULATED**. Reproduction is an exposed
engineering replay, not a fresh customer experiment or independent certification.

The runtime, policy, service cohort and independent checker are frozen by
`SOURCE_FREEZE.json` with external SHA-256:

```text
117ea809b09cb7bc8597bdcfb472e0df63a15d987dfedbc6844ef482d6c01ed5
```

The distribution's `PACKAGE_MANIFEST.json` records its exact 40-character public
source commit and each distributed member's size and hash. Match that commit to
the immutable release tag or qualified PR head. The source commit and the runtime
freeze are different identities: later documentation, evidence and qualification
repairs do not replace the frozen candidate.

The current version is the disclosed **v3 persistence repair**. Original freeze
`68e4edb58962eac4110e4d9ff5e1845cd37ea5eb5450817c1431d3651715f2c1`
and its exact source closure are preserved under
`historical/commercial-010/attempt-v2/`, with the original hash manifest. The
financial policy, seeds, costs and native financial methods remain unchanged.
The new version changes SQLite persistence and supervisor receipt-path reporting;
it does not claim that the physical corruption's root cause was established.
Both failed attempts and their conservative resource charges remain recorded.
`RECOVERY_ALLOCATION_002.json` declares the additive 7,800-second cumulative
reservation ceiling, not an exact CPU bill, inside the unchanged wall deadline.
Do not execute current code while presenting the old freeze as its identity.

## Clean package preparation

Download the source ZIP and `RELEASE_SHA256SUMS.txt` from the same release. Verify
the ZIP against its published checksum before extraction. When downloading every
listed release asset, `sha256sum -c RELEASE_SHA256SUMS.txt` checks the complete set,
including the source-matched publication gate. The original qualification-stage
`SHA256SUMS.txt` is also retained unchanged. Preserve the
original files and use new exclusive directories for every replay.

```bash
python3 -m zipfile -e AGI_ALPHA_Commercial010_source_evidence.zip /tmp/agi-commercial010-source
cd /tmp/agi-commercial010-source
python3 -m venv /tmp/agi-commercial010-env
. /tmp/agi-commercial010-env/bin/activate
python -m pip install --only-binary=:all: -r requirements-commercial010.txt
```

Use Python 3.12. The native exchange needs the pinned `cryptography`, `cffi` and
`pycparser` dependencies; this is not a standard-library-only runtime. Installing
them may require network access. After installation, the declared replay needs no
Git history, model API, account credentials, customer contact or payment service.
The supplied compiled PDF can be checked without a TeX installation.

Check every extracted member before running it:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root/'PACKAGE_MANIFEST.json').read_bytes())
assert manifest['scope'] == 'SIMULATED'
assert not any((p/'.git').exists() for p in [root, *root.parents])
for name, meta in manifest['entries'].items():
    path = root/name
    assert not path.is_symlink()
    raw = path.read_bytes()
    assert len(raw) == meta['bytes']
    assert hashlib.sha256(raw).hexdigest() == meta['sha256'], name
print('Verified source commit:', manifest['source_commit'])
PY
```

The compact package includes the current workflow files because one benchmark
regression checks hosted test discovery. Current source tests execute current
code; historical cycle-001/004/005/006 replays in the broader repository use their
own immutable materialization boundaries and are not rerun by this compact smoke.

## Input, service, document and runtime checks

```bash
python -m unittest discover -s tests -p '*010*.py' -v
python -m unittest discover -s tests -p '*011*.py' -v
python -m unittest discover -s portfolio25 -p 'test_*.py' -v
python -m unittest discover -s benchmarks -p 'test_*.py' -v
python run_commercial010.py --freeze-sha256 117ea809b09cb7bc8597bdcfb472e0df63a15d987dfedbc6844ef482d6c01ed5 --check-inputs --output /tmp/agi-commercial010-input-check.json
python scripts/check_commercial010_paper.py --root . --output /tmp/agi-commercial010-paper-check.json
python run_commercial010.py --freeze-sha256 117ea809b09cb7bc8597bdcfb472e0df63a15d987dfedbc6844ef482d6c01ed5 --smoke --smoke-world qualified_differentiation --output /tmp/agi-commercial010-positive --resource-ledger /tmp/agi-commercial010-positive-resources.json
python run_commercial010.py --freeze-sha256 117ea809b09cb7bc8597bdcfb472e0df63a15d987dfedbc6844ef482d6c01ed5 --smoke --smoke-world zero_demand --output /tmp/agi-commercial010-zero --resource-ledger /tmp/agi-commercial010-zero-resources.json
```

Input checking authenticates frozen bytes and independently rechecks service
acceptance. It does not execute the market or establish a commercial verdict.
The document checker validates source/output bindings and the separately recorded
PDF visual inspection; it does not certify commercial assumptions.

Each smoke executes exposed exploration seed **1**, fixed multiplier **9,500
basis points**, and one frozen scenario. The positive world must permit simulated
sales; the zero-demand control must produce no sales and cannot qualify a flywheel.
These smokes check the complete standalone execution path, not adaptive policy
selection or the entire confirmation region. The existing bounded supervisor
records limits, failures and resource use. Each smoke has a 600-second CPU/wall
ceiling; no successful smoke converts a simulated receipt into observed revenue.

Inspect each output's `RECEIPT.json` and `artifacts/RESULT.json`. The result includes
the native action tape, recomputed ledger summary, decisions, costs, reserves,
settlement and funding provenance. The hosted workflow independently replays each
native ledger and records `CLEAN_REPLAY_QUALIFICATION.json`. Its distributed
`CLEAN_REPLAY_RECEIPTS.zip` retains the executed smoke receipts and ledgers.

## Full finite campaign and original interruption

The full experiment comprises 297 prospectively frozen world/seed/policy cases.
Its final evidence index and paper distinguish completed work, the interrupted
first invocation, recovered cases, confirmation, sensitivity and failure regions.
They retain the original resource reservation; resumption does not create a new
campaign allowance or silently discard failed work.

The published lossless evidence index is
`evidence/commercial010/raw-parts/INDEX.json`, externally pinned by SHA-256
`6f7ce670140a14060324464dfa13c25652a793604292823dbe1e47ba6913ca29`.
Its 282 bounded parts preserve the original interrupted run, failed recovery and
completed v3 recovery, including raw SQLite bytes, journals, action tapes and logs.
Restoration is optional and uses additional storage; the compact smoke does not
need to expand these historical outputs.

```bash
python scripts/archive_commercial010_evidence.py extract --index evidence/commercial010/raw-parts/INDEX.json --index-sha256 6f7ce670140a14060324464dfa13c25652a793604292823dbe1e47ba6913ca29 --output /tmp/agi-commercial010-restored-evidence
```

If a single complete ZIP is needed instead of an extraction, use the same helper's
`reassemble` command with those index arguments and a new exclusive ZIP output.
The index and every part/member identity are checked before restored evidence is
used. Restoration changes neither outcomes nor the original resource charges.

A separately authorized full engineering rerun uses the same frozen entry point:

```bash
python run_commercial010.py --freeze-sha256 117ea809b09cb7bc8597bdcfb472e0df63a15d987dfedbc6844ef482d6c01ed5 --output /tmp/agi-commercial010-full-engineering-replay --resource-ledger /tmp/agi-commercial010-full-engineering-resources.json
```

This command can take substantially longer than a smoke and reserves a bounded
3,600-second CPU/wall allowance. It creates a new exposed engineering run; it must
not be used to reset the original campaign's accounting, choose a favorable seed,
or claim fresh scientific confirmation. Keep failed outputs and resource ledgers.
Never delete or replace them to obtain a green result. Hosted CI runs only the two
small controls above and verifies the published full-campaign evidence bindings.

## Source-matched publication

The commercial workflow uploads the actual compact ZIP, PDF, TeX, browser HTML,
Markdown report, source manifest, checksums and replay receipts as
`commercial010-source-evidence`. A main-only publisher requires its own successful
qualification and successful **push/main** runs of `campaign.yml`,
`consequential007.yml` and `consequential009.yml` at exactly the same source SHA.
PR checks from another event or branch cannot satisfy this gate.

The publisher downloads that run's artifact, verifies its bytes and source
identity, and creates the uniquely tagged experimental prerelease
`commercial-flywheel-20261030-r1`. An existing tag identifying another source is
refused; published assets are never replaced. The final reading links and measured
commercial conclusions are in `docs/commercial010/REPORT.md`.

## Separately scoped portfolio successor

`portfolio25/SOURCE_IMPORT.json` preserves PR17's exact original source identities;
`HARDENING.json` and `HOSTED_QUALIFICATION.json` distinguish the validated research
implementation from unvalidated demand and quote assumptions. Its 30 assertions
are explicitly discovered by both current hosted workflows.

The compact source also includes `campaign/commercial-011`, its four executed
synthetic technical-service types, guarded-growth policies, source snapshots and
compressed native ledger journals. Read `campaign/commercial-011/REPORT.md` and
`README.md` for its own commands and conclusions. Its aggregate 120-month model is
separate from commercial010's eight-cycle experiment; it does not establish actual
customer revenue or a billion-dollar outcome.
