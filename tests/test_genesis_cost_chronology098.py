"""GENESIS native cost chronology 098 — frozen adversarial protocol.

Registered before adding executable test logic, on an isolated branch based on
PR233 exact source 895166b94410d7157aadb4c2bdac8022383361f2.

Scientific question
-------------------
Does the *canonical* native GENESIS public audit reject a legitimate, HMAC-
replayed BusinessAccount whose acquisition cost was posted at the wrong
source-prescribed hour, despite unchanged cost amount and a still-valid native
ledger? The original source schedules acquisition for first job at hour 24.

Finite fixed cases (no outcome-dependent substitution)
------------------------------------------------------
C0: original registered pilot, every acquisition and maintenance cost posted
at hour 24*(job index+1). Expected: canonical audit and independent witness
both accept.
C1: first acquisition amount unchanged, but date shifted exactly one hour
EARLIER (24->23), injected via BusinessAccount.cost before creating its native
action; all subsequent actions and obligations as originally registered.
Expected: independent source chronology witness rejects; determine from
actual native run whether canonical audit currently rejects or accepts. The
answer is a measured engineering finding, not asserted beforehand.
C2: synthetic key-free copy of genuine exported action rows, with an added
duplicate overhead cost; independent witness rejects, no account is rewritten.
C3: synthetic key-free copy with first acquisition amount +1 microUSD;
independent witness rejects, no account is rewritten.
C4: registered no-purchase case still pays actual fixed acquisition and
maintenance; independent witness accepts and no real revenue is claimed.

No private keys, signer material, actual customers, spending, provider calls or
original P0 accounts. Every operation uses disposable, existing canonical
native simulated accounts and public exports. No platform guard is relaxed.

Only this new test file may be edited on this branch. PR233, PR229, PR232,
current main and all original frozen evidence remain unchanged. A sidecar
witness is NOT an alternative native financial authority or release gate.
Do not merge without the existing owner incorporating any required enforcement
into the canonical audit and qualifying it through the ordinary source gates.

Do not relabel failures, retry until favorable or infer paid commerce.
"""
