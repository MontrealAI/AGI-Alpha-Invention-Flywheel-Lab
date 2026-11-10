# SPDX-License-Identifier: Apache-2.0
"""Official Codex app-server bridge using the HARNESS's authorized SIWC session.

This is a distinct engineering execution path, never a generic-model API fallback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import stat
import subprocess
import threading
import tempfile
import time

from .adapters import BridgeError, ID, MAX_BODY, MAX_RESPONSE, RUN_ID, strict_json
from .chatgpt import APP_NAME, ChatGPTPlanService, RESOURCE


from .codex_permissions import PROFILE, permission_overrides, verify_profile_protocol, verify_runtime_sandbox

verify_sandbox_protocol = verify_profile_protocol


# Bind this module before a later lazy self-upgrade evaluator imports it.
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class _AgentMessages:
    """Keep app-server message items distinct until their terminal snapshots.

    Deltas have an itemId but no phase. Item lifecycle events supply the phase
    and item/completed supplies authoritative text. A missing/null phase stays
    compatible with legacy providers without merging their separate messages.
    """
    def __init__(self):
        self.items = {}
        self.received_characters = 0

    def _item(self, ident):
        if not isinstance(ident, str) or not ident:
            raise BridgeError("CODEX_PROTOCOL", "Codex message did not supply an item ID.", 502)
        return self.items.setdefault(ident, {"text": "", "phase": None, "completed": False})

    def delta(self, params):
        item = self._item(params.get("itemId"))
        delta = params.get("delta")
        if not isinstance(delta, str) or item["completed"]:
            raise BridgeError("CODEX_PROTOCOL", "Codex returned an invalid message delta.", 502)
        item["text"] += delta
        self.received_characters += len(delta)
        self.items[params["itemId"]] = self.items.pop(params["itemId"])

    def snapshot(self, value, *, completed):
        if not isinstance(value, dict):
            raise BridgeError("CODEX_PROTOCOL", "Codex returned a malformed item.", 502)
        if value.get("type") != "agentMessage":
            return
        item = self._item(value.get("id"))
        phase, text = value.get("phase"), value.get("text")
        if phase not in (None, "commentary", "partial_answer", "final_answer") or not isinstance(text, str):
            raise BridgeError("CODEX_PROTOCOL", "Codex returned malformed agent message text or phase.", 502)
        # Null means unknown, not permission to downgrade known commentary into
        # a legacy terminal answer when a later snapshot omits phase metadata.
        if phase is not None:
            item["phase"] = phase
        item.update(text=text, completed=completed)
        # Item starts/deltas may interleave. Follow their latest lifecycle
        # activity so a late completion wins and a newer unfinished item blocks
        # fallback to an older result. A turn snapshot supplies canonical order.
        self.items[value["id"]] = self.items.pop(value["id"])

    def final_text(self):
        items = list(self.items.values())
        final = [item for item in items if item["phase"] == "final_answer"]
        candidate = final[-1] if final else (items[-1] if items else None)
        # Do not fall back to an earlier unknown message if the last item is
        # explicitly nonterminal or unfinished, nor to a superseded final.
        if candidate and candidate["completed"] and candidate["phase"] in (None, "final_answer"):
            return candidate["text"]
        return ""


class CodexService:
    max_concurrent = 1

    def __init__(self, config=None, plan_service=None, workspace_root=None, process_factory=subprocess.Popen, sandbox_validator=verify_sandbox_protocol, runtime_probe=verify_runtime_sandbox):
        self.config = config or {}
        self.plan = plan_service or ChatGPTPlanService()
        self.root = Path(workspace_root or self.config.get("workspace_root") or (Path.home() / "AlphaGenesisWork")).expanduser()
        self.process_factory = process_factory
        self._lock = threading.RLock()
        self._active, self._runs = {}, set()
        self._closed = False
        self.binary = self.config.get("executable") or shutil.which("codex")
        self.sandbox_validator = sandbox_validator
        self.runtime_probe = runtime_probe
        self._validated_binary = None

    def gate(self):
        if self._closed:
            raise BridgeError("CODEX_CLOSED", "This Codex execution service is closed.", 409)
        self.plan.gate()
        if self.config.get("allow_execution") is not True:
            raise BridgeError("CODEX_DISABLED", "Codex execution is disabled. Explicitly enable it in local configuration.", 403)
        if not self.binary or not Path(self.binary).is_absolute() or not Path(self.binary).is_file():
            raise BridgeError("CODEX_UNAVAILABLE", "Install the official Codex CLI and configure its absolute executable path.", 409)
        identity = (self.binary, Path(self.binary).stat().st_mtime_ns, Path(self.binary).stat().st_size)
        if self._validated_binary != identity:
            self.sandbox_validator(self.binary)
            self._validated_binary = identity

    def status(self):
        try:
            self.gate()
            enabled, reason = True, "Codex app-server is configured. A completed authenticated turn is required for live qualification."
        except BridgeError as error:
            enabled, reason = False, error.message
        return {"enabled": enabled, "ready": enabled and self.plan.status()["ready"], "reason": reason,
                "sandbox": "workspace-write" if self.config.get("allow_workspace_write") is True else "read-only",
                "workspace_root": str(self.root), "network_access": False,
                "usage_category": "chatgpt_plan_codex", "qualification": "CONTRACT_TESTED_ONLY"}

    def discover(self):
        self.gate()
        return self.plan.discover()

    def execution_identity(self):
        if self._closed:
            raise BridgeError("CODEX_CLOSED", "This Codex execution service is closed.", 409)
        return self.plan.execution_identity()

    def redact(self, text):
        return self.plan.redact(text)

    def cancel(self, run_id):
        with self._lock:
            row = self._active.get(run_id)
            if row:
                row["cancel"].set()
            return {"run_id": run_id, "cancelled": row is not None}

    def close(self):
        with self._lock:
            self._closed = True
            for row in self._active.values():
                row["cancel"].set()

    def _directory(self, run_id):
        if self.root.is_symlink():
            raise BridgeError("CODEX_WORKSPACE", "Codex workspace root cannot be a symlink.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = self.root / run_id
        if directory.exists() or directory.is_symlink():
            raise BridgeError("CODEX_WORKSPACE", "Use a new Codex run ID; existing workspaces are never overwritten.", 409)
        directory.mkdir(mode=0o700)
        runtimes = self.root / ".harness-runtimes"
        if runtimes.is_symlink():
            raise BridgeError("CODEX_WORKSPACE", "Codex runtime root cannot be a symlink.")
        runtimes.mkdir(mode=0o700, exist_ok=True)
        if os.name != "nt" and (runtimes.stat().st_uid != os.getuid() or stat.S_IMODE(runtimes.stat().st_mode) & 0o077):
            raise BridgeError("CODEX_WORKSPACE", "Codex runtime root must be user-owned with permissions 0700.")
        home = runtimes / run_id
        home.mkdir(mode=0o700)
        return directory.resolve(), home.resolve()

    def _checkpoint(self, workspace_id, value=None):
        if not isinstance(workspace_id, str) or not RUN_ID.fullmatch(workspace_id):
            raise BridgeError("CODEX_RESUME", "A valid original workspace run ID is required.")
        directory = self.root / ".harness-checkpoints"
        if self.root.is_symlink() or directory.is_symlink():
            raise BridgeError("CODEX_RESUME", "Checkpoint storage cannot be a symlink.")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt" and (directory.stat().st_uid != os.getuid() or stat.S_IMODE(directory.stat().st_mode) & 0o077):
            raise BridgeError("CODEX_RESUME", "Checkpoint directory must be user-owned with permissions 0700.")
        path = directory / (workspace_id + ".json")
        with self.plan.store.locked():
            state = self.plan.store.read()
            if "codex_checkpoint_key" not in state:
                state["codex_checkpoint_key"] = secrets.token_hex(32)
                self.plan.store.write(state)
            try:
                key = bytes.fromhex(state["codex_checkpoint_key"])
                if len(key) != 32:
                    raise ValueError()
            except (ValueError, TypeError):
                raise BridgeError("CODEX_RESUME", "Checkpoint signing state is invalid.", 409) from None
        if value is None:
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as source:
                    if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                        raise ValueError()
                    raw = source.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise ValueError()
                envelope = strict_json(raw)
                result = envelope.get("payload")
                expected = hmac.new(key, json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(), hashlib.sha256).hexdigest()
                if not isinstance(envelope.get("hmac_sha256"), str) or not hmac.compare_digest(envelope["hmac_sha256"], expected):
                    raise ValueError()
                if not isinstance(result, dict) or result.get("schema") != 1 or result.get("workspace_id") != workspace_id:
                    raise ValueError()
                return result
            except (OSError, ValueError, TypeError, AttributeError):
                raise BridgeError("CODEX_RESUME", "No valid saved Codex checkpoint exists for this run.", 409) from None
        temp = directory / (".checkpoint-" + secrets.token_hex(8))
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "wb") as target:
                signature = hmac.new(key, json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(), hashlib.sha256).hexdigest()
                target.write(json.dumps({"payload": value, "hmac_sha256": signature}, allow_nan=False).encode())
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def resume(self, data, on_event=None, *, expected_execution_identity=None, cancelled_before_dispatch=None):
        if not isinstance(data, dict) or not isinstance(data.get("resume_run_id"), str):
            raise BridgeError("CODEX_RESUME", "Supply resume_run_id for the original Codex workspace and a fresh run_id.")
        return self.generate(data, on_event=on_event, expected_execution_identity=expected_execution_identity,
                             cancelled_before_dispatch=cancelled_before_dispatch)

    def _workspace_lock(self, workspace_id):
        directory = self.root / ".harness-checkpoints"
        if not isinstance(workspace_id, str) or not RUN_ID.fullmatch(workspace_id):
            raise BridgeError("CODEX_RESUME", "Use the original workspace run ID.")
        if self.root.is_symlink() or directory.is_symlink():
            raise BridgeError("CODEX_RESUME", "Checkpoint storage cannot be a symlink.")
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / (workspace_id + ".lock")
        if path.is_symlink():
            raise BridgeError("CODEX_RESUME", "Checkpoint lock cannot be a symlink.")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError()
            if os.name == "nt":
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            os.close(fd)
            raise BridgeError("CODEX_BUSY", "This Codex workspace is already in use or cannot be safely locked.", 409) from None

    def _command(self, directory, writable):
        # Isolated CODEX_HOME excludes existing MCP/app configuration and credentials.
        values = {
            "model_provider": '"openai_chatgpt_plan"',
            "model_providers.openai_chatgpt_plan.name": '"ChatGPT plan"',
            "model_providers.openai_chatgpt_plan.base_url": json.dumps(RESOURCE),
            "model_providers.openai_chatgpt_plan.env_key": '"ACCESS_TOKEN"',
            "model_providers.openai_chatgpt_plan.wire_api": '"responses"',
            "model_providers.openai_chatgpt_plan.requires_openai_auth": "false",
            "model_providers.openai_chatgpt_plan.supports_websockets": "false",
            "shell_environment_policy.inherit": '"none"',
            "shell_environment_policy.exclude": '["ACCESS_TOKEN", "OPENAI_API_KEY", "CHATGPT_ACCESS_TOKEN"]',
            "web_search": '"disabled"',
        }
        args = [self.binary, "app-server", "--listen", "stdio://"]
        for key, value in values.items():
            args += ["-c", key + "=" + value]
        return args + permission_overrides(directory, writable, self.binary)

    def generate(self, data, on_event=None, *, expected_execution_identity=None, cancelled_before_dispatch=None):
        self.gate()
        with self.plan._lock:
            self.plan._check_execution_identity(expected_execution_identity)
        if not isinstance(data, dict) or set(data) - {"provider", "model", "prompt", "run_id", "max_output_tokens", "json_mode", "stream", "resume_run_id"}:
            raise BridgeError("INPUT", "Unsupported Codex generation fields.")
        model, prompt, run_id = data.get("model"), data.get("prompt"), data.get("run_id")
        if not isinstance(model, str) or not ID.fullmatch(model) or not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > MAX_BODY // 2 or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise BridgeError("INPUT", "Provide a valid Codex model, prompt and unique run ID.")
        if data.get("json_mode") is True:
            raise BridgeError("CAPABILITY", "This Codex engineering path returns text and artifacts; structured-model output is not claimed.")
        with self._lock:
            self.plan._check_pre_dispatch_cancellation(cancelled_before_dispatch)
            if self._active or run_id in self._runs:
                raise BridgeError("BUSY", "Wait for the active Codex turn and use a new run ID.", 409)
            cancel = threading.Event()
            self._runs.add(run_id)
            self._active[run_id] = {"cancel": cancel}
        process, account, checkpoint, workspace_id, workspace_lock = None, None, None, None, None
        events = queue.Queue(maxsize=128)
        try:
            with self.plan._lock:
                self.plan._check_execution_identity(expected_execution_identity)
                account = self.plan._account()
            if model not in {row["id"] for row in self.plan._discover_account(account)["models"]}:
                raise BridgeError("CAPABILITY", "This model is not in the selected account catalog.")
            # The plan service's request guard also applies to Codex; this is one
            # turn, which may contain several internal model calls and tool actions.
            with self.plan._lock:
                self.plan._check_execution_identity(expected_execution_identity)
                if self.plan._quota_blocked or self.plan.requests_started >= self.plan.request_limit:
                    raise BridgeError("CHATGPT_LIMIT", "The local ChatGPT request/turn limit is reached.", 429)
                if self.plan._active:
                    raise BridgeError("BUSY", "Another ChatGPT request is active.", 429)
                self.plan._active["codex:" + run_id] = cancel
            workspace_id = data.get("resume_run_id") or run_id
            writable = self.config.get("allow_workspace_write") is True
            if data.get("resume_run_id"):
                workspace_lock = self._workspace_lock(workspace_id)
                checkpoint = self._checkpoint(workspace_id)
                expected_identity = hashlib.sha256(account["subject"].encode()).hexdigest()
                if checkpoint.get("client_id") != account["client_id"] or checkpoint.get("subject_sha256") != expected_identity:
                    raise BridgeError("CODEX_RESUME_ACCOUNT", "Reconnect the original ChatGPT account registration before resuming this thread.", 403)
                if checkpoint.get("model") != model:
                    raise BridgeError("CODEX_RESUME_MODEL", "Resume with the originally selected model; use a new workspace for a different model.", 409)
                if not isinstance(checkpoint.get("attempt_ids"), list) or run_id in checkpoint["attempt_ids"]:
                    raise BridgeError("RUN_ID", "This Codex attempt ID is already recorded or its checkpoint is invalid.", 409)
                if not isinstance(checkpoint.get("thread_id"), str) or not RUN_ID.fullmatch(checkpoint["thread_id"]):
                    raise BridgeError("CODEX_RESUME", "Saved Codex thread ID is invalid.", 409)
                previous = checkpoint.get("sandbox")
                if previous not in {"read-only", "workspace-write"} or (previous == "workspace-write" and not writable):
                    raise BridgeError("CODEX_RESUME_PERMISSION", "Restore the original explicitly authorized workspace policy before resuming.", 403)
                writable = previous == "workspace-write"  # Resumption never increases original rights.
                directory = self.root / workspace_id
                runtimes = self.root / ".harness-runtimes"
                if runtimes.is_symlink():
                    raise BridgeError("CODEX_RESUME", "Codex runtime root cannot be a symlink.")
                codex_home = runtimes / workspace_id
                if directory.is_symlink() or codex_home.is_symlink() or not directory.is_dir() or not codex_home.is_dir():
                    raise BridgeError("CODEX_RESUME", "The original isolated workspace/runtime is unavailable.", 409)
                directory, codex_home = directory.resolve(), codex_home.resolve()
                if codex_home.is_relative_to(directory):
                    raise BridgeError("CODEX_RESUME", "Codex runtime must remain outside the writable workspace.", 409)
                if checkpoint.get("workspace_path") != str(directory) or checkpoint.get("codex_home") != str(codex_home):
                    raise BridgeError("CODEX_RESUME_WORKSPACE", "The original signed Codex workspace location changed. Start a fresh run at the new location.", 409)
            else:
                directory, codex_home = self._directory(run_id)
                checkpoint = {"schema": 1, "workspace_id": workspace_id, "client_id": account["client_id"],
                              "subject_sha256": hashlib.sha256(account["subject"].encode()).hexdigest(),
                              "sandbox": "workspace-write" if writable else "read-only",
                              "workspace_path": str(directory), "codex_home": str(codex_home)}
                workspace_lock = self._workspace_lock(workspace_id)
            env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG") if key in os.environ}
            env.update({"CODEX_HOME": str(codex_home), "HOME": str(codex_home), "ACCESS_TOKEN": account["access_token"]})
            command = self._command(directory, writable)
            self.runtime_probe(command, directory, codex_home, writable)
            with self.plan._lock, self.plan.store.locked():
                current = self.plan.store.read()
                self.plan._check_execution_identity(expected_execution_identity, state=current)
                self.plan._check_pre_dispatch_cancellation(cancelled_before_dispatch)
                selected = current["accounts"].get(current.get("active"), {})
                if cancel.is_set() or current.get("active") != account["client_id"] or selected.get("access_token") != account["access_token"]:
                    raise BridgeError("CANCELLED", "Codex authorization changed or turn was cancelled before process launch.", 409)
                self.plan.requests_started += 1
                process = self.process_factory(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                               text=True, encoding="utf-8", bufsize=1, cwd=str(directory), env=env)

            def reader():
                try:
                    for line in process.stdout:
                        if len(line.encode()) > MAX_BODY:
                            events.put(BridgeError("CODEX_SIZE", "Codex event exceeded the local resource limit.", 502), timeout=1)
                            return
                        events.put(strict_json(line), timeout=1)
                except (BridgeError, UnicodeError, OSError):
                    try:
                        events.put(BridgeError("CODEX_STREAM", "Codex protocol stream could not be read.", 502), timeout=1)
                    except queue.Full:
                        process.terminate()
                except queue.Full:
                    process.terminate()
                finally:
                    try:
                        events.put(None, timeout=1)
                    except queue.Full:
                        pass

            threading.Thread(target=reader, daemon=True).start()

            def send(method=None, params=None, ident=None, result=None):
                message = {"id": ident} if ident is not None else {}
                if method:
                    message.update(method=method, params=params or {})
                else:
                    message["result"] = result
                process.stdin.write(json.dumps(message, allow_nan=False) + "\n")
                process.stdin.flush()

            send("initialize", {"clientInfo": {"name": APP_NAME, "title": "ALPHA GENESIS HARNESS", "version": "0.3.0"}, "capabilities": {"experimentalApi": True}}, 0)
            thread_id, turn_id, text, completed, interrupted = None, None, "", False, None
            agent_messages = _AgentMessages()
            total = 0
            while True:
                if cancel.is_set():
                    if interrupted is None:
                        interrupted = time.monotonic()
                        if thread_id and turn_id:
                            send("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, 90)
                        else:
                            raise BridgeError("CANCELLED", "Codex turn cancelled before inference could start.", 409)
                    if time.monotonic() - interrupted > 3:
                        raise BridgeError("CANCELLED", "Codex turn cancelled; upstream usage may remain.", 409)
                try:
                    message = events.get(timeout=0.2)
                except queue.Empty:
                    if process.poll() is not None:
                        raise BridgeError("CODEX_EXIT", "Codex exited without a completed turn.", 502)
                    continue
                if message is None:
                    raise BridgeError("CODEX_INTERRUPTED", "Codex stream ended without turn/completed.", 502)
                if isinstance(message, BridgeError):
                    raise message
                if not isinstance(message, dict):
                    raise BridgeError("CODEX_PROTOCOL", "Codex returned a malformed protocol message.", 502)
                total += len(json.dumps(message))
                if total > MAX_RESPONSE:
                    raise BridgeError("CODEX_SIZE", "Codex protocol output exceeded the local resource limit.", 502)
                if message.get("error"):
                    raise BridgeError("CODEX_RPC", "Codex rejected the request. Check the installed version, model, authorization and sandbox support.", 502)
                if message.get("id") == 0 and "result" in message:
                    send("initialized")
                    params = {"model": model, "cwd": str(directory), "approvalPolicy": "never", "permissions": PROFILE}
                    if data.get("resume_run_id"):
                        params["threadId"] = checkpoint["thread_id"]
                    send("thread/resume" if data.get("resume_run_id") else "thread/start", params, 1)
                elif message.get("id") == 1 and "result" in message:
                    if message["result"].get("activePermissionProfile", {}).get("id") != PROFILE:
                        raise BridgeError("CODEX_PROFILE", "Codex did not confirm the requested isolated permission profile.", 502)
                    thread_id = message["result"].get("thread", {}).get("id")
                    if not isinstance(thread_id, str) or not thread_id:
                        raise BridgeError("CODEX_PROTOCOL", "Codex did not supply a thread ID.", 502)
                    if data.get("resume_run_id") and thread_id != checkpoint["thread_id"]:
                        raise BridgeError("CODEX_PROTOCOL", "Codex returned a different thread during resume.", 502)
                    checkpoint.update(thread_id=thread_id, last_run_id=run_id, status="running", model=model,
                                      attempt_ids=checkpoint.get("attempt_ids", []) + [run_id])
                    self._checkpoint(workspace_id, checkpoint)
                    send("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": prompt}], "model": model,
                                         "cwd": str(directory), "approvalPolicy": "never", "permissions": PROFILE}, 2)
                elif message.get("id") == 2 and "result" in message:
                    turn_id = message["result"].get("turn", {}).get("id")
                elif message.get("method") in {"item/agentMessage/delta", "item/started", "item/completed"}:
                    if message.get("params", {}).get("threadId") != thread_id or message.get("params", {}).get("turnId") != turn_id or turn_id is None:
                        raise BridgeError("CODEX_PROTOCOL", "Codex output did not match the active thread and turn.", 502)
                    if message["method"] == "item/agentMessage/delta":
                        agent_messages.delta(message["params"])
                        if on_event:
                            on_event({"type": "progress", "provider": "codex", "received_characters": agent_messages.received_characters})
                    else:
                        agent_messages.snapshot(message["params"].get("item"), completed=message["method"] == "item/completed")
                elif message.get("method") == "turn/completed":
                    params = message.get("params", {})
                    if params.get("threadId") != thread_id or params.get("turn", {}).get("id") != turn_id or turn_id is None:
                        raise BridgeError("CODEX_PROTOCOL", "Codex completion did not match the active thread and turn.", 502)
                    if cancel.is_set() or params.get("turn", {}).get("status") != "completed":
                        raise BridgeError("CODEX_INCOMPLETE", "Codex turn failed or was interrupted; no completed result was accepted.", 502)
                    items = params["turn"].get("items", [])
                    if not isinstance(items, list):
                        raise BridgeError("CODEX_PROTOCOL", "Codex completion returned malformed turn items.", 502)
                    for item in items:
                        agent_messages.snapshot(item, completed=True)
                    text = agent_messages.final_text()
                    completed = True
                    break
                elif message.get("method") and "id" in message:
                    # No external action, unknown tool, authentication or approval
                    # request is automatically accepted by this integration.
                    if message["method"].endswith("requestApproval"):
                        send(ident=message["id"], result={"decision": "decline"})
                    else:
                        process.stdin.write(json.dumps({"id": message["id"], "error": {"code": -32601, "message": "Unsupported server request; no permission granted."}}) + "\n")
                        process.stdin.flush()
            if not completed or not text.strip():
                raise BridgeError("CODEX_EMPTY", "Codex completed without a terminal or legacy message result.", 502)
            checkpoint["status"] = "completed"
            self._checkpoint(workspace_id, checkpoint)
            for field in ("access_token", "refresh_token", "id_token"):
                if account.get(field):
                    text = text.replace(account[field], "[credential redacted]")
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            artifacts = []
            for path in sorted(directory.rglob("*")):
                if ".codex-runtime" in path.relative_to(directory).parts or path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory):
                    continue
                raw = self._read_artifact(directory, path.relative_to(directory))
                if raw is None:
                    continue
                if any(account.get(key, "").encode() in raw for key in ("access_token", "refresh_token", "id_token") if account.get(key)):
                    continue  # Never export an artifact containing a credential.
                artifacts.append({"path": path.relative_to(directory).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            if on_event:
                on_event({"type": "delta", "provider": "codex", "delta": text})
            return {"run_id": run_id, "provider": "codex", "model": model, "text": text, "thread_id": thread_id,
                    "artifacts": artifacts, "workspace": str(directory), "resume_run_id": workspace_id,
                    "usage": {"input_tokens": None, "output_tokens": None},
                    "cost": {"currency": None, "amount": None, "accounted": None, "basis": "chatgpt_plan_codex_turn", "attempts": 1, "complete_cost_known": False},
                    "qualification": "LIVE_CODEX_TURN_NOT_INDEPENDENT_VERIFICATION"}
        finally:
            if workspace_lock is not None and checkpoint and checkpoint.get("thread_id") and checkpoint.get("status") != "completed":
                checkpoint["status"] = "interrupted"
                try:
                    self._checkpoint(workspace_id, checkpoint)
                except (BridgeError, OSError):
                    pass  # Cleanup must still stop the child and release locks.
            if process:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                for pipe in (process.stdin, process.stdout):
                    if pipe:
                        pipe.close()
            with self._lock:
                self._active.pop(run_id, None)
            with self.plan._lock:
                self.plan._active.pop("codex:" + run_id, None)
            if workspace_lock is not None:
                os.close(workspace_lock)

    @staticmethod
    def _read_artifact(directory, relative):
        # Open every path component without following links. On platforms without
        # descriptor-relative no-follow opens, fail closed for automatic exports.
        if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
            return None
        opened = []
        try:
            current = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened.append(current)
            for part in relative.parts[:-1]:
                current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                opened.append(current)
            fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESPONSE:
                    return None
                raw = source.read(MAX_RESPONSE + 1)
                return raw if len(raw) <= MAX_RESPONSE else None
        except OSError:
            return None
        finally:
            for fd in reversed(opened):
                os.close(fd)
