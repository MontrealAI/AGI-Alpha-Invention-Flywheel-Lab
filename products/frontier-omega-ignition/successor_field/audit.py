"""Independent verifier: original ASCII sections, exact fractions and an interval comparison."""
import argparse
import csv
from datetime import date
from fractions import Fraction
from pathlib import Path
from cohort import DATES, FIELDS, SELECTION, checked_facts


def original(name):
    text = checked_facts(name, "txt")
    if name == "forecast":
        if not text.startswith("PREDICTIONS:") or "UT1-UTC(sec)" not in text:
            raise ValueError("Forecast section or units missing")
        status = "forecast"
    else:
        if "time unit is millisecond (ms)" not in text or "UT1 err" not in text or "(0 h UTC)" not in text:
            raise ValueError("Final issue unit/time/error header missing")
        status = None
    output = {}
    for line in text.splitlines():
        words = line.split()
        if line == "Final values":
            status = "final"
        elif line == "Preliminary extension":
            status = "preliminary"
        elif words and len(words[0]) == 4 and words[0].isdigit():
            if status is None or len(words) != (7 if name == "forecast" else 14):
                raise ValueError("Unidentified original series")
            day = date(*map(int, words[:3]))
            if day in output or (day - date(1858, 11, 17)).days != int(words[3]):
                raise ValueError("Bad original calendar / MJD")
            output[day] = (status, words[6], None if name == "forecast" else words[11])
    return output


def expected(epochs, limit):
    threshold = Fraction(str(limit))
    forecasts, references = original("forecast"), original("reference")
    for day in epochs:
        row = [day.isoformat(), str((day - date(1858, 11, 17)).days), "", "", "", "", "defer", ""]
        forecast, final = forecasts.get(day), references.get(day)
        if not forecast:
            row[7] = "forecast_absent"
        else:
            row[2] = forecast[1]
            if not final:
                row[7] = "reference_absent"
            elif final[0] != "final":
                row[7] = "reference_preliminary"
            else:
                value, err = final[1:]
                corr = Fraction(value) - 1000 * Fraction(forecast[1])
                ticks = corr * 10000
                if ticks.denominator != 1:
                    raise ValueError("Insufficient delivery resolution")
                magnitude = abs(ticks.numerator)
                signed = ("-" if ticks < 0 else "") + f"{magnitude//10000}.{magnitude%10000:04d}"
                row[3:6] = [value, err, signed]
                lower, upper = abs(corr) - Fraction(err), abs(corr) + Fraction(err)
                if upper < threshold:
                    row[6:] = ["retain", "below_margin"]
                elif lower > threshold:
                    row[6:] = ["reprocess", "above_margin"]
                else:
                    row[6:] = ["review", "inside_margin"]
        ticks = threshold * 10000
        if ticks.denominator != 1 or ticks < 0:
            raise ValueError("Unsupported policy precision")
        threshold_label = f"{ticks.numerator//10000}.{ticks.numerator%10000:04d}"
        yield [*row, "IERS-A-XXXIX-031", "IERS-B-464", threshold_label]


def check(rows, epochs, limit):
    required = [list(FIELDS), *expected(epochs, limit)]
    if len(rows) != len(required):
        raise ValueError("Missing or extra delivery rows")
    for i, (given, truth) in enumerate(zip(rows, required)):
        if list(given) != truth:
            raise ValueError(f"Delivery row {i} differs from original ASCII reference")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--tolerance-ms", default="1.0")
    ap.add_argument("--date", type=date.fromisoformat, action="append")
    args = ap.parse_args()
    days = sorted(args.date or DATES)
    if set(days) - SELECTION or len(days) != len(set(days)) or Fraction(args.tolerance_ms) < 0:
        ap.error("Invalid date population or tolerance")
    with args.csv.open(newline="", encoding="utf8") as fh:
        check(list(csv.reader(fh)), days, args.tolerance_ms)
    print(f"{len(days)} UTC epochs independently reproduced from the two ASCII bulletins.")
