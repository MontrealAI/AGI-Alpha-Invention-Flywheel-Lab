"""Finite ideal confidential production functionality; no cryptographic claim."""

from collections import Counter
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from itertools import product
import json


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def validate_spec(spec):
    matrix, vector = spec["matrix"], spec["vector"]
    if not matrix or not vector or any(len(row) != len(vector) for row in matrix):
        raise ValueError("matrix/vector dimensions do not match")
    if any(type(v) is not int for row in matrix for v in row) or any(type(v) is not int for v in vector):
        raise ValueError("this evaluator accepts exact integer inputs")
    ids = [p["id"] for p in spec["providers"]]
    if len(ids) != len(set(ids)) or any(not p.isidentifier() for p in ids):
        raise ValueError("provider identifiers must be unique identifiers")
    starts = 0
    for block in spec["blocks"]:
        if block["start"] != starts or block["stop"] <= block["start"] or block["stop"] > len(matrix):
            raise ValueError("blocks must cover rows once in order")
        starts = block["stop"]
    if starts != len(matrix) or not spec["blocks"]:
        raise ValueError("blocks do not cover the complete requested output")
    if any(type(v) is not int or v < 0 for v in spec["costs_cents"].values()):
        raise ValueError("complete cost entries must be nonnegative integer cents")
    if type(spec["fee_cents"]) is not int or spec["fee_cents"] < 0:
        raise ValueError("fee must be nonnegative integer cents")
    for p in spec["providers"]:
        if type(p["capacity_blocks"]) is not int or p["capacity_blocks"] < 0:
            raise ValueError("invalid capacity")
        group = p.get("resource_group")
        if group is not None and group not in spec["resource_limits"]:
            raise ValueError("resource limit missing")
    if any(type(v) is not int or v < 0 for v in spec["resource_limits"].values()):
        raise ValueError("invalid shared resource limit")


def _feasible(spec, assignments, excluded):
    providers = {p["id"]: p for p in spec["providers"]}
    if len(assignments) != len(spec["blocks"]) or any(p in excluded or p not in providers for p in assignments):
        return False
    used, resources = Counter(assignments), Counter()
    for pid, count in used.items():
        provider = providers[pid]
        if count > provider["capacity_blocks"] or provider["operator"] != "dot_rows" or provider["input_type"] != "integer_matrix_vector" or provider["output_type"] != "partial_rows":
            return False
        if provider.get("resource_group") is not None:
            resources[provider["resource_group"]] += count
    return all(count <= spec["resource_limits"][group] for group, count in resources.items())


def compile_composition(spec, assignments):
    assignments = tuple(assignments)
    if not _feasible(spec, assignments, ()):
        raise ValueError("cannot compile an infeasible complete route")
    operators, lines, result_vars = [], ["def deliver(matrix, vector, kernels):"], []
    for i, (block, provider) in enumerate(zip(spec["blocks"], assignments)):
        variable = f"part_{i}"
        lines.append(f"    {variable} = kernels[{provider!r}](matrix[{block['start']}:{block['stop']}], vector)")
        result_vars.append(variable)
        operators.append({"id": block["id"], "op": "dot_rows", "provider": provider, "start": block["start"], "stop": block["stop"], "inputs": ["matrix", "vector"], "output_type": "partial_rows"})
    lines.append("    return " + " + ".join(result_vars))
    source = "\n".join(lines) + "\n"
    operators.append({"id": "join", "op": "concat", "inputs": [b["id"] for b in spec["blocks"]], "output_type": "complete_rows"})
    return {"assignments": list(assignments), "operators": operators, "source": source, "program_sha256": sha256(source.encode()).hexdigest()}


@lru_cache(maxsize=128)
def _compose_cached(encoded_spec, excluded):
    spec = json.loads(encoded_spec)
    validate_spec(spec)
    providers = sorted(p["id"] for p in spec["providers"] if p["id"] not in excluded)
    routes = []
    for assignments in product(providers, repeat=len(spec["blocks"])):
        if _feasible(spec, assignments, excluded):
            routes.append(compile_composition(spec, assignments))
    return tuple(routes)


def compose(spec, excluded=()):
    """Generate executable compositions from typed operators and constraints."""
    return deepcopy(_compose_cached(_json(spec), tuple(sorted(set(excluded)))))


def _dot_rows(matrix, vector):
    return [sum(a * b for a, b in zip(row, vector)) for row in matrix]


@lru_cache(maxsize=512)
def _execute_cached(encoded_spec, encoded_route):
    spec, route = json.loads(encoded_spec), json.loads(encoded_route)
    if not _feasible(spec, route["assignments"], ()):
        raise ValueError("route no longer satisfies public capabilities")
    expected = compile_composition(spec, route["assignments"])
    if expected != route:
        raise ValueError("generated program does not match its public route")
    namespace = {}
    exec(compile(route["source"], "<generated-production-composition>", "exec"), {"__builtins__": {}}, namespace)
    kernels = {p["id"]: _dot_rows for p in spec["providers"]}
    result = namespace["deliver"](spec["matrix"], spec["vector"], kernels)
    if len(result) != len(spec["matrix"]) or any(type(v) is not int for v in result):
        raise ValueError("production failed its output contract")
    return tuple(result)


def execute(spec, route):
    return list(_execute_cached(_json(spec), _json(route)))


def verify_output(spec, output):
    if not isinstance(output, list) or len(output) != len(spec["matrix"]):
        return False
    for i, row in enumerate(spec["matrix"]):
        expected = 0
        for j in range(len(spec["vector"])):
            expected += row[j] * spec["vector"][j]
        if type(output[i]) is not int or output[i] != expected:
            return False
    return True


def effective_tariffs(spec, submitted_asks, mode):
    """Trusted ideal functionality only; its input is not given to the policy."""
    ids = {p["id"] for p in spec["providers"]}
    if set(submitted_asks) != ids or any(type(v) is not int or v not in spec["ask_domain_cents"] for v in submitted_asks.values()):
        raise ValueError("invalid registered submitted-ask world")
    if mode == "exact":
        return dict(submitted_asks)
    if mode != "coarse":
        raise ValueError("mode must be exact or coarse")
    tariffs = {p: spec["tariff_cents"][str(v)] for p, v in submitted_asks.items()}
    if any(tariffs[p] < submitted_asks[p] for p in ids):
        raise ValueError("tariff cannot cover a provider's submitted ask")
    return tariffs


def provider_accepts(submitted_ask_cents, offered_cents, units):
    return offered_cents >= submitted_ask_cents * units


def buyer_accepts(buyer, quoted_price_cents, price_cap_cents):
    return quoted_price_cents <= min(price_cap_cents, buyer["budget_cents"]) and buyer["benefit_cents"] - quoted_price_cents >= buyer["outside_option_utility_cents"]


def _response(status, price=None, route=None, breakdown=None, output=None, candidates=0, arithmetic_ops=0):
    return {"status": status, "quoted_price_cents": price, "route": None if route is None else route["assignments"], "program_sha256": None if route is None else route["program_sha256"], "cost_breakdown": breakdown, "output": output, "meter": {"feasible_compositions": candidates, "production_integer_multiplications": arithmetic_ops, "verification_integer_multiplications": arithmetic_ops, "cost_provenance": "authored envelopes, not measured human labor or billing"}}


def oracle(spec, submitted_asks, mode, query, buyer=None):
    """Ideal secure computation: disclosure is exactly the returned transcript."""
    buyer = dict(buyer) if buyer is not None else {"benefit_cents": 4800, "outside_option_utility_cents": 1800, "budget_cents": 3000}
    if set(query) != {"excluded", "price_cap_cents"}:
        raise ValueError("query contains fields outside the registered language")
    ids = {p["id"] for p in spec["providers"]}
    if not isinstance(query["excluded"], (list, tuple)) or any(p not in ids for p in query["excluded"]):
        raise ValueError("unknown provider exclusion")
    cap = query["price_cap_cents"]
    if type(cap) is not int or cap < 0:
        raise ValueError("invalid complete-offer cap")
    tariffs = effective_tariffs(spec, submitted_asks, mode)
    routes = _compose_cached(_json(spec), tuple(sorted(set(query["excluded"]))))
    if not routes:
        return _response("unavailable")
    route = min(routes, key=lambda r: (sum(tariffs[p] for p in r["assignments"]), tuple(r["assignments"])))
    production = sum(tariffs[p] for p in route["assignments"])
    breakdown = {key + "_cents": value for key, value in spec["costs_cents"].items()}
    breakdown.update({"production_cents": production, "fee_cents": spec["fee_cents"]})
    price = sum(breakdown.values())
    if not buyer_accepts(buyer, price, cap):
        return _response("buyer_declined", price, route, breakdown, candidates=len(routes))
    units = Counter(route["assignments"])
    if any(not provider_accepts(submitted_asks[p], tariffs[p] * count, count) for p, count in units.items()):
        return _response("provider_declined", price, route, breakdown, candidates=len(routes))
    output = execute(spec, route)
    if not verify_output(spec, output):
        return _response("verification_failed", price, route, breakdown, candidates=len(routes))
    operations = len(spec["matrix"]) * len(spec["vector"])
    return _response("offer_accepted", price, route, breakdown, output, len(routes), operations)


def canonical_public_response(response):
    """Include every released field, including refusals and public metering."""
    return _json(response)


class ConfidentialExchange:
    """Oracle boundary with fixed tariff rule, independent of sessions/queries."""

    def __init__(self, spec, submitted_asks, mode, buyer=None):
        self._spec = deepcopy(spec)
        self._asks = dict(submitted_asks)
        self._mode = mode
        self._buyer = deepcopy(buyer)
        self._transcript = []
        effective_tariffs(self._spec, self._asks, self._mode)

    def ask(self, query):
        response = oracle(self._spec, self._asks, self._mode, deepcopy(query), self._buyer)
        self._transcript.append({"query": deepcopy(query), "response": deepcopy(response)})
        return response

    def transcript(self):
        return deepcopy(self._transcript)

    def successor(self, new_spec):
        if new_spec["tariff_cents"] != self._spec["tariff_cents"] or new_spec["ask_domain_cents"] != self._spec["ask_domain_cents"]:
            raise ValueError("successor cannot reset the subject's disclosure partition")
        return ConfidentialExchange(new_spec, self._asks, self._mode, self._buyer)


def information_boundary():
    return {"policy_inputs": ["public request", "public capability graph", "registered ask domain", "tariff rule", "previous released responses"], "private_inputs": ["submitted provider asks", "buyer complete-outcome benefit, outside-option utility, and budget"], "trusted_component": "ideal centralized secure functionality and buyer-consent oracle (cryptography not implemented)", "public_outputs": ["complete quoted price", "chosen provider route", "program digest", "aggregate cost breakdown", "accepted exact computation", "decline/unavailable status", "public operation counts"], "not_claimed": ["cryptographic implementation", "truthful cost reports", "strategic equilibrium", "protection under external side information", "real supplier consent", "real demand", "discovery-method superiority"]}
