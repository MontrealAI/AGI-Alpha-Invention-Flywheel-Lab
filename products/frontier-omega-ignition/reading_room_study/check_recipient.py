"""Verify exact original HTML recovery and delivery after serializer correction."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from run import ROOT


INSERT = re.compile(rb'<meta data-rr-added="policy" [^>]+ />|<a data-rr-added="[0-9]+" [^>]+>\[PDF p\. [0-9]+\]</a>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    trial = parser.parse_args().trial
    report = json.loads((trial/"SUCCESSOR_RESULTS.json").read_text())
    attest = {}
    for name, result in report["results"].items():
        original = (ROOT/"docs/research"/f"{name}.html").read_bytes()
        rich = (trial/name/"candidate/annotated-author.html").read_bytes()
        baseline = (trial/name/"direct/annotated-author.html").read_bytes()
        restored, count = INSERT.subn(b"", rich)
        success = (restored == original and rich == baseline and all(result["negative_controls"].values())
                   and result["verdicts"]["annotated"]["accepted"]
                   and count == result["verdicts"]["annotated"]["correct"] + 1)
        attest[name] = {"accepted": success, "exact_original_html_bytes_restored": restored == original,
                        "insertions": count, "direct_bytes_identical": baseline == rich,
                        "correct_links": result["verdicts"]["annotated"]["correct"],
                        "wrong_links": result["verdicts"]["annotated"]["wrong"],
                        "total": result["verdicts"]["annotated"]["total"],
                        "html_sha256": hashlib.sha256(rich).hexdigest()}
    observed = {"study": "RR-02 recipient correction",
                "original_observation": "SUCCESSOR_RESULTS.json",
                "annotator_sha256": report["files_sha256"]["annotate.py"],
                "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "results": attest}
    with (trial/"RECIPIENT_QUALIFICATION.json").open("x") as fh:
        json.dump(observed,fh,indent=2); fh.write("\n")
    if not all(record["accepted"] for record in attest.values()):
        raise SystemExit("Exact markup recovery failed.")


if __name__ == "__main__":
    main()
