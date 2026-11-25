# Qualify the owner GPU workstation

Run from the release checkout on the approved Ubuntu workstation. Have an approved CUDA-enabled `llama-server` and the complete GPT-OSS-20B MXFP4 GGUF available locally. The launcher uses the exact publisher digest and byte length registered in the model preflight. [Registered checkpoints](../../evidence-bound/productive/REGISTRATION.json)

```sh
python3 -B publication/outcome-driven/intelligence/qualify_owner_gpu.py \
  --weights /absolute/path/gpt-oss-20b-MXFP4.gguf --output ./frontier-gpu-qualification
```

Use `--llama-server /absolute/path/llama-server` if the binary is outside your PATH. Both NVIDIA devices are selected by default. For the approved Qwen alternative, add `--checkpoint qwen3-30b-a3b-q4_k_m` and provide that registered GGUF. Start with GPT-OSS if the approved build supports it. [Model preflight](../../evidence-bound/productive/REPORT.md)

The launcher starts one offline listener on `127.0.0.1:38461` and stops it when finished. It runs the two bilingual calculation missions and the missing-evidence mission against the same local model in both the evidence-bound executor and the ordinary tool-assisted comparison. The receipt records the verdict, request count, token usage and elapsed time of each arm. The launcher samples GPU board memory and, where reported, board energy. It also records runtime-reported CUDA placement, context and token throughput. The whole-run wall budget starts at model-server launch and is 30 minutes. [Registered mission and comparison criteria](../../evidence-bound/evaluation/fresh/README.md)

Review and share `frontier-gpu-qualification/RECEIPT.json`. The private output directory also contains model transcripts and runtime logs for local troubleshooting. The result is an engineering reproduction of published cases. Any later claim about unseen tasks or training and adaptation needs its own registered evaluation.

## Poste Ubuntu du propriétaire

Exécutez la commande ci-dessus à partir de la version publiée, sur le poste Ubuntu approuvé. Utilisez un exécutable CUDA `llama-server` approuvé et le fichier complet GPT-OSS-20B MXFP4 déjà présent sur le poste. Le lanceur vérifie le fichier, mesure le placement CUDA, la mémoire, le débit et l’énergie des cartes lorsqu’elle est disponible, puis exécute les cas bilingues enregistrés avec les deux méthodes. Transmettez seulement `frontier-gpu-qualification/RECEIPT.json` après l’avoir examiné. Les transcriptions et les journaux restent sur le poste.
