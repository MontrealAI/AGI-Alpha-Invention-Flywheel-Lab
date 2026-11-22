from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

from .fixtures import PROVIDER_IDS, buyer_terms, protocol_dimensions, public_queries, public_spec, secret_worlds, triple_queries
from .independent import adaptive_transcript_attack, ordinary_cache_statistics, public_quote_prediction, public_quote_projection, reconstruct_from_complement_quotes, verify_complete_offer
from .mechanism import ConfidentialExchange, canonical_public_response, compose, execute, information_boundary, oracle

PREFIX = "experiments/super_alpha_20261103_185dc1a1"
PHASES = (("primary", "exact"), ("primary", "coarse"), ("successor", "exact"), ("successor", "coarse"), ("resource_conflict", "exact"), ("resource_conflict", "coarse"), ("successor_repartition", "coarse"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def registered_sources(root):
    directory = Path(root) / PREFIX
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir()) if p.suffix == ".py" or p.name == "PROTOCOL.json"}


def check_registration(protocol):
    domain = protocol["domain"]
    assert domain["providers"] == list(PROVIDER_IDS)
    assert domain["private_submitted_ask_domain_cents"] == public_spec()["ask_domain_cents"]
    assert domain["coarse_tariff_cents"] == public_spec()["tariff_cents"]
    assert domain["successor_repartition_stress_tariff_cents"] == public_spec("successor_repartition")["tariff_cents"]
    assert domain["public_query_language"]["price_cap_cents"] == sorted({q["price_cap_cents"] for q in public_queries()})
    assert len(secret_worlds()) == 256 and len(public_queries()) == 96
    assert sum(public_spec()["costs_cents"].values()) == 340 and public_spec()["fee_cents"] == 200
    private = domain["buyer_private"]
    assert (private["benefit_cents"], private["outside_utility_cents"], private["budget_cents"]) == (buyer_terms()["benefit_cents"], buyer_terms()["outside_option_utility_cents"], buyer_terms()["budget_cents"])


def partition(signatures, worlds):
    groups = defaultdict(list)
    for world, signature in signatures.items():
        groups[signature].append(world)
    sizes = Counter()
    per_world = {}
    individual_disclosure = 0
    minimum_per_provider = {provider: len(public_spec()["ask_domain_cents"]) for provider in PROVIDER_IDS}
    for signature, members in groups.items():
        sizes[len(members)] += len(members)
        values = {provider: len({worlds[member][provider] for member in members}) for provider in PROVIDER_IDS}
        for provider, count in values.items():
            minimum_per_provider[provider] = min(minimum_per_provider[provider], count)
        if any(count == 1 for count in values.values()):
            individual_disclosure += len(members)
        for member in members:
            per_world[member] = {"remaining_worlds": len(members), "possible_values_per_provider": values, "transcript_signature_sha256": digest(signature)}
    return {"worlds": len(worlds), "equivalence_classes": len(groups), "minimum_remaining_worlds": min(sizes), "maximum_remaining_worlds": max(sizes), "world_count_by_ambiguity": dict(sorted(sizes.items())), "exact_vector_reconstruction_worlds": sizes[1], "any_provider_exactly_identified_worlds": individual_disclosure, "minimum_possible_values_per_provider": minimum_per_provider, "per_world": per_world}


def run(root, output, source_commit=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    protocol = json.loads((root / PREFIX / "PROTOCOL.json").read_text())
    check_registration(protocol)
    sources = registered_sources(root)
    if output.exists():
        freeze = json.loads((output / "SOURCE.json").read_text())
        if freeze["source_hashes"] != sources:
            raise ValueError("COMPLETED_OR_INTERRUPTED_EVIDENCE_SOURCE_CHANGED")
        if (output / "RESULTS.json").exists():
            return json.loads((output / "RESULTS.json").read_text())
        raise ValueError("INTERRUPTED_EVIDENCE_REQUIRES_EXPLICIT_NEW_REPRODUCTION_DIRECTORY")
    output.mkdir(parents=True)
    freeze = {"schema": "super-alpha-185dc1a1/executed-source/v1", "source_commit": source_commit, "base_commit": protocol["base_commit"], "preregistration_commit": "a35463f684fa41902cad88ef126433eef2df443d", "protocol_file_sha256": sha256((root / PREFIX / "PROTOCOL.json").read_bytes()).hexdigest(), "source_hashes": sources, "source_sha256": digest(sources), "started_at_utc": datetime.now(timezone.utc).isoformat()}
    write_new(output / "SOURCE.json", freeze)
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    worlds, queries = secret_worlds(), public_queries()
    complete_order_query_index = queries.index({"excluded": [], "price_cap_cents": 3000})
    summaries, signatures, receipts, acceptance = {}, {}, {}, {}
    response_codes = {}
    total_checked = 0
    try:
        for job, mode in PHASES:
            name = job + ":" + mode
            spec = public_spec(job)
            counts, price_histogram = Counter(), Counter()
            world_signatures, by_world = {}, {}
            for identity, asks in worlds.items():
                signature, accepted_indices = [], []
                for index, query in enumerate(queries):
                    response = oracle(spec, asks, mode, query, buyer_terms())
                    checked = verify_complete_offer(spec, asks, mode, query, response, buyer_terms())
                    if not checked["valid"]:
                        failure = {"phase": name, "world": identity, "query": query, "response": response, "verification": checked}
                        write_new(output / "COUNTEREXAMPLE.json", failure)
                        raise AssertionError("INDEPENDENT_COMPLETE_OUTCOME_CHECK_FAILED")
                    total_checked += 1
                    counts[response["status"]] += 1
                    if response["status"] == "offer_accepted":
                        accepted_indices.append(index)
                        price_histogram[response["quoted_price_cents"]] += 1
                    public = canonical_public_response(response)
                    if public not in response_codes:
                        response_codes[public] = len(response_codes)
                    signature.append(response_codes[public])
                world_signatures[identity] = tuple(signature)
                by_world[identity] = tuple(accepted_indices)
            signatures[name], acceptance[name] = world_signatures, by_world
            summaries[name] = {"worlds": len(worlds), "queries_per_world": len(queries), "complete_cases": len(worlds) * len(queries), "status_counts": dict(counts), "accepted_quote_cents_histogram": dict(sorted(price_histogram.items())), "independent_mismatches": 0, "no_exclusion_max_cap_accepted_worlds": sum(complete_order_query_index in accepted for accepted in by_world.values()), "interpretation": "Counterfactual offer evaluations; repeated quotes are not distinct customers, native orders, collections or profit."}
            print(json.dumps({"phase": name, "checked": summaries[name]["complete_cases"], "counts": dict(counts)}), flush=True)

        lost_offers, loss_witnesses = {}, {}
        for job in ("primary", "successor", "resource_conflict"):
            total, improved = 0, 0
            no_exclusion_losses = []
            for identity, asks in worlds.items():
                exact = set(acceptance[job + ":exact"][identity])
                coarse = set(acceptance[job + ":coarse"][identity])
                lost = exact - coarse
                total += len(lost)
                if complete_order_query_index in lost:
                    no_exclusion_losses.append(identity)
                improved += len(coarse - exact)
                if lost and job not in loss_witnesses:
                    query = queries[min(lost)]
                    loss_witnesses[job] = {"authored_world": asks, "query": query, "exact": oracle(public_spec(job), asks, "exact", query), "coarse": oracle(public_spec(job), asks, "coarse", query)}
            lost_offers[job] = {"exact_accepted_coarse_declined": total, "coarse_accepted_exact_declined": improved, "denominator": len(worlds) * len(queries), "no_exclusion_max_cap_lost_worlds": no_exclusion_losses, "no_exclusion_max_cap_world_count": len(worlds)}

        privacy = {}
        for name in ("primary:exact", "primary:coarse", "successor:coarse", "successor_repartition:coarse"):
            privacy[name] = partition(signatures[name], worlds)
        for label, second in (("stable_predecessor_plus_stable_successor", "successor:coarse"), ("stable_predecessor_plus_repartitioned_successor", "successor_repartition:coarse")):
            joined = {identity: signatures["primary:coarse"][identity] + signatures[second][identity] for identity in worlds}
            privacy[label] = partition(joined, worlds)

        exact_reconstructions = 0
        representative = "200-300-600-700"
        algebraic_witness = None
        for identity, asks in worlds.items():
            exchange = ConfidentialExchange(public_spec(), asks, "exact")
            attack = reconstruct_from_complement_quotes(exchange.ask, PROVIDER_IDS, 3000)
            if attack.get("identified") and attack["released_tariffs_cents"] == asks:
                exact_reconstructions += 1
            if identity == representative:
                algebraic_witness = attack

        adaptive = {}
        for mode in ("exact", "coarse"):
            exchange = ConfidentialExchange(public_spec(), worlds[representative], mode)
            adaptive[mode] = adaptive_transcript_attack(lambda query: public_quote_projection(exchange.ask(query)), worlds, triple_queries(), lambda hypothesis, query: public_quote_prediction(public_spec(), hypothesis, mode, query))

        retained = ConfidentialExchange(public_spec(), worlds[representative], "coarse")
        successor = retained.successor(public_spec("successor"))
        successor_query = {"excluded": [], "price_cap_cents": 3000}
        continued = successor.ask(successor_query)
        fresh = ConfidentialExchange(public_spec("successor"), worlds[representative], "coarse").ask(successor_query)
        assert continued == fresh
        reset_rejected = False
        try:
            retained.successor(public_spec("successor_repartition"))
        except ValueError as error:
            reset_rejected = "disclosure partition" in str(error)
        assert reset_rejected
        assert all(summary["independent_mismatches"] == 0 for summary in summaries.values())
        programs = {}
        for job in ("primary", "successor", "resource_conflict"):
            spec = public_spec(job)
            generated = compose(spec)
            first = generated[0]
            programs[job] = {"generated_compositions": len(generated), "example_program": first, "actual_output": execute(spec, first)}

        per_world = []
        for identity in worlds:
            per_world.append({"world": identity, "accepted_quote_counts": {name: len(values[identity]) for name, values in acceptance.items()}, "privacy": {name: {k: v for k, v in value["per_world"][identity].items() if k != "transcript_signature_sha256"} for name, value in privacy.items()}})
        for value in privacy.values():
            del value["per_world"]
        result = {"schema": "super-alpha-185dc1a1/decisive-results/v1", "scope": "EXHAUSTIVE_AUTHORED_FINITE_MODEL_WITH_IDEAL_SECURE_INTERNALS", "source": freeze, "dimensions": protocol_dimensions(), "complete_cases_independently_checked": total_checked, "strong_ordinary_mismatches": 0, "phase_results": summaries, "privacy": privacy, "exact_complement_reconstruction": {"worlds_reconstructed": exact_reconstructions, "worlds": len(worlds), "queries_per_world": 4, "private_values_read_by_attacker": False, "representative_witness": algebraic_witness}, "adaptive_representative_attacks": adaptive, "privacy_offer_tradeoff": lost_offers, "lost_offer_witnesses": loss_witnesses, "generated_programs": programs, "successor_causal_controls": {"continued_and_fresh_same_content_output_equal": continued == fresh, "repartition_rejected_by_continuing_exchange": reset_rejected, "stable_privacy_minimum_worlds": privacy["stable_predecessor_plus_stable_successor"]["minimum_remaining_worlds"], "discarded_policy_repartition_exact_reconstructions": privacy["stable_predecessor_plus_repartitioned_successor"]["exact_vector_reconstruction_worlds"], "ordinary_equal_content_control": "The independently implemented ordinary solver matches every whole offer, including the fresh successor; ordinary reuse of the same global partition preserves the same privacy.", "causal_interpretation": "The globally stable release partition prevents compositional ask reconstruction. An unsafe fresh partition is a failure ablation, not a strongest no-inheritance baseline. Fresh ordinary reconstruction with equal useful content ties; no discovery-method gain is established.", "earned_capital_effect": "NONE: native account is research-only with zero earnings; no financed successor claim.", "retained_content_vs_method": "Retained public tariff policy is useful content and a correctness condition; the experiment does not establish an improved inventor or unavoidable dependence on predecessor."}, "information_boundary": information_boundary(), "ordinary_reuse_cache": ordinary_cache_statistics(), "financial_boundary": "Offer arithmetic is counterfactual only. All actual modeled account expenses, zero native sales and the exact rolling-year loss are in the separately audited canonical account. Neither quote counts nor broker fees are booked revenue.", "verdict": {"technical_construction": "EXECUTED_AND_INDEPENDENTLY_CHECKED", "exact_quote_confidentiality": "FALSIFIED" if exact_reconstructions else "NOT_FALSIFIED_IN_THIS_DOMAIN", "stable_finite_domain_ask_ambiguity": "PRESERVED" if privacy["stable_predecessor_plus_stable_successor"]["any_provider_exactly_identified_worlds"] == 0 else "FALSIFIED", "fresh_successor_release_reset": "FALSIFIED_BY_COMPOSITION" if privacy["stable_predecessor_plus_repartitioned_successor"]["any_provider_exactly_identified_worlds"] else "NOT_FALSIFIED_IN_THIS_DOMAIN", "super_alpha_method_advantage": "NOT_ESTABLISHED_ORDINARY_COMPLETE_CONTROL_TIES", "commercial_scale": "NOT_QUALIFIED", "three_billion_objective": "UNMET", "next_action_executed": "Constructed stable disclosure-partition retention and refusal of incompatible successor reset; tested the adverse offer and equal-content controls."}, "telemetry": {"cpu_seconds": time.process_time() - cpu_start, "wall_seconds": time.perf_counter() - wall_start, "meaning": "Runtime telemetry only; not human labor, paid billing, economic cost or an algorithmic speed claim."}, "registered_domain_rows": per_world}
        if registered_sources(root) != sources:
            raise ValueError("EXECUTED_SOURCE_CHANGED_DURING_CAMPAIGN")
        write_new(output / "RESULTS.json", result)
        return result
    except BaseException as error:
        write_new(output / "FAILURE.json", {"type": type(error).__name__, "message": str(error), "completed_independent_cases": total_checked, "source": freeze})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    result = run(args.root, args.output, args.source_commit)
    if args.compare:
        expected = json.loads(args.compare.read_text())
        excluded = {"source", "telemetry", "ordinary_reuse_cache"}
        semantic = lambda value: {key: item for key, item in value.items() if key not in excluded}
        if expected["source"]["source_hashes"] != result["source"]["source_hashes"]:
            raise ValueError("REPRODUCTION_EXECUTABLE_SOURCE_MISMATCH")
        if semantic(expected) != semantic(result):
            raise ValueError("REGISTERED_RESULT_REPRODUCTION_MISMATCH")
        print(json.dumps({"independent_reproduction": "accepted", "semantic_sha256": digest(semantic(result))}))
    print(json.dumps({"checked": result["complete_cases_independently_checked"], "privacy": result["privacy"], "tradeoff": result["privacy_offer_tradeoff"], "verdict": result["verdict"], "telemetry": result["telemetry"]}, sort_keys=True))


if __name__ == "__main__":
    main()
