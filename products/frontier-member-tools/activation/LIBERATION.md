# FRONTIER Ω · Activation 1.3

Use one offline workbench for the three existing exact tools, the public transit-timing investigation, the compact construction comparison, and the river-discharge cross-check.

```sh
python3 discovery_workbench.py list
python3 discovery_workbench.py covariance
python3 discovery_workbench.py timing-audit
python3 discovery_workbench.py hydrology
python3 discovery_workbench.py construction
python3 verify_liberation.py
```

The archived results carry the dates, units, withheld-target denominators and decision scope. A historical forecast comparison grants no observing authority. The hydrology calculation applies to complete published daily means with the stated interval and unit. It grants no water-management authority.

## Replay from original observations

Download the three exact files linked in `study/liberation/SOURCES.json`. Earlier ExoClock files are OSF revision 1. The full replay checks the bytes, separates the known public releases, and recomputes every fit, split and coverage result. The shorter offline verification checks the same results from the compact retained evidence.

```sh
python3 verify_liberation.py --elements /path/to/catalogue_of_ephemerides.txt \
  --older /path/to/all_mid_time_data.txt --later /path/to/by_planet.zip
```

Add `--independent /path/to/table4.csv --independent-elements /path/to/table3.csv` to rerun the cross-reduction timing audit using the pinned Ivshina and Winn tables. The reported matches use two reductions of the same historical TESS events.

The original exact tools are also available from `discovery_workbench.py ephemeris`, `endpoint` and `calibration`. See [SUBSTRATE.md](SUBSTRATE.md) for their independent replay and for the existing isolated native Python procedure. Compact expressions use a bounded arithmetic interpreter with no native candidate execution.

## Reviewed handoff and local model

```sh
python3 liberation.py packet --arm direct --development study/substrate/DEVELOPMENT.json --output review.json
python3 liberation.py import --packet review.json --response returned.json --output candidate.json
python3 liberation.py evaluate --candidate candidate.json --confirmation study/liberation/CONFIRMATION.json
```

The reviewed response has a matching `packet_sha256`, an actual `author`, and `programs` containing the four named expressions. Use a new independent confirmation for a new scientific claim. The examples and held sets here reproduce the published investigation.

The exact reported local CPU model config is in `study/liberation/config.json`. If authorized, set up the owner-host CUDA route in [SUBSTRATE.md](SUBSTRATE.md). For this compact study, use the exact Qwen3-4B Instruct 2507 Q4_K_M weight from the recorded comparison and serve it on loopback port 18661 with 8,192 context and the registered runtime settings. If another approved model is selected, pin its actual digest, context, reported speed and provider config in a new comparison.

```sh
lease=$(python3 -c 'import time; print(int(time.time())+3600)')
for arm in direct harness typed; do
  python3 liberation.py construct --development study/substrate/DEVELOPMENT.json \
    --arm "$arm" --workspace "liberation-study/$arm" --config study/liberation/config.json \
    --model qwen3-4b-instruct-2507-q4_k_m --tokens 600 --until "$lease" > "result-$arm.json"
  python3 liberation.py evaluate --candidate "result-$arm.json" --confirmation study/liberation/CONFIRMATION.json
done
```

Choose a budget appropriate to a different task. An interrupted dispatch preserves its pending reservation and settles to abstention when reopened under this one-dispatch protocol. The original construction and the separately registered `--feedback` correction have independent workspaces and retain all outcomes. No direct frontier provider authentication is conferred by these instructions.

## Atelier en français

La commande `python3 discovery_workbench.py list` présente les environnements disponibles. `covariance` reproduit la décision scientifique à partir des résultats archivés. `hydrology` vérifie le volume dérivé des moyennes journalières publiées. `verify_liberation.py` vérifie également les décisions d’abstention et les témoins. Les trois fichiers originaux d’ExoClock permettent de refaire l’étude entière. Les données de vérification et les réservations de temps pour les observations ont des portées distinctes.
