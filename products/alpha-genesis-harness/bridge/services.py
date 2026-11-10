# SPDX-License-Identifier: Apache-2.0
"""One explicit routing boundary; subscription allowances never become API dollars."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import threading

from .adapters import BridgeError, Runtime


class AccessRuntime:
    def __init__(self, runtime=None, config=None, private_root=None):
        self.base = runtime or Runtime(config)
        self.config = config or {}
        self.private_root = Path(private_root or Path.home() / ".alpha-genesis-harness")
        self._services = {}
        self._lock = threading.RLock()

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

    def generate(self, data, on_event=None):
        name = data.get("provider") if isinstance(data, dict) else None
        if name in {"chatgpt", "codex"}:
            self._network_allowed()
            return self.service(name).generate(data, on_event=on_event)
        if isinstance(name, str) and self.base.provider(name).remote:
            self._network_allowed()
        if on_event is None:
            return self.base.generate(data)
        return self.base.generate(data, on_event=on_event)

    def discover(self, ident):
        if ident in {"chatgpt", "codex"}:
            self._network_allowed()
            return self.service(ident).discover()
        if self.base.provider(ident).remote:
            self._network_allowed()
        return self.base.discover(ident)

    def cancel(self, run_id):
        results = [self.base.cancel(run_id)]
        for service in tuple(self._services.values()):
            results.append(service.cancel(run_id))
        return {"run_id": run_id, "cancelled": any(r.get("cancelled") for r in results),
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
        for service in tuple(self._services.values()):
            close = getattr(service, "close", None)
            if close:
                close()
