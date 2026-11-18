"""Bind the historical sky-planning instrument to a local, revisioned operator mission."""
import hashlib
import json
from .fixed_delivery import archive, receive

from .store import PRODUCT, Conflict, StateError, canonical, digest

PRESET = PRODUCT / "examples/followup.json"
INVENTION = PRODUCT / "invention"
# Only reviewed public inputs and fixed local code can enter a recipient.
PUBLIC_FILES = ("plan.py", "verify.py", "geometry.py", "reference.py", "catalog.json", "mission.json", "sources/fink-alerts.json")


def source_files():
    files = {name: (INVENTION / name).read_bytes() for name in PUBLIC_FILES}
    files["review_followup.py"] = (PRODUCT / "ignition/followup_recipient.py").read_bytes()
    return files


def identity(files=None):
    files = dict(source_files() if files is None else files)
    files["example"] = PRESET.read_bytes()
    return digest({name: hashlib.sha256(content).hexdigest() for name, content in files.items()})


def contract(state, files):
    mission = state["mission"]
    preset = json.loads(PRESET.read_bytes())["mission"]
    if (mission["purpose"] != preset["purpose"] or mission["requirements"] != preset["requirements"]
            or mission["construction_spec"] or state["sources"] or state.get("inherited")):
        raise StateError("This installed instrument accepts only the registered public follow-up planning scope.")
    if set(mission["time"]) - {"deadline"}:
        raise StateError("The observing windows and public evidence are frozen. Amend only the execution deadline.")
    resources = mission["resources"]
    allowed = {"followup", "execution_strategy", "direct_method", "direct_after_research", "max_model_calls"}
    if (set(resources) - allowed or resources.get("execution_strategy", "adaptive") not in {"direct", "adaptive"}
            or resources.get("direct_method", "specialist") != "specialist" or resources.get("direct_after_research")):
        raise StateError("Choose direct or adaptive execution with the installed follow-up planner and its two controls.")
    controls = resources["followup"]
    if type(controls) is not dict or set(controls) != {"max_slots", "visits_per_target"}:
        raise StateError("Supply exactly max_slots and visits_per_target.")
    model = json.loads(files["mission.json"])
    capacity = len(model["slots_utc"])
    if type(controls["max_slots"]) is not int or not 0 <= controls["max_slots"] <= capacity:
        raise StateError(f"max_slots must be a whole number from 0 to {capacity} for this modeled night pair.")
    if type(controls["visits_per_target"]) is not int or controls["visits_per_target"] not in {1, 2}:
        raise StateError("Choose one or two visits per covered target.")
    return dict(model, **controls)


def checked(state):
    # Work from one exact snapshot. A cached Python import cannot silently run older
    # logic against a newer source digest. The subprocess sees no private brief.
    files = source_files()
    bound = identity(files)
    if bound != state.get("specialist_source") or digest([state["mission"], state["sources"]]) != state["input_sha256"]:
        raise Conflict("Source or mission identity changed. Open a new revision.")
    model = contract(state, files)
    files["mission.json"] = (canonical(model) + "\n").encode()
    result = receive(files, "review_followup.py", "The installed planner or independent check rejected this worklist.")
    binding = {"mission_sha256": digest(model), "input_sha256": state["input_sha256"], "specialist_sha256": bound}
    return files, binding, result


def run(controller, state):
    state["routing"] = {"strategy": state["mission"]["resources"].get("execution_strategy", "adaptive"),
                        "route": "direct", "method": "specialist",
                        "reason": "Construct a historical observing worklist under the operator’s selected cadence and budget."}
    controller._step(state, "construction", state["routing"]["reason"])
    _, binding, result = checked(state)
    state["contract_sha256"] = digest(binding)
    state["contract"] = dict(binding, sha256=state["contract_sha256"])
    state["followup_result"] = result["plan"]
    state["evaluation"] = {"status": "pass", "verification": result["verification"],
                           "comparison": {"outcome": "independent_schedule_objective_agreement"}}
    state["artifact"] = {"kind": "followup_worklist", "sha256": digest(result["plan"])}
    controller._step(state, "verification", "Worklist accepted for local historical planning. Dispatch authority is absent.", "verified")


def deliver(state, payload, trial):
    files, binding, result = checked(state)
    plan = result["plan"]
    if (state["contract_sha256"] != digest(binding) or state["contract"] != dict(binding, sha256=digest(binding))
            or digest(state["followup_result"]) != digest(plan) or state["artifact"].get("sha256") != digest(plan)
            or digest(state["evaluation"].get("verification")) != digest(result["verification"])):
        raise Conflict("The saved worklist or independent receipt differs from this revision. Requalify.")
    if trial:
        if payload != {}:
            raise StateError("Use {} to replay this worklist. Amend the mission to change its scope.")
        return plan
    for name, data in (("plan.json", plan), ("verification.json", result["verification"])):
        files[name] = (canonical(data) + "\n").encode()
    files["README.txt"] = (
        "FRONTIER OMEGA | Offline follow-up planning / Planification de suivi hors ligne\n"
        "Extract the files and run / Extraire les fichiers et exécuter : python3 -IB review_followup.py\n"
        "The catalog and modeled windows travel with this worklist. Inspect catalog.json for source attribution.\n"
        "Le catalogue et les créneaux modélisés accompagnent le programme. Les sources figurent dans catalog.json.\n"
        "With the Astropy packages declared in catalog.json, regenerate the comparison / Refaire les éphémérides :\n"
        "python3 -B reference.py --out independent-catalog.json\n"
        "Planning only. No telescope dispatch, observation, time allocation or purchase.\n"
        "Planification seulement. Aucune commande, observation, attribution de temps ou transaction.\n"
    ).encode()
    return archive(files)
