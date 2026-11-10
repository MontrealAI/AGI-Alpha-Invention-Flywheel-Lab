# SPDX-License-Identifier: Apache-2.0
"""Official Sign in with ChatGPT public-client flow and plan Responses transport.

No consumer-interface automation, browser credentials, API keys or billing fallback.
Live eligibility and commercial approval are external qualification dependencies.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from .adapters import BridgeError, ID, MAX_BODY, MAX_RESPONSE, NoRedirect, RUN_ID, strict_json

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
APP_NAME = "alpha_genesis_harness"
UNUSABLE_REFRESH = {"invalid_grant", "invalid_refresh_token", "token_expired",
                   "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"}
TOKEN_FIELDS = {"access_token", "refresh_token", "id_token", "expires_at", "scopes"}


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def _error(raw, status):
    """Keep stable codes and HTTP status, never echo arbitrary remote text or tokens."""
    code = "CHATGPT_HTTP"
    try:
        value = strict_json(raw)
        error = value.get("error", {})
        candidate = error if isinstance(error, str) else error.get("code")
        if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", candidate):
            code = candidate
    except (BridgeError, AttributeError, TypeError):
        pass
    messages = {
        "subscription_sharing_usage_limit_exceeded": "The selected app or ChatGPT plan usage limit was reached. Review ChatGPT Settings → Usage.",
        "subscription_sharing_usage_unavailable": "ChatGPT plan usage is temporarily unavailable. Try again later; no alternate billing was used.",
        "subscription_sharing_user_not_eligible": "This account or workspace is not eligible for this ChatGPT plan integration.",
        "subscription_sharing_unsupported_capability": "The selected model or request capability is unsupported by ChatGPT plan usage.",
        "access_denied": "ChatGPT authorization was declined. No inference was sent.",
    }
    return BridgeError(code, messages.get(code, f"ChatGPT request failed (HTTP {status}; {code}). Check the connection and its permissions."), status if 400 <= status <= 599 else 502)


class PlanTransport:
    """Pinned public destinations, TLS, no environment proxies or redirects."""
    def __init__(self, timeout=60):
        self.timeout = timeout

    def open(self, url, token=None, body=None, form=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in {"auth.openai.com", "api.openai.com"} or parsed.fragment:
            raise BridgeError("CHATGPT_ENDPOINT", "Only official OpenAI HTTPS endpoints are allowed.")
        headers = {"Accept": "application/json", "User-Agent": "AlphaGenesisHarness/0.2"}
        data = None
        if token:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers.update({"Content-Type": "application/json", "Accept": "text/event-stream"})
            data = json.dumps(body, allow_nan=False).encode()
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(form).encode()
        try:
            return build_opener(ProxyHandler({}), NoRedirect()).open(Request(url, data=data, headers=headers), timeout=self.timeout)
        except HTTPError as exc:
            raw, status = exc.read(16384), exc.code
            exc.close()
            raise _error(raw, status) from None
        except (URLError, OSError, TimeoutError):
            raise BridgeError("CHATGPT_CONNECTION", "ChatGPT connection failed. Sent requests may have consumed plan allowance; no automatic retry or billing fallback occurred.", 502) from None

    def json(self, url, token=None, form=None):
        with self.open(url, token=token, form=form) as response:
            if response.status == 200 and form is not None and "revoke" in url:
                return {}
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise BridgeError("CHATGPT_SIZE", "ChatGPT response exceeded the local resource limit.", 502)
            if not raw and form is not None:
                return {}
            value = strict_json(raw)
            if not isinstance(value, dict):
                raise BridgeError("CHATGPT_RESPONSE", "Expected an object from ChatGPT.", 502)
            return value

    def events(self, token, body, cancel):
        """SSE framing supports multiline data; interrupted streams never become success."""
        try:
            if cancel.is_set():
                raise BridgeError("CANCELLED", "ChatGPT request cancelled before dispatch.", 409)
            with self.open(RESOURCE + "/responses", token=token, body=body) as response:
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    raise BridgeError("CHATGPT_STREAM", "ChatGPT did not return an event stream.", 502)
                total, parts = 0, []
                while True:
                    if cancel.is_set():
                        raise BridgeError("CANCELLED", "ChatGPT request cancelled. Already consumed plan usage may remain.", 409)
                    raw = response.readline(MAX_BODY + 1)
                    if not raw:
                        break
                    total += len(raw)
                    if len(raw) > MAX_BODY or total > MAX_RESPONSE:
                        raise BridgeError("CHATGPT_SIZE", "ChatGPT stream exceeded the local resource limit.", 502)
                    line = raw.decode("utf-8").rstrip("\r\n")
                    if line.startswith("data:"):
                        parts.append(line[5:].lstrip(" "))
                    elif not line and parts:
                        data, parts = "\n".join(parts), []
                        if data != "[DONE]":
                            yield strict_json(data)
        except (OSError, UnicodeError):
            raise BridgeError("CHATGPT_STREAM", "ChatGPT stream was interrupted; no completed result was accepted.", 502) from None


def verify_identity(token, client_id, nonce, transport, expected_subject=None, now=None):
    """Verify RS256 with maintained cryptography primitives, trusted OIDC JWKS only."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        raise BridgeError("CHATGPT_DEPENDENCY", "Install the optional cryptography package to verify ChatGPT identity before connecting.", 409) from None
    try:
        header_raw, payload_raw, signature = token.split(".")
        header, claims = strict_json(_decode(header_raw)), strict_json(_decode(payload_raw))
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError()
        metadata = transport.json(ISSUER + "/.well-known/openid-configuration")
        jwks_uri = metadata["jwks_uri"]
        u = urlsplit(jwks_uri)
        if metadata.get("issuer") != ISSUER or u.scheme != "https" or u.netloc != "auth.openai.com" or u.query or u.fragment:
            raise ValueError()
        keys = transport.json(jwks_uri)["keys"]
        matches = [k for k in keys if k.get("kid") == header["kid"] and k.get("kty") == "RSA" and k.get("use", "sig") == "sig" and k.get("alg", "RS256") == "RS256"]
        if len(matches) != 1:
            raise ValueError()
        key = matches[0]
        public = rsa.RSAPublicNumbers(int.from_bytes(_decode(key["e"]), "big"), int.from_bytes(_decode(key["n"]), "big")).public_key()
        public.verify(_decode(signature), (header_raw + "." + payload_raw).encode(), padding.PKCS1v15(), hashes.SHA256())
        current = time.time() if now is None else now
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if (claims.get("iss") != ISSUER or client_id not in audiences or
                (len(audiences) > 1 and claims.get("azp") != client_id) or
                (claims.get("azp") is not None and claims["azp"] != client_id) or
                type(claims.get("exp")) not in {int, float} or claims["exp"] <= current or
                type(claims.get("iat")) not in {int, float} or claims["iat"] > current + 60 or
                (claims.get("nbf") is not None and claims["nbf"] > current + 60) or
                not isinstance(claims.get("sub"), str) or not claims["sub"] or
                (nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce)) or
                (expected_subject is not None and claims["sub"] != expected_subject)):
            raise ValueError()
        return {"subject": claims["sub"], "issuer": ISSUER, "email": str(claims.get("email", ""))[:254]}
    except (ValueError, TypeError, KeyError, AttributeError, InvalidSignature, OverflowError):
        raise BridgeError("CHATGPT_IDENTITY", "ChatGPT identity validation failed. The active account was not replaced.", 403) from None


class CredentialStore:
    """Owner-only POSIX records; Windows DPAPI protects the serialized record."""
    def __init__(self, directory):
        self.directory = Path(directory).expanduser()
        self.path = self.directory / "chatgpt-auth.json"
        self._lock = threading.RLock()

    def _prepare(self):
        # Reject links in the app-owned location instead of following credential paths.
        if self.directory.is_symlink():
            raise BridgeError("CHATGPT_STORAGE", "Credential storage cannot be a symbolic link.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            info = self.directory.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise BridgeError("CHATGPT_STORAGE", "Credential directory must be owned by this user and have permissions 0700.")
        if self.path.is_symlink():
            raise BridgeError("CHATGPT_STORAGE", "Credential file cannot be a symbolic link.")

    @contextmanager
    def locked(self):
        self._prepare()
        with self._lock:
            lockpath = self.directory / "chatgpt-auth.lock"
            fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                if os.name == "nt":
                    import msvcrt
                    os.write(fd, b"0")
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.close(fd)

    @staticmethod
    def _dpapi(raw, decrypt=False):
        import ctypes
        from ctypes import wintypes
        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
        buffer = ctypes.create_string_buffer(raw)
        source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        target = Blob()
        function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise BridgeError("CHATGPT_STORAGE", "Windows could not protect or unlock ChatGPT credentials.")
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target.pbData)

    def read(self):
        if not self.path.exists():
            return {"schema": 1, "host_id": "urn:uuid:" + str(uuid.uuid4()), "accounts": {}, "active": None}
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise BridgeError("CHATGPT_STORAGE", "Credential storage must be an ordinary file.")
            if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
                raise BridgeError("CHATGPT_STORAGE", "Credential file must have owner-only permissions (0600).")
            raw = source.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise BridgeError("CHATGPT_STORAGE", "Credential record is too large.")
        if os.name == "nt":
            raw = self._dpapi(raw, decrypt=True)
        value = strict_json(raw)
        if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("accounts"), dict):
            raise BridgeError("CHATGPT_STORAGE", "Credential record is invalid.")
        return value

    def write(self, value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if os.name == "nt":
            raw = self._dpapi(raw)
        temp = self.directory / (".chatgpt-" + secrets.token_hex(8))
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)


class ChatGPTPlanService:
    def __init__(self, config=None, storage_path=None, transport=None, browser_open=webbrowser.open, identity_verifier=verify_identity):
        self.config = config or {}
        self.transport = transport or PlanTransport()
        self.browser_open, self.identity_verifier = browser_open, identity_verifier
        default = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "alpha-genesis-harness"
        self.store = CredentialStore(storage_path or default)
        self.pending = None
        self._lock = threading.RLock()
        self._runs = {}
        self._active = {}
        self.requests_started = 0
        self.request_limit = self.config.get("request_limit", 20)
        if type(self.request_limit) is not int or self.request_limit < 1:
            raise BridgeError("CONFIG", "ChatGPT request_limit must be a positive operator-selected session limit.")
        self._quota_blocked = False

    def gate(self):
        if self.config.get("allow_plan_usage") is not True:
            raise BridgeError("CHATGPT_DISABLED", "ChatGPT plan access is disabled. Enable the authorized connection in local configuration.", 403)
        distribution = self.config.get("distribution", "commercial")
        if distribution not in {"open-source-local", "commercial"}:
            raise BridgeError("CHATGPT_ELIGIBILITY", "Choose the actual distribution type in local configuration.", 403)
        approval = self.config.get("commercial_approval_reference")
        if distribution == "commercial" and (not isinstance(approval, str) or not approval.strip() or len(approval) > 1000):
            raise BridgeError("CHATGPT_COMMERCIAL_APPROVAL", "ChatGPT plan use in the paid edition requires OpenAI commercial authorization. No authorization is recorded.", 403)

    def _state(self):
        with self.store.locked():
            return self.store.read()

    def redact(self, text):
        if self.store.path.exists():
            for account in self._state()["accounts"].values():
                for field in ("access_token", "refresh_token", "id_token"):
                    if account.get(field):
                        text = text.replace(account[field], "[credential redacted]")
        return text

    @staticmethod
    def _has_permission(account):
        return bool(account.get("access_token")) and {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(account.get("scopes", []))

    def status(self):
        try:
            self.gate()
            enabled, reason = True, "Choose an account or continue with ChatGPT."
        except BridgeError as error:
            enabled, reason = False, error.message
        # Disabled default does not create a credential directory.
        state = self._state() if enabled or self.store.path.exists() else {"accounts": {}, "active": None}
        accounts = [{"id": ident, "label": row.get("label", row.get("email") or ident), "email": row.get("email", ""),
                     "connected": bool(row.get("access_token")), "plan_usage": self._has_permission(row)}
                    for ident, row in state["accounts"].items()]
        active = state["accounts"].get(state.get("active"), {})
        ready = enabled and self._has_permission(active) and not self._quota_blocked and self.requests_started < self.request_limit
        if self._quota_blocked:
            reason = "ChatGPT plan usage is paused after a usage-limit response. Review Settings → Usage, then explicitly reconnect."
        with self._lock:
            pending = {k: self.pending[k] for k in ("id", "status", "error") if k in self.pending} if self.pending else None
        return {"enabled": enabled, "ready": ready, "reason": reason, "accounts": accounts,
                "active_account_id": state.get("active"), "pending": pending,
                "usage": {"category": "chatgpt_plan", "requests_started": self.requests_started, "request_limit": self.request_limit, "usd": None},
                "usage_url": "https://chatgpt.com/settings/usage", "qualification": "CONTRACT_TESTED_ONLY"}

    def start_sign_in(self, account_id=None, reconsent=False):
        self.gate()
        # Verify optional identity dependency before asking the user to authenticate.
        try:
            import cryptography  # noqa: F401
        except ImportError:
            raise BridgeError("CHATGPT_DEPENDENCY", "Install cryptography before connecting ChatGPT.", 409) from None
        with self._lock:
            if self.pending and self.pending.get("status") == "pending":
                raise BridgeError("CHATGPT_PENDING", "A ChatGPT sign-in is already pending.", 409)
            with self.store.locked():
                state = self.store.read()
                account = state["accounts"].get(account_id) if account_id else None
                if account_id and account is None:
                    raise BridgeError("CHATGPT_ACCOUNT", "Choose a saved ChatGPT account.")
                self.store.write(state)  # Persist the host identifier before first registration.
            attempt = {"id": secrets.token_hex(16), "status": "pending", "state": secrets.token_urlsafe(32),
                       "nonce": secrets.token_urlsafe(32), "verifier": secrets.token_urlsafe(48),
                       "client_id": account_id, "subject": account.get("subject") if account else None,
                       "created": time.monotonic()}
            service = self

            class Callback(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def do_GET(self):
                    parsed = urlsplit(self.path)
                    if self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"] or parsed.path != "/auth/callback":
                        self.send_error(400)
                        return
                    try:
                        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=12)
                        if any(len(values) != 1 for values in query.values()):
                            raise ValueError()
                        values = {k: v[0] for k, v in query.items()}
                        if not hmac.compare_digest(values.get("state", ""), attempt["state"]):
                            raise ValueError()
                    except ValueError:
                        self.send_error(403)
                        return
                    try:
                        service.complete_callback(attempt, values)
                        message = b"ChatGPT connection saved. Return to the HARNESS."
                    except BridgeError as error:
                        attempt.update(status="failed", error=error.code)
                        message = b"ChatGPT connection was not completed. Return to the HARNESS for status."
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(message)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Content-Security-Policy", "default-src 'none'")
                    self.end_headers()
                    self.wfile.write(message)

            listener = HTTPServer(("127.0.0.1", 0), Callback)
            listener.timeout = 0.5
            attempt["redirect_uri"] = f"http://127.0.0.1:{listener.server_port}/auth/callback"
            query = {"client_id": account_id or "dynamic_agent_client", "ext_agent_host_id": state["host_id"],
                     "response_type": "code", "redirect_uri": attempt["redirect_uri"], "scope": SCOPES,
                     "resource": RESOURCE, "state": attempt["state"], "nonce": attempt["nonce"],
                     "code_challenge_method": "S256", "code_challenge": _b64(hashlib.sha256(attempt["verifier"].encode()).digest())}
            if account:
                if account.get("id_token"):
                    query["id_token_hint"] = account["id_token"]
                if account.get("email"):
                    query["login_hint"] = account["email"]
            else:
                query["agent_name_hint"] = APP_NAME
            if reconsent is True:
                query["prompt"] = "consent"
            self.pending = attempt

            def listen():
                try:
                    while attempt["status"] == "pending" and time.monotonic() - attempt["created"] < 600:
                        listener.handle_request()
                    if attempt["status"] == "pending":
                        attempt.update(status="failed", error="CHATGPT_SIGN_IN_EXPIRED")
                finally:
                    listener.server_close()
                    for key in ("state", "nonce", "verifier", "redirect_uri"):
                        attempt.pop(key, None)

            threading.Thread(target=listen, daemon=True).start()
            # Authorization URL may contain an ID-token hint; never return or log it.
            if not self.browser_open(AUTHORIZE + "?" + urlencode(query)):
                attempt.update(status="failed", error="CHATGPT_BROWSER")
                raise BridgeError("CHATGPT_BROWSER", "Could not open the system browser. Configure a browser and retry.", 409)
            return {"attempt_id": attempt["id"], "status": "pending"}

    def complete_callback(self, attempt, values):
        if attempt.get("status") != "pending" or not hmac.compare_digest(values.get("state", ""), attempt["state"]):
            raise BridgeError("CHATGPT_STATE", "Invalid or already used authorization callback.", 403)
        if values.get("error"):
            raise _error(json.dumps({"error": values["error"]}).encode(), 403)
        issued = values.get("client_id", attempt["client_id"])
        if not isinstance(issued, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", issued) or issued == "dynamic_agent_client" or (attempt["client_id"] and issued != attempt["client_id"]):
            raise BridgeError("CHATGPT_CLIENT", "Registration did not return the expected issued client ID.", 403)
        code = values.get("code")
        if not isinstance(code, str) or not code or len(code) > 4096:
            raise BridgeError("CHATGPT_CODE", "Authorization code is missing or invalid.", 403)
        # Preserve the issued registration even if its single-use code later fails.
        with self.store.locked():
            state = self.store.read()
            state["accounts"].setdefault(issued, {"client_id": issued, "label": issued})
            self.store.write(state)
        data = self.transport.json(TOKEN, form={"grant_type": "authorization_code", "client_id": issued,
                    "code": code, "code_verifier": attempt["verifier"], "redirect_uri": attempt["redirect_uri"], "resource": RESOURCE})
        identity = self.identity_verifier(data.get("id_token", ""), issued, attempt["nonce"], self.transport, attempt.get("subject"))
        with self._lock, self.store.locked():
            if attempt.get("status") != "pending":
                raise BridgeError("CHATGPT_STATE", "Authorization attempt was cancelled.", 403)
            state = self.store.read()
            account = state["accounts"][issued]
            account.update(identity, client_id=issued, label=(identity["email"] or identity["subject"]) + " · " + issued[-8:])
            self._save_tokens(account, data, initial=True)
            state["active"] = issued
            for cancel in self._active.values():
                cancel.set()
            self.store.write(state)
        self._quota_blocked = False
        attempt.update(status="complete")

    @staticmethod
    def _save_tokens(account, data, initial=False):
        if not isinstance(data.get("access_token"), str) or not data["access_token"] or str(data.get("token_type", "")).lower() != "bearer":
            raise BridgeError("CHATGPT_TOKEN", "ChatGPT returned an invalid token response.", 502)
        lifetime = data.get("expires_in")
        if type(lifetime) not in {int, float} or not 0 < lifetime <= 86400:
            raise BridgeError("CHATGPT_TOKEN", "ChatGPT token expiry is missing or invalid.", 502)
        if initial and not isinstance(data.get("scope"), str):
            raise BridgeError("CHATGPT_TOKEN", "ChatGPT did not report granted scopes.", 502)
        account["access_token"] = data["access_token"]
        account["expires_at"] = time.time() + lifetime
        if "scope" in data:
            if not isinstance(data["scope"], str):
                raise BridgeError("CHATGPT_TOKEN", "ChatGPT returned malformed granted scopes.", 502)
            account["scopes"] = data["scope"].split()
        for field in ("refresh_token", "id_token"):
            if field in data:
                if not isinstance(data[field], str) or not data[field]:
                    raise BridgeError("CHATGPT_TOKEN", "ChatGPT returned malformed credentials.", 502)
                account[field] = data[field]

    def select_account(self, account_id):
        self.gate()
        with self._lock, self.store.locked():
            for cancel in self._active.values():
                cancel.set()
            state = self.store.read()
            if account_id not in state["accounts"] or not state["accounts"][account_id].get("subject"):
                raise BridgeError("CHATGPT_ACCOUNT", "Select a validated saved account.")
            state["active"] = account_id
            self.store.write(state)
        self._quota_blocked = False
        return self.status()

    def _account(self):
        self.gate()
        with self.store.locked():
            state = self.store.read()
            account = state["accounts"].get(state.get("active"))
            if not account or not self._has_permission(account):
                raise BridgeError("CHATGPT_CONSENT", "Connect ChatGPT and explicitly authorize plan usage before inference.", 403)
            if account.get("expires_at", 0) <= time.time() + 60:
                if not account.get("refresh_token"):
                    raise BridgeError("CHATGPT_EXPIRED", "ChatGPT authorization expired. Sign in again.", 401)
                try:
                    data = self.transport.json(TOKEN, form={"grant_type": "refresh_token", "client_id": account["client_id"],
                             "refresh_token": account["refresh_token"], "resource": RESOURCE})
                except BridgeError as error:
                    if error.code in UNUSABLE_REFRESH:
                        for key in TOKEN_FIELDS:
                            account.pop(key, None)
                        self.store.write(state)
                    raise
                if "id_token" in data:
                    identity = self.identity_verifier(data["id_token"], account["client_id"], None, self.transport, account["subject"])
                    account.update(identity)
                self._save_tokens(account, data)
                self.store.write(state)
            if not self._has_permission(account):
                raise BridgeError("CHATGPT_CONSENT", "The refreshed authorization does not permit ChatGPT plan usage.", 403)
            return dict(account)

    def disconnect(self, account_id=None, revoke_remote=True):
        # Local sign-out remains available even if integration eligibility was disabled.
        with self._lock:
            for cancel in self._active.values():
                cancel.set()
            if self.pending and self.pending.get("status") == "pending":
                self.pending.update(status="failed", error="CHATGPT_SIGN_IN_CANCELLED")
        confirmed = False
        with self._lock, self.store.locked():
            state = self.store.read()
            ident = account_id or state.get("active")
            account = state["accounts"].get(ident)
            if not account:
                raise BridgeError("CHATGPT_ACCOUNT", "Choose a saved account.")
            if revoke_remote and account.get("refresh_token"):
                try:
                    metadata = self.transport.json(ISSUER + "/.well-known/openid-configuration")
                    endpoint = metadata["revocation_endpoint"]
                    parsed = urlsplit(endpoint)
                    if parsed.scheme != "https" or parsed.netloc != "auth.openai.com" or parsed.query or parsed.fragment:
                        raise ValueError()
                    self.transport.json(endpoint, form={"token": account["refresh_token"], "token_type_hint": "refresh_token", "client_id": ident})
                    confirmed = True
                except (BridgeError, KeyError, ValueError):
                    pass
            for key in TOKEN_FIELDS:
                account.pop(key, None)
            self.store.write(state)
        return {"disconnected": True, "remote_revocation_confirmed": confirmed,
                "notice": "Renewable session revoked." if confirmed else "Local credentials cleared. Remote revocation was not confirmed; disconnect this app in ChatGPT Settings."}

    def close(self):
        with self._lock:
            if self.pending and self.pending.get("status") == "pending":
                self.pending.update(status="failed", error="CHATGPT_SIGN_IN_CANCELLED")
            for cancel in self._active.values():
                cancel.set()

    def discover(self):
        account = self._account()
        return self._discover_account(account)

    def _discover_account(self, account):
        raw = self.transport.json(RESOURCE + "/models", token=account["access_token"])
        if not isinstance(raw.get("models"), list):
            raise BridgeError("CHATGPT_MODELS", "ChatGPT returned an invalid account model catalog.", 502)
        models = [{"id": row["slug"], "label": str(row.get("display_name", row["slug"]))[:160], "configured": True}
                  for row in raw["models"] if isinstance(row, dict) and row.get("visibility") == "list" and isinstance(row.get("slug"), str) and ID.fullmatch(row["slug"])]
        return {"models": models, "scope": "Current selected-account catalog; only completed inference establishes access for that request.", "has_more": False}

    def cancel(self, run_id):
        with self._lock:
            event = self._active.get(run_id)
            if event:
                event.set()
            return {"run_id": run_id, "cancelled": event is not None}

    def generate(self, data, on_event=None):
        if not isinstance(data, dict) or set(data) - {"model", "prompt", "run_id", "json_mode", "max_output_tokens", "provider", "stream"}:
            raise BridgeError("INPUT", "Unsupported ChatGPT generation fields.")
        model, prompt, run_id = data.get("model"), data.get("prompt"), data.get("run_id")
        if not isinstance(model, str) or not ID.fullmatch(model) or not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > MAX_BODY // 2 or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise BridgeError("INPUT", "Choose a model, provide a prompt under 512 KiB and a unique run ID.")
        if data.get("json_mode") is True:
            raise BridgeError("CAPABILITY", "Use text mode with ChatGPT plan requests; structured output is not claimed.")
        with self._lock:
            if self._quota_blocked or self.requests_started >= self.request_limit:
                raise BridgeError("CHATGPT_LIMIT", "ChatGPT requests are paused by the local session limit or a provider usage limit.", 429)
            if run_id in self._runs:
                raise BridgeError("RUN_ID", "This ChatGPT run ID was already used.", 409)
            if self._active:
                raise BridgeError("BUSY", "A ChatGPT request is already active; wait or cancel it.", 429)
            cancel = threading.Event()
            self._runs[run_id] = True
            self._active[run_id] = cancel
        body = {"model": model, "input": [{"role": "user", "content": prompt}], "store": False, "stream": True}
        text, completed, usage = "", False, {"input_tokens": None, "output_tokens": None}
        try:
            account = self._account()
            available = self._discover_account(account)["models"]
            if model not in {row["id"] for row in available}:
                raise BridgeError("CAPABILITY", "The selected model is not in this ChatGPT account's current catalog.")
            with self._lock:
                if cancel.is_set() or self._state().get("active") != account["client_id"]:
                    raise BridgeError("CHATGPT_ACCOUNT_CHANGED", "ChatGPT account changed or request cancelled during preparation.", 409)
                self.requests_started += 1
            for event in self.transport.events(account["access_token"], body, cancel):
                if cancel.is_set():
                    raise BridgeError("CANCELLED", "ChatGPT response cancelled; consumed plan usage may remain.", 409)
                if not isinstance(event, dict):
                    raise BridgeError("CHATGPT_STREAM", "Malformed ChatGPT event.", 502)
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    delta = event.get("delta")
                    if not isinstance(delta, str):
                        raise BridgeError("CHATGPT_STREAM", "Malformed ChatGPT text event.", 502)
                    text += delta
                    if on_event:
                        on_event({"type": "progress", "provider": "chatgpt", "received_characters": len(text)})
                elif kind == "response.completed":
                    response = event.get("response", {})
                    if not isinstance(response, dict) or response.get("status") != "completed":
                        raise BridgeError("CHATGPT_INCOMPLETE", "ChatGPT did not complete the response.", 502)
                    reported = response.get("usage", {})
                    usage = {key: reported.get(key) if type(reported.get(key)) is int and reported[key] >= 0 else None for key in usage}
                    completed = True
                    break
                elif kind in {"response.failed", "error"}:
                    error = event.get("response", event).get("error", event)
                    raise _error(json.dumps({"error": error}).encode(), 429 if error.get("code") == "subscription_sharing_usage_limit_exceeded" else 502)
                elif kind == "response.incomplete":
                    raise BridgeError("CHATGPT_INCOMPLETE", "ChatGPT returned an incomplete response. No completed result was accepted.", 502)
            if not completed:
                raise BridgeError("CHATGPT_INTERRUPTED", "ChatGPT stream ended without response.completed.", 502)
            if cancel.is_set():
                raise BridgeError("CANCELLED", "ChatGPT response cancelled before acceptance.", 409)
            if not text.strip():
                raise BridgeError("CHATGPT_EMPTY", "ChatGPT completed without usable text.", 502)
            for key in ("access_token", "refresh_token", "id_token"):
                if account.get(key):
                    text = text.replace(account[key], "[credential redacted]")
            if on_event:
                on_event({"type": "delta", "provider": "chatgpt", "delta": text})
            return {"run_id": run_id, "provider": "chatgpt", "model": model, "text": text, "usage": usage,
                    "cost": {"currency": None, "amount": None, "accounted": None, "basis": "chatgpt_plan_allowance", "attempts": 1, "complete_cost_known": False},
                    "notice": "ChatGPT plan allowance is distinct from API billing. HTTP plan requests do not support a max_output_tokens parameter; the local field is not sent.",
                    "qualification": "LIVE_RESPONSE_NOT_INDEPENDENT_VERIFICATION"}
        except BridgeError as error:
            if error.code == "subscription_sharing_usage_limit_exceeded":
                self._quota_blocked = True
            raise
        finally:
            with self._lock:
                self._active.pop(run_id, None)
