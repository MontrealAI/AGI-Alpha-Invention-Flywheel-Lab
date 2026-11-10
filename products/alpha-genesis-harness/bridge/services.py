# SPDX-License-Identifier: Apache-2.0
"""One explicit routing boundary; subscription allowances never become API dollars."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import inspect
from pathlib import Path
from types import SimpleNamespace
import threading

from .adapters import BridgeError, Runtime


LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

_GATES_LOCK = threading.RLock()


class _ExecutionLease:
    def __init__(self, runtime, gate, route, identity, validate, cancelled):
        self.runtime, self.gate, self.route = runtime, gate, route
        self.identity, self.validate, self.cancelled = identity, validate, cancelled
        self.thread, self.used = threading.get_ident(), False


class _ExecutionGate:
    def __init__(self):
        self.condition = threading.Condition()
        self.waiters, self.active = [], {}

    @contextmanager
    def acquire(self, runtime, route, identity, validate, cancelled, capacity):
        ticket, owner = object(), threading.get_ident()
        lease = _ExecutionLease(runtime, self, route, identity, validate, cancelled)
        with self.condition:
            if owner in self.active:
                raise BridgeError("EXECUTION_REENTRANCY", "Nested generation cannot reuse an active execution slot.", 409)
            self.waiters.append(ticket)
        try:
            while True:
                # Never call authority/workflow callbacks under the queue lock.
                if cancelled():
                    raise BridgeError("CANCELLED", "Queued request cancelled before dispatch; no model attempt was started.", 409)
                validate()
                limit = capacity()
                if type(limit) is not int or limit < 1:
                    raise BridgeError("CONFIG", "Execution service must declare a positive concurrency capacity.")
                with self.condition:
                    if self.waiters[0] is ticket and len(self.active) < limit:
                        self.waiters.pop(0)
                        self.active[owner] = lease
                        break
                    self.condition.wait(0.05)
            validate()
            if cancelled():
                raise BridgeError("CANCELLED", "Queued request cancelled before dispatch; no model attempt was started.", 409)
            yield lease
        finally:
            with self.condition:
                if ticket in self.waiters:
                    self.waiters.remove(ticket)
                if self.active.get(owner) is lease:
                    self.active.pop(owner)
                self.condition.notify_all()


class AccessRuntime:
    def __init__(self, runtime=None, config=None, private_root=None):
        self.base = runtime or Runtime(config)
        self.config = config or {}
        self.private_root = Path(private_root or Path.home() / ".alpha-genesis-harness")
        self._services = {}
        self._lock = threading.RLock()
        self._queued_requests = {}
        self._closed = False

    def __getattr__(self, name):
        return getattr(self.base, name)

    def service(self, name):
        if name not in {"chatgpt", "codex"}:
            raise BridgeError("PROVIDER", "Unknown subscription execution service.")
        with self._lock:
            if name not in self._services:
                if name == "chatgpt":
                    from .chatgpt import ChatGPTPlanService
                    self._services[name] = ChatGPTPlanService(
                        self.config.get("chatgpt", {}), storage_path=self.private_root / "chatgpt")
                else:
                    from .codex import CodexService
                    self._services[name] = CodexService(self.config.get("codex", {}),
                                                       plan_service=self.service("chatgpt"),
                                                       workspace_root=self.private_root / "codex-workspaces")
            return self._services[name]

    def _network_allowed(self):
        if self.config.get("local_only") is True or getattr(self.base, "local_only", False):
            raise BridgeError("LOCAL_ONLY", "Local-only mode disables remote model connections.", 403)

    def provider(self, ident):
        if ident in {"chatgpt", "codex"}:
            return SimpleNamespace(remote=True, id=ident, kind=ident)
        return self.base.provider(ident)

    @contextmanager
    def execution_slot(self, data, cancelled=lambda: False):
        name = data.get("provider") if isinstance(data, dict) else None
        if name in {"chatgpt", "codex"}:
            self._network_allowed()
            selected = self.service(name)
            target = selected.plan if name == "codex" else selected
            identity = selected.execution_identity()
            current_identity = selected.execution_identity
            capacity = lambda: min(selected.max_concurrent, target.max_concurrent)
        else:
            provider = self.base.provider(name)
            if provider.remote:
                self._network_allowed()
            target = self.base
            identity = (id(target), id(getattr(target, "providers", {}).get(name)))
            current_identity = lambda: (id(self.base), id(getattr(self.base, "providers", {}).get(name)))
            capacity = lambda: getattr(target, "max_concurrent", 1)
        route = (name, data.get("model"))
        def validate():
            if self._closed:
                raise BridgeError("CANCELLED", "Execution runtime closed before dispatch.", 409)
            if name in {"chatgpt", "codex"} or provider.remote:
                self._network_allowed()
            if current_identity() != identity:
                raise BridgeError("EXECUTION_IDENTITY_CHANGED", "Selected connection or account changed while queued. Submit a new request explicitly.", 409)
        with _GATES_LOCK:
            if not hasattr(target, "_harness_execution_gate"):
                target._harness_execution_gate = _ExecutionGate()
            gate = target._harness_execution_gate
        with gate.acquire(self, route, identity, validate, cancelled, capacity) as lease:
            lease.expected_provider = provider if name not in {"chatgpt", "codex"} else None
            yield lease

    def generate(self, data, on_event=None, _admission=None):
        run_id = data.get("run_id") if isinstance(data, dict) else None
        cancel = threading.Event()
        with self._lock:
            if run_id in self._queued_requests:
                raise BridgeError("RUN_ID", "This run ID already has a queued or active request.", 409)
            self._queued_requests[run_id] = cancel
        try:
            if _admission is None:
                with self.execution_slot(data, cancelled=cancel.is_set) as admission:
                    return self._generate_admitted(data, on_event, admission, cancel)
            return self._generate_admitted(data, on_event, _admission, cancel)
        finally:
            with self._lock:
                self._queued_requests.pop(run_id, None)

    def _consume_admission(self, data, admission, cancel):
        route = (data.get("provider"), data.get("model"))
        try:
            if not isinstance(admission, _ExecutionLease) or admission.runtime is not self or admission.thread != threading.get_ident() or admission.route != route:
                raise BridgeError("EXECUTION_ADMISSION", "Generation needs its own matching execution admission.", 409)
            admission.validate()
            if cancel.is_set() or admission.cancelled():
                raise BridgeError("CANCELLED", "Queued request cancelled before dispatch.", 409)
            with admission.gate.condition:
                if admission.used or admission.gate.active.get(admission.thread) is not admission:
                    raise BridgeError("EXECUTION_ADMISSION", "Execution admission is expired or was already consumed.", 409)
                admission.used = True
        except BridgeError as error:
            error.pre_dispatch = True
            raise
        return route

    def _generate_admitted(self, data, on_event, admission, cancel):
        name = self._consume_admission(data, admission, cancel)[0]
        if name in {"chatgpt", "codex"}:
            return self.service(name).generate(data, on_event=on_event, expected_execution_identity=admission.identity,
                cancelled_before_dispatch=lambda: cancel.is_set() or admission.cancelled())
        options = {} if on_event is None else {"on_event": on_event}
        parameters = inspect.signature(self.base.generate).parameters
        if "cancelled_before_dispatch" in parameters:
            options["cancelled_before_dispatch"] = lambda: cancel.is_set() or admission.cancelled()
        if "expected_provider" in parameters:
            options["expected_provider"] = admission.expected_provider
        return self.base.generate(data, **options)

    def generate_admitted_external(self, data, generate, admission, on_event=None):
        """Trusted fixed constructors may dispatch a seeded target on this lease."""
        if data.get("provider") != "codex":
            error = BridgeError("EXECUTION_ADMISSION", "External admitted targets are limited to the authorized Codex constructor.", 409)
            error.pre_dispatch = True
            raise error
        self._consume_admission(data, admission, threading.Event())
        return generate(data, on_event=on_event, expected_execution_identity=admission.identity,
                        cancelled_before_dispatch=admission.cancelled)

    def resume(self, data, on_event=None):
        if not isinstance(data, dict) or not isinstance(data.get("resume_run_id"), str):
            raise BridgeError("CODEX_RESUME", "Supply resume_run_id for the original Codex workspace and a fresh run_id.")
        return self.generate(data, on_event=on_event)

    def discover(self, ident):
        if ident in {"chatgpt", "codex"}:
            self._network_allowed()
            return self.service(ident).discover()
        if self.base.provider(ident).remote:
            self._network_allowed()
        return self.base.discover(ident)

    def cancel(self, run_id):
        with self._lock:
            queued = self._queued_requests.get(run_id)
            if queued is not None:
                queued.set()
        results = [self.base.cancel(run_id)]
        for service in tuple(self._services.values()):
            results.append(service.cancel(run_id))
        return {"run_id": run_id, "cancelled": queued is not None or any(r.get("cancelled") for r in results),
                "notice": "Cancellation stops local acceptance. Upstream compute and usage may continue."}

    def redact(self, text):
        text = self.base.redact(text)
        for service in tuple(self._services.values()):
            if hasattr(service, "redact"):
                text = service.redact(text)
        return text

    def status(self):
        result = self.base.status()
        result["access_categories"] = {"api": "separately billed", "local": "local compute",
                                       "chatgpt": "eligible plan allowance", "codex": "separate Codex execution"}
        result["local_only"] = self.config.get("local_only") is True or getattr(self.base, "local_only", False)
        if result["local_only"]:
            for provider in result["providers"]:
                if self.base.provider(provider["id"]).remote:
                    provider.update(ready=False, reason="Local-only mode refuses this remote provider.")
        return result

    def close(self):
        with self._lock:
            self._closed = True
            for cancel in self._queued_requests.values():
                cancel.set()
        for service in tuple(self._services.values()):
            close = getattr(service, "close", None)
            if close:
                close()
