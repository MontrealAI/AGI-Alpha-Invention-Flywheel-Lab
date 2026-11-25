"""Create a detached evaluator copy of the exact operator-declared runtime source."""

from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess


BRIDGE = Path("products/alpha-genesis-harness/bridge")
SUPPORT = (
    Path("products/frontier-member-tools"),
    Path("docs/research/frontier-omega-alpha"),
    Path("publication/universal/game-theory"),
)


def filehash(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    p = ArgumentParser()
    p.add_argument("repo",type=Path)
    p.add_argument("declared",type=Path)
    p.add_argument("destination",type=Path)
    args = p.parse_args()
    source = args.repo.resolve()
    frozen = json.loads(args.declared.read_bytes())
    assert set(frozen) >= {"universal_missions.py","mission_contracts.py","mission_tools.py","workflows.py","adapters.py"}
    for name, expected in frozen.items():
        assert filehash(source / BRIDGE / name) == expected, f"Declared freeze differs: {name}"
    args.destination.mkdir(parents=True,exist_ok=False)
    manifest = {}
    all_sources = [
        *(source/BRIDGE).glob("*.py"),
        *(source/BRIDGE).glob("*.json"),
    ]
    # Only specific first-party native dependencies used in the held trials.
    # A read-only provenance scan is distinct from permitting model access.
    expected_deps = {"relational.py", "endpoint-screen.mjs",
                     "solve.py", "verify.py", "baselines.py", "observation.py"}
    for part in SUPPORT:
        for name in expected_deps:
            all_sources.extend((source/part).rglob(name))
    for path in sorted(set(all_sources)):
        assert path.is_file() and not path.is_symlink()
        relative = path.relative_to(source)
        target = args.destination / "source" / relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        digest = filehash(target)
        assert digest == filehash(path), f"Source changed during snapshot: {relative}"
        manifest[str(relative)] = digest
    for name, expected in frozen.items():
        assert manifest[str(BRIDGE/name)] == expected, f"Declared source changed: {name}"
    identity = {"created_at_utc":datetime.now(timezone.utc).isoformat(),
                "declared_backend_manifest_sha256":filehash(args.declared),
                "worktree_head_at_freeze":subprocess.check_output(["git","rev-parse","HEAD"],cwd=source,text=True).strip(),
                "included_files":len(manifest)}
    for name, content in (("FILES.json",manifest),("IDENTITY.json",identity)):
        (args.destination/name).write_text(json.dumps(content,indent=2,sort_keys=True)+"\n")
    print("Evaluator frozen manifest:",filehash(args.destination/"FILES.json"),"files",len(manifest))


if __name__=="__main__":
    main()
