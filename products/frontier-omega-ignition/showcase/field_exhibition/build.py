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
from discovery_field.decision_study.evaluate import sources as decision_sources
from field_trials.replay_cpu import read_observation
from replay import read, replay
from change_desk import archive_series

WORKLIST_FIELDS = ("target_id", "utc", "ra_deg", "dec_deg", "min_alt_deg", "max_sun_alt_deg")
ORIGIN = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/"
PRIOR = "b10de326ae6dad744ba26aa76cd7e2ec613e09f4/docs/frontier-omega-ignition/continuation/"
# Only these public research and implementation files may be published by the renderer.
FILES = {
    "invention": ["REGISTRATION.md", "README.md", "INDEPENDENT_GEOMETRY_REVIEW.md", "geometry.py", "plan.py", "verify.py", "reference.py", "qualify.py", "photometry.py",
                  "mission.json", "catalog.json", "public.json", "sources/fink-alerts.json", "sources/alerts-source.json", "sources/fink-holdout.json", "sources/holdout-source.json"],
    "field_lab": ["README.md", "REGISTRATION.md", "field.py", "protocol.py", "capture.py", "fixture_server.py", "verify.py", "workload.json", "PUBLIC.json", "intake.py", "intake_workload.json", "INTAKE_REGISTRATION.md", "intake_recorded/result.json", "intake_recorded/independent_challenge.json",
                  "hosted_repeat/operation.json", "hosted_repeat/wire.json",
                  *[f"evidence/{target}-{route}.json" for target in ("nominal", "adverse") for route in ("field", "conventional")]],
    "successor_field": ["REGISTRATION.md", "cohort.py", "audit.py", "triage.py", "SOURCES.json", "OBSERVATION.json", "archive-queue.csv",
                        *[f"facts/{series}.{ext}" for series in ("forecast", "reference") for ext in ("txt", "html", "csv")]],
    "table_desk": ["table_desk.py"],
    "invention/next_week": ["README.md", "RESULT.json", "replay.py", "photometry-120m.csv", "photometry-10m.csv",
                            "sources/alerts.json", "sources/objects.json", "sources/alerts-source.json", "sources/holdout-source.json"],
    "field_trials": ["recorded/summary.json"],
    "invention/evolution": ["README.md", "REGISTRATION.md", "alert.py", "RESULT.json", "worklist.csv"],
    "invention/early_survey": ["README.md", "REGISTRATION.md", "REFERENCE.md", "survey.py", "acquire.py", "RESULT.json", "worklist.csv",
                               "sources/index.json", "sources/reference-index.json", "sources/class.json.gz",
                               "sources/objects-1.json.gz", "sources/reference-1.json.gz"],
    "invention/early_survey/exposures": ["REGISTRATION.md", "README.md", "avro_packet.py", "verify.py", "refresh.py", "test_exposures.py", "test_avro_external.py", "RESULT.json", "ARCHIVE_ACCESS.json",
                                        "sources/index.json", "sources/detections.json", "sources/astrometry.json.gz",
                                        "sources/coverage.csv.gz", "sources/empty-geometry.csv.gz", "sources/empty-stream.csv.gz",
                                        "sources/forced.json.gz", "sources/g.avro.gz", "sources/r.avro.gz", "sources/history.avro.gz"],
    "evolution_trials": ["REGISTRATION.md", "verify.py", "select.sql", "early.py",
                         "broker_control.py", "BROKER_CONTROL.json", "BROKER_REPLAY.md",
                         "broker_sources/alerce-window.vot", "broker_sources/alternate-notice.json",
                         *[f"broker_sources/{candid}.avro.gz" for candid in
                           ("3579392285815015017", "3580268845815015008", "3584356425815015004", "3584382785815015006")]],
    "discovery_field/decision_study": ["sources.json", "missions.json", "possibilities.json", "REGISTRATION.md", "evaluate.py", "included.json",
                                       "calibration_bounds.py", "calibration_observation.json"],
    "discovery_field": ["catalog.json", "REGISTRATION.md"],
}
def opportunities():
    folder = PRODUCT / "discovery_field/decision_study"
    raw = read(folder / "possibilities.json")
    sources = decision_sources()
    cards = raw["opportunities"]
    if len({row["id"] for row in cards}) != len(cards) or len(cards) != 5:
        raise ValueError("The public field needs five distinct opportunities")
    for card in cards:
        support = [sources[key] for key in card["source_ids"]]
        if not support or card["url"] not in [source["url"] for source in support] or urlparse(card["url"]).scheme != "https":
            raise ValueError("Opportunity is missing its attributed primary source")
        card["sources"] = [{"title": source["title"], "url": source["url"]} for source in support]
        for lang in ("en", "fr"):
            if any(not card[lang].get(key) for key in ("title", "finding", "limit", "test")):
                raise ValueError("Incomplete bilingual opportunity")
    return cards


def recorded_acquisition():
    folder = PRODUCT / "invention/early_survey"
    fink = read(folder / "sources/index.json")["requests"] + read(folder / "sources/reference-index.json")
    extension = list(read(folder / "exposures/sources/index.json").values())
    return {"requests": len(fink) + len(extension),
            "bytes": sum(row["bytes"] for row in fink) + sum(row["size_bytes"] for row in extension),
            "request_seconds": round(sum(row["wall_seconds"] for row in fink + extension), 4)}


def worklist_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=WORKLIST_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def recipient():
    files = {f"{group}/{filename}": (PRODUCT / group / filename).read_bytes()
             for group, names in FILES.items() for filename in names}
    for filename in ("PRESENT.md", "REPRODUCE.md", "replay.py", "change_desk.py"):
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
    verified = replay()
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
    payload = {"changeSeries":archive_series(), "acquisition":recorded_acquisition(), "intake":read(PRODUCT / "field_lab/intake_recorded/result.json"), "secondWeekReport":(PRODUCT / "invention/next_week/RESULT.json").read_text(), "pilotReport":pilot_text, "sky": sky, "field":read(PRODUCT / "field_lab/PUBLIC.json"), "successor":successor["summary"],
               "hostedIntake":verified["hosted_intake_repeat"],
               "opportunities":opportunities(), "copy":copy, "archive":{"sha256":sha(archive), "bytes":base64.b64encode(archive).decode("ascii")},
               "command":"python3 -B replay.py", "related":[{"label": k,"url":ORIGIN + PRIOR + f} for k,f in
                         [("oldEndpoint","FRONTIER_LAB.html"),("oldReading","FRONTIER_IGNITION.html"),("oldPairing","PAIRING_LAB.html")]]}
    css = (HERE / "style.css").read_text()
    js = (HERE / "change_desk.js").read_text() + "\n" + (HERE / "app.js").read_text()
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
