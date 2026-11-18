"""Turn a permitted benchmark requirement into a checked, portable decision."""
from datetime import date
import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .store import PRODUCT, Conflict, StateError, canonical, digest

PRESET = PRODUCT / "examples/endpoint.json"
RECEIVER_PATHS = (
    "endpoint_lab/decide.py", "endpoint_lab/reports.json",
    "endpoint_lab/replay_delivery.py", "endpoint_study/reference.py",
    "endpoint_study/sources/manifest.json",
)


def receiver_files():
    names = list(RECEIVER_PATHS)
    from endpoint_study.reference import MANIFEST, bound_bytes
    source = "endpoint_study/sources/"
    manifest = bound_bytes(PRODUCT / source / "manifest.json", MANIFEST)
    files = {name: (PRODUCT / name).read_bytes() for name in names}
    files[source + "manifest.json"] = manifest
    for item in json.loads(manifest):
        name = source + item["table_file"]
        files[name] = bound_bytes(PRODUCT / name, item["table_sha256"])
    return files


def identity(files=None):
    files = receiver_files() if files is None else dict(files)
    files["examples/endpoint.json"] = PRESET.read_bytes()
    return digest({key: hashlib.sha256(data).hexdigest() for key, data in files.items()})


def requirements(state):
    mission = state["mission"]
    standard = json.loads(PRESET.read_bytes())["mission"]
    if (mission["purpose"] != standard["purpose"] or mission["requirements"] != standard["requirements"]
            or mission["construction_spec"] or state["sources"]):
        raise StateError("This instrument evaluates the named public benchmark scope. Use a research mission for other goals or sources.")
    if state.get("inherited"):
        raise StateError("This installed instrument cannot apply an inherited construction program.")
    if set(mission["time"]) - {"as_of", "deadline"}:
        raise StateError("Only a benchmark status date and an execution deadline can be checked.")
    resources = mission["resources"]
    if (resources.get("execution_strategy", "adaptive") not in {"adaptive", "direct"}
            or resources.get("direct_method", "specialist") != "specialist"
            or resources.get("direct_after_research")):
        raise StateError("Select direct or adaptive specialist execution for this installed instrument.")
    unknown = set(resources) - {"endpoint_lab", "execution_strategy", "direct_method", "direct_after_research", "max_model_calls"}
    if unknown:
        raise StateError("Unrepresented resource requirements: " + ", ".join(sorted(unknown)))
    if "as_of" in mission["time"] and date.fromisoformat(mission["time"]["as_of"]) != date(2026, 11, 17):
        raise StateError("Review status was observed on 2026-11-17. A decision on another date requires fresh evidence.")
    return resources["endpoint_lab"]


def checked(contract):
    from endpoint_lab.decide import decide
    from endpoint_study.reference import verify
    result = decide(contract)
    verification = verify(contract, result)
    return result, verification


def run(controller, state):
    contract = requirements(state)
    state["routing"] = {"strategy": state["mission"]["resources"].get("execution_strategy", "adaptive"),
                        "route": "direct", "method": "specialist",
                        "reason": "The operator supplied a measurable workload and selected the installed public reports."}
    controller._step(state, "routing", state["routing"]["reason"])
    result, verification = checked(contract)
    record = {"parameters": contract, "input_sha256": state["input_sha256"],
              "specialist_sha256": state["specialist_source"]}
    state["contract_sha256"] = digest(record)
    state["contract"] = dict(record, sha256=state["contract_sha256"])
    state["endpoint_result"] = result
    state["evaluation"] = {"status": "pass", "comparison": {"outcome": "independent_report_agreement"},
                           "verification": verification}
    state["artifact"] = {"kind": "endpoint_evidence", "sha256": digest(result)}
    controller._step(state, "verification", "Independent report replay agrees. Benchmark decision: " + result["decision"], "verified")


def deliver(state, payload, trial):
    contract = requirements(state)
    result, verification = checked(contract)
    record = {"parameters": contract, "input_sha256": digest([state["mission"], state["sources"]]),
              "specialist_sha256": identity()}
    binding = digest(record)
    if (state["input_sha256"] != record["input_sha256"] or state["specialist_source"] != record["specialist_sha256"]
            or state["contract_sha256"] != binding or state["contract"] != dict(record, sha256=binding)
            or state["artifact"]["sha256"] != digest(result) or state["endpoint_result"] != result
            or state["evaluation"]["verification"] != verification):
        raise Conflict("The decision, thresholds, source or verification changed. Amend and qualify again.")
    if trial:
        if payload != {}:
            raise StateError("Use {} for the accepted decision. Amend the mission to change its requirements.")
        return result
    files = receiver_files()
    if identity(files) != state["specialist_source"]:
        raise Conflict("The receiver source changed while preparing the download.")
    from endpoint_study.reference import connect, selection
    with connect() as db:
        reference = selection(contract, db)
    files["reference-result.json"] = (canonical(reference) + "\n").encode()
    files["contract.json"] = (canonical(contract) + "\n").encode()
    files["decision.json"] = (canonical(result) + "\n").encode()
    files["README.txt"] = b"From the extracted directory, run: python3 -B endpoint_lab/replay_delivery.py\nPython 3.11 or later. Review status was observed 2026-11-17. Uses only local public evidence. A measured benchmark point does not establish procurement rights or performance on new traffic.\n"
    out = io.BytesIO()
    with ZipFile(out, "w") as z:
        for name, content in sorted(files.items()):
            item = ZipInfo(name, (2026, 11, 17, 0, 0, 0))
            z.writestr(item, content, compress_type=ZIP_DEFLATED)
    return out.getvalue()
