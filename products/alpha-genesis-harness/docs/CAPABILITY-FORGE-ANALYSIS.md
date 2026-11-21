# Capability Forge · supplemental scoring decision

Before model outputs on the sealed qualification set, exposed development responses showed one compatibility problem. The local model returned complete response objects whose explicit final answer was a JSON string, sometimes with an extra layer of string escaping. The registered strict contract counts these as interface failures.

The supplemental report retains that original verdict. It separately decodes only the complete explicit answer field and independently checks its exact content. It does not search prose for a desired answer, recover truncated generations, retry failed cases or change the held-out inputs. Both metrics will be published. A formatting failure can matter in unattended delivery while still containing a mathematically correct result.

## Français

Une réponse de développement a révélé un problème de compatibilité du format. L’évaluation stricte est conservée. Le rapport supplémentaire décode uniquement le champ de réponse explicite d’un objet complet et vérifie le résultat exact. Il ne récupère aucune génération tronquée et ne relance aucun essai. Les deux résultats seront rapportés.
