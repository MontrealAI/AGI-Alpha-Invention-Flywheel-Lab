# Append-only finalization addendum

The first finalizer (`040c6415...`) authenticated and independently audited the original account, then validly appended two already registered maturity events at hour9889. It subsequently failed because it compared the entire rolling-profit receipt, whose action-tape hash and count of excluded settlement-drain actions necessarily change when a valid maturity event is appended. No original action, revenue, expense, cash or profit changed.

A read-only diagnostic independently audited the same original account. Exactly two receipt fields differ: `native_actions_sha256` and `settlement_drain_actions_excluded` (2 to4). All other rolling-window fields match, including $9,670.32 profit within [0,8760). The first finalizer remains failed and its exact source is retained.

Prospective revised finalizer SHA256: `81e172386a6b7f2d464fc5595803ddd6b365c9456412c7248ab88e1b57438342`.

The revision authenticates the original checkpoint as a source-bound prefix, requires that every subsequent action is a native-audited maturity at or after the profit endpoint, and compares all observer fields except the two necessarily changed identity/count fields. Monetary/window preservation requirements are unchanged. Original action-prefix bytes and revenue, expenses, profit, collections and cash must remain exact. It may advance only to original registered maturities and mark that same original state complete; no replacement account, new seed, order, producer run, funding, scenario or strategy is allowed. The financial source remains `20e24b8c...`. The seven completed case result files remain immutable.

At publication, the revised finalizer has not yet executed. Its success is not asserted here.
