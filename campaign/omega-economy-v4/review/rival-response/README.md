# Preserve a competitor’s original production method

The one-buyer witness gave both parties zero baseline production costs. The seller quoted 50, the rival could quote 10 and the seller's proposed operator cost 20 without improving output. With copying enabled, the earlier solver removed the rival's original technology. It reported 30 units of seller profit. Keeping the original rival offer eligible gives the rival 10 units and the seller chooses nonentry with zero profit. These are abstract units in a finite game.

The independent oracle evaluates original and copied technology at each admitted rival price and considers nonentry. It covers 5,184 declared combinations of costs, optional copying, build and partner payments, buyer wallets and price ties. The earlier source disagreed in 1,555 cases. The corrected solver matched every case. Each run used 20,736 buyer-allocation evaluations. The published illustration retained its 20 seller states, seller price 19 and expected contribution of 41/10.

Run the oracle on a checkout and give it a new output path:

```sh
python -B independent_rival_game_oracle.py /absolute/path/to/checkout /absolute/new/oracle-result.json
```

[Earlier oracle receipt](RIVAL_REGISTERED_ORACLE_BEFORE.json) · [Corrected oracle receipt](RIVAL_REGISTERED_ORACLE_AFTER.json) · [Public API and file-bound replay](PUBLIC_API_REPLAY.json) · [Raw CLI results and test gate](GAME_MAKER_REPAIR.json). The original buyer portfolios, paid reach, and primary money accounts use separate source maps. The changed finite-game result never authorizes a native payment.
