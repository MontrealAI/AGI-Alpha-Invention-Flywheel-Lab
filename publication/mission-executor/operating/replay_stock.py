"""Replay both saved portable artifacts against an ordinary comparison."""
import json
from pathlib import Path

from bridge.instruments import evaluate
from bridge.workflows import portable_digest


root = Path(__file__).resolve().parent
checkpoint = json.loads((root / "FRENCH-PREVIEW-CHECKPOINT.json").read_bytes())
assert portable_digest({k: v for k, v in checkpoint.items() if k != "sha256"}) == checkpoint["sha256"]
preview = json.loads(checkpoint["files"]["stock_alert.json"])
direct = json.loads((root / "direct-stock/REPAIR-RESULT.json").read_bytes())["instrument"]
controls = json.loads((root / "direct-stock/COMPARISON-PLAN.json").read_bytes())["controls"]
for name, artifact in (("executor", preview), ("direct after repair", direct)):
    for case in controls:
        stock, seuil = case["stock"], case["seuil"]
        actual = evaluate(artifact, {"stock": stock, "seuil": seuil})["output"]
        assert actual == {"alerte": stock < seuil}
    print(name, len(controls), "matched")
