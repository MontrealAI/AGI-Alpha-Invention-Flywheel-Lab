"""Two loopback HTTP clients, observed SSE events and post-run visible-text tokenization."""
from __future__ import annotations

import contextlib
import http.client
import json
import socket
import subprocess
import threading
import time

from protocol import decode, require, sha


def micros():
    return time.monotonic_ns() // 1000


@contextlib.contextmanager
def http_stream(port, body, timeout, *, path="/v1/chat/completions", accept="text/event-stream"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.connect()
        sock = conn.sock
        def interrupt():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        deadline = threading.Timer(timeout, interrupt)
        deadline.daemon = True
        deadline.start()
        try:
            conn.request("POST", path, body, {"Content-Type":"application/json",
                         "Accept":accept, "Accept-Encoding":"identity"})
            with conn.getresponse() as res:
                yield res.status, res.getheader("Content-Type", ""), res
        finally:
            deadline.cancel()
    finally:
        conn.close()


@contextlib.contextmanager
def curl_stream(port, body, timeout):
    # -q must be first. Never consult .curlrc, proxies or netrc. No redirects.
    args = ["curl", "-q", "--silent", "--no-buffer", "--include", "--noproxy", "*",
            "--proto", "=http", "--http1.1", "--max-time", str(timeout), "-H", "Expect:",
            "-H", "Accept: text/event-stream", "-H", "Content-Type: application/json",
            "-H", "Accept-Encoding: identity", "--data-binary", "@-",
            f"http://127.0.0.1:{port}/v1/chat/completions"]
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        try:
            proc.stdin.write(body)
            proc.stdin.close()
            first = proc.stdout.readline(4097).split()
            require(len(first) >= 2 and first[0].startswith(b"HTTP/"), "curl returned no HTTP status")
            status = int(first[1])
            content_type = ""
            header_bytes = 0
            while True:
                line = proc.stdout.readline(8193)
                header_bytes += len(line)
                require(line and header_bytes <= 65536, "curl returned incomplete or oversized headers")
                if line in {b"\r\n", b"\n"}:
                    break
                name, _, value = line.partition(b":")
                if name.lower() == b"content-type":
                    content_type = value.decode("ascii").strip()
            yield status, content_type, proc.stdout
        finally:
            if proc.poll() is None:
                proc.kill()


def attempt(port, authority, workload, case, route, epoch):
    start = micros() - epoch
    rec = {"start_us":start, "end_us":None, "http":None, "sse":False, "events":[], "error":None}
    body = json.dumps({"model":authority["model"], "stream":True, "stream_options":{"include_usage":True},
                       "temperature":0, "max_tokens":workload["max_output_tokens"],
                       "messages":[{"role":"system", "content":workload["instruction"]},
                                   {"role":"user", "content":case["prompt"]}]}, ensure_ascii=False).encode()
    rec["request_bytes"] = len(body)
    rec["request_sha256"] = sha(body)
    wire = http_stream if route == "field" else curl_stream
    try:
        with wire(port, body, workload["attempt_timeout_s"]) as (status, content_type, handle):
            rec["http"] = status
            rec["sse"] = content_type.split(";")[0].strip().lower() == "text/event-stream"
            if status == 200 and rec["sse"]:
                budget = workload["max_response_bytes"]
                parts = []
                while budget > 0:
                    line = handle.readline(budget + 1)
                    if not line:
                        break
                    budget -= len(line)
                    require(budget >= 0, "response budget")
                    line = line.decode("utf-8").rstrip("\r\n")
                    if line.startswith("data:"):
                        value = line[5:]
                        parts.append(value[1:] if value.startswith(" ") else value)
                    elif not line and parts:
                        data = "\n".join(parts)
                        rec["events"].append([micros() - epoch, data])
                        parts.clear()
                        if data == "[DONE]":
                            break
                if not budget and (not rec["events"] or rec["events"][-1][1] != "[DONE]"):
                    rec["error"] = "response-budget"
    except (OSError, ValueError, UnicodeError, http.client.HTTPException, subprocess.SubprocessError):
        rec["error"] = "client-or-stream-error"
    rec["end_us"] = micros() - epoch
    return rec


def read_events(rec, model):
    chunks = []
    first = None
    stopped = False
    done = False
    valid = rec["http"] == 200 and rec["sse"] and rec["error"] is None
    usage = None
    stream_id = None
    try:
        for stamp, wire in rec["events"]:
            if wire == "[DONE]":
                require(not done and stopped, "missing stop")
                done = True
                continue
            event = decode(wire)
            require(not done and "error" not in event and event.get("model") == model, "wrong generation")
            if "id" in event:
                require(isinstance(event["id"],str) and (stream_id is None or stream_id == event["id"]),
                        "changed streaming completion identity")
                stream_id = event["id"]
            choices = event["choices"]
            if event.get("usage") is not None:
                reported = event["usage"]
                require(isinstance(reported, dict), "usage")
                usage = {k:reported[k] for k in ("prompt_tokens", "completion_tokens")
                         if type(reported.get(k)) is int and reported[k] >= 0}
            if choices == []:  # Standard post-stop usage frame
                require(stopped and usage is not None, "unexpected empty choices")
                continue
            require(isinstance(choices, list) and len(choices) == 1 and not stopped, "choice sequence")
            choice = choices[0]
            require(type(choice["index"]) is int and choice["index"] == 0, "choice index")
            delta = choice["delta"]
            text = delta.get("content")
            require(text is None or isinstance(text, str), "content is not text")
            require(not any(k in delta for k in ("tool_calls","function_call","refusal")), "non-text output")
            if text:
                chunks.append(text)
                if first is None:
                    first = stamp
            reason = choice.get("finish_reason")
            require(reason is None or reason == "stop", "incomplete finish")
            stopped = reason == "stop"
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        valid = False
    return "".join(chunks), first, bool(valid and done and stopped and chunks), usage


def native_tokens(port, text, timeout, maximum):
    body = json.dumps({"content":text,"add_special":False,"parse_special":False}).encode()
    with http_stream(port,body,timeout,path="/tokenize",accept="application/json") as (status,_,response):
        require(status == 200, "tokenizer HTTP")
        raw = response.read(maximum + 1)
        require(len(raw) <= maximum, "tokenizer response budget")
        tokens = decode(raw)["tokens"]
        require(type(tokens) is list and all(type(n) is int and n >= 0 for n in tokens), "invalid token IDs")
        return tokens
