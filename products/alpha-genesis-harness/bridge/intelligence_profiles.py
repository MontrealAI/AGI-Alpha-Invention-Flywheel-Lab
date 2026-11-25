# SPDX-License-Identifier: Apache-2.0
"""Paired local discovery and verified preferences on the native HARNESS runtime."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import threading
from time import monotonic
from urllib.parse import urlsplit

from .adapters import BridgeError, ID, Provider, strict_json
from .onboarding import PRESETS, _endpoint
from .output_schema import SchemaError, validate_output
from .workflows import _atomic, _regular, digest, encoded


ENGINES = ("ollama", "lm-studio", "llama-cpp", "vllm")
LAUNCHERS = {"ollama": ("ollama",), "lm-studio": ("lms", "llmster"),
             "llama-cpp": ("llama-server",), "vllm": ("vllm",)}
GUIDES = {"ollama": "https://ollama.com/download", "lm-studio": "https://lmstudio.ai/download",
          "llama-cpp": "https://github.com/ggml-org/llama.cpp/releases",
          "vllm": "https://docs.vllm.ai/en/latest/getting_started/installation/"}
PREFERENCE = "frontier-local-intelligence/v1"
MODES = ("local", "hybrid")
HASH = re.compile(r"[0-9a-f]{64}\Z")
PROBE_PROMPT = 'Connection check. Return the integer 42 in the JSON field "answer". Follow the required output format exactly.'
PROBE_SCHEMA = {"type": "object", "properties": {"answer": {"type": "integer"}},
                "required": ["answer"], "additionalProperties": False}
READINESS_KINDS = ("json_schema", "json", "prompt_json")


def _require(condition, code, message, status=400):
    if not condition:
        raise BridgeError(code, message, status)


def _local_endpoint(provider):
    part = urlsplit(provider.base)
    return (provider.kind in {"openai", "ollama"} and not provider.remote and not provider.key and not provider.key_env
            and part.scheme == "http" and part.hostname == "127.0.0.1" and part.port is not None)


def _managed_socket(provider):
    part = urlsplit(provider.base)
    if part.scheme == "http" and part.hostname in {"127.0.0.1", "localhost"}:
        return part.port or 80
    return None


def _model_policy(model):
    if model is None:
        return {"input_per_million": "0", "output_per_million": "0", "max_output_tokens": 4096,
                "input_token_overhead": 256, "context_window": None,
                "json_mode": True, "json_schema": True, "streaming": False, "tool_calling": False}
    return {"input_per_million": str(model.input_price), "output_per_million": str(model.output_price),
            "max_output_tokens": model.max_output_tokens, "input_token_overhead": model.input_token_overhead,
            "context_window": model.context_window, "json_mode": model.json_mode, "json_schema": model.json_schema,
            "streaming": model.streaming, "tool_calling": model.tool_calling}


def _format(policy):
    if policy["json_schema"]:
        return "json_schema"
    return "json" if policy["json_mode"] else "prompt_json"


def _windows_memory():
    import ctypes
    from ctypes.wintypes import DWORD

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", DWORD), ("load", DWORD),
                    ("physical_total", ctypes.c_ulonglong), ("physical_available", ctypes.c_ulonglong),
                    ("pagefile_total", ctypes.c_ulonglong), ("pagefile_available", ctypes.c_ulonglong),
                    ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong),
                    ("extended_virtual_available", ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return status.physical_total, status.physical_available
    return None, None


def _host_memory(system):
    if system == "Windows":
        return _windows_memory()
    total, available = None, None
    try:
        size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        total = pages * size if pages > 0 and size > 0 else None
        pages = os.sysconf("SC_AVPHYS_PAGES")
        available = pages * size if pages >= 0 and size > 0 else None
    except (AttributeError, OSError, ValueError):
        pass
    if system == "Darwin" and total is None:
        try:
            total = int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"],
                                                stderr=subprocess.DEVNULL, timeout=2).strip()) or None
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    if system == "Linux":
        try:
            with Path("/proc/meminfo").open(encoding="ascii") as source:
                for line in source:
                    if line.startswith("MemAvailable:"):
                        available = int(line.split()[1]) * 1024
                        break
        except (OSError, ValueError, IndexError):
            pass
    return total, available


def _launcher_found(engine, system):
    if any(shutil.which(executable) for executable in LAUNCHERS[engine]):
        return True
    if engine == "lm-studio":
        suffix = ".exe" if system == "Windows" else ""
        return any((Path.home() / ".lmstudio" / "bin" / (name + suffix)).is_file() for name in LAUNCHERS[engine])
    if system == "Darwin" and engine == "ollama":
        app = Path("Ollama.app/Contents/Resources/ollama")
        return any((location / app).is_file() for location in (Path("/Applications"), Path.home() / "Applications"))
    return False


def _host_info(root):
    system = platform.system()
    total, available = _host_memory(system)
    try:
        storage = shutil.disk_usage(next(p for p in (root, *root.parents) if p.is_dir())).free
    except (OSError, StopIteration):
        storage = None
    engines = [{"engine": engine, "label": PRESETS[engine]["label"], "installation": GUIDES[engine],
                "launcher_found": _launcher_found(engine, system)}
               for engine in ENGINES]
    return {"system": system, "architecture": platform.machine(), "logical_cpus": os.cpu_count(),
            "physical_memory_bytes": total, "available_memory_bytes": available,
            "available_workspace_bytes": storage, "engines": engines}


@dataclass(frozen=True)
class _Catalog:
    engine: str
    provider: Provider
    configured: bool


class _LocalProvider(Provider):
    def __init__(self, ident, raw, model, upstream_model):
        super().__init__(ident, raw)
        self.model, self.upstream_model = model, upstream_model

    def request(self, model, *args, **kwargs):
        url, body = super().request(model, *args, **kwargs)
        body["model"] = self.upstream_model
        return url, body

    def models_response(self, response):
        rows = response.get("models" if self.kind == "ollama" else "data", [])
        listed = isinstance(rows, list) and any(isinstance(row, dict) and self.upstream_model ==
                                               row.get("id", row.get("name", row.get("model"))) for row in rows)
        return {"models": [{"id": self.model, "configured": True}] if listed else [], "has_more": False,
                "scope": "Exact upstream model identity reported by the selected local runtime."}


@dataclass(frozen=True)
class _Candidate:
    catalog: _Catalog
    model: str
    reported_digest: str | None

    @property
    def model_label(self):
        if self.model.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[/\\]", self.model):
            return self.model.replace("\\", "/").rsplit("/", 1)[-1] or "Local model"
        return self.model

    @property
    def model_id(self):
        if ID.fullmatch(self.model) and self.model_label == self.model:
            return self.model
        return "frontier-model-" + digest(self.model)

    def policy(self):
        return _model_policy(self.catalog.provider.models.get(self.model))

    def binding(self):
        provider = self.catalog.provider
        return digest({"endpoint": provider.base, "transport": provider.kind, "limit_field": provider.limit_field,
                       "model": self.model, "reported_digest": self.reported_digest, "policy": self.policy()})

    def route(self, observed_format):
        source = self.catalog.provider
        raw = self.policy()
        raw.update(json_schema=observed_format == "json_schema", json_mode=observed_format == "json",
                   streaming=False, tool_calling=False)
        ident = "frontier-local-" + digest([self.binding(), observed_format])
        return _LocalProvider(ident, {"kind": source.kind, "label": source.label, "base_url": source.base,
                                     "output_limit_field": source.limit_field, "models": {self.model_id: raw}},
                              self.model_id, self.model)


class IntelligenceProfiles:
    """One nonsecret preference, with opaque choices and per-endpoint runtime identities."""

    def __init__(self, local_connections):
        self.base = local_connections.base
        self.root = local_connections.root
        self.path = self.root / "frontier-intelligence-profile.json"
        self._lock = threading.RLock()
        self._catalog_key = secrets.token_bytes(32)
        self._choices = {}
        self._operation = False
        self._selected = self._read() if self.path.exists() or self.path.is_symlink() else None
        self._installed = {}
        self._verified = None
        self._verified_source = None

    def _read(self):
        _require(not self.path.is_symlink(), "INTELLIGENCE_SETTINGS", "Local preferences must be a private regular file.")
        row = strict_json(_regular(self.path, 16384))
        fields = {"format", "binding", "provider", "model", "model_label", "engine", "label", "mode", "max_output_tokens", "verification"}
        _require(isinstance(row, dict) and set(row) == fields and row.get("format") == PREFERENCE
                 and isinstance(row.get("binding"), str) and HASH.fullmatch(row["binding"])
                 and isinstance(row.get("model"), str) and ID.fullmatch(row["model"])
                 and isinstance(row.get("model_label"), str) and 0 < len(row["model_label"]) <= 512
                 and row.get("engine") in (*ENGINES, "configured") and row.get("mode") in MODES
                 and type(row.get("max_output_tokens")) is int and row["max_output_tokens"] >= 64
                 and isinstance(row["label"], str) and 0 < len(row["label"]) <= 100,
                 "INTELLIGENCE_SETTINGS", "The saved local preference is invalid.")
        verification = row["verification"]
        _require(isinstance(verification, dict) and set(verification) == {"at", "format", "elapsed_ms", "input_tokens", "output_tokens"}
                 and verification["format"] in READINESS_KINDS
                 and isinstance(verification["at"], str) and len(verification["at"]) <= 50
                 and all(v is None or (type(v) is int and v >= 0) for v in (verification["input_tokens"], verification["output_tokens"]))
                 and type(verification["elapsed_ms"]) is int and verification["elapsed_ms"] >= 0
                 and row["provider"] == "frontier-local-" + digest([row["binding"], verification["format"]]),
                 "INTELLIGENCE_SETTINGS", "The saved local readiness record is invalid.")
        return row

    def _save(self, row):
        _require(not any(p.is_symlink() for p in (self.root, *self.root.parents)),
                 "INTELLIGENCE_SETTINGS", "Local preferences need a private directory without symlink parents.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(self.root, 0o700)
        _atomic(self.path, encoded(row))

    def _view(self):
        if self._selected is None:
            return None
        row = self._selected
        source = self._verified_source
        ready = (self._verified is not None and self.base.providers.get(row["provider"]) is self._verified
                 and (source is None or self.base.providers.get(source.id) is source))
        return {key: row[key] for key in ("provider", "model", "model_label", "engine", "label", "mode", "max_output_tokens")} | {
            "ready": ready, "verification": dict(row["verification"]),
        }

    def status(self):
        with self._lock:
            return {"selection": self._view(), "modes": list(MODES), "remote_requests": False}

    def current(self):
        with self._lock:
            selected = self._view()
            return selected if selected and selected["ready"] else None

    def _routes(self):
        with self.base._lock:
            configured = tuple(entry for entry in self.base.providers.values() if not entry.id.startswith("frontier-local-"))
        managed = {_managed_socket(entry) for entry in configured}
        protected = {(_managed_socket(entry), urlsplit(entry.base).path) for entry in configured if entry.key or entry.key_env}
        explicit = []
        for entry in configured:
            if _local_endpoint(entry) and (_managed_socket(entry), urlsplit(entry.base).path) not in protected:
                engine = entry.id.removeprefix("local-")
                explicit.append(_Catalog(engine if engine in ENGINES else "configured", entry, True))
        defaults = []
        for engine in ENGINES:
            _, _, raw = _endpoint({"engine": engine})
            provider = Provider("local-" + engine, raw)
            if _managed_socket(provider) not in managed:
                defaults.append(_Catalog(engine, provider, False))
        return explicit + defaults

    def _catalog(self, catalog):
        provider = catalog.provider
        response = self.base.sender(provider.models_request(), provider.headers(), timeout=min(self.base.timeout, 2))
        _require(isinstance(response, dict), "PROVIDER_RESPONSE", "Invalid local model catalog.", 502)
        key = "models" if provider.kind == "ollama" else "data"
        rows = response.get(key)
        _require(isinstance(rows, list), "PROVIDER_RESPONSE", "Invalid local model catalog.", 502)
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ident = row.get("id", row.get("name", row.get("model")))
            if not isinstance(ident, str) or not 0 < len(ident) <= 512 or not ident.isprintable() or ident != ident.strip():
                continue
            if provider.kind == "ollama" and not ID.fullmatch(ident):
                continue
            if catalog.configured and ident not in provider.models:
                continue
            if (row.get("remote_host") or row.get("remote_model") or ident.lower().endswith((":cloud", "-cloud"))
                    or (provider.kind == "ollama" and (type(row.get("size")) is not int or row["size"] <= 0))):
                continue
            configured_model = provider.models.get(ident)
            if configured_model is not None and (configured_model.input_price or configured_model.output_price):
                continue
            policy = _model_policy(configured_model)
            if policy["max_output_tokens"] < 64:
                continue
            hint = row.get("digest")
            hint = hint.removeprefix("sha256:") if isinstance(hint, str) else ""
            stated_digest = hint if HASH.fullmatch(hint) else None
            result.append(_Candidate(catalog, ident, stated_digest))
        return result

    def _probe_catalog(self, catalog):
        try:
            return self._catalog(catalog), None
        except BridgeError as error:
            return [], error.code

    def discover(self, body, *, admit=lambda: None):
        _require(isinstance(body, dict) and body == {"consent": True} and body["consent"] is True,
                 "INTELLIGENCE_PERMISSION", "Allow this connector to look for supported local runtimes.", 403)
        admit()
        routes = self._routes()
        with ThreadPoolExecutor(max_workers=len(ENGINES)) as executor:
            catalogs = list(executor.map(self._probe_catalog, routes))
        admit()
        candidates, diagnostics = {}, []
        for route, (matches, error) in zip(routes, catalogs):
            diagnostics.append({"engine": route.engine, "label": route.provider.label,
                                "listed_models": len(matches), "catalog_error": error})
            for match in matches:
                ident = hmac.new(self._catalog_key, match.binding().encode("ascii"), hashlib.sha256).hexdigest()
                candidates[ident] = match
        with self._lock:
            self._choices = candidates
            results = [{"id": ident, "label": row.catalog.provider.label, "model": row.model_label,
                        "engine": row.catalog.engine, "configured": row.catalog.configured,
                        "selected": bool(self._selected and self._selected["binding"] == row.binding())}
                       for ident, row in candidates.items()]
        return {"candidates": results, "diagnostics": diagnostics, "host": _host_info(self.root)}

    def _probe(self, route, model, output_format, admit):
        limit = min(route.models[model].max_output_tokens, 128)
        marker = secrets.token_hex(6) if output_format == "json_schema" else None
        schema = None
        if marker:
            schema = dict(PROBE_SCHEMA, properties=dict(PROBE_SCHEMA["properties"], check={"type": "string", "const": marker}),
                          required=["answer", "check"])
        url, body = route.request(model, PROBE_PROMPT, limit, json_mode=output_format == "json", json_schema=schema)
        if route.kind == "ollama":
            body["options"]["temperature"] = 0
        else:
            body["temperature"] = 0
        probe_id = "frontier-readiness-" + secrets.token_hex(16)
        admit()
        with self.base._lock:
            _require(not self.base._active, "INTELLIGENCE_BUSY", "Finish active inference before testing another connection.", 409)
            self.base._active.add(probe_id)
        try:
            # Authority callbacks can acquire the pairing lock. Keep them outside runtime locks.
            admit()
            began = monotonic()
            reply = self.base.sender(url, route.headers(), body, timeout=min(self.base.timeout, 45))
            elapsed = round((monotonic() - began) * 1000)
            text, usage, tools = route.parse_result(reply)
            try:
                parsed = strict_json(text)
                validate_output(parsed, schema or PROBE_SCHEMA)
            except (BridgeError, SchemaError):
                raise BridgeError("INTELLIGENCE_PROBE_FORMAT", "The runtime did not demonstrate the requested output format.", 502) from None
            _require(type(parsed["answer"]) is int and parsed["answer"] == 42 and not tools, "INTELLIGENCE_PROBE_RESULT",
                     "The runtime did not complete the readiness check.", 502)
            return {"at": datetime.now(timezone.utc).isoformat(), "format": output_format,
                    "elapsed_ms": elapsed, "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]}
        finally:
            with self.base._lock:
                self.base._active.discard(probe_id)

    def _qualify(self, candidate, admit, saved_format):
        observed_formats = ((saved_format or _format(candidate.policy()),)
                            if saved_format or candidate.catalog.configured else READINESS_KINDS)
        for output_format in observed_formats:
            route = candidate.route(output_format)
            try:
                return route, self._probe(route, candidate.model_id, output_format, admit)
            except BridgeError as error:
                unsupported = error.code == "PROVIDER_HTTP" and str(error).startswith(("Provider HTTP 400.", "Provider HTTP 422."))
                if output_format == observed_formats[-1] or not (unsupported or error.code == "INTELLIGENCE_PROBE_FORMAT"):
                    raise

    def _resolve(self, candidate, mode, admit, output_format=None, saved=None):
        source = candidate.catalog.provider

        def recheck():
            admit()
            if candidate.catalog.configured:
                _require(self.base.providers.get(source.id) is source, "INTELLIGENCE_CANDIDATE_CHANGED",
                         "The local runtime changed during verification.", 409)

        with self._lock:
            _require(not self._operation, "INTELLIGENCE_BUSY", "A local connection check is already running.", 409)
            _require(saved is None or saved is self._selected, "INTELLIGENCE_CANDIDATE_CHANGED",
                     "The saved preference changed during reconnection.", 409)
            current = self._view()
            if saved is None and current and current["ready"] and current["mode"] == mode and self._selected["binding"] == candidate.binding():
                existing = current
            else:
                existing = None
            self._operation = True
        try:
            recheck()
            if existing is not None:
                return {"selection": existing}
            refreshed = self._catalog(candidate.catalog)
            _require(any(row.binding() == candidate.binding() for row in refreshed), "INTELLIGENCE_CANDIDATE_CHANGED",
                     "The chosen model changed. Refresh the local catalog.", 409)
            route, report = self._qualify(candidate, recheck, output_format)
            recheck()
            with self._lock, self.base._lock:
                _require(not self.base._active, "INTELLIGENCE_BUSY", "An inference request started before the profile could change.", 409)
                if candidate.catalog.configured:
                    _require(self.base.providers.get(source.id) is source, "INTELLIGENCE_CANDIDATE_CHANGED",
                             "The local runtime changed during verification.", 409)
                current_route = self.base.providers.get(route.id)
                _require(current_route is None or current_route is self._installed.get(route.id), "INTELLIGENCE_SETTINGS",
                         "The verified route conflicts with an existing configured provider.", 409)
                record = {"format": PREFERENCE, "binding": candidate.binding(), "provider": route.id, "model": candidate.model_id,
                          "model_label": candidate.model_label,
                          "engine": candidate.catalog.engine, "label": route.label, "mode": mode,
                          "max_output_tokens": route.models[candidate.model_id].max_output_tokens, "verification": report}
                self._save(record)
                existing = {name: entry for name, entry in self.base.providers.items() if self._installed.get(name) is not entry}
                self.base.providers = dict(existing, **{route.id: route})
                self._installed = {route.id: route}
                self._verified, self._selected = route, record
                self._verified_source = source if candidate.catalog.configured else None
                return {"selection": self._view()}
        finally:
            with self._lock:
                self._operation = False

    def connect(self, body, *, admit=lambda: None):
        _require(isinstance(body, dict) and set(body) == {"id", "consent", "mode"} and body["consent"] is True
                 and body["mode"] in MODES and isinstance(body["id"], str),
                 "INTELLIGENCE_PERMISSION", "Choose a listed local model and approve its readiness check.", 403)
        with self._lock:
            candidate = self._choices.get(body["id"])
        _require(candidate is not None, "INTELLIGENCE_CANDIDATE_CHANGED", "Refresh the local model catalog before selecting.", 409)
        return self._resolve(candidate, body["mode"], admit)

    def reconnect(self, body, *, admit=lambda: None):
        _require(isinstance(body, dict) and body == {"consent": True} and body["consent"] is True,
                 "INTELLIGENCE_PERMISSION", "Allow a check of your saved local preference.", 403)
        with self._lock:
            saved = self._selected
        admit()
        _require(saved is not None, "INTELLIGENCE_NOT_READY", "Choose a local model first.", 409)
        self.discover(body, admit=admit)
        with self._lock:
            match = next((row for row in self._choices.values() if row.binding() == saved["binding"]), None)
        _require(match is not None, "INTELLIGENCE_CANDIDATE_CHANGED", "The saved exact model is no longer listed.", 409)
        return self._resolve(match, saved["mode"], admit, saved["verification"]["format"], saved)

    def disconnect(self, body, *, admit=lambda: None):
        _require(isinstance(body, dict) and body == {"consent": True} and body["consent"] is True,
                 "INTELLIGENCE_PERMISSION", "Confirm removal of the saved local connection.", 403)
        admit()
        with self._lock, self.base._lock:
            _require(not self._operation and not self.base._active, "INTELLIGENCE_BUSY",
                     "Finish active inference before removing the saved connection.", 409)
            self.path.unlink(missing_ok=True)
            self.base.providers = {name: entry for name, entry in self.base.providers.items() if self._installed.get(name) is not entry}
            self._installed.clear()
            self._verified = self._verified_source = self._selected = None
            return {"selection": None}
