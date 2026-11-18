"""Qualify one previously identified zero-MAD scheduled window through the native Reader."""
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

import numpy as np
import reader_cpu as study

PANEL = "scheduled-0000"
FORWARD = "9831dc954e988b83d056353b2e722599a13839e4cb4f4da3437564996a640fa1"
ALL_PLANES = "2864142ca6871c5e6aaf7d77c8cc8751b5c720deb9cf587809b3487271268a98"
PRESENT = "ac2aea93b5351af4b80e0a8fb76b742403f56765971b65cb8d88712ffd6f630e"


def acquire_sparse(work):
    source = urlsplit(study.ZARR)
    prefix = source.path.lstrip("/") + "/0/"
    base = f"{source.scheme}://{source.netloc}/"
    metadata = json.loads(study.download(study.ZARR + "/.zarray", 65536))
    schema = dict(zarr_format=2, shape=[28, 7660, 11140], chunks=[28, 128, 128],
                  dtype="|u1", compressor=None, filters=None, order="C", fill_value=0,
                  dimension_separator="/")
    study.verify(all(metadata.get(k) == v for k, v in schema.items()), "Changed Zarr metadata")
    target = work / (PANEL + ".zarr")
    target.mkdir()
    (target / ".zarray").write_text(json.dumps(dict(metadata, shape=[28, 384, 384],
                                                    dimension_separator=".")))
    data = np.zeros((28, 384, 384), dtype=np.uint8)
    fill = []
    listings = []
    for row in range(3):
        row_prefix = f"{prefix}{row}/"
        query = urlencode({"list-type": 2, "prefix": row_prefix, "max-keys": 1000})
        listing = study.download(base + "?" + query, 512_000)
        tree = ElementTree.fromstring(listing)
        study.verify(tree.findtext("{*}IsTruncated") == "false" and
                     tree.findtext("{*}Prefix") == row_prefix, "Incomplete object listing")
        keys = {node.findtext("{*}Key") for node in tree.findall("{*}Contents")}
        listings.append(study.digest(listing))
        for col in range(9, 12):
            key = f"{row_prefix}{col}"
            present = key in keys
            study.verify(present == ((row, col) == (2, 11)), "Changed sparse panel source key: " + key)
            if not present:
                fill.append([row, col])
                continue
            chunk = study.download(base + key, 28 * 128 * 128)
            study.verify(study.digest(chunk) == PRESENT, "Full source chunk identity changed")
            local_col = col - 9
            (target / f"0.{row}.{local_col}").write_bytes(chunk)
            data[:, row*128:(row+1)*128, local_col*128:(local_col+1)*128] = np.frombuffer(
                chunk, dtype=np.uint8).reshape(28, 128, 128)
    center = data[6:23]
    n_nonzero = int(np.count_nonzero(center))
    mad = float(np.median(np.abs(center.astype(np.int16) - np.median(center))))
    study.verify(study.digest(data.tobytes()) == ALL_PLANES and
                 study.digest(center.tobytes()) == FORWARD and n_nonzero == 10946 and mad == 0,
                 "Sparse panel differs from the independent production-window certificate")
    return {"ordinal": 0, "y": 0, "x": 1152, "shape": list(data.shape), "sha256": ALL_PLANES,
            "center_forward_sha256": FORWARD, "center_nonzero": n_nonzero, "center_mad": mad,
            "source_chunk_sha256": PRESENT, "missing_fill_chunks": fill, "listings_sha256": listings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("builds", type=Path)
    parser.add_argument("receipts", type=Path)
    args = parser.parse_args()
    src, builds, receipts = [p.resolve() for p in (args.source, args.builds, args.receipts)]
    receipts.mkdir(parents=True, exist_ok=True)
    output = receipts / "reader-v3-sparse.json"
    started = time.monotonic()
    result = {"status": "incomplete", "source": study.UPSTREAM,
              "release_candidate_sha": os.environ.get("QUALIFICATION_SHA"),
              "candidate_patch_sha256": study.PATCH, "checkpoint_sha256": study.CHECKPOINT,
              "monetary_cost": None, "runs": []}

    def save():
        result["comparison_elapsed_s"] = time.monotonic() - started
        tmp = output.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        tmp.replace(output)

    try:
        study.verify(subprocess.check_output(["git", "-C", src, "rev-parse", "HEAD"],
                     text=True).strip() == study.UPSTREAM, "Wrong upstream revision")
        with tempfile.TemporaryDirectory(dir=builds) as folder:
            work = Path(folder)
            study.checkpoint(work, builds / "reader-v3-cache.pth")
            result["input"] = acquire_sparse(work)
            save()
            expected = None
            for block, order in enumerate(study.ORDERS):
                for arm in order:
                    run = study.run_one(work, src, builds, PANEL, block, arm, allow_constant=True)
                    result["runs"].append(run)
                    save()
                    images = [run["forward"], run["reverse"]]
                    if expected is None:
                        expected = images
                    study.verify(expected == images, "Sparse TIFF/pixel mismatch")
            study.verify(len({r["native_extension_sha256"] for r in result["runs"]}) == 2,
                         "Expected distinct installed native readers")
            result["constant_output"] = {
                direction: result["runs"][0][direction]["distinct_uint8"] == 1
                for direction in ("forward", "reverse")}
            result["status"] = "paired_tiffs_equal"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
