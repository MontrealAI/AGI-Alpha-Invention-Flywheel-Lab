"""Reproduce the finite portfolio from public code and optional pinned public data."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SENSOR_URL = "https://archive.ics.uci.edu/static/public/270/gas%2Bsensor%2Barray%2Bdrift%2Bdataset%2Bat%2Bdifferent%2Bconcentrations.zip"


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def sensor_replay(output, archive=None, download=False):
    import numpy as np
    from portfolio071.sensor_interface import train
    from portfolio071.verify_sensor import EXPECTED_ARCHIVE, read_batches, verify
    output.mkdir(parents=True, exist_ok=False)
    if archive is None:
        if not download:
            raise ValueError("Provide the pinned research archive or explicitly request its public download")
        archive = output / "source.zip"
        with urllib.request.urlopen(SENSOR_URL, timeout=60) as response, archive.open("xb") as destination:
            shutil.copyfileobj(response, destination)
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != EXPECTED_ARCHIVE:
        raise ValueError("Public data archive identity mismatch")
    batches = output / "batches"
    batches.mkdir()
    expected = {"batch" + str(i) + ".dat" for i in range(1,11)}
    found = set()
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            if name in expected:
                if name in found or info.file_size > 30_000_000:
                    raise ValueError("Unexpected public-data member")
                found.add(name)
                with (batches / name).open("xb") as stream:
                    stream.write(z.read(info))
    if found != expected:
        raise ValueError("Missing registered chronological batch")
    data = output / "observations"
    data.mkdir()
    np.savez_compressed(data / "train.npz", **read_batches(batches,[1,2,3,4]))
    np.savez_compressed(data / "tune.npz", **read_batches(batches,[5]))
    train(data, output / "trained")
    return verify(batches,data,output/"trained",output/"verification",Path(archive))


def stage_native_source(output, thermal_evidence):
    from commercial.ledger import canonical
    from connected_enterprise.finance import SOURCE_PATHS
    from portfolio071.service import SOURCES, prepare_manifest
    target = output / "native-source"
    for name in sorted(set(SOURCE_PATHS) | set(SOURCES)):
        source = ROOT / name
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            raise ValueError("Symlink source refused")
        with destination.open("xb") as stream:
            stream.write(source.read_bytes())
    deliveries = []
    for label in ("k1","k2"):
        example = json.loads((thermal_evidence/(label+".json")).read_text())
        request, artifact = copy.deepcopy(example["request"]), copy.deepcopy(example["artifact"])
        request["id"] = "portfolio071-" + label
        deliveries.append((request,artifact))
    manifest = prepare_manifest(target,deliveries)
    write(output/"native-manifest.json",manifest)
    return target,manifest


def run(output, *, economics=True, sensor_archive=None, download_sensor=False):
    from portfolio071.verify_purpose import run as verify_purpose
    from portfolio071.verify_thermal import run as verify_thermal
    from portfolio071.verify_foundry import run as verify_foundry
    output = Path(output).absolute()
    output.mkdir(parents=True,exist_ok=False)
    wall,cpu = time.monotonic(),time.process_time()
    purpose = verify_purpose(output/"r1"/"RESULTS.json")
    thermal = verify_thermal(output/"r3")
    foundry = verify_foundry(output/"r5")
    sensor = None
    if sensor_archive is not None or download_sensor:
        sensor = sensor_replay(output/"r2",sensor_archive,download_sensor)
    economic = None
    if economics:
        from portfolio071.economics import run_campaign
        source,manifest = stage_native_source(output,output/"r3")
        economic = run_campaign(source,manifest,output/"economics")
    summary = {"schema":"portfolio071/reproduction/v1", "scientific_source_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"portfolio071").glob("*.py"))},
               "routes":{"R1":"independent finite-model replay completed", "R2":sensor["verdict"] if sensor else "NOT_RERUN; public recorded negative evidence is separate", "R3":{"K1":thermal["k1_accepted"],"K2":thermal["k2_accepted"],"physical_qualification":False},"R4":{"native_arms":economic["completed_arms"],"milestone_3b_count":economic["milestone_3b_count"]} if economic else "NOT_RERUN", "R5":"independent finite-model replay completed"},
               "actual_external_revenue_usd":0,"physical_deployments":0,"paid_model_api_calls":0,
               "resource_use":{"process_cpu_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-wall,"model_tokens":None,"actual_host_or_model_bill":None},
               "claim_boundary":"Source-matched replay is not new blinded scientific confirmation, market validation, industrial qualification or a global optimality proof."}
    write(output/"SUMMARY.json",summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--skip-economics",action="store_true")
    parser.add_argument("--sensor-archive",type=Path)
    parser.add_argument("--download-sensor",action="store_true")
    args=parser.parse_args()
    result=run(args.output,economics=not args.skip_economics,sensor_archive=args.sensor_archive,download_sensor=args.download_sensor)
    print(json.dumps(result["routes"],sort_keys=True))


if __name__=="__main__":
    main()
