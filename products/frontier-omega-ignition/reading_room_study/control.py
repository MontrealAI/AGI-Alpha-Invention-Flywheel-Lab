"""Five adversarial blocks over a deterministic two-page, text-native PDF."""

import json
from pathlib import Path


UNIQUE_A = "Aster systems received 47 sealed units."
UNIQUE_B = "Cobalt systems returned 18 sealed units."
REPEATED = "Reference conditions apply on both pages."
ABSENT = UNIQUE_A.replace("47", "74")
LEFT = "This passage begins here and"
RIGHT = "ends on the following page."
BLOCKS = [UNIQUE_B, REPEATED, ABSENT, LEFT + " " + RIGHT, UNIQUE_A]
EXPECTED = [("matched", [2]), ("ambiguous", [1, 2]), ("missing", []),
            ("missing", []), ("matched", [1])]


def write_inputs(directory: Path):
    # Minimal static PDF using real native text and a cross-reference table.
    rows = [[UNIQUE_A, REPEATED, LEFT], [RIGHT, REPEATED, UNIQUE_B]]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 2 /Kids [4 0 R 6 0 R] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for number, lines in zip((5, 7), rows):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {number} 0 R >>".encode())
        text = "BT /F1 12 Tf 72 720 Td 20 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
        data = text.encode("ascii")
        objects.append(f"<< /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream")
    buffer = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        buffer.extend(f"{offset:010} 00000 n \n".encode())
    buffer.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    (directory / "control.pdf").write_bytes(buffer)
    (directory / "control.json").write_text(json.dumps({
        "title": "Receipt control", "language": "en",
        "blocks": [{"kind": "paragraph", "text": text} for text in BLOCKS],
    }, indent=2), encoding="utf-8")
