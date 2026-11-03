"""Independent transcript attack and outcome checks for the registered experiment."""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from itertools import product
from typing import Any, Callable, Iterable, Mapping


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def transcript_candidates(
    candidate_worlds: Mapping[str, Any],
    transcript: Iterable[dict[str, Any]],
    predict_public_output: Callable[[Any, Any], Any],
) -> list[str]:
    observations = list(transcript)
    return sorted(
        identity
        for identity, world in candidate_worlds.items()
        if all(
            canonical(predict_public_output(world, observation["query"]))
            == canonical(observation["response"])
            for observation in observations
        )
    )


def adaptive_transcript_attack(
    oracle: Callable[[Any], Any],
    candidate_worlds: Mapping[str, Any],
    permitted_queries: Iterable[Any],
    predict_public_output: Callable[[Any, Any], Any],
) -> dict[str, Any]:
    """A transcript-only, distribution-free finite minimax identification attack.

    The attacker receives public hypotheses, public mechanism code, and an output
    oracle. It never receives or inspects the actual hidden world. Candidate IDs
    are labels in the public hypothesis space, not identifiers read from the oracle.
    """
    if not candidate_worlds:
        raise ValueError("The public hypothesis space must be nonempty")
    queries = {canonical(query): query for query in permitted_queries}
    remaining = dict(candidate_worlds)
    transcript: list[dict[str, Any]] = []
    while len(remaining) > 1 and queries:
        choices = []
        for query_key, query in queries.items():
            buckets: dict[str, list[str]] = defaultdict(list)
            for identity, hypothesis in remaining.items():
                buckets[canonical(predict_public_output(hypothesis, query))].append(identity)
            worst = max(map(len, buckets.values()))
            choices.append((worst, query_key, query, buckets))
        worst, query_key, query, buckets = min(choices, key=lambda item: (item[0], item[1]))
        if worst == len(remaining):
            break
        response = oracle(query)
        response_key = canonical(response)
        if response_key not in buckets:
            raise ValueError("Observed output is outside the public hypothesis model")
        remaining = {identity: remaining[identity] for identity in buckets[response_key]}
        transcript.append({"query": query, "response": response, "remaining": len(remaining)})
        del queries[query_key]
    independently_replayed = transcript_candidates(candidate_worlds, transcript, predict_public_output)
    if independently_replayed != sorted(remaining):
        raise AssertionError("Transcript replay disagrees with adaptive filtering")
    return {
        "initial_candidates": len(candidate_worlds),
        "remaining_candidates": sorted(remaining),
        "ambiguity": len(remaining),
        "exact_reconstruction": len(remaining) == 1,
        "query_count": len(transcript),
        "transcript": transcript,
        "stop_reason": "singleton" if len(remaining) == 1 else "no_distinguishing_permitted_query",
        "scope": "finite public hypothesis space; no probabilistic privacy guarantee",
    }


def composed_transcript_candidates(
    candidate_worlds: Mapping[str, Any],
    phases: Iterable[tuple[Iterable[dict[str, Any]], Callable[[Any, Any], Any]]],
) -> list[str]:
    remaining = dict(candidate_worlds)
    for transcript, predictor in phases:
        identities = transcript_candidates(remaining, transcript, predictor)
        remaining = {identity: remaining[identity] for identity in identities}
    return sorted(remaining)


def reconstruct_from_complement_quotes(
    oracle: Callable[[dict[str, Any]], dict[str, Any]],
    public_provider_ids: Iterable[str],
    public_price_cap_cents: int,
) -> dict[str, Any]:
    """Identify released per-provider tariffs from complete complement bundles.

    For n providers, each admitted query must buy exactly n-1 distinct providers.
    The attacker uses only released aggregate production charges. This identifies
    raw submitted asks only in an exact-pay mechanism; coarse pay reveals tariffs.
    """
    providers = tuple(public_provider_ids)
    if len(providers) < 2 or len(set(providers)) != len(providers):
        raise ValueError("Distinct public provider identities are required")
    sums: dict[str, int] = {}
    transcript = []
    for excluded in providers:
        query = {"excluded": [excluded], "price_cap_cents": public_price_cap_cents}
        response = oracle(query)
        transcript.append({"query": query, "response": response})
        if response.get("status") not in ("offer_accepted", "buyer_declined"):
            return {"identified": False, "reason": "complement_quote_unavailable", "transcript": transcript}
        route = response.get("route", [])
        if sorted(route) != sorted(set(providers) - {excluded}):
            return {"identified": False, "reason": "not_a_complete_complement", "transcript": transcript}
        amount = response["cost_breakdown"]["production_cents"]
        if type(amount) is not int or amount < 0:
            raise ValueError("Public production charge must be nonnegative integer cents")
        sums[excluded] = amount
    total_numerator = sum(sums.values())
    divisor = len(providers) - 1
    if total_numerator % divisor:
        return {"identified": False, "reason": "nonadditive_released_tariffs", "transcript": transcript}
    total = total_numerator // divisor
    tariffs = {provider: total - sums[provider] for provider in providers}
    return {
        "identified": all(value >= 0 for value in tariffs.values()),
        "released_tariffs_cents": tariffs,
        "query_count": len(transcript),
        "transcript": transcript,
        "scope": "identifies additive released tariffs, not raw asks under coarsening",
    }


def reference_matvec(spec: Mapping[str, Any]) -> list[int]:
    matrix, vector = spec["matrix"], spec["vector"]
    if any(len(row) != len(vector) for row in matrix):
        raise ValueError("Matrix and vector dimensions disagree")
    if any(type(value) is not int for row in matrix for value in row) or any(type(value) is not int for value in vector):
        raise ValueError("The accepted task uses exact integer arithmetic")
    return list(_reference_matvec_cached(tuple(tuple(row) for row in matrix), tuple(vector)))


@lru_cache(maxsize=64)
def _reference_matvec_cached(matrix: tuple[tuple[int, ...], ...], vector: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sum(entry * weight for entry, weight in zip(row, vector)) for row in matrix)


def _reference_tariff(ask: int, mode: str | Mapping[int, int]) -> int:
    if ask not in (200, 300, 600, 700):
        raise ValueError("Ask is outside the preregistered public domain")
    if isinstance(mode, Mapping):
        tariff = mode.get(ask)
        if type(tariff) is not int or tariff < ask:
            raise ValueError("Custom tariff must preserve provider participation")
        return tariff
    if mode == "exact":
        return ask
    if mode == "coarse":
        return 300 if ask in (200, 300) else 700
    raise ValueError("Unknown tariff mode")


def _valid_route(spec: Mapping[str, Any], route: Iterable[str], excluded: Iterable[str]) -> bool:
    route = tuple(route)
    providers = {provider["id"]: provider for provider in spec["providers"]}
    if len(route) != len(spec["blocks"]) or any(provider not in providers or provider in excluded for provider in route):
        return False
    for identity, provider in providers.items():
        if route.count(identity) > provider["capacity_blocks"]:
            return False
        if identity in route and (
            provider["operator"] != "dot_rows"
            or provider["input_type"] != "integer_matrix_vector"
            or provider["output_type"] != "partial_rows"
        ):
            return False
    for group, limit in spec["resource_limits"].items():
        if sum(providers[identity].get("resource_group") == group for identity in route) > limit:
            return False
    return True


@lru_cache(maxsize=128)
def _ordinary_routes_cached(encoded_graph: str, excluded: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    graph = json.loads(encoded_graph)
    provider_ids = tuple(sorted(provider["id"] for provider in graph["providers"]))
    return tuple(
        route
        for route in product(provider_ids, repeat=len(graph["blocks"]))
        if _valid_route(graph, route, excluded)
    )


def ordinary_cache_statistics() -> dict[str, dict[str, int | None]]:
    return {
        "routes": dict(_ordinary_routes_cached.cache_info()._asdict()),
        "matrix_vector": dict(_reference_matvec_cached.cache_info()._asdict()),
    }


def ordinary_complete_offer(
    spec: Mapping[str, Any],
    asks: Mapping[str, int],
    mode: str | Mapping[int, int],
    query: Mapping[str, Any],
    buyer: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Exhaustive ordinary broker with the same content and tariff permissions.

    This implementation does not call the candidate compiler, oracle, tariff
    function, or executable operators. It enumerates complete assignments and
    checks the full buyer package against the declared outside option.
    """
    provider_ids = tuple(sorted(provider["id"] for provider in spec["providers"]))
    if set(asks) != set(provider_ids):
        raise ValueError("One submitted ask per provider is required")
    tariff_rule = {int(key): value for key, value in spec["tariff_cents"].items()} if mode == "coarse" else mode
    tariffs = {identity: _reference_tariff(asks[identity], tariff_rule) for identity in provider_ids}
    graph = {key: spec[key] for key in ("providers", "blocks", "resource_limits")}
    feasible_routes = _ordinary_routes_cached(canonical(graph), tuple(sorted(set(query.get("excluded", ())))))
    routes = [(sum(tariffs[identity] for identity in route), route) for route in feasible_routes]
    if not routes:
        return {"status": "unavailable", "route": None, "quoted_price_cents": None, "output": None}
    production, route = min(routes)
    breakdown = {key + "_cents": value for key, value in spec["costs_cents"].items()}
    breakdown.update(production_cents=production, fee_cents=spec["fee_cents"])
    quoted = sum(breakdown.values())
    buyer = {"benefit_cents": 4800, "outside_option_utility_cents": 1800, "budget_cents": 3000} if buyer is None else buyer
    cap = min(query["price_cap_cents"], buyer["budget_cents"], buyer["benefit_cents"] - buyer["outside_option_utility_cents"])
    accepted = quoted <= cap
    return {
        "status": "offer_accepted" if accepted else "buyer_declined",
        "route": list(route),
        "quoted_price_cents": quoted,
        "cost_breakdown": breakdown,
        "output": reference_matvec(spec) if accepted else None,
        "provider_surplus_cents": {identity: tariffs[identity] - asks[identity] for identity in route},
        "buyer_utility_cents": buyer["benefit_cents"] - quoted if accepted else buyer["outside_option_utility_cents"],
        "feasible_routes": len(routes),
    }


def public_quote_projection(response: Mapping[str, Any]) -> dict[str, Any]:
    """Released quote fields that do not require guessing buyer preferences."""
    return {key: response.get(key) for key in ("quoted_price_cents", "route", "cost_breakdown")}


def public_quote_prediction(
    spec: Mapping[str, Any],
    hypothetical_asks: Mapping[str, int],
    mode: str | Mapping[int, int],
    query: Mapping[str, Any],
) -> dict[str, Any]:
    """Predict public quoting without access to any actual buyer private input.

    Quoting precedes consent and is invariant to the dummy buyer used here. The
    attacker discards consent/output fields; the exhaustive privacy evaluator
    separately checks the complete released transcript, including those fields.
    """
    dummy_buyer = {"benefit_cents": 0, "outside_option_utility_cents": 0, "budget_cents": 0}
    return public_quote_projection(ordinary_complete_offer(spec, hypothetical_asks, mode, query, dummy_buyer))


def verify_complete_offer(
    spec: Mapping[str, Any],
    asks: Mapping[str, int],
    mode: str | Mapping[int, int],
    query: Mapping[str, Any],
    response: Mapping[str, Any],
    buyer: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    errors = []
    buyer = {"benefit_cents": 4800, "outside_option_utility_cents": 1800, "budget_cents": 3000} if buyer is None else buyer
    reference = ordinary_complete_offer(spec, asks, mode, query, buyer)
    if response.get("status") != reference["status"]:
        errors.append("incorrect_whole_offer_acceptance")
    if reference["status"] == "unavailable":
        if response.get("output") not in (None, []):
            errors.append("unavailable_offer_has_delivered_output")
        return {"valid": not errors, "errors": errors, "reference": reference}
    route = response.get("route", ())
    if not isinstance(route, (list, tuple)):
        errors.append("malformed_route")
        route = ()
    if not _valid_route(spec, route, query.get("excluded", ())):
        errors.append("invalid_capacity_type_or_resource_assignment")
    if list(route) != reference["route"]:
        errors.append("not_the_strong_ordinary_minimum_with_registered_tiebreak")
    if response.get("quoted_price_cents") != reference["quoted_price_cents"]:
        errors.append("incorrect_complete_price")
    breakdown = response.get("cost_breakdown")
    if breakdown != reference["cost_breakdown"] or not isinstance(breakdown, dict) or any(type(value) is not int for value in breakdown.values()):
        errors.append("incorrect_complete_cost_breakdown")
    if response.get("status") == "offer_accepted":
        output = response.get("output")
        if not isinstance(output, list) or any(type(value) is not int for value in output) or output != reference_matvec(spec):
            errors.append("incorrect_delivered_integer_matvec")
        if any(value < 0 for value in reference["provider_surplus_cents"].values()):
            errors.append("provider_worse_than_declared_outside_option")
        if reference["buyer_utility_cents"] < buyer["outside_option_utility_cents"]:
            errors.append("buyer_worse_than_declared_outside_option")
    elif response.get("output") not in (None, []):
        errors.append("declined_offer_has_delivered_output")
    return {"valid": not errors, "errors": errors, "reference": reference}
