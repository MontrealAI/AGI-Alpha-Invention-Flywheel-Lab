# FRONTIER Ω · Intelligence Substrate workbench

Activation 1.2. The public workbench runs with Python 3.11 or later and needs neither a network connection nor a model for the exact scientific tools.

```sh
python3 science_workbench.py list
python3 science_workbench.py ephemeris
python3 science_workbench.py endpoint
python3 science_workbench.py calibration
python3 verify_substrate.py
```

Pass a path after an environment name to check a case in the same format. Example records and source bindings are in `study/substrate` and `study/amplification`. Reproduce the full case construction and two-method census with the archived source bytes, if available.

```sh
python3 verify_substrate.py --paper /path/to/table8.txt --archive /path/to/planets.json
PYTHONPATH="$PWD" python3 study/substrate/assemble.py \
  --registration study/substrate/REGISTRATION.json --paper /path/to/table8.txt \
  --archive /path/to/planets.json --output ./new-study
```

The publication table is the machine-readable Table 8 of Kokori et al. (2026), [ApJS, 283, 5](https://doi.org/10.3847/1538-4365/ae3238), CC BY 4.0. The [machine-readable table](https://content.cld.iop.org/journals/0067-0049/283/1/5/revision1/apjsae3238t8_mrt.txt) and [ExoClock endpoint](https://www.exoclock.space/database/planets_json) must match the digests in the registration. The live database can change. Use the frozen short case set when the original snapshot is unavailable or register the updated snapshot as a new study.

The transit tool gives the range of model standard deviation consistent with the reported marginal errors and an unspecified correlation. The result assumes a linear ephemeris and BJD TDB for both the fitted center and the anchor. It does not assess changing periods, validate a timing provenance claim, or give a probability-calibrated observing window. Operational adoption also remains in abstention for the Endpoint sample.

## Evaluator and reviewed handoff

For native candidate execution use x86-64 Linux with the x86-64 system Python, `unshare`, `bubblewrap`, `libseccomp.so.2` and working unprivileged user/network namespaces. The worker fails closed if these conditions do not hold. The exact workbench and non-native verification work separately on any supported Python host.

```sh
python3 verify_substrate.py --native
python3 substrate_study.py packet --development study/substrate/DEVELOPMENT.json \
  --arm direct --output mission.json
```

Review the exported prompt and give it to the approved account through the operator's normal ChatGPT interface. Include the printed packet binding in the returned JSON object’s `packet_sha256` field and record the actual source and author. Keep confirmation outside the account and constructor directories.

```sh
python3 substrate_study.py import --packet mission.json --response response.json --output candidate.json
python3 substrate_study.py evaluate --candidate candidate.json \
  --confirmation study/substrate/CONFIRMATION.json --arm direct
```

The bundled worked response used the included Codex session with operator-assisted transport. The packet proves binding and replay of the response artifact. Provider identity and independent custody require their own evidence.

## Owner-controlled Ubuntu host with two TITAN RTX cards

Use an existing CUDA-enabled llama.cpp binary and the exact GGUF you are authorized to run. The examples assume the registered 8B GGUF and `llama-server` on the owner’s PATH. Confirm the device inventory, free memory, exact build and weight hash before launch. The release does not attest to the host's availability, driver, actual GPU placement, sustained speed or model capability.

```sh
nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.free --format=csv
llama-server --version
weight=/absolute/path/to/qwen3-8b-q4_k_m.gguf
printf 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785  %s\n' "$weight" | sha256sum -c -
```

Start with one GPU and the same 8192 context as the registered attempt. Check the server's actual placement and prefill/generation rate. If a larger approved model needs both cards, repeat the build's memory diagnostic and start a separately named checkpoint with both visible devices, the model's actual hash/name/limits, and a measured placement plan. A larger context or different weight is a separate comparison. Run no other listener on this port.

```sh
CUDA_VISIBLE_DEVICES=0 llama-server --model "$weight" --host 127.0.0.1 --port 18646 \
  --ctx-size 8192 --parallel 1 --n-gpu-layers 99 --no-ui --reasoning off --jinja
```

In a second terminal in this archive:

```sh
curl --noproxy '*' --fail --silent http://127.0.0.1:18646/health
python3 verify_substrate.py --native
lease=$(python3 -c 'import time; print(int(time.time())+7200)')
for arm in direct harness typed; do
  python3 substrate_study.py construct --development study/substrate/DEVELOPMENT.json \
    --workspace "local-study/$arm" --config study/substrate/LOCAL-CONFIG.json \
    --model qwen3-8b-q4-k-m --until "$lease" --arm "$arm" > "candidate-$arm.json"
  python3 substrate_study.py evaluate --candidate "candidate-$arm.json" \
    --confirmation study/substrate/CONFIRMATION.json --arm "$arm"
done
```

Choose a fresh execution directory for another independent attempt. For interrupted dispatches, reopening the same directory restores the immutable inputs and charges the outstanding reservation. These commands apply the same input and output contract on Linux. The example config is local-only and has a zero paid-request budget. It does not start a listener, grant authority, train a model, authorize a service or retain a wallet or evaluation key.

## Rejouer les calculs

L’atelier fonctionne hors ligne, sans modèle, pour les trois calculs de référence. Lancez `python3 science_workbench.py list` pour choisir un environnement, puis `python3 verify_substrate.py` pour contrôler les fichiers, les témoins et les décisions. Le calcul des transits tient compte de toute corrélation admissible entre l’erreur de la période et celle du temps de référence. Une autorisation d’observation exige une vérification distincte. La validation d’un candidat Python dans le bac à sable exige Linux x86-64. Les commandes pour l’hôte Ubuntu ne constituent pas une mesure des deux cartes TITAN RTX.
