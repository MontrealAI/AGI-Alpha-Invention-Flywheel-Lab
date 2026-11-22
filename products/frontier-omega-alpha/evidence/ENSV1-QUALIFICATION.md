# AGI Club ENSv1 qualification / Qualification ENSv1 AGI Club

## Ethereum mainnet

Read-only checks on 22 November 2026 used the same `Mainnet.ownsClub` verifier as the reader and publisher. The suffix routes through the [mainnet ENSv1 Registry and Name Wrapper](https://docs.ens.domains/learn/deployments/). No migration is required. The registry and wrapper calls shared one canonical block hash per check.

| Case | Result |
| --- | --- |
| Existing wrapped members | Four current wallet owners passed and an unrelated address failed for each at block 26473372. The Registry pointed to the ENSv1 Name Wrapper. Both Wrapper ownership reads agreed. |
| Expired wrapped name | Two public archive RPCs agreed. The registered owner passed at block 25768466, nine seconds before expiry, and was denied at block 25768467, three seconds after expiry. At block 26473387, the Registry still pointed to the Wrapper and the Wrapper returned the zero owner. |
| Unwrapped Club members | A Registry `NewOwner` scan under `club.agi.eth` produced 118 distinct labels. At block 26473387, all 118 Registry entries pointed to the ENSv1 Name Wrapper. No unwrapped specimen was found in that scan. |
| Wrapped transfer | At block 22985713, the former wallet passed and the recipient was denied. At the transfer block 22985714, the former wallet was denied and the recipient passed. The test replayed actual state across a past ENSv1 Name Wrapper transfer. |
| Unwrapped transfers and exact expiry | Fixture signers covered a Registry ownership transfer and loss of access for the former owner. Tests covered the exact expiry of an emancipated subname, expiry of temporary fuses on a parent-controlled name, and denial when the Registry no longer listed an owner. |
| $AGIALPHA | The live contract returned the expected symbol and 18 decimals. At block 26473434, a qualifying holder passed and an unrelated non-holder was denied with no Club label. The exact 1,000,000-token boundary passed fixture tests. |
| Existing members extend their ENSv1 subnames | At blocks 19223883, 20395493 and 20395519, three member wallets each called the ENSv1 Name Wrapper's `extendExpiry` for their own leaf. Each leaf's old and new expiries were read across the block boundary. A second archive provider agreed on the after-state. All three qualified at block 26473698, past their original deadline of 16 August 2026. |
| Parent-only extension | At block 21774631, `club.agi.eth` extended its deadline from 15 May 2030 to 15 August 2033. The sampled member's own expiry stayed at 15 May 2030, as the reads immediately before and after confirmed. |

The primary reads came from `ethereum-rpc.publicnode.com`. Blockscout indexed Registry logs. The historical reads used `eth.drpc.org` and `eth-mainnet.g.alchemy.com/public` against the same Ethereum history. The operational record omits member names and wallets. The live work was read-only. Browser and publisher qualification used fixture signers. A consenting live MetaMask pilot and independent security release review remain required before production activation.

For the transaction-free candidate, a fresh mainnet test at block 26473588 confirmed three wrapped Club holders and rejected the unrelated wallet for all three names. It also confirmed a holder through the token-only route and rejected the comparison wallet. The domain-bound signature through ciphertext reading was exercised separately with fixture signers in both languages. [Transaction-free access and trade-offs](../GITHUB-NATIVE.md)

The Club's existing renewal page reads the leaf and parent wrapper records and submits the two hashes to `extendExpiry`. The deployed ENSv1 contracts determine the effective expiry. At block 26473698, 110 of 118 indexed leaves had a current owner and unexpired wrapper date. All 110 displayed the `CAN_EXTEND_EXPIRY` fuse. The reader verifies eligibility with current read-only calls. The browser regression confirmed pause after expiry, restoration with the existing device and no new enrollment signature, independent operator revocation and wallet-change locking. [Club tool](https://github.com/MontrealAI/MontrealAI.github.io/blob/a9cc143bc05495405ac63b0e2645c425d66410b8/extendexpiryv0.html#L79) · [ENSv1 expiry](https://docs.ens.domains/wrapper/expiry/)

| Blocks compared | Leaf deadline before (UTC) | Leaf deadline after (UTC) |
| --- | --- | --- |
| 19223882 → 19223883 | 2026-08-16 15:17:44 | 2027-08-15 15:11:11 |
| 20395492 → 20395493 | 2026-08-16 15:17:44 | 2030-05-15 11:11:11 |
| 20395518 → 20395519 | 2026-08-16 15:17:44 | 2030-05-15 11:11:11 |

At the common recheck, all three leaf deadlines were 2030-05-15 11:11:11 UTC. The parent deadline was 2033-08-15 15:17:44 UTC. The recorded calls belong to the historical owners. This qualification submitted no wallet signatures or transactions.

### Recheck a consenting case

From `products/frontier-omega-alpha` with the locked Node dependencies installed, supply the existing name's first label and current wallet in `FRONTIER_TEST_LABEL` and `FRONTIER_TEST_WALLET` outside Git. This check sends Ethereum read requests and returns a decision and its block.

```sh
node --input-type=module <<'JS'
import { getAddress } from 'ethers';
import { Mainnet, httpRpc } from './access/chain.mjs';
const mainnet = new Mainnet(httpRpc('https://ethereum-rpc.publicnode.com'));
const snapshot = await mainnet.snapshot();
const owner = await mainnet.ownsClub(getAddress(process.env.FRONTIER_TEST_WALLET),
  process.env.FRONTIER_TEST_LABEL, snapshot);
console.log({ clubEligible: owner, block: snapshot.number, hash: snapshot.ref.blockHash });
JS
```

## Français

Les vérifications en lecture seule du 22 novembre 2026 ont confirmé quatre titulaires ENSv1 de noms AGI Club encapsulés, ainsi que le refus d’un autre portefeuille pour chacun. Deux sources Ethereum d’archives ont confirmé l’admissibilité d’un titulaire neuf secondes avant l’expiration de son sous-nom et son refus trois secondes après. Le rejeu d’un véritable transfert au bloc 22985714 confirme la perte d’accès de l’ancien titulaire et l’admissibilité du nouveau. Au bloc 26473387, les 118 entrées du Registre relevées renvoyaient toutes au Name Wrapper ENSv1. Les essais automatisés couvrent aussi les transferts des noms non encapsulés et l’expiration des permissions temporaires. Au bloc 26473434, le parcours $AGIALPHA a accepté un titulaire admissible et refusé un autre portefeuille sans libellé Club.

Trois membres ont prolongé leur propre sous-nom ENSv1 aux blocs 19223883, 20395493 et 20395519. Ils demeuraient admissibles au bloc 26473698, après leur échéance initiale. Les échéances avant et après chaque prolongation figurent au tableau ci-dessus. Au bloc 21774631, la prolongation de `club.agi.eth` a changé uniquement l’échéance du parent dans le cas observé. Le navigateur retrouve le même enregistrement et les mêmes droits de lecture après le renouvellement. L’essai de ce parcours a utilisé des signataires de test et une publication simulée.

Aucune migration vers ENSv2 n’est requise. Le seuil indépendant demeure de 1 000 000 de $AGIALPHA. Avant l’activation, terminez la revue de sécurité indépendante et l’essai MetaMask avec des membres qui y consentent. La commande ci-dessus vérifie un titulaire depuis les données publiques, sans demander de signature ni émettre de transaction.
