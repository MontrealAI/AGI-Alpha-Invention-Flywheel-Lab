# CONTINUITÉ Ω — Lire le résultat consigné en français ou en anglais

[English](OUTPUTS.md) · **Français** · [Démarrage rapide](QUICKSTART.fr.md) · [Guide du prototype](README.fr.md)

Le compagnon de lecture présente les artefacts de transfert, d’audit et de refus consignés par le prototype dans la langue choisie. Il conserve les identifiants bruts, les codes de statut, les quantités, les montants et les empreintes des fichiers. **Un rapport lisible ne constitue ni un nouvel audit, ni une certification, ni la preuve qu’un engagement envers un client a été tenu.**

Le prototype d’origine demeure inchangé. Ses messages au terminal et son `PASSPORT.md` d’origine utilisent l’anglais ; le compagnon fournit une lecture complète en français ou en anglais des sorties JSON prises en charge, avec des explications, une aide et des erreurs localisées. L’édition bilingue **1.1.1** de l’article reste une publication distincte.

## Lire un exercice nominal

Python **3.10+** suffit. Exécuter les commandes depuis la racine du dépôt ; aucune installation, clé d’API, connexion réseau ou action externe n’est nécessaire.

```bash
python3 -m continuity_omega demo --case nominal --out /tmp/continuity-reading-demo-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language fr
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language en
```

La première commande crée un nouvel exercice synthétique. Les deux suivantes lisent les mêmes enregistrements et affichent du Markdown au terminal. Pour créer une lecture à partager, choisir un **nouveau fichier absolu hors du dossier des éléments probants**, dont le dossier parent existe déjà :

```bash
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language fr --out /tmp/CONTINUITY_READING_FR_001.md
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language en --out /tmp/CONTINUITY_READING_EN_001.md
```

Utiliser de nouveaux noms lors d’une nouvelle exécution. Le lecteur refuse les fichiers de sortie existants, les liens symboliques de sortie, les chemins de sortie relatifs et les sorties situées dans le dossier des éléments probants. Il n’écrase jamais `PASSPORT.md`, ne modifie aucun audit et ne change aucune décision d’acceptation.

```bash
python3 scripts/continuity_passport.py --help
python3 scripts/continuity_passport.py --language fr --help
```

L’aide est bilingue par défaut. Choisir `--language en` ou `--language fr` pour localiser l’aide, les erreurs de validation et le texte du rapport. Le choix de langue est obligatoire pour produire un rapport.

## Lire aussi un refus

Un refus renseigne utilement sur ce que le constructeur a refusé de proposer. Exécuter les commandes suivantes séparément : la première renvoie volontairement le **code de sortie 2** et crée un enregistrement `REJECTION.json`.

```bash
python3 -m continuity_omega demo --case overbooked --out /tmp/continuity-reading-refused-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-refused-001 --language fr
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-refused-001 --language en
```

Pour ce cas, la lecture française explique qu’aucun fournisseur simulé ne satisfait la capacité et le délai. Le lecteur renvoie **0**, car il a présenté avec succès un enregistrement de refus pris en charge. Il n’a ni transformé le refus en validation ni réexécuté le constructeur.

## Comprendre les décisions

| Code consigné ou résultat de commande | Signification |
| --- | --- |
| `READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT` | Indicateur de préparation enregistré par le constructeur. Il ne constitue ni une acceptation ni le résultat d’un nouvel audit. |
| `PASS_SYNTHETIC_ONLY` | Décision enregistrée du vérificateur synthétique. Le rapport n’établit ni que cette décision correspond encore aux fichiers, ni que la source est authentique, ni que l’activité a repris. |
| `FAIL` | Échec d’audit enregistré. Le rapport conserve le nombre d’échecs consigné et explique chaque code indiqué. Le nombre historique peut dépasser le nombre de codes distincts, car le comptage précède la déduplication. |
| `REJECTED_BEFORE_HANDOFF` | Le constructeur a consigné un refus avant de proposer un transfert. Les coûts réels et les conséquences pour les clients n’ont pas été mesurés. |
| Sortie `0` du lecteur | L’enregistrement pris en charge a été présenté, y compris s’il consigne un refus ou un échec d’audit. |
| Sortie `2` du lecteur | Le lecteur a refusé un enregistrement non pris en charge ou mal formé, un chemin de sortie non sûr ou une commande invalide. Aucun rapport partiel n’est créé pour une entrée non prise en charge. |

Le vérificateur est implémenté indépendamment **sous forme de code distinct produit par les mêmes auteurs**. Il ne s’agit pas d’une certification indépendante externe. Tous les scénarios d’exercice fournis sont synthétiques. Ces enregistrements ne confèrent aucune autorisation de contacter des clients, de réserver de la capacité, d’exécuter une reprise ou de déplacer de l’argent.

## Ce que couvre le rapport

| Fichier source | Lecture humaine complète |
| --- | --- |
| `HANDOFF.json` | Commandes restant à exécuter, identifiants de produits et de commandes, unités, numéros des événements sources, empreintes des spécifications, fournisseur simulé, domaine de défaillance, capacité déclarée et délais modélisés. |
| `PASSPORT.json` | Préparation du constructeur, divergences de restauration, offre/coût complet/contribution/budget modélisés, comparateur classique, six déclarations concernant les éléments probants réels et occasion suivante proposée. |
| `AUDIT.json` | Verdict enregistré, totaux de réexécution consignés, nombre d’échecs consigné, codes de diagnostic distincts, lacunes de restauration et ensemble des six conditions réelles requises. |
| `REJECTION.json` | Refus enregistré, motif pris en charge et portée synthétique. Ce fichier est lu à la place des trois enregistrements précédents. |

Chaque lecture conserve aussi les références brutes de schéma et de portée, les empreintes de source/transfert/idempotence consignées lorsqu’elles sont présentes, et les empreintes SHA-256 des fichiers exacts qui ont été lus. Les codes techniques restent inchangés ; les explications qui les entourent sont localisées. Les empreintes identifient des octets, **pas leur véracité, leur origine ni leur exhaustivité**.

Le compagnon ne lit ni `INPUT.json` ni le `PASSPORT.md` d’origine. Il ne réexécute pas les événements et ne recalcule ni la capacité, ni les coûts, ni les empreintes de source, de transfert ou d’idempotence consignées, ni un avantage économique. Un transfert modifié accompagné d’un ancien `PASS_SYNTHETIC_ONLY` peut donc être présenté : les quantités du transfert et celles de l’audit enregistré apparaissent séparément, avec une mention explicite de l’absence de nouvel audit. Un dossier réécrit de manière cohérente peut aussi être présenté sans acquérir la moindre garantie d’authenticité. Une déclaration réelle ayant la valeur `true` reste une **déclaration consignée non vérifiée**.

Les faiblesses connues du vérificateur historique concernant les montants booléens, les entrées mal formées et les vues `inspect` périmées restent décrites dans le [guide des éléments probants](../continuity-omega-paper/EVIDENCE.fr.md). Ce compagnon ne répare ni ne qualifie le vérificateur et n’intègre pas les travaux de renforcement gérés séparément.

## Les entrées non prises en charge sont refusées explicitement

Le lecteur prend en charge le schéma v1 publié et son vocabulaire narratif français/anglais fini. Les champs requis absents ou supplémentaires, les schémas ou messages inconnus, les codes de diagnostic inconnus, les mélanges de refus et de transfert, les champs JSON en double, les nombres non finis, les montants booléens, les identifiants mal formés ou les fichiers probants sous forme de liens symboliques entraînent un refus explicite de présentation. Les entiers JSON de plus de **4096 chiffres** dépassent le format pris en charge. De nouveaux champs ou textes exigent une traduction explicite et révisée ; le lecteur ne les omet pas silencieusement.

Ces contrôles établissent que le compagnon peut présenter intégralement l’enregistrement pris en charge. Ils n’établissent ni la justesse métier, ni l’authenticité de la source, ni le résultat d’un nouvel audit. Les éléments probants d’origine demeurent intacts lorsque la présentation est refusée.

## Demander un nouveau contrôle séparément

```bash
python3 -m continuity_omega verify --in-dir /tmp/continuity-reading-demo-001
```

Cette commande distincte exécute le vérificateur du prototype extrait et affiche son nouveau résultat. Elle **ne remplace pas le fichier `AUDIT.json` enregistré**. Une lecture ultérieure décrit toujours l’audit enregistré. Conserver séparément la sortie de cette commande si une trace de ce contrôle est nécessaire, en maintenant les limites du vérificateur décrites ci-dessus.

## Exécuter les contrôles ciblés

```bash
python3 -m unittest discover -s tests -p 'test_continuity_passport.py' -v
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
```

La première suite couvre la lecture bilingue, la conservation des nombres et des codes, l’immutabilité des fichiers, les entrées inconnues ou mal formées, les erreurs localisées, la sûreté des sorties et la distinction entre résultat consigné et état actuel. La seconde est la suite de tests d’implémentation construite pour le prototype inchangé. Ces résultats sont des contrôles logiciels, pas des preuves de reprise réelle, de commandes livrées, de paiement encaissé ou de certification externe.

Poursuivre avec le [guide du prototype](README.fr.md), le [pilote réel proposé](REAL_PILOT.fr.md) ou l’[article de recherche bilingue](../continuity-omega-paper/README.fr.md).
