# SPDX-License-Identifier: Apache-2.0
"""Explicit, non-secret local model setup without editing application source.

Only numeric loopback endpoints are constructed. Settings never enable cloud
requests, change the session budget, or infer model capabilities from a name.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import threading

from .adapters import BridgeError, ID, Provider, strict_json
from .workflows import _atomic, _regular, encoded


PRESETS = {
    "ollama": {"label": "Ollama", "port": 11434, "kind": "ollama", "path": ""},
    "lm-studio": {"label": "LM Studio", "port": 1234, "kind": "openai", "path": "/v1"},
    "llama-cpp": {"label": "llama.cpp", "port": 8080, "kind": "openai", "path": "/v1"},
    "vllm": {"label": "vLLM", "port": 8000, "kind": "openai", "path": "/v1"},
    "mlx": {"label": "MLX compatible server", "port": 8080, "kind": "openai", "path": "/v1"},
    "custom": {"label": "Local OpenAI-compatible server", "port": 8080, "kind": "openai", "path": "/v1"},
}
CONNECT_FIELDS = {"engine", "port", "model", "consent", "json_mode", "streaming", "tool_calling",
                  "max_output_tokens", "context_window", "save"}
SAVED_FIELDS = CONNECT_FIELDS - {"consent", "save"}


def _check(ok, message, code="LOCAL_SETUP"):
    if not ok:
        raise BridgeError(code, message, 409 if code == "LOCAL_SETUP_BUSY" else 400)


def _endpoint(data):
    _check(isinstance(data, dict), "Local model setup must be an object.")
    engine = data.get("engine")
    _check(isinstance(engine, str) and engine in PRESETS, "Choose a supported local engine.")
    preset = PRESETS[engine]
    port = data.get("port", preset["port"])
    _check(type(port) is int and 1 <= port <= 65535, "Use a local server port between 1 and 65535.")
    raw = {"kind": preset["kind"], "label": preset["label"] + " · local",
           "base_url": f"http://127.0.0.1:{port}" + preset["path"],
           "output_limit_field": "max_tokens", "models": {}}
    return engine, port, raw


def _configuration(data):
    _check(isinstance(data, dict) and not set(data) - CONNECT_FIELDS, "Unsupported local setup fields. URLs, credentials and cloud settings are not accepted.")
    _check(data.get("consent") is True, "Explicit permission is required to connect this installed local model.")
    engine, port, raw = _endpoint(data)
    model = data.get("model")
    _check(isinstance(model, str) and ID.fullmatch(model), "Enter an exact installed model identifier.")
    for flag in ("json_mode", "streaming", "tool_calling", "save"):
        _check(flag not in data or type(data[flag]) is bool, f"{flag} must be true or false.")
    limit = data.get("max_output_tokens", 4096)
    context = data.get("context_window")
    _check(type(limit) is int and limit > 0, "Use a positive output-token limit.")
    _check(context is None or (type(context) is int and context >= limit), "Context window must cover the output-token limit, or remain unspecified.")
    model_config = {"input_per_million": 0, "output_per_million": 0,
                    "input_token_overhead": 4096, "max_output_tokens": limit,
                    "json_mode": data.get("json_mode", False), "streaming": data.get("streaming", False),
                    "tool_calling": data.get("tool_calling", False), "context_window": context}
    raw["models"][model] = model_config
    provider = Provider("local-" + engine, raw)
    _check(not provider.remote and not provider.key and not provider.key_env, "Local configuration must remain credential-free and on loopback.")
    saved = {"engine": engine, "port": port, "model": model, "max_output_tokens": limit,
             "context_window": context, **{flag: model_config[flag] for flag in ("json_mode", "streaming", "tool_calling")}}
    return provider, saved


class LocalConnectionService:
    """Installs local Provider objects while preserving all existing runtime guards."""
    def __init__(self, runtime, private_root):
        self.runtime = runtime
        self.base = getattr(runtime, "base", runtime)
        self.root = Path(private_root).expanduser().absolute()
        _check(not any(p.is_symlink() for p in [self.root, *self.root.parents]), "Local settings require a private directory without symlink parents.")
        _check(not self.root.exists() or self.root.is_dir(), "Local settings directory is unavailable.")
        self.path = self.root / "local-model-connections.json"
        self._lock = threading.RLock()
        self._saved = {}
        self._owned = {}
        if self.path.exists() or self.path.is_symlink():
            self._restore()

    def presets(self):
        return {"engines": [{"id": key, **value} for key, value in PRESETS.items()],
                "host": "127.0.0.1", "settings_saved": sorted({key[0] for key in self._saved}),
                "scope": "Connect an installed local server. No model download, cloud connection, credential, or paid request is performed. A trusted loopback server may itself forward requests; configure it for local inference."}

    def _restore(self):
        value = strict_json(_regular(self.path, 65536))
        _check(isinstance(value, dict) and set(value) == {"format", "version", "connections"}
               and value["format"] == "alpha-genesis-local-models" and value["version"] == 1
               and isinstance(value["connections"], list),
               "Saved local model settings are invalid.")
        providers, settings = {}, {}
        for row in value["connections"]:
            _check(isinstance(row, dict) and not set(row) - SAVED_FIELDS, "Saved local settings contain unsupported fields.")
            provider, saved = _configuration(dict(row, consent=True))
            key = (saved["engine"], saved["model"])
            _check(key not in settings, "Saved local model is duplicated.")
            _check(provider.id not in self.base.providers, "Saved local connection conflicts with an explicitly configured provider.")
            if provider.id in providers:
                previous = providers[provider.id]
                _check(previous.base == provider.base, "Saved local models for an engine must use one endpoint.")
                provider.models = dict(previous.models, **provider.models)
            providers[provider.id] = provider
            settings[key] = saved
        with self.base._lock:
            _check(not self.base._active, "Finish or cancel active inference before restoring local models.", "LOCAL_SETUP_BUSY")
            self.base.providers = dict(self.base.providers, **providers)
        self._owned = providers
        self._saved = settings

    def _persist(self, settings):
        _check(not any(p.is_symlink() for p in [self.root, *self.root.parents]), "Local settings require a private directory without symlink parents.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(self.root, 0o700)
        value = {"format": "alpha-genesis-local-models", "version": 1,
                 "connections": [settings[key] for key in sorted(settings)]}
        payload = encoded(value)
        _check(len(payload) <= 65536, "Saved model configuration exceeds 64 KiB. Remove unused connections before adding more.")
        _atomic(self.path, payload)

    def discover(self, data):
        _check(isinstance(data, dict) and not set(data) - {"engine", "port"}, "Discovery accepts only a local engine and port.")
        engine, port, raw = _endpoint(data)
        provider = Provider("local-" + engine, raw)
        response = self.base.sender(provider.models_request(), provider.headers(), timeout=self.base.timeout)
        _check(isinstance(response, dict), "The local server returned an invalid model catalog.", "PROVIDER_RESPONSE")
        result = provider.models_response(response)
        result.update(engine=engine, port=port, endpoint=provider.base)
        return result

    def connect(self, data):
        provider, saved = _configuration(data)
        engine = saved["engine"]
        with self._lock, self.base._lock:
            _check(not self.base._active, "Finish or cancel active inference before changing local models.", "LOCAL_SETUP_BUSY")
            previous = self.base.providers.get(provider.id)
            _check(previous is None or previous is self._owned.get(provider.id), "This provider ID belongs to the private configuration. Choose another preset or edit that configuration explicitly.")
            settings = copy.deepcopy(self._saved)
            if previous is not None and previous.base == provider.base:
                provider.models = dict(previous.models, **provider.models)
            else:
                settings = {key: value for key, value in settings.items() if key[0] != engine}
            key = (engine, saved["model"])
            if data.get("save", True):
                settings[key] = saved
            else:
                settings.pop(key, None)
            self._persist(settings)
            # Pointer replacement preserves concurrent readers' immutable provider objects.
            self.base.providers = dict(self.base.providers, **{provider.id: provider})
            self._owned[provider.id] = provider
            self._saved = settings
            status = self.runtime.status()
            result_provider = next(row for row in status["providers"] if row["id"] == provider.id)
        return {"connected": True, "provider": result_provider,
                "saved": key in settings, "inference_verified": False,
                "scope": "Explicit local configuration accepted. Run a workflow to verify inference. Zero token rates mean no configured API token charge; complete compute costs remain unknown.",
                "status": status}

    def disconnect(self, data):
        _check(isinstance(data, dict) and set(data) == {"engine"}, "Disconnect requires only the local engine identifier.")
        engine, _, _ = _endpoint(data)
        ident = "local-" + engine
        with self._lock, self.base._lock:
            _check(not self.base._active, "Finish or cancel active inference before removing a local model.", "LOCAL_SETUP_BUSY")
            provider = self.base.providers.get(ident)
            _check(provider is None or provider is self._owned.get(ident), "This provider belongs to the private configuration and cannot be removed here.")
            settings = {key: value for key, value in self._saved.items() if key[0] != engine}
            self._persist(settings)
            self.base.providers = {key: value for key, value in self.base.providers.items() if key != ident}
            self._saved = settings
            self._owned.pop(ident, None)
            status = self.runtime.status()
        return {"disconnected": True, "provider": ident, "status": status}
