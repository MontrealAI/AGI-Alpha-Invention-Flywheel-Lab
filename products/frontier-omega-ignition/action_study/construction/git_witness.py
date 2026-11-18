"""Recover UTC epochs from the actual native Git objects with their original identities."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from time import monotonic

HERE = Path(__file__).resolve().parent


def capture(repo, source):
    start = monotonic()
    def git(*args, input_bytes=None):
        return subprocess.run(["git", "-C", str(repo), *args], input=input_bytes,
                              stdout=subprocess.PIPE, check=True).stdout

    rev = git("rev-parse", source["tag"] + "^{commit}").decode().strip()
    if rev != source["commit"]:
        raise ValueError("selected Git release does not match the REST source")
    ids = [r["oid"] for r in source["commits"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate source object IDs")
    raw = git("cat-file", "--batch", input_bytes=("\n".join(ids) + "\n").encode())
    from io import BytesIO
    stream = BytesIO(raw)
    entries = []
    for oid in ids:
        oid_bytes, kind, size = stream.readline().split()
        if oid_bytes.decode() != oid or kind != b"commit":
            raise ValueError("missing or substituted native Git object")
        obj = stream.read(int(size))
        if (stream.read(1) != b"\n" or len(obj) != int(size) or
                hashlib.sha1(b"commit " + size + b"\x00" + obj).hexdigest() != oid):
            raise ValueError("native Git object bytes do not match their ID")
        headers = obj.split(b"\n\n", 1)[0].splitlines()
        times = {}
        for name in ("author", "committer"):
            line, = [h for h in headers if h.startswith(name.encode() + b" ")]
            times[name] = int(line.rsplit(b" ", 2)[-2])
        entries.append([oid, times["author"], times["committer"]])
    return {"git": git("--version").decode().strip(), "release_commit": rev,
            "observed_utc": datetime.now(timezone.utc).isoformat(), "columns": ["oid", "author_epoch", "committer_epoch"],
            "entries": entries, "native_object_bytes_read_including_batch_headers": len(raw),
            "capture_seconds_excluding_checkout": round(monotonic()-start, 6)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkout", type=Path)
    ap.add_argument("output", type=Path)
    opt = ap.parse_args()
    result = capture(opt.checkout, json.loads((HERE / "source_clocks.json").read_bytes()))
    with opt.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, separators=(",", ":"))
        out.write("\n")
    print(len(result["entries"]), "content-verified original Git objects")
