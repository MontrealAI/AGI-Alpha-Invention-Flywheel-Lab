# Two public dispatch exclusions upheld / Deux exclusions confirmées

**ABSTAIN.** The MONTREAL.AI dispatch research workflow acquired and independently decoded the original inputs for both withheld days. Neither arm recovered a complete, source-justified day. Keep the existing production060 admissibility rule and the ordinary SciPy route. No dispatch was released. [Registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/933219e2b791132dae69e840f834b82566416f0c/publication/unseen-advantage/DISPATCH-REGISTRATION.md) · [Frozen executable](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/4fc58ceca7bb10109b71e8a6d6d4e7faf70700d4/publication/unseen-advantage)

| Case | Raw evidence | Conventional result | Recovery result | Separate numerical verification |
|---|---|---|---|---|
| `cdp_o45_08d` | 45 orders, 45 × 8 times and a 53 × 53 distance matrix. The eight entries for order 37 are absent in the times and each of the two proxy-distance directions. | ABSTAIN | ABSTAIN, two completions retain all recorded values but give different hypothetical travel times | Passed |
| `cdp_o50_d` | 50 orders, 49 × 8 times and a 57 × 57 distance matrix. There are 392 finite overlaps and neither representation provides the missing row identity. | ABSTAIN | ABSTAIN, two order-preserving one-row omissions assign the first visible row to different orders | Passed |
| `cdp_o5_06d` | Five orders and 40 finite travel times in both representations | Source ready | Source ready, zero recovered cells | Passed |

The two completions in each refusal preserve the published observations under the stated representation and omission model. Their values are counterexamples. They have no authority as estimates or replacement travel inputs. The original corpus remains at 261 of 263 mapped finite-travel days, separate from historical dispatch and quality acceptance.

## Execution and costs

- The first registered retrieval hit HTTP 403 for all three files. It returned ABSTAIN without scoring. The retry used standard HTTPS with curl against the same official URLs, retrieved 11,701 bytes, took 21.625 seconds of transfer time, and matched all pinned SHA-256 digests. No raw MATLAB file is distributed here. [Initial attempt](evidence/dispatch-initial-acquisition.json) · [Retry](evidence/dispatch-retrieval-retry.json)
- The successful run checked all three cases and rejected all 11 recorded negative controls, including a changed numeric output and both duplicated ambiguity witnesses. Captured wall time was 0.502 seconds for the restarted process including imports, with 0.0369 seconds inside the runner after imports. On this one run the conventional reconciliation took 1.547 ms across the three files. The experimental route took 0.843 ms plus 0.769 ms for witness verification. Both routes shared the same acquisition and pinned metadata. These are execution measurements for the tested files, with unknown people, source fees, operational maintenance and complete downstream costs. [Run receipt](evidence/dispatch-recovery.json) · [Process time](evidence/dispatch-time-recovered.txt)
- The initial development implementation rejected the official five-order sample because it assumed double storage for `prod2constr_matrix`. The source stores that array as unsigned bytes inside a double-class matrix. Support for the documented numeric storage tag fixed the error before the evaluation artifact was frozen. A separate timing-wrapper attempt stopped before acquisition because `/usr/bin/time` was unavailable. Bash timing captured the subsequent attempts.
- The candidate decoder uses Python's standard library. The independent numerical decoder uses SciPy 1.17.0 and NumPy 2.3.5 on Linux x86-64 with Python 3.12.14. Its technique and code path are distinct. The case IDs and files are public, and there was no independent operating administrator, real plant approval or consenting member.

## Reproduce

Use the frozen standalone Python programs and the pinned repository checkout. Put the three unmodified source files in a temporary directory if the default Python HTTPS client is refused. The runner always verifies each file against the original public version.

```sh
git switch --detach 4fc58ceca7bb10109b71e8a6d6d4e7faf70700d4
mkdir -p /tmp/frontier-dispatch-raw
base=https://data.mendeley.com/public-files/datasets/b78bc94d95/files
curl -fLsS --max-time 20 "$base/dcac9669-c76f-40fd-a922-c2932bcaebb0/file_downloaded" -o /tmp/frontier-dispatch-raw/cdp_o45_08d.mat
curl -fLsS --max-time 20 "$base/e085eaff-68e1-4adc-b1a8-c5a3eb2befbd/file_downloaded" -o /tmp/frontier-dispatch-raw/cdp_o50_d.mat
curl -fLsS --max-time 20 "$base/8bb8a385-a0ae-4bcb-ac35-a8bd6d36faff/file_downloaded" -o /tmp/frontier-dispatch-raw/cdp_o5_06d.mat
python publication/unseen-advantage/run_dispatch_recovery.py --source-cache /tmp/frontier-dispatch-raw
```

Data credit Alexandros Tzanetos and Maude Blondin, Mendeley Data v1, [10.17632/b78bc94d95.1](https://doi.org/10.17632/b78bc94d95.1), CC BY 4.0. The new data excerpts are derived diagnostics, case IDs, and toy counterexamples. The previously distributed normalized data preserve time of day and pseudonyms.

## Résultats en français

**ABSTAIN.** Aucune des deux journées précédemment exclues ne peut être réadmise à partir de la version publiée. Les huit temps manquants de la commande 37 manquent aussi aux deux blocs de distances dérivées. Dans l'autre journée, les deux représentations comportent 49 lignes pour 50 commandes, sans clé qui permette d'identifier la ligne omise. Le témoin valide propose deux complétions incompatibles avec une identification unique. La journée témoin est demeurée admissible.

Le décodeur SciPy distinct a confirmé les trois décisions et vérifié les témoins. Les onze contrôles négatifs ont réussi. La première récupération a été refusée en HTTP 403 pour chacun des trois fichiers, puis la reprise par curl a récupéré 11 701 octets en 21,625 secondes de transfert, avec les trois empreintes attendues. Le calcul conventionnel a pris 1,547 ms, contre 1,613 ms pour l'analyse expérimentale et sa vérification. Ces chronométrages ne couvrent pas le coût complet. Aucune répartition opérationnelle, acceptation par un exploitant, économie réalisée ou valeur membre ne découle de ce résultat.
