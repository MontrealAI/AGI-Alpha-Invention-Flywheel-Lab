# Which observing dates warrant reprocessing?

An archive that used a provisional Earth-orientation forecast can use this instrument to identify dates worth revisiting. It compares the **specific forecast available at the time** with values a later IERS bulletin marked final. Each CSV row carries both issue identities and the applied tolerance. An independent reader verifies its dates, units, status, signed correction and final standard error against the original scientific publications.

**On the 35 registered UTC midnights, an illustrative 1.0 ms tolerance returned 1 date to reprocess, 2 to review, 28 to retain and 4 to defer.** The three production routes delivered the same 3,644 bytes. These are screening decisions on public data. Their operational value depends on whether an archive used this exact forecast, how the timing correction affects its science and what reprocessing costs.

[Open the work queue](archive-queue.csv) · [Recorded comparison and timings](OBSERVATION.json) · [Frozen comparison](REGISTRATION.md) · [Original source identities](SOURCES.json)

## Three dates explain the decision

| UTC midnight | Forecast UT1−UTC | Later final UT1−UTC | Final minus forecast | Final standard error | Action |
| --- | ---: | ---: | ---: | ---: | --- |
| 2026-08-31 | 0.00429 s | 3.2723 ms | −1.0177 ms | 0.0222 ms | Review. The tolerance lies inside the registered one-error margin. |
| 2026-09-01 | 0.00350 s | 2.4534 ms | −1.0466 ms | 0.0412 ms | Reprocess under this policy. Even the lower edge of the magnitude margin exceeds 1.0 ms. |
| 2026-09-02 | 0.00289 s | Pending in this edition | — | — | Defer. The later bulletin printed a numerical preliminary value. |

The margin is a screening convention. It uses the published final formal standard error. Calibration of a probability of error, full astrometric uncertainties, intranight interpolation and a change to actual archived science products would each require further evidence. Source section and edition matter. The forecast is edition XXXIX/031, published July 30. The comparison reference is issue 464, dated October 1. Their dates, units and product definitions are available from IERS. [Bulletin A metadata](https://datacenter.iers.org/versionMetadata.php?filename=mt/bulletina-xxxix-031.txt) · [Bulletin B metadata](https://datacenter.iers.org/versionMetadata.php?filename=mt/bulletinb-464.txt)

## Reproduce and change the decision

Python 3.11+ and its standard library suffice. The direct route and the independent verifier travel with this directory. The retained arm also imports the original sibling [Table Desk](../table_desk/table_desk.py). From the repository root, choose fresh output paths.

```sh
lab=products/frontier-omega-ignition/successor_field
python3 "$lab/triage.py" --route direct --output /tmp/iers-queue.csv
python3 "$lab/audit.py" /tmp/iers-queue.csv
cmp "$lab/archive-queue.csv" /tmp/iers-queue.csv
python3 "$lab/triage.py" --route ordinary --date 2026-09-01 \
  --tolerance-ms 2 --output /tmp/iers-2ms.csv
python3 "$lab/audit.py" /tmp/iers-2ms.csv --date 2026-09-01 --tolerance-ms 2
python3 "$lab/observe.py" --output /tmp/iers-comparison
python3 -m unittest discover -s "$lab" -p 'test_*.py' -v
```

The 2 ms contract changes September 1 to **retain**. The public slices support the registered dates listed in [cohort.py](cohort.py). The optional source check below fetches six bounded original files directly from IERS, verifies every SHA-256 and regenerates all six factual projections. It also accepts local source files via `--source-dir`. Normal reproduction is offline.

```sh
python3 "$lab/prepare.py" --output /tmp/iers-retrieved
```

## Experiment E · did retaining Table Desk help?

The earlier instrument accepted a reusable rectangular table. This mission requires a new dated action. The archive must reconcile two scientific issues, different precision and units, the correct one of three type columns, an uncertainty margin and the final/preliminary boundary. Both publications are new to this registered study. They are issued as ASCII with publisher-generated HTML and CSV editions. The experiment measures semantic table handling and archival triage. A new vision-model or physical PDF transcription was outside the executed comparison.

| Route under equal source permissions | Construction and evidence | Median producer + separate recipient audit |
| --- | --- | ---: |
| Adapted Table Desk | Verify two-tier grouped headings, UT units and legend. Pass the isolated rectangular body to the original reader. Its exact-cell checker compares date, status, value and error with the publisher CSV before applying the policy. | 45.5 ms + 34.4 ms |
| Ordinary reuse | Same public views, published parsing recipe, inherited component available to inspect, and identical scientific policy. Generic ElementTree extraction and complete row equality implement the recipe. | 32.2 ms + 25.8 ms |
| Direct conventional route | Read the publisher CSV, join dates in SQLite, compare exact integer ticks, deliver through the same recipient requirements. | 30.0 ms + 29.3 ms |

Each timing column uses the median of three fresh processes in cyclic order, measured on the qualification host. The producer includes acquisition from the local projections, imports, checks, computation and CSV publication. The separate recipient starts a new Python process and independently reads the two original ASCII sections. The direct route was the fastest median producer in this run. Source publication, human research, complete construction, hosting and later support are separate costs. The publisher produced all three views, so agreement checks interpretation of the same institution’s measurements.

The unadapted Table Desk refused both actual publisher HTML files because a grouped header spans multiple columns. The same refusal reproduces on the offline projections. An initial independent reader also treated the numbered section heading as a data year and withheld the first direct delivery. Accepting a four-digit year repaired this specific reader error before any CSV was delivered. All nine final route runs and their recipient checks passed. The old component now contributes to a different usable output. Ordinary reuse and the direct workflow achieved that same output. Improved invention capacity, saved total effort and intrinsic commercial advantage remain open. [Original instrument](../table_desk/README.md) · [Applied Foundry v2 mechanism, pp. 8–19 and 22–26](../../../docs/harness/OUT_PAPERS.md#foundry-v2--construct-and-qualify-a-reusable-discovery-instrument)

## Costs and experiment F · decision to adopt

| Cost or outcome | What the record establishes |
| --- | --- |
| Source search and acquisition | Six version-bound originals, 722,332 bytes, HTTP 200 for all six. Their overlapping fetches sum to 70.958 s of request time. The shared projection used 0.128 s wall time and retains 40,504 bytes of factual data. Discovery and model allocation have no itemized bill here. |
| Development, checking, failed work | An included coding agent wrote the adaptation and controls. The elapsed interval from local protocol creation to first independently accepted set of numerical decisions was approximately 219 s, including overlapping acquisition and other work. It excludes earlier discovery and subsequent tests, documentation, integration and CI. Active labor, per-arm build time and full economic cost are unknown. The initial reader failure consumed unmetered effort. The sequence was registered locally before scoring. It first appears publicly with the results. |
| Historical programme cost | The old Table Desk’s original visual-model qualification consumed 39.1139 wall seconds and 111.714 CPU seconds. Its OCR subprocesses took 1.016715 seconds. Those costs belong to the programme. The earlier programming, reference preparation, other qualification, and the portion attributable to this particular component are unpriced. [Historical receipts](../table_desk/evidence/) |
| Beneficiary, rights, value | An archive operator controls release identity, data rights, scientific tolerance, remediation and acceptance. Here the entire input is public factual material. No beneficiary archive or telescope was accessed. There is no observed avoided rerun, revenue, payment, financing, customer adoption or demonstrated profit. No native financial transaction was created. |
| Alternatives and maintenance | The publisher CSV and standard database require little custom code. Astropy distributes IERS data for ordinary time/coordinate transformations. Reproducing a *historical forecast vintage* still requires the corresponding edition. Future issue layouts, new units, rotations, deployment, support, liability and distribution require costing if this is adopted. The self-service and no-purchase alternatives remain available. [Astropy IERS documentation](https://docs.astropy.org/en/stable/utils/iers.html) |
| Human productivity | A competent human can select the two editions, use CSV/SQL or a spreadsheet and run conventional computation at machine speed. No human participants or work logs were collected. Wages, employer costs, preparation, correction, delivery and ongoing support have no measured comparison. |

**Next real adoption test for the flagship.** The astronomy worklist can be shadowed on one fresh observing night, using an operator’s own historical or prospective alert snapshot, observatory coordinates, ephemeris, allowed slots, actual overhead and scoring priorities. Freeze the eligible population and complete constraints before either route sees the outcome. Give a competent operator using the normal Fink/astroplan workflow, the direct exact schedule and IGNITION the same information and permissions. Have the operator check feasible windows, timing, missed opportunities, excess proposals and practical usefulness with route identity hidden where feasible. Record actual preparation, verification, corrections, operational obligations and any voluntary adoption or rejection. Collecting a trial requires an interested operator with an authorized data scope. No operator has joined this trial and no observing request was submitted. [Fink's existing services](https://fink-broker.org/about/) · [astroplan scheduling](https://astroplan.readthedocs.io/en/stable/tutorials/scheduling.html)

**Next real adoption test for this successor.** Pair one opt-in archived cohort with proof of its actual historical EOP input, an agreed scientific tolerance and the current archive procedure. If a site already used final data, the appropriate scope is empty and additional reruns have no demonstrated value. Compare the number and cost of owner-accepted avoided reruns with the full cost of acquisition, validation, manual review, errors and future upkeep. Capture an explicit accept, decline or defer disposition. The coarse transient schedule and this midnight timing study serve different decisions.

## Démonstration en français

**Faut-il reprendre le traitement d’une nuit d’observation après la publication des valeurs définitives de rotation de la Terre ?** Le fichier CSV compare la prévision connue à l’époque avec la valeur définitive et son incertitude publiée. Au seuil illustratif de 1,0 ms, sur 35 dates à minuit UTC, **1 est à retraiter, 2 sont à examiner, 28 sont à conserver et 4 demeurent en attente**.

Le 31 août, la correction de −1,0177 ms tombe dans la marge d’incertitude autour du seuil. Le 1er septembre, la correction de −1,0466 ms dépasse le seuil même après prise en compte de l’erreur formelle publiée de 0,0412 ms. Le 2 septembre, le bulletin ne donne encore qu’une valeur provisoire. Passer le seuil à 2 ms permet de conserver le 1er septembre selon cette règle. Les trois méthodes livrent le même fichier et un calcul indépendant vérifie chaque ligne à partir des bulletins originaux. Pour évaluer la valeur économique, il faudra un jeu de données d’archives réelles dont la prévision initiale est connue, ainsi que les coûts et critères scientifiques retenus par son responsable.
