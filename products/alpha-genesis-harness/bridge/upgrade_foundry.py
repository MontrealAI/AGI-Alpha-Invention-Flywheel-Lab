# SPDX-License-Identifier: Apache-2.0
"""Model-written interpreter upgrades, with external qualification in a native sandbox.

Initial adapter: arbitrary Python changes confined to bridge/instruments.py.
Activation selects an isolated research candidate, never overwrites installed code.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import random
import secrets
import stat
import subprocess
import sys
import threading
import time

from . import adapters as _adapters, workflows as _workflows, codex as _codex, codex_permissions as _permissions
from . import workflow_schemas as _workflow_schemas, output_schema as _output_schema
from .adapters import BridgeError, strict_json
from .codex import CodexService
from .codex_permissions import PROFILE, permission_overrides, verify_profile_protocol, verify_runtime_sandbox
from .workflows import _atomic, _regular, digest, encoded, equivalent, require

PRODUCT = Path(__file__).resolve().parent.parent
OWN_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EDITABLE = "bridge/instruments.py"
MAX_FILES = 100
MAX_BYTES = 8 * 1024 * 1024
_ACTIVE_BY_ROOT = {}
_ACTIVE_LOCK = threading.RLock()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def _source_guard():
    require(hashlib.sha256(_regular(Path(__file__), 1024 * 1024)).hexdigest() == OWN_SHA,
            "Foundry evaluator source changed; restart before continuing.", "FOUNDRY_SOURCE_DRIFT")


def _authority_manifest(binary):
    _source_guard()
    sources = {"upgrade_foundry.py": OWN_SHA}
    for module in (_adapters, _workflows, _workflow_schemas, _output_schema, _codex, _permissions):
        path = Path(module.__file__)
        actual = hashlib.sha256(_regular(path, 1024 * 1024)).hexdigest()
        require(actual == module.LOADED_SOURCE_SHA256,
                "Loaded evaluator dependency differs from source bytes; restart before continuing.", "FOUNDRY_SOURCE_DRIFT")
        sources[path.name] = actual
    executable = None
    if binary and Path(binary).is_file():
        path = Path(binary).resolve()
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            require(path.stat().st_size <= 512 * 1024 * 1024, "Configured executable exceeds integrity-check envelope.", "FOUNDRY_BINARY")
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        executable = {"path": str(path), "sha256": hasher.hexdigest()}
    return {"sources": sources, "codex_executable": executable, "python": {"version": sys.version, "executable": str(Path(sys.executable).resolve())}}


def _snapshot(directory):
    """Read ordinary source assets only; no credentials, tests or customer data."""
    directory = Path(directory)
    files = {}
    for pattern in ("bridge/*.py", "app/*.js", "app/*.html", "app/*.css", "VERSION.json"):
        for path in sorted(directory.glob(pattern)):
            require(not any(p.is_symlink() for p in [path, *path.parents]), "Source snapshot refuses symbolic links.", "FOUNDRY_SOURCE")
            raw = CodexService._read_artifact(directory, path.relative_to(directory))
            require(raw is not None and len(raw) <= 1024 * 1024, "Snapshot entries must be bounded regular files with safe no-follow reads.", "FOUNDRY_SOURCE")
            files[path.relative_to(directory).as_posix()] = raw.decode("utf-8")
    require(EDITABLE in files and len(files) <= MAX_FILES and sum(len(v.encode()) for v in files.values()) <= MAX_BYTES,
            "Product source snapshot is unavailable or outside its transfer envelope.", "FOUNDRY_SOURCE")
    return files


def _write_snapshot(directory, files):
    for name, content in files.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic(path, content.encode())


def _manifest(files):
    return {k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()}


def _protocol(seed):
    """Freeze fresh instances before the model sees construction source.

    Direct scalar arithmetic is the competent conventional oracle. Fixed JSON
    equality expectations are declared independently of either interpreter.
    """
    rng = random.Random(seed)
    cases = []
    for i in range(48):
        x, gain, offset = (rng.randrange(-1000, 1001) for _ in range(3))
        spec = {"name": "Preregistered arithmetic " + str(i), "inputs": ["x", "gain", "offset"],
                "outputs": {"result": {"op": "add", "args": [{"op": "mul", "args": [{"field": "x"}, {"field": "gain"}]}, {"field": "offset"}]}}}
        cases.append({"id": "fresh-" + str(i), "instrument": spec, "inputs": {"x": x, "gain": gain, "offset": offset},
                      "max_operations": 10000, "expected": {"result": x * gain + offset},
                      "reference": {"formula": "x*gain+offset", "x": x, "gain": gain, "offset": offset}})
    for name, change in [("missing-input", "input"), ("wrong-type", "type"), ("unknown-operation", "op"), ("exhausted-budget", "budget")]:
        case = copy.deepcopy(cases[0]); case["id"] = name; case.pop("expected"); case["expect_error"] = True; case.pop("reference")
        if change == "input": case["inputs"].pop("x")
        if change == "type": case["inputs"]["x"] = "not-a-number"
        if change == "op": case["instrument"]["outputs"]["result"]["op"] = "unsupported_operation"
        if change == "budget": case["max_operations"] = 1
        cases.append(case)
    equality_cases = [
        ("list-bool-number", [True], [1], False),
        ("object-bool-number", {"value": False}, {"value": 0}, False),
        ("nested-bool-number", {"rows": [{"value": [True]}]}, {"rows": [{"value": [1.0]}]}, False),
        ("nested-number-bool", [[{"value": 0.0}]], [[{"value": False}]], False),
        ("nested-numeric", {"values": [1, -0.0, 2.5]}, {"values": [1.0, 0, 2.5]}, True),
        ("object-order", {"a": [1], "b": False}, {"b": False, "a": [1.0]}, True),
        ("list-order", [1, 2], [2, 1], False),
        ("list-length", [1], [1, 2], False),
        ("object-keys", {"a": None}, {"b": None}, False),
        ("container-type", [], {}, False),
        ("null-bool", None, False, False),
        ("unicode-exact", "\u00e9", "e\u0301", False),
    ]
    for name, left, right, expected in equality_cases:
        cases.append({"id": "equality-" + name,
                      "instrument": {"name": "Fixed JSON equality regression", "inputs": ["left", "right"],
                                     "outputs": {"result": {"op": "eq", "args": [{"field": "left"}, {"field": "right"}]}}},
                      "inputs": {"left": left, "right": right}, "max_operations": 10000,
                      "expected": {"result": expected}})
    return {"schema": "harness-interpreter-upgrade-protocol/v2", "seed": seed, "cases": cases,
            "acceptance": "Every fresh affine case matches the independent direct arithmetic oracle; fixed JSON equality cases match declared booleans; every declared malformed case is rejected.",
            "comparison": "Original HARNESS and candidate on all cases; competent direct scalar arithmetic on the matching affine subset; costs measured separately.",
            "limits": "Finite sampled affine and fixed JSON/interpreter regression scope; no proof of all expressions or general capability improvement."}


class _SeededCodex(CodexService):
    def __init__(self, original, root, files):
        config = {**original.config, "executable": original.binary}
        super().__init__(config, original.plan, root, original.process_factory, original.sandbox_validator, original.runtime_probe)
        self.seed_files = files

    def _directory(self, run_id):
        directory, runtime = super()._directory(run_id)
        _write_snapshot(directory, self.seed_files)
        return directory, runtime


# This is only a wire wrapper. Candidate Python is imported solely INSIDE the
# native sandbox. Expected answers and the authority to qualify stay in the host.
_CHILD = r'''import importlib.util,json,sys
from pathlib import Path
p=Path(sys.argv[1]); packet=json.loads(sys.argv[2])
spec=importlib.util.spec_from_file_location("isolated_candidate",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=[]
for c in packet:
 try:
  r=m.evaluate(c["instrument"],c["inputs"],c["max_operations"])
  out.append({"id":c["id"],"output":r["output"]})
 except Exception:
  out.append({"id":c["id"],"error":True})
print(json.dumps({"results":out},allow_nan=False,separators=(",",":")))
'''


class NativeEvaluator:
    """Credential-free official command/exec; fail closed when sandbox is absent."""
    def __init__(self, binary, *, process_factory=subprocess.Popen, profile_validator=verify_profile_protocol, runtime_probe=verify_runtime_sandbox):
        self.binary = binary
        self.process_factory, self.profile_validator, self.runtime_probe = process_factory, profile_validator, runtime_probe

    def run(self, directory, cases, *, cancel=None):
        require(self.binary and Path(self.binary).is_absolute() and Path(self.binary).is_file(), "Install a supported official Codex CLI for native sandbox evaluation.", "FOUNDRY_SANDBOX_BLOCKED")
        directory = Path(directory).resolve()
        cancel = cancel or threading.Event()
        self.profile_validator(self.binary)
        runtime = directory.parent / (".review-runtime-" + secrets.token_hex(8))
        runtime.mkdir(mode=0o700)
        command = [self.binary, "app-server", "--listen", "stdio://", "-c", 'shell_environment_policy.inherit="none"',
                   "-c", 'web_search="disabled"', "-c", 'model_provider="harness_no_inference"',
                   "-c", 'model_providers.harness_no_inference.name="No inference"',
                   "-c", 'model_providers.harness_no_inference.base_url="http://127.0.0.1:9/v1"',
                   "-c", 'model_providers.harness_no_inference.wire_api="responses"'] + permission_overrides(directory, False, self.binary)
        # The probe must pass before candidate code can run. It uses only a
        # synthetic sentinel, and fails if any network/private-file read succeeds.
        self.runtime_probe(command, directory, runtime, False)
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG") if key in os.environ}
        env.update({"HOME": str(runtime), "CODEX_HOME": str(runtime), "PYTHONDONTWRITEBYTECODE": "1"})
        process, messages = None, queue.Queue(maxsize=32)
        try:
            require(not cancel.is_set(), "Evaluation cancelled before dispatch.", "FOUNDRY_CANCELLED")
            process = self.process_factory(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          text=True, encoding="utf-8", bufsize=1, cwd=str(directory), env=env)
            def read():
                try:
                    for line in process.stdout:
                        if len(line.encode()) > 1024 * 1024: break
                        messages.put(strict_json(line), timeout=1)
                except (BridgeError, OSError, queue.Full, UnicodeError): pass
                finally:
                    try: messages.put(None, timeout=1)
                    except queue.Full: pass
            threading.Thread(target=read, daemon=True).start()
            def rpc(ident, method, params):
                process.stdin.write(json.dumps({"id": ident, "method": method, "params": params}) + "\n"); process.stdin.flush()
                deadline = time.monotonic() + 45  # Bounded local evaluation RPC, not a mission deadline.
                while time.monotonic() < deadline:
                    require(not cancel.is_set(), "Evaluation cancelled; no result qualified.", "FOUNDRY_CANCELLED")
                    try: row = messages.get(timeout=.2)
                    except queue.Empty: continue
                    require(isinstance(row, dict), "Sandbox protocol ended before completion.", "FOUNDRY_SANDBOX")
                    if row.get("id") == ident:
                        require(not row.get("error") and isinstance(row.get("result"), dict), "Sandbox rejected evaluation.", "FOUNDRY_SANDBOX")
                        return row["result"]
                    if "id" in row and row.get("method"):
                        process.stdin.write(json.dumps({"id": row["id"], "error": {"code": -32601, "message": "No additional permission granted."}}) + "\n"); process.stdin.flush()
                raise BridgeError("FOUNDRY_SANDBOX_TIMEOUT", "Bounded evaluation command did not finish; no qualification.")
            rpc(0, "initialize", {"clientInfo": {"name": "alpha_genesis_foundry", "version": "0.3.0"}, "capabilities": {"experimentalApi": True}})
            process.stdin.write('{"method":"initialized","params":{}}\n'); process.stdin.flush()
            profiles = rpc(1, "permissionProfile/list", {"cwd": str(directory)})
            require(any(row.get("id") == PROFILE and row.get("allowed") is True for row in profiles.get("data", [])), "Read-only evaluator profile was not authorized.", "FOUNDRY_SANDBOX")
            inputs = [{key: c[key] for key in ("id", "instrument", "inputs", "max_operations")} for c in cases]
            result = rpc(2, "command/exec", {"command": [sys.executable, "-I", "-S", "-B", "-c", _CHILD, str(directory / EDITABLE), json.dumps(inputs, separators=(",", ":"), allow_nan=False)],
                         "cwd": str(directory), "permissionProfile": PROFILE, "timeoutMs": 30000, "outputBytesCap": 1024 * 1024})
            require(result.get("exitCode") == 0, "Candidate process failed; no passing result accepted.", "FOUNDRY_CANDIDATE_FAILED")
            value = strict_json(result.get("stdout", ""))
            require(isinstance(value, dict) and set(value) == {"results"} and isinstance(value["results"], list), "Candidate returned invalid result envelope.", "FOUNDRY_CANDIDATE_FAILED")
            require(not cancel.is_set(), "Evaluation cancelled; late result discarded.", "FOUNDRY_CANCELLED")
            return value["results"]
        finally:
            if process:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=3)
                for stream in (process.stdin, process.stdout):
                    if stream: stream.close()


class UpgradeFoundryService:
    def __init__(self, workflows, codex, *, product_root=PRODUCT, evaluator=None):
        self.workflows, self.codex, self.product_root = workflows, codex, Path(product_root)
        self.root = workflows.root / "upgrade-foundry"
        require(not self.root.is_symlink(), "Foundry root cannot be a symlink.", "FOUNDRY_INTEGRITY")
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.path = self.root / "state.json"
        self.lock = workflows._lock("upgrade-foundry")
        self.evaluator = evaluator or NativeEvaluator(codex.binary)
        with _ACTIVE_LOCK:
            self.active = _ACTIVE_BY_ROOT.setdefault(str(self.root), {})
        with self.lock:
            if not self.path.exists():
                self._save({"schema": 1, "experiments": [], "active_candidate": None, "activation_history": []})
            else:
                state = self._load(); changed = False
                for exp in state["experiments"]:
                    if exp["status"] in {"constructing", "qualifying"} and exp["id"] not in self.active:
                        exp["events"].append({"kind": "interruption_recovered", "previous_status": exp["status"], "at": timestamp(),
                            "cost": "Upstream completion and consumption unknown; no automatic retry or qualification."})
                        exp["status"] = "interrupted"; changed = True
                if changed: self._save(state)

    def _save(self, state):
        require(len(encoded(state)) <= MAX_BYTES, "Foundry state exceeds the bounded local document envelope.", "FOUNDRY_SIZE")
        _atomic(self.path, encoded({"state": state, "mac": hmac.new(self.workflows._key, encoded(state), hashlib.sha256).hexdigest()}))

    def _load(self):
        _source_guard()
        value = strict_json(_regular(self.path))
        require(isinstance(value, dict) and set(value) == {"state", "mac"}, "Invalid foundry state.", "FOUNDRY_INTEGRITY")
        expected = hmac.new(self.workflows._key, encoded(value["state"]), hashlib.sha256).hexdigest()
        require(isinstance(value["mac"], str) and hmac.compare_digest(value["mac"], expected), "Foundry state authentication failed.", "FOUNDRY_INTEGRITY")
        return value["state"]

    def _experiment(self, state, ident):
        require(isinstance(ident, str), "Choose a registered experiment.", "FOUNDRY_INPUT")
        result = next((x for x in state["experiments"] if x["id"] == ident), None)
        require(result is not None, "Experiment not found.", "FOUNDRY_INPUT")
        return result

    def _public(self, state):
        result = copy.deepcopy(state)
        for exp in result["experiments"]:
            exp.pop("source_files", None)
            # Withhold the registered confirmation set from model construction.
            # An explicit owner export reveals it after the experiment finishes.
            exp.pop("protocol", None)
        result["scope"] = "Arbitrary model-written interpreter-module changes only; isolated research activation, no installed-code replacement."
        result["live_qualification"] = "NOT_ESTABLISHED_UNLESS_A_COMPLETED_AUTHORIZED_CONSTRUCTION_AND_NATIVE_SANDBOX_RECEIPT_IS_PRESENT"
        return result

    def close(self):
        """Cancel in-flight model and isolated execution without promoting results."""
        with self.lock:
            for ident, active in list(self.active.items()):
                active["cancel"].set()
                if "codex" in active:
                    active["codex"].cancel(ident)
                    active["codex"].close()

    def status(self):
        with self.lock: return self._public(self._load())

    def register(self, data):
        require(isinstance(data, dict) and set(data) <= {"objective", "model"}, "Register objective and selected Codex model only.", "FOUNDRY_INPUT")
        require(isinstance(data.get("objective"), str) and 0 < len(data["objective"]) <= 12000, "Supply a bounded upgrade objective.", "FOUNDRY_INPUT")
        require(isinstance(data.get("model"), str) and 0 < len(data["model"]) <= 200, "Select an authorized Codex model.", "FOUNDRY_INPUT")
        files = _snapshot(self.product_root)
        ident = "upgrade_" + secrets.token_hex(12)
        protocol = _protocol(secrets.randbits(128))
        exp = {"id": ident, "created_at": timestamp(), "objective": data["objective"], "model": data["model"], "adapter": "instrument-module-v1", "editable_paths": [EDITABLE],
               "status": "registered", "source_files": files, "baseline_manifest": _manifest(files), "protocol": protocol, "protocol_sha256": digest(protocol),
               "evaluator_sha256": OWN_SHA, "evaluator_dependencies": _authority_manifest(self.codex.binary), "costs": {"model": None, "engineering": None, "maintenance": None, "complete_cost_known": False}, "events": []}
        with self.lock:
            state = self._load(); require(len(state["experiments"]) < 100, "Archive completed foundry research before starting more in this document.", "FOUNDRY_SIZE")
            state["experiments"].append(exp); self._save(state)
            directory = self.root / ident; directory.mkdir(mode=0o700)
            _write_snapshot(directory / "baseline", files)
            _atomic(directory / "PROTOCOL.json", encoded(protocol))
            return {"experiment": self._public({"experiments": [exp]})["experiments"][0], "state": self._public(state)}

    def _construction_runtime(self):
        runtime = self.workflows.runtime
        config = getattr(runtime, "config", {})
        require(not (getattr(runtime, "local_only", False) or
                     (isinstance(config, dict) and config.get("local_only") is True)),
                "Local-only mode disables remote foundry construction.", "LOCAL_ONLY")
        require(callable(getattr(runtime, "execution_slot", None)) and
                callable(getattr(runtime, "generate_admitted_external", None)) and
                callable(getattr(runtime, "service", None)),
                "Foundry construction requires shared model execution admission.", "FOUNDRY_EXECUTION_ADMISSION")
        require(runtime.service("codex") is self.codex,
                "Foundry Codex connection differs from the shared runtime connection.", "FOUNDRY_EXECUTION_ADMISSION")
        return runtime

    def construct(self, data):
        require(isinstance(data, dict) and data.get("authorize") is True, "Explicitly authorize model-driven source construction.", "FOUNDRY_AUTHORIZATION")
        runtime = self._construction_runtime()
        with self.lock:
            state = self._load(); exp = self._experiment(state, data.get("experiment_id"))
            require(exp["status"] == "registered", "Construction requires a fresh registered experiment; attempts are not silently retried.", "FOUNDRY_STATE")
            require(self.codex.config.get("allow_workspace_write") is True, "Explicit Codex workspace-write permission is required.", "FOUNDRY_AUTHORIZATION")
            self.codex.gate()
            ident = exp["id"]; directory = self.root / ident
            seeded = _SeededCodex(self.codex, directory / "construction", exp["source_files"])
            cancel = threading.Event()
            exp["status"] = "constructing"; self.active[ident] = {"codex": seeded, "cancel": cancel}; self._save(state)
            prompt = ("Improve the HARNESS source to address this objective: " + exp["objective"] + "\n"
                      "This is an isolated source snapshot. Edit ONLY bridge/instruments.py. Preserve existing evaluate(spec, inputs, max_operations) output and safety contracts. "
                      "No network, dependency installation, permission changes or edits to any other file. Avoid bytecode writes (PYTHONDONTWRITEBYTECODE=1). "
                      "The qualification protocol and evaluator are outside this workspace and cannot be changed. Produce real Python source changes, explain mechanism, limitations and costs. "
                      "A finite external confirmation set includes correct affine arithmetic, missing fields, wrong types, unknown operations and exhausted budgets. "
                      "Do not claim superiority or qualification; the separate evaluator decides. Never seek credentials or production access.")
        started = time.perf_counter()
        last_progress = [0.0]
        def progress(event):
            if event.get("type") != "progress" or time.monotonic() - last_progress[0] < 1:
                return
            last_progress[0] = time.monotonic()
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                current["progress"] = {"phase": "constructing", "received_characters": event.get("received_characters"), "updated_at": timestamp()}
                self._save(state)
        dispatched = False
        def dispatch_seeded(request, on_event=None, *, expected_execution_identity=None, cancelled_before_dispatch=None):
            nonlocal dispatched
            self._construction_runtime()
            require(not cancel.is_set(), "Queued construction cancelled before dispatch.", "FOUNDRY_CANCELLED")
            require(seeded.plan is self.codex.plan, "Seeded construction changed the selected account.", "FOUNDRY_EXECUTION_ADMISSION")
            dispatched = True
            return seeded.generate(request, on_event=on_event, expected_execution_identity=expected_execution_identity,
                                   cancelled_before_dispatch=cancelled_before_dispatch)
        try:
            request = {"provider": "codex", "model": exp["model"], "prompt": prompt, "run_id": ident}
            with runtime.execution_slot(request, cancelled=cancel.is_set) as admission:
                response = runtime.generate_admitted_external(request, dispatch_seeded, admission, on_event=progress)
            candidate = Path(response["workspace"])
            require(candidate.resolve() == (directory / "construction" / ident).resolve(), "Unexpected construction workspace.", "FOUNDRY_INTEGRITY")
            files = self._candidate_files(candidate, exp["baseline_manifest"])
            require(files[EDITABLE] != exp["source_files"][EDITABLE], "Model made no change to the allowed interpreter source.", "FOUNDRY_NO_CHANGE")
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                require(not self.active[ident]["cancel"].is_set(), "Construction cancelled; late source is not accepted.", "FOUNDRY_CANCELLED")
                current.update(status="constructed", candidate_manifest=_manifest(files), candidate_sha256=_manifest(files)[EDITABLE], candidate_relative=f"{ident}/construction/{ident}")
                current["costs"].update(construction_wall_seconds=time.perf_counter() - started, model=response.get("cost"))
                current["events"].append({"kind": "constructed", "at": timestamp(), "run_id": response["run_id"], "qualification": response.get("qualification"), "source_sha256": current["candidate_sha256"]})
                self._save(state); return {"experiment": self._public({"experiments": [current]})["experiments"][0], "state": self._public(state)}
        except Exception as error:
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                current["status"] = "blocked" if getattr(error, "code", "").startswith(("CODEX_SANDBOX", "CODEX_UNAVAILABLE", "CHATGPT")) else "construction_failed"
                current["events"].append({"kind": "construction_failed", "at": timestamp(), "code": getattr(error, "code", "CONSTRUCTION_FAILED"),
                    "dispatch_started": dispatched, "cost": "Unknown upstream consumption; no automatic retry." if dispatched else "No model dispatch occurred; no model attempt was started."})
                current["costs"]["construction_wall_seconds"] = time.perf_counter() - started
                self._save(state)
            raise
        finally:
            self.active.pop(ident, None); seeded.close()

    @staticmethod
    def _candidate_files(directory, baseline):
        files = _snapshot(directory)
        require(set(files) == set(baseline), "Candidate added or removed tracked source assets.", "FOUNDRY_SCOPE")
        require(all(hashlib.sha256(value.encode()).hexdigest() == baseline[name] for name, value in files.items() if name != EDITABLE),
                "Candidate changed source outside the authorized interpreter module.", "FOUNDRY_SCOPE")
        # Even ignored extras must not be device files, links, hidden configuration
        # or additional executable content that could influence qualification.
        for count, path in enumerate(Path(directory).rglob("*"), 1):
            require(count <= MAX_FILES * 4, "Candidate directory inventory exceeds its bounded envelope.", "FOUNDRY_SCOPE")
            kind = path.lstat().st_mode
            require(stat.S_ISREG(kind) or stat.S_ISDIR(kind), "Candidate contains a link or nonregular filesystem object.", "FOUNDRY_SCOPE")
            if stat.S_ISREG(kind):
                require(path.relative_to(directory).as_posix() in files, "Candidate contains unregistered files.", "FOUNDRY_SCOPE")
        return files

    def _bind(self, exp):
        require(exp["evaluator_sha256"] == OWN_SHA and digest(exp["protocol"]) == exp["protocol_sha256"], "Frozen evaluation authority changed.", "FOUNDRY_INTEGRITY")
        require(exp.get("evaluator_dependencies") == _authority_manifest(self.codex.binary), "Frozen evaluator dependencies, Python runtime or Codex executable changed.", "FOUNDRY_INTEGRITY")
        directory = self.root / exp["id"]
        require(_regular(directory / "PROTOCOL.json") == encoded(exp["protocol"]), "Registered protocol bytes changed.", "FOUNDRY_INTEGRITY")
        require(_manifest(_snapshot(directory / "baseline")) == exp["baseline_manifest"], "Baseline source changed.", "FOUNDRY_INTEGRITY")
        candidate = self.root / exp["candidate_relative"]
        files = self._candidate_files(candidate, exp["baseline_manifest"])
        require(_manifest(files) == exp["candidate_manifest"], "Candidate changed after construction; start a new experiment.", "FOUNDRY_INTEGRITY")
        return directory / "baseline", candidate

    @staticmethod
    def _judge(cases, rows):
        require(isinstance(rows, list) and len(rows) == len(cases), "Candidate output count differs from the frozen test set.", "FOUNDRY_OUTPUT")
        decisions = []
        for case, row in zip(cases, rows):
            require(isinstance(row, dict) and row.get("id") == case["id"] and set(row) <= {"id", "output", "error"}, "Candidate output identities or fields are invalid.", "FOUNDRY_OUTPUT")
            passed = row.get("error") is True if case.get("expect_error") else "error" not in row and equivalent(row.get("output"), case["expected"])
            decisions.append({"id": case["id"], "passed": bool(passed)})
        return {"passed": all(x["passed"] for x in decisions), "cases": len(cases), "accepted_cases": sum(x["passed"] for x in decisions), "decisions": decisions}

    def qualify(self, data):
        require(isinstance(data, dict) and data.get("authorize") is True, "Explicitly authorize isolated candidate execution in the native sandbox.", "FOUNDRY_AUTHORIZATION")
        with self.lock:
            state = self._load(); exp = self._experiment(state, data.get("experiment_id"))
            require(exp["status"] == "constructed", "Qualify a constructed, unchanged candidate.", "FOUNDRY_STATE")
            baseline, candidate = self._bind(exp); ident = exp["id"]
            cancel = threading.Event(); self.active[ident] = {"cancel": cancel}
            exp["status"] = "qualifying"; self._save(state)
        arms = {}
        try:
            for name, directory in (("baseline", baseline), ("candidate", candidate)):
                started = time.perf_counter(); rows = self.evaluator.run(directory, exp["protocol"]["cases"], cancel=cancel)
                arms[name] = {**self._judge(exp["protocol"]["cases"], rows), "wall_seconds": time.perf_counter() - started}
            started = time.perf_counter()
            ordinary = [{"id": c["id"], "output": {"result": c["reference"]["x"] * c["reference"]["gain"] + c["reference"]["offset"]}}
                        for c in exp["protocol"]["cases"] if "reference" in c]
            valid = [c for c in exp["protocol"]["cases"] if "reference" in c]
            arms["ordinary_direct_arithmetic"] = {**self._judge(valid, ordinary), "wall_seconds": time.perf_counter() - started,
                "scope": "Competent direct arithmetic on the same affine outcomes; JSON equality and malformed-input contracts belong to the two interpreter arms."}
            self._bind(exp); _source_guard()
            require(not cancel.is_set(), "Qualification cancelled; no candidate activated.", "FOUNDRY_CANCELLED")
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                require(not cancel.is_set(), "Qualification cancelled before final decision; result discarded.", "FOUNDRY_CANCELLED")
                passed = all(arm["passed"] for arm in arms.values())
                current["status"] = "qualified" if passed else "rejected"
                current["qualification"] = {"correctness": "PASS" if passed else "FAIL", "arms": arms, "protocol_sha256": exp["protocol_sha256"],
                    "candidate_sha256": exp["candidate_sha256"], "independent_evaluation": "Host compares sandbox outputs to preregistered direct arithmetic and fixed JSON equality expectations; child verdicts are never authority.",
                    "general_improvement": "NOT_ESTABLISHED", "objective_achievement": "NOT_ESTABLISHED_BY_REGRESSION_PASS", "complete_cost_advantage": "UNKNOWN", "production_promotion": False}
                current["events"].append({"kind": "qualified" if passed else "rejected", "at": timestamp()}); self._save(state)
                return {"experiment": self._public({"experiments": [current]})["experiments"][0], "state": self._public(state)}
        except Exception as error:
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                current["status"] = "qualification_blocked" if getattr(error, "code", "").startswith(("CODEX_SANDBOX", "FOUNDRY_SANDBOX")) else "qualification_failed"
                current["qualification"] = {"correctness": "BLOCKED" if "blocked" in current["status"] else "FAIL", "arms": arms, "error_code": getattr(error, "code", "EVALUATION_FAILED"), "production_promotion": False}
                self._save(state)
            raise
        finally:
            self.active.pop(ident, None)

    def cancel(self, data):
        ident = data.get("experiment_id") if isinstance(data, dict) else None
        with self.lock:
            self._experiment(self._load(), ident); active = self.active.get(ident)
            if active:
                active["cancel"].set()
                if "codex" in active: active["codex"].cancel(ident)
            return {"cancelled": active is not None, "state": self.status()}

    def activate(self, data):
        require(isinstance(data, dict) and data.get("authorize") is True, "Explicitly authorize the qualified isolated research candidate.", "FOUNDRY_AUTHORIZATION")
        with self.lock:
            state = self._load(); exp = self._experiment(state, data.get("experiment_id"))
            require(exp["status"] == "qualified" and exp.get("qualification", {}).get("correctness") == "PASS", "Only a qualified unchanged candidate can be selected.", "FOUNDRY_STATE")
            require(data.get("expected_candidate_sha256") == exp["candidate_sha256"], "Confirm the exact reviewed candidate SHA-256.", "FOUNDRY_AUTHORIZATION")
            self._bind(exp)
            state["activation_history"].append({"previous": state["active_candidate"], "next": exp["id"], "at": timestamp()})
            state["active_candidate"] = exp["id"]; self._save(state)
            return {"state": self._public(state), "scope": "Selected for explicit sandbox-only retained calls. Installed HARNESS code is unchanged."}

    def rollback(self, data):
        require(isinstance(data, dict) and data.get("authorize") is True, "Explicitly authorize clearing the isolated research selection.", "FOUNDRY_AUTHORIZATION")
        with self.lock:
            state = self._load(); previous = state["active_candidate"]
            state["activation_history"].append({"previous": previous, "next": None, "at": timestamp(), "reason": "operator rollback"})
            state["active_candidate"] = None; self._save(state)
            return {"state": self._public(state), "rolled_back": previous}

    def evaluate_retained(self, data):
        require(isinstance(data, dict) and set(data) <= {"instrument", "inputs", "expected", "max_operations"}, "Use bounded instrument inputs and optional expected output.", "FOUNDRY_INPUT")
        operations = data.get("max_operations", 10000)
        require(type(operations) is int and 1 <= operations <= 1000000, "Invalid finite operation envelope.", "FOUNDRY_INPUT")
        with self.lock:
            state = self._load(); exp = self._experiment(state, state["active_candidate"])
            _, candidate = self._bind(exp)
            ident, candidate_sha = exp["id"], exp["candidate_sha256"]
            require(ident not in self.active, "Another operation already owns this candidate.", "FOUNDRY_BUSY")
            case = {"id": "retained-call", "instrument": data.get("instrument"), "inputs": data.get("inputs"), "max_operations": operations}
            require(len(encoded(case)) <= 1024 * 1024, "Retained call exceeds its input envelope.", "FOUNDRY_INPUT")
            cancel = threading.Event(); self.active[ident] = {"cancel": cancel}
        try:
            rows = self.evaluator.run(candidate, [case], cancel=cancel)
            with self.lock:
                state = self._load(); current = self._experiment(state, ident)
                require(not cancel.is_set() and state["active_candidate"] == ident and current["candidate_sha256"] == candidate_sha,
                        "Retained call cancelled or active candidate changed; late result discarded.", "FOUNDRY_CANCELLED")
                self._bind(current)
                require(isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict) and rows[0].get("id") == "retained-call"
                        and set(rows[0]) <= {"id", "output", "error"}, "Invalid retained result.", "FOUNDRY_OUTPUT")
                result = {"candidate_id": ident, "candidate_sha256": candidate_sha, "result": rows[0],
                          "qualification": "EXECUTED_NOT_INDEPENDENTLY_ACCEPTED", "accepted": None}
                if "expected" in data:
                    case["expected"] = data["expected"]
                    result["accepted"] = self._judge([case], rows)["passed"]
                    result["qualification"] = "CALLER_EXPECTATION_CHECKED"
                current["events"].append({"kind": "retained_call", "at": timestamp(), "input_sha256": digest(case), "accepted": result["accepted"]}); self._save(state)
                return {"execution": result, "state": self._public(state)}
        finally:
            with self.lock:
                if self.active.get(ident, {}).get("cancel") is cancel: self.active.pop(ident, None)

    def export(self, data):
        with self.lock:
            state = self._load(); exp = copy.deepcopy(self._experiment(state, data.get("experiment_id")))
            require(exp["status"] not in {"constructing", "qualifying", "registered"}, "Export the protocol after this attempt ends; do not leak the confirmation set into construction.", "FOUNDRY_STATE")
            exp.pop("source_files", None)
            if exp.get("candidate_relative"):
                _, candidate = self._bind(exp)
                exp["candidate_source"] = _regular(candidate / EDITABLE, 1024 * 1024).decode()
            return {"experiment": exp, "sha256": digest(exp), "notice": "Research source and finite evidence only; no credentials, deployment authority or general improvement claim."}
