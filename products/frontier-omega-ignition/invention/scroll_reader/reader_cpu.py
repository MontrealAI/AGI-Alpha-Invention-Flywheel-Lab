"""Run the registered CPU Reader V3 comparison on two real CT panels."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

UPSTREAM = "4c0a117f4ae983992bbe2ce134c0389d7280f120"
PATCH = "336420772c845a10ece5edf316ab7494d79662390580112496299a0524727c57"
CHECKPOINT = "ea405417450abd8ace1b8ff79ebce3adb646c5e48ab95da46844d77efe984d8a"
WEIGHTS = ("https://huggingface.co/domenicor046/reader-v3/resolve/"
           "aee1d64bced4eb35546348f3d276b9e2a0b99c46/reader-v3.pth")
ZARR = ("https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0139/segments/"
        "20260206000002-w054_2026020617/surface-volumes/"
        "9.362um-1.2m-113keV-volume-20250728140407.zarr/0")
PANELS = {
    "edge": (29, 84, "ac28e093f969c673e73185085f5906d1315b8086e02808c532d00d1abadfcf08"),
    "ordinary": (39, 39, "36375d679d00528c821c161cfe0b56c8fa3ebd6664f4ef2311fad98c4a0faf6c"),
}
ORDERS = (("histogram", "candidate"), ("candidate", "histogram"))
MODULE = "vesuvius.ink_detection.inference.infer"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(condition, message):
    if not condition:
        raise ValueError(message)


def download(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "MONTREAL-AI-Reader-qualification"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(limit + 1)
            verify(len(data) <= limit, "Object exceeds registered size: " + url)
            return data
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def checkpoint(work, cache):
    data = cache.read_bytes() if cache.exists() else download(WEIGHTS, 138379659)
    verify(len(data) == 138379659 and digest(data) == CHECKPOINT, "Checkpoint identity mismatch")
    if not cache.exists():
        cache.write_bytes(data)
    (work / "reader-v3.pth").symlink_to(cache)


def acquire(work, result, cache):
    checkpoint(work, cache)
    metadata = json.loads(download(ZARR + "/.zarray", 65536))
    required = dict(zarr_format=2, shape=[28, 7660, 11140], chunks=[28, 128, 128],
                    dtype="|u1", compressor=None, filters=None, order="C", fill_value=0,
                    dimension_separator="/")
    for name, value in required.items():
        verify(metadata.get(name) == value, "Unsupported source metadata: " + name)
    for panel, (y0, x0, expected) in PANELS.items():
        target = work / (panel + ".zarr")
        target.mkdir()
        (target / ".zarray").write_text(json.dumps(dict(metadata, shape=[28, 384, 384],
                                                        dimension_separator=".")))
        output = np.empty((28, 384, 384), dtype=np.uint8)
        chunks = {}
        for row in range(3):
            for col in range(3):
                key = f"0/{y0 + row}/{x0 + col}"
                chunk = download(ZARR + "/" + key, 28 * 128 * 128)
                verify(len(chunk) == 28 * 128 * 128, "Short CT chunk: " + key)
                chunks[key] = digest(chunk)
                (target / f"0.{row}.{col}").write_bytes(chunk)
                output[:, row*128:(row+1)*128, col*128:(col+1)*128] = np.frombuffer(
                    chunk, dtype=np.uint8).reshape(28, 128, 128)
        verify(digest(output.tobytes()) == expected, "Assembled panel differs: " + panel)
        result["panels"][panel] = {"sha256": expected, "source_chunk_sha256": chunks}


def picture(path, allow_constant=False):
    with Image.open(path) as tif:
        verify(tif.format == "TIFF" and tif.mode == "L" and tif.size == (384, 384),
               "Wrong TIFF type or dimensions")
        pixels = tif.tobytes()
    verify(allow_constant or min(pixels) < max(pixels), "Constant TIFF")
    return {"tiff_sha256": digest(path.read_bytes()), "pixels_sha256": digest(pixels),
            "min": min(pixels), "max": max(pixels), "distinct_uint8": len(set(pixels))}


def run_one(work, src, builds, panel, block, arm, *, allow_constant=False):
    run = work / f"{panel}-{block}-{arm}"
    run.mkdir()
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(
        (str(builds / ("installed-" + arm)), str(src / "vesuvius/src"))),
        OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
        TORCH_FORCE_WEIGHTS_ONLY_LOAD="1", CUDA_VISIBLE_DEVICES="",
        PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1")
    interpreter = [sys.executable, "-B"]
    native = subprocess.check_output(interpreter + ["-c",
        "import vc_reader._transforms as ext; print(ext.__file__)"], cwd=run, env=env,
        text=True).strip()
    prefix = (builds / ("installed-" + arm)).resolve()
    verify(Path(native).resolve().is_relative_to(prefix), "Loaded the wrong native reader")
    command = interpreter + ["-m", MODULE, str(work / (panel + ".zarr")),
        str(work / "reader-v3.pth"), str(run / "out.tif"), "--device", "cpu",
        "--no-compile", "--workers", "0", "--batch-size", "1", "--direction", "both",
        "--overlap", "0.5", "--blend-mode", "hann"]
    log = run / "infer.log"
    with log.open("w") as stream:
        proc = subprocess.run(["/usr/bin/time", "-f", "%e %U %S %M", "-o", "cost", *command],
                              cwd=run, env=env, stdout=stream, stderr=subprocess.STDOUT)
    logged = log.read_text(errors="replace")
    if proc.returncode:
        print(logged[-10000:], file=sys.stderr)
        raise RuntimeError(f"Native CLI failed: panel={panel} block={block} arm={arm} rc={proc.returncode}")
    verify(logged.count("missing_keys=0 unexpected_keys=0") == 1, "Checkpoint loading unverified")
    verify(logged.count("Selected 1 patches for inference") == 2, "Two single-patch directions required")
    wall, user, system, rss = (run / "cost").read_text().strip().split()
    return {"arm": arm, "panel": panel, "block": block, "wall_s": float(wall),
            "user_cpu_s": float(user), "system_cpu_s": float(system), "peak_rss_kib": int(rss),
            "native_extension_sha256": digest(Path(native).read_bytes()),
            "forward": picture(run / "out.tif", allow_constant),
            "reverse": picture(run / "out_reverse.tif", allow_constant)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("builds", type=Path)
    parser.add_argument("receipts", type=Path)
    args = parser.parse_args()
    src, builds, receipts = [p.resolve() for p in (args.source, args.builds, args.receipts)]
    receipts.mkdir(parents=True, exist_ok=True)
    receipt = receipts / "reader-v3.json"
    result = {"status": "incomplete", "upstream_sha": UPSTREAM, "candidate_patch_sha256": PATCH,
              "release_candidate_sha": os.environ.get("QUALIFICATION_SHA"),
              "runner": platform.platform(), "python": sys.version, "checkpoint_sha256": CHECKPOINT,
              "panels": {}, "wheels": {}, "runs": [], "monetary_cost": None,
              "billing_scope": "No billing record supplied; CPU, elapsed time and memory measured."}
    started = time.monotonic()

    def save():
        result["comparison_elapsed_s"] = time.monotonic() - started
        temp = receipt.with_suffix(".tmp")
        temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        temp.replace(receipt)

    try:
        verify(subprocess.check_output(["git", "-C", src, "rev-parse", "HEAD"],
               text=True).strip() == UPSTREAM, "Wrong upstream revision")
        for arm in ORDERS[0]:
            wheel, = (builds / ("wheel-" + arm)).glob("*.whl")
            result["wheels"][arm] = {"file": wheel.name, "sha256": digest(wheel.read_bytes())}
        with tempfile.TemporaryDirectory(dir=builds) as tmp:
            work = Path(tmp)
            acquire(work, result, builds / "reader-v3-cache.pth")
            save()
            for panel in PANELS:
                expected = None
                for block, order in enumerate(ORDERS):
                    for arm in order:
                        run = run_one(work, src, builds, panel, block, arm)
                        result["runs"].append(run)
                        save()
                        products = [run["forward"], run["reverse"]]
                        if expected is None:
                            expected = products
                        verify(products == expected, "Paired outputs differ on " + panel)
        binaries = {run["native_extension_sha256"] for run in result["runs"]}
        verify(len(binaries) == 2, "Expected two distinct native transform builds")
        result["status"] = "paired_tiffs_equal"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
