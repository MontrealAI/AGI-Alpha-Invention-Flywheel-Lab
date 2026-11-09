"""EIT105 source-locked preflight of a genuinely independent physical phantom record.

Only provenance and acquisition-contract inspection; no accuracy or business claims.
Source: Zenodo 7192883 v1, CC BY 4.0. No private human data.
"""
from collections import Counter
import csv
from hashlib import md5, sha256
import io
import json
import math
import re
from urllib.request import urlopen, Request

ROOT = "https://zenodo.org/records/7192883"
SOURCES = {
    "data_description.JSON": ("901dea0cc0692cf90e8e5790bcfcaa1a", 200_000),
    "circle_petg.csv": ("262a968766cd034914155ac2bfcd121e", 15_000_000),
}
FIELDS = ("object", "material", "value_desc", "meas_num", "r", "phi",
          "ex_mat_0", "ex_mat_1")
VOLTAGES = tuple(f"E_{i:02d}" for i in range(1, 17))

def check_source(name, data):
    if name not in SOURCES:
        raise ValueError("UNREGISTERED_SOURCE")
    expected, limit = SOURCES[name]
    if not data or len(data) > limit:
        raise ValueError("INVALID_SIZE")
    if md5(data).hexdigest() != expected:
        raise ValueError("SOURCE_CONTENT_CHANGED")
    return {"name": name, "bytes": len(data), "sha256": sha256(data).hexdigest(),
            "upstream_md5": expected}

def fetch_source(name):
    if name not in SOURCES:
        raise ValueError("UNREGISTERED_SOURCE")
    url = ROOT + "/files/" + name + "?download=1"
    request = Request(url, headers={"User-Agent": "AGI-ALPHA-external-phantom-preflight/1"})
    with urlopen(request, timeout=90) as response:
        return response.read(SOURCES[name][1] + 1)

def metadata(data):
    obj = json.loads(data)
    if not isinstance(obj, dict) or obj.get("license") != ["CC BY 4.0"]:
        raise ValueError("UNEXPECTED_LICENSE")
    identifiers = []
    for field in obj.get("variableMeasured", []):
        if not isinstance(field, dict):
            raise ValueError("INVALID_METADATA_FIELD")
        identifier = field.get("identifier")
        if isinstance(identifier, list):
            if len(identifier) != 1:
                raise ValueError("AMBIGUOUS_METADATA_IDENTIFIER")
            identifier = identifier[0]
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("INVALID_METADATA_IDENTIFIER")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("DUPLICATE_METADATA_IDENTIFIER")
    declared = set(identifiers)
    if not set(FIELDS + VOLTAGES).issubset(declared):
        raise ValueError("SOURCE_METADATA_SCHEMA_CHANGED")
    return {"declared_fields": len(declared), "license": obj["license"],
            "declared_file_count": len(obj.get("fileName", []))}

def describe_csv(data):
    body = data.decode("utf-8-sig")
    header = body.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    cols = tuple(reader.fieldnames or ())
    if not cols or len(cols) != len(set(cols)):
        raise ValueError("INVALID_CSV_HEADER")
    missing = set(FIELDS + VOLTAGES).difference(cols)
    if missing:
        raise ValueError("MISSING_ACQUISITION_FIELDS:" + ",".join(sorted(missing)))
    n = 0
    group = Counter()
    categories = {key: Counter() for key in ("object", "material", "value_desc")}
    pairs = set()
    types = Counter()
    for row in reader:
        n += 1
        if n > 250_000:
            raise ValueError("REGISTERED_ROW_BOUND")
        if None in row or any(v is None for v in row.values()):
            raise ValueError("RAGGED_CSV_ROW")
        for key in categories:
            categories[key][row[key]] += 1
        group[tuple(row[k] for k in ("object", "material", "r", "phi", "meas_num", "value_desc"))] += 1
        types[row["value_desc"]] += 1
        if row["value_desc"] == "measurement":
            try:
                a, b = int(row["ex_mat_0"]), int(row["ex_mat_1"])
                if not 0 <= a < 16 or not 0 <= b < 16 or a == b:
                    raise ValueError("INVALID_EXCITATION")
                pairs.add((a, b))
                for key in VOLTAGES:
                    if not math.isfinite(float(row[key])):
                        raise ValueError("NONFINITE_VOLTAGE")
            except (TypeError, ValueError) as exc:
                raise ValueError("INVALID_MEASUREMENT:" + str(exc)) from exc
    if n < 1 or types["measurement"] < 1:
        raise ValueError("NO_PHYSICAL_MEASUREMENTS")
    return {
        "rows": n, "columns": cols, "physical_group_count": len(group),
        "group_size_histogram": dict(sorted(Counter(group.values()).items())),
        "distinct_excitation_pairs": len(pairs),
        "measurement_rows": types["measurement"],
        "empty_reference_rows": types["mean_empty_ground"],
        "categories": {k: dict(sorted(v.items())) for k, v in categories.items()},
    }

def run():
    result = {
        "schema": "eit105/external-preflight/v1",
        "frozen_protocol_sha": "21c2b7972f4c73e27d1255b0186d530297b55826",
        "origin": ROOT, "inputs": [],
        "new_physical_acquisitions": 0,
        "commercial_buyer_acceptances": 0, "real_collections_usd": 0,
        "native_financial_accounts_operated": 0,
        "trailing_365_profit_usd": None,
        "qualified_physical_product": False,
        "decision": "HOLD_NO_BID_NO_DEPLOY",
    }
    for name in SOURCES:
        data = fetch_source(name)
        result["inputs"].append(check_source(name, data))
        result["metadata" if name.endswith(".JSON") else "acquisition_contract"] = (
            metadata(data) if name.endswith(".JSON") else describe_csv(data))
    return result

if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
