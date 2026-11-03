#!/usr/bin/env python3
"""Exact finite analytical illustrations for FLYWHEEL OMEGA.

No network calls, operating accounts, generated code, or empirical demand.
Integers and fractions are model quantities, not measured resource bills.
See PROTOCOL.md before interpreting an optimum or a funding calculation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import product
import json
from pathlib import Path
from typing import Mapping, Sequence

Number = int | Fraction
PUBLIC_SOURCE = (
    "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/"
    "8cd375784c24b879ae1eb4835c6af4fb925cbf4c/"
    "campaign/omega-inventor/PROTOCOL_V4.md"
)


def exact_nonnegative(value: Number, name: str) -> Number:
    if type(value) not in (int, Fraction) or value < 0:
        raise ValueError(f"{name}: exact nonnegative integer or Fraction required")
    return value


def require(condition: bool, message: str) -> None:
    """Scientific checks remain active even if Python is invoked with -O."""
    if not condition:
        raise AssertionError(message)


def serial(value):
    """Serialize rational values exactly; never introduce floating-point money."""
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {str(key): serial(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    return value


@dataclass(frozen=True)
class CompositionContract:
    service_count: int
    outcomes: tuple[int, ...]
    composition_authorized: bool
    union_preserves_acceptance_and_rights: bool
    repeated_services_add_no_value: bool
    one_aggregate_checkout: bool

    def validate(self) -> None:
        if type(self.service_count) is not int or self.service_count < 1:
            raise ValueError("positive service count required")
        if any(flag is not True for flag in (
            self.composition_authorized,
            self.union_preserves_acceptance_and_rights,
            self.repeated_services_add_no_value,
            self.one_aggregate_checkout,
        )):
            raise ValueError("explicit productive equivalence and composition rights required")
        if (not self.outcomes or self.outcomes[0] != 0
                or tuple(sorted(set(self.outcomes))) != self.outcomes):
            raise ValueError("distinct sorted outcomes including non-entry required")
        if any(type(mask) is not int or not 0 <= mask < 1 << self.service_count
               for mask in self.outcomes):
            raise ValueError("outcome outside declared services")
        allowed = set(self.outcomes)
        if any(left | right not in allowed
               for left in self.outcomes for right in self.outcomes):
            raise ValueError("missing union outcome; do not invent its semantics")


def powerset_contract(service_count: int) -> CompositionContract:
    return CompositionContract(
        service_count, tuple(range(1 << service_count)), True, True, True, True
    )


def checked_menu(menu: Mapping[int, Number], contract: CompositionContract):
    contract.validate()
    items = []
    for mask, price in menu.items():
        if type(mask) is not int or mask not in contract.outcomes:
            raise ValueError("offer has undeclared outcome")
        exact_nonnegative(price, "price")
        if mask == 0:
            if price != 0:
                raise ValueError("non-entry must cost zero")
            continue
        items.append((mask, price))
    return tuple(sorted(items))


def cheapest_cart_prices(menu: Mapping[int, Number],
                         contract: CompositionContract) -> dict[int, Number]:
    """Dynamic programming on the union graph; nonnegative self-loops cannot help."""
    offers = checked_menu(menu, contract)
    distance: dict[int, Number] = {0: 0}
    for state in contract.outcomes:
        if state not in distance:
            continue
        for offered, price in offers:
            successor = state | offered
            candidate = distance[state] + price
            if successor not in distance or candidate < distance[successor]:
                distance[successor] = candidate
    return distance


def exhaustive_carts(menu: Mapping[int, Number], contract: CompositionContract):
    """Independent oracle: enumerate all offer subsets, without the DP recurrence."""
    offers = checked_menu(menu, contract)
    carts = []
    for selected in product((False, True), repeat=len(offers)):
        delivered, charge = 0, 0
        for take, (outcome, price) in zip(selected, offers):
            if take:
                delivered |= outcome
                charge += price
        carts.append((delivered, charge))
    return carts


def exhaustive_cart_prices(menu: Mapping[int, Number],
                           contract: CompositionContract) -> dict[int, Number]:
    result = {}
    for outcome, charge in exhaustive_carts(menu, contract):
        if outcome not in result or charge < result[outcome]:
            result[outcome] = charge
    return result


@dataclass(frozen=True)
class Buyer:
    values: tuple[Number, ...]
    budget: Number
    outside_utility: Number = 0

    def validate(self, contract: CompositionContract) -> None:
        if len(self.values) != 1 << contract.service_count or self.values[0] != 0:
            raise ValueError("complete declared outcome values and zero empty value required")
        for value in self.values:
            exact_nonnegative(value, "value")
        exact_nonnegative(self.budget, "budget")
        exact_nonnegative(self.outside_utility, "outside utility")


@dataclass(frozen=True)
class Choice:
    outcome: int
    payment: Number
    utility_above_outside: Number
    seller_contribution: Number

    def record(self):
        return serial(self.__dict__)


DECLINE = Choice(0, 0, 0, 0)


def checked_costs(costs: Mapping[int, Number] | None,
                  contract: CompositionContract) -> dict[int, Number]:
    result = dict(costs) if costs is not None else dict.fromkeys(contract.outcomes, 0)
    if set(result) != set(contract.outcomes) or result[0] != 0:
        raise ValueError("cost for each declared outcome and zero-cost non-entry required")
    for value in result.values():
        exact_nonnegative(value, "production cost")
    return result


def _choose_prices(prices: Mapping[int, Number], buyer: Buyer,
                   costs: Mapping[int, Number]) -> Choice:
    candidates = []
    for outcome, payment in prices.items():
        if outcome == 0 or payment > buyer.budget:
            continue
        utility = buyer.values[outcome] - payment - buyer.outside_utility
        if utility > 0:
            candidates.append(Choice(outcome, payment, utility, payment - costs[outcome]))
    if not candidates:
        return DECLINE
    return min(candidates, key=lambda row: (
        -row.utility_above_outside, row.seller_contribution, row.payment, row.outcome
    ))


def _choose_raw_carts(carts, buyer: Buyer, costs: Mapping[int, Number]) -> Choice:
    """Independent argmax over raw carts, including a pessimistic tie convention."""
    best, best_key = DECLINE, None
    for outcome, charge in carts:
        if outcome == 0 or charge > buyer.budget:
            continue
        utility = buyer.values[outcome] - buyer.outside_utility - charge
        if utility <= 0:
            continue
        contribution = charge - costs[outcome]
        key = (utility, -contribution, -charge, -outcome)
        if best_key is None or key > best_key:
            best_key = key
            best = Choice(outcome, charge, utility, contribution)
    return best


def buyer_choice(menu: Mapping[int, Number], contract: CompositionContract,
                 buyer: Buyer, *, mode: str = "cart",
                 costs: Mapping[int, Number] | None = None) -> Choice:
    offers = checked_menu(menu, contract)
    buyer.validate(contract)
    production = checked_costs(costs, contract)
    if mode == "single":
        prices = {0: 0, **dict(offers)}
    elif mode == "cart":
        prices = cheapest_cart_prices(menu, contract)
    else:
        raise ValueError("mode must be single or cart")
    return _choose_prices(prices, buyer, production)


def exhaustive_buyer_choice(menu: Mapping[int, Number], contract: CompositionContract,
                            buyer: Buyer, *, costs=None) -> Choice:
    buyer.validate(contract)
    production = checked_costs(costs, contract)
    return _choose_raw_carts(exhaustive_carts(menu, contract), buyer, production)


@lru_cache(maxsize=1)
def closure_study():
    contract = powerset_contract(3)
    zeros = dict.fromkeys(contract.outcomes, 0)
    buyers = []
    for weights in product(range(3), repeat=3):
        values = tuple(sum(weights[index] for index in range(3) if mask & (1 << index))
                       for mask in contract.outcomes)
        buyers.extend(Buyer(values, budget) for budget in range(7))
    counts = dict(menus=0, enumerated_carts=0, buyer_budget_cases=0,
                  contractive_inequalities=0, subadditive_inequalities=0,
                  idempotence_cases=0, coordinate_monotonicity_cases=0)
    for prices in product((1, 2, 3), repeat=7):
        menu = dict(zip(range(1, 8), prices))
        closed = cheapest_cart_prices(menu, contract)
        carts = exhaustive_carts(menu, contract)
        oracle = {}
        for outcome, charge in carts:
            oracle[outcome] = min(oracle.get(outcome, charge), charge)
        if closed != oracle:
            raise AssertionError(("DP/cart disagreement", menu))
        counts["menus"] += 1
        counts["enumerated_carts"] += len(carts)
        for mask, price in menu.items():
            require(closed[mask] <= price, "closure exceeded a posted price")
            counts["contractive_inequalities"] += 1
            raised = dict(menu)
            raised[mask] += 1
            raised_closed = cheapest_cart_prices(raised, contract)
            require(all(closed[state] <= raised_closed[state] for state in closed), "closure monotonicity failed")
            counts["coordinate_monotonicity_cases"] += 1
        for left in contract.outcomes:
            for right in contract.outcomes:
                require(closed[left | right] <= closed[left] + closed[right], "closure subadditivity failed")
                counts["subadditive_inequalities"] += 1
        require(cheapest_cart_prices(closed, contract) == closed, "closure idempotence failed")
        counts["idempotence_cases"] += 1
        for buyer in buyers:
            if _choose_prices(closed, buyer, zeros) != _choose_raw_carts(carts, buyer, zeros):
                raise AssertionError(("buyer/cart disagreement", menu, buyer))
            counts["buyer_budget_cases"] += 1
    return {
        "scope": "Exhaustive declared finite integer domain; not a proof for unknown services.",
        "price_grid": [1, 2, 3], "service_count": 3,
        "additive_item_weights": [0, 1, 2], "budgets": list(range(7)),
        "all_checks_pass": True, **counts,
        "maximum_raw_carts_per_menu": 128,
        "raw_cart_buyer_evaluations": counts["buyer_budget_cases"] * 128,
    }


def pinned_v3_witness():
    menu = {1: 518, 2: 823, 3: 1554}
    closed = cheapest_cart_prices(menu, powerset_contract(2))
    return {
        "source": PUBLIC_SOURCE,
        "scope": "Static public arithmetic, not a new native or solver replay.",
        "units": "cents in the cited historical authored market",
        "first_price": 518, "second_price": 823, "joint_quote": 1554,
        "same_service_union_cart_price": closed[3],
        "quote_minus_cart": menu[3] - closed[3],
    }


def _menu_tie_key(menu):
    return len(menu), tuple(sorted(menu.items()))


def finite_menu_study():
    contract, buyer = powerset_contract(2), Buyer((0, 7, 7, 14), 14)
    modes = {"single": None, "cart": None, "exhaustive_cart_control": None}
    summaries = dict(menus=0, cart_revenue_higher=0, cart_revenue_lower=0,
                     revenue_ties=0, changed_outcomes=0, quoted_joint_above_cart=0,
                     single_nonentry=0, cart_nonentry=0)
    for entries in product((None, *range(15)), repeat=3):
        menu = {mask: price for mask, price in zip((1, 2, 3), entries) if price is not None}
        choices = {
            "single": buyer_choice(menu, contract, buyer, mode="single"),
            "cart": buyer_choice(menu, contract, buyer),
            "exhaustive_cart_control": exhaustive_buyer_choice(menu, contract, buyer),
        }
        require(choices["cart"] == choices["exhaustive_cart_control"], "independent buyer controls disagree")
        for mode, choice in choices.items():
            incumbent = modes[mode]
            if (incumbent is None or choice.payment > incumbent[0].payment
                    or (choice.payment == incumbent[0].payment
                        and _menu_tie_key(menu) < _menu_tie_key(incumbent[1]))):
                modes[mode] = (choice, menu)
        single, cart = choices["single"], choices["cart"]
        summaries["menus"] += 1
        summaries["cart_revenue_higher"] += cart.payment > single.payment
        summaries["cart_revenue_lower"] += cart.payment < single.payment
        summaries["revenue_ties"] += cart.payment == single.payment
        summaries["changed_outcomes"] += cart.outcome != single.outcome
        summaries["single_nonentry"] += single.outcome == 0
        summaries["cart_nonentry"] += cart.outcome == 0
        closed = cheapest_cart_prices(menu, contract)
        summaries["quoted_joint_above_cart"] += 3 in menu and closed[3] < menu[3]
    reference = {1: 6, 2: 6, 3: 13}
    return serial({
        "scope": "Revenue optimum only over the 4096 stated one-shot menus; no cost or capital optimum.",
        "units": "abstract units", "values": buyer.values, "budget": buyer.budget,
        "offer_choices": ["absent", *range(15)], **summaries,
        "optima": {mode: {"menu": menu, "choice": choice.record()}
                   for mode, (choice, menu) in modes.items()},
        "reference_menu": reference,
        "reference_single_choice": buyer_choice(reference, contract, buyer, mode="single").record(),
        "reference_cart_choice": buyer_choice(reference, contract, buyer).record(),
        "nonentry_receipt": 0,
        "conventional_control_ties": modes["cart"][0].payment == modes["exhaustive_cart_control"][0].payment,
    })


@dataclass(frozen=True)
class CashStep:
    label: str
    change: Number


def cash_arithmetic(steps: Sequence[CashStep], opening: Number,
                    protected_reserve: Number = 0):
    """Inspect a declared sequence. Infeasible notional paths are not execution traces."""
    exact_nonnegative(opening, "opening cash")
    exact_nonnegative(protected_reserve, "protected reserve")
    cumulative: Number = 0
    required: Number = protected_reserve
    path: list[Number] = [opening]
    first_shortfall = "opening reserve" if opening < protected_reserve else None
    for step in steps:
        if type(step.change) not in (int, Fraction):
            raise ValueError("exact signed cash change required")
        cumulative += step.change
        required = max(required, protected_reserve - cumulative)
        path.append(opening + cumulative)
        if path[-1] < protected_reserve and first_shortfall is None:
            first_shortfall = step.label
    return {
        "opening_cash": opening, "protected_reserve": protected_reserve,
        "minimum_opening_cash": required, "feasible": first_shortfall is None,
        "first_liquidity_shortfall": first_shortfall,
        "notional_cash_path": path,
        "complete_plan_surplus": cumulative,
        "notional_closing_cash": path[-1],
        "scope": "Arithmetic of a supplied plan; not an account or executed business.",
    }


ROUTES = ("ordinary_monolithic", "staging_alone", "connector_alone", "connector_and_staging")


def route_steps(route: str, first_price: Number = 6, second_price: Number = 6,
                *, final_price: Number | None = None, lifecycle_burden: Number = 0):
    h = exact_nonnegative(lifecycle_burden, "lifecycle burden")
    exact_nonnegative(first_price, "first price")
    exact_nonnegative(second_price, "second price")
    total = first_price + second_price if final_price is None else exact_nonnegative(final_price, "final price")
    schedules = {
        "ordinary_monolithic": [CashStep("complete production and checks", -9), CashStep("accepted final payment", total)],
        "staging_alone": [CashStep("first production and checks", -7), CashStep("accepted first payment", first_price),
                          CashStep("second production and checks", -2), CashStep("accepted second payment", second_price)],
        "connector_alone": [CashStep("connector construction", -2), CashStep("first production and checks", -3),
                            CashStep("second production and checks", -4), CashStep("accepted final payment", total)],
        "connector_and_staging": [CashStep("connector construction", -2), CashStep("first production and checks", -3),
                                  CashStep("accepted first payment", first_price), CashStep("second production and checks", -4),
                                  CashStep("accepted second payment", second_price)],
    }
    if route not in schedules:
        raise ValueError("unknown registered route")
    return ([CashStep("additional upfront lifecycle burden", -h)] if h else []) + schedules[route]


def arrangement_enumeration(opening: Number):
    """Finite joint price/route comparison; no invented prepayments or financing."""
    counts = dict(candidates=0, buyer_voluntary_complete_contracts=0, financeable_complete_contracts=0,
                  positive_surplus_contracts=0)
    winner = {"route": "nonentry", "surplus": 0, "receipts": 0, "prices": [], "minimum_capital": 0}
    conventional_rows = [(0, "nonentry", (), 0, 0)]
    for route in ROUTES:
        staged = route in ("staging_alone", "connector_and_staging")
        prices = product(range(15), repeat=2) if staged else ((price,) for price in range(15))
        for quote in prices:
            counts["candidates"] += 1
            if staged:
                # Every accepted stage is worth seven and can be declined independently.
                if any(price >= 7 for price in quote) or sum(quote) > 14:
                    continue
                steps = route_steps(route, quote[0], quote[1])
                receipts = sum(quote)
            else:
                if quote[0] >= 14:
                    continue
                steps = route_steps(route, final_price=quote[0])
                receipts = quote[0]
            counts["buyer_voluntary_complete_contracts"] += 1
            evaluated = cash_arithmetic(steps, opening)
            # Independent conventional calculation uses explicit paid-cost and collected-receipt prefixes.
            paid, received, need = 0, 0, 0
            for step in steps:
                if step.change < 0:
                    paid -= step.change
                else:
                    received += step.change
                need = max(need, paid - received)
            require(need == evaluated["minimum_opening_cash"], "independent cash calculations disagree")
            if need <= opening:
                counts["financeable_complete_contracts"] += 1
                counts["positive_surplus_contracts"] += received - paid > 0
                conventional_rows.append((received - paid, route, tuple(quote), receipts, need))
                if evaluated["complete_plan_surplus"] > winner["surplus"]:
                    winner = {"route": route, "surplus": evaluated["complete_plan_surplus"],
                              "receipts": receipts, "prices": list(quote), "minimum_capital": need}
    conventional_best = max(row[0] for row in conventional_rows)
    require(conventional_best == winner["surplus"], "conventional arrangement control disagrees")
    return serial({"opening_cash": opening, **counts, "best_registered_feasible_arrangement": winner,
                   "conventional_best_surplus": conventional_best,
                   "same_choice_conventional_control_ties": True,
                   "scope": "Global enumeration of the 480 declared route/price contracts plus nonentry, not all economic arrangements."})


def staged_arrangement():
    reference = {route: cash_arithmetic(route_steps(route), 6) for route in ROUTES}
    h_values = (0, Fraction(1, 2), 1, Fraction(3, 2), 3)
    sensitivity = []
    for h in h_values:
        row = cash_arithmetic(route_steps("connector_and_staging", lifecycle_burden=h), 6)
        require(row["minimum_opening_cash"] == 5 + h, "upfront lifecycle capital sensitivity failed")
        require(row["complete_plan_surplus"] == 3 - h, "lifecycle surplus sensitivity failed")
        require(row["feasible"] == (h <= 1), "lifecycle feasibility threshold failed")
        sensitivity.append({"additional_upfront_lifecycle_burden": h, **row})
    return serial({
        "units": "abstract units", "status": "Authored analytical construction, not autonomous or physical invention.",
        "reference_opening_cash": 6, "reference_actual_collections": 12,
        "declared_total_process_cost": 9,
        "cost_scope": "Inclusive authored process envelopes; unknown actual development/discovery/model/host bills are not measured or assumed zero.",
        "reference_h": 0, "routes": reference,
        "cost_sensitivity": sensitivity,
        "symbolic_cost_sensitivity": {"h_domain": "h >= 0, payable before work",
                                      "joint_minimum_capital": "5 + h", "joint_surplus": "3 - h",
                                      "feasible_at_six": "h <= 1", "positive_surplus": "h < 3"},
        "joint_construction_only_feasible_at_reference_capital":
            [name for name, row in reference.items() if row["feasible"]] == ["connector_and_staging"],
        "finite_route_price_comparison": [arrangement_enumeration(6), arrangement_enumeration(9)],
        "successor_cash_eligibility": {
            "naive_advertised_joint_quote": 13, "actual_collectable_cart_price": 12,
            "naive_projected_closing_cash": 10, "actual_closing_cash": 9,
            "upfront_successor_requirement": 10, "actual_requirement_satisfied": False,
            "cash_shortfall": 1, "actual_first_episode_surplus": 3,
            "scope": "Total current-cash eligibility, not a claim that nine units are all earned profit.",
        },
    })


def successor_comparison():
    initial = cash_arithmetic(route_steps("connector_and_staging"), 6)
    opening = initial["notional_closing_cash"]
    reused = [CashStep("new first production and checks", -3), CashStep("accepted first payment", 6),
              CashStep("new second production and checks", -4), CashStep("accepted second payment", 6)]
    rebuild = route_steps("connector_and_staging")
    arms = {}
    for name, steps in (("retained_connector", reused), ("rebuild_connector", rebuild),
                        ("ordinary_equal_content_reuse", reused)):
        record = cash_arithmetic(steps, opening)
        arms[name] = {"second_episode": record,
                      "second_episode_declared_cost": -sum(step.change for step in steps if step.change < 0),
                      "two_episode_declared_cost": 9 - sum(step.change for step in steps if step.change < 0),
                      "two_episode_collections": 24,
                      "two_episode_surplus": 3 + record["complete_plan_surplus"]}
    # Extra cash changes the available comparison: final-only payment is now affordable.
    adaptive_steps = [CashStep("new first production and checks", -3),
                      CashStep("new second production and checks", -4),
                      CashStep("accepted pure-bundle payment", 13)]
    adaptive = cash_arithmetic(adaptive_steps, opening)
    return serial({"units": "abstract units", "reference_h_per_episode": 0,
                   "scope": "Fixed-menu/fixed-schedule inheritance ablation on a supplied compatible second use; not an optimal two-episode policy or a generalization/discovery result.",
                   "first_episode_acquisition_cost_retained_in_history": 2,
                   "arms": arms, "ordinary_equal_content_reuse_ties": True,
                   "stronger_adaptive_continuation": {
                       "second_episode": adaptive, "second_episode_declared_cost": 7,
                       "second_episode_receipts": 13, "two_episode_collections": 25,
                       "two_episode_declared_cost": 16,
                       "two_episode_surplus": 3 + adaptive["complete_plan_surplus"],
                       "ordinary_same_content_constructor_can_take_same_route": True,
                       "reason": "Opening second-episode cash nine can pay seven before final-only receipt; pure bundle thirteen remains worthwhile to value fourteen.",
                   },
                   "inventor_improvement_established": False})


def evaluate():
    return serial({
        "schema": "flywheel-omega/exact-analytical-companion/v1",
        "evidence_scope": "Authored exact finite verification; no empirical demand, real bills, native account qualification or autonomous discovery result.",
        "closure_study": closure_study(),
        "pinned_v3_witness": pinned_v3_witness(),
        "finite_menu_study": finite_menu_study(),
        "staged_arrangement": staged_arrangement(),
        "successor_comparison": successor_comparison(),
        "claims": {"real_revenue_established": False, "full_lifecycle_cost_measured": False,
                   "open_world_incentives_verified": False, "inventor_superiority_established": False,
                   "usd3b_milestone_established": False},
    })


def write_results(destination: Path):
    # Fail fast on known existing output, then recheck atomically when writing.
    if destination.exists():
        raise FileExistsError(f"refusing to replace existing output: {destination}")
    payload = evaluate()
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new output JSON file; existing files are refused")
    args = parser.parse_args()
    write_results(args.output)
    print(f"Exact analytical results written to {args.output}")


if __name__ == "__main__":
    main()
