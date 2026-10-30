# Passive profiles, measured spectra and the missing physical witness

**Decision: no new measurement means admitted.** The frozen exact diagnostic found no duplicate inputs in either released input view, so it did not produce even an exact recorded-input alias witness. This does not prove that passive profiles identify physical kinetics. Independent timing, same-system identity and repeatability evidence remain necessary to adjudicate that question.

This is another bounded development probe within overnight008. It does not repeat predictor training or reset the campaign's error budget. Root agreed to the proposed exact test before execution, then explicitly confirmed that a blocked physical gate permits only a released-record diagnostic. `PROTOCOL.json` froze at `2026-10-30T08:14:30Z`, SHA256 `f823d05d40e14ee039bd4c738cb9ded02cc05a8251e61609608888b255236faa`; numerical input/target relation execution began afterward. Old `science_recovery` evidence was left unchanged.

## Actual source access and data meaning

The primary paper releases paired fuel-cell profiles and measured spectra, plus an AI-native predictor and conventional model comparisons. The model's published code uses the first nine channels and a100-sample window selected from a180-sample released history after the documented sampling interval. We read that source and retained all available input/history for the second diagnostic. We did not execute downloaded programs, deserialize pickle model checkpoints or train another predictor. No poor predictor score could establish fundamental physical underidentification.

The processed dataset4 MAT file was obtained from the exact public code revision `320ac4649a618c2d20b1009aa9dcc0a27d7664be`, verified against Git blob `5b14a996232797c8c0ec9ce7294ae3ef516755fa` and SHA256 `8f02b75054e3cf8e337a3c196f8b330ea740b698902bd38639e9536583af855b`. It contains828 X/Y record pairs: X `[828,10,180]`, Y1 `[828,38,2]`, and the source split permutation. The10th input channel is constant1 throughout. The authors' source asserts row correspondence and indexes X/Y identically; this is source-bound released-record pairing, not independent acquisition-clock validation.

The raw Zenodo release is a1,978,537,477-byte ZIP, larger than this allocation. Instead of calling it inaccessible or downloading it whole, we read its public HTTP ranges: the131,072-byte tail and894,750-byte directory identify5,079 entries. Exact `Content-Range` and body lengths were checked; extracted source entries were checked by ZIP CRC32 and saved SHA256. Whole-archive MD5 is only publisher metadata and was not locally verified. The raw release is openly licensed MIT, separately from the article's publication license. The relevant author readmes and two small raw-format examples were extracted without executing archive contents or importing a whole platform.

The raw documentation prevents several attractive but invalid shortcuts:

- Dataset4 raw inventory has79 condition folders and948 spectral files, each folder containing12 stack/cell-location spectra. The processed828 rows equal69×12 arithmetically; the exact exclusion/row map has not been reconstructed. The authors document excluded incomplete0.4A/cm² humidity/coolant recordings.
- The12 suffixes are **different targets**: a00 is the whole stack and a01–a11 identify different cells. They do not supply same-cell repeatability or a physical measurement-noise bound.
- Dataset2's own readme explicitly says certain missing time recordings were replaced by a180-second replication of operating-condition information from impedance sheets. Those records were not selected for this dataset4 test and cannot be promoted as physical aliases.
- A raw dataset4 time-recording example includes absolute timestamps, elapsed seconds, nominal500ms logging and sensor/unit headers. A separate first-sorted raw spectrum includes the June13 date, sweep time11:59:15–12:05:31 and per-frequency acquisition times, magnitude, phase, voltage and current. Its roughly376-second sweep is not an instantaneous physical observation. The chosen time-recording example is June17, so these examples are **not assumed paired**.

Raw timestamps make a future clock-aware audit possible. They do not by themselves establish which processed window ends at which spectral acquisition, whether a response changed during the sweep or how much spectral variation is measurement noise. The processed file has no explicit per-record clock/site map. Original sensor registers and more individual-cell voltages are available in the raw recording; a strong complete alternative may use this legitimate context. Repairing omitted site identity or indexing would be routine conditioning, not invention of a new measurement means.

## Frozen execution and result

All828 released records were retained. The first view exactly reproduces the source's nine-channel/final100-sample recipe; the second uses all ten channels and all180 samples. Only signed zero was canonicalized. No rounding, nearest-neighbor grouping, learned distance, fitted residual, SNR threshold or output-selected cohort was used. Hash groups were required to pass exact elementwise-value equality before any label comparison. The full38-complex-value label vector was the declared target, with no invented materiality threshold.

| Frozen view | Records | Unique input groups | Duplicate pairs | Conflicting-label groups |
| --- | ---: | ---: | ---: | ---: |
| Published9×100 |828 |828 |0 |0 |
| All10×180 released history |828 |828 |0 |0 |

The executed code/report/raw group digests are under `exact-r1/`. The source split index was verified as a complete zero-based permutation and retained, but not used to exclude records. The diagnostic consumed about0.284CPU seconds and80MiB peak RSS. All data are exposed development evidence; confirmation alpha spent is0.

There is no observed exact-input label conflict to attribute to any measurement limitation. The absence of conflicts is also insufficient to establish a unique physical map: continuous noisy inputs are usually distinct, and a finite observation set cannot exclude unobserved ambiguities. We did not convert near inputs into identical physical conditions to manufacture a positive result. No scientific advantage over ISDiffM, ordinary methods, site-conditioned models or complete operando methods is established.

## What would justify constructing another means

A physical missing-means claim now requires a documented same-cell/stack reference with an exact acquisition timeline, independently measured repeatability/calibration, fixed useful operating obligation and permissible interventions. The first discrimination is whether materially different physical responses persist despite observational equivalence established by **external measurement evidence**, rather than convenience distances or fitted residuals. Any persistence test must distinguish measurement noise, cell identity, time evolution during acquisition, input replication and missing history.

If a real ambiguity survives, an active intervention or synchronized orthogonal observation could be specified to distinguish the competing responses. Existing operando/LTV, trend-removal/differencing, physics-based and AI-native routes must receive equal input, context and control access. A new means would need to demonstrate a useful consequence beyond those complete alternatives; another prediction score or routine metadata repair does not satisfy that requirement. This dataset audit has not admitted that experiment.

Full original recording access was available within the budget through ranged retrieval; access was not used as an invented administrative stall. The remaining physical gate is evidence not yet reconstructed or supplied: the per-row timing/site/frequency map and independent same-system repetition/calibration. No customer, payment, willingness-to-pay, negative-to-positive complete-cost cohort or unrestricted earned funds were manufactured. Search, model inference, integration, verification, physical operation and liabilities remain cost items or unknowns; measured CPU is not full monetary cost.

Replay the frozen diagnostic with the bundled exact MAT file:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 prlimit --as=2147483648 --cpu=300 --nofile=64 -- timeout 180 python3 exact_alias_probe.py --output /tmp/alias-diagnostic-NEW
```

The output directory must not exist. Source hashes, input schema, protocol, author readmes, original bytes, access failures and range receipts remain alongside the report. The result supports an honest next construction decision; it is not mission success.
