# Release and mission replay

Use the [deployed release receipt](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/atlas-release.json) to select the exact source revision, workflow run, Atlas ledger digest and executor digest. The GitHub run must contain successful `build`, `deploy` and `verify-live` jobs. The following command verifies the public assets against that run.

```sh
python3 scripts/frontier_atlas.py verify "$ledger_sha256" \
  --source-commit "$source_commit" --workflow-run "$workflow_run"
```

The browser replay requires the pinned Playwright dependency from the Pages workflow, Chromium and a real local compatible model on the approved loopback route. It checks the archive and every source-bound file against the public receipt before opening the connector. It pairs under an isolated eligibility fixture. Production URL, source revision, downloaded executor, model readiness, first execution, journal exports and restart are recorded. Model output belongs to the paired executor. Test eligibility belongs to the test harness.

```sh
export FRONTIER_EXECUTOR_VERSION=1.2.0
export FRONTIER_EXPECTED_COMMIT="$source_commit"
export FRONTIER_CHROME=/absolute/path/to/chromium
site=https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/
runner=publication/evidence-bound/production/run-evidence-browser.sh
goal='Build frontier AI LLM for Game Theory.'
"$runner" "$site" "$run_dir" en "$goal" start
"$runner" "$site" "$run_dir" en "$goal" restart
```

Set `FRONTIER_FOLLOWUP_GOAL` for the different mission to run within the same pairing and selected model. The browser selects **New mission** first to preserve independent mission history. Use a fresh output directory for each first use. The browser stores raw archives and connection logs privately. Export only the reviewed receipts.

For an independent source-based French control, acquire the two listed CPython headers from their exact publisher commits as `alpha.h` and `bravo.h`. The [registration tool](../prepare_cpython_case.py) verifies their Git blob IDs and SHA-256 digests, then creates a local `--mission-evidence` file and obtains the conventional result. Set `FRONTIER_EVIDENCE_INPUT` to that local file and run the browser with its exact French ambition.

The [staged browser control](STAGED-BROWSER-CONTROL.json) used authored provider responses and tested the UI and journal. The [source engine control](SOURCE-ENGINE-CONTROL.json) covers actual source identity, exact execution and five independent arithmetic edges with an authored instrument. The [schema review](SCHEMA-SCOPE-REVIEW.json) covers denial at the SQLite and verified-claim boundary. Each receipt states its authorization and inference scope.

The independently checked [telemetry classifier](TELEMETRY-CLASSIFIER.json) is an assisted repair. It accepts declared valid 16-bit integer inputs for this decision convention. To replay the wraparound example write an input file and use the trusted evaluator from the downloaded executor.

```sh
printf '%s\n' '{"previous":65530,"current":5}' > input.json
python3 -I -S bridge/instruments.py /path/to/TELEMETRY-CLASSIFIER.json input.json
```

The unchanged [automatic artifact grade](FOLLOWUP-ASSESSMENT.json) and the [assisted repair grade](FOLLOWUP-ASSISTED-ASSESSMENT.json) use the same held cases and separate provenance.

The automatic grade binds the original browser captures and the private downloaded journal. Published JSON receipts use reviewed serialization and may add diagnostic fields. The [public receipt map](FOLLOWUP-PROJECTION-MAP.json) records both digests and checks the shared JSON fields.
