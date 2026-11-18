# What changed when the desk retained the measurement history?

An archive desk could issue two change notices on October 26, 2026 from public detections of **ZTF26acbezdh**. The g-band difference magnitude had decreased by 0.836744 mag and the r-band magnitude by 0.557955 mag. Each pair uses the same detector channel and the same recorded ZTF reference-image processing ID within its band. The registered next same-band visit was missing from the detected series in both cases. The evidence supports a brightening in the positive difference signal over each baseline. Its later persistence remains unresolved. [October worklist and original sources](../invention/early_survey/)

## Independent comparison

The conventional route starts with the public broker responses. SQLite independently reconstructs the roster, nightly clock, latest eligible observation, same-detector comparison and earliest subsequent measurement. The receiver checks signed magnitudes, errors, reference IDs, broker rates, deadlines, dispositions, actions and missing evidence. Both routes have the same public data and may use existing conventional software.

| Registered scientific scope | Retained instrument | Direct SQL |
| --- | --- | --- |
| November 1–8 and November 10–17, SLSN candidates | 40 comparisons in 24 target/band scopes, 0 notices | Identical complete output, including the strongest measured change in each tested scope |
| October 25–November 1, four early SN Ia candidates, cold start | 3 comparisons, 0 notices | Identical complete output |
| Same October data, including seven prior days for baselines | 9 comparisons, 2 notices on one object, 0 adjudicable repeats | Identical complete output |

The previous two-band colour delivery retained 14 distinct detections from the first November week and 10 from the second. With its per-target counts it could establish only two of the 24 final issuance dispositions. One target had only one detection, so neither band could issue a two-detection notice. The other 22 dispositions remained unresolved from the reduced products. An executable counterexample places four observations into two alternative histories. Both produce identical data through the original colour instrument, while only one produces a persisting same-band change. The retained source responses and selection code enabled a different delivery. A direct archive analysis achieved the same result. [Comparison registration](REGISTRATION.md) · [Executable counterexample](test_verify.py)

Fink has supplied magnitude rate, uncertainty and time separation since December 2023. Its two individually matched October trigger rows give −0.162397 and −0.132321 mag/day; the frozen desk rule gives −0.168558 and −0.135625 mag/day. Both broker rows use detections. This checks direction on the original survey data and identifies a serious incumbent. It supplies no independent astrophysical observation. [Fink science module definitions](https://doc.ztf.fink-broker.org/broker/science_modules/) · [Source-by-source receipt](../invention/early_survey/RESULT.json)

## Cost of a checked delivery

The following medians include separate fresh Python processes on the same Linux x86-64 host. Production reads the pinned local files and writes a new JSON delivery. Acceptance reruns the counterpart from source and compares the complete content. The normal October product already runs an internal SQL check; its production time includes that work. The direct October producer needs no retained product helpers. Per-run accepted time includes both phases. The median of each sum can differ from the sum of separate medians.

| Local route | Rotations | Median production | Median independently checked delivery |
| --- | ---: | ---: | ---: |
| November retained | 3 | 105.8 ms | 163.9 ms |
| November direct SQL | 3 | 67.3 ms | 182.8 ms |
| November prior colour outputs, partial dispositions only | 3 | 52.7 ms | 153.0 ms |
| October retained | 4 | 137.4 ms | 205.7 ms |
| October direct SQL | 4 | 63.3 ms | 199.0 ms |

The October complete outputs each contain 17,368 bytes and have identical canonical SHA-256. Three public acquisition requests totaled 44,042 response bytes and 16.4957 s of request time. Both October routes share that upstream work. November source acquisition and the earlier instruments also belong to programme cost. The second November object query took 5.9898 s. Earlier colour construction and its SQL check were observed at approximately 0.0001 and 0.0018 s once inputs were resident. Original search, engineering, failed investigations, first-week acquisition time, model allocation, analyst review, distribution, support, access terms, ongoing maintenance and opportunity cost lack an all-in measurement. A preliminary timing harness launched an extra wrapper for one recipient, giving asymmetric recipient medians of 30.9 and 86.7 ms. The table uses the corrected paired protocol with each counterpart's normal entry point. [November measurements](OBSERVATION.json) · [October measurements and source digests](EARLY_OBSERVATION.json) · [Earlier acquisition and construction](../invention/README.md)

No prospective observatory, paid delivery, enterprise transaction, participant or human-only benchmark was observed. A competent operator can use the broker fields, public cutouts, direct SQL and the option to leave the queue empty. Full cost per independently confirmed physical change is undefined in these cohorts because none was adjudicated as persistent. Commercial redistribution rights and responsibility for false priorities would need an agreement. A willing operator's first shadow run should compare both systems on identical arrival times, cutoff, review budget, obligations and reference inspection. Record accepted priorities, missed or reversed priorities, coverage gaps, interventions, monetary costs and elapsed reviewer time. That experiment would test adoption value and the conventional human workflow.

## Reproduce

From the product root with Python 3.11+ and SQLite, or from the extracted public instrument for the two verification commands:

```sh
python3 -B evolution_trials/verify.py --check invention/evolution/RESULT.json
python3 -B evolution_trials/early.py --check invention/early_survey/RESULT.json
python3 -B -m unittest discover -s evolution_trials
python3 -B evolution_trials/observe.py --october --out /tmp/new-october-timing.json
```

The resource command uses POSIX process accounting. Run it with a new output path. The two direct recipients can also produce a complete JSON decision using `--out`, including an earlier `--as-of` UTC timestamp. The test suite checks every nightly revision and both microsecond sides of each published November detection. The October test checks the pending-to-expired transition and rejects a substituted reference-image ID.

**En français.** Le 26 octobre, les mesures antérieures permettent de signaler un éclaircissement en lumière différentielle dans deux bandes pour ZTF26acbezdh. Aucune détection admissible ultérieure n’a permis d’en établir la persistance dans le délai prévu. Le calcul SQL direct reproduit les deux avis, les identifiants des images de référence et les taux de variation publiés par Fink. L’utilité économique pour un observatoire reste à mesurer.
