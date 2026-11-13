"""Conservative four-force uncertainty certificate for an unvalidated mixed contact.

All outputs are conditional on user-declared measurement and error values.
This code never validates calibration, sensor provenance, mixed-surface transfer,
safety, WCAG, buyer acceptance or a physical device.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "contact-transfer150/force-contract/v1"
THRESHOLD = Decimal("0.05")
SOURCE_FIXTURE_SHA256 = "7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced"
REGISTRATION_SHA256 = "6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa"
NOMINAL = (
    ("0.01", "0.04296481068177409", "0.04271352018282576"),
    ("0.10", "4.700545225035074", "3.9902611168911872"),
)
KEYS = frozenset(("schema", "scope", "source_declaration", "provenance", "force_unit", "velocity_mm_s", "states"))
STATE_KEYS = frozenset(("indentation_mm", "static_N", "dynamic_N", "static_error_N", "dynamic_error_N"))


def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("DUPLICATE_JSON_FIELD:" + k)
        out[k] = v
    return out


def _reject_constant(v):
    raise ValueError("NONFINITE_JSON:" + v)


def parse(raw: bytes):
    if len(raw) > 65536:
        raise ValueError("BOUNDED_RECORD_REQUIRED")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=_reject_constant)
    except UnicodeDecodeError as exc:
        raise ValueError("UTF8_REQUIRED") from exc


def decimal_text(value, *, positive=False):
    if not isinstance(value, str) or len(value) > 120:
        raise ValueError("FINITE_DECIMAL_STRING_REQUIRED")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("FINITE_DECIMAL_STRING_REQUIRED") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0) or (number and number.adjusted() < -100) or number > Decimal("1e9"):
        raise ValueError("POSITIVE_FINITE_BOUNDED_NUMBER_REQUIRED")
    return number


def _display_fraction(value: Fraction, rounding) -> str:
    """Display an exact rational with a directed rounding guarantee at 80 digits.

    The acceptance comparison itself is performed on the exact Fraction,
    never on this presentation string.
    """
    with localcontext() as context:
        context.prec = 80
        context.rounding = rounding
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def measure(record):
    if type(record) is not dict or frozenset(record) != KEYS:
        raise ValueError("EXACT_RECORD_FIELDS_REQUIRED")
    if record["schema"] != SCHEMA or record["scope"] not in ("SOURCE_MODEL_DEMO", "EXTERNAL_DECLARED_UNVERIFIED"):
        raise ValueError("SCHEMA_AND_NONCERTIFYING_SCOPE_REQUIRED")
    for key in ("source_declaration", "provenance"):
        text = record[key]
        if not isinstance(text, str) or not text.strip() or len(text) > 500:
            raise ValueError("SOURCE_DECLARATION_AND_PROVENANCE_REQUIRED")
    if record["force_unit"] != "N" or decimal_text(record["velocity_mm_s"]) != Decimal("0.1"):
        raise ValueError("FROZEN_FORCE_UNIT_AND_VELOCITY_REQUIRED")
    if type(record["states"]) is not list or len(record["states"]) != 2:
        raise ValueError("TWO_FROZEN_LOAD_STATES_REQUIRED")
    states = []
    for i, state in enumerate(record["states"]):
        if type(state) is not dict or frozenset(state) != STATE_KEYS:
            raise ValueError("EXACT_STATE_FIELDS_REQUIRED")
        expected_indent = (Decimal("0.01"), Decimal("0.10"))[i]
        if decimal_text(state["indentation_mm"]) != expected_indent:
            raise ValueError("FROZEN_LOAD_ORDER_REQUIRED")
        s = decimal_text(state["static_N"], positive=True)
        d = decimal_text(state["dynamic_N"], positive=True)
        es = decimal_text(state["static_error_N"])
        ed = decimal_text(state["dynamic_error_N"])
        if es >= s or ed >= d:
            raise ValueError("POSITIVE_FORCE_INTERVAL_REQUIRED")
        lower = (Fraction(s) - Fraction(es)) / (Fraction(d) + Fraction(ed))
        upper = (Fraction(s) + Fraction(es)) / (Fraction(d) - Fraction(ed))
        if lower > upper:
            raise ValueError("INVALID_RATIO_BOUNDS")
        states.append({"ratio_lower": lower, "ratio_upper": upper,
                       "ratio_nominal": Fraction(s) / Fraction(d)})
    lower_change = states[1]["ratio_lower"] - states[0]["ratio_upper"]
    upper_change = states[1]["ratio_upper"] - states[0]["ratio_lower"]
    nominal_change = states[1]["ratio_nominal"] - states[0]["ratio_nominal"]
    sufficient = lower_change >= Fraction(THRESHOLD)
    return {
        "schema": "contact-transfer150/numeric-contract-result/v1",
        "declared_input_scope": record["scope"],
        "source_declaration": record["source_declaration"],
        "source_fixture_sha256": SOURCE_FIXTURE_SHA256,
        "registration_sha256": REGISTRATION_SHA256,
        "threshold": str(THRESHOLD),
        "load_ratios": [
            {k: _display_fraction(v, ROUND_FLOOR if k == "ratio_lower"
                                   else ROUND_CEILING if k == "ratio_upper"
                                   else ROUND_HALF_EVEN)
             for k, v in state.items()} for state in states
        ],
        "nominal_change": _display_fraction(nominal_change, ROUND_HALF_EVEN),
        "lower_change": _display_fraction(lower_change, ROUND_FLOOR),
        "upper_change": _display_fraction(upper_change, ROUND_CEILING),
        "precision_contract": "EXACT_RATIONAL_DECISION_80_DIGIT_OUTWARD_ROUNDED_BOUNDS",
        "numeric_verdict": "SUFFICIENT_WITHIN_DECLARED_BOUNDS" if sufficient else "HOLD_DECLARED_BOUNDS_ALLOW_FAILURE",
        "physical_transfer_verified": False,
        "error_model_independently_validated": False,
        "device_safety_or_beneficiary_acceptance": False,
        "commercial_customer_or_revenue": False,
        "interpretation": "Conditional interval arithmetic only. No laboratory evidence, physical transfer or error guarantee is independently established.",
    }


def source_model_demo(epsilon: Decimal):
    if not epsilon.is_finite() or epsilon < 0 or epsilon >= Decimal("1"):
        raise ValueError("FINITE_RELATIVE_ERROR_REQUIRED")
    return {
        "schema": SCHEMA, "scope": "SOURCE_MODEL_DEMO",
        "source_declaration": "Published single-contact source-model interpolation; mixed-surface measurements not acquired",
        "provenance": "Fu et al. Fig S9 source-calibration model via blue-sky064 fixed nominal computation; synthetic design preflight",
        "force_unit": "N", "velocity_mm_s": "0.1",
        "states": [
            {"indentation_mm": indentation, "static_N": static, "dynamic_N": dynamic,
             "static_error_N": str(Decimal(static) * epsilon),
             "dynamic_error_N": str(Decimal(dynamic) * epsilon)}
            for indentation, static, dynamic in NOMINAL
        ],
    }


def demo():
    with localcontext() as context:
        context.prec = 45
        lo, hi = Decimal("0"), Decimal("0.1")
        for _ in range(70):
            mid = (lo + hi) / 2
            if measure(source_model_demo(mid))["numeric_verdict"] == "SUFFICIENT_WITHIN_DECLARED_BOUNDS":
                lo = mid
            else:
                hi = mid
        return {
            "schema": "contact-transfer150/source-model-preflight/v1",
            "scope": "SOURCE_MODEL_ONLY_NOT_PHYSICAL_MEASUREMENT",
            "nominal": measure(source_model_demo(Decimal("0"))),
            "error_2pct": measure(source_model_demo(Decimal("0.02"))),
            "error_4pct": measure(source_model_demo(Decimal("0.04"))),
            "symmetric_relative_force_error_threshold_bracket": [str(lo), str(hi)],
            "physical_data_acquired": False,
            "complete_comparator_or_commerce_proven": False,
            "decision": "PHYSICAL_TRANSFER_AND_ERROR_CALIBRATION_REQUIRED_NO_BID_NO_DEPLOY",
        }


def _new_output(target: Path, raw: bytes):
    if not target.is_absolute() or target.exists() or any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError("NEW_ABSOLUTE_REGULAR_OUTPUT_REQUIRED")
    if not target.parent.is_dir():
        raise ValueError("EXISTING_OUTPUT_PARENT_REQUIRED")
    target.write_bytes(raw)
    return str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("demo", "evaluate"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.operation == "demo":
        if args.input is not None:
            parser.error("demo forbids input")
        result = demo()
    else:
        if args.input is None or args.input.is_symlink() or not args.input.is_file():
            parser.error("evaluate requires a regular input JSON")
        raw = args.input.read_bytes()
        result = measure(parse(raw))
        result["input_sha256"] = sha256(raw).hexdigest()
    receipt = json.dumps(result, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if args.output is not None:
        _new_output(args.output, receipt)
    print(receipt.decode("utf-8"), end="")


if __name__ == "__main__":
    main()
