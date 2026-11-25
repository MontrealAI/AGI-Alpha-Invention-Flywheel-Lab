# TOI-216 April 2023 · timing and independent archive admission

**GO for rejecting the registered ordinary clock aliases. ABSTAIN on the April planet attribution.** The closest of 18 clock interpretations places the discrepant catalogue value **4,689.557 seconds** from the frozen TOI-216 c fit, against a registered tolerance of **584.689 seconds**. The closest interpretation of a b fit remains **464,116.926 seconds** away. Three requests to the independent ASAS-SN archive returned empty products for the target. New transit observation and catalogue-error attribution remain unestablished. [Registration](APRIL-REGISTRATION.json) · [Clock result](APRIL-CLOCK-RESULT.json) · [Archive result](ASASSN-RESULT.json)

## Timestamp diagnosis

The ExoClock inner-planet record `20467_TESS_TOI-216.02_495_2023-04-27` displays April 27. Its published fitted value `2460056.8146 BJD_TDB` converts to approximately **April 22 at 07:32:57 UTC** at geocenter. The registered interpretations cover JD, HJD and BJD in UTC and TDB, each with zero, minus or plus half a day. Even with those offsets, the implied dates span April 21–22. This work tests consistency of the reported timestamp with clock conventions and the frozen TESS fits. It cannot identify which observation, search window or fitting step produced the catalogue entry. [ExoClock .02 index](https://www.exoclock.space/database/planets/TOI-216.02/) · [Prior Sector 64 analysis](../../factory/REPORT.md)

Two fresh JPL Horizons responses provided Earth and Sun geometric state vectors relative to the solar-system barycenter in ICRF. A separate Astropy calculation using its bundled ephemeris agreed on all 18 transformed times within **0.000090 seconds**. Six synthetic conventions recovered the planted timing within the same bound. The checker rejected all four invalid-vector controls for frame, units, body identity or bracketing. The comparison validates the registered transformations. The tolerance includes the frozen statistical timing scales and a two-second margin for ground-site or TESS displacement. [JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html) · [Astropy time corrections](https://docs.astropy.org/en/stable/time/index.html#barycentric-and-heliocentric-light-travel-time-corrections) · [NASA TESS orbit](https://astrobiology.nasa.gov/news/tess-nasas-next-planet-hunter-takes-to-the-sky/)

| Frozen TESS comparison | Closest transformed candidate | Required agreement |
| --- | ---: | ---: |
| Outer planet c | 4,689.557 s | 584.689 s |
| Later inner planet b | 464,116.926 s | 740.654 s |
| Earlier inner planet b | 923,994.234 s | 718.469 s |

## Independent archive acquisition

The public Sky Patrol client protocol matched `TIC 55652896` to native target `652835415411` in both `stellar_main` and `master_list`. The match lies 1.024 arcseconds from the registered pointing. Three direct block requests across two publisher servers returned the same 3,267-byte Parquet with zero rows and no timestamp column. The same protocol returned **830 finite dated rows** for the publisher's documented example, demonstrating working photometry transport for that other object. The positive control required for the same target and April month remains missing. The Sky Patrol GUI returned HTTP 429 and the legacy published form endpoint returned 404. Public product coverage for TOI-216 remains unestablished. [Sky Patrol project](https://asas-sn.github.io/skypatrol/) · [Client and example](https://github.com/asas-sn/skypatrol#downloading-curves) · [Archived queries and exact bytes](ASASSN-RESULT.json)

The bounded archive study made 16 direct public requests and no paid, authenticated or physical observing actions. Raw response digests and byte counts are recorded where a body was acquired. The pinned Parquet dependency required a 47.7 MB wheel on this executor. Forecast and observing adoption remain **NO-GO**. An independent, clocked April light curve with usable contact coverage would reopen the attribution question. [Earlier ground-only controls](../../mission-executor/opportunity/SCIENCE.md)

## Reproduce

From the repository root, use a dedicated new directory and approved Python dependencies. The exact response digests identify this run. Horizons writes a fresh retrieval header. Compare `vector_payload_sha256` to verify its physical input matrix on recapture. New returned observation rows require the registered coverage audit before any fit.

```sh
work=$(mktemp -d)
python3 -m pip install --target "$work/deps" astropy==7.2.0 numpy==2.5.5 pyarrow==22.0.0
python3 publication/outcome-driven/science/recapture.py "$work/captures" --include-skypatrol
PYTHONPATH="$work/deps" OPENBLAS_NUM_THREADS=1 python3 -B publication/outcome-driven/science/april_clock.py "$work/captures"
PYTHONPATH="$work/deps" OPENBLAS_NUM_THREADS=1 python3 -B publication/outcome-driven/science/asassn_admission.py "$work/captures"
```
