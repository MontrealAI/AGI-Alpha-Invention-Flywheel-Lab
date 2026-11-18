"""Cross-check every decoded field, including cutouts, with the independent fastavro library."""
import gzip
from io import BytesIO
from pathlib import Path
import unittest

try:
    import fastavro
except ImportError:
    fastavro = None
if __package__:
    from .avro_packet import record
else:
    from avro_packet import record


@unittest.skipIf(fastavro is None, "optional fastavro is required for this independent decoder check")
class FormatCheck(unittest.TestCase):
    def test_all_fields_against_external_library(self):
        for path in sorted((Path(__file__).parent/"sources").glob("*.avro.gz")):
            with self.subTest(file=path.name):
                raw = gzip.decompress(path.read_bytes())
                self.assertEqual([record(raw)], list(fastavro.reader(BytesIO(raw))))


if __name__ == "__main__":
    unittest.main()
