# Operation and deployment / Exploitation et déploiement

**Current GitHub-only release path.** See [GitHub Pages and MetaMask](GITHUB-NATIVE.md) for native provisioning, isolated hosting, bilingual instructions and the current threat model. The original SIWE access service remains the local reference.

## English

### Reproduce and prepare the member packet

Use Node.js 24+, Python 3.12+, a POSIX workspace and a private work directory outside the checkout. From the repository root, build the public preview without generating or opening a wallet.

```sh
site_stage="$(mktemp -d)"
python3 scripts/build_research_site.py --output "$site_stage/published"
python3 -m http.server --bind 127.0.0.1 --directory "$site_stage/published" 8080
```

Open `http://127.0.0.1:8080/frontier-omega-alpha/`. For qualified local research and browser tests, run the following from `products/frontier-omega-alpha`.

```sh
npm ci --ignore-scripts
npm test
npx playwright install chromium
npm run test:browser
python3 -m unittest discover -s tests -p test_research.py -v

research_run="$(mktemp -d)"
python3 -m research scan --state "$research_run/radar.sqlite" --allow-network
python3 -m research fetch --output "$research_run/inputs" --allow-network --environment-egress
python3 -m research run --inputs "$research_run/inputs" --output "$research_run/run"
python3 -m research verify --inputs "$research_run/inputs" --report "$research_run/run/research-receipt.json"
python3 -m research packet --inputs "$research_run/inputs" --report "$research_run/run/research-receipt.json" --output "$research_run/packet"
```

Use `--environment-egress` on `scan` and `fetch` when running behind approved managed HTTPS egress. It requires curl. The default direct transport uses HARNESS host/DNS pinning. The egress variant trusts the administrator's proxy and certificates, rejects redirects, bounds text responses and pins each experiment input by SHA-256. Keep the same private database for periodic observations. To run the radar periodically, schedule the bounded `scan` invocation as the researcher on the approved host. Origin timestamps and retrieval timestamps have separate meanings. Changes in bytes reopen review. The operator assesses what changed. Use `compare-source --source <key> --previous <pinned-url> --allow-network` for a historical comparison on the same registered source host.

The opportunity list and scoring weights are editable in an operator-approved protocol. The experiment entry point runs the registered Lean receipt method on named statements and exact content. No network call, external process, model invocation or spending is initiated by document content. Use a new protocol for a new acceptance rule. Keep rejected evidence and actual costs. The first packet exporter is specific to the initial Lean study. To publish a different study, supply approved bilingual records in the `validateRecord` schema.

### Deployment and release

On an authorized host, use a dedicated service user, an operator-only state directory and a wrapping key outside the checkout. The browser API binds to loopback and requires TLS termination. Publish the private reader build at an isolated origin when possible. If enabling the existing project Pages origin, qualify every page/script served by that shared origin. A URL path is not an origin boundary.

Set these values in the service's private configuration.

| Setting | Meaning |
| --- | --- |
| `FRONTIER_SITE_URL` | Exact canonical HTTPS URL of the wallet UI, including its path. The origin and URI bind SIWE. |
| `FRONTIER_RPC_URL` | Trusted HTTPS Ethereum-mainnet RPC with EIP-1898 block-hash reads. Treat any provider credential as a secret. |
| `FRONTIER_STATE_DIR` | Absolute, owner-only directory for local SQLite state. Use one service instance and a local disk. |
| `FRONTIER_KEK_FILE` | Absolute path to the owner-only wrapping key. Supply independently of the database and web roots. |
| `FRONTIER_PORT` | Loopback port. Defaults to `8787`. |

The TLS reverse proxy should route only `/v1/` to the access service, preserve the browser's `Origin`, disable request and response body logging and caching, apply an edge per-client rate limit and set HSTS and `frame-ancestors 'none'` on a dedicated protected UI. Keep the origin and key material out of any service that does not need them. Disable cores/crash reporting for the process. Store private inputs and browser-released research files separately. Protect or disable backups and analytics that could capture protected data.

For a same-origin reader build, set the two public HTML files’ `frontier-api` meta value to `same-origin` in the protected deployment copy. For a reviewed cross-origin setup, set the meta value to the exact public HTTPS API origin and add exactly that origin to `connect-src` in the reader build. Keep the tracked GitHub Pages version offline until deployment qualification. The backend trusts the configured web origin only. The landing page never signs a transaction, requests an approval or reveals production secrets.

```sh
node access/ops.mjs keygen "$FRONTIER_KEK_FILE"
node access/ops.mjs chain-check
node access/ops.mjs publish experiment-brief 1 /absolute/private/packet/experiment.json
npm start
```

Repeat `publish` for each approved version or use `publish-server` for server-side decryption with no key transfer. Avoid exposing unpublished or tenant-private projects through the member catalog. Member wallets receive the reader role. The researcher role owns its private collection and runs the research commands. A designated release operator with access to the separate service state and wrapping key can publish, withdraw and rotate. Hosting and commercial authority remain separate from these file permissions.

The GitHub Pages build uses the repository's existing protected-main deployment pipeline. The qualification workflow cannot publish. Production qualification needs a trusted TLS host and RPC, the signed-in Club and token paths with authorized real wallets, expiry and loss-of-entitlement checks, isolated-origin/privacy review and an independent release sign-off. The selected Club wallet should own the exact name. The token wallet should meet the threshold without Club access. Use normal review to qualify publication of the public shell.

### Rotation and recovery

- Withdraw a release with `node access/ops.mjs withdraw <id> <version>`. Its history stays in private storage. Existing copies remain readable by recipients who already saved them.
- Revoke all active sessions and challenges with `node access/ops.mjs revoke-all`. Availability and eligibility are rechecked before all key releases. Clients also revalidate while open.
- For a new key epoch, create a new key file with `keygen`. Back up the SQLite state on private storage using a consistent offline snapshot or SQLite backup. Run `node access/ops.mjs rotate /absolute/private/new-key.json` with the old key still configured. Active releases are re-encrypted and sessions revoked atomically. Restart with the new key path. Verify a round trip before restoring traffic. Keep the appropriate old key apart from retained backups per your retention policy.
- For suspected exposure, disable the reader origin on the proxy, revoke, rotate, investigate and decide whether to withdraw affected releases. Treat copies of the old ciphertext plus its old content keys as readable. Production key storage and provider credentials are separate recovery dependencies.

## Français

### Reproduire l’essai et préparer les dossiers

Utilisez Node.js 24 ou ultérieur, Python 3.12 ou ultérieur, un poste POSIX et un espace de travail privé hors du dépôt. Dans les commandes ci-dessus, la première série construit et sert le site public. La seconde installe les dépendances, exécute les tests, observe les sources, télécharge les pièces, réalise la comparaison, la vérifie et produit six dossiers en anglais et en français. Le site local est accessible à l’adresse `http://127.0.0.1:8080/frontier-omega-alpha/`.

Ajoutez `--environment-egress` à `scan` et `fetch` dans un environnement où le trafic HTTPS autorisé transite par un relais géré. Cette option requiert curl. En accès direct, HARNESS fixe l’hôte et l’adresse résolue. Avec le relais, le contrôle fait confiance au relais et à ses certificats, refuse les redirections, borne les réponses textuelles et vérifie l’empreinte SHA-256 des pièces de l’essai. Réutilisez la même base privée pour les observations périodiques. La planification de `scan` relève du compte de recherche sur la machine autorisée. Les dates de publication et d’observation sont distinctes. Une modification des octets rouvre l’analyse. Pour comparer les révisions d’une source inscrite, utilisez `compare-source --source <clé> --previous <URL-figée> --allow-network`.

L’opérateur peut établir un nouveau protocole et ajuster les hypothèses ou leur pondération. L’expérience initiale utilise un ensemble déclaré d’énoncés Lean et contrôle les pièces exactes. Un texte téléchargé ne déclenche aucune exécution, dépense ni requête de modèle. Conservez les refus et les coûts réellement engagés. L’export bilingue fourni décrit la première étude Lean. Pour une autre étude, fournissez des dossiers bilingues approuvés conformes au schéma `validateRecord`.

### Déploiement et publication

Sur la machine autorisée, utilisez un compte de service dédié, un répertoire d’état privé et une clé d’enveloppe hors du dépôt. L’API écoute sur l’interface de bouclage et exige une terminaison TLS. Privilégiez une origine isolée pour la version protégée. Si vous activez l’accès depuis l’origine Pages du projet, qualifiez tous les sites et scripts servis par cette même origine.

| Paramètre | Rôle |
| --- | --- |
| `FRONTIER_SITE_URL` | URL HTTPS officielle de l’interface de connexion, avec son chemin. L’origine et l’URI lient la signature SIWE. |
| `FRONTIER_RPC_URL` | Point d’accès HTTPS de confiance au réseau principal Ethereum prenant en charge EIP-1898. Gardez tout identifiant du fournisseur secret. |
| `FRONTIER_STATE_DIR` | Répertoire absolu privé pour SQLite, sur disque local et avec une seule instance de service. |
| `FRONTIER_KEK_FILE` | Fichier absolu privé de la clé d’enveloppe, conservé séparément de la base et des racines Web. |
| `FRONTIER_PORT` | Port de bouclage. Valeur par défaut `8787`. |

Configurez le relais TLS pour transmettre uniquement `/v1/`, respecter l’en-tête `Origin`, désactiver la mise en cache et la journalisation des corps des requêtes ou réponses et limiter le trafic par client. Sur l’origine dédiée, activez HSTS et l’interdiction d’intégrer la page dans un cadre. Désactivez les vidages mémoire et la télémétrie susceptible de capter des données protégées. Protégez les sauvegardes.

Pour servir l’interface protégée sur la même origine que l’API, affectez `same-origin` à `frontier-api` dans les deux pages de la copie de déploiement. Pour une architecture interorigines validée, indiquez l’origine HTTPS exacte de l’API dans cette valeur et dans la directive `connect-src`. Gardez la version Pages hors ligne jusqu’à la qualification de l’accès. La configuration n’exige aucune approbation ni transaction de jetons.

La commande `keygen` crée la clé privée. `chain-check` vérifie l’identité du jeton sur la chaîne. `publish` chiffre une version approuvée. `publish-server` conserve la clé côté serveur. Le portefeuille admissible donne accès en lecture. Le compte de recherche possède les fichiers de travail. Seul l’opérateur désigné disposant de l’état privé et de la clé publie, retire ou renouvelle les dossiers. Les autorisations de déploiement et de transaction restent distinctes.

Le site public suit la chaîne de publication existante du dépôt. Le processus de qualification n’a aucun droit de déploiement. Pour activer la version protégée, validez l’origine TLS, le fournisseur Ethereum, les deux accès avec des portefeuilles réels autorisés, l’expiration et la perte d’admissibilité, la confidentialité et la revue indépendante de la mise en service. La publication du site public suit le circuit normal de revue.

### Rotation et reprise

- `withdraw <id> <version>` retire un dossier du catalogue. Les copies déjà reçues demeurent entre les mains de leurs destinataires.
- `revoke-all` révoque toutes les sessions et demandes de connexion actives. Chaque délivrance de clé vérifie à nouveau l’admissibilité.
- Sauvegardez SQLite de manière cohérente et privée. Créez une nouvelle clé avec `keygen`. Exécutez `rotate /chemin/privé/nouvelle-clé.json` en laissant l’ancienne clé configurée. La rotation rechiffre les dossiers actifs et révoque les sessions dans une même transaction. Redémarrez avec le nouveau chemin. Vérifiez le déchiffrement avant de rouvrir le trafic. Séparez des sauvegardes les anciennes clés nécessaires à leur restauration.
- En cas de soupçon d’exposition, fermez l’origine protégée sur le relais, révoquez, faites la rotation et examinez les dossiers à retirer. Un ancien fichier chiffré accompagné de son ancienne clé demeure lisible. La clé et les éventuels identifiants du fournisseur sont des dépendances de reprise distinctes.
