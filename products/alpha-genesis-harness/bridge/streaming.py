# SPDX-License-Identifier: Apache-2.0
"""Bounded incremental SSE/NDJSON decoding; no model or tool execution authority."""
from __future__ import annotations

import http.client
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler


def stream_transport(url, headers, body, *, kind, timeout, cancel, on_text):
    try:
        from .adapters import BridgeError, NoRedirect, MAX_RESPONSE, strict_json
    except ImportError:
        from adapters import BridgeError, NoRedirect, MAX_RESPONSE, strict_json
    payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
    headers = dict(headers, Accept="application/x-ndjson" if kind == "ollama" else "text/event-stream")
    accumulator = StreamAccumulator(kind, on_text)
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(url, data=payload, headers=headers), timeout=timeout) as response:
            size, pending = 0, []
            while True:
                if cancel.is_set():
                    raise BridgeError("CANCELLED", "Cancelled the local stream; provider work may already have incurred usage.", 409)
                line = response.readline(MAX_RESPONSE + 1)
                size += len(line)
                if size > MAX_RESPONSE:
                    raise BridgeError("PROVIDER_SIZE", "Provider stream exceeded the safe response size.", 502)
                if not line:
                    if pending:
                        accumulator.feed(strict_json(b"\n".join(pending)))
                    break
                line = line.rstrip(b"\r\n")
                if kind == "ollama":
                    if line:
                        accumulator.feed(strict_json(line))
                elif not line:
                    if pending:
                        raw = b"\n".join(pending)
                        pending = []
                        if raw == b"[DONE]":
                            accumulator.end_marker = True
                        else:
                            accumulator.feed(strict_json(raw))
                elif line.startswith(b"data:"):
                    pending.append(line[5:].lstrip(b" "))
            return accumulator.finish()
    except HTTPError as error:
        status = error.code
        error.close()
        code = {401: "PROVIDER_AUTH", 403: "PROVIDER_AUTH", 429: "PROVIDER_QUOTA"}.get(status, "PROVIDER_HTTP")
        raise BridgeError(code, f"Provider HTTP {status}; stream stopped and its reservation remains accounted.", 502) from None
    except (URLError, TimeoutError, OSError, http.client.HTTPException):
        raise BridgeError("PROVIDER_CONNECTION", "Provider stream failed or timed out; sent work remains accounted.", 502) from None


class StreamAccumulator:
    """Build the provider's ordinary response shape, requiring terminal evidence."""
    def __init__(self, kind, on_text=lambda _: None):
        self.kind, self.on_text = kind, on_text
        self.text = ""
        self.calls = {}
        self.usage = {}
        self.blocks = {}
        self.response = None
        self.complete = False
        self.end_marker = False
        self.finish_reason = None
        self.reported_model = None

    def add_text(self, value):
        if not isinstance(value, str):
            self.fail()
        self.text += value
        if value:
            self.on_text(value)

    @staticmethod
    def fail():
        try:
            from .adapters import BridgeError
        except ImportError:
            from adapters import BridgeError
        raise BridgeError("PROVIDER_STREAM", "Malformed, rejected or incomplete provider stream; partial output is not accepted.", 502)

    def feed(self, event):
        if not isinstance(event, dict) or event.get("error"):
            self.fail()
        kind = self.kind
        if isinstance(event.get("model"), str):
            self.reported_model = event["model"]
        if isinstance(event.get("modelVersion"), str):
            self.reported_model = event["modelVersion"]
        if kind == "responses":
            typ = event.get("type")
            if typ in {"error", "response.failed", "response.incomplete", "response.cancelled"}:
                self.fail()
            if typ == "response.output_text.delta":
                self.add_text(event.get("delta"))
            elif typ == "response.completed":
                self.response = event.get("response")
                self.complete = isinstance(self.response, dict) and self.response.get("status") == "completed"
            return
        if kind == "anthropic":
            typ = event.get("type")
            if typ == "error":
                self.fail()
            if typ == "message_start":
                self.usage.update(event.get("message", {}).get("usage", {}))
                self.reported_model = event.get("message", {}).get("model")
            elif typ == "content_block_start":
                self.blocks[event["index"]] = dict(event["content_block"])
            elif typ == "content_block_delta":
                block, delta = self.blocks[event["index"]], event["delta"]
                if delta.get("type") == "text_delta":
                    self.add_text(delta["text"])
                    block["text"] = block.get("text", "") + delta["text"]
                elif delta.get("type") == "input_json_delta":
                    block["_json"] = block.get("_json", "") + delta["partial_json"]
            elif typ == "message_delta":
                self.usage.update(event.get("usage", {}))
                self.finish_reason = event.get("delta", {}).get("stop_reason", self.finish_reason)
            elif typ == "message_stop":
                self.complete = self.finish_reason in {"end_turn", "tool_use", "stop_sequence"}
            return
        if kind == "gemini":
            self.usage.update(event.get("usageMetadata", {}))
            for candidate in event.get("candidates", []):
                if candidate.get("index", 0) != 0:
                    continue
                for part in candidate.get("content", {}).get("parts", []):
                    if "text" in part and not part.get("thought"):
                        self.add_text(part["text"])
                    if "functionCall" in part:
                        self.calls[len(self.calls)] = part
                if candidate.get("finishReason"):
                    self.finish_reason = candidate["finishReason"]
                    self.complete = self.finish_reason == "STOP"
            return
        if kind == "ollama":
            message = event.get("message", {})
            self.add_text(message.get("content", ""))
            for call in message.get("tool_calls", []):
                self.calls[len(self.calls)] = call
            if event.get("done") is True:
                self.complete = event.get("done_reason", "stop") in {"stop", "tool_calls"}
                self.usage = {k: event.get(k) for k in ("prompt_eval_count", "eval_count")}
            return
        # OpenAI-compatible chat deltas; function arguments may be fragmented.
        self.usage.update(event.get("usage") or {})
        for choice in event.get("choices", []):
            if choice.get("index", 0) != 0:
                continue
            delta = choice.get("delta", {})
            self.add_text(delta.get("content") or "")
            for call in delta.get("tool_calls", []):
                index = call["index"]
                if type(index) is not int or index < 0 or index > 63:
                    self.fail()
                target = self.calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if call.get("id"):
                    target["id"] = call["id"]
                for key in ("name", "arguments"):
                    value = call.get("function", {}).get(key, "")
                    if not isinstance(value, str):
                        self.fail()
                    target["function"][key] += value
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
                self.complete = self.finish_reason in {"stop", "tool_calls"}

    def finish(self):
        try:
            from .adapters import strict_json
        except ImportError:
            from adapters import strict_json
        if not self.complete or (self.kind == "openai" and not self.end_marker):
            self.fail()
        if self.kind == "responses":
            return self.response
        if self.kind == "anthropic":
            blocks = [self.blocks[k] for k in sorted(self.blocks)]
            for block in blocks:
                if "_json" in block:
                    block["input"] = strict_json(block.pop("_json"))
            return {"content": blocks, "usage": self.usage, "stop_reason": self.finish_reason, "model": self.reported_model}
        if self.kind == "gemini":
            return {"candidates": [{"content": {"parts": [{"text": self.text}] + list(self.calls.values())},
                                    "finishReason": self.finish_reason}], "usageMetadata": self.usage, "modelVersion": self.reported_model}
        if self.kind == "ollama":
            return {"message": {"content": self.text, "tool_calls": list(self.calls.values())}, "model": self.reported_model, **self.usage}
        return {"choices": [{"message": {"content": self.text, "tool_calls": list(self.calls.values())},
                              "finish_reason": self.finish_reason}], "usage": self.usage, "model": self.reported_model}
