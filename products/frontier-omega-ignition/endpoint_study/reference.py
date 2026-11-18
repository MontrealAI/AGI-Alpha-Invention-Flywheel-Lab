"""Select qualifying measurements directly from complete MLPerf tables using SQLite."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import io
import json
import re
from pathlib import Path
import sqlite3

SOURCES = Path(__file__).resolve().parent / "sources"
MANIFEST = "77cb3a9593e42d4260fd394f8b344c5a2f15d3e6c0083d27c436b5e2ef6157b9"
NUMERIC = ("ttft_p90_ms", "tps_per_user", "tpot_p90_ms", "system_tps")
IDS = ("source", "run", "concurrency")
POINT_FIELDS = IDS + NUMERIC
CONTRACT_FIELDS = {"model", "dataset", "max_ttft_p90_ms", "min_tps_per_user", "min_concurrency",
                   "load_mode", "rate_metric", "require_point_accuracy", "require_price", "require_access"}


def number(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("Numeric evidence must be an exact decimal or integer")
    try:
        v = Decimal(value)
        if not v.is_finite():
            raise ValueError("Nonfinite measurement")
        return Fraction(v)
    except InvalidOperation as error:
        raise ValueError("Invalid numerical measurement") from error


def bound_bytes(path, expected):
    contents = path.read_bytes()
    if sha256(contents).hexdigest() != expected:
        raise ValueError(f"Published source changed: {path.name}")
    return contents


def observations(sources=SOURCES):
    manifest = json.loads(bound_bytes(sources / "manifest.json", MANIFEST))
    for source in manifest:
        metadata = source["metadata"]
        raw = bound_bytes(sources / source["table_file"], source["table_sha256"])
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
        header, *rows = rows
        run_count = source["n_run_columns"]
        if header != ["Field Name"] + [f"Run {i}" for i in range(1, run_count + 1)]:
            raise ValueError("Unexpected run columns")
        data = {}
        section = ""
        for label, *values in rows:
            if len(values) != run_count:
                raise ValueError("Incomplete source row")
            if not any(values):
                section = label
                continue
            key = (section, label)
            if key in data:
                raise ValueError("Duplicate table row")
            data[key] = values
        # The three percentile blocks contain identically named P90 rows. Scope
        # them to their complete source headers, and keep units as reported.
        columns = {
            "concurrency": ("", "Concurrency"), "system_tps": ("", "System Tokens/Second"),
            "tps_per_user": ("", "Tokens/Second per User"), "ttft_p90_ms": ("", "TTFT P90 (ms)"),
            "tpot_p90_ms": ("Time Per Output Token (TPOT) (ms)", "P90"),
            "mode": ("", "Config Type"), "region": ("", "Config Region"),
            "failed": ("", "Total Queries Failed"), "state": ("", "Result State"),
            "accuracy": ("", "Measured Accuracy Score"), "issued": ("", "Total Queries Issued")
        }
        for offset in range(run_count):
            row = {name: data[key][offset].replace(",", "") for name, key in columns.items()}
            for key in ("concurrency","failed","issued"):
                row[key] = int(row[key]) if row[key].isdigit() else None
            for key in NUMERIC:
                if row[key] in {"—", "-", ""}:
                    row[key] = None
            yield {**row, "source":source["id"], "run":offset+1, "verified":source["verified"],
                   "version":metadata["Version"], "availability":metadata["System Availability"],
                   "model":metadata["Model Name"], "dataset":metadata["Dataset Name"],
                   "division":metadata["Division"], "deployment":metadata["Deployment"]}


def connect(sources=SOURCES):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.create_function("leq", 2, lambda l, r: l is not None and r is not None and number(l) <= number(r))
    db.create_function("tail_rate_met", 2, lambda ms, threshold:
                       ms is not None and number(ms) > 0 and number(ms) * number(threshold) <= 1000)
    db.execute("""CREATE TABLE evidence (source TEXT, run INTEGER, concurrency INTEGER, ttft_p90_ms TEXT,
        tps_per_user TEXT, tpot_p90_ms TEXT, system_tps TEXT, verified INTEGER, model TEXT, dataset TEXT,
        division TEXT, deployment TEXT, version TEXT, availability TEXT, issued INTEGER, mode TEXT, region TEXT, failed INTEGER, state TEXT, accuracy TEXT,
        PRIMARY KEY(source,run))""")
    db.executemany("""INSERT INTO evidence VALUES (:source,:run,:concurrency,:ttft_p90_ms,:tps_per_user,
        :tpot_p90_ms,:system_tps,:verified,:model,:dataset,:division,:deployment,:version,:availability,:issued,:mode,:region,:failed,:state,:accuracy)""",
        observations(sources))
    return db


ELIGIBLE = """
    SELECT * FROM evidence WHERE verified AND division='Standardized' AND deployment='Client on Premises'
      AND version='v1.0' AND availability='Available' AND model=:model AND dataset=:dataset
      AND state='complete' AND issued>0 AND failed=0 AND concurrency>0
      AND lower(mode) IN ('submission','online') AND lower(region)!='offline'
      AND (:load_mode='reported' OR lower(mode)='online')
"""
BEST = "WITH qualified AS ("+ELIGIBLE+"""
      AND concurrency>=:min_concurrency AND leq(ttft_p90_ms,:max_ttft_p90_ms)
      AND CASE WHEN :rate_metric='reported_tps_per_user' THEN leq(:min_tps_per_user,tps_per_user)
               ELSE tail_rate_met(tpot_p90_ms,:min_tps_per_user) END
      AND :rate_metric!='agentic_e2e' AND NOT :require_price AND NOT :require_access
      AND (NOT :require_point_accuracy OR accuracy NOT IN ('—','-',''))
) SELECT source,run,concurrency,ttft_p90_ms,tps_per_user,tpot_p90_ms,system_tps
FROM qualified WHERE concurrency=(SELECT MAX(concurrency) FROM qualified) ORDER BY source,run
"""


def checked_contract(contract):
    if not isinstance(contract, dict) or set(contract) != CONTRACT_FIELDS:
        raise ValueError("Unsupported evidence contract fields")
    if (contract["rate_metric"] not in {"reported_tps_per_user", "inverse_p90_tpot", "agentic_e2e"}
            or contract["load_mode"] not in {"reported", "online"}):
        raise ValueError("Unsupported rate metric or load mode")
    for key in ("require_access", "require_price", "require_point_accuracy"):
        if type(contract[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    if type(contract["min_concurrency"]) is not int or contract["min_concurrency"] < 1:
        raise ValueError("Invalid concurrency")
    if not all(isinstance(contract[k],str) and contract[k].strip() for k in ("model","dataset")):
        raise ValueError("Missing model or dataset")
    for key in ("max_ttft_p90_ms","min_tps_per_user"):
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(contract[key])) or number(contract[key]) <= 0:
            raise ValueError("A rate or time threshold must be positive and use plain decimal notation")
    return contract


def selection(contract, db):
    rows = [dict(row) for row in db.execute(BEST, {**checked_contract(contract), "min_concurrency":str(contract["min_concurrency"])})]
    return {"decision":"supported" if rows else "withheld", "selected":rows}


def canonical(rows):
    if not isinstance(rows,list):
        raise ValueError("Missing selection list")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not set(POINT_FIELDS).issubset(row):
            raise ValueError("Missing source identity or source measurement")
        if not isinstance(row["source"],str) or any(type(row[k]) is not int for k in ("run","concurrency")):
            raise ValueError("Invalid source identity or concurrency")
        result.append(tuple(row[k] for k in IDS) + tuple(number(row[k]) for k in NUMERIC))
    return sorted(result)


def check_points(expected, result):
    if (result.get("decision") != expected["decision"]
            or canonical(result.get("selected")) != canonical(expected["selected"])):
        raise ValueError("Decision, all eligible ties or selected source measurements differ from full reports")


def verify(contract, result):
    """Check a producer's decision against independent, pinned full-report evidence."""
    with connect() as db:
        expected = selection(contract, db)
    contract_hash = sha256(json.dumps(contract, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    if (not isinstance(result, dict) or result.get("schema") != "frontier-endpoints/decision/v1"
            or result.get("contract") != contract or result.get("contract_sha256") != contract_hash
            or result.get("deployment_authorized") is not False
            or result.get("reports_sha256") != "ba572c5d5abf65aaf95406c66689d5b786a4bc4371d507ae2254e72c7763ac90"
            ):
        raise ValueError("Scope, evidence or contract identity differs from the registered decision")
    check_points(expected, result)
    return {"checked":True, "scope":"contract binding, authority, decision, tied source IDs and published numerical fields",
            "source_manifest_sha256":MANIFEST,
            "decision":expected["decision"], "selected_count":len(expected["selected"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.contract.read_bytes())
    if args.receipt:
        answer = verify(spec, json.loads(args.receipt.read_bytes()))
    else:
        with connect() as connection:
            answer = selection(spec, connection)
    print(json.dumps(answer, indent=2))
