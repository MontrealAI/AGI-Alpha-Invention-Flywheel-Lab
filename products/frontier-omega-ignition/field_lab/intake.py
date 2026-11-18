"""Compile two explicitly scoped bilingual service bounds, with their source spans."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import math
import re
import sys

if __package__:
    from .protocol import accepted
else:
    from protocol import accepted


# Every expression matches a complete clause. A percentile in another clause
# cannot qualify this event, and a separately mentioned user cannot qualify a rate.
NUMBER = r"(?P<number>[0-9]+(?:[.,][0-9]+)?)"
UNIT = r"(?P<unit>ms|milliseconds?|millisecondes?|s|seconds?|secondes?)"
TIME = rf"{NUMBER}\s*{UNIT}"
EN_EVENT = r"(?:the\s+)?first[-\s]+visible[-\s]+(?:output|content|token)"
FR_EVENT = r"(?:le\s+)?premier\s+(?:contenu|jeton)\s+visible"
EN_P90 = r"(?:P90|90th\s+percentile)"
FR_P90 = r"(?:P90|90e\s+(?:centile|percentile))"
EN_MAX = r"(?:within|(?:must\s+not|shall\s+not|cannot)\s+exceed|(?:is\s+|must\s+be\s+)?(?:at\s+most|no\s+(?:more|greater)\s+than)|(?:is\s+)?(?:<=|≤))"
FR_MAX = r"(?:(?:est\s+)?(?:d['’]au\s+plus|au\s+plus)|ne\s+doit\s+pas\s+dépasser|(?:<=|≤))"
SEC = r"(?:tokens?|jetons?)(?:\s+de\s+sortie)?(?:\s*/\s*(?:s|sec|second|seconde)|\s+(?:per\s+second|par\s+seconde))"
PER_USER = r"(?:\s+(?:per\s+(?:individual\s+)?user|for\s+each\s+user|par\s+utilisateur|pour\s+chaque\s+utilisateur)|\s*/\s*(?:user|utilisateur))"
RATE = rf"{NUMBER}\s+(?:(?:output|de\s+sortie)\s+)?{SEC}"
MIN = r"(?:at\s+least|no\s+less\s+than|au\s+moins|minimum\s+(?:de|of)|>=|≥)"
FR_FLOOR = r"(?:débit\s+(?:minimal|minimum)\s+de|au\s+moins)"
LATENCY = [
    rf"{EN_P90}\s+(?:time\s+to\s+)?{EN_EVENT}(?:\s+latency)?\s*{EN_MAX}\s*{TIME}",
    rf"(?:time\s+to\s+)?{EN_EVENT}\s+(?:at\s+){EN_P90}\s*{EN_MAX}\s*{TIME}",
    rf"{EN_MAX}\s*{TIME}\s+to\s+{EN_EVENT}\s+at\s+{EN_P90}",
    rf"(?:au\s+)?{FR_P90}\s*,?\s+{FR_EVENT}\s+en\s+{TIME}\s+au\s+(?:plus|maximum)",
    rf"{FR_EVENT}\s+au\s+{FR_P90}\s+en\s+{TIME}\s+au\s+(?:plus|maximum)",
    rf"{FR_EVENT}\s+au\s+{FR_P90}\s*{FR_MAX}\s*{TIME}",
    rf"(?:au\s+)?{FR_P90}\s*,?\s+{FR_EVENT}\s*{FR_MAX}\s*{TIME}",
]
FLOOR = [
    rf"{MIN}\s*{RATE}{PER_USER}",
    rf"{FR_FLOOR}\s+{RATE}{PER_USER}",
    rf"(?:per-user\s+output\s+rate|per-user\s+(?:delivery\s+)?rate)\s*(?:of\s+)?{MIN}\s*{RATE}",
    rf"(?:each\s+user\s+must\s+receive|chaque\s+utilisateur\s+doit\s+recevoir)\s+{MIN}\s*{RATE}",
]
PATTERNS = [(name, re.compile(pattern, re.I)) for name, patterns in
            (("p90_ms", LATENCY), ("min_rate", FLOOR)) for pattern in patterns]
# These neutral legacy UI headings carry no service constraints. An unfamiliar
# sentence remains unparsed and therefore reaches the operator as a deferral.
LEGACY_HEADING = re.compile(
    r"\s*(?:Support console|Soutien bilingue|Research preview|Atelier interne|Editor preview|Portail public)\.\s+",
    re.I,
)
SEPARATOR = re.compile(r"\s+(?:and|et)\s+|\s*;\s*|\.\s+|\n+", re.I)
INTRO = re.compile(r"(?:require|we require|we need|nous exigeons)\s+", re.I)


def json_number(number, milliseconds):
    decimal = Decimal(number.replace(",", "."))
    if not decimal.is_finite() or decimal <= 0:
        return None
    if milliseconds:
        sign, digits, exponent = decimal.as_tuple()
        decimal = Decimal((sign, digits, exponent + 3))
    if decimal == decimal.to_integral_value():
        # Python's JSON integer conversion has a platform-specific digit limit.
        if decimal.adjusted() + 1 > (getattr(sys, "get_int_max_str_digits", lambda: 4300)() or math.inf):
            return None
        return int(decimal)
    as_float = float(decimal)
    # Only hand off a number that round-trips through the standard JSON encoder.
    return as_float if math.isfinite(as_float) and Decimal(str(as_float)) == decimal else None


def clauses(brief):
    heading = LEGACY_HEADING.match(brief)
    start = heading.end() if heading else 0
    end = len(brief.rstrip())
    if end and brief[end-1] == ".":
        end -= 1
    edges = list(SEPARATOR.finditer(brief, start, end))
    starts = [start, *(m.end() for m in edges)]
    ends = [*(m.start() for m in edges), end]
    for lo, hi in zip(starts, ends):
        while lo < hi and brief[lo].isspace():
            lo += 1
        while lo < hi and brief[hi-1].isspace():
            hi -= 1
        yield lo, hi


def compile_brief(brief):
    """Construct exact JSON-ready fields only when both meanings consume the brief."""
    receipt = {"brief_sha256": hashlib.sha256(brief.encode("utf-8")).hexdigest(),
               "answer": {"status": "defer"}, "evidence": [], "reason": "unrecognized-or-extra-clause"}
    found = {}
    for lo, hi in clauses(brief):
        introduction = INTRO.match(brief, lo, hi)
        begin = introduction.end() if introduction else lo
        for field, rule in PATTERNS:
            match = rule.fullmatch(brief, begin, hi)
            if match:
                if field in found:
                    receipt["reason"] = "duplicated-bound"
                    return receipt
                milliseconds = field == "p90_ms" and match["unit"].lower() in (
                    "s", "second", "seconds", "seconde", "secondes")
                value = json_number(match["number"], milliseconds)
                if value is None:
                    receipt["reason"] = "unsupported-numeric-precision-or-domain"
                    return receipt
                found[field] = value
                receipt["evidence"].append({"field": field, "span": [lo, hi], "text": brief[lo:hi],
                                            "value": value, "unit": "ms" if field == "p90_ms" else "tokens/s/user"})
                break
        else:
            return receipt
    if found.keys() == {"p90_ms", "min_rate"}:
        receipt.update(answer={"status": "ready", **found}, reason="two-explicit-supported-bounds")
    else:
        receipt["reason"] = "missing-bound"
    return receipt


def guard(receipt, supplied):
    """Defer on disagreement. Callers must separately require a complete model response."""
    if accepted(supplied, receipt["answer"]):
        return receipt["answer"]
    return {"status": "defer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", nargs="?", help="English or French service brief. Omit to read standard input.")
    parser.add_argument("--candidate", help="Optional model-produced JSON text to compare with the clauses.")
    args = parser.parse_args()
    result = compile_brief(args.brief if args.brief is not None else sys.stdin.read())
    if args.candidate is not None:
        result["checked_candidate"] = guard(result, args.candidate)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
