"""Reproduce an exact width-two example and audit an unresolved dispatch ambiguity."""

import argparse
from collections import Counter
from functools import cache
from hashlib import sha256
from itertools import combinations_with_replacement, permutations, product
import json
from math import factorial
from pathlib import Path
from time import perf_counter, process_time


DISPATCH_SHA = "d619e9a0ede7ab480e1875e48e784b406cbadc6292112c30253600d21cce9adc"


@cache
def tableau_count(content):
    """Count SSYTs of shape (sum(content)-2, 2) by their sorted lower row."""
    if any(value < 0 for value in content):
        return 0
    labels = [i for i, value in enumerate(content) if value > 0]
    count = 0
    for left, right in combinations_with_replacement(labels, 2):
        top_counts = list(content)
        top_counts[left] -= 1
        top_counts[right] -= 1
        if min(top_counts) < 0:
            continue
        first_two = []
        for label, multiplicity in enumerate(top_counts):
            first_two.extend([label] * min(2 - len(first_two), multiplicity))
            if len(first_two) == 2:
                break
        if first_two[0] < left and first_two[1] < right:
            count += 1
    return count


def prefix_envelope(permutation):
    return tuple(max(permutation[:i]) for i in range(1, len(permutation) + 1))


def dominates(upper, lower):
    return all(a >= b for a, b in zip(upper, lower))


def expand(weights):
    coeffs = {}
    for lower in sorted(weights, reverse=True):
        coeffs[lower] = weights[lower] - sum(
            value for upper, value in coeffs.items() if dominates(upper, lower)
        )
    assert all(
        value == sum(c for h, c in coeffs.items() if dominates(h, envelope))
        for envelope, value in weights.items()
    )
    return coeffs


def shape_panel(outer, inner):
    rows = len(outer)
    end_outer = [value + rows - i for i, value in enumerate(outer)]
    end_inner = [value + rows - i for i, value in enumerate(inner)]
    correction = {}
    hook = {}
    full = {}
    feasible = 0
    for perm in permutations(range(1, rows + 1)):
        env = prefix_envelope(perm)
        content = tuple(end_outer[label - 1] - a for label, a in zip(perm, end_inner))
        tableau = tableau_count(content)
        if min(content) < 0:
            hook_weight = correction_weight = 0
        else:
            feasible += 1
            r = sum(value > 0 for value in content)
            t = sum(value >= 2 for value in content)
            hook_weight = (r - 1) * (r - 2) // 2
            correction_weight = t - 1
            # Coefficient of x^content in h_(N-2) h_2 - h_(N-1) h_1.
            jacobi_trudi = r * (r - 1) // 2 + t - r
            assert jacobi_trudi == hook_weight + correction_weight == tableau
        for weights, value in ((correction, correction_weight), (hook, hook_weight), (full, tableau)):
            # Multiple permutations can share a prefix envelope.
            assert weights.setdefault(env, value) == value
    expansions = {name: expand(weights) for name, weights in
                  (("correction", correction), ("hook", hook), ("full", full))}
    assert all(x >= 0 for x in expansions["full"].values())
    return feasible, expansions


def partition(n, cap=None):
    if n == 0:
        yield ()
        return
    for first in range(min(n, cap or n), 0, -1):
        for rest in partition(n - first, first):
            yield (first, *rest)


def immanant():
    known_negative = (2, 3, 4, 4)
    feasible, expansions = shape_panel((3, 3, 3, 1), (1, 1, 0, 0))
    target = {(1, 3, 4, 4): 1, (2, 2, 4, 4): 1, known_negative: -1, (3, 3, 4, 4): 1}
    assert {key: value for key, value in expansions["correction"].items() if value} == target
    assert expansions["hook"][known_negative] == 1
    assert expansions["full"][known_negative] == 0

    panel_count = 0
    permutations_tested = 0
    feasible_tested = 0
    coefficients = 0
    negative_corrections = 0
    for n in range(4, 11):
        for outer in partition(n):
            if len(outer) > 4:
                continue
            for inner in product(*(range(length) for length in outer)):
                if sum(outer) - sum(inner) < 4 or any(a < b for a, b in zip(inner, inner[1:])):
                    continue
                examined, result = shape_panel(outer, inner)
                panel_count += 1
                feasible_tested += examined
                permutations_tested += factorial(len(outer))
                coefficients += len(result["full"])
                negative_corrections += sum(value < 0 for value in result["correction"].values())
    return {
        "published_fixture": {
            "shape": [[3, 3, 3, 1], [1, 1]],
            "permutations": 24,
            "feasible_permutations": feasible,
            "prefix_envelopes": len(expansions["full"]),
            "nonzero_coefficients": {
                name: [{"envelope": key, "value": value} for key, value in panel.items() if value]
                for name, panel in expansions.items()
            },
        },
        "extended_check": {
            "skew_shapes": panel_count,
            "permutations": permutations_tested,
            "feasible_permutations": feasible_tested,
            "coefficients_checked": coefficients,
            "negative_correction_only_coefficients": negative_corrections,
            "negative_complete_coefficients": 0,
            "scope": "Outer partition 4 through 10 cells, at most four nonempty skew rows, skew size at least four.",
        },
    }


@cache
def outcomes(n):
    alignments = [tuple(x for x in range(1, n + 1) if x != absent) for absent in range(1, n + 1)]
    return tuple(
        (row, offset, tuple(k for k, mapping in enumerate(alignments, 1) if mapping[row - 1] == row + offset))
        for row in range(1, n) for offset in (0, 1)
    )


@cache
def partition_depth(first, last):
    if first >= last:
        return 0
    return 1 + min(
        max(partition_depth(first, cut), partition_depth(cut + 1, last))
        for cut in range(first, last)
    )


def median_trace(n, omitted):
    start, finish = 1, n
    interrogations = []
    while start < finish:
        row = (start + finish) // 2
        shifted = omitted <= row
        interrogations.append(row)
        if shifted:
            finish = row
        else:
            start = row + 1
    assert start == omitted
    return interrogations


def classifier_benchmark(n):
    import sklearn
    from sklearn.tree import DecisionTreeClassifier, export_text

    def extracted(size, formatted):
        feature_rows = []
        labels = []
        for row, offset, survivors in outcomes(size):
            feature_rows.append([row, size - row, offset] if formatted else [size, row, offset])
            labels.append(len(survivors) == 1)
        return feature_rows, labels

    def checked(labels, predictions):
        return {
            "correct": sum(a == b for a, b in zip(labels, predictions)),
            "false_unique": sum(b and not a for a, b in zip(labels, predictions)),
            "missed_unique": sum(a and not b for a, b in zip(labels, predictions)),
        }

    result = {}
    for formatted in (False, True):
        train, target = [], []
        for size in range(3, 25):
            x, y = extracted(size, formatted)
            train.extend(x)
            target.extend(y)
        x_test, held = extracted(n, formatted)
        model = DecisionTreeClassifier(max_depth=3, random_state=1729)
        wall, cpu = perf_counter(), process_time()
        model.fit(train, target)
        elapsed = (perf_counter() - wall, process_time() - cpu)
        feature_names = ["row", "last_order_minus_row", "shift"] if formatted else ["orders", "row", "shift"]
        result["boundary_features" if formatted else "raw_features"] = {
            **checked(held, model.predict(x_test).tolist()),
            "fit_elapsed_seconds": elapsed[0],
            "fit_cpu_seconds": elapsed[1],
            "rule": export_text(model, feature_names=feature_names),
        }
    return {
        "implementation": sklearn.__version__,
        "training_anchors": len(train),
        "held_anchors": len(held),
        "majority": checked(held, [False] * len(held)),
        **result,
    }


def dispatch(receipt):
    raw = receipt.read_bytes()
    assert sha256(raw).hexdigest() == DISPATCH_SHA
    context = json.loads(raw)
    observed = next(c for c in context["cases"] if c["baseline"]["case"] == "cdp_o50_d")
    n = observed["baseline"]["orders"]
    assert observed["baseline"]["travel_shape"] == [n - 1, 8]
    assert observed["baseline"]["verdict"] == "ABSTAIN" and not observed["baseline"]["row_mapping_verified"]

    tests = outcomes(n)
    for row, offset, candidates in tests:
        expected = range(1, row + 1) if offset == 1 else range(row + 1, n + 1)
        assert candidates == tuple(expected)
    resolved = [
        {"observed_row": row, "authenticated_order": row + offset, "omitted_order": candidates[0]}
        for row, offset, candidates in tests if len(candidates) == 1
    ]
    assert len(resolved) == 2
    interior = next(t for t in tests if t[:2] == (n // 2, 0))
    traces = [median_trace(n, omitted) for omitted in range(1, n + 1)]
    distribution = Counter(map(len, traces))
    bound = (n - 1).bit_length()
    assert partition_depth(1, n) == max(distribution) == bound
    clean = next(c["challenger"] for c in context["cases"] if c["baseline"]["case"] == "cdp_o5_06d")
    repeated = [count for count in Counter(map(tuple, clean["truck_travel_minutes"])).values() if count > 1]
    assert repeated == [2]
    return {
        "reference_receipt_sha256": DISPATCH_SHA,
        "orders": n,
        "travel_shape": observed["baseline"]["travel_shape"],
        "recorded_travel_values": observed["challenger"]["overlap_cells"],
        "mappings": n,
        "authenticated_anchors_observed": 0,
        "hypothetical_anchors_tested": len(tests),
        "certifying_singletons": resolved,
        "counterexample": {
            "row": interior[0], "authenticated_order": interior[0],
            "compatible_omissions": [interior[2][0], interior[2][-1]],
            "surviving_mappings": len(interior[2]),
        },
        "best_worst_case_adaptive_queries": bound,
        "median_query_count_distribution": dict(sorted(distribution.items())),
        "repeated_travel_vector_group_sizes_on_published_clean_control": repeated,
        "decision": "ABSTAIN_SOURCE_RECOVERY; exact evidence-acquisition plan under equal authorized-query costs",
        "small_model_comparison": classifier_benchmark(n),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatch', type=Path, help='Optional original, pinned dispatch recovery receipt.')
    args = parser.parse_args()
    wall = perf_counter()
    cpu = process_time()
    result = {"immanant": immanant()}
    if args.dispatch is not None:
        result['dispatch'] = dispatch(args.dispatch)
    result["local_elapsed_seconds"] = perf_counter() - wall
    result["local_cpu_seconds"] = process_time() - cpu
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
