from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from connected_enterprise.scale import trailing_profit
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services
from experiments.commerce006 import PINS as LEGACY_PINS

PREFIX = "experiments/super_alpha_20261103_185dc1a1/"
MODULE = PREFIX + "finance.py"
SCHEMA = "super-alpha-185dc1a1/discovery-finance/v1"
OPENING = 100_000_000_000
END_HOUR = 8760
COST_BASIS = "AUTHORED_COMPLETE_DISCOVERY_ENVELOPE_ACTUAL_BILLING_UNKNOWN"
CATEGORIES = ("research", "construction", "verification", "failed_attempts", "inference", "compute", "tools_and_inputs", "maintenance")
ZERO_CATEGORIES = {"acquisition", "onboarding", "production_delivery_support_refunds", "tax", "financing", "capital_depreciation"}
POLICY = "IMMEDIATE_EXPENSING_NO_CAPITALIZATION_NO_FINANCING_NO_SALES"
BOOTSTRAP = "Unused native runtime fixtures only: 96 accepted baseline service artifacts and 3 adversarial fixtures; zero orders, deliveries, customers, collections or revenue from them. These are not the confidential-capability experiment's output."


def _read(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("REGULAR_FINANCE_FILE_REQUIRED")
    return strict_json(path.read_bytes())


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value) + b"\n")


def _safe(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or Path(relative).as_posix() != relative:
        raise ValueError("RELATIVE_SOURCE_PATH_REQUIRED")
    path = Path(root).absolute() / relative
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("SOURCE_SYMLINK_REFUSED")
    return path


def validate_protocol(protocol):
    if not isinstance(protocol, dict) or not isinstance(protocol.get("finance"), dict):
        raise ValueError("REGISTERED_DISCOVERY_FINANCE_REQUIRED")
    f = protocol["finance"]
    required = {"opening_microUSD", "operating_end_hour", "cost_basis", "costs", "zero_cost_categories"}
    metadata = {"native_boundary", "continuity", "milestone"}
    if not required <= set(f) or set(f) - required - metadata or any(not isinstance(f[k], str) or not f[k].strip() for k in set(f) & metadata):
        raise ValueError("EXACT_DISCOVERY_FINANCE_FIELDS_REQUIRED")
    if type(f["opening_microUSD"]) is not int or f["opening_microUSD"] != OPENING or type(f["operating_end_hour"]) is not int or f["operating_end_hour"] != END_HOUR:
        raise ValueError("EXACT_100K_AND_365_DAY_RESEARCH_HORIZON_REQUIRED")
    if f["cost_basis"] != COST_BASIS or not isinstance(f["costs"], list) or len(f["costs"]) != len(CATEGORIES):
        raise ValueError("AUTHORED_COMPLETE_EIGHT_CATEGORY_ENVELOPE_REQUIRED")
    ids, categories, last_hour = set(), set(), -1
    for row in f["costs"]:
        if not isinstance(row, dict) or set(row) != {"id", "category", "hour", "amount_microUSD", "basis"}:
            raise ValueError("EXACT_COST_ROW_REQUIRED")
        if not isinstance(row["id"], str) or not row["id"] or len(row["id"]) > 80 or row["id"] in ids:
            raise ValueError("UNIQUE_COST_ID_REQUIRED")
        if row["category"] not in CATEGORIES or row["category"] in categories:
            raise ValueError("ONE_COST_PER_REGISTERED_CATEGORY_REQUIRED")
        if type(row["hour"]) is not int or not last_hour <= row["hour"] < END_HOUR or row["hour"] < 0:
            raise ValueError("ORDERED_IN_HORIZON_COST_HOURS_REQUIRED")
        if type(row["amount_microUSD"]) is not int or row["amount_microUSD"] <= 0 or not isinstance(row["basis"], str) or not row["basis"].strip():
            raise ValueError("POSITIVE_EXACT_COST_AND_ASSUMPTION_BASIS_REQUIRED")
        ids.add(row["id"]); categories.add(row["category"]); last_hour = row["hour"]
    if sum(r["amount_microUSD"] for r in f["costs"]) > OPENING:
        raise ValueError("DECLARED_DISCOVERY_PATH_NOT_CASH_FUNDED")
    zeros = f["zero_cost_categories"]
    if not isinstance(zeros, dict) or set(zeros) != ZERO_CATEGORIES or any(not isinstance(v, str) or not v.strip() for v in zeros.values()):
        raise ValueError("EXPLICIT_ZERO_COST_APPLICABILITY_REQUIRED")
    paths = protocol.get("source_paths")
    if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)) or any(not isinstance(p, str) or not p.startswith(PREFIX) for p in paths):
        raise ValueError("REGISTERED_EXPERIMENT_SOURCE_PATHS_REQUIRED")
    for p in paths:
        _safe(Path.cwd(), p)
    return f


def required_paths(protocol, protocol_path):
    validate_protocol(protocol)
    return sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS) | set(LEGACY_PINS) | set(protocol["source_paths"]) | {MODULE, protocol_path})


def _source_hashes(root, paths):
    return {p: hashlib.sha256(_safe(root, p).read_bytes()).hexdigest() for p in paths}


def _copy_source(root, target, hashes):
    if _source_hashes(root, hashes) != hashes:
        raise ValueError("DISCOVERY_SOURCE_CHANGED")
    for relative in hashes:
        dest = _safe(target, relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_safe(root, relative), dest)


def _binding(protocol, hashes, protocol_path):
    return {"schema": SCHEMA, "protocol_path": protocol_path, "protocol_sha256": digest(protocol),
            "source_hashes": hashes, "source_sha256": digest(hashes), "accounting_policy": POLICY,
            "bootstrap_scope": BOOTSTRAP}


def _expected_request(cost, binding):
    return {"operation": "spend", "id": "discovery-" + cost["id"], "kind": "discovery_" + cost["category"],
            "amount": cost["amount_microUSD"], "day": cost["hour"],
            "work": {"experiment_binding_sha256": digest(binding), "protocol_sha256": binding["protocol_sha256"],
                     "experiment_source_sha256": binding["source_sha256"], "cost": cost, "scope": COST_BASIS},
            "expected_net": 0, "allow_seed": True}


def _prefix(record, protocol, binding, contract):
    ledger = record["ledger"]
    config = ledger["config"]
    if config["opening"] != OPENING or config["working"] != 0 or config["contract"] != contract:
        raise ValueError("DISCOVERY_ACCOUNT_IDENTITY_OR_CAPITAL_CHANGED")
    if ledger["orders"] or any(row["op"] != "cost" for row in ledger["actions"]):
        raise ValueError("COST_ONLY_ACCOUNT_CANNOT_CLAIM_SALES_OR_OTHER_ACTIONS")
    entries = record["connected_journal"]["entries"]
    costs = protocol["finance"]["costs"]
    if len(entries) > len(costs) or len(ledger["actions"]) != len(entries):
        raise ValueError("REGISTERED_COST_PREFIX_REQUIRED")
    for cost, entry in zip(costs, entries):
        if entry["request"] != _expected_request(cost, binding) or entry["status"] != "COMPLETE" or entry["funding"] != "SEED":
            raise ValueError("REGISTERED_SOURCE_BOUND_COST_CHANGED")
    total = sum(r["amount_microUSD"] for r in costs[:len(entries)])
    s = ledger["summary"]
    expected = {"revenue": 0, "collections": 0, "expenses": total, "expensePaid": total, "payables": 0,
                "profit": -total, "cash": OPENING-total, "available": OPENING-total,
                "custodyReserve": 0, "tailReserve": 0, "workingCapital": 0, "reservedInvestment": 0,
                "unrestrictedEarned": 0, "recoveryIncome": 0}
    if any(s[k] != v for k, v in expected.items()):
        raise ValueError("DISCOVERY_NATIVE_COST_RECONCILIATION_FAILED")
    return len(entries)


def _report(record, protocol, binding, contract, native_audit):
    count = _prefix(record, protocol, binding, contract)
    complete = count == len(protocol["finance"]["costs"])
    window = trailing_profit(record["ledger"], operating_end_hour=END_HOUR if count else None, operating_complete=complete)
    return {"schema": SCHEMA, "scope": "AUDITED_CONDITIONAL_COST_ONLY_DISCOVERY_ACCOUNT",
            "account_contract": contract, "binding_sha256": digest(binding), "native_export_sha256": digest(record),
            "native_audit": native_audit, "costs_committed": count, "complete": complete,
            "financial_summary_microUSD": record["ledger"]["summary"], "trailing_profit": window,
            "cost_basis": COST_BASIS, "accounting_policy": POLICY,
            "actual_model_host_billing_microUSD": None, "actual_human_labor_hours": None,
            "real_customers": 0, "simulated_qualified_orders": 0, "bootstrap_scope": BOOTSTRAP,
            "three_billion_objective": "UNMET", "profitable_earned_funded_successor": "NOT_ESTABLISHED",
            "year_scope": "Closed modeled discovery and asset-maintenance interval [0,8760), with no commercial operation or annualized sales. Full authored envelopes are expensed, including failed-attempt and idle maintenance allowances; these are not observed bills.",
            "continuing_customer_obligations": "NONE_NO_SOLD_SERVICES", "accounts_pooled": False,
            "capital_injections_after_opening_microUSD": 0}


def _freeze(root, protocol_path, output):
    protocol = _read(_safe(root, protocol_path))
    validate_protocol(protocol)
    hashes = _source_hashes(root, required_paths(protocol, protocol_path))
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != hashes[MODULE]:
        raise ValueError("EXECUTING_DISCOVERY_FINANCE_SOURCE_CHANGED")
    binding = _binding(protocol, hashes, protocol_path)
    output.mkdir(parents=True, exist_ok=False)
    _copy_source(root, output / "source", hashes)
    manifest = prepare_services(output / "source", "runtime_fixtures")
    contract = "super-alpha-discovery-185dc1a1-" + uuid.uuid4().hex
    frozen = {"schema": SCHEMA, "protocol": protocol, "binding": binding, "contract": contract,
              "manifest_sha256": digest(manifest), "fresh_separately_seeded_account": True}
    _write(output / "MANIFEST.json", manifest)
    _write(output / "FROZEN.json", frozen)
    return frozen, manifest


def _load(root, output):
    frozen, manifest = _read(output / "FROZEN.json"), _read(output / "MANIFEST.json")
    if frozen.get("schema") != SCHEMA or digest(manifest) != frozen["manifest_sha256"]:
        raise ValueError("DISCOVERY_FREEZE_OR_MANIFEST_CHANGED")
    protocol, binding = frozen["protocol"], frozen["binding"]
    validate_protocol(protocol)
    paths = required_paths(protocol, binding["protocol_path"])
    if sorted(binding["source_hashes"]) != paths or binding != _binding(protocol, binding["source_hashes"], binding["protocol_path"]):
        raise ValueError("EXACT_DISCOVERY_SOURCE_BINDING_REQUIRED")
    if _read(_safe(output / "source", binding["protocol_path"])) != protocol:
        raise ValueError("FROZEN_PROTOCOL_CHANGED")
    for source in (root, output / "source"):
        if _source_hashes(source, paths) != binding["source_hashes"]:
            raise ValueError("DISCOVERY_SOURCE_CHANGED")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != binding["source_hashes"][MODULE]:
        raise ValueError("EXECUTING_DISCOVERY_FINANCE_SOURCE_CHANGED")
    return frozen, manifest


def run(root, protocol_path, output, *, max_new_costs=None):
    root, output = Path(root).absolute(), Path(output).absolute()
    if max_new_costs is not None and (type(max_new_costs) is not int or max_new_costs < 0):
        raise ValueError("NONNEGATIVE_CHECKPOINT_STEP_REQUIRED")
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("ACCOUNT_OUTPUT_SYMLINK_REFUSED")
    if output.exists():
        frozen, manifest = _load(root, output)
        if protocol_path != frozen["binding"]["protocol_path"]:
            raise ValueError("ORIGINAL_PROTOCOL_PATH_REQUIRED")
    else:
        frozen, manifest = _freeze(root, protocol_path, output)
    protocol, binding, contract = frozen["protocol"], frozen["binding"], frozen["contract"]
    with JournalAccount(output / "source", manifest, output / "account.sqlite", opening=OPENING, working=0, contract=contract) as account:
        record = account.export()
        count = _prefix(record, protocol, binding, contract)
        checkpoint_path = output / "CHECKPOINT.json"
        if checkpoint_path.exists():
            state = account.verify_checkpoint(_read(checkpoint_path))
            if state.get("binding_sha256") != digest(binding) or type(state.get("next_cost")) is not int or not 0 <= state["next_cost"] <= count:
                raise ValueError("ORIGINAL_DISCOVERY_CHECKPOINT_REQUIRED")
        elif count:
            raise ValueError("NONEMPTY_DISCOVERY_ACCOUNT_CHECKPOINT_MISSING")
        _write(checkpoint_path, account.seal_checkpoint({"binding_sha256": digest(binding), "next_cost": count}))
        target = len(protocol["finance"]["costs"]) if max_new_costs is None else min(len(protocol["finance"]["costs"]), count + max_new_costs)
        for index in range(count, target):
            request = _expected_request(protocol["finance"]["costs"][index], binding)
            receipt = account.spend(request["id"], request["kind"], request["amount"], request["day"],
                                    request["work"], request["expected_net"], allow_seed=True)
            if receipt is None:
                raise ValueError("DISCOVERY_COST_NOT_FUNDED_NO_IMPUTED_SUCCESS")
            _write(checkpoint_path, account.seal_checkpoint({"binding_sha256": digest(binding), "next_cost": index + 1}))
        record = account.export()
        native_audit = account.audit()
        report = _report(record, protocol, binding, contract, native_audit)
        evidence = {"schema": SCHEMA, "frozen": frozen, "manifest": manifest, "native_export": record, "report": report,
                    "privacy": "Key-free public export; native signing authority and SQLite recovery state are excluded."}
        _write(output / "PUBLIC_EVIDENCE.json", evidence)
        _write(output / "REPORT.json", report)
    return report


def audit_public(root, evidence):
    root = Path(root).absolute()
    if not isinstance(evidence, dict) or set(evidence) != {"schema", "frozen", "manifest", "native_export", "report", "privacy"} or evidence["schema"] != SCHEMA:
        raise ValueError("EXACT_PUBLIC_DISCOVERY_EVIDENCE_REQUIRED")
    frozen, manifest = evidence["frozen"], evidence["manifest"]
    protocol, binding, contract = frozen["protocol"], frozen["binding"], frozen["contract"]
    validate_protocol(protocol)
    if sorted(binding["source_hashes"]) != required_paths(protocol, binding["protocol_path"]) or binding != _binding(protocol, binding["source_hashes"], binding["protocol_path"]) or digest(manifest) != frozen["manifest_sha256"]:
        raise ValueError("PUBLIC_DISCOVERY_SOURCE_OR_MANIFEST_CHANGED")
    if _read(_safe(root, binding["protocol_path"])) != protocol or _source_hashes(root, binding["source_hashes"]) != binding["source_hashes"]:
        raise ValueError("PUBLIC_DISCOVERY_SOURCE_CHANGED")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != binding["source_hashes"][MODULE]:
        raise ValueError("EXECUTING_DISCOVERY_FINANCE_SOURCE_CHANGED")
    with tempfile.TemporaryDirectory(prefix="super-alpha-public-audit-") as temporary:
        source = Path(temporary) / "source"
        _copy_source(root, source, binding["source_hashes"])
        reconstructed = prepare_services(source, "runtime_fixtures")
        for key in set(manifest) - {"resource_receipt"}:
            if reconstructed.get(key) != manifest[key]:
                raise ValueError("BOOTSTRAP_FIXTURE_RECONSTRUCTION_CHANGED")
        checked = audit_journal(evidence["native_export"], root=source, manifest=manifest)
        expected = _report(evidence["native_export"], protocol, binding, contract, checked)
    if evidence["report"] != expected:
        raise ValueError("PUBLIC_DISCOVERY_REPORT_CHANGED")
    return {"schema": SCHEMA, "accepted": True, "scope": "SOURCE_BOUND_PUBLIC_NATIVE_COST_REPLAY_NO_ACCOUNT_OPENED",
            "binding_sha256": digest(binding), "native_export_sha256": digest(evidence["native_export"]),
            "costs_committed": expected["costs_committed"], "complete": expected["complete"],
            "trailing_365_day_profit_microUSD": expected["trailing_profit"]["trailing_365_day_profit_microUSD"],
            "actual_model_host_billing_microUSD": None}


def audit(root, output):
    return audit_public(root, _read(Path(output) / "PUBLIC_EVIDENCE.json"))


def main():
    parser = argparse.ArgumentParser(description="Source-bound cost-only native discovery account; no sales.")
    parser.add_argument("command", choices=("run", "audit", "audit-public"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--protocol", default=PREFIX + "PROTOCOL.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--max-new-costs", type=int)
    args = parser.parse_args()
    if args.command == "run":
        if args.output is None:
            parser.error("run requires --output")
        result = run(args.root, args.protocol, args.output, max_new_costs=args.max_new_costs)
    elif args.command == "audit":
        if args.output is None:
            parser.error("audit requires --output")
        result = audit(args.root, args.output)
    else:
        if args.evidence is None:
            parser.error("audit-public requires --evidence")
        result = audit_public(args.root, _read(args.evidence))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
