# SPDX-License-Identifier: Apache-2.0
"""Preserve exact, registered evidence fields in a French translation draft."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MARKER = re.compile(r'⟦E[0-9]{2,}⟧')


def canonical(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()


def fingerprint(data):
    return sha256(data).hexdigest()


def frozen_cases():
    registration = json.loads((HERE / 'REGISTRATION.json').read_bytes())
    raw = (HERE / 'INPUTS.json').read_bytes()
    if fingerprint(raw) != registration['english_inputs_sha256']:
        raise ValueError('Source notice registration changed')
    study = json.loads(raw)
    sources = {}
    for case in study['cases']:
        path = case['source_path']
        if path not in sources:
            sources[path] = subprocess.check_output(
                ['git', 'show', f"{study['source_commit']}:{path}"], cwd=ROOT
            )
        source = sources[path]
        if fingerprint(source) != case['source_sha256']:
            raise ValueError(f'Public source changed: {path}')
        line = source.decode().splitlines()[case['line'] - 1]
        if case['english'] not in line:
            raise ValueError(f'Exact source span missing: {case["id"]}')
    return registration, study['cases']


def prepare(case):
    english = case['english']
    if '⟦' in english or '⟧' in english:
        raise ValueError('Source collides with reserved translation markers')
    spans = []
    for i, field in enumerate(case['fields'], 1):
        value = field['en']
        if not value or english.count(value) != 1:
            raise ValueError('Protected source field must have a unique exact location')
        start = english.index(value)
        spans.append((start, start + len(value), f'⟦E{i:02d}⟧', field['fr']))
    translated_fields = {}
    parts = []
    previous = 0
    for start, stop, marker, target in sorted(spans):
        if start < previous or not target or '⟦' in target or '⟧' in target:
            raise ValueError('Protected source fields must not overlap or contain markers')
        parts.extend((english[previous:start], marker))
        translated_fields[marker] = target
        previous = stop
    parts.append(english[previous:])
    return ''.join(parts), translated_fields


def restore(case, response):
    _, fields = prepare(case)
    found = Counter(MARKER.findall(response))
    remainder = MARKER.sub('', response)
    if found != Counter(fields.keys()) or '⟦' in remainder or '⟧' in remainder:
        return {'status': 'HOLD_FIELDS', 'text': None,
                'expected': list(fields), 'found': dict(found)}
    if not response.strip():
        return {'status': 'HOLD_EMPTY', 'text': None}
    text = MARKER.sub(lambda match: fields[match[0]], response).strip()
    return {'status': 'DRAFT_FOR_BILINGUAL_REVIEW', 'text': text,
            'protected_fields': list(fields.values())}


def instruction(case, locked):
    prefix = ('Translate the following text into French. Only output the translated result '
              'without any additional explanation. Preserve every condition, measured quantity, '
              'language, decision status, and authorization limit. Use clear technical language. ')
    if locked:
        draft, fields = prepare(case)
        if fields:
            prefix += 'Copy each ⟦E00⟧-style marker exactly once with all delimiters and digits unchanged.'
    else:
        draft = case['english']
        if case['fields']:
            prefix += 'Use these exact renderings: ' + '; '.join(
                f'{field["en"]} → {field["fr"]}' for field in case['fields']
            ) + '.'
    return prefix.strip() + '\n\n' + draft


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('id')
    parser.add_argument('--reply', type=Path, help='Decode a saved model reply as a reviewable draft.')
    args = parser.parse_args()
    _, cases = frozen_cases()
    case = next((case for case in cases if case['id'] == args.id), None)
    if case is None:
        parser.error('Use one of the registered case IDs.')
    if args.reply is None:
        print(instruction(case, locked=True))
    else:
        with args.reply.open('rb') as stream:
            raw = stream.read(32_769)
        if len(raw) > 32_768:
            parser.error('Draft exceeds the registered experiment limit.')
        print(canonical(restore(case, raw.decode())).decode(), end='')


if __name__ == '__main__':
    main()
