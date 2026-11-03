# Delayed-case finalization amendment

Original financial registration: `b28155ff8f0c7ba26a9ac74d477a4865587554eba2ff275042c3e8de4ec12d76`.
Unchanged native financial source: `20e24b8cdb7688707dc390bb0562ef504357e2de342cd775d61f156b2b38f4a2`.
Prospective finalizer SHA256: `040c6415b3bade6b1b0994f5aa95dba30d35db3a38c3048b88ea4ee90e486d6c`.

The original delayed-collection case processed its full eight-request queue, including post-horizon collections, then attempted to move the financial clock back to hour8759 for a zero-cost closing marker. The native `EVENT_TIME_REGRESSION` guard rejected that action. The failed command remains failed. Seven other completed cases and their evidence remain unchanged.

Only case07 may be finalized. The finalizer must open its ORIGINAL account through JournalAccount and mandatory adaptive Account, validate the source and authenticated checkpoint, require an empty operating queue with exactly eight original request decisions, and independently audit the existing history before any transition. It may advance to the maximum of the existing clock, hour8760 and the already registered maturity dates plus one. It may not create orders, production, fees, tax adjustments, funding, new decisions or substitute accounts. No reseeding, copied balance, original-history rewrite or source change is permitted.

The dated trailing-year observer remains [0,8760). Its result must be identical before and after finalization. Revenue, expense, profit, collections and cash must also remain identical. Only legitimate maturity-related restriction changes may occur. All original action-prefix bytes must remain unchanged. A public before/after receipt will distinguish this amended completion from the original failed invocation. This is a recovery amendment, not an additional favorable economic trial.

At publication of this amendment, the finalizer has not yet operated the delayed account. Its result is not asserted here.
