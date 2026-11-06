# CONTINUITY Ω — Read the recorded result in English or French

**English** · [Français](OUTPUTS.fr.md) · [Quick start](QUICKSTART.md) · [Prototype guide](README.md)

The reading companion presents the prototype’s recorded handoff, audit and refusal artifacts in your chosen language. It preserves the raw identifiers, status codes, quantities, amounts and file fingerprints. **A readable report is not a fresh audit, a certification or proof that a customer promise was fulfilled.**

The original prototype remains unchanged. Its terminal messages and original `PASSPORT.md` use English; the companion supplies a complete English or French reading of the supported JSON outputs, with localized explanations, help and errors. The paper’s bilingual edition **1.1.1** remains a separate publication.

## Read a nominal exercise

Python **3.10+** is sufficient. Run from the repository root; no installation, API key, network connection or external action is needed.

```bash
python3 -m continuity_omega demo --case nominal --out /tmp/continuity-reading-demo-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language en
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language fr
```

The first command creates a new synthetic exercise. The next two read the same saved records and print Markdown to the terminal. To create a shareable reading, choose a **new absolute file outside the evidence directory**, whose parent already exists:

```bash
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language en --out /tmp/CONTINUITY_READING_EN_001.md
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-demo-001 --language fr --out /tmp/CONTINUITY_READING_FR_001.md
```

Use fresh names when repeating these commands. The reader refuses existing output files, symbolic-link outputs, relative output paths and outputs inside the evidence directory. It never overwrites `PASSPORT.md`, modifies an audit or changes an acceptance decision.

```bash
python3 scripts/continuity_passport.py --help
python3 scripts/continuity_passport.py --language fr --help
```

Help is bilingual by default. Select `--language en` or `--language fr` for localized help, validation errors and report text. The language is required when rendering a report.

## Read a refusal too

A refusal is useful evidence of what the constructor declined to propose. Run the following commands separately: the first deliberately returns **exit code 2** and creates a `REJECTION.json` record.

```bash
python3 -m continuity_omega demo --case overbooked --out /tmp/continuity-reading-refused-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-refused-001 --language en
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-reading-refused-001 --language fr
```

For this case, the French reading explains that no simulated supplier satisfies capacity and deadline. The reader returns **0** because it successfully presented a supported refusal record. It has not turned the refusal into a pass or rerun the constructor.

## Understand the decisions

| Recorded token or command result | Meaning |
| --- | --- |
| `READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT` | The producer’s saved readiness marker. It is not an acceptance or a result from a fresh audit. |
| `PASS_SYNTHETIC_ONLY` | A saved decision from the synthetic checker. The report does not establish that the decision still matches the files, that the source is authentic or that the business recovered. |
| `FAIL` | A saved audit failure. The report preserves the recorded failure count and explains each listed code. The historical count can exceed the number of distinct codes because counting precedes deduplication. |
| `REJECTED_BEFORE_HANDOFF` | The constructor recorded a refusal before a proposed handoff. Actual costs and consequences for customers were not measured. |
| Reader exit `0` | The supported record was rendered, including a recorded refusal or failed audit. |
| Reader exit `2` | The reader refused an unsupported or malformed record, unsafe output path or invalid command. No partial report is created for unsupported input. |

The checker is independently implemented **as separate code under shared research authorship**. This is not external independent certification. All supplied exercise scenarios are synthetic. These records confer no permission to contact customers, reserve capacity, execute recovery or move money.

## What the report covers

| Source file | Complete human reading |
| --- | --- |
| `HANDOFF.json` | Outstanding orders, product and order identifiers, units, source-event numbers, specification digests, simulated supplier, failure domain, declared capacity and modeled deadlines. |
| `PASSPORT.json` | Producer readiness, restoration discrepancies, modeled offer/full cost/contribution/budget, conventional comparator, six real-world evidence declarations and the proposed successor. |
| `AUDIT.json` | Saved verdict, recorded replay totals, recorded failure count, distinct diagnostic codes, restoration gaps and all six required real-world gates. |
| `REJECTION.json` | The saved refusal, its supported reason and its synthetic scope. This file is read instead of the three records above. |

Each reading also retains raw schema and scope references, recorded source/handoff/idempotency digests where present, and SHA-256 fingerprints of the exact files read. Technical tokens remain unchanged; surrounding explanations are localized. The fingerprints identify bytes, **not the truth, origin or completeness of those bytes**.

The companion does not read `INPUT.json` or the original `PASSPORT.md`. It neither replays events nor recalculates capacity, costs, recorded source/handoff/idempotency digests or economic advantage. A changed handoff beside an old `PASS_SYNTHETIC_ONLY` can therefore be presented: handoff quantities and saved audit quantities appear separately, with an explicit warning that no fresh audit occurred. A coherently rewritten dossier can also be presented without gaining any authenticity claim. A real-world declaration set to `true` remains an **unverified recorded declaration**.

The historical checker’s known weaknesses involving Boolean monetary values, malformed input and stale inspection remain documented in the [evidence guide](../continuity-omega-paper/EVIDENCE.md). This companion does not repair or qualify the checker, and does not integrate the separately owned hardening work.

## Unsupported input is refused explicitly

The reader supports the published v1 schema and its finite English/French narrative vocabulary. Missing or extra required fields, unfamiliar schemas or messages, unknown diagnostic codes, mixed refusal/handoff records, duplicate JSON members, non-finite numbers, Boolean amounts, malformed identifiers or symbolic-link evidence files cause an explicit presentation refusal. JSON integers longer than **4096 digits** are outside this reader’s supported format. New fields or narrative require an explicit reviewed translation; the reader does not silently discard them.

These checks establish that the companion can present the supported record completely. They do not establish domain correctness, source authenticity or a fresh audit result. Original evidence stays intact when presentation is refused.

## Request a new check separately

```bash
python3 -m continuity_omega verify --in-dir /tmp/continuity-reading-demo-001
```

This separate command runs the checked-out prototype’s checker and prints its new result. It **does not replace the saved `AUDIT.json`**. A subsequent reading still describes the saved audit. Keep the new command’s output separately if you need a record of that check, and retain the checker limitations described above.

## Run the focused checks

```bash
python3 -m unittest discover -s tests -p 'test_continuity_passport.py' -v
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
```

The first suite covers bilingual reading, numeric/token preservation, file immutability, malformed/unknown inputs, localized errors, output safety and the recorded-versus-current distinction. The second is the unchanged prototype’s authored implementation suite. Their results are software checks, not evidence of real recovery, delivered orders, collected payment or external certification.

Continue with the [prototype guide](README.md), [proposed real pilot](REAL_PILOT.md), or [bilingual research paper](../continuity-omega-paper/README.md).
