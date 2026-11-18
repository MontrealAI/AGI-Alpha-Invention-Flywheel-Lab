"""Acquire public Git object clocks without retaining names, e-mail or free-text messages."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.request import Request, urlopen

API = "https://api.github.com/repos/git/git"
TAG = "v2.47.0"


def acquire():
    exchanges = []
    start = monotonic()

    def fetch(path):
        url = API + path
        request = Request(url, headers={"Accept": "application/vnd.github+json",
                                        "User-Agent": "Frontier-Omega-Git-Clock-Study"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("unexpected response size")
            exchanges.append({"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                              "response_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw)

    obj = fetch("/git/ref/tags/" + TAG)["object"]
    if obj["type"] == "tag":
        obj = fetch("/git/tags/" + obj["sha"])["object"]
    if obj["type"] != "commit":
        raise ValueError("release tag did not resolve to a commit")
    commits = []
    for page in (1, 2):
        found = fetch(f"/commits?sha={obj['sha']}&per_page=100&page={page}")
        commits += [{"oid": item["sha"], "author": item["commit"]["author"]["date"],
                     "committer": item["commit"]["committer"]["date"]} for item in found]
        if sum(r["oid"][-1] not in "0123" and r["author"][:16] == r["committer"][:16]
               for r in commits) >= 2:
            break
    return {"publisher": "Git project, via GitHub REST", "tag": TAG, "commit": obj["sha"],
            "route": "GitHub commits list, returned order", "exchanges": exchanges, "commits": commits,
            "elapsed_seconds": round(monotonic() - start, 6)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = acquire()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    print("Acquired", len(data["commits"]), "public commit-clock observations")
