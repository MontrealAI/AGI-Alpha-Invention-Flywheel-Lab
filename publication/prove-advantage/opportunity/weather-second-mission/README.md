# A held-gauge reconstruction for Montréal

**NO-GO for comparative advancement.** Over seven registered UTC days, PARDIG had mean absolute error of 0.19575 mm/day against the held Trudeau gauge. The ordinary estimate based on the St-Hubert gauge achieved 0.12857 mm/day. Both agreed with the reference on six of seven days at the 1.0 mm threshold. Each missed the only reference day above that threshold. Neither left nor right rectangular integration changed the score.

| UTC day beginning | ECCC Trudeau reference (mm) | Ordinary ECCC St-Hubert (mm) | PARDIG-NRT (mm) |
| --- | ---: | ---: | ---: |
| 2025-10-13 | 0 | 0 | 0 |
| 2025-10-14 | 1.6 | 0.7 | 0.22974 |
| 2025-10-15 | 0 | 0 | 0 |
| 2025-10-16 | 0 | 0 | 0 |
| 2025-10-17 | 0 | 0 | 0 |
| 2025-10-18 | 0 | 0 | 0 |
| 2025-10-19 | 0 | 0 | 0 |

## What ran

The registration was written before reading precipitation amounts. The target was the automated Montréal–Pierre Elliott Trudeau station 30165, climate identifier 702S006. The ordinary reconstruction borrowed the same UTC-day total from Montréal/St-Hubert station 48374, climate identifier 7027329, about 26 km away. Neither estimate used the held target amounts. The archive for the date range was already accessible for retrospective review. Where the target gauge is directly available, its reading is the simplest ordinary option. [Registration](REGISTRATION.json) · [ECCC station inventory](https://api.weather.gc.ca/collections/climate-stations/items?f=json&bbox=-74.1,45.3,-73.35,45.8&limit=125)

The script matched 24 hourly endings per station per day. The station CSVs report local standard time, so the conversion uses fixed UTC−05:00 during the October dates. The candidate used the nearest PARDIG-NRT 0.1° cell at 45.5° N and 73.7° W. It verified 97 quarter-hour coordinates for each day and applied the trapezoid rule to the instantaneous rates, including both boundaries. Rates in m/h become millimetres after multiplying by 1,000 and integrating in hours. Boundary rectangle alternatives used the same rates. Unavailable or flagged gauge values and missing or invalid model values require abstention. [PARDIG data contract](https://developers.google.com/weathernext/guides/pardig) · [ECCC technical documentation](https://www.climate.meteo.gc.ca/doc/Technical_Documentation.pdf)

The successful run took 23.75 seconds, including public acquisition, using a local CPU. The compressed PARDIG tile was 2,707,460 bytes. Both gauge receipts, exact source URLs and digests are recorded. A separate CSV reader and decimal-arithmetic check reacquired byte-identical gauge inputs, reproduced 14 daily totals across 336 hourly entries, and recalculated both errors. The first attempts stopped on an incomplete CSV row and an exhausted workspace volume respectively. The parser now records incomplete rows as unavailable. The registration and scoring stayed fixed, and seven days passed the completeness checks. No human time, commercial saving or operating cost was established. [Executed receipt](RECEIPT.json) · [Arithmetic crosscheck](CROSSCHECK.json)

## Timing and scope

**ABSTAIN for prospective use.** The archived time field gives a valid time. The downloads do not establish first availability at each decision deadline. This study is an exploratory retrospective check of one pair of stations and one wet reference day. It provides no calibration for other sites, no prospective workflow result and no evidence about safety, dispatch or actual economic usefulness.

To replay, use Python 3.11 or newer and the local `zstd` executable. From this directory, copy the script and registration into a temporary directory so the recorded receipt stays intact.

```sh
case_dir=$(mktemp -d)
cp REGISTRATION.json replay_precip.py "$case_dir/"
python3 "$case_dir/replay_precip.py"
```

## Français

Sur sept jours UTC prédéfinis, l’erreur absolue moyenne de PARDIG a été de 0,19575 mm par jour. L’estimation fondée sur le pluviomètre de Saint-Hubert a obtenu 0,12857 mm par jour. Les deux méthodes ont classé correctement six jours sur sept au seuil de 1 mm. L’heure de première disponibilité des données n’est pas établie pour un usage prospectif.
