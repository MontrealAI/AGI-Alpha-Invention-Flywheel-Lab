# SPDX-License-Identifier: Apache-2.0
"""Exercise approved input rebinding on portable restore using the historical mixture."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "claim-binding"))
from replay import BRIDGE_ROOT, FixtureRuntime, UniversalMissionService, case_requirements, correction
from bridge.pages_missions import PagesMissions
from bridge.workflows import digest


def run():
    history = json.loads((HERE.parent / "claim-binding" / "HISTORICAL-M06.json").read_bytes())
    ambition, requirements = history["ambition"], case_requirements(history["approved_data"])
    tools = ["construct_table", "run_table"]
    role = {"provider": "fixture", "model": "captured-replay-and-authored-correction"}
    evidence_file = {"schema": "frontier/local-mission-input-v1", "ambition": ambition, "language": "en",
                     "requirements": requirements, "tools": tools}
    original_spec = {"ambition": ambition, "language": "en", **role, "requirements": requirements, "tools": tools,
                     "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                     "max_turns": 2, "max_actions": 10, "max_output_tokens": 1024}

    with TemporaryDirectory() as root:
        with_source = UniversalMissionService(FixtureRuntime([correction(requirements)]), Path(root) / "original")
        reopened = UniversalMissionService(FixtureRuntime([correction(requirements)]), Path(root) / "restored")
        refused = UniversalMissionService(FixtureRuntime([]), Path(root) / "other")
        try:
            registered = with_source.submit(original_spec)
            before = with_source.step(registered["id"])
            archive = with_source.export(registered["id"])
            bridge = PagesMissions(reopened, role=role, evidence_input=evidence_file, announce=lambda code: None)
            imported = bridge.import_local(archive)
            restored = reopened.get(imported["id"])
            reopened.resume(imported["id"], background=False)
            claimed = reopened.step(imported["id"])
            other = PagesMissions(refused, role=role, evidence_input={**evidence_file, "language": "fr"},
                                  announce=lambda code: None).import_local(archive)
            assert before["evidence"]["status"] == claimed["evidence"]["status"] == "VERIFIED"
            assert restored["status"] == "paused" and restored["evidence"]["status"] == "ABSTAIN"
            assert {row["reason"] for row in restored["evidence"]["claims"]} == {"NO_BOUND_EXECUTION"}
            assert restored["original_ambition"] == ambition and restored["parent_run_id"] == before["id"]
            assert restored["spec"]["mission"]["requirements"] == requirements
            assert set(restored["artifacts"]) == set(archive["files"])
            assert other["evidence"]["status"] == "UNVERIFIED" and not other["evidence"]["claims"]
            assert claimed["qualification"] == "UNVERIFIED"
            return {"scope": "Native runtime and Pages bridge with operator-authored actions and no live model inference",
                    "bridge_sha256": sha256((BRIDGE_ROOT / "bridge" / "pages_missions.py").read_bytes()).hexdigest(),
                    "original": ambition, "manifest_sha256": digest(evidence_file), "original_export_sha256": archive["sha256"],
                    "before": before["evidence"]["status"], "restore": restored["status"],
                    "exact_ambition_and_prior_retained": True, "approved_inputs_rebound": True,
                    "restored_before_fresh_execution": restored["evidence"]["status"],
                    "unmatched_manifest": other["evidence"]["status"], "after_fresh_execution": claimed["evidence"]["status"],
                    "after_fresh_quantities": {row["id"]: row["value"] for row in claimed["evidence"]["claims"]},
                    "whole_mission_qualification": claimed["qualification"]}
        finally:
            for runner in (with_source, reopened, refused):
                runner.close()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, ensure_ascii=False))
