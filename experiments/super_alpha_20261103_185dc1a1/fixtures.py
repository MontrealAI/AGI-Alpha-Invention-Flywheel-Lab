"""Frozen synthetic public requests and finite submitted-ask hypotheses."""

from itertools import combinations, product

PROVIDER_IDS = ("p0", "p1", "p2", "p3")
ASK_DOMAIN_CENTS = (200, 300, 600, 700)
TARIFF_CENTS = {200: 300, 300: 300, 600: 700, 700: 700}
PRICE_CAPS_CENTS = (0, 1200, 1600, 2000, 2400, 3000)
COSTS_CENTS = {"construction": 120, "verification": 50, "acquisition": 80, "infrastructure": 30, "support": 60}


def public_spec(job_id="primary"):
    if job_id not in ("primary", "successor", "successor_repartition", "resource_conflict"):
        raise ValueError("unknown frozen public request")
    is_successor = job_id.startswith("successor")
    rows = 16 if is_successor else 12
    offset = 5 if is_successor else 0
    matrix = [[((r + 1 + offset) * (c + 3) + r * c) % 19 - 9 for c in range(5)] for r in range(rows)]
    vector = [-3, 2, 1, -2, 4] if is_successor else [2, -1, 3, 1, -2]
    providers = [{"id": p, "capacity_blocks": 1, "operator": "dot_rows", "input_type": "integer_matrix_vector", "output_type": "partial_rows", "resource_group": None} for p in PROVIDER_IDS]
    resource_limits = {}
    if job_id == "resource_conflict":
        providers[0]["resource_group"] = "shared_license"
        providers[1]["resource_group"] = "shared_license"
        resource_limits["shared_license"] = 1
    return {
        "job_id": job_id,
        "matrix": matrix,
        "vector": vector,
        "blocks": [{"id": f"b{k}", "start": k * 4, "stop": (k + 1) * 4, "output_type": "partial_rows"} for k in range(rows // 4)],
        "providers": providers,
        "resource_limits": resource_limits,
        "costs_cents": dict(COSTS_CENTS),
        "fee_cents": 200,
        "ask_domain_cents": list(ASK_DOMAIN_CENTS),
        "tariff_cents": {str(k): v for k, v in ({200: 600, 600: 600, 300: 700, 700: 700} if job_id == "successor_repartition" else TARIFF_CENTS).items()},
        "economic_provenance": "All reservation asks, costs, benefits, capacities, and outside options are authored synthetic assumptions; no observed demand or billing.",
        "protected_input": "Submitted provider ask, not true marginal cost, identity, output, capacity, or public tariff tier.",
    }


def buyer_terms():
    return {"benefit_cents": 4800, "outside_option_utility_cents": 1800, "budget_cents": 3000}


def secret_worlds():
    return {"-".join(str(v) for v in values): dict(zip(PROVIDER_IDS, values)) for values in product(ASK_DOMAIN_CENTS, repeat=len(PROVIDER_IDS))}


def public_queries():
    exclusions = [list(s) for n in range(len(PROVIDER_IDS) + 1) for s in combinations(PROVIDER_IDS, n)]
    return [{"excluded": excluded, "price_cap_cents": cap} for excluded in exclusions for cap in PRICE_CAPS_CENTS]


def triple_queries():
    return [{"excluded": [p], "price_cap_cents": max(PRICE_CAPS_CENTS)} for p in PROVIDER_IDS]


def protocol_dimensions():
    return {"providers": 4, "ask_worlds": 256, "exclusion_masks": 16, "queries_per_request": 96, "primary_rows": 12, "successor_rows": 16, "block_rows": 4, "fixed_full_offer_cost_cents": 340, "broker_fee_cents": 200, "modes": ["exact", "coarse"], "source_of_numbers": "authored finite test, not commercial measurements"}
