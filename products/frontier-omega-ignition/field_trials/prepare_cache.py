"""Prepare the two pinned CPU inputs and retain an acquisition-only receipt."""
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from http.client import IncompleteRead, RemoteDisconnected
import json
import os
from pathlib import Path
import signal
import socket
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "products/alpha-genesis-harness"))
from connected_enterprise.platform_runtime import command_budget
from scripts import qualify_hosted_local as pins

ASSETS = (("llama.tar.gz", pins.BINARY_URL, pins.BINARY_ARCHIVE_BYTES, pins.BINARY_ARCHIVE_SHA),
          ("model.gguf", pins.MODEL_URL, pins.MODEL_BYTES, pins.MODEL_SHA))
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


class InputRefused(ValueError):
    """Only these program-authored explanations may enter a public receipt."""


@contextmanager
def platform_window():
    seconds = command_budget()["timeout_seconds"]
    if seconds is None:
        yield
        return

    def expired(signum, frame):
        raise TimeoutError("Hosted platform receipt reserve reached")

    handler = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)


class PublisherRedirect(HTTPRedirectHandler):
    def __init__(self, origin):
        super().__init__()
        self.origin = origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        host = target.hostname or ""
        github = self.origin == "github.com" and host in {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
        hf = self.origin == "huggingface.co" and (host == "huggingface.co" or host.endswith((".hf.co", ".huggingface.co")))
        secure = target.scheme == "https" and target.username is None and target.password is None and target.port in (None, 443)
        if not secure or not (github or hf):
            raise InputRefused("Unexpected publisher redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def quarantine(path, cache):
    folder = cache / "quarantine"
    folder.mkdir(exist_ok=True, mode=0o700)
    with NamedTemporaryFile(dir=folder, prefix=path.name + "-", delete=False) as target:
        destination = Path(target.name)
    path.replace(destination)
    return destination.relative_to(cache).as_posix()


def retry_delay(error, index):
    if isinstance(error, HTTPError):
        if error.code not in TRANSIENT_HTTP:
            return None
        requested = (error.headers or {}).get("Retry-After")
        if requested:
            try:
                if requested.isascii() and requested.isdecimal():
                    seconds = int(requested)
                else:
                    seconds = (parsedate_to_datetime(requested) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                return None
            if seconds > 30:
                return None
            return max(2 ** index, seconds)
    else:
        cause = error.reason if isinstance(error, URLError) else error
        if not (isinstance(cause, (TimeoutError, ConnectionResetError, RemoteDisconnected, IncompleteRead)) or
                isinstance(cause, socket.gaierror) and cause.errno == socket.EAI_AGAIN):
            return None
    return 2 ** index


def retrieve(asset, cache, staged, attempt):
    name, origin, size, expected = asset
    opener = build_opener(PublisherRedirect(urlsplit(origin).hostname))
    clock = command_budget()["timeout_seconds"]
    h = hashlib.sha256()
    count = 0
    with opener.open(origin, timeout=min(120, clock) if clock is not None else 120) as response, staged.open("xb") as out:
        attempt["response_host"] = urlsplit(response.geturl()).hostname
        declared = response.headers.get("Content-Length")
        while True:
            command_budget()
            block = response.read(min(4 * 1024 * 1024, size + 1 - count))
            if not block:
                break
            out.write(block)
            h.update(block)
            count += len(block)
            attempt["bytes_read"] = count
            if count > size:
                break
    attempt["received_sha256"] = h.hexdigest()
    if count < size and declared == str(size):
        raise ConnectionResetError("Transfer ended before the declared length")
    if count != size or h.hexdigest() != expected:
        attempt["quarantine"] = quarantine(staged, cache)
        raise InputRefused("Received content differs from pinned identity")
    staged.replace(cache / name)


def prepare(asset, cache, record, checkpoint):
    name, origin, size, expected = asset
    dest = cache / name
    record.update(name=name, origin=origin, expected_bytes=size, expected_sha256=expected, attempts=[])
    checkpoint()
    command_budget()
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or not dest.is_file():
            raise InputRefused("Cache entry must be a regular file")
        record["cached_bytes"] = dest.stat().st_size
        record["cached_sha256"] = pins.sha(dest)
        if record["cached_bytes"] != size or record["cached_sha256"] != expected:
            record["quarantine"] = quarantine(dest, cache)
            raise InputRefused("Existing cache differs from pinned identity")
        record["status"] = "verified_existing"
        return
    with TemporaryDirectory(dir=cache, prefix=".prefetch-") as tmp:
        for number in range(1, 4):
            started = time.monotonic()
            attempt = {"number": number, "bytes_read": 0, "status": "started"}
            record["attempts"].append(attempt)
            checkpoint()
            part = Path(tmp) / name
            try:
                retrieve(asset, cache, part, attempt)
                attempt["status"] = "verified"
                record["status"] = "verified_download"
                return
            except (OSError, ValueError, IncompleteRead) as error:
                attempt.update(status="failed", error_type=type(error).__name__)
                if isinstance(error, HTTPError):
                    attempt.update(http_status=error.code, response_host=urlsplit(error.geturl()).hostname)
                    error.close()
                delay = retry_delay(error, number)
                remaining = command_budget()["timeout_seconds"]
                if number == 3 or delay is None or (remaining is not None and remaining <= delay):
                    raise
                attempt["retry_after_seconds"] = delay
                part.unlink(missing_ok=True)
            finally:
                attempt["wall_seconds"] = round(time.monotonic() - started, 4)
                checkpoint()
            time.sleep(delay)


def record_preparation(cache, output):
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": "ignition.cpu-inputs.v1", "checkout_revision": pins.git("rev-parse", "HEAD"),
              "started_at": datetime.now(timezone.utc).isoformat(),
              "pins_source_sha256": pins.sha(Path(pins.__file__)), "preparer_sha256": pins.sha(Path(__file__)),
              "assets": [], "prepared": False, "scope": "Public file acquisition only", "billing": None}
    started, cpu = time.monotonic(), time.process_time()

    def checkpoint():
        record["wall_seconds"] = round(time.monotonic() - started, 4)
        record["cpu_seconds"] = round(time.process_time() - cpu, 4)
        with NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as handle:
            json.dump(record, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(handle.name, output)

    item = record
    try:
        with platform_window():
            for asset in ASSETS:
                item = {"status": "preparing"}
                record["assets"].append(item)
                prepare(asset, cache, item, checkpoint)
            record["prepared"] = True
    except (OSError, ValueError, IncompleteRead) as error:
        record["prepared"] = False
        item["status"] = "failed"
        if item is record:
            record["stage"] = "platform_window"
        # HTTP exception text can contain temporary signed redirect URLs.
        item["obstruction"] = str(error) if isinstance(error, InputRefused) else type(error).__name__
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint()
    print(json.dumps(record, allow_nan=False))
    return record["prepared"]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    options = parser.parse_args()
    sys.exit(0 if record_preparation(options.assets, options.receipt) else 1)
