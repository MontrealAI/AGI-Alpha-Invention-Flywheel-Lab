# Exact package readiness for MONTREAL.AI release operators

A read-only operator mission checked whether actual published executor packages can be reused when the installation file name alone is ambiguous. It authenticated archived bytes for two approved executor releases and correctly held an actual same-name staging archive. A separate Productive Intelligence Factory package verified using the unchanged declarative decision. The comparison used the earlier public Pages observation from workflow `45637319050`. It describes those exact bytes, which may differ from a subsequent published package. [Registration](REGISTRATION.json) · [Publisher receipt](../../outcome-driven/verification/LIVE-RELEASE.json) · [Results](RESULT.json)

| Actual package | Disposition | Outer SHA-256 prefix | Source commit prefix | Manifest files and Git-pinned sources |
| --- | --- | --- | --- | ---: |
| Published executor 1.1.0 | Verified | `58e1aac31e1c` | `297a51c25c48` | 47 and 11 |
| Published executor 1.2.0 | Verified | `dd37e23f2629` | `9a53a4b8bb7e` | 50 and 11 |
| Same-name staged executor 1.2.0 | Hold | `46e78f225c2f` | `5955c08d36d3` | 50 and source mismatch |
| Published Factory 1.5.0 | Verified | `5a29bc8d2158` | `436bb1b142a0` | 164 and 4 |

The returned decision requires agreement between the outer archive digest, the full manifest and independent Git source bytes. SHA-256 was measured through Python and `sha256sum`. The eleven bound executor files include both-language start instructions, all three launchers, the execution and checked interpreter modules and the user model-connection documentation. The four checks in the Factory case bind the evidence snapshot, registration, verifier and truth mechanism. The direct incumbent used the repository's existing temporary installation check. That comparator read and extracted approved bytes for measurement and ran no archive code. [Audit and incumbent path](audit.py) · [Deterministic HARNESS projection](readiness.sql)

The HARNESS instrument, ordinary Python given the same evidence, and the existing exact ZIP inspection agreed on **7/7** frozen decisions. Missing files and withdrawn publisher pins stayed unresolved. For the two actual executor packages, the incumbent's median full check ran in about 8.75 ms per case. HARNESS's isolated projection ran in about 32–44 ms on the same inputs before the additional observation pass. For the Factory package the measured times were about 16 ms and 32 ms respectively. The same-content Python decision finished in roughly 5 μs after evidence acquisition. Hosted authoring cost, human attention, amortization and ongoing maintenance were unobserved. [Measured scope](RESULT.json)

**GO** for exact historical package preflight on these data. The established ordinary route remains appropriate for this decision. **NO-GO** for a first complete economic advantage, causal improvement of a subsequent inventor or a second improvement generation. The transfer shows repeated use of the explicit publisher-binding requirement. When it was withdrawn, the tools withheld the Factory archive. Ordinary comparable integration was equally correct. [Transfer registration](TRANSFER-REGISTRATION.json)

## Reproduce

Supply locally saved public archives or build exact historical source packages matching the full observed digests in `RESULT.json`. Keep the known staging ZIP separate from the approved 1.2 ZIP. A currently served download may have a different identity. Use a full Git checkout containing the source commits for independent byte checks and Python 3.11 or later with SQLite 3.37 or later and `sha256sum`. The audit runs locally with zero network requests. It can use HARNESS from a verified extracted package through `--harness`.

```sh
run=$(mktemp -d)
python -B audit.py --released-11 "$approved_11" --released-12 "$approved_12" \
  --staged-12 "$staged_12" --factory-15 "$approved_factory" --output "$run/audit.json"
```

## Français

Le contrôle a confirmé les archives publiques exactes des exécuteurs 1.1.0 et 1.2.0, puis a écarté une archive de préproduction qui portait le même nom que l'archive 1.2.0 approuvée. La même règle a confirmé l'archive du Productive Intelligence Factory 1.5.0. Les trois méthodes concordent sur les sept cas. Le contrôle conventionnel a aussi exigé les empreintes attendues et a été plus rapide dans cette mesure locale. Aucun avantage économique ni progrès causal de l'inventeur n'a été établi. [Résultats](RESULT.json)
