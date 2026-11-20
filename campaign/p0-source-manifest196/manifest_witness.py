#!/usr/bin/env python3
"""Source-only P0-196 witness: manifest-specific source bindings, never accounts."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

TARGET = "f0987aa48d5c9136b28540f54eabf5367e63bbe6"
OWNER = "ced6c1cb004887dcdafaea59a2976020be649f8e"
PINNED = {
    (TARGET, "connected_enterprise/finance.py"): "02c81396ad90dbd31efbfeeb1a973fbbdb428bb4",
    (OWNER, "connected_enterprise/finance.py"): "c01e5cd97fb32b3e5fcd5cea190424d8f4f5d5ec",
    (OWNER, "connected_enterprise/upgrades.py"): "9866d004c412fc05c9f6292cf898307f177359df",
}
SCHEMAS = {
    "default": None,
    "production": {"schema": "production060/native-services/v1"},
    "inventory": {"schema": "inventory061/native-services/v1"},
}
CHANGES = {
    "common": "commercial/ledger.py",
    "production_only": "production060/service.py",
    "inventory_only": "inventory061/service.py",
}


def git_bytes(commit, path):
    """Read exact immutable public Git object; never import any native code."""
    ref = commit + ":" + path
    sha = subprocess.run(["git", "rev-parse", "--verify", ref],
                         capture_output=True, text=True, check=True).stdout.strip()
    if sha != PINNED[(commit, path)]:
        raise ValueError("PINNED_BLOB_CHANGED:" + ref)
    return subprocess.run(["git", "show", ref],
                          capture_output=True, check=True).stdout


def function(tree, name):
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(funcs) != 1:
        raise ValueError("SOURCE_FUNCTION_CHANGED:" + name)
    return funcs[0]


def names_from_target(source):
    tree = ast.parse(source, filename="target-finance.py")
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                    "SOURCE_PATHS", "PRODUCTION_SOURCE_PATHS", "INVENTORY_SOURCE_PATHS"}:
                value = ast.literal_eval(node.value)
                if not isinstance(value, tuple) or not value or len(set(value)) != len(value):
                    raise ValueError("INVALID_SOURCE_PATHS:" + target.id)
                if any(not isinstance(p, str) or p.startswith("/") or ".." in Path(p).parts for p in value):
                    raise ValueError("NONCANONICAL_SOURCE_PATHS")
                constants[target.id] = value
    if len(constants) != 3:
        raise ValueError("MISSING_CURRENT_SOURCE_PATHS")
    selector = function(tree, "source_paths_for_manifest")
    source_identity = function(tree, "source_identity")
    # Verify that the actual identity algorithm calls the selector with manifest.
    calls = [c for c in ast.walk(source_identity) if isinstance(c, ast.Call)
             and isinstance(c.func, ast.Name) and c.func.id == "source_paths_for_manifest"]
    if len(calls) != 1 or len(calls[0].args) != 1 or not isinstance(calls[0].args[0], ast.Name) or calls[0].args[0].id != "manifest":
        raise ValueError("TARGET_SOURCE_IDENTITY_SELECTOR_CHANGED")
    # Only evaluate the pinned, isolated selector AST with literal data. Do not
    # execute the full module or import JournalAccount/native finance/account.
    scope = {"__builtins__": {"isinstance": isinstance, "dict": dict, "tuple": tuple},
             **constants}
    exec(compile(ast.Module(body=[selector], type_ignores=[]),
                 "pinned-source-selector", "exec"), scope, scope)
    select = scope["source_paths_for_manifest"]
    paths = {}
    for name, manifest in SCHEMAS.items():
        values = tuple(select(manifest))
        if not values or len(set(values)) != len(values):
            raise ValueError("SELECTED_SOURCE_PATHS_INVALID:" + name)
        paths[name] = values
    return paths


def owner_target_call(owner_upgrade, owner_finance):
    upgrade = ast.parse(owner_upgrade, filename="owner-upgrades.py")
    finance = ast.parse(owner_finance, filename="owner-finance.py")
    target_method = function(upgrade, "authorize_upgrade")
    target_calls = [call for call in ast.walk(target_method)
                    if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "source_identity"
                    and len(call.args) == 1 and not call.keywords
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "target_root"]
    old_identity = function(finance, "source_identity")
    return {
        "historical_target_no_manifest_calls": len(target_calls),
        "historical_source_identity_positional_parameters":
            [a.arg for a in old_identity.args.args],
    }


def fingerprint(paths, mutate=None):
    """Synthetic file-hash map only; not a signature or real source identifier."""
    mapping = {p: hashlib.sha256(("fixture-original:" + p).encode()).hexdigest()
               for p in paths}
    if mutate is not None:
        if mutate not in mapping:
            raise ValueError("SYNTHETIC_CHANGE_PATH_NOT_SELECTED:" + mutate)
        mapping[mutate] = hashlib.sha256(("fixture-modified:" + mutate).encode()).hexdigest()
    return hashlib.sha256(json.dumps(mapping, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def report():
    sources = {key: git_bytes(*key) for key in PINNED}
    paths = names_from_target(sources[(TARGET, "connected_enterprise/finance.py")])
    owner = owner_target_call(sources[(OWNER, "connected_enterprise/upgrades.py")],
                              sources[(OWNER, "connected_enterprise/finance.py")])
    requirements = {
        "default_omits_production": CHANGES["production_only"] not in paths["default"],
        "production_includes_production": CHANGES["production_only"] in paths["production"],
        "default_omits_inventory": CHANGES["inventory_only"] not in paths["default"],
        "inventory_includes_inventory": CHANGES["inventory_only"] in paths["inventory"],
        "common_in_all": all(CHANGES["common"] in v for v in paths.values()),
        "historical_upgrade_uses_no_manifest": owner["historical_target_no_manifest_calls"] == 2,
        "historical_identity_accepts_root_only": owner["historical_source_identity_positional_parameters"] == ["root"],
    }
    # The source is inspected, not modified. Compute isolated fingerprints only.
    hashes = {k: {"baseline": fingerprint(v)} for k, v in paths.items()}
    for name, value in CHANGES.items():
        for variant, selected in paths.items():
            if value in selected:
                hashes[variant][name] = fingerprint(selected, value)
            else:
                hashes[variant][name] = hashes[variant]["baseline"]
    requirements.update({
        "common_changes_every_fingerprint":
            all(h["common"] != h["baseline"] for h in hashes.values()),
        "production_changes_production_not_default":
            hashes["production"]["production_only"] != hashes["production"]["baseline"]
            and hashes["default"]["production_only"] == hashes["default"]["baseline"],
        "inventory_changes_inventory_not_default":
            hashes["inventory"]["inventory_only"] != hashes["inventory"]["baseline"]
            and hashes["default"]["inventory_only"] == hashes["default"]["baseline"],
    })
    accepted = all(requirements.values())
    return {
        "schema": "agi-alpha/p0-manifest-negative-witness/v1",
        "source": {"target_commit": TARGET, "owner_historical_commit": OWNER,
                   "public_blob_sha1": [{"commit": a, "path": b, "sha1": sha}
                                        for (a, b), sha in PINNED.items()]},
        "fixed_service_schemas": {k: v for k, v in SCHEMAS.items()},
        "path_counts": {name: len(value) for name, value in paths.items()},
        "path_membership": {name: sorted(set(value) & set(CHANGES.values()))
                            for name, value in paths.items()},
        "owner_call_witness": owner,
        "checks": requirements,
        "fingerprints": hashes,
        "all_frozen_negative_checks_met": accepted,
        "verdict": "SYNTHETIC_MANIFEST_UNDERBINDING_WITNESS_ONLY" if accepted
                   else "FROZEN_NEGATIVE_WITNESS_NOT_REPRODUCED",
        "native_account_opened": False,
        "live_finance_or_migration_qualified": False,
        "observed_commerce": False,
        "actual_profit_usd": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="New create-only result path")
    args = parser.parse_args()
    result = report()
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as f:
            f.write(raw)
    else:
        print(raw.decode(), end="")
    if not result["all_frozen_negative_checks_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
