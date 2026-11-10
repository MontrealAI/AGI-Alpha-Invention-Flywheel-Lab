# SPDX-License-Identifier: Apache-2.0
"""Current official Codex permission profiles, checked before OAuth execution."""
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import subprocess
import sys
import sysconfig
import tempfile
import threading

from .adapters import BridgeError, strict_json

# Bind this module before a later lazy self-upgrade evaluator imports it.
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

PROFILE = "harness_isolated"


def verify_profile_protocol(binary):
    """Named profile selection is an explicit experimental app-server capability."""
    with tempfile.TemporaryDirectory(prefix="harness-codex-schema-") as directory:
        environment = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG") if key in os.environ}
        environment.update({"HOME": directory, "CODEX_HOME": directory})
        try:
            result = subprocess.run([binary, "app-server", "generate-json-schema", "--experimental", "--out", directory],
                                    env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=15, check=False)
            if result.returncode:
                raise ValueError()
            for name, field in (("ThreadStartParams", "permissions"), ("ThreadResumeParams", "permissions"),
                                ("TurnStartParams", "permissions"), ("CommandExecParams", "permissionProfile"),
                                ("ThreadStartResponse", "activePermissionProfile")):
                schema = strict_json(Path(directory, "v2", name + ".json").read_bytes())
                if field not in schema["properties"]:
                    raise ValueError()
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            raise BridgeError("CODEX_SANDBOX_UNSUPPORTED", "This Codex CLI does not expose the required named permission-profile protocol. Install a compatible official release.", 409) from None


def permission_overrides(directory, writable, binary):
    """Use exact roots; no legacy sandbox override can broaden this profile."""
    paths = {":root": "deny", ":minimal": "read", ":tmpdir": "deny", ":slash_tmp": "deny",
             str(Path(directory).resolve()): "write" if writable else "read",
             str(Path(binary).resolve()): "read", str(Path(sys.executable).resolve()): "read"}
    executable = Path(binary).resolve()
    # Official standalone companions and npm platform packages contain runtime
    # binaries only. Support those layouts without granting their parent HOME,
    # /opt prefix, entire node_modules tree or customer project directory.
    for parent in (executable.parent, executable.parent.parent):
        for name in ("codex-resources", "codex-path"):
            candidate = parent / name
            if candidate.is_dir():
                paths[str(candidate.resolve())] = "read"
    if executable.suffix == ".js" and executable.parent.name == "bin" and executable.parent.parent.name == "codex" and executable.parent.parent.parent.name == "@openai":
        package = executable.parent.parent
        paths[str(package)] = "read"
        for platform in ("linux-x64", "linux-arm64", "darwin-x64", "darwin-arm64", "win32-x64", "win32-arm64"):
            candidate = package.parent / ("codex-" + platform)
            if candidate.is_dir():
                paths[str(candidate.resolve())] = "read"
    # Non-system Python installs need their actual standard library and shared
    # interpreter library. Do not broaden access to /opt, sys.prefix or HOME.
    for name in ("stdlib", "platstdlib"):
        value = sysconfig.get_path(name)
        if value and Path(value).is_dir():
            paths[str(Path(value).resolve())] = "read"
    libdir, library = sysconfig.get_config_var("LIBDIR"), sysconfig.get_config_var("LDLIBRARY")
    if libdir and library and Path(libdir, library).is_file():
        paths[str(Path(libdir, library).resolve())] = "read"
    filesystem = "{" + ",".join(json.dumps(key) + "=" + json.dumps(value) for key, value in paths.items()) + "}"
    values = {"default_permissions": json.dumps(PROFILE), f"permissions.{PROFILE}.filesystem": filesystem,
              f"permissions.{PROFILE}.network.enabled": "false", "shell_environment_policy.set.PATH": json.dumps(os.defpath)}
    result = []
    for key, value in values.items():
        result += ["-c", key + "=" + value]
    return result


def verify_runtime_sandbox(command, directory, codex_home, writable, process_factory=subprocess.Popen):
    """No inference. Prove local allow/deny and credential-environment boundaries.

    A synthetic environment sentinel is used, never an OAuth/API credential.
    Native sandbox failure is a host dependency, not permission to bypass it.
    """
    directory, codex_home = Path(directory), Path(codex_home)
    marker = ".harness-probe-" + secrets.token_hex(8)
    allowed = directory / marker
    written = directory / (marker + "-write")
    outside = directory.parent / (marker + "-outside")
    allowed.write_text("HARNESS_ALLOWED", encoding="utf-8")
    outside.write_text("HARNESS_FORBIDDEN", encoding="utf-8")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG") if key in os.environ}
    env.update({"HOME": str(codex_home), "CODEX_HOME": str(codex_home), "ACCESS_TOKEN": "HARNESS_SYNTHETIC_ENV_SENTINEL"})
    process = None
    failure = "protocol_initialization"
    events = queue.Queue(maxsize=32)
    # Paths are passed as argv, never interpolated into shell source.
    program = """import json,os,socket,sys
from pathlib import Path
r={}
try:r['read_allowed']=Path(sys.argv[1]).read_text()=='HARNESS_ALLOWED'
except OSError:r['read_allowed']=False
try:Path(sys.argv[2]).read_bytes();r['outside_denied']=False
except OSError:r['outside_denied']=True
try:Path(sys.argv[3]).write_text('HARNESS_WRITE');r['write_allowed']=True
except OSError:r['write_allowed']=False
s=socket.socket();s.settimeout(1)
try:r['network_denied']=s.connect_ex(('127.0.0.1',int(sys.argv[4])))!=0
except OSError:r['network_denied']=True
finally:s.close()
r['credential_env_hidden']='ACCESS_TOKEN' not in os.environ
print(json.dumps(r,sort_keys=True))
"""
    try:
        # Even an unexpected eager catalog lookup during startup must remain
        # local. This no-inference probe never points a client at OpenAI APIs.
        probe_command = [argument if not argument.startswith("model_providers.openai_chatgpt_plan.base_url=")
                         else 'model_providers.openai_chatgpt_plan.base_url="http://127.0.0.1:9/v1"'
                         for argument in command]
        process = process_factory(probe_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, encoding="utf-8", bufsize=1, cwd=str(directory), env=env)

        def reader():
            try:
                for line in process.stdout:
                    if len(line) > 65536:
                        break
                    events.put(strict_json(line), timeout=1)
            except (BridgeError, OSError, queue.Full, UnicodeError):
                pass
            finally:
                try: events.put(None, timeout=1)
                except queue.Full: pass

        threading.Thread(target=reader, daemon=True).start()

        def rpc(ident, method, params):
            process.stdin.write(json.dumps({"id": ident, "method": method, "params": params}) + "\n")
            process.stdin.flush()
            for _ in range(64):
                message = events.get(timeout=20)
                if message is None:
                    raise ValueError()
                if message.get("id") == ident:
                    if message.get("error") or not isinstance(message.get("result"), dict):
                        raise ValueError()
                    return message["result"]
            raise ValueError()

        rpc(0, "initialize", {"clientInfo": {"name": "alpha_genesis_harness", "title": "HARNESS sandbox check", "version": "0.3.0"},
                               "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"method":"initialized","params":{}}\n')
        process.stdin.flush()
        profiles = rpc(1, "permissionProfile/list", {"cwd": str(directory)})
        if not any(row.get("id") == PROFILE and row.get("allowed") is True for row in profiles.get("data", [])):
            failure = "permission_profile_not_allowed"
            raise ValueError()
        failure = "native_command_execution"
        result = rpc(2, "command/exec", {"command": [sys.executable, "-I", "-c", program, str(allowed), str(outside), str(written), str(port)],
                    "cwd": str(directory), "permissionProfile": PROFILE, "timeoutMs": 10000, "outputBytesCap": 4096})
        if result.get("exitCode") != 0:
            if "Operation not permitted" in str(result.get("stderr", "")):
                failure = "host_sandbox_operation_not_permitted"
            elif "Python" in str(result.get("stderr", "")) or "ModuleNotFound" in str(result.get("stderr", "")):
                failure = "python_runtime_unavailable_in_sandbox"
            raise ValueError()
        checks = strict_json(result.get("stdout", ""))
        expected = {"read_allowed": True, "outside_denied": True, "write_allowed": writable,
                    "network_denied": True, "credential_env_hidden": True}
        if checks != expected or written.exists() != writable:
            failure = "sandbox_boundary_check_failed"
            raise ValueError()
        return {"status": "PASS", "checks": checks, "scope": "Local sandbox probe; no authenticated model execution."}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, queue.Empty, subprocess.TimeoutExpired):
        raise BridgeError("CODEX_SANDBOX_UNAVAILABLE", f"The native Codex sandbox check failed ({failure}). No OAuth-backed Codex process was started; workspace, network and credential isolation must pass before use.", 409) from None
    finally:
        listener.close()
        if process:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            for pipe in (process.stdin, process.stdout):
                if pipe: pipe.close()
        for path in (allowed, written, outside):
            path.unlink(missing_ok=True)
