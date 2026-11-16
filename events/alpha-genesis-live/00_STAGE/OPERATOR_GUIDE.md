# Operator guide — ALPHA GENESIS FLYWHEEL Ω — LIVE

## Two independent operational stages

**Stage A, HARNESS:** launch your existing ALPHA GENESIS HARNESS according to its own `START-HERE.html` and `docs/WORKSHOP.md`. Enter the ambition, sources, alternatives and acceptance conditions. This workspace is the venue's conceptual stage. Its authenticated model integrations remain governed by the HARNESS's own qualification matrix.

**Stage B, live agentic companion:** use the separately installed official Codex CLI to perform the bounded Northstar Launch scenario. The bridge validates `codex login status`, runs the planner with first-party ChatGPT authorization, requests real calls through an allowlisted read-only host broker, and records source identities and model operations. A separate Node verifier recomputes the complete dossier. The second agent proposes three paths; the builder then constructs a portable HTML scenario desk, with frozen-policy conditional computations.

**Connection is automatic after the account holder authorizes first-party sign-in.** It is not a clandestine connection to an already logged-in browser tab. Credentials and ChatGPT subscription tokens are never packaged, read or redistributed by our code.

## Setup and dry run

From this unzipped top-level directory on a trusted Mac/Linux/Windows computer:

```sh
node --version        # 22 or higher recommended
npm install -g @openai/codex
codex login           # official ChatGPT sign-in; follow browser instructions
codex login status    # confirm it says "using ChatGPT"
node --test engine/tests/*.test.mjs
node 00_STAGE/run_show.mjs --mode preview --focus confidence
```

Then run a genuine full model-backed proof:

```sh
node 00_STAGE/run_show.mjs --mode codex-pro --focus confidence
```

If the currently available Codex model requires an exact ID, add `--model MODEL_ID` (do not assume or hard-code an unavailable model). Change focus with `time` or `cost`; all scenarios use the same synthetic case and frozen policy. The generated instrument is `00_STAGE/output/ALPHA_GENESIS_MISSION_STUDIO.html` and `RUN_SUMMARY.json` tells you whether actual model calls happened.

### What the agent can and cannot do

- **Can:** read the four supplied synthetic files through approved host calls, use model reasoning to decide next tool calls, inspect all eight orders, create a structured dossier, respond to verifier feedback, propose strategies and construct a reusable local evidence desk.
- **Cannot:** purchase anything, send email, authorize funds, access arbitrary enterprise systems, fetch arbitrary personal data, silently connect to a user's ChatGPT browser session, or prove that modeled supplier recovery occurred.
- **No API key required for Codex CLI:** the user authenticates with their own ChatGPT account, with plan-specific eligibility and usage limits. ChatGPT subscriptions and separately billed API access are not equivalent.

## Rehearsal protocol

1. Do the scripted run and independently verify its `agent-receipt.json` using `node engine/verify_receipt.mjs 00_STAGE/output/agent-receipt.json`.
2. Complete the account holder's real `codex login`, then one full `--mode codex-pro` run. Inspect the `actualModelCalls`, `toolEvents`, `verification`, and `strategy.json`.
3. Confirm the result shows **LIVE_MODEL** (not `SCRIPTED_PREVIEW`) and the instrument reproduces its baseline. Preserve a copy outside the event folder, with date and source identities.
4. Open the HTML on the presentation computer, select all 3 routes, test the check button, and download the JSON. Verify the displayed assumption labels.
5. Test Zoom screen share and recordings/captions, a guest registration path, audio, and a presenter-offline fallback. Do not present a scripted preview as fresh inference.

## Most important live interaction

At minute ~20, audience votes whether the priority is **time**, **financial exposure**, or **confidence**. Pass the winner as `--focus time|cost|confidence`, with a pre-run verified live receipt available as presenter continuity backup. The second model-backed strategy is allowed to choose among the three established paths; the audience then chooses again in the HTML desk. This gives observable agency and useful surprise without depending on an unrestricted, untestable promise.

## HARNESS handoff

Open `00_STAGE/output/HARNESS_HANDOFF.md` (generated with the latest run). Use it as source material and manually record the constructed solution and evidence in the HARNESS mission. This is a deliberate manual handoff, not an untested native project import or paid-edition ChatGPT integration claim.

## Confidentiality and security

Never request private records, credentials, customer contracts or emails in a group demonstration. The built-in case is fictional and includes one untrusted supplier note to verify tool-output instruction boundaries. The CLI sign-in is first party and remains on the presenter host. Run the Node code only from an independently reviewed copy of this package, not an unknown archive. Keep outputs with user session data private where appropriate. Do not expose a public control endpoint or commit auth files.
