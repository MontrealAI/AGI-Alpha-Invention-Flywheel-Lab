# FRONTIER Ω — Deux décisions utiles grâce à une capacité réutilisée

[English](README.md) · Expérience du 21 novembre 2026

**Nous avons construit et reproduit deux outils de décision par calcul :** un répertoire minimal de conditions réactionnelles qui préserve la qualité des rendements enregistrés, et un panel minimal de substrats qui préserve les distinctions entre profils de réponse catalytique. Les deux utilisent le même noyau d’optimisation exacte, inchangé, de 8 216 octets.

Une partie concrète d’un futur système de chimie automatisée devient ainsi utilisable aujourd’hui : transformer des mesures publiées en choix compacts et vérifiables. Le premier résultat fournit un répertoire de conditions; la capacité conservée résout ensuite un autre problème de conception expérimentale.

## 1. Premier résultat : cinq conditions complémentaires

La source contient **960 réactions enregistrées** : le couplage de l’indométacine à dix nucléophiles de type aniline, selon 96 combinaisons activateur/base/solvant. Chaque substrat doit atteindre au moins **90 % de son propre meilleur rendement enregistré**. Cinq conditions sont nécessaires et suffisantes pour satisfaire cette exigence pour **10 substrats sur 10**. La meilleure condition unique en couvre **4 sur 10**.

| Activateur | Base | Solvant | Identifiants des substrats attribués |
|---|---|---|---|
| TCFH | 1-Methylimidazole | DMF | n3, n9 |
| TCFH | 2,6-Lutidine | THF | n5, n6, n7, n8 |
| HATU | Diisopropylethylamine | MeCN | n10 |
| TCFH | Diisopropylethylamine | MeCN | n4 |
| DPPCl | N-methylmorpholine | MeCN | n1, n2 |

Le [résultat complet](evidence/first_portfolio.json) fournit les noms des substrats, les attributions, les rendements enregistrés, les seuils individuels, les lignes sources et un certificat d’optimalité. Il sert de répertoire de référence et de point de départ pour planifier une réplication. L’article source précise le contexte expérimental complet; ce tableau présente les composants variables.

**La préservation relative du rendement comporte des limites importantes.** Le rendement absolu attribué le plus faible est de **16,59 %**. La plus petite marge au-dessus du seuil requis est de **0,04 point de pourcentage**. L’incertitude de mesure est inconnue : la garantie exacte porte sur le tableau enregistré. La robustesse du rendement lors d’une nouvelle expérience reste à établir.

## 2. Deuxième résultat : six sondes préservent 253 distinctions

Le deuxième outil sélectionne les substrats qui distinguent les profils de réponse des ligands dans une borylation catalysée au nickel. Dans le cas principal, en éthanol, une distinction correspond à un écart absolu de rendement enregistré d’au moins **20 points de pourcentage**.

Le panel minimal comprend **six des 33 substrats** :

**s10 · s15 · s2 · s21 · s33 · s7**

Pour chacune des **253 paires parmi 23 ligands**, au moins un substrat sélectionné préserve cette distinction. Le [résultat du deuxième outil](evidence/successor.json) contient le panel, les rendements justificatifs reliés aux sources pour chaque paire, et son certificat.

Ce panel de référence compact permet de comparer les comportements catalytiques enregistrés et de préparer des mesures complémentaires. Les étiquettes `s…` correspondent au champ `electrophile_id`; les noms et identifiants moléculaires figurent dans la [table de correspondance source figée](https://github.com/doyle-lab-ucla/ochem-data/blob/e739f4d4d2002218fd225de5e8b2e6c235cabd6b/NiB/rxns/inchi_23l.csv). Une identification prospective exige des mesures comparables, un modèle d’erreur justifié et une bibliothèque de référence appropriée. L’écart de 20 points est une résolution déclarée, et non une borne d’erreur expérimentale étalonnée.

## Ce qui a été transféré et ce que montrent les comparaisons

[`cover.py`](cover.py) met en œuvre des méthodes connues de couverture minimale et produit des certificats d’optimalité vérifiables indépendamment. Le premier adaptateur traduit les exigences de rendement en contraintes de couverture. Le second traduit les paires de ligands distinguables en contraintes de couverture. **Le noyau est resté identique octet par octet** après le [gel du premier composant](evidence/FIRST_ASSET_FREEZE.json); le deuxième outil réutilise sa capacité de résolution et de certification.

| Cas principal | Noyau conservé | Méthode gloutonne indépendante | HiGHS indépendant |
|---|---:|---:|---:|
| Amidation, rendement relatif de 90 % | 5 conditions | 5 | 5 |
| Nickel / éthanol, écart de 20 points | 6 substrats | 8 | 6 |

Les **15 cas déclarés** ont été exécutés. Les vérifications indépendantes des sources, des résultats et des certificats ont accepté [les cinq premiers cas](independent/FIRST_FULL_VERDICT.json) et [les dix suivants](independent/SUCCESSOR_FULL_VERDICT.json). HiGHS et un autre solveur exact confirment tous les minima. Le [témoin exécuté à contenu identique](independent/WRAPPER_TRANSFER_QUALIFIED.json) utilise une copie distincte du même code : résultats et certificats concordent pour dix cas, avec cinq répétitions par bras. La [revue indépendante](independent/REVIEW.md) consigne 36 altérations sémantiques ou de preuves rejetées. Ces résultats rejoignent ceux de méthodes classiques compétentes.

L'[audit complet actuel](independent/WRAPPER_AUDIT_QUALIFIED.json) vérifie également l'identité du code figé. La [revue des commandes](independent/WRAPPER_REVIEW.json) consigne 16 tests supplémentaires de rejet en ligne de commande, les corrections et les reçus antérieurs qu'ils remplacent. Le [bilan et les enseignements](OUTCOME_AND_LESSONS.json) précisent la contribution utile, les échecs observés, les coûts non mesurés et la preuve économique encore manquante.

| Seuil de rendement relatif | 50 % | 70 % | 80 % | 90 % | 95 % |
|---|---:|---:|---:|---:|---:|
| Nombre minimal de conditions | 2 | 3 | 5 | 5 | 7 |

| Écart du deuxième outil, en points de pourcentage | 10 | 15 | 20 | 25 | 30 |
|---|---:|---:|---:|---:|---:|
| Panel minimal en éthanol | 3 | 4 | 6 | 9 | 10 |
| Panel minimal en méthanol | 4 | 4 | 6 | 9 | 9 |

À 30 points, quatre paires en éthanol et trois en méthanol restent indiscernables, même avec le tableau complet; les résultats les signalent explicitement. Les trois fichiers sources contiennent au total **2 478 lignes enregistrées** : 960 + 759 + 759.

Le transfert était planifié : la famille du deuxième problème était anticipée, et un nouvel adaptateur a utilisé un solveur existant. Le résultat établit deux instruments rétrospectifs utilisables et une réutilisation concrète de capacité. L’invention économique autonome, la supériorité d’une méthode d’invention, une nouvelle chimie, les économies d’essais physiques et les revenus restent à établir. Les ensembles de conditions complémentaires et la couverture minimale ont des antécédents directs.

## Reproduire localement

Exécuter depuis ce répertoire avec Python 3.12 ou une version ultérieure. Les outils principaux et l’audit utilisent uniquement la bibliothèque standard. L’accès Internet sert à récupérer les sources figées; les fichiers existants sont contrôlés par empreinte cryptographique.

```bash
python fetch_sources.py --data-dir data
python portfolio.py --csv data/amidation.csv --output outputs/first.json
python successor.py --data-dir data --output outputs/successor.json
python audit.py --data-dir data --first outputs/first.json --successor outputs/successor.json --output outputs/audit.json
```

Les fichiers JSON contiennent les décisions, les éléments justificatifs et les certificats. Effectuer l’audit avant d’utiliser un résultat reproduit. Les durées peuvent varier selon la machine.

Pour les comparaisons facultatives avec les solveurs indépendants :

```bash
python -m pip install -r requirements-comparison.txt
python independent/baselines.py --stage first --source-root data --output outputs/first-baselines.json --repeats 5
python independent/baselines.py --stage successor --source-root data --output outputs/successor-baselines.json --repeats 5
python transfer_check.py --successor outputs/successor.json --baseline outputs/successor-baselines.json --output outputs/transfer-control.json --repeats 5
```

## Sources et interprétation

- **Données figées :** [dépôt du laboratoire Doyle, commit ae3e910…](https://github.com/doyle-lab-ucla/bandit-optimization/tree/ae3e910dcea27cfd1631a28b793b6c63607baedd). Les valeurs originales, dont trois rendements d’amidation négatifs, sont conservées. Les fichiers nickel constituent un sous-ensemble complet de 23 ligands. Les empreintes, la licence source GPLv3 et les limites liées à l’étalonnage sont documentées dans [SOURCES.md](SOURCES.md).
- **Mesures d’amidation :** Wang et al., *Identifying general reaction conditions by bandit optimization*, Nature (2024). [DOI : 10.1038/s41586-024-07021-y](https://doi.org/10.1038/s41586-024-07021-y).
- **Mesures nickel :** Stevens et al., *Advancing Base Metal Catalysis through Data Science*, Organometallics (2022). [DOI : 10.1021/acs.organomet.2c00089](https://doi.org/10.1021/acs.organomet.2c00089).
- **Antécédent direct des répertoires :** Sivilotti et al., *Active learning high coverage sets of complementary reaction conditions*, Digital Discovery (2025). [DOI : 10.1039/d4dd00365a](https://doi.org/10.1039/d4dd00365a).
- **Contexte pratique :** Stevens et al., *Structured HTE Data and Integrated Bayesian Optimization Accelerate Scalable Amidation Process Development* (2026), décrit des répertoires ciblés en développement industriel. [DOI : 10.1021/acsorginorgau.6c00051](https://doi.org/10.1021/acsorginorgau.6c00051). Cette publication ne valide pas le répertoire particulier présenté ici.
