"""Measure whether held KTC boundary voltages are identifiable from visible channels."""

from argparse import ArgumentParser
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
from time import perf_counter_ns, process_time_ns
from zipfile import ZipFile

import numpy as np
from scipy.io import loadmat
from scipy.linalg import svd

REGISTRATION = "7529e43338381b50d4ef5e852071756461d251c1"
NAMES = ("EvaluationData.zip", "EvaluationData_full.zip")
PINS = {
    NAMES[0]: (426229, "b23be74ac5951ae93a12351552a12c5c"),
    NAMES[1]: (599040, "340d9751f62001b0cc0e1a869bd429a6"),
    "Codes_Python.zip": (3201639, "aaf8ee2e9fb6c64e5ae6f5d18141e940"),
}
CASE_PATH = re.compile(r"(?:^|/)level_?([1-7])/data([1-3])\.mat$", re.I)


def checked_bytes(raw, file_name):
    size, md5 = PINS[file_name]
    if len(raw) != size or hashlib.md5(raw, usedforsecurity=False).hexdigest() != md5:
        raise ValueError(f"archive does not match publisher's version: {file_name}")
    return hashlib.sha256(raw).hexdigest()


def archive(directory, name):
    with (directory / name).open("rb") as f:
        payload = f.read(PINS[name][0] + 1)
    digest = checked_bytes(payload, name)
    return ZipFile(BytesIO(payload)), digest


def inventory(z):
    result = {}
    for path in z.namelist():
        match = CASE_PATH.search(path)
        if not match:
            continue
        key = tuple(int(x) for x in match.groups())
        if key in result:
            raise ValueError(f"duplicate source coordinates {key}")
        result[key] = path
    if set(result) != {(level, case) for level in range(1, 8) for case in range(1, 4)}:
        raise ValueError("incomplete official archive case set")
    return result


def read_mat(z, path):
    if z.getinfo(path).file_size > 100_000:
        raise ValueError("oversized phantom record")
    return loadmat(BytesIO(z.read(path)), variable_names=["Inj", "Mpat", "Uel"])


def patterns(i, m, level):
    if i.shape != (32, 76) or m.shape != (32, 31):
        raise ValueError("unexpected full-array shape")
    if not (np.isfinite(i).all() and np.isin(m, [-1, 0, 1]).all()
            and np.all(i.sum(axis=0) == 0) and np.all(m.sum(axis=0) == 0)
            and np.all((i != 0).sum(axis=0) == 2) and np.all((m != 0).sum(axis=0) == 2)):
        raise ValueError("not the registered paired-drive, paired-sense design")
    drop = 2 * (level - 1)
    drives = np.flatnonzero(~np.any(i[:drop], axis=0))
    senses = np.flatnonzero(~np.any(m[:drop], axis=0))
    visible = np.zeros((76, 31), dtype=bool)
    visible[np.ix_(drives, senses)] = True
    return drives, senses, visible.ravel()


def observations(limited, full, level):
    i, m = full["Inj"], full["Mpat"]
    drives, senses, visible = patterns(i, m, level)
    drop = 2 * (level - 1)
    for name, values, keep in (("Inj", i, drives), ("Mpat", m, senses)):
        reference = limited[name]
        possibilities = (values, values[:, keep], values[drop:, keep])
        if not any(np.array_equal(reference, opt) for opt in possibilities):
            raise ValueError(f"reduced {name} coordinates conflict with full archive")
    complete = full["Uel"].ravel(order="F")
    reduced = limited["Uel"].ravel(order="F")
    if complete.size != visible.size or not np.isfinite(complete).all():
        raise ValueError("full archive lacks finite source readings")
    if reduced.size == complete.size:
        if np.any(reduced[~visible] != 0):
            raise ValueError("full-size reduced data have nonzero values at omitted positions")
        reduced = reduced[visible]
    if not np.array_equal(reduced, complete[visible]):
        raise ValueError("source overlap disagrees at matched measured coordinates")
    return i, m, complete, visible


def design(i, m):
    # All currents in one drive have the same absolute amplitude. Pull it
    # outside each functional to keep the observability design integer.
    drive = np.repeat(np.sign(i).T.astype(np.int8), m.shape[1], axis=0)
    sense = np.tile(m.T.astype(np.int8), (i.shape[1], 1))
    r, c = np.triu_indices(i.shape[0])
    coefficients = drive[:, r] * sense[:, c]
    off = r != c
    coefficients[:, off] += drive[:, c[off]] * sense[:, r[off]]
    return coefficients, r, c


def conventional(matrix, visible):
    retained = matrix[visible]
    _, singular, vt = svd(retained.astype(float), full_matrices=False, check_finite=False)
    rank = int(np.count_nonzero(singular > np.finfo(float).eps * max(retained.shape) * singular[0]))
    basis = vt[:rank]
    missing = matrix[~visible].astype(float)
    error = np.linalg.norm(missing - (missing @ basis.T) @ basis, axis=1)
    tolerance = 16 * np.finfo(float).eps * max(retained.shape) * np.linalg.norm(missing, axis=1)
    return rank, error <= tolerance, error


def coordinate_witnesses(matrix, visible):
    # A previously unobserved symmetric operator entry is an exact null
    # direction wherever the corresponding omitted coefficient is nonzero.
    free = ~np.any(matrix[visible], axis=0)
    hidden = (matrix[~visible] != 0) & free
    has_witness = np.any(hidden, axis=1)
    locations = np.where(has_witness, np.argmax(hidden, axis=1), -1)
    return locations


def independent_check(i, m, visible, witnesses, rr, cc):
    """Recheck the claimed perturbations by contracting one entry directly."""
    s = m.shape[1]
    visible_index = np.flatnonzero(visible)
    di, si = visible_index // s, visible_index % s
    current = np.sign(i).astype(np.int16)
    sense = m.astype(np.int16)
    for index, coordinate in zip(np.flatnonzero(~visible), witnesses, strict=True):
        if coordinate == -1:
            continue
        if not 0 <= coordinate < len(rr):
            return False
        r, c = rr[coordinate], cc[coordinate]
        actual = current[r, index // s] * sense[c, index % s]
        affected = current[r, di] * sense[c, si]
        if r != c:
            actual += current[c, index // s] * sense[r, index % s]
            affected += current[c, di] * sense[r, si]
        if not actual or np.any(affected):
            return False
    return True


def measure(fn, *args):
    wall, cpu = perf_counter_ns(), process_time_ns()
    result = fn(*args)
    return result, {"wall_ms": (perf_counter_ns() - wall) / 1e6,
                    "cpu_ms": (process_time_ns() - cpu) / 1e6}


def score(i, m, values, visible):
    (coefficients, rr, cc), setup_cost = measure(design, i, m)
    (rank, determined, residual), incumbent_cost = measure(conventional, coefficients, visible)
    witnesses, constructor_cost = measure(coordinate_witnesses, coefficients, visible)
    valid, verify_cost = measure(independent_check, i, m, visible, witnesses, rr, cc)
    if not valid:
        raise ValueError("independent algebraic check failed")
    if np.any((witnesses >= 0) & determined):
        raise ValueError("exact witness contradicts conventional rank analysis")
    errors = []
    if determined.any():
        gains = np.repeat(np.max(np.abs(i), axis=0), m.shape[1])
        y = values[visible] / gains[visible]
        estimate = np.linalg.lstsq(coefficients[visible], y, rcond=None)[0]
        recovered = (coefficients[~visible][determined] @ estimate) * gains[~visible][determined]
        errors = np.abs(recovered - values[~visible][determined]).tolist()
    indices = np.flatnonzero(~visible)
    usable = np.flatnonzero(witnesses >= 0)
    sample = None
    if usable.size:
        row = usable[0]
        p = witnesses[row]
        sample = {"drive_index_zero_based": int(indices[row] // 31),
                  "sense_index_zero_based": int(indices[row] % 31),
                  "one_symmetric_entry_zero_based": [int(rr[p]), int(cc[p])]}
    return {"reported_full_measurements": int(len(values)), "same_visible_readings": int(visible.sum()),
            "withheld_measured_readings": int(len(indices)), "visible_rank": rank,
            "conventional_identified": int(determined.sum()),
            "exact_certificates_verified": int(usable.size),
            "minimum_withheld_design_residual": float(np.min(residual)) if residual.size else None,
            "source_unit_recovery_errors": errors, "one_counterexample": sample,
            "stage_costs": {"shared_design": setup_cost, "conventional": incumbent_cost,
                            "constructor": constructor_cost, "independent_check": verify_cost},
            "certificate_indices_sha256": hashlib.sha256(witnesses.astype("<i2").tobytes()).hexdigest()}


def development_controls():
    checked = []
    try:
        checked_bytes(b"wrong public archive", NAMES[0])
    except ValueError:
        checked.append("wrong_archive_digest")
    else:
        raise AssertionError("wrong archive digest was accepted")
    i = np.array([[1, 0], [-1, 1], [0, -1]])
    m = i.copy()
    a, rr, cc = design(i, m)
    visible = np.array([True, True, False, False])
    _, determined, _ = conventional(a, visible)
    w = coordinate_witnesses(a, visible)
    if determined.tolist() != [True, False] or w[0] != -1 or w[1] < 0:
        raise AssertionError("reciprocal positive control or missing direction failed")
    if not independent_check(i, m, visible, w, rr, cc):
        raise AssertionError("counterexample control did not verify")
    w[1] = 0
    if independent_check(i, m, visible, w, rr, cc):
        raise AssertionError("modified null witness was accepted")
    return [*checked, "known_reciprocal_omitted_reading_identifiable", "modified_null_witness"]


def evaluate(directory):
    controls = development_controls()
    cases = []
    faults = []
    limited_zip, limited_digest = archive(directory, NAMES[0])
    full_zip, full_digest = archive(directory, NAMES[1])
    with limited_zip as limited, full_zip as full:
        li, fi = inventory(limited), inventory(full)
        for key in sorted(li):
            try:
                small, complete = read_mat(limited, li[key]), read_mat(full, fi[key])
                inputs = observations(small, complete, key[0])
                metrics, costs = measure(score, *inputs)
                cases.append({"level": key[0], "phantom": key[1], **metrics, "compute": costs})
                if key == (1, 1):
                    changed = {**small, "Uel": small["Uel"].copy()}
                    changed["Uel"].flat[0] += 1.0
                    try:
                        observations(changed, complete, key[0])
                    except ValueError:
                        controls.append("modified_retained_reading")
                    else:
                        raise AssertionError("modified source voltage was accepted")
                    changed = {**small, "Mpat": small["Mpat"].copy()}
                    changed["Mpat"].flat[0] += 1
                    try:
                        observations(changed, complete, key[0])
                    except ValueError:
                        controls.append("inconsistent_read_coordinates")
                    else:
                        raise AssertionError("modified source coordinates were accepted")
            except (KeyError, ValueError, np.linalg.LinAlgError) as error:
                faults.append({"level": key[0], "phantom": key[1], "error": str(error)})
    if sum(row["withheld_measured_readings"] == 0 for row in cases if row["level"] == 1) == 3:
        controls.append("all_active_level")
    digests = dict(zip(NAMES, (limited_digest, full_digest), strict=True))
    return {"schema": "frontier/ktc-observation-admissibility/v1", "registration": REGISTRATION,
            "executable_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "source_doi": "10.5281/zenodo.10986692", "archive_sha256": digests, "cases": cases,
            "failures": faults, "controls": controls,
            "adoption": "ABSTAIN", "physical_site_costed_acceptance": False,
            "interpretation": "Exact structural witnesses under a symmetric linear electrical response. "
                              "The full direct archive is available. No physical field quality or price measured."}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    if args.development:
        output = {"development_controls": development_controls()}
    else:
        if args.data_dir is None:
            parser.error("--data-dir is required for the evaluation")
        output = evaluate(args.data_dir)
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
