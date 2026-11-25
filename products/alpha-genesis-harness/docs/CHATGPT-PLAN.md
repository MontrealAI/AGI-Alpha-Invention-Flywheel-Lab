# ChatGPT plans and Codex / Forfaits ChatGPT et Codex

## Qualification status

**Implemented and contract-tested; authenticated live qualification is BLOCKED.**
No ChatGPT Pro login, live plan inference or live Codex turn was performed for
this release. The test suite uses synthetic credentials and protocol fixtures.
The paid Official Edition has **no recorded OpenAI commercial authorization**.
Do not market plan-powered execution as operational in that edition until both
authorization and an authenticated completed-request test are recorded.

The implementation uses the official public Sign in with ChatGPT flow. It does
not request passwords, copy browser tokens, use consumer-interface automation,
read existing Codex credential files or switch to API billing when a plan fails.
ChatGPT identity sign-in and authorization to use a plan are separate grants.

## Install the optional identity verifier

From the unpacked product directory, in the Python environment used to launch
the connector:

```sh
python3 -m pip install -r requirements-chatgpt.txt
```

On Windows, use `py -3 -m pip` if that is the installed Python launcher. The
application refuses sign-in if the cryptographic verifier is unavailable.
Offline/manual and ordinary provider workflows do not require this dependency.
The pinned packages follow the repository's existing dependency baseline;
the original engineering environment additionally exercised signature verification
with cryptography 50.0.0. A clean isolated environment successfully installed
the exact pins (cryptography 50.0.2, cffi 2.1.1, pycparser 3.11) and passed the
12 ChatGPT, 9 Codex and 10 independent continuation tests. See
`evidence/OPTIONAL-DEPENDENCY-VERIFICATION.json`. These are offline contract
checks, not authenticated inference or actual Codex sandbox qualification.

## Eligible open-source local installation

Use this configuration only for an installation that actually meets OpenAI's
open-source/local eligibility requirements:

```json
{
  "chatgpt": {
    "allow_plan_usage": true,
    "distribution": "open-source-local",
    "request_limit": 20
  }
}
```

1. Launch the HARNESS connector with this private configuration.
2. Open Intelligence Center and select ChatGPT plan access.
3. Select **Continue with ChatGPT**. Your system browser opens the official
   OpenAI authorization page. Select your account/workspace and review consent.
4. Return to the HARNESS after the loopback callback succeeds. The account
   selector distinguishes registrations even when their email addresses match.
5. Load models from the connected account, select one, then run a small useful
   task using the current mission brief.
6. Check the connection status after the request. Authorization permits a
   request. The first valid `response.completed` with output establishes an
   observed execution on that connection.

The native connector stores separate HTTP plan and Codex completion receipts
per account in its protected vault. The latest receipt contains the route, model,
completion time and provider-reported token counts, when available. Sign-in,
catalog discovery and incomplete responses never create a receipt. Reconsent,
revocation and loss of usable credentials remove or suppress current
qualification. A late result after an account switch remains associated with the
original request and cannot qualify the newly selected connection. Completing a
request establishes provider execution. Accepting its result still requires
mission-specific verification.

Select **Download connection receipt** in the ChatGPT or Codex status area to
save a JSON file with the route, model, completion time and available token
counts. The file omits account identifiers, credentials, prompts and responses.

The local session limit counts started requests or Codex turns. A Codex turn
can perform several internal model calls. This limit is neither a token cap
nor a monetary ceiling. Set the app's actual plan and credit permissions in
[ChatGPT Settings → Usage](https://chatgpt.com/settings/usage). No usage amount
is translated into an invented API dollar cost. Review app-specific limits and
the use of any ChatGPT credits in the same settings.

## Paid edition: approval before activation

OpenAI's current documentation directs paid and remotely hosted applications to
the [Sign in with ChatGPT interest form](https://openai.com/form/sign-in-with-chatgpt-interest/).
The registration/partner process and eligibility decision belong to OpenAI.
An Apache license does not establish approval for the paid package.

The public Pages experience opens the native connector or a reviewed manual
handoff. It does not act as a hosted Sign in with ChatGPT inference client.
The paid distribution defaults to disabled. When OpenAI has actually granted
the applicable permission, record the approval reference in private local
configuration and follow any provider-supplied integration conditions:

```json
{
  "chatgpt": {
    "allow_plan_usage": true,
    "distribution": "commercial",
    "commercial_approval_reference": "REPLACE ONLY WITH AN ACTUAL APPROVAL REFERENCE",
    "request_limit": 20
  }
}
```

The reference is an operator attestation; this application cannot verify that
OpenAI issued it. Supplying text does not grant commercial rights or establish
live eligibility. There is no UI control to manufacture approval. Do not
relabel a paid edition as an open-source local installation to bypass this gate.
If approval requires a different registered-client flow, implement and qualify
that supplied contract before enabling the paid connection.

The owner application dossier is in `CHATGPT-COMMERCIAL-APPLICATION.md`.

## Identity, storage and account control

Each host persists a random opaque host ID. Each authorization attempt has new
state, nonce and PKCE material. The application checks the callback state,
issued client ID, ID-token signature, issuer, audience, expiry, nonce and
returning account identity. It uses OpenAI's OIDC discovery and trusted JWKS.
Only the granted scopes enable inference; declined plan consent leaves identity
sign-in usable without authorizing model requests.

The HARNESS launcher stores credentials in the local user's
`~/.alpha-genesis-harness/chatgpt/chatgpt-auth.json` by default. An embedding
application can supply its own private data root.
Unix storage requires a user-owned 0700 directory and 0600 file. Windows uses
the current user's DPAPI protection. Windows behavior is implemented but has
not been verified on an actual Windows machine for this release. Tokens do not
enter browser storage, project exports or public archives. Do not put the
credential directory inside a project you intend to share.

Renewal is serialized with process and file locks. Rotating credentials are
replaced together. Terminal refresh failures remove unusable credentials while
retaining the account registration. Temporary connection failures preserve the
connection for an explicit retry. Account switching and disconnect cancel active
requests; a request already sent upstream may still consume allowance.

Disconnect attempts official token revocation, then clears local tokens. If
revocation fails, the interface says so; finish disconnection in ChatGPT
Settings. In local-only mode, disconnect clears locally without making a remote
request and therefore cannot confirm remote revocation.

## Inference behavior and errors

The adapter retrieves the account-specific `/v1/models` catalog and calls the
public `/v1/responses` endpoint using OAuth. HTTP requests use `store:false`,
`stream:true` and an explicit input array. They omit unsupported request fields,
including `max_output_tokens`, temperature and previous response identifiers.
The general UI's output limit is not an enforceable upstream limit for this
route. The interface reports stream progress and releases redacted text only
after terminal completion. This prevents partial output from being labeled a
completed result and avoids credentials leaking across chunk boundaries.

Quota exhaustion pauses new dispatch. Partial, failed and interrupted streams
are not accepted as successful. Error codes remain distinct from API-provider
errors. No automatic paid fallback or repeated inference retry occurs.

The 2026-11-10 protocol review additionally tests malformed terminal events,
missing usage, unknown error shapes, signed invalid identity claims and attempts
to replace an existing registration's identity. Such failures cannot become
successful completions or overwrite a different validated account. Admission
errors retain their HTTP status, response shape, safe request identifier and
unsupported parameter when supplied. Arbitrary remote error text and credential
values are omitted from public diagnostics. These adversarial checks are offline
contract evidence, not proof of a successful authenticated Pro request.

| Symptom | Action |
|---|---|
| Connection disabled | Check actual eligibility and explicit local configuration. |
| Commercial approval required | Obtain applicable OpenAI authorization; use another configured route meanwhile. |
| Consent declined | Retry only when you want to grant access. Select reconsent if plan permission was omitted. |
| Identity verification failed | Do not bypass validation. Check system time and start a fresh authorization. |
| Authorization expired/revoked | Sign in again using the retained registration. |
| Plan usage limit | Inspect ChatGPT Settings → Usage; do not infer a reset time or buy credits automatically. |
| Unsupported capability | Choose an account-listed model and supported text request. |
| Interrupted stream | Preserve the failed attempt; retry explicitly with a new run ID if appropriate. |
| Browser cannot open | Configure a system browser on the local host and retry. Headless manual-token pasting is unsupported. |

## Promotional API credits for eligible ChatGPT subscribers

1. Open the official benefit guide and check current eligibility from the
   ChatGPT or API Platform account you control. Activation is handled by OpenAI.
2. Select the receiving API organization you own. Confirm the grant in that
   organization's API Billing → Credit grants. A project used for the mission
   must belong to this organization and be authorized to use its API access.
3. Keep API execution paused when you require zero additional expenditure and
   cannot enforce that boundary. OpenAI applies purchased API credits after
   promotional credits expire or run out. The HARNESS does not activate
   recharge, change billing settings or verify account balances.
4. For a later authorized qualification, retain private evidence tying the
   provider request, organization, project, actual usage and applicable
   credit deduction together. Usage counters alone do not establish the balance
   used or the cash charged. Protect all account identifiers and credentials.

The API promotion does not fund signed-in Codex usage or Codex via API keys.
Signed-in Codex and OAuth plan inference follow ChatGPT usage settings.
[Official API credits benefit guide](https://help.openai.com/en/articles/20001626-api-credits-benefit-for-eligible-chatgpt-subscriptions)

## Codex engineering pathway

Install the official Codex CLI separately. Use the HARNESS's authorized ChatGPT
connection; this implementation does not reuse a consumer session or the CLI's
preexisting credential file. Enable Codex explicitly:

```json
{
  "chatgpt": {
    "allow_plan_usage": true,
    "distribution": "open-source-local",
    "request_limit": 20
  },
  "codex": {
    "allow_execution": true,
    "allow_workspace_write": false
  }
}
```

For the paid edition, the same commercial gate applies. Use the actual
distribution and approval state. An optional `executable` field selects an
absolute path to the trusted official `codex` executable. The default connector
uses its own private `codex-workspaces` directory. Enable workspace writes only
when the specific engineering task needs them and you authorize them.

Each run has a new isolated workspace and a protected `CODEX_HOME` in a sibling directory outside the writable execution root. The bridge uses the
documented app-server initialize → thread/start → turn/start protocol and a
Responses provider supplied with the HARNESS OAuth token. It excludes existing
MCP/app configuration and billing environment variables, denies external action
approval requests, disables tool network access, restricts read roots and permits
workspace writes only after explicit local opt-in. Model outputs and files still
need independent acceptance checks. This is an engineering executor, not proof
that an arbitrary generated program is safe or correct.

A completed turn exposes text and a manifest of bounded ordinary artifact files.
Symlinks and files containing credentials are not exported. Automatic secure
artifact inventory uses descriptor-relative no-follow opens; it fails closed
on platforms without that support. The working directory remains available for
manual inspection. Codex authentication, actual sandbox enforcement and artifact
construction have not yet been live-qualified on this release. Completed and interrupted run directories persist. The backend supports explicit
resume through `/api/codex/resume`, using the original `resume_run_id` and a new
`run_id`, the original account registration and the original model. The response
returns `resume_run_id` for later continuation. Example authenticated API body:

```json
{
  "resume_run_id": "original-codex-run",
  "run_id": "continuation-2",
  "model": "THE_ORIGINAL_ACCOUNT_MODEL",
  "prompt": "Continue the interrupted construction and verify the output."
}
```

Use the existing same-origin HARNESS session header; do not expose its token
outside the local application. Checkpoints bind the original absolute workspace,
Codex runtime directory, model, account, thread and sandbox policy. They are
HMAC-authenticated with a key in the protected credential store outside the
execution workspace. Resume never increases the original permissions, and a
cross-process workspace lock refuses concurrent continuation. Failed preflight
does not increment the local plan request counter. Keep the original private
workspace and credential/signing state; copying a project export is not permission
to resume a different account's Codex session.

Before passing any OAuth token to a Codex process, the bridge exports the
installed CLI's schema with `--experimental` and checks the official named
permission-profile interfaces. The application explicitly opts into that
app-server capability. It configures a profile that denies filesystem access by
default, permits the platform minimum and required Python runtime files, grants
only the chosen workspace's read/write policy, and disables tool networking.
It never combines that profile with legacy sandbox overrides.

A separate local app-server probe uses a synthetic environment sentinel and no
real credential. It must prove permitted workspace reads, the configured write
policy, denial of a separate synthetic private file, denial of a local network
connection and exclusion of the credential environment variable from tool
processes. Only then may the OAuth-backed process start. A successful model
thread must also confirm the requested active profile. The runtime directory
and signed checkpoint store remain outside the agent's writable root.

Run the same no-inference probe manually:

```sh
python3 scripts/probe_codex_sandbox.py --executable /absolute/path/to/codex --work-root /absolute/path/to/private-probe-work
```

Exit 0 means the two local sandbox checks passed. Exit 2 means they are blocked;
read the JSON reason and correct the host/runtime without disabling isolation.
The public stable CLI `0.167.0` and preview `0.169.0-alpha.7` expose the required
named-profile contract. The initial legacy RPC approach did not, and was replaced.
Official npm downloads were integrity-checked before isolated schema inspection.
The currently installed `0.172.0-alpha.2` reported the required profile
interfaces in schema inspection and the profile was accepted in a local
app-server session. The native command failed with `Operation not permitted`.
The authentication path stayed closed. A separate supported host must pass the
native check before an eligible account can qualify an actual turn.

## Français

**État : code réalisé et tests de contrat réussis; validation réelle bloquée.**
Aucune connexion Pro, inférence réelle ou exécution Codex authentifiée n'a été
effectuée pour cette version. L'édition payante ne dispose pas d'une autorisation
commerciale OpenAI enregistrée. Les tests simulés ne prouvent pas ces accès.

Installez les dépendances facultatives avec
`python3 -m pip install -r requirements-chatgpt.txt`, puis lancez le
connecteur avec la configuration correspondant réellement à votre distribution.
Choisissez **Continuer avec ChatGPT**, sélectionnez votre compte et votre espace
de travail sur le site officiel, examinez le consentement et revenez au HARNESS.
Chargez la liste des modèles du compte et lancez une petite tâche à partir du
mandat en cours. Le statut distingue l'identité vérifiée, le consentement au
forfait et l'inférence constatée. Le connecteur conserve un reçu distinct par
compte et par voie d'exécution pour la dernière réponse achevée. Il indique le
modèle, l'heure et les nombres de jetons fournis. La vérification du résultat de
la mission reste une étape distincte.

Sélectionnez **Télécharger la preuve de connexion** dans le statut de ChatGPT
ou de Codex pour enregistrer la voie, le modèle, l'heure et les nombres de
jetons disponibles. Le fichier JSON exclut les identifiants de compte, les
secrets, les mandats et les réponses.

L'identification ne suffit pas : il faut aussi autoriser l'utilisation du
forfait. Les jetons restent dans le stockage local protégé, jamais dans le
navigateur ou les exports du projet. La déconnexion tente de révoquer la session
et efface les jetons locaux; l'interface indique si la révocation distante n'a
pas pu être confirmée. En mode local seulement, aucune révocation réseau n'est
tentée. Changez de compte depuis le sélecteur dédié.

Les limites du forfait, les crédits autorisés, les coûts API et les coûts de
calcul local sont distincts. Aucune panne n'active automatiquement une API payante.
Le compteur local limite les requêtes ou tours démarrés; un tour Codex peut
comporter plusieurs appels internes. Il ne constitue pas un plafond monétaire.
Consultez [Paramètres ChatGPT → Utilisation](https://chatgpt.com/settings/usage).

Pour les crédits API promotionnels, vérifiez votre admissibilité, activez
l'avantage depuis votre propre compte et sélectionnez l'organisation API
bénéficiaire. Vérifiez l'octroi dans les paramètres de facturation et utilisez
uniquement un projet autorisé de cette organisation. Les crédits API achetés
peuvent prendre le relais après la promotion. Si vous exigez zéro dépense
supplémentaire, laissez l'API en pause tant que cette limite ne peut pas être
appliquée. Une validation réelle exige une requête autorisée et une preuve de
facturation correspondante. L'avantage ne couvre pas les tours Codex via une
clé API. [Guide OpenAI de l'avantage en crédits API](https://help.openai.com/en/articles/20001626-api-credits-benefit-for-eligible-chatgpt-subscriptions)

L'édition commerciale exige l'autorisation applicable d'OpenAI. La référence
enregistrée dans la configuration est une attestation de l'opérateur, pas une
vérification par OpenAI. Il est interdit de déclarer l'édition payante comme
installation libre admissible pour contourner cette condition. Le dossier à
préparer figure dans `CHATGPT-COMMERCIAL-APPLICATION.md`.

Pour Codex, installez l'outil officiel, autorisez la connexion ChatGPT du HARNESS
et activez explicitement l'exécution. Chaque travail utilise un dossier isolé.
Les accès réseau des outils sont désactivés; les écritures nécessitent une
autorisation locale. Inspectez et testez les fichiers obtenus avant utilisation.
La reprise explicite est disponible par `/api/codex/resume`, avec l'identifiant
original `resume_run_id`, un nouveau `run_id`, le même compte, le même modèle et
le dossier d'origine. Les points de reprise signés conservent les permissions
initiales et refusent les modifications ou accès simultanés. Le schéma des profils de permissions de l'outil Codex installé est vérifié
localement. Un second test, sans authentification ni modèle, doit démontrer les
limites du système de fichiers, du réseau et des variables d'environnement
avant transmission d'un vrai jeton. Un environnement incompatible est refusé;
aucun contournement automatique n'est proposé.

## Official references checked for this implementation

- [Overview and eligibility](https://developers.openai.com/siwc/token-sharing-open-source)
- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Accounts, renewal and revocation](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Models and completed inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview request restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [Sign-in user experience and usage settings](https://developers.openai.com/siwc/ui-ux-guidelines)
- [Error recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [SIWC Codex configuration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- [Codex app-server protocol](https://developers.openai.com/codex/app-server)
- [Codex integration options](https://developers.openai.com/blog/codex-as-a-platform)
- [Signed-in Codex eligibility](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)

Tests: `python3 -m unittest discover -s tests -p 'test_chatgpt.py' -v` and
`python3 -m unittest discover -s tests -p 'test_codex.py' -v` from this product.
The additional security/protocol regressions run with
`python3 -m unittest discover -s tests -p 'test_chatgpt_hardening.py' -v`.
