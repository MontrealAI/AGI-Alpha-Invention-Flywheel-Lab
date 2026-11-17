# TD01 optional model arm

Before inference, fix one pass per independently presented registered crop, using the official accessible NVIDIA parser with its documented parsing task prompt, a limit of 2,048 generated tokens per crop and no target-specific tuning. Preserve both raw outputs, actual model revision, dependency/runtime versions, generation settings, load/inference timing and incomplete attempts. A successful model load alone contributes no accepted matrix. The grader requires the same full matrix as the other arms. If the model returns markup, identify the deterministic table extraction and repeated-header handling separately.

## Recorded CPU observation

The lab ran the pinned public weights locally on the two registered PNGs. After loading one model, it generated one output per crop with no continuation or second model attempt. The model saw the page crops; the per-cell rectangles used by Tesseract were withheld from it. Its raw outputs are preserved in [the observation](evidence/nemotron/observation.json). The printed table contains text. The presence of a recent, usable parser is established for these images; machine transcription on this table also succeeds with established tools.

The deterministic receiver interprets one plain-text LaTeX tabular environment per output, removes the explicit header wrapper, checks the repeated header, joins page fragments and compares all cells with the registered author source. It treats unsupported markup or source drift as an unresolved delivery. Adapter implementation followed inspection of the model's output format; it has no cell-specific text substitutions. The [accepted receipt](evidence/nemotron/receipt.json) contains the same CSV digest as the other three routes.

Reproduce the scored recipient from the product directory without a model environment:

```sh
python3 -B table_desk/parser_matrix.py --observation table_desk/evidence/nemotron \
  --author ../../docs/research/cycle-001.html --output /tmp/td01-received-new
```

To repeat actual inference, install the public project's Python dependencies into a fresh CPU environment. The observed environment used Python 3.12, torch 2.13.0+cpu, torchvision 0.28.0+cpu, transformers 5.19.0, timm 1.0.22, accelerate 1.12.0, einops 0.8.1, safetensors 0.8.0, NumPy 2.2.6 and Pillow 12.3.0. The [upstream project manifest](https://huggingface.co/nvidia/Nemotron-3.5-Parse/blob/ea2e1fe486bea3e7d0d505df9bafa4ad562407a0/pyproject.toml) records supported dependency ranges. Use the public Hugging Face CLI in that environment to receive the pinned provider files. The model weights occupy 2,523,266,640 bytes. The runner verifies every supplied weight, processor, configuration and local provider module in its manifest before loading. The public exhibition and normal tests can be used independently of this download.

```sh
hf download nvidia/Nemotron-3.5-Parse --revision ea2e1fe486bea3e7d0d505df9bafa4ad562407a0 \
  --include 'model.safetensors' 'hf_*.py' '*.json' 'chat_template.jinja' --local-dir /tmp/td01-model
python3 -B table_desk/observe_parser.py --model /tmp/td01-model \
  --crops table_desk/evidence --output /tmp/td01-new-observation
python3 -B table_desk/parser_matrix.py --observation /tmp/td01-new-observation \
  --author ../../docs/research/cycle-001.html --output /tmp/td01-received-again
```

The CPU run measured 39.1139 seconds wall time, 111.714 process CPU seconds and 3,079,996 KiB peak resident memory. Per-page processing took 20.2282 and 10.6643 seconds. The clock includes in-process dependency imports, weight verification and model loading. Package installation, downloading, source preparation, development, review, delivery, support and monetary costs were outside that clock. Hardware and dependency changes may change timings and output.
