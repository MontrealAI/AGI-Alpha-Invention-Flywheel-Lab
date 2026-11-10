# Troubleshooting / Dépannage

| Symptom | What to check | What to preserve |
|---|---|---|
| Blank app or missing styles | Extract the whole ZIP; keep the app files together; enable JavaScript | Archive identity and browser/version |
| Launcher cannot find Python | Install Python 3.10+ separately; use `python3 launch.py` or Windows `py -3 launch.py` | Exact terminal error, without secrets |
| Port already in use | Close an old connector or use `--port 8766` | Do not kill unrelated applications |
| Browser cannot reach connector | Use the exact printed loopback address; keep connector running | Current run export before restarting |
| Session/Origin error | Reload the served app from its own printed address; avoid third-party frames | No session tokens in a report |
| No local models | Start your local inference server; inspect its installed models; use exact IDs | Provider/model identity, endpoint without credentials |
| API permission refused | Confirm deliberate external transmission consent and request budget | Refusal is not permission to enable billing |
| Invalid credential or model | Use the provider's official account tools; check model entitlement | Never paste keys into projects or support messages |
| OAuth consent refused | Respect refusal; select another authorized access mode | No consumer-password or cookie workaround |
| ChatGPT unavailable in paid edition | Verify applicable commercial approval and published eligibility | Do not relabel the paid edition open source to bypass approval |
| Token expired or revoked | Use the official reconnect flow; disconnect obsolete accounts | Do not extract browser session tokens |
| Quota exhausted | Stop, wait for the plan's documented reset or choose another explicitly authorized resource | No automatic purchase or API fallback |
| Request timeout/outage | Inspect whether the provider may have accepted it; retry only under configured policy | Uncertain cost remains unknown |
| Unsupported tool/JSON capability | Choose a demonstrably capable model or supported text workflow | Capability refusal, not forced dispatch |
| CONTEXT preflight refusal | Shorten the prompt or requested output, or configure a larger context supported by both the running server and model; keep the declared limit accurate | This conservative estimate includes UTF-8 input bytes, framing allowance and output budget; it is not a universal hardware minimum |
| Malformed model output | Inspect validation errors and ask for a corrected artifact within the schema | Failed attempt and unchanged acceptance target |
| Tool execution rejected | Review the allowlist, paths, input bounds and acceptance contract | Do not enable unrestricted shell to force success |
| Run interrupted/cancelled | Inspect durable state; resume supported steps from the same workspace | Checkpoint, previous attempts and any uncertain dispatch |
| Project import rejected | Check format/version, file size and integrity; use your original export | Corrupted file separately from the valid backup |
| Browser project missing | Reopen exported JSON; browser storage depends on profile/location | Without a backup, erased browser data may be unrecoverable |
| Download integrity mismatch | Obtain the trusted exact archive/checksum again and do not execute mismatched bytes | Digest and source revision, no private content |

A bug report should name the release commit, product version, OS/browser/Python version, expected behavior, actual error and a small synthetic reproduction. Remove keys, authorization codes, tokens, customer content and private workspace paths. No response-time commitment is included in this edition.

## Français

Décompressez d'abord tous les fichiers. Pour un problème de connexion, utilisez l'adresse locale exacte affichée et gardez le connecteur ouvert. Pour un modèle local absent, démarrez son serveur et vérifiez son identifiant. Pour une permission API refusée, n'activez pas automatiquement de facturation.

Un refus OAuth doit être respecté. Une autorisation expirée se renouvelle par le parcours officiel. Un quota épuisé n'autorise ni achat de crédits ni changement automatique vers une API payante. L'accès au forfait ChatGPT dans une édition commerciale reste conditionnel à l'approbation applicable.

Une sortie invalide doit être corrigée selon son schéma; ne modifiez pas le critère d'acceptation après le résultat. Après interruption, inspectez le point de reprise et conservez les essais précédents. Une empreinte incorrecte impose de retrouver les octets de confiance avant exécution.

Un refus **CONTEXT** peut survenir avant toute inférence. Réduisez la demande ou la sortie prévue, ou configurez une fenêtre plus grande réellement prise en charge par le serveur et le modèle. L'estimation prudente inclut les octets d'entrée, une réserve de formatage et la sortie; elle ne définit pas un minimum matériel universel.

Pour signaler un défaut, indiquez la version exacte, le système, le navigateur/Python, le résultat attendu et une reproduction synthétique. Ne transmettez jamais de clé, code d'autorisation, jeton ni donnée privée.
