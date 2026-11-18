"""Build a scorer-free public work packet for the direct AI/hybrid route."""
import hashlib
import shutil
from pathlib import Path

from . import archive
from . import fieldkit as kit


def build(directory):
    root = Path(directory)
    root.mkdir(mode=0o700)
    (root / "tools").mkdir()
    for source in (archive.BROKER / "broker_control.py", archive.EXPOSURES / "avro_packet.py"):
        shutil.copyfile(source, root / "tools" / source.name)
    plan, roster = archive.plan_and_cases()
    expected = archive.pins()
    notice, indexed, acquired = archive.index(expected)
    kit.write(root / "notice.json", {"target": notice.target, "issue_utc": notice.issued, "deadline_utc": notice.deadline,
                                     "bands": notice.bands})
    kit.write(root / "tasks.json", {"protocol_sha256": kit.digest({"plan": plan, "cases": roster}), "tasks": [
        {k: c[k] for k in ("case_id", "band", "cutoff_utc", "source_set_sha256", "question")} for c in roster]})
    projection = kit.load(archive.EXPOSURES / "sources/detections.json")
    for i, cutoff in enumerate(archive.SLOTS, 1):
        folder = root / str(i)
        folder.mkdir()
        stop = archive.mjd(cutoff)
        permitted = {cid: v for cid, v in indexed.items() if v[0] < stop}
        packet_digests = {}
        for cid in permitted:
            raw = archive.raw_packet(cid, expected)
            (folder / (str(cid) + ".avro")).write_bytes(raw)
            packet_digests[str(cid)] = hashlib.sha256(raw).hexdigest()
        kit.write(folder / "tap-prefix.json", {"publisher": "ALeRCE", "population": "bounded original TAP query; prefix on observation UTC",
                  "cutoff_utc": cutoff, "tap_query": archive.direct.selection_query(notice), "original_tap_sha256": expected["index"],
                  "tap_received_utc": acquired.isoformat(), "columns": ["candid", "mjd", "fid", "rfid", "pid"],
                  "rows": [[str(k), *v] for k, v in permitted.items()], "packet_sha256": packet_digests})
        kit.write(folder / "broker-projection.json", {"publisher": "ALeRCE", "target": notice.target, "cutoff_utc": cutoff,
                  "detections": [r for r in projection["detections"] if r["mjd"] < stop]})
    # The final work packet contains public evidence and two reusable decoders, never an arm result or grading key.
    (root / "TASK.md").write_text("""Review the six pending positive difference-light questions in tasks.json.
Use only this packet, your included intelligence and local standard-library software. Read event folders 1, 2, 3 in order. For each pair, use only that folder, notice.json and the two reusable public tools. The later folders contain information unavailable to an earlier exposure-time cutoff. Historical source ingestion times at those cutoffs are unknown. The raw observations are original public ZTF Avro packets; the JSON TAP prefix and broker photometry are derived source projections. The complete conventional routines in tools/ may be adopted. No network query, external authority, existing answer key or campaign result is needed.

For each band match program 1, positive difference flux, target, field, readout, filter, reference image and packet identity to both issue anchors. Use the first eligible repeat at least 0.5 d after trigger and inside the issue-to-deadline window before the exposure cutoff. An earlier same-reference row without a required original packet leaves the case unresolved. For an eligible measurement compute signed PSF magnitude change from baseline and quadrature formal uncertainty in mag. Compare with max(0.2 mag, 2 sigma). Classify as persisted or reversed relative to the trigger change if significant, otherwise not_reproduced. Return keep_open before a qualifying original packet exists. All actions are archival shadow recommendations.

Write answers.json containing protocol_sha256 (from tasks.json) and a responses array with case_id, source_set_sha256 and answer. An open answer is {"action":"keep_open"}. A delivered answer is {"action":"deliver","measurement":{"witness":"<candid>", "reference":"<rfid>", "baseline":"<candid>", "trigger":"<candid>", "packet_sha256":"<sha256 of original uncompressed packet>", "direction":"persisted/reversed/not_reproduced", "unit":"mag", "delta_mag":<number>, "sigma_mag":<number>}}. Add a short route description and actual execution clocks separately in worker.json. Keep your script for reproduction. Do not communicate outside this study.
""", encoding="utf-8")
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}
    kit.write(root / "input-manifest.json", {"files": manifest, "task_sha256": kit.digest(manifest)})
    return kit.digest(manifest)
