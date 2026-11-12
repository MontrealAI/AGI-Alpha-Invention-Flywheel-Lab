# SPDX-License-Identifier: Apache-2.0
"""Frozen workshop contracts, observations and independent controls.

The connector supplies only the public contract to a builder. This module is
also the standalone replay/adapter interface shipped with an exported mission.
"""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import io
import json
import math
from pathlib import Path
from statistics import linear_regression

ARTIFACT = "instrument.json"
NIST = "https://www.itl.nist.gov/div898/handbook/mpc/section3/mpc37.htm"
WCAG = "https://www.w3.org/TR/2024/REC-WCAG22-20241212/#contrast-minimum"
WCAG_GUIDE = "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html"
NUMBER_FIELDS = ("low", "mid", "high", "reading")

PROFILES = {
    "optics": {"format": "csv", "origin": 2000, "scale": 100, "unit": "μm",
               "lower": 3, "upper": 7, "maxResidual": 0.25, "maxDrift": 0.5, "minSpan": 4,
               "beneficiary": "Thin-film workshop inspecting glass coupons with an optical micrometer."},
    "pressure": {"format": "json", "origin": 20, "scale": 4, "unit": "kPa",
                 "lower": 4, "upper": 8, "maxResidual": 0.5, "maxDrift": 0.75, "minSpan": 5,
                 "beneficiary": "Water-cartridge cooperative accepting a pressure-test batch."},
    "cold": {"format": "key-value", "origin": -3000, "scale": 100, "unit": "centi-°C",
             "lower": 2, "upper": 6, "maxResidual": 0.125, "maxDrift": 0.25, "minSpan": 6,
             "beneficiary": "Cold-chain operator distinguishing a logger offset from an excursion."},
}
SUPPORTED = "supported"
UNSUPPORTED = {"status": "unsupported", "corrected": None, "defect": None, "drift": None}

# Frozen before candidate inference. The two first optics rows have the same
# reading with different correct actions. Reference readings are synthetic.
CALIBRATION_CASES = (
    ("O01", "optics", (0, 5, 10, 8), True, True, (8, True, False)),
    ("O02", "optics", (4, 9, 14, 8), True, True, (4, False, True)),
    ("O03", "optics", (2, 7, 12, 11), True, True, (9, True, True)),
    ("O04", "optics", (0, 5, 10, 3), True, True, (3, False, False)),
    ("O05", "optics", (0, None, 10, 3), True, True, None),
    ("O06", "optics", (0, 5.5, 10, 3), True, True, None),
    ("P01", "pressure", (2, 8, 14, 8), True, True, (5, False, True)),
    ("P02", "pressure", (0, 4, 8, 6), True, True, (7.5, False, True)),
    ("P03", "pressure", (0, 5, 10, 8), True, True, (8, False, False)),
    ("P04", "pressure", (0, 5, 10, 3), False, True, None),
    ("P05", "pressure", (5, 3, 1, 3), True, True, None),
    ("P06", "pressure", (0, 5, 10, 11), True, True, None),
    ("C01", "cold", (0, 5, 10, 7), True, True, (7, True, False)),
    ("C02", "cold", (-1, 4, 9, 7), True, True, (8, True, True)),
    ("C03", "cold", (0, 5, 10, 7), True, False, None),
    ("C04", "cold", (0.25, 5.375, 10.25, 2.25), True, True, (2, False, False)),
    ("C05", "cold", (0, 2.5, 5, 3), True, True, None),
    ("C06", "cold", (0, 5, 10, None), True, True, None),
)

FRESH_CALIBRATION = (
    ("F01", "cold", (1, 6, 11, 3), True, True, (2, False, True)),
    ("F02", "cold", (1, 6.25, 11, 3), True, True, None),
    ("F03", "cold", (-0.5, 4.5, 9.5, 6.5), True, True, (7, True, True)),
    ("F04", "cold", (0, 5, 10, 2), True, True, (2, False, False)),
    ("F05", "cold", (0, 5, 10, 10), True, True, (10, True, False)),
    ("F06", "cold", (0, 5, None, 2), True, True, None),
)

CALIBRATION_CONTRACT = """Construct instrument.json to distinguish a product defect from sensor drift.
All inputs are normalized and present. Booleans: observed (all four readings present), trusted
(reference traceability declared), affine (the operating regime supports a stable affine hypothesis).
Numbers: low, mid, high, reading, lower, upper, maxResidual, maxDrift, minSpan.
The three physical standards have normalized true values 0, 5, and 10. Their measured values are
low, mid and high. The middle point is an independent challenge, never used to fit the endpoints.
A supported case needs all three booleans true, high-low >= minSpan, reading in [low,high],
and abs(mid-(low+high)/2) <= maxResidual. No division before support is established.
In supported cases corrected = 10*(reading-low)/(high-low). Compute defect as
(corrected < lower) or (corrected > upper). Use strict inequalities: equality at either limit
is acceptable. Drift means abs(low)>maxDrift OR abs(high-10)>maxDrift.
Emit exactly four output keys: status ("supported" or "unsupported"), corrected (number or null),
defect (boolean or null), drift (boolean or null). When unsupported all but status are null.
Missing readings are represented as zero with observed=false. A single sample cannot identify drift.
An ordinary regression with the same independent midpoint check is a strong comparator."""

CONTRAST_CONTRACT = """Construct instrument.json for a preflight of WCAG 2.2 criterion 1.4.3.
Inputs: sourceCurrent, measured, largeText, logo, incidental (booleans); ratio (number).
Decide in this order:
1. If sourceCurrent is false, finding is review and minimum is null.
2. Otherwise logo or incidental makes finding exception and minimum null. Incidental here means
an inactive control, pure decoration, text invisible to everyone, or text incidental to a picture
with significant other visual content. Brand styling alone is not an exception.
3. Otherwise an unmeasured ratio or a ratio outside [1,21] makes finding review and minimum null.
4. Otherwise minimum is 3 for largeText and 4.5 for ordinary text. Finding is pass exactly when
ratio >= minimum, else fail. Compare the unrounded ratio.
Use one threshold binding so both outputs apply the same rule. A compact decision expression
is choose(not sourceCurrent, 'review', choose(exempt, 'exception', choose(not usable,
'review', choose(ratio >= threshold, 'pass', 'fail')))). Here exempt means logo or incidental
and usable means measured and 1 <= ratio <= 21. The minimum is the threshold only when
sourceCurrent and usable and not exempt. Large text still requires a ratio at least 3.
Emit exactly {"finding":"review|exception|pass|fail","minimum":number or null}.
The minimum is null for review or exception. This is a scoped preflight, not a whole-site audit."""

ARRANGEMENT_CONTRACT = """Construct instrument.json for a voluntary shared-instrument planning screen.
Inputs: costItems (array of all full-horizon nonnegative costs for the shared route), separateCost
(full comparable independent route), cashNow (already received and available), cashDueNow (required
before delivery), laterPromises (uncollected and never available now), feeA/feeB, budgetA/budgetB,
outsideA/outsideB (outside route cost of each participant), acceptsA/acceptsB (hypothetical acceptance),
rightsReady, privacyReady (booleans). All money is integer cents with no separate ledger.
Calculate independent outputs first:
- fullCost = sum(costItems).
- liquid = cashNow >= cashDueNow. This output depends on these two inputs only.
- voluntary = acceptsA and acceptsB and feeA <= budgetA and feeA <= outsideA
  and feeB <= budgetB and feeB <= outsideB.
Select shared exactly when liquid and voluntary and rightsReady and privacyReady
and feeA + feeB >= fullCost and fullCost < separateCost.
Otherwise select separate_or_stop. Neither result authorizes spending.
Emit exactly {"fullCost":number,"liquid":boolean,"voluntary":boolean,"decision":"shared|separate_or_stop"}.
Voluntary is the conjunction of both acceptances and both fee tests. Labels are conditional only."""

FAMILIES = {
    "foundry": {"objective": "Distinguish defects from sensor drift for three inspection users.",
                "contract": CALIBRATION_CONTRACT, "scope": "affine-inspection/v1",
                "uncertainty": "Could the same reading be a product defect or a sensor offset?",
                "routes": ["Use one raw sample", "Use ordinary regression with qualified checks",
                           "Build three adapters independently", "Share an instrument after qualifying each adapter",
                           "Stop or gather a physical reference"],
                "sources": [{"url": NIST, "title": "NIST e-Handbook 2.3.7",
                             "role": "End and middle check standards for an assumed linear regime."}],
                "limits": "Synthetic readings. Requires traceable physical references, a qualified operating range and a stable affine regime in the field. A single midpoint cannot exclude every nonlinear or time-varying response."},
    "contrast": {"objective": "Check contrast claims and exceptions against WCAG 2.2.",
                 "contract": CONTRAST_CONTRACT, "scope": "wcag22-143/v1",
                 "uncertainty": "Does a low ratio violate the criterion, or is the exception actually applicable?",
                 "routes": ["Review the official criterion directly", "Use a contrast checker plus manual exception review",
                            "Construct a claim-and-exception decision instrument", "Request a missing measurement"],
                 "sources": [{"url": WCAG, "title": "WCAG 2.2 Recommendation, 12 December 2024, SC 1.4.3",
                              "role": "Thresholds and stated exceptions."},
                             {"url": WCAG_GUIDE, "title": "W3C Understanding SC 1.4.3",
                              "role": "Rounding and distinction between branding and logotypes."}],
                 "limits": "Checks supplied measurements and human-classified exceptions for one pinned criterion. It does not classify page content, measure pixels or certify a site."},
    "arrangement": {"objective": "Compare a shared inspection build with separate delivery and stopping.",
                    "contract": ARRANGEMENT_CONTRACT, "scope": "voluntary-cost-screen/v1",
                    "uncertainty": "Will each participant prefer the route, and can work start with available cash?",
                    "routes": ["Build separately", "Share a core and qualify separate adapters",
                               "Stage or change the offer", "Wait or stop"],
                    "sources": [],
                    "limits": "Hypothetical input only. Include development, inference, tools, verification, failed work, acquisition, delivery, maintenance, refunds and obligations as applicable. Assumes the independent cost and alternative inputs are complete; this is not a financial ledger or market validation."},
}


def scalar(text):
    if text in (None, ""):
        return None
    if type(text) not in (str, int, float):
        raise ValueError("Reading must be a finite number or missing.")
    value = float(text)
    if not math.isfinite(value) or abs(value) > 10**9:
        raise ValueError("Reading is outside the declared adapter range.")
    return value


def normalize(profile, raw):
    """Translate one declared transport into a typed common observation."""
    profile_info = PROFILES[profile]
    form = profile_info["format"]
    if form == "csv":
        reader = csv.DictReader(io.StringIO(raw), strict=True)
        columns = ["ref0_um", "ref5_um", "ref10_um", "sample_um", "traceable", "affine"]
        rows = list(reader)
        if reader.fieldnames != columns or len(rows) != 1 or None in rows[0] or None in rows[0].values():
            raise ValueError("Expected one optics CSV record with the documented header.")
        record = rows[0]
        values = [record[c] for c in columns[:4]]
        flags = [record["traceable"], record["affine"]]
    elif form == "json":
        from_json = portable_json(raw)
        if not isinstance(from_json, dict) or set(from_json) != {"references_kpa", "sample_kpa", "traceable", "affine"}:
            raise ValueError("Invalid pressure JSON contract.")
        refs = from_json["references_kpa"]
        if not isinstance(refs, list) or len(refs) != 3:
            raise ValueError("Expected three pressure references.")
        values = refs + [from_json["sample_kpa"]]
        flags = [from_json["traceable"], from_json["affine"]]
    else:
        fields = {}
        for line in raw.splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in fields:
                raise ValueError("Invalid or duplicate logger field.")
            fields[key] = value
        if set(fields) != {"ref_low", "ref_mid", "ref_high", "sample", "traceable", "affine"}:
            raise ValueError("Invalid cold-chain logger fields.")
        values = [fields[k] for k in ("ref_low", "ref_mid", "ref_high", "sample")]
        flags = [fields["traceable"], fields["affine"]]
    if form == "json":
        if any(type(v) is not bool for v in flags) or any(type(v) not in (type(None), int, float) for v in values):
            raise ValueError("Pressure JSON requires native booleans and numeric or null readings.")
    else:
        if any(v not in ("0", "1") for v in flags):
            raise ValueError("Traceability and affine declarations require 0 or 1.")
        flags = [v == "1" for v in flags]
    values = [scalar(v) for v in values]
    result = {k: 0 if v is None else (v - profile_info["origin"]) / profile_info["scale"] for k, v in zip(NUMBER_FIELDS, values)}
    result.update(observed=None not in values, trusted=flags[0], affine=flags[1])
    result.update({k: profile_info[k] for k in ("lower", "upper", "maxResidual", "maxDrift", "minSpan")})
    return result


def sample_raw(profile, values, trusted, affine):
    info = PROFILES[profile]
    vals = [None if v is None else info["origin"] + info["scale"] * v for v in values]
    if profile == "pressure":
        return json.dumps(dict(references_kpa=vals[:3], sample_kpa=vals[3], traceable=trusted, affine=affine))
    vals = ["" if v is None else str(v) for v in vals] + [str(int(trusted)), str(int(affine))]
    if profile == "optics":
        return "ref0_um,ref5_um,ref10_um,sample_um,traceable,affine\n" + ",".join(vals) + "\n"
    return "\n".join(f"{k}={v}" for k, v in zip(("ref_low", "ref_mid", "ref_high", "sample", "traceable", "affine"), vals)) + "\n"


def decision(corrected, defect, drift):
    return {"status": SUPPORTED, "corrected": corrected, "defect": defect, "drift": drift}


def calibration_cases(fresh=False):
    for ident, profile, measurements, trusted, affine, expected in FRESH_CALIBRATION if fresh else CALIBRATION_CASES:
        raw = sample_raw(profile, measurements, trusted, affine)
        yield {"id": ident, "profile": profile, "raw": raw, "input": normalize(profile, raw),
               "expected": dict(UNSUPPORTED) if expected is None else decision(*expected)}


def library_control(row):
    """Python standard-library endpoint fit with the same reference access."""
    lo, mid, hi, sample = (row[k] for k in NUMBER_FIELDS)
    if (not all(row[k] for k in ("observed", "trusted", "affine"))
            or hi - lo < row["minSpan"] or not lo <= sample <= hi):
        return dict(UNSUPPORTED)
    slope, offset = linear_regression((0, 10), (lo, hi))
    if abs(mid - (slope * 5 + offset)) > row["maxResidual"]:
        return dict(UNSUPPORTED)
    corrected = (sample - offset) / slope
    return decision(corrected, not row["lower"] <= corrected <= row["upper"],
                    max(abs(lo), abs(hi - 10)) > row["maxDrift"])


def interpolation_control(row):
    """Independent exact interpolation comparator, using the same adapter inputs."""
    if not row["observed"] or not row["trusted"] or not row["affine"]:
        return dict(UNSUPPORTED)
    a, b, c, x = map(lambda k: Fraction(row[k]), NUMBER_FIELDS)
    if c - a < row["minSpan"] or abs(2 * b - a - c) > 2 * row["maxResidual"] or x < a or x > c:
        return dict(UNSUPPORTED)
    position = 10 * (x - a) / (c - a)
    return decision(float(position), position < row["lower"] or position > row["upper"],
                    abs(a) > row["maxDrift"] or abs(c - 10) > row["maxDrift"])


def contrast_cases():
    rows = (
        ("T01", True, True, False, False, False, 4.5, "pass", 4.5),
        ("T02", True, True, False, False, False, 4.499, "fail", 4.5),
        ("T03", True, True, True, False, False, 3, "pass", 3),
        ("T04", True, True, True, False, False, 2.99, "fail", 3),
        ("T05", True, False, False, True, False, 0, "exception", None),
        ("T06", True, False, False, False, True, 0, "exception", None),
        ("T07", True, False, False, False, False, 0, "review", None),
        ("T08", False, True, True, True, False, 12, "review", None),
        ("T09", True, True, False, False, False, 22, "review", None),
    )
    fields = ("sourceCurrent", "measured", "largeText", "logo", "incidental", "ratio")
    for ident, *rest in rows:
        yield {"id": ident, "input": dict(zip(fields, rest[:6])),
               "expected": dict(finding=rest[6], minimum=rest[7])}


def arrangement_cases():
    # Cost order: development, adaptations, inference/tools, verification,
    # failed work, acquisition/delivery, maintenance, refunds/obligations.
    base = dict(costItems=[18000, 9000, 3000, 5000, 2000, 4000, 6000, 3000],
                separateCost=67000, cashNow=30000, cashDueNow=25000, laterPromises=30000,
                feeA=26000, feeB=26000, budgetA=30000, budgetB=30000,
                outsideA=31000, outsideB=29000, acceptsA=True, acceptsB=True,
                rightsReady=True, privacyReady=True)
    rows = (
        ("E01", {}, True, True, "shared", 50000),
        ("E02", {"cashNow": 8000, "laterPromises": 60000}, False, True, "separate_or_stop", 50000),
        ("E03", {"outsideB": 25000}, True, False, "separate_or_stop", 50000),
        ("E04", {"privacyReady": False}, True, True, "separate_or_stop", 50000),
        ("E05", {"feeA": 20000}, True, True, "separate_or_stop", 50000),
        ("E06", {"separateCost": 50000}, True, True, "separate_or_stop", 50000),
        ("E07", {"acceptsA": False}, True, False, "separate_or_stop", 50000),
        ("E08", {"budgetB": 20000}, True, False, "separate_or_stop", 50000),
        ("E09", {"costItems": [18000, 9000, 3000, 5000, 2000, 4000, 6000, 9000]},
         True, True, "separate_or_stop", 56000),
        ("E10", {"rightsReady": False}, True, True, "separate_or_stop", 50000),
    )
    for ident, change, liquid, voluntary, selection, total in rows:
        yield {"id": ident, "input": dict(base, **change),
               "expected": dict(fullCost=total, liquid=liquid, voluntary=voluntary, decision=selection)}


def observations(family, fresh=False):
    if family == "foundry":
        return list(calibration_cases(fresh))
    if family == "contrast":
        return list(contrast_cases())
    if family == "arrangement":
        return list(arrangement_cases())
    return []


def portable_json(raw):
    if __package__:
        from .instruments import strict_portable_json
    else:
        from RUN_INSTRUMENT import strict_portable_json
    return strict_portable_json(raw)


def compare(family, rows):
    """Return executed ordinary controls and the sample-only ambiguity."""
    if family != "foundry":
        return {}
    def sample_only(row):
        return (row["reading"] < row["lower"] or row["reading"] > row["upper"]) if row["observed"] else None
    return {
        "sample_only": [{"id": row["id"], "defect": sample_only(row["input"]),
                         "expected_defect": row["expected"]["defect"]} for row in rows],
        "stdlib_fit": [{"id": row["id"], "output": library_control(row["input"])} for row in rows],
        "exact_interpolation": [{"id": row["id"], "output": interpolation_control(row["input"])} for row in rows],
    }


def main():
    parser = argparse.ArgumentParser(description="Run the exported bounded workshop instrument independently.")
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="Run one input file.")
    run.add_argument("input", type=Path)
    run.add_argument("--profile", choices=PROFILES, help="Adapt raw sensor data, or omit for a normalized JSON object.")
    sub.add_parser("check", help="Replay every frozen observation from PROOF.json.")
    args = parser.parse_args()
    from RUN_INSTRUMENT import evaluate
    here = Path(__file__).resolve().parent
    spec = portable_json((here / ARTIFACT).read_bytes())
    proof = portable_json((here / "PROOF.json").read_bytes())
    if args.action == "run":
        if args.input.stat().st_size > 1_048_576:
            parser.error("Input exceeds 1 MiB.")
        raw = args.input.read_text(encoding="utf-8")
        observation = normalize(args.profile, raw) if args.profile else portable_json(raw)
        print(json.dumps(evaluate(spec, observation, proof["max_operations"]), ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    checked = []
    for case in proof["observations"]:
        observation = normalize(case["profile"], case["raw"]) if "profile" in case else case["input"]
        try:
            actual = evaluate(spec, observation, proof["max_operations"])["output"]
            from RUN_INSTRUMENT import _json_equal
            checked.append({"id": case["id"], "passed": _json_equal(actual, case["expected"]), "actual": actual})
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            checked.append({"id": case["id"], "passed": False, "error": str(error)})
    passed = bool(checked) and all(row["passed"] for row in checked)
    print(json.dumps({"passed": passed, "checks": checked}, ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
