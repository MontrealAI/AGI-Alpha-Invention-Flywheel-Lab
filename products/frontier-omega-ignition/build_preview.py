"""Build the offline, public IGNITION evidence edition from reviewed repository files."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

PRODUCT = Path(__file__).resolve().parent
# Independently pin the public exports. A new receipt or an arbitrary private
# workspace snapshot cannot authorize itself for inclusion in the preview.
PUBLIC = {
    "integrity": ("Inspect a research release",
                  "df8bfda09f864dd6b655f0ef1fc9cbcfd95e4d9abc89f0f65fbc03b774f35b6f",
                  "5bd2cb3fb853cb45229ae1ba106f3f3d90a05fb341aad9511932ff8e348a2730"),
    "migration": ("Migrate the Blue Sky candidate register",
                  "18042d86bbb2d2c2410bfe0c40a5e8107e25d1ec904d3dedeffc5199e1a81eea",
                  "6aeed44d96b0aa72ecacd037a08179f07eed428eff7fa31c9a8659bba4626fd6"),
    "unsupported": ("Qualify a physical contact surface",
                    "10dc8e7e586c1c71ec230aaf9620e5d747f55ba6fd079d8f0942c537abaefe9c", None),
}


def regular(relative):
    file = PRODUCT / relative
    if file.resolve(strict=True) != file or not file.is_file():
        raise ValueError(f"Preview inputs must be regular repository files: {relative}")
    return file.read_bytes()


def checked(relative, digest):
    raw = regular(relative)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"Reviewed public digest mismatch: {relative}")
    return raw


def inert_json(value):
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return encoded.replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")


def exactly_once(document, marker, replacement):
    if document.count(marker) != 1:
        raise ValueError(f"Reviewed web source marker changed: {marker}")
    return document.replace(marker, replacement)


def csp_hash(value):
    return "'sha256-" + base64.b64encode(hashlib.sha256(value.encode()).digest()).decode() + "'"


def render():
    receipts = json.loads(regular("evidence/recipient-checks.json"))["cases"]
    bundle = []
    for name, (title, run_hash, zip_hash) in PUBLIC.items():
        matches = [case for case in receipts if case["mission"] == name]
        if (len(matches) != 1 or matches[0]["run_evidence_sha256"] != run_hash
                or matches[0].get("bundle_sha256") != zip_hash):
            raise ValueError(f"Public recipient receipt mismatch: {name}")
        record = json.loads(checked(f"evidence/{name}-run.json", run_hash))
        if record.get("handoff") is not None or record["status"] != ("verified" if zip_hash else "deferred"):
            raise ValueError(f"Unexpected public run status or pending handoff: {name}")
        item = dict(id=name, title=title, run=record, run_sha256=run_hash)
        if zip_hash:
            item.update(archive_sha256=zip_hash, archive=base64.b64encode(
                checked(f"evidence/{name}-artifact.zip", zip_hash)).decode())
        bundle.append(item)

    html = regular("web/preview.html").decode()
    style = regular("web/style.css").decode()
    app = regular("web/app.js").decode()
    start, end = "// BEGIN SHARED READ-ONLY EVIDENCE VIEW\n", "// END SHARED READ-ONLY EVIDENCE VIEW\n"
    if app.count(start) != 1 or app.count(end) != 1 or app.index(start) >= app.index(end):
        raise ValueError("Shared read-only renderer markers changed")
    script = '"use strict";\n' + app.split(start, 1)[1].split(end, 1)[0] + regular("web/preview.js").decode()
    if "</script" in script.lower() or "</style" in style.lower():
        raise ValueError("Unexpected closing tag in reviewed renderer assets")
    policy = ("default-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; "
              f"script-src {csp_hash(script)}; style-src {csp_hash(style)}")
    html = exactly_once(html, "<!-- SECURITY_POLICY -->", f'<meta http-equiv="Content-Security-Policy" content="{policy}">')
    html = exactly_once(html, "<!-- STYLE -->", f"<style>{style}</style>")
    html = exactly_once(html, "<!-- RENDERER -->", f"<script>{script}</script>")
    return exactly_once(html, "<!-- EVIDENCE -->", '<script id="public-preview-data" type="application/json">'
                        + inert_json(bundle) + "</script>")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new standalone HTML file")
    args = parser.parse_args()
    html = render().encode()
    with args.output.open("xb") as output:
        output.write(html)
    print(f"{args.output}  {len(html)} bytes  sha256 {hashlib.sha256(html).hexdigest()}")


if __name__ == "__main__":
    main()
