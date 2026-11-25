# SPDX-License-Identifier: Apache-2.0
"""Same-origin, member-authorized API setup and guarded inference profiles."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading

from .adapters import BridgeError, Budget, ID, Provider, Runtime, decimal
from .chatgpt import CredentialStore
from .services import AccessRuntime


PROVIDERS = {
    "openai": ("OpenAI API", "responses", "https://api.openai.com/v1"),
    "anthropic": ("Anthropic Claude API", "anthropic", "https://api.anthropic.com/v1"),
    "gemini": ("Google Gemini API", "gemini", "https://generativelanguage.googleapis.com/v1beta"),
    "xai": ("xAI API", "openai", "https://api.x.ai/v1"),
    "mistral": ("Mistral API", "openai", "https://api.mistral.ai/v1"),
    "deepseek": ("DeepSeek API", "openai", "https://api.deepseek.com"),
}
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
KEY = re.compile(r"[\x21-\x7e]{8,4096}\Z")
ORG = re.compile(r"org[-_][a-zA-Z0-9_-]{1,128}\Z")
PROJECT = re.compile(r"proj_[a-zA-Z0-9_-]{1,128}\Z")
GEMINI_MODEL = re.compile(r"[A-Za-z0-9._-]+\Z")
SETUP_TIMEOUT = timedelta(minutes=15)
PROFILE_LIMIT = 32
TEST_HISTORY_LIMIT = 32
INPUT_OVERHEAD = 4096
PROFILE_FIELDS = frozenset({"id", "binding", "provider", "project", "organization", "credential", "model",
                            "expires_at", "max_output_tokens", "max_turns", "input_rate", "output_rate",
                            "budget", "verification"})


def require(condition, code, message, status=400):
    if not condition:
        raise BridgeError(code, message, status)


def utc_now():
    return datetime.now(timezone.utc)


def _opaque(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def _text(value, max_length):
    return isinstance(value, str) and len(value) <= max_length and (not value or value.isprintable())


def _amount(value, description):
    require(type(value) in {str, int, float} and len(str(value)) <= 64, "INTELLIGENCE_LIMITS",
            f"Enter a finite, nonnegative {description} in USD.")
    try:
        result = decimal(value, description)
    except BridgeError:
        raise BridgeError("INTELLIGENCE_LIMITS", f"Enter a finite, nonnegative {description} in USD.") from None
    require(abs(result.adjusted()) <= 100, "INTELLIGENCE_LIMITS", "The amount exceeds supported numeric precision.")
    return result


def _provider_error(error):
    if error.code in {"PROVIDER_AUTH", "PROVIDER_HTTP"}:
        status = re.match(r"Provider HTTP (\d+)\.", error.message)
        status = int(status[1]) if status else None
        if status == 401:
            return BridgeError("INTELLIGENCE_CREDENTIAL", "The selected provider refused this credential.", 403)
        if status == 403:
            return BridgeError("INTELLIGENCE_PERMISSION", "Check the selected project's model permission and account eligibility.", 403)
        if status in {400, 404, 422}:
            return BridgeError("INTELLIGENCE_MODEL", "The selected model did not accept this inference request.", 409)
    if error.code == "PROVIDER_QUOTA":
        return BridgeError("INTELLIGENCE_QUOTA", "The provider reported a quota, rate, or spending limit.", 429)
    if error.code == "PROVIDER_CONNECTION":
        return BridgeError("INTELLIGENCE_CONNECTION", "The selected provider could not be reached. A sent request may still incur charges.", 502)
    if error.code == "BUDGET":
        return BridgeError("INTELLIGENCE_BUDGET", "The request exceeds the permitted local estimate or the guard is locked.", 409)
    return BridgeError("INTELLIGENCE_VERIFICATION", "The selected provider did not complete the authorized connection test.", 502)


class _BoundProvider(Provider):
    def __init__(self, row):
        name = row["provider"]
        label, kind, endpoint = PROVIDERS[name]
        models = {}
        if row.get("model") is not None:
            models[row["model"]] = {"input_per_million": row["input_rate"],
                                   "output_per_million": row["output_rate"],
                                   "input_token_overhead": INPUT_OVERHEAD,
                                   "max_output_tokens": row["max_output_tokens"]}
        super().__init__(name, {"kind": kind, "label": label, "base_url": endpoint, "models": models,
                                "output_limit_field": "max_tokens" if kind == "openai" else "max_completion_tokens"})
        self.key = row["credential"]
        self.organization, self.project = row["organization"], row["project"]

    def headers(self):
        headers = super().headers()
        if self.id == "openai":
            headers["OpenAI-Project"] = self.project
            if self.organization:
                headers["OpenAI-Organization"] = self.organization
        return headers

    def request(self, model, prompt, *args, **kwargs):
        url, body = super().request(model, prompt, *args, **kwargs)
        if self.id == "deepseek" and prompt.startswith("FRONTIER connection test."):
            # The short readiness probe checks text. Mission requests use model defaults.
            body["thinking"] = {"type": "disabled"}
        return url, body


def _budget_record(budget):
    return {"limit": str(budget.limit), "committed": str(budget.committed),
            "reserved": str(budget.reserved), "locked": budget.locked}


def _budget_from(row):
    result = Budget(_amount(row["limit"], "limit"))
    result.committed = _amount(row["committed"], "commitment")
    result.reserved = _amount(row["reserved"], "reservation")
    result.locked = row["locked"] is True
    return result


class _ProfileBudget:
    """Use the native guard with private atomic reservations across restarts."""

    def __init__(self, service, record, group="accounts"):
        self.service = service
        self.identifier, self.binding = record["id"], record["binding"]
        self.group = group
        self.last = record["budget"]
        self.locked = False  # Runtime can also record a provider usage overrun during settlement.

    def _change(self, event, reservation, amount=None):
        self.service._check_storage()
        with self.service.store.locked():
            state = self.service.store.read()
            record = state.get(self.group, {}).get(self.identifier)
            if not record or record["binding"] != self.binding:
                require(event == "settle", "INTELLIGENCE_REVOKED", "This intelligence profile was revoked.", 403)
                return
            budget = _budget_from(record["budget"])
            if event == "reserve":
                require(not self.service._closed, "INTELLIGENCE_REVOKED", "The native connector has closed.", 403)
                require(self.service.clock() < datetime.fromisoformat(record["expires_at"]),
                        "INTELLIGENCE_EXPIRED", "This intelligence profile expired.", 403)
                budget.reserve(reservation)
            else:
                if self.locked:
                    budget.locked = True
                budget.settle(reservation, amount)
            record["budget"] = _budget_record(budget)
            self.service.store.write(state)
            self.last = record["budget"]

    def reserve(self, amount):
        self._change("reserve", amount)

    def settle(self, reserved, amount):
        self._change("settle", reserved, amount)

    def view(self):
        record = self.service._read().get(self.group, {}).get(self.identifier)
        return {**_budget_from(record["budget"] if record and record["binding"] == self.binding else self.last).view(),
                "scope": "native-profile-estimate"}


@dataclass(frozen=True)
class NativeRoute:
    profile_id: str
    provider: str
    model: str
    label: str
    project: str
    binding: str = field(repr=False)
    expires_at: datetime
    max_output_tokens: int
    max_turns: int
    runtime: AccessRuntime = field(repr=False)
    _valid: object = field(repr=False)
    category: str = "api"

    def valid(self):
        return self._valid()

    @property
    def usage(self):
        return {"category": "api_billed", "estimate": self.runtime.budget.view()}


@dataclass
class _Discovery:
    provider: _BoundProvider = field(repr=False)
    models: tuple
    expires_at: datetime
    testing: bool = False


class NativeIntelligenceService:
    """The locally authenticated UI provisions verified, isolated API profiles."""

    def __init__(self, runtime, private_root, *, clock=utc_now):
        self.native = runtime
        self.clock = clock
        self.root = Path(private_root).expanduser().absolute() / "native-intelligence"
        self.store = CredentialStore(self.root)
        self.store.path = self.root / "provider-profiles.json"
        self._check_storage()
        self._lock = threading.RLock()
        self._setups = {}
        self._routes = {}
        self._active_tests = {}
        self._retired_keys = deque(maxlen=PROFILE_LIMIT)
        self._closed = False

    def _check_storage(self):
        require(not any(part.is_symlink() for part in (self.root, *self.root.parents)),
                "INTELLIGENCE_STORAGE", "Profiles require a private directory without symbolic-link parents.")

    def _read(self):
        self._check_storage()
        if not self.store.path.exists() and not self.store.path.is_symlink():
            return {"accounts": {}}
        self.store._prepare()  # Validate ownership without waiting on an in-flight inference reservation.
        return self.store.read()

    def _record(self, identifier):
        return self._read()["accounts"].get(identifier)

    def redact(self, text):
        """Shield paired mission inputs and outputs from known API credentials."""
        keys = {record["credential"] for record in self._read()["accounts"].values() if record.get("credential")}
        with self._lock:
            self._prune()
            keys.update(setup.provider.key for setup in self._setups.values())
            keys.update(key for key, _ in self._active_tests.values())
            keys.update(self._retired_keys)
        variants = keys | {json.dumps(key)[1:-1] for key in keys}
        for value in sorted(variants, key=len, reverse=True):
            text = text.replace(value, "[credential redacted]")
        return text

    def _verify_record(self, identifier, record):
        require(_opaque(identifier) and isinstance(record, dict) and set(record) == PROFILE_FIELDS
                and record["id"] == identifier and _opaque(record["binding"])
                and isinstance(record["provider"], str) and record["provider"] in PROVIDERS and isinstance(record["model"], str)
                and ID.fullmatch(record["model"]) and isinstance(record["credential"], str)
                and KEY.fullmatch(record["credential"]) and isinstance(record["verification"], dict)
                and record["verification"].get("model") == record["model"] and _text(record["expires_at"], 40)
                and type(record["max_turns"]) is int and 1 <= record["max_turns"] <= 100
                and type(record["max_output_tokens"]) is int and 64 <= record["max_output_tokens"] <= 32768,
                "INTELLIGENCE_STORAGE", "The saved intelligence profile is invalid.", 409)

    def _candidate(self, supplied):
        require(isinstance(supplied, dict) and set(supplied) == {"provider", "credential", "organization", "project", "consent"}
                and supplied["consent"] is True and isinstance(supplied["provider"], str)
                and supplied["provider"] in PROVIDERS, "INTELLIGENCE_PERMISSION",
                "Choose a supported provider and allow discovery on that account.", 403)
        key, organization, project = (supplied[key] for key in ("credential", "organization", "project"))
        require(isinstance(key, str) and KEY.fullmatch(key) and not key.lower().startswith(("sk-admin-", "sk-ant-admin")),
                "INTELLIGENCE_CREDENTIAL", "Enter a standard project API credential in the local companion.")
        if supplied["provider"] == "openai":
            valid_project = isinstance(project, str) and PROJECT.fullmatch(project)
            valid_org = organization == "" or (isinstance(organization, str) and ORG.fullmatch(organization))
        else:
            valid_project = _text(project, 100) and bool(project.strip())
            valid_org = organization == ""
        require(valid_project and valid_org and key not in project and key not in organization,
                "INTELLIGENCE_PROJECT", "Confirm the exact project or workspace selected for this credential.")
        return _BoundProvider(supplied)

    def _prune(self):
        for setup_id, setup in tuple(self._setups.items()):
            if not setup.testing and setup.expires_at <= self.clock():
                self._setups.pop(setup_id, None)

    def discover(self, data):
        provider = self._candidate(data)
        with self._lock:
            self._prune()
            require(not self._closed and len(self._setups) < PROFILE_LIMIT, "INTELLIGENCE_BUSY",
                    "Finish an open setup before starting a new one.", 409)
            setup_id = secrets.token_urlsafe(32)
            setup = _Discovery(provider, (), self.clock() + SETUP_TIMEOUT, testing=True)
            self._setups[setup_id] = setup
        try:
            try:
                response = self.native.base.sender(provider.models_request(), provider.headers(), timeout=self.native.base.timeout)
                require(isinstance(response, dict), "PROVIDER_RESPONSE", "Invalid model catalog.", 502)
                if provider.kind == "gemini":
                    candidates = response.get("models")
                    require(isinstance(candidates, list), "PROVIDER_RESPONSE", "Invalid model catalog.", 502)
                    response = dict(response, models=[candidate for candidate in candidates if isinstance(candidate, dict)
                                    and isinstance(candidate.get("supportedGenerationMethods"), list)
                                    and "generateContent" in candidate["supportedGenerationMethods"]])
                catalog = provider.models_response(response)
            except BridgeError as error:
                raise _provider_error(error) from None
            models = tuple(dict.fromkeys(row["id"] for row in catalog["models"] if provider.key not in row["id"]
                           and (provider.kind != "gemini" or GEMINI_MODEL.fullmatch(row["id"]))))
            require(models, "INTELLIGENCE_NO_MODELS", "No usable model was listed for this project.", 409)
            with self._lock:
                require(not self._closed, "INTELLIGENCE_REVOKED", "The native connector is closed.", 409)
                setup.models = models
                setup.testing = False
            return {"state": "awaiting_verification", "setup_id": setup_id, "provider": provider.id,
                    "label": provider.label, "models": models, "has_more": catalog["has_more"],
                    "expires_at": setup.expires_at.isoformat()}
        except Exception:
            with self._lock:
                self._setups.pop(setup_id, None)
            raise

    def _configuration(self, data):
        require(isinstance(data, dict) and set(data) == {"setup_id", "model", "input_rate", "output_rate",
                    "budget_usd", "max_output_tokens", "max_turns", "expiry_hours", "consent"}
                and data["consent"] is True and _opaque(data["setup_id"]), "INTELLIGENCE_PERMISSION",
                "Authorize one inference test and the displayed profile limits.", 403)
        budget, input_rate, output_rate = (_amount(data[key], label) for key, label in
                                          (("budget_usd", "budget"), ("input_rate", "input rate"), ("output_rate", "output rate")))
        require(budget > 0 and (input_rate > 0 or output_rate > 0), "INTELLIGENCE_BUDGET",
                "Authorize a positive budget and the provider's actual maximum token rates for API inference.", 409)
        limits = [("max_output_tokens", 64, 32768), ("max_turns", 1, 100), ("expiry_hours", 1, 720)]
        require(all(type(data[key]) is int and lower <= data[key] <= upper for key, lower, upper in limits),
                "INTELLIGENCE_LIMITS", "Select valid output, request and expiration limits.")
        return budget, input_rate, output_rate

    def _access(self, row, budget):
        policy = {"allow_paid_requests": True, "source_hosts": [], "max_attempts": 1,
                  "max_concurrent_requests": 1, "timeout_seconds": self.native.base.timeout}
        runtime = Runtime(policy, sender=self.native.base.sender)
        runtime.providers[row["provider"]] = _BoundProvider(row)
        runtime.budget = budget
        return AccessRuntime(runtime, policy)

    @staticmethod
    def _challenge(max_output_tokens):
        marker = "FRONTIER-" + secrets.token_hex(4)
        return marker, {"prompt": f"FRONTIER connection test. Reply with only this exact text: {marker}",
                        "run_id": "frontier_verify_" + secrets.token_hex(12), "max_output_tokens": min(max_output_tokens, 512)}

    @staticmethod
    def _verify_response(marker, result):
        require(isinstance(result, dict) and isinstance(result.get("text"), str)
                and hmac.compare_digest(result["text"].strip().encode("utf-8"), marker.encode("ascii")),
                "INTELLIGENCE_VERIFICATION", "The response did not pass the connection challenge. The sent request may be billed.", 502)

    def _begin_test(self, row, limit):
        record = {key: row[key] for key in ("id", "binding", "provider", "model", "expires_at")}
        record.update(budget=_budget_record(Budget(limit)), state="verifying", at=self.clock().isoformat())
        self._check_storage()
        with self.store.locked():
            state = self.store.read()
            tests = state.setdefault("connection_tests", {})
            if len(tests) >= TEST_HISTORY_LIMIT:
                candidates = sorted((item for item in tests.values() if item["state"] != "verifying"
                                    or self.clock() > datetime.fromisoformat(item["at"]) + SETUP_TIMEOUT),
                                    key=lambda item: item["at"])
                require(candidates, "INTELLIGENCE_BUSY", "Wait for the other connection tests to finish.", 409)
                del tests[candidates[0]["id"]]
            tests[record["id"]] = record
            self.store.write(state)
        return _ProfileBudget(self, record, "connection_tests")

    def _finish_test(self, row, error=None):
        self._check_storage()
        with self._lock, self.store.locked():
            state = self.store.read()
            test = state["connection_tests"].get(row["id"])
            require(test is not None and test["binding"] == row["binding"], "INTELLIGENCE_STORAGE",
                    "The local connection test record changed.", 409)
            if error is None:
                require(not self._closed and len(state["accounts"]) < PROFILE_LIMIT,
                        "INTELLIGENCE_STORAGE", "Profile storage changed after the test. A sent request may be billed.", 409)
                test["state"] = "verified"
                row["budget"] = test["budget"]
                state["accounts"][row["id"]] = row
            else:
                test["state"], test["code"] = "failed", error.code
            self.store.write(state)

    def verify(self, data):
        limit, input_rate, output_rate = self._configuration(data)
        marker, request = self._challenge(data["max_output_tokens"])
        estimate = ((len(request["prompt"].encode("utf-8")) + INPUT_OVERHEAD) * input_rate
                    + request["max_output_tokens"] * output_rate) / 1_000_000
        require(limit >= estimate, "INTELLIGENCE_TEST_BUDGET",
                "The authorized budget is too low for this test. Choose a larger limit to authorize it.", 409)
        setup_id = data["setup_id"]
        with self._lock:
            self._prune()
            setup = self._setups.get(setup_id)
            require(setup is not None and not setup.testing and not self._closed,
                    "INTELLIGENCE_SETUP", "This setup expired, was used, or is still running. Discover models again.", 409)
            require(data["model"] in setup.models, "INTELLIGENCE_MODEL", "Select an exact model from this connection's catalog.")
            self._setups.pop(setup_id)
        provider = setup.provider
        row = {"id": secrets.token_urlsafe(32), "binding": secrets.token_urlsafe(32), "provider": provider.id,
               "project": provider.project, "organization": provider.organization, "credential": provider.key,
               "model": data["model"], "expires_at": (self.clock() + timedelta(hours=data["expiry_hours"])).isoformat(),
               "max_turns": data["max_turns"], "max_output_tokens": data["max_output_tokens"],
               "input_rate": str(input_rate), "output_rate": str(output_rate)}
        self._check_storage()
        require(len(self._read()["accounts"]) < PROFILE_LIMIT, "INTELLIGENCE_STORAGE", "Remove an unused profile before adding another.", 409)
        budget = self._begin_test(row, limit)
        runtime = self._access(row, budget)
        with self._lock:
            require(not self._closed, "INTELLIGENCE_REVOKED", "The native connector is closed.", 409)
            self._active_tests[row["id"]] = (provider.key, runtime)
        try:
            try:
                result = runtime.generate(dict(request, provider=provider.id, model=row["model"]))
            except BridgeError as error:
                raise _provider_error(error) from None
            self._verify_response(marker, result)
            row["verification"] = {"at": self.clock().isoformat(), "model": row["model"],
                                   "reported_model": result.get("reported_model"), "usage": result["usage"],
                                   "qualification": result.get("qualification")}
            self._finish_test(row)
        except (BridgeError, OSError) as error:
            if not isinstance(error, BridgeError):
                error = BridgeError("INTELLIGENCE_STORAGE", "Local storage failed. A sent connection test may be billed.", 409)
            try:
                self._finish_test(row, error)
            except (BridgeError, OSError):
                pass  # The durable reservation still accounts for an interrupted test.
            raise error from None
        finally:
            runtime.close()
            with self._lock:
                self._active_tests.pop(row["id"], None)
        profile = self._view(row)
        return {"state": profile["state"], "profile": profile}

    def _view(self, row):
        verification = row["verification"]
        budget = {**_budget_from(row["budget"]).view(), "scope": "native-profile-estimate"}
        status = "expired" if self.clock() >= datetime.fromisoformat(row["expires_at"]) else (
            "limit_reached" if budget["locked"] or not budget["remaining"] else "ready")
        return {"id": row["id"], "label": PROVIDERS[row["provider"]][0], "category": "api", "model": row["model"],
                "project": row["project"], "expires_at": row["expires_at"], "ready": status == "ready", "state": status,
                "max_turns": row["max_turns"], "max_output_tokens": row["max_output_tokens"],
                "verification": verification, "usage": {"category": "api_billed", "estimate": budget}}

    def status(self):
        state = self._read()
        profiles = []
        for identifier, row in state["accounts"].items():
            self._verify_record(identifier, row)
            profiles.append(self._view(row))
        tests = []
        for row in sorted(state.get("connection_tests", {}).values(), key=lambda item: item["at"], reverse=True)[:8]:
            if row["state"] == "verified":
                continue
            outcome = row["state"]
            if outcome == "verifying" and row["id"] not in self._active_tests:
                outcome = "interrupted"
            tests.append({"state": outcome, "label": PROVIDERS[row["provider"]][0], "model": row["model"], "at": row["at"],
                          "usage": _budget_from(row["budget"]).view()})
        return {"profiles": profiles, "providers": [{"id": name, "label": details[0]} for name, details in PROVIDERS.items()],
                "credential_protection": "windows-dpapi" if os.name == "nt" else "owner-only-file", "recent_tests": tests}

    def get_route(self, profile_id):
        require(_opaque(profile_id), "INTELLIGENCE_PROFILE", "Select a verified local intelligence profile.")
        with self._lock:
            row = self._record(profile_id)
            require(row is not None and not self._closed, "INTELLIGENCE_REVOKED", "This intelligence profile is unavailable or revoked.", 403)
            self._verify_record(profile_id, row)
            expires = datetime.fromisoformat(row["expires_at"])
            require(self.clock() < expires, "INTELLIGENCE_EXPIRED", "This intelligence profile expired. Reconnect the provider.", 403)
            budget = _budget_from(row["budget"])
            require(not budget.locked and budget.limit > budget.committed + budget.reserved, "INTELLIGENCE_BUDGET",
                    "This intelligence profile reached its local spending limit.", 409)
            cached = self._routes.get(profile_id)
            if cached is not None and cached.binding == row["binding"] and cached.valid():
                return cached
            runtime = self._access(row, _ProfileBudget(self, row))
            binding = row["binding"]

            def valid():
                if self._closed or self.clock() >= expires:
                    return False
                try:
                    current = self._record(profile_id)
                    return bool(current and all(current[key] == row[key] for key in PROFILE_FIELDS - {"budget", "verification"}))
                except (BridgeError, OSError, ValueError, KeyError):
                    return False

            route = NativeRoute(profile_id, row["provider"], row["model"], PROVIDERS[row["provider"]][0], row["project"],
                                binding, expires, row["max_output_tokens"], row["max_turns"], runtime, valid)
            self._routes[profile_id] = route
            return route

    def disconnect(self, data):
        require(isinstance(data, dict) and set(data) == {"profile_id", "consent"} and data["consent"] is True
                and _opaque(data["profile_id"]), "INTELLIGENCE_PERMISSION", "Explicitly confirm removal of this credential.", 403)
        identifier = data["profile_id"]
        self._check_storage()
        with self._lock, self.store.locked():
            state = self.store.read()
            removed = state["accounts"].pop(identifier, None)
            if removed is not None:
                self.store.write(state)
                self._retired_keys.append(removed["credential"])
            route = self._routes.pop(identifier, None)
        if route is not None:
            route.runtime.close()
        return {"state": "revoked", "profile_id": identifier}

    def close(self):
        with self._lock:
            self._closed = True
            routes = tuple(self._routes.values())
            active = tuple(runtime for _, runtime in self._active_tests.values())
            self._routes.clear()
            self._setups.clear()
            self._retired_keys.clear()
        for route in routes:
            route.runtime.close()
        for runtime in active:
            runtime.close()
