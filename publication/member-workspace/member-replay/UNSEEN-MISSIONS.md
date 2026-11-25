# Two fresh bilingual construction missions

A separate evaluator authored and froze two fictional missions, four disclosed examples per mission, and independent exhaustive references before the candidate ran. The examples contained no member data. Held records stayed out of model prompts. The product used a staged 1.4 companion on Linux with isolated browser eligibility. The study used Qwen3.5-0.8B-Q4_0 through local llama.cpp and sent no provider request outside the computer.

Registration SHA-256 `578556c97cc6c6abb2ba07fe3d8a9f013eb787a17dce7bc501d16dc50f944941`. The staged companion SHA-256 was `d6996862c12b167e16d8c80ee7cde66b3b70603b69d3b7d27f4a8de0a025e72e`.

## Frozen ambitions

### English

> A mobile repair café needs a portable checker for conflicts between two reservations of the same shared bench. Construct and test it using the attached fictional examples. Given two integer minute intervals in one day, treat each start as included and each end as excluded. An invalid interval or missing field must give a refusal, never a silent correction. For a valid pair, calculate both overlap_minutes and gap_minutes. Give a deterministic portable artifact the café can replay and compare it with exhaustive minute-set comparison on the authorized observations. This is an operating test for this declared bench only.

The 1,301 held records included 1,076 expected refusals. The disclosed examples have SHA-256 `9e652f54950b5d99fa77f3970928ae8e6bdd033b99aed3e1692f7db2b199a624`. The held references have SHA-256 `17767b462589af1ce6f169198f7233b13af9a5e61e235109cef9cae535f92a79`.

### Français

> Notre atelier itinérant réemploie des panneaux pour ses présentoirs. Construisez et testez un instrument déterministe portable qui calcule le plus grand nombre de sections entières de même longueur que l'on peut préparer. Deux marges inviolables, une à chaque bord, sont comprises dans la longueur totale. Une perte est comptée entre deux sections, et aucune perte supplémentaire après la dernière. Les longueurs sont des millimètres entiers, les marges et la perte peuvent être nulles, la longueur du panneau et celle d'une section doivent être positives, et les marges réunies ne peuvent dépasser la longueur du panneau. Une mesure manquante ou invalide doit mener à un refus. Servez-vous du fichier joint fictif, notez la préparation réellement exécutée, et laissez un outil réutilisable. Un estimé de coût ou une recommandation de procédure physique n'est pas demandé.

The 817 held records included 157 expected refusals. The disclosed examples have SHA-256 `c75fa6b109bd79e90f4b5b0a0c50763ae6dd4e406bfa76b8c2c0766e0ab74ea0`. The held references have SHA-256 `d8d0751e0f89f4b844b61ee2a4b6c19eba19f4a62eb89adf7f3e4092d0a66d9e`.

## Observed results

| Trial | English | French |
| --- | --- | --- |
| Product, up to three model requests with 584 output tokens each | Actual local submission with its approved source. One model attempt reached the output limit. No usable response or action. | Actual local submission with its approved source. One model attempt reached the output limit. No usable response or action. |
| Product, up to three requests with 1,280 output tokens and ten actions | Three usable replies and ten tool attempts. A portable SQL file ran on development data. The SQL sums already-computed overlap and gap columns and cannot take raw intervals. Independent relevance verdict FAIL. | One model request generated 1,223 tokens. The native adapter refused the provider response and paused without a usable reply or artifact. The exact refusal cause was not retained. |
| Direct, same model and request/output limits, ordinary JSON | All three responses reached the limit. No admissible code. | All three responses reached the limit. No admissible code. |
| Direct, same model and limits, explicit JSON schema for portable Python | Two complete candidates refused valid disclosed examples. The third response reached the limit. No candidate passed disclosed examples. | All three responses reached the limit. No admissible code. |

The product preserved the full ambitions and source digests through approved companion pairing and local submission in both languages. The SQL was real construction and execution. Its input mismatch withheld it from held replay. No arm produced a mechanism eligible for held testing, so the study established no held-domain success or product advantage. Observable workload and completion states are local measurements. Complete costs and productive value remain unmeasured.

| Receipt | SHA-256 |
| --- | --- |
| Product, 584-token run | `ab675da2591372e90645f4e16826f3ffe819fdc661278401c6855c771891a4ec` |
| Product, 1,280-token run | `6e81d0de54d3a5204fb4d24f285175d933ccd486f93d12b8d744bbfa6d13f5f4` |
| Independent SQL scope check | `912445a215a6258c167b4772ac929b2a6d4efcf861ba50a84ffecb947abf00ab` |
| Direct ordinary JSON | `726e6ab698c7a3b1114081a2e411e84f37fe74a3078898aa8bc4d339f5c43776` |
| Direct explicit schema | `bdd72620b755e0c70de0bba8d3cac8c814b42cb811116711c4511676456f63e9` |
