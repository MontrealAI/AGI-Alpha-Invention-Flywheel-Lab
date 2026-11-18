"""Explicitly permitted public files for portable decisions. Workspace files are never traversed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ("action_study/__init__.py", "action_study/desk.py", "action_study/pack.py")
ZTF = "invention/early_survey/"
EXPOSURES = ZTF + "exposures/"
OBS = "action_study/observing/"
CHOICE = "action_study/qualification_choice/"
ZTF_CODE = ("action_study/ztf.py", ZTF + "survey.py", ZTF + "acquire.py", "evolution_trials/verify.py",
            "evolution_trials/select.sql", "invention/evolution/alert.py", "invention/geometry.py", "invention/reference.py",
            ZTF + "sources/index.json", ZTF + "sources/reference-index.json")
ZTF_DATA = tuple(ZTF + "sources/" + f for f in ("class.json.gz", "objects-1.json.gz", "reference-1.json.gz"))
AVRO_CODE = tuple(EXPOSURES + f for f in ("avro_packet.py", "verify.py", "sources/index.json"))
AVRO_DATA = tuple(EXPOSURES + "sources/" + f for f in ("detections.json", "astrometry.json.gz", "coverage.csv.gz",
                  "empty-geometry.csv.gz", "empty-stream.csv.gz", "forced.json.gz", "g.avro.gz", "r.avro.gz", "history.avro.gz"))
OBS_CODE = tuple(OBS + f for f in ("adapter.py", "capture.py", "sources.json"))
CHOICE_CODE = tuple(CHOICE + f for f in ("adapter.py", "acquire.py", "roster.py")) + ("discovery_field/decision_study/calibration_bounds.py",)


def contents(names):
    return {name: (ROOT / name).read_bytes() for name in names}


def computation_files(profile, routes):
    if profile == "ztf-persistence":
        files = ZTF_CODE + (AVRO_CODE if "alerce" in routes else ())
    elif profile == "gw-status":
        files = OBS_CODE
    elif profile == "engineering-qualification":
        files = CHOICE_CODE
    else:
        raise ValueError("Unknown registered profile.")
    return contents(BASE + files)


def public_files():
    import json
    files = contents(BASE + ZTF_CODE + ZTF_DATA + AVRO_CODE + AVRO_DATA + OBS_CODE + CHOICE_CODE)
    selection = json.loads(files[OBS + "sources.json"])
    files.update(contents([OBS + "sources/" + k + ".gz" for k in selection["originals"]]))
    files.update(contents([OBS + "sources/april.csv.gz"]))
    pool_name = CHOICE + "sources/pool.json"
    pool = json.loads((ROOT / pool_name).read_bytes())
    files.update(contents([pool_name, *(CHOICE + "sources/" + f for f in pool["attachments"]),
                           *(CHOICE + "sources/" + group["file"] for group in pool["groups"].values())]))
    # Longitudinal checks and source identities accompany the public exhibition.
    # The private recipient below packages only the sources used by its own mission.
    extras = {
        "action_study": ("REGISTRATION.md", "README.md", "test_desk.py"),
        "action_study/observing": ("README.md", "REGISTRATION.md", "desk.py", "direct.py", "cost.py",
                                   "result.json", "costs.json", "test_observing.py"),
        "action_study/qualification_choice": ("README.md", "REGISTRATION.md", "direct.py", "prepare.py", "verify.py",
                                              "result.json", "qualification_input.json", "economics.json"),
        "action_study/opportunities": ("README.md", "choices.json", "sources.json", "verify.py", "model_operations.json",
                                       "test_opportunity_sources.py"),
        "action_study/construction": ("README.md", "REGISTRATION.md", "COHORT_REGISTRATION.md", "git-clock-converter.zip",
                                      "conventional.py", "source_clocks.json", "native_clocks.json"),
        "action_study/shadow": ("README.md", "REGISTRATION.md", "archive.py", "direct_inputs.py", "fieldkit.py",
                                "shadow.py", "test_shadow.py"),
        "invention/early_survey/exposures": ("STREAM_FIRST_REVIEW.md",),
    }
    files.update(contents([folder + "/" + name for folder, names in extras.items() for name in names]))
    return files


def scoped_files(mission, attempts):
    """Only the public evidence needed to reproduce this revision's attempted routes."""
    import json
    profile, routes = mission["profile"], mission["sources"]
    files = computation_files(profile, routes)
    if not attempts:
        return files
    if profile == "ztf-persistence":
        files.update(contents(ZTF_DATA))
        if any(a["route"] == "alerce" for a in attempts):
            files.update(contents(AVRO_DATA))
    elif profile == "gw-status":
        meta = json.loads(files[OBS + "sources.json"])
        name = mission["scope"]["event"] + ".xml_fmt"
        if name in meta["originals"]:
            files.update(contents([OBS + "sources/" + name + ".gz"]))
        if any(a["route"] == "status_history" for a in attempts):
            files.update(contents([OBS + "sources/april.csv.gz"]))
    else:
        name = CHOICE + "sources/pool.json"
        pool = json.loads((ROOT / name).read_bytes())
        groups = {row["id"] for a in attempts for row in a["evidence"] if row.get("id") in pool["groups"]}
        files.update(contents([name, *(CHOICE + "sources/" + f for f in pool["attachments"]),
                               *(CHOICE + "sources/" + pool["groups"][g]["file"] for g in groups)]))
    return files
