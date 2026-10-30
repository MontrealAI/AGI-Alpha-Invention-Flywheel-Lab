"""Check immutable paper/source bindings and the separately recorded visual QA."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root):
    root = Path(root)
    paper = root / 'docs/commercial010'
    manifest = json.loads((paper / 'SOURCE_MANIFEST.json').read_bytes())
    checked = []
    for group, prefix in [('sources', root), ('generated_outputs', paper)]:
        for name, expected in manifest[group].items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts:
                raise ValueError('RELATIVE_PAPER_SOURCE_REQUIRED')
            source = prefix / p
            if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError('PAPER_BINDING_CHANGED ' + name)
            checked.append(name)
    raw = (paper / 'paper.pdf').read_bytes()
    if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-100:]:
        raise ValueError('COMPILED_PDF_REQUIRED')
    if '<!doctype html>' not in (paper / 'index.html').read_text().lower():
        raise ValueError('BROWSER_EDITION_REQUIRED')
    qa = json.loads((paper / 'PDF_QA.json').read_bytes())
    if qa['pdf_sha256'] != hashlib.sha256(raw).hexdigest() or qa['pages_inspected'] < 1 or qa['layout_defects']:
        raise ValueError('CURRENT_PDF_VISUAL_QA_REQUIRED')
    return {'source_bindings_checked': len(checked), 'pdf_sha256': hashlib.sha256(raw).hexdigest(),
            'pages_inspected': qa['pages_inspected'], 'scope': 'Document integrity and visual-QA record, not new commercial confirmation.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = check(a.root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2)
