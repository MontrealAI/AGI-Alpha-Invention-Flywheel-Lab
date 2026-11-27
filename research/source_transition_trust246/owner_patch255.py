"""P0-255: pinned bootstrap for a codec-less 9fac historical root.
Research proposal only; the legacy closure, account, key and signer are untouched.
"""
import ast
import hashlib
import json

from owner_patch253 import git_blob_id, patch_historical_owner

CODEC_BLOB = "2397091ef8e1960ad13950693d5b3cd04e2ff7c5"
MANIFEST_BLOB = "d09a1a739b4432ee971579e40b398e3b322d0cac"
LEGACY = "9facd934d9ae763691e8a51052a67793cac5b48e"
CODEC = "connected_enterprise/transition_evidence.py"


def legacy_python_inventory(manifest):
    files = json.loads(manifest)["versions"][LEGACY]["files"]
    return {name: sha for name, sha in files.items()
            if name.endswith(".py") and not set(name.split("/")) &
            {"__pycache__", ".git", ".venv", "historical-source-versions"}}


def patch_legacy_owner(raw, codec, manifest):
    if git_blob_id(codec) != CODEC_BLOB:
        raise ValueError("OWNER_BOOTSTRAP_CODEC_CHANGED")
    if git_blob_id(manifest) != MANIFEST_BLOB:
        raise ValueError("OWNER_BOOTSTRAP_MANIFEST_CHANGED")
    inventory = legacy_python_inventory(manifest)
    if not inventory or CODEC in inventory:
        raise ValueError("EXACT_CODECLESS_LEGACY_REQUIRED")
    code = codec.decode("utf-8")
    ast.parse(code)
    # Static function body, isolated namespace. No dynamic exec/import of
    # successor code and no modification of the historical source inventory.
    prefix = ("def _owner_legacy_codec():\n" +
              "".join("    " + line + "\n" for line in code.splitlines()) +
              "    return externalize, preflight_storage, persist_evidence\n")
    ast.parse(prefix)
    helper = (
        "def _owner_codec_mode(files):\n"
        "    name = " + repr(CODEC) + "\n"
        "    if name in files:\n"
        "        if files[name] != " + repr(hashlib.sha256(codec).hexdigest()) + ":\n"
        "            raise ValueError('OWNER_HISTORICAL_CODEC_CHANGED')\n"
        "        return False\n"
        "    if files != " + repr(inventory) + ":\n"
        "        raise ValueError('OWNER_CODECLESS_LEGACY_INVENTORY_CHANGED')\n"
        "    return True\n\n\n"
    )
    source = patch_historical_owner(raw).decode("utf-8")

    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError("OWNER_BOOTSTRAP_ANCHOR_NOT_UNIQUE")
        source = source.replace(old, new, 1)

    replace("def authorize_upgrade(", helper + "def authorize_upgrade(")
    replace("    payload = {'root': str(historical_root),",
            "    bootstrap = _owner_codec_mode(files) if evidence_dir is not None else False\n"
            "    payload = {'bootstrap_legacy_codec': bootstrap, 'root': str(historical_root),")
    replace("if p['evidence_dir'] and importlib.util.find_spec('connected_enterprise.transition_evidence'):\n"
            " from connected_enterprise.transition_evidence import evidence_directory\n"
            " scope=evidence_directory(p['evidence_dir'])",
            "if p['evidence_dir']:\n"
            " if p['bootstrap_legacy_codec']:\n"
            "  externalize,preflight_storage,persist_evidence=_owner_legacy_codec()\n"
            " else:\n"
            "  from connected_enterprise.transition_evidence import evidence_directory,externalize,preflight_storage,persist_evidence\n"
            "  scope=evidence_directory(p['evidence_dir'])")
    replace("  from connected_enterprise.transition_evidence import externalize, preflight_storage, persist_evidence\n", "")
    replace("    env = {**os.environ, 'PYTHONPATH': str(historical_root),",
            "    if bootstrap:\n        code = " + repr(prefix) + " + code\n"
            "    env = {**os.environ, 'PYTHONPATH': str(historical_root),")
    ast.parse(source)
    if "codec_source" in source or "exec(p[" in source:
        raise ValueError("SUCCESSOR_EXECUTION_REMAINS_IN_SIGNER")
    return source.encode("utf-8")


def static_gates(raw, codec, manifest, patched):
    """Key-free, execute only the generated pure inventory selector."""
    node = next(n for n in ast.parse(patched).body
                if isinstance(n, ast.FunctionDef) and n.name == "_owner_codec_mode")
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<owner-selector>", "exec"), scope)
    mode = scope["_owner_codec_mode"]
    legacy = legacy_python_inventory(manifest)
    good = {**legacy, CODEC: hashlib.sha256(codec).hexdigest()}
    results = []

    def negative(name, thunk, expected):
        try:
            thunk()
        except ValueError as exc:
            accepted = str(exc) == expected
        else:
            accepted = False
        results.append({"name": name, "accepted": accepted})

    negative("changed_bootstrap_codec", lambda: patch_legacy_owner(raw, codec+b"\n", manifest),
             "OWNER_BOOTSTRAP_CODEC_CHANGED")
    negative("changed_bootstrap_manifest", lambda: patch_legacy_owner(raw, codec, manifest+b"\n"),
             "OWNER_BOOTSTRAP_MANIFEST_CHANGED")
    negative("unknown_codecless_inventory", lambda: mode({**legacy, "unknown.py": "0"*64}),
             "OWNER_CODECLESS_LEGACY_INVENTORY_CHANGED")
    negative("changed_historical_codec", lambda: mode({**legacy, CODEC: "0"*64}),
             "OWNER_HISTORICAL_CODEC_CHANGED")
    results.extend([{"name":"exact_legacy_selects_bootstrap", "accepted": mode(legacy) is True},
                    {"name":"historical_codec_selects_import", "accepted": mode(good) is False}])
    return results
