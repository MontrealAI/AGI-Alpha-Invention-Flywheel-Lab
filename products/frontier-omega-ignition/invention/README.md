# From an alert to a usable observation

Six public Fink alerts designated as superluminous-supernova candidates led to two distinct deliverables for MONTREAL.AI’s public-data research desk.

**Four measured products.** In a later, held-out week, the survey recorded positive difference-flux detections for all six targets. Four have a g-band and r-band measurement less than two hours apart. The downloadable table gives each subtraction detection’s ZTF alert identifier, observation time, passband, difference magnitude and formal error. For ZTF26abydvon the two detections were 7.73 minutes apart on November 5. The difference-light measurement is g−r = +0.794 ± 0.172 mag. Two targets lack a qualifying pair in these data. A future exposure cannot recover the missing historical color.

**A changeable observing worklist.** A model of two observing nights and six twenty-minute windows can cover five different candidate positions once, or three positions twice with at least eighteen hours and a change of UTC date between visits. The worklist contains exact source IDs, UTC, pointing coordinates, and independently checked geometric limits. The operator can change the budget and cadence and reproduce the decision offline. All six windows are hypothetical. No organization offered telescope time.

## Use the instrument

Run from this directory with Python 3.11+ and its standard SQLite module. The first four commands run offline. Use a new output path for each delivery.

```sh
python3 qualify.py --check
python3 plan.py --out /tmp/new-followup-plan
python3 verify.py /tmp/new-followup-plan/worklist.json
python3 photometry.py --out /tmp/new-difference-photometry.csv --max-gap-minutes 120
python3 -m unittest discover -s . -p 'test_*.py'
```

Edit a copy of `mission.json` and supply it to both worklist commands with `--mission`. For example, change `visits_per_target` to 2 or `max_slots` to 4. Changes to positions, site, duration or offered times require regenerating the independent ephemeris. The results contain mission and catalog identities. The application has no telescope control or dispatch interface.

For another public ZTF-format alert cohort, provide the exact response bytes with `reference.py --alerts` and a matching `--source` descriptor following `sources/alerts-source.json`. Declare its issuer, class, URL, retrieval time, raw byte count and SHA-256, selection interval and sample size. Supply your mission and independent catalog to both planning commands. For a new photometry goal, `photometry.py --catalog … --observations … --source …` takes a bounded public detection projection and its matching hash, row count and half-open Julian-date interval. Everything operates on local files. The shipped provenance only applies to the shipped bytes.

## What entered the construction

The public Fink broker exposes dated class searches and object-level ZTF observations. Russeil et al. report that NOMAI supplies a rare-transient candidate stream based on multi-band light curves. The paper reports 22 recoveries among 24 active labeled examples as an upper bound on real-time completeness. That statistic never becomes a per-object probability here. The April preprint and September publication preceded this campaign. The October alerts and November measurements determine the product’s contents. The recorded work cannot establish that the algorithm first became possible within five weeks. [Primary classification study](https://doi.org/10.1051/0004-6361/202660399) · [April preprint](https://arxiv.org/abs/2604.14761) · [Fink class search](https://doc.ztf.fink-broker.org/services/search/classsearch/) · [Recorded classification semantics](https://doc.ztf.fink-broker.org/broker/classification/)

The frozen class query covered October 25 through November 1, UTC half-open. It returned six distinct targets for a request limit of 100 alerts. The whole 882-byte result is included in `sources/fink-alerts.json`. The raw SHA-256 is `bd0e18b40abb8d0371411481537485f065eb2b894df45ff1aa1fecf6422850ae`. `catalog.json` contains the query URL, an attributed target projection, and the independent reference. The archive was read on November 18 UTC. Alert timestamps predate the planning cutoff. A retrospective class query does not establish exactly what an operator saw at that instant. The planning input uses only the earlier class-query response. [Public class query](https://api.ztf.fink-portal.org/api/v1/latests?class=SLSN+candidate&n=100&startdate=2026-10-25&stopdate=2026-11-01&columns=i%3AobjectId%2Ci%3Ajd%2Ci%3Ara%2Ci%3Adec%2Ci%3Afid%2Ci%3Amagpsf%2Ci%3Asigmapsf&output-format=json)

The second public query requested positive/negative subtraction sign, candid, passband, JD, PSF difference magnitude and uncertainty for the same six objects. It returned 206 detections (32,792 bytes), of which 44 lay in the held-out November 1–8 UTC interval. We retained the bounded projection, original response length and SHA-256, retrieval time and query in `sources/`. Subsequent visits to the mutable endpoint can add or revise data. The pinned projection permits exact offline replay. Only the held-out photometry route reads these observations. [Fink object service](https://doc.ztf.fink-broker.org/services/search/objectid/)

The registered color calculation picks each target’s closest qualifying positive g/r pair. Its formal error uses quadrature of the two published per-point uncertainties assuming independent errors. The measurement describes the light in the difference images. A host-subtracted total-source color, a common epoch, extinction corrections, calibration covariance and a spectroscopic class would each require additional evidence. The CSV’s `g_candid` and `r_candid` fields identify the two individual subtraction detections. The `target_id` field identifies the astronomical object. A direct SQLite self-join, window ranking and formal-error calculation independently checks both detection identifiers, timestamps, measurements and abstentions. The registered two-hour threshold yields four products. An exploratory variation after the main test gives 0, 1, 2 and 3 products at 5, 10, 30 and 60 minutes. [ZTF alert schema](https://zwickytransientfacility.github.io/ztf-avro-alert/schema.html)

## What the worklist qualifies

The site at 32°N, 111°W is a geometric example at zero elevation. The contract requires target altitude of at least 30° and solar altitude of at most −18° throughout a visit, with an added degree of clearance. Both implementations sample each minute including the end. At the celestial rotation rate a point between the samples is within roughly 0.13° of one sample. One degree provides margin for sampling and the registered angular approximation. The producer computes approximate solar and precessed target positions and maximizes fully covered unique targets by packing nonoverlapping visit bundles. The direct route computes ephemerides with Astropy and enumerates permissible telescope assignments by slot, with the same calendar, permissions, targets and cadence. Every altitude/darkness eligibility decision matched across 36 target/slot pairs. The maximum difference between their computed extrema was 0.006394°. The procedures can select different equally good assignments. [USNO solar method](https://aa.usno.navy.mil/faq/sun_approx) · [Astroplan astronomical-darkness convention](https://astroplan.readthedocs.io/en/stable/api/astroplan.AtNightConstraint.html)

| Allowed visits | One visit per target | Two visits per target |
|---:|---:|---:|
| 0 | 0 | 0 |
| 1 | 1 | 0 |
| 2 | 2 | 1 |
| 3 | 3 | 1 |
| 4 | 4 | 2 |
| 5 | 5 | 2 |
| 6 | 5 | 3 |

All 14 registered results matched the direct route. `verify.py` also checks individual assignments, coordinates, margins, full cadence, source and mission identity. Changed inputs, fabricated angles, repeated, incomplete and suboptimal worklists are exercised in `test_invention.py`. A complete conventional route attains the same output quality in this study. The output is accepted for this offline geometric decision. Live access, source brightness at the offered time, limiting magnitude, S/N, Moon, horizon mask, weather, slews and calibration overhead, spectrograph suitability and exposure quality are outside that qualification.

To recreate the frozen Astropy reference from original source rows, use the package versions below. IERS auto-download is disabled. The local qualification used Python 3.12.14 and NumPy 2.2.6. Fresh ephemerides are a separate operation from desk replay.

```sh
python3 -m pip install 'astropy==7.2.0' 'pyerfa==2.0.1.5' 'astropy-iers-data==0.2026.11.16.0.37.44' 'numpy==2.2.6'
python3 reference.py --out /tmp/new-invention-catalog.json
cmp catalog.json /tmp/new-invention-catalog.json
```

## Economics and next decision

The possible benefit is a source-linked answer a researcher can actually use and fewer requests for data already in the archive. Four existing archival pairs fulfilled the registered data contract. No observation was canceled or resource saving measured. The scarce spectroscopy programme described by Gemini demonstrates real activity in this domain. Its participants have expressed no demand for this product. Fink and Lasair brokers, Astroplan/Astropy, direct SQL, manual scientific review and forgoing a request are credible alternatives. [Gemini observing programme](https://archive.gemini.edu/programinfo/GN-2026A-LP-210) · [Public alert brokers](https://rubinobservatory.org/for-scientists/data-products/alerts-and-brokers)

| Measured local step | Elapsed time |
|---|---:|
| Construct all 14 worklists using geometric calculations | 0.0291 s |
| Check all 14, including complete direct assignment | 0.0075 s |
| Direct assignment alone with the precomputed independent reference | 0.0070 s |
| Build the archival two-band products / run independent SQL | 0.0001 s / 0.0018 s |
| Rebuild independent ephemerides from original alerts, including Python startup | 0.857 s |

These are one-machine observations with inputs resident locally. The direct standalone timing excludes generating ephemerides. The verification timing already includes direct assignment. Original source acquisition, dependency installation, construction, checking, revisions, failed exploratory fetches, maintenance and operator integration all consume resources. External source-search time, all-in labor, model allocation, facility charges, delivered service price, customer acquisition, downstream support and avoided observing time remain unpriced. An attempted alternate TNS webpage fetch returned 403. It contributed no result. No purchase, external delivery, recruitment or revenue occurred. Both implementations were constructed in the included engineering session. No conventional human worker was timed.

**Next real test.** A willing observatory or archive user supplies an actual request, expected scientific product, allocation and constraints they have authority to share. Freeze a future shadow night before data arrive. Compare accepted measurements and complete cost with their existing broker plus scheduling/SQL workflow. Expose which viable requests expire, which existing measurements fulfill the request, whether anyone adopts the product and why. Spectroscopy requires its own instrument and science-quality acceptance. No outreach or booking took place.

## Présentation en français

Six candidats issus des alertes publiques Fink/ZTF ont donné lieu à deux résultats vérifiables. Les données d’archive de la semaine suivante contiennent 44 mesures. Pour quatre cibles, on peut livrer une mesure g−r de la lumière différentielle avec les identifiants ZTF des deux détections sur les images de différence et son incertitude formelle. Pour les deux autres, les données ne contiennent aucune paire admissible dans la fenêtre de deux heures. Le fichier CSV permet d’inspecter directement le résultat.

Pour une répétition géométrique sur deux nuits, six créneaux fictifs de vingt minutes permettent de couvrir cinq cibles une fois, ou trois cibles à deux reprises. Astropy et une affectation exhaustive indépendante retrouvent le même maximum dans les quatorze scénarios. Le calendrier est un exercice rétrospectif. La météo, l’instrument, le temps de télescope et la qualité spectroscopique restent à établir. Les seules observations physiques présentées proviennent de ZTF.

**Attribution.** This work uses publicly available measurements of the Zwicky Transient Facility, served and classified through the Fink community broker. Cite Bellm et al. (2019), Möller et al. (2021), and Russeil et al. (2026) for the respective original projects and methods. Derived schedules and photometry are MONTREAL.AI research outputs. Sponsorship, acceptance by any observatory, and paid redistribution rights have not been established. [ZTF public data](https://www.ztf.caltech.edu/ztf-public-releases.html) · [Fink documentation](https://doc.ztf.fink-broker.org/)
