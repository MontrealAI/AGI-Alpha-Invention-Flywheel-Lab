# A2A198 — a source-bound, local-only agent interoperability experiment

**Status:** opt-in draft research. Original product and live-market rights remain with the PR484 owner. Not a new commercial product, deployed service, paid agent, open public endpoint, or Blue Sky flagship.

**Question:** Can a separate A2A v1 JSON-RPC client discover and call the existing independent, offline `gate.run` through the official protocol, without weakening source validation, copying its verifier, or activating any financial/credential path? The strong direct Python/HTTP incumbent is expected to tie on output quality; a standard adapter is not a defensible invention by itself.

## Frozen source and execution

Preregistered **before code** in [PREREGISTRATION.md](PREREGISTRATION.md), commit `ee23e891a9a8a98a37a405050ad8e38c96f7e855`, against released main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. The only producer/checker is the unchanged PR484 `gate.py` from commit `b333a5f4ac9495b9c8259170597239a1792bf1ac`, Git blob `115cf8531df65a66dcc679e2d35cb03394cea11a`. The runner computes and enforces the original Git blob identity before importing. CI checks both exact Git refs and performs real loopback GET/POST against the unchanged original module. No private customer or model data are required.

Operator reproduction after checking out the **exact** PR484 source into `source-pr484/`:

```sh
export A2A198_GATE="$PWD/source-pr484/products/frontier_machine_asset_001/gate.py"
python3 -m unittest discover -v -s campaign/a2a-interop198 -p test_a2a.py
python3 campaign/a2a-interop198/a2a_adapter.py --gate "$A2A198_GATE" --port 8795
```

On the same machine, `GET http://127.0.0.1:8795/.well-known/agent-card.json` retrieves the self-describing card. `POST http://127.0.0.1:8795/a2a` accepts a standard JSON-RPC 2.0 `SendMessage` with a fresh `ROLE_USER` message containing one `data` Part matching the PR484 contract. The accepted response is a `ROLE_AGENT` structured-data message with original output and original local receipt. Unsupported old versions, tasks, multi-part, streaming, invalid contracts, oversized bodies and payment endpoints are rejected.

CI compares direct original `gate.run(request)` with the A2A response on the **same input**, without weakening the incumbent. Dedicated test IDs A1–A12 are fixed in the preregistration. A first failure remains failed; later corrections must have their own source and new run receipts. `python -m py_compile` and a development smoke with a **fake gate** are not qualification on the real asset.

## What this does **not** prove

- No new productive transformation: the incumbent gate does copy/strip/upper/lower with a free verifier. Protocol convenience is engineering interoperability, **not** a newly attainable economically valuable outcome.
- No external A2A client certification: the local server and its own test client are under one operator. No independent third-party SDK interoperability matrix.
- No security or identity assurance: this is unauthenticated loopback, not HTTPS, a signed agent card, public provenance or any authority to receive external messages.
- No payment, external customer, buyer willingness, revenue, native reinvestment, complete host/model/engineering bill, profit or recursive invention. No mainnet RPCs or tokens invoked.
- No release admission: source-matched tests can qualify this **supporting experiment** only; it cannot replace protected financial P0 migration or enable production.

Strong alternatives: direct conventional Python/HTTP; existing A2A SDK/framework; external managed distribution (not authorized); and no entry. Research the actual valuable task, independently willing machine agent buyer, complete cost and specialist competitive controls before treating an interface as a sellable machine asset. `NO SALES / NO BID / NO DEPLOY` remains the product default.

Primary protocol: https://a2a-protocol.org/v1.0.0/specification/ . Public developer-interest signal, **not** demand: https://www.cognizant.com/us/en/ai-lab/blog/open-agentic-web-challenge .
