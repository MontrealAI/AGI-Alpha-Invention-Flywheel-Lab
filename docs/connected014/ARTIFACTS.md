# Source-bound operation and public evidence

All commerce is simulated. Business source: `ffc1f2e14e88e11f75d5087ab0f7c4e60512431e`;116-file source SHA256`3d985299bf6cfaf546b712ebd9e878e875aaf730ffdb32023637aafc5504a38d`. Economic learning/source rules were frozen before each registered fresh experiment. The expansion evaluator was separately published at`692c09ae631b0fd4f1331327505e2942ad8767a6`; the assisted recovery authority and tools at`b60eb7018fc7090ff3d7876c7b4e6b87a5e86922`.

From this repository checkout, reconstruct the full eight-business expansion archive:

```sh
python scripts/reassemble_connected014.py --manifest artifacts/connected014-expansion-parts/INDEX.json --output /tmp/agi-expansion-new.zip
python -m zipfile -e /tmp/agi-expansion-new.zip /tmp/agi-expansion-new
python /tmp/agi-expansion-new/harness/run_connected014_expansion.py _audit --output /tmp/agi-expansion-new
```

The final command is read-only historical replay and needs no private simulation key. It rederives financial records, actual artifacts, operating semantics, cohort origin, growth summaries and the complete report. The public package includes the recovery allocation, original native prefix, dry-run and live-application proof. It cannot reopen or spend from an original account. Live operation/resume requires the retained local private keys and a current authorized resource allocation. Historical runtime cutoffs are preserved; do not misrepresent a historical replay as a fresh confirmation.

Reconstruct and audit the separately registered 20-world pricing comparison:

```sh
python scripts/reassemble_connected014.py --manifest artifacts/connected014-confirmation002-parts/INDEX.json --output /tmp/agi-pricing-new.zip
python -m zipfile -e /tmp/agi-pricing-new.zip /tmp/agi-pricing-new
cd /tmp/agi-pricing-new/source
python -m connected_enterprise audit --output /tmp/agi-pricing-new
```

The incomplete001 checkpoint and exposed development history remain under `artifacts/connected014-incomplete001-parts/INDEX.json` and `artifacts/connected014-development-parts/INDEX.json`. They have no full confirmation verdict and no live recovery authority. All archives omit private simulation keys and SQLite accounts. Their exact hashes/size/ordered parts are checked by the reassembler, including ZIP CRC and key-file refusal.

Fresh operation uses `python -m connected_enterprise run --output /absolute/new/output`; it freezes a new source/configuration manifest and uses separate explicit simulated seed allocations. Read [the operator guide](OPERATOR.md). Never copy an earned balance between evaluation worlds.

The research edition can be regenerated after decoding both complete archives:

```sh
python scripts/render_connected014_report.py --run /tmp/agi-expansion-new --comparison-run /tmp/agi-pricing-new --output /absolute/new/research-edition
```

It requires LaTeX; all result inputs must have an accepted package audit and the same business-source binding. No deployment, merge or formal release has occurred. Four source002 hosted workflows concluded success; the adaptive workflow's individual tests/replays/artifact upload all passed, but its terminal API state was cancelled. See the exact source-bound CI receipts rather than inferring all-green qualification for a later metadata-only commit.
