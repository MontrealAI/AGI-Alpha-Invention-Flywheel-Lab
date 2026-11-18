"""Build a bilingual offline exhibition and its identical downloadable public recipient."""
import argparse
import base64
import csv
import io
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(PRODUCT / "invention"))
from photometry import FIELDS, stamp
from plan import build
from verify import verify
from showcase.build import csp_hash, sha
from discovery_field.protocol import sources as checked_sources
from field_trials.replay_cpu import read_observation
from replay import read, replay

WORKLIST_FIELDS = ("target_id", "utc", "ra_deg", "dec_deg", "min_alt_deg", "max_sun_alt_deg")
ORIGIN = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/"
PRIOR = "b10de326ae6dad744ba26aa76cd7e2ec613e09f4/docs/frontier-omega-ignition/continuation/"
# Only these public research and implementation files may be published by the renderer.
FILES = {
    "invention": ["REGISTRATION.md", "README.md", "geometry.py", "plan.py", "verify.py", "reference.py", "qualify.py", "photometry.py",
                  "mission.json", "catalog.json", "public.json", "sources/fink-alerts.json", "sources/alerts-source.json", "sources/fink-holdout.json", "sources/holdout-source.json"],
    "field_lab": ["README.md", "REGISTRATION.md", "field.py", "protocol.py", "capture.py", "fixture_server.py", "verify.py", "workload.json", "PUBLIC.json",
                  *[f"evidence/{target}-{route}.json" for target in ("nominal", "adverse") for route in ("field", "conventional")]],
    "successor_field": ["REGISTRATION.md", "cohort.py", "audit.py", "triage.py", "SOURCES.json", "OBSERVATION.json", "archive-queue.csv",
                        *[f"facts/{series}.{ext}" for series in ("forecast", "reference") for ext in ("txt", "html", "csv")]],
    "table_desk": ["table_desk.py"],
    "invention/next_week": ["README.md", "RESULT.json", "replay.py", "photometry-120m.csv", "photometry-10m.csv",
                            "sources/alerts.json", "sources/objects.json", "sources/alerts-source.json", "sources/holdout-source.json"],
    "field_trials": ["recorded/summary.json"],
    "discovery_field": ["catalog.json", "REGISTRATION.md"],
}
# Each summary and its translation refer to the named, frozen source excerpt.
BASIS = {
    "sky": "4d429a84c8feded41b30af5c2bf44edb5152aa65c96375aca831479ed7f98504",
    "weather": "8cba699b67ba7e2af3c0c4886a562a99373949c8a6f76b7134a9ac7fc342d1fb",
    "proof": "7ff4d2e62584c233e2029028f8e1673c08a426b44b0ed392d33d3d59ab450830",
    "cad": "6f4a06ad98d7cfeae1c91b365c8f5f337547a73b8f237475ef0bd2e788883488",
    "kernel": "b2f8b209077f8bd3410eb0fc107fb1781e1ac8fca9080372cfcf65c3a49d0f66",
}


def opportunities():
    catalog = read(PRODUCT / "discovery_field/catalog.json")
    sources = checked_sources()
    labels = read(HERE / "opportunities.json")
    result = []
    for row in catalog["opportunities"]:
        key = row["id"]
        source = sources[row["source"]]
        if source["excerpt_sha256"] != BASIS[key] or urlparse(source["publication"]).scheme != "https":
            raise ValueError(f"Review translated material claim for changed source: {key}")
        result.append({"id": key, "publication": source["publication"], "translations": labels[key]})
    if set(BASIS) != {r["id"] for r in result} or len(BASIS) != len(result):
        raise ValueError("Opportunity population differs from translated cards")
    return result


def worklist_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=WORKLIST_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def recipient():
    files = {f"{group}/{filename}": (PRODUCT / group / filename).read_bytes()
             for group, names in FILES.items() for filename in names}
    for filename in ("PRESENT.md", "REPRODUCE.md", "replay.py"):
        files[filename] = (HERE / filename).read_bytes()
    files["SHA256SUMS"] = "".join(f"{sha(files[name])}  {name}\n" for name in sorted(files)).encode()
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            item = ZipInfo(name, date_time=(2026, 11, 17, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = ZIP_DEFLATED
            archive.writestr(item, content, compresslevel=9)
    return stream.getvalue()


def exhibition():
    replay()
    sky = read(PRODUCT / "invention/public.json")
    mission = sky["mission"]
    catalog = read(PRODUCT / "invention/catalog.json")
    # The short bilingual contract names this historical location and date specifically.
    if (mission["site"] != {"latitude_deg":32.0,"longitude_deg":-111.0} or mission["duration_minutes"] != 20
            or mission["min_target_alt_deg"] != 30 or mission["max_sun_alt_deg"] != -18 or mission["guard_deg"] != 1
            or mission["min_revisit_hours"] != 18 or {s[:10] for s in mission["slots_utc"]} != {"2026-11-01", "2026-11-02"}):
        raise ValueError("Review bilingual observing-contract caption for changed scope")
    for case in sky["cases"]:
        request = {**mission, "max_slots": case["budget"], "visits_per_target": case["visits"]}
        outcome = build(request, catalog)
        acceptance = verify(request, catalog, outcome)
        receipt = {"schema": "frontier.observing-case.v1", "case_id": case["id"], "mission": request,
                   "worklist": outcome, "acceptance": acceptance}
        # Carry the exact recipient bytes through the browser, including decimal spelling.
        case["receipt_text"] = json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        case["csv"] = worklist_csv(case["slots"])
    sky["primary"] = next(c["id"] for c in sky["cases"] if c["budget"] == mission["max_slots"] and c["visits"] == mission["visits_per_target"])
    photo = sky["photometry"]
    photo["columns"] = FIELDS
    first_acquisition = read(PRODUCT / "invention/sources/holdout-source.json")
    photo["source_url"] = first_acquisition["query"]
    photo["window_utc"] = [stamp(jd) for jd in first_acquisition["interval_jd"]]
    sky["holdout"] = {"detected": len(photo["first_detections"]), "total": photo["targets"],
                      "note": {"en": "The survey acquired these measurements independently of the worklist.",
                               "fr": "Le relevé a acquis ces mesures indépendamment du programme calculé."}}
    successor = read(PRODUCT / "successor_field/OBSERVATION.json")
    if not successor["independent_agreement"] or set(successor["accepted_routes"]) != {"direct", "ordinary", "retained"}:
        raise ValueError("Successor acceptance changed")
    copy = read(HERE / "copy.json")
    if copy["en"].keys() != copy["fr"].keys():
        raise ValueError("Missing translation")
    pilot_text = (PRODUCT / "field_trials/recorded/summary.json").read_text()
    pilot = json.loads(pilot_text)
    if pilot != read_observation():
        raise ValueError("Local model pilot projection differs from independent capture replay")
    if (pilot["scope"] != "recorded public synthetic CPU pilot" or pilot["hardware"]["gpu_layers"] != 0
            or {(r["route"], r["concurrency"]) for r in pilot["arms"]} != {(k,n) for k in ("field", "conventional") for n in (1,3)}
            or len(pilot["arms"]) != 4 or any(r["requests"] != 6 for r in pilot["arms"])):
        raise ValueError("Update the bilingual pilot scope for the changed cohort")
    archive = recipient()
    payload = {"secondWeekReport":(PRODUCT / "invention/next_week/RESULT.json").read_text(), "pilotReport":pilot_text, "sky": sky, "field":read(PRODUCT / "field_lab/PUBLIC.json"), "successor":successor["summary"],
               "opportunities":opportunities(), "copy":copy, "archive":{"sha256":sha(archive), "bytes":base64.b64encode(archive).decode("ascii")},
               "command":"python3 -B replay.py", "related":[{"label": k,"url":ORIGIN + PRIOR + f} for k,f in
                         [("oldEndpoint","FRONTIER_LAB.html"),("oldReading","FRONTIER_IGNITION.html"),("oldPairing","PAIRING_LAB.html")]]}
    css = (HERE / "style.css").read_text()
    js = (HERE / "app.js").read_text()
    policy = "default-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; script-src " + csp_hash(js) + "; style-src " + csp_hash(css)
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    doc = (HERE / "index.html").read_text()
    for marker, value in [("@@CSS@@",css),("@@DATA@@",data),("@@APP@@",js),("@@POLICY@@",policy)]:
        if doc.count(marker) != 1:
            raise ValueError("Invalid exhibition template marker " + marker)
        doc=doc.replace(marker,value)
    return doc.encode(), archive


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--recipient", type=Path)
    args = p.parse_args()
    page, archive = exhibition()
    args.output.write_bytes(page)
    print(sha(page), args.output)
    if args.recipient:
        args.recipient.write_bytes(archive)
        print(sha(archive), args.recipient)
