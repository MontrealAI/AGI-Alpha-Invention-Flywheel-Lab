"""Independent source/decision audit for NEXT072; no constructor imports.

Read-only OOXML extraction, scalar condition-mean checks, independently derived
acquisition traces and complete economic-scope checks. Numerical source access
is gated by the public protocol/source freeze. No network retrieval is provided.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import posixpath
import re
import resource
import statistics
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np

REPO = Path(__file__).resolve().parents[1]
EXPERIMENT = "NEXT072-20261102"
WORKBOOK_BYTES = 10905627
WORKBOOK_BLOB = "f35c9efe3bf0f917068b2aaf2c2236b593c06e2c"
SPLIT_PREFIX = "NEXT072-K1-v1|"
PRIMARY_POLICY = "probability_of_hit"
POLICIES = (PRIMARY_POLICY, "sequential_kernel", "ordinary_equal_content",
            "static_probability_of_hit", "static_kernel", "kernel_exploitation",
            "linear_ridge", "additive_magnitude", "diversity", "constant_features"
            ) + tuple(f"hash_{i:02d}" for i in range(32))
HIT_POLICIES = {PRIMARY_POLICY, "ordinary_equal_content", "static_probability_of_hit", "constant_features"}
FEATURES = ["min_single_norm", "max_single_norm", "additive_norm", "single_cosine",
            "difference_norm", "absolute_norm_difference"]
REQUIRED_COLUMNS = {"gene_name", "pert_group", "seed", "AB", "A", "B", "ctrl", "error", "rank"}
XML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
SOURCE_ABS_TOL = 1e-10
NUMERIC_ABS_TOL = 1e-8
NUMERIC_REL_TOL = 1e-8


class VerificationFailure(ValueError):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail


def require(condition, message, detail=None):
    if not condition:
        raise VerificationFailure(message, detail)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def object_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def _unique_object(items):
    out = {}
    for key, value in items:
        require(key not in out, "DUPLICATE_JSON_KEY", key)
        out[key] = value
    return out


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "REGULAR_INPUT_REQUIRED", str(path))
    return json.loads(path.read_text(), object_pairs_hook=_unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(VerificationFailure("NONFINITE_JSON", value)))


def validate_freeze(path, public_commit, repo=REPO):
    require(re.fullmatch("[0-9a-f]{40}", public_commit) is not None, "PUBLIC_FREEZE_COMMIT_REQUIRED")
    value = read_json(path)
    require(value.get("schema") == 1 and value.get("experiment_id") == EXPERIMENT, "EXACT_NEXT072_FREEZE_REQUIRED")
    files = value.get("files")
    required = {"next072/data.py", "next072/policy.py", "next072/evaluate.py", "next072/protocol.py",
                "next072/run.py", "next072/freeze.py", "next072/independent_verify.py",
                "next072/test_independent_verify.py", "next072/economic_check.py",
                "experiments/next_series_20261102/PREREG_K1.md",
                "experiments/next_series_20261102/INDEPENDENT_PREREG.md",
                "experiments/next_series_20261102/ECONOMIC_ADVERSARY.md"}
    require(isinstance(files, dict) and required <= set(files), "COMPLETE_INDEPENDENT_SOURCE_FREEZE_REQUIRED")
    for name, expected in files.items():
        require(isinstance(name, str) and not Path(name).is_absolute() and ".." not in Path(name).parts,
                "BOUNDED_FREEZE_PATH_REQUIRED")
        source = Path(repo) / name
        require(source.is_file() and not source.is_symlink() and file_hash(source) == expected,
                "FROZEN_SOURCE_CHANGED", name)
    require(value.get("prereg_sha256") == files["experiments/next_series_20261102/PREREG_K1.md"],
            "PROTOCOL_IDENTITY_DISAGREES")
    return {"public_commit": public_commit, "freeze_sha256": file_hash(path), "files": files}


def workbook_identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "REGULAR_WORKBOOK_REQUIRED")
    size = path.stat().st_size
    require(size == WORKBOOK_BYTES, "WORKBOOK_BYTE_COUNT_CHANGED", size)
    git_hash = hashlib.sha1(b"blob " + str(size).encode() + b"\0")
    secure_hash = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            git_hash.update(block)
            secure_hash.update(block)
    require(git_hash.hexdigest() == WORKBOOK_BLOB, "PINNED_WORKBOOK_GIT_BLOB_CHANGED")
    return {"bytes": size, "git_blob": git_hash.hexdigest(), "sha256": secure_hash.hexdigest()}


def cell_value(cell, strings):
    require(cell.find(XML + "f") is None, "SOURCE_EXPORT_FORMULA_UNEXPECTED")
    kind = cell.get("t", "n")
    if kind == "inlineStr":
        return "".join(piece.text or "" for piece in cell.iter(XML + "t"))
    value = cell.find(XML + "v")
    if value is None or value.text is None:
        return None
    if kind == "s":
        index = int(value.text)
        require(0 <= index < len(strings), "INVALID_SHARED_STRING_INDEX")
        return strings[index]
    if kind == "b":
        require(value.text in {"0", "1"}, "INVALID_BOOLEAN_CELL")
        return value.text == "1"
    require(kind in {"n", "str"}, "UNSUPPORTED_OR_ERROR_SOURCE_CELL", kind)
    return value.text if kind == "str" else float(value.text)


def column_number(address):
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", address or "")
    require(match is not None, "EXPLICIT_CELL_ADDRESS_REQUIRED")
    out = 0
    for character in match[1]:
        out = out * 26 + ord(character) - ord("A") + 1
    return out - 1, int(match[2])


def workbook_rows(path):
    """Stream the single source worksheet using independent stdlib OOXML code."""
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), "DUPLICATE_OOXML_MEMBER")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall(XML + "sheets/" + XML + "sheet")
        require(len(sheets) == 1, "EXACTLY_ONE_SOURCE_WORKSHEET_REQUIRED")
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        matches = [row for row in relationships if row.get("Id") == sheets[0].get(REL + "id")]
        require(len(matches) == 1 and matches[0].get("TargetMode") != "External", "SOURCE_SHEET_RELATIONSHIP_REQUIRED")
        target = matches[0].get("Target", "")
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        require(".." not in PurePosixPath(member).parts and member.startswith("xl/"), "BOUNDED_WORKSHEET_MEMBER_REQUIRED")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            with archive.open("xl/sharedStrings.xml") as stream:
                for _, node in ET.iterparse(stream, events=("end",)):
                    if node.tag == XML + "si":
                        strings.append("".join(text.text or "" for text in node.iter(XML + "t")))
                        node.clear()
        header = None
        last_row = 0
        with archive.open(member) as stream:
            for _, node in ET.iterparse(stream, events=("end",)):
                if node.tag != XML + "row":
                    continue
                row_number = int(node.get("r", "0"))
                require(row_number == last_row + 1, "MISSING_OR_DUPLICATE_WORKSHEET_ROW", row_number)
                last_row = row_number
                cells = {}
                for cell in node.findall(XML + "c"):
                    column, cell_row = column_number(cell.get("r"))
                    require(cell_row == row_number and column not in cells, "CELL_ADDRESS_OR_DUPLICATE_COLUMN_ERROR")
                    cells[column] = cell_value(cell, strings)
                require(cells and any(value is not None for value in cells.values()), "EMPTY_SOURCE_ROW", row_number)
                if header is None:
                    header = [cells.get(i) for i in range(max(cells) + 1)]
                    require(all(isinstance(x, str) and x for x in header) and len(header) == len(set(header))
                            and REQUIRED_COLUMNS <= set(header), "SOURCE_COLUMNS_DISAGREE")
                else:
                    require(max(cells) < len(header), "UNLABELLED_SOURCE_COLUMN")
                    yield {name: cells.get(i) for i, name in enumerate(header)}
                node.clear()
        require(header is not None and last_row > 1, "EMPTY_SOURCE_WORKBOOK")


def number(value, label):
    require(not isinstance(value, bool) and value is not None, "MISSING_NUMERIC_OBSERVATION", label)
    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise VerificationFailure("INVALID_NUMERIC_OBSERVATION", label) from error
    require(math.isfinite(converted), "NONFINITE_OBSERVATION", label)
    return converted


def pair_identity(value):
    require(isinstance(value, str), "TEXT_PAIR_IDENTITY_REQUIRED")
    pieces = value.split("+")
    require(len(pieces) == 2 and all(pieces) and len(set(pieces)) == 2
            and "ctrl" not in pieces and all(x == x.strip() for x in pieces), "INVALID_PAIR_IDENTITY", value)
    return "+".join(sorted(pieces)), pieces


def reconstruct(records, expected_readouts=1000):
    """Inspect every row; no invalid observation is silently dropped."""
    residuals, single, control, ranks = {}, {}, {}, {}
    seen_pairs, seen_genes, failures = set(), set(), []
    rows = 0
    maximum_residual_difference = 0.0

    def consistent(mapping, key, value, scope):
        require(key not in mapping or abs(mapping[key] - value) <= SOURCE_ABS_TOL, "CONFLICTING_" + scope, str(key))
        mapping.setdefault(key, value)

    for rows, row in enumerate(records, 1):
        try:
            pair, original = pair_identity(row.get("pert_group"))
            seen_pairs.add(pair)
            gene = row.get("gene_name")
            require(isinstance(gene, str) and bool(gene), "TEXT_READOUT_GENE_REQUIRED")
            seen_genes.add(gene)
            require(number(row.get("seed"), "seed") == 1, "UNREGISTERED_SOURCE_SEED")
            require((pair, gene) not in residuals, "DUPLICATE_PAIR_READOUT", pair + "/" + gene)
            a, b, ab, c, error = [number(row.get(name), name) for name in ("A", "B", "AB", "ctrl", "error")]
            residual = math.fsum((ab, -a, -b, c))
            gap = abs(residual - error)
            maximum_residual_difference = max(maximum_residual_difference, gap)
            require(gap <= SOURCE_ABS_TOL, "PUBLISHED_ERROR_DISAGREES_WITH_MEANS", pair + "/" + gene)
            consistent(single, (original[0], gene), a, "SINGLE_MEAN")
            consistent(single, (original[1], gene), b, "SINGLE_MEAN")
            consistent(control, gene, c, "CONTROL_MEAN")
            consistent(ranks, gene, number(row.get("rank"), "rank"), "CONTROL_RANK")
            residuals[pair, gene] = residual
        except VerificationFailure as error:
            failures.append({"data_row": rows, "code": str(error), "detail": error.detail})
    denominator = {"source_rows": rows, "identified_pairs": len(seen_pairs), "identified_readouts": len(seen_genes),
                   "valid_pair_readout_records": len(residuals), "invalid_records": len(failures)}
    require(not failures, "SOURCE_RECORDS_REJECTED_NO_IMPUTATION", {"denominator": denominator, "failures": failures})
    genes, names = sorted(seen_genes), sorted(seen_pairs)
    require(names and genes, "NO_SOURCE_OBSERVATIONS", denominator)
    require(expected_readouts is None or len(genes) == expected_readouts, "READOUT_PANEL_COUNT_DISAGREES", denominator)
    require(set(ranks.values()) == set(range(1, len(genes) + 1)), "INCOMPLETE_CONTROL_RANK_PANEL", denominator)
    require(set(residuals) == {(p, g) for p in names for g in genes}, "INCOMPLETE_PAIR_READOUT_COVERAGE", denominator)
    ranked = sorted(genes, key=ranks.get)
    require(all(control[left] + SOURCE_ABS_TOL >= control[right] for left, right in zip(ranked, ranked[1:])),
            "RANKS_DO_NOT_ORDER_CONTROL_EXPRESSION")
    feature_rows, outcomes = [], []
    interventions = sorted({name for pair in names for name in pair.split("+")})
    for pair in names:
        a, b = pair.split("+")
        require(all((name, g) in single for name in (a, b) for g in genes), "INCOMPLETE_SINGLE_PROFILE")
        va = [single[a, g] - control[g] for g in genes]
        vb = [single[b, g] - control[g] for g in genes]
        norm_a, norm_b = [math.sqrt(math.fsum(x * x for x in vector)) for vector in (va, vb)]
        cosine = math.fsum(x * y for x, y in zip(va, vb)) / (norm_a * norm_b) if norm_a and norm_b else 0.0
        feature_rows.append([min(norm_a, norm_b), max(norm_a, norm_b),
            math.sqrt(math.fsum((x + y) ** 2 for x, y in zip(va, vb))), max(-1.0, min(1.0, cosine)),
            math.sqrt(math.fsum((x - y) ** 2 for x, y in zip(va, vb))), abs(norm_a - norm_b)])
        outcomes.append(math.sqrt(math.fsum(residuals[pair, g] ** 2 for g in genes) / len(genes)))
    return {"pair_names": names, "features": feature_rows, "outcomes": outcomes,
            "readout_genes": genes, "single_interventions": interventions, "rows": rows,
            "source_units": "author-exported log-transformed expression units", "feature_names": FEATURES}, {
        "denominator": denominator, "maximum_published_residual_disagreement": maximum_residual_difference,
        "source_means_checked": ["AB", "A", "B", "ctrl"], "rank_order_consistent_with_control": True,
        "cell_level_counts_normalization_and_sampling_error_revalidated": False}


def split(names):
    ranked = sorted(names, key=lambda name: (hashlib.sha256((SPLIT_PREFIX + name).encode()).digest(), name))
    references = ranked[:(len(names) + 3) // 4]
    candidates = sorted(set(names) - set(references))
    return references, candidates, len(candidates) // 4, (len(candidates) + 3) // 4


def normalized_features(features):
    n, p = len(features), len(features[0])
    centers = [math.fsum(row[j] for row in features) / n for j in range(p)]
    scales = [math.sqrt(math.fsum((row[j] - centers[j]) ** 2 for row in features) / n) or 1.0 for j in range(p)]
    return np.array([[(row[j] - centers[j]) / scales[j] for j in range(p)] for row in features])


def kernel_matrix(x):
    squared = np.array([[math.fsum((float(a) - float(b)) ** 2 for a, b in zip(left, right))
                         for right in x] for left in x])
    nonzero = [math.sqrt(squared[i, j]) for i in range(len(x)) for j in range(i + 1, len(x)) if squared[i, j] > 0]
    length = statistics.median(nonzero) if nonzero else 1.0
    return np.exp(squared / (-2.0 * length * length))


def kernel_estimates(kernel, fit, outcomes, candidates):
    center = math.fsum(outcomes) / len(outcomes)
    scale = math.sqrt(math.fsum((value - center) ** 2 for value in outcomes) / len(outcomes)) or 1.0
    chol = np.linalg.cholesky(kernel[np.ix_(fit, fit)] + np.eye(len(fit)) / 10)
    standardized = np.array([(value - center) / scale for value in outcomes])
    whitened = np.linalg.solve(chol, standardized)
    means, deviations = [], []
    for candidate in candidates:
        # Scalar candidate evaluation preserves exact equality for identical
        # feature vectors; vectorized BLAS tail rounding must not break ties.
        projected = np.linalg.solve(chol, kernel[fit, candidate])
        means.append(center + scale * math.fsum(float(a * b) for a, b in zip(projected, whitened)))
        deviations.append(scale * math.sqrt(max(0.0, 1.0 - math.fsum(float(v * v) for v in projected))))
    return np.array(means), np.array(deviations)


def linear_estimates(x, fit, values, candidates):
    design = np.array([[1.0, *x[i]] for i in fit])
    penalty = np.diag([0.0] + [1.0] * x.shape[1])
    y = np.array(values)

    def coefficients(matrix, target, ridge):
        return np.linalg.solve(matrix.T @ matrix + ridge * penalty, matrix.T @ target)

    losses = []
    for ridge in (0.01, 0.1, 1.0, 10.0):
        squared_errors = []
        for holdout in range(len(fit)):
            remaining = [i for i in range(len(fit)) if i != holdout]
            if not remaining:
                squared_errors = [float("inf")]
                break
            beta = coefficients(design[remaining], y[remaining], ridge)
            squared_errors.append(float(y[holdout] - design[holdout] @ beta) ** 2)
        losses.append((math.fsum(squared_errors) / len(squared_errors), ridge))
    ridge = min(losses)[1]
    beta = coefficients(design, y, ridge)
    return np.array([[1.0, *x[i]] for i in candidates]) @ beta, ridge


def reference_hit_threshold(initial_values):
    values = sorted(float(value) for value in initial_values)
    require(bool(values) and all(math.isfinite(value) for value in values), "FINITE_INITIAL_REFERENCE_THRESHOLD_REQUIRED")
    # Integer nearest-rank calculation, separate from the constructor's ceil.
    rank = (3 * len(values) + 3) // 4
    return values[rank - 1]


def normal_hit_scores(means, deviations, threshold):
    require(len(means) == len(deviations) and math.isfinite(threshold), "VALID_NORMAL_SCORE_INPUT_REQUIRED")
    scores, probabilities = [], []
    for mean, deviation in zip(means, deviations):
        require(math.isfinite(mean) and math.isfinite(deviation) and deviation >= 0, "FINITE_NONNEGATIVE_DEVIATION_REQUIRED")
        score = (float(mean) - threshold) / max(float(deviation), 1e-12)
        require(math.isfinite(score), "FINITE_HIT_SCORE_REQUIRED")
        scores.append(score)
        probabilities.append(math.erfc(-score / math.sqrt(2.0)) / 2.0)
    return np.array(scores), np.array(probabilities)


def independent_trace(prepared, policy):
    """Reconstruct choices with only prior revealed outcomes in each fit."""
    require(policy in POLICIES, "UNREGISTERED_POLICY")
    names, raw = prepared["pair_names"], prepared["features"]
    references, candidates, budget, _ = split(names)
    lookup = {name: i for i, name in enumerate(names)}
    outcomes = dict(zip(names, prepared["outcomes"]))
    known = {name: outcomes[name] for name in references}
    initial = dict(known)
    threshold = reference_hit_threshold(initial.values())
    pending = set(candidates)
    x = normalized_features(raw)
    if policy == "constant_features":
        x = np.zeros((len(names), 1))
    kernel = kernel_matrix(x)
    hash_priority = {}
    if policy.startswith("hash_"):
        salt = "NEXT072-RANDOM-" + policy[-2:]
        order = sorted(candidates, key=lambda name: (hashlib.sha256((salt + name).encode()).digest(), name))
        hash_priority = {name: i for i, name in enumerate(order)}
    receipt = []
    while len(receipt) < budget:
        current = sorted(pending)
        indices = [lookup[name] for name in current]
        available = initial if policy in {"static_kernel", "static_probability_of_hit"} else known
        fit_names = sorted(available)
        fit = [lookup[name] for name in fit_names]
        values = [available[name] for name in fit_names]
        means, deviations, extra = np.zeros(len(current)), np.zeros(len(current)), {}
        probabilities = None
        if policy in HIT_POLICIES:
            means, deviations = kernel_estimates(kernel, fit, values, indices)
            scores, probabilities = normal_hit_scores(means, deviations, threshold)
            extra = {"hit_threshold_from_initial_references": threshold}
        elif policy in {"sequential_kernel", "static_kernel", "kernel_exploitation"}:
            means, deviations = kernel_estimates(kernel, fit, values, indices)
            scores = means if policy == "kernel_exploitation" else means + deviations
        elif policy == "linear_ridge":
            means, ridge = linear_estimates(x, fit, values, indices)
            scores, extra = means, {"ridge": ridge}
        elif policy == "additive_magnitude":
            scores = np.array([raw[i][2] for i in indices])
        elif policy == "diversity":
            scores = np.array([min(float(np.sum((x[i] - x[j]) ** 2)) for j in fit) for i in indices])
        else:
            scores = np.array([-hash_priority[name] for name in current], dtype=float)
        require(np.isfinite(scores).all(), "NONFINITE_INDEPENDENT_ACQUISITION")
        batch = []
        if policy == "diversity":
            remaining_scores = scores.copy()
            for _ in range(min(4, budget - len(receipt))):
                choice = min((j for j in range(len(current)) if j not in [q[0] for q in batch]),
                             key=lambda j: (-float(remaining_scores[j]), current[j]))
                batch.append((choice, float(remaining_scores[choice])))
                remaining_scores = np.minimum(remaining_scores, np.array([
                    float(np.sum((x[i] - x[indices[choice]]) ** 2)) for i in indices]))
        else:
            batch = [(j, float(scores[j])) for j in sorted(range(len(current)),
                     key=lambda j: (-float(scores[j]), current[j]))[:min(4, budget - len(receipt))]]
        committed = [{"pair": current[j], "prediction": float(means[j]),
            "acquisition_deviation": float(deviations[j]), "acquisition_index": score,
            "batch": len(receipt) // 4, "references_available_before_batch": len(available), **extra,
            **({"model_hit_probability": float(probabilities[j])} if probabilities is not None else {})}
            for j, score in batch]
        for item in committed:
            query = len(receipt) + 1
            item.update(revealed_D=outcomes[item["pair"]], query_number=query,
                        remaining_budget_before=budget - query + 1, remaining_budget_after=budget - query)
            known[item["pair"]] = item["revealed_D"]
            pending.remove(item["pair"])
            receipt.append(item)
    return receipt


def compare_tree(actual, expected, path="root"):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), "OBJECT_FIELDS_DISAGREE", path)
        for key in expected:
            compare_tree(actual[key], expected[key], path + "." + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), "LIST_LENGTH_DISAGREES", path)
        for i, value in enumerate(expected):
            compare_tree(actual[i], value, f"{path}[{i}]")
    elif isinstance(expected, float):
        require(type(actual) in {int, float} and math.isfinite(actual)
                and math.isclose(actual, expected, abs_tol=NUMERIC_ABS_TOL, rel_tol=NUMERIC_REL_TOL),
                "INDEPENDENT_NUMBER_DISAGREES", path)
    else:
        require(type(actual) is type(expected) and actual == expected, "EXACT_VALUE_DISAGREES", path)


def expected_profile_counts(prepared, n_reference, budget):
    single_count = len(prepared["single_interventions"])
    return {"unique_single_profiles": single_count, "control_profiles": 1,
            "calibration_double_profiles": n_reference, "selected_double_profiles": budget,
            "total_profiles_used_per_policy": single_count + 1 + n_reference + budget,
            "total_profiles_for_all_pairs": single_count + 1 + len(prepared["pair_names"]),
            "count_is_not_money_or_equal_assay_cost": True}


def verify_result(prepared, result):
    names = prepared["pair_names"]
    references, candidates, budget, target_count = split(names)
    outcomes = dict(zip(names, prepared["outcomes"]))
    targets = sorted(candidates, key=lambda name: (-outcomes[name], name))[:target_count]
    require(set(result.get("receipts", {})) == set(POLICIES)
            and set(result.get("policy_results", {})) == set(POLICIES), "ALL_FORTY_TWO_REGISTERED_POLICIES_REQUIRED")
    for key, expected in {"status": "source_bound_replay_completed", "primary_policy": PRIMARY_POLICY, "references": references,
        "confirmation_candidates": candidates, "confirmation_target_pairs_after_seal": targets,
        "reference_pairs": len(references), "confirmation_pairs": len(candidates),
        "query_budget": budget, "target_count": target_count,
        "input_denominator": {"pairs": len(names), "readout_genes": len(prepared["readout_genes"]), "pair_readout_rows": prepared["rows"]},
        "full_profile_cost_counts": expected_profile_counts(prepared, len(references), budget)}.items():
        compare_tree(result.get(key), expected, key)
    metrics = {}
    for policy in POLICIES:
        actual = result["receipts"][policy]
        expected = independent_trace(prepared, policy)
        require(len(actual) == budget, "EXACT_QUERY_BUDGET_REQUIRED", policy)
        unlabelled = [{key: value for key, value in row.items()
                       if key not in {"is_target_after_seal", "cumulative_discoveries_after_seal"}} for row in actual]
        compare_tree(unlabelled, expected, policy + ".pre_reveal_trace")
        discoveries = 0
        for row in actual:
            discoveries += row["pair"] in targets
            require(row.get("is_target_after_seal") is (row["pair"] in targets)
                    and type(row.get("cumulative_discoveries_after_seal")) is int
                    and row["cumulative_discoveries_after_seal"] == discoveries, "POST_SEAL_LABEL_OR_DISCOVERY_COUNT_DISAGREES", policy)
        metrics[policy] = {"queries": budget, "discoveries": discoveries, "missed_targets": target_count - discoveries,
            "non_target_queries": budget - discoveries, "target_count": target_count,
            "precision": discoveries / budget if budget else None, "recall": discoveries / target_count,
            "boundary_met": discoveries * 2 >= target_count, "sealed_selection_sha256": object_hash(unlabelled)}
    random_mean = math.fsum(metrics[f"hash_{i:02d}"]["discoveries"] for i in range(32)) / 32
    for policy, row in metrics.items():
        row["lift_vs_hash_mean"] = row["discoveries"] / random_mean if random_mean else None
        compare_tree(result["policy_results"][policy], row, policy + ".metrics")
    compare_tree(result.get("hash_control_mean_discoveries"), random_mean, "hash_control_mean")
    require(result["receipts"]["ordinary_equal_content"] == result["receipts"][PRIMARY_POLICY]
            and result.get("equal_content_ordinary_reuse_exact_tie") is True, "ORDINARY_EQUAL_CONTENT_TECHNICAL_TIE_REQUIRED")
    require(result.get("proposed_discovery_boundary_met") is metrics[PRIMARY_POLICY]["boundary_met"],
            "PRIMARY_DISCOVERY_VERDICT_DISAGREES")
    for key in ("physical_or_biological_delivery_admission", "commercial_or_native_financial_admission"):
        require(result.get(key) == "NOT_ESTABLISHED", "UNSUPPORTED_ADMISSION", key)
    reference_genes = {g for p in references for g in p.split("+")}
    candidate_genes = {g for p in candidates for g in p.split("+")}
    primary_count = metrics[PRIMARY_POLICY]["discoveries"]
    return {"policies_verified": len(metrics), "primary_policy": PRIMARY_POLICY,
        "fixed_hit_threshold_from_initial_references": reference_hit_threshold(outcomes[name] for name in references),
        "normal_model_probability_is_not_biological_calibration": True,
        "initial_references_per_policy": len(references),
        "initial_reveal_budget_per_policy": budget, "final_reveal_budget_per_policy": 0,
        "policy_query_records_checked": len(metrics) * budget, "source_pairs": len(names),
        "all_pairs_accounted_for": len(references) + len(candidates) == len(names),
        "reference_candidate_pairs_disjoint": not set(references).intersection(candidates),
        "shared_reference_candidate_genes": sorted(reference_genes & candidate_genes),
        "scope": "New pairs of measured single interventions; no unseen-gene or independent-cell-trial claim.",
        "independently_recomputed_policy_results": metrics,
        "proposed_boundary_met": metrics[PRIMARY_POLICY]["boundary_met"],
        "primary_minus_control_discoveries": {name: primary_count - metrics[name]["discoveries"] for name in (
            "constant_features", "static_probability_of_hit", "sequential_kernel", "linear_ridge", "additive_magnitude", "diversity")}
            | {"hash_mean": primary_count - random_mean},
        "control_differences_are_fixed_replay_descriptions_not_physical_effects": True,
        "ordinary_specialist_technical_tie": True,
        "profile_counts": expected_profile_counts(prepared, len(references), budget),
        "adaptive_query_batches": math.ceil(budget / 4),
        "economic_admission": "NOT_ESTABLISHED",
        "unknown_economic_inputs": ["Assay-specific money/cell/read costs", "Failure and repeat costs", "Batch turnaround and delays",
            "Complete specialist attention and loaded compensation", "Agent research/inference cost", "Buyer acceptance of missed targets",
            "Voluntary demand, price and contract terms", "Qualification, support, licensing and liability", "Working capital and taxes"]}


def review_policy_source(path):
    """A bounded source review, explicitly not a hostile-code isolation proof."""
    tree = ast.parse(Path(path).read_text())
    allowed_imports = {"__future__", "hashlib", "math", "dataclasses", "numpy", "protocol"}
    forbidden = {"open", "eval", "exec", "compile", "globals", "locals", "vars", "getattr", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(all(alias.name in allowed_imports for alias in node.names), "UNREVIEWED_POLICY_IMPORT")
        if isinstance(node, ast.ImportFrom):
            require(node.module in allowed_imports, "UNREVIEWED_POLICY_IMPORT")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden, "HIDDEN_ACCESS_OR_DYNAMIC_POLICY_CALL")
        if isinstance(node, ast.Attribute):
            require(node.attr not in {"__self__", "__globals__", "__closure__", "__dict__", "_RevealOracle__outcomes"},
                    "HIDDEN_OUTCOME_INTROSPECTION")
    contexts = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PublicContext"]
    require(len(contexts) == 1, "EXACT_PUBLIC_POLICY_CONTEXT_REQUIRED")
    fields = [node.target.id for node in contexts[0].body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)]
    require(fields == ["names", "features", "reference_names", "reference_values", "query_budget"], "POLICY_CONTEXT_ADDS_UNREGISTERED_INPUT")
    return {"accepted": True, "policy_source_sha256": file_hash(path), "context_fields": fields,
        "meaning": "Reviewed policy source plus independent causal trace reconstruction; shared-host procedural isolation, not external blinding or a security sandbox."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=REPO / "experiments/next_series_20261102/FREEZE.json")
    parser.add_argument("--public-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "NEW_INDEPENDENT_RECEIPT_PATH_REQUIRED")
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    report = {"schema": "next072/independent-verification/v1", "experiment_id": EXPERIMENT,
              "started_utc": datetime.now(timezone.utc).isoformat(), "accepted": False,
              "verifier": "included-agent:/root/recovery_constructor_v2", "same_host_review": True,
              "actual_host_and_inference_money_cost": "UNKNOWN", "outside_human_or_laboratory_actions": 0}
    exit_code = 1
    try:
        binding = validate_freeze(args.freeze, args.public_commit)
        report["source_binding"] = binding
        report["policy_source_review"] = review_policy_source(REPO / "next072/policy.py")
        identity = workbook_identity(args.workbook)
        report["workbook_identity"] = identity
        result_path = args.attempt / "results.json"
        compact_path = args.attempt / "compact_evidence.json"
        resource_path = args.attempt / "resource_receipt.json"
        report["input_file_sha256"] = {p.name: file_hash(p) for p in (result_path, compact_path, resource_path)}
        result, compact, measured = [read_json(path) for path in (result_path, compact_path, resource_path)]
        require(result.get("public_freeze_commit") == args.public_commit
                and measured.get("public_freeze_commit") == args.public_commit, "CONFIRMATION_PUBLIC_COMMIT_CHANGED")
        require(result.get("execution_kind") in {"registered_confirmation", "engineering_reproduction"}
                and result.get("execution_kind") == measured.get("execution_kind"), "EXECUTION_ROLE_CHANGED")
        report["execution_kind"] = result["execution_kind"]
        require(measured.get("status") == "COMPLETED"
                and measured.get("mode") == "author_condition_mean_source_replay", "ORIGINAL_WORKBOOK_EXECUTION_REQUIRED")
        require(measured.get("freeze_document_sha256") == binding["freeze_sha256"]
                and measured.get("actual_code_and_contract_hashes") == binding["files"],
                "CONSTRUCTOR_SOURCE_FREEZE_BINDING_CHANGED")
        compare_tree(measured.get("input_identity"), identity, "source_identity")
        require(measured.get("result_sha256") == file_hash(result_path)
                and measured.get("prepared_evidence_sha256") == object_hash(compact)
                and result.get("input_evidence_sha256") == object_hash(compact), "CONSTRUCTOR_ARTIFACT_BINDING_CHANGED")
        prepared, measurement = reconstruct(workbook_rows(args.workbook))
        report["measurement_audit"] = measurement
        compare_tree(compact, prepared, "independent_condition_mean_reconstruction")
        report["result_audit"] = verify_result(prepared, result)
        require(validate_freeze(args.freeze, args.public_commit) == binding, "SOURCE_CHANGED_DURING_VERIFICATION")
        require(workbook_identity(args.workbook) == identity, "WORKBOOK_CHANGED_DURING_VERIFICATION")
        require(all(file_hash(args.attempt / name) == value for name, value in report["input_file_sha256"].items()),
                "RESULT_INPUT_CHANGED_DURING_VERIFICATION")
        report["accepted"] = True
        report["scope"] = "Source-bound research replay and complete finite allocation audit. No physical, biological, buyer-demand or financial admission."
        exit_code = 0
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error), "detail": getattr(error, "detail", None)}
    report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.perf_counter() - started_wall, cpu_seconds=time.process_time() - started_cpu,
        peak_rss_kib_linux=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"accepted": report["accepted"], "output": str(args.output), "failure": report.get("failure")}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
