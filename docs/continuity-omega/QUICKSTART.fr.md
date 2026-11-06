# CONTINUITY Ω · un engagement vérifié séparément dans un exercice synthétique

[English](QUICKSTART.md) · **Français** · [Article de recherche, édition 1.1.0](../continuity-omega-paper/README.fr.md)

## Note de portée : la source historique v0.1

La reproduction présentée dans l’article est figée au commit [`a755d0375693465f8f31c0c919cc186eae74bbcc`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/a755d0375693465f8f31c0c919cc186eae74bbcc/continuity_omega). Ses **29 tests d’implémentation construits pour le prototype réussissent**, mais un examen distinct à cinq sondes reproduit un témoin positif nominal, l’acceptation d’un montant monétaire de type booléen, une exception non interceptée face à une structure mal formée, une vue `inspect` qui renvoie le passeport enregistré sans nouvel audit après modification des éléments probants, ainsi que l’acceptation d’une entrée réécrite de manière cohérente après recalcul de son empreinte modifiable. Ce dernier cas illustre la limite d’authenticité des sources déjà déclarée. Ces observations établissent des faiblesses et une limite de confiance ; elles **ne qualifient ni le vérificateur, ni une reprise réelle, ni une livraison au client**. La proposition de renforcement de la PR 279, gérée séparément, n’est ni intégrée ni qualifiée par cette publication. Voir le [guide probant complet](../continuity-omega-paper/EVIDENCE.fr.md) et les [contre-exemples consignés](../continuity-omega-paper/evidence/COUNTEREXAMPLES.json). Les commandes ci-dessous exécutent le code de la version extraite ; reproduire ces observations historiques exige la procédure de l’article fondée sur la source figée.

> **Restaurer le système ne suffit pas à rétablir l’activité.**
>
> **Trouver ce que la reprise a omis. Construire une voie qui tient l’engagement.**

**Prototype de recherche exécutable v0.1.0, limité au synthétique.**

```sh
python3 -m continuity_omega demo --out /tmp/continuity-omega-demo-001
python3 -m continuity_omega verify --in-dir /tmp/continuity-omega-demo-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-omega-demo-001 --language fr
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
python3 -m unittest discover -s tests -p 'test_continuity_passport.py' -v
```

Choisir un nouveau dossier probant. Le compagnon de lecture affiche le résultat enregistré en français ; utiliser `--language en` pour l’anglais. Il n’exécute **aucun nouvel audit**. La commande distincte `verify` affiche un nouveau résultat, mais ne met pas à jour le fichier `AUDIT.json` enregistré. Voir [Lire les sorties](OUTPUTS.fr.md) pour enregistrer un rapport localisé complet, lire un refus et comprendre chaque statut consigné. La sortie anglaise d’origine du prototype demeure inchangée.

Lire [le guide du prototype](README.fr.md) pour la définition du produit, l’exemple synthétique détaillé de 1 900 unités, les témoins négatifs, les limites et les références du NIST. Lire [le pilote proposé](REAL_PILOT.fr.md) pour les conditions exactes de la prochaine acceptation client et l’épreuve économique complète.

Cet ensemble ne recherche pas de vulnérabilités, ne contacte personne, ne réserve aucune capacité réelle, n’accepte aucune condition client, n’accède à aucun enregistrement commercial réel et ne modifie aucune autorité financière. Seul l’exercice synthétique est exécutable aujourd’hui. Le service payant réel et le marché restent à établir.
