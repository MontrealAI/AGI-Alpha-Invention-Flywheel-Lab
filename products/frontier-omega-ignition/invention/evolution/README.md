# Would a later survey visit sustain the change?

An archive researcher can now reconstruct a dated list of same-band changes, inspect each pair of original detections and test an issued notice against the first eligible later detection. The earlier instrument delivered a g−r colour. This instrument asks whether the reported positive difference light moved sufficiently quickly in one band to warrant an archive review, and whether the next visit corroborated the displacement.

**The first two registered weeks produced 40 usable comparisons and zero alerts.** The largest absolute change among those comparisons was 0.184045 mag. The issue rule required at least 0.20 mag. There was consequently no prediction to adjudicate in these two cohorts. The follow-up success fraction is undefined. A subsequent [independently registered population](../early_survey/REGISTRATION.md) investigates a different target population without changing these results.

| Measurement window (2026 UTC, end exclusive) | Selected targets | Positive g/r detections | Target/bands with a comparison | Comparisons evaluated | Alerts issued | Later witnesses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nov 1–8 | 6 | 44 | 9 / 12 | 26 | 0 | 0 |
| Nov 10–17 | 6 | 25 | 9 / 12 | 14 | 0 | 0 |

Two objects appeared in both cohorts, ZTF26abrluog and ZTF26abwpoui. The twelve target-week entries represent ten distinct objects. Alert counts are descriptive of these selected intervals. The broker's later retrieval times are known. Historical ingestion and operator availability at each event time were unmeasured. [First query and observation identities](../sources/holdout-source.json) · [Second query and observation identities](../next_week/sources/holdout-source.json)

### Inspect a real decision

For ZTF26abwpoui in r, detection `3600356304715015009` at 08:33:05.002 UTC on November 10 had a positive difference magnitude of 19.457700. The next selected comparison endpoint was `3601376864715015006` at 09:02:40.997 UTC on November 11, with magnitude 19.621426. The November 12 decision used a change of +0.163726 ± 0.217019 mag over 1.020556 days, or +0.160428 mag/day. Its rate cleared the 0.10 mag/day minimum. Its change and its formal-error test both fell short. The earlier study could deliver g−r for this object during the same week. In this task it correctly stays on routine archive monitoring. [Source-linked JSON](RESULT.json) · [24-row observer worklist](worklist.csv)

Each target/band row also exposes its largest absolute eligible comparison so a recipient can inspect a quiet result. This display measure was added after observing the zero-alert outcome. It takes the earliest comparison on a tie, uses only evidence available at the chosen cutoff, and leaves issue and witness selection intact. In the CSV these columns begin with `strongest_`. The `issued_utc` column remains empty for a group with no alert, even when a diagnostic pair exists.

### Reproduce or turn back the clock

Run from `products/frontier-omega-ignition`, using Python 3.11+ with SQLite:

```sh
python3 -B invention/evolution/alert.py --check
python3 -B evolution_trials/verify.py --check invention/evolution/RESULT.json
python3 -B invention/evolution/alert.py --as-of 2026-11-12T00:00:00Z --out /tmp/nov12-notices.json
python3 -B evolution_trials/verify.py --as-of 2026-11-12T00:00:00Z --check /tmp/nov12-notices.json
python3 -B invention/evolution/alert.py --as-of 2026-11-12T00:00:00Z --csv /tmp/nov12-worklist.csv
python3 -B -m unittest discover -s invention/evolution -p 'test_*.py'
```

Outputs require a fresh path. IDs are decimal strings in JSON because survey detection IDs can exceed JavaScript's safe-integer range. When importing a CSV into a spreadsheet, select text for fields ending in `_candid`. Source JD is converted to UTC from its published decimal digits, truncated to milliseconds for display. The decision uses the unrounded observations and exact decimal inequalities. The complete JSON carries the original photometry, provenance digests, selected epochs, flags and dispositions.

### What an alert would mean

At each UTC midnight the desk evaluates the latest qualified positive g or r detection since the previous midnight. For the same target and filter, it chooses a baseline 0.5–7 days earlier whose lag is closest to two days. An issue needs an absolute change of 0.20 mag, an absolute rate of 0.10 mag/day and a change at least three times the combined formal errors. The first issue per target/band is kept.

The first eligible same-band visit at least 0.5 days after the triggering measurement, from the issue time to its three-day deadline (exclusive), adjudicates it. Displacement from the original baseline must reach 0.20 mag and twice the new combined errors. The direction determines `persisted` or `reversed`. A weaker displaced measurement yields `not_reproduced`. On either measured failure the desk withdraws the review notice. `awaiting_repeat` describes a test in progress. A finished three-day window without an admissible measurement yields `coverage_gap`; an earlier end of archived coverage yields `right_censored`. These two conditions leave persistence unknown. Synthetic test cases exercise every outcome; the published two-week science counts come solely from the original surveys. [Pre-outcome rules](REGISTRATION.md) · [Executable cases](test_alert.py)

Positive signed magnitude change means the measured positive difference signal faded. Both contrasts share the original baseline, which induces correlation. A different observation ID supplies a later measurement; formal uncertainty uses independent-error quadrature per pair and excludes reference, calibration and selection effects. The seven-column archive projections omit field, readout channel, reference-image processing ID, quality stamps, nondetections and forced photometry. Checking those fields and the original images is necessary for a physical interpretation. The later measurement is selected by event time without inspecting its brightness. The result describes neither total-source flux nor transient type. [ZTF survey-packet definitions](https://zwickytransientfacility.github.io/ztf-avro-alert/schema.html)

### Equal-permission alternatives and cost

The source-capability route retains #449's exact target-selection procedure and archive acquisition. Those measurements now support a different decision. An independent SQLite route reselects the source intervals, target roster, baseline, timing, status and projection from the same bytes. It recovered all 24 dispositions. The two earlier delivered colour products alone proved only 2 of 24 negative issuance decisions; the rest lack sufficient same-band history. The complete conventional workflow can reopen the raw archive and recover the same result. [Alternative and cost registration](../../evolution_trials/REGISTRATION.md) · [Direct SQL recipient](../../evolution_trials/verify.py)

An established operational alternative for astronomers is Fink's rate and uncertainty product, available since December 2023. It gives its time separation and identifies upper-limit-derived rates. Those fields are outside the original seven-column projection; numeric equivalence to this contract would require the same epochs and selection. ZTFReST already performed real-time rapid-transient searches in 2021. The working successor is a source-bound past-cutoff decision and witness worklist; historical newness, faster science, complete-cost savings and demand are open. [Fink science modules](https://doc.ztf.fink-broker.org/broker/science_modules/) · [Andreoni et al., ZTFReST](https://arxiv.org/abs/2104.06352)

This replay required no new source query, observing access or paid provider. The second historical object query previously took 5.9898 s. Acquiring the first cohort and developing/verifying both previous instruments consumed resources; only parts were timed. Construction, preparation, repeated direct checking, beneficiary work, maintenance, delivery and support belong in a lifecycle comparison. No observatory adopted the queue and no saved or redeployed exposure was measured. A willing desk can prospectively freeze a shadow queue and its existing Fink/SQL comparison, then track accepted review decisions and operator time per accepted outcome.

### Apply the instrument to another authorized archive

The low-level function `evaluate_cohort(cohort_id, targets, rows, start, end, as_of)` accepts source rows with the original `i:objectId`, `i:candid`, `i:jd`, `i:fid`, `i:isdiffpos`, `i:magpsf`, `i:sigmapsf` fields. Load source floats as `Decimal`, supply a known pre-window target roster, and convert UTC with `julian()`. It returns one seven-day cohort. Optional `baseline_lookback_days=7` admits the previous week only for a baseline. Optional `require_same_detector=True` requires matching valid `i:field` and `i:rcid` for the baseline and later witness. The latest eligible detection in the target/band/day is selected first. A missing matching prior stream can legitimately withhold a comparison. The caller owns source acquisition, provenance, program permissions and independent validation for a new input. These functions only read supplied data.
