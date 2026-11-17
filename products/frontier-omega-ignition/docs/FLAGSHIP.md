# Can a release reviewer trust what arrived?

On 17 November 2026 we investigated what would let a MONTREAL.AI release reviewer distinguish a correct research handoff from a plausible-looking one. The research edition already assembles an explicit list of files and checks in-repository source. A separately delivered archive is another observation. In an earlier public handoff, MONTREAL.AI reported receiving a different PDF under the expected filename. That report establishes a concrete reason to test the receiving end. It does not measure the frequency or cost of this problem. [Research edition at the investigated revision](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/09e611c6df506ab24fba494b1ec41716e3721049/docs/frontier-omega-ignition/research-edition/README.md) · [Public handoff history, issue 4850](https://github.com/MontrealAI/AGI-Alpha-Agent-v0/issues/4850)

## Three candidate investigations

| Direction | What the recipient would learn | Strong alternative | Decisive condition |
|---|---|---|---|
| Compare the received file inventory and bytes against an independently obtained reference | Which expected files arrived, which changed, which disappeared and which were added | GNU SHA-256 plus a complete file-name inventory | Use actual research-edition files and a mixed-fault receipt. An ordinary route with the same output defeats a functional superiority claim. |
| Verify publisher identity and provenance | Whether a trusted publisher signed these release bytes | Cosign with a trusted signer, issuer and verification bundle | Obtain the actual release's signed bundle and a separately grounded signer policy. A locally invented signature would change the question. |
| Re-execute the evidence on the received artifact | Whether its behavior satisfies the original mission contract | Existing repository tests plus a separately run reference implementation | Freeze a consequential recipient test; compare the same delivered bytes and controls. Matching file hashes alone cannot settle behavior. |

The first direction supplies a useful offline delivery step that this implementation can exercise with public data. The second requires a publisher trust anchor and signed material. The third remains a candidate for a new research contract. We retained both as live alternatives, without substituting an identity or behavior claim for the byte-level outcome. The Blue Sky charter requires a consequential, newly attainable result for admission as a flagship. This narrow release audit remains a control and a candidate for integration. [Blue Sky charter](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/09e611c6df506ab24fba494b1ec41716e3721049/campaign/blue-sky-064/CHARTER.md) · [Sigstore verification requirements](https://docs.sigstore.dev/quickstart/quickstart-cosign/)

## Controls frozen before construction

`examples/integrity.json` contains the complete bytes of `ignition.css` and `studio.css` from public research-edition commit `09e611c6df506ab24fba494b1ec41716e3721049`. The acquired Git blob IDs are `4c48bf971890ea6465a3b824b7f9a8d4d24607f0` and `389e4fbd9ca6ad402cf01e41ee90b4b6f38efd1c`. The example checks the clean delivery, a changed/absent/extra combination, an empty delivery, bad encoding and an unsafe name. It never expands an incoming archive or opens a supplied path. In a real release, the reviewer must obtain the expected manifest through a trusted channel separate from the observed payload.

`examples/migration.json` translates a projection of the actual Blue Sky 064 research cards into an editorial queue. The target adds an area derived from the first segment of the candidate identifier. A construction model sees the target columns and training examples; its assignment includes choosing the source column and the extraction operation. Two distinct real cards are frozen for confirmation. Synthetic examples exercise changed decision text, order and rejection of a malformed input within a batch. A JSON projection says nothing about the scientific validity or commercial feasibility of the cards. [Pinned public source records](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/09e611c6df506ab24fba494b1ec41716e3721049/campaign/blue-sky-064/CANDIDATES.json)

`examples/unsupported.json` requests real load and wear measurements from a fabricated contact surface. The lab supplied no specimen, actuator, calibrated instrument or physical observations. A correct run preserves the purpose and refuses to manufacture a qualification.

## Comparison and economics

From the product directory, execute `python3 examples/compare_conventional.py` with GNU `sha256sum` and jq available. The separate implementation uses the operating system digest executable with explicitly computed file-set differences, and a strict jq field transformation. It has no import from the candidate builder or evaluator. Each test result retains the exact tool version, observed response and fixture identity. Wall times reflect single local case executions and subprocess overhead. They cannot price model construction, professional review or an entire engagement. [Executed conventional comparison](../evidence/conventional-comparison.json)

GNU Coreutils 9.7 predates the 13 October 2026 five-week baseline. jq 1.7 is also an established available alternative. The local comparison reuses those older versions today. It establishes a direct ordinary route to the frozen outputs. We have no matched historical record of operator time, full costs, or access on 13 October. Codex 0.169.0 added local diagnostic ZIP export within the window; its announcement provides no evidence of a change in byte verification or record projection. [GNU 9.7 release history](https://github.com/coreutils/coreutils/blob/v9.7/NEWS) · [jq 1.7 release](https://github.com/jqlang/jq/releases/tag/jq-1.7) · [Codex CLI release](https://github.com/openai/codex/releases/tag/rust-v0.169.0)

A publishing team could compare time per accepted handoff, packaging and review labor, incident rework, installation cost, model use and retained maintenance under identical delivery requirements. No buyer was observed, contacted or charged. The reference manifest, executable construction language and evaluator may be reused subject to rights. Each new package requires its own trusted reference, scoped permissions and acceptance. The evidence does not establish commercial compounding or an economic frontier crossing.

## What actually ran

The included ChatGPT Work session supplied eight fresh structured replies through the application's operator-assisted exchange. Three replies served each software mission and two served the physical control. The application made zero programmable model calls in this qualification. Each recipient program subsequently ran without a model. The operator who prepared the public fixtures also submitted the replies. The construction packets excluded confirmation cases, but the exercise was not blinded to that operator. The reported model family is GPT-6, as identified by the active session; its exact backend and token usage were unavailable.

| Mission | Observed outcome | Conventional comparison |
|---|---|---|
| Release receipt | A sixth candidate superseded the original signer-verification favourite. The portable verifier passed nine cases including controls. | Independent stdlib inventory comparison tied. GNU Coreutils plus a file inventory also matched all five declared cases. |
| Research register | The model supplied a field mapping and split operation. The portable verifier passed nine cases including controls. | The example-only learner abstained because two mappings fit training. Strict jq, which could use the stated purpose, matched all four declared cases. |
| Physical wear | Research stopped at selection. The run contains its missing-measurement explanation. | No physical comparison took place. |

The reference evidence was captured against runtime digest `374eac5734a674901b9c02bb6db7264dced16a173a99eea6d661ff8954b23ffd`. Both ZIPs ran through their own extracted command line outside the source tree with Python isolated mode. The bundled interpreter and evaluator allow that qualification to be repeated against the exact delivered code. An implementation revision or future release requires its own qualification. [Recipient checks](../evidence/recipient-checks.json) · [Release receipt artifact](../evidence/integrity-artifact.zip) · [Editorial migration artifact](../evidence/migration-artifact.zip)

## Present the investigation in five minutes

1. **Start with the decision.** Ask the audience what they would do if the expected research styles arrived under familiar names, with one file modified and one unexpected. Open `web/index.html` locally and import `evidence/integrity-run.json` as a saved run. Identify the recorded-replay label. Show the dated sources and the transition from verifying a signature to comparing received bytes with an independent reference.
2. **Hand the artifact to the recipient.** Extract `evidence/integrity-artifact.zip` into a fresh directory and run the commands below there. The first command rechecks the frozen contract. The second supplies intact example bytes. The third supplies an actual, different input. Point out the difference between “missing,” “changed” and “unexpected.” A receiver who must authenticate the publisher still needs a trusted identity and appropriate signature material.

   ```sh
   python3 -I run.py verify
   python3 -I run.py run < example-input.json
   echo '{"files":{"ignition.css":"YQ==","extra.css":"Yg=="}}' | python3 -I run.py run
   ```

3. **Change the ambition.** Open the recorded migration and extract `evidence/migration-artifact.zip` into another fresh directory. Show how this program maps an actual research card into an editorial row and leaves the decision untouched. Ask the audience for a new record and run it through the published artifact. Then replace a required text value with a boolean and show the whole batch refuse.

   ```sh
   python3 -I run.py verify
   echo '{"rows":[{"id":"optics-sensor","name":"An audience example","status":"DEFER"}]}' | python3 -I run.py run
   ```

4. **Give the ordinary alternative equal footing.** Present the jq and GNU outcomes next to the candidates. The example-only learner faced a real ambiguity. A competent specialist with the same stated purpose could resolve it. There is no independent evidence here for a productivity, earnings or historical novelty claim.
5. **Ask for an observation the software cannot make.** Open `evidence/unsupported-run.json`. Read the original physical-measurement requirement and its missing specimen and instrumentation. There is no accepted artifact to export. A future experiment needs genuine observations from the intended surface.

For a fresh investigation, start the loopback service with an explicitly selected local or assisted provider as described in the operator guide. Load a public example or enter a new purpose. On an assisted run use each new request, return its reviewed JSON and inspect the current progress. The saved run files are for recorded review only. The system should refuse exports after a material amendment until the new revision passes fresh checks.

## Requalify the recorded artifacts against this checkout

Run `python3 examples/requalify_recorded.py --output /tmp/ignition-recipient-replay` from the product directory, using a new output directory each time. The command verifies the archived run IDs, runtime mapping, input and archive identities. It freezes the original mission specifications again, evaluates the recorded programs using today's implementation, builds separate ZIPs, then starts each new recipient outside the source tree and checks its example output. No model calls or new research take place. Its new receipt identifies the historic runtime, current runtime, replay script, Python version and newly emitted bundles. Comparable verdicts and output data reproduce; fresh timing observations can change bundle bytes. [Historic per-file source identities](../evidence/assisted-runtime.json)

## Try the receiver on a complete research edition

The whole-directory qualification rebuilt the original PR #436 research edition from 15 pinned source files, and delivered a fresh, offline receiver for the resulting 15 files (239,857 bytes). Its reference includes a separately pinned digest for the sender's `ASSEMBLY.json` as well as the files that manifest lists. The received copy never supplies the trusted reference.

| Delivery | Actual receiver observation | Exit |
|---|---|---|
| Original publication tree | All 15 files matched | 0 |
| Modified HTML, missing browser test and extra stylesheet | Named `index.html` as changed, `tests/test_browser.py` as missing, `unlisted.css` as unexpected | 1 |
| Replaced README and revised the received manifest to fit the replacement | Named both `README.md` and `ASSEMBLY.json` as changed | 1 |

GNU Coreutils 9.7 with an independent full inventory returned the same three classifications. All source bytes and changes are public or synthetic. This is a deterministic integration check on a reconstructed publication tree; it establishes the receiver's file-level behavior. The experiment used zero model calls and no external customer delivery. [Full measurements and source identities](../evidence/release-handoff.json)

From the product directory in a Git checkout containing `09e611c6df506ab24fba494b1ec41716e3721049`, run:

```sh
python3 examples/qualify_release_handoff.py --output /tmp/ignition-edition-handoff
```

If the original commit is in a separate checkout, supply `--reference-tree /path/to/that/checkout`. The script checks the exact input identities before executing the assembler. Open the fresh `research-edition-receiver.zip` in the output directory, extract it to a new location, and use `python3 -I run.py audit-directory /path/to/received-edition`. A nonmatching inventory returns exit 1; invalid input returns 2. This full-directory operation belongs to the new receiver. The two small historical ZIPs above preserve their earlier command interfaces.
