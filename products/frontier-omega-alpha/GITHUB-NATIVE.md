# GitHub Pages and MetaMask / GitHub Pages et MetaMask

## Access decision

Members authenticate with a MetaMask message signature and read-only Ethereum mainnet checks. A pre-provisioned member can connect MetaMask, verify eligibility and read approved research. A new browser needs its encrypted content keys provisioned once. All wallet operations in these paths are transaction-free.

GoalOS Singularity Office uses Ethereum ownership reads and a typed signature or personal signature. The existing dual-access GoalOS Foundry supports both direct token balance and direct Club ownership with `eth_call` and `personal_sign`. Those static gates admit the browser to public app assets. The separate GoalOS encrypted-vault scaffold deliberately rejects unlocks until an audited decryption provider is configured. [GoalOS Office source](https://github.com/MontrealAI/MontrealAI.github.io/blob/a9cc143bc05495405ac63b0e2645c425d66410b8/goalos-singularity-office-omega/access.js) · [Dual-access source](https://github.com/MontrealAI/MontrealAI.github.io/blob/a9cc143bc05495405ac63b0e2645c425d66410b8/sovereign-alpha-foundry-v0/GoalOS_UVSI3_v8_STANDALONE.html#L1987) · [Vault scaffold source](https://github.com/MontrealAI/MontrealAI.github.io/blob/a9cc143bc05495405ac63b0e2645c425d66410b8/GoalOS_AGI_Club_Web3_Encrypted_Vault_Scaffold_v7/assets/vault-provider.js)

| Architecture | Security and confidentiality | Member friction and cost | Mobile | Operations |
| --- | --- | --- | --- | --- |
| GoalOS static gate | Read-only wallet eligibility and a signed browser receipt. The browser loads public application assets. | Connect and sign. Zero gas. | Injected MetaMask. Actual device coverage depends on the product build. | Static publishing. Suitable for public assets. |
| #541 zero-value enrollment prototype | Ethereum sender recovery and finality feed per-device HPKE. On-chain enrollment reveals wallet and optional Club label. Approved research remains ciphertext. | One Ethereum transaction with gas and confirmation on a new browser. | Browser fixtures covered desktop and narrow layouts. | Scheduled chain scanner, finalized checkpoint and encrypted publisher. Archived on the [original candidate](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/dcaa91fe2a78561aafd3de2cefd77a8256cd4be3/products/frontier-omega-alpha/GITHUB-NATIVE.md). |
| Signed device request and pre-provisioned ciphertext | Domain-bound EIP-4361 signature, current entitlement, nonextractable P-256 device key, AES-256-GCM and per-device HPKE. Private request and public ciphertext have separate authority. | First device signs and needs an approved handoff. A provisioned device connects and reads after its current check. Zero gas. | Bilingual desktop and narrow Chromium fixtures passed. A physical MetaMask Mobile pilot remains open. | Static GitHub Pages, an existing authorized operator, a protected Actions publisher and the approved repository. No standing API service. |
| Existing local SIWE reference | A trusted HTTPS issuer verifies the same eligible wallet and releases encrypted keys to the authenticated session. | Connect and sign on first use. Zero gas. | Local browser tests use fixture signers. | Needs a separately authorized running issuer. GitHub Pages serves static files. |

The signed-device candidate provides confidential GitHub-hosted reading after provisioning. Fully unattended first-time enrollment remains unverified. A public Pages reader has no authorized channel for delivering a new signed request to the protected publisher. The initial handoff needs an approved operator or another separately authorized receiving mechanism. A GitHub account used to submit a file would be a transport dependency. Member reading uses MetaMask. [GitHub Pages architecture](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) · [MetaMask sign-in guidance](https://docs.metamask.io/metamask-connect/evm/guides/sign-data/)

## Eligibility and encryption

The ENSv1 Registry at `0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e` identifies the direct owner of an unwrapped one-label `.club.agi.eth` name on Ethereum mainnet. If it points to the ENSv1 Name Wrapper at `0xD4416b13d2b3a9aBae7AcD5D6C2BbDBE25686401`, both `ownerOf` and `getData` must match the wallet. An emancipated Club subname expires at its deadline. A temporary fuse expiry can leave a parent-controlled name's ownership intact. A direct Registry subname has no separate expiry field. A transfer changes Club eligibility on the next check. Existing ENSv1 names qualify as issued. Holding at least 1,000,000 authentic $AGIALPHA independently qualifies the signing wallet. [Mainnet ENSv1 deployments](https://docs.ens.domains/learn/deployments/) · [Real ownership, transfer, expiry and token evidence](evidence/ENSV1-QUALIFICATION.md)

On each fresh canonical block, FRONTIER reads the member's own effective expiry and verifies that `club.agi.eth` and `agi.eth` still have effective owners. For the `.eth` root of this namespace it also checks the ENSv1 Base Registrar lease and its on-chain grace period. The effective limit is the earliest applicable member or ancestor ownership deadline. The existing Club tool submits `extendExpiry` for the specific member node. Updating a parent increases the extension ceiling. A member's own expiry changes only when its node is extended. FRONTIER only reads these changes. [Existing membership renewal tool](https://github.com/MontrealAI/MontrealAI.github.io/blob/a9cc143bc05495405ac63b0e2645c425d66410b8/extendexpiryv0.html#L79) · [ENSv1 extension rules](https://docs.ens.domains/wrapper/expiry/)

The reader makes a nonextractable P-256 device key in IndexedDB on its isolated HTTPS origin. Its MetaMask request uses a canonical EIP-4361 message bound to the origin, wallet, chain, device public key, optional Club label, random nonce and expiry. The protected publisher checks the signature and current eligibility again. It seals content keys to that device using RFC 9180 P-256/HKDF-SHA256/AES-256-GCM. Envelope authentication binds the signed proof and exact ciphertext digest. The public library contains encrypted records, opaque proof identifiers and device envelopes. Signed packets, wallets and labels are inside the sealed operator input.

## Member and operator procedure

1. Open the approved reader on the isolated GitHub Pages origin and connect MetaMask. Select the Club name or the token path. On the Club path, enter the first label of the name.
2. For a new device, review and sign the displayed request. Provide the download privately only through the authorized handoff. The browser holds the device private key and can show signed request status.
3. After the operator provisions the device, return with the same browser storage and wallet. Connect, recheck current eligibility and open authorized encrypted dossiers. A pre-expiry ENSv1 extension works on the next check. If an existing membership lapses, access pauses. The same device resumes after current eligibility returns and the publisher refreshes its encrypted keys. Renewal requires no new FRONTIER signature or registration. Explicit operator revocations stay in effect. Account and chain changes lock the reader. A new device or cleared storage requires provisioning again.
4. Obtain independent review and owner approval before release. The approved isolated GitHub Pages origin must serve only trusted content. Set `FRONTIER_ALPHA_READER` to its exact HTTPS root. Build the static bundle with the guarded publisher workflow's `build_reader` input. Configure `frontier-omega-alpha-provision` for protected `main` with the approved reviewer, publisher key and trusted Ethereum RPC. Complete the consenting wallet pilot before activation.

The publisher handles up to 48 approved requests per pass and retains up to 96 registered devices, including paused devices. It rechecks wallet eligibility and withholds new keys during a lapse. Existing readers can keep copies of data they already decrypted. The static GitHub publication can be delayed. The historical chain scanner and its tests remain as evidence of the former approach.

From `products/frontier-omega-alpha` with the approved operator settings in the environment:

```sh
npm ci --ignore-scripts
node native/operator.mjs preflight
node native/operator.mjs approve-enrollment /private/signed-device.json /private/sealed-enrollment.json
node native/operator.mjs seal research-brief 1 /private/approved-research.json /private/sealed-record.json
```

Set the reviewed preflight anchor in `FRONTIER_ALPHA_ANCHOR_HEIGHT` and `FRONTIER_ALPHA_ANCHOR_HASH`. The reviewed repository changes use the sealed enrollment file as `native/approved-enrollments.json` and the approved encrypted content in `native/approved-releases.json`. The approved-enrollment file initially contains `null`. The protected publisher revalidates requests even after operator approval. GitHub pages and job logs receive only published ciphertext and compact status outputs. The existing state branch retains the encrypted checkpoint and matching library. Apply the existing secret custody procedure with `keygen` and `rekey`. Rotate the catalog, enrollment batch and matching checkpoint together.

Disable protected publication with `FRONTIER_ALPHA_NATIVE_ENABLED` and rebuild Pages. A record can be withdrawn through the approved catalog. An enrollment can be revoked through the reviewed identifier list. Resume after failures from an authenticated checkpoint and matching library. A signed enrollment uses a different library schema from the archived transaction prototype. An archived receipt supplies no signed enrollment authority.

Initial fixture qualification covers wrapped ENSv1, the token-only path, ineligible wallets, domain and device binding, replay, sealed input, checkpoint restore, and post-approval revocation. The real tests so far read mainnet eligibility, including live holders and archived transfer and expiry outcomes. Consent-based sign-in with real MetaMask wallets, physical mobile compatibility, a secure handoff, administrator-enforced checks and independent release sign-off remain production gates.

## Reproduce the Lean release experiment

The release radar links the Lean 4.35.0 to 4.36.0 observation to an experiment on whether the new `bv_decide +uf` mode proves equivalent calls to an abstract function. Verify both official Linux toolchain archives against the SHA-256 values in the [qualification evidence](evidence/github-native-qualification.json), then use their approved local installations. The runner compares the new mode, default `bv_decide`, `grind`, and explicit congruence on identical statements across both releases. It records axiom audits. An independent Python enumeration checks the two valid workloads and gives a concrete witness for the false workload.

```sh
python3 -m research.lean_delta --before /opt/lean-4.35.0/bin/lean --after /opt/lean-4.36.0/bin/lean
```

The registered run uses locally installed tools with a 30-second limit per proof and no paid APIs. It is separate from the recurring proof-receipt replay, which retrieves only the registered evidence.

## Français

### Décision et expérience membre

Le lecteur GitHub Pages vérifie le portefeuille MetaMask à l’aide d’une signature de message et de lectures sur Ethereum. Pour un appareil déjà provisionné, le membre se connecte, confirme son admissibilité et lit les dossiers chiffrés autorisés. La démarche est sans transaction et sans frais de gaz. Un nouveau navigateur nécessite une remise initiale de clés approuvée.

GoalOS Office et le parcours double de GoalOS illustrent l’accès par signature. Les fichiers de ces applications statiques sont publics. Le modèle de coffre GoalOS exige un fournisseur de déchiffrement audité. FRONTIER remet les clés à l’appareil au moyen d’enveloppes HPKE. La signature lie l’origine, le réseau, le portefeuille, la clé publique de l’appareil, l’échéance et un nonce. Le lecteur garde la clé privée dans son stockage local isolé.

| Solution | Protection et expérience | Coût, mobile et exploitation |
| --- | --- | --- |
| Accès statique GoalOS | Signature et contrôle du portefeuille, fichiers publics. | Zéro gaz. Interface MetaMask injectée. Publication statique. |
| Prototype de la demande nº 541 | Dossiers chiffrés. L’inscription publie les données du portefeuille sur Ethereum. | Transaction et frais à la première inscription. Attente de finalité et analyse des blocs. |
| Demande signée et provisionnement | Dossiers AES-256-GCM, enveloppes HPKE liées à l’appareil, admissibilité revérifiée. | Zéro gaz. Remise initiale autorisée. Essais de navigateur bilingues réussis. Essai MetaMask Mobile réel en attente. |
| Référence SIWE locale | Session authentifiée et remise de clés chiffrées. | Zéro gaz. Nécessite un serveur HTTPS autorisé au-delà des fichiers statiques de Pages. |

Ouvrez le lecteur sur son origine GitHub Pages approuvée. Sélectionnez AGI Club ou $AGIALPHA et connectez MetaMask. Une demande signée pour un nouvel appareil est remise en privé à l’opérateur selon le canal approuvé. Le processus GitHub autonome de première inscription reste à démontrer. Après provisionnement, le même navigateur et le même portefeuille peuvent relire les dossiers autorisés après une vérification courante.

### Admissibilité ENSv1

Pour un nom direct sous `.club.agi.eth`, le titulaire correspond au registre ENSv1 ou aux deux lectures du Name Wrapper ENSv1. FRONTIER vérifie l’échéance du nom du membre, l’autorité des parents et le terme d’enregistrement d’`agi.eth` auprès du Base Registrar ENSv1, période de grâce comprise. Prolonger un parent augmente le plafond. Le sous-nom conserve sa propre échéance jusqu’à sa prolongation. Un transfert ou l’expiration d’un sous-nom émancipé peut suspendre l’accès. Un sous-nom contrôlé par son parent peut conserver son titulaire à l’expiration de permissions temporaires. Le même appareil retrouve ses clés à la publication suivante après rétablissement de l’admissibilité, sans réinscription. Une révocation décidée par l’opérateur reste en vigueur. Les noms ENSv1 actuels sont admissibles sans migration. Le seuil indépendant demeure de 1 000 000 de $AGIALPHA authentiques. [Qualification en lecture seule](evidence/ENSV1-QUALIFICATION.md)

### Opérations

Configurez l’origine HTTPS isolée et l’environnement `frontier-omega-alpha-provision` sur la branche protégée. Conservez les secrets et les signatures en clair dans l’espace privé de l’opérateur. Utilisez les commandes de la section anglaise pour valider et sceller une demande. Placez uniquement les enveloppes chiffrées dans la revue GitHub. Effectuez la revue de sécurité indépendante ainsi que l’essai MetaMask réel avant toute activation. Un nouveau portefeuille, un réseau différent ou une admissibilité perdue verrouille la lecture. Les copies déjà déchiffrées peuvent subsister.

### Reproduire l’expérience sur les versions de Lean

Le radar relie le passage de Lean 4.35.0 à 4.36.0 à une expérience qui vérifie si `bv_decide +uf` peut prouver l’équivalence d’appels à une fonction abstraite. Vérifiez les deux archives Linux officielles avec les empreintes SHA-256 de la qualification, puis exécutez la commande de la section anglaise. Elle compare le nouveau mode à `bv_decide`, à `grind` et à une preuve explicite par congruence. Une énumération Python indépendante vérifie les deux cas valides et fournit un contre-exemple concret au troisième. L’exécution locale est limitée à 30 secondes par preuve et conserve la liste des axiomes utilisés.

## Primary references / Références primaires

- [GitHub Pages hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [protected environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments), [workflow token and dispatch](https://docs.github.com/en/actions/concepts/security/github_token), [schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [MetaMask message signing](https://docs.metamask.io/metamask-connect/evm/guides/sign-data/) and [EIP-4361](https://eips.ethereum.org/EIPS/eip-4361) and [mobile browser](https://support.metamask.com/configure/wallet/how-to-use-the-metamask-mobile-browser)
- [Ethereum JSON-RPC](https://ethereum.org/developers/docs/apis/json-rpc/), [Ethereum execution specification](https://ethereum.github.io/execution-apis/), [EIP-7623 gas pricing](https://eips.ethereum.org/EIPS/eip-7623)
- [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180.html), [CFRG test vectors](https://github.com/cfrg/draft-irtf-cfrg-hpke/blob/master/test-vectors.json), [hpke-js](https://github.com/dajiaji/hpke-js)
