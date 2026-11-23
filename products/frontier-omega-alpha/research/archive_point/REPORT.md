# FRONTIER Ω ALPHA · Recover a bounded exact public forecast point

**A standalone direct NOAA archive query now recovers the registered 2 m temperature without transferring the whole selected field or depending on a point-subsetting service.** Six held requests matched ECMWF ecCodes numerically at the exact native grid cell. Every direct point query fit the preregistered **384 KiB** response-payload budget. The indexed conventional full-field path exceeded that budget on all six. A working NCAR point service remains the most transfer-efficient ordinary route.

[Preregistered contract](registration.json) · [Signed receipt](evidence/confirmation.json) · [Conventional retry](evidence/point-service-retry.json) · [Standalone query](evidence/standalone-query.json)

## Why this target

MONTREAL.AI internal archive research is the beneficiary. The living November 23 Frontier Atlas supplied the portable-instrument and scientific-instrument entries. The reviewed weather-data lead exposed a concrete bottleneck: the primary archive distributes public NOAA GFS objects containing complete model fields, even for a one-point study. In development, the 2024-01-15 00Z f024 object had 540,110,427 bytes. Competent indexing already narrowed it to an 871,538-byte temperature field. The invention target was the remaining unnecessary transfer and reconstruction, with a second complete server-side comparator. The broader search and actual deferrals span an unavailable physical experiment, the AnyS1 representation lead, RepoFactory experimental environments, supplier intake and a funding arrangement. The last four lack complete cleared workflows, accepted outcomes or validated commitments for this run. [Living Frontier Atlas](../possibility_observatory/evidence/atlas.en.md) · [NOAA GFS open archive](https://registry.opendata.aws/noaa-gfs-bdp-pds/) · [NCAR archive and subsetting](https://gdex.ucar.edu/datasets/d084001/dataaccess/) · [AnyS1](https://arxiv.org/abs/2611.23751) · [RepoFactory](https://arxiv.org/abs/2611.21152)

## Different means and held results

GRIB2 5.3 stores grouped spatial differences. For the registered scan order, only the prefix through the requested grid cell contributes to the result. The implementation validates forecast time, discipline, origin, grid spacing, field type, 2 m height, missing-value rules, metadata sizes and archive range response. It uses group offsets and the closed-form recurrence for constant groups to recover the point from a bounded prefix without reconstructing a global grid. Unsupported encodings or times abstain. NOAA defines the packing and recursive recovery. The ordinary comparator uses the same index and whole selected message with ecCodes 2.50.0. NCAR uses its ordinary public coordinate subset, with cycle, valid time, native coordinate and kelvin verified and its explicit 2 m request checked against the independent full-field output. [NOAA encoding template](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-3.shtml) · [NCAR subset access](https://tds.gdex.ucar.edu/thredds/catalog/files/g/d084001/2025/20250605/catalog.html?dataset=files%2Fd084001%2F2025%2F20250605%2Fgfs.0p25.2025060512.f024.grib2)

| Mode | Accepted on first attempt | Within the payload budget | Payload summed over six | Sum of measured cold request and decode wall time |
| --- | ---: | ---: | ---: | ---: |
| Bounded direct-origin decoder | 6/6 | 6/6 | 2,213,597 B | 46.63 s |
| Indexed complete NOAA field and ecCodes | 6/6 | 0/6 | 4,409,832 B | 46.08 s |
| NCAR coordinate subset | 5/6 | 5/6 | 1,001 B | 83.52 s |

The direct implementation read **49.8% fewer payload bytes** than the indexed full-field route. All six direct pairs had identical decoded doubles under the declared tolerance. The first NCAR request for the winter Québec-area case returned HTTP 200 headers and timed out before a response body. One separately recorded retry returned the same accepted value with 200 more bytes in 20.10 seconds. A competent retrying point client thus reached 6/6 under the experimental payload budget when NCAR responded. The original timeout and unsuccessful development NetCDF request were retained as observed limitations, not an estimate of service availability. The Ubuntu device used the approved public host networking path through curl. The alternate Python development transport previously refused the archive origin. The signed receipt retains raw response digests, ETags, ranges, per-arm unresolved states, latencies, decoder thread CPU, child CPU for the complete run and all query identities. Shared index cost is charged to both direct arms in the table. The body counts exclude HTTP/TLS and provider compute. Library downloads, service work, energy, labor, maintenance, downstream acceptance and effective cost remain incompletely measured. The disposable comparator install reported about 61 MB of wheels and is separate from the experimental data budget.

### Executable operating envelope

The standalone command serves the direct-origin outcome without fetching ecCodes or contacting NCAR. On 2024-01-18’s archived Québec-area cell it delivered **257.85171875 K with 368,932 bytes** in a separate use of the instrument. The inputs are archives and model forecasts, so this result cannot establish realized weather. The experimental transfer bound is not a customer or operational requirement. The tested technical capability can be kept as research software. Productive S₁ admission, full economic advantage, causal S₂ transfer and constructor or learning-rule improvement remain unqualified.

```sh
lab=products/frontier-omega-alpha/research/archive_point
python3 -B "$lab/query.py" --day 2024-01-18 --cycle 00 --latitude 46.75 --longitude -71.25
python3 -B "$lab/replay.py" audit "$lab/evidence/confirmation.json" \
  --key-sha256 d16ea889e128693e68fe91802e3228849ee4a92f6984f51a12ba4da86ae34a9e
```

For a fresh live comparison, install the public `eccodes==2.43.0` Python binding and record its actual native API version, then run `replay.py run --state PRIVATE_STATE --output OUTSIDE_STATE/confirmation.json`. It uses the registered six trials and keeps matching checkpoint state for resumption. The offline audit checks the signature and recomputes acceptance from frozen results. It does not fetch or decode raw GRIB messages. Endpoint **ABSTAIN**, indexed SQLite, the #567 conventional Gaussian-process winner and the exact prior signed evidence remain in force. [Accepted #567 research](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/567) · [Production gates #550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550)

## Français

**Le nouvel outil extrait un point de l’archive NOAA dans la limite expérimentale de 384 Kio, sans devoir transférer le champ complet.** Il a reproduit les six températures à 2 m obtenues indépendamment avec ecCodes. Le transfert direct total est passé de 4 409 832 à 2 213 597 octets, une réduction de **49,8 %**. Le temps direct total est comparable. Le service de sous-ensemble de la NCAR a servi cinq points avec beaucoup moins d’octets. La sixième requête a expiré, puis une relance indépendante a obtenu la valeur attendue. Cette expérience établit une capacité technique dans le périmètre testé. Les coûts complets et l’avantage économique restent inconnus. Aucun S₁ productif, transfert causal S₂ ou gain d’apprentissage n’est établi. [Résultat signé](evidence/confirmation.json)
