# Building a release-archive clock converter

The private IGNITION controller can now resolve an ambiguous whole-field migration by examining a small number of labelled, source-linked records. The deliverable in this trial converts pre-normalized Git author and committer UTC clocks into separate written and landed UTC fields. Each object retains two distinct clocks for release-cohort review. [Download the offline converter](git-clock-converter.zip) · [Frozen C1 registration](REGISTRATION.md)

## What changed

The earlier Qwen migration produced two executable proposals. Each passed five of nine checks. Both failed on visible development data. Its two local calls consumed 2,080 input and 368 output tokens. The original archive and denominator are preserved. The existing bounded learner also has a distinct limitation: a request for more than 16 complete mappings defers even when an approved source can cheaply distinguish the projected fields. [Earlier source-matched study](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44239753684)

A mission may now supply `resources.mapping_evidence` alongside a `record_migration` definition with demonstrations. Each candidate record has an ID, a normalized input row, and the expected fields. The mission freezes a publisher, locator, version, retrieval time, a SHA-256 over those provenance fields and records, the approval digest of the beneficiary, purpose, requirements and field contract, and a maximum number of labels. The adaptive route then retains all development-compatible whole-field projections for each output. It reads the label of the affordable input with the largest guaranteed reduction per annotation, counting disagreements across all source records with that input. It defers on ambiguity, contradiction, exhausted budget, overlap with confirmations or substitution of the pinned pool. The SHA-256 represents the operator's approved bytes. Independent scientific or engineering evidence establishes whether those labels deserve trust.

This route is for typed whole-field projection. Open-ended direct model construction and the existing choice/split paths remain available for other purposes. The trial uses the original typed conversion and refusal rules. The UTC calendar interpretation is established upstream from Git timestamps. [Runnable mission example](mission.py)

## Observed comparison

Two equal-clock demonstrations admitted 64 whole-field mappings. A single selected source label identified the six intended fields. The conventional learner needed six labels in source order. Each route passed 23 frozen contract checks. The included direct Codex mapping also passed 23/23 from the written semantics alone. The stronger no-inheritance comparator was a short, independent SQLite projection. It matched the recipient on all 23 sealed Git IDs and all three malformed JSONL cases.

The 23 sealed IDs cover 14 distinct minute-level clock vectors. Among 75 nonsealed, nonteaching records, 43 shared a sealed vector and were excluded from the source pool to prevent leakage. The case count and the sealed ID count happen to coincide. The 23 acceptance checks include grouped confirmation batches, malformed cases, two role/time controls, a development batch and automatic evaluator controls.

A separate native Git lookup read all 100 original objects, recomputed each object ID from its actual commit bytes, extracted both UTC epochs and corroborated both clocks against the REST projection. The native and REST routes observe the same Git objects. They independently test extraction and interpretation. [Conventional SQL tool](conventional.py) · [Native-object check](git_witness.py) · [Registered source responses](source_clocks.json)

The pinned Qwen3-4B direct route timed out on the first request after 200.102 seconds. The one remaining request completed in 336.490 seconds with 932 input and 242 output tokens. Its own typed program passed all 23 checks and delivered a recipient. Setup, incomplete transport and successful delivery together consumed 554.017 wall seconds and 1,530.564 process-and-child CPU seconds on shared CPU. First-attempt token usage and actual provider or infrastructure cost are unknown. This was a fresh bounded migration with clear role names. It leaves the historical matched 2/6 result and open-ended construction failures intact. [Failed transport](qwen_timeout.json) · [Live proposal, costs and receipt](qwen_record.json)

The REST acquisition took 17.495 seconds over three GETs and 369,963 response bytes. Both cohort clocks were already publicly available. Fewer examined labels saved no HTTP requests on this acquisition. SQLite and the included direct route had sufficient semantic instructions at the outset. Engineering, historical component development, actual bills, independent reviewer labour, maintenance, support and beneficiary time have no complete monetary measurement. The measured outcome is correct delivery of this converter. Release-engineer productivity, adoption and compounding invention remain open. [Complete measured comparison](results.json)

## Downstream decision

The separately frozen release-hour test selected exactly one of the 100 records for the landed-changes review queue, the tagged commit `777489f9e09c8d0dd6b12f9d90de6376330577a2` in the hour beginning 2024-10-06 22:00 UTC. Native Git plus SQL agreed on every inclusion and exclusion. On this particular hour the author clock selected the same one commit. The stronger semantics changed zero review decisions. A willing release team with a consequential clock-dependent review is needed to test incremental beneficiary value. [Registered decision](COHORT_REGISTRATION.md) · [Executable cohort comparison](cohort.py)

The local model records bind their working-tree runtime hashes. Current-source deterministic replay recompiles the actual recorded proposal, executes the independent cases, and compares the published recipient's executable and contract bytes with the checkout. The local live model measurement and a later CI replay are distinct observations.

## Reproduction

From the product directory, run with Python 3.10 or newer.

```sh
python3 action_study/construction/verify.py
python3 -m unittest discover -s tests -p 'test_evidence_projection.py'
python3 action_study/construction/cohort.py
```

The first command exercises the normal private controller, independent SQL, actual recipient CLI, refusal controls and recorded model output offline. To corroborate all objects again, use a checkout containing the released Git tag.

```sh
git clone --filter=blob:none --no-checkout --depth=350 --single-branch --branch v2.47.0 https://github.com/git/git.git git-clocks-source
python3 action_study/construction/verify.py --native-git git-clocks-source
```

To use the shipped recipient, extract the ZIP into an empty directory. Within it run the following.

```sh
python3 -I run.py verify
python3 -I run.py run < example-input.json
python3 -I run.py migrate-jsonl < incoming.jsonl > converted.jsonl
```

To measure a fresh Qwen execution on an already-owned cache containing the repository-pinned model and runtime, use `observe_model.py CACHE NEW_OUTPUT.json`. Default replay makes no live requests. The human-only economic baseline needs an independently authorized study with operator time, real workflow and downstream utility.
