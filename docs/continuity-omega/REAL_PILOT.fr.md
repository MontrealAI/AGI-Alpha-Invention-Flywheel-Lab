# CONTINUITY Ω — Contrat d’acceptation du premier pilote payant (proposé ; aucune approbation réelle)

[English](REAL_PILOT.md) · **Français** · [Article de recherche, édition 1.1.0](../continuity-omega-paper/README.fr.md)

## Note de portée : la source historique v0.1

La reproduction présentée dans l’article est figée au commit [`a755d0375693465f8f31c0c919cc186eae74bbcc`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/a755d0375693465f8f31c0c919cc186eae74bbcc/continuity_omega). Ses **29 tests d’implémentation construits pour le prototype réussissent**, mais un examen distinct à cinq sondes reproduit un témoin positif nominal, l’acceptation d’un montant monétaire de type booléen, une exception non interceptée face à une structure mal formée, une vue `inspect` qui renvoie le passeport enregistré sans nouvel audit après modification des éléments probants, ainsi que l’acceptation d’une entrée réécrite de manière cohérente après recalcul de son empreinte modifiable. Ce dernier cas illustre la limite d’authenticité des sources déjà déclarée. Ces observations établissent des faiblesses et une limite de confiance ; elles **ne qualifient ni le vérificateur, ni une reprise réelle, ni une livraison au client**. La proposition de renforcement de la PR 279, gérée séparément, n’est ni intégrée ni qualifiée par cette publication. Voir le [guide probant complet](../continuity-omega-paper/EVIDENCE.fr.md) et les [contre-exemples consignés](../continuity-omega-paper/evidence/COUNTEREXAMPLES.json). Les commandes ci-dessous exécutent le code de la version extraite ; reproduire ces observations historiques exige la procédure de l’article fondée sur la source figée.

## L’unique affirmation commerciale falsifiable

**Un transfert fiable et auditable des engagements envers les clients peut-il rendre une promesse de repli délimitée moins coûteuse ou plus fiable que la meilleure solution déjà disponible, et assez attrayante pour qu’une entreprise réelle l’accepte et la paie à un prix couvrant son coût complet ?** La victoire d’une solution classique ou une décision de ne pas acheter constituent des réponses valides. Découvrir une obligation oubliée par la reprise ne constitue pas, en soi, une réussite commerciale.

### Client précis et tâche à accomplir

- **Acheteur :** la direction des opérations d’un imprimeur régional interentreprises (B2B) d’étiquettes d’emballage sans second site, avec l’autorité du propriétaire ou de la direction générale pour l’approbation commerciale.
- **Client final :** un acheteur professionnel autorisé dont les conditions de commande peuvent être utilisées dans un exercice délimité.
- **Fournisseur de repli :** un imprimeur indépendant qualifié *réel*, proposant un produit d’étiquettes nommé et un créneau précisément réservé. Sa disponibilité et son acceptation doivent être obtenues et authentifiées séparément. Une lettre d’intention vague n’est pas une réservation payée.
- **Exercice :** une répétition isolée et non destructive ; aucune cyberattaque, aucun sabotage d’un système en service, aucun transfert non autorisé de données clients de production.
- **Exemple de cible :** une commande acceptée de 20 000 unités au plus dans un délai de 48 **heures ouvrées convenues**, uniquement si le fournisseur concerné démontre cette capacité et ce délai précis. Le cas synthétique de 1 900 unités **n’établit pas** une capacité de 20 000 unités.

### Éléments fixés avant l’exercice

1. Finalité : engagement exact envers le client et acceptation du résultat, tolérances d’erreur et de réimpression, heures limites, échéances, objectifs de point de reprise et de délai de reprise.
2. Garde des éléments probants : événements de commande d’origine protégés hors des systèmes de reprise touchés, garde des signatures et des clés ou origine authentifiée, fréquence des mises à jour, chaîne de garde et politique de traitement de l’incertitude.
3. Autorisations : champs de données précis pouvant être partagés, parties et juridictions, conservation, restrictions et autorité d’activation d’urgence. Aucun document client n’entre dans un dépôt public.
4. Fournisseur : produit qualifié, créneau et quantité réellement réservés, capacité démontrée après déduction des autres engagements, domaines de défaillance communs, politique d’annulation et de remboursement, assurance, canal de réponse effectif et solution si la capacité devient indisponible.
5. Économie : plafond de l’acheteur, meilleures solutions existantes, coûts complets d’acquisition, de mise en œuvre, d’exercice, de production, de transport, de vérification, de soutien, d’assurance, de financement et de traitement juridique, obligations de remboursement et réserves de protection ; chaque étape de trésorerie est financée par les mécanismes de comptes autorisés existants.
6. Comparaison : (A) reprise compétente par le prestataire existant et fournisseur de secours ; (B) même fournisseur, mêmes enregistrements et mêmes ressources avec utilisation directe d’une IA de pointe ; (C) mise à l’épreuve et transfert CONTINUITY Ω ; (D) absence d’achat ou organisation de la solution par le client lui-même. Comptabiliser les coûts complets du cycle de vie et toutes les interventions humaines séparément.
7. Tests : commandes perdues, modifications périmées, commandes annulées, doublons, nouvelles commandes tardives, restauration à partir d’un historique incomplet, surréservation du fournisseur, défaillance corrélée, refus, production défectueuse, paiement retardé et échec de la reprise.

### Évaluation du résultat

Le client et le fournisseur de secours acceptent la livraison ; cette acceptation ne relève pas d’une IA qui s’évalue elle-même. La vérification indépendante compare les étiquettes produites, ou un substitut hors production entièrement convenu, aux éléments graphiques et spécifications, à la quantité, à la qualité et à l’échéance. Les éléments probants doivent respecter les autorisations réelles d’utilisation des données. Une garantie de capacité future exige un contrat et des éléments de capacité effectifs.

Mesurer : engagements correctement exécutés et acceptés dans les délais ; heures réellement écoulées ; unités manquantes, dupliquées ou incorrectes ; incidents liés aux autorisations de divulgation ; heures de travail ; flux de trésorerie complets et contribution réalisée ; exposition au risque ; performance des concurrents. Rapporter les échecs et les inconnues. Les affirmations portent **sur chaque commande, installation et fenêtre de capacité effectivement mises à l’épreuve**. Un exercice sur table approuvé n’équivaut pas à une production de repli achevée.

### Échelle explicite des verdicts

Les codes ci-dessous restent identiques dans les deux langues ; leur sens et les éléments requis sont expliqués en français.

| Verdict | Éléments requis |
| --- | --- |
| `SYNTHETIC CHECK PASSED` | Vérification synthétique réussie : la source locale publiée et son vérificateur réussissent les tests inventés ; aucun élément client ou fournisseur. |
| `AUTHORIZED LIVE DRILL` | Exercice réel autorisé : des autorisations effectives et une entente d’exercice acceptée séparément existent. |
| `RECOVERY HANDOFF VERIFIED` | Transfert de reprise vérifié : dossier de commande et état de préparation de la solution de repli évalués indépendamment dans le périmètre déclaré. |
| `CUSTOMER DELIVERY ACCEPTED` | Livraison acceptée par le client : l’acheteur accepte le résultat réel selon les conditions fixées, et les obligations complètes sont consignées. |
| `PAID COMMERCIAL VALUE` | Valeur commerciale payée : les sommes sont encaissées, les obligations comptabilisées et le coût complet de toute la campagne rapproché. |
| `SUCCESSOR ENABLEMENT` | Occasion suivante rendue possible : une nouvelle tâche indépendante réussit mieux ou à moindre coût grâce à la méthode conservée, face à un comparateur classique disposant du même contenu. |
| `IMPROVED INVENTOR` | Inventeur amélioré : au fil de nouvelles campagnes distinctes, le *processus de découverte lui-même* progresse face à des solutions solides équipées des mêmes moyens. |

Le prototype actuel n’a atteint **que la première ligne**.

### Décision de poursuivre ou d’arrêter

**Poursuivre vers un exercice réel, contrôlé et payant** uniquement si de véritables éléments du client et du fournisseur sont obtenus, si la garde complète des sources et les autorisations sont en place, si le comparateur classique visant le même engagement est défini, si la sécurité technique est examinée, si la capacité et la trésorerie sont réellement disponibles et si l’achat est volontairement accepté.

**Ne pas revendiquer une continuité en production ni une certification par un tiers** avant qu’un exercice réel représentatif et approuvé soit exécuté et évalué indépendamment. Ne pas revendiquer un marché sans paiement encaissé et comptabilisation du coût complet. Ne pas revendiquer une occasion suivante rendue possible sans nouvelle utilisation distincte et comparaison causale.

### Prochaine occasion, encore à construire

Si un exercice payant démontre le transfert, tester si un réseau de producteurs de secours peut proposer des créneaux de continuité vérifiés aux entreprises qui ne peuvent financer un second site dédié. Les moyens manquants pourraient être une sémantique interopérable des engagements envers les clients, des réservations partagées authentifiées, un contrat de capacité et de priorité, ou une couche de vérification et de rapprochement. Chacun doit être construit, négocié et vérifié indépendamment. Un fournisseur qui vend déjà une offre équivalente à un coût complet inférieur l’emporte.
