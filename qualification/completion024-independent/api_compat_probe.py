"""Static, never-importing P0 source API collision map for pinned public Git trees."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

FILES = (
    "adaptive_enterprise/account.py",
    "commercial/ledger.py",
    "commercial/native_engine.py",
    "connected_enterprise/engine.py",
    "connected_enterprise/finance.py",
    "connected_enterprise/verify.py",
    "vendor/alpha_claim/protected_exchange_prospective_v1.py",
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    a = node.args
    pos = [x.arg for x in a.posonlyargs + a.args]
    default_at = len(pos) - len(a.defaults)
    return {
        "signature": ast.unparse(a),
        "positional_only": [x.arg for x in a.posonlyargs],
        "positional_or_keyword": [x.arg for x in a.args],
        "keyword_only": [x.arg for x in a.kwonlyargs],
        "required": [x for i, x in enumerate(pos) if i < default_at]
        + [x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is None],
        "var_positional": a.vararg.arg if a.vararg else None,
        "var_keyword": a.kwarg.arg if a.kwarg else None,
        "asynchronous": isinstance(node, ast.AsyncFunctionDef),
    }


def _symbols(tree: ast.Module) -> dict:
    result = {}
    def add(n, key):
        if key in result:
            raise ValueError("DUPLICATE_DECLARATION:" + key)
        result[key] = {"call": _signature(n), "body_sha256": sha256(ast.dump(n, include_attributes=False).encode())}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, node.name)
        elif isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(inner, node.name + "." + inner.name)
    return result


def inspect(main_root: Path, owner_root: Path) -> dict:
    rows = []
    for path in FILES:
        main_path, owner_path = main_root / path, owner_root / path
        if main_path.is_symlink() or owner_path.is_symlink() or not main_path.is_file() or not owner_path.is_file():
            raise ValueError("MISSING_OR_SYMLINK_SOURCE:" + path)
        main_bytes, owner_bytes = main_path.read_bytes(), owner_path.read_bytes()
        main = _symbols(ast.parse(main_bytes, filename=path))
        owner = _symbols(ast.parse(owner_bytes, filename=path))
        if sha256(main_bytes) == sha256(owner_bytes):
            raise ValueError("EXPECTED_CONFLICT_NO_LONGER_PRESENT:" + path)
        main_only, owner_only = sorted(set(main) - set(owner)), sorted(set(owner) - set(main))
        changed = []
        for name in sorted(set(main) & set(owner)):
            m, o = main[name], owner[name]
            if m["body_sha256"] == o["body_sha256"]:
                continue
            mc, oc = m["call"], o["call"]
            main_kw = set(mc["positional_or_keyword"] + mc["keyword_only"])
            owner_kw = set(oc["positional_or_keyword"] + oc["keyword_only"])
            missing_names = sorted(main_kw - owner_kw) if not oc["var_keyword"] else []
            owner_required = set(oc["required"]) - set(mc["required"])
            changed.append({
                "symbol": name,
                "main_signature": mc["signature"],
                "owner_signature": oc["signature"],
                "signature_changed": mc != oc,
                "owner_missing_main_named_arguments": missing_names,
                "owner_additional_required_arguments": sorted(owner_required),
                "body_changed": True,
            })
        rows.append({"path": path, "main_sha256": sha256(main_bytes), "owner_sha256": sha256(owner_bytes),
                     "main_only_symbols": main_only, "owner_only_symbols": owner_only,
                     "changed_shared_callables": changed, "shared_changed_count": len(changed)})
    index = {r["path"]: r for r in rows}
    ledger = index["commercial/ledger.py"]
    engine = index["connected_enterprise/engine.py"]
    finance = index["connected_enterprise/finance.py"]
    # These were identified in the frozen development protocol, *not* a blind confirmation.
    assert "_NativePrefixReplay.__init__" in ledger["main_only_symbols"]
    assert "fresh_account_config" in engine["main_only_symbols"]
    assert "JournalAccount._audit_incremental" in finance["main_only_symbols"]
    assert "JournalAccount._prefix_identity" in finance["main_only_symbols"]
    key = {(r["path"], c["symbol"]): c for r in rows for c in r["changed_shared_callables"]}
    assert "_expected_before" in key[("commercial/ledger.py", "TapeExchange.execute")]["owner_missing_main_named_arguments"]
    assert "manifest" in key[("connected_enterprise/finance.py", "source_identity")]["owner_missing_main_named_arguments"]
    return {
        "schema": "agi-alpha/p0-seven-path-api-collision-map/v1",
        "scope": "READ_ONLY_AST_DEVELOPMENT_DIAGNOSTIC_NOT_SEMANTIC_QUALIFICATION",
        "main_and_owner_source_conflicts": rows,
        "file_count": len(rows),
        "main_only_symbol_count": sum(len(r["main_only_symbols"]) for r in rows),
        "owner_only_symbol_count": sum(len(r["owner_only_symbols"]) for r in rows),
        "changed_shared_symbol_count": sum(r["shared_changed_count"] for r in rows),
        "safe_integration": False,
        "original_account_migrated": False,
        "qualified_release": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main-root", type=Path, required=True)
    p.add_argument("--owner-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    report = inspect(a.main_root, a.owner_root)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "main_and_owner_source_conflicts"}, sort_keys=True))
    for row in report["main_and_owner_source_conflicts"]:
        print(row["path"], "main-only", len(row["main_only_symbols"]), "owner-only", len(row["owner_only_symbols"]), "changed", row["shared_changed_count"])


if __name__ == "__main__":
    main()
