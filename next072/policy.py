"""Allocation policies. This module never receives the hidden outcome vector."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np

from .protocol import BATCH_SIZE, HIT_DEVIATION_FLOOR, HIT_THRESHOLD_QUANTILE, KERNEL_RIDGE, LINEAR_RIDGES


def hash_order(names, salt):
    return sorted(names, key=lambda name: (hashlib.sha256((salt + name).encode()).hexdigest(), name))


def standardize(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError("Features must be a finite two-dimensional matrix")
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    return (x - x.mean(axis=0)) / scale


def rbf_kernel(x):
    d2 = np.maximum(0.0, ((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
    nonzero = np.sqrt(d2[np.triu_indices(len(x), 1)])
    nonzero = nonzero[nonzero > 0]
    length = float(np.median(nonzero)) if len(nonzero) else 1.0
    return np.exp(-0.5 * d2 / (length * length)), length


def kernel_prediction(kernel, indices, y, candidates):
    y = np.asarray(y, dtype=float)
    center = float(y.mean())
    scale = float(y.std()) or 1.0
    train = kernel[np.ix_(indices, indices)] + KERNEL_RIDGE * np.eye(len(indices))
    cross = kernel[np.ix_(candidates, indices)]
    standardized = (y - center) / scale
    weights = np.linalg.solve(train, standardized)
    means = center + scale * (cross @ weights)
    projected = np.linalg.solve(train, cross.T)
    variance = np.maximum(0.0, 1.0 - (cross * projected.T).sum(axis=1))
    return means, scale * np.sqrt(variance)


def linear_prediction(x, indices, y, candidates):
    """LOO selection from fixed ridge values, using revealed references only."""
    observed_x = np.c_[np.ones(len(indices)), x[indices]]
    y = np.asarray(y, dtype=float)
    penalty = np.eye(observed_x.shape[1])
    penalty[0, 0] = 0.0
    fits = []
    for ridge in LINEAR_RIDGES:
        gram = observed_x.T @ observed_x + ridge * penalty
        inverse_x = np.linalg.solve(gram, observed_x.T)
        coefficient = inverse_x @ y
        diagonal = np.sum(observed_x * inverse_x.T, axis=1)
        denominator = 1.0 - diagonal
        if (np.abs(denominator) < 1e-12).any():
            loss = float("inf")
        else:
            loss = float(np.mean(((y - observed_x @ coefficient) / denominator) ** 2))
        fits.append((loss, ridge, coefficient))
    _, ridge, coefficient = min(fits, key=lambda item: (item[0], item[1]))
    return np.c_[np.ones(len(candidates)), x[candidates]] @ coefficient, ridge


def hit_threshold(initial_reference_values):
    """Fixed nearest-rank empirical quantile, with no interpolation."""
    values = sorted(float(value) for value in initial_reference_values)
    if not values or not np.isfinite(values).all():
        raise ValueError("Invalid initial reference values for hit threshold")
    return values[math.ceil(HIT_THRESHOLD_QUANTILE * len(values)) - 1]


def probability_of_hit_scores(means, deviations, threshold):
    """Rank Gaussian exceedance monotonically without CDF saturation ties.

    The floor is a numerical convention in source-expression units, not a
    measurement-noise estimate. Probabilities are model scores, not calibrated
    biological probabilities.
    """
    z = (np.asarray(means) - threshold) / np.maximum(deviations, HIT_DEVIATION_FLOOR)
    probabilities = np.asarray([0.5 * math.erfc(-float(value) / math.sqrt(2.0)) for value in z])
    return z, probabilities


@dataclass(frozen=True)
class PublicContext:
    names: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    reference_names: tuple[str, ...]
    reference_values: tuple[float, ...]
    query_budget: int


def allocate(context: PublicContext, reveal, policy: str) -> list[dict]:
    """Commit each batch before calling reveal; retain every actual query."""
    names = list(context.names)
    lookup = {name: i for i, name in enumerate(names)}
    if len(lookup) != len(names) or context.query_budget < 0:
        raise ValueError("Invalid pair identities or budget")
    raw = np.asarray(context.features, dtype=float)
    x = standardize(raw)
    if len(x) != len(names):
        raise ValueError("Feature rows do not match pair identities")
    if policy == "constant_features":
        x = np.zeros((len(x), 1))
    kernel, _ = rbf_kernel(x)
    observed = dict(zip(context.reference_names, context.reference_values))
    if len(observed) != len(context.reference_names) or not observed:
        raise ValueError("Invalid initial references")
    if not np.isfinite(list(observed.values())).all() or not set(observed).issubset(lookup):
        raise ValueError("Invalid reference observations")
    reference = dict(observed)
    threshold = hit_threshold(reference.values())
    selected = []
    pending = set(names) - set(observed)
    if context.query_budget > len(pending):
        raise ValueError("Reveal budget exceeds candidate set")
    hash_priority = None
    if policy.startswith("hash_"):
        number = int(policy.split("_")[1])
        if number not in range(32):
            raise ValueError("Unregistered hash control")
        hash_priority = {name: i for i, name in enumerate(hash_order(pending, f"NEXT072-RANDOM-{number:02d}"))}

    while len(selected) < context.query_budget:
        current = sorted(pending)
        candidate_idx = [lookup[name] for name in current]
        fit_data = reference if policy in ("static_kernel", "static_probability_of_hit") else observed
        fit_names = sorted(fit_data)
        fit_idx = [lookup[name] for name in fit_names]
        fit_y = [fit_data[name] for name in fit_names]
        means = np.zeros(len(current))
        deviations = np.zeros(len(current))
        extra = {}
        hit_probabilities = None
        if policy in ("probability_of_hit", "ordinary_equal_content", "static_probability_of_hit", "constant_features"):
            means, deviations = kernel_prediction(kernel, fit_idx, fit_y, candidate_idx)
            scores, hit_probabilities = probability_of_hit_scores(means, deviations, threshold)
            extra = {"hit_threshold_from_initial_references": threshold}
        elif policy in ("sequential_kernel", "static_kernel", "kernel_exploitation"):
            means, deviations = kernel_prediction(kernel, fit_idx, fit_y, candidate_idx)
            beta = 0.0 if policy == "kernel_exploitation" else 1.0
            scores = means + beta * deviations
        elif policy == "linear_ridge":
            means, ridge = linear_prediction(x, fit_idx, fit_y, candidate_idx)
            scores = means.copy()
            extra = {"ridge": ridge}
        elif policy == "additive_magnitude":
            scores = raw[candidate_idx, 2]
        elif policy == "diversity":
            distances = ((x[candidate_idx, None, :] - x[fit_idx][None, :, :]) ** 2).sum(axis=2)
            scores = distances.min(axis=1)
        elif hash_priority is not None:
            scores = np.asarray([-hash_priority[name] for name in current], dtype=float)
        else:
            raise ValueError(f"Unregistered policy: {policy}")
        if not np.isfinite(scores).all():
            raise ValueError("Nonfinite acquisition index")
        batch_size = min(BATCH_SIZE, context.query_budget - len(selected))
        if policy == "diversity":
            # Diversity can update on selected features without any outcomes.
            batch = []
            committed_scores = {}
            dist = np.asarray(scores).copy()
            for _ in range(batch_size):
                available = [j for j in range(len(current)) if j not in batch]
                j = min(available, key=lambda q: (-float(dist[q]), current[q]))
                batch.append(j)
                committed_scores[j] = float(dist[j])
                distance_new = ((x[candidate_idx] - x[candidate_idx[j]]) ** 2).sum(axis=1)
                dist = np.minimum(dist, distance_new)
        else:
            batch = sorted(range(len(current)), key=lambda j: (-float(scores[j]), current[j]))[:batch_size]
            committed_scores = {j: float(scores[j]) for j in batch}
        commitments = [
            {"pair": current[j], "prediction": float(means[j]), "acquisition_deviation": float(deviations[j]),
             "acquisition_index": committed_scores[j], "batch": len(selected) // BATCH_SIZE,
             "references_available_before_batch": len(fit_data), **extra,
             **({"model_hit_probability": float(hit_probabilities[j])} if hit_probabilities is not None else {})}
            for j in batch
        ]
        # All commitments above are computed before any outcome in this batch.
        for item in commitments:
            pair = item["pair"]
            item["remaining_budget_before"] = context.query_budget - len(selected)
            value = float(reveal(pair))
            if not np.isfinite(value):
                raise ValueError("Oracle returned a nonfinite reference value")
            item["revealed_D"] = value
            item["query_number"] = len(selected) + 1
            item["remaining_budget_after"] = context.query_budget - len(selected) - 1
            observed[pair] = value
            pending.remove(pair)
            selected.append(item)
    return selected
