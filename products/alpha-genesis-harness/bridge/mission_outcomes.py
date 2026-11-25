# SPDX-License-Identifier: Apache-2.0
"""Render mission outcomes from the current journal's assessed evidence."""

from itertools import islice

from .workflows import digest, require


SCHEMA = "frontier/mission-outcome/v1"
TEXT_FIELDS = {"deliverable", "verification"}
LIST_FIELDS = {"criteria", "constraints", "assumptions", "abstention_conditions", "alternatives"}
DECLARATION_FIELDS = TEXT_FIELDS | LIST_FIELDS | {"required_claims"}
MISSING_REASONS = {"AUTHORIZED_INPUT_MISSING", "REQUIRED_FIELD_MISSING"}
ENDING_STATES = {"complete", "needs_review", "failed", "exhausted"}
BLOCKED_STATES = {"cancelled", "expired", "revoked"}
MISSING_LIMIT = 8
CLAIM_FIELDS = ("id", "dataset", "unit", "dimension")

MESSAGES = {
    "VERIFIED": (
        "All required numerical results agree with their registered references. Independent mission acceptance remains separate.",
        "Tous les résultats numériques requis concordent avec leurs références déclarées. La mission reste soumise à une évaluation indépendante.",
    ),
    "PARTIAL": (
        "Some required numerical results are verified. The remaining requirements need evidence or verification.",
        "Certains résultats numériques requis sont vérifiés. Les autres exigences nécessitent des preuves ou une vérification.",
    ),
    "ABSTAIN": (
        "A required input or observation is missing. Supply the listed evidence before drawing the conclusion.",
        "Une donnée ou une observation requise manque. Fournissez les éléments indiqués avant de tirer la conclusion.",
    ),
    "BLOCKED": (
        "A required check or permission blocks this result. Review the recorded reasons.",
        "Un contrôle ou une autorisation empêche de retenir ce résultat. Consultez les motifs consignés.",
    ),
    "PENDING": (
        "The required conclusions are awaiting an eligible calculation and verification.",
        "Les conclusions requises attendent un calcul admissible et sa vérification.",
    ),
    "UNVERIFIED": (
        "Review the recorded work and evidence to assess completion.",
        "Examinez le travail et les preuves consignés pour évaluer l’achèvement de la mission.",
    ),
}

REASON_MESSAGES = {
    "AUTHORIZED_INPUT_MISSING": ("The approved dataset is missing.", "Le jeu de données approuvé manque."),
    "REQUIRED_FIELD_MISSING": ("A required field or observation is missing.", "Un champ ou une observation requise manque."),
    "NO_BOUND_EXECUTION": ("Run the calculation against its approved inputs.", "Exécutez le calcul sur les données approuvées."),
    "INDEPENDENT_REFERENCE_REQUIRED": ("The calculation needs a separate reference.", "Le calcul nécessite une référence distincte."),
    "REFERENCE_DISAGREES": ("The executed value differs from the registered reference.", "La valeur calculée diffère de la référence déclarée."),
    "CLAIM_CONTRADICTS_EXECUTED_RESULT": ("The proposed value differs from the executed value.", "La valeur proposée diffère de la valeur calculée."),
    "INPUT_ORIGIN_INELIGIBLE": ("The input provenance is ineligible for this claim.", "La provenance des données est inadmissible pour cette affirmation."),
    "INPUT_ASSUMPTIONS_INCOMPATIBLE": ("The input assumptions are incompatible with this claim.", "Les hypothèses des données sont incompatibles avec cette affirmation."),
    "INSTRUMENT_REPAIR_REQUIRED": ("Correct the instrument and rerun the calculation on the approved inputs.", "Corrigez l’instrument et relancez le calcul sur les données approuvées."),
    "EXECUTION_OPERATION_STALE": ("The calculation must be rerun with the current operation.", "Le calcul doit être relancé avec l’opération actuelle."),
    "OUTCOME_EVIDENCE_SCOPE_MISMATCH": ("The evidence belongs to a different or incomplete scope.", "Les preuves relèvent d’un périmètre différent ou incomplet."),
}


def _text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8")) <= limit


def validate_contract(contract, requirements):
    """Accept only operator declarations and references to already registered claims."""
    code = "MISSION_OUTCOME_CONTRACT"
    require(isinstance(contract, dict) and set(contract) <= DECLARATION_FIELDS,
            "An outcome contract can declare requirements but cannot grant acceptance.", code)
    for field in TEXT_FIELDS & contract.keys():
        require(_text(contract[field], 4096), "Outcome deliverable and verification need bounded text.", code)
    for field in LIST_FIELDS & contract.keys():
        values = contract[field]
        require(isinstance(values, list) and len(values) <= 12 and all(_text(value, 1200) for value in values),
                "Outcome criteria, constraints and other conditions need bounded text lists.", code)
    if "required_claims" in contract:
        declared = {claim["id"] for claim in requirements.get("evidence", {}).get("claims", [])}
        ids = contract["required_claims"]
        require(isinstance(ids, list) and all(isinstance(ident, str) and ident in declared for ident in ids)
                and len(set(ids)) == len(ids) and set(ids) == declared,
                "An outcome contract must cover exactly the registered required claim IDs.", code)


def _present_contract(spec, mission, requirements, claims):
    declared = requirements.get("outcome", {})
    approved = requirements.get("evidence", {}).get("inputs", {})
    inputs = [{"id": ident, "kind": row["kind"], "source_version": row["version"], "origin": row["origin"]}
              for ident, row in sorted(approved.items())]
    inputs.extend({"id": ident, "kind": "table"} for ident in sorted(requirements.get("approved_tables", {}))
                  if ident not in approved)
    limits = {key: spec[key] for key in (
        "max_iterations", "max_actions", "max_output_tokens", "max_operations", "local_only", "tool_permissions",
    ) if key in spec}
    return {
        "original_ambition": mission["original_ambition"],
        "objective": spec["objective"],
        "deliverable": declared.get("deliverable", spec["objective"]),
        "required_claims": [claim["id"] for claim in claims],
        "criteria": declared.get("criteria", []),
        "constraints": declared.get("constraints", []),
        "assumptions": declared.get("assumptions", []),
        "abstention_conditions": declared.get("abstention_conditions", []),
        "alternatives": declared.get("alternatives", []),
        "verification": declared.get("verification"),
        "approved_inputs": inputs,
        "approved_source_count": len(requirements.get("public_sources", [])),
        "approved_source_captures": [{"id": ident, "source_version": row["version"], "sha256": row["sha256"]}
                                     for ident, row in sorted(requirements.get("source_snapshots", {}).items())],
        "resource_envelope": limits,
    }


def _row_identity(requirements, dataset, table, row):
    keys = requirements.get("approved_schemas", {}).get(dataset, {}).get("primary_keys", {}).get(table, [])
    values = {key: row.get(key) for key in keys}
    if all(type(value) is int or isinstance(value, str) and _text(value, 120) for value in values.values()):
        return values
    return {}


def _missing_observations(requirements, claim):
    dataset = claim["dataset"]
    if claim["tool"] == "run_table":
        data = requirements.get("approved_tables", {}).get(dataset, {})
        for table, field in claim.get("required_fields", []):
            rows = data.get(table)
            if not isinstance(rows, list) or not rows:
                yield {"path": [table, field], "label": f"{table}.{field}"}
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or row.get(field) is None:
                    label = f"{table}[{index}].{field}"
                    missing = {"path": [table, field], "row_index": index, "label": label}
                    identity = _row_identity(requirements, dataset, table, row) if isinstance(row, dict) else {}
                    if identity:
                        missing["row_key"] = identity
                        missing["label"] += " (" + ", ".join(f"{key}={value}" for key, value in identity.items()) + ")"
                    yield missing
    else:
        data = requirements["evidence"]["inputs"].get(dataset, {}).get("values", {})
        for path in claim.get("required_fields", []):
            value = data
            for part in path:
                value = value.get(part) if isinstance(value, dict) else None
            if value is None:
                yield {"path": path, "label": ".".join(path)}


def _current_report(state, claim, report, claim_hash):
    return (report.get("mission_id") == state["id"] and report.get("revision_sha256") == state["spec_hash"]
            and report.get("claim_contract_sha256") == claim_hash and report.get("source_version") == claim["version"]
            and all(report.get(key) == claim[key] for key in (*CLAIM_FIELDS, "locator", "requires")))


def _claim_events(journal):
    latest = {}
    for event in journal:
        detail = event["detail"]
        if event["kind"] == "claim_refused":
            ident = detail.get("claim_id")
        elif event["kind"] == "tool_completed":
            receipt = detail.get("outcome", {}).get("claim_execution")
            ident = receipt.get("claim_id") if isinstance(receipt, dict) else None
        else:
            continue
        if isinstance(ident, str):
            latest[ident] = event
    return latest


def _verified(state, claim, report, event, fields):
    # The evidence service has already checked the input lineage, operation and output.
    # Require its positive report and live journal proof to agree at this presentation boundary.
    receipt = report.get("execution_receipt")
    if not isinstance(receipt, dict) or event is None or event["kind"] != "tool_completed":
        return None
    operation = receipt.get("operation")
    if not isinstance(operation, dict) or not isinstance(operation.get("artifact_sha256"), str):
        return None
    if (claim.get("reference") is None or report.get("reference") != claim["reference"]
            or report.get("reason") != "MATCHES_FROZEN_REFERENCE" or not isinstance(report.get("value"), str)
            or report.get("value") != report.get("executed_value")
            or receipt.get("mission_id") != state["id"] or receipt.get("revision_sha256") != state["spec_hash"]
            or receipt.get("claim_id") != claim["id"] or receipt.get("claim_contract_sha256") != report["claim_contract_sha256"]
            or not isinstance(receipt.get("sha256"), str)
            or event["sha256"] != report.get("event_sha256")
            or state["artifacts"].get(operation.get("artifact"), {}).get("sha256") != operation.get("artifact_sha256")
            or event.get("detail", {}).get("outcome", {}).get("claim_execution") != receipt):
        return None
    return {**fields, "status": "VERIFIED", "value": report["value"], "source_version": claim["version"],
            "assumptions": claim["requires"], "reference_tolerance": str(claim["reference"].get("tolerance", "0")),
            "claim_contract_sha256": report["claim_contract_sha256"], "event_sha256": report["event_sha256"],
            "execution_sha256": receipt["sha256"]}


def _project_claim(state, requirements, claim, report, events, language_index):
    fields = {key: claim[key] for key in CLAIM_FIELDS}
    claim_hash = digest(claim)
    if report is None:
        status, reason = "ABSTAIN", "NO_BOUND_EXECUTION"
    elif not _current_report(state, claim, report, claim_hash):
        status, reason = "REJECTED", "OUTCOME_EVIDENCE_SCOPE_MISMATCH"
    elif report.get("status") == "VERIFIED":
        verified = _verified(state, claim, report, events.get(claim["id"]), fields)
        if verified is not None:
            return verified
        status, reason = "REJECTED", "OUTCOME_EVIDENCE_SCOPE_MISMATCH"
    else:
        status, reason = report["status"], report["reason"]
    detail = {**fields, "status": status, "reason": reason, "claim_contract_sha256": claim_hash}
    if reason == "AUTHORIZED_INPUT_MISSING":
        detail["missing"] = [{"dataset": claim["dataset"], "label": claim["dataset"]}]
    elif reason == "REQUIRED_FIELD_MISSING":
        missing = list(islice(_missing_observations(requirements, claim), MISSING_LIMIT + 1))
        detail["missing"], detail["missing_truncated"] = missing[:MISSING_LIMIT], len(missing) > MISSING_LIMIT
    if reason in REASON_MESSAGES:
        detail["message"] = REASON_MESSAGES[reason][language_index]
    return detail


def _status(required, conclusions, unresolved, execution_status, authority):
    if required and not unresolved:
        return "VERIFIED"
    if conclusions:
        return "PARTIAL"
    if authority in BLOCKED_STATES or execution_status in BLOCKED_STATES or any(
            item["status"] == "REJECTED" for item in unresolved):
        return "BLOCKED"
    if any(item["reason"] in MISSING_REASONS for item in unresolved):
        return "ABSTAIN"
    if not required or execution_status in ENDING_STATES or any(item["status"] == "SOURCE_BOUND" for item in unresolved):
        return "UNVERIFIED"
    return "PENDING"


def assemble_outcome(state, evidence, *, authority=None):
    """Project freshly assessed server evidence without reading any proposed prose."""
    spec, mission = state["spec"], state["spec"]["mission"]
    requirements, language = mission["requirements"], mission["language"]
    language_index = int(language == "fr")
    claims = requirements.get("evidence", {}).get("claims", [])
    contract = _present_contract(spec, mission, requirements, claims)
    events = _claim_events(state["events"])
    reports = {report["id"]: report for report in evidence["claims"]}
    conclusions, unresolved = [], []
    for claim in claims:
        record = _project_claim(state, requirements, claim, reports.get(claim["id"]), events, language_index)
        (conclusions if record["status"] == "VERIFIED" else unresolved).append(record)
    status = _status(claims, conclusions, unresolved, state["status"], authority)
    return {"schema": SCHEMA, "mission_id": state["id"], "revision_sha256": state["spec_hash"],
            "contract_sha256": digest(contract), "contract": contract, "language": language,
            "status": status, "message": MESSAGES[status][language_index], "conclusions": conclusions,
            "unresolved": unresolved, "quantitative_report_ready": status == "VERIFIED",
            "independent_acceptance": "NOT_ESTABLISHED"}
