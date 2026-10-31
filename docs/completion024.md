# Composed native lifecycle qualification

The qualified released champion is connected014-85fba7c94cac5f741d047807a0c83e8ce11f4216 (the same historical operating closure) until the composed source completes all normal gates. Every collection below is simulated. The historical operator022 paper and economic evidence remain bound to their original source.

Use Python 3.12 and `python -m pip install --only-binary=:all: -r requirements-commercial010.txt`. Existing run, registration, comparison and scoreboard commands are documented in [the operator manual](connected014/OPERATOR.md) and [the capital manual](completion023/OPERATOR.md).

For an **owned local experimental business** with an existing signed STATE, nonempty queue and retained private key, choose the target source and immutable policy explicitly:

```sh
python -m connected_enterprise upgrade --output /absolute/business --historical-source /absolute/current-owned-source --manifest /absolute/SERVICES.json --policy /absolute/POLICY.json --expected-checkpoint CHECKPOINT_CANONICAL_SHA256 --id owner-forward-2 --transition-format v2-cas
python -m connected_enterprise operate --output /absolute/business --max-events 2
python -m connected_enterprise resume --output /absolute/business
python -m connected_enterprise audit --output /absolute/business
python -m connected_enterprise scoreboard --output /absolute/business
python scripts/export_recovered023.py --business /absolute/business --output /absolute/new-public-export --offline-historical-sources
```

`CHECKPOINT_CANONICAL_SHA256` is `commercial.ledger.digest` of the parsed signed STATE envelope, not the file's whitespace-dependent byte hash. V1 remains the default and retains its original 16 MB guard. V2 is explicit. Its wire HMAC binds content addresses; canonical prior records, original signed journal and operating state are preserved in the caller-selected business's `TRANSITION_EVIDENCE`. The current owner signs inside the pinned historical process. Parent code never receives its key. A signed preparation is retained before publishing OPERATOR; migration consumes that exact ticket. Up to four forward transitions retain their original signatures and source inventories. Owner signing checks a shared publication budget for the target, unique historical verifiers, exact evidence objects and checkpoint records; its admission receipt is retained. Export stores each verifier version once. Temporary compatibility views give older verifiers their original lookup layout using links to private temporary copies, preserving original source files. Downgrade, branch, stale checkpoint and changed preparation are rejected.

If atomic object publication is interrupted, retry uses complete content-addressed objects. Partial private stages are never canonical objects. To preserve abandoned stage bytes and obtain an owner-authenticated recovery receipt:

```sh
python -m connected_enterprise recover-transition-evidence --output /absolute/business --historical-source /absolute/current-owned-source --manifest /absolute/SERVICES.json --expected-checkpoint CHECKPOINT_CANONICAL_SHA256 --id preserved-stage-1
```

This command retains orphan bytes, signs metadata with existing owner authority, and changes neither financial history nor liabilities. Corrupt published objects and unknown/symlink files fail closed; they are not silently overwritten. Keep the recovery receipt and private originals. Public export includes only exact reachable key-free objects and verifier closures and enforces the shared 10,000-file/512-MiB limits.

Neither a public package nor the older successor022 private backup authorizes rewinding the original business. Its later completion023 account/tape, signed STATE/journal/recovery sidecars, unchanged private key, complete source maps and manifest remain unavailable to this receiving environment. New experimental accounts and engineering tests do not replace that missing continuation state.

Qualification is a frozen-source engineering reproduction, not new buyer evidence, measured frontier billing, annual profit or external commerce. The current binding must be generated from the actual accepted clean qualification receipt, after source changes stop; it cannot promote the historical paper to new-source economic confirmation.

Each registered historical runtime is checked against its own stored file map, including resources that a newer selector no longer includes. Its unchanged bytes remain part of the authenticated source-transition history; the new selector cannot retroactively redefine them. Native financial advance checks cash and profit immediately around each individual maturity operation. This assertion supplements canonical replay and does not prohibit legitimate claim costs or collected recoveries at the same clock.

PR 38's separate strategic-commerce experiment is not included in this candidate. Its opt-in policy and packaging changes need their own composition and qualification after the safe native lifecycle release; its synthetic or public experiment receipts do not qualify this source.

Run the finite installed-source native continuation proof with one command (a new private experimental output, no original-account replacement):

```sh
python scripts/operate_completion024.py --output /absolute/new-native-proof
```

It materializes the exact pinned legacy verifier, reaches the preregistered nonempty production/acceptance/settlement queue with an existing permanent tail, upgrades that same account using owner-held CAS authority, completes the 504-hour planning horizon and bounded settlement drain, resumes, audits, scores and exports it. The released-byte verifier runs this command from the actual downloaded source. Raw private state stays local; its public ZIP and failure transport exclude the key and database. This is exposed-world engineering reproduction; the unavailable latest original account remains a separate continuity dependency.
