"""Opt-in Codex-assisted clean-room source reconstruction.

No agent is invoked without explicit disclosure permission. The agent receives
only selected behavioral observations, not the binary or the full replay set.
The independently re-run oracle is the sole acceptance authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from resurrect import Hold, _validated_observations, canonical, load, read_manifest, save, verify


def selected_examples(cases, limit=100):
    """Deterministic spread without showing every observation when possible."""
    if not cases:
        raise Hold("no observations")
    count = min(limit, max(1, len(cases) // 3))
    positions = sorted({int(i * (len(cases) - 1) / max(1, count - 1)) for i in range(count)})
    return [cases[i] for i in positions]


def develop_with_codex(manifest_path, observations_path, output_path, *, authorize_disclosure=False, rounds=2):
    """Attempt agent-written replacement using the user's pre-authenticated Codex CLI.

    The agent can read samples but is not handed the binary or all domain outputs.
    Missing Codex, refused disclosure, runtime failures or mismatches are HOLD.
    """
    if not authorize_disclosure:
        raise Hold("external-model data disclosure not authorized; use deterministic synthesize")
    if type(rounds) is not int or not 1 <= rounds <= 5:
        raise Hold("agent rounds must be 1 to 5")
    codex = shutil.which("codex")
    if not codex:
        raise Hold("Codex CLI not installed; requires a separately authenticated local Codex session")
    manifest = read_manifest(manifest_path)
    observations = load(observations_path)
    cases = _validated_observations(manifest, observations)
    examples = selected_examples(cases)
    # No oracle path or binary is included in the proposed agent workspace.
    public_manifest = {"schema": manifest["schema"], "name": manifest["name"],
                       "axes": manifest["axes"], "protocol": "JSON object per stdin line; one JSON output per line"}
    result = {"status": "HOLD_NO_ACCEPTED_CANDIDATE", "attempts": 0,
              "observed_examples_shared": len(examples), "candidate": None,
              "qualification": "AGENT_PATH_NOT_TESTED_BY_REPOSITORY_CI"}
    with tempfile.TemporaryDirectory(prefix="resurrect-codex-") as base:
        workspace = Path(base)
        workspace.chmod(0o700)
        save(workspace / "public_contract.json", public_manifest)
        save(workspace / "examples.json", examples)
        prompt = (
            "Reconstruct a maintainable, standalone Python 3 CLI replacement for the "
            "rights-authorized JSONL program described by public_contract.json. "
            "Use ONLY examples.json and public_contract.json as evidence; do not search the "
            "operator's filesystem, retrieve original binaries, open network connections, "
            "or request secrets. Create exactly solution.py in this workspace. "
            "Read a JSON object per stdin line and print one JSON object per stdout line. "
            "The true reference is checked externally; never claim tests pass unless measured. "
            "Do not use third-party libraries. Refuse out-of-domain inputs. "
            "A rule-based/generalizable implementation is preferable to hard-coding samples. "
            "Read feedback.json when present and repair mismatches without changing the API."
        )
        for attempt in range(1, rounds + 1):
            # Minimal permissions; this is not a hard OS sandbox boundary.
            command = [codex, "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
                       "--cd", str(workspace), "--ephemeral", prompt]
            try:
                done = subprocess.run(command, cwd=workspace, text=True, capture_output=True,
                                      timeout=3600, check=False)
            except (OSError, subprocess.TimeoutExpired) as err:
                raise Hold(f"Codex invocation failed or timed out: {err}") from err
            result["attempts"] = attempt
            if done.returncode != 0:
                raise Hold(f"Codex CLI failed (exit {done.returncode}); inspect local Codex authentication")
            candidate = workspace / "solution.py"
            if not candidate.is_file() or candidate.stat().st_size > 1_000_000:
                raise Hold("agent did not write a bounded solution.py")
            # Default Docker is not bypassable from this path.
            verdict = verify(manifest_path, candidate, unsafe_local=False)
            result["verdict"] = verdict
            if verdict["status"] == "PASS_FINITE_DOMAIN":
                dest = Path(output_path).resolve()
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, dest)
                result.update({"status": "AGENT_CANDIDATE_FINITE_DOMAIN_ACCEPTED",
                               "candidate": str(dest), "qualification": "DOCKER_REPLAY_OF_DECLARED_SCOPE_ONLY"})
                return result
            save(workspace / "feedback.json", {"status": verdict["status"],
                                                "example_counterexamples": verdict["mismatches"]})
    return result
