"""Bind the installed archive experiment to a private, durable, independently checked mission."""
import hashlib
import json

from .change_recipient import controls, json_bytes
from .fixed_delivery import archive, receive
from .store import PRODUCT, Conflict, StateError, digest

PRESET = PRODUCT / "examples/change_desk.json"
PUBLIC_FILES = (
    "invention/early_survey/survey.py", "invention/early_survey/acquire.py",
    "invention/early_survey/REGISTRATION.md", "invention/early_survey/REFERENCE.md",
    "invention/early_survey/sources/index.json", "invention/early_survey/sources/class.json.gz",
    "invention/early_survey/sources/objects-1.json.gz", "invention/early_survey/sources/reference-index.json",
    "invention/early_survey/sources/reference-1.json.gz",
    "invention/evolution/alert.py", "invention/evolution/REGISTRATION.md",
    "invention/geometry.py", "invention/reference.py", "evolution_trials/verify.py", "evolution_trials/select.sql",
)


# The public historical response files allow offline checking. Precomputed full-period
# results would disclose a later decision even in a cutoff-specific delivery.
EXPOSURES = "invention/early_survey/exposures/"
SECOND_ARCHIVE_FILES = tuple(EXPOSURES + name for name in (
    "avro_packet.py", "verify.py", "REGISTRATION.md",
    "sources/index.json", "sources/detections.json", "sources/astrometry.json.gz",
    "sources/coverage.csv.gz", "sources/empty-geometry.csv.gz", "sources/empty-stream.csv.gz",
    "sources/forced.json.gz", "sources/g.avro.gz", "sources/r.avro.gz", "sources/history.avro.gz",
))


def source_files(extra=False):
    selected = PUBLIC_FILES + (SECOND_ARCHIVE_FILES if extra else ())
    files = {name: (PRODUCT / name).read_bytes() for name in selected}
    files["review_change.py"] = (PRODUCT / "ignition/change_recipient.py").read_bytes()
    return files


def identity(scope, files=None, preset=None):
    extra = isinstance(scope, dict) and scope.get("check_other_archive") is True
    files = dict(source_files(extra) if files is None else files)
    files["example"] = PRESET.read_bytes() if preset is None else preset
    return digest({name: hashlib.sha256(value).hexdigest() for name, value in files.items()})


def checked(state):
    mission = state["mission"]
    scope = controls(mission["resources"]["change_desk"])
    files = source_files(scope["check_other_archive"])
    preset = PRESET.read_bytes()
    source_digest = identity(scope, files, preset)
    if state.get("specialist_source") != source_digest or state["input_sha256"] != digest([mission, state["sources"]]):
        raise Conflict("Source or mission identity changed. Open a new revision.")
    expected = json.loads(preset)["mission"]
    if (mission["purpose"] != expected["purpose"] or mission["requirements"] != expected["requirements"]
            or mission["construction_spec"] or state["sources"] or state.get("inherited")):
        raise StateError("This instrument accepts the installed public archive and its registered review question.")
    resources = mission["resources"]
    allowed = {"change_desk", "execution_strategy", "direct_method", "direct_after_research", "max_model_calls"}
    if (set(resources) - allowed or set(mission["time"]) - {"deadline"}
            or resources.get("execution_strategy", "adaptive") not in ("adaptive", "direct")
            or resources.get("direct_method", "specialist") != "specialist" or resources.get("direct_after_research")):
        raise StateError("Select direct or adaptive execution of the installed archive instrument.")
    files["scope.json"] = json_bytes(scope)
    result = receive(files, "review_change.py", "The independent archive check withheld this delivery.")
    binding = {"input_sha256": state["input_sha256"], "specialist_sha256": source_digest, "scope": scope}
    return files, dict(binding, sha256=digest(binding)), result


def run(controller, state):
    reason = "Reconstruct the selected public archive interval and compare each review decision with independent SQL."
    state["routing"] = {"strategy": state["mission"]["resources"].get("execution_strategy", "adaptive"),
                        "route": "direct", "method": "specialist", "reason": reason}
    controller._step(state, "construction", reason)
    _, contract, result = checked(state)
    state["contract"] = contract
    state["contract_sha256"] = contract["sha256"]
    state["change_result"] = result["queue"]
    state["evaluation"] = {"status": "pass", "verification": result["receipt"]}
    state["artifact"] = {"kind": "dated_archive_queue", "sha256": digest(result["queue"])}
    controller._step(state, "verification", "Archive review queue verified for the selected UTC cutoff and baseline.", "verified")


def deliver(state, payload, trial):
    files, contract, result = checked(state)
    if (digest(state["contract"]) != digest(contract) or state["contract_sha256"] != contract["sha256"]
            or digest(state["change_result"]) != digest(result["queue"])
            or state["artifact"] != {"kind": "dated_archive_queue", "sha256": digest(result["queue"])}
            or digest(state["evaluation"]) != digest({"status": "pass", "verification": result["receipt"]})):
        raise Conflict("Saved queue, receipt or contract differs from this revision. Requalify.")
    if trial:
        if payload != {}:
            raise StateError("Use {} to replay the current review queue. Amend the mission to change its scope.")
        return result["queue"]
    files["queue.json"] = json_bytes(result["queue"])
    files["worklist.csv"] = result["csv"].encode("utf-8")
    if "archive_csv" in result:
        files["archive-recheck.csv"] = result["archive_csv"].encode("utf-8")
    files["verification.json"] = json_bytes(result["receipt"])
    files["README.txt"] = (
        "FRONTIER Ω · Dated archive review / Suivi des variations archivées\n\n"
        "Extract and verify / Extraire et vérifier\n  python3 -IB review_change.py\n\n"
        "To compare with a separately retained workbench digest, supply --expect-queue SHA256.\n"
        "Pour comparer avec une empreinte conservée dans l’atelier, ajouter --expect-queue SHA256.\n\n"
        "queue.json records the signed measurements and public detection IDs for your UTC cutoff. "
        "worklist.csv gives a decision for every selected target and band. "
        "When the second archive was selected, archive-recheck.csv gives its separately dated result. "
        "The original public historical responses accompany this delivery. The cutoff controls which observations enter the calculation.\n\n"
        "queue.json donne les mesures signées et les identifiants de détection à la date UTC choisie. "
        "worklist.csv indique la décision pour chaque cible et chaque filtre. Si la seconde archive a été choisie, "
        "archive-recheck.csv donne son résultat à la date demandée. Les réponses publiques des archives sont incluses. "
        "Le calcul utilise uniquement les observations admissibles à la date choisie.\n"
    ).encode("utf-8")
    return archive(files)
