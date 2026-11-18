"""Read the frozen public GCN records, or compare them to a fresh read-only download."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
INDEX = "https://gcn.gsfc.nasa.gov/lvc_events.html"
CIRCULAR = "https://gcn.nasa.gov/circulars/36190.json"
MANIFEST_SHA = "8e3262668071272b885e85070e3661045042b8b4752343bb1819df008a3ed8ae"
FIELDS = ("event", "trigger", "serial", "kind")
EVENT = re.compile(r"S[0-9]{6}[a-z]+")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")


def instant(value):
    if not isinstance(value, str) or not UTC.fullmatch(value):
        raise ValueError("Specify an exact UTC timestamp with seconds and a trailing Z.")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    data = (HERE / "sources.json").read_bytes()
    if digest(data) != MANIFEST_SHA:
        raise ValueError("The registered source manifest changed.")
    return json.loads(data)


def original(name, source):
    # Names originate in the manifest, independent of mission or reported record fields.
    data = gzip.decompress((HERE / "sources" / (name + ".gz")).read_bytes())
    if len(data) != source["size_bytes"] or digest(data) != source["sha256"]:
        raise ValueError("The archived original differs from its registered digest.")
    return data


class AprilRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            row = self.row
            self.row = None
            if len(row) < 5 or not "2024/04/01" <= row[1] < "2024/05/01":
                return
            match = re.fullmatch(r"(S[0-9]{6}[a-z]+) XML", row[0])
            if match:
                self.rows.append((match[1], row[1].replace("/", "-") + "T" + row[2] + "Z",
                                  int(row[3]), row[4]))


def project_roster(source):
    parser = AprilRows()
    parser.feed(source.decode("utf-8"))
    parser.close()
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(sorted(parser.rows, key=lambda r: (r[1], r[0], r[2])))
    return out.getvalue().encode()


def roster(registered):
    source = original("april.csv", registered["roster_projection"])
    return list(csv.DictReader(io.StringIO(source.decode("ascii"))))


def selection(rows):
    starts = {}
    retracted = {}
    for row in rows:
        event, trigger = row["event"], instant(row["trigger"])
        if row["kind"] in {"Pre", "Ini", "Ear"} and trigger.day >= 10:
            starts[event] = min(starts.get(event, trigger), trigger)
        if row["kind"] == "Ret":
            retracted[event] = min(retracted.get(event, trigger), trigger)
    consecutive = sorted(starts, key=lambda event: (starts[event], event))[:5]
    if any(x in retracted for x in consecutive) or not retracted:
        control = None
    else:
        control = min(retracted, key=lambda event: (retracted[event], event))
    return consecutive, control


def refresh():
    """Compare original bodies, and separately the complete April table, without replacement."""
    reg = manifest()
    results = []
    for name, item in {"roster": reg["roster"], **reg["originals"]}.items():
        expected = CIRCULAR if name == "36190.json" else INDEX if name == "roster" else (
            "https://gcn.gsfc.nasa.gov/notices_l/" + name)
        if item["url"] != expected:
            raise ValueError("Unregistered acquisition route.")
        req = Request(expected, headers={"User-Agent": "Frontier-Omega-archival-reproduction/1"})
        try:
            with urlopen(req, timeout=90) as response:
                if response.geturl() != expected:
                    raise ValueError("Archive redirected to an unregistered route.")
                data = response.read(32_000_001)
                if len(data) > 32_000_000:
                    raise ValueError("Archive exceeded the independent read bound.")
            row = {"source": name, "bytes": len(data), "sha256": digest(data),
                   "original_matches": digest(data) == item["sha256"]}
            if name == "roster":
                row["april_projection_matches"] = (
                    digest(project_roster(data)) == reg["roster_projection"]["sha256"])
        except (OSError, ValueError) as error:
            row = {"source": name, "error": str(error), "original_matches": False}
        results.append(row)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-official", required=True, action="store_true",
                        help="Read only the pinned public NASA GCN URLs.")
    parser.parse_args()
    records = refresh()
    print(json.dumps(records, indent=2))
    raise SystemExit(0 if all(row["original_matches"] for row in records) else 1)
