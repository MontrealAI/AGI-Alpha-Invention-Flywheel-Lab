# A contract that individual loads cannot fulfill alone

This bounded computational kernel constructs and independently checks a pooled demand-flexibility plan. Four synthetic loads each have only 40 kWh of event flexibility; a frozen contract requires 100 kWh after a declared 5% derating. The solver preserves every device's required energy, per-slot power and availability, and compensates each participating load for its declared displacement cost plus a positive margin. Low budgets and insufficient later capacity can cause refusal.

The inputs are synthetic hourly profiles, not observed devices. A checked planning artifact is not measured energy delivery, grid qualification, a customer or a payment. Aggregation and mixed-integer optimization are established mechanisms. The ordinary comparator receives the same information and can build the same solver; all four registered profiles tie on participant compensation. The fresh two-event successor is feasible under both controls, so retained-capability advantage remains unestablished.

Install the repository's optional engineering dependencies, then execute from a clean checkout:

```sh
python -m pip install --only-binary=:all: -r requirements-engineering061.txt
python -m unittest tests.test_flexibility063 -v
python -m flexibility063.experiment --output /absolute/new/technical-output
```

`REGISTRATION.json` fixes the finite probes, profiles, controls and claim boundaries. `profiles.json` contains three single-event contracts and one fresh two-event successor. The technical report includes exact input/source identities, accepted outputs, refusal results, runtimes, participant payments and all ordinary controls. The two other candidate probes test only inverse identifiability and a simple manufacturing interface prerequisite; they are not physical demonstrations or full commercial evaluations.

`kernel.solve(request, mode='pooled')` uses established SciPy/HiGHS mixed-integer optimization. `mode='individual'` tests every single load; `mode='conventional'` explicitly permits ordinary reconstruction of the same mathematical model. Solver arithmetic is floating point; the separate verifier recomputes all delivered energy and payments with Python integers and rejects infeasible outputs. Sparse constraints avoid dense device-by-slot memory growth. Explicit finite profile and numerical bounds protect this adapter; they are not enterprise growth ceilings.

`verify.verify(request, artifact)` checks the complete device partition, energy conservation, capacities, availability, no event rebound, derated aggregate target, exact participant compensation and budget. It imports no producer. Procedural independence on the same host is not external certification.

`service.prepare_manifest` binds the frozen profile bytes, checker, executing sources and future output path before native production. Only independently accepted late-bound artifact hashes can prepare funded native orders. Every prepared output is rebound during replay, including later-refunded orders. The native seam reuses the canonical `JournalAccount` and adaptive `Account`; it creates no parallel financial ledger. The commercial report states whether the transaction purchases a computational plan or models subsequent physical participation costs.

Actual model/host billing, physical response, regulation, market demand and a genuinely new economic frontier remain unmeasured. The research edition and native conditional commercial report retain these distinctions.
