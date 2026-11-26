# Find public AI impact assessments

[Open the 24 verified links](LINKS.json). Search by system name or AI Register ID. Each entry gives the English and French system names, responsible organization, and the exact published assessment resource. The Government of Canada’s November 18 consultation identified missing links to assessments as a barrier to public scrutiny. [Consultation findings](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/advancing-ai/progress/consultations-government-canada-ai-register-what-we-heard.html) · [Original register and Open Government Licence](https://open.canada.ca/data/dataset/fcbc0200-79ba-4fa4-94a6-00e32facea6b)

Use the scope notes when a source concerns a particular module, phase, or edition. Catalogue listing and modification times describe the published resource. The documented assessment and the system’s current deployment can refer to different stages. This index establishes documentary identity within the reviewed scope. It leaves regulatory applicability, compliance, current deployment assurance, and the existence of unpublished assessments unresolved.

## Recheck a source

From the release checkout, run the command with the exact `register_id` from the index. Python uses the original public download and verifies its size and SHA-256. A changed source requires a new review before reusing its qualification.

```sh
python3 -B publication/prove-advantage/binding-constraint/assessment-links/verify.py \
  --system 2526-ESDC-EDSC-011 --verify
```

Omitting `--verify` retrieves the index entry locally. The verifier does not interpret the assessment and needs no model, account or API key.

## Independent result

The April register had 412 entries across 43 organizations and no dedicated assessment-link field. We searched the official catalogue and obtained 121 original assessment resources on the resolved acquisition run. We compared a same-organization, exact-title workflow with a candidate that also inspected original documents and reviewed scope evidence. An independent evaluator froze 16 cases before opening the outputs.

| Workflow | Exact links on 8 supported cases | Erroneous links on 8 withheld cases |
| --- | ---: | ---: |
| Exact title and original document | 5 | 0 |
| Candidate with scope evidence withheld | 5 | 0 |
| Candidate with reviewed scope evidence | 7 | 0 |
| Independent direct review with official search and original sources | 8 | 0 |

Direct review found the assessment for `2526-ESDC-EDSC-011`. Its publication title names the report differently, and the assessment’s project description establishes the match. That case entered the released index through separate review after the frozen trial. A second reviewer independently checked 16 additional documented identities outside the held set. Those 16 and the eight supported held cases form this 24-entry snapshot. The measured comparison favored direct review. Complete operator cost and adoption remain unmeasured. [Frozen comparison and source acquisition](../EVALUATION.json)

Two original legacy assessment exports require their matching forms to reproduce the published mitigation scores. [Reproduce the published scores](../assessment-versions/README.md)

## Consulter les évaluations algorithmiques publiques

[Ouvrez les 24 liens vérifiés](LINKS.json). Recherchez le nom du système ou son identifiant dans le Registre de l’IA du gouvernement du Canada. Chaque entrée indique les noms français et anglais, l’organisation responsable et la ressource publiée. Consultez les notes de portée pour les évaluations qui concernent un module, une phase ou une édition précise.

La commande ci-dessus récupère le fichier public d’origine et vérifie sa taille et son empreinte SHA-256. Sans `--verify`, elle consulte seulement l’index local. Si la source change, il faut revoir l’édition avant de réutiliser la qualification. Le rapprochement documentaire ne constitue aucune conclusion de conformité, et la version en exploitation peut différer de celle qu’évalue le document publié. [Registre officiel](https://open.canada.ca/data/fr/dataset/fcbc0200-79ba-4fa4-94a6-00e32facea6b)

[Reproduire les résultats avec la version d’origine de chaque formulaire](../assessment-versions/README.md)
