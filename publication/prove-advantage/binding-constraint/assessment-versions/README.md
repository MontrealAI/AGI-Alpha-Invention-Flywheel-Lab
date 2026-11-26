# Reproduce published assessment scores

The version-aware replay recovers the published scores of three actual federal assessments. It selects the official form definition from the original export’s version and checks the bytes before applying the corresponding arithmetic. Use it for the three public records below and review provenance again when an original resource changes. [Exact input files and official published scores](SOURCES.json)

| Published assessment | Original form | Published mitigation | Current component replay | Version-matched replay |
| --- | --- | ---: | ---: | ---: |
| ESDC · Internal Activity and Access Monitoring | 0.10.0 | 31 | 26 | 31 |
| ISED · Non-Competitive Local Licensing | 0.10.0 | 34 | 29 | 34 |
| PrairiesCan and PacifiCan · funding review | 1.0.1 | 51 | 51 | 51 |

The captured current application components accepted the two legacy files. Four answered items still appeared in their imported data and contributed five points under the original form. The current scorer omitted those contributions. The impact levels were unchanged in these cases. This historical reproduction used genuine application components with offline import and document adapters. The archived official scorers independently reproduce the same published scores. [Component observations](COMPATIBILITY.json) · [Federal tool and scoring guidance](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/automated-decision-making/algorithmic-impact-assessment.html)

A separate Chromium replay of the captured official page confirmed the same displayed scores using the normal file input. The built-in download fallback saved the two legacy records as `v1.0.1` while preserving every answer. The modern control’s downloaded bytes matched its original input. Keep the original export as the source of its scoring version. The browser ran in fresh offline contexts, and the download test covered the built-in fallback. [Independent browser evidence](BROWSER-EVIDENCE.json)

## Legacy impact-level differences

Three additional public Immigration, Refugees and Citizenship Canada assessments are published as **Level II** in both languages. The captured current calculator displayed **Level I** after the original JSON exports were opened through normal file selection in Chromium. The original form reproduces the scores and levels in all six published PDFs. [Exact exports, report pages, hashes and observations](LEVEL-EVIDENCE.json)

| Published assessment | Published and original-form result | Captured current display |
| --- | --- | --- |
| Visitor Record Applications triage | Current 41 · Level II | Current 39 · Level I |
| International Experience Canada work permit eligibility | Current 36 · Level II | Current 34 · Level I |
| Integrity Trends Analysis Tool | Current 34 · Level II | Current 34 · Level I |

The maximum raw score is 126 in the original form and 167 in the captured current form. Both define Level I as at most one quarter of that maximum. The third record crosses the displayed level boundary with the numerical current score still at 34. Strict option-list screening withheld the Visitor Record case because one original encoded choice falls outside the tagged list. The archived calculator's scoring rule and both original PDFs agree on its historical score. A fourth initially flagged record could not be bound to its published historical result.

## Run the replay

Download the two form JSON files and the three assessment exports using the `href` and `filename` pairs in [SOURCES.json](SOURCES.json). Put them together in a local directory. The Python standard library is sufficient. The replay reads the exact original JSON and returns computed scores. The references to the five original published reports allow a separate documentary check.

```sh
python3 -B publication/prove-advantage/binding-constraint/assessment-versions/replay.py /path/to/inputs
```

Use `--case esdc-activity-monitoring` to replay one assessment with its matching form definition. Keep the original exports for future review and preserve their version information. The code uses the official forms published under the MIT licence and the public assessment material identified in the Canadian Open Government catalogue. The allowed inputs for this release are the exact records in the manifest.

For the impact-level study, place the three exports under their `filename` values in [LEVEL-EVIDENCE.json](LEVEL-EVIDENCE.json) beside `official-survey-0.10.0.json` from [SOURCES.json](SOURCES.json). Use `--level-study` with the same command. This mode follows the original calculator’s encoded-choice scoring for those exact files and checks the scores against the corresponding published reports. It refuses changes to the original bytes.

## Reproduire les résultats publiés

Le calcul reprend les résultats de trois évaluations fédérales. Il vérifie l’empreinte des fichiers et utilise le formulaire officiel qui correspond à la version de chaque export. Pour deux évaluations faites avec la version 0.10.0, les composants de la version actuelle ont produit une cote d’atténuation inférieure de cinq points. Le calcul à partir du formulaire d’origine a retrouvé les résultats publiés. Les niveaux d’incidence sont demeurés les mêmes.

Téléchargez les fichiers JSON indiqués dans [SOURCES.json](SOURCES.json), conservez les noms de fichiers et exécutez la commande ci-dessus. La reproduction concerne les documents publiés cités et leur version. Le résultat ne confirme pas la conformité ou l’état d’un système en exploitation.

### Trois écarts de niveau d’incidence

Trois évaluations d’Immigration, Réfugiés et Citoyenneté Canada sont publiées au **niveau II** en français et en anglais. Le calculateur actuel, reproduit dans Chromium à partir de ses composants officiels, a affiché le **niveau I** à l’ouverture des exports JSON d’origine. La cote actuelle est passée de 41 à 39 pour le triage des demandes de fiche du visiteur et de 36 à 34 pour l’admissibilité aux permis de travail d’Expérience internationale Canada. Elle est demeurée à 34 pour l’outil d’analyse des tendances en matière d’intégrité, dont le niveau affiché a tout de même changé. [Fichiers d’origine, pages et résultats vérifiés](LEVEL-EVIDENCE.json)

Pour reproduire les cotes publiées, ajoutez les trois exports du fichier [LEVEL-EVIDENCE.json](LEVEL-EVIDENCE.json) au même dossier que `official-survey-0.10.0.json`, en utilisant les noms de fichiers indiqués. Ajoutez `--level-study` à la commande ci-dessus. Le programme vérifie les empreintes avant de calculer les cotes selon le formulaire d’origine.
