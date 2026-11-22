# GitHub Pages and MetaMask / GitHub Pages et MetaMask

## Architecture decision

GitHub Pages serves files. Anonymous visitors have no authorized GitHub write or workflow-dispatch channel. MetaMask signatures authenticate an account, but a signing interface alone cannot send a request to a trusted publisher or recover a secret from public files. GitHub OAuth, delegated browser credentials and third-party relays are outside this deployment. No gas-free anonymous ingress was demonstrated within the allowed interfaces.

The native candidate uses a funded-for-gas Ethereum mainnet EIP-1559 transaction with zero value to the protocol's identity precompile at `0x0000000000000000000000000000000000000004`. The destination transforms no state and echoes calldata. Direct Ethereum signers send no tokens and approve no allowances. Ethereum processes gas separately. The reader obtains a current gas estimate and fee cap, then waits for a separate confirmation click and the MetaMask confirmation. The wallet displays the fee and can reject the request. A successful registration is reused on later visits.

The browser generates a nonextractable P-256 private key and stores it through IndexedDB on an isolated GitHub Pages origin. The wire format starts with the FRONTIER application identifier, version and mainnet marker. It binds the wallet address, a random 128-bit nonce, a short enrollment submission window, the 65-byte public key and the optional normalized Club label. The publisher rehashes and recovers the signed transaction, compares its successful receipt and scans canonical blocks through Ethereum's finalized head. It applies the PR #541 ENS Registry and Name Wrapper rules and the same exact ERC-20 balance threshold at a fresh, canonical mainnet snapshot. Either proven path suffices.

The publisher unwraps a reviewed catalog with a protected GitHub environment key. Every content key is AES-256-GCM encrypted in that catalog. Each authorized member envelope uses RFC 9180 base mode with DHKEM P-256, HKDF-SHA256 and AES-256-GCM. Associated data links the chain, signed enrollment transaction and the digest of the exact ciphertext and metadata. The browser verifies that digest and both authentication tags before rendering data as text. Public Pages outputs contain ciphertext and per-device HPKE envelopes. The public Git branch stores the same validated library alongside a compact encrypted checkpoint that authenticates its digest. Either file from a different publication forces recovery before issuing any keys.

| Lane | Authority and outputs |
| --- | --- |
| Existing project Pages | The reviewed `research-pages.yml` workflow serves the landing page at `/frontier-omega-alpha/`. It appends two validated files, `library.json` and `native-config.json`, only from the configured main-branch publication. The offline landing works without them. |
| Isolated reader Pages | A staged bundle is served at the root of a separate trusted origin hosted on GitHub Pages. It fetches ciphertext from the canonical project Pages path. The shared `montrealai.github.io` origin is rejected before device storage or wallet interaction. |
| Publisher Actions | A protected environment loads the policy and approved sealed catalog from the event commit on `main`, advances the encrypted checkpoint, and uses a fast-forward write to `frontier-omega-alpha-state`. The existing Pages workflow receives an authenticated dispatch. The published bytes allow retries after a failed dispatch. |
| Research Actions | A separate bounded job watches six public upstream release records. It compares `latest` with the version-pinned record and preserves public candidate evidence in `frontier-omega-alpha-radar`. A weekly or manually requested Lean replay reacquires pinned public inputs, runs the registered baseline and candidate, verifies the result and retains only public receipts. These jobs have no publisher secrets. |

The reader supports MetaMask injected in the desktop extension or MetaMask Mobile's in-app browser. The mobile link uses MetaMask's documented deep link. The native issuer rejects ERC-1271-only accounts and relayed contract-wallet transactions because an outer sender alone cannot prove contract-wallet authority. The retained local SIWE/EIP-1271 implementation provides reference tests and documentation.

## Member guide

1. Open the public FRONTIER Ω ALPHA site, choose AGI Club or AGIALPHA, and follow the approved reader link. Use MetaMask on Ethereum mainnet. For Club access enter only the name's first label.
2. Connecting MetaMask has no network charge. A first-time registration previews the destination, zero ETH value, estimated fee and proposed fee ceiling. Confirm only if the amount and destination in MetaMask match your intent.
3. The transaction, signing wallet, optional ENS label, device public key and participation are public. Anyone can correlate a publication receipt with its enrollment calldata. Unenrolled visitors can also download ciphertext. Decrypted copies remain usable by anyone who already saved them.
4. After mining, wait for Ethereum finality and the next successful GitHub Actions publication. Schedules can be delayed or dropped. Check status in the reader without logging into GitHub.
5. Return with the same browser storage and MetaMask account. Reading requests no fresh enrollment transaction. Browser data loss, using another device, or selecting a different eligibility path for a revoked enrollment can require explicit re-enrollment and another gas fee. MetaMask seed phrases cannot restore the browser key. If a wallet response is interrupted, the reader can recover the matching receipt from the published enrollment identifier.
6. The reader locks on wallet or network change and verifies current eligibility before reading. A new content version needs a fresh publisher authorization. A device that loses eligibility frees its enrollment slot and must register again if it later qualifies. Revocation cannot recall old keys, archived envelopes or copies.

## Owner setup and recovery

Keep release approval and environment settings under normal repository controls.

1. Complete independent review, then approve the merge using the existing branch process. The public shell can be deployed through the existing Pages workflow before turning on protected publication.
2. Approve one isolated origin served by GitHub Pages. A dedicated Pages repository can use a verified custom subdomain you control. An already controlled independent `github.io` origin can also work if it serves only trusted content. Preserve the existing MontrealAI project Pages and its domain settings. Enable HTTPS. Inspect the isolated root, its code and its absence of unrelated tenants, and verify the public library can be fetched from it.
3. Set the repository variable `FRONTIER_ALPHA_READER` to the exact HTTPS root URL, including the final slash. Dispatch **FRONTIER Ω ALPHA GitHub publisher** with `build_reader` set to true. Deploy its static reader artifact on the approved isolated GitHub Pages origin through its authorized publisher. This build uses no production keys.
4. Create a `frontier-omega-alpha-provision` environment restricted to the protected `main` branch. Use environment secrets named `FRONTIER_ALPHA_PUBLISH_KEY` and `FRONTIER_ALPHA_RPC`. Set the RPC to a trusted HTTPS Ethereum mainnet endpoint that supports full finalized blocks, raw transactions and canonical block-hash calls. The endpoint is used solely for Ethereum data. Scope automatic state writes to the dedicated branch and allow the documented workflow dispatch permissions. Never expose either secret to the frontend or to a pull-request workflow.
5. Use the following repository commands from `products/frontier-omega-alpha`. Generate the key outside Git. Inject its value only through the protected operator environment and GitHub secret settings. Store the selected preflight anchor height and hash as `FRONTIER_ALPHA_ANCHOR_HEIGHT` and `FRONTIER_ALPHA_ANCHOR_HASH`. Establish the anchor before enabling wallet enrollment.

```sh
npm ci --ignore-scripts
node native/operator.mjs keygen /private/frontier-alpha-publisher.key
node native/operator.mjs preflight
node native/operator.mjs seal research-brief 1 /private/authorized-record.json /private/sealed-record.json
```

6. Review and place the approved **sealed** records in `native/approved-releases.json` on protected `main`. The committed catalog is initially empty. The private sources and unwrapped keys remain outside Git and artifacts. After the reader, catalog, branch permissions, environment and external review are ready, set `FRONTIER_ALPHA_NATIVE_ENABLED` to true and use the same workflow's protected publisher dispatch. Check its first state commit and the existing Pages deploy. `FRONTIER_ALPHA_RESEARCH_ENABLED` enables the research schedule separately.
7. Run a live pilot using consenting MetaMask users with exclusive Club-only and token-only qualification, and independently verify denial. Include the in-app mobile browser. Consent for a live wallet action and its fee stays with the signer. The product cannot self-approve a transaction.

The standard schedule runs every 15 minutes. It scans at most 120 blocks and 48 candidate signals per run, with interruption checkpoints including the transaction offset. The currently qualified envelope supports 96 active devices, one active device per wallet, 96 recent terminal receipts, 12 releases and 6 MiB of public library JSON. The reader suppresses enrollment when the publisher is catching up or its heartbeat is stale. Scheduled delivery has no uptime or latency guarantee. Processing 120 full blocks involves network and Actions compute. Standard public GitHub Actions and an approved provider can be used, with provider availability and limits subject to actual operation. No mandatory paid hosting is configured. User gas fees vary with the network and the payload. GitHub's Pages storage, bandwidth and usage limits apply. Treat throughput, fee quotes and finality delays as measured properties of the deployed pilot.

**Disable or withdraw.** Turn off `FRONTIER_ALPHA_NATIVE_ENABLED` and rebuild the existing Pages site to remove the live library and native configuration. To withdraw individual releases, publish an updated approved catalog. To revoke a compromised device for future envelopes, add its public enrollment identifier to the reviewed `native/revoked-enrollments.json` list. Delivery history can still be recovered from Git and archives. Future releases need different versions and fresh keys.

**Rotate.** Content rotation means sealing new versions, retiring old versions from the active catalog, and provisioning new envelopes after current checks. To change the publisher key while preserving the cursor and member devices, stop publication and use `node native/operator.mjs rekey <sealed-checkpoint> <matching-library> <approved-catalog> <private-output>` with the old and new environment keys (`FRONTIER_ALPHA_PUBLISH_KEY` and `FRONTIER_ALPHA_NEXT_PUBLISH_KEY`). Review the new wrapped catalog and the independently re-encrypted checkpoint. Update the state branch with a normal reviewed fast-forward commit. Update the environment key and catalog together during the paused window. For suspected compromise generate fresh **content** versions as well. An attacker with an old leaked key and its historical sealed records can still read those records.

**Recover.** Preserve the last known canonical checkpoint and its corresponding public library. After a failed job, run again with the same source-bound ledger. After a finalized-anchor disagreement, stop, investigate the trusted RPC/chain, and restore a reviewed checkpoint before any affected enrollment. Resume from a verified canonical position. Do not advance past unseen enrollments or reuse post-reorg authorizations. A recently provisioned reader with an interrupted submission can reconcile receipts by local nonce, without using the wallet seed.

## Reproduce the Lean release experiment

The release radar links the Lean 4.35.0 to 4.36.0 observation to an experiment on whether the new `bv_decide +uf` mode proves equivalent calls to an abstract function. Verify both official Linux toolchain archives against the SHA-256 values in the [qualification evidence](evidence/github-native-qualification.json), then use their approved local installations. The runner compares the new mode, default `bv_decide`, `grind`, and explicit congruence on identical statements across both releases. It records axiom audits. An independent Python enumeration checks the two valid workloads and gives a concrete witness for the false workload.

```sh
python3 -m research.lean_delta --before /opt/lean-4.35.0/bin/lean --after /opt/lean-4.36.0/bin/lean
```

The registered run uses locally installed tools with a 30-second limit per proof and no paid APIs. It is separate from the recurring proof-receipt replay, which retrieves only the registered evidence.

## Security review record

| Boundary | Control and remaining exposure |
| --- | --- |
| Wallet spoofing, enrollment replays and key substitution | Strict domain-tagged calldata, EOA raw-signature recovery and receipt position, current blockchain entitlement, expiring enrollment nonce, durable deduplication and single current device. A phished signer can approve an enrollment for another device. MetaMask and the approved reader origin are core trust dependencies. |
| Chains, contracts, balances and reorgs | Chain ID 1, fixed contract addresses, exact integer balance threshold, wrapped-name expiry, finalized contiguous enrollment scanning, fresh EIP-1898 reads and checkpoint recheck before commit. The RPC is trusted for canonical completeness. An Ethereum reorganization after publication cannot revoke an already delivered key. |
| Publisher, credentials and PRs | GitHub origin and state-branch custody are trusted. Environment secrets appear only in a job restricted to the official repository's reviewed `main`. A fixed ref and lease-safe commits protect state forks. Lockfile-pinned dependencies, install hooks disabled, a narrow state commit and public schema validation bound the artifact. |
| Browser origin, XSS and keys | A dedicated HTTPS origin is required. The member browser performs Web Crypto and stores a nonextractable key. The protected renderer inserts text and accepts only HTTPS source links. Dependency code and script authority on that full origin remain trusted. A compromised browser, wallet, reader publisher or authorized recipient can expose plaintext. |
| Availability, fee and scale | Size, request, block, signal, registry and artifact bounds. A stale/no-catch-up publisher prevents new fee prompts. On-chain flooding can delay recovery. Retry uses verified receipts, an atomic IndexedDB claim and a non-forced state ref. No guarantee on scheduling or provider availability. |
| Research and financial authority | Public source data is bounded and parsed as data, with separate workflow privileges. The system neither executes fetched instructions nor has paid compute or a spending key. Reported release changes create hypotheses, while proof replay, acceptance, revenue and profit remain distinct states. |

The qualification proves local and CI behavior, standards interoperability and read-only mainnet compatibility. The production environment, trusted origin, named independent review and real-member pilot must be verified separately.

## Français

### Décision et expérience membre

GitHub Pages sert des fichiers statiques. Une visite anonyme ne dispose d’aucun canal d’écriture ou de déclenchement GitHub autorisé. Une signature MetaMask établit la maîtrise du portefeuille. Pour remettre une clé à une personne admissible, le processus de publication a besoin d’un canal d’enregistrement vérifiable. Aucun canal anonyme, autonome et sans frais n’a été démontré dans les interfaces autorisées.

Le candidat utilise une transaction EIP-1559, de valeur nulle, sur le réseau principal Ethereum vers le précompilé d’identité `0x0000000000000000000000000000000000000004`. Ce précompilé renvoie les données et n’écrit aucun état. Les frais sont distincts des zéro ETH transférés. Aucun achat, transfert, dépôt, approbation ou mise en jeu de jeton n’est requis. La page présente une estimation et un plafond de frais avant la demande de confirmation dans MetaMask.

1. Ouvrez la page publique FRONTIER Ω ALPHA et sélectionnez AGI Club ou AGIALPHA. Suivez le lien vers l’origine GitHub Pages isolée.
2. Connectez l’extension MetaMask ou le navigateur intégré de MetaMask Mobile au réseau principal Ethereum. Pour AGI Club, saisissez uniquement le premier libellé du nom.
3. Vérifiez le destinataire, la valeur de zéro ETH et les frais dans MetaMask. L’adresse signataire, la clé publique, le libellé Club facultatif et la participation peuvent être reliés à la transaction publique.
4. Après le minage, attendez la finalité Ethereum et une publication GitHub réussie. Un horaire GitHub Actions peut être retardé. L’état se consulte dans le lecteur, sans compte GitHub.
5. Revenez avec le navigateur, le stockage et le compte correspondants pour lire sans nouvelle transaction. La clé privée P-256 reste non extractible dans le stockage du lecteur. Effacer ce stockage ou changer d’appareil peut entraîner un nouvel enregistrement et des frais. La phrase secrète MetaMask ne restaure pas cette clé. Un enregistrement dont la réponse est interrompue peut être retrouvé par le reçu publié.
6. L’admissibilité est recalculée avant la lecture et la délivrance de nouvelles clés. Un changement de compte ou de réseau verrouille le lecteur. Un appareil devenu inadmissible libère sa place. Pour revenir après avoir retrouvé son admissibilité, il faut se réinscrire. Les anciens destinataires peuvent conserver les dossiers, enveloppes et clés déjà obtenus.

La version native vérifie les transactions directes du signataire. Les portefeuilles qui exigent une signature EIP-1271 ou un relais de contrat restent à qualifier dans cette version. La version locale de référence conserve les essais SIWE et EIP-1271.

### Opérations et reprise

- Faites approuver la fusion sur `main` et la revue indépendante. Le site public suit `research-pages.yml`. Il fonctionne en mode hors ligne sans catalogue protégé.
- Autorisez une origine indépendante hébergée sur GitHub Pages avec HTTPS. Utilisez une origine que vous contrôlez ou un sous-domaine vérifié rattaché au dépôt Pages dédié. Conservez la configuration du site existant. Inscrivez l’adresse racine exacte dans `FRONTIER_ALPHA_READER`. Lancez le processus GitHub avec `build_reader` pour produire les fichiers du lecteur. Publiez-les sur l’origine approuvée. Le lecteur refuse la conservation de clés sur l’origine publique partagée.
- Restreignez l’environnement `frontier-omega-alpha-provision` à la branche protégée. Enregistrez `FRONTIER_ALPHA_PUBLISH_KEY` et `FRONTIER_ALPHA_RPC` comme secrets d’environnement. Le RPC doit fournir des blocs finalisés complets, les transactions signées brutes et des lectures par empreinte de bloc canonique. Il sert exclusivement d’interface Ethereum.
- Suivez les commandes `keygen`, `preflight` et `seal` de la section anglaise. Placez l’ancre vérifiée dans `FRONTIER_ALPHA_ANCHOR_HEIGHT` et `FRONTIER_ALPHA_ANCHOR_HASH`. Confirmez le catalogue chiffré sur `main`. Conservez les documents en clair et les clés en dehors du dépôt et des artefacts.
- Activez `FRONTIER_ALPHA_NATIVE_ENABLED` une fois l’origine, les autorisations, les secrets et le catalogue approuvés. Testez la première publication et les deux parcours avec des personnes qui consentent à utiliser de vrais portefeuilles. Évaluez également le navigateur de MetaMask Mobile et un cas inéligible. `FRONTIER_ALPHA_RESEARCH_ENABLED` active séparément la collecte périodique et la reproduction scientifique.
- Le processus examine au plus 120 blocs et 48 signaux par exécution. Le premier périmètre est de 96 appareils actifs, un par portefeuille, 96 reçus terminaux récents, 12 dossiers et 6 Mio pour la bibliothèque publique. Un retard de lecture ou de publication suspend l’inscription. Les frais dépendent de l’état d’Ethereum et de la transaction. Aucun abonnement d’hébergement payant n’est configuré. La disponibilité et les limites du fournisseur RPC et de GitHub Pages doivent être mesurées en situation réelle.
- En cas d’incident, désactivez la publication protégée et reconstruisez Pages. Pour retirer des dossiers, révisez le catalogue. Pour révoquer un appareil compromis lors des prochaines publications, ajoutez son identifiant public à la liste revue `native/revoked-enrollments.json`. Pour renouveler leurs clés, scellez de nouvelles versions. Pour changer la clé de publication, fournissez à `rekey` le point de reprise et la bibliothèque de la même publication, puis alignez le catalogue, le nouveau point de reprise chiffré et le secret GitHub avant la reprise. Le point de reprise compact authentifie l’empreinte de la bibliothèque. En cas de réorganisation de l’ancre, restaurez les deux fichiers d’une publication sûre et réanalysez les inscriptions touchées. Les anciennes copies restent accessibles à qui les détient.

### Reproduire l’expérience sur les versions de Lean

Le radar relie le passage de Lean 4.35.0 à 4.36.0 à une expérience qui vérifie si `bv_decide +uf` peut prouver l’équivalence d’appels à une fonction abstraite. Vérifiez les deux archives Linux officielles avec les empreintes SHA-256 de la qualification, puis exécutez la commande de la section anglaise. Elle compare le nouveau mode à `bv_decide`, à `grind` et à une preuve explicite par congruence. Une énumération Python indépendante vérifie les deux cas valides et fournit un contre-exemple concret au troisième. L’exécution locale est limitée à 30 secondes par preuve et conserve la liste des axiomes utilisés.

### Contrôles de sécurité

La vérification lie le signataire direct, l’adresse du précompilé, le réseau principal, le format, le nonce, le bloc finalisé et la clé publique de l’appareil. Les règles AGI Club ou AGIALPHA sont revérifiées avant la délivrance de nouvelles clés. Les clés de contenu sont protégées par AES-256-GCM et remises au seul destinataire prévu au moyen de HPKE RFC 9180. La modification de l’enveloppe ou du fichier chiffré fait échouer l’authentification.

Les secrets de publication sont réservés au processus GitHub de `main` sur le dépôt officiel. La revue traite l’usurpation, le hameçonnage, le rejeu, les faux blocs, les fuites de secrets, les scripts sur la même origine, les dépendances, la perte de clé, la saturation et les sources de recherche malveillantes. La sécurité suppose la maîtrise de GitHub, de l’origine de lecture, du RPC, du navigateur et de MetaMask. Une revue indépendante de l’instance réelle et un essai avec de vrais membres restent nécessaires.

## Primary references / Références primaires

- [GitHub Pages hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [protected environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments), [workflow token and dispatch](https://docs.github.com/en/actions/concepts/security/github_token), [schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [MetaMask transaction confirmation](https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/eth_sendTransaction/) and [mobile browser](https://support.metamask.com/configure/wallet/how-to-use-the-metamask-mobile-browser)
- [Ethereum JSON-RPC](https://ethereum.org/developers/docs/apis/json-rpc/), [Ethereum execution specification](https://ethereum.github.io/execution-apis/), [EIP-7623 gas pricing](https://eips.ethereum.org/EIPS/eip-7623)
- [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180.html), [CFRG test vectors](https://github.com/cfrg/draft-irtf-cfrg-hpke/blob/master/test-vectors.json), [hpke-js](https://github.com/dajiaji/hpke-js)
