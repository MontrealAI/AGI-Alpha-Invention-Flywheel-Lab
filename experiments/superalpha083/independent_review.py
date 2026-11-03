#!/usr/bin/env python3
"""Independent finite verifier for Super Alpha 083.

Uses a separately written polynomial GF(256) implementation and an exhaustive
subset-span lattice; does not call codec.py for mathematical reference values.
The executable codec is used only as the system under test for byte round trips.
No network, paid services, private account data, or external state changes.
"""
from __future__ import annotations

import argparse
import copy
import math
import sys
import tempfile
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random
import time
from collections import Counter
from typing import Iterable

if not __debug__:
    raise RuntimeError("Run without Python -O: validation assertions are required.")

POLYNOMIAL = 0x11D
N, K = 14, 8


def polynomial_mul(a: int, b: int) -> int:
    """Carryless integer multiplication followed by polynomial long division."""
    product = 0
    for bit in range(8):
        if (b >> bit) & 1:
            product ^= a << bit
    for bit in range(14, 7, -1):
        if (product >> bit) & 1:
            product ^= POLYNOMIAL << (bit - 8)
    return product


MUL = tuple(bytes(polynomial_mul(a, b) for b in range(256)) for a in range(256))
INV = tuple(0 if a == 0 else next(b for b in range(1, 256) if MUL[a][b] == 1)
            for a in range(256))


def field_self_test() -> dict:
    """Check every product against independent repeated xtime arithmetic."""
    def peasant(a: int, b: int) -> int:
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a & 256:
                a ^= POLYNOMIAL
        return out
    assert all(MUL[a][b] == peasant(a, b)
               for a in range(256) for b in range(256))
    assert all(MUL[a][INV[a]] == 1 for a in range(1, 256))
    # Bilinearity over the polynomial basis plus commutativity, all a,b.
    assert all(MUL[a][b] == MUL[b][a]
               for a in range(256) for b in range(256))
    return {"polynomial": "0x11d", "independent_product_cross_checks": 65536,
            "nonzero_inverses_checked": 255, "passed": True}


def add_to_basis(basis: tuple[bytes | None, ...], vector: Iterable[int]):
    """Append to an echelon basis without using the experiment's rank code."""
    v = bytearray(vector)
    for p, value in enumerate(v):
        if not value:
            continue
        if basis[p] is not None:
            multiple = MUL[value]
            row = basis[p]
            for j in range(p, K):
                v[j] ^= multiple[row[j]]
        else:
            inverse = MUL[INV[value]]
            normalized = bytes(inverse[x] for x in v)
            return basis[:p] + (normalized,) + basis[p + 1:]
    return basis


def independent_rank(rows: Iterable[Iterable[int]]) -> int:
    basis = (None,) * K
    for row in rows:
        basis = add_to_basis(basis, row)
    return sum(row is not None for row in basis)


def subset_ranks(generator: list[list[int]]) -> list[int]:
    """Every one of 2^14 subsets; independent exact min-helper certificate."""
    bases = [(None,) * K] * (1 << N)
    ranks = [0] * (1 << N)
    for subset in range(1, 1 << N):
        added = subset & -subset
        parent = subset ^ added
        basis = add_to_basis(bases[parent], generator[added.bit_length() - 1])
        bases[subset] = basis
        ranks[subset] = sum(row is not None for row in basis)
    return ranks


def normalize_placement(value) -> list[list[int]]:
    if isinstance(value, dict):
        groups = list(value.values())
    elif isinstance(value, list) and len(value) == N and all(isinstance(x, int) for x in value):
        # 14 rack labels, not a permutation; permutations are interpreted by
        # the fixed sizes only when all labels are distinct.
        if sorted(value) == list(range(N)):
            groups = [value[:5], value[5:10], value[10:]]
        else:
            groups = [[i for i, rack in enumerate(value) if rack == label]
                      for label in sorted(set(value))]
    elif isinstance(value, list):
        groups = value
    else:
        raise ValueError("No recognizable rack placement")
    groups = [list(map(int, group)) for group in groups]
    assert sorted(map(len, groups)) == [4, 5, 5], groups
    assert sorted(itertools.chain.from_iterable(groups)) == list(range(N)), groups
    return groups


def erasure_cases(racks: list[list[int]]) -> list[tuple[int, ...]]:
    ordinary = [case for size in (1, 2, 3)
                for case in itertools.combinations(range(N), size)]
    assert len(ordinary) == 469
    return ordinary + [tuple(rack) for rack in racks]


def independent_min_helpers(ranks: list[int]) -> tuple[list[int], list[list[int]]]:
    minimum = [N] * N
    witnesses = [[] for _ in range(N)]
    for helpers in range(1 << N):
        size = helpers.bit_count()
        for target in range(N):
            if not (helpers & (1 << target)) and size < minimum[target]:
                if ranks[helpers] == ranks[helpers | (1 << target)]:
                    minimum[target] = size
                    witnesses[target] = [j for j in range(N) if helpers & (1 << j)]
    assert all(size < N for size in minimum)
    return minimum, witnesses


def binary_distance(generator: list[list[int]]) -> dict | None:
    if not all(x in (0, 1) for row in generator for x in row):
        return None
    masks = [sum(x << j for j, x in enumerate(row)) for row in generator]
    weights = [sum((source & mask).bit_count() % 2 for mask in masks)
               for source in range(1, 1 << K)]
    return {"nonzero_source_words_checked": 255,
            "minimum_distance": min(weights),
            "weight_histogram": dict(sorted(Counter(weights).items()))}


def independent_encode(generator: list[list[int]], source: list[bytes]) -> list[bytes]:
    assert len(set(map(len, source))) == 1
    assert all(len(row) == len(source) for row in generator)
    length = len(source[0])
    encoded = []
    for row in generator:
        output = bytearray(length)
        for coefficient, shard in zip(row, source):
            if coefficient:
                product = shard.translate(MUL[coefficient])
                for j, value in enumerate(product):
                    output[j] ^= value
        encoded.append(bytes(output))
    return encoded


def mathematical_review(name: str, generator, placement) -> dict:
    g = [[int(value) for value in row] for row in generator]
    assert len(g) == N and all(len(row) == K for row in g), (name, "shape")
    assert all(0 <= value < 256 for row in g for value in row), (name, "field elements")
    assert g[:K] == [[int(i == j) for j in range(K)] for i in range(K)], (name, "not systematic")
    racks = normalize_placement(placement)
    ranks = subset_ranks(g)
    all_mask = (1 << N) - 1
    cases = erasure_cases(racks)
    failed = []
    for case in cases:
        survivors = all_mask ^ sum(1 << j for j in case)
        if ranks[survivors] != K:
            failed.append({"erased": list(case), "survivor_rank": ranks[survivors]})
    minima, witnesses = independent_min_helpers(ranks)
    failure_profile = {}
    for size in range(1, N + 1):
        lost = [mask for mask in range(1, 1 << N) if mask.bit_count() == size]
        failure_profile[str(size)] = {
            "patterns": len(lost),
            "unrecoverable_patterns": sum(ranks[all_mask ^ mask] < K for mask in lost),
        }
    distance = next(int(size) for size, profile in failure_profile.items()
                    if profile["unrecoverable_patterns"])
    binary = binary_distance(g)
    if binary:
        assert binary["minimum_distance"] == distance
    return {"method": name, "systematic_14_by_8": True,
            "generator_sha256": hashlib.sha256(bytes(itertools.chain.from_iterable(g))).hexdigest(),
            "rack_placement": racks,
            "nonempty_up_to_three_patterns_checked": 469,
            "rack_patterns_checked": 3, "contract_failures": failed,
            "contract_passed": not failed, "all_subset_ranks_checked": 1 << N,
            "minimum_helper_counts": minima, "minimum_helper_witnesses": witnesses,
            "mean_minimum_helper_count": sum(minima) / N,
            "worst_minimum_helper_count": max(minima),
            "minimum_distance_from_all_erasure_patterns": distance,
            "all_erasure_failure_profile": failure_profile, "binary_distance_check": binary}


METHODOLOGICAL_LIMITS = [
    "Passing the registered contract establishes a narrow finite linear-code capability, not a new industry, invention, or Super Alpha admission.",
    "Ordinary RS/LRC controls may already satisfy the same acceptance contract; improvement must be measured against feasible executable controls, not against an infeasible straw man.",
    "Equal acceptance of all <=3 losses and 3 chosen rack losses does not imply equal reliability. The exhaustive failure profile and minimum distance expose losses beyond that contract.",
    "Whole-shard helper count is not total cost: cross-rack placement, bandwidth, disk I/O, CPU, memory, latency, repair scheduling and availability may change the winner.",
    "No willing-demand, price, delivered-rights, security/support/maintenance, financing, tax, or complete-alternative evidence is supplied by byte correctness or local timings. No all-in economics or market claim follows.",
    "Finite deterministic search is not evidence of globally best code or comparison with the unreproduced current frontier. Search and placement budgets must be disclosed separately.",
    "Fresh random rack placement is a reconfiguration stress test of a fixed code, not code-family generalization; the matrix-vector successor is reuse of linearity, not independent commercial validation.",
    "Single-process Python timings are environment-dependent computational observations, not production throughput, causal lifecycle savings, or a basis for annualized revenue/profit.",
]


def load_methods(result):
    methods = result.get("methods", result.get("controls", result.get("results")))
    if isinstance(methods, dict):
        return [(name, item) for name, item in methods.items()]
    if isinstance(methods, list):
        return [(item.get("name", item.get("method", str(i))), item) for i, item in enumerate(methods)]
    raise ValueError("RESULT.json must contain methods as a list or mapping")


def get_generator(method):
    for key in ("generator", "generator_matrix", "G", "matrix"):
        if key in method:
            return method[key]
    raise KeyError("method generator matrix missing")


def get_placement(method):
    for key in ("placement", "racks", "rack_placement"):
        if key in method:
            return method[key]
    raise KeyError("method rack placement missing")


def linear_combination(rows: list[list[int]], target: list[int]) -> list[int]:
    """Independently derive target as a linear combination of helper rows."""
    basis = [None] * K
    width = len(rows)
    for i, row in enumerate(rows):
        vector = list(row)
        coefficients = [int(i == j) for j in range(width)]
        for p in range(K):
            scale = vector[p]
            if not scale:
                continue
            if basis[p] is not None:
                previous, previous_coefficients = basis[p]
                vector = [a ^ MUL[scale][b] for a, b in zip(vector, previous)]
                coefficients = [a ^ MUL[scale][b] for a, b in zip(coefficients, previous_coefficients)]
            else:
                inv = INV[scale]
                basis[p] = ([MUL[inv][a] for a in vector],
                            [MUL[inv][a] for a in coefficients])
                break
    vector = list(target)
    coefficients = [0] * width
    for p in range(K):
        scale = vector[p]
        if not scale:
            continue
        if basis[p] is None:
            raise ValueError("target is outside helper span")
        previous, previous_coefficients = basis[p]
        vector = [a ^ MUL[scale][b] for a, b in zip(vector, previous)]
        coefficients = [a ^ MUL[scale][b] for a, b in zip(coefficients, previous_coefficients)]
    assert not any(vector)
    return coefficients


def inspect_declared_metadata(method, review):
    """Check claims in RESULT against independently computed facts."""
    expected_helpers = method.get("single_repair_minimum_helpers")
    if expected_helpers is not None:
        assert expected_helpers == review["minimum_helper_counts"], "reported helper minimum mismatch"
    if "rank_rejections" in method:
        assert sorted(map(tuple, method["rank_rejections"])) == sorted(
            tuple(item["erased"]) for item in review["contract_failures"]), "reported rank rejection mismatch"
    g = get_generator(method)
    paths = method.get("helper_witnesses", [])
    for target, helpers in enumerate(paths):
        assert target not in helpers and len(set(helpers)) == len(helpers)
        assert len(helpers) == review["minimum_helper_counts"][target]
        coefficients = linear_combination([g[i] for i in helpers], g[target])
        assert all(coefficients), "reported minimum witness has unused helper"
    fresh = []
    for seed in range(92001, 92021):
        permutation = list(range(N))
        random.Random(seed).shuffle(permutation)
        racks = [permutation[:5], permutation[5:10], permutation[10:]]
        ranks = [independent_rank([g[i] for i in range(N) if i not in rack]) for rack in racks]
        fresh.append({"seed": seed, "rack_ranks": ranks})
    if "fresh_placement" in method:
        assert method["fresh_placement"] == fresh, "fresh placement outcome mismatch"
    review["fresh_placement_independently_rechecked"] = fresh
    review["fresh_placement_complete_contract_passes"] = sum(all(r == K for r in x["rack_ranks"]) for x in fresh)
    review["reported_metadata_matches"] = True


def byte_review(codec, method, review) -> dict:
    """Test executable codec against a separate polynomial-byte encoder."""
    import numpy as np
    g = get_generator(method)
    cases = erasure_cases(review["rack_placement"])
    plans = [codec.decoder(g, lost) for lost in cases]
    inverse_checks = 0
    for lost, plan in zip(cases, plans):
        expected_recoverable = independent_rank([g[i] for i in range(N) if i not in lost]) == K
        assert (plan is not None) == expected_recoverable
        if plan is None:
            continue
        helpers, inverse = plan
        assert len(helpers) == K and len(set(helpers)) == K and not set(helpers).intersection(lost)
        assert independent_encode(inverse, [bytes(g[i]) for i in helpers]) == [bytes(int(i == j) for j in range(K)) for i in range(K)]
        inverse_checks += 1
    witness_coefficients = [linear_combination([g[i] for i in helpers], g[target])
                            for target, helpers in enumerate(review["minimum_helper_witnesses"])]
    encode_cases = decode_cases = minimum_witness_cases = 0
    digest = hashlib.sha256()
    for seed in range(43001, 43021):
        rng = np.random.default_rng(seed)
        for length in (1, 17, 1024):
            source = rng.integers(0, 256, (K, length), dtype=np.uint8)
            reference = independent_encode(g, [row.tobytes() for row in source])
            stored = codec.apply(g, source)
            assert stored.shape == (N, length)
            assert stored.tobytes() == b"".join(reference), "encoder differs from polynomial reference"
            encode_cases += 1
            for plan in plans:
                if plan is None:
                    continue
                helpers, inverse = plan
                decoded = codec.apply(inverse, stored[helpers])
                assert decoded.shape == source.shape and decoded.tobytes() == source.tobytes(), "actual decoder byte mismatch"
                digest.update(decoded.tobytes())
                decode_cases += 1
            for target, helpers in enumerate(review["minimum_helper_witnesses"]):
                repaired = independent_encode([witness_coefficients[target]], [reference[i] for i in helpers])[0]
                assert repaired == reference[target], "independent minimum-repair byte mismatch"
                minimum_witness_cases += 1
    assert method.get("byte_cases", decode_cases) == decode_cases
    assert method.get("byte_failures", 0) == 0
    assert method.get("recovered_output_sha256", digest.hexdigest()) == digest.hexdigest(), "recorded byte digest mismatch"
    return {"passed": True, "input_seeds": "43001..43020", "shard_lengths": [1, 17, 1024],
            "independent_encoder_comparisons": encode_cases,
            "decoder_inverse_certificates": inverse_checks,
            "executable_decoder_byte_cases": decode_cases,
            "independently_derived_minimum_helper_byte_cases": minimum_witness_cases,
            "reproduced_output_sha256": digest.hexdigest(),
            "minimum_helper_test_scope": "Reference verifier executes independently derived minimum-helper repair; production benchmark's decoder uses eight full shards."}


def successor_review(codec, method, review) -> dict:
    """Check binary matvec outputs against integer bit parity, not numpy matmul."""
    import numpy as np
    declared = method.get("successor", {})
    if not declared.get("tested"):
        return {"tested": False, "reason": "No executed successor reported for this method."}
    g = get_generator(method)
    assert all(x in (0, 1) for row in g for x in row)
    plans = [codec.decoder(g, lost) for lost in erasure_cases(review["rack_placement"])]
    cases = 0
    for seed in range(71001, 71011):
        rng = np.random.default_rng(seed)
        blocks = rng.integers(0, 2, (K, 16, 128), dtype=np.uint8)
        vector = rng.integers(0, 2, 128, dtype=np.uint8)
        packed_vector = sum(int(bit) << i for i, bit in enumerate(vector))
        reference = bytes((sum(int(bit) << i for i, bit in enumerate(row)) & packed_vector).bit_count() % 2
                          for block in blocks for row in block)
        coded = codec.apply(g, blocks.reshape(K, -1)).reshape(N, 16, 128)
        outputs = bytes((sum(int(bit) << i for i, bit in enumerate(row)) & packed_vector).bit_count() % 2
                        for block in coded for row in block)
        output_array = np.frombuffer(outputs, dtype=np.uint8).reshape(N, 16)
        for helpers, inverse in plans:
            recovered = codec.apply(inverse, output_array[helpers])
            assert recovered.tobytes() == reference, "successor byte parity mismatch"
            cases += 1
    assert declared.get("cases", cases) == cases
    assert declared.get("failures", 0) == 0
    return {"tested": True, "passed": True, "cases": cases,
            "reference": "Integer bit-packing, AND and popcount parity for GF(2) matrix-vector product.",
            "scope": "Verifies linear-code reuse, not discovery improvement or all-in direct-recomputation savings."}


def verify_fingerprints(root: Path, result: dict) -> dict:
    expected = result.get("source_sha256")
    assert isinstance(expected, dict) and set(expected) == {"codec.py", "run.py"}, "missing or unexpected source fingerprints"
    hashes = {}
    for filename, declared in expected.items():
        actual = hashlib.sha256((root / filename).read_bytes()).hexdigest()
        assert declared == actual, "source fingerprint mismatch: " + filename
        hashes[filename] = {"declared": declared, "actual": actual, "matches": True}
    assert result.get("preregistered_commit") == "3c1c57d5352e949513673d9b0f041e9933f60fe2", "preregistration commit mismatch"
    actual = hashlib.sha256((root / "PREREGISTRATION.md").read_bytes()).hexdigest()
    assert result.get("preregistration_sha256") == actual, "preregistration fingerprint mismatch"
    return hashes


def verify_minimum_repair_weights(method: dict, weights: list) -> None:
    g = get_generator(method)
    helpers = method["helper_witnesses"]
    assert len(weights) == N and len(helpers) == N
    for target, (path, coeff) in enumerate(zip(helpers, weights)):
        assert target not in path and len(set(path)) == len(path)
        assert len(coeff) == len(path) and all(0 < c < 256 for c in coeff)
        assert coeff == linear_combination([g[i] for i in path], g[target]), "minimum-repair coefficient mismatch"
        assert independent_encode([coeff], [bytes(g[i]) for i in path]) == [bytes(g[target])], "minimum-repair identity mismatch"


def mutation_tests(root: Path, original: dict) -> dict:
    """Prove corrupt inputs are rejected rather than blessed by the report."""
    method = original["methods"][0]
    reference = mathematical_review(method["name"], get_generator(method), get_placement(method))
    tested = []
    def reject(label, operation):
        try:
            operation()
        except (AssertionError, ValueError, KeyError, IndexError):
            tested.append(label)
        else:
            raise AssertionError("Verifier accepted deliberate corruption: " + label)
    bad = copy.deepcopy(method)
    bad["generator"] = [[0] * K for _ in range(N)]
    reject("singular all-zero generator", lambda: mathematical_review(bad["name"], bad["generator"], bad["racks"]))
    bad_claim = copy.deepcopy(method)
    bad_claim["single_repair_minimum_helpers"][0] += 1
    reject("corrupt claimed minimum helper count", lambda: inspect_declared_metadata(bad_claim, reference))
    bad_witness = copy.deepcopy(method)
    bad_witness["helper_witnesses"][0][0] = 0
    reject("recovery witness illegally reads erased target", lambda: inspect_declared_metadata(bad_witness, reference))
    bad_hash = copy.deepcopy(original)
    bad_hash["source_sha256"]["codec.py"] = "0" * 64
    reject("source fingerprint mismatch", lambda: verify_fingerprints(root, bad_hash))
    bad_prereg = copy.deepcopy(original)
    bad_prereg["preregistration_sha256"] = "0" * 64
    reject("preregistration fingerprint mismatch", lambda: verify_fingerprints(root, bad_prereg))
    weights = [linear_combination([method["generator"][i] for i in path], method["generator"][target])
               for target, path in enumerate(method["helper_witnesses"])]
    weights[0][0] ^= 2
    reject("corrupt minimum-repair coefficient", lambda: verify_minimum_repair_weights(method, weights))
    with tempfile.TemporaryDirectory(prefix="superalpha083-review-") as directory:
        temporary = Path(directory)
        for name in ("codec.py", "run.py", "PREREGISTRATION.md"):
            (temporary / name).write_bytes((root / name).read_bytes())
        with (temporary / "codec.py").open("a") as f:
            f.write("\n# deliberate source corruption for verifier test\n")
        reject("modified source file rejected before import", lambda: verify_fingerprints(temporary, original))
    return {"passed": True, "corruptions_rejected": tested, "test_count": len(tested)}


def review_result(result_path: Path) -> dict:
    start = time.perf_counter()
    result = json.loads(result_path.read_text())
    hashes = verify_fingerprints(result_path.parent, result)
    codec_path = result_path.with_name("codec.py")
    spec = importlib.util.spec_from_file_location("codec_under_review", codec_path)
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    assert all(codec.mul(a, b) == MUL[a][b] for a in range(256) for b in range(256))
    assert all(codec.inv(a) == INV[a] for a in range(1, 256))
    reviews = []
    for name, method in load_methods(result):
        review = mathematical_review(name, get_generator(method), get_placement(method))
        assert review["contract_passed"], "registered erasure contract failed: " + name
        inspect_declared_metadata(method, review)
        review["byte_verification"] = byte_review(codec, method, review)
        review["successor_verification"] = successor_review(codec, method, review)
        reviews.append(review)
    return {"reviewer": "independent_review.py", "qualification": "New exact-source independent qualification; prior V1 receipt retained separately.", "source_result": str(result_path.name),
            "source_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "reviewer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "field_self_test": field_self_test(), "mutation_tests": mutation_tests(result_path.parent, result), "codec_field_products_checked": 65536,
            "codec_inverses_checked": 255, "source_fingerprints": hashes,
            "preregistration_local_sha256_matches_result": result.get("preregistration_sha256") == hashlib.sha256(result_path.with_name("PREREGISTRATION.md").read_bytes()).hexdigest(),
            "methods": reviews,
            "mathematics_passed": all(r["contract_passed"] for r in reviews),
            "byte_system_under_test_passed": all(r["byte_verification"]["passed"] for r in reviews),
            "methodological_limits": METHODOLOGICAL_LIMITS + [
                "The recorded recovery timings are eight-shard full-source decoding, not observed optimal single-shard repair timings; helper-count improvements remain a restricted linear-repair metric."],
            "preregistration_record_gaps": [
                "The original search records final states for 24 starts, but no full proposal/failure/incumbent trace or explicit proposal/mutation counts. The fixed loop budget is visible in source, not independently attested as an execution ledger.",
                "Tied incumbents are chosen lexicographically by masks/placement. No separate XOR-operation or other complexity measure verifies the preregistered lower-complexity tie preference.",
                "The candidate uses 9600 joint code/placement proposals with a 0.35 placement-mutation probability; controls receive 9600 dedicated placement trials. The actual placement proposal opportunities are not equal and this asymmetry is not a controlled causal comparison.",
            ],
            "review_elapsed_seconds": time.perf_counter() - start}


def review_supplement(root: Path, original_review: dict) -> dict:
    import numpy as np
    start = time.perf_counter()
    original_path, supplement_path = root / "RESULT.json", root / "SUPPLEMENT_RESULT.json"
    original = json.loads(original_path.read_text())
    supplement = json.loads(supplement_path.read_text())
    verify_fingerprints(root, original)
    assert supplement["original_result_sha256"] == hashlib.sha256(original_path.read_bytes()).hexdigest()
    assert supplement["source_sha256"] == hashlib.sha256((root / "supplement.py").read_bytes()).hexdigest()
    assert supplement["supplement_registered_after_original"] is True
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location("supplement_under_review", root / "supplement.py")
        actual = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(actual)
    finally:
        sys.path.pop(0)
    codec = sys.modules["codec"]
    new_reviews = []
    reviewed = {m["method"]: m for m in original_review["methods"]}
    for method in supplement["new_controls"]:
        review = mathematical_review(method["name"], get_generator(method), get_placement(method))
        assert review["contract_passed"], "supplementary contract failure"
        inspect_declared_metadata(method, review)
        review["byte_verification"] = byte_review(codec, method, review)
        review["successor_verification"] = successor_review(codec, method, review)
        new_reviews.append(review)
        reviewed[method["name"]] = review
    methods = {m["name"]: m for m in original["methods"] + supplement["new_controls"]}
    certificates = []
    assert {c["name"] for c in supplement["comparisons"]} == set(methods)
    for comparison in supplement["comparisons"]:
        name = comparison["name"]
        method, reference = methods[name], reviewed[name]
        for size, profile in comparison["reliability_profile"].items():
            independently = reference["all_erasure_failure_profile"][size]
            assert profile["tested"] == independently["patterns"]
            assert profile["unrecoverable"] == independently["unrecoverable_patterns"]
        repair = comparison["minimum_read_repairs"]
        verify_minimum_repair_weights(method, repair["weights"])
        assert math.isfinite(repair["seconds"]) and repair["seconds"] >= 0
        g = get_generator(method)
        plans = [actual.plan(g, target, helpers) for target, helpers in enumerate(method["helper_witnesses"])]
        assert plans == repair["weights"], "executed repair compiler differs from recorded weights"
        count = byte_reads = 0
        digest = hashlib.sha256()
        for seed in range(43001, 43021):
            rng = np.random.default_rng(seed)
            for length in (1, 17, 1024):
                source = rng.integers(0, 256, (K, length), dtype=np.uint8)
                expected = independent_encode(g, [row.tobytes() for row in source])
                stored = codec.apply(g, source)
                assert stored.tobytes() == b"".join(expected)
                for target, (helpers, coeff) in enumerate(zip(method["helper_witnesses"], plans)):
                    got = codec.apply([coeff], stored[helpers])[0].tobytes()
                    assert got == expected[target], "executed minimum-read byte mismatch"
                    digest.update(got)
                    count += 1
                    byte_reads += len(helpers) * length
        assert count == repair["repair_cases"] == 840
        assert repair["failures"] == 0 and repair["helper_bytes_read"] == byte_reads
        certificates.append({"method": name, "passed": True, "minimum_helper_counts": reference["minimum_helper_counts"],
                             "actual_compiler_plans_checked": 14, "actual_minimum_read_byte_cases": count,
                             "helper_bytes_read": byte_reads, "repair_output_sha256": digest.hexdigest()})
    return {"reviewer": "independent_review.py", "reviewer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "original_result_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
            "supplement_result_sha256": hashlib.sha256(supplement_path.read_bytes()).hexdigest(),
            "supplement_source_sha256": supplement["source_sha256"],
            "supplement_registered_after_original": True,
            "all_checks_passed": True, "new_control_reviews": new_reviews,
            "executed_minimum_read_repair_certificates": certificates,
            "scope": "Independent correctness and restricted full-shard linear-repair verification; no SOTA, novelty, dominance or economic admission.",
            "timestamps": {"reviewer_unix_epoch": time.time(), "meaning": "Runtime epoch. Filesystem modification timestamps are not treated as UTC or proof of registration order."},
            "elapsed_seconds": time.perf_counter() - start}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="?", type=Path, default=Path(__file__).with_name("RESULT.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("INDEPENDENT_REVIEW.json"))
    parser.add_argument("--supplement", action="store_true", help="Also verify SUPPLEMENT_RESULT.json separately")
    args = parser.parse_args()
    review = review_result(args.result)
    args.output.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n")
    if args.supplement:
        supplementary = review_supplement(args.result.parent, review)
        args.output.with_name("INDEPENDENT_SUPPLEMENT_REVIEW.json").write_text(json.dumps(supplementary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"mathematics_passed": review["mathematics_passed"],
                      "methods": len(review["methods"]), "supplement_verified": args.supplement, "output": str(args.output),
                      "elapsed_seconds": review["review_elapsed_seconds"]}))


if __name__ == "__main__":
    main()
