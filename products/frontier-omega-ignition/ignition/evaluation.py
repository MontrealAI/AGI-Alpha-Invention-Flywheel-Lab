"""Separately implemented conventional routes and checks for frozen contracts."""

import base64
import hashlib
import itertools
import time
from pathlib import Path

from .construction import ConstructionError, canonical, check_contract, execute, fingerprint


class ReferenceRefusal(ValueError):
    pass


def _convert(value, kind):
    if kind == "text":
        if type(value) is str:
            return value
    elif kind == "integer":
        if type(value) in (str, int) and len(str(value)) <= 17:
            try:
                parsed = int(value)
            except ValueError:
                parsed = None
            if parsed is not None and str(parsed) == str(value) and abs(parsed) < 2**53:
                return parsed
    elif kind == "boolean":
        if type(value) is bool:
            return value
        if type(value) is str and value in ["false", "true"]:
            return value == "true"
    raise ReferenceRefusal("invalid_value")


def _extract(row, op):
    if "sources" in op:
        values = [row[name] for name in op["sources"]]
        if any(type(v) is not str for v in values):
            raise ReferenceRefusal("invalid_value")
        return op["separator"].join(values)
    value = row[op["source"]]
    if "split" in op:
        if type(value) is not str:
            raise ReferenceRefusal("invalid_value")
        try:
            return value.split(op["split"]["separator"])[op["split"]["index"]]
        except IndexError:
            raise ReferenceRefusal("invalid_value") from None
    return value


def _reference_migrate(definition, payload):
    if type(payload) is not dict or payload.keys() != {"rows"}:
        raise ReferenceRefusal("invalid_input")
    rows = payload["rows"]
    if type(rows) is not list or len(rows) > 2048:
        raise ReferenceRefusal("invalid_input")
    columns = definition["columns"]
    fields = set(definition.get("input_fields", ()))
    for column in columns:
        fields.update(column["sources"] if "sources" in column else [column["source"]])
    output = []
    emitted = 0
    for row in rows:
        if type(row) is not dict or not fields.issubset(row):
            raise ReferenceRefusal("missing_field")
        if definition["extra_fields"] == "reject" and fields != row.keys():
            raise ReferenceRefusal("extra_field")
        mapped = {}
        for op in columns:
            value = _convert(_extract(row, op), op["type"])
            emitted += len(value) if type(value) is str else 1
            if emitted > 2 * 1024 * 1024:
                raise ReferenceRefusal("budget")
            mapped[op["target"]] = value
        output.append(mapped)
    result = {"rows": output}
    if len(canonical(result)) > 2 * 1024 * 1024:
        raise ReferenceRefusal("budget")
    return result


def _reference_audit(definition, payload):
    if type(payload) is not dict or payload.keys() != {"files"}:
        raise ReferenceRefusal("invalid_input")
    actual = payload["files"]
    if type(actual) is not dict or len(actual) > 256:
        raise ReferenceRefusal("invalid_input")
    result = {"matched": [], "changed": [], "missing": [], "unexpected": []}
    manifest = definition["manifest"]
    allowed = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_. -")
    for name in sorted(manifest.keys() | actual.keys()):
        if len(name) > 240 or any(not p or p in {".", ".."} or set(p) - allowed for p in name.split("/")):
            raise ReferenceRefusal("invalid_path")
        if name not in actual:
            result["missing"].append(name)
            continue
        try:
            if type(actual[name]) is not str:
                raise ValueError
            data = base64.b64decode(actual[name], validate=True)
            if base64.b64encode(data).decode() != actual[name]:
                raise ValueError
        except ValueError:
            raise ReferenceRefusal("invalid_value") from None
        digest = hashlib.new("sha256", data).hexdigest()
        state = "unexpected" if name not in manifest else ("matched" if manifest[name] == digest else "changed")
        result[state].append(name)
    return {"ok": not any(result[k] for k in ("changed", "missing", "unexpected")), **result}


def _operations(fields, developments):
    """Finite conventional synthesis, increasingly expressive expressions first by cost."""
    yield [{"source": field} for field in fields]
    components = []
    for field in fields:
        values = [row[field] for row, _ in developments]
        if not all(type(v) is str for v in values):
            continue
        for sep in (" ", "-", "_", "/", ".", ",", ":", "|"):
            count = min(v.count(sep) for v in values)
            if not count:
                continue
            # Positive and negative selectors are genuinely different for arbitrary-length input.
            for idx in range(min(count + 1, 8)):
                components.append({"source": field, "split": {"separator": sep, "index": idx}})
    yield components
    yield [{"sources": [a, b], "separator": sep} for a, b in itertools.permutations(fields, 2)
           for sep in (" ", "-", "_", "/", ".", ",", ":", "|")]


def _learn_reference(definition):
    pairs = [(row, out) for demo in definition["demonstrations"]
             for row, out in zip(demo["input"]["rows"], demo["expected"]["rows"])]
    fields = definition["input_fields"]
    inferred = []
    for target in definition["targets"]:
        target_name, typ = target["name"], target["type"]
        for family in _operations(fields, pairs):
            matches = []
            for expression in family:
                try:
                    if all(canonical(_convert(_extract(row, expression), typ)) == canonical(out[target_name])
                           for row, out in pairs):
                        matches.append(expression)
                except ReferenceRefusal:
                    continue
                if len(matches) > 1:
                    return None, "ambiguous minimum-cost development hypotheses"
            if matches:
                inferred.append({"target": target_name, "type": typ, **matches[0]})
                break
        else:
            return None, "no supported conventional expression fits development data"
    return {"columns": inferred, "extra_fields": definition["extra_fields"], "input_fields": fields}, None


def _observe(call, *args):
    try:
        return {"output": call(*args)}
    except ConstructionError as err:
        return {"error": err.code}
    except ReferenceRefusal as err:
        return {"error": str(err)}


def _probes(spec):
    """Predeclared controls derived solely from the frozen specification."""
    if spec["kind"] == "manifest_audit":
        return [("absent package", {"files": {}}), ("unlisted member", {"files": {"IGNITION.control": ""}}),
                ("invalid logical name", {"files": {"../IGNITION.control": ""}}),
                ("malformed bytes", {"files": {"IGNITION.control": "*"}})]
    probes = [("empty batch", {"rows": []}), ("missing columns", {"rows": [{}]}),
              ("wrong envelope", {"rows": [], "extra": True})]
    for case in spec["cases"]:
        rows = case["input"].get("rows")
        if "expected" in case and type(rows) is list and rows and type(rows[0]) is dict:
            row = rows[0]
            extra_key = "IGNITION_unknown_column"
            while extra_key in row:
                extra_key += "_"
            probes.append(("extra column policy", {"rows": [{**row, extra_key: 1}]}))
            break
    return probes


def _witness(observation):
    if observation is None:
        return None
    raw = canonical(observation)
    if len(raw) <= 2048:
        return observation
    return {"observation_sha256": hashlib.sha256(raw).hexdigest(), "canonical_bytes": len(raw),
            "reproduce": "Run the artifact on the named frozen input."}


def check_receipt_integrity(receipt):
    if type(receipt) is not dict or receipt.get("receipt_sha256") != fingerprint(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"}):
        raise ConstructionError("stale_receipt", "archived receipt bytes changed")


def evaluator_identity():
    here = Path(__file__).resolve().parent
    return {filename: hashlib.sha256((here / filename).read_bytes()).hexdigest()
            for filename in ("construction.py", "evaluation.py")}


def _declared_migration(program):
    """Target order is immaterial. The fields, conversions and input policy are contractual."""
    fields = set(program.get("input_fields", ()))
    operations = {}
    for column in program["columns"]:
        fields.update(column["sources"] if "sources" in column else [column["source"]])
        operations[column["target"]] = {k: v for k, v in column.items() if k != "target"}
    return {"required": sorted(fields), "extra_fields": program["extra_fields"], "operations": operations}


def evaluate(contract, artifact):
    spec = check_contract(contract)
    if type(artifact) is not dict or artifact.get("contract_sha256") != contract["sha256"] or artifact.get("kind") != spec["kind"]:
        raise ConstructionError("stale_contract", "artifact and frozen mission do not match")
    start = time.perf_counter_ns()
    definition = spec["definition"]
    reference_obstruction = None
    reference_config = definition
    learned = "demonstrations" in definition
    if learned:
        reference_config, reference_obstruction = _learn_reference(definition)
    reference = _reference_audit if spec["kind"] == "manifest_audit" else _reference_migrate
    cases = []
    candidate_elapsed = 0
    reference_elapsed = 0
    checks = [("confirmation", c["name"], c["input"],
               {"output": c["expected"]} if "expected" in c else {"error": c["error"]}) for c in spec["cases"]]
    for name, payload in _probes(spec):
        checks.append(("derived negative/control", name, payload, None))
    if learned:
        for i, demo in enumerate(definition["demonstrations"], 1):
            checks.append(("development", f"development {i}", demo["input"], {"output": demo["expected"]}))
    for group, name, payload, expected in checks:
        t0 = time.perf_counter_ns()
        reference_result = _observe(reference, reference_config, payload) if reference_config else None
        t1 = time.perf_counter_ns()
        candidate = _observe(execute, artifact, payload)
        t2 = time.perf_counter_ns()
        candidate_elapsed += t2 - t1
        reference_elapsed += t1 - t0
        if expected is None:
            # Generic controls have independent expectations even when conventional synthesis abstains.
            if name == "empty batch":
                expected = {"output": {"rows": []}}
            elif name == "missing columns":
                expected = {"error": "missing_field"}
            elif name == "wrong envelope":
                expected = {"error": "invalid_input"}
            elif name == "extra column policy" and definition.get("extra_fields") == "reject":
                expected = {"error": "extra_field"}
            elif name == "extra column policy" and learned:
                first = next(c for c in spec["cases"] if c.get("expected", {}).get("rows"))
                expected = {"output": {"rows": first["expected"]["rows"][:1]}}
            else:
                expected = reference_result
        if expected is None:
            raise ConstructionError("invalid_contract", "control has no independent oracle")
        cases.append({"name": name, "group": group, "input_sha256": fingerprint(payload),
                      "expected": _witness(expected), "candidate": _witness(candidate), "reference": _witness(reference_result),
                      "candidate_pass": canonical(candidate) == canonical(expected),
                      "reference_pass": canonical(reference_result) == canonical(expected) if reference_result is not None else None})
    candidate_pass = all(c["candidate_pass"] for c in cases)
    reference_pass = reference_config is not None and all(c["reference_pass"] for c in cases)
    # A declared full specification provides a second oracle. Contradictory operator labels
    # quarantine the result. In example-based induction each independently inferred mapping is a competitor.
    oracles_agree = learned or reference_pass
    program = artifact.get("program")
    if spec["kind"] == "manifest_audit":
        contract_conforms = program == definition  # Pin every trusted hash, including unseen files.
    elif learned:
        contract_conforms = type(program) is dict and program.get("extra_fields") == definition["extra_fields"]
    else:
        # Frozen source-to-target mappings are an explicit requirement even when two
        # source columns happen to have identical values on every confirmation row.
        try:
            contract_conforms = _declared_migration(program) == _declared_migration(definition)
        except (TypeError, KeyError, AttributeError):
            contract_conforms = False
    candidate_pass &= contract_conforms
    if reference_obstruction or not oracles_agree:
        comparison = "incomparable"
    elif candidate_pass == reference_pass:
        comparison = "tie"
    else:
        comparison = "candidate_wins" if candidate_pass else "baseline_wins"
    result = {"format": "ignition-local-evaluation/1", "status": "pass" if candidate_pass and oracles_agree else "fail",
            "contract_sha256": contract["sha256"], "artifact_sha256": artifact.get("sha256"),
            "implementation_sha256": evaluator_identity(), "cases": cases,
            "declared_program_conforms": contract_conforms,
            "comparison": {"name": ("enumerative example-based migration" if learned else
                                    "direct stdlib manifest diff" if spec["kind"] == "manifest_audit" else
                                    "direct conventional schema migration"),
                           "outcome": comparison, "reference_pass": reference_pass,
                           "reference_obstruction": reference_obstruction, "oracles_agree": oracles_agree,
                           "criterion": "conformance to declared operations and complete correctness on the frozen workload; latency is telemetry only"},
            "scope": "Local software acceptance on frozen confirmations and controls. Custody, demand, economic advantage and frontier crossing are unestablished.",
            "telemetry_ns": {"candidate": candidate_elapsed, "reference": reference_elapsed,
                             "local_evaluation": time.perf_counter_ns() - start}}
    return {**result, "receipt_sha256": fingerprint(result)}
