# Transactional data successor

The software produces an actual SQLite event database and a derived group-total database/CSV under declared interruption and retry conditions. Data engineering teams can inspect the persisted outputs and recovery behavior. This is a purely computational construction using established SQLite transactions and uniqueness constraints, not a physical laboratory controller.

Eight cases were registered before this implementation atc58b4cc3a8abf65b3945d09d98a2e10c88cf9791: normal, committed reply loss, process death during a transaction, reordered duplicates, conflicting duplicate, malformed event, interrupted projection/restart and a100,000-event gateway. The faulting workers exit without graceful connection cleanup. Separate acceptance code compares persisted rows and projections to a Python reference calculation, checks SQLite integrity and checks the delivered CSV. Mutated totals must be rejected. SQLite's independently developed transaction engine supplies the actual persistence behavior; the fixture specification and both Python implementations remain developer-authored on the same host.

```sh
python -m enterprise078.transactional_data.run --output /absolute/new/result
```

The command retains all eight cases, returns nonzero if any fails, records source/dependency identities, CPU/wall/bytes and publishes the largest actual database and CSV through the dedicated workflow artifact. This measures process-crash recovery under the tested OS/SQLite configuration, not power-loss durability on arbitrary storage or safe physical actuation.

Strong ordinary SQL is the implementation; no discovery advantage is claimed. K1 produces exact persistent unique events. K2 uses that durable asset to build a different derived view and CSV, preserving the previous view if interrupted before commit. These are actual software outputs, but no funded successor or new commercial revenue is claimed: the original native authority is currently unavailable. Do not substitute a fresh balance for that account.

Construction and model/host billing remain unknown, not zero. Customer budgets, outside options, voluntary demand, acquisition cost, support capacity and new native catalog admission still need an explicit costed offer and accountable operating test. Large software markets and user counts do not establish this product's demand. US$3billion trailing365-day native profit remains unachieved.

Source basis and alternatives:
- [SQLite atomic commit and storage assumptions](https://www.sqlite.org/atomiccommit.html)
- [SQLite transaction behavior](https://www.sqlite.org/lang_transaction.html)
- [NIST autonomous-laboratory integration constraints](https://www.nist.gov/programs-projects/development-standards-support-modular-and-autonomous-laboratory-ecosystem)
- [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative)
- [Census2023 software-publisher establishments](https://data.census.gov/profile/511210_-_Software_publishers?g=010XX00US&n=511210)

These sources establish mechanisms and context, not buyer validation. Conventional SQL, database migration/ETL products, internal engineering and no purchase remain the outside options. The next investment is justified only if the accepted complete output and full costs beat a credible option for a reachable buyer.
