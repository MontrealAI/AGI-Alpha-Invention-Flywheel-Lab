"""Replay the post-reveal TOI-216 shoulder diagnostic from public Sector 64 FITS."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares
import transit_cascade


COLUMNS = {"TIME": ">f8", "QUALITY": ">i4", "SAP_FLUX": ">f4", "SAP_FLUX_ERR": ">f4",
           "PDCSAP_FLUX": ">f4", "PDCSAP_FLUX_ERR": ">f4"}


def quality_rows(raw, reducer):
    _, extension = reducer["fits_header"](raw, 0)
    header, data_offset = reducer["fits_header"](raw, extension)
    offsets = {}
    cursor = 0
    for idx in range(1, int(header["TFIELDS"]) + 1):
        column, form = header[f"TTYPE{idx}"], header[f"TFORM{idx}"]
        offsets[column] = cursor
        cursor += int(form[:-1] or 1) * reducer["FITS_FIELD_BYTES"][form[-1]]
    dtype = np.dtype({"names": list(COLUMNS), "formats": list(COLUMNS.values()),
                      "offsets": [offsets[col] for col in COLUMNS], "itemsize": int(header["NAXIS1"])})
    rows = np.frombuffer(raw, dtype, count=int(header["NAXIS2"]), offset=data_offset)
    clean = rows[(rows["QUALITY"] == 0) & np.isfinite(rows["TIME"])]
    return np.sort(clean, order="TIME")


def isolated_shapes(reducer, source, inner):
    shapes = []
    for row in inner["isolated_dips"]:
        midpoint = row["frozen_mid_bjd_tdb"]
        time = (source.time - (midpoint - source.reference)) * 24
        selected = np.abs(time) <= 12
        t, f, e = time[selected], source.flux[selected], source.error[selected]
        median = np.median(f)
        window = reducer["Window"](t, (f / median - 1) * 1000, e / median * 1000,
                                   source.cadence, inner["nominal_duration_hour"], (-0.5, 0.5))
        candidate = reducer["fit_candidate"](window, 0)
        if candidate is None:
            raise ValueError(f"Unable to fit isolated template {row['id']}")
        duration, ingress, curvature, depth = map(float, candidate.parameters[1:5])
        shapes.append({**row, "duration_hour": duration, "ingress_fraction": ingress,
                       "curvature": curvature, "depth_ppt": depth})
    return shapes


def overlap_trials(reducer, source, rows, time, shift, inner, outer, shapes):
    lower = np.array([-0.60, 4.3, 0.05, 0, 0, -np.inf, -np.inf, -np.inf])
    upper = np.array([0.60, 6.7, 0.49, 0.9, 80, np.inf, np.inf, np.inf])
    init = np.array([0, 5.5, 0.16, 0.30, 18, 0, 0, 0])
    settings = dict(loss="soft_l1", f_scale=2.5, x_scale="jac", max_nfev=200)
    trials = []
    for column in ("PDCSAP_FLUX", "SAP_FLUX"):
        uncertainty = column + "_ERR"
        mask = ((np.abs(time) <= 10.8) & np.isfinite(rows[column])
                & np.isfinite(rows[uncertainty]) & (rows[uncertainty] > 0))
        t, f, e = time[mask], rows[column][mask].astype(float), rows[uncertainty][mask].astype(float)
        median = np.median(f)
        f, e = (f / median - 1) * 1000, e / median * 1000
        white = reducer["mad"](np.diff(f)[np.diff(t) < 1.5 * source.cadence]) / np.sqrt(2)
        e = np.hypot(e, np.sqrt(max(0, white ** 2 - np.median(e) ** 2)))
        win = reducer["Window"](t, f, e, source.cadence, outer["nominal_duration_hour"], (-0.60, 0.60))
        for rounded in (False, True):
            def main(p):
                return reducer["standardized_residuals"](p, win, 0, rounded)

            single = least_squares(main, init, bounds=(lower, upper), **settings)
            white_factor, beta = reducer["noise_scales"](win, single.fun, single.x)
            shift_uncertainty = inner["catalogue_uncertainty_days"] * 24
            shifts = (-3 * shift_uncertainty, 0.0, 3 * shift_uncertainty)
            for shape in shapes:
                for center_shift in shifts:
                    template = reducer["integrated_dip"](t - shift - center_shift, shape["duration_hour"],
                                                         shape["ingress_fraction"], shape["curvature"],
                                                         source.cadence, False) / e
                    both = least_squares(lambda p: main(p[:-1]) + p[-1] * template, np.r_[single.x, 0.0],
                                         bounds=(np.r_[lower, -20], np.r_[upper, 30]), **settings)

                    def at_depth(depth):
                        trial = least_squares(lambda p: main(p) + depth * template, both.x[:-1],
                                              bounds=(lower, upper), **settings)
                        if not trial.success:
                            raise ValueError("Profile fit failed to converge")
                        return trial.cost

                    if not single.success or not both.success:
                        raise ValueError("Transit fit failed to converge")
                    null_cost = at_depth(0)
                    constrained_cost = min(null_cost, both.cost) if both.x[-1] >= 0 else null_cost
                    cn = (white_factor * beta) ** 2
                    lower_depth = max(0, both.x[-1])
                    upper_depth = brentq(lambda d: 2 * (at_depth(d) - constrained_cost) / cn - 2.71,
                                         lower_depth, 15)
                    controls = {str(d): float(2 * (at_depth(d) - null_cost) / cn)
                                for d in inner["depth_controls_ppt"]}
                    trials.append({"flux_column": column, "outer_rounded_contacts": rounded,
                                   "secondary_template_id": shape["id"], "shift_min": 60 * center_shift,
                                   "fitted_secondary_depth_ppt": float(both.x[-1]),
                                   "profile_upper_depth_ppt": float(upper_depth),
                                   "fixed_depth_deviance_increase_vs_zero": controls,
                                   "outer_fit_depth_ppt": float(single.x[4]),
                                   "outer_fit_duration_hour": float(single.x[1]),
                                   "outer_fit_mid_bjd_tdb": float(outer["catalogue_mid_bjd_tdb"] + single.x[0] / 24),
                                   "white_noise_scale": white_factor, "time_correlated_noise_scale": beta})
    return trials


def run(inputs, fits):
    reducer_bytes = Path(transit_cascade.__file__).read_bytes()
    if sha256(reducer_bytes).hexdigest() != inputs["reducer_sha256"]:
        raise ValueError("Unexpected reducer SHA-256")
    reducer = vars(transit_cascade)
    raw = fits.read_bytes()
    if len(raw) != inputs["product_bytes"] or sha256(raw).hexdigest() != inputs["product_sha256"]:
        raise ValueError("Unexpected FITS byte count or SHA-256")
    source = reducer["fits_light_curve"](raw, inputs["product_sha256"])
    for key in ("tic_id", "sector"):
        if source.receipt[key] != inputs[key]:
            raise ValueError(f"Unexpected FITS {key}")
    rows = quality_rows(raw, reducer)
    inner, outer = inputs["inner"], inputs["outer"]
    reference = outer["catalogue_mid_bjd_tdb"]
    time = (rows["TIME"] - (reference - source.reference)) * 24
    inner_shift = (inner["catalogue_mid_bjd_tdb"] - reference) * 24
    shapes = isolated_shapes(reducer, source, inner)
    trials = overlap_trials(reducer, source, rows, time, inner_shift, inner, outer, shapes)
    return {"purpose": inputs["purpose"], "fits_sha256": inputs["product_sha256"],
            "reducer_sha256": inputs["reducer_sha256"], "sector": source.receipt["sector"],
            "tic_id": source.receipt["tic_id"], "quality_rule": "QUALITY == 0",
            "inner_reference_minus_outer_minutes": inner_shift * 60,
            "quality_zero_cadences_within_2_77h_outer": int(np.count_nonzero(np.abs(time) <= 2.77)),
            "quality_zero_cadences_within_1_30h_inner": int(np.count_nonzero(np.abs(time - inner_shift) <= 1.30)),
            "isolated_shapes": shapes, "models": trials}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--fits", required=True, type=Path)
    args = parser.parse_args()
    output = run(json.loads(args.inputs.read_bytes()), args.fits)
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
