# Capability scope qualification

An operator-bound 12-hour NOAA request stops before retrieval. A compatible, operator-bound Endpoint batch runs the published executable and retains its screening disposition. [Machine-readable receipt](SEMANTIC-RECEIPT.json)

## Recorded outcomes

| Requirement or control | Observed result |
| --- | --- |
| NOAA forecast from November 29, 2024 at 00:00 UTC to 12:00 UTC | INCOMPATIBLE. The required and proposed instants are compared independently. The archived f024 contract requires an elapsed 24 hours. |
| NOAA forecast at the correct temporal horizon with longitude −73.60° | INCOMPATIBLE. Native coordinates lie on the exact quarter-degree grid. |
| NOAA forecast at the correct horizon and native point | COMPATIBLE for declared scope. New archive retrieval remains outside this executor. The downloaded archive's offline checker authenticated six registered ecCodes comparisons. |
| Published seven-row Endpoint Evidence Screen batch | Highest qualifying tested load 140. All row dispositions matched the independent exact SQLite execution. |
| Tightened P90 ceiling, raised throughput floor, and withheld-P90 controls | Loads 35, 70, and ABSTAIN, respectively. All rows matched SQLite. Operating adoption remained ABSTAIN in every run. |

NCEP documents pgrb2 as one of several GFS products, with distinct forecast-hour filenames and a native 0.25° grid. The released point evaluator has the narrower f024 contract recorded here. [NCEP product inventory](https://www.nco.ncep.noaa.gov/pmb/products/gfs/) · [Release documentation](../../../products/frontier-member-tools/ARCHIVE.md)

## Operating boundary

The dispatcher uses the mission's separately supplied structured requirements and resolves capabilities from its own catalogue. It returns COMPATIBLE, INCOMPATIBLE, ADAPTATION_REQUIRED, MISSING_INPUT, UNDETERMINED, or UNAUTHORIZED. A model's proposed identifier and input do not supply the missing authority or evidence. An ambition whose exact material facts have not been bound can continue through a different supported route or request the actual missing facts.

For NOAA the engine checks UTC instants, exact elapsed hours, supported UTC cycles, exact coordinates, source identity, data kind, quantity, units, grid, and package version. COMPATIBLE confirms scope against those facts. New archive bytes, packing, and an independently accepted value need their own checks in the native query path. The runtime has no NOAA network dispatch.

For Endpoint the model can reference an operator-bound evidence batch with `{"use":"verified_batch"}`. The operator's version, scope, measurement semantics, cutoff, limits, and batch fingerprint remain authoritative. The runtime checks the complete finite batch before dispatch and runs the unchanged published screening implementation in a private local process. The process receives the batch on standard input and hashes its output. The binding does not independently authenticate an operator's empirical measurements or qualify an extrapolation.

Typed composition checks compare registry-owned input and output ports, operation order, and declared dimensions, units, time basis, and provenance. The tested NOAA temperature to Endpoint batch composition was incompatible. This evidence covers the pre-dispatch boundary. A compatible multi-tool composition still needs verified input binding and acceptance of the final result.

## Reproduce

Run from `products/alpha-genesis-harness` with Python and an installed Node runtime compatible with Endpoint Evidence Screen 1.0.0.

```sh
python -m unittest discover -s tests -p test_mission_contracts.py -v
```

Extract the immutable Endpoint release and check its manifest before use. Pass its sample to the repository integration and the package's independent baseline. The tested input had SHA-256 `59a55127ec07ae801a85f834afbfbb6b1f01bdaecdcb9159f1cd434741afcbae`. [Endpoint release archive](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/endpoint-evidence-screen-1.0.0.zip)

```python
from pathlib import Path
import json

from bridge.mission_contracts import endpoint_requirements, invoke

batch = json.loads(Path("/path/to/extracted/endpoint/sample.json").read_bytes())
receipt = invoke("endpoint-screen", endpoint_requirements(batch), {"use": "verified_batch"})
assert receipt["executed"]
assert receipt["output"]["highest_tested_load"] == 140
assert receipt["output"]["operating_adoption"] == "ABSTAIN"
```

Use the extracted package's `endpoint-sqlite.py sample.json` to compare the complete returned object. The deliberate controls in the receipt set maximum P90 to 100 ms, minimum throughput to 300 tokens/s/user, or set every P90 measurement to null. The measured elapsed values cover the dispatch or baseline process, including startup. They supply no complete cost or performance advantage claim.

Pour le contrôle de Montréal, la demande de 12 heures et la longitude hors grille sont refusées avant l’exécution. Le filtre Endpoint exécute le lot autorisé et conserve l’abstention quant à l’adoption opérationnelle. Le rejeu SQLite confirme les résultats des quatre contrôles.
