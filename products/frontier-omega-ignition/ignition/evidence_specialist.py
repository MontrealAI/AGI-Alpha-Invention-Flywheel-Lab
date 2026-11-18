"""Install the closed, read-only evidence desk in the durable private mission controller."""
from action_study import desk, pack
from .fixed_delivery import archive
from .store import Conflict, StateError, digest


def identity(task):
    return desk.case(task)["sha256"]


def template(task):
    rules = desk.validate(task)
    return {"purpose": rules["question"], "beneficiary": rules["beneficiary"],
            "requirements": [rules["acceptance"], rules["time_rule"]],
            "resources": {"evidence_action": task}, "authority": {}, "time": {}, "construction_spec": {}}


def checked(state):
    mission = state["mission"]
    task = mission["resources"]["evidence_action"]
    preset = template(task)
    if (mission["purpose"] != preset["purpose"] or mission["requirements"] != preset["requirements"]
            or mission["construction_spec"] or state["sources"] or state.get("inherited")
            or set(mission["resources"]) - {"evidence_action", "execution_strategy", "direct_method", "direct_after_research"}
            or mission["resources"].get("execution_strategy", "adaptive") not in ("adaptive", "direct")
            or mission["resources"].get("direct_method", "specialist") != "specialist"
            or mission["resources"].get("direct_after_research") or set(mission["time"]) - {"deadline"}):
        raise StateError("Use a registered decision contract, installed public sources and a read-only scope.")
    receipt = desk.case(task)
    if state.get("specialist_source") != receipt["sha256"] or state["input_sha256"] != digest([mission, state["sources"]]):
        raise Conflict("The mission or its evidence changed. Open a fresh revision.")
    binding = {"input_sha256": state["input_sha256"], "specialist_sha256": receipt["sha256"], "rule": receipt["contract_sha256"]}
    return receipt, dict(binding, sha256=digest(binding))


def run(controller, state):
    reason = "Read the least costly permitted source that settles the registered decision and retain the evidence."
    state["routing"] = {"strategy": "direct", "route": "direct", "method": "specialist", "reason": reason}
    controller._step(state, "construction", reason)
    receipt, contract = checked(state)
    state.update(contract=contract, contract_sha256=contract["sha256"], evidence_result=receipt,
                 evaluation={"status": "pass", "verification": receipt["sha256"]},
                 artifact={"kind": "evidence_decision", "sha256": receipt["sha256"]})
    controller._step(state, "verification", "The receipt qualifies a recommendation for this exact decision and source scope.", "verified")


def deliver(state, payload, trial):
    receipt, contract = checked(state)
    if (state["contract"] != contract or state["contract_sha256"] != contract["sha256"] or state["evidence_result"] != receipt
            or state["evaluation"] != {"status": "pass", "verification": receipt["sha256"]}
            or state["artifact"] != {"kind": "evidence_decision", "sha256": receipt["sha256"]}):
        raise Conflict("Saved decision differs from the reconstructed qualification.")
    if trial:
        if payload != {}:
            raise StateError("Use an empty object to replay this decision. Amend to change its scope.")
        return receipt
    files = pack.scoped_files(receipt["mission"], receipt["attempts"])
    files["mission.json"] = desk.encoded(receipt["mission"])
    files["decision.json"] = desk.encoded(receipt)
    files["README.txt"] = (
        "Extract and run / Extraire et exécuter\n"
        "python3 -IB action_study/desk.py verify decision.json --mission mission.json\n"
        "Add --expect SHA256 using an independently kept receipt digest.\n"
        "Ajouter --expect SHA256 avec une empreinte conservée séparément.\n"
        "Historical public archive files can contain later revisions. The specified cutoff controls the decision.\n"
        "Les fichiers publics historiques peuvent contenir des révisions ultérieures. La date limite gouverne la décision.\n"
    ).encode()
    return archive(files)
