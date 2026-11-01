from pathlib import Path
import argparse
import hashlib
import json

EDITION = Path('docs/transformational063')
CAMPAIGN = Path('campaign/transformational-063')


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('UNSAFE_PUBLICATION_PATH')
    target = root / relative
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root):
        raise ValueError('MISSING_OR_UNSAFE_PUBLICATION_FILE:' + name)
    return target


def required_paths(root):
    names = ['paper.pdf', 'paper.tex', 'finance-results.tex', 'references.bib',
             'technical-results.pdf', 'make_figures.py', 'REPORT.md', 'SOURCE_REVIEW.md',
             'source-provenance.json', 'PDF_QA.json']
    paths = {str(EDITION / name) for name in names}
    paths.update(str(CAMPAIGN / name) for name in ['ADMISSION.md', 'LESSONS.md', 'README.md', 'TECHNICAL.json', 'REGRESSION_RECEIPT.json'])
    for directory in [root / CAMPAIGN / 'native', root / CAMPAIGN / 'direct-generalist']:
        for path in directory.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                paths.add(str(path.relative_to(root)))
    return paths


def verify(root):
    root = Path(root).resolve()
    metadata = read_json(root / EDITION / 'publication.json')
    if metadata['schema'] != 'transformational063/publication/v1' or set(metadata['sha256']) != required_paths(root):
        raise ValueError('PUBLICATION_FILE_COVERAGE_CHANGED')
    for name, expected in metadata['sha256'].items():
        if sha(safe_file(root, name)) != expected:
            raise ValueError('PUBLICATION_BYTES_CHANGED:' + name)
    pdf = root / EDITION / 'paper.pdf'
    qa = read_json(root / EDITION / 'PDF_QA.json')
    if not pdf.read_bytes().startswith(b'%PDF-') or qa['pdf_sha256'] != sha(pdf):
        raise ValueError('PDF_QA_BINDING_CHANGED')
    if qa['visual_review'] != 'all_pages_rendered_and_inspected' or qa['visual_defects_found'] != 0:
        raise ValueError('ACTUAL_VISUAL_QA_REQUIRED')
    if qa['pages'] < 1 or len(qa['rendered_page_sha256']) != qa['pages'] or qa['latex_overfull_boxes'] or qa['undefined_references']:
        raise ValueError('PDF_QA_INCOMPLETE')
    technical = read_json(root / CAMPAIGN / 'TECHNICAL.json')
    for name, expected in technical['source_files_sha256'].items():
        if sha(safe_file(root, name)) != expected:
            raise ValueError('TECHNICAL_SOURCE_CHANGED:' + name)
    regression = read_json(root / CAMPAIGN / 'REGRESSION_RECEIPT.json')
    for name, expected in regression['test_source_sha256'].items():
        if sha(safe_file(root, name)) != expected:
            raise ValueError('RECORDED_REGRESSION_SOURCE_CHANGED:' + name)
    native = root / CAMPAIGN / 'native'
    if (native / 'private').exists() or any('adaptive-simulation-key' in p.name for p in native.rglob('*')):
        raise ValueError('PRIVATE_RECOVERY_NOT_PUBLICATION')
    source = read_json(native / 'SOURCE.json')
    for name, expected in source['files'].items():
        if sha(safe_file(root, name)) != expected or sha(safe_file(native / 'source', name)) != expected:
            raise ValueError('NATIVE_CURRENT_OR_FROZEN_SOURCE_CHANGED:' + name)
    report = read_json(native / 'REPORT.json')
    audit = read_json(native / 'AUDIT.json')
    if report['source_sha256'] != source['sha256'] or not audit['accepted'] or set(audit['scenarios']) != set(report['scenarios']):
        raise ValueError('NATIVE_RECORDED_AUDIT_BINDING_CHANGED')
    if report['primary_seed_microUSD'] != 100_000_000_000 or report['real_customers'] != 0:
        raise ValueError('EXPERIMENT_SCOPE_CHANGED')
    receipt = {'accepted': True, 'schema': 'transformational063/publication-check/v1',
               'pdf_sha256': sha(pdf), 'pages': qa['pages'], 'native_source_sha256': source['sha256'],
               'scope': 'Publication bytes, current/frozen source and recorded visual/audit bindings; native operating audit is a separate replay.'}
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), sort_keys=True))
