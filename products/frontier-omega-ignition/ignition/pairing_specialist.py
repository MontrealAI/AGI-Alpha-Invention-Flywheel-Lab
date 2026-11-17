"""Versioned private mission entry point for the fixed public Pairing Lab instrument."""
import hashlib
import io
import json
from datetime import date
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from flagship import conventional, package, pairing_lab
from .store import Conflict, PRODUCT, StateError, canonical, digest

PRESET = PRODUCT / "examples" / "pairing.json"


def identity():
    paths = [PRODUCT / "flagship" / name for name in package.FILES] + [PRESET]
    paths.extend(sorted(p for p in (PRODUCT / "frontier_study").glob("*")
                        if p.suffix in (".json", ".py") and p.is_file()))
    return digest({str(p.relative_to(PRODUCT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def parameters(mission):
    standard = json.loads(PRESET.read_bytes())["mission"]
    if (mission["purpose"] != standard["purpose"] or mission["requirements"] != standard["requirements"]
            or mission["construction_spec"]):
        raise StateError("This specialist answers the public benchmark decision only. Remove pairing_lab to investigate a different objective or requirement.")
    params = mission["resources"]["pairing_lab"]
    if not isinstance(params, dict) or set(params) != set(standard["resources"]["pairing_lab"]):
        raise StateError("Supply budget, width, min_percent, model and repository in pairing_lab")
    if mission["resources"].get("direct_method", "specialist") != "specialist":
        raise StateError("This registered task uses an offline specialist. Remove the override to run it.")
    return params


def compare(params):
    raw = (PRODUCT / "flagship" / "runs.csv").read_bytes()
    if pairing_lab.digest(raw) != pairing_lab.PUBLIC_HASH:
        raise Conflict("Study inputs differ from the registered public dataset")
    analysis = pairing_lab.analyze(raw, **params, witnesses=False)
    picked, scores = conventional.enumerate_sql(raw, params["budget"], params["width"],
                                               params["model"], params["repository"])
    if (list(picked) if picked else None) != analysis["selected"]:
        raise StateError("Independent SQL disagreed with the selected policy")
    if picked:
        for split in ("calibration", "audit"):
            if scores[split][picked] != analysis[split]:
                raise StateError("Independent SQL disagreed with the recorded issue or token totals")
        audit = scores["audit"][picked]
        confirmed = (audit["tokens"] <= params["budget"] * audit["tasks"] and
                     100 * audit["solved"] >= params["min_percent"] * audit["tasks"])
        if confirmed != analysis["qualifies"]:
            raise StateError("Independent SQL totals disagree with the pilot decision")
    return dict(analysis, sql_agreement=True)


def run(ctrl, state):
    mission = state["mission"]
    params = parameters(mission)
    if state["sources"]:
        raise StateError("The named study accepts its pinned public inputs. Remove pairing_lab for an investigation of additional submitted sources.")
    strategy = mission["resources"].get("execution_strategy", "adaptive")
    research = strategy == "research"
    state["routing"] = {"strategy": strategy, "route": "research" if research else "direct", "method": "specialist",
                        "reason": "Investigate the curated capability inventory before checking the named study." if research else
                                  "The operator selected an installed, independently checkable coding-stack study."}
    ctrl._step(state, "routing", state["routing"]["reason"])
    cutoff = mission["time"].get("as_of")
    if cutoff is not None and date.fromisoformat(cutoff) < date(2026, 10, 22) and not research:
        return ctrl._step(state, "selection", "The public task measurements were unavailable on the requested date.", "deferred")
    if research:
        from frontier_study import default_mission, investigate
        question = dict(default_mission(), purpose=mission["purpose"], beneficiary=mission["beneficiary"])
        if cutoff:
            question["as_of"] = cutoff
        study = investigate(question)
        state["opportunity_study"] = study
        if study["decision"].get("candidate_id") != "paired-replay" or study["decision"]["status"] != "select":
            return ctrl._step(state, "selection", "The evidence study selected another route. The requested specialist has not been qualified.", "deferred")
    contract = {"purpose": mission["purpose"], "requirements": mission["requirements"], "parameters": params,
                "input_sha256": state["input_sha256"], "specialist_sha256": ctrl.pairing_source,
                "data_sha256": pairing_lab.PUBLIC_HASH}
    state["contract_sha256"] = digest(contract)
    state["contract"] = dict(contract, sha256=state["contract_sha256"])
    ctrl._step(state, "contract", "Froze the operator's thresholds, cohort, purpose and source identities.")
    result = compare(params)
    state["pairing_result"] = result
    state["artifact"] = {"kind": "pairing_lab", "sha256": digest(result), "selected": result["selected"]}
    state["evaluation"] = {"status": "pass", "comparison": {"outcome": "independent_sql_agreement"},
                           "scope": "Accepted decision report. The stack's separate pilot verdict is " + result["verdict"] + "."}
    ctrl._step(state, "verification", "Independent SQL reproduced the decision and recorded totals. Pilot finding: " + result["verdict"], "verified")


def deliver(ctrl, state, payload, trial):
    params = parameters(state["mission"])
    contract = dict(state["contract"])
    recorded = contract.pop("sha256")
    result = compare(params)
    if (state["input_sha256"] != digest([state["mission"], state["sources"]]) or identity() != ctrl.pairing_source or recorded != digest(contract) or recorded != state["contract_sha256"]
            or contract["input_sha256"] != state["input_sha256"] or contract["specialist_sha256"] != ctrl.pairing_source
            or contract["parameters"] != params or digest(result) != state["artifact"]["sha256"] or result != state["pairing_result"]):
        raise Conflict("The decision or its acceptance inputs changed. Amend this mission for fresh verification.")
    if trial:
        if payload != {}:
            raise StateError("Use an empty object to inspect the current decision. Submit changed thresholds as an amended mission.")
        return result
    stream = io.BytesIO()
    package.build(stream)
    with ZipFile(stream, "a") as bundle:
        info = ZipInfo("mission-decision.json", (2026, 11, 17, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        bundle.writestr(info, (canonical(result) + "\n").encode())
    return stream.getvalue()
