"""Build a source-bound UTC-midnight Earth-orientation reprocessing queue."""
import argparse
import csv
from datetime import date
from decimal import Decimal
from functools import lru_cache
import io
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import xml.etree.ElementTree as ET
from cohort import DATES, EPOCH, FIELDS, HERE, SELECTION, checked_facts


def tolerance(value):
    # SQLite represents the declared 0.0001-ms policy in exact signed integers.
    if not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,4})?", value):
        raise ValueError("Tolerance must be a nonnegative millisecond decimal, at most four decimal places.")
    return Decimal(value)


@lru_cache(maxsize=1)
def desk():
    sys.path.insert(0, str(HERE.parent / "table_desk"))
    import table_desk
    return table_desk


def html_grid(name, route):
    markup = checked_facts(name, "html")
    table = ET.fromstring(markup)
    groups, fields, units, legend = table.findall("thead/tr")
    group_layout = [(v.text, int(v.get("colspan", 1))) for v in groups]
    if group_layout != [("Time", 4), ("Pole", 9), ("UT", 5), ("Nutation", 9)]:
        raise ValueError("Unrecognized grouped time/pole/UT/nutation layout")
    if legend[0].text != "T=Type: r=rapid - f=final - p=predictions":
        raise ValueError("Missing published type legend")
    labels = [(c.text or "").replace(" ", "") for c in fields]
    unit = "[sec]" if name == "forecast" else "[msec]"
    if labels[:4] != ["MJD", "Year", "Month", "Day"] or labels[13:16] != ["T", "UT1-UTC", "sigma_UT1-UTC"]:
        raise ValueError("Unrecognized UT fields")
    if [c.text for c in units][14:16] != [unit, unit]:
        raise ValueError("Unrecognized UT unit")
    if route == "ordinary":
        return [[c.text or "" for c in row] for row in table.findall("tbody/tr")]
    # The original reader properly refuses spanning headers. Only the separately
    # validated rectangular body is passed to it; its span policy is unchanged.
    parser = desk().TableReader(1)
    parser.feed("<table>" + markup.split("<tbody>", 1)[1].split("</tbody>", 1)[0] + "</table>")
    parser.close()
    return parser.cells


def csv_grid(name):
    records = csv.reader(io.StringIO(checked_facts(name, "csv")), delimiter=";")
    labels = next(records)
    if labels[:4] != ["MJD", "Year", "Month", "Day"] or labels[13:16] != ["Type", "UT1-UTC", "sigma_UT1-UTC"]:
        raise ValueError("Publisher CSV UT field placement changed")
    return list(records)


def records(grid, kind):
    result = {}
    status_names = {"f": "final", "p": "prediction", "r": "rapid", "-": ""}
    for row in grid:
        if len(row) != 27:
            raise ValueError("Publisher column count changed")
        day = date(*map(int, row[1:4]))
        if day not in SELECTION or day in result or (day - EPOCH).days != int(row[0]):
            raise ValueError("Duplicate, inconsistent or out-of-scope date/MJD")
        status = status_names[row[13]] if kind == "html" else row[13]
        values = [v if v != "---" else "" for v in row[14:16]]
        for v in values:
            if v and not re.fullmatch(r"[+-]?(?:[0-9]+)?\.[0-9]+", v):
                raise ValueError("Malformed scientific decimal")
        result[day] = (status, *values)
    return result


def policy(forecast, final, tolerance_ms):
    pred = forecast[1] if forecast and forecast[0] == "prediction" else ""
    if not pred:
        return (pred, "", "", "", "defer", "forecast_absent")
    if not final or final[0] != "final":
        reason = "reference_preliminary" if final else "reference_absent"
        return (pred, "", "", "", "defer", reason)
    value, error = final[1:]
    sigma = Decimal(error)
    if sigma < 0:
        raise ValueError("Negative final standard error")
    correction = Decimal(value) - Decimal(pred) * 1000
    if abs(correction) > tolerance_ms + sigma:
        action, reason = "reprocess", "above_margin"
    elif abs(correction) < tolerance_ms - sigma:
        action, reason = "retain", "below_margin"
    else:
        action, reason = "review", "inside_margin"
    return pred, value, error, format(correction, ".4f"), action, reason


def exact_ticks(value, scale):
    if not value:
        return None
    number = Decimal(value) * scale
    if number != number.to_integral_value():
        raise ValueError("Publisher precision exceeds the exact SQL tick size")
    return int(number)


def sql_rows(epochs, limit):
    # Conventional archive workflow. Duplicate edition/date rows violate the PK.
    # The table stores the publisher's printed text alongside exact 0.1-µs ticks.
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE epochs (day TEXT PRIMARY KEY, mjd INTEGER UNIQUE)")
        db.executemany("INSERT INTO epochs VALUES (?,?)", [(d.isoformat(), (d - EPOCH).days) for d in epochs])
        db.execute("CREATE TABLE values_ut (edition TEXT, mjd INTEGER, type TEXT, value TEXT, error TEXT, "
                   "ticks INTEGER, sigma INTEGER, PRIMARY KEY (edition, mjd))")
        for name, scale in [("forecast", Decimal(10000000)), ("reference", Decimal(10000))]:
            for day, (status, value, error) in records(csv_grid(name), "csv").items():
                ticks = exact_ticks(value, scale)
                sigma = exact_ticks(error, scale)
                db.execute("INSERT INTO values_ut VALUES (?,?,?,?,?,?,?)",
                           (name, (day - EPOCH).days, status, value, error, ticks, sigma))
        sql = """
            WITH joined AS (
                SELECT e.day, e.mjd, a.value AS forecast, b.value AS final, b.error,
                       b.type AS ref_type, b.ticks - a.ticks AS difference, b.sigma
                FROM epochs e
                LEFT JOIN values_ut a ON a.mjd=e.mjd AND a.edition='forecast' AND a.type='prediction'
                LEFT JOIN values_ut b ON b.mjd=e.mjd AND b.edition='reference'
            )
            SELECT day,mjd,forecast,final,error,difference,
                CASE WHEN forecast IS NULL THEN 'forecast_absent'
                     WHEN ref_type IS NULL THEN 'reference_absent'
                     WHEN ref_type <> 'final' THEN 'reference_preliminary'
                     WHEN ABS(difference) > ? + sigma THEN 'above_margin'
                     WHEN ABS(difference) < ? - sigma THEN 'below_margin'
                     ELSE 'inside_margin' END
            FROM joined ORDER BY day
        """
        actions = {"above_margin": "reprocess", "below_margin": "retain", "inside_margin": "review"}
        bound = int(limit * 10000)
        for day, mjd, pred, value, error, difference, reason in db.execute(sql, (bound, bound)):
            action = actions.get(reason, "defer")
            if action == "defer":
                yield (day, str(mjd), pred or "", "", "", "", action, reason)
            else:
                signed = format(Decimal(difference) / 10000, ".4f")
                yield (day, str(mjd), pred, value, error, signed, action, reason)


def make_queue(route, epochs, limit):
    if route == "direct":
        return list(sql_rows(epochs, limit))
    views = {}
    for name in ("forecast", "reference"):
        grid = records(html_grid(name, route), "html")
        # Both reuse arms receive the same publisher CSV and written checking recipe.
        expected = records(csv_grid(name), "csv")
        matrix = [list((d.isoformat(), *values)) for d, values in sorted(grid.items())]
        gold = [list((d.isoformat(), *values)) for d, values in sorted(expected.items())]
        matches = desk().compare(matrix, gold)["accepted"] if route == "retained" else matrix == gold
        if not matches:
            raise ValueError("Published HTML and CSV UT records differ")
        views[name] = grid
    return [(day.isoformat(), str((day - EPOCH).days),
             *policy(views["forecast"].get(day), views["reference"].get(day), limit)) for day in epochs]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--route", choices=("retained", "ordinary", "direct"), default="direct")
    ap.add_argument("--tolerance-ms", default="1.0")
    ap.add_argument("--date", type=date.fromisoformat, action="append", help="Select a registered epoch; repeatable")
    ap.add_argument("--output", type=Path, required=True, help="A new CSV path")
    args = ap.parse_args()
    epochs = sorted(args.date or DATES)
    if len(set(epochs)) != len(epochs) or set(epochs) - SELECTION:
        ap.error("Date outside the public projection or repeated")
    limit = tolerance(args.tolerance_ms)
    rows = make_queue(args.route, epochs, limit)
    # An unaudited file must never appear at its final path.
    import audit
    audit.check([FIELDS, *rows], epochs, limit)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as stage:
        path = Path(stage) / "queue.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, lineterminator="\n").writerows([FIELDS, *rows])
        os.link(path, args.output)


if __name__ == "__main__":
    main()
