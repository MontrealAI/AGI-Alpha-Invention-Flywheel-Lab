# SPDX-License-Identifier: Apache-2.0
"""Text-only protocol adapters. No tools, automatic actions, credentials on disk or billing setup."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

MAX_BODY = 1_048_576  # HTTP resource safety, not a mission/business-scale ceiling.
MAX_RESPONSE = 4_194_304
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}\Z")
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
ENV_ID = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
KINDS = {"openai", "anthropic", "gemini", "ollama"}
DEFAULT_HOSTS = ["arxiv.org", "www.nature.com", "www.science.org", "docs.ollama.com",
                 "ai.google.dev", "developers.openai.com", "platform.claude.com",
                 "montrealai.github.io"]


class BridgeError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def decimal(value, name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BridgeError("CONFIG", f"{name} must be a finite nonnegative number.") from None
    if not number.is_finite() or number < 0:
        raise BridgeError("CONFIG", f"{name} must be a finite nonnegative number.")
    return number


def strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise BridgeError("JSON", "Duplicate JSON field.")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, TypeError):
        raise BridgeError("JSON", "A valid finite JSON object is required.") from None


def endpoint(value, local_only=False):
    try:
        part = urlsplit(value)
        port = part.port
    except (ValueError, TypeError):
        raise BridgeError("CONFIG", "Invalid provider endpoint.") from None
    if part.username or part.password or part.query or part.fragment or not part.hostname:
        raise BridgeError("CONFIG", "Provider endpoints cannot contain credentials, queries or fragments.")
    loopback = part.hostname in {"127.0.0.1", "localhost", "::1"}
    if local_only and not loopback:
        raise BridgeError("CONFIG", "Ollama endpoints must be local loopback addresses.")
    if part.scheme != "https" and not (part.scheme == "http" and loopback):
        raise BridgeError("CONFIG", "Provider connections require HTTPS or explicit loopback HTTP.")
    if port is not None and not 1 <= port <= 65535:
        raise BridgeError("CONFIG", "Invalid provider port.")
    return value.rstrip("/")


@dataclass(frozen=True)
class Model:
    id: str
    input_price: Decimal
    output_price: Decimal
    json_mode: bool
    max_output_tokens: int
    input_token_overhead: int


class Provider:
    def __init__(self, name, raw):
        if not ID.fullmatch(name) or not isinstance(raw, dict) or raw.get("kind") not in KINDS:
            raise BridgeError("CONFIG", "Invalid provider configuration.")
        self.id, self.kind = name, raw["kind"]
        self.label = str(raw.get("label", name))[:100]
        self.base = endpoint(raw["base_url"], self.kind == "ollama")
        self.key_env = raw.get("key_env", "")
        if self.key_env and not ENV_ID.fullmatch(self.key_env):
            raise BridgeError("CONFIG", "key_env must be an environment variable name, never a key.")
        self.key = os.environ.get(self.key_env, "") if self.key_env else ""
        self.version = raw.get("api_version", "2026-10-21")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.version):
            raise BridgeError("CONFIG", "Invalid Anthropic API version.")
        self.limit_field = raw.get("output_limit_field", "max_completion_tokens")
        if self.limit_field not in {"max_completion_tokens", "max_tokens"}:
            raise BridgeError("CONFIG", "Invalid compatible output limit field.")
        self.models = {}
        for name, model in raw.get("models", {}).items():
            if not ID.fullmatch(name) or not isinstance(model, dict):
                raise BridgeError("CONFIG", "Invalid model configuration.")
            # No default price or inferred free tier for remote providers.
            if "input_per_million" not in model or "output_per_million" not in model:
                raise BridgeError("CONFIG", "Declare both model prices in USD per million tokens.")
            bound = model.get("max_output_tokens", 4096)
            overhead = model.get("input_token_overhead", 4096)
            if type(bound) is not int or bound < 1 or type(overhead) is not int or overhead < 0:
                raise BridgeError("CONFIG", "Declare positive output and nonnegative input-overhead token bounds.")
            self.models[name] = Model(name, decimal(model["input_per_million"], "input price"),
                                      decimal(model["output_per_million"], "output price"),
                                      model.get("json_mode") is True, bound, overhead)

    @property
    def remote(self):
        return urlsplit(self.base).hostname not in {"localhost", "127.0.0.1", "::1"}

    @property
    def ready(self):
        return bool(self.models) and (bool(self.key) or not self.remote)

    def headers(self):
        result = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.kind == "anthropic":
            result["anthropic-version"] = self.version
            result["x-api-key"] = self.key
        elif self.kind == "gemini":
            result["x-goog-api-key"] = self.key
        elif self.key:
            result["Authorization"] = "Bearer " + self.key
        return result

    def request(self, model, prompt, limit, json_mode=False):
        if json_mode and not self.models[model].json_mode:
            raise BridgeError("CAPABILITY", "JSON output is not enabled for this model.")
        message = [{"role": "user", "content": prompt}]
        if self.kind == "openai":
            body = {"model": model, "messages": message, self.limit_field: limit, "stream": False}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            return self.base + "/chat/completions", body
        if self.kind == "anthropic":
            # JSON is prompt-constrained; no universal structured-output capability is asserted.
            if json_mode:
                raise BridgeError("CAPABILITY", "Use text output for this Anthropic adapter; validate imported JSON locally.")
            return self.base + "/messages", {"model": model, "messages": message, "max_tokens": limit, "stream": False}
        if self.kind == "gemini":
            config = {"maxOutputTokens": limit, "candidateCount": 1}
            if json_mode:
                config["responseMimeType"] = "application/json"
            return self.base + "/models/" + quote(model.removeprefix("models/"), safe="") + ":generateContent", {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
        body = {"model": model, "messages": message, "stream": False, "options": {"num_predict": limit}}
        if json_mode:
            body["format"] = "json"
        return self.base + "/api/chat", body

    def parse(self, response):
        try:
            if self.kind == "openai":
                text = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})
                counts = usage.get("prompt_tokens"), usage.get("completion_tokens")
            elif self.kind == "anthropic":
                text = "\n".join(v["text"] for v in response["content"] if v.get("type") == "text")
                usage = response.get("usage", {})
                # No explicit cache is requested. Still account cache input if returned.
                inp = usage.get("input_tokens")
                if type(inp) is int:
                    inp += usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                counts = inp, usage.get("output_tokens")
            elif self.kind == "gemini":
                text = "\n".join(p["text"] for p in response["candidates"][0]["content"]["parts"] if "text" in p)
                usage = response.get("usageMetadata", {})
                output = usage.get("candidatesTokenCount")
                if type(output) is int:
                    output += usage.get("thoughtsTokenCount", 0)
                counts = usage.get("promptTokenCount"), output
            else:
                text = response["message"]["content"]
                counts = response.get("prompt_eval_count"), response.get("eval_count")
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
            known = all(type(v) is int and v >= 0 for v in counts)
            return text, {"input_tokens": counts[0] if known else None,
                          "output_tokens": counts[1] if known else None}
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise BridgeError("PROVIDER_RESPONSE", "Provider returned no usable text. Its full reservation remains accounted.", 502) from None

    def models_request(self):
        return self.base + ("/api/tags" if self.kind == "ollama" else "/models")

    def models_response(self, response):
        rows = response.get("models" if self.kind in {"ollama", "gemini"} else "data", [])
        if not isinstance(rows, list):
            raise BridgeError("PROVIDER_RESPONSE", "Invalid model-list response.", 502)
        result = []
        for row in rows:
            ident = row.get("id", row.get("name", "")) if isinstance(row, dict) else ""
            if isinstance(ident, str) and ID.fullmatch(ident):
                result.append({"id": ident.removeprefix("models/") if self.kind == "gemini" else ident,
                               "configured": ident in self.models or ident.removeprefix("models/") in self.models})
        return {"models": result, "scope": "Provider-reported first page; listing does not prove generation access or model capability.",
                "has_more": bool(response.get("has_more") or response.get("nextPageToken"))}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transport(url, headers, body=None, timeout=60):
    """No proxy, redirect, cookies or exception-body echo (which could leak credentials)."""
    data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode() if body is not None else None
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(url, data=data, headers=headers), timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise BridgeError("PROVIDER_SIZE", "Provider response exceeded the safe response size.", 502)
            return strict_json(raw)
    except HTTPError as error:
        status = error.code
        error.close()
        raise BridgeError("PROVIDER_HTTP", f"Provider HTTP {status}. Check the selected model, access and configuration.", 502) from None
    except (URLError, TimeoutError, OSError, http.client.HTTPException):
        raise BridgeError("PROVIDER_CONNECTION", "Provider connection failed or timed out. Any sent attempt retains its cost reservation.", 502) from None


class Budget:
    """Atomic process-session spending guard; NOT a native enterprise account or billing ledger."""
    def __init__(self, limit):
        self.limit, self.committed, self.reserved = decimal(limit, "session budget"), Decimal(0), Decimal(0)
        self.locked = False
        self._lock = threading.RLock()

    def reserve(self, amount):
        with self._lock:
            if self.locked or self.committed + self.reserved + amount > self.limit:
                raise BridgeError("BUDGET", "The request would exceed the session spending guard, or a previous overrun locked it.", 409)
            self.reserved += amount

    def settle(self, reserved, amount):
        with self._lock:
            self.reserved -= reserved
            self.committed += amount
            if amount > reserved or self.committed > self.limit:
                self.locked = True

    def view(self):
        with self._lock:
            return {"currency": "USD", "limit": float(self.limit), "committed": float(self.committed),
                    "reserved": float(self.reserved), "remaining": float(max(Decimal(0), self.limit-self.committed-self.reserved)),
                    "locked": self.locked, "scope": "process-session"}


class Runtime:
    def __init__(self, config=None, sender=transport):
        config = config or {}
        if not isinstance(config, dict):
            raise BridgeError("CONFIG", "Configuration must be an object.")
        self.providers = {key: Provider(key, raw) for key, raw in config.get("providers", {}).items()}
        self.budget = Budget(config.get("session_budget_usd", 0))
        self.allow_paid = config.get("allow_paid_requests") is True
        self.timeout = config.get("timeout_seconds", 60)
        self.attempts = config.get("max_attempts", 1)
        self.max_concurrent = config.get("max_concurrent_requests", 2)
        if type(self.max_concurrent) is not int or self.max_concurrent < 1:
            raise BridgeError("CONFIG", "max_concurrent_requests must be a positive local resource limit.")
        if type(self.timeout) not in {int, float} or not 1 <= self.timeout <= 600:
            raise BridgeError("CONFIG", "timeout_seconds must be between 1 and 600 for each HTTP request.")
        if type(self.attempts) is not int or not 1 <= self.attempts <= 3:
            raise BridgeError("CONFIG", "max_attempts must be 1–3; each attempt reserves its full cost.")
        hosts = config.get("source_hosts", DEFAULT_HOSTS)
        if not isinstance(hosts, list) or any(not isinstance(h, str) or not re.fullmatch(r"[a-z0-9.-]+", h) for h in hosts):
            raise BridgeError("CONFIG", "source_hosts must be exact lowercase domain names.")
        self.source_hosts = frozenset(hosts)
        self.sender = sender
        self._runs, self._active, self._lock = {}, set(), threading.RLock()

    def redact(self, text):
        for provider in self.providers.values():
            if provider.key:
                text = text.replace(provider.key, "[credential redacted]")
        return text

    def status(self):
        rows = []
        for p in self.providers.values():
            reason = "Ready" if p.ready else "Configure a model and its credential environment variable where required."
            if p.remote and not self.allow_paid:
                reason = "Remote inference disabled. Explicit customer spending authorization is required in local configuration."
            rows.append({"id": p.id, "label": p.label, "kind": p.kind, "models": list(p.models),
                         "ready": p.ready and (self.allow_paid or not p.remote), "reason": reason,
                         "capabilities": {"text": True, "json": p.kind != "anthropic" and any(m.json_mode for m in p.models.values()),
                                          "streaming": False, "discovery": True},
                         "qualification": "CONTRACT_TESTED_ONLY"})
        return {"providers": rows, "budget": self.budget.view(), "source_hosts": sorted(self.source_hosts),
                "cost_notice": "User-declared token rates and conservative reservations are estimates, not a provider billing cap. Unknown compute, maintenance and external bills are not zero."}

    def provider(self, ident):
        if not isinstance(ident, str) or ident not in self.providers:
            raise BridgeError("PROVIDER", "Choose a configured provider.")
        return self.providers[ident]

    def discover(self, ident):
        p = self.provider(ident)
        # Model-list retrieval is still an authenticated remote API request,
        # even if the provider does not charge for metadata. Preserve the
        # explicit remote-request consent boundary before any sender call.
        if p.remote and not self.allow_paid:
            raise BridgeError("PERMISSION", "Remote model discovery is disabled until explicitly authorized in local configuration.", 403)
        if p.remote and not p.key:
            raise BridgeError("CREDENTIAL", "Set the provider credential in its configured environment variable.")
        response = self.sender(p.models_request(), p.headers(), timeout=self.timeout)
        return p.models_response(response)

    def cancel(self, ident):
        if not isinstance(ident, str) or not RUN_ID.fullmatch(ident):
            raise BridgeError("INPUT", "A valid run_id is required.")
        with self._lock:
            event = self._runs.get(ident) if ident in self._active else None
            if event is not None:
                event.set()
            return {"run_id": ident, "cancelled": event is not None,
                    "notice": "Cancellation stops retries and result acceptance; an upstream request may continue and incur charges."}

    def generate(self, data):
        if not isinstance(data, dict) or set(data) - {"provider", "model", "prompt", "max_output_tokens", "run_id", "json_mode"}:
            raise BridgeError("INPUT", "Unsupported generation fields; only text generation is permitted.")
        p = self.provider(data.get("provider"))
        model = data.get("model")
        prompt, run_id = data.get("prompt"), data.get("run_id")
        limit = data.get("max_output_tokens", 2048)
        if not isinstance(model, str) or model not in p.models or not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > MAX_BODY // 2:
            raise BridgeError("INPUT", "Choose a configured model and a nonempty prompt under 512 KiB.")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise BridgeError("INPUT", "A unique run_id using letters, digits, underscore or hyphen is required.")
        m = p.models[model]
        if type(limit) is not int or not 1 <= limit <= m.max_output_tokens:
            raise BridgeError("INPUT", "Output token limit exceeds the configured model limit.")
        if not p.ready:
            raise BridgeError("CREDENTIAL", "Provider credentials or models are missing.")
        if p.remote and not self.allow_paid:
            raise BridgeError("PERMISSION", "Remote inference is disabled until the customer explicitly authorizes it in local configuration.", 403)
        url, body = p.request(model, prompt, limit, data.get("json_mode") is True)
        # One token per UTF-8 byte plus declared framing overhead is conservative for
        # ordinary text tokenizers. Not a vendor-enforced billing guarantee.
        input_bound = len(prompt.encode("utf-8")) + m.input_token_overhead
        one = (Decimal(input_bound)*m.input_price + Decimal(limit)*m.output_price) / 1_000_000
        reserved = one*self.attempts
        with self._lock:
            if run_id in self._runs:
                raise BridgeError("RUN_ID", "This run_id has already been used; duplicate dispatch is refused.", 409)
            if len(self._active) >= self.max_concurrent:
                raise BridgeError("BUSY", "The configured simultaneous-request limit is reached. Wait or cancel a running request.", 429)
            self.budget.reserve(reserved)
            cancel = threading.Event()
            self._runs[run_id] = cancel
            self._active.add(run_id)
        accounted, attempts, usage, text, last_error = Decimal(0), 0, None, None, None
        try:
            for attempt in range(self.attempts):
                if cancel.is_set():
                    raise BridgeError("CANCELLED", "Run cancelled. Completed or sent attempts remain accounted.", 409)
                attempts += 1
                try:
                    response = self.sender(url, p.headers(), body, timeout=self.timeout)
                    text, usage = p.parse(response)
                    if usage["input_tokens"] is None:
                        amount, basis = one, "reserved_unknown"
                    else:
                        amount = (Decimal(usage["input_tokens"])*m.input_price + Decimal(usage["output_tokens"])*m.output_price) / 1_000_000
                        basis = "reported_usage_at_user_rates"
                        if amount > one:
                            self.budget.locked = True
                    accounted += amount
                    if cancel.is_set():
                        raise BridgeError("CANCELLED_ACCOUNTED", "Run cancelled; the completed response was discarded and its cost accounted.", 409)
                    return {"run_id": run_id, "provider": p.id, "model": model, "text": self.redact(text), "usage": usage,
                            "cost": {"currency": "USD", "amount": float(amount), "accounted": float(accounted), "basis": basis,
                                     "attempts": attempts, "complete_cost_known": False},
                            "qualification": "LIVE_RESPONSE_NOT_INDEPENDENT_VERIFICATION"}
                except BridgeError as error:
                    if error.code == "CANCELLED_ACCOUNTED":
                        raise
                    # A missing response never makes a possibly dispatched request free.
                    accounted += one
                    last_error = error
                    if error.code not in {"PROVIDER_HTTP", "PROVIDER_CONNECTION"} or attempt + 1 == self.attempts:
                        raise
                    if cancel.wait(min(2 ** attempt, 4)):
                        raise BridgeError("CANCELLED", "Run cancelled; no further retry sent.", 409)
                except Exception:
                    # An unexpected parser/transport failure is not proof that dispatch
                    # was free. Charge the complete attempt reservation before refusing.
                    accounted += one
                    raise BridgeError("PROVIDER_RESPONSE", "The provider response could not be safely processed; its full reservation remains accounted.", 502) from None
            raise last_error or BridgeError("UNKNOWN", "No result.", 502)
        finally:
            self.budget.settle(reserved, accounted)
            with self._lock:
                self._active.discard(run_id)


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address, timeout):
        super().__init__(hostname, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the already-validated numeric address; DNS cannot rebind between check/use.
        raw = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def retrieve_source(url, allowed_hosts, previous=None, resolver=socket.getaddrinfo, connector=PinnedHTTPS):
    try:
        u = urlsplit(url)
        if (u.scheme != "https" or not u.hostname or u.hostname not in allowed_hosts or
                u.port not in {None, 443} or u.username or u.password or u.fragment):
            raise ValueError()
        if any(c in url for c in "\r\n\x00"):
            raise ValueError()
        addresses = {row[4][0] for row in resolver(u.hostname, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError()
    except (ValueError, TypeError, OSError):
        raise BridgeError("SOURCE_URL", "Use an exact allowlisted HTTPS host resolving only to public addresses.") from None
    if previous is not None and (not isinstance(previous, str) or not re.fullmatch(r"[a-f0-9]{64}", previous)):
        raise BridgeError("SOURCE_HASH", "The previous source identity must be a SHA-256 hex digest.")
    connection = connector(u.hostname, sorted(addresses)[0], 30)
    try:
        connection.request("GET", (u.path or "/") + ("?" + u.query if u.query else ""), headers={
            "User-Agent": "AlphaGenesisHarness/0.1 source retrieval", "Accept": "text/plain,text/html,application/json",
            "Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise BridgeError("SOURCE_HTTP", "Source did not return HTTP 200. Redirects are not followed.", 502)
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in {"text/plain", "text/html", "application/json", "text/markdown"} or response.getheader("Content-Encoding", "identity") != "identity":
            raise BridgeError("SOURCE_TYPE", "Only uncompressed text, HTML, Markdown and JSON sources are accepted.")
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise BridgeError("SOURCE_SIZE", "Source is over 1 MiB. Import a relevant attributed excerpt manually.")
        sha = hashlib.sha256(raw).hexdigest()
        return {"url": url, "sha256": sha, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "changed": None if previous is None else previous != sha, "previous_sha256": previous,
                "content_type": content_type, "text": raw.decode("utf-8", errors="replace"),
                "trust": "UNTRUSTED_SOURCE_CONTENT", "freshness_scope": "Retrieval time is not the document publication date; byte change is not verified semantic change."}
    except (OSError, http.client.HTTPException):
        raise BridgeError("SOURCE_CONNECTION", "Source retrieval failed or timed out.", 502) from None
    finally:
        connection.close()
