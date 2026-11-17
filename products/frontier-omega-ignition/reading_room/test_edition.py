import json
import shutil
import tempfile
import unittest
from pathlib import Path

from edition import build, locate, normalized, read_source


def sample_pdf():
    """A small born-digital document for exercising Poppler and delivery paths."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] "
        b"/Contents 4 0 R /Resources << /Font << /F 5 0 R >> >> >>",
    ]
    contents = b"BT /F 14 Tf 40 740 Td (One attested sentence.) Tj ET\n"
    objects += [b"<< /Length " + str(len(contents)).encode() + b" >>\nstream\n"
                + contents + b"endstream",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(data)


class ReadingEditionTest(unittest.TestCase):
    def test_location_requires_one_distinct_page(self):
        def result(value, pages):
            return locate({"text": value}, [normalized(page) for page in pages])
        self.assertEqual(result("The fee", ["The fee. The fee.", "Their fee."])["page"], 1)
        self.assertEqual(result("The fee", ["The fee.", "The fee!"])["candidate_pages"], [1, 2])
        for value, pages in [("The fee", ["The", "fee"]), ("case", ["Cases"]), ("10", ["−10"]),
                             ("5", ["0.5"]), ("10", ["10.05"]), ("Yield 5.", ["Yield 5.05"]),
                             ("90", ["90%"])]:
            with self.subTest(value=value, pages=pages):
                self.assertEqual(result(value, pages)["status"], "missing")
        self.assertEqual(result("The office", ["The\n oﬃce"])["status"], "matched")
        self.assertEqual(result("1.5", ["1.5 on page one", "11.5 on page two"])["page"], 1)

    def test_html_semantics_without_active_content(self):
        html = """<html lang="fr"><title>Une édition</title><p>Outside</p>
        <main><nav><p>Index</p></nav><section><h2>Première <em>section</em></h2>
        <p>Un &amp; deux<br>trois<span hidden>quatre</span>.<script>oops()</script></p>
        <p>Look <img alt="graphic"></p><p hidden>hidden</p></section></main></html>"""
        title, lang, rows, selection = read_source(html, "html")
        self.assertEqual((title, lang), ("Une édition", "fr"))
        self.assertEqual([r["text"] for r in rows], ["Première section", "Un & deux trois.", "Look"])
        self.assertEqual(rows[0]["level"], 2)
        self.assertEqual(selection, {"scope": "main", "embedded_blocks": 1})
        self.assertEqual(locate(rows[2], ["Look"])["reason"], "embedded_content_requires_review")
        _, _, math_rows, _ = read_source("<p>Result: <math><mi>x</mi></math></p><p><img></p>", "html")
        self.assertEqual([r["text"] for r in math_rows], ["Result: x", ""])
        self.assertTrue(all(locate(row, ["Result: x"])["page"] is None for row in math_rows))
        _, lang, rows, selection = read_source("<body><h1>T</h1><p>Body</p></body>", "html")
        self.assertEqual((lang, selection["scope"], rows[1]["text"]), ("und", "body", "Body"))
        with self.assertRaises(ValueError):
            read_source('{"title":"T","blocks":[{"kind":"heading","text":"T","level":false}]}', "json")

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler")
    def test_delivery_and_failed_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "manuscript.json"
            original = {"title": "Read & inspect", "language": "en", "blocks": [
                {"kind": "paragraph", "text": "One attested sentence."},
                {"kind": "paragraph", "text": "<script>alter()</script>"}]}
            source.write_text(json.dumps(original))
            pdf = base / "input.pdf"
            pdf.write_bytes(sample_pdf())
            out = base / "first"
            summary = build(pdf, source, out)
            self.assertEqual(summary, {"matched": 1, "ambiguous": 0, "missing": 1, "total": 2})
            self.assertEqual((out / "source.pdf").read_bytes(), pdf.read_bytes())
            self.assertEqual((out / "manuscript.original.txt").read_bytes(), source.read_bytes())
            html = (out / "index.html").read_text()
            self.assertIn('href="source.pdf#page=1"', html)
            self.assertIn("&lt;script&gt;alter()&lt;/script&gt;", html)
            self.assertNotIn("<script>", html)
            second = base / "second"
            second.mkdir()
            build(out / "source.pdf", out / "manuscript.original.txt", second, "json")
            for name in ("index.html", "receipt.json"):
                self.assertEqual((out / name).read_bytes(), (second / name).read_bytes())
            with self.assertRaises(ValueError):
                build(pdf, source, out)
            source.write_text("{}")
            with self.assertRaises(ValueError):
                build(pdf, source, base / "failed")
            self.assertFalse((base / "failed").exists())


if __name__ == "__main__":
    unittest.main()
