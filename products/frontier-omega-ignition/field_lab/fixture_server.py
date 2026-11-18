"""A deterministic local stream target for apparatus qualification; no AI inference."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time


def direct_answer(brief):
    latency = re.search(r"(\d+(?:[.,]\d+)?)\s+(ms|s)\b", brief)
    rate = re.search(r"(\d+(?:[.,]\d+)?)\s+tokens/s (?:per user|par utilisateur)", brief)
    if "P90" not in brief or not latency or not rate:
        return {"status": "defer"}
    def value(number):
        return float(number.replace(",", "."))
    return {"status": "ready", "p90_ms": value(latency[1]) * (1000 if latency[2] == "s" else 1),
            "min_rate": value(rate[1])}


@contextlib.contextmanager
def serve(profile):
    if profile not in {"nominal", "adverse"}:
        raise ValueError("unknown fixture profile")
    seen = set()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            brief = request["messages"][-1]["content"]
            model = request["model"]
            output = json.dumps(direct_answer(brief), separators=(",", ":"))
            if profile == "adverse":
                if brief.startswith("Soutien"):
                    output = '{"status":"ready","p90_ms":321,"min_rate":80}'
                if brief.startswith("Research"):
                    with lock:
                        first = brief not in seen
                        seen.add(brief)
                    if first:
                        self.send_error(503)
                        return
                if brief.startswith("Editor"):
                    output = ""
                if brief.startswith("Portail"):
                    model = "different-fixture-revision"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            def emit(content, reason=None):
                event = {"model": model, "choices":[{"index":0, "delta":{"content":content},
                                                     "finish_reason":reason}]}
                self.wfile.write(("data: " + json.dumps(event, separators=(",", ":")) + "\n\n").encode())
                self.wfile.flush()
            # Content is deliberately fragmented. Never equate a frame with a token.
            time.sleep(0.008)
            emit(output[:3])
            if profile == "adverse" and brief.startswith("Atelier"):
                return
            time.sleep(0.002)
            emit(output[3:])
            emit("", "stop")
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval":0.02}, daemon=True)
    thread.start()
    try:
        yield server.server_port, seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
