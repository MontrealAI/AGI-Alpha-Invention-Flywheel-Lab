# FRONTIER Ω — Capturing the Exponential
## Private opportunity-inventory workbench

An executable, local research workspace for the ALPHA Economic Engine. Keep valuable blocked outcomes, beneficiaries, acceptance requirements, frontier dependencies, current alternatives and next experiments together. Track what deserves a retest as the available tools change.

This work extends the existing Reservoir in PR #422 and release radar in PR #424. It does not replace the ALPHA economic engine or its financial account. The original six public dossiers and five observations are preserved unchanged; six additional **opportunity hypotheses** bring the starter inventory to twelve.

## Start

Python 3.10+ on a POSIX system. Tested on Linux; macOS is an intended POSIX target, not separately verified. Native Windows is not supported by the inherited `fcntl` lock; use a qualified POSIX environment. No third-party runtime package, model API key, paid service or purchase is required.

```sh
python3 start_frontier.py
```

The launcher seeds a private SQLite inventory, prints a session-specific local URL, and opens your browser. Default URL host: `127.0.0.1`, port `8766`. Keep the printed URL private: its fragment contains the session token. The browser removes the fragment and retains the token in tab session storage. The running terminal must stay open; Ctrl+C stops the server. Nothing continues after the process stops.

Use another port or private directory:

```sh
python3 start_frontier.py --port 8877 --root ./my-frontier-private
python3 start_frontier.py --no-browser
```

A supplied root must be owner-only (`0700`). Existing state is reused without resetting opportunities, notes or trials. Do not run another watcher on the same state directory: the existing single-worker lock is retained.

## The inventory

The starter contains **12 dossiers, five reported capability observations and 26 capability-to-problem retest signals**. No customer price, economic value, independent capability crossing or real revenue has been established for these dossiers.

| Outcome hypothesis | Initial question to resolve |
|---|---|
| Compiled cryptographic assurance | Can the exact deployed binary and agreed property be checked economically? |
| Committed-model inference receipts | Can the required proof scope justify full production and integration cost? |
| Complex software modernization | Can behavior, security, recovery and rollback meet an independent contract? |
| Agent-operated business procedures | Can exception-heavy tool workflows pass task-specific checks? |
| Cross-application computer-use workcells | Can verifiable state changes replace brittle click automation? |
| Electronic design-to-bench | Can independent physical testing validate the generated design? |
| Verified GPU-kernel savings | Can correctness and measured runtime gains beat competent kernels? |
| Proof-carrying memory-safety repairs | Can an accepted repair preserve behavior and establish the required property? |
| Adaptive compute scheduling | Can a new policy beat strong schedulers under the same workload and constraints? |
| Engineering simulation surrogates | Can calibrated error and out-of-distribution refusal support an engineering decision? |
| Specification-to-RTL delivery | Can generated hardware logic pass independent formal and implementation checks? |
| Calibrated binding-affinity research triage | Can retrospective, blinded evaluation justify a non-clinical research workflow? |

The original six dossiers retain their source-reported context. The six additions are explicitly authored hypotheses inspired by primary sources, not proof that the activity was impossible five weeks ago. In particular, AlphaEvolve is an established 2025 comparator, not a newly invented November capability.

New dossier sources include the official KernelBench and KernelAgent repositories, Anthropic's formal-verification research, Google DeepMind's AlphaEvolve work, NVIDIA PhysicsNeMo and Verilog evaluation projects, and the Boltz project. Exact source URLs, comparison alternatives and decisive tests are attached to each record. No source publication establishes willingness to pay.

## Operate from the browser

**Inventory:** search by outcome, beneficiary or capability. Use Add problem to create a dossier without editing JSON. Each record includes the desired outcome, current blocker, acceptance test, competent specialist route, human-plus-AI route, no-purchase alternative and next experiment. Original records are immutable; create a newly identified dossier for materially revised acceptance or contractual requirements.

**Research notes:** assign an operator priority, research stage, next review date, value hypothesis, proposed unlock condition, buyer pathway and notes. The stages are Blocked, Retest, Testing, Pilot review and Archived. They describe research progress, not financial status or technical certification. Edits are revisioned; stale edits are rejected rather than overwriting another session.

**Complete-cost scenarios:** enter explicit low/high USD estimates for price, paid-acceptance probability, all ten cost categories and additional losses. Blank fields remain unknown, not zero. Estimated net contribution is calculated exactly in integer microUSD, including conservative and optimistic bounds. These are stated assumptions, not real earnings, current funding or an empirically proved threshold crossing. The priority order is operator-selected, not a claimed globally optimal ranking.

**Retest queue:** inspect the particular capability observation that matched a problem. Mark a task Pending, Running, Done or Dismissed, with an evidence note or reason required for a terminal disposition. Completing a task never certifies a profitable opportunity or authorizes production.

**Export/import:** download a portable inventory snapshot and restore it atomically. Original problem/observation/trial bodies are retained. The snapshot contains the **current** research profiles and task dispositions, not every historical note revision. The source database retains revision history. Conflicting existing records or notes cause the whole import to roll back. Snapshots and dashboards may contain private customer information; they are not safe to publish automatically.

## Optional automatic release monitoring

By default, the workbench makes no external requests. To enable periodic metadata checks against the supplied explicit GitHub repository allowlist:

```sh
python3 start_frontier.py --monitor
```

The default source list covers Triton, vLLM, Lean, NVIDIA PhysicsNeMo and Boltz. It uses the existing PR #424 radar, not a second crawler. Configure another allowlist with `--sources path.json`. The default polling period is one hour; the processing floor is five minutes. The loop also processes local `inbox/*.json` records. A missing release, failed request or invalid response creates no feasibility claim.

A new reported release can generate matching **INVESTIGATE_ONLY** signals. Source descriptions are untrusted metadata, never executable instructions. Repository tags are coarse relevance hints; they can produce false positives and miss opportunities. Monitoring currently inspects the latest public GitHub release, not every paper, closed model release, cost change or historical release. A source update is not automatically benchmarked or converted into a paid job.

## Boundaries and security

The service is a private single-user research tool, not an Internet-facing production service. It binds only to loopback and uses per-session bearer authorization, exact Host/Origin checks, strict bounded JSON, script-hash CSP, no external browser assets and escaped untrusted text. The application does not discover credentials, call paid model APIs, execute arbitrary uploaded code or modify financial accounts.

Local SQLite hashes detect accidental or unsophisticated record modification; an operator able to rewrite code, files and hashes is not an independent adversarial verifier. This is not a cryptographic inference receipt, buyer attestation, hardened multi-tenant server or a claim of safe hostile local-user access.

Each request/import has a two-megabyte processing envelope. This is not a commercial ceiling on the number of opportunities; import in batches when needed. Runtime state, secrets and customer material must remain outside public source control. The supplied package contains only public hypotheses and code.

## Tests and qualification

```sh
python3 -m unittest discover -s tests -p 'test_frontier_workbench.py' -v
```

The new suite has **45 passing tests** in the working environment, covering actual private SQLite persistence, profiles, optimistic revisions, full-cost exact arithmetic, unknown inputs, atomic imports, source-radar fixtures, malicious markup, storage links, HTTP authorization, CSRF, script CSP and a separately launched server process. This is a scoped suite, not the repository's entire test suite.

Browser checks exercised Chromium desktop/mobile rendering, search, adding a dossier, persistent profile and queue edits, disabled network defaults and the standalone read-only preview. **Direct browser navigation to the local HTTP origin was blocked by the environment's administrator policy.** No policy was changed. Browser DOM interactions used an explicitly disclosed in-process API adapter; actual HTTP endpoints and the separate launcher process were tested independently. Do not call this an integrated browser-to-HTTP end-to-end qualification.

No live model benchmark, externally accepted outcome, paid customer, complete actual-cost margin or self-sustaining enterprise is demonstrated by these tests. Network-radar behavior is fixture tested here; access to external GitHub endpoints depends on the operator's host and permissions. The code has not been merged or deployed by this work.

## Delivery files

The runnable source kit includes exact upstream base bytes, new workbench code, public seeds, tests, compact evidence and a SHA-256 source manifest. The separate read-only HTML preview contains the public starter inventory and no server secret. It cannot save data or start monitoring. Use the Python launcher for the persistent working application.
