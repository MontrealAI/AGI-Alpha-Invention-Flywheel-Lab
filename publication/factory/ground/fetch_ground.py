"""Retrieve and verify the two public ExoFOP timing photometry files."""

from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request, urlopen

MANIFEST_SHA256 = "31d967a00f2e5b339c70e4c16d14cb0a983a699cab9233ddf59a9ceb011c5bea"


def main():
    root = Path(__file__).resolve().parent
    manifest = (root / "EXOFOP-FILES.json").read_bytes()
    if sha256(manifest).hexdigest() != MANIFEST_SHA256:
        raise ValueError("The fixed public ExoFOP request manifest changed")
    directory = root / "exofop"
    directory.mkdir(exist_ok=True)
    for source in json.loads(manifest):
        name = source["file_name"]
        if Path(name).name != name:
            raise ValueError("Expected a plain original archive filename")
        path = directory / name
        if path.is_file():
            payload = path.read_bytes()
        else:
            request = Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                payload = response.read(source["bytes"] + 1)
        if len(payload) != source["bytes"] or sha256(payload).hexdigest() != source["sha256"]:
            raise ValueError(f"Unexpected public archive bytes for {name}")
        if not path.is_file():
            with path.open("xb") as stream:
                stream.write(payload)
        print(source["file_id"], name, len(payload))


if __name__ == "__main__":
    main()
