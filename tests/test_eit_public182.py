"""Offline adversarial tests. Deliberately no physical measurements or network calls."""
import importlib.util
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "research/eit_public182/intake.py"
spec = importlib.util.spec_from_file_location("eit_public182_intake", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_record():
    names = ("AgarCylinderPhantom.zip", "AgarChestPhantom.zip", "HeadPhantom.zip")
    return {
        "id": 24120439,
        "doi": "10.5281/zenodo.24120439",
        "metadata": {
            "title": "Open Electrical Impedance Tomography data from phantoms with moderate conductivity contrast",
            "rights": [{"id": "cc-by-4.0"}],
        },
        "files": [
            {"key": name, "size": i * 123456,
             "checksum": "md5:" + format(i, "032x"),
             "links": {"self": "https://zenodo.org/api/records/24120439/files/" + name + "/content"}}
            for i, name in enumerate(names, 1)
        ],
    }


class IntakeOfflineTests(unittest.TestCase):
    def test_complete_metadata_is_explicitly_not_physical_evidence(self):
        receipt = module.validate(sample_record(), "a" * 64)
        self.assertEqual(receipt["phantom_classes_present"], list(module.PHANTOMS))
        self.assertFalse(receipt["archive_bytes_independently_hashed"])
        self.assertFalse(receipt["physical_measurements_analyzed"])
        self.assertFalse(receipt["clinical_or_commercial_claim"])
        self.assertEqual(len(receipt["files"]), 3)

    def test_missing_phantom_refused_without_choosing_convenient_case(self):
        x = sample_record()
        x["files"].pop()
        with self.assertRaisesRegex(module.IntakeRefusal, "MISSING_REGISTERED_PHANTOM_CLASS"):
            module.validate(x, "a" * 64)

    def test_wrong_identity_refused(self):
        x = sample_record()
        x["id"] = 24120438
        with self.assertRaisesRegex(module.IntakeRefusal, "WRONG_RECORD_ID"):
            module.validate(x, "a" * 64)

    def test_missing_doi_refused(self):
        x = sample_record()
        x["doi"] = "10.5281/zenodo.1"
        with self.assertRaisesRegex(module.IntakeRefusal, "DOI_NOT_BOUND"):
            module.validate(x, "a" * 64)

    def test_unverified_rights_refused(self):
        x = sample_record()
        x["metadata"].pop("rights")
        with self.assertRaisesRegex(module.IntakeRefusal, "LICENSE_UNVERIFIED"):
            module.validate(x, "a" * 64)

    def test_untrusted_archive_host_refused(self):
        x = sample_record()
        x["files"][0]["links"]["self"] = "https://attacker.invalid/a.zip"
        with self.assertRaisesRegex(module.IntakeRefusal, "UNTRUSTED_FILE_URL"):
            module.validate(x, "a" * 64)

    def test_unsafe_path_refused(self):
        x = sample_record()
        x["files"][0]["key"] = "../AgarCylinderPhantom.zip"
        with self.assertRaisesRegex(module.IntakeRefusal, "UNSAFE_OR_MISSING"):
            module.validate(x, "a" * 64)

    def test_missing_checksum_refused(self):
        x = sample_record()
        x["files"][0]["checksum"] = ""
        with self.assertRaisesRegex(module.IntakeRefusal, "INVALID_DECLARED_CHECKSUM"):
            module.validate(x, "a" * 64)

    def test_boolean_size_not_accepted_as_integer(self):
        x = sample_record()
        x["files"][0]["size"] = True
        with self.assertRaisesRegex(module.IntakeRefusal, "INVALID_DECLARED_SIZE"):
            module.validate(x, "a" * 64)

    def test_duplicate_name_even_with_case_change_refused(self):
        x = sample_record()
        duplicate = dict(x["files"][0], key="agarcylinderphantom.ZIP")
        x["files"].append(duplicate)
        with self.assertRaisesRegex(module.IntakeRefusal, "DUPLICATE_FILE"):
            module.validate(x, "a" * 64)

    def test_duplicate_json_fields_refused(self):
        with self.assertRaisesRegex(module.IntakeRefusal, "DUPLICATE_JSON_KEY"):
            json.loads('{"id":24120439,"id":24120439}', object_pairs_hook=module.unique_pairs)

    def test_no_url_substitution(self):
        with self.assertRaisesRegex(module.IntakeRefusal, "SOURCE_URL_CHANGED"):
            module.read_record("https://zenodo.org/api/records/999")

    def test_deterministic_receipt(self):
        a = module.validate(sample_record(), "b" * 64)
        b = module.validate(sample_record(), "b" * 64)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
