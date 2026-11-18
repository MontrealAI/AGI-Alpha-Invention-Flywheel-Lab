"""Synthetic changes to a real registered claim, independent of live websites."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SPEC = spec_from_file_location("opportunity_source_verifier", Path(__file__).with_name("verify.py"))
verify = module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class SourceChange(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.path = self.directory / "study.html"
        self.claim = "Under advance knowledge of task costs"
        self.original = f"<article>{self.claim}</article>".encode()
        self.row = {"id": "study", "excerpt": self.claim,
                    "acquisition": {"sha256": verify.digest(self.original)}}

    def test_changed_navigation_preserves_the_passage(self):
        self.path.write_bytes(self.original + b"<nav>Home</nav>")
        result = verify.check_page(self.row, self.directory)
        self.assertFalse(result["exact_http_body"])
        self.assertTrue(result["registered_excerpt_present"])

    def test_withdrawn_passage_in_script_cannot_keep_source_support(self):
        self.path.write_text(f"<article>Withdrawn</article><script>let archived = '{self.claim}'</script>")
        result = verify.check_page(self.row, self.directory)
        self.assertFalse(result["exact_http_body"])
        self.assertFalse(result["registered_excerpt_present"])


if __name__ == "__main__":
    unittest.main()
