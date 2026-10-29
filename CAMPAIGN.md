# First campaign: executed bounded cycle

**Decision: retain competent DC methods; pivot before commercial admission.**

The three-way primary-source screen compares grid interconnection,
second-life battery qualification and industrial heat recovery. Grid study
delay matters, but numerical outage screening is not established as its
binding residual constraint, and mature libraries already provide this
method. The public benchmark probe therefore qualifies a repair and an
adapter, without claiming a consequential invention.

Read [the decision](campaign/cycle-001/DECISION.md),
[opportunity evidence](campaign/cycle-001/OPPORTUNITY_SCREEN.md),
[foundation inventory](campaign/cycle-001/FOUNDATION_INVENTORY.md),
[verification](verification/VERIFICATION.md) and
[research edition](docs/research/cycle-001.md).

## Clean installation and one-command replay

Python 3.12 on Linux with 1 GiB worker address space available:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python reproduce.py --output /tmp/alpha-cycle-001-NEW
```

The output path must not exist. A worker has a 120-second CPU limit,
150-second wall limit, 1 GiB address space, 128 file descriptors and 10 MiB
per-file output ceiling. Its environment is reduced and thread counts are
fixed. This runs reviewed fixed code, not arbitrary generated programs;
these limits are not an effect/network sandbox. Local bwrap failed and no
generated program was executed. No internet operation occurs in the
replay; dependencies are installed separately.

The replay verifies exact input and kernel hashes, runs the independent
DC checker, preserves the seeded failing candidate, constructs a fresh
conditional IEEE30 transfer envelope using four arms, and feeds that
artifact into Alpha's pinned protected simulated exchange. The checker
refuses buyer acceptance without a buyer-issued service specification.
All simulated offers refund, with zero revenue and earned funds.

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s verification -v
```

`STARTED.json` without `COMPLETE.json` is incomplete evidence. Preserve
it and rerun to a new path. A complete run binds `REPORT.json` by SHA256.
Reproduction is a deterministic development replay; the exposed panels
do not become fresh confirmation. Source changes require an explicit
new freeze and review, never silently updating expected hashes.

Original evidence under `evidence/cycle-001/` is immutable within this
edition. Timings and SQLite bytes may vary on replay. Simulated opening
capital is not earned revenue and cannot finance a claimed successor.
