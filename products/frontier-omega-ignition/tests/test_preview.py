import base64
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import build_preview as preview


class Parts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = {}
        self.part = None
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.part = "records" if attrs.get("type") == "application/json" else "script"
        elif tag == "style":
            self.part = tag
        elif tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.parts["policy"] = attrs["content"]
        for key in ("href", "src", "action"):
            if key in attrs and not attrs[key].startswith("#"):
                self.resources.append(attrs[key])

    def handle_data(self, data):
        if self.part:
            self.parts[self.part] = self.parts.get(self.part, "") + data

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.part = None


class PreviewTests(unittest.TestCase):
    def test_exact_public_payloads_determinism_and_offline_policy(self):
        artifact = preview.render()
        self.assertEqual(artifact, preview.render())
        parsed = Parts()
        parsed.feed(artifact)
        self.assertEqual(parsed.resources, [])
        blocks = parsed.parts
        for name in ("script", "style"):
            self.assertIn(preview.csp_hash(blocks[name]), blocks["policy"])
        self.assertIn("connect-src 'none'", blocks["policy"])
        self.assertIn("default-src 'none'", blocks["policy"])
        for capability in ("fetch(", "XMLHttpRequest", "WebSocket", "/api/", "sessionStorage", "localStorage"):
            self.assertNotIn(capability, blocks["script"])
        recordings = json.loads(blocks["records"])
        self.assertEqual([rec["id"] for rec in recordings], list(preview.PUBLIC))
        for rec in recordings:
            name = rec["id"]
            raw = preview.regular(f"evidence/{name}-run.json")
            self.assertEqual(rec["run_sha256"], sha256(raw).hexdigest())
            self.assertEqual(rec["run"], json.loads(raw))
            if name == "unsupported":
                self.assertNotIn("archive", rec)
            else:
                archive = base64.b64decode(rec["archive"], validate=True)
                self.assertEqual(archive, preview.regular(f"evidence/{name}-artifact.zip"))
                self.assertEqual(sha256(archive).hexdigest(), rec["archive_sha256"])

    def test_inert_strings_cannot_create_elements(self):
        sample = {"witness": "</script><img src=x><script>1&2</script>\u2028"}
        encoded = preview.inert_json(sample)
        self.assertNotIn("<", encoded)
        self.assertNotIn("&", encoded)
        self.assertEqual(json.loads(encoded), sample)

    def test_unrelated_private_sources_and_forged_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            (repo / "web").mkdir()
            (repo / "evidence").mkdir()
            for name in ("preview.html", "style.css", "app.js", "preview.js"):
                shutil.copyfile(preview.PRODUCT / "web" / name, repo / "web" / name)
            names = ["recipient-checks.json"]
            for name, (_, _, archive) in preview.PUBLIC.items():
                names.append(f"{name}-run.json")
                if archive:
                    names.append(f"{name}-artifact.zip")
            for name in names:
                shutil.copyfile(preview.PRODUCT / "evidence" / name, repo / "evidence" / name)
            secret = "UNRELATED_PRIVATE_MISSION_SENTINEL_0319"
            (repo / "evidence" / "private-run.json").write_text(secret)
            with patch.object(preview, "PRODUCT", repo):
                self.assertNotIn(secret, preview.render())
                source = repo / "evidence" / "integrity-run.json"
                sibling = repo / "evidence" / "private-copy.json"
                source.rename(sibling)
                source.symlink_to(sibling)
                with self.assertRaisesRegex(ValueError, "regular repository"):
                    preview.render()
                source.unlink()
                changed = sibling.read_bytes().replace(b"reviewer", b"reader")
                source.write_bytes(changed)
                with self.assertRaisesRegex(ValueError, "digest mismatch"):
                    preview.render()
                receipt = repo / "evidence" / "recipient-checks.json"
                forged = json.loads(receipt.read_bytes())
                next(c for c in forged["cases"] if c["mission"] == "integrity")["run_evidence_sha256"] = sha256(changed).hexdigest()
                receipt.write_text(json.dumps(forged))
                with self.assertRaisesRegex(ValueError, "recipient receipt mismatch"):
                    preview.render()
