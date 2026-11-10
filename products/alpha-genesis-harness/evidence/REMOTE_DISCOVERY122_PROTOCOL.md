# HARNESS122 — remote discovery consent boundary (frozen before repair)

**Baseline:** protected main `96c9dec4ded463bb8ec6b8a7cc0d0f7e3e3d1aa5`, product head from normally merged PR #320 (`c80e76cea9775b27bded0d16eb4e13f8a795bc4d`). **Scope:** only optional product bridge remote model metadata discovery, associated tests, and this bounded evidence. No native account, repository financial authority, keys, customer data or network request.

## Exploratory finding (pre-registration; not a post-fix pass)

At the merged source, `Runtime.status()` reports remote inference disabled when `allow_paid_requests: false`, and `Runtime.generate()` rejects remote generation (PERMISSION/403). But `Runtime.discover()` calls the configured authenticated remote `/models` sender without checking `allow_paid_requests`. A synthetic sender recorded one outgoing-intent invocation to the remote provider endpoint. No real HTTP request was made; whether a provider would bill metadata requests is unknown. This is an API-consent boundary, not a demonstrated external charge.

## Fixed registered regression and decision

Freeze the cases **before editing product source**, do not change the cases after observing repair results:

- R1 **forbidden remote discovery:** user-declared remote provider, inert synthetic environment placeholder, `allow_paid_requests=false`, session_budget=0, injected in-memory sender. `discover()` MUST raise `BridgeError(PERMISSION,403)` and sender call count MUST remain zero. Do not treat a zero-token model list as permission to call a remote API.
- R2 **authorized synthetic remote discovery:** identical remote synthetic provider, `allow_paid_requests=true` and fake sender returning a finite model list. Discovery MUST succeed once with one injected sender call; no live HTTP traffic.
- R3 **local zero-budget discovery:** configured loopback Ollama provider, `allow_paid_requests=false`, fake sender. Discovery MUST remain available; no remote endpoint or paid service.
- R4 **remote inference guard:** without consent, generation MUST still fail PERMISSION/403 with zero sender calls.
- R5 **no-secret/no-network default:** default constructed runtime has no configured providers; no discovery or generation of a remote provider is possible.

Acceptance: all five frozen cases pass on the **same exact source head**, existing 45 Python tests and 60 Node tests do not regress, hosted source-matched qualification succeeds, and independent artifact/clean source evaluation before any release claim. Failures must remain failures. No user credential, paid API, purchase, outreach, production deployment or native financial account is permitted. This is a narrowly bounded software security regression, not proof of commercial demand, profit or generalized provider safety.

Owner boundary: former PR #320 is already merged. Publish prospective product correction in a separate normally reviewed PR, never rewrite the former merge or any historical result. Normal release/download qualification remains independently required.
