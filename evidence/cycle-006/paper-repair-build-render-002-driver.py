"""Trusted final paper compile and render within one enclosing resource run."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(ROOT / 'scripts/build_cycle006_paper.py'), '--markdown', 'docs/research/cycle-006.md', '--manifest', 'docs/research/cycle-006.inputs.json'], cwd=ROOT, check=True, timeout=40)
subprocess.run(['/usr/bin/pdftoppm', '-r', '120', '-png', str(ROOT / 'docs/research/cycle-006.pdf'), str(ROOT / 'evidence/cycle-006/paper-repair-build-render-002-run/page')], cwd=ROOT, check=True, timeout=40)
