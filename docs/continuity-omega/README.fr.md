# CONTINUITÉ Ω — Tenir parole, démontrer la reprise

[English](README.md) · **Français** · [Article de recherche, édition 1.1.1](../continuity-omega-paper/README.fr.md)

## Note de portée : la source historique v0.1

La reproduction présentée dans l’article est figée au commit [`a755d0375693465f8f31c0c919cc186eae74bbcc`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/a755d0375693465f8f31c0c919cc186eae74bbcc/continuity_omega). Ses **29 tests d’implémentation construits pour le prototype réussissent**, mais un examen distinct à cinq sondes reproduit un témoin positif nominal, l’acceptation d’un montant monétaire de type booléen, une exception non interceptée face à une structure mal formée, une vue `inspect` qui renvoie le passeport enregistré sans nouvel audit après modification des éléments probants, ainsi que l’acceptation d’une entrée réécrite de manière cohérente après recalcul de son empreinte modifiable. Ce dernier cas illustre la limite d’authenticité des sources déjà déclarée. Ces observations établissent des faiblesses et une limite de confiance ; elles **ne qualifient ni le vérificateur, ni une reprise réelle, ni une livraison au client**. La proposition de renforcement de la PR 279, gérée séparément, n’est ni intégrée ni qualifiée par cette publication. Voir le [guide probant complet](../continuity-omega-paper/EVIDENCE.fr.md) et les [contre-exemples consignés](../continuity-omega-paper/evidence/COUNTEREXAMPLES.json). Les commandes ci-dessous exécutent le code de la version extraite ; reproduire ces observations historiques exige la procédure de l’article fondée sur la source figée.

**Le produit visé :** un exercice de continuité des activités qui montre si un engagement client défini peut encore être tenu lorsque l’informatique habituelle est indisponible, et qui met à l’épreuve les moyens manquants susceptibles de rendre une autre solution d’exécution économiquement viable.

**Le prototype publié :** un exercice de transfert de commandes entièrement hors ligne, rattaché à une source précise et explicitement **SYNTHETIC** (« synthétique »). Il ne constitue ni un produit de sécurité de production, ni un test d’intrusion, ni un système opérationnel de réservation auprès de plusieurs fournisseurs, ni une certification. Son arithmétique est exacte dans les limites des entrées déclarées ; les autorisations des fournisseurs, l’historique des sources et la demande sont construits pour le scénario. Il n’accède à aucune donnée client, infrastructure, entente contractuelle ou somme d’argent réelle.

## Qui l’achète ?

Hypothèse initiale concernant l’acheteur : **la direction des opérations d’un imprimeur régional interentreprises (B2B) d’étiquettes d’emballage, comptant de 5 à 50 personnes et dépourvu d’un second site de production**. Un pilote payant réaliste porterait sur un produit sélectionné, une obligation envers un client réel, un producteur de secours, un exercice isolé approuvé et leurs véritables éléments contractuels et techniques. Le propriétaire ou la direction générale approuve l’achat ; la direction des opérations est responsable de l’acceptation. Aucun acheteur correspondant à ce profil n’a encore été recruté ni accepté de payer.

## Quel changement manque encore ?

Le premier test évident demande : *L’application restaurée démarre-t-elle ?* Le test plus exigeant demande : **Quels engagements envers les clients la restauration a-t-elle omis ?** Le changement suivant porte sur la structure du problème : *Pourquoi faudrait-il restaurer entièrement les systèmes de l’entreprise d’origine avant de pouvoir exécuter une commande déjà acceptée ?*

Le prototype construit un dossier transférable vers une solution de repli à partir d’un historique d’événements antérieur à l’interruption, scellé séparément, plutôt qu’à partir d’un instantané restauré potentiellement incomplet. Son vérificateur implémenté séparément reconstruit les obligations, vérifie les contraintes de disponibilité des fournisseurs et de coûts prévues par le code, et rejette les falsifications couvertes par ces contrôles. La source historique présente les faiblesses décrites ci-dessus.

## Exécuter en une minute (Python 3.10+ ; aucun paquet, réseau ou clé d’API)

À la racine du dépôt :

```bash
python3 -m continuity_omega demo --case nominal --out /tmp/continuity-omega-demo-001
python3 -m continuity_omega verify --in-dir /tmp/continuity-omega-demo-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-omega-demo-001 --language fr
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
```

Utiliser un **nouveau** dossier de sortie ; l’interface en ligne de commande refuse d’écraser les éléments déjà consignés.

Le compagnon lit les enregistrements sauvegardés en français ; choisir `--language en` pour l’anglais. Il n’exécute **aucun nouvel audit** et ne modifie jamais les éléments probants. La commande distincte `verify` affiche un nouveau contrôle sans remplacer le fichier `AUDIT.json` enregistré. Voir [Lire les sorties](OUTPUTS.fr.md) pour les refus localisés, les rapports à partager, la signification exacte des statuts et les tests ciblés du lecteur.

Fichiers créés :

- `INPUT.json` — hypothèses de l’exercice synthétique et empreinte des événements sources consignée séparément.
- `HANDOFF.json` — engagements restant à exécuter, exigences, provenance, contrôle de capacité, fenêtre d’achèvement modélisée et liaison d’idempotence.
- `PASSPORT.json` — divergences de la restauration, économie du modèle, limites explicites des éléments probants et hypothèse concernant l’occasion suivante.
- `AUDIT.json` — réexécution exacte implémentée séparément ; `PASS_SYNTHETIC_ONLY` (« validation limitée au synthétique ») ou `FAIL` (« échec »).
- `PASSPORT.md` — Passeport de continuité d’origine en anglais ; le compagnon fournit une lecture complète en français ou en anglais à partir des enregistrements JSON.

Pour des témoins négatifs sans action réelle, créer un nouveau dossier et remplacer `nominal` par `tampered_source`, `overbooked`, `correlated_outage`, `unqualified`, `late`, `buyer_declines`, `uneconomic`, `unapproved_sharing` ou `no_order_source`. Ces cas renvoient le code 2 et produisent `REJECTION.json` au lieu d’un transfert autorisé. `missing_from_restored` et `extra_restored` montrent comment des éléments sources protégés peuvent révéler une restauration défectueuse tout en permettant de proposer un transfert distinct. Une divergence dans une base de données restaurée **ne prouve pas** que cette base a été reprise de manière sûre.

## Résultat de la démonstration (données et montants inventés)

La source construite pour le scénario accepte 1 000 unités de `LBL-100`, 800 de `LBL-200` et 600 de `LBL-300`. Elle porte ensuite la première commande à 1 100 unités et annule la troisième. **Il reste 1 900 unités à exécuter, réparties sur deux commandes.** L’instantané restauré conserve une quantité périmée de 1 000 unités pour `LBL-100`, omet entièrement `LBL-200` et maintient à tort la commande annulée.

Un imprimeur simulé dispose d’une capacité de 3 200 unités, dont 1 100 sont déjà réservées : il reste 2 100 unités selon une règle prudente de chevauchement des intervalles. Un fournisseur concurrent dispose de 1 800 unités, ce qui est insuffisant. Le transfert sélectionne l’imprimeur simulé ayant la capacité nécessaire ; son délai annoncé de 22 heures respecte la limite fixée à 48 heures. Le coût complet modélisé est de 5 050 $ US, le prix proposé de 5 700 $ US, le budget hypothétique de l’acheteur de 5 800 $ US et la contribution modélisée de 650 $ US. **Aucun achat, aucune acceptation, aucune réservation de capacité, aucune livraison réelle et aucune recette n’ont eu lieu.**

Le vérificateur implémenté séparément réexécute la source déclarée et contrôle les contraintes couvertes par son code sans appeler le producteur. Il ne rejette pas toutes les entrées invalides ; voir la note de portée ci-dessus. Il ne peut pas établir indépendamment l’origine de la source, la véracité des déclarations du fournisseur, les habilitations, les droits juridiques, la production physique ou l’acceptation de l’acheteur. Son « indépendance » désigne des **chemins de code distincts produits par les mêmes auteurs**, jamais une certification externe.

## Limites déterminantes

- L’empreinte des événements doit être conservée hors de l’environnement endommagé et authentifiée par un véritable processus de garde. Une empreinte SHA-256 stockée dans le même fichier JSON modifiable **ne garantit pas l’authenticité**. Un attaquant pouvant modifier à la fois le contenu et l’empreinte peut falsifier ces éléments synthétiques.
- Un incident réel peut toucher des commandes postérieures au dernier point de contrôle protégé de la source. L’objectif de point de reprise (RPO), le rapprochement des opérations manuelles et l’incertitude doivent être traités explicitement ; des enregistrements absents ne doivent **jamais** être fabriqués à partir d’une supposition de l’IA.
- La disponibilité du fournisseur, la réservation, les conditions, les domaines de défaillance partagés et le financement sont des déclarations synthétiques. Un indicateur booléen n’est ni une entente signée avec le fournisseur ni une réservation atomique tenant compte des autres clients.
- L’arithmétique d’un devis n’établit pas les coûts réels de tout le cycle de vie, les recours après échec, les obligations de l’employeur, l’assurance, l’encaissement ou la fiscalité ; les conditions juridiques et les droits autorisés nécessitent un examen.
- Aucun balayage de vulnérabilités, test d’exploitation dangereux, simulation destructive, échange avec des fournisseurs, accès aux données de production, paiement ou changement des paramètres de sécurité n’a lieu.
- Une procédure classique compétente disposant des mêmes informations complètes et des mêmes outils constitue un comparateur solide. Ce prototype ne revendique **ni nouvel algorithme, ni avantage exclusif, ni cyberrésilience mesurée, ni réussite commerciale**.

## Travaux antérieurs et limites de l’intégration

Le scénario existant `campaign/genesis_commitment001` dans ce dépôt comprend déjà une reprise d’application synthétique, des engagements de ressources fondés sur le mécanisme natif `JournalAccount` et une comptabilité commerciale simulée. Son cas central a perdu 1 080 $ US parce que l’acheteur a choisi de ne pas acheter. Ce **nouveau transfert de commandes isolé** vise un moyen manquant différent ; il ne duplique ni ne remplace le grand livre financier canonique, ne supplante pas ses réservations, ne modifie pas cet historique et ne rebaptise pas la perte antérieure en réussite. Une future intégration client devra réutiliser l’autorité native existante sur la trésorerie et les obligations, avec de véritables éléments du fournisseur et une livraison effectivement acceptée.

## Fondements externes (antécédents, sans approbation du projet)

- NIST SP 800-184, *Guide for Cybersecurity Event Recovery* (2016) : planification de la reprise, essais réalistes et amélioration. <https://csrc.nist.gov/pubs/sp/800/184/final>
- NIST SP 800-34 Rev. 1, *Contingency Planning Guide for Federal Information Systems* (2010) : impact sur les activités, traitement de repli, priorités de reprise et mise à l’épreuve des plans. <https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final>

Aucune de ces normes ne certifie ce produit. La reprise gérée existante, les tests de restauration des sauvegardes et la planification classique des capacités sont des solutions de comparaison solides, et non des références artificiellement faibles.

## Qu’est-ce qui rend l’invention suivante possible ?

Une représentation de transfert testée avec succès et réutilisable légalement pourrait servir à une autre famille de produits ou à un fabricant indépendant. La campagne suivante devra **fixer d’abord de nouveaux critères d’acceptation**, construire le nouvel adaptateur, le vérifier, inclure tous les coûts d’acquisition et de transfert, puis comparer les résultats à ceux d’une équipe compétente disposant des mêmes sources, outils et autorisations. Une réussite ultérieure ne prouve pas, à elle seule, que la méthode conservée en est la cause.

**État de la recherche :** prototype synthétique exécutable localement. **État du marché :** non établi. **Assurance indépendante par un tiers :** non établie. **Prochaine action autorisée :** recruter un client et un fournisseur de secours volontaires pour un exercice non destructif assorti d’autorisations explicites ; ne jamais déclencher une action externe à partir de ces indicateurs synthétiques.
