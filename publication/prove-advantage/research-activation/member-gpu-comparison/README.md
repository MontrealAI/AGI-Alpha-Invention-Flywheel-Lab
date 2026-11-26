# MY FRONTIER Ω: dual-TITAN local-model handoff experiment

**Qualified for two bounded historical computations. Not a frontier discovery or a ChatGPT Pro comparison.**

On November 26, 2026, one offline GPT-OSS-20B worker ran on each TITAN RTX. Both arms received the same Bank of Canada source observations for the first window. Direct inference attempted both windows. The FRONTIER arm selected the existing `successive-changes` operation with one declarative plan and reused it on the unseen-to-that-arm window, changing only the file, hash, URL and date range. The installed verifier at [PR #617](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/617) ran the computations. No generated code was executed.

| Window | Largest USD/CAD move | Largest EUR/CAD move |
| --- | --- | --- |
| 2025-05-16 to 2025-05-27 | May 22–23: −0.0114 | May 16–20: +0.0083 |
| 2025-12-19 to 2025-12-31 | Dec 22–23: −0.0043 | Dec 23–24: −0.0033 |

The initial candidate returned an object for dates where an array was required. The verifier rejected it. The initial second-window success inadvertently also corrected the date shape; it is not evidence of retention. The follow-up gave a structural date-array example and made the series labels explicit in the direct arm. It kept both inputs, model settings, scoring and verifier unchanged. The amended run is a diagnostic replay, not a new independent confirmation.

The amended FRONTIER arm matched the precomputed Python Decimal reference on both windows. The direct arm did not satisfy the maximum-only output contract on either window, but its reported changes could be filtered to the same correct results with ordinary deterministic postprocessing. The strong conventional calculation also matched both. Therefore this does **not** establish arithmetic superiority over competent conventional methods. The defensible advantage in these two cases is producing an exact, hash-bound result via an existing reusable operation, with one model call rather than two and a refusal on a wrong source hash.

The final run placed 10,949.38 MiB of model buffers on each worker's GPU. The FRONTIER arm used 866 total observed model tokens, direct used 3,209 total across the two calls. These are inference counts, not full workflow costs; neither complete wall-clock advantage nor revenue was measured. No paid provider requests occurred. The separate 120B hardware test and the real-member comparison are not part of this result.

## Replay

Fetch both exact HTTPS source URLs in [result.json](result.json), checking their SHA-256 digests before use, and save as `fx-2025-05-16.json` and `fx-2025-12-19.json`. Use `frontier-native-work.mjs` from repository commit `e17f270122d917d077c84a35adade375914289f5` beside these scripts. Its tested SHA-256 is in the receipt. With Node, an extracted `model_plan` from the evidence can be verified locally using `node verify.mjs PLAN.json SOURCE.json`, without a model. The complete test uses Python 3.11+, Node, a CUDA-enabled llama.cpp build and a verified GPT-OSS-20B MXFP4 GGUF. In a fresh test directory, set `FRONTIER_WEIGHTS` and `FRONTIER_LLAMA_SERVER` to absolute local paths, then run `python3 -B run.py`. The model workers bind only to loopback. A rerun may produce different model text; the recorded plans and arithmetic are replayable.

## Résumé

Sur deux fenêtres historiques, FRONTIER Ω a obtenu les résultats exacts avec une seule invocation locale du modèle et a réutilisé l’opération sans nouvelle inférence. Le premier essai avait échoué à cause de la structure des dates. Un calcul classique et un filtrage déterministe des réponses directes ont aussi retrouvé les résultats. L’expérience démontre une vérification et une réutilisation circonscrites, pas une nouvelle capacité scientifique ni une supériorité sur ChatGPT Pro.
