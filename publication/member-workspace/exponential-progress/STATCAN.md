# AI plans in Québec and across Canada

**Planning scope.** In the third quarter of 2026, the estimated share of businesses planning to use AI to produce goods or deliver services over the next 12 months was **27.4% in Québec and 25.2% in Canada**. The gap was larger and positive for professional, scientific and technical services, and negative for information and cultural industries. Canada includes Québec. The results describe intentions and do not test the significance of province-to-national differences. [Statistics Canada table 33-10-1207-01, 2026](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3310120701) · [National analysis](https://www150.statcan.gc.ca/n1/pub/11-621-m/11-621-m2026013-eng.htm)

| Industries | Québec estimate and quality | Canada estimate and quality | Difference in percentage points |
| --- | ---: | ---: | ---: |
| All industries | 27.4% A | 25.2% A | +2.2 |
| Information and cultural | 36.6% D | 48.0% B | −11.4 |
| Professional, scientific and technical services | 65.7% C | 54.8% B | +10.9 |

Quality letters reproduce the survey metadata. A is excellent, B very good, C good and D acceptable. Responses were collected from July 2 to August 6, 2026. Each respondent's planning period starts with the date of their response. Canada-wide results agree with the separately published Statistics Canada summary. The English and French tables share the same survey observations. [Exact cells, province identifiers and vectors](STATCAN-RESULT.json)

## What the alternative delivered

This supports better questions for MONTREAL.AI when evaluating future sector-specific experiments. The comparison distinguishes industries that would be conflated by a single Québec average. It establishes neither individual demand nor realized adoption. No survey, buyer arrangement, external outreach or offer occurred.

The public LOCuST lead shaped the metadata-grounding check. We used the official coordinate, geography, scale, status and vector to verify the same six cells in two separately downloaded language editions of the same table. The first direct English filter found 2/6: the CSV adds industry codes `[51]` and `[54]` to the business labels found in the metadata. The competent conventional check used the exact data labels and matched 6/6. The October 1 Statistics Canada article independently exposed all three national point estimates and matched 3/3. The portable check uses Python with exact arithmetic and reproducible source digests. It took 0.473 seconds on the engineering host after acquiring 540,183 bytes across both downloads, including the conventional cross-check. Download time, author attention and downstream review were not isolated. [LOCuST](https://arxiv.org/abs/2611.32646v1) · [Frozen task](STATCAN-REGISTRATION.json) · [Executable check](statcan.py)

**GO** for this precise internal data check and reuse against identical official snapshots. **NO-GO** for a competitive AI advantage from the selected example. The conventional control produces the same business answer. A broader metadata-grounding experiment would need fresh held questions on multiple independently published data systems and relevant users.

A batch request to the ordinary public StatCan Web Data Service returned all six already identified vectors in a 2,295-byte response in 4.617 seconds. It matched the values, measure scale and quality letters from both editions. This route is an effective incumbent when the vector IDs are known. It uses the same survey. [Read-only WDS check](STATCAN-WDS.json) · [Official status-code definitions](https://www.statcan.gc.ca/en/developers/wds/user-guide)

## Reproduce

Use the two source URLs and SHA-256 digests in [STATCAN-REGISTRATION.json](STATCAN-REGISTRATION.json). Leave both ZIP files unchanged. The program reads the registered CSV member without extracting the archive.

```sh
python -B statcan.py "$capture/statcan-q3-en.zip" "$capture/statcan-q3-fr.zip"
```

Data from Statistics Canada, Canadian Survey on Business Conditions, table 33-10-1207-01, 2026. [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence)

## Français

Au troisième trimestre de 2026, **27,4 %** des entreprises au Québec et **25,2 %** des entreprises au Canada prévoyaient d’utiliser l’IA pour produire des biens ou fournir des services au cours des douze mois suivants. Dans les services professionnels, scientifiques et techniques, les estimations étaient de **65,7 %** au Québec et de **54,8 %** au Canada. Dans l’industrie de l’information et l’industrie culturelle, elles étaient de **36,6 %** et de **48,0 %**. Le total canadien comprend le Québec. Ces données portent sur des intentions déclarées. Elles ne mesurent ni l’adoption effective ni la signification statistique des écarts. [Tableau officiel de Statistique Canada](https://www150.statcan.gc.ca/t1/tbl1/fr/tv.action?pid=3310120701)

La vérification par code de série concorde pour les **six valeurs** entre les éditions française et anglaise d’un même tableau. Un filtre conventionnel corrigé donne les mêmes six résultats. Le programme et son reçu peuvent servir à reproduire le contrôle. L’étude n’établit aucun avantage économique ni aucune supériorité de l’IA pour ce travail. [Données et preuves](STATCAN-RESULT.json)
