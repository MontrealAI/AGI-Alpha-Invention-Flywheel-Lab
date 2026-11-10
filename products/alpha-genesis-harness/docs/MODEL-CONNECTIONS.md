# Choose your intelligence / Choisir votre intelligence

## Start without an API key

Open the core browser application. Define your mission, choose a working mode and create a prompt. Copy it into an AI chat account you already control. Paste the response back into the HARNESS with the provider/model and role declared. Independent alternatives require genuinely separate model work; a label alone does not establish independence.

Manual mode is usable without Python or a provider credential. The bundled demonstration contains synthetic instructional inputs; it does not call a model or possess live knowledge.

## Optional local bridge

The bridge is an advanced optional connection route. It uses Python **3.10 or later**, supplied separately, and the Python standard library. The release does not bundle Python or a signed desktop installer. From the product folder:

```bash
python3 bridge/server.py --config /absolute/path/to/private-config.json
```

On Windows installations where Python's launcher is available, use `py -3` instead of `python3`. This is guidance, not a claim of testing every Windows/Python distribution. Without `--config`, the server serves the manual application with providers unconfigured and a zero request budget.

Copy the provided `bridge/config.example.json` to a **private location outside the product folder**. Follow `bridge/README.md` for exact fields. Model names are customer-configured: no example model identifier implies availability in your account. Credentials are read from named environment variables such as `HARNESS_OPENAI_API_KEY`; do not add literal keys to source, configuration examples, model responses or project exports.

| Route | Customer must provide | Qualification boundary |
|---|---|---|
| Manual chat | An authorized chat service or local UI, when using a model | Works through copy/paste; not an account integration |
| OpenAI-compatible API | Endpoint, supported model, correct prices and authorized credentials | Adapter contract tests do not establish every compatible vendor works |
| Anthropic API | Account access, model, current prices and authorized credentials | Live authenticated test required before claiming a tested integration |
| Google Gemini API | Account access, model, current prices and authorized credentials | Live authenticated test required before claiming a tested integration |
| Ollama | A running local installation and installed model | Local protocol tests do not establish available models or machine capacity |

API usage is separate from the CAD $299 package and separate from a consumer AI subscription. The development mandate has not authorized obtaining keys or making separately billable model calls; no such testing is represented as completed.

Before enabling requests, review the declared session budget, configured prices, request limits and permission toggle. Unknown or incorrect provider billing cannot be converted into a measured zero cost. A request already accepted by a provider can continue or be billed after local cancellation. Retries can consume additional resources. Read the bridge's exact accounting behavior and limitations before use.

## Français

Commencez par le parcours manuel : créez une demande, copiez-la dans votre service d'IA, puis importez la réponse en indiquant le modèle et son rôle. Aucune clé API ni installation Python n'est nécessaire pour ce parcours.

Le connecteur facultatif utilise Python 3.10 ou une version ultérieure. Sa configuration doit rester dans un dossier privé, hors de l'application. Les clés sont lues depuis des variables d'environnement. Les noms des modèles, leurs tarifs et votre droit d'accès doivent être vérifiés auprès du fournisseur.

Un abonnement de clavardage ne comprend pas nécessairement l'accès API. Les frais sont distincts du prix du produit. Les essais avec réponses simulées vérifient le contrat logiciel; ils ne démontrent pas une connexion réelle authentifiée. Une annulation locale ne garantit pas l'arrêt ni le remboursement d'une demande déjà reçue par le fournisseur.
