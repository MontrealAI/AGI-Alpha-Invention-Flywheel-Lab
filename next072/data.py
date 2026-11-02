"""Read author-published condition means without modifying the workbook.

Only this preparation/evaluator module sees all reference outcomes. The policy
module receives single-derived features and a restricted reveal interface.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np

from .protocol import SOURCE_BLOB, SOURCE_BYTES, TOLERANCE


class InputFailure(ValueError):
    """A source identity or observation contract failed."""


def canonical_pair(value: str) -> tuple[str, str]:
    parts = str(value).split("+")
    if len(parts) != 2 or not all(parts) or "ctrl" in parts or parts[0] == parts[1]:
        raise InputFailure(f"Invalid double perturbation identity: {value!r}")
    return tuple(sorted(parts))


def numeric(value, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise InputFailure(f"Missing or nonnumeric {field}")
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise InputFailure(f"Invalid numeric {field}") from exc
    if not math.isfinite(out):
        raise InputFailure(f"Nonfinite {field}")
    return out


def source_identity(path: Path) -> dict:
    content = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    result = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "git_blob": blob}
    if len(content) != SOURCE_BYTES or blob != SOURCE_BLOB:
        raise InputFailure(f"Source identity mismatch: {result}")
    return result


def workbook_records(path: Path) -> Iterable[dict]:
    # Read-only analysis, no workbook authoring or edits.
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if len(workbook.worksheets) != 1:
            raise InputFailure("Registered source must contain exactly one data sheet")
        rows = workbook.worksheets[0].iter_rows(values_only=True)
        header = next(rows, None)
        required = {"gene_name", "pert_group", "seed", "AB", "A", "B", "ctrl", "error", "rank"}
        if header is None or not required.issubset(header) or len(header) != len(set(header)):
            raise InputFailure(f"Unexpected source columns: {header}")
        for row in rows:
            if not any(v is not None for v in row):
                raise InputFailure("Empty source row inside registered data")
            yield dict(zip(header, row))
    finally:
        workbook.close()


def _same(mapping: dict, key, value: float, scope: str) -> None:
    if key in mapping and not math.isclose(mapping[key], value, abs_tol=TOLERANCE, rel_tol=0):
        raise InputFailure(f"Conflicting {scope}: {key!r}")
    mapping[key] = value


def prepare_records(records: Iterable[dict], expected_readouts: int | None = 1000) -> dict:
    observed = {}
    singles = {}
    control = {}
    control_rank = {}
    pairs = set()
    row_count = 0
    for row in records:
        row_count += 1
        if numeric(row.get("seed"), "seed") != 1:
            raise InputFailure("Source includes a seed other than the registered seed 1")
        original = str(row["pert_group"]).split("+")
        pair = canonical_pair(row["pert_group"])
        name = "+".join(pair)
        gene = str(row["gene_name"])
        if not gene or gene == "None":
            raise InputFailure("Missing readout-gene identity")
        if (name, gene) in observed:
            raise InputFailure(f"Duplicate pair/readout record: {name}/{gene}")
        vals = {field: numeric(row.get(field), field) for field in ("AB", "A", "B", "ctrl", "error")}
        residual = vals["AB"] - vals["A"] - vals["B"] + vals["ctrl"]
        if not math.isclose(residual, vals["error"], abs_tol=TOLERANCE, rel_tol=0):
            raise InputFailure(f"Published residual disagrees with condition means: {name}/{gene}")
        observed[(name, gene)] = residual
        _same(singles, (original[0], gene), vals["A"], "single profile")
        _same(singles, (original[1], gene), vals["B"], "single profile")
        _same(control, gene, vals["ctrl"], "control profile")
        if "rank" in row:
            _same(control_rank, gene, numeric(row["rank"], "rank"), "control-expression rank")
        pairs.add(name)

    genes = sorted(control)
    pair_names = sorted(pairs)
    if not pair_names or not genes:
        raise InputFailure("No complete pairs/readouts")
    if expected_readouts is not None and len(genes) != expected_readouts:
        raise InputFailure(f"Expected {expected_readouts} readout genes, observed {len(genes)}")
    if control_rank and set(control_rank.values()) != set(range(1, len(genes) + 1)):
        raise InputFailure("Control-ranked panel does not contain the complete registered rank interval")
    if row_count != len(pair_names) * len(genes):
        raise InputFailure("Incomplete pair-by-readout Cartesian coverage")

    features = []
    scores = []
    all_interventions = set()
    for name in pair_names:
        a, b = canonical_pair(name)
        all_interventions.update((a, b))
        try:
            va = np.asarray([singles[(a, g)] - control[g] for g in genes])
            vb = np.asarray([singles[(b, g)] - control[g] for g in genes])
            residual = np.asarray([observed[(name, g)] for g in genes])
        except KeyError as exc:
            raise InputFailure(f"Missing pair/readout or single-profile observation: {exc}") from exc
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        cosine = float(np.dot(va, vb) / (na * nb)) if na > 0 and nb > 0 else 0.0
        features.append([
            min(na, nb), max(na, nb), float(np.linalg.norm(va + vb)),
            float(np.clip(cosine, -1, 1)), float(np.linalg.norm(va - vb)), abs(na - nb),
        ])
        scores.append(float(np.sqrt(np.mean(residual * residual))))

    return {
        "pair_names": pair_names,
        "features": features,
        "outcomes": scores,
        "readout_genes": genes,
        "single_interventions": sorted(all_interventions),
        "rows": row_count,
        "source_units": "author-exported log-transformed expression units",
        "feature_names": ["min_single_norm", "max_single_norm", "additive_norm", "single_cosine", "difference_norm", "absolute_norm_difference"],
    }


def canonical_json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
