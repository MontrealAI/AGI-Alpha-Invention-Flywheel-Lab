# My Frontier Ω · Foundry qualification

**One local model constructed an executable byte-window instrument, matched 14/14 checks, and reproduced the length of a fresh 32-byte NOAA response. Conventional Python remains the incumbent. Neither tested successor constructed a runnable instrument.**

The strongest relevant acquisition alternatives remain NOAA Archive Point and NCAR's existing point service, which uses less transferred data when applicable. The work here is a technical qualification of a portable, verified member workflow, with beneficiary acceptance and complete-cost advantage outstanding.

## Registered evidence

| Arm | Observed result |
| --- | --- |
| Qwen2.5-0.5B, direct tree output | Neither the original response nor its syntax-only repair sealed. Wall time 20.71 s and 14.52 s. |
| Qwen2.5-0.5B, direct inference on the original cases | It returned a fenced list of 13 original input pairs and no computed outputs, for 0/14 requested outputs even if the fence is removed. Wall time 12.21 s. |
| Python integer reference | 14/14 exact matches, including real recorded ranges and two boundary cases. The complete Python workflow remains the comparator. The measured arithmetic kernel was about 10 µs on this host. |
| Qwen2.5-0.5B, compact formulas | 0/14. It returned `bytes = start` and `ordered = True`. Model wall time 0.81 s. |
| Qwen3-4B, compact formulas | 14/14. Three invalid-input controls refused. Model wall time 3.69 s, 80 input tokens and 15 output tokens. Four CPU threads. Runtime start to health about 4.04 s. CLI comparison 0.114 s. |
| Fresh reuse | HTTP 206 from NOAA with exact `Content-Range: bytes 0-31/534403916`. The frozen instrument returned `32` and `ordered: true`. Acquisition 4.66 s and offline CLI execution with recheck 0.120 s. |
| S₂, ordinary reuse vs retained S₁ | Both returned the same unsupported `len(body)` expression, with `body` declared an integer. Neither reached the 26-case acceptance suite. S₂ and causal transfer were unproven. No promotion. |

The earlier standalone archive receipt was separately produced but reused an identical input range. The fresh acquisition for the pinned Qwen3 arm used a different NOAA archive date. The experiment keeps both observations distinct.

The comparison separates measurement, acceptance and authority. The public archive records, RFC 9110 and integer arithmetic give independent technical references. The experiment did not use an evaluator-controlled hidden corpus, a separately administered host, or a consenting member. The recorded process timings use a shared host and exclude complete labor, review, energy, maintenance, failure and hosting costs. The local route spent no API fees. A chargeable provider account was not used. No monetary benefit, recursive improvement or productive superiority has been established.

## Local companion release check

A live streaming Qwen3 request returned two valid assignments separated by a semicolon. The initial importer required one assignment per line and correctly stopped without making an executable file. I changed the importer to inspect Python's syntax tree and accept named scalar assignments with either separator. It rejects execution statements and uses the existing HARNESS formula compiler to emit only data. Independent review identified an expansion risk. The updated importer counts expanded nodes before serializing. The corrected packaged path discovered the model, previewed the request, streamed a reply, compiled and checked **6/6**, and exported a reusable capability. The model call took **5.22 s** with **146** input and **15** output tokens. The [operation receipt](companion-operation.json) preserves both the failure and the resulting artifact identity.

## Versions and reproduction

- [Initial registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/ada2b9f9a12997d8968df53cc316ce81f730fc3b/publication/frontier-foundry/REGISTRATION.md) and [exact failure receipt](archive-trial.json).
- [Formula registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/60f3e42f09e4cd28752a779968dd736c12dd8958/publication/frontier-foundry/FORMULA-REGISTRATION.md) and [exact failure receipt](formula-trial.json).
- [Reference model registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/353f4842483425c27389a652d0d1388d5683462c/publication/frontier-foundry/REFERENCE-MODEL-REGISTRATION.md) and [complete reference model receipt](reference-model-trial.json).
- Retained capability fingerprint `ab26310e2bd51d624733db78717195d7d8e3b7b73af836b859e1d8a372748f15`. The qualification receipt records the outputs, independent case reference, model hash, raw answers, candidate, timing, and reuse acquisition. The archive case receipt was independently signed and is checked by the existing NOAA package verifier.
- [Offline commands and exact scope](../../products/frontier-member-tools/foundry/README.md). The deployed `atlas-release.json` identifies the authorized distribution bytes. Use the original companion's packaged suite when reopening a capability, including when no model is available.

For model replay, download the [llama.cpp b12242 Linux x64 archive](https://github.com/ggml-org/llama.cpp/releases/tag/b12242), SHA-256 `909eef25cd53e6601c8a07c866d8dbb2983e74177088d55182137a8fb8255d62`. Retrieve either the [0.5B official GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/9217f5db79a29953eb74d5343926648285ec7e67) or the [pinned Qwen3 4B quantization](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/tree/ae44f08e1392f39c0e474af10c3ff8355c8b6688). Verify the weights against their registrations. The files are transient dependencies and are excluded from the release. Set the runtime library directory according to the platform and run locally:

```sh
llama-server -m /path/to/model.gguf --host 127.0.0.1 --port 18479 \
  --alias qwen3-4b-instruct-2507-q4_k_m --threads 4 --ctx-size 4096 \
  --parallel 1 --n-gpu-layers 0 --no-webui
```

Keep the test server within a trusted local environment and stop it after the trial. The quoted command is for a contained qualification host. Review the runtime's access controls for ordinary multiuser work. With an extracted companion and the source checkout, run from the repository root:

```sh
python3 publication/frontier-foundry/run_formula_trial.py /path/to/extracted /tmp/qwen3-replay.json --reference-model
```

For the two 0.5B replays, start the server with the matching weights and alias `qwen2.5-0.5b-q4_k_m`. Run `run_formula_trial.py` without `--reference-model` or use `run_archive_trial.py` for the original nested expressions. Model determinism and elapsed time are conditional on the pinned runtime, sampler, model and host. The historical cases are model-withheld and public. Fresh hidden evaluator evidence remains separate.

## Français

**Un instrument créé avec Qwen3-4B en local a réussi les 14 contrôles et vérifié une nouvelle réponse NOAA de 32 octets. Python demeure la référence. Les deux démarches de succession ont produit la même expression non prise en charge.**

Les fichiers ci-dessus conservent les réponses initiales de Qwen2.5-0.5B, les deux rejets de structure et l’échec de la méthode à formules sur les 14 cas. Le modèle de référence Qwen3 a obtenu **14/14**. Les trois entrées invalides ont été refusées. L’inférence a duré **3,69 s**, la vérification locale **0,114 s**. La nouvelle acquisition a duré **4,66 s**, et sa vérification avec l’instrument conservé **0,120 s**. Les deux méthodes S₂ ont proposé `len(body)` pour un champ entier. Les cas S₂ sont conservés dans le protocole et aucun instrument S₂ n’a franchi le contrôle de construction.

Dans la rubrique **Mon intelligence**, lancez le rejeu ou figez une mission. Ouvrez un instrument HARNESS et des cas issus d’une méthode de référence, puis exécutez et exportez le résultat. Suivez les mêmes commandes hors ligne pour réutiliser l’instrument exact, sans charger le modèle. La référence signée, le protocole public, les réponses du modèle et les empreintes sont conservés. Les fichiers éditoriaux servis par Pages sont publics. L’accès à l’interface demeure réservé aux comptes admissibles. Les dossiers #550 et #565 demeurent applicables.

Les relevés établissent une qualification technique et un réemploi sur une nouvelle entrée publique. Ils ne démontrent ni avantage économique ni amélioration récursive. L’évaluation humaine, l’acceptation d’une mission membre réelle et la mesure des coûts complets restent à établir.
