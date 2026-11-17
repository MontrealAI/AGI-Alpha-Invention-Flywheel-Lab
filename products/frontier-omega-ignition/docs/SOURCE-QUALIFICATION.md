# Qualifying live source retrieval

Run the registered public-source experiment from a clean checkout. It uses the production HARNESS transport. It needs public HTTPS access to api.github.com and standard Python. The experiment sends six unauthenticated GET requests, covering two built-in feeds and one repository separately named by the operator. It does not send a customer mission or invoke a model.

```sh
python -B products/frontier-omega-ignition/qualify_sources.py \
  --expected-source "$(git rev-parse HEAD)" \
  --output /tmp/ignition-sources-receipt.json
```

| Registered source | Recent observations | Earlier observation |
| --- | --- | --- |
| huggingface/transformers | Up to three public releases, including the publisher's publication timestamps and tag identities | One commit on the default branch at or before the UTC date 35 days before execution |
| pypa/build | The same release selection | The same earlier-commit selection |
| jqlang/jq, provided as an explicit public repository URL | The same release selection with the operator-authority provenance retained | The same earlier-commit selection |

**Acceptance.** Each publisher must produce at least one release and one eligible earlier commit. References must match the expected public repository and request. The HARNESS must observe source bytes during this invocation. The receipt retains the exact request and source URLs, content identities and retrieval times. Earlier commits retain their committer timestamps and an unknown publication date. The finite release sample can contain pre-window events or pre-releases.

## Bringing a new public repository

In the advanced Resources field, supply `public_repositories` as an array, for example `{"public_repositories":["https://github.com/jqlang/jq"]}`. Then enable public source retrieval for this mission. Up to four canonical GitHub repository root URLs can be examined in one run. The explicit URLs may name projects absent from the built-in registry. Case-equivalent names share one request pair. Expanded paths, query strings, credentials and clone suffixes are rejected before dispatch.

The production transport constructs two read-only requests per distinct repository and pins the connection to public addresses for api.github.com. It uses no GitHub authentication. It never requests an arbitrary URL supplied by the model or inferred from mission prose. An inaccessible repository or missing release history yields a per-repository failure record. Earlier commits and release metadata may support investigation even when they cannot establish a capability improvement.

**Outcomes.** Exit 0 records PASS for source acquisition. Exit 1 records malformed or inconsistent evidence, or a source revision mismatch. Exit 2 records BLOCKED for unavailable public transport, a missing observation or an unverifiable checkout. If the service is unavailable, the previous model qualification and independent engineering jobs keep their separate results. The CI receipt contains only public observations, identities and compact failure reasons. Retry on a new invocation and keep the earlier receipt.

**Interpretation.** A release date locates a report in time. It cannot by itself establish that a model was accessible, that it improved a customer outcome, or that the earlier complete method failed. A committer timestamp is not independent proof of when a snapshot first became public. To compare two dated portable constructions, use `python -m ignition.compare protocol.json before.json after.json` from this product directory and evaluate both against the same frozen contract.

The product's workbench renders candidate, challenge and source records from each execution. Its two public example briefs contain attributed, frozen excerpts for reproducibility. The earlier research edition retains a separate authored catalogue. Those three sources of information have different evidentiary roles. The public comparison demonstrates historical conventional alternatives for digest verification and record migration; the recent diagnostic ZIP announcement supplies no measured advantage on either task. [Flagship evidence](FLAGSHIP.md)
