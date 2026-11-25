# Notices techniques révisées en français

Ces notices documentent les observations à la révision publique 1.3 et les études citées. Chaque texte reprend un extrait anglais figé et revu. Ce dossier sert de référence à l’équipe de MONTREAL.AI et de QUÉBEC.AI. [Évaluation bilingue](REPORT.md) · [Sources exactes](INPUTS.json)

## Démarrage dans le navigateur

**GO pour l’adaptateur à activation volontaire et le contrôle de bon fonctionnement. NON TESTÉ avec un véritable modèle sur l’appareil.** La version d’ingénierie de Chromium indiquait que le modèle était téléchargeable en anglais, mais a renvoyé un écho de test. Le contrôle de bon fonctionnement empêche l’envoi de l’ambition au modèle et oriente le membre vers les autres options d’intelligence de la même mission. La version de test indiquait que le français était indisponible.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/GATES.md#L12)

## Autorisation d’une demande auprès d’un fournisseur

**PARTIEL. GO pour la mise en œuvre à portée limitée et les essais de protocole sur données de test.** Les essais du compagnon natif ont couvert OpenAI, Anthropic, Gemini, xAI, Mistral et DeepSeek. La clé du fournisseur est saisie dans le compagnon accessible sur l’interface de bouclage, qui la conserve dans son espace privé. Une approbation distincte dans le compagnon autorise précisément la mission en attente avant l’envoi. Le connecteur ordinaire démarre sans identifiant d’accès partagé. **NO-GO pour la qualification d’un compte réel, des frais facturés par le fournisseur et de l’inférence à distance en production.** Cette observation nécessite toujours le projet et le budget approuvés d’un membre consentant.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/GATES.md#L14)

## Annulation et limites

**GO pour les cas de reprise et de refus mis à l’essai.** Les essais du moteur et du navigateur ont couvert les jetons à usage unique déjà consommés, les portées incompatibles, les travaux remplacés ou annulés, les profils expirés ou supprimés et une réponse du fournisseur arrivée après l’annulation. Les essais sur données de test ont confirmé la réservation avant l’envoi. La facturation du fournisseur reste à mesurer séparément.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/GATES.md#L15)

## Identité des archives publiées

**GO uniquement avec les éléments probants correspondant exactement au code source, à l’archive et aux plateformes dans le reçu de publication.** L’identité des archives 1.0, 1.1 et de la dernière archive 1.2 mise à disposition est conservée aux côtés de celle de la version 1.3.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/GATES.md#L16)

## Vérification du site public

Le processus de compilation en lecture seule vérifie les entrées, reconstruit les deux versions linguistiques et compare le livrable déterministe à la version publique en ligne. Seule la tâche de déploiement dispose des autorisations d’écriture pour Pages et OIDC. Une tâche distincte en lecture seule récupère le registre publié et les deux pages HTML publiques. Après une modification, elle teste aussi le site dans Chrome à l’aide de données de test isolées pour le fournisseur de portefeuille. Les ressources prévues se limitent à l’exécuteur public existant et au déploiement sur Pages. Le test dans le navigateur ne fait aucun appel à Ethereum, ne demande aucune signature à un participant et n’envoie aucune transaction.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/FRONTIER-ATLAS.md#L7)

## Attribution de créneaux dans le scénario simulé

Un agent distinct a rédigé le programme direct avec le Codex compris dans l’abonnement, à partir du problème et du schéma enregistrés. Un troisième agent a fourni indépendamment deux jeux de données d’acceptation avant de voir le code SQL. Les résultats des **46/46** cas correspondaient à ceux du programme direct, y compris lors de la réexécution du livrable portable sans modification. Dans le jeu de données complet produit indépendamment, l’allocation était de 1, 2, 2 dans les trois groupes et la perte dans le scénario le plus défavorable était de 1. Les trois prévisions manquantes dans un scénario déclaré indépendamment ont été signalées une par une, et l’outil s’est abstenu d’attribuer une allocation. Des contrôles supplémentaires ont porté sur les minima irréalisables, les enregistrements nuls et en double, les valeurs hors portée, les limites de capacité, l’ordre des prévisions et la conservation des pertes. Toutes les données et tout le code relevaient d’une même administration.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/mission-study/README.md#L17)

## Adaptation et comparateurs en théorie des jeux

**GO pour le point de contrôle expérimental et les politiques de décision exactes examinées. NO-GO pour la promotion du spécialiste entraîné.** Un nouvel entraînement sur processeur, en 33 mises à jour, a modifié 122 880 paramètres aux fins de l’extraction structurée de protocoles stratégiques. Le modèle adapté, le modèle de base direct et le modèle de base avec recherche documentaire ont chacun reproduit exactement un des huit dossiers réservés à l’évaluation. Le comparateur distinct utilisant le Codex compris dans l’abonnement a obtenu 8/8 et a permis les deux vérifications exactes de politiques de décision. Une étude de suivi distincte fondée sur un graphe a obtenu 4/4 et a certifié indépendamment un gain exact de 387/13 minutes dans un seul jeu admis au protocole.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/bring-your-own-intelligence/GATES.md#L27)

## Portée de l’observation sur TITAN RTX

Les notes du pilote Data Center 620.70.10 du 23 novembre présentent des éléments probants propres à certaines cartes Turing, dont les T4/T4G, sans établir de résultat pour la TITAN RTX sur la machine du propriétaire. Il faut laisser cette décision en suspens. La liste distincte du pilote graphique Linux 615.78.08 de NVIDIA indique la TITAN RTX sous l’identifiant de périphérique 1E02. Cette piste de recherche est donc envisageable, sous réserve d’une preuve d’installation et de fonctionnement sur la machine du propriétaire.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/opportunity/REPORT.md#L21)

## Constats et économie du travail dans l’Atlas

MONTREAL.AI a mené deux nouveaux cycles de travail dans l’Atlas qui ont conduit à accepter trois constats documentaires de portée précise et une abstention circonscrite. Le processus de recherche établi a produit les mêmes décisions acceptées en moins de temps de session observé que le parcours intégré. Les rapports documentés et le contrôle de provenance sont conservés. La comparaison n’établit aucun rendement économique net ni revenu.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/opportunity/REPORT.md#L3)

## Appariement astronomique et décision d’abstention

L’équipe d’astronomie a qualifié un nouveau jeu de données réservé à la validation sur une plage de dates, en utilisant des données intactes du secteur 27 de TESS et des mesures distinctes de LCOGT. TESS a mesuré un événement candidat. Dans le fichier indépendant des observations au sol, la colonne d’horodatage barycentrique ne contient que des zéros, et les observations commencent des heures après l’événement ajusté. Le contrôle direct indépendant s’est également abstenu. Ces résultats établissent que l’appariement testé est inadmissible. La décision d’adopter la prévision demeure **ABSTENTION**.

[Texte anglais à la révision exacte](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c/publication/opportunity/REPORT.md#L56)
