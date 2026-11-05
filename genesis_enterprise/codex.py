"""Optional installed Codex proposer; ChatGPT authentication only, no API fallback.

Only unqualified JSON hypotheses are returned. No candidate code is executed.
Transport is independently testable. A live round trip is a separate test.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .policy import canonical, digest, loads
from .frontier import proposal_prompt, proposal_schema, validate_hypotheses


def command(executable, folder, model):
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', model):
        raise ValueError('EXPLICIT_ACCESSIBLE_MODEL_IDENTIFIER_REQUIRED')
    return [executable, 'exec', '--ignore-user-config', '--sandbox', 'read-only',
            '--skip-git-repo-check', '--json', '--model', model,
            '--output-schema', str(folder / 'schema.json'), '-o', str(folder / 'answer.json'),
            '-c', 'forced_login_method="chatgpt"', '-c', 'model_provider="openai"',
            '-c', 'approval_policy="never"', '-c', 'web_search="disabled"',
            '-c', 'features.shell_tool=false', '-c', 'features.view_image=false',
            '-c', 'features.skill_mcp_dependency_install=false',
            '-c', 'apps._default.enabled=false', '-c', 'plugins._default.enabled=false',
            '-c', 'mcp_servers={}', '-']


def propose(objective, observations, output, model, *, runner=None, executable=None):
    """Call only on an explicit propose action. Never install/login or buy access."""
    output = Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('NEW_REGULAR_PROPOSAL_OUTPUT_REQUIRED')
    if executable is None:
        executable = shutil.which('codex')
    if not executable:
        raise RuntimeError('CODEX_NOT_INSTALLED_NO_PROVIDER_FALLBACK')
    runner = subprocess.run if runner is None else runner
    # Keep saved managed ChatGPT auth in the user's CLI; do not read tokens.
    # Remove provider keys, endpoint overrides and unrelated credential variables.
    environment = {k: v for k, v in os.environ.items() if k in
                   {'PATH', 'HOME', 'CODEX_HOME', 'TMPDIR', 'TEMP', 'TMP', 'SYSTEMROOT', 'LANG', 'LC_ALL'}}
    prompt = proposal_prompt(objective, observations)
    with tempfile.TemporaryDirectory(prefix='genesis-proposal-') as tmp:
        folder = Path(tmp)
        (folder / 'schema.json').write_bytes(canonical(proposal_schema()))
        # --ignore-user-config avoids user MCP/hook setup in this isolated run.
        # Managed platform restrictions remain authoritative; a conflict fails.
        cmd = command(executable, folder, model)
        result = runner(cmd, input=prompt, text=True, capture_output=True,
                        cwd=folder, env=environment, check=False)
        if result.returncode != 0:
            raise RuntimeError('CODEX_PROPOSAL_FAILED_NO_API_FALLBACK')
        answer = folder / 'answer.json'
        if answer.is_symlink() or not answer.is_file() or answer.stat().st_size > 2_000_000:
            raise ValueError('BOUNDED_REGULAR_MODEL_OUTPUT_REQUIRED')
        hypotheses = validate_hypotheses(loads(answer.read_bytes()))
        usage = None
        for line in result.stdout.splitlines():
            try:
                event = loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(event, dict) and event.get('type') == 'turn.completed':
                usage = event.get('usage')
        receipt = {'schema': 'genesis/codex-proposals/v1', 'requested_model': model,
            'actual_model_identity': 'NOT_INDEPENDENTLY_ATTESTED', 'authentication_policy': 'CHATGPT_ONLY',
            'prompt_sha256': digest(prompt), 'observations_sha256': digest(observations),
            'hypotheses': hypotheses['hypotheses'], 'reported_usage': usage,
            'access_or_commercial_qualification_granted': False}
        with output.open('xb') as stream:
            stream.write(canonical(receipt))
        return receipt
