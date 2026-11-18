# FRONTIER Ω IGNITION · Endpoint Lab

Open `FRONTIER_LAB.html` in an offline browser, or use **Enter the Endpoint Lab** in the local workbench. The EN/FR button changes the entire exhibit. Public-source links require a network connection only when opened. All observations below refer to the reports captured on November 17, 2026.

## Five minutes in English

| Time | Show | Say or ask |
| --- | --- | --- |
| 0:00 | Opening curve | “MONTREAL.AI has one experiment to allocate. Which published load should we investigate for an interactive service?” Each dot is one real run. The axes are logarithmic. Gold marks runs satisfying both displayed limits. |
| 0:40 | **Interactive GPT-OSS**, then **Inspect the comparison** | “At most 500 ms to first token at P90 and at least 100 reported tokens/s per user.” The highest-throughput row has 22,528 concurrent queries, 509.0 ms and 42.1 tokens/s per user. Run 4 meets both limits at 140, 147.6 ms and 294.4 tokens/s per user. The next recorded load is 272. Re-measure that load and the selected point on authorized infrastructure using representative requests. |
| 1:40 | **Require a verified price** or **MONTREAL.AI’s own traffic** | Ask the audience which missing input would change its decision. The instrument abstains. It records neither an effective price nor observations of the lab’s traffic. An equipment category marked “Available” establishes no right to use it. |
| 2:10 | **What does “tokens per second” mean?** | Move the slider to 110. DeepSeek’s reported per-user field selects 64 concurrent queries. The inverse of P90 time per output token selects 128. At 64 tokens/s, the corresponding choices reverse order, at 512 and 256. Across 400 tested thresholds, 109 choices changed. Independent SQL agreed with the decision code across all 800 evaluations. These counts refer to the tested thresholds. |
| 3:05 | Source inspection and opportunity field | Adjust both limits, inspect the underlying source table, or choose NVIDIA’s provisional report. Provisional rows can be read and filtered here. The evidence contract requires a verified source. Select the overlooked alternative. Using the publisher’s table, direct SQL and one representative local benchmark is a credible competing workflow. |
| 4:00 | **Take the decision apart** and remaining experiments | Download the instrument and the standalone page. The archive contains both earlier exhibitions. The numerical study recovered 20/20 cells on a published simulated-outcomes table across all four methods. In the calibrated two-page case the initial model receiver withheld. Later processing of the same generation recovered 25/25 cells and the qualifying note on both pages. The reader study has zero participants. Reader time, accuracy, accessibility benefit and full operating cost are open. |

The endpoint study registered nine cases and checked seven corrupted receipts. It answers a retrospective workload question. There was no service deployment, customer engagement, human productivity observation, capacity reservation or measured economic return.

## Cinq minutes en français

| Temps | Montrer | Dire ou demander |
| --- | --- | --- |
| 0:00 | Courbe d’ouverture | « MONTREAL.AI peut consacrer son prochain essai à une seule charge. Quel point publié mérite un essai pour un service interactif? » Les axes sont logarithmiques. Chaque point représente un essai réel. Les points dorés respectent les deux seuils affichés. |
| 0:40 | **GPT-OSS interactif**, puis la comparaison | Fixez le délai P90 du premier jeton à 500 ms et le débit minimal publié à 100 jetons/s par personne. Le débit total maximal correspond à 22 528 requêtes simultanées, 509,0 ms et 42,1 jetons/s par personne. L’essai 4 satisfait aux deux exigences à 140 requêtes, 147,6 ms et 294,4 jetons/s par personne. Le prochain point publié est 272. Mesurez ces deux charges sur une infrastructure autorisée avec des requêtes représentatives. |
| 1:40 | **Exiger un prix vérifié** ou **Requêtes réelles de MONTREAL.AI** | Demandez quelle donnée pourrait faire évoluer la décision. L’instrument s’abstient. Le dossier ne contient ni prix effectif ni observation des requêtes du laboratoire. La catégorie de disponibilité du matériel ne constitue pas un droit d’accès. |
| 2:10 | **Que signifie « jetons par seconde »?** | À 110 jetons/s, le débit publié par personne admet 64 requêtes simultanées pour DeepSeek. L’inverse du délai P90 par jeton en admet 128. À 64 jetons/s les deux chiffres sont 512 et 256. Le choix change pour 109 des 400 seuils étudiés. Le calcul SQL indépendant concorde avec le programme pour les 800 évaluations. |
| 3:05 | Tableau source et pistes de recherche | Modifiez les deux seuils. Le rapport provisoire de NVIDIA peut être examiné, mais les décisions enregistrées exigent une vérification. Ouvrez la piste souvent négligée. Le tableau de l’éditeur, SQL et un essai local représentatif constituent une méthode concurrente sérieuse. |
| 4:00 | **Refaites le calcul** et expériences suivantes | Téléchargez le dossier et la page autonome. Le ZIP contient les deux expositions précédentes. Les quatre méthodes ont récupéré les 20 cellules d’un tableau publié de résultats simulés. Sur l’étalonnage de deux pages, l’adaptateur initial du modèle s’est abstenu. Une reprise de la même sortie a récupéré les 25 cellules et la note de chaque page. L’étude de lecture compte zéro participant. Temps, exactitude, gains d’accessibilité et coûts complets restent à mesurer. |

## Reproduce / Reproduire

Extract the instrument beside the saved exhibition and open a terminal in the extracted folder. Use a new receipt filename for each run. Extrayez le dossier à côté de l’exposition enregistrée, ouvrez un terminal dans le dossier extrait et utilisez un nouveau nom de reçu à chaque essai.

```sh
python3 -B decide.py --contract cases/interactive_gpt.json --output my-receipt.json
python3 -B reference.py --contract cases/interactive_gpt.json --receipt my-receipt.json
python3 -B reference.py --contract cases/interactive_gpt.json
```

The third command displays the independent SQL selection. Copy a contract from `cases/`, change one requirement and rerun both programs. Inspect `sources/manifest.json` for publisher links and table hashes. La troisième commande affiche le choix indépendant de SQL. Copiez un fichier de `cases/`, modifiez une exigence, puis relancez les deux programmes. Les liens des éditeurs et les empreintes des tableaux figurent dans `sources/manifest.json`.
