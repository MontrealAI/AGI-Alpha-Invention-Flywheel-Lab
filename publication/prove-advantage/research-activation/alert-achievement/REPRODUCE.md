# Reproduce the scoped CPU comparison

Use a dedicated Linux x64 work directory with enough free storage for the 3.56 GB source and two 1.12 GB variants. The local wrapper uses Bubblewrap and the system `libseccomp.so.2`. Operate on the named public artifacts and review the runtime and scope before execution. The wrapper is provided for this exact CPU trial.

1. Copy `run_isolated.py`, `release_operator_fr.txt` and `host_qualification_en.txt` from this directory to the trial work directory.
2. Retrieve and validate the [Ubuntu x64 archive](https://github.com/ggml-org/llama.cpp/releases/download/b12774/llama-b12774-bin-ubuntu-x64.tar.gz) and [pinned FP16 weights](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-fp16.gguf) against the exact digests in the [receipt](RUNTIME-RECEIPT.json). Name the weights `qwen.fp16.gguf` and extract the archive under `runtime/` with a safe archive extractor.
3. From the trial work directory, use the following command, passing the path to this Git repository to reconstruct the calibration input. The two evaluation prompts are the files copied in step 1.

```sh
python3 - /path/to/AGI-Alpha-Invention-Flywheel-Lab <<'PY'
from pathlib import Path
import subprocess
import sys

revision = '8bb8d60b43c1f3bbffc26ee1ae9ed2a810fe0a44'
paths = (
    'products/alpha-genesis-harness/README.md',
    'docs/harness/DEVELOPER_GUIDE.md',
    'products/alpha-genesis-harness/docs/OMEGA-GENESIS-NEXT.md',
)
text = '\n\n'.join(subprocess.check_output(['git', '-C', sys.argv[1], 'show',
                                          f'{revision}:{p}']).decode('utf-8') for p in paths)
Path('calibration.txt').write_text(text[:48000], encoding='utf-8')
PY

python3 run_isolated.py probe
python3 run_isolated.py llama-imatrix -m /work/qwen.fp16.gguf -f /work/calibration.txt \
  -o /work/results/calibration.gguf --output-format gguf --no-ppl --chunks 8 -c 256 -b 256 -t 8 -ngl 0
python3 run_isolated.py llama-quantize --imatrix /work/results/calibration.gguf \
  /work/qwen.fp16.gguf /work/results/conventional.gguf Q4_K_M 8
frontier_ceiling=$(stat -c '%s' results/conventional.gguf)
frontier_target_bytes=$(( frontier_ceiling * 995 / 1000 ))
python3 run_isolated.py llama-quantize --imatrix /work/results/calibration.gguf \
  --target-size "${frontier_target_bytes}b" --state-file /work/results/target.state \
  /work/qwen.fp16.gguf /work/results/automatic.gguf F16 8
test "$(stat -c '%s' results/automatic.gguf)" -le "$frontier_ceiling"
```

Run each combination of `conventional.gguf` and `automatic.gguf` with `release_operator_fr.txt` and `host_qualification_en.txt`. Repeat for the FP16 reference at `/work/qwen.fp16.gguf`. Give a separate reviewer anonymous outputs and the [registered work requirements](RUNTIME-RECEIPT.json).

```sh
python3 run_isolated.py llama-completion -m /work/results/conventional.gguf \
  --no-conversation --no-display-prompt --simple-io -f /work/release_operator_fr.txt \
  -n 512 -c 4096 -t 8 -ngl 0 --temp 0 --seed 42
```

The original calibration was executed before the inner-process measurement wrapper was added. Its elapsed measurement is retained. Reruns can record CPU time and peak RSS for that stage with this wrapper. Startup and saturation timing can vary by machine. The checksum, file-ceiling and acceptance questions govern the scoped decision. [Results](REPORT.md)
