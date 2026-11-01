# Real operational concrete dispatch

The retained producer creates plant-loading, truck and delivery schedules from263 public anonymized Quebec operating days. The independent replay checks delivery quantities, release times, truck/plant occupancy, return travel, timing and declared operational assumptions. Ordinary methods and adverse economics remain visible; useful production does not imply algorithmic superiority or buyers.

The bundled `data/` JSON is portable, time-only normalized data under [CC BY4.0](https://creativecommons.org/licenses/by/4.0/), credited to Alexandros Tzanetos and Maude Blondin, [Mendeley Data v1,10.17632/b78bc94d95.1](https://data.mendeley.com/datasets/b78bc94d95/1). No latent calendar components or addresses are included. Source defects, missing mixes, unresolved loading-rate units and two incomplete travel days are preserved. See `data/README.md` and `PUBLIC_PROVENANCE.json`. Original binary tables and third-party web snapshots are not distributed here.

```sh
python -m pip install --only-binary=:all: -r requirements-engineering061.txt
python -m unittest discover -s tests -p 'test_production060*.py' -v
python -m production060.evaluation_run --help
python -m production060.business --help
```

`evaluation.json` retains the acceptance rules, information split, native cost assumptions and input hashes. `evidence/ordinary/summary.json` is a compact historical result, not a new-source qualification or a collection of buyers. Per-day execution dumps are deliberately omitted. The enterprise native adapter retains actual funding, independent acceptance, collection and financial guards. Eight plants belong to one source operator, not eight customers; simulated acquisition and pricing remain conditional.
