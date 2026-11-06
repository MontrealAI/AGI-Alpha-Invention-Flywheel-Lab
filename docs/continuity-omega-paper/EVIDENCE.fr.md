# Lire les éléments probants

[English](EVIDENCE.md) · **Français** · [Article](README.fr.md) · [Contrat de traduction](TRANSLATION.md)

L’édition de recherche 1.1.0 utilise un ensemble commun d’identités pour les éléments probants dans les deux langues. Ce guide explique les fichiers en langage courant. Il ne les remplace pas, ne les transforme pas en observations de terrain et ne qualifie aucune révision ultérieure du prototype.

## Ce que signifie chaque fichier

| Fichier | Ce qu’il consigne | Ce qu’il n’établit pas |
| --- | --- | --- |
| [REPRODUCTION.json](evidence/REPRODUCTION.json) | L’exécution de deux implémentations synthétiques existantes liées à des sources figées, leurs nombres de tests, les décisions sur les scénarios et l’identité exacte des sources. | La correction complète du vérificateur, l’authenticité d’un historique client, une reprise réelle, une livraison physique ou un échange commercial. |
| [COUNTEREXAMPLES.json](evidence/COUNTEREXAMPLES.json) | Cinq observations délimitées sur la même source historique de transfert : un témoin positif, trois faiblesses et une limite de confiance déjà déclarée. | Une estimation du taux d’échec, une comparaison d’IA ou la qualification de la correction ultérieure proposée. |
| [POOLING.json](evidence/POOLING.json) | Le calcul exact d’une illustration volontairement construite de coûts partagés et de capacité simultanée. | Des prix de marché observés, une volonté d’achat réelle, un calendrier de production ou une transaction commerciale. |
| [QA.json](evidence/QA.json) | Les contrôles historiques de publication préservés pour l’édition 1.0.0, dont l’identité de son PDF et les contrôles du JavaScript de son lecteur. | Des contrôles de qualité des fichiers modifiés de la version 1.1.0, le déploiement actuel, une accessibilité universelle ou une nouvelle expérience de cyberrésilience. |
| [TRANSLATION_QA.json](evidence/TRANSLATION_QA.json) | Les contrôles locaux effectivement consignés pour l’édition 1.1.0 : parité structurelle bilingue, revue sémantique, mise en page et JavaScript du lecteur. | Des contrôles absents de ce fichier, un déploiement en ligne vérifié, une certification indépendante de la traduction ou de nouveaux éléments opérationnels ou commerciaux. |
| [PUBLICATION.json](PUBLICATION.json) | Les identités canoniques de la publication et l’inventaire complet des fichiers de cette édition. | La vérité d’une affirmation scientifique ou l’authenticité d’un document commercial externe. |
| [CLAIMS.json](CLAIMS.json) / [CLAIMS.fr.json](CLAIMS.fr.json) | Les mêmes identifiants d’affirmations, catégories, ancrages probants et limites en anglais et en français. | De nouveaux éléments probants créés par la traduction ou une affirmation plus forte dans l’une des langues. |

Les commandes de reproduction créent aussi de nouveaux fichiers locaux `RESULT.json` et des journaux détaillés. Ces comptes rendus documentent l’exécution concernée ; ils ne remplacent pas silencieusement le dossier historique publié. Une nouvelle exécution, une source corrigée et une nouvelle édition ont des identités différentes.

## Les deux reproductions liées à leurs sources figées

**Source du transfert :** `a755d0375693465f8f31c0c919cc186eae74bbcc`.

L’objet `tests.pr278` consigne 29 tests d’implémentation réussis et aucun échec. L’objet `pr278` consigne 12 cas fournis en ligne de commande : trois validations du transfert et neuf refus avant transfert. Le cas nominal reconstruit deux engagements en attente totalisant 1 900 unités. L’instantané restauré présente toujours trois divergences ; la validation du dossier de transfert ne corrige pas cet instantané.

Le fournisseur fourni par le scénario dispose de 3 200 unités de capacité, dont 1 100 déjà réservées et 2 100 restantes selon la règle prudente d’intervalles du scénario. Son délai stipulé est de 22 heures pour une exigence de 48 heures dans l’exemple. Aucune de ces valeurs ne mesure une fabrication réelle. La cible proposée du pilote, jusqu’à 20 000 unités dans un délai de 48 heures ouvrées convenues, constitue une affirmation distincte qui reste à qualifier.

Les champs `modeled_offer_usd=5700`, `modeled_cost_usd=5050` et `modeled_contribution_usd=650` décrivent un calcul construit pour l’étude. Ils ne constituent ni une facture, ni un encaissement, ni un profit réalisé, ni une mesure complète des coûts réels. La perte modélisée de 1 080 $ US du scénario central antérieur GENESIS Commitment 001 relève d’une source distincte et demeure un résultat historique négatif.

**Source de la reprise :** `84c4288b4726a17a90f8462d1d6faf8b5f8f00b5`.

L’objet `tests.pr277` consigne neuf tests d’implémentation réussis. Le candidat et le comparateur classique compétent retournent tous deux `[true, false, false, false]` sur quatre cas construits. Le premier est accepté ; les trois cas défectueux sont rejetés. La vérification des quatre comptes rendus de décision ne signifie pas que quatre reprises ont réussi. L’égalité avec le comparateur classique reste une égalité.

Le total de 38 tests d’implémentation est un décompte d’inventaire. Il ne constitue pas un échantillon statistique de clients, d’incidents ou de découvertes produites par des modèles.

## Le vérificateur lui-même admet des contre-exemples

Le dossier des cinq sondes maintient la distinction entre une faiblesse connue et un test de qualification réussi.

| Sonde | Observation sur la source historique |
| --- | --- |
| `positive_control` | Le cas synthétique nominal réussit, avec deux obligations totalisant 1 900 unités. |
| `boolean_currency` | Dans un cas à coût nul ajusté de façon cohérente, le constructeur rejette une offre booléenne, mais le vérificateur et la commande `verify` l’acceptent sans signaler d’échec d’audit. |
| `malformed_top_level` | Une entrée `null` au niveau supérieur provoque `AttributeError`, au lieu d’un refus structuré. |
| `stale_inspection` | Après modification de `required_units` à 1, `inspect` retourne le Passeport de préparation enregistré, sans nouvel audit. Une nouvelle exécution de `verify` retourne `FAIL` ; l’ancien audit enregistré indique toujours `PASS_SYNTHETIC_ONLY`. |
| `coherent_reseal` | La réécriture de la modification de commande, suivie du recalcul des identités internes du dossier, produit 2 000 unités et une validation. Il s’agit de la distinction déjà déclarée entre cohérence interne et rattachement à un scénario original conservé à l’extérieur. |

Ces sondes ont été motivées par [le rapport ultérieur de renforcement, dans sa révision consultée](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/6cd7e1bb7197cabdf8f3d093eead662cde5351f4/docs/continuity-omega/HARDENING.md), puis exécutées sur la source antérieure inchangée. La correction proposée n’est ni intégrée ni qualifiée ici. Les cinq observations sont distinctes des 29 tests d’origine, qui réussissent toujours.

## Lire les verdicts bruts sans en élargir la portée

| Code inchangé | Sens dans cette publication |
| --- | --- |
| `PASS_SYNTHETIC_ONLY` | Le programme a retourné une validation pour le fichier synthétique fourni. La fausse validation connue montre pourquoi il s’agit d’une décision logicielle observée, et non d’une preuve de correction générale du vérificateur. |
| `FAIL` | Le vérificateur a signalé l’échec d’une condition lors du contrôle concerné. Cela ne prouve pas que l’objectif de l’entreprise est impossible. |
| `REJECTED_BEFORE_HANDOFF` | La construction a été refusée dans les conditions du cas fourni ; aucune action externe ni réservation réelle n’a eu lieu. |
| `READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT` | Indicateur de préparation émis par le constructeur, et non acceptation indépendante ou résultat d’un audit à jour. |
| `REPRODUCED_SYNTHETIC_ONLY` | L’outil de reproduction a obtenu les résultats logiciels historiques attendus. Cela n’efface pas les contre-exemples distincts. |
| `COUNTEREXAMPLES_REPRODUCED_NOT_CHECKER_QUALIFICATION` | Les observations attendues des contre-exemples ont été reproduites. Le code de sortie 0 signifie ici que des faiblesses ont été reproduites avec succès, et non que le vérificateur est sûr. |
| `DEMONSTRATED`, `FAILED`, `NOT ESTABLISHED` | Verdicts proposés du Passeport pour une étape nommée et ses conditions déclarées. Des éléments propres à une étape ne peuvent pas être promus en preuve d’une autre étape. |
| `TIE; HOLD / NO DEPLOY` | Égalité avec le comparateur classique et absence de justification établie pour un déploiement, telles que consignées par l’étude de reprise. Ce code ne modifie pas l’autorité opérationnelle d’une autre tâche. |

## L’illustration exacte de mutualisation

L’illustration fixe le coût commun à `K=900`, le coût par acheteur à `c=100`, le plafond de prix à `B=400`, la capacité utilisable à `C=2000` et la quantité par acheteur à `q=750`, pour une période commune où tous les acheteurs peuvent activer leur engagement simultanément. Les conditions économiques exigent `n_min=3` ; la capacité simultanée impose `n_max=2`. Deux acheteurs donnent une contribution de `-300` unités monétaires hypothétiques. Trois atteignent l’équilibre, mais exigent 2 250 unités de capacité. La liste des nombres d’acheteurs réalisables est vide.

Sous les hypothèses indiquées dans l’article, les intervalles arithmétiques se recoupent si et seulement si `ceil(K/(B-c)) <= floor(C/q)`. La faisabilité opérationnelle, la participation réelle, les droits et le calendrier de trésorerie restent distincts. Modifier un curseur ou une entrée explore un autre arrangement construit pour l’étude ; cela ne révèle ni un prix de marché ni une capacité réellement disponible.

## Identité, exhaustivité et indépendance

`source_files` et `source_sha256` rattachent les octets reproduits à un blob Git et à une empreinte SHA-256. Une empreinte ne prouve ni qu’une source contient toutes les obligations ni que ses déclarations sur les fournisseurs sont vraies. La date limite d’observation, la garde externe, les engagements conclus hors du système et les réservations concurrentes exigent leurs propres éléments probants.

Des codes de vérification distincts et des tâches d’IA séparées peuvent partager les mêmes omissions de sources, hypothèses et auteurs. La revue consignée s’est déroulée dans un seul processus d’assistance. Elle ne constitue ni une certification par un tiers ni une expérience comparant deux modèles de pointe. L’édition bilingue modifie les langues de lecture disponibles ; elle ne change pas ces limites.
