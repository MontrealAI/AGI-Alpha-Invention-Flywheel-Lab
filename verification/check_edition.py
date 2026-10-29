"""Check published source/evidence identities and decision consistency, not scientific novelty."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "campaign/cycle-001/EDITION_SHA256.json").read_text())
    for name, expected in manifest.items():
        path = ROOT / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Edition identity mismatch: " + name)
    run = ROOT / "evidence/cycle-001/connected-run-02"
    report = json.loads((run / "REPORT.json").read_text())
    successor = json.loads((run / "SUCCESSOR.json").read_text())
    exchange = json.loads((run / "exchange/EXCHANGE.json").read_text())
    if not report["independent_checks_passed"] or not report["criticism_repaired"] or report["independent_checks"] != 33:
        raise ValueError("Recorded engineering verdict differs")
    if not successor["ordinary_reuse_equal"] or successor["causal_experience_advantage"] != "NOT_ESTABLISHED":
        raise ValueError("Successor decision differs")
    if hashlib.sha256((run / "SUCCESSOR.json").read_bytes()).hexdigest() != exchange["actualReport"]["fileSha256"]:
        raise ValueError("Exchange payload is not the recorded successor")
    if exchange["snapshot"]["revenue"] or exchange["snapshot"]["unrestrictedEarned"] or not report["no_statistical_confirmation"]:
        raise ValueError("Economic or confirmation verdict differs")
    pdf = ROOT / "docs/research/cycle-001.pdf"
    if not pdf.read_bytes().startswith(b"%PDF-"):
        raise ValueError("Research PDF absent")
    print(json.dumps({"edition_files_verified": len(manifest), "evidence_consistent": True,
                      "commercial_success": False, "ordinary_reuse_parity": True}))


if __name__ == "__main__":
    main()
