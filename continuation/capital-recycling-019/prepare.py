import json
from pathlib import Path

from adaptive_enterprise.instruments import prepare_services
from enterprise.services import prepare_services as prepare_enterprise_services

root = Path(__file__).resolve().parents[2]
manifest_path = root / "continuation/capital-recycling-019/services/MANIFEST.json"
manifest = (
    json.loads(manifest_path.read_text())
    if manifest_path.exists()
    else prepare_services(root, "continuation/capital-recycling-019/services", cohort_seed=19019)
)
enterprise_manifest_path = root / "continuation/capital-recycling-019/enterprise-services/MANIFEST.json"
enterprise_manifest = (
    json.loads(enterprise_manifest_path.read_text())
    if enterprise_manifest_path.exists()
    else prepare_enterprise_services(root, "continuation/capital-recycling-019/enterprise-services")
)
catalogue = json.loads((root / "portfolio_scale/universe.json").read_text())
bundles = json.loads((root / "portfolio_scale/reference_bundles.json").read_text())
summary = {
    "manifest_jobs": len(manifest["jobs"]),
    "accepted_jobs": sum(x["accepted"] for x in manifest["jobs"]),
    "enterprise_manifest_jobs": len(enterprise_manifest["jobs"]),
    "enterprise_accepted_jobs": sum(x["accepted"] for x in enterprise_manifest["jobs"]),
    "catalogue_jobs": len(catalogue["jobs"]),
    "catalogue_families": len({x["family"] for x in catalogue["jobs"]}),
    "catalogue_segments_mandate_assertion": 4,
    "catalogue_tiers_mandate_assertion": 2,
    "reference_bundles": len(bundles["sample_enterprise_programs"]),
    "manifest": "continuation/capital-recycling-019/services/MANIFEST.json",
}
(root / "continuation/capital-recycling-019/PREPARE_RESULT.json").write_text(
    json.dumps(summary, sort_keys=True, indent=2) + "\n"
)
print(json.dumps(summary, sort_keys=True))
