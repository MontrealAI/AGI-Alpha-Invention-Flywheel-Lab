# Historical earthquake catalog audit

This second specialized capability reconciles dated USGS ComCat event records in a rectangle that crosses the antimeridian. It selects the latest published row for each event ID, preserves exact magnitude thresholds, and withholds IDs whose latest rows disagree. The standalone executable uses Python’s standard library. Its registered output is an event-ID selection for an archived catalog snapshot. [USGS ComCat](https://earthquake.usgs.gov/data/comcat/) · [Event API](https://earthquake.usgs.gov/fdsnws/event/1/)

| Observed historical panel | Records from the two halves | Eligible event IDs | Exact alternatives |
| --- | ---: | ---: | --- |
| Fiji region, July 2025 | 88 | 39 | Both agreed on every ID |
| Fiji region, June 2025 | 75 | 22 | Both agreed on every ID |

The two alternatives used a separate SQLite plan with exact rational collation and a separate request to the official USGS service using its shifted-longitude rectangle. All six public responses are archived by checksum, with full request addresses and acquisition times. This is agreement on the published records. The archive and all reported results are bounded by the exact source queries. [Registration](REGISTRATION.json) · [Observed results](RESULT.json)

A separate evaluator froze 40 cases before receiving the candidate, including controls for identical dateline aliases, revisions that withdraw eligibility, equal-timestamp contradictions, and near-boundary decimals. The candidate and exact Fraction oracle each scored **40/40**. The ordinary binary64 SQLite implementation scored **38/40** and included five ineligible IDs. The evaluator also replayed four slices of a separate 2014 Aleutian public sample. Evaluation and construction used separate authoring contexts on the same project administration. [Independent evaluation](../specialization-evaluation/)

**GO** for the registered portable historical audit. Use exact coordinate and revision handling. The standalone exact Fraction and SQL methods are viable alternatives. The matched local runs establish functionality and measured costs in this scope. They leave material economic advantage, catalog completeness, hazard inference and autonomous specialization unqualified.

## Reproduce

Run from this directory with Python 3.11 or later. The first command sequence uses the preserved research samples. `--fetch` on the last command performs six new bounded requests and may return later records or different metadata. Use a separate capture directory to preserve the existing archive.

```sh
python -B -m unittest -v test_specialist.py
python -B observe.py
python -B specialist.py samples/development_window.case.json
python -B observe.py --fetch --capture /tmp/frontier-usgs-new-capture
```

The input has `bounds` and `records`. Each record supplies `id`, `lon`, `lat`, `mag`, `time_ms` and `updated_ms`. Coordinates and magnitudes support finite decimal strings. A null magnitude is ineligible. Time is UTC epoch milliseconds, with an inclusive start and exclusive end. The result has sorted `included` and `conflicting` event IDs. A conflicting greatest revision suppresses that event ID.

On this Linux host the 21 paired in-process audits took approximately **0.13–0.15 ms** median wall time for the specialist and **2.73–3.25 ms** for the separately constructed in-memory SQLite comparison. The six acquisitions took about **18 s** in HTTP calls, excluding pacing. The faster in-process mechanism leaves transfer, whole-work and operating cost claims open.

## Français

Ce spécialiste vérifie des données sismiques historiques publiées par l’USGS dans une région qui chevauche l’antiméridien. Il retient la dernière révision de chaque événement et écarte les identifiants dont les dernières données se contredisent. Les seuils géographiques et de magnitude utilisent des décimales exactes. Le résultat distingue les événements retenus des entrées contradictoires.

Les trois méthodes exactes ont retenu les mêmes **39 événements en juillet** et **22 en juin 2025** dans la région des Fidji. Le candidat et le vérificateur indépendant à fractions exactes ont réussi **40 cas sur 40**. La version SQLite à virgule flottante a réussi **38 cas sur 40**. La qualification porte sur cet audit de catalogues historiques. Pour reproduire l’évaluation locale, utilisez les commandes ci-dessus. [Relevé des sources et résultats](RESULT.json) · [Évaluation indépendante](../specialization-evaluation/)
