# GENESIS 002 funding correction qualification

Base: `0964ad2c2aedd3351b5367eafba869212cde34f6`, original PR #229.
This is a separate stacked engineering correction, not an owner-branch rewrite,
account migration, fresh commercial confirmation, merge or release.

## Reproduction and repair

Original hosted failure: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41896249975/job/126806430300

The exact public source reproduced 51 local tests with six native funding errors.
Seven new regression methods ran before the fix: 58 total tests, seven failed
subtests and nine errors. None of these runs is retrospectively relabeled a pass.

Only the GENESIS selector and operating wrapper change runtime behavior. All 64
other files in the 66-file native runtime inventory match the original Git blobs.
The canonical account, ledger, native custody/earned guards, protocol amounts,
price menu, buyer budgets, registered dates and residual obligations are unchanged.

Repair: process already-eligible dated native maturities before each new job;
include fee, custody collateral and production in the cash gate; charge the fee
against the earned-funding gate; validate native price/residual eligibility before
registration; reconstruct same-hour maturity in zero-overhead independent audit.
The original reserve check remains. Source binding refuses operating an old-source
account with these changed bytes. No historical account was opened or reset.

## Local checks on repaired source

- GENESIS suite: 58 tests passed, then one additive exact-native cash-boundary test
  passed (59 distinct methods total). The policy suite includes 2,000 seeded
  comparisons against an independently expressed enumerator.
- Original frontier compatibility: 25 tests passed.
- Unchanged platform-runtime suite: 16 tests passed. An earlier incomplete local
  source extraction failed two imports; extracting the missing unchanged enterprise
  package resolved that workspace limitation without changing a test or runtime.
- Independent review found no blocking defect; it separately ran all 26 policy
  tests, parsed four Python files and parsed both modified workflow YAML files.
- Full pilot, completed resume, byte-identical native export comparison, independent
  audit and key-free export audit completed. Four computational deliveries settled;
  three production expenses were earned-funded. This is an engineering reproduction
  with authored simulated demand, not new empirical evidence.

The local Python environment used NumPy 2.3.5, SciPy 1.17.0 and cffi 2.1.1, but
cryptography 50.0.0 and pycparser 3.00 differ from the hosted pinned 50.0.2/3.11.
Exact-head standard hosted qualification with pinned dependencies is therefore
required before integration; no broad hosted pass is asserted by this file.

The pilot reports $240 modeled collections, $135.90 modeled profit, $4 protected
tail, no payables and zero actual revenue. Initial capital is the unchanged $100
scenario. This short four-request engineering episode is not annualized profit,
real commerce, a new qualified flagship, causal successor advantage or the $3B
trailing-year objective. Private account/recovery material is not published.

## Reproduce

Run the commands in README.md on a new disposable output path. Run these suites:

```sh
python -m unittest discover -s tests -p 'test_genesis_enterprise_*.py' -v
python -m unittest discover -s tests -p 'test_frontier_*001.py' -v
python -m unittest discover -s tests -p 'test_connected_platform_runtime064.py' -v
```

Keep the original source-bound failure and independent strong ordinary alternative.
Normal owner-controlled review/integration remains separate from this correction.
