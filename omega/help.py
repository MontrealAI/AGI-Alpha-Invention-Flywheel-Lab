from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

README = Path(__file__).with_name('README.md')
TOPICS = (
    ('output', 'Interrupted output and retries', r'output_exists|interrupted|interruption|retry|retries|partial output|fileexistserror'),
    ('resources', 'Resource checkpoints', r'resource_checkpoint|resource|memory|insufficient resources|budget'),
    ('external', 'External proposal handoff', r'external_proposal|external route|proposal file|model unavailable|provider unavailable|model unavailability|api key'),
    ('installation', 'Installation and runtime', r'modulenotfounderror|no module named|install|dependency|dependencies|python version|interpreter'),
    ('input', 'Invalid requests or rejected plans', r'exact_.*_required|integer_required|request_binding|quality_exceeded|capacity_exceeded|objective_mismatch|consent|invalid|malformed|jsondecodeerror|rejected plan|plan_dimensions'),
)


def _excerpt(document, section):
    lines = document.splitlines()
    heading = '### ' + section
    try:
        start = lines.index(heading)
    except ValueError:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('#')), len(lines))
    return {'file': 'omega/README.md', 'section': section, 'line': start + 1, 'excerpt': '\n'.join(lines[start:end]).strip()}


def diagnose(question):
    if type(question) is not str or not question.strip() or len(question) > 4096:
        raise ValueError('SHORT_ERROR_OR_QUESTION_REQUIRED')
    document = README.read_text(encoding='utf-8')
    matches = [(topic, section) for topic, section, pattern in TOPICS if re.search(pattern, question, re.IGNORECASE)]
    if len(matches) == 1:
        topic, section = matches[0]
        citation = _excerpt(document, section)
    else:
        topic, citation = 'unknown', None
    if citation is None:
        topic = 'unknown'
        citation = _excerpt(document, 'Unknown or unresolved issues')
    return {
        'schema': 'omega/local-doc-help/v1',
        'status': 'DOCUMENTED' if topic != 'unknown' else 'UNKNOWN',
        'topic': topic,
        'scope': 'DETERMINISTIC_DOCUMENT_LOOKUP_NOT_MODEL_DIAGNOSIS',
        'documentation_sha256': hashlib.sha256(document.encode()).hexdigest(),
        'citations': [citation] if citation else [],
        'next_step': 'Read the cited guidance and decide manually; no action has been executed.' if topic != 'unknown' else 'Stop the affected step, preserve inputs and outputs, and inspect the local error and README manually.',
        'network_calls': 0,
    }


def main():
    parser = argparse.ArgumentParser(description='Find documented local guidance without model calls or file uploads.')
    parser.add_argument('question', nargs='+')
    args = parser.parse_args()
    print(json.dumps(diagnose(' '.join(args.question)), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
