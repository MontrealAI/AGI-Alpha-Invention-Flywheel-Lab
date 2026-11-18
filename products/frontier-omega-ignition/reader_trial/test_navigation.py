"""Score the RR-N1 registration using the actual generated scientific index."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
import materials

LINES = (
    "Measured −5.02 mol. Yield 90%. Bound x ≤ 5. Energy 2e−3 J.",
    "Measured +5.02 mol. Yield 90. Bound 5 ≤ x. Energy 2e+3 J.",
    "Measured 5.2 mol. Yield 90.5%. Bound x ≥ 5. Energy 2e3 J.",
    "Measured 5 mol. Yield 190%. Bound x < 5. Energy 12e−3 J.",
)


def fixture_packet(work):
    pdf = work / "fixture.pdf"
    html = work / "fixture.html"
    html.write_text("<html lang='en'><title>Scientific navigation test</title></html>")
    # Avoid an external font dependency. MuPDF's bundled CJK fallback covers
    # the ASCII, minus and inequality glyphs used in these four controlled lines.
    font = pymupdf.Font(fontname="cjk")
    with pymupdf.open() as doc:
        for line in LINES:
            page = doc.new_page()
            writer = pymupdf.TextWriter(page.rect)
            writer.append((30, 50), line, font=font, fontsize=12)
            writer.write_text(page)
        doc.save(pdf)
    spec = {"paper":"fixture", "html_sha256":materials.sha(html), "pdf_sha256":materials.sha(pdf), "pdf_pages":len(LINES)}
    with patch.object(materials, "RESEARCH", work), patch.dict(materials.REG["languages"], en=spec):
        materials.build("en", "D", work / "packet")
    return work / "packet" / "index-pages.html"


def navigation_results(index):
    raw = subprocess.check_output(["node", str(materials.HERE / "navigation_check.cjs"), str(index)], text=True)
    return json.loads(raw)


def version_results(work):
    output = {}
    for lang in ("en", "fr"):
        files = materials.sources(lang)
        local = work / lang
        local.mkdir()
        for path in files.values():
            shutil.copyfile(path, local/path.name)
        with patch.object(materials, "RESEARCH", local):
            materials.build(lang, "D", local/"original")
            output[lang+".original"] = (local/"original"/"index-pages.html").is_file()
            for fmt, path in files.items():
                target = local/path.name
                data = bytearray(target.read_bytes())
                data[len(data)//2] ^= 1
                target.write_bytes(data)
                destination = local/("modified-"+fmt)
                try:
                    materials.build(lang, "D", destination)
                except ValueError as error:
                    output[lang+"."+fmt] = "identity differs" in str(error) and not destination.exists()
                else:
                    output[lang+"."+fmt] = False
                shutil.copyfile(path,target)
    return output


class NavigationTests(unittest.TestCase):
    def test_actual_packet_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            for result in navigation_results(fixture_packet(Path(temp))):
                with self.subTest(query=result["query"]):
                    self.assertEqual(result["observed"], result["expected"])

    def test_registered_source_version_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, passed in version_results(Path(temp)).items():
                with self.subTest(control=name):
                    self.assertTrue(passed)
