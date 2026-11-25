# Productive evidence and causal transfer

Two MONTREAL.AI release decisions were verified from actual operating data. The #594 product release had already completed its live verification job. Its build and deploy waited 12 min 9 s and 9 min 38 s respectively before their first recorded steps. At the later capture, the #595 revision was publicly served by a successful scheduled run. The earliest successful push of that same revision could not establish which run was currently serving it. [Frozen observation and results](RESULT.json)

## Opportunity selection

| Candidate | Actual benefit and strongest feasible route | Decision |
| --- | --- | --- |
| Decide release readiness and identify observable delays | Release operators need the exact public source and the occupied stage before choosing to wait, investigate or use a release. Ordinary Actions records and the independently retrieved Pages receipt supply those facts. | Selected. Two distinct real releases were available and the decision can recur without deploying another service. |
| Activate the stronger local model on the owner’s GPU host | Higher inference capacity could materially improve mission completion. An actual owner-host run and observed model performance are required. | Retain the stronger-model procedure. The present environment cannot establish owner-host execution. |
| Use radar observations to guide an actual site action | Verified NISAR metadata already supports acquisition planning. A site action would require approved imagery, a consequential decision and an accepted outcome. | Preserve the existing result. The authorized evidence supports metadata planning. |

The operator value is a repeatable determination of whether an exact release can be cited as live, how it was verified, and which observable stage consumed the wait. The incumbent is a direct deterministic check of the same GitHub Jobs and public Pages facts. Releasing or rerunning anything was outside this read-only work. [Initial registration](REGISTRATION.json) · [Earlier opportunity assessment](../../evidence-bound/productive/REPORT.md)

## Actual use and repeat use

| Public release and exact run | Disposition | Build, deploy and verification wait | Submission to verified job completion | Local median retained / conventional process |
| --- | --- | --- | --- | --- |
| #594, 45547873631 | GO for the historical publication witness | 729, 578, 95 s | 1,525 s | 48.876 / 37.292 ms |
| #595, 45551096060 | HOLD for current service. The live receipt named a later run. | 97, 48, 19 s | 274 s for the historical run | 35.865 / 39.994 ms |
| #595, 45614033463 | GO for the subsequent scheduled publication observed at capture | 4, 6, 3 s | 132 s | 41.728 / 33.823 ms |

Each decision checked the exact workflow, event, main branch, commit, run attempt, three job results and separately acquired publication identity. Each waiting interval measures the job record’s creation-to-first-started-step duration. These intervals measure an observable wait. The cause and allocation of the underlying platform delay are unknown. The scheduled observation followed a separate registration and preserves the original strict failure to bind the push to the current receipt. [#594 actual run](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45547873631) · [#595 earliest push](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45551096060) · [#595 scheduled run](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45614033463) · [Follow-up registration](FOLLOWUP-REGISTRATION.json)

The retained implementation and a separate ordinary Python implementation agreed across all three cases and seven controls. Wrong commit, missing job, failed verification, development-only origin, stale receipt and duplicate identity each produced HOLD. With missing timing, exact publication verification stayed valid and the bottleneck remained unset. Both arms used the same observed input and completed nine alternated fresh processes per case. The ordinary comparator is the recommended operating default for this stand-alone decision. Neither arm met the registered material speed gate. [Jobs API](https://docs.github.com/en/rest/actions/workflow-jobs) · [Frozen comparisons](RESULT.json)

The observed acquisition used 11 public requests and 172,803 response-body bytes across both studies. Shared acquisition for the publication cases took 12.660, 13.496, and 10.242 seconds. The runtime archive source decision took another 5.206 seconds. This includes network observation and, for the archive, local reading and inspection. The registration-to-assessment window was about 299 seconds and includes construction, acquisition and verification. Any pre-registration discovery time, actual inference resource cost for included Codex authoring, human attention, recurring maintenance, electricity, network charges and avoided operating expenditure remain unmeasured. The timed tools issued zero model calls and completed no transactions. Realized revenue and cash returns remain unestablished. A break-even estimate requires an observed per-use saving and actual use frequency. [Cost scope and medians](RESULT.json)

## Successor decision

The fresh decision checked the official publisher identity of an existing 23,158,635-byte Linux CPU archive. The initial release work retained a scoped decision gate, explicit source binding and a first failed prerequisite. The successor applied those requirements to the upstream package and used two local hash implementations on the already approved file. The publisher asset identity `729746370`, upload state and SHA-256 matched, and archive inspection found one regular `llama-b12242/llama-server` member. The publisher marks b12242 as a prerelease. The result qualifies the observed file’s identity and declared package origin. Runtime safety, GPU fit, scientific inference and production promotion retain their own gates. [Official publisher metadata](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12242) · [Release assets API](https://docs.github.com/en/rest/releases/assets) · [Observation](OBSERVATIONS.json)

| Successor arm | Observed outcome | Local median |
| --- | --- | --- |
| Original Pages interpreter | HOLD because the upstream record is outside its registered input | 36.875 ms |
| Publisher binding withdrawn | HOLD for absent scoped publisher authority | 37.757 ms |
| Retained mechanism | GO for matching official and locally measured bytes | 39.864 ms |
| Conventional integration | Same complete GO and provenance facts | 30.247 ms |
| Ordinary equal-content `jq` reuse | Matching pass decision | 5.184 ms |

Both complete positive routes refused four negative controls covering publisher digest alteration, incorrect tag, same-size digest disagreement and missing local bytes. The compact `jq` route agreed on all decisions. This isolates the operational effect of the publisher-binding requirement within an authored program. One included-Codex author prepared the comparable mechanisms and one authorized environment held the inputs. An independently controlled authoring intervention and a separately measured direct strong-inventor arm remain outstanding. **NO-GO** for inferred inventor improvement, a further generation, or recursive compounding. First useful transfer is the normal reuse of a documented source constraint, which ordinary tools also achieve. [Original registration and causal gate](REGISTRATION.json) · [Transfer results](RESULT.json)

## Retention and reuse

| Asset | Admission and reuse conditions |
| --- | --- |
| Ordinary Pages decision | GO for read-only operator use on exact GitHub Jobs, public Pages receipt and trusted expected commit/run/event. Python 3.11+ with standard library. Revalidate each case and preserve prior receipts before a live deployment supersedes them. Withhold absent evidence. |
| Exact archive identity check | GO for operator use on previously approved files and an explicit official release record. Python and `sha256sum` or the standard system equivalent. Repeat both the publisher check and actual byte digest on a changed release. Keep prerelease status visible. |
| Retained generic check gate | Experimental reusable proof of correct scope and denial behavior. No change to standing services or capability admission. The existing registry requires its own authorization and testable acceptance for promotion. Archive source identities can be quarantined by changing the permitted input reference and withdrawing the qualification when the source, dependency or digest changes. |

Run from this directory. The first command replays the frozen published observations. The second acquires new public evidence for the registered targets and requires an existing b12242 archive. The third re-reads the separately registered scheduled run. An updated live receipt can cause the later commands to produce different outcomes. [Source and replay identities](RESULT.json)

```sh
run=$(mktemp -d)
python3 -B assess.py "$run/replayed.json"
python3 -B capture.py start /path/to/approved/llama-b12242.tar.gz "$run/observations.json"
python3 -B capture.py followup "$run/followup.json"
jq '.pages[1]' "$run/observations.json" > "$run/current-research.json"
python3 -B ordinary.py pages "$run/current-research.json"
```

## Français

Deux versions réelles ont été vérifiées à partir de leurs exécutions GitHub Actions et d’un reçu de publication indépendant. La version #594 a été vérifiée dans son périmètre historique. Pour #595, le reçu public a confirmé la version exacte, mais a désigné une exécution planifiée plus récente que la première exécution de publication. Les deux méthodes ont correctement suspendu la décision initiale. L’examen supplémentaire a ensuite confirmé l’exécution réellement servie. Les temps mesurés décrivent l’intervalle avant la première étape consignée. La cause de l’attente demeure inconnue. [Résultats](RESULT.json)

Le contrôle suivant a vérifié l’identité d’une archive locale de llama.cpp à partir de la taille et de l’empreinte publiées. L’archive officielle de 23 158 635 octets est marquée comme préversion. Le contrôle conventionnel a fourni le même résultat à moindre coût mesuré. Aucun rendement financier ni avantage récursif n’a été établi. [Observations](OBSERVATIONS.json) · [Vérification conventionnelle](ordinary.py)
