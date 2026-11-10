# Agentic workflows / Parcours agentiques

The connected workspace can now ask configured models to propose concrete tool actions, execute the allowed actions locally, observe results, independently recompute operator-frozen cases, ask a separate critic to examine the result, and repair a failed construction. A single model may fill separate roles; a different configured model can fill each role. Actual provider/model assignments, requests, costs when reported, tool results and failures are recorded.

This is a bounded construction workflow. The implemented tools write plain-text documents, CSV datasets and declarative instruments, read only the run's own artifacts, and execute the instrument grammar. There is no arbitrary shell, Python source, generated HTML, payment, outreach or external-system tool. Model text cannot edit acceptance conditions or grant itself permissions. An instrument has a portable fixed Python evaluator in its download; it can run outside the HARNESS.

Public-source retrieval is a separate optional `retrieve_source` permission, disabled by default. When explicitly enabled outside local-only mode, agents can request exact HTTPS URLs on the connector's configured host allowlist. The existing public-address checks, pinned TLS connection, size/type restrictions and no-redirect policy apply. Retrieved text is stored as untrusted evidence with URL, retrieval timestamp and byte digest. Retrieval time does not establish publication date, freshness of the underlying claim, or truth. Neither a workflow nor a model can override the connector's local-only setting.

## Start a connected run

Start the connector and open its browser workspace. Select builder and critic models from your configured connections. Supply an objective, context and acceptance checks, then start the workflow. Leave **Local only** enabled for loopback inference. A ChatGPT, Codex or remote API connection requires disabling that restriction deliberately; its own connection consent and quota/budget guards remain necessary.

The example `examples/agentic-local-workflow.json` has executable synthetic acceptance cases. Replace only the provider/model placeholders with actual configured local IDs. You can choose a single builder, builder plus critic, or add researcher and economist roles. Researcher and economist calls use the supplied information; they do not establish that current external research was retrieved. A researcher precedes construction; economic analysis follows successful technical checks. Economic feasibility remains a separate question.

Each role uses the existing runtime, including the official subscription and Codex routes where authorized. Unsupported model capabilities and malformed replies fail explicitly. No fallback provider is selected silently.

## Use the CLI

From the extracted product folder, with a private config outside the release:

```sh
python3 -m bridge.workflows create --config /private/config.json --spec examples/agentic-local-workflow.json --workspace /private/my-workspaces
python3 -m bridge.workflows run --config /private/config.json --run-id PRINTED_RUN_ID --workspace /private/my-workspaces
python3 -m bridge.workflows inspect --run-id PRINTED_RUN_ID --workspace /private/my-workspaces
python3 -m bridge.workflows export --run-id PRINTED_RUN_ID --workspace /private/my-workspaces --output my-project.json
```

`step` makes one model call and its bounded actions. `run` continues to a stopping condition. `resume` explicitly continues a paused or interrupted run. A cancelled, exhausted or finished run does not dispatch again; create a successor with new declared limits if appropriate. An interrupted upstream request may have consumed allowance even when no response was saved. Resume records that uncertainty and may issue a new request; it is not automatic cost-free replay. Process-session API guards reset when the connector closes, while provider bills do not reset.

One connector/CLI process owns a workspace at a time. Close its server before using that workspace from another process, or use a separate private directory. Checkpoints have atomic replacement, a private integrity key, artifact digests and a chained event history. This detects changed local records while the key remains trusted; it is not public certification or protection against a fully compromised local account. Avoid shared untrusted folders.

## Acceptance and export

Instrument checks compare actual output with the operator's frozen input/expected-output cases. They are implemented independently from the proposing model. The operator's tests may still be incomplete or wrong: independent human/scientific test preparation is not inferred. Document checks only test specified text and length; they do not certify factual correctness. Model agreement never overrides a failing executable check.

The export contains your objective, context, run history and artifacts. Inspect it before sharing. It excludes provider credentials, OAuth tokens and the private workspace integrity key. The JSON export includes an integrity digest; an untrusted sender can recompute their own digest, so imported verification is always historical and is not accepted as current authority. Imports get a new identity and need new execution/rechecking. Corrupt artifacts, symlinks, traversal paths and active-file imports are refused.

A completed verified instrument becomes a capability record containing its source run, role assignments, version hash, evidence, costs when available and applicability limits. A successor can set `inherited_capability` to that run ID. Its own acceptance cases are independently rerun; previous verification never transfers automatically. `reuse` executes the instrument on new data but does not assert that the new problem's meaning or real-world outcome is accepted.

## Offline construction demonstration

```sh
python3 -m bridge.workflows demo --workspace /private/new-demo --output demo-evidence.json
```

This uses **authored fixture responses**, not a live model. It builds a faulty affine calibration instrument, records failing checks, receives a critic's correction, constructs the repaired instrument and passes the frozen cases. It reopens the saved work, reuses the instrument on a different production-estimation problem, and compares a fresh-construction control and equal-content ordinary reuse. The ordinary arithmetic route ties. Four fixture calls were needed for initial construction versus two for fresh correct construction; inherited reuse adds no calls, but neither does ordinary reuse. Complete economic costs remain unknown. **No successor advantage or general compounding claim is established.**

## Français

Le parcours connecté enchaîne proposition, actions autorisées, observation, vérification des cas fixés par l'utilisateur, critique distincte et correction. Les outils créent des documents texte, des CSV et des instruments déclaratifs exécutables. Ils n'exécutent aucun code arbitraire et n'autorisent ni paiement ni communication externe.

Choisissez les modèles, définissez l'objectif et les critères avant de lancer le parcours. Le mode local interdit les connexions distantes. Une validation positive concerne uniquement les cas indiqués; l'accord d'un modèle ne remplace jamais un test indépendant. Les archives contiennent votre contexte privé et doivent être examinées avant partage. Les identifiants de connexion en sont exclus. La réutilisation sur un nouveau problème exige de nouveaux critères et une nouvelle vérification.

## Executable strategy policies

The connected executor supports seven policies. These select actual call/action order; they do not claim that a larger topology is better.

| `strategy` | Required roles | Executed behavior |
| --- | --- | --- |
| `single-model` | builder | Construct, run frozen checks, repair within limits. |
| `actor-critic` | builder, critic | Add a separate critique invocation after each construction. |
| `researcher-builder-verifier` | researcher, builder, critic | Analyze supplied information first, then construct and critique. |
| `strategist-economist` | builder, economist | Add economic analysis after technical acceptance; it cannot authorize transactions. |
| `parallel-exploration` | builder | Dispatch distinct operator-registered approach branches with isolated artifacts and independent checks. |
| `adaptive` | builder | Try a direct primary approach first, then activate registered alternatives only after recorded failed work exhausts its allocation. |
| `adversarial-review` | builder, adversary | Ask a separate invocation for counterexample inputs and execute/adjudicate them against an operator reference or existing frozen case. |

Optional critic, adversary, researcher and economist roles execute when explicitly configured. Separate invocations may use the same model; that is not independent training or external scientific validation. Routes never change silently.

For parallel exploration, add `approaches`, an array of two to four distinct brief strings. `max_iterations` and `max_actions` are **shared across the parent and all children**, partitioned before any model dispatch. Each child has its own immutable artifact directory. A branch cannot read its siblings' artifacts or be dispatched independently through the HTTP API. The model-call ceiling includes every registered researcher, critic, adversary and economist allocation. The existing runtime additionally guards concurrent API monetary reservations; completed, failed, cancelled and unresolved attempts remain in the parent's request-cost evidence. Complete economic costs usually remain unknown.

For example, extend an existing valid spec with:

```json
{
  "strategy": "parallel-exploration",
  "approaches": ["Use a direct affine equation.", "Use explicit products and a separately checked offset."],
  "max_iterations": 4,
  "max_actions": 8
}
```

A parent step runs one model phase in each eligible branch concurrently, subject to runtime concurrency limits. All launched sibling work settles before selection. Among branches completing the same frozen acceptance and required reviews, selection uses fewest tool actions, then model calls, then registered branch order. This is deterministic selection, not a claim of economic optimality. Failed alternatives and actual routes remain in the portable parent export. Parent pause/cancel applies to all children; resume preserves their identities and consumed allowances. Crash recovery reuses parent-reserved child identities and does not create a second budget allocation.

`adaptive` uses the same `approaches` plus optional `adaptive_after_failures` (default `1`), which allocates that many construction attempts to the initial direct approach. At least one iteration/action must remain for each alternative. A successful primary finishes without alternatives. A failed primary can activate alternatives only when its history contains a refused response/tool or failed executable verification. A transport error pauses for explicit operator recovery. Acceptance, model routes and permissions stay frozen; the switch event links its supporting failed evidence.

For adversarial review, the adversary returns:

```json
{"counterexamples":[{"artifact":"calculator.json","input":{"x":-1},"expected":{"result":-2},"reason":"Probe negative input"}],"feedback":"Check boundary behavior."}
```

`expected` is only a model claim. Optional `adversarial_oracles` maps artifact filenames to operator-supplied bounded reference instruments. Each reference must agree with every original frozen case for that artifact before dispatch. New counterexamples execute against both the candidate and that frozen reference; adjudicated cases persist through repair. Without a reference, only an already-frozen input has an authoritative expected output. Other claims stop at `needs_review`, never becoming model-authored acceptance. Reference correctness outside its supplied cases remains an explicit assumption. An empty adversary proposal list demonstrates no discovered counterexample, not universal correctness.

Parent JSON exports contain every branch's complete historical events, outcomes, role routes and artifact digests. Imports validate every child contract against the exact parent plan before writing any imported file. They use fresh local identities and are paused/unverified; historical local child IDs cannot point at unrelated local capabilities. Import starts a new declared allocation, while resuming the same run preserves its spent allowance. Archives remain bounded to 16 MiB and may include private losing-branch content as well as the winner.

## Paired retrieval comparison

```sh
python3 -m bridge.strategy_demo --workspace /private/new-paired-demo --output paired-evidence.json
```

This deterministic qualification uses authored conditional responses and a synthetic source transport: **no live model and no network retrieval**. Both arms have the same objective, context, structural acceptance, two model-call allocations and two tool actions. Only the treatment has the explicit source permission. Separate workspaces and identical initial resources prevent retrieved evidence from leaking into the control. The source coefficient is withheld from the model task context and original checks.

The source arm resolves the synthetic coefficient; the no-retrieval arm honestly abstains. Both satisfy the report's structural checks, so a separately recorded outcome measure distinguishes factual resolution from a valid abstention. A competent ordinary source reader resolves the same coefficient using a deterministic parser and zero model calls. The result demonstrates authorized information access and retained evidence, with no established reasoning, discovery or economic advantage. See `evidence/strategy-comparisons.json`; actual local inference is reported separately in `evidence/live-local-workflows.json`.
