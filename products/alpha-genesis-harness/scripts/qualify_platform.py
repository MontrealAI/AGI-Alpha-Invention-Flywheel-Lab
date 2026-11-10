#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Operate externally identified release bytes using the host's native source launcher.

This exercises .cmd on Windows and .command through /bin/sh on macOS, then
headless native-OS Chromium. It does not claim Finder/Explorer double-click,
notarization, code signing, live model access or a clean consumer OS image.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from package_release import MAX_ARCHIVE, verify_snapshot


def native_launcher(product: Path, workspace: Path, port: int, system: str | None = None) -> list[str]:
    """Only controlled launcher names and bounded generated arguments enter a shell."""
    system = system or platform.system()
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Use a valid loopback port")
    options = ["--port", str(port), "--no-browser", "--workspace", str(workspace)]
    if system == "Windows":
        # cmd syntax expands percent/exclamation even inside quotes. Refuse those
        # path spellings rather than relying on POSIX escaping or shell=True.
        if re.search(r'[%!^&|<>()"\r\n]', str(workspace)):
            raise ValueError("Native Windows qualification needs a shell-safe temporary path")
        launcher = product / "Launch-HARNESS.cmd"
        # Popen applies CRT quoting to each argument. A prequoted combined
        # command would introduce backslash-quotes that cmd does not decode.
        # The fixed simple batch name needs no quoting or /s outer-quote removal.
        result = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", launcher.name, *options]
    elif system == "Darwin":
        launcher = product / "Launch-HARNESS.command"
        result = ["/bin/sh", str(launcher), *options]
    elif system == "Linux":
        launcher = product / "Launch-HARNESS.sh"
        result = ["/bin/sh", str(launcher), *options]
    else:
        raise ValueError("No native source launcher qualification for " + system)
    if launcher.is_symlink() or not launcher.is_file():
        raise ValueError("Exact archive lacks the platform source launcher")
    return result


def private_environment() -> dict[str, str]:
    """Pass only operating-system paths, never caller credentials or model settings."""
    allowed = {"PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "COMSPEC",
               "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"}
    result = {key: value for key, value in os.environ.items() if key.upper() in {name.upper() for name in allowed}}
    result.update({"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    return result


def launcher_interpreter(environment: dict[str, str]) -> dict:
    """Observe the same interpreter selection rule used by the shipped launcher."""
    if platform.system() == "Windows":
        launcher = shutil.which("py", path=environment.get("PATH"))
        command = [launcher, "-3"] if launcher else [shutil.which("python", path=environment.get("PATH")) or "python"]
    else:
        command = [shutil.which("python3", path=environment.get("PATH")) or "python3"]
    command.extend(["-c", "import json,sys; print(json.dumps({'executable':sys.executable,'version':sys.version.split()[0]}))"])
    probe = subprocess.run(command, env=environment, capture_output=True, text=True, check=True)
    result = json.loads(probe.stdout)
    if not isinstance(result.get("version"), str) or not isinstance(result.get("executable"), str):
        raise ValueError("Native launcher interpreter identity is unavailable")
    return {**result, "basis": "Separate probe using the same py -3 / python / python3 selection rule as the native source launcher"}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


GENESIS_STARTUP_PROBE = r'''
import json, sys, traceback
from pathlib import Path
result = {"status": "FAIL", "stage": "imports", "completed_stages": [],
          "interpreter": sys.executable, "python_version": sys.version.split()[0],
          "scope": "Credential-free initialization diagnostic only; not browser or native-launcher qualification."}
workflows = None
try:
    from bridge.workflows import WorkflowService
    from bridge.genesis_next import GenesisNextService
    result["completed_stages"].append("imports")
    result["stage"] = "workflow_initialization"
    workflows = WorkflowService(None, Path(sys.argv[1]))
    result["completed_stages"].append(result["stage"])
    result["stage"] = "genesis_initialization"
    genesis = GenesisNextService(workflows)
    result["completed_stages"].append(result["stage"])
    result["stage"] = "genesis_status"
    status = genesis.status()
    assert any(cap.get("id") == "bounded-verification" for cap in status.get("capabilities", [])), "Expected source-backed capability is missing"
    result["completed_stages"].append(result["stage"])
    result["status"] = "PASS"
    result["stage"] = "complete"
except Exception as error:
    result.update({"exception_type": type(error).__name__, "errno": getattr(error, "errno", None),
                   "winerror": getattr(error, "winerror", None), "traceback": traceback.format_exc()})
finally:
    if workflows is not None:
        try:
            workflows.close()
        except Exception:
            result["status"] = "FAIL"
            result["cleanup_traceback"] = traceback.format_exc()
    print(json.dumps(result))
sys.exit(0 if result["status"] == "PASS" else 1)
'''


def probe_genesis_startup(product: Path, workspace: Path, output: Path, interpreter: str,
                          environment: dict[str, str]) -> dict:
    """Expose a hidden local initialization exception on exact trusted source bytes."""
    result = subprocess.run([interpreter, "-c", GENESIS_STARTUP_PROBE, str(workspace)],
                            cwd=product, env=environment, capture_output=True, text=True)
    (output / "genesis-startup.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output / "genesis-startup.stderr.txt").write_text(result.stderr, encoding="utf-8")
    try:
        diagnostic = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ValueError("GENESIS initialization diagnostic did not return a receipt; inspect its preserved output") from None
    (output / "GENESIS-STARTUP-DIAGNOSTIC.json").write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
    if result.returncode or diagnostic.get("status") != "PASS":
        raise ValueError("GENESIS initialization failed at " + str(diagnostic.get("stage")) + "; inspect its preserved traceback")
    return diagnostic


def request(port: int, path: str, headers: dict | None = None) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Loopback qualification response exceeded its envelope")
        return response.status, json.loads(raw)
    finally:
        connection.close()


def authenticate(port: int, process: subprocess.Popen) -> dict:
    """Finite readiness polling; this is an installation check, not mission runtime."""
    deadline = time.monotonic() + 45
    while True:
        if process.poll() is not None:
            raise ValueError("Native launcher exited before local authentication")
        try:
            status, session = request(port, "/api/session", {"X-Harness-Client": "browser"})
            if status != 200 or not isinstance(session.get("token"), str) or len(session["token"]) < 20:
                raise ValueError("Local session bootstrap did not return a private token")
            break
        except (ConnectionError, OSError, TimeoutError):
            if time.monotonic() >= deadline:
                raise ValueError("Native launcher did not expose its loopback application within 45 seconds") from None
            time.sleep(0.1)
    denied, _ = request(port, "/api/status")
    if denied != 403:
        raise ValueError("Unauthenticated status request was not refused")
    authorized, status = request(port, "/api/status", {"X-Harness-Token": session["token"]})
    if authorized != 200 or not isinstance(status, dict):
        code = status.get("error", {}).get("code") if isinstance(status, dict) else None
        diagnostic = code if isinstance(code, str) and re.fullmatch(r"[A-Z0-9_]{1,80}", code) else "UNKNOWN"
        raise ValueError(f"Authenticated local status was unavailable (HTTP {authorized}; {diagnostic})")
    # Never retain the token. Record only minimal observable readiness.
    return {"bootstrap": "PASS", "unauthenticated_status": denied, "authenticated_status": authorized,
            "configured_providers": len(status.get("providers", [])),
            "workflow_engine_available": status.get("workflow_engine_available") is True}


def stop_owned_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=10)


def qualify(archive: Path, expected_sha256: str, expected_source_revision: str, output: Path,
            visual_modules: Path, browser_executable: Path, node_executable: str | None = None) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256) or not re.fullmatch(r"[a-f0-9]{40}", expected_source_revision):
        raise ValueError("Exact externally supplied archive SHA-256 and source revision are required")
    with archive.open("rb") as stream:
        raw = stream.read(MAX_ARCHIVE + 1)
    if len(raw) > MAX_ARCHIVE or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Archive does not match the external digest or size envelope")
    integrity = verify_snapshot(raw, expected_sha256=expected_sha256, expected_source_revision=expected_source_revision)
    if integrity.get("build_mode") != "source-bound" or not integrity.get("source_claim_matches_commit"):
        raise ValueError("Native qualification requires exact committed-source release bytes")
    visual_modules, browser_executable = visual_modules.resolve(strict=True), browser_executable.resolve(strict=True)
    node = node_executable or shutil.which("node")
    if not node or not browser_executable.is_file():
        raise ValueError("Explicit Node and native browser executables are required")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "alpha-genesis-native-platform/v1", "status": "FAIL", "archive_sha256": expected_sha256,
               "source_revision": expected_source_revision, "host": {"system": platform.system(), "platform": platform.platform(),
               "architecture": platform.machine(), "qualifier_python": platform.python_version()}, "checks": {},
               "scope": "Native source-launcher process plus headless Chromium on this OS, operating exact extracted archive bytes. No desktop double-click, signing/notarization, live-provider, clean consumer image or commercial qualification.",
               "provider_calls": 0, "complete_host_cost": None}
    start = time.monotonic()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="harness-native-") as temporary:
            # macOS exposes its temporary directory through /var -> /private/var.
            # Canonicalize only our newly created directory; product workspace
            # validation continues to refuse symlink paths supplied by callers.
            root = Path(temporary).resolve(strict=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
                bundle.extractall(root / "extracted")
            roots = list((root / "extracted").iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise ValueError("Release must extract into one product directory")
            product = roots[0]
            expected_visual = json.loads((product / "tests/visual/package.json").read_text())["dependencies"]["playwright-core"]
            installed_visual = json.loads((visual_modules / "playwright-core/package.json").read_text())["version"]
            if installed_visual != expected_visual:
                raise ValueError("Native browser driver differs from the packaged pinned requirement")
            port = free_port()
            private_workspace = root / "private-workspace"
            command = native_launcher(product, private_workspace, port)
            receipt["launcher"] = Path("Launch-HARNESS.cmd" if platform.system() == "Windows" else "Launch-HARNESS.command" if platform.system() == "Darwin" else "Launch-HARNESS.sh").name
            environment = private_environment()
            receipt["launcher_interpreter"] = launcher_interpreter(environment)
            receipt["checks"]["genesis_startup_diagnostic"] = probe_genesis_startup(
                product, root / "diagnostic-workspace", output,
                receipt["launcher_interpreter"]["executable"], environment)
            with (output / "launcher.stdout.txt").open("w", encoding="utf-8") as stdout, (output / "launcher.stderr.txt").open("w", encoding="utf-8") as stderr:
                try:
                    process = subprocess.Popen(command, cwd=product, env=environment, stdout=stdout, stderr=stderr,
                                               start_new_session=os.name != "nt", creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
                    receipt["checks"]["loopback_authentication"] = authenticate(port, process)
                    environment.update({"NODE_PATH": str(visual_modules), "CHROME_BIN": str(browser_executable), "PYTHON": sys.executable,
                                        "HARNESS_BASE_URL": f"http://127.0.0.1:{port}", "HARNESS_SCREENSHOT_DIR": str(output / "browser"),
                                        "EXPECTED_SOURCE": expected_source_revision})
                    replay = product / "evidence/UI_BROWSER_REPLAY.cjs"
                    if replay.is_symlink() or not replay.is_file():
                        raise ValueError("Archive lacks the cross-platform browser replay")
                    operation = subprocess.run([node, str(replay)], cwd=product, env=environment, capture_output=True, text=True)
                    (output / "browser.stdout.txt").write_text(operation.stdout, encoding="utf-8")
                    (output / "browser.stderr.txt").write_text(operation.stderr, encoding="utf-8")
                    receipt["browser_returncode"] = operation.returncode
                    if operation.returncode:
                        raise ValueError("Native browser workflow failed; preserved evidence contains the reason")
                    browser_receipt = json.loads((output / "browser/BROWSER-VERIFICATION.json").read_text())
                    expected_platform = {"Windows": "win32", "Darwin": "darwin", "Linux": "linux"}[platform.system()]
                    if browser_receipt.get("status") != "PASS" or browser_receipt.get("platform") != expected_platform or browser_receipt.get("source_revision") != expected_source_revision or browser_receipt.get("server_mode") != "external-native-launcher":
                        raise ValueError("Native browser receipt does not establish this exact platform/source/launcher")
                    if not browser_receipt.get("exports"):
                        raise ValueError("Native browser did not qualify an actual output download")
                    native_state = private_workspace / "genesis-next" / "state.json"
                    if native_state.is_symlink() or not native_state.is_file():
                        raise ValueError("Native launcher did not create GENESIS state in the expected private workspace")
                    receipt["checks"]["native_workspace"] = {
                        "genesis_state_created_at_requested_path": True,
                        "scope": "Existence only after the actual launcher/browser experiment; no workspace contents or integrity key retained."}
                    receipt["checks"]["browser"] = browser_receipt
                    receipt["status"] = "PASS"
                finally:
                    stop_owned_process(process)
                    process = None
    except BaseException as error:
        receipt["error"] = str(error)
        raise
    finally:
        stop_owned_process(process)
        receipt["wall_seconds"] = round(time.monotonic() - start, 6)
        (output / "PLATFORM-QUALIFICATION.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--visual-modules", required=True, type=Path)
    parser.add_argument("--browser-executable", required=True, type=Path)
    parser.add_argument("--node-executable")
    args = parser.parse_args()
    print(json.dumps(qualify(args.archive, args.expected_sha256, args.expected_source_revision, args.output,
                             args.visual_modules, args.browser_executable, args.node_executable), indent=2))


if __name__ == "__main__":
    main()
