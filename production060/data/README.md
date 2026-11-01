Integration distribution note: the following describes the original normalization workspace. This Git distribution includes normalized time-only JSON and PUBLIC_PROVENANCE.json; the external raw/parser paths below are historical provenance, not bundled runnable dependencies. Use the credited public dataset URL and recorded source hashes to obtain original inputs.

# CDP060 public operational inputs

This directory normalizes all 263 published daily instances of **Real operational data for the Concrete Delivery Problem**, Alexandros Tzanetos and Maude Blondin (2023), Mendeley Data v1, DOI [10.17632/b78bc94d95.1](https://doi.org/10.17632/b78bc94d95.1). The dataset license is **CC BY 4.0**. Normalization changes the storage format and units of truck travel; it does not create demand, repairs, operating schedules, prices, buyers, or commercial validation.

The raw public archive and every extracted public member are preserved in the adjacent `cdp060-inputs` directory. All 269 archive members were verified against the official record's per-file SHA256 before parsing. `source_manifest.json` records the archive, official metadata, parser wheel, code and normalized output hashes. `../cdp060-inputs/verified-files.json` holds the exact per-member source hashes and official file IDs.

## Files and consumer contract

- `resources.json`: 8 plants, 214 truck records, the original 9 numeric parameters, their meanings/units, plant travel matrices and a reconciled plant/capacity fleet count table.
- `catalog.json`: all 263 instance IDs and absolute JSON paths, actual order counts, volumes, actual static/dynamic classification, split-load counts and completeness flags.
- `days/<id>.json`: the actual orders and matrices. Order fields are `id`, `client_id`, `volume_m3`, `default_load_m3`, `release_min`, `requested_min`, `interval_min`, `mix_id`, `usage`.
- `validation.json`: comparisons performed and all preserved source discrepancies.
- `normalize.py`: the reproducible normalizer. Run `PYTHONPATH=/workspace/scratch/ebd85108b356/cdp060-prep/parser python /workspace/scratch/ebd85108b356/cdp060-prep/normalize.py`.

`travel_minutes[i][j]` is **truck travel time**, with the source `GoogleTravelTimeMultiplier=1.4` already applied exactly once. Rows follow exported order IDs; column `j` is plant pseudoID `j+1`. `source_car_travel_minutes` preserves the published pre-multiplier values. `plant_travel_minutes` is likewise already multiplied. Source plant-to-plant asymmetry is preserved. Source site-to-plant return travel is assumed equal to the corresponding plant-to-site travel; there are no site-to-site delivery arcs. The original DistanceMatrix blocks independently confirm orientation and unmultiplied source travel via the supplied 0.36 km/min conversion. Those distances are derived proxies, not independently surveyed distances.

`release_min` and `requested_min` contain **minutes since operational-day midnight**, including seconds if present. They mean order release and requested first arrival, respectively. Every internal calendar component is deliberately discarded. Source IDs refer only to public pseudonyms; client IDs are daily, so matching them between instances would invent customer retention. The article says days are randomized within order-count groups; instance serial numbers are not chronology. `kind` uses actual release clocks; `source_filename_kind` preserves the filename label separately.

`default_load_m3=0` means the customer did not specify a per-delivery size. The source default is then 7.5 m3. Split-load counts are the sum of `ceil(volume / (default_load or 7.5))`; they do not assert truck feasibility or create extra orders. A final load can be smaller. Preserve the requested arrival and interval semantics when selecting an operating model.

## Loading and other limits

The named `LoadingRates` source table has `PlantID` and `MeanLoadingRate`. Its `VariableUnits` is empty and the article does not supply the time unit. Therefore **`loading_rate_m3_min` is null for every plant**. Raw values `[57.5,52.5,80,70,55,45,62.5,0]` are retained as `source_mean_loading_rate`; assigning m3/hour or m3/min would be an additional modeling assumption. Plant 8 has a literal source zero. The article's published equation `(max-min)/2` is a half-range rather than an arithmetic mean, another unresolved source ambiguity.

The source explicitly specifies one loading dock per plant. It supplies a 10-minute default loading duration where a usable rate is unavailable, plus preparation, cleaning, unloading, break and meal durations. It does not supply loading-rate units, mix/plant capability restrictions, concrete freshness limits, shift durations or break/meal triggers. These require explicit operating assumptions or exception handling; the data do not authorize physical dispatch. The included static matrices do not establish robustness to real traffic.

## Preserved adverse source evidence

- Missing MixCode cells remain `mix_id:null`; `missing_mix_order_ids` and `mix_data_complete` expose them. A schedule using such a record requires a mix exception, not an invented recipe.
- `cdp_o45_08d`: order 37 has eight source NaN travel values; exported as null.
- `cdp_o50_d`: 50 order rows but only 49 travel rows. The order/row mapping is unresolved. Its operator-facing matrix is all null; its raw 49-row matrix remains in `source_car_travel_minutes`. No row correspondence is guessed.
- Those two days have `operating_data_complete:false`; the other 261 have mapped finite travel. This flag concerns travel availability and does not certify missing mix information or the unsupplied operational constraints.
- `cdp_o49_02d` and `cdp_o49_13d`: source specs claim 50 orders while tables contain 49. Table sums are respectively 831.75 and 627.0 m3, versus source spec totals 841.75 and 627.75. Actual order rows drive exported totals; original specs remain alongside them.
- `cdp_o5_05d` and `cdp_o5_10d` are labeled dynamic by filename but all release clocks are zero. Actual exported `kind` is static.

The validation status is **normalized with preserved source issues**, not a claim that source data are perfect or that scheduling/business economics have passed.

## Parser provenance

The task-local dependency is [foreverallama/matio](https://github.com/foreverallama/matio), PyPI **mat-io 1.0.2**, BSD-3-Clause, installed only under `parser/`. Its LICENSE, project metadata, build entry points and Python loading entry point were inspected before use; its Python source contains no `eval`, `exec`, shell/network or pickle operation matched by the review. The downloaded wheel and its embedded license are retained. h5py 3.16.0 is a task-local import dependency. Global NumPy/SciPy/pandas are reused.

Native DataFrame conversion requires an undeclared PyArrow dependency. The normalizer instead uses the package's public `raw_data=True` decoder and exact named MATLAB table properties `varnames`, `data`, `nrows`, `nvars`; it never guesses opaque column positions. Clock extraction is separately checked against NumPy datetime arithmetic without exporting the calendar values. Fleet aggregation is checked against all 214 individual truck records. Numeric travel/distance blocks are decoded independently of the table properties.

Source documentation: [data article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10189365/), [dataset record](https://data.mendeley.com/datasets/b78bc94d95/1). Dataset license and article license differ; this directory redistributes the dataset under CC BY 4.0, not the article text.
